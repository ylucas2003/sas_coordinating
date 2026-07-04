"""Tools de relatório — agregados compostos para respostas ricas em uma chamada.

Diferença das outras tools: estas fazem múltiplas queries e devolvem um payload
completo, poupando o LLM de ter que encadear 4–6 chamadas separadas.

Quando usar:
  - `relatorio_aluno`  → "gera um relatório do aluno X", "me dá um panorama do fulano"
  - `historico_aluno`  → "histórico completo do aluno X", "como foi o fulano em cada ciclo"
  - `relatorio_ciclo`  → "relatório do ciclo Y", "resumo geral do último ciclo"

Todas são READ-ONLY e seguem o padrão: retornam dict JSON-serializável ou
{"erro": "..."} em caso de falha.
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict
from typing import Any

from supabase import Client

from ...stats.utils import como_float, nota_real


# ─── relatorio_aluno ──────────────────────────────────────────────────────

def relatorio_aluno(cliente: Client, *, aluno_id: str) -> dict:
    """Relatório completo do aluno: perfil, notas por matéria, ausências, tendência."""

    # 1. Dados básicos
    aluno_resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, ativo")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not aluno_resp.data:
        return {"erro": f"aluno {aluno_id} não encontrado"}
    aluno = aluno_resp.data[0]

    # 2. Classificação
    classif_resp = (
        cliente.table("classificacao_aluno")
        .select("perfil, tendencia, zona, media_recente, desvio_recente, coef_tendencia, janela_simulados")
        .eq("aluno_id", aluno_id)
        .limit(1)
        .execute()
    )
    classif = (classif_resp.data or [{}])[0]

    # 3. Turma atual
    turma_resp = (
        cliente.table("matricula_turma")
        .select("turma(serie, trilha, section_original, sede(nome))")
        .eq("aluno_id", aluno_id)
        .is_("ativo_ate", "null")
        .order("ativo_desde", desc=True)
        .limit(1)
        .execute()
    )
    turma_raw = (turma_resp.data or [{}])[0].get("turma") or {}
    turma = {
        "serie": turma_raw.get("serie"),
        "trilha": turma_raw.get("trilha"),
        "sede": (turma_raw.get("sede") or {}).get("nome"),
        "sectionOriginal": turma_raw.get("section_original"),
    } if turma_raw else None

    # 4. Notas — todas as do aluno (presentes + ausentes)
    notas_resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, anulado, e_agregado, "
            "nota_maxima, tipo, ciclo_id, materia_id)"
        )
        .eq("aluno_id", aluno_id)
        .execute()
    )

    materias_resp = cliente.table("materia").select("id, codigo, nome").execute()
    mat_info = {m["id"]: m for m in (materias_resp.data or [])}

    # Monta lista completa e identifica o ciclo mais recente
    ciclo_ids_vistos: set[str] = set()
    notas_completas: list[dict] = []
    ausencias_total = 0

    for linha in notas_resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        presente = bool(linha.get("presente"))
        if not presente:
            ausencias_total += 1
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        mid = sim.get("materia_id")
        cid = sim.get("ciclo_id")
        if cid:
            ciclo_ids_vistos.add(cid)
        notas_completas.append({
            "simuladoId": sim.get("id"),
            "simulado": sim.get("nome"),
            "rotuloCurto": sim.get("rotulo_curto"),
            "data": sim.get("data_aplicacao"),
            "tipo": sim.get("tipo"),
            "cicloId": cid,
            "materiaId": mid,
            "materia": (mat_info.get(mid) or {}).get("nome") if mid else None,
            "nota": round(nota, 2) if nota is not None else None,
            "presente": presente,
        })

    notas_completas.sort(key=lambda r: r["data"] or "")

    # 5. Ciclo mais recente
    ciclo_mais_recente_id: str | None = None
    if ciclo_ids_vistos:
        ciclos_resp = (
            cliente.table("ciclo")
            .select("id, nome, ordem, vestibular_alvo, ano_letivo(ano)")
            .in_("id", list(ciclo_ids_vistos))
            .execute()
        )
        ciclos_ord = sorted(
            ciclos_resp.data or [],
            key=lambda c: ((c.get("ano_letivo") or {}).get("ano") or 0, c.get("ordem") or 0),
            reverse=True,
        )
        if ciclos_ord:
            ciclo_mais_recente_id = ciclos_ord[0]["id"]

    # 6. Notas do ciclo mais recente por matéria
    notas_ultimo_ciclo: dict[str, list[float]] = defaultdict(list)
    ausencias_ultimo_ciclo = 0
    for n in notas_completas:
        if n["cicloId"] != ciclo_mais_recente_id:
            continue
        if not n["presente"]:
            ausencias_ultimo_ciclo += 1
            continue
        if n["nota"] is not None and n["materia"]:
            notas_ultimo_ciclo[n["materia"]].append(n["nota"])

    resumo_por_materia = []
    for materia, vals in notas_ultimo_ciclo.items():
        media = round(sum(vals) / len(vals), 2)
        resumo_por_materia.append({
            "materia": materia,
            "media": media,
            "nProvas": len(vals),
            "abaixoCorte": media < 4.0,
        })
    resumo_por_materia.sort(key=lambda r: r["media"])

    # 7. Últimas 10 notas (para o LLM narrar evolução recente)
    notas_presentes = [n for n in notas_completas if n["presente"] and n["nota"] is not None]
    ultimas_notas = notas_presentes[-10:]

    return {
        "aluno": {
            "id": aluno["id"],
            "nome": aluno["nome"],
            "matricula": aluno.get("matricula"),
            "ativo": aluno.get("ativo"),
            "turma": turma,
        },
        "classificacao": {
            "zona": classif.get("zona"),
            "perfil": classif.get("perfil"),
            "tendencia": classif.get("tendencia"),
            "mediaRecente": como_float(classif.get("media_recente")),
            "desvioRecente": como_float(classif.get("desvio_recente")),
            "coefTendencia": como_float(classif.get("coef_tendencia")),
            "janelaSimulados": classif.get("janela_simulados"),
        },
        "ausenciasTotal": ausencias_total,
        "ausenciasUltimoCiclo": ausencias_ultimo_ciclo,
        "resumoUltimoCiclo": resumo_por_materia,
        "ultimasNotas": ultimas_notas,
    }


_SCHEMA_RELATORIO_ALUNO = {
    "name": "relatorio_aluno",
    "description": (
        "Relatório completo do aluno em uma chamada: dados básicos, classificação (zona/perfil/tendência), "
        "resumo de notas por matéria no último ciclo, total de ausências e últimas 10 notas. "
        "Use quando pedirem 'relatório do aluno', 'panorama do fulano', ou antes de uma reunião."
    ),
    "parameters": {
        "type": "object",
        "properties": {"aluno_id": {"type": "string", "description": "UUID do aluno."}},
        "required": ["aluno_id"],
    },
}


# ─── historico_aluno ──────────────────────────────────────────────────────

def historico_aluno(
    cliente: Client,
    *,
    aluno_id: str,
    ciclo_id: str | None = None,
) -> dict:
    """Histórico completo do aluno, organizado por ciclo."""

    aluno_resp = (
        cliente.table("aluno")
        .select("id, nome, matricula")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not aluno_resp.data:
        return {"erro": f"aluno {aluno_id} não encontrado"}
    aluno = aluno_resp.data[0]

    notas_resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, anulado, e_agregado, "
            "nota_maxima, tipo, ciclo_id, materia_id)"
        )
        .eq("aluno_id", aluno_id)
        .execute()
    )

    materias_resp = cliente.table("materia").select("id, nome").execute()
    mat_nome = {m["id"]: m["nome"] for m in (materias_resp.data or [])}

    ciclo_ids_usados: set[str] = set()
    por_ciclo: dict[str, list[dict]] = defaultdict(list)

    for linha in notas_resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        cid = sim.get("ciclo_id")
        if not cid:
            continue
        if ciclo_id and cid != ciclo_id:
            continue
        ciclo_ids_usados.add(cid)
        presente = bool(linha.get("presente"))
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        mid = sim.get("materia_id")
        por_ciclo[cid].append({
            "simuladoId": sim.get("id"),
            "simulado": sim.get("nome"),
            "rotuloCurto": sim.get("rotulo_curto"),
            "data": sim.get("data_aplicacao"),
            "tipo": sim.get("tipo"),
            "materia": mat_nome.get(mid) if mid else None,
            "nota": round(nota, 2) if nota is not None else None,
            "presente": presente,
        })

    if not ciclo_ids_usados:
        return {"aluno": aluno, "ciclos": []}

    ciclos_resp = (
        cliente.table("ciclo")
        .select("id, nome, ordem, vestibular_alvo, ano_letivo(ano)")
        .in_("id", list(ciclo_ids_usados))
        .execute()
    )
    ciclos_info = {
        c["id"]: {
            "id": c["id"],
            "nome": c["nome"],
            "vestibularAlvo": c.get("vestibular_alvo"),
            "ordem": c.get("ordem"),
            "ano": (c.get("ano_letivo") or {}).get("ano"),
        }
        for c in (ciclos_resp.data or [])
    }

    ciclos_saida = []
    for cid, notas in por_ciclo.items():
        notas.sort(key=lambda n: n["data"] or "")
        presentes = [n for n in notas if n["presente"] and n["nota"] is not None]
        ausentes = [n for n in notas if not n["presente"]]
        media_geral = round(sum(n["nota"] for n in presentes) / len(presentes), 2) if presentes else None

        por_materia: dict[str, list[float]] = defaultdict(list)
        for n in presentes:
            if n["materia"]:
                por_materia[n["materia"]].append(n["nota"])

        resumo_mat = [
            {
                "materia": m,
                "media": round(sum(vs) / len(vs), 2),
                "nProvas": len(vs),
                "abaixoCorte": (sum(vs) / len(vs)) < 4.0,
            }
            for m, vs in por_materia.items()
        ]
        resumo_mat.sort(key=lambda r: r["media"])

        ciclos_saida.append({
            "ciclo": ciclos_info.get(cid, {"id": cid}),
            "mediaGeral": media_geral,
            "nPresencas": len(presentes),
            "nAusencias": len(ausentes),
            "resumoPorMateria": resumo_mat,
            "notas": notas,
        })

    ciclos_saida.sort(
        key=lambda c: (
            (c["ciclo"].get("ano") or 0),
            (c["ciclo"].get("ordem") or 0),
        )
    )

    return {"aluno": aluno, "totalCiclos": len(ciclos_saida), "ciclos": ciclos_saida}


_SCHEMA_HISTORICO_ALUNO = {
    "name": "historico_aluno",
    "description": (
        "Histórico completo do aluno organizado por ciclo: todas as notas, presença/ausência, "
        "média por matéria em cada ciclo. Use para 'como foi o aluno em cada ciclo', "
        "'histórico completo', ou para comparar evolução entre ciclos."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "aluno_id": {"type": "string", "description": "UUID do aluno."},
            "ciclo_id": {
                "type": "string",
                "description": "UUID do ciclo para filtrar (omitir = todos os ciclos).",
            },
        },
        "required": ["aluno_id"],
    },
}


# ─── relatorio_ciclo ──────────────────────────────────────────────────────

def relatorio_ciclo(cliente: Client, *, ciclo_id: str) -> dict:
    """Relatório completo do ciclo: stats, alunos em risco/destaque, matérias problemáticas, simulados mais difíceis."""

    # 1. Info do ciclo
    ciclo_resp = (
        cliente.table("ciclo")
        .select("id, nome, vestibular_alvo, periodo_inicio, periodo_fim, ano_letivo(ano)")
        .eq("id", ciclo_id)
        .limit(1)
        .execute()
    )
    if not ciclo_resp.data:
        return {"erro": f"ciclo {ciclo_id} não encontrado"}
    ciclo_raw = ciclo_resp.data[0]
    ciclo = {
        "id": ciclo_raw["id"],
        "nome": ciclo_raw["nome"],
        "vestibularAlvo": ciclo_raw.get("vestibular_alvo"),
        "ano": (ciclo_raw.get("ano_letivo") or {}).get("ano"),
        "periodoInicio": ciclo_raw.get("periodo_inicio"),
        "periodoFim": ciclo_raw.get("periodo_fim"),
    }

    # 2. Simulados do ciclo (não anulados, não agregados)
    sim_resp = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, tipo, data_aplicacao, materia_id, nota_maxima")
        .eq("ciclo_id", ciclo_id)
        .eq("anulado", False)
        .execute()
    )
    sims = [s for s in (sim_resp.data or []) if not s.get("e_agregado")]
    sim_ids = [s["id"] for s in sims]

    if not sim_ids:
        return {"ciclo": ciclo, "aviso": "nenhum simulado encontrado para este ciclo"}

    # 3. Matérias
    mat_ids = list({s["materia_id"] for s in sims if s.get("materia_id")})
    mat_info: dict[str, dict] = {}
    if mat_ids:
        mat_resp = cliente.table("materia").select("id, codigo, nome").in_("id", mat_ids).execute()
        mat_info = {m["id"]: m for m in (mat_resp.data or [])}

    # 4. Métricas dos simulados (para ranking de dificuldade)
    met_resp = (
        cliente.table("metrica_simulado")
        .select("simulado_id, media, mediana, n_presentes, n_ausentes")
        .in_("simulado_id", sim_ids)
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .execute()
    )
    metricas = {m["simulado_id"]: m for m in (met_resp.data or [])}

    simulados_com_dificuldade = []
    for s in sims:
        m = metricas.get(s["id"]) or {}
        media = como_float(m.get("media"))
        mid = s.get("materia_id")
        simulados_com_dificuldade.append({
            "simuladoId": s["id"],
            "nome": s.get("nome"),
            "rotuloCurto": s.get("rotulo_curto"),
            "tipo": s.get("tipo"),
            "materia": (mat_info.get(mid) or {}).get("nome") if mid else None,
            "media": round(media, 2) if media is not None else None,
            "nPresentes": m.get("n_presentes"),
            "nAusentes": m.get("n_ausentes"),
        })
    simulados_com_dificuldade.sort(key=lambda x: (x["media"] is None, x["media"] or 0))

    # 5. Notas do ciclo para stats gerais e matérias problemáticas
    notas_resp = (
        cliente.table("nota")
        .select("aluno_id, simulado_id, pontuacao, presente")
        .in_("simulado_id", sim_ids)
        .eq("presente", True)
        .execute()
    )

    nota_max_por_sim = {s["id"]: como_float(s.get("nota_maxima")) or 10.0 for s in sims}
    sim_para_mat = {s["id"]: s.get("materia_id") for s in sims}

    todas_notas: list[float] = []
    por_mat_aluno: dict[tuple[str, str], list[float]] = defaultdict(list)

    for linha in notas_resp.data or []:
        sid = linha["simulado_id"]
        nota = nota_real(como_float(linha.get("pontuacao")), nota_max_por_sim.get(sid, 10.0))
        if nota is None:
            continue
        todas_notas.append(nota)
        mid = sim_para_mat.get(sid)
        if mid:
            por_mat_aluno[(mid, linha["aluno_id"])].append(nota)

    stats_gerais: dict[str, Any] = {}
    if todas_notas:
        stats_gerais = {
            "nNotas": len(todas_notas),
            "media": round(sum(todas_notas) / len(todas_notas), 2),
            "mediana": round(st.median(todas_notas), 2),
            "desvioPadrao": round(st.pstdev(todas_notas), 2),
            "pctAbaixoCorte": round(100 * sum(1 for n in todas_notas if n < 4.0) / len(todas_notas), 1),
        }

    # Matérias problemáticas
    resumo_mat: list[dict] = []
    mat_agrupado: dict[str, list[float]] = defaultdict(list)
    for (mid, _), vals in por_mat_aluno.items():
        mat_agrupado[mid].append(sum(vals) / len(vals))

    for mid, medias_alunos in mat_agrupado.items():
        abaixo = sum(1 for v in medias_alunos if v < 4.0)
        m_info = mat_info.get(mid, {})
        resumo_mat.append({
            "materia": m_info.get("nome"),
            "nAlunos": len(medias_alunos),
            "media": round(sum(medias_alunos) / len(medias_alunos), 2),
            "pctAbaixoCorte": round(100 * abaixo / len(medias_alunos), 1),
            "abaixoCorte": abaixo,
        })
    resumo_mat.sort(key=lambda r: -r["pctAbaixoCorte"])

    # 6. Alunos em risco e destaque (do classificacao_aluno — estado atual)
    risco_resp = (
        cliente.table("classificacao_aluno")
        .select("aluno_id, zona, tendencia, perfil, media_recente")
        .in_("zona", ["risco", "cinzenta"])
        .execute()
    )
    destaque_resp = (
        cliente.table("classificacao_aluno")
        .select("aluno_id, zona, tendencia, perfil, media_recente")
        .eq("zona", "top")
        .execute()
    )

    def _enriquecer_com_nomes(rows: list[dict]) -> list[dict]:
        ids = [r["aluno_id"] for r in rows]
        if not ids:
            return []
        nomes_r = cliente.table("aluno").select("id, nome, ativo").in_("id", ids).execute()
        nomes = {a["id"]: a for a in (nomes_r.data or [])}
        saida = []
        for r in rows:
            a = nomes.get(r["aluno_id"]) or {}
            if not a.get("ativo", True):
                continue
            saida.append({
                "nome": a.get("nome"),
                "zona": r.get("zona"),
                "tendencia": r.get("tendencia"),
                "perfil": r.get("perfil"),
                "mediaRecente": como_float(r.get("media_recente")),
            })
        return saida

    alunos_risco = sorted(
        _enriquecer_com_nomes(risco_resp.data or []),
        key=lambda x: (x["mediaRecente"] is None, x["mediaRecente"] or 0),
    )
    alunos_destaque = sorted(
        _enriquecer_com_nomes(destaque_resp.data or []),
        key=lambda x: (x["mediaRecente"] is None, x["mediaRecente"] or 0),
        reverse=True,
    )

    return {
        "ciclo": ciclo,
        "nSimulados": len(sims),
        "statsGerais": stats_gerais,
        "porMateria": resumo_mat,
        "simuladosMaisDificeis": simulados_com_dificuldade[:5],
        "alunosRisco": alunos_risco[:20],
        "alunosDestaque": alunos_destaque[:10],
    }


_SCHEMA_RELATORIO_CICLO = {
    "name": "relatorio_ciclo",
    "description": (
        "Relatório completo de um ciclo em uma chamada: estatísticas gerais, "
        "matérias problemáticas (% abaixo do corte), os 5 simulados mais difíceis, "
        "lista de alunos em risco e alunos destaque. "
        "Use para 'relatório do ciclo X', 'resumo do último ciclo', ou antes de reunião de coordenação."
    ),
    "parameters": {
        "type": "object",
        "properties": {"ciclo_id": {"type": "string", "description": "UUID do ciclo."}},
        "required": ["ciclo_id"],
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_RELATORIO_ALUNO, relatorio_aluno),
    (_SCHEMA_HISTORICO_ALUNO, historico_aluno),
    (_SCHEMA_RELATORIO_CICLO, relatorio_ciclo),
]
