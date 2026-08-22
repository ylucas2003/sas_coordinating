"""O único lugar por onde o SAS escreve no Canvas (docs/18 §2.3).

Antes, cinco rotas chamavam `await canvas.…` cada uma do seu jeito — e cada
uma decidia sozinha que a escrita acontecia. A coordenação decidiu que
**nada sobe ao Canvas sem alguém clicar** (21/08, 19h05): a rota recebe
`sincronizar_canvas: bool`, sem default, e quando é False o objeto fica em
`canvas_estado='divergente'` — um estado legítimo, visível, que o retry
automático nunca toca.

Cada função aqui é chamada DEPOIS de o banco já estar gravado. A escrita no
Canvas é melhor-esforço: o resultado vira estado na linha (`sincronizado` /
`falhou` + erro), nunca exceção para o coordenador — com uma exceção, a
exclusão, que precisa ser síncrona porque o Assignment não existiria mais
para um retry.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from supabase import Client

from ..config import get_settings
from . import mapeador
from .agendamento import carregar_simulado_para_canvas, sincronizar_simulado_no_canvas
from .cliente import ClienteCanvas

log = logging.getLogger("sas.canvas.escrita")

DIVERGENTE = "divergente"


class CanvasIndisponivel(RuntimeError):
    """Sem URL/token configurados. O chamador decide se é 503 ou só estado."""


def _cliente() -> ClienteCanvas:
    settings = get_settings()
    if not settings.canvas_base_url or not settings.canvas_api_token:
        raise CanvasIndisponivel("Canvas não configurado no servidor")
    return ClienteCanvas(base_url=settings.canvas_base_url, token=settings.canvas_api_token)


def marcar_divergente(cliente: Client, tabela: str, id_: str) -> None:
    """O coordenador escolheu não mandar. Fica registrado na linha, e o
    badge "difere do Canvas" nasce daqui."""
    cliente.table(tabela).update(
        {"canvas_estado": DIVERGENTE, "canvas_erro": None}
    ).eq("id", id_).execute()


# ─── Ciclo → Assignment Group ─────────────────────────────────────────────


async def criar_grupo_do_ciclo(cliente: Client, ciclo_id: str) -> dict[str, Any]:
    """Cria o Assignment Group de um ciclo que nasceu sem ele (divergente ou
    falhou). Devolve {canvas_estado, canvas_assignment_group_id?, erro?}."""
    linha = (
        cliente.table("ciclo")
        .select("id, ordem, vestibular_alvo, canvas_assignment_group_id, ano_letivo(canvas_course_id)")
        .eq("id", ciclo_id)
        .limit(1)
        .execute()
    ).data
    if not linha:
        return {"canvas_estado": "falhou", "erro": "ciclo não encontrado"}
    ciclo = linha[0]
    if ciclo.get("canvas_assignment_group_id"):
        cliente.table("ciclo").update({"canvas_estado": "sincronizado", "canvas_erro": None}).eq(
            "id", ciclo_id
        ).execute()
        return {"canvas_estado": "sincronizado",
                "canvas_assignment_group_id": ciclo["canvas_assignment_group_id"]}

    course_id = (ciclo.get("ano_letivo") or {}).get("canvas_course_id")
    if not course_id:
        erro = "ano letivo sem canvas_course_id — rode o sync"
        cliente.table("ciclo").update({"canvas_estado": "falhou", "canvas_erro": erro}).eq(
            "id", ciclo_id
        ).execute()
        return {"canvas_estado": "falhou", "erro": erro}

    nome = mapeador.compor_nome_grupo_ciclo(
        ordem=ciclo["ordem"], vestibular=ciclo["vestibular_alvo"]
    )
    try:
        async with _cliente() as canvas:
            grupo = await canvas.criar_assignment_group(str(course_id), nome=nome)
    except Exception as exc:  # vira estado na linha, não exceção pro coordenador
        log.warning("canvas recusou grupo do ciclo %s: %s", ciclo_id, exc)
        cliente.table("ciclo").update({"canvas_estado": "falhou", "canvas_erro": str(exc)}).eq(
            "id", ciclo_id
        ).execute()
        return {"canvas_estado": "falhou", "erro": str(exc)}

    cliente.table("ciclo").update(
        {
            "canvas_assignment_group_id": str(grupo["id"]),
            "canvas_estado": "sincronizado",
            "canvas_erro": None,
        }
    ).eq("id", ciclo_id).execute()
    return {"canvas_estado": "sincronizado", "canvas_assignment_group_id": str(grupo["id"])}


# ─── Simulado → Assignment ────────────────────────────────────────────────


async def enviar_simulado(cliente: Client, simulado_id: str) -> str:
    """Cria ou realinha o Assignment. Devolve o canvas_estado final.

    Reusa `sincronizar_simulado_no_canvas`, que já sabe não re-POSTar um
    Assignment que talvez tenha sido criado num timeout anterior.
    """
    try:
        ctx = _cliente()
    except CanvasIndisponivel as exc:
        cliente.table("simulado").update(
            {"canvas_estado": "falhou", "canvas_erro": str(exc)}
        ).eq("id", simulado_id).execute()
        return "falhou"
    simulado = carregar_simulado_para_canvas(cliente, simulado_id)
    if simulado is None:
        return "falhou"
    async with ctx as canvas:
        return await sincronizar_simulado_no_canvas(cliente, canvas, simulado=simulado)


async def apagar_simulado(cliente: Client, *, course_id: str, external_id: str) -> None:
    """Apaga o Assignment. Levanta — exclusão não tem retry possível."""
    async with _cliente() as canvas:
        await canvas.apagar_assignment(str(course_id), str(external_id))


# ─── Nota → Submission ────────────────────────────────────────────────────


async def enviar_nota(
    cliente: Client,
    *,
    aluno_id: str,
    simulado_id: str,
) -> dict[str, Any]:
    """Manda `pontuacao_sas` (o valor em vigor) para a submission do aluno.

    Ao contrário de simulado, nota não tem `canvas_estado`: a divergência é
    derivada de `pontuacao_sas` vs `pontuacao_canvas` (docs/18 §2.4). Se o
    Canvas aceitar, `pontuacao_canvas` passa a ser o mesmo valor e a
    divergência some sozinha.
    """
    linha = (
        cliente.table("nota")
        .select(
            "pontuacao, pontuacao_sas, presente, "
            "aluno:aluno_id(canvas_user_id), "
            "simulado:simulado_id(external_id, ciclo:ciclo_id(ano_letivo(canvas_course_id)))"
        )
        .eq("aluno_id", aluno_id)
        .eq("simulado_id", simulado_id)
        .limit(1)
        .execute()
    ).data
    if not linha:
        return {"ok": False, "erro": "nota não encontrada"}
    nota = linha[0]
    canvas_user_id = (nota.get("aluno") or {}).get("canvas_user_id")
    simulado = nota.get("simulado") or {}
    external_id = simulado.get("external_id")
    course_id = ((simulado.get("ciclo") or {}).get("ano_letivo") or {}).get("canvas_course_id")

    faltando = [
        rotulo
        for rotulo, valor in (
            ("aluno sem canvas_user_id", canvas_user_id),
            ("simulado sem Assignment no Canvas", external_id),
            ("ciclo sem canvas_course_id", course_id),
        )
        if not valor
    ]
    if faltando:
        return {"ok": False, "erro": "; ".join(faltando)}

    presente = bool(nota.get("presente"))
    valor = nota.get("pontuacao")
    posted_grade = "" if not presente else valor

    try:
        async with _cliente() as canvas:
            await canvas.atualizar_nota_submission(
                str(course_id), str(external_id), str(canvas_user_id),
                posted_grade=posted_grade, marcar_ausente=not presente,
            )
    except CanvasIndisponivel as exc:
        return {"ok": False, "erro": str(exc)}
    except httpx.HTTPStatusError as exc:
        return {"ok": False, "erro": f"Canvas recusou (HTTP {exc.response.status_code})"}
    except (httpx.TimeoutException, httpx.TransportError):
        return {"ok": False, "erro": "Canvas fora de alcance"}

    # O Canvas agora diz o mesmo que o SAS: a divergência desaparece.
    cliente.table("nota").update({"pontuacao_canvas": valor}).eq("aluno_id", aluno_id).eq(
        "simulado_id", simulado_id
    ).execute()
    return {"ok": True}
