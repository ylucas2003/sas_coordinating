"""Endpoints de simulados.

As métricas (media, mediana, desvioPadrao, nPresentes) vêm da tabela de cache
`metrica_simulado` (recorte_tipo='geral'), preenchida pelo stats engine ao
fim de cada upload — frontend nunca calcula nada.
"""

import re
from datetime import UTC, date, time

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from supabase import Client

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..canvas_sync import escrita, mapeador
from ..config import get_settings
from ..lembretes import motor as lembretes
from ..lembretes.aplicacoes import aluno_simulado
from ..lembretes.email import email_configurado
from ..schemas.domain import MateriaResumo, Simulado, TipoSimulado
from ..stats.classificacao import recalcular_tudo as recalcular_classificacoes
from ..stats.metricas import (
    carregar_metrica_geral,
    corte_aplicavel,
    mapa_metrica_geral_por_simulado,
    recalcular_simulado,
)
from ..stats.utils import como_float, nota_real
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/simulados",
    tags=["simulados"],
    dependencies=[Depends(get_current_coordenador)],
)


_CAMPOS_SIMULADO = (
    "id, nome, rotulo_curto, tipo, data_aplicacao, ciclo_id, materia_id, "
    "nota_maxima, anulado, origem, canvas_estado, canvas_erro, evento_agenda_id, "
    "external_id"
)


def _mapa_materias(cliente: Client) -> dict[str, MateriaResumo]:
    resp = cliente.table("materia").select("id, codigo, nome").execute()
    return {
        m["id"]: MateriaResumo(codigo=m["codigo"], nome=m["nome"])
        for m in (resp.data or [])
    }


def _mapa_ciclos(cliente: Client) -> dict[str, dict]:
    resp = cliente.table("ciclo").select("id, ordem, vestibular_alvo").execute()
    return {c["id"]: c for c in (resp.data or [])}


def _linha_para_simulado(
    linha: dict,
    metrica: dict | None,
    materias: dict[str, MateriaResumo],
    ciclos: dict[str, dict],
) -> Simulado:
    ciclo = ciclos.get(linha["ciclo_id"], {})
    materia_id = linha.get("materia_id")
    return Simulado(
        id=linha["id"],
        nome=linha["nome"],
        rotuloCurto=linha.get("rotulo_curto"),
        tipo=linha.get("tipo"),
        materia=materias.get(materia_id) if materia_id else None,
        dataAplicacao=linha["data_aplicacao"],
        cicloId=linha["ciclo_id"],
        cicloOrdem=ciclo.get("ordem"),
        vestibularAlvo=ciclo.get("vestibular_alvo"),
        notaMaxima=float(linha.get("nota_maxima") or 0),
        anulado=bool(linha.get("anulado")),
        origem=linha.get("origem") or "canvas",
        canvasEstado=linha.get("canvas_estado") or "sincronizado",
        canvasErro=linha.get("canvas_erro"),
        media=como_float((metrica or {}).get("media")),
        mediana=como_float((metrica or {}).get("mediana")),
        desvioPadrao=como_float((metrica or {}).get("desvio_padrao")),
        nPresentes=(metrica or {}).get("n_presentes"),
    )


@router.get("", response_model=list[Simulado])
async def listar_simulados() -> list[Simulado]:
    cliente = get_supabase()
    metricas = mapa_metrica_geral_por_simulado(cliente)
    materias = _mapa_materias(cliente)
    ciclos = _mapa_ciclos(cliente)
    resp = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .order("data_aplicacao", desc=True)
        .execute()
    )
    return [
        _linha_para_simulado(linha, metricas.get(linha["id"]), materias, ciclos)
        for linha in (resp.data or [])
    ]


# ─── Agendamento (P1 — o simulado nasce no SAS) ───────────────────────────


