"""Sedes e turmas — entidades de "contexto" usadas em filtros."""

from fastapi import APIRouter, Depends

from ..auth import get_current_coordenador
from ..schemas.domain import Sede, Turma
from ..supabase_client import get_supabase

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
        .select("id, sede_id, ano_letivo_id, serie, trilha, section_original, ano_letivo(ano)")
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
            )
        )
    return turmas
