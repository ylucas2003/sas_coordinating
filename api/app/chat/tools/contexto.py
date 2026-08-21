"""Tools de contexto — o que a plataforma mostra e o agente não enxergava.

Alertas e insights são o miolo "proativo" do produto (é o que o Painel exibe
antes de qualquer pergunta), mas o agente não tinha como lê-los: ele sabia
recalcular quem está em risco na hora e não sabia o que o próprio sistema já
havia sinalizado. Sede e turma são filtros de primeira classe na interface e
também não existiam aqui — sem eles o agente não responde nada recortado por
unidade.
"""

from __future__ import annotations

from typing import Any

from supabase import Client

_PESO_SEVERIDADE = {"critico": 0, "atencao": 1, "informativo": 2}


# ─── listar_alertas ───────────────────────────────────────────────────────

def listar_alertas(
    cliente: Client,
    *,
    severidade: str | None = None,
    categoria: str | None = None,
    limite: int = 20,
) -> dict:
    """Alertas pendentes (não resolvidos), do mais severo para o menos."""
    consulta = (
        cliente.table("alerta")
        .select("id, categoria, severidade, entidade_tipo, entidade_id, titulo, subtitulo, disparado_em")
        .eq("resolvido", False)
    )
    if severidade:
        consulta = consulta.eq("severidade", severidade)
    if categoria:
        consulta = consulta.eq("categoria", categoria)

    linhas = consulta.order("disparado_em", desc=True).limit(100).execute().data or []
    linhas.sort(key=lambda r: (_PESO_SEVERIDADE.get(r["severidade"], 99), r.get("disparado_em") or ""))
    return {"total": len(linhas), "alertas": linhas[:limite]}


_SCHEMA_LISTAR_ALERTAS = {
    "name": "listar_alertas",
    "description": (
        "Alertas pendentes que o SISTEMA já sinalizou (queda de desempenho, "
        "variância anômala, etc.), do mais severo para o menos. Use quando "
        "perguntarem 'o que precisa de atenção', 'tem algum alerta', 'o que "
        "aconteceu de importante'. Diferente de alunos_em_risco, que calcula "
        "na hora: aqui você lê o que já foi detectado e ainda não foi resolvido."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "severidade": {
                "type": "string",
                "enum": ["critico", "atencao", "informativo"],
                "description": "Filtra por severidade (opcional).",
            },
            "categoria": {"type": "string", "description": "Filtra por categoria (opcional)."},
            "limite": {"type": "integer", "default": 20, "description": "Máx. de alertas."},
        },
    },
}


# ─── insights_do_ciclo ────────────────────────────────────────────────────

def insights_do_ciclo(
    cliente: Client,
    *,
    ciclo_id: str,
    fase: str = "todas",
    materia_codigo: str | None = None,
) -> dict:
    """Insights JÁ GERADOS para o ciclo (leitura de cache, não gera novos).

    Gerar insight chama o LLM; fazer isso de dentro de uma conversa que já é
    uma chamada de LLM sairia caro e lento. Aqui só lemos o que a tela do
    Painel produziu.
    """
    consulta = (
        cliente.table("insight_ciclo")
        .select("fase, materia_codigo, tipo_insight, bullets, gerado_em")
        .eq("ciclo_id", ciclo_id)
    )
    if fase != "todas":
        consulta = consulta.eq("fase", fase)
    if materia_codigo:
        consulta = consulta.eq("materia_codigo", materia_codigo)

    linhas = consulta.order("gerado_em", desc=True).limit(20).execute().data or []
    if not linhas:
        return {
            "total": 0,
            "insights": [],
            "aviso": "Nenhum insight gerado ainda para este recorte. Eles são "
                     "produzidos quando alguém abre o ciclo no Painel.",
        }
    return {"total": len(linhas), "insights": linhas}


_SCHEMA_INSIGHTS_CICLO = {
    "name": "insights_do_ciclo",
    "description": (
        "Insights em texto já gerados para um ciclo (leitura, não gera novos). "
        "Use para saber o que o sistema já concluiu sobre o ciclo antes de "
        "recalcular estatísticas do zero."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ciclo_id": {"type": "string", "description": "UUID do ciclo."},
            "fase": {
                "type": "string",
                "enum": ["fase_1", "fase_2", "todas"],
                "default": "todas",
            },
            "materia_codigo": {"type": "string", "description": "Slug da matéria (opcional)."},
        },
        "required": ["ciclo_id"],
    },
}


# ─── listar_alunos ────────────────────────────────────────────────────────

