"""Endpoints de ciclos."""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..auth import get_current_coordenador
from ..canvas_sync import mapeador
from ..canvas_sync.cliente import ClienteCanvas
from ..config import get_settings
from ..schemas.domain import Ciclo, VestibularAlvo
from ..stats import ciclo_estatisticas, classificacao_ciclo, criterios, insights
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/ciclos",
    tags=["ciclos"],
    dependencies=[Depends(get_current_coordenador)],
)


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


class CriarCicloBody(BaseModel):
    ordem: int = Field(gt=0, le=99)
    vestibular: VestibularAlvo
    ano: int | None = None   # None = ano vigente (maior ano com curso no Canvas)


@router.post("", response_model=Ciclo, status_code=201)
async def criar_ciclo(body: CriarCicloBody) -> Ciclo:
    """Cria um ciclo no SAS E o Assignment Group correspondente no Canvas.

    TRANSACIONAL (diferente do simulado, que é híbrido): um ciclo que existe
    no SAS mas não no Canvas não serve pra nada — nenhum simulado pode nascer
    nele. Se o Canvas recusar, nada é salvo e o coordenador vê o erro.
    """
    cliente = get_supabase()

    # Ano letivo de destino: o pedido, ou o maior com curso conhecido.
    consulta = cliente.table("ano_letivo").select("id, ano, canvas_course_id")
    if body.ano is not None:
        consulta = consulta.eq("ano", body.ano)
    anos = (consulta.order("ano", desc=True).execute()).data or []
    anos_com_curso = [a for a in anos if a.get("canvas_course_id")]
    if not anos_com_curso:
        raise HTTPException(
            status_code=409,
            detail="Nenhum ano letivo com curso do Canvas conhecido — rode o sync antes.",
        )
    ano_letivo = anos_com_curso[0]

    existente = (
        cliente.table("ciclo")
        .select("id, vestibular_alvo")
        .eq("ano_letivo_id", ano_letivo["id"])
        .eq("ordem", body.ordem)
        .limit(1)
        .execute()
    )
    if existente.data:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ciclo {body.ordem} de {ano_letivo['ano']} já existe "
                f"({existente.data[0].get('vestibular_alvo') or 'sem vestibular'}). "
                "Cada ordem de ciclo tem um único vestibular."
            ),
        )

    settings = get_settings()
    if not settings.canvas_base_url or not settings.canvas_api_token:
        raise HTTPException(status_code=502, detail="Canvas não configurado no servidor.")

    nome_grupo = mapeador.compor_nome_grupo_ciclo(ordem=body.ordem, vestibular=body.vestibular)
    try:
        async with ClienteCanvas(
            base_url=settings.canvas_base_url, token=settings.canvas_api_token
        ) as canvas:
            grupo = await canvas.criar_assignment_group(
                str(ano_letivo["canvas_course_id"]), nome=nome_grupo
            )
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"Canvas recusou a criação do grupo: {exc}"
        )

    linha = (
        cliente.table("ciclo")
        .insert(
            {
                "ano_letivo_id": ano_letivo["id"],
                "ordem": body.ordem,
                "nome": f"Ciclo {body.ordem} · {body.vestibular} · {ano_letivo['ano']}",
                "vestibular_alvo": body.vestibular,
                "canvas_assignment_group_id": str(grupo["id"]),
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    return Ciclo(
        id=linha["id"],
        nome=linha["nome"],
        anoLetivo=ano_letivo["ano"],
        vestibularAlvo=linha.get("vestibular_alvo"),
        periodoInicio="",
        periodoFim="",
        simuladoIds=[],
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


@router.get("/{ciclo_id}/classificacao")
async def classificacao_do_ciclo(
    ciclo_id: str,
    criterio: str = Query(
        "tio-leo",
        description="Slug do critério: tio-leo | ita-f1 | ita-f2 | ime-f1 | ime-f2.",
    ),
    fase: int | None = Query(
        None, ge=1, le=2, description="Restringe às notas de uma fase. Default: a do critério."
    ),
) -> dict:
    """Lista ordenada do ciclo segundo um critério — o painel só desenha.

    Toda regra de corte vive em app/stats/criterios.py (docs/18 §1.2). Esta
    rota é o único caminho pelo qual o front obtém veredito, motivo, cor e
    posição: a regra deixa de existir em TypeScript.

    A resposta carrega o critério usado para o front mostrar a legenda certa
    ("corte abaixo de 4,0 · ITA §4.6.6.5") sem conhecer a regra.
    """
    try:
        regua = criterios.por_slug(criterio)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cliente = get_supabase()
    existe = cliente.table("ciclo").select("id").eq("id", ciclo_id).limit(1).execute()
    if not existe.data:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")

    linhas = classificacao_ciclo.classificar(
        cliente, ciclo_id=ciclo_id, criterio=regua, fase=fase
    )
    return {
        "criterio": _descrever_criterio(regua),
        "fase": fase if fase is not None else regua.fase,
        "total": len(linhas),
        "cortados": sum(1 for l in linhas if not l["aprovado"]),
        "alunos": linhas,
    }


@router.get("/criterios/disponiveis")
async def criterios_disponiveis() -> list[dict]:
    """Os critérios que o seletor do painel oferece."""
    return [_descrever_criterio(c) for c in criterios.CRITERIOS.values()]


def _descrever_criterio(c: criterios.Criterio) -> dict:
    """Forma serializável de um critério — o suficiente para legenda e tooltip."""
    return {
        "slug": c.slug,
        "nome": c.nome,
        "descricao": c.descricao,
        "fase": c.fase,
        "combinador": c.combinador,
        "desempate": list(c.desempate),
        "predicados": [
            {
                "materia": p.materia,
                "operador": p.operador,
                "minimo": (
                    {"acertos": p.valor.acertos, "de": p.valor.de}
                    if isinstance(p.valor, criterios.Acertos)
                    else p.valor
                ),
                "eliminatorio": p.eliminatorio,
                "entraNaMedia": p.entra_na_media,
                "peso": p.peso,
                "fonte": p.fonte,
            }
            for p in c.predicados
        ],
    }


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
