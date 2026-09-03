"""Endpoints de auditoria de planilhas — a ESCRITA foi aposentada.

A planilha foi como o projeto nasceu, e por isso a rota de upload existiu. Em
30/08/2026 a medição em produção mostrou `SELECT count(*) FROM upload` = **0**:
nem uma vez em toda a vida do sistema. As 102.143 notas entraram pelo sync do
Canvas ([docs/32 §2.4](../../../docs/32-plano-sprint-4.md)).

O problema não era a rota estar ociosa — era ela ser um **segundo escritor sem
arbitragem**. `nota.pontuacao` tem a disputa resolvida desde a `0024`
(`pontuacao_canvas`/`pontuacao_sas` + trigger), mas `nota.presente` não tem par
nenhum: quem escrevesse por último venceria, em silêncio. Fechar a porta faz a
pergunta de precedência **deixar de existir**, que é melhor que respondê-la.

⚠️ Aposentar aqui quer dizer **tirar do caminho de quem clica**, não apagar o
código. `app/ingest/` fica inteiro e roda por `scripts/importar_planilha.py` —
é o plano B se o Canvas cair, e o caminho de uma carga histórica. As rotas de
LEITURA continuam: o histórico de uploads é dado de auditoria.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..auth import get_current_coordenador
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(get_current_coordenador)],
)


# ─── Schemas de resposta ──────────────────────────────────────────────────


class RegistroUpload(BaseModel):
    id: str
    arquivo_origem: str
    status: str
    linhas_total: int | None = None
    linhas_aceitas: int | None = None
    linhas_rejeitadas: int | None = None
    resumo: dict[str, Any] | None = None
    criado_em: str
    finalizado_em: str | None = None


class EventoUpload(BaseModel):
    nivel: str
    mensagem: str
    linha_planilha: int | None = None
    coluna_planilha: str | None = None
    criado_em: str


class DetalheUpload(BaseModel):
    upload: RegistroUpload
    eventos: list[EventoUpload]


# ─── POST /uploads ────────────────────────────────────────────────────────


@router.post("", status_code=410)
async def receber_upload(
    arquivo: UploadFile = File(..., description="Planilha CSV ou XLSX exportada do Canvas."),
    autor: str | None = Form(default=None, description="Identificador de quem enviou."),
    salvar_no_storage: bool = Form(default=True),
) -> None:
    """410 Gone — a planilha deixou de ser caminho de entrada (docs/32 §2.4).

    A assinatura fica de pé de propósito: um cliente antigo que ainda poste
    recebe a explicação, e não um 404 que parece rota quebrada. O corpo do
    arquivo nem chega a ser lido.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            "A importação de planilha foi aposentada. Quem traz nota para o SAS é o "
            "sync do Canvas, que roda a cada 5 minutos. Para carga histórica, use "
            "`api/scripts/importar_planilha.py` — o mesmo pipeline, fora da requisição."
        ),
    )


# ─── GET /uploads ─────────────────────────────────────────────────────────


@router.get("", response_model=list[RegistroUpload])
async def listar_uploads(limite: int = 50) -> list[RegistroUpload]:
    """Histórico de uploads, mais recentes primeiro."""
    cliente = get_supabase()
    resposta = (
        cliente.table("upload")
        .select("*")
        .order("criado_em", desc=True)
        .limit(limite)
        .execute()
    )
    return [RegistroUpload(**linha) for linha in (resposta.data or [])]


# ─── GET /uploads/{id} ────────────────────────────────────────────────────


@router.get("/{upload_id}", response_model=DetalheUpload)
async def obter_upload(upload_id: str) -> DetalheUpload:
    """Detalhe de um upload + log de eventos (avisos, erros)."""
    cliente = get_supabase()

    upload_resp = (
        cliente.table("upload").select("*").eq("id", upload_id).limit(1).execute()
    )
    if not upload_resp.data:
        raise HTTPException(status_code=404, detail=f"upload {upload_id} não encontrado")

    eventos_resp = (
        cliente.table("upload_evento")
        .select("nivel,mensagem,linha_planilha,coluna_planilha,criado_em")
        .eq("upload_id", upload_id)
        .order("criado_em", desc=False)
        .execute()
    )

    return DetalheUpload(
        upload=RegistroUpload(**upload_resp.data[0]),
        eventos=[EventoUpload(**ev) for ev in (eventos_resp.data or [])],
    )