def listar_alunos(
    cliente: Client,
    *,
    zona: str | None = None,
    perfil: str | None = None,
    tendencia: str | None = None,
    turma_id: str | None = None,
    sede_id: str | None = None,
    limite: int = 30,
) -> dict:
    """Alunos filtrados por classificação e/ou lotação — o que a tela Alunos faz."""
    consulta = cliente.table("classificacao_aluno").select(
        "aluno_id, perfil, tendencia, zona, media_recente, aluno:aluno_id(id, nome, matricula)"
    )
    if zona:
        consulta = consulta.eq("zona", zona)
    if perfil:
        consulta = consulta.eq("perfil", perfil)
    if tendencia:
        consulta = consulta.eq("tendencia", tendencia)

    linhas = consulta.limit(500).execute().data or []

    # Turma/sede vivem em matricula_turma, não na classificação — filtramos
    # por interseção de ids em vez de tentar um join que o PostgREST não faz
    # direto a partir desta tabela.
    if turma_id or sede_id:
        ids = _alunos_por_lotacao(cliente, turma_id=turma_id, sede_id=sede_id)
        linhas = [l for l in linhas if l["aluno_id"] in ids]

    linhas.sort(key=lambda r: (r.get("media_recente") is None, -(r.get("media_recente") or 0)))

    alunos = [
        {
            "alunoId": l["aluno_id"],
            "nome": (l.get("aluno") or {}).get("nome"),
            "matricula": (l.get("aluno") or {}).get("matricula"),
            "zona": l["zona"],
            "perfil": l["perfil"],
            "tendencia": l["tendencia"],
            "mediaRecente": l.get("media_recente"),
        }
        for l in linhas
    ]
    return {"total": len(alunos), "alunos": alunos[:limite]}


def _alunos_por_lotacao(cliente: Client, *, turma_id: str | None, sede_id: str | None) -> set[str]:
    if sede_id and not turma_id:
        turmas = cliente.table("turma").select("id").eq("sede_id", sede_id).execute().data or []
        turma_ids = [t["id"] for t in turmas]
        if not turma_ids:
            return set()
        resp = cliente.table("matricula_turma").select("aluno_id").in_("turma_id", turma_ids).execute()
    else:
        resp = cliente.table("matricula_turma").select("aluno_id").eq("turma_id", turma_id).execute()
    return {m["aluno_id"] for m in (resp.data or [])}


_SCHEMA_LISTAR_ALUNOS = {
    "name": "listar_alunos",
    "description": (
        "Lista alunos por classificação (zona, perfil, tendência) e/ou lotação "
        "(turma, sede), ordenados pela média mais recente. É o equivalente da "
        "tela Alunos. Sem nenhum filtro, devolve todos. Para descobrir turma_id "
        "ou sede_id, use listar_turmas / listar_sedes."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "zona": {"type": "string", "enum": ["top", "cinzenta", "risco"]},
            "perfil": {"type": "string", "enum": ["ancora", "misterio", "regular"]},
            "tendencia": {"type": "string", "enum": ["subindo", "estavel", "caindo"]},
            "turma_id": {"type": "string", "description": "UUID da turma."},
            "sede_id": {"type": "string", "description": "UUID da sede."},
            "limite": {"type": "integer", "default": 30},
        },
    },
}


# ─── listar_sedes / listar_turmas ─────────────────────────────────────────

def listar_sedes(cliente: Client) -> dict:
    resp = cliente.table("sede").select("id, nome, codigo, modalidade").order("nome").execute()
    return {"sedes": resp.data or []}


_SCHEMA_LISTAR_SEDES = {
    "name": "listar_sedes",
    "description": (
        "Lista as sedes (unidades) do colégio. Use para mapear um nome de sede "
        "citado pelo usuário ('Aldeota', 'Online') no sede_id que listar_alunos espera."
    ),
    "parameters": {"type": "object", "properties": {}},
}


def listar_turmas(cliente: Client, *, sede_id: str | None = None) -> dict:
    consulta = cliente.table("turma").select(
        "id, section_original, serie, trilha, sede_id, sede:sede_id(nome)"
    )
    if sede_id:
        consulta = consulta.eq("sede_id", sede_id)
    linhas = consulta.order("section_original").execute().data or []
    return {
        "turmas": [
            {
                "id": t["id"],
                "nome": t.get("section_original"),
                "serie": t.get("serie"),
                "trilha": t.get("trilha"),
                "sedeId": t.get("sede_id"),
                "sede": (t.get("sede") or {}).get("nome"),
            }
            for t in linhas
        ]
    }


_SCHEMA_LISTAR_TURMAS = {
    "name": "listar_turmas",
    "description": (
        "Lista as turmas, opcionalmente de uma sede. Use para mapear o nome de "
        "uma turma no turma_id que listar_alunos espera."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "sede_id": {"type": "string", "description": "UUID da sede (opcional)."},
        },
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, callable]] = [
    (_SCHEMA_LISTAR_ALERTAS, listar_alertas),
    (_SCHEMA_INSIGHTS_CICLO, insights_do_ciclo),
    (_SCHEMA_LISTAR_ALUNOS, listar_alunos),
    (_SCHEMA_LISTAR_SEDES, listar_sedes),
    (_SCHEMA_LISTAR_TURMAS, listar_turmas),
]
