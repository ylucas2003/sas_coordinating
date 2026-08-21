"""Lembrete que o coordenador pede pra si mesmo — a aplicação da P2.

Recorte literal do que morava no despachante: nenhuma mudança de
comportamento. Se a suíte da P2 passar igual depois do refactor, o corte entre
motor e aplicação saiu no lugar certo (docs/13 §6, etapa 5).

Materialização: nenhuma aqui — quem cria a regra E o disparo é a rota de
agendamento, no instante do agendamento (decisão A7 da P2).
"""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from typing import Any

from supabase import Client

from ..motor import FUSO_BRASIL, compor_email
from . import Mensagem


def preparar(
    cliente: Client, *, regra: dict[str, Any], disparo: dict[str, Any]
) -> Mensagem | None:
    """Guarda: a regra está viva e o evento está de pé? Senão, nada sai."""
    contexto = (
        cliente.table("regra_lembrete")
        .select(
            "id, cancelada_em, "
            "evento_agenda(id, titulo, data_evento, hora_evento, cancelado_em)"
        )
        .eq("id", regra["id"])
        .limit(1)
        .execute()
    ).data
    if not contexto:
        return None
    evento = contexto[0].get("evento_agenda") or {}
    if contexto[0].get("cancelada_em") or evento.get("cancelado_em"):
        return None

    assunto, corpo = compor_email(
        titulo=str(evento.get("titulo") or "Evento agendado"),
        data_evento=date.fromisoformat(str(evento["data_evento"])),
        hora_evento=time.fromisoformat(str(evento["hora_evento"])),
        hoje=datetime.now(timezone.utc).astimezone(FUSO_BRASIL).date(),
    )
    return Mensagem(assunto=assunto, corpo=corpo)
