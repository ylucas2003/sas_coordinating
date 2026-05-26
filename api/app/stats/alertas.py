"""Engine de alertas — 7 categorias.

Cada regra é uma função `regra_*` que retorna `list[dict]` com o payload de
um alerta pronto pra upsert na tabela `alerta`. A coluna `hash_dedup`
(UNIQUE) é a chave de idempotência: rodar o pipeline duas vezes sobre os
mesmos dados gera o mesmo hash → upsert silencioso, sem flood.

Categorias (declaradas no schema 0001):
  - QUEDA_RENDIMENTO       : aluno caindo
  - SUBIDA_ATIPICA         : aluno subindo
  - PROVA_MAL_CALIBRADA    : desvio do simulado muito acima do histórico
  - MATERIA_EM_RISCO       : matéria abaixo do histórico por N simulados
  - DIFERENCA_ENTRE_SEDES  : Welch t-test entre sedes
  - ZONA_TRANSICAO         : aluno mudou de zona vs. classificação anterior
  - PANORAMA_CICLO         : resumo informativo quando um ciclo é concluído
"""

from __future__ import annotations

import logging
import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from . import thresholds as th
from .utils import como_float, hash_dedup_alerta, nota_real, welch_t_test

log = logging.getLogger("sas.stats.alertas")


def avaliar_tudo(cliente: Client) -> int:
    """Roda as 7 regras e upserta os alertas. Retorna o total emitido."""
    limpar_caches()
    todos: list[dict] = []
    todos += regra_queda_rendimento(cliente)
    todos += regra_subida_atipica(cliente)
    todos += regra_prova_mal_calibrada(cliente)
    todos += regra_materia_em_risco(cliente)
    todos += regra_diferenca_entre_sedes(cliente)
    todos += regra_zona_transicao(cliente)
    todos += regra_panorama_ciclo(cliente)

    log.info("emitindo %d alertas (após dedup por hash)", len(todos))
    for alerta in todos:
        cliente.table("alerta").upsert(
            alerta,
            on_conflict="hash_dedup",
            ignore_duplicates=True,
        ).execute()
    return len(todos)


# ─── Regras ───────────────────────────────────────────────────────────────


def regra_queda_rendimento(cliente: Client) -> list[dict]:
    """Aluno: média(últimos 3) - média(3 anteriores) <= -DELTA. Vermelho."""
    alertas: list[dict] = []
    historico = _historico_notas_por_aluno(cliente)

    for aluno_id, notas in historico.items():
        if len(notas) < 2 * th.JANELA_QUEDA_SUBIDA:
            continue
        recentes = notas[-th.JANELA_QUEDA_SUBIDA:]
        anteriores = notas[-2 * th.JANELA_QUEDA_SUBIDA : -th.JANELA_QUEDA_SUBIDA]
        media_recente = st.mean([n["pontuacao"] for n in recentes])
        media_anterior = st.mean([n["pontuacao"] for n in anteriores])
        delta = media_recente - media_anterior

        if delta <= -th.DELTA_QUEDA_SUBIDA:
            nome = _nome_aluno(cliente, aluno_id)
            sparkline = [n["pontuacao"] for n in notas[-(2 * th.JANELA_QUEDA_SUBIDA) :]]
            janela_chave = "-".join(n.get("simulado_id", "") or "" for n in recentes)
            alertas.append(
                {
                    "categoria": "QUEDA_RENDIMENTO",
                    "severidade": "vermelho",
                    "entidade_tipo": "aluno",
                    "entidade_id": aluno_id,
                    "titulo": f"{nome} caiu {abs(delta):.1f} pontos em {th.JANELA_QUEDA_SUBIDA} simulados",
                    "subtitulo": f"média atual {media_recente:.1f} · anterior {media_anterior:.1f}",
                    "dados_brutos": {"sparkline": sparkline, "delta": round(delta, 2)},
                    "hash_dedup": hash_dedup_alerta(
                        categoria="QUEDA_RENDIMENTO",
                        entidade_tipo="aluno",
                        entidade_id=aluno_id,
                        janela_chave=janela_chave,
                    ),
                }
            )
    return alertas


