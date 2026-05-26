"""Classificação dos alunos.

Para cada aluno ativo calcula:
  - media_recente / desvio_recente : sobre as últimas N notas
  - coef_tendencia / tendencia     : regressão linear das mesmas N notas
  - perfil                         : âncora / mistério / regular
  - zona                           : top / cinzenta / risco (vs. nota de corte)

Persiste em `classificacao_aluno (aluno_id PK)`.
"""

from __future__ import annotations

import logging
import statistics as st
from collections import defaultdict

from supabase import Client

from . import thresholds as th
from .utils import como_float, nota_real, percentil, regressao_linear, t_critico

log = logging.getLogger("sas.stats.classificacao")


def recalcular_tudo(cliente: Client) -> int:
    """Recalcula classificação de todos os alunos ativos.

    Notas trabalhadas aqui já estão em escala 0–10 (normalizadas em
    `_notas_recentes_por_aluno`). A zona usa regra do ITA/IME: basta UMA
    matéria recente em Fase 2 abaixo do corte (4,0) para o aluno ser
    considerado em risco.

    Retorna a quantidade de alunos efetivamente classificados (com >= 2 notas).
    """
    alunos_ativos = _carregar_alunos_ativos(cliente)
    log.info("classificando %d alunos ativos", len(alunos_ativos))

    notas_por_aluno = _notas_recentes_por_aluno(cliente, janela=th.JANELA_CLASSIFICACAO)
    turmas_por_aluno = _turma_ativa_por_aluno(cliente)
    metricas_turma = _metricas_por_turma(cliente, notas_por_aluno, turmas_por_aluno)
    notas_fase2_por_aluno_materia = _notas_fase2_por_aluno_materia(
        cliente, janela=th.JANELA_CLASSIFICACAO
    )
    codigo_materia_por_id = _mapa_codigo_materia(cliente)

    classificados = 0
    for aluno in alunos_ativos:
        aluno_id = aluno["id"]
        notas = notas_por_aluno.get(aluno_id, [])
        if len(notas) < 2:
            continue

        valores = [n["pontuacao"] for n in notas]
        media_recente = st.mean(valores)
        desvio_recente = st.stdev(valores) if len(valores) > 1 else 0.0

        slope, t_stat = regressao_linear(valores)
        tendencia = _classificar_tendencia(slope, t_stat, n=len(valores))

        turma_id = turmas_por_aluno.get(aluno_id)
        perfil = _classificar_perfil(
            media_recente=media_recente,
            desvio_recente=desvio_recente,
            metrica_turma=metricas_turma.get(turma_id),
        )

        zona = _classificar_zona_por_materia(
            notas_por_materia_codigo=_resumir_notas_por_materia(
                notas_fase2_por_aluno_materia.get(aluno_id, {}),
                codigo_materia_por_id,
            ),
            media_recente=media_recente,
        )

        cliente.table("classificacao_aluno").upsert(
            {
                "aluno_id": aluno_id,
                "perfil": perfil,
                "tendencia": tendencia,
                "zona": zona,
                "media_recente": round(media_recente, 2),
                "desvio_recente": round(desvio_recente, 2),
                "coef_tendencia": round(slope, 3),
                "p_valor_tendencia": None,
                "janela_simulados": th.JANELA_CLASSIFICACAO,
            },
            on_conflict="aluno_id",
        ).execute()
        classificados += 1

    return classificados


# ─── Classificadores ─────────────────────────────────────────────────────


def _classificar_tendencia(slope: float, t_stat: float, n: int) -> str:
    """Subindo / caindo / estável usando slope + significância (t-Student)."""
    if abs(slope) < th.SLOPE_MINIMO:
        return "estavel"
    if n < 3:
        return "estavel"
    critico = t_critico(n - 2)
    if slope > 0 and t_stat > critico:
        return "subindo"
    if slope < 0 and t_stat < -critico:
        return "caindo"
    return "estavel"


