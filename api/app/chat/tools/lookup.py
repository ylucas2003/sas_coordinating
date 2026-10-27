"""Tools de lookup — descobrir entidades (alunos, ciclos, simulados, matérias).

Estas são a porta de entrada do agente: como o usuário fala por nome,
precisamos resolver "aluno João Silva" → aluno_id antes de usar tools que
exigem id. Por isso o LLM SEMPRE chama lookup antes das tools detalhadas.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client

# ─── buscar_aluno_por_nome ────────────────────────────────────────────────

#: A busca existe para ligar um nome a um id, não para listar a escola: com
#: duas letras e sem teto, `nome='al'` trazia todos os alunos (mapa de LGPD de
#: 24/10; minimização, LGPD art. 6º, III). O despacho não confere `maximum`,
#: então quem limita é o handler.
TETO_DE_CANDIDATOS = 20


def literal_no_like(termo: str) -> str:
    """O termo como LETRAS num padrão LIKE/ILIKE: `%` e `_` são curingas, e a
    barra invertida é o ESCAPE padrão do Postgres — os três vão escapados.

    Sem isto, `nome='__'` ou `'%%'` passava no mínimo de 2 caracteres e trazia
    os primeiros alunos da escola em ordem alfabética, sem trecho de nome
    nenhum (revisão de 26/10, quando a busca por nome entrou no MCP). O `*`
    não tem escape: o PostgREST o troca por `%` em todo padrão de like — quem
    chama tira antes (`buscar_aluno_por_nome`).
    """
    return termo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def buscar_aluno_por_nome(cliente: Client, *, nome: str, limite: int = 8) -> dict:
    """Busca alunos por um TRECHO do nome (ILIKE %trecho%, com o trecho lido
    como letras — `literal_no_like`). Retorna até `limite` candidatos.

    O `*` sai antes de contar os 2 caracteres: nome não tem `*`, e o PostgREST
    o leria como `%` (`'**'` voltaria a listar a escola)."""
    termo = (nome or "").replace("*", "").strip()
    if len(termo) < 2:
        return {"erro": "nome muito curto (mín. 2 caracteres)"}
    padrao = f"%{literal_no_like(termo)}%"
    resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, ativo")
        .ilike("nome", padrao)
        .order("nome")
        .limit(min(max(1, limite), TETO_DE_CANDIDATOS))
        .execute()
    )
    return {"total": len(resp.data or []), "alunos": resp.data or []}


_SCHEMA_BUSCAR_ALUNO = {
    "name": "buscar_aluno_por_nome",
    "description": (
        "Quando usar: SEMPRE primeiro quando o usuário menciona um aluno pelo nome — as "
        "outras tools pedem o id.\n"
        "Antes de chamar, confirme: um trecho do nome com pelo menos 2 letras. Com a "
        "matrícula em mãos, use buscar_aluno_por_matricula.\n"
        "Definições: busca parcial, sem diferenciar maiúscula. Mais de um candidato = "
        "pergunte qual antes de seguir; nunca escolha sozinho.\n"
        "Exemplo: 'como está a Ana Souza?' → buscar_aluno_por_nome(nome='Ana Souza')."
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
                "description": f"Máx. de candidatos, até {TETO_DE_CANDIDATOS}.",
                "default": 8,
            },
        },
        "required": ["nome"],
    },
}


# ─── buscar_aluno_por_matricula ───────────────────────────────────────────

def buscar_aluno_por_matricula(cliente: Client, *, matricula: str) -> dict:
    """O aluno de uma matrícula (o SIS User ID, único na 0001), ou erro.

    Com o pseudônimo ligado (MCP_MOSTRAR_NOME_DO_ALUNO=false), é a única
    porta de entrada que o MCP abre (docs/43 §5.4): buscar por nome deixaria
    no provedor o par "nome digitado ↔ matrícula devolvida", que é justamente
    o vínculo que o pseudônimo quer evitar (mapa de LGPD de 24/10). Com o nome
    real — o padrão desde 26/10 —, `buscar_aluno_por_nome` também está lá
    (`METADADOS`, no fim do módulo). Pela matrícula, quem pergunta já sabe de
    quem fala, e a resposta é no máximo um aluno.
    """
    alvo = (matricula or "").strip()
    if not alvo:
        return {"erro": "informe a matrícula do aluno"}
    resp = (
        cliente.table("aluno")
        .select("id, nome, matricula, ativo")
        .eq("matricula", alvo)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return {"erro": f"nenhum aluno com a matrícula {alvo}"}
    return {"aluno": resp.data[0]}


_SCHEMA_BUSCAR_MATRICULA = {
    "name": "buscar_aluno_por_matricula",
    "description": (
        "Quando usar: quando a pessoa diz a matrícula do aluno ('o 2024001', 'Aluno "
        "9000002') e você precisa do id para as outras tools.\n"
        "Antes de chamar, confirme: a matrícula inteira, como está no cadastro; não há busca "
        "parcial.\n"
        "Definições: matrícula = o SIS User ID do Canvas, única por aluno. A resposta é um "
        "aluno só, com id, nome, matrícula e se está ativo.\n"
        "Exemplo: 'como está o aluno 9000002?' → buscar_aluno_por_matricula(matricula="
        "'9000002'), depois relatorio_aluno com o id."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "matricula": {"type": "string", "description": "A matrícula (SIS User ID) do aluno."},
        },
        "required": ["matricula"],
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
            "id, nome, rotulo_curto, tipo, data_aplicacao, ciclo_id, "
            "materia_id, anulado, e_agregado"
        )
        # Agendados (P1, data futura) ficam de fora: "o último simulado" do
        # assistente deve ser um que já aconteceu.
        .lte("data_aplicacao", date.today().isoformat())
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
            "id, nome, rotulo_curto, tipo, data_aplicacao, ciclo_id, "
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
    (_SCHEMA_BUSCAR_MATRICULA, buscar_aluno_por_matricula),
    (_SCHEMA_OBTER_ALUNO, obter_aluno),
    (_SCHEMA_LISTAR_CICLOS, listar_ciclos),
    (_SCHEMA_LISTAR_SIMULADOS, listar_simulados),
    (_SCHEMA_OBTER_SIMULADO, obter_simulado),
    (_SCHEMA_LISTAR_MATERIAS, listar_materias),
]

#: O que vai ao MCP da coordenação (docs/43 §5.4, mapa de LGPD de 24/10).
#: Catálogo sem pessoa (ciclos, simulados, matérias) e o aluno com chave de
#: identidade no mesmo dict. `buscar_aluno_por_nome` entrou em 26/10, quando o
#: dono decidiu que o MCP mostra o nome do aluno (app/mcp/configuracao.py,
#: `mostrar_nome_do_aluno`): ela só ficava fora porque a entrada é nome
#: digitado, e cada chamada deixaria no provedor o par nome ↔ matrícula — que,
#: com o nome liberado, toda tool de aluno já entrega. Com o pseudônimo ligado
#: de novo, o catálogo do MCP a tira (`app.mcp.catalogo.SO_COM_NOME_DO_ALUNO`).
#: A minimização continua: `TETO_DE_CANDIDATOS` aqui e o teto de linhas do MCP.
METADADOS: dict[str, dict] = {
    "buscar_aluno_por_nome": {"expor_no_mcp": True},
    "buscar_aluno_por_matricula": {"expor_no_mcp": True},
    "obter_aluno": {"expor_no_mcp": True},
    "listar_ciclos": {"expor_no_mcp": True},
    "listar_simulados": {"expor_no_mcp": True},
    "obter_simulado": {"expor_no_mcp": True},
    "listar_materias": {"expor_no_mcp": True},
}
