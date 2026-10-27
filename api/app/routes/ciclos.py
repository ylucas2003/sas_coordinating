"""Endpoints de ciclos."""

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..canvas_sync import escrita
from ..canvas_sync.pendencias import (
    TETO_NOTAS_POR_LOTE as TETO_NOTAS_POR_LOTE,  # test_envio_lote_canvas lê daqui
)
from ..canvas_sync.pendencias import pendencias_do_ciclo
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
        ordem=linha.get("ordem") or 0,
        anoLetivo=ano,
        vestibularAlvo=linha.get("vestibular_alvo"),
        periodoInicio=linha.get("periodo_inicio") or "",
        periodoFim=linha.get("periodo_fim") or "",
        simuladoIds=simulado_ids,
        canvasEstado=linha.get("canvas_estado"),
        canvasErro=linha.get("canvas_erro"),
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
        ordem=body.ordem,
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


def _pendencias_ou_404(cliente, ciclo_id: str) -> dict:
    """A leitura é do domínio (`canvas_sync/pendencias.py`, que a tool do
    assistente também chama); o 404 do ciclo inexistente é daqui."""
    pendencias = pendencias_do_ciclo(cliente, ciclo_id)
    if pendencias is None:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")
    return pendencias


@router.get("/{ciclo_id}/pendencias-canvas", response_model=dict)
def pendencias_canvas(
    ciclo_id: str,
    _: dict = Depends(get_current_coordenador),
) -> dict:
    """O que subiria se o coordenador mandasse o ciclo inteiro. Não escreve."""
    return _pendencias_ou_404(get_supabase(), ciclo_id)


