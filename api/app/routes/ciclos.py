"""Endpoints de ciclos."""

from collections import defaultdict

from fastapi import APIRouter, HTTPException, Query

from ..schemas.domain import Ciclo
from ..stats import ciclo_estatisticas, insights
from ..supabase_client import get_supabase

router = APIRouter(prefix="/ciclos", tags=["ciclos"])


def _agrupar_simulados_por_ciclo(cliente) -> dict[str, list[str]]:
    """Devolve {ciclo_id: [simulado_id, ...]} pra montar os Ciclos."""
    resp = cliente.table("simulado").select("id, ciclo_id").execute()
    mapa: dict[str, list[str]] = defaultdict(list)
    for linha in resp.data or []:
        mapa[linha["ciclo_id"]].append(linha["id"])
    return mapa


def _linha_para_ciclo(linha: dict, simulado_ids: list[str]) -> Ciclo:
    ano = (linha.get("ano_letivo") or {}).get("ano") or 0
    return Ciclo(
        id=linha["id"],
        nome=linha["nome"],
        anoLetivo=ano,
        vestibularAlvo=linha.get("vestibular_alvo"),
        periodoInicio=linha.get("periodo_inicio") or "",
        periodoFim=linha.get("periodo_fim") or "",
        simuladoIds=simulado_ids,
    )


@router.get("", response_model=list[Ciclo])
async def listar_ciclos() -> list[Ciclo]:
    cliente = get_supabase()
    mapa = _agrupar_simulados_por_ciclo(cliente)
    resp = (
        cliente.table("ciclo")
        .select("id, nome, ordem, vestibular_alvo, periodo_inicio, periodo_fim, ano_letivo(ano)")
        .order("ordem")
        .execute()
    )
    return [_linha_para_ciclo(linha, mapa.get(linha["id"], [])) for linha in (resp.data or [])]


@router.get("/{ciclo_id}", response_model=Ciclo)
async def obter_ciclo(ciclo_id: str) -> Ciclo:
    cliente = get_supabase()
    resp = (
        cliente.table("ciclo")
        .select("id, nome, ordem, vestibular_alvo, periodo_inicio, periodo_fim, ano_letivo(ano)")
        .eq("id", ciclo_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")

    mapa = _agrupar_simulados_por_ciclo(cliente)
    return _linha_para_ciclo(resp.data[0], mapa.get(ciclo_id, []))


@router.get("/{ciclo_id}/estatisticas")
async def estatisticas_do_ciclo(
    ciclo_id: str,
    com_insights: bool = Query(
        True,
        description="Se true, anexa bullets LLM (prático + técnico) em conjunta.insights e porMateria[*].insights.",
    ),
) -> dict:
    """Payload completo do ciclo — F1, F2, análise conjunta e por matéria.

    Estrutura: ver `ciclo_estatisticas.calcular`. O front renderiza tudo
    numa única página vertical, sem filtros de fase. Insights são gerados
    em duas linguagens: 'pratico' (visível por default) e 'tecnico' (dentro
    da seção "dados estatísticos avançados").

    Insights LLM são opcionais (controlados por `com_insights`) e retornam
    listas vazias se OPENAI_API_KEY não estiver configurada.
    """
    cliente = get_supabase()
    payload = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")

    if com_insights:
        _anexar_insights(cliente, payload)
    return payload


def _anexar_insights(cliente, payload: dict) -> None:
    """Anexa insights (prático + técnico) em-place no payload."""
    ciclo = payload["ciclo"]
    contexto_base = {
        "nomeCiclo": ciclo.get("nome"),
        "vestibularAlvo": ciclo.get("vestibularAlvo"),
        "temCicloAnterior": payload.get("cicloAnterior") is not None,
    }

    # ── Conjunta (ciclo todo, F1+F2 agregados) ──
    payload["conjunta"]["insights"] = {
        "pratico": insights.gerar_para_recorte(
            cliente,
            ciclo_id=ciclo["id"],
            fase="todas",
            materia_codigo=None,
            tipo="pratico",
            stats_payload=payload["conjunta"],
            contexto={**contexto_base, "recorte": "conjunta"},
        ),
        "tecnico": insights.gerar_para_recorte(
            cliente,
            ciclo_id=ciclo["id"],
            fase="todas",
            materia_codigo=None,
            tipo="tecnico",
            stats_payload=payload["conjunta"],
            contexto={**contexto_base, "recorte": "conjunta"},
        ),
    }

    # ── Por matéria: gera insights agregando F1+F2 da matéria, mesmo molde ──
    for recorte_materia in payload.get("porMateria", []):
        materia = recorte_materia.get("materia") or {}
        codigo = materia.get("codigo")
        if not codigo:
            recorte_materia["insights"] = {"pratico": [], "tecnico": []}
            continue

        ctx_mat = {
            **contexto_base,
            "recorte": "materia",
            "materia": materia,
            "eliminatoriaF1": recorte_materia.get("eliminatoriaF1", False),
        }
        recorte_materia["insights"] = {
            "pratico": insights.gerar_para_recorte(
                cliente,
                ciclo_id=ciclo["id"],
                fase="todas",
                materia_codigo=codigo,
                tipo="pratico",
                stats_payload=recorte_materia,
                contexto=ctx_mat,
            ),
            "tecnico": insights.gerar_para_recorte(
                cliente,
                ciclo_id=ciclo["id"],
                fase="todas",
                materia_codigo=codigo,
                tipo="tecnico",
                stats_payload=recorte_materia,
                contexto=ctx_mat,
            ),
        }
