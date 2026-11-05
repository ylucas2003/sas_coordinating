"""Sedes e turmas — entidades de "contexto" usadas em filtros."""

from collections import Counter

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import get_current_coordenador
from ..schemas.domain import Sede, Turma
from ..supabase_client import get_supabase
from .alunos import _mapa_aluno_para_turma_ativa, _mapa_turma_para_serie

router = APIRouter(
    tags=["dimensoes"],
    dependencies=[Depends(get_current_coordenador)],
)


@router.get("/sedes", response_model=list[Sede])
async def listar_sedes() -> list[Sede]:
    cliente = get_supabase()
    resp = cliente.table("sede").select("id, nome, modalidade").order("nome").execute()
    return [Sede(**linha) for linha in (resp.data or [])]


@router.get("/turmas", response_model=list[Turma])
async def listar_turmas() -> list[Turma]:
    cliente = get_supabase()
    resp = (
        cliente.table("turma")
        .select(
            "id, sede_id, ano_letivo_id, serie, serie_do_curso, trilha, "
            "section_original, ano_letivo(ano)"
        )
        .order("section_original")
        .execute()
    )

    turmas: list[Turma] = []
    for linha in resp.data or []:
        ano_letivo = (linha.get("ano_letivo") or {}).get("ano") or 0
        turmas.append(
            Turma(
                id=linha["id"],
                nome=linha["section_original"],
                sedeId=linha["sede_id"],
                anoLetivo=ano_letivo,
                serie=linha.get("serie_do_curso") or 3,
            )
        )
    return turmas


class BlocoDaCoordenacao(BaseModel):
    serie: int
    alunos: int
    alertas: int


#: A ordem dos blocos no rail. O 3º vem primeiro porque é o que já existia.
_ORDEM_DOS_BLOCOS = (3, 1, 2)


@router.get("/blocos", response_model=list[BlocoDaCoordenacao])
def listar_blocos() -> list[BlocoDaCoordenacao]:
    """Os blocos do rail, com o que cada um mostra no cabeçalho (docs/44 §4).

    Série sem aluno não vira bloco: enquanto só houver o 3º, o rail fica igual ao
    de sempre, e por isso esta rota pode ir ao ar antes da importação. O 3º
    aparece sempre, mesmo vazio, porque é ele que `/painel` e `/alunos` abrem.
    """
    cliente = get_supabase()
    turma_para_serie = _mapa_turma_para_serie(cliente)
    alunos = Counter(
        turma_para_serie.get(turma_id, 3)
        for turma_id in _mapa_aluno_para_turma_ativa(cliente).values()
    )
    abertos = cliente.table("alerta").select("serie").eq("resolvido", False).execute()
    alertas = Counter(linha.get("serie", 3) for linha in abertos.data or [])
    return [
        BlocoDaCoordenacao(serie=serie, alunos=alunos[serie], alertas=alertas[serie])
        for serie in _ORDEM_DOS_BLOCOS
        if serie == 3 or alunos[serie] > 0
    ]


@router.get("/materias")
async def listar_materias() -> list[dict]:
    """Matérias canônicas — usadas no formulário de agendamento (P1)."""
    cliente = get_supabase()
    resp = cliente.table("materia").select("id, codigo, nome").order("nome").execute()
    return resp.data or []
