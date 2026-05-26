"""Tools de lookup — descobrir entidades (alunos, ciclos, simulados, matérias).

Estas são a porta de entrada do agente: como o usuário fala por nome,
precisamos resolver "aluno João Silva" → aluno_id antes de usar tools que
exigem id. Por isso o LLM SEMPRE chama lookup antes das tools detalhadas.
"""

from __future__ import annotations

from typing import Any

from supabase import Client


# ─── buscar_aluno_por_nome ────────────────────────────────────────────────

def buscar_aluno_por_nome(cliente: Client, *, nome: str, limite: int = 8) -> dict:
    """Busca alunos por nome (ILIKE %nome%). Retorna até `limite` candidatos."""
    if not nome or len(nome.strip()) < 2:
        return {"erro": "nome muito curto (mín. 2 caracteres)"}
    padrao = f"%{nome.strip()}%"
    resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, ativo")
        .ilike("nome", padrao)
        .order("nome")
        .limit(limite)
        .execute()
    )
    return {"total": len(resp.data or []), "alunos": resp.data or []}


_SCHEMA_BUSCAR_ALUNO = {
    "name": "buscar_aluno_por_nome",
    "description": (
        "Procura alunos pelo nome (busca parcial, case-insensitive). "
        "Use SEMPRE primeiro quando o usuário menciona um aluno por nome — "
        "você precisa do id antes de chamar outras tools."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "nome": {
                "type": "string",
                "description": "Trecho do nome do aluno (mín. 2 caracteres).",
            },
            "limite": {
                "type": "integer",
                "description": "Máx. de candidatos (default 8).",
                "default": 8,
            },
        },
        "required": ["nome"],
    },
}


# ─── obter_aluno ──────────────────────────────────────────────────────────

def obter_aluno(cliente: Client, *, aluno_id: str) -> dict:
    """Detalhes do aluno + classificação atual (perfil, tendência, zona, média)."""
    resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, ativo")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"erro": f"aluno {aluno_id} não encontrado"}
    aluno = resp.data[0]

    classif_resp = (
        cliente.table("classificacao_aluno")
        .select("perfil, tendencia, zona, media_recente, desvio_recente, coef_tendencia")
        .eq("aluno_id", aluno_id)
        .limit(1)
        .execute()
    )
    classif = (classif_resp.data or [{}])[0]

    vest_resp = (
        cliente.table("vestibular_alvo_aluno")
        .select("vestibular")
        .eq("aluno_id", aluno_id)
        .execute()
    )
    vestibulares = [v["vestibular"] for v in (vest_resp.data or [])]

    turma = _turma_ativa(cliente, aluno_id)

    return {
        **aluno,
        "vestibularesAlvo": vestibulares,
        "turma": turma,
        "classificacao": {
            "perfil": classif.get("perfil"),
            "tendencia": classif.get("tendencia"),
            "zona": classif.get("zona"),
            "mediaRecente": _f(classif.get("media_recente")),
            "desvioRecente": _f(classif.get("desvio_recente")),
            "coefTendencia": _f(classif.get("coef_tendencia")),
        },
    }


_SCHEMA_OBTER_ALUNO = {
    "name": "obter_aluno",
    "description": (
        "Detalhes completos de um aluno (perfil, tendência, zona, média recente, "
        "turma, vestibulares-alvo). Use após buscar_aluno_por_nome ter retornado o id."
    ),
    "parameters": {
        "type": "object",
        "properties": {"aluno_id": {"type": "string", "description": "UUID do aluno."}},
        "required": ["aluno_id"],
    },
}


# ─── listar_ciclos ────────────────────────────────────────────────────────