def regra_subida_atipica(cliente: Client) -> list[dict]:
    """Espelho da queda. Verde."""
    alertas: list[dict] = []
    historico = _historico_notas_por_aluno(cliente)

    for aluno_id, notas in historico.items():
        if len(notas) < 2 * th.JANELA_QUEDA_SUBIDA:
            continue
        recentes = notas[-th.JANELA_QUEDA_SUBIDA:]
        anteriores = notas[-2 * th.JANELA_QUEDA_SUBIDA : -th.JANELA_QUEDA_SUBIDA]
        media_recente = st.mean([n["pontuacao"] for n in recentes])
        media_anterior = st.mean([n["pontuacao"] for n in anteriores])
        delta = media_recente - media_anterior

        if delta >= th.DELTA_QUEDA_SUBIDA:
            nome = _nome_aluno(cliente, aluno_id)
            sparkline = [n["pontuacao"] for n in notas[-(2 * th.JANELA_QUEDA_SUBIDA) :]]
            janela_chave = "-".join(n.get("simulado_id", "") or "" for n in recentes)
            alertas.append(
                {
                    "categoria": "SUBIDA_ATIPICA",
                    "severidade": "verde",
                    "entidade_tipo": "aluno",
                    "entidade_id": aluno_id,
                    "titulo": f"{nome} subiu {delta:.1f} pontos em {th.JANELA_QUEDA_SUBIDA} simulados",
                    "subtitulo": f"média atual {media_recente:.1f} · anterior {media_anterior:.1f}",
                    "dados_brutos": {"sparkline": sparkline, "delta": round(delta, 2)},
                    "hash_dedup": hash_dedup_alerta(
                        categoria="SUBIDA_ATIPICA",
                        entidade_tipo="aluno",
                        entidade_id=aluno_id,
                        janela_chave=janela_chave,
                    ),
                }
            )
    return alertas


def regra_prova_mal_calibrada(cliente: Client) -> list[dict]:
    """Desvio do simulado ≥ MULTIPLO × desvio histórico do mesmo ciclo/fase. Âmbar."""
    alertas: list[dict] = []
    metricas = (
        cliente.table("metrica_simulado")
        .select("simulado_id, desvio_padrao, media, n_presentes")
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .execute()
    )
    if not metricas.data:
        return alertas

    simulados_resp = (
        cliente.table("simulado")
        .select("id, nome, ciclo_id, tipo, anulado")
        .eq("anulado", False)
        .execute()
    )
    simulado_por_id = {s["id"]: s for s in (simulados_resp.data or [])}

    # Desvio histórico = mediana dos desvios de simulados do mesmo ciclo+fase.
    desvios_por_grupo: dict[tuple, list[float]] = defaultdict(list)
    for m in metricas.data:
        sim = simulado_por_id.get(m["simulado_id"])
        if not sim:
            continue
        d = como_float(m.get("desvio_padrao"))
        if d is None:
            continue
        chave = (sim["ciclo_id"], sim.get("tipo"))
        desvios_por_grupo[chave].append(d)

    historicos = {chave: st.median(lista) for chave, lista in desvios_por_grupo.items() if lista}

    for m in metricas.data:
        sim = simulado_por_id.get(m["simulado_id"])
        if not sim:
            continue
        d = como_float(m.get("desvio_padrao"))
        if d is None:
            continue
        chave = (sim["ciclo_id"], sim.get("tipo"))
        historico = historicos.get(chave)
        if historico is None or historico == 0:
            continue
        if d >= th.MULTIPLO_VARIANCIA * historico:
            alertas.append(
                {
                    "categoria": "PROVA_MAL_CALIBRADA",
                    "severidade": "ambar",
                    "entidade_tipo": "simulado",
                    "entidade_id": sim["id"],
                    "titulo": f"Desvio atípico em {sim['nome']}",
                    "subtitulo": f"σ = {d:.1f} · histórico do grupo = {historico:.1f}",
                    "dados_brutos": {
                        "desvio_atual": round(d, 2),
                        "desvio_historico": round(historico, 2),
                        "media": como_float(m.get("media")),
                        "n_presentes": m.get("n_presentes"),
                    },
                    "hash_dedup": hash_dedup_alerta(
                        categoria="PROVA_MAL_CALIBRADA",
                        entidade_tipo="simulado",
                        entidade_id=sim["id"],
                        janela_chave="",
                    ),
                }
            )
    return alertas


