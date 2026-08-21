"""Materialização e regeração de disparos.

Decisão A7 (docs/12 §1): o disparo é MATERIALIZADO na criação da regra —
"enviar dia 17/09 às 07:00" fica gravado no banco — e regerado quando a data
do evento muda. Um disparo materializado é intenção, não ordem: a guarda do
despachante reverifica o estado do mundo antes de qualquer envio, então
disparo desatualizado vira no-op, não dano.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from supabase import Client

# Fuso fixo — o Brasil não tem horário de verão desde 2019 (mesma decisão
# _FUSO do canvas_sync/agendamento.py).
FUSO_BRASIL = timezone(timedelta(hours=-3))

# Estados em que um disparo ainda pode virar alguma coisa. 'enviado' e
# 'cancelado' são terminais e nunca se tocam — são histórico.
_ESTADOS_VIVOS = ["agendado", "falhou", "enviando"]

# Tipos de destinatário que cuidam da PRÓPRIA materialização (docs/13 §4.7).
# O lembrete de aluno é materializado na véspera, por varredura, em N disparos
# — regerar aqui produziria um disparo órfão com destinatário vazio, e
# cancelar aqui calaria o dia inteiro por causa de UMA prova cancelada. Quem
# reconcilia esses é a aplicação, a cada tick.
MATERIALIZA_SOZINHA = frozenset({"aluno"})


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def calcular_enviar_em(data_evento: date, hora_evento: time, dias_antes: int) -> datetime:
    """`dias_antes` antes do evento, na mesma hora do evento, fuso -03:00.

    "3 dias antes da prova" = mesmo horário, 3 dias antes. Sem janela de
    silêncio (decisão A8, docs/12 §1) — o horário calculado é o do envio.
    """
    return datetime.combine(
        data_evento - timedelta(days=dias_antes), hora_evento, tzinfo=FUSO_BRASIL
    )


def compor_email(
    *, titulo: str, data_evento: date, hora_evento: time, hoje: date
) -> tuple[str, str]:
    """Assunto e corpo do lembrete — compostos no INSTANTE do envio, a partir
    do dado fresco do evento (nunca na materialização; ver docs/12 §1)."""
    data_br = data_evento.strftime("%d/%m/%Y")
    hora_txt = hora_evento.strftime("%H:%M")
    dias = (data_evento - hoje).days
    if dias > 1:
        quando = f"em {dias} dias"
    elif dias == 1:
        quando = "amanhã"
    elif dias == 0:
        quando = "hoje"
    else:
        quando = f"era em {data_br}"
    assunto = f"Lembrete: {titulo} — {quando}"
    corpo = (
        "Lembrete do SAS:\n\n"
        f"  {titulo}\n"
        f"  {data_br} às {hora_txt} ({quando}).\n\n"
        "Este lembrete foi agendado por você no SAS."
    )
    return assunto, corpo


def _materializar_disparo(
    cliente: Client, *, regra: dict[str, Any], evento: dict[str, Any], destinatario: str
) -> None:
    enviar_em = calcular_enviar_em(
        date.fromisoformat(str(evento["data_evento"])),
        time.fromisoformat(str(evento["hora_evento"])),
        int(regra["dias_antes"]),
    )
    cliente.table("disparo").insert(
        {
            "regra_lembrete_id": regra["id"],
            "destinatario": destinatario,
            "canal": regra["canal"],
            "enviar_em": enviar_em.isoformat(),
        }
    ).execute()


def criar_regra_com_disparo(
    cliente: Client, *, evento: dict[str, Any], dias_antes: int, destinatario: str
) -> dict[str, Any]:
    """Cria a regra e materializa seu disparo (1 em P2 — P4 estende aqui a
    cadência, 1 regra → N disparos, sem tocar no despachante).

    `enviar_em` no passado é criado mesmo assim: vence no próximo tick e o
    coordenador recebe na hora — melhor que recusar "lembrete de amanhã"
    agendado hoje.
    """
    regra = (
        cliente.table("regra_lembrete")
        .insert(
            {
                "evento_agenda_id": evento["id"],
                "destinatario_tipo": "coordenador",
                "canal": "email",
                "dias_antes": dias_antes,
            },
            returning="representation",
        )
        .execute()
    ).data[0]
    _materializar_disparo(cliente, regra=regra, evento=evento, destinatario=destinatario)
    return regra


def regerar_disparos_do_evento(cliente: Client, evento_agenda_id: str) -> None:
    """Remarque: cancela os disparos vivos e materializa de novo com a data
    atual do evento. 'enviado' não se toca — é histórico.

    Cinto e suspensório de propósito (docs/12 §4.3): a regeração dá o
    histórico limpo; a guarda no envio cobre a corrida e qualquer caminho
    futuro que esqueça de regerar.
    """
    evento_resp = (
        cliente.table("evento_agenda")
        .select("id, data_evento, hora_evento, criado_por, cancelado_em")
        .eq("id", evento_agenda_id)
        .limit(1)
        .execute()
    )
    if not evento_resp.data:
        return
    evento = evento_resp.data[0]

    regras = [
        r
        for r in (
            cliente.table("regra_lembrete")
            .select("id, dias_antes, canal, destinatario_tipo")
            .eq("evento_agenda_id", evento_agenda_id)
            .is_("cancelada_em", "null")
            .execute()
        ).data
        or []
        # Regra que se materializa sozinha não se regera aqui (MATERIALIZA_SOZINHA).
        if r.get("destinatario_tipo") not in MATERIALIZA_SOZINHA
    ]

    for regra in regras:
        vivos = (
            cliente.table("disparo")
            .select("id, destinatario")
            .eq("regra_lembrete_id", regra["id"])
            .in_("estado", _ESTADOS_VIVOS)
            .execute()
        ).data or []
        # O destinatário do disparo novo vem do antigo (continuidade do
        # histórico); sem antigo, re-resolve do evento.
        destinatario = (
            vivos[0]["destinatario"] if vivos else (evento.get("criado_por") or "")
        )
        if vivos:
            cliente.table("disparo").update(
                {"estado": "cancelado", "atualizado_em": _agora_iso()}
            ).in_("id", [d["id"] for d in vivos]).execute()
        if evento.get("cancelado_em") or not destinatario:
            continue
        _materializar_disparo(
            cliente, regra=regra, evento=evento, destinatario=destinatario
        )


def cancelar_disparos_do_evento(cliente: Client, evento_agenda_id: str) -> None:
    """Evento cancelado: mata as regras e os disparos vivos. 'enviado' fica —
    e-mail que saiu é fato, não intenção.

    ⚠️ Os disparos de regra em MATERIALIZA_SOZINHA NÃO caem aqui: um disparo de
    aluno é o digest do DIA, e o dia pode ter outras provas de pé. A regra
    morre (esta prova sai da lista); o disparo é reconciliado pela aplicação —
    re-ancorado se o dia sobreviveu, cancelado pela guarda se esvaziou.
    """
    regras = (
        cliente.table("regra_lembrete")
        .select("id, destinatario_tipo")
        .eq("evento_agenda_id", evento_agenda_id)
        .is_("cancelada_em", "null")
        .execute()
    ).data or []
    if not regras:
        return
    agora = _agora_iso()
    cliente.table("regra_lembrete").update({"cancelada_em": agora}).in_(
        "id", [r["id"] for r in regras]
    ).execute()

    ids_do_motor = [
        r["id"]
        for r in regras
        if r.get("destinatario_tipo") not in MATERIALIZA_SOZINHA
    ]
    if not ids_do_motor:
        return
    cliente.table("disparo").update(
        {"estado": "cancelado", "atualizado_em": agora}
    ).in_("regra_lembrete_id", ids_do_motor).in_("estado", _ESTADOS_VIVOS).execute()