@router.post("/{ciclo_id}/enviar-canvas-lote", response_model=dict)
async def enviar_ciclo_ao_canvas_em_lote(
    ciclo_id: str,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Manda o ciclo inteiro — grupo, simulados e notas — numa passada.

    Quatro exigências, e nenhuma é detalhe (docs/32 §4.2):

    1. **Ordem obrigatória: grupo → assignments → notas.** Um Assignment não
       entra num Assignment Group que não existe, e uma submission não existe
       sem o Assignment. Mandar fora de ordem produz falha que parece do
       Canvas e não é.
    2. **Resultado POR ITEM, nunca um "ok" agregado.** Sucesso parcial é o caso
       normal; um lote que diz "sucesso" tendo falhado em 3 de 12 é pior que
       não ter lote nenhum.
    3. **Idempotente.** Cada item reusa a função de escrita unitária de
       `canvas_sync/escrita.py`, que já é o único lugar por onde o SAS escreve
       no Canvas — reexecutar não duplica. Não se abre um segundo caminho de
       escrita.
    4. **Auditoria: um evento por item, mais um do lote.** É o que distingue
       "escolheu não mandar" de "mandou e falhou" daqui a três meses.
    """
    cliente = get_supabase()
    pendencias = _pendencias_ou_404(cliente, ciclo_id)
    ip = request.client.host if request.client else None
    ator = coordenador.get("sub")
    itens: list[dict] = []

    def registrar(tipo: str, id_: str, rotulo: str, ok: bool, erro: str | None) -> None:
        itens.append({"tipo": tipo, "id": id_, "rotulo": rotulo, "ok": ok, "erro": erro})
        auditar(
            cliente, "enviado_ao_canvas", canal="canvas",
            ator_tipo="coordenador", ator_id=ator, recurso=f"{tipo}/{id_}", ip=ip,
            detalhe={"lote": ciclo_id, "ok": ok, "erro": erro},
        )

    # ── 1 · o grupo ──
    grupo_ok = not pendencias["grupo"]["pendente"]
    if pendencias["grupo"]["pendente"]:
        resultado = await escrita.criar_grupo_do_ciclo(cliente, ciclo_id)
        grupo_ok = resultado.get("canvas_estado") == "sincronizado"
        registrar("ciclo", ciclo_id, pendencias["nome"] or ciclo_id, grupo_ok, resultado.get("erro"))

    # ⚠️ Sem o grupo, nada abaixo tem onde entrar. Parar aqui e DIZER que
    # parou é melhor que mandar 40 assignments para o lugar errado.
    if not grupo_ok:
        return _resumo_do_lote(itens, interrompido="o grupo do ciclo não foi criado no Canvas")

    # ── 2 · os simulados ──
    for simulado in pendencias["simulados"]:
        estado = await escrita.enviar_simulado(cliente, simulado["id"])
        registrar(
            "simulado", simulado["id"], simulado["nome"],
            estado == "sincronizado",
            None if estado == "sincronizado" else f"estado final: {estado}",
        )

    # ── 3 · as notas ──
    for nota in pendencias["notas"]:
        resultado = await escrita.enviar_nota(
            cliente, aluno_id=nota["alunoId"], simulado_id=nota["simuladoId"]
        )
        registrar(
            "nota", f"{nota['alunoId']}/{nota['simuladoId']}",
            f"{nota['aluno']} — {nota['simulado']}",
            bool(resultado.get("ok")), resultado.get("erro"),
        )

    resumo = _resumo_do_lote(itens)
    resumo["notasAlemDoTeto"] = pendencias["notasAlemDoTeto"]
    auditar(
        cliente, "enviado_ao_canvas", canal="canvas",
        ator_tipo="coordenador", ator_id=ator, recurso=f"ciclo/{ciclo_id}/lote", ip=ip,
        detalhe={k: resumo[k] for k in ("enviados", "falhas", "total")},
    )
    return resumo


def _resumo_do_lote(itens: list[dict], interrompido: str | None = None) -> dict:
    enviados = sum(1 for i in itens if i["ok"])
    return {
        "itens": itens,
        "total": len(itens),
        "enviados": enviados,
        "falhas": len(itens) - enviados,
        "interrompido": interrompido,
    }


@router.get("", response_model=list[Ciclo])
def listar_ciclos() -> list[Ciclo]:
    cliente = get_supabase()
    mapa = _agrupar_simulados_por_ciclo(cliente)
    resp = (
        cliente.table("ciclo")
        .select(
            "id, nome, ordem, vestibular_alvo, periodo_inicio, periodo_fim, "
            "canvas_estado, canvas_erro, ano_letivo(ano)"
        )
        .order("ordem")
        .execute()
    )
    return [_linha_para_ciclo(linha, mapa.get(linha["id"], [])) for linha in (resp.data or [])]


@router.get("/{ciclo_id}", response_model=Ciclo)
def obter_ciclo(ciclo_id: str) -> Ciclo:
    cliente = get_supabase()
    resp = (
        cliente.table("ciclo")
        .select(
            "id, nome, ordem, vestibular_alvo, periodo_inicio, periodo_fim, "
            "canvas_estado, canvas_erro, ano_letivo(ano)"
        )
        .eq("id", ciclo_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")

    mapa = _agrupar_simulados_por_ciclo(cliente)
    return _linha_para_ciclo(resp.data[0], mapa.get(ciclo_id, []))


@router.get("/{ciclo_id}/classificacao")
def classificacao_do_ciclo(
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
        "criterio": criterios.descrever_criterio(regua),
        "fase": fase if fase is not None else regua.fase,
        "total": len(linhas),
        "cortados": sum(1 for l in linhas if not l["aprovado"]),
        "alunos": linhas,
    }


@router.get("/criterios/disponiveis")
def criterios_disponiveis() -> list[dict]:
    """Os critérios que o seletor do painel oferece — embutidos e criados."""
    cliente = get_supabase()
    return [
        {**criterios.descrever_criterio(c), "embutido": c.slug in criterios.CRITERIOS}
        for c in criterios_repo.listar(cliente)
    ]


@router.get("/{ciclo_id}/estatisticas")
def estatisticas_do_ciclo(
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

    payload["criterio"] = criterios.descrever_criterio(regua)
    if com_insights:
        # `_anexar_insights` faz até QUATRO chamadas síncronas de LLM em série.
        # Este handler é `def` (threadpool do FastAPI), então a espera não trava
        # o event loop — antes ele era `async def` e a fronteira era um
        # `asyncio.to_thread` explícito, porque chamado direto congelava a API
        # inteira por dezenas de segundos: o balcão da cantina esperando a ficha
        # de ciclo de outra pessoa (docs/40 §12.1.1). Ao virar `def` por causa da
        # performance da ficha (29/09/2026), o `to_thread` deixou de ser preciso.
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