class AgendarSimuladoBody(BaseModel):
    cicloId: str
    rotuloCurto: str = Field(pattern=r"^P\d+$")   # "P2", "P27" — gramática do nome
    materiaId: str
    dataAplicacao: date
    hora: time = time(7, 0)
    notaMaxima: int = Field(gt=0, description="Número de questões da prova")
    tipo: TipoSimulado
    lembrarDiasAntes: int | None = Field(
        default=None, ge=0,
        description="Lembrete por e-mail pro coordenador X dias antes (P2). "
                    "0 = no dia, na hora do simulado.",
    )
    avisarAlunos: bool = Field(
        default=True,
        description="Lembrete automático pros alunos na véspera (P3). A regra "
                    "nasce aqui; os disparos, na véspera (docs/13 §1).",
    )
    # Sem default: a rota nunca decide sozinha se escreve no Canvas. O
    # coordenador escolhe a cada ação (docs/18 §2.3). False = o simulado
    # nasce 'divergente' e o retry automático não o toca.
    sincronizarCanvas: bool


@router.post("/agendar", response_model=Simulado, status_code=201)
async def agendar_simulado(
    body: AgendarSimuladoBody,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> Simulado:
    """Cria um simulado no SAS (fase pré-aplicação) e, se pedido, o Assignment.

    A linha nasce sempre (com evento de agenda). Com `sincronizarCanvas` a
    criação lá é tentada na hora e, se falhar, fica 'falhou' com retry no
    sync de 5 min. Sem, fica 'divergente' — o coordenador escolheu, e o retry
    não mexe (docs/18 §2.5). Os lembretes disparam de qualquer jeito: o
    motor é do SAS e não depende do Canvas (docs/18 §2.6).
    """
    cliente = get_supabase()

    # Antes de criar qualquer coisa: lembrete pedido sem SES configurado é
    # 422 na cara — degradar em silêncio aqui seria um lembrete que nunca
    # chega, pior que erro (docs/12 §1).
    if body.lembrarDiasAntes is not None and not email_configurado():
        raise HTTPException(
            status_code=422,
            detail="Lembrete por e-mail indisponível: SES não configurado no "
                   "servidor (AWS_SES_* e EMAIL_REMETENTE). Agende sem lembrete "
                   "ou configure o envio.",
        )

    ciclo_resp = (
        cliente.table("ciclo")
        .select("id, ordem, vestibular_alvo, canvas_assignment_group_id")
        .eq("id", body.cicloId)
        .limit(1)
        .execute()
    )
    if not ciclo_resp.data:
        raise HTTPException(status_code=404, detail=f"ciclo {body.cicloId} não encontrado")
    ciclo = ciclo_resp.data[0]

    materia_resp = (
        cliente.table("materia")
        .select("id, nome")
        .eq("id", body.materiaId)
        .limit(1)
        .execute()
    )
    if not materia_resp.data:
        raise HTTPException(status_code=404, detail=f"matéria {body.materiaId} não encontrada")
    materia = materia_resp.data[0]

    # Guarda de duplo clique — a checagem explícita cobre o que o índice
    # parcial (que não vê materia_id NULL) cobre e mais um pouco.
    duplicado = (
        cliente.table("simulado")
        .select("id")
        .eq("ciclo_id", ciclo["id"])
        .eq("rotulo_curto", body.rotuloCurto)
        .eq("materia_id", materia["id"])
        .limit(1)
        .execute()
    )
    if duplicado.data:
        raise HTTPException(
            status_code=409,
            detail=f"{body.rotuloCurto} de {materia['nome']} já existe neste ciclo.",
        )

    # O nome é DERIVADO (ciclo, rótulo, matéria, data) — mesma gramática que o
    # sync lê. É o que faz SAS e Canvas falarem a mesma língua.
    nome = mapeador.compor_nome_assignment(
        ciclo_ordem=ciclo["ordem"],
        rotulo_curto=body.rotuloCurto,
        materia_nome=materia["nome"],
        data_aplicacao=body.dataAplicacao,
    )

    settings = get_settings()
    evento = (
        cliente.table("evento_agenda")
        .insert(
            {
                "tipo": "simulado",
                "titulo": nome,
                "data_evento": body.dataAplicacao.isoformat(),
                "hora_evento": body.hora.strftime("%H:%M"),
                "criado_por": settings.coordenador_email,
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    simulado_linha = (
        cliente.table("simulado")
        .insert(
            {
                "ciclo_id": ciclo["id"],
                "materia_id": materia["id"],
                "nome": nome,
                "rotulo_curto": body.rotuloCurto,
                "data_aplicacao": body.dataAplicacao.isoformat(),
                "nota_maxima": body.notaMaxima,
                "tipo": body.tipo,
                "e_agregado": False,
                "origem": "sas",
                "canvas_estado": "pendente" if body.sincronizarCanvas else escrita.DIVERGENTE,
                "evento_agenda_id": evento["id"],
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    estado_canvas = escrita.DIVERGENTE
    if body.sincronizarCanvas:
        estado_canvas = await escrita.enviar_simulado(cliente, simulado_linha["id"])

    auditar(
        cliente, "simulado_criado", canal="simulado",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"simulado/{simulado_linha['id']}",
        ip=request.client.host if request.client else None,
        detalhe={
            "nome": nome, "data_aplicacao": body.dataAplicacao.isoformat(),
            "sincronizar_canvas": body.sincronizarCanvas, "canvas_estado": estado_canvas,
        },
    )

    # Lembretes por último: são acessórios do evento — se algo falhar aqui, o
    # agendamento já está de pé (docs/12 §4.5).
    if body.lembrarDiasAntes is not None:
        lembretes.criar_regra_com_disparo(
            cliente,
            evento=evento,
            dias_antes=body.lembrarDiasAntes,
            destinatario=evento.get("criado_por") or settings.coordenador_email,
        )

    # Aluno: só a REGRA nasce aqui. Os disparos são materializados na véspera
    # pela varredura (docs/13 §1) — o elenco de alunos de daqui a 40 dias não
    # é o de hoje. Sem SES configurado a regra é criada mesmo assim: diferente
    # do lembrete do coordenador (422), este é acessório do simulado e não
    # pode impedir o agendamento; se o SES não existir na véspera, o disparo
    # falha e fica registrado como estado.
    if body.avisarAlunos:
        cliente.table("regra_lembrete").insert(
            {
                "evento_agenda_id": evento["id"],
                "destinatario_tipo": "aluno",
                "canal": "email",
                "dias_antes": aluno_simulado.DIAS_ANTES,
            }
        ).execute()

    return await obter_simulado(simulado_linha["id"])


@router.get("/{simulado_id}", response_model=Simulado)
async def obter_simulado(simulado_id: str) -> Simulado:
    cliente = get_supabase()
    resp = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")
    metrica = carregar_metrica_geral(cliente, simulado_id)
    materias = _mapa_materias(cliente)
    ciclos = _mapa_ciclos(cliente)
    return _linha_para_simulado(resp.data[0], metrica, materias, ciclos)


@router.get("/{simulado_id}/histograma")
async def histograma_simulado(simulado_id: str) -> dict:
    """Distribuição de notas em bins de 0,5 ponto. Lê direto de metrica_simulado."""
    cliente = get_supabase()
    metrica = carregar_metrica_geral(cliente, simulado_id)
    if metrica is None:
        raise HTTPException(status_code=404, detail=f"métrica de {simulado_id} ainda não calculada")
    return {
        "histograma": metrica.get("histograma"),
        "media": como_float(metrica.get("media")),
        "mediana": como_float(metrica.get("mediana")),
        "desvioPadrao": como_float(metrica.get("desvio_padrao")),
        "quartil1": como_float(metrica.get("quartil_1")),
        "quartil3": como_float(metrica.get("quartil_3")),
        "nPresentes": metrica.get("n_presentes"),
        "nAusentes": metrica.get("n_ausentes"),
    }


@router.get("/{simulado_id}/notas")
async def listar_notas_simulado(simulado_id: str) -> list[dict]:
    """Tabela completa: aluno × nota (em escala 0–10). Usada na ficha do simulado.

    Também devolve `acertos` (pontuação bruta) e `total` (nota_maxima) caso
    a UI queira mostrar "12/20" ao lado da nota.
    """
    cliente = get_supabase()
    base = (
        cliente.table("simulado")
        .select("nota_maxima")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not base.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")
    nota_maxima_sim = como_float(base.data[0].get("nota_maxima"))

    resp = (
        cliente.table("nota")
        .select("pontuacao, presente, aluno(id, nome)")
        .eq("simulado_id", simulado_id)
        .execute()
    )
    saida: list[dict] = []
    for linha in resp.data or []:
        aluno = linha.get("aluno") or {}
        pontuacao_bruta = como_float(linha.get("pontuacao"))
        nota = nota_real(pontuacao_bruta, nota_maxima_sim)
        saida.append(
            {
                "alunoId": aluno.get("id"),
                "nome": aluno.get("nome", ""),
                "nota": round(nota, 2) if nota is not None else None,   # 0–10
                "acertos": pontuacao_bruta,                              # bruto
                "total": nota_maxima_sim,
                "presente": bool(linha.get("presente")),
            }
        )
    saida.sort(key=lambda r: (not r["presente"], -(r["nota"] or 0)))
    return saida


@router.get("/{simulado_id}/por-materia")
async def metricas_por_materia(simulado_id: str) -> list[dict]:
    """Quebra por matéria.

    No schema atual, cada simulado tem uma única `materia_id` (ou None se
    agregado). Pra uma quebra real "por matéria dentro de uma prova de dia",
    olhamos os simulados irmãos do mesmo ciclo+data e exibimos lado a lado.
    """
    cliente = get_supabase()
    base = (
        cliente.table("simulado")
        .select("id, ciclo_id, data_aplicacao, materia_id")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not base.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")

    alvo = base.data[0]
    irmaos = (
        cliente.table("simulado")
        .select("id, nome, materia_id, anulado")
        .eq("ciclo_id", alvo["ciclo_id"])
        .eq("data_aplicacao", alvo["data_aplicacao"])
        .eq("anulado", False)
        .execute()
    )

    materias = cliente.table("materia").select("id, nome").execute()
    nome_materia = {m["id"]: m["nome"] for m in (materias.data or [])}

    metricas = mapa_metrica_geral_por_simulado(cliente)
    linhas: list[dict] = []
    for s in irmaos.data or []:
        if not s.get("materia_id"):
            continue
        m = metricas.get(s["id"]) or {}
        linhas.append(
            {
                "simuladoId": s["id"],
                "nome": s["nome"],
                "materia": nome_materia.get(s["materia_id"], "?"),
                "media": como_float(m.get("media")),
                "mediana": como_float(m.get("mediana")),
                "desvioPadrao": como_float(m.get("desvio_padrao")),
                "nPresentes": m.get("n_presentes"),
            }
        )
    linhas.sort(key=lambda r: r["materia"])
    return linhas


@router.get("/{simulado_id}/por-sede")
async def metricas_por_sede(simulado_id: str) -> list[dict]:
    """Quebra do simulado por sede (a partir de metrica_simulado)."""
    cliente = get_supabase()
    metricas_resp = (
        cliente.table("metrica_simulado")
        .select("recorte_id, media, mediana, desvio_padrao, n_presentes")
        .eq("simulado_id", simulado_id)
        .eq("recorte_tipo", "sede")
        .execute()
    )
    sedes = cliente.table("sede").select("id, nome").execute()
    nome_sede = {s["id"]: s["nome"] for s in (sedes.data or [])}

    linhas: list[dict] = []
    for linha in metricas_resp.data or []:
        sid = linha.get("recorte_id")
        linhas.append(
            {
                "sedeId": sid,
                "sede": nome_sede.get(sid, "?"),
                "media": como_float(linha.get("media")),
                "mediana": como_float(linha.get("mediana")),
                "desvioPadrao": como_float(linha.get("desvio_padrao")),
                "nPresentes": linha.get("n_presentes"),
            }
        )
    linhas.sort(key=lambda r: -(r["media"] or 0))
    return linhas


# ─── Edição manual ────────────────────────────────────────────────────────


class PatchSimuladoBody(BaseModel):
    anulado: bool | None = None
    nota_maxima: float | None = None
    rotulo_curto: str | None = None
    nome: str | None = None
    data_aplicacao: date | None = None   # remarcar — só simulados origem='sas'
    # Sem default (docs/18 §2.3). Só tem efeito em simulados origem='sas';
    # os do Canvas nunca recebem write-back daqui.
    sincronizar_canvas: bool


@router.patch("/{simulado_id}", response_model=Simulado)
async def editar_simulado(
    simulado_id: str,
    body: PatchSimuladoBody,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> Simulado:
    """Edita campos de um simulado.

    Campos aceitos: anulado, nota_maxima, rotulo_curto, nome, data_aplicacao.

    - anulado=true  → métricas do simulado são removidas do cache; classificações
                       recalculadas (o simulado sai das janelas de notas).
    - anulado=false → simulado reativado; métricas e classificações recalculadas.
    - nota_maxima   → escala de normalização muda; métricas e classificações
                       recalculadas.
    - rotulo_curto / nome → sem impacto em estatísticas.

    Simulados origem='sas' (nascidos no agendamento): `nome` não é editável —
    ele é DERIVADO de (ciclo, rótulo, matéria, data) e se recompõe quando as
    partes mudam. `data_aplicacao` (remarcar) só existe pra eles, atualiza o
    evento de agenda junto, e toda edição faz write-back no Canvas.
    """
    cliente = get_supabase()

    resp = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")

    simulado_atual = resp.data[0]
    anulado_antes = bool(simulado_atual.get("anulado"))
    e_do_sas = simulado_atual.get("origem") == "sas"

    atualizacao: dict = {}
    if body.anulado is not None:
        atualizacao["anulado"] = body.anulado
    if body.nota_maxima is not None:
        if body.nota_maxima <= 0:
            raise HTTPException(status_code=422, detail="nota_maxima deve ser positiva")
        atualizacao["nota_maxima"] = body.nota_maxima
    if body.rotulo_curto is not None:
        if e_do_sas and not re.fullmatch(r"P\d+", body.rotulo_curto):
            raise HTTPException(
                status_code=422,
                detail="rotulo_curto de simulado agendado deve seguir o padrão P<n> (ex.: P2)",
            )
        atualizacao["rotulo_curto"] = body.rotulo_curto
    if body.nome is not None:
        if e_do_sas:
            raise HTTPException(
                status_code=422,
                detail=(
                    "O nome de um simulado agendado é derivado de ciclo, rótulo, "
                    "matéria e data — edite as partes, o nome se recompõe."
                ),
            )
        atualizacao["nome"] = body.nome
    if body.data_aplicacao is not None:
        if not e_do_sas:
            raise HTTPException(
                status_code=422,
                detail="data_aplicacao de simulado do Canvas é do Canvas — não editável aqui.",
            )
        atualizacao["data_aplicacao"] = body.data_aplicacao.isoformat()

    if not atualizacao:
        raise HTTPException(status_code=422, detail="Nenhum campo informado para atualizar")

    # Recompor o nome quando alguma parte dele mudou (só origem='sas').
    if e_do_sas and ("rotulo_curto" in atualizacao or "data_aplicacao" in atualizacao):
        ciclo_resp = (
            cliente.table("ciclo").select("ordem")
            .eq("id", simulado_atual["ciclo_id"]).limit(1).execute()
        )
        materia_resp = (
            cliente.table("materia").select("nome")
            .eq("id", simulado_atual["materia_id"]).limit(1).execute()
        )
        if ciclo_resp.data and materia_resp.data:
            atualizacao["nome"] = mapeador.compor_nome_assignment(
                ciclo_ordem=ciclo_resp.data[0]["ordem"],
                rotulo_curto=atualizacao.get("rotulo_curto")
                or simulado_atual["rotulo_curto"],
                materia_nome=materia_resp.data[0]["nome"],
                data_aplicacao=date.fromisoformat(
                    atualizacao.get("data_aplicacao")
                    or str(simulado_atual["data_aplicacao"])
                ),
            )

    # Edição em simulado do SAS: com sincronizar_canvas, cai pra 'pendente'
    # até o PUT confirmar (falha → 'falhou' → retry do sync). Sem, fica
    # 'divergente': o coordenador escolheu e o retry não toca (docs/18 §2.5).
    if e_do_sas:
        atualizacao["canvas_estado"] = "pendente" if body.sincronizar_canvas else escrita.DIVERGENTE

    cliente.table("simulado").update(atualizacao).eq("id", simulado_id).execute()

    # Remarcar mantém o evento de agenda em dia — é dele que P2 vai derivar
    # os disparos de lembrete.
    if e_do_sas and simulado_atual.get("evento_agenda_id"):
        patch_evento: dict = {}
        if "data_aplicacao" in atualizacao:
            patch_evento["data_evento"] = atualizacao["data_aplicacao"]
        if "nome" in atualizacao:
            patch_evento["titulo"] = atualizacao["nome"]
        if patch_evento:
            cliente.table("evento_agenda").update(patch_evento).eq(
                "id", simulado_atual["evento_agenda_id"]
            ).execute()
        # Remarque invalida os disparos pendentes de lembrete — regera com a
        # data nova (a guarda no envio cobre a corrida; docs/12 §4.3).
        if "data_aplicacao" in atualizacao:
            lembretes.regerar_disparos_do_evento(
                cliente, simulado_atual["evento_agenda_id"]
            )

    estado_canvas = atualizacao.get("canvas_estado")
    if e_do_sas and body.sincronizar_canvas:
        estado_canvas = await escrita.enviar_simulado(cliente, simulado_id)

    auditar(
        cliente, "simulado_editado", canal="simulado",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"simulado/{simulado_id}",
        ip=request.client.host if request.client else None,
        detalhe={
            "campos": {k: (str(v) if v is not None else None) for k, v in atualizacao.items()
                       if k != "canvas_estado"},
            "origem": simulado_atual.get("origem"),
            "sincronizar_canvas": body.sincronizar_canvas if e_do_sas else None,
            "canvas_estado": estado_canvas,
        },
    )

    anulado_novo = atualizacao.get("anulado", anulado_antes)
    muda_stats = "anulado" in atualizacao or "nota_maxima" in atualizacao

    if muda_stats:
        if anulado_novo:
            # Remove cache de métricas — recalcular_tudo ignora anulados mas
            # não limpa registros anteriores. Limpamos manualmente.
            cliente.table("metrica_simulado").delete().eq("simulado_id", simulado_id).execute()
        else:
            # Reativado ou nota_maxima mudou: recalcula métricas deste simulado.
            simulado_para_corte = {**simulado_atual, **atualizacao}
            nota_maxima = como_float(simulado_para_corte.get("nota_maxima")) or 10.0
            corte = corte_aplicavel(simulado_para_corte)
            recalcular_simulado(
                cliente,
                simulado_id=simulado_id,
                nota_maxima=nota_maxima,
                corte=corte,
            )
        recalcular_classificacoes(cliente)

    resp_novo = (
        cliente.table("simulado")
        .select(_CAMPOS_SIMULADO)
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    metrica = carregar_metrica_geral(cliente, simulado_id)
    materias = _mapa_materias(cliente)
    ciclos = _mapa_ciclos(cliente)
    return _linha_para_simulado(resp_novo.data[0], metrica, materias, ciclos)


@router.post("/{simulado_id}/retry-canvas", response_model=Simulado)
async def retry_canvas(
    simulado_id: str,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> Simulado:
    """Botão "enviar ao Canvas agora" — serve tanto pra 'falhou' (zera o
    contador, que o reprocessamento desiste em 5) quanto pra 'divergente'
    (o coordenador mudou de ideia). É o ÚNICO caminho que tira um simulado
    de 'divergente': o automático nunca faz isso (docs/18 §2.5)."""
    cliente = get_supabase()
    resp = (
        cliente.table("simulado")
        .select("id, origem")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")
    if resp.data[0].get("origem") != "sas":
        raise HTTPException(status_code=422, detail="Simulado do Canvas não precisa de retry.")

    cliente.table("simulado").update(
        {"canvas_tentativas": 0, "canvas_estado": "pendente"}
    ).eq("id", simulado_id).execute()
    estado = await escrita.enviar_simulado(cliente, simulado_id)
    auditar(
        cliente, "enviado_ao_canvas", canal="canvas",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"simulado/{simulado_id}",
        ip=request.client.host if request.client else None,
        detalhe={"canvas_estado": estado},
    )
    return await obter_simulado(simulado_id)


@router.delete("/{simulado_id}", status_code=200)
async def cancelar_simulado(
    simulado_id: str,
    request: Request,
    sincronizar_canvas: bool = Query(
        ...,
        description="Apagar também o Assignment no Canvas. Sem default: é a única "
                    "operação irreversível das cinco (docs/18 §2.2) — leva as "
                    "submissions dos alunos junto.",
    ),
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Desmarca um simulado agendado (origem='sas', sem notas).

    Com `sincronizar_canvas`, o Assignment é apagado do Canvas (aluno não vê
    prova fantasma). Sem, ele FICA lá, órfão de propósito — e o external_id
    vai para a auditoria, porque é o único rastro que sobra dele no SAS. A
    linha de simulado sai do banco; o REGISTRO HISTÓRICO de que a prova
    chegou a ser agendada fica em evento_agenda.cancelado_em — que é também
    o que P2 consulta pra matar os disparos pendentes.
    """
    cliente = get_supabase()
    resp = (
        cliente.table("simulado")
        .select("id, origem, external_id, evento_agenda_id, "
                "ciclo(ano_letivo(canvas_course_id))")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"simulado {simulado_id} não encontrado")
    simulado = resp.data[0]

    if simulado.get("origem") != "sas":
        raise HTTPException(
            status_code=422,
            detail="Só simulados agendados pelo SAS podem ser desmarcados — "
                   "os do Canvas usam 'anulado'.",
        )

    tem_nota = (
        cliente.table("nota").select("aluno_id").eq("simulado_id", simulado_id)
        .limit(1).execute()
    )
    if tem_nota.data:
        raise HTTPException(
            status_code=409,
            detail="Simulado já tem notas — prova aplicada não se desmarca, se anula.",
        )

    # Canvas primeiro, quando pedido (DELETE é idempotente; 404 lá = já não
    # existe = ok). Falha aqui aborta ANTES de mexer no banco — senão o
    # Assignment ficaria órfão SEM o coordenador ter escolhido isso.
    course_id = (
        (simulado.get("ciclo") or {}).get("ano_letivo") or {}
    ).get("canvas_course_id")
    apagado_no_canvas = False
    if sincronizar_canvas and simulado.get("external_id"):
        if not course_id:
            raise HTTPException(
                status_code=502,
                detail="Ciclo sem canvas_course_id — não há como apagar o Assignment.",
            )
        try:
            await escrita.apagar_simulado(
                cliente, course_id=str(course_id), external_id=str(simulado["external_id"])
            )
        except escrita.CanvasIndisponivel as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Canvas recusou a exclusão: {exc}"
            ) from exc
        apagado_no_canvas = True

    cliente.table("metrica_simulado").delete().eq("simulado_id", simulado_id).execute()
    cliente.table("simulado").delete().eq("id", simulado_id).execute()
    if simulado.get("evento_agenda_id"):
        from datetime import datetime

        cliente.table("evento_agenda").update(
            {"cancelado_em": datetime.now(UTC).isoformat()}
        ).eq("id", simulado["evento_agenda_id"]).execute()
        # Evento morto não lembra ninguém: regras e disparos vivos caem junto
        # (e a guarda no envio cobre quem escapar; docs/12 §4.5).
        lembretes.cancelar_disparos_do_evento(cliente, simulado["evento_agenda_id"])

    auditar(
        cliente, "simulado_removido", canal="simulado",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"simulado/{simulado_id}",
        ip=request.client.host if request.client else None,
        detalhe={
            "sincronizar_canvas": sincronizar_canvas,
            "apagado_no_canvas": apagado_no_canvas,
            # Se ficou órfão no Canvas, este é o único rastro dele no SAS.
            "canvas_assignment_id": simulado.get("external_id"),
            "canvas_course_id": course_id,
        },
    )

    return {
        "status": "cancelado", "simuladoId": simulado_id,
        "apagadoNoCanvas": apagado_no_canvas,
    }
