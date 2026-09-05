"""Tools heurísticas — perguntas pedagógicas com critério codificado.

Por que aqui (e não no LLM)?
  - "Aluno em risco" e "destaque" precisam ter critério REPRODUTÍVEL e auditável.
  - Critério fixo + LLM narra = melhor combinação custo/qualidade.

Critérios atuais (calibráveis em stats/thresholds.py):
  - em risco       → classificacao.zona == 'risco' (já calculado pelo stats engine)
  - destaque       → classificacao.zona == 'top'
  - tendência      → classificacao.coef_tendencia
  - matérias com queda → para cada matéria, % de alunos abaixo do corte agora vs. ciclo anterior
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict

from supabase import Client

from ...stats import criterios
from ...stats.utils import como_float, nota_real, simulado_entra_no_agregado

# ─── alunos_em_risco ──────────────────────────────────────────────────────

def alunos_em_risco(cliente: Client, *, limite: int = 30) -> dict:
    """Lista alunos com `zona='risco'` — o veredito do avaliador de criterios.py.

    A zona deixou de ser "alguma matéria abaixo de 4,0 OU média baixa": ela sai
    de `avaliar(CRITERIO_DA_CASA, …)`, e a régua do colégio corta com E, não
    com OU. Um aluno com 2,0 em Matemática e 8,0 no resto NÃO está em risco por
    essa régua (docs/31 §P1).
    """
    return _alunos_por_zona(cliente, zona="risco", limite=limite, ordenacao="asc_media")


_SCHEMA_RISCO = {
    "name": "alunos_em_risco",
    "description": (
        "Alunos atualmente em zona de risco. A zona é o veredito do avaliador de "
        "stats/criterios.py sob a régua da casa ('Tio Leo'), que corta quem falha na "
        "matéria E na média, mais as matérias eliminatórias — não é 'alguma matéria "
        "abaixo de um número'. Não invente critério alternativo nem cite corte fixo: "
        "para o corte de cada matéria, use materias_problematicas, que devolve o valor."
    ),
    "parameters": {
        "type": "object",
        "properties": {"limite": {"type": "integer", "default": 30}},
        "required": [],
    },
}


# ─── alunos_destaque ──────────────────────────────────────────────────────

def alunos_destaque(cliente: Client, *, limite: int = 20) -> dict:
    """Lista alunos com zona='top' — confortavelmente acima do corte."""
    return _alunos_por_zona(cliente, zona="top", limite=limite, ordenacao="desc_media")


_SCHEMA_DESTAQUE = {
    "name": "alunos_destaque",
    "description": (
        "Alunos com desempenho de destaque — zona 'top' (todas as matérias com margem "
        "confortável acima do corte). Ordenados pela média recente."
    ),
    "parameters": {
        "type": "object",
        "properties": {"limite": {"type": "integer", "default": 20}},
        "required": [],
    },
}


# ─── tendencia_aluno ──────────────────────────────────────────────────────

def tendencia_aluno(cliente: Client, *, aluno_id: str) -> dict:
    """Resumo do movimento recente do aluno: slope, classificação, last vs. anterior."""
    classif_resp = (
        cliente.table("classificacao_aluno")
        .select("perfil, tendencia, zona, media_recente, desvio_recente, coef_tendencia, p_valor_tendencia, janela_simulados")
        .eq("aluno_id", aluno_id)
        .limit(1)
        .execute()
    )
    if not classif_resp.data:
        return {"erro": f"aluno {aluno_id} sem classificação calculada (notas insuficientes?)"}

    c = classif_resp.data[0]
    return {
        "alunoId": aluno_id,
        "perfil": c.get("perfil"),
        "tendencia": c.get("tendencia"),
        "zona": c.get("zona"),
        "mediaRecente": como_float(c.get("media_recente")),
        "desvioRecente": como_float(c.get("desvio_recente")),
        "coefTendencia": como_float(c.get("coef_tendencia")),
        "pValorTendencia": como_float(c.get("p_valor_tendencia")),
        "janelaSimulados": c.get("janela_simulados"),
    }


_SCHEMA_TENDENCIA = {
    "name": "tendencia_aluno",
    "description": (
        "Resumo de tendência de um aluno: perfil, zona, coeficiente angular da regressão das "
        "últimas N notas, e classificação textual (subindo/estável/caindo). "
        "Critério reproduzível — use sempre que perguntarem 'está melhorando?'."
    ),
    "parameters": {
        "type": "object",
        "properties": {"aluno_id": {"type": "string", "description": "UUID do aluno."}},
        "required": ["aluno_id"],
    },
}


# ─── materias_problematicas ───────────────────────────────────────────────

def materias_problematicas(cliente: Client, *, ciclo_id: str) -> dict:
    """Por matéria: % de alunos abaixo do corte na Fase 2, ordenado pelo pior.

    Calcula direto das notas do ciclo (sem cache adicional). Útil pra
    "quais matérias precisam de mais atenção neste ciclo?"
    """
    # Simulados do ciclo, F2 apenas, não anulados.
    sim_resp = (
        cliente.table("simulado")
        .select(
            "id, materia_id, tipo, fase, nota_maxima, anulado, e_agregado, nota_confiavel"
        )
        .eq("ciclo_id", ciclo_id)
        .execute()
    )
    sims = [
        s for s in (sim_resp.data or [])
        if simulado_entra_no_agregado(s)
        and s.get("materia_id") and s.get("tipo") == "fase_2"
    ]
    if not sims:
        return {"cicloId": ciclo_id, "materias": [], "aviso": "sem simulados de Fase 2 nesse ciclo"}

    nota_max = {s["id"]: como_float(s.get("nota_maxima")) or 10.0 for s in sims}
    sim_por_mat: dict[str, list[str]] = defaultdict(list)
    for s in sims:
        sim_por_mat[s["materia_id"]].append(s["id"])

    materias_resp = cliente.table("materia").select("id, codigo, nome").execute()
    materia_info = {m["id"]: m for m in (materias_resp.data or [])}

    notas_resp = (
        cliente.table("nota")
        .select("aluno_id, simulado_id, pontuacao, presente")
        .in_("simulado_id", [s["id"] for s in sims])
        .eq("presente", True)
        .eq("computavel", True)
        .execute()
    )

    # Agrega: para cada (aluno, matéria), média das notas (escala 0–10).
    por_mat_aluno: dict[tuple[str, str], list[float]] = defaultdict(list)
    sim_para_mat = {s["id"]: s["materia_id"] for s in sims}
    for linha in notas_resp.data or []:
        sim_id = linha["simulado_id"]
        mid = sim_para_mat.get(sim_id)
        if not mid:
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), nota_max.get(sim_id, 10.0))
        if nota is None:
            continue
        por_mat_aluno[(mid, linha["aluno_id"])].append(nota)

    regua = criterios.por_slug(criterios.CRITERIO_DA_CASA)
    saida = []
    for mid in sim_por_mat:
        valores_por_aluno = []
        for (m2, _), notas in por_mat_aluno.items():
            if m2 != mid:
                continue
            valores_por_aluno.append(sum(notas) / len(notas))
        if not valores_por_aluno:
            continue
        m_info = materia_info.get(mid, {})
        codigo = m_info.get("codigo") or ""
        # Cada matéria tem o SEU corte na régua — o do Inglês não é o da
        # Matemática. Somar tudo contra um 4,0 único era o que fazia esta tool
        # discordar do Painel sobre quantos estão abaixo (docs/31 §1.1).
        corte = criterios.corte_da_materia(regua, codigo)
        if corte is None:
            corte = criterios.corte_da_media(regua) or 0.0
        abaixo_corte = sum(1 for v in valores_por_aluno if v < corte)
        saida.append({
            "materia": {"codigo": codigo or None, "nome": m_info.get("nome")},
            "corte": corte,
            "nAlunos": len(valores_por_aluno),
            "abaixoCorte": abaixo_corte,
            "pctAbaixoCorte": round(100 * abaixo_corte / len(valores_por_aluno), 1),
            "media": round(sum(valores_por_aluno) / len(valores_por_aluno), 2),
            "mediana": round(st.median(valores_por_aluno), 2),
        })
    saida.sort(key=lambda r: -r["pctAbaixoCorte"])
    return {"cicloId": ciclo_id, "criterio": regua.nome, "materias": saida}


_SCHEMA_MATERIAS_PROB = {
    "name": "materias_problematicas",
    "description": (
        "Para cada matéria do ciclo (Fase 2), calcula a % de alunos abaixo do corte "
        "que a régua da casa exige NAQUELA matéria (o campo `corte` de cada linha diz qual foi). "
        "Retorna ordenado da pior pra melhor. Útil pra 'em qual matéria devo focar?'"
    ),
    "parameters": {
        "type": "object",
        "properties": {"ciclo_id": {"type": "string", "description": "UUID do ciclo."}},
        "required": ["ciclo_id"],
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────────

def _alunos_por_zona(
    cliente: Client,
    *,
    zona: str,
    limite: int,
    ordenacao: str,
) -> dict:
    """Lista alunos cuja classificação tem a zona indicada.

    `ordenacao`: 'asc_media' (piores primeiro) | 'desc_media' (melhores primeiro)
    """
    resp = (
        cliente.table("classificacao_aluno")
        .select("aluno_id, perfil, tendencia, zona, media_recente")
        .eq("zona", zona)
        .execute()
    )
    if not resp.data:
        return {"zona": zona, "total": 0, "alunos": []}

    aluno_ids = [r["aluno_id"] for r in resp.data]
    nomes_resp = (
        cliente.table("aluno")
        .select("id, nome, ativo")
        .in_("id", aluno_ids)
        .execute()
    )
    nomes = {a["id"]: a for a in (nomes_resp.data or [])}

    linhas = []
    for r in resp.data:
        aid = r["aluno_id"]
        info = nomes.get(aid) or {}
        if not info.get("ativo", True):
            continue
        linhas.append({
            "alunoId": aid,
            "nome": info.get("nome"),
            "perfil": r.get("perfil"),
            "tendencia": r.get("tendencia"),
            "zona": r.get("zona"),
            "media": como_float(r.get("media_recente")),
        })
    reverso = ordenacao == "desc_media"
    linhas.sort(key=lambda x: (x["media"] is None, x["media"]), reverse=reverso)
    truncado = len(linhas) > limite
    return {"zona": zona, "total": len(linhas), "truncado": truncado, "alunos": linhas[:limite]}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_RISCO, alunos_em_risco),
    (_SCHEMA_DESTAQUE, alunos_destaque),
    (_SCHEMA_TENDENCIA, tendencia_aluno),
    (_SCHEMA_MATERIAS_PROB, materias_problematicas),
]
