"""Endpoints de ciclos."""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..canvas_sync import escrita
from ..schemas.domain import Ciclo, VestibularAlvo
from ..stats import (
    ciclo_estatisticas,
    classificacao_ciclo,
    criterios,
    criterios_repo,
    insights,
)
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
    # Sem default (docs/18 §2.3). False = o ciclo nasce sem Assignment Group,
    # em 'divergente'; simulados agendados nele ficam 'divergente' também até
    # alguém clicar "enviar ao Canvas" no ciclo.
    sincronizar_canvas: bool


@router.post("", response_model=Ciclo, status_code=201)
async def criar_ciclo(
    body: CriarCicloBody,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> Ciclo:
    """Cria um ciclo no SAS e, se pedido, o Assignment Group no Canvas.

    Era transacional ("ciclo sem grupo no Canvas não serve pra nada"). Deixou
    de ser quando a coordenação decidiu que nada sobe ao Canvas sem alguém
    clicar (docs/18 §2.1): o ciclo nasce sempre; sem `sincronizar_canvas`
    fica 'divergente', e `POST /ciclos/{id}/enviar-canvas` cria o grupo
    depois. Um simulado agendado num ciclo sem grupo herda o 'divergente'.
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

    linha = (
        cliente.table("ciclo")
        .insert(
            {
                "ano_letivo_id": ano_letivo["id"],
                "ordem": body.ordem,
                "nome": f"Ciclo {body.ordem} · {body.vestibular} · {ano_letivo['ano']}",
                "vestibular_alvo": body.vestibular,
                "canvas_estado": "pendente" if body.sincronizar_canvas else escrita.DIVERGENTE,
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    resultado = {"canvas_estado": escrita.DIVERGENTE}
    if body.sincronizar_canvas:
        resultado = await escrita.criar_grupo_do_ciclo(cliente, linha["id"])

    auditar(
        cliente, "ciclo_criado", canal="ciclo",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"ciclo/{linha['id']}",
        ip=request.client.host if request.client else None,
        detalhe={
            "nome": linha["nome"],
            "sincronizar_canvas": body.sincronizar_canvas,
            "canvas_estado": resultado["canvas_estado"],
            "canvas_erro": resultado.get("erro"),
        },
    )

    return Ciclo(
        id=linha["id"],
        nome=linha["nome"],
        anoLetivo=ano_letivo["ano"],
        vestibularAlvo=linha.get("vestibular_alvo"),
        periodoInicio="",
        periodoFim="",
        simuladoIds=[],
    )


@router.post("/{ciclo_id}/enviar-canvas", response_model=dict)
async def enviar_ciclo_ao_canvas(
    ciclo_id: str,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Cria o Assignment Group de um ciclo 'divergente' ou 'falhou'. É o único
    caminho que tira um ciclo de 'divergente' (docs/18 §2.5)."""
    cliente = get_supabase()
    resultado = await escrita.criar_grupo_do_ciclo(cliente, ciclo_id)
    auditar(
        cliente, "enviado_ao_canvas", canal="canvas",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"ciclo/{ciclo_id}",
        ip=request.client.host if request.client else None,
        detalhe=resultado,
    )
    if resultado["canvas_estado"] == "falhou" and resultado.get("erro") == "ciclo não encontrado":
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")
    return resultado


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
    cliente = get_supabase()
    try:
        # `resolver`, e não `por_slug`: as réguas que a coordenação cria só
        # existem no banco, e o Painel tem de conseguir classificar por elas.
        regua = criterios_repo.resolver(cliente, criterio)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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


#: As matérias do `materia` (carga inicial da 0001). Enumerar aqui é o que
#: permite entregar o corte de cada uma resolvido: o predicado `*` da régua do
#: colégio não sabe listar as disciplinas que ele cobre.
_MATERIAS_CONHECIDAS = ("matematica", "fisica", "quimica", "portugues", "ingles", "redacao")


@router.get("/criterios/disponiveis")
async def criterios_disponiveis() -> list[dict]:
    """Os critérios que o seletor do painel oferece — embutidos e criados."""
    cliente = get_supabase()
    return [
        {**_descrever_criterio(c), "embutido": c.slug in criterios.CRITERIOS}
        for c in criterios_repo.listar(cliente)
    ]


def _descrever_criterio(c: criterios.Criterio) -> dict:
    """Forma serializável de um critério — legenda, tooltip e cortes prontos.

    `cortes`, `corteGenerico` e `corteMedia` existem para o front **não**
    precisar reimplementar `corte_da_materia`. Sem eles, desenhar a linha do
    corte num gráfico obriga a percorrer `predicados` procurando a matéria e
    caindo no `*` — que é a regra de corte outra vez, em TypeScript, que é
    exatamente o que a Sprint 2 proibiu (docs/18 §1.2).
    """
    return {
        "slug": c.slug,
        "nome": c.nome,
        "descricao": c.descricao,
        "fase": c.fase,
        "combinador": c.combinador,
        "desempate": list(c.desempate),
        # Mínimo por matéria já resolvido, incluindo o que vem do `*`.
        "cortes": {
            codigo: criterios.corte_da_materia(c, codigo)
            for codigo in _MATERIAS_CONHECIDAS
            if criterios.corte_da_materia(c, codigo) is not None
        },
        "corteGenerico": criterios.corte_da_materia(c, "__qualquer__"),
        "corteMedia": criterios.corte_da_media(c),
        "eliminatorias": [
            codigo for codigo in _MATERIAS_CONHECIDAS if criterios.e_eliminatoria(c, codigo)
        ],
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
    criterio: str = Query(
        criterios.CRITERIO_DA_CASA,
        description="Slug da régua que define os cortes do payload. Default: a régua da casa.",
    ),
) -> dict:
    """Payload completo do ciclo — F1, F2, análise conjunta e por matéria.

    Estrutura: ver `ciclo_estatisticas.calcular`. O front renderiza tudo
    numa única página vertical, sem filtros de fase. Insights são gerados
    em duas linguagens: 'pratico' (visível por default) e 'tecnico' (dentro
    da seção "dados estatísticos avançados").

    `criterio` decide TODOS os cortes do payload — a linha vertical dos
    histogramas e o `pctAprovados` de cada bloco. É o mesmo parâmetro de
    `/classificacao`, de propósito: com ele, trocar a régua no Painel move a
    tabela e o gráfico juntos, que era a divergência descrita em docs/31 §1.1.

    Insights LLM são opcionais (controlados por `com_insights`) e retornam
    listas vazias se OPENAI_API_KEY não estiver configurada.
    """
    cliente = get_supabase()
    try:
        regua = criterios_repo.resolver(cliente, criterio)
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id, criterio=regua)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")

    payload["criterio"] = _descrever_criterio(regua)
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
        # Qual régua produziu os cortes deste payload. Sem isto o modelo
        # escrevia "62% abaixo do corte de 4,0" ao lado de um histograma com a
        # linha em 5,0 — os prompts decoravam o par 4,0/5,0 e o bloco conjunta
        # não carregava `corte` nenhum.
        "regua": (payload.get("criterio") or {}).get("nome"),
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
            "eliminatoria": recorte_materia.get("eliminatoria", False),
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
