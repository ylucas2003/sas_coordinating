"""Eventos de e-mail: bounces/complaints do SES e descadastro do destinatário.

Pré-requisito de qualquer envio em volume (docs/13 §4.6) e compromisso
assumido no caso da AWS: endereço que quica sai da lista sozinho, e quem não
quer receber tem como sair.

**Segurança do endpoint do SNS:** o SNS não manda header customizado, então a
autenticação é o token no path (`SES_WEBHOOK_TOKEN`) + o `TopicArn` conferido
contra o tópico esperado. A verificação de assinatura fica de fora por ora
(⬜ docs/13 §4.6): o pior que o endpoint faz é marcar um endereço como
inválido — reversível com um DELETE, e sem vazar nada.
"""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from ..config import get_settings
from ..lembretes import supressao
from ..lembretes.descadastro import token_valido
from ..supabase_client import get_supabase

router = APIRouter(tags=["email"])


@router.post("/email/eventos-ses/{token}")
async def eventos_ses(token: str, request: Request) -> dict[str, Any]:
    settings = get_settings()
    if not settings.ses_webhook_token or token != settings.ses_webhook_token:
        raise HTTPException(status_code=404, detail="não encontrado")

    payload: dict[str, Any] = await request.json()

    arn_esperado = settings.ses_sns_topic_arn
    if arn_esperado and payload.get("TopicArn") not in (None, arn_esperado):
        raise HTTPException(status_code=403, detail="tópico inesperado")

    tipo = payload.get("Type")

    # Handshake do SNS: confirmar é fazer um GET na URL que ele mandou. Só
    # depois disso o tópico começa a entregar de verdade.
    if tipo == "SubscriptionConfirmation":
        url = payload.get("SubscribeURL")
        if not url:
            raise HTTPException(status_code=400, detail="SubscribeURL ausente")
        async with httpx.AsyncClient(timeout=10) as http:
            await http.get(url)
        return {"status": "subscription_confirmada"}

    cliente = get_supabase()
    registrados = 0
    for endereco, motivo, detalhe in supressao.interpretar_evento_ses(payload):
        supressao.registrar_invalido(
            cliente, endereco=endereco, motivo=motivo, detalhe=detalhe
        )
        registrados += 1
    return {"status": "ok", "registrados": registrados}


_PAGINA = """<!doctype html><meta charset="utf-8">
<title>SAS — lembretes</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:34rem;margin:4rem auto;padding:0 1rem;color:#1f2937}}
h1{{font-size:1.25rem}} .ok{{color:#15803d}} .erro{{color:#b91c1c}}</style>
<h1 class="{classe}">{titulo}</h1><p>{texto}</p>"""


@router.get("/lembretes/descadastrar", response_class=HTMLResponse)
async def descadastrar(
    e: str = Query(..., description="endereço"),
    t: str = Query(..., description="assinatura HMAC"),
) -> HTMLResponse:
    """Link do rodapé de todo lembrete de aluno. Sem login: o HMAC prova que o
    link foi emitido por nós, e o efeito é só parar de mandar e-mail."""
    if not token_valido(e, t):
        return HTMLResponse(
            _PAGINA.format(
                classe="erro",
                titulo="Link inválido",
                texto="Este link de descadastro não confere. "
                      "Fale com a coordenação se continuar recebendo.",
            ),
            status_code=400,
        )
    supressao.registrar_invalido(
        get_supabase(), endereco=e, motivo="descadastro", detalhe="link do rodapé"
    )
    return HTMLResponse(
        _PAGINA.format(
            classe="ok",
            titulo="Pronto — você não receberá mais lembretes",
            texto=f"O endereço <strong>{e}</strong> foi removido dos lembretes "
                  "do SAS. Isso não afeta seu acesso à plataforma.",
        )
    )