def _classificar_perfil(
    *,
    media_recente: float,
    desvio_recente: float,
    metrica_turma: dict | None,
) -> str:
    """Âncora / mistério / regular — comparando contra a turma do aluno."""
    if metrica_turma is None:
        return "regular"

    p85 = metrica_turma.get("percentil_85")
    desvio_turma = metrica_turma.get("desvio_padrao_turma") or 0.0
    mediana_desvios = metrica_turma.get("mediana_desvios") or 0.0

    if p85 is not None and media_recente >= p85 and desvio_recente < th.FATOR_DESVIO_ANCORA * (desvio_turma or 1):
        return "ancora"
    if mediana_desvios > 0 and desvio_recente > th.FATOR_DESVIO_MISTERIO * mediana_desvios:
        return "misterio"
    return "regular"


def _classificar_zona_por_materia(
    *,
    notas_por_materia_codigo: dict[str, float],   # {codigo: nota_media_recente em 0-10}
    media_recente: float,
) -> str:
    """Top / cinzenta / risco usando regra ITA/IME por matéria.

    Regra real: aluno reprovado se ALGUMA matéria core (Mat/Fís/Quím/Port)
    ficar abaixo de 4,0 nos simulados de Fase 2.

      - risco:    alguma matéria core < 4,0  (ou faltam dados pra decidir)
      - top:      todas as matérias core ≥ 4,0 + margem (5,0 por padrão)
      - cinzenta: todas ≥ 4,0 mas alguma entre 4 e 5
    """
    if not notas_por_materia_codigo:
        # Sem dados de Fase 2 → cai num default neutro baseado na média geral.
        if media_recente >= th.NOTA_CORTE_FASE_2 + th.MARGEM_TOP_SOBRE_CORTE:
            return "top"
        if media_recente >= th.NOTA_CORTE_FASE_2:
            return "cinzenta"
        return "risco"

    minimo_observado = None
    for codigo in th.MATERIAS_PARA_CORTE:
        nota = notas_por_materia_codigo.get(codigo)
        if nota is None:
            continue  # matéria sem dado nessa janela — não penaliza nem premia
        if minimo_observado is None or nota < minimo_observado:
            minimo_observado = nota

    if minimo_observado is None:
        # Nenhuma matéria core observada — fallback pra média.
        return "cinzenta" if media_recente >= th.NOTA_CORTE_FASE_2 else "risco"

    if minimo_observado < th.NOTA_CORTE_FASE_2:
        return "risco"
    if minimo_observado >= th.NOTA_CORTE_FASE_2 + th.MARGEM_TOP_SOBRE_CORTE:
        return "top"
    return "cinzenta"


def _resumir_notas_por_materia(
    notas_por_materia_id: dict[str, list[float]],
    codigo_por_materia_id: dict[str, str],
) -> dict[str, float]:
    """{materia_codigo: média das notas (0-10) recentes nessa matéria}."""
    out: dict[str, float] = {}
    for materia_id, lista in notas_por_materia_id.items():
        if not lista:
            continue
        codigo = codigo_por_materia_id.get(materia_id)
        if not codigo:
            continue
        out[codigo] = st.mean(lista)
    return out


# ─── Carregadores ────────────────────────────────────────────────────────


def _carregar_alunos_ativos(cliente: Client) -> list[dict]:
    resp = cliente.table("aluno").select("id, nome, ativo").eq("ativo", True).execute()
    return resp.data or []