def listar_ciclos(cliente: Client) -> dict:
    """Lista todos os ciclos ordenados por ano e ordem (mais antigos primeiro)."""
    resp = (
        cliente.table("ciclo")
        .select("id, nome, ordem, vestibular_alvo, periodo_inicio, periodo_fim, ano_letivo(ano)")
        .order("ordem")
        .execute()
    )
    saida = []
    for c in resp.data or []:
        saida.append(
            {
                "id": c["id"],
                "nome": c["nome"],
                "ordem": c["ordem"],
                "ano": (c.get("ano_letivo") or {}).get("ano"),
                "vestibularAlvo": c.get("vestibular_alvo"),
                "periodoInicio": c.get("periodo_inicio"),
                "periodoFim": c.get("periodo_fim"),
            }
        )
    # Ordena por (ano, ordem) crescente, depois inverte → mais recentes primeiro
    saida.sort(key=lambda c: ((c["ano"] or 0), c["ordem"] or 0), reverse=True)
    return {"total": len(saida), "ciclos": saida}


_SCHEMA_LISTAR_CICLOS = {
    "name": "listar_ciclos",
    "description": (
        "Lista todos os ciclos cadastrados (mais recentes primeiro). "
        "Use para descobrir o id do ciclo quando o usuário fala 'ciclo passado', 'último ciclo' etc."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── listar_simulados ─────────────────────────────────────────────────────

def listar_simulados(
    cliente: Client,
    *,
    ciclo_id: str | None = None,
    materia_codigo: str | None = None,
    incluir_anulados: bool = False,
    limite: int = 30,
) -> dict:
    """Lista simulados com filtros opcionais (ciclo / matéria)."""
    q = (
        cliente.table("simulado")
        .select(
            "id, nome, rotulo_curto, tipo, fase, data_aplicacao, ciclo_id, "
            "materia_id, anulado, e_agregado"
        )
        .order("data_aplicacao", desc=True)
    )
    if ciclo_id:
        q = q.eq("ciclo_id", ciclo_id)
    if not incluir_anulados:
        q = q.eq("anulado", False)
    if materia_codigo:
        # Resolve materia_id pelo código
        m = (
            cliente.table("materia")
            .select("id")
            .eq("codigo", materia_codigo)
            .limit(1)
            .execute()
        )
        if not m.data:
            return {"erro": f"matéria '{materia_codigo}' não existe"}
        q = q.eq("materia_id", m.data[0]["id"])
    q = q.limit(limite)
    resp = q.execute()

    materias_nome = _mapa_codigo_nome_materia(cliente)
    saida = []
    for s in resp.data or []:
        mid = s.get("materia_id")
        mat = materias_nome.get(mid) if mid else None
        saida.append(
            {
                "id": s["id"],
                "nome": s["nome"],
                "rotuloCurto": s.get("rotulo_curto"),
                "tipo": s.get("tipo"),
                "fase": s.get("fase"),
                "dataAplicacao": s.get("data_aplicacao"),
                "cicloId": s.get("ciclo_id"),
                "materia": mat,
                "anulado": s.get("anulado"),
                "eAgregado": s.get("e_agregado"),
            }
        )
    return {"total": len(saida), "simulados": saida}


_SCHEMA_LISTAR_SIMULADOS = {
    "name": "listar_simulados",
    "description": (
        "Lista simulados, opcionalmente filtrando por ciclo_id e/ou matéria. "
        "Ordenados do mais recente pro mais antigo."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ciclo_id": {"type": "string", "description": "UUID do ciclo (opcional)."},
            "materia_codigo": {
                "type": "string",
                "enum": ["matematica", "fisica", "quimica", "portugues", "ingles", "redacao"],
                "description": "Código slug da matéria (opcional).",
            },
            "incluir_anulados": {"type": "boolean", "default": False},
            "limite": {"type": "integer", "default": 30, "description": "Máx. simulados retornados."},
        },
        "required": [],
    },
}


# ─── obter_simulado ───────────────────────────────────────────────────────

def obter_simulado(cliente: Client, *, simulado_id: str) -> dict:
    """Detalhes de um simulado + métricas gerais (média, mediana, desvio, n)."""
    resp = (
        cliente.table("simulado")
        .select(
            "id, nome, rotulo_curto, tipo, fase, data_aplicacao, ciclo_id, "
            "materia_id, nota_maxima, anulado, e_agregado"
        )
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"erro": f"simulado {simulado_id} não encontrado"}
    s = resp.data[0]

    metr = (
        cliente.table("metrica_simulado")
        .select("media, mediana, desvio_padrao, minimo, maximo, quartil_1, quartil_3, n_presentes, n_ausentes")
        .eq("simulado_id", simulado_id)
        .eq("recorte_tipo", "geral")
        .is_("recorte_id", "null")
        .limit(1)
        .execute()
    )
    m = (metr.data or [{}])[0]

    mat = None
    if s.get("materia_id"):
        mat_resp = (
            cliente.table("materia")
            .select("codigo, nome")
            .eq("id", s["materia_id"])
            .limit(1)
            .execute()
        )
        if mat_resp.data:
            mat = mat_resp.data[0]

    return {
        "id": s["id"],
        "nome": s["nome"],
        "rotuloCurto": s.get("rotulo_curto"),
        "tipo": s.get("tipo"),
        "fase": s.get("fase"),
        "dataAplicacao": s.get("data_aplicacao"),
        "cicloId": s.get("ciclo_id"),
        "materia": mat,
        "notaMaxima": _f(s.get("nota_maxima")),
        "anulado": s.get("anulado"),
        "eAgregado": s.get("e_agregado"),
        "metricas": {
            "media": _f(m.get("media")),
            "mediana": _f(m.get("mediana")),
            "desvioPadrao": _f(m.get("desvio_padrao")),
            "minimo": _f(m.get("minimo")),
            "maximo": _f(m.get("maximo")),
            "quartil1": _f(m.get("quartil_1")),
            "quartil3": _f(m.get("quartil_3")),
            "nPresentes": m.get("n_presentes"),
            "nAusentes": m.get("n_ausentes"),
        },
    }


_SCHEMA_OBTER_SIMULADO = {
    "name": "obter_simulado",
    "description": "Detalhes de um simulado + métricas gerais (média, mediana, desvio, n).",
    "parameters": {
        "type": "object",
        "properties": {"simulado_id": {"type": "string", "description": "UUID do simulado."}},
        "required": ["simulado_id"],
    },
}


# ─── listar_materias ──────────────────────────────────────────────────────

def listar_materias(cliente: Client) -> dict:
    resp = cliente.table("materia").select("codigo, nome").order("nome").execute()
    return {"materias": resp.data or []}


_SCHEMA_LISTAR_MATERIAS = {
    "name": "listar_materias",
    "description": "Lista todas as matérias (código + nome). Use só se precisar mapear nome → código.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── Helpers ─────────────────────────────────────────────────────────────

def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _turma_ativa(cliente: Client, aluno_id: str) -> dict | None:
    """Turma atual do aluno (matricula sem ativo_ate)."""
    resp = (
        cliente.table("matricula_turma")
        .select("turma(id, serie, trilha, section_original, sede(nome))")
        .eq("aluno_id", aluno_id)
        .is_("ativo_ate", "null")
        .order("ativo_desde", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return None
    t = resp.data[0].get("turma") or {}
    sede = (t.get("sede") or {}).get("nome")
    return {
        "id": t.get("id"),
        "serie": t.get("serie"),
        "trilha": t.get("trilha"),
        "sectionOriginal": t.get("section_original"),
        "sede": sede,
    }


def _mapa_codigo_nome_materia(cliente: Client) -> dict[str, dict]:
    resp = cliente.table("materia").select("id, codigo, nome").execute()
    return {m["id"]: {"codigo": m["codigo"], "nome": m["nome"]} for m in (resp.data or [])}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_BUSCAR_ALUNO, buscar_aluno_por_nome),
    (_SCHEMA_OBTER_ALUNO, obter_aluno),
    (_SCHEMA_LISTAR_CICLOS, listar_ciclos),
    (_SCHEMA_LISTAR_SIMULADOS, listar_simulados),
    (_SCHEMA_OBTER_SIMULADO, obter_simulado),
    (_SCHEMA_LISTAR_MATERIAS, listar_materias),
]