def regra_materia_em_risco(cliente: Client) -> list[dict]:
    """Média da matéria em N simulados consecutivos < histórico - 1σ. Âmbar."""
    alertas: list[dict] = []

    # Estrutura: para cada matéria, lista cronológica de (simulado_id, media_geral).
    medias_resp = (
        cliente.table("metrica_simulado")
        .select("simulado_id, media")
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .execute()
    )
    media_por_simulado = {linha["simulado_id"]: como_float(linha["media"]) for linha in (medias_resp.data or [])}

    sims_resp = (
        cliente.table("simulado")
        .select("id, nome, materia_id, data_aplicacao, anulado, e_agregado")
        .eq("anulado", False)
        .eq("e_agregado", False)
        .order("data_aplicacao")
        .execute()
    )

    por_materia: dict[str, list[dict]] = defaultdict(list)
    for s in sims_resp.data or []:
        if not s.get("materia_id"):
            continue
        media = media_por_simulado.get(s["id"])
        if media is None:
            continue
        por_materia[s["materia_id"]].append({"id": s["id"], "nome": s["nome"], "media": media})

    materias_resp = cliente.table("materia").select("id, nome").execute()
    nome_materia = {m["id"]: m["nome"] for m in (materias_resp.data or [])}

    n = th.N_SIMULADOS_MATERIA_RISCO
    for materia_id, lista in por_materia.items():
        if len(lista) < n + 1:
            continue
        # Histórico = média + desvio das `len - n` provas mais antigas (pra
        # comparar com as `n` mais recentes).
        recentes = lista[-n:]
        historicas = [x["media"] for x in lista[:-n]]
        if len(historicas) < 2:
            continue
        media_hist = st.mean(historicas)
        desvio_hist = st.stdev(historicas)
        if desvio_hist == 0:
            continue

        limite = media_hist - th.DELTA_DESVIO_MATERIA * desvio_hist
        if all(s["media"] < limite for s in recentes):
            nome = nome_materia.get(materia_id, materia_id)
            chave = "-".join(s["id"] for s in recentes)
            alertas.append(
                {
                    "categoria": "MATERIA_EM_RISCO",
                    "severidade": "ambar",
                    "entidade_tipo": "simulado",  # ancora no último simulado da janela
                    "entidade_id": recentes[-1]["id"],
                    "titulo": f"{nome} caiu nos {n} últimos simulados",
                    "subtitulo": f"médias recentes < {limite:.1f} (histórico {media_hist:.1f} ± {desvio_hist:.1f})",
                    "dados_brutos": {
                        "materia_id": materia_id,
                        "sparkline": [s["media"] for s in lista[-min(len(lista), 8) :]],
                        "media_historica": round(media_hist, 2),
                        "desvio_historico": round(desvio_hist, 2),
                    },
                    "hash_dedup": hash_dedup_alerta(
                        categoria="MATERIA_EM_RISCO",
                        entidade_tipo="simulado",
                        entidade_id=recentes[-1]["id"],
                        janela_chave=chave,
                    ),
                }
            )
    return alertas