def _notas_recentes_por_aluno(cliente: Client, *, janela: int) -> dict[str, list[dict]]:
    """{aluno_id: [{pontuacao, data_aplicacao, simulado_id, materia_id, tipo}]}.

    Notas em **escala 0–10 já normalizada** — `pontuacao` aqui é `nota_real`
    (acertos / total * 10), não os acertos brutos. Isso é o que permite
    somar/comparar valores entre simulados de matérias diferentes.

    Filtra simulados anulados e agregados. Mantém só as últimas `janela` notas
    por aluno.
    """
    resp = (
        cliente.table("nota")
        .select(
            "aluno_id, pontuacao, simulado("
            "id, data_aplicacao, anulado, e_agregado, materia_id, tipo, nota_maxima"
            ")"
        )
        .eq("presente", True)
        .execute()
    )

    bruto: dict[str, list[dict]] = defaultdict(list)
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        pontuacao_bruta = como_float(linha.get("pontuacao"))
        nota_maxima = como_float(sim.get("nota_maxima"))
        nota = nota_real(pontuacao_bruta, nota_maxima)
        if nota is None:
            continue
        bruto[linha["aluno_id"]].append(
            {
                "pontuacao": nota,                          # já em 0–10
                "data_aplicacao": sim.get("data_aplicacao") or "",
                "simulado_id": sim.get("id"),
                "materia_id": sim.get("materia_id"),
                "tipo": sim.get("tipo"),                    # fase_1 | fase_2 | None
            }
        )

    # Ordena por data e fatia.
    resultado: dict[str, list[dict]] = {}
    for aluno_id, notas in bruto.items():
        notas.sort(key=lambda n: n["data_aplicacao"])
        resultado[aluno_id] = notas[-janela:] if len(notas) > janela else notas
    return resultado


def _turma_ativa_por_aluno(cliente: Client) -> dict[str, str]:
    """{aluno_id: turma_id} a partir da matrícula com ativo_ate IS NULL."""
    resp = (
        cliente.table("matricula_turma")
        .select("aluno_id, turma_id, ativo_desde")
        .is_("ativo_ate", "null")
        .execute()
    )
    mapa: dict[str, tuple[str, str]] = {}
    for linha in resp.data or []:
        aluno_id = linha["aluno_id"]
        ativo_desde = linha.get("ativo_desde") or ""
        existente = mapa.get(aluno_id)
        if existente is None or ativo_desde > existente[1]:
            mapa[aluno_id] = (linha["turma_id"], ativo_desde)
    return {aluno_id: v[0] for aluno_id, v in mapa.items()}


def _metricas_por_turma(
    cliente: Client,
    notas_por_aluno: dict[str, list[dict]],
    turmas_por_aluno: dict[str, str],
) -> dict[str, dict]:
    """Pré-computa, para cada turma:
       - percentil_85 das médias recentes dos alunos da turma
       - desvio_padrao_turma  (desvio padrão das mesmas médias)
       - mediana_desvios      (mediana dos desvios individuais dos alunos)
    """
    medias_por_turma: dict[str, list[float]] = defaultdict(list)
    desvios_por_turma: dict[str, list[float]] = defaultdict(list)

    for aluno_id, notas in notas_por_aluno.items():
        if len(notas) < 2:
            continue
        turma_id = turmas_por_aluno.get(aluno_id)
        if not turma_id:
            continue
        valores = [n["pontuacao"] for n in notas]
        medias_por_turma[turma_id].append(st.mean(valores))
        desvios_por_turma[turma_id].append(st.stdev(valores))

    resultado: dict[str, dict] = {}
    for turma_id, medias in medias_por_turma.items():
        desvios = desvios_por_turma.get(turma_id, [])
        resultado[turma_id] = {
            "percentil_85": percentil(medias, 85),
            "desvio_padrao_turma": st.stdev(medias) if len(medias) > 1 else 0.0,
            "mediana_desvios": st.median(desvios) if desvios else 0.0,
            "media_turma": st.mean(medias),
            "n_alunos": len(medias),
        }
    return resultado


