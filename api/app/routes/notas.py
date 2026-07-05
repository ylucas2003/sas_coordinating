"""Rotas de edição manual de notas pelo coordenador.

PATCH /notas/{aluno_id}/{simulado_id}
    Cria ou corrige a nota de um aluno num simulado. Após o upsert, recalcula
    as métricas do simulado e a classificação de todos os alunos.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator

from ..auth import get_current_coordenador
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
    "id, nota_maxima, anulado, e_agregado, tipo, materia_id, "
    "ciclo:ciclo_id(vestibular_alvo), materia:materia_id(codigo)"
)


class PatchNotaBody(BaseModel):
    pontuacao: float | None = None
    presente: bool | None = None

    @model_validator(mode="after")
    def validar_consistencia(self) -> "PatchNotaBody":
        if self.presente is False and self.pontuacao is not None:
            raise ValueError("presente=false implica pontuacao=null")
        return self


@router.patch("/{aluno_id}/{simulado_id}")
async def editar_nota(
    aluno_id: str,
    simulado_id: str,
    body: PatchNotaBody,
) -> dict:
    """Cria ou corrige a nota de um aluno num simulado.

    Aceita pontuacao bruta (mesma escala do simulado, ex.: 12 de 20) e/ou
    presente. Se presente=false, pontuacao deve ser null.

    Após o upsert, recalcula métricas do simulado e classificação dos alunos.
    """
    cliente = get_supabase()

    resp_aluno = cliente.table("aluno").select("id").eq("id", aluno_id).limit(1).execute()
    if not resp_aluno.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")

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
    }