def regra_diferenca_entre_sedes(cliente: Client) -> list[dict]:
    """Welch t-test entre sedes no mesmo simulado. Vermelho se p < α e Δ ≥ mínimo."""
    alertas: list[dict] = []

    # Para cada simulado, coleta lista de notas por sede via v_nota_dimensoes.
    # Normalizamos as notas (acertos / nota_maxima * 10) antes do teste-t —
    # senão, simulados com nota_maxima maior dominam o sinal.
    sims_resp = (
        cliente.table("simulado")
        .select("id, nome, anulado, e_agregado, nota_maxima")
        .eq("anulado", False)
        .eq("e_agregado", False)
        .execute()
    )

    sedes_resp = cliente.table("sede").select("id, nome").execute()
    nome_sede = {s["id"]: s["nome"] for s in (sedes_resp.data or [])}

    for sim in sims_resp.data or []:
        nota_maxima_sim = como_float(sim.get("nota_maxima"))
        resp = (
            cliente.table("v_nota_dimensoes")
            .select("pontuacao, sede_id")
            .eq("simulado_id", sim["id"])
            .eq("presente", True)
            .execute()
        )
        por_sede: dict[str, list[float]] = defaultdict(list)
        for linha in resp.data or []:
            sede_id = linha.get("sede_id")
            nota = nota_real(como_float(linha.get("pontuacao")), nota_maxima_sim)
            if sede_id and nota is not None:
                por_sede[sede_id].append(nota)

        if len(por_sede) < 2:
            continue

        # Comparações pareadas — só registramos a maior diferença significativa.
        chaves = list(por_sede.keys())
        for i in range(len(chaves)):
            for j in range(i + 1, len(chaves)):
                a, b = chaves[i], chaves[j]
                amostra_a, amostra_b = por_sede[a], por_sede[b]
                if len(amostra_a) < 3 or len(amostra_b) < 3:
                    continue
                t_stat, p_valor = welch_t_test(amostra_a, amostra_b)
                media_a, media_b = st.mean(amostra_a), st.mean(amostra_b)
                delta = abs(media_a - media_b)
                if p_valor < th.P_VALOR_MAX_SEDES and delta >= th.DELTA_MIN_SEDES:
                    sede_baixa, sede_alta = (a, b) if media_a < media_b else (b, a)
                    media_baixa = min(media_a, media_b)
                    media_alta = max(media_a, media_b)
                    alertas.append(
                        {
                            "categoria": "DIFERENCA_ENTRE_SEDES",
                            "severidade": "vermelho",
                            "entidade_tipo": "simulado",
                            "entidade_id": sim["id"],
                            "titulo": f"Diferença entre sedes em {sim['nome']}",
                            "subtitulo": (
                                f"{nome_sede.get(sede_alta, '?')} {media_alta:.1f} × "
                                f"{nome_sede.get(sede_baixa, '?')} {media_baixa:.1f} "
                                f"(p={p_valor:.3f})"
                            ),
                            "dados_brutos": {
                                "sede_alta_id": sede_alta,
                                "sede_baixa_id": sede_baixa,
                                "media_alta": round(media_alta, 2),
                                "media_baixa": round(media_baixa, 2),
                                "p_valor": round(p_valor, 4),
                                "t_stat": round(t_stat, 3),
                            },
                            "hash_dedup": hash_dedup_alerta(
                                categoria="DIFERENCA_ENTRE_SEDES",
                                entidade_tipo="simulado",
                                entidade_id=sim["id"],
                                janela_chave=f"{sede_alta}|{sede_baixa}",
                            ),
                        }
                    )
    return alertas


def regra_zona_transicao(cliente: Client) -> list[dict]:
    """Aluno mudou de zona vs. snapshot anterior.

    Sem histórico explícito de classificações (não há tabela própria), por
    enquanto essa regra fica em no-op — só vai disparar quando salvarmos
    `classificacao_aluno` num histórico (fora do MVP).
    """
    return []