def _notas_fase2_por_aluno_materia(
    cliente: Client,
    *,
    janela: int,
) -> dict[str, dict[str, list[float]]]:
    """{aluno_id: {materia_id: [notas normalizadas recentes em 0-10]}}.

    Restringido a simulados de **Fase 2** (onde vale a regra do corte por
    matéria). Fase 1 fica de fora porque ela tem nota combinada — não dá pra
    falar "matemática da Fase 1 abaixo de 4" do mesmo jeito.
    """
    resp = (
        cliente.table("nota")
        .select(
            "aluno_id, pontuacao, simulado("
            "id, data_aplicacao, anulado, e_agregado, materia_id, tipo, nota_maxima"
            ")"
        )
        .eq("presente", True)
        .execute()
    )

    bruto: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(lambda: defaultdict(list))
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        if sim.get("tipo") != "fase_2":
            continue
        materia_id = sim.get("materia_id")
        if not materia_id:
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        bruto[linha["aluno_id"]][materia_id].append(
            (sim.get("data_aplicacao") or "", nota)
        )

    # Ordena por data e fatia pra janela.
    resultado: dict[str, dict[str, list[float]]] = {}
    for aluno_id, por_materia in bruto.items():
        resumo: dict[str, list[float]] = {}
        for materia_id, pares in por_materia.items():
            pares.sort(key=lambda x: x[0])
            recentes = pares[-janela:] if len(pares) > janela else pares
            resumo[materia_id] = [nota for _, nota in recentes]
        resultado[aluno_id] = resumo
    return resultado


def _mapa_codigo_materia(cliente: Client) -> dict[str, str]:
    """{materia_id: codigo} pra traduzir o id da matéria pro slug usado em thresholds."""
    resp = cliente.table("materia").select("id, codigo").execute()
    return {linha["id"]: linha["codigo"] for linha in (resp.data or [])}


def _menor_corte_por_aluno(cliente: Client) -> dict[str, float]:
    """{aluno_id: menor nota_corte entre vestibulares-alvo}.

    Usa o ano letivo mais recente para nota_corte. Se o aluno não tem alvos
    configurados, fica fora do mapa (a função de zona devolve 'cinzenta').
    """
    alvos = cliente.table("vestibular_alvo_aluno").select("aluno_id, vestibular").execute()
    if not (alvos.data or []):
        return {}

    # Mais recente: ano com maior valor de `ano`.
    anos = cliente.table("ano_letivo").select("id, ano").order("ano", desc=True).limit(1).execute()
    if not anos.data:
        return {}
    ano_letivo_id = anos.data[0]["id"]

    cortes_resp = (
        cliente.table("nota_corte_vestibular")
        .select("vestibular, nota_corte")
        .eq("ano_letivo_id", ano_letivo_id)
        .execute()
    )
    cortes = {linha["vestibular"]: como_float(linha["nota_corte"]) for linha in (cortes_resp.data or [])}
    if not cortes:
        return {}

    resultado: dict[str, float] = {}
    por_aluno: dict[str, list[float]] = defaultdict(list)
    for alvo in alvos.data:
        corte = cortes.get(alvo["vestibular"])
        if corte is not None:
            por_aluno[alvo["aluno_id"]].append(corte)
    for aluno_id, lista in por_aluno.items():
        if lista:
            resultado[aluno_id] = min(lista)
    return resultado


# ─── Consultas auxiliares ────────────────────────────────────────────────


def mapa_classificacao(cliente: Client) -> dict[str, dict]:
    """{aluno_id: linha de classificacao_aluno} usado pelas rotas."""
    resp = (
        cliente.table("classificacao_aluno")
        .select("aluno_id, perfil, tendencia, zona, media_recente, desvio_recente, coef_tendencia, janela_simulados")
        .execute()
    )
    return {linha["aluno_id"]: linha for linha in (resp.data or [])}


def sparkline_por_aluno(cliente: Client, *, janela: int = th.JANELA_CLASSIFICACAO) -> dict[str, list[float]]:
    """{aluno_id: [pontuacoes_cronologicas]} pra mini-gráfico das telas."""
    notas = _notas_recentes_por_aluno(cliente, janela=janela)
    return {aluno_id: [n["pontuacao"] for n in lista] for aluno_id, lista in notas.items()}
