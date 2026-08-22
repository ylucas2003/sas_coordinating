"""O tick do motor: processa os disparos vencidos.

Chamado pelo EventBridge de hora em hora (POST /disparos/processar — o path
cron horário chama /disparos/processar), pelo fim do sync de 5 min, ou por
curl manual. Idempotente por disparo (decisão A9, docs/12 §1): o claim por
UPDATE condicional garante que tick duplicado — retry da AWS, deploy no meio —
não produz dois envios.

Risco assumido em A9: melhor duplicar que perder. O resgate de claim órfão
(processo que morreu entre o claim e o envio) re-tenta, podendo raramente
duplicar um e-mail que chegou a sair — inofensivo pra lembrete; revisitar
quando o canal for WhatsApp (P5).

O que a P3 acrescentou, tudo por causa do volume (docs/13 §4.4):
  - a varredura das aplicações roda ANTES da fila, no mesmo tick;
  - guarda e texto saíram daqui pra `aplicacoes/` — o motor não sabe mais o
    que é um evento cancelado, só o que é um `None`;
  - ritmo entre envios, orçamento de tempo por rodada e teto de 24h.
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

from ..config import get_settings
from . import aplicacoes, supressao
from . import email as email_ses

MAX_TENTATIVAS = 5
ENVIANDO_ORFAO_MINUTOS = 30


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _filtro_ts(momento: datetime) -> str:
    """Timestamp pra usar em FILTRO do PostgREST (query string). O '+' de
    '+00:00' não é encodado pelo cliente e viraria espaço na URL — o Postgres
    rejeitaria ("invalid input syntax"). O sufixo 'Z' diz o mesmo sem '+'."""
    return momento.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _resgatar_claims_orfaos(cliente: Client) -> int:
    """'enviando' parado há mais de 30 min = processo morreu no meio do envio.
    Volta pra 'falhou' (com tentativa contada) e o laço normal re-tenta."""
    corte = _filtro_ts(_agora() - timedelta(minutes=ENVIANDO_ORFAO_MINUTOS))
    orfaos = (
        cliente.table("disparo")
        .select("id, tentativas")
        .eq("estado", "enviando")
        .lt("atualizado_em", corte)
        .execute()
    ).data or []
    for disparo in orfaos:
        cliente.table("disparo").update(
            {
                "estado": "falhou",
                "tentativas": (disparo.get("tentativas") or 0) + 1,
                "erro": "processo interrompido durante o envio (claim órfão) — "
                        "pode ter duplicado",
                "atualizado_em": _agora().isoformat(),
            }
        ).eq("id", disparo["id"]).execute()
    return len(orfaos)


def _enviados_nas_ultimas_24h(cliente: Client) -> int:
    """Contagem do teto de segurança. Janela deslizante de 24h porque é assim
    que a cota do SES conta — não por dia do calendário."""
    resp = (
        cliente.table("disparo")
        .select("id", count="exact")
        .eq("estado", "enviado")
        .gte("enviado_em", _filtro_ts(_agora() - timedelta(hours=24)))
        .limit(1)
        .execute()
    )
    if resp.count is not None:
        return int(resp.count)
    return len(resp.data or [])


def _carregar_regra(cliente: Client, regra_id: str) -> dict[str, Any] | None:
    """Releitura FRESCA da regra depois do claim. O que ela significa é com a
    aplicação (docs/13 §1.1); aqui só se sabe de qual tipo ela é."""
    resp = (
        cliente.table("regra_lembrete")
        .select("id, destinatario_tipo, canal, cancelada_em, evento_agenda_id")
        .eq("id", regra_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


def _materializar_sem_derrubar_o_tick(cliente: Client) -> dict[str, Any]:
    try:
        return aplicacoes.materializar_pendentes(cliente)
    except Exception as exc:   # noqa: BLE001 — a fila tem que rodar mesmo assim
        return {"erro": str(exc)[:500]}


async def processar_disparos_vencidos(cliente: Client) -> dict[str, Any]:
    """Uma passada da fila. Envio sequencial e espaçado: o SES tem cota por
    segundo, e centenas de e-mails idênticos disparados de uma vez é
    exatamente o padrão que derruba reputação de remetente."""
    settings = get_settings()
    inicio = _time.monotonic()
    orcamento = max(1, int(settings.lembretes_orcamento_segundos))
    intervalo = 1.0 / max(0.1, float(settings.email_envios_por_segundo))

    resultado: dict[str, Any] = {
        "enviados": 0,
        "falharam": 0,
        "cancelados": 0,
        "pulados": 0,
        "restantes": 0,
        "resgatados": _resgatar_claims_orfaos(cliente),
        # A varredura das aplicações vem ANTES da fila, no mesmo tick: é o que
        # garante que o digest da véspera exista antes de o relógio ser lido.
        #
        # Isolada de propósito: materializar e ENVIAR são independentes, e um
        # erro na varredura (bug, banco fora) não pode segurar o que já está
        # materializado — inclusive o lembrete do coordenador, que nem passa
        # por ela. O erro fica no resultado do tick, visível.
        "materializacao": _materializar_sem_derrubar_o_tick(cliente),
    }

    fila = (
        cliente.table("disparo")
        .select(
            "id, destinatario, canal, tentativas, regra_lembrete_id, "
            "contexto, chave_idempotencia"
        )
        .in_("estado", ["agendado", "falhou"])
        .lte("enviar_em", _filtro_ts(_agora()))
        .lt("tentativas", MAX_TENTATIVAS)
        .order("enviar_em")
        .execute()
    ).data or []

    invalidos = supressao.carregar_invalidos(cliente)
    enviados_24h = _enviados_nas_ultimas_24h(cliente)
    teto = int(settings.email_teto_diario)

    for indice, disparo in enumerate(fila):
        if _time.monotonic() - inicio > orcamento:
            # A fila é durável: o que não coube sai no tick seguinte, na ordem
            # de enviar_em (o mais atrasado primeiro).
            resultado["restantes"] = len(fila) - indice
            resultado["motivo_parada"] = "orcamento"
            break
        if enviados_24h >= teto:
            resultado["restantes"] = len(fila) - indice
            resultado["motivo_parada"] = "teto_diario"
            break

        # Claim (CAS): só quem virou o estado envia. Zero linhas afetadas =
        # outro processo pegou este disparo — segue o baile.
        claim = (
            cliente.table("disparo")
            .update({"estado": "enviando", "atualizado_em": _agora().isoformat()})
            .eq("id", disparo["id"])
            .in_("estado", ["agendado", "falhou"])
            .execute()
        )
        if not claim.data:
            resultado["pulados"] += 1
            continue

        # Endereço queimado (bounce/complaint/descadastro) não recebe mais
        # nada — nem o que já estava materializado.
        if supressao.normalizar(disparo["destinatario"]) in invalidos:
            _cancelar(cliente, disparo["id"])
            resultado["cancelados"] += 1
            continue

        regra = _carregar_regra(cliente, disparo["regra_lembrete_id"])
        # Guarda + composição, delegadas à aplicação: None = o mundo mudou.
        # O disparo vira 'cancelado' (não 'falhou' — não é erro).
        mensagem = (
            aplicacoes.preparar(cliente, regra=regra, disparo=disparo)
            if regra is not None
            else None
        )
        if mensagem is None:
            _cancelar(cliente, disparo["id"])
            resultado["cancelados"] += 1
            continue

        try:
            email_ses.enviar_email(
                destinatario=disparo["destinatario"],
                assunto=mensagem.assunto,
                corpo=mensagem.corpo,
            )
        except Exception as exc:
            cliente.table("disparo").update(
                {
                    "estado": "falhou",
                    "tentativas": (disparo.get("tentativas") or 0) + 1,
                    "erro": str(exc)[:500],
                    "atualizado_em": _agora().isoformat(),
                }
            ).eq("id", disparo["id"]).execute()
            resultado["falharam"] += 1
            continue

        cliente.table("disparo").update(
            {
                "estado": "enviado",
                "enviado_em": _agora().isoformat(),
                "assunto": mensagem.assunto,
                "corpo": mensagem.corpo,
                "erro": None,
                "atualizado_em": _agora().isoformat(),
            }
        ).eq("id", disparo["id"]).execute()
        resultado["enviados"] += 1
        enviados_24h += 1
        await asyncio.sleep(intervalo)

    return resultado


def _cancelar(cliente: Client, disparo_id: str) -> None:
    cliente.table("disparo").update(
        {"estado": "cancelado", "atualizado_em": _agora().isoformat()}
    ).eq("id", disparo_id).execute()
