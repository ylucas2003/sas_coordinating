"""Upserts idempotentes nas tabelas de domínio.

Cada função recebe o cliente do Supabase e devolve o `id` (uuid string) do
registro inserido/atualizado. Usamos chaves naturais nos `on_conflict`
para que reupload da mesma planilha não duplique nada:

  - sede               → codigo
  - ano_letivo         → ano
  - turma              → (sede_id, ano_letivo_id, serie, trilha)
  - materia            → codigo
  - aluno              → matricula
  - ciclo              → (ano_letivo_id, ordem)
  - simulado           → external_id
  - nota               → (aluno_id, simulado_id)
  - matricula_turma    → (aluno_id, turma_id, ativo_desde)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from supabase import Client


# ─── Helpers ──────────────────────────────────────────────────────────────


def _executar_upsert(
    cliente: Client,
    tabela: str,
    valores: dict[str, Any],
    on_conflict: str,
) -> dict[str, Any]:
    """Executa um upsert e retorna a primeira linha do resultado.

    `on_conflict` é uma string com colunas separadas por vírgula, no formato
    aceito pelo PostgREST (ex.: 'sede_id,ano_letivo_id,serie,trilha').
    """
    resposta = (
        cliente.table(tabela)
        .upsert(valores, on_conflict=on_conflict, returning="representation")
        .execute()
    )
    if not resposta.data:
        raise RuntimeError(f"Upsert em '{tabela}' não retornou dados. Valores: {valores!r}")
    return resposta.data[0]


def _isoformat(d: date | None) -> str | None:
    return d.isoformat() if d else None


# ─── Sede ─────────────────────────────────────────────────────────────────


def upsert_sede(
    cliente: Client,
    *,
    codigo: str,
    modalidade: str,
    nome: str | None = None,
) -> str:
    """Cria ou atualiza uma sede a partir do código (ex.: 'AD', 'MF', 'ONLINE')."""
    valores = {
        "codigo": codigo,
        "nome": nome or codigo,           # placeholder amigável até a coord. editar
        "modalidade": modalidade,
    }
    linha = _executar_upsert(cliente, "sede", valores, on_conflict="codigo")
    return linha["id"]


# ─── Ano letivo ───────────────────────────────────────────────────────────


def upsert_ano_letivo(cliente: Client, *, ano: int) -> str:
    linha = _executar_upsert(cliente, "ano_letivo", {"ano": ano}, on_conflict="ano")
    return linha["id"]


# ─── Turma ────────────────────────────────────────────────────────────────


def upsert_turma(
    cliente: Client,
    *,
    sede_id: str,
    ano_letivo_id: str,
    serie: int,
    trilha: str,
    section_original: str,
) -> str:
    valores = {
        "sede_id": sede_id,
        "ano_letivo_id": ano_letivo_id,
        "serie": serie,
        "trilha": trilha,
        "section_original": section_original,
    }
    linha = _executar_upsert(
        cliente,
        "turma",
        valores,
        on_conflict="sede_id,ano_letivo_id,serie,trilha",
    )
    return linha["id"]


# ─── Matéria ──────────────────────────────────────────────────────────────


def buscar_materia_por_codigo(cliente: Client, codigo: str) -> str | None:
    resposta = cliente.table("materia").select("id").eq("codigo", codigo).limit(1).execute()
    return resposta.data[0]["id"] if resposta.data else None


# ─── Aluno ────────────────────────────────────────────────────────────────


def upsert_aluno(cliente: Client, *, matricula: str, nome: str) -> str:
    valores = {
        "matricula": matricula,
        "nome": nome,
        "ativo": True,
    }
    linha = _executar_upsert(cliente, "aluno", valores, on_conflict="matricula")
    return linha["id"]


def upsert_alunos_em_lote(
    cliente: Client,
    *,
    alunos: list[dict[str, Any]],
    tamanho_lote: int = 500,
) -> dict[str, str]:
    """Upsert em lote de alunos. Devolve {matricula: aluno_id}.

    Espera dicts com `matricula`, `nome`, `ativo`. Usa `returning=representation`
    pra recuperar o id de cada linha (necessário pra montar matricula_turma e
    notas depois). Cada lote vira UMA requisição HTTP — muito mais barato que
    818 requisições sequenciais.
    """
    if not alunos:
        return {}

    matricula_para_id: dict[str, str] = {}
    for inicio in range(0, len(alunos), tamanho_lote):
        lote = alunos[inicio : inicio + tamanho_lote]
        resposta = (
            cliente.table("aluno")
            .upsert(lote, on_conflict="matricula", returning="representation")
            .execute()
        )
        for linha in resposta.data or []:
            matricula_para_id[linha["matricula"]] = linha["id"]
    return matricula_para_id


def upsert_matricula_turma(
    cliente: Client,
    *,
    aluno_id: str,
    turma_id: str,
    ativo_desde: date,
) -> None:
    valores = {
        "aluno_id": aluno_id,
        "turma_id": turma_id,
        "ativo_desde": _isoformat(ativo_desde),
    }
    _executar_upsert(
        cliente,
        "matricula_turma",
        valores,
        on_conflict="aluno_id,turma_id,ativo_desde",
    )


def upsert_matriculas_em_lote(
    cliente: Client,
    *,
    matriculas: list[dict[str, Any]],
    tamanho_lote: int = 500,
) -> int:
    """Upsert em lote para matricula_turma. Espera dicts com aluno_id,
    turma_id, ativo_desde (date ou string ISO). Devolve total processado."""
    if not matriculas:
        return 0

    # Normaliza datas pra ISO
    normalizadas: list[dict[str, Any]] = []
    for m in matriculas:
        m2 = dict(m)
        ativo_desde = m2.get("ativo_desde")
        if isinstance(ativo_desde, date):
            m2["ativo_desde"] = ativo_desde.isoformat()
        normalizadas.append(m2)

    total = 0
    for inicio in range(0, len(normalizadas), tamanho_lote):
        lote = normalizadas[inicio : inicio + tamanho_lote]
        cliente.table("matricula_turma").upsert(
            lote,
            on_conflict="aluno_id,turma_id,ativo_desde",
            returning="minimal",
        ).execute()
        total += len(lote)
    return total


# ─── Ciclo ────────────────────────────────────────────────────────────────


def upsert_ciclo(
    cliente: Client,
    *,
    ano_letivo_id: str,
    ordem: int,
    nome: str,
    vestibular_alvo: str | None = None,
) -> str:
    valores = {
        "ano_letivo_id": ano_letivo_id,
        "ordem": ordem,
        "nome": nome,
        "vestibular_alvo": vestibular_alvo,
    }
    linha = _executar_upsert(
        cliente,
        "ciclo",
        valores,
        on_conflict="ano_letivo_id,ordem",
    )
    return linha["id"]


def atualizar_periodo_ciclo(
    cliente: Client,
    *,
    ciclo_id: str,
    periodo_inicio: date,
    periodo_fim: date,
) -> None:
    """Atualiza o min/max das datas de aplicação dos simulados do ciclo."""
    cliente.table("ciclo").update(
        {
            "periodo_inicio": _isoformat(periodo_inicio),
            "periodo_fim": _isoformat(periodo_fim),
        }
    ).eq("id", ciclo_id).execute()


# ─── Simulado ─────────────────────────────────────────────────────────────


def upsert_simulado(
    cliente: Client,
    *,
    external_id: str,
    ciclo_id: str,
    materia_id: str | None,
    nome: str,
    rotulo_curto: str | None,
    data_aplicacao: date,
    nota_maxima: float,
    e_agregado: bool,
    tipo: str | None = None,
) -> str:
    valores = {
        "external_id": external_id,
        "ciclo_id": ciclo_id,
        "materia_id": materia_id,
        "nome": nome,
        "rotulo_curto": rotulo_curto,
        "data_aplicacao": _isoformat(data_aplicacao),
        "nota_maxima": nota_maxima,
        "e_agregado": e_agregado,
        "tipo": tipo,
    }
    linha = _executar_upsert(cliente, "simulado", valores, on_conflict="external_id")
    return linha["id"]


def upsert_simulados_em_lote(
    cliente: Client,
    *,
    simulados: list[dict[str, Any]],
    tamanho_lote: int = 200,
) -> dict[str, str]:
    """Upsert em lote de simulados. Devolve {external_id: simulado_id}.

    Espera dicts já formatados (com data_aplicacao em string ISO). Cada lote
    vira UMA requisição HTTP — bem mais barato que N requisições sequenciais.
    """
    if not simulados:
        return {}

    external_para_id: dict[str, str] = {}
    for inicio in range(0, len(simulados), tamanho_lote):
        lote = simulados[inicio : inicio + tamanho_lote]
        resposta = (
            cliente.table("simulado")
            .upsert(lote, on_conflict="external_id", returning="representation")
            .execute()
        )
        for linha in resposta.data or []:
            external_para_id[linha["external_id"]] = linha["id"]
    return external_para_id


# ─── Nota ─────────────────────────────────────────────────────────────────


def upsert_notas_em_lote(
    cliente: Client,
    *,
    notas: list[dict[str, Any]],
) -> int:
    """Upsert em lote para `nota`. Espera dicts com aluno_id, simulado_id, pontuacao, presente.

    Retorna o número de linhas afetadas. Usa lotes de 500 para evitar payloads
    gigantes no PostgREST.
    """
    if not notas:
        return 0

    total = 0
    TAMANHO_LOTE = 500
    for inicio in range(0, len(notas), TAMANHO_LOTE):
        lote = notas[inicio : inicio + TAMANHO_LOTE]
        resposta = (
            cliente.table("nota")
            .upsert(lote, on_conflict="aluno_id,simulado_id", returning="minimal")
            .execute()
        )
        # supabase-py v2 não devolve count com returning=minimal; consideramos
        # como sucesso pelo lote enviado.
        _ = resposta
        total += len(lote)
    return total


# ─── Questões de quiz (Canvas — Fase 2 do sync) ───────────────────────────


def upsert_questoes_em_lote(
    cliente: Client,
    *,
    questoes: list[dict[str, Any]],
) -> dict[str, str]:
    """Upsert em lote de `questao`. Devolve {canvas_question_id: questao_id}.

    Espera dicts com simulado_id, canvas_question_id, posicao, texto, pontos.
    Nunca envia `assunto` — a classificação futura não pode ser sobrescrita
    pelo sync.
    """
    if not questoes:
        return {}

    canvas_para_id: dict[str, str] = {}
    TAMANHO_LOTE = 200
    for inicio in range(0, len(questoes), TAMANHO_LOTE):
        lote = questoes[inicio : inicio + TAMANHO_LOTE]
        resposta = (
            cliente.table("questao")
            .upsert(lote, on_conflict="simulado_id,canvas_question_id", returning="representation")
            .execute()
        )
        for linha in resposta.data or []:
            canvas_para_id[linha["canvas_question_id"]] = linha["id"]
    return canvas_para_id


def upsert_alternativas_em_lote(
    cliente: Client,
    *,
    alternativas: list[dict[str, Any]],
) -> dict[tuple[str, str], str]:
    """Upsert em lote de `questao_alternativa`.

    Devolve {(questao_id, canvas_answer_id): alternativa_id}. Espera dicts com
    questao_id, canvas_answer_id, texto, correta.
    """
    if not alternativas:
        return {}

    chave_para_id: dict[tuple[str, str], str] = {}
    TAMANHO_LOTE = 500
    for inicio in range(0, len(alternativas), TAMANHO_LOTE):
        lote = alternativas[inicio : inicio + TAMANHO_LOTE]
        resposta = (
            cliente.table("questao_alternativa")
            .upsert(lote, on_conflict="questao_id,canvas_answer_id", returning="representation")
            .execute()
        )
        for linha in resposta.data or []:
            chave_para_id[(linha["questao_id"], linha["canvas_answer_id"])] = linha["id"]
    return chave_para_id


def upsert_respostas_questao_em_lote(
    cliente: Client,
    *,
    respostas: list[dict[str, Any]],
) -> int:
    """Upsert em lote de `questao_resposta_aluno` (PK aluno_id+questao_id).

    Espera dicts com aluno_id, questao_id, alternativa_id (ou None) e correta.
    Retorna o número de linhas enviadas.
    """
    if not respostas:
        return 0

    total = 0
    TAMANHO_LOTE = 500
    for inicio in range(0, len(respostas), TAMANHO_LOTE):
        lote = respostas[inicio : inicio + TAMANHO_LOTE]
        (
            cliente.table("questao_resposta_aluno")
            .upsert(lote, on_conflict="aluno_id,questao_id", returning="minimal")
            .execute()
        )
        total += len(lote)
    return total


# ─── Upload (auditoria) ───────────────────────────────────────────────────


def criar_upload(
    cliente: Client,
    *,
    arquivo_origem: str,
    caminho_storage: str | None,
    autor: str | None,
) -> str:
    valores = {
        "arquivo_origem": arquivo_origem,
        "caminho_storage": caminho_storage,
        "autor": autor,
        "status": "processando",
    }
    resposta = cliente.table("upload").insert(valores).execute()
    return resposta.data[0]["id"]


def finalizar_upload(
    cliente: Client,
    *,
    upload_id: str,
    status: str,
    resumo: dict[str, Any] | None = None,
    erro_mensagem: str | None = None,
    linhas_total: int | None = None,
    linhas_aceitas: int | None = None,
    linhas_rejeitadas: int | None = None,
) -> None:
    cliente.table("upload").update(
        {
            "status": status,
            "resumo": resumo,
            "erro_mensagem": erro_mensagem,
            "linhas_total": linhas_total,
            "linhas_aceitas": linhas_aceitas,
            "linhas_rejeitadas": linhas_rejeitadas,
            "finalizado_em": "now()",
        }
    ).eq("id", upload_id).execute()


def registrar_evento(
    cliente: Client,
    *,
    upload_id: str,
    nivel: str,
    mensagem: str,
    linha_planilha: int | None = None,
    coluna_planilha: str | None = None,
) -> None:
    cliente.table("upload_evento").insert(
        {
            "upload_id": upload_id,
            "nivel": nivel,
            "mensagem": mensagem,
            "linha_planilha": linha_planilha,
            "coluna_planilha": coluna_planilha,
        }
    ).execute()


# ─── Sincronização Canvas (auditoria) ─────────────────────────────────────


def criar_execucao_sync(cliente: Client, *, tipo: str) -> str:
    """Abre uma linha em canvas_sync_execucao (tipo: 'backfill' | 'incremental')."""
    resposta = (
        cliente.table("canvas_sync_execucao")
        .insert({"tipo": tipo, "status": "processando"})
        .execute()
    )
    return resposta.data[0]["id"]


def finalizar_execucao_sync(
    cliente: Client,
    *,
    execucao_id: str,
    status: str,
    resumo: dict[str, Any] | None = None,
    erro_mensagem: str | None = None,
) -> None:
    cliente.table("canvas_sync_execucao").update(
        {
            "status": status,
            "resumo": resumo,
            "erro_mensagem": erro_mensagem,
            "finalizado_em": "now()",
        }
    ).eq("id", execucao_id).execute()
