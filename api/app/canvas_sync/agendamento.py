"""Escrita SAS → Canvas do agendamento (P1).

Um simulado origem='sas' nasce no banco com canvas_estado='pendente' e
external_id NULL; este módulo é quem o materializa no Canvas — na hora
(chamado pela rota, feedback imediato) ou no tick de 5 min (reprocessamento
dos que ficaram em limbo). A mesma função serve os dois caminhos, e é
deliberadamente tolerante: falha vira estado no banco, nunca exceção pro
chamador.

Regras que moram aqui:
  - POST nunca repete (sem idempotência na API do Canvas) — antes de recriar,
    procura por nome exato (buscar_assignment_por_nome).
  - PUT repete à vontade (idempotente).
  - Desiste depois de MAX_TENTATIVAS — resgate manual pelo botão da UI, que
    zera o contador.
"""

from __future__ import annotations

from datetime import date, time
from typing import Any

from supabase import Client

from . import mapeador
from .cliente import ClienteCanvas

MAX_TENTATIVAS = 5

# O que o SAS manda pro Canvas. on_paper: a prova é presencial em papel —
# nenhuma entrega online — e o Canvas ainda registra nota/missing/excused,
# que é o que o sync lê de volta. published é obrigatório: o sync descarta
# assignment não publicado (sincronizar.py).
_SUBMISSION_TYPES = ["on_paper"]

# Fuso fixo — o Brasil não tem horário de verão desde 2019.
_FUSO = "-03:00"


def _due_at_iso(data_aplicacao: date, hora: time) -> str:
    return f"{data_aplicacao.isoformat()}T{hora.strftime('%H:%M')}:00{_FUSO}"


def montar_payload_assignment(
    *,
    nome: str,
    nota_maxima: float,
    data_aplicacao: date,
    hora: time,
    assignment_group_id: str,
) -> dict[str, Any]:
    return {
        "name": nome,
        "points_possible": nota_maxima,
        "due_at": _due_at_iso(data_aplicacao, hora),
        "assignment_group_id": int(assignment_group_id),
        "submission_types": _SUBMISSION_TYPES,
        "published": True,
    }


def _marcar(
    cliente: Client,
    simulado_id: str,
    *,
    estado: str,
    erro: str | None = None,
    external_id: str | None = None,
    incrementar_tentativa: int = 0,
) -> None:
    patch: dict[str, Any] = {"canvas_estado": estado, "canvas_erro": erro}
    if external_id is not None:
        patch["external_id"] = external_id
    if incrementar_tentativa:
        atual = (
            cliente.table("simulado")
            .select("canvas_tentativas")
            .eq("id", simulado_id)
            .limit(1)
            .execute()
        )
        tentativas = (atual.data or [{}])[0].get("canvas_tentativas") or 0
        patch["canvas_tentativas"] = tentativas + incrementar_tentativa
    cliente.table("simulado").update(patch).eq("id", simulado_id).execute()