def regra_panorama_ciclo(cliente: Client) -> list[dict]:
    """Quando todos os simulados de um ciclo já têm métrica geral, emite resumo.

    Severidade cinza (informativo). Hash inclui o ciclo_id — não duplica.
    """
    alertas: list[dict] = []
    sims_resp = (
        cliente.table("simulado")
        .select("id, ciclo_id, anulado, e_agregado")
        .eq("anulado", False)
        .eq("e_agregado", False)
        .execute()
    )
    sims_por_ciclo: dict[str, list[str]] = defaultdict(list)
    for s in sims_resp.data or []:
        sims_por_ciclo[s["ciclo_id"]].append(s["id"])

    metricas_resp = (
        cliente.table("metrica_simulado")
        .select("simulado_id, media")
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .execute()
    )
    media_por_simulado = {linha["simulado_id"]: como_float(linha["media"]) for linha in (metricas_resp.data or [])}

    ciclos_resp = cliente.table("ciclo").select("id, nome").execute()
    nome_ciclo = {c["id"]: c["nome"] for c in (ciclos_resp.data or [])}

    for ciclo_id, ids in sims_por_ciclo.items():
        if not ids:
            continue
        medias = [media_por_simulado.get(sid) for sid in ids]
        if any(m is None for m in medias):
            continue  # ainda incompleto
        media_ciclo = st.mean([m for m in medias if m is not None])
        alertas.append(
            {
                "categoria": "PANORAMA_CICLO",
                "severidade": "cinza",
                "entidade_tipo": "simulado",  # usa o último simulado como âncora
                "entidade_id": ids[-1],
                "titulo": f"Panorama de {nome_ciclo.get(ciclo_id, 'ciclo')}",
                "subtitulo": f"{len(ids)} simulados · média geral {media_ciclo:.1f}",
                "dados_brutos": {
                    "ciclo_id": ciclo_id,
                    "n_simulados": len(ids),
                    "media_ciclo": round(media_ciclo, 2),
                    "medias_por_simulado": [round(m, 2) for m in medias if m is not None],
                },
                "hash_dedup": hash_dedup_alerta(
                    categoria="PANORAMA_CICLO",
                    entidade_tipo="simulado",
                    entidade_id=ciclo_id,  # ancora pelo ciclo: 1 alerta por ciclo
                    janela_chave="-".join(ids),
                ),
            }
        )
    return alertas


# ─── Carregadores compartilhados ─────────────────────────────────────────


# Cache *por execução* de avaliar_tudo. Limpado no início de cada upload,
# então não vaza entre invocações da rota /uploads.
_cache_historico: dict[str, list[dict]] = {}
_cache_nomes: dict[str, str] = {}
_historico_carregado = False


def _historico_notas_por_aluno(cliente: Client) -> dict[str, list[dict]]:
    """{aluno_id: [{pontuacao, simulado_id, data_aplicacao}]} cronológico ascendente.

    Notas em escala 0–10 normalizada (`acertos / total * 10`). Crítico: as
    regras de queda/subida comparam médias entre janelas de simulados — se
    misturarmos escalas, todo aluno que migrar de uma matéria com 15 questões
    pra uma com 10 dispara alerta falso.
    """
    global _historico_carregado
    if _historico_carregado:
        return _cache_historico

    resp = (
        cliente.table("nota")
        .select(
            "aluno_id, pontuacao, simulado("
            "id, data_aplicacao, anulado, e_agregado, nota_maxima"
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
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None:
            continue
        bruto[linha["aluno_id"]].append(
            {
                "pontuacao": nota,
                "simulado_id": sim.get("id"),
                "data_aplicacao": sim.get("data_aplicacao") or "",
            }
        )

    for notas in bruto.values():
        notas.sort(key=lambda n: n["data_aplicacao"])

    _cache_historico.update(bruto)
    _historico_carregado = True
    return _cache_historico


def _nome_aluno(cliente: Client, aluno_id: str) -> str:
    if aluno_id in _cache_nomes:
        return _cache_nomes[aluno_id]
    resp = cliente.table("aluno").select("nome").eq("id", aluno_id).limit(1).execute()
    nome = (resp.data[0]["nome"] if resp.data else aluno_id)
    _cache_nomes[aluno_id] = nome
    return nome


def limpar_caches() -> None:
    """Chamar no início de `avaliar_tudo` pra garantir snapshot fresco."""
    global _historico_carregado
    _cache_historico.clear()
    _cache_nomes.clear()
    _historico_carregado = False
