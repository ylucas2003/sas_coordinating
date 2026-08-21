"""Rotas de edição manual de notas pelo coordenador.

PATCH /notas/{aluno_id}/{simulado_id}
    Corrige a nota de um aluno num simulado — **no Canvas primeiro**, no banco
    depois.

A ordem não é detalhe: a nota é um dado do Canvas (o aluno faz a prova lá, o
Canvas corrige, e é ele quem sabe se a submission veio missing/excused). Gravar
só no banco produzia edição fantasma — o upsert do sync (a cada 5 min, e no
reconcile diário) trazia o valor do Canvas de volta por cima, sem conflito e
sem aviso. O coordenador corrigia a nota e ela sumia sozinha.

Por isso, diferente do agendamento de simulado (que é origem SAS e pode ficar
em canvas_estado='falhou' até o retry), falha aqui **aborta a edição**: nada é
gravado localmente. Melhor recusar do que gravar uma nota que vai evaporar.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from supabase import Client

from ..auth import get_current_coordenador
from ..canvas_sync.cliente import ClienteCanvas
from ..config import get_settings
from ..stats.classificacao import recalcular_tudo as recalcular_classificacoes
from ..stats.metricas import corte_aplicavel, recalcular_simulado
from ..stats.utils import como_float
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/notas",
    tags=["notas"],
    dependencies=[Depends(get_current_coordenador)],
)

_CAMPOS_SIMULADO = (
    "id, nota_maxima, anulado, e_agregado, tipo, materia_id, external_id, "
    "ciclo:ciclo_id(vestibular_alvo, ano_letivo(canvas_course_id)), "
    "materia:materia_id(codigo)"
)


class PatchNotaBody(BaseModel):
    pontuacao: float | None = None
    presente: bool | None = None

    @model_validator(mode="after")
    def validar_consistencia(self) -> "PatchNotaBody":
        if self.presente is False and self.pontuacao is not None:
            raise ValueError("presente=false implica pontuacao=null")
        return self


def _course_id_do_simulado(simulado: dict) -> str | None:
    ciclo = simulado.get("ciclo") or {}
    return ((ciclo.get("ano_letivo") or {}) or {}).get("canvas_course_id")


async def _gravar_no_canvas(
    *,
    simulado: dict,
    canvas_user_id: str,
    pontuacao: float | None,
    presente: bool,
) -> None:
    """Escreve a nota no Canvas. Levanta HTTPException — o chamador não grava
    nada localmente se isto falhar."""
    settings = get_settings()
    if not settings.canvas_base_url or not settings.canvas_api_token:
        raise HTTPException(
            status_code=503,
            detail="Canvas não configurado no servidor — edição de nota indisponível.",
        )

    course_id = _course_id_do_simulado(simulado)
    if not course_id:
        raise HTTPException(
            status_code=422,
            detail="Ciclo sem canvas_course_id — rode a sincronização do Canvas antes de editar.",
        )
    if not simulado.get("external_id"):
        raise HTTPException(
            status_code=422,
            detail="Simulado sem Assignment correspondente no Canvas — não há onde gravar a nota.",
        )

    # Ausente: apaga a nota (string vazia) e marca missing. Presente: envia a
    # pontuação e limpa a marca de falta.
    posted_grade = "" if not presente else (pontuacao if pontuacao is not None else None)

    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        try:
            await canvas.atualizar_nota_submission(
                str(course_id),
                str(simulado["external_id"]),
                str(canvas_user_id),
                posted_grade=posted_grade,
                marcar_ausente=not presente,
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Canvas recusou a alteração (HTTP {exc.response.status_code}). "
                    "A nota não foi alterada."
                ),
            ) from exc
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise HTTPException(
                status_code=502,
                detail="Canvas fora de alcance. A nota não foi alterada — tente de novo.",
            ) from exc


@router.patch("/{aluno_id}/{simulado_id}")
async def editar_nota(
    aluno_id: str,
    simulado_id: str,
    body: PatchNotaBody,
) -> dict:
    """Corrige a nota de um aluno num simulado.

    Aceita pontuacao bruta (mesma escala do simulado, ex.: 12 de 20) e/ou
    presente. Se presente=false, pontuacao deve ser null.

    Grava no Canvas primeiro; só depois no banco, recalculando métricas do
    simulado e classificação dos alunos.
    """
    cliente: Client = get_supabase()

    resp_aluno = (
        cliente.table("aluno")
        .select("id, nome, canvas_user_id")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp_aluno.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")
    aluno = resp_aluno.data[0]
    if not aluno.get("canvas_user_id"):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Aluno {aluno.get('nome') or aluno_id} não tem canvas_user_id — "
                "sem isso não há como gravar a nota no Canvas."
            ),
        )

    resp_sim = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp_sim.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")

    simulado = resp_sim.data[0]
    if simulado.get("anulado"):
        raise HTTPException(
            status_code=422,
            detail="Simulado anulado — editar notas não tem efeito nas estatísticas.",
        )
    if simulado.get("e_agregado"):
        raise HTTPException(
            status_code=422,
            detail="Simulado agregado é calculado, não tem nota própria para editar.",
        )

    resp_atual = (
        cliente.table("nota")
        .select("pontuacao, presente")
        .eq("aluno_id", aluno_id)
        .eq("simulado_id", simulado_id)
        .limit(1)
        .execute()
    )
    atual = resp_atual.data[0] if resp_atual.data else {}

    presente_novo = body.presente if body.presente is not None else bool(atual.get("presente", True))
    if body.pontuacao is not None:
        pontuacao_nova = body.pontuacao
    elif not presente_novo:
        pontuacao_nova = None
    else:
        pontuacao_nova = como_float(atual.get("pontuacao"))

    # Canvas primeiro. Se falhar, a exceção sobe e o banco não é tocado.
    await _gravar_no_canvas(
        simulado=simulado,
        canvas_user_id=aluno["canvas_user_id"],
        pontuacao=pontuacao_nova,
        presente=presente_novo,
    )

    cliente.table("nota").upsert(
        {
            "aluno_id": aluno_id,
            "simulado_id": simulado_id,
            "pontuacao": pontuacao_nova,
            "presente": presente_novo,
        },
        on_conflict="aluno_id,simulado_id",
    ).execute()

    nota_maxima = como_float(simulado.get("nota_maxima")) or 10.0
    corte = corte_aplicavel(simulado)
    recalcular_simulado(cliente, simulado_id=simulado_id, nota_maxima=nota_maxima, corte=corte)
    recalcular_classificacoes(cliente)

    return {
        "alunoId": aluno_id,
        "simuladoId": simulado_id,
        "pontuacao": pontuacao_nova,
        "presente": presente_novo,
        "gravadoNoCanvas": True,
    }
