"""Edição manual de nota pelo painel — **só o administrador** (docs/35 §11.7).

PATCH /notas/{aluno_id}/{simulado_id}
    Corrige a nota de um aluno num simulado — no SAS sempre; no Canvas só se
    quem edita pedir (`sincronizar_canvas`).

⚠️ **Este PATCH não é a única porta que escreve nota, e fechá-lo não fecha as
outras.** O ingest de planilha (`app/ingest/`) e o sync do Canvas
(`app/canvas_sync/`) gravam `nota` por caminhos próprios, e continuam abertos
a quem pode disparar um upload ou um sync. O pedido da coordenação foi
"alterar notas no painel", então só o painel mudou — dito em voz alta para
ninguém concluir que a nota virou intocável.

Até a migration 0024 a ordem era "Canvas primeiro, banco depois, e falha
aborta": a edição só sobrevivia se estivesse no Canvas, porque o sync trazia
o valor de lá por cima. Isso acabou com `nota.pontuacao_sas` — a edição fica
numa coluna própria que o sync nunca toca, e `pontuacao` (o valor em vigor)
é resolvido por trigger como COALESCE(sas, canvas). Ver docs/18 §2.4.

Consequência: o Canvas deixou de ser pré-condição. Sem `canvas_user_id`, sem
Assignment ou com o Canvas fora do ar, a edição grava do mesmo jeito — e a
divergência fica visível, em vez de a edição ser recusada.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, model_validator
from supabase import Client

from ..auditoria import registrar as auditar
from ..auth import get_current_administrador, get_current_coordenador
from ..canvas_sync import escrita
from ..stats.classificacao import recalcular_tudo as recalcular_classificacoes
from ..stats.metricas import corte_aplicavel, recalcular_simulado
from ..stats.utils import como_float
from ..supabase_client import get_supabase

# O piso é coordenação; a rota que existe hoje sobe para administrador na
# própria assinatura. Fica assim, e não com o router inteiro promovido, porque
# o próximo endpoint de nota que nascer aqui (uma leitura, um recálculo) não
# tem por que herdar a restrição da EDIÇÃO.
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
    # Sem default de propósito: a rota nunca decide sozinha se escreve no
    # Canvas — o coordenador decide, a cada edição (docs/18 §2.3).
    sincronizar_canvas: bool

    @model_validator(mode="after")
    def validar_consistencia(self) -> PatchNotaBody:
        if self.presente is False and self.pontuacao is not None:
            raise ValueError("presente=false implica pontuacao=null")
        return self


def _course_id_do_simulado(simulado: dict) -> str | None:
    ciclo = simulado.get("ciclo") or {}
    return ((ciclo.get("ano_letivo") or {}) or {}).get("canvas_course_id")


@router.patch(
    "/{aluno_id}/{simulado_id}",
    dependencies=[Depends(get_current_administrador)],
)
async def editar_nota(
    aluno_id: str,
    simulado_id: str,
    body: PatchNotaBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Corrige a nota de um aluno num simulado. Só o administrador.

    Aceita pontuacao bruta (mesma escala do simulado, ex.: 12 de 20) e/ou
    presente. Se presente=false, pontuacao deve ser null.

    Grava em `pontuacao_sas` (o trigger resolve `pontuacao`), recalcula as
    métricas e, se `sincronizar_canvas`, tenta o Canvas DEPOIS — falha lá
    não desfaz a edição aqui; vira `gravadoNoCanvas: false` + erro.
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
        .select("pontuacao, pontuacao_canvas, pontuacao_sas, presente")
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

    agora = datetime.now(UTC).isoformat()
    cliente.table("nota").upsert(
        {
            "aluno_id": aluno_id,
            "simulado_id": simulado_id,
            # Só a coluna do SAS. `pontuacao` é resolvida pelo trigger da
            # 0024 e o sync continua livre para escrever `pontuacao_canvas`.
            "pontuacao_sas": pontuacao_nova,
            "presente": presente_novo,
            "editada_em": agora,
            "editada_por": administrador.get("sub"),
        },
        on_conflict="aluno_id,simulado_id",
    ).execute()

    nota_maxima = como_float(simulado.get("nota_maxima")) or 10.0
    corte = corte_aplicavel(simulado)
    recalcular_simulado(cliente, simulado_id=simulado_id, nota_maxima=nota_maxima, corte=corte)
    recalcular_classificacoes(cliente)

    resultado_canvas: dict = {"ok": False, "erro": "não solicitado"}
    if body.sincronizar_canvas:
        resultado_canvas = await escrita.enviar_nota(
            cliente, aluno_id=aluno_id, simulado_id=simulado_id
        )

    # A decisão fica no registro — é o que distingue "escolheu não mandar"
    # de "tentou e falhou" daqui a três meses (docs/18 §3.3).
    auditar(
        cliente, "nota_editada", canal="nota",
        # `ator_tipo` continua "coordenador" mesmo com o ator sendo o
        # administrador: ele nomeia a TABELA do ator (`usuario_coordenacao`), e
        # é assim que `routes/auditoria.py` resolve o nome de quem fez. Quem
        # podia fazer está na 0045, não aqui.
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"nota/{aluno_id}/{simulado_id}",
        ip=request.client.host if request.client else None,
        detalhe={
            "aluno": aluno.get("nome"),
            "valor_antes": como_float(atual.get("pontuacao")),
            "valor_depois": pontuacao_nova,
            "valor_canvas": como_float(atual.get("pontuacao_canvas")),
            "presente": presente_novo,
            "sincronizar_canvas": body.sincronizar_canvas,
            "canvas_ok": resultado_canvas["ok"],
            "canvas_erro": resultado_canvas.get("erro"),
        },
    )

    return {
        "alunoId": aluno_id,
        "simuladoId": simulado_id,
        "pontuacao": pontuacao_nova,
        "presente": presente_novo,
        "gravadoNoCanvas": resultado_canvas["ok"],
        "canvasErro": None if resultado_canvas["ok"] else resultado_canvas.get("erro"),
    }