async def sincronizar_simulado_no_canvas(
    cliente: Client,
    canvas: ClienteCanvas,
    *,
    simulado: dict[str, Any],
) -> str:
    """Cria (ou atualiza) o Assignment de um simulado origem='sas' no Canvas.

    `simulado` precisa vir com os joins:
        id, external_id, nome, nota_maxima, data_aplicacao,
        ciclo(canvas_assignment_group_id, ano_letivo(canvas_course_id)),
        evento_agenda(hora_evento)

    Devolve o canvas_estado final ('sincronizado' | 'falhou'). Nunca levanta:
    falha vira estado no banco — é o contrato que permite ao agendamento
    devolver 201 mesmo com o Canvas fora do ar.
    """
    simulado_id = simulado["id"]
    ciclo = simulado.get("ciclo") or {}
    group_id = ciclo.get("canvas_assignment_group_id")
    course_id = ((ciclo.get("ano_letivo") or {}) or {}).get("canvas_course_id")

    if not course_id or not group_id:
        # Sem destino não há o que tentar — e não é falha transitória, então
        # não queima tentativa. Dois motivos possíveis:
        #   * o ciclo nasceu 'divergente' (coordenador escolheu não criar o
        #     grupo — docs/18 §2.1): o simulado HERDA o divergente, senão o
        #     retry ficaria martelando um 'falhou' que nunca se resolve;
        #   * o sync ainda não preencheu os ids: aí é 'falhou' mesmo.
        if ciclo.get("canvas_estado") == "divergente":
            _marcar(cliente, simulado_id, estado="divergente", erro=None)
            return "divergente"
        _marcar(
            cliente, simulado_id, estado="falhou",
            erro="ciclo sem canvas_course_id/canvas_assignment_group_id — rode o sync",
        )
        return "falhou"

    data_aplicacao = date.fromisoformat(str(simulado["data_aplicacao"]))
    hora_bruta = (simulado.get("evento_agenda") or {}).get("hora_evento") or "07:00"
    hora = time.fromisoformat(str(hora_bruta))
    payload = montar_payload_assignment(
        nome=simulado["nome"],
        nota_maxima=float(simulado["nota_maxima"]),
        data_aplicacao=data_aplicacao,
        hora=hora,
        assignment_group_id=str(group_id),
    )

    try:
        if simulado.get("external_id"):
            # Já existe no Canvas — só realinha (PUT, idempotente).
            await canvas.atualizar_assignment(
                str(course_id), str(simulado["external_id"]), assignment=payload
            )
            _marcar(cliente, simulado_id, estado="sincronizado")
            return "sincronizado"

        # Nunca criado (ou o POST anterior morreu sem resposta): antes de
        # POSTar, procura por nome exato — um timeout pode ter criado o
        # Assignment mesmo assim, e recriar às cegas duplicaria a prova.
        existente = await canvas.buscar_assignment_por_nome(
            str(course_id), simulado["nome"]
        )
        if existente is not None:
            _marcar(
                cliente, simulado_id,
                estado="sincronizado", external_id=str(existente["id"]),
            )
            return "sincronizado"

        criado = await canvas.criar_assignment(str(course_id), assignment=payload)
        _marcar(
            cliente, simulado_id,
            estado="sincronizado", external_id=str(criado["id"]),
        )
        return "sincronizado"
    except Exception as exc:
        _marcar(
            cliente, simulado_id,
            estado="falhou", erro=str(exc)[:500], incrementar_tentativa=1,
        )
        return "falhou"


_SELECT_SIMULADO_CANVAS = (
    "id, external_id, nome, nota_maxima, data_aplicacao, canvas_tentativas, "
    "ciclo(canvas_assignment_group_id, canvas_estado, ano_letivo(canvas_course_id)), "
    "evento_agenda(hora_evento)"
)


def carregar_simulado_para_canvas(cliente: Client, simulado_id: str) -> dict[str, Any] | None:
    resp = (
        cliente.table("simulado")
        .select(_SELECT_SIMULADO_CANVAS)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    return resp.data[0] if resp.data else None


async def reprocessar_canvas_pendentes(
    cliente: Client,
    canvas: ClienteCanvas,
) -> dict[str, int]:
    """Varre simulados origem='sas' em limbo e tenta materializá-los.

    Chamado pelo sync incremental (5 min) — mesmo assunto, mesma trava,
    granularidade melhor que o tick horário, e sem mexer em infra/.

    A lista de estados é FECHADA de propósito: `divergente` significa que o
    coordenador ESCOLHEU não mandar (docs/18 §2.5). Se este filtro um dia
    virar "tudo que não é sincronizado", o job passa a reenviar em minutos o
    que ele decidiu segurar — em silêncio.
    """
    resp = (
        cliente.table("simulado")
        .select(_SELECT_SIMULADO_CANVAS)
        .eq("origem", "sas")
        .in_("canvas_estado", ["pendente", "falhou"])   # nunca 'divergente'.
        .lt("canvas_tentativas", MAX_TENTATIVAS)
        .execute()
    )
    pendentes = resp.data or []
    resultado = {"sincronizados": 0, "falharam": 0}
    for simulado in pendentes:
        estado = await sincronizar_simulado_no_canvas(cliente, canvas, simulado=simulado)
        chave = "sincronizados" if estado == "sincronizado" else "falharam"
        resultado[chave] += 1
    return resultado
