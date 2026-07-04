"""Tools de artefato — gerar gráficos inline e exportar CSV.

Diferente das outras tools (que só leem do banco), estas produzem payloads
que viram renderizações no frontend. O agente chama com os parâmetros e o
backend devolve dicionários que o front interpreta:
  - histograma     → renderiza com componente histograma.js
  - linha_temporal → renderiza com componente linha-temporal.js
  - tabela         → tabela markdown inline (o LLM costuma fazer bem sozinho,
                     mas tem caso em que vale forçar estrutura)
  - csv            → upload no storage e retorna URL

No MVP, CSV é simplificado: gera string CSV inline (até ~500 linhas) e devolve
no payload. Pra escala maior, integrar com supabase storage depois.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from supabase import Client

from ...stats.utils import como_float, nota_real


# ─── gerar_grafico ────────────────────────────────────────────────────────

def gerar_grafico(
    cliente: Client,
    *,
    tipo: str,
    fonte: str,
    fonte_id: str,
    titulo: str | None = None,
) -> dict:
    """Gera um artefato visual a partir de uma fonte conhecida.

    Combinações suportadas:
      - tipo='histograma',     fonte='simulado',   fonte_id=<id>  → distribuição de notas
      - tipo='linha_temporal', fonte='aluno',      fonte_id=<id>  → trajetória do aluno
      - tipo='linha_temporal', fonte='ciclo',      fonte_id=<id>  → evolução do ciclo

    Retorna `{tipo, titulo, payload}` — onde `payload` é o que o componente
    do frontend (histograma.js / linha-temporal.js) sabe renderizar.
    """
    if tipo == "histograma" and fonte == "simulado":
        return _hist_simulado(cliente, fonte_id, titulo)
    if tipo == "linha_temporal" and fonte == "aluno":
        return _linha_aluno(cliente, fonte_id, titulo)
    if tipo == "linha_temporal" and fonte == "ciclo":
        return _linha_ciclo(cliente, fonte_id, titulo)
    return {"erro": f"combinação não suportada: tipo={tipo}, fonte={fonte}"}


_SCHEMA_GERAR_GRAFICO = {
    "name": "gerar_grafico",
    "description": (
        "Cria um gráfico inline que o frontend renderiza junto da resposta. "
        "Combinações suportadas: "
        "(tipo='histograma', fonte='simulado'), "
        "(tipo='linha_temporal', fonte='aluno'), "
        "(tipo='linha_temporal', fonte='ciclo')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": ["histograma", "linha_temporal"]},
            "fonte": {"type": "string", "enum": ["simulado", "aluno", "ciclo"]},
            "fonte_id": {"type": "string", "description": "UUID da entidade fonte."},
            "titulo": {"type": "string", "description": "Título exibido acima do gráfico."},
        },
        "required": ["tipo", "fonte", "fonte_id"],
    },
}


# ─── exportar_csv ─────────────────────────────────────────────────────────

def exportar_csv(
    cliente: Client,
    *,
    fonte: str,
    fonte_id: str | None = None,
    zona: str | None = None,
    titulo: str | None = None,
) -> dict:
    """Gera CSV inline a partir de uma fonte conhecida.

    Fontes:
      - 'notas_simulado'        : todas as notas de um simulado (precisa fonte_id)
      - 'alunos_por_zona'       : lista de alunos numa zona (precisa zona: 'top'/'risco'/'cinzenta')
      - 'trajetoria_aluno'      : trajetória completa de um aluno (precisa fonte_id)
    """
    if fonte == "notas_simulado" and fonte_id:
        rows = _csv_notas_simulado(cliente, fonte_id)
    elif fonte == "alunos_por_zona" and zona:
        rows = _csv_alunos_por_zona(cliente, zona)
    elif fonte == "trajetoria_aluno" and fonte_id:
        rows = _csv_trajetoria(cliente, fonte_id)
    elif fonte == "relatorio_aluno" and fonte_id:
        rows = _csv_relatorio_aluno(cliente, fonte_id)
    elif fonte == "relatorio_ciclo" and fonte_id:
        rows = _csv_relatorio_ciclo(cliente, fonte_id)
    else:
        return {"erro": f"fonte/argumentos inválidos: fonte={fonte}, fonte_id={fonte_id}, zona={zona}"}

    if not rows:
        return {"erro": "nenhuma linha pra exportar"}

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    conteudo = buf.getvalue()
    return {
        "tipo": "csv",
        "titulo": titulo or f"export-{fonte}",
        "nLinhas": len(rows),
        "conteudo": conteudo,
    }


_SCHEMA_EXPORTAR_CSV = {
    "name": "exportar_csv",
    "description": (
        "Gera um CSV inline a partir de uma fonte conhecida. O frontend mostra como "
        "botão de download. Use para listas grandes (>30 itens) que não cabem no chat."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "fonte": {
                "type": "string",
                "enum": [
                    "notas_simulado",
                    "alunos_por_zona",
                    "trajetoria_aluno",
                    "relatorio_aluno",
                    "relatorio_ciclo",
                ],
            },
            "fonte_id": {"type": "string", "description": "UUID quando fonte exige (não usado em alunos_por_zona)."},
            "zona": {
                "type": "string",
                "enum": ["top", "cinzenta", "risco"],
                "description": "Para fonte='alunos_por_zona'.",
            },
            "titulo": {"type": "string", "description": "Título sugerido pro arquivo."},
        },
        "required": ["fonte"],
    },
}


# ─── Implementações dos artefatos ────────────────────────────────────────

def _hist_simulado(cliente: Client, simulado_id: str, titulo: str | None) -> dict:
    resp = (
        cliente.table("metrica_simulado")
        .select("media, mediana, desvio_padrao, n_presentes, histograma")
        .eq("simulado_id", simulado_id)
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"erro": f"sem métricas calculadas pro simulado {simulado_id}"}
    m = resp.data[0]
    sim_resp = (
        cliente.table("simulado")
        .select("nome, rotulo_curto, data_aplicacao")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    sim = (sim_resp.data or [{}])[0]
    return {
        "tipo": "histograma",
        "titulo": titulo or f"Distribuição — {sim.get('nome', 'simulado')}",
        "payload": {
            "histograma": m.get("histograma"),
            "media": como_float(m.get("media")),
            "mediana": como_float(m.get("mediana")),
            "desvioPadrao": como_float(m.get("desvio_padrao")),
            "nPresentes": m.get("n_presentes"),
            "simuladoId": simulado_id,
            "simuladoNome": sim.get("nome"),
        },
    }


def _linha_aluno(cliente: Client, aluno_id: str, titulo: str | None) -> dict:
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, anulado, e_agregado, nota_maxima)"
        )
        .eq("aluno_id", aluno_id)
        .execute()
    )
    aluno_resp = cliente.table("aluno").select("nome").eq("id", aluno_id).limit(1).execute()
    aluno_nome = (aluno_resp.data or [{}])[0].get("nome", aluno_id)

    pontos = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado") or not linha.get("presente"):
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        pontos.append({
            "data": sim.get("data_aplicacao"),
            "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
            "nota": round(nota, 2),
            "simuladoId": sim.get("id"),
        })
    pontos.sort(key=lambda p: p["data"] or "")

    return {
        "tipo": "linha_temporal",
        "titulo": titulo or f"Evolução — {aluno_nome}",
        "payload": {"pontos": pontos, "alunoId": aluno_id, "alunoNome": aluno_nome},
    }


def _linha_ciclo(cliente: Client, ciclo_id: str, titulo: str | None) -> dict:
    """Evolução do ciclo: cada ponto é a média do simulado."""
    from ...stats import ciclo_estatisticas
    payload = ciclo_estatisticas.calcular(cliente, ciclo_id=ciclo_id)
    if payload is None:
        return {"erro": f"ciclo {ciclo_id} não encontrado"}
    evol = payload.get("evolucaoTemporal") or []
    pontos = [
        {
            "data": p.get("data"),
            "rotulo": p.get("rotuloCurto") or p.get("nome"),
            "nota": p.get("media"),
            "simuladoId": p.get("simuladoId"),
            "materia": (p.get("materia") or {}).get("nome"),
            "fase": p.get("fase"),
        }
        for p in evol
    ]
    nome = (payload.get("ciclo") or {}).get("nome", ciclo_id)
    return {
        "tipo": "linha_temporal",
        "titulo": titulo or f"Evolução do ciclo — {nome}",
        "payload": {"pontos": pontos, "cicloId": ciclo_id, "cicloNome": nome},
    }


def _csv_notas_simulado(cliente: Client, simulado_id: str) -> list[dict]:
    sim = (
        cliente.table("simulado")
        .select("nota_maxima, nome")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not sim.data:
        return []
    nota_max = como_float(sim.data[0].get("nota_maxima"))

    resp = (
        cliente.table("nota")
        .select("pontuacao, presente, aluno(nome, matricula)")
        .eq("simulado_id", simulado_id)
        .execute()
    )
    rows = []
    for linha in resp.data or []:
        aluno = linha.get("aluno") or {}
        bruta = como_float(linha.get("pontuacao"))
        nota = nota_real(bruta, nota_max)
        rows.append({
            "matricula": aluno.get("matricula", ""),
            "nome": aluno.get("nome", ""),
            "presente": "sim" if linha.get("presente") else "nao",
            "nota": round(nota, 2) if nota is not None else "",
        })
    rows.sort(key=lambda r: (-(r["nota"] or 0)))
    return rows


def _csv_alunos_por_zona(cliente: Client, zona: str) -> list[dict]:
    resp = (
        cliente.table("classificacao_aluno")
        .select("aluno_id, perfil, tendencia, zona, media_recente, desvio_recente")
        .eq("zona", zona)
        .execute()
    )
    if not resp.data:
        return []
    aluno_ids = [r["aluno_id"] for r in resp.data]
    nomes_resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, ativo")
        .in_("id", aluno_ids)
        .execute()
    )
    nomes = {a["id"]: a for a in (nomes_resp.data or [])}
    rows = []
    for r in resp.data:
        a = nomes.get(r["aluno_id"]) or {}
        if not a.get("ativo", True):
            continue
        rows.append({
            "matricula": a.get("matricula", ""),
            "nome": a.get("nome", ""),
            "perfil": r.get("perfil"),
            "tendencia": r.get("tendencia"),
            "zona": r.get("zona"),
            "media_recente": como_float(r.get("media_recente")) or "",
            "desvio_recente": como_float(r.get("desvio_recente")) or "",
        })
    rows.sort(key=lambda x: x["nome"])
    return rows


def _csv_trajetoria(cliente: Client, aluno_id: str) -> list[dict]:
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "nome, rotulo_curto, data_aplicacao, anulado, e_agregado, "
            "nota_maxima, tipo, materia_id)"
        )
        .eq("aluno_id", aluno_id)
        .execute()
    )
    materias_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (materias_resp.data or [])}

    rows = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        rows.append({
            "data": sim.get("data_aplicacao") or "",
            "simulado": sim.get("nome", ""),
            "rotulo": sim.get("rotulo_curto") or "",
            "materia": nome_mat.get(sim.get("materia_id"), ""),
            "presente": "sim" if linha.get("presente") else "nao",
            "nota": round(nota, 2) if nota is not None else "",
        })
    rows.sort(key=lambda r: r["data"])
    return rows


def _csv_relatorio_aluno(cliente: Client, aluno_id: str) -> list[dict]:
    """CSV do relatório do aluno: uma linha por nota, com ciclo e matéria."""
    from .relatorios import historico_aluno
    hist = historico_aluno(cliente, aluno_id=aluno_id)
    if "erro" in hist:
        return []
    rows = []
    for ciclo_bloco in hist.get("ciclos") or []:
        ciclo_nome = (ciclo_bloco.get("ciclo") or {}).get("nome", "")
        for n in ciclo_bloco.get("notas") or []:
            rows.append({
                "ciclo": ciclo_nome,
                "data": n.get("data") or "",
                "simulado": n.get("simulado") or "",
                "materia": n.get("materia") or "",
                "tipo": n.get("tipo") or "",
                "presente": "sim" if n.get("presente") else "nao",
                "nota": n.get("nota") if n.get("nota") is not None else "",
            })
    return rows


def _csv_relatorio_ciclo(cliente: Client, ciclo_id: str) -> list[dict]:
    """CSV do relatório do ciclo: uma linha por aluno × matéria com médias."""
    from .relatorios import relatorio_ciclo
    rel = relatorio_ciclo(cliente, ciclo_id=ciclo_id)
    if "erro" in rel:
        return []
    ciclo_nome = (rel.get("ciclo") or {}).get("nome", "")
    rows = []
    for mat in rel.get("porMateria") or []:
        rows.append({
            "ciclo": ciclo_nome,
            "materia": mat.get("materia") or "",
            "nAlunos": mat.get("nAlunos") or "",
            "media": mat.get("media") or "",
            "pctAbaixoCorte": mat.get("pctAbaixoCorte") or "",
            "abaixoCorte": mat.get("abaixoCorte") or "",
        })
    return rows


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_GERAR_GRAFICO, gerar_grafico),
    (_SCHEMA_EXPORTAR_CSV, exportar_csv),
]
