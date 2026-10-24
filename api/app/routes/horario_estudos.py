"""HTTP do horário de estudos (docs/42).

Só fronteira, como o resto de `routes/`: as regras — limites, sobreposição, teto
— moram em `app/horario_estudos.py`, e é lá que se testam.

Router próprio, e não mais rotas em `routes/me.py`, porque `me.py` é proxy do que
o aluno LÊ sobre as próprias notas; aqui o aluno ESCREVE, e quatro verbos num
arquivo de leitura escondem o único que muda dado.

⚠️ Todas por `get_current_aluno`, e o `aluno_id` sai do token — nunca da URL nem
do corpo. Não existe visão da coordenação, de propósito (docs/42 §0, decisão 4):
se um dia existir, é outra rota, com outra autorização e outra conversa.

Códigos: 422 para valor que não faz sentido, 409 para valor válido que bate com o
que o aluno já tem (sobreposição, teto), 404 para bloco inexistente OU de outro
aluno — a rota não confirma que o uuid existe.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from .. import horario_estudos as regras
from ..auth import get_current_aluno
from ..schemas.horario_estudos import (
    AtualizarBloco,
    BlocoDeEstudo,
    CriarBlocos,
    HorarioDeEstudos,
)
from ..supabase_client import get_supabase

router = APIRouter(prefix="/me/horario-estudos", tags=["horario-estudos"])


def _traduzir(exc: Exception) -> HTTPException:
    """A exceção do domínio vira o código HTTP certo, com a frase para o aluno."""
    if isinstance(exc, regras.BlocoInexistente):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, regras.ConflitoDeHorario):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


_ERROS = (regras.BlocoInvalido, regras.ConflitoDeHorario, regras.BlocoInexistente)


@router.get("", response_model=HorarioDeEstudos)
async def obter_horario(user: dict = Depends(get_current_aluno)) -> HorarioDeEstudos:
    """A semana inteira do aluno. Vazia (`blocos: []`) é o estado mais comum."""
    return HorarioDeEstudos(blocos=regras.listar(get_supabase(), user["aluno_id"]))


@router.post("", response_model=list[BlocoDeEstudo], status_code=201)
async def criar_blocos(
    corpo: CriarBlocos, user: dict = Depends(get_current_aluno)
) -> list[BlocoDeEstudo]:
    """Cria um bloco por dia escolhido, tudo ou nada, e devolve só os criados."""
    try:
        return regras.criar(
            get_supabase(),
            user["aluno_id"],
            corpo.diasSemana,
            corpo.horaInicio,
            corpo.duracaoMinutos,
            corpo.rotulo,
        )
    except _ERROS as exc:
        raise _traduzir(exc) from exc


@router.patch("/{bloco_id}", response_model=BlocoDeEstudo)
async def atualizar_bloco(
    bloco_id: UUID, corpo: AtualizarBloco, user: dict = Depends(get_current_aluno)
) -> BlocoDeEstudo:
    """Edita UM bloco; campo ausente não é mexido.

    `bloco_id: UUID` e não `str`: uma string qualquer chegaria ao PostgREST como
    `eq.abc` numa coluna `uuid`, e a resposta seria 400 do banco virando 500 aqui.
    """
    try:
        return regras.atualizar(
            get_supabase(),
            user["aluno_id"],
            str(bloco_id),
            dia_semana=corpo.diaSemana,
            hora_inicio=corpo.horaInicio,
            duracao_minutos=corpo.duracaoMinutos,
            rotulo=corpo.rotulo,
        )
    except _ERROS as exc:
        raise _traduzir(exc) from exc


@router.delete("/{bloco_id}", status_code=204)
async def apagar_bloco(
    bloco_id: UUID, user: dict = Depends(get_current_aluno)
) -> Response:
    try:
        regras.apagar(get_supabase(), user["aluno_id"], str(bloco_id))
    except _ERROS as exc:
        raise _traduzir(exc) from exc
    return Response(status_code=204)
