"""Funções puras: objetos JSON do Canvas → dicts prontos pros upserts.

Sem I/O aqui — só parsing e mapeamento de campos. Reaproveita de
ingest/header.py tudo que é regra de domínio (matérias canônicas, gramática
de ciclo/vestibular, decomposição de Section, inferência de fase); o que é
novo é só a gramática do NOME do Assignment, que difere da planilha:

    planilha:  "1_P1 - Matemática - 09/02/2025 (4255)"   ← external_id no nome
    Canvas:    "1_P1 - Matemática - 08/02/2026"           ← id vem do próprio objeto
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from ..ingest.header import (
    PADRAO_CICLO_VESTIBULAR,
    codigo_materia,
    parse_data_br,
)

# "1_P1 - Matemática - 08/02/2026" (sem "(id)" no fim — vem de assignment["id"]).
PADRAO_ASSIGNMENT_SIMULADO = re.compile(
    r"""
    ^
    (?P<ciclo_ordem>\d+)_
    (?P<rotulo_curto>P\d+)\s*-\s*
    (?P<materia>[^-]+?)\s*-\s*
    (?P<data>\d{2}/\d{2}/\d{4})
    \s*$
    """,
    re.VERBOSE,
)

# "2026 3o ITA/IME Simulados" → ano 2026. O curso legado sem prefixo de ano
# ("3o ITA/IME SIMULADOS") não casa — decisão: só sincronizamos cursos com ano.
PADRAO_CURSO_SIMULADOS = re.compile(
    r"^(?P<ano>\d{4})\s+\d+o\s+ITA/IME\s+Simulados\s*$",
    re.IGNORECASE,
)


# ─── Parsing de nomes ─────────────────────────────────────────────────────


def parsear_ano_curso_simulados(nome_curso: str) -> int | None:
    m = PADRAO_CURSO_SIMULADOS.match(nome_curso.strip())
    return int(m.group("ano")) if m else None


def parsear_grupo_ciclo(nome_grupo: str) -> tuple[int, str] | None:
    """'1° CICLO - ITA' → (1, 'ITA'). None para tudo que não é ciclo ITA/IME
    ('1° CICLO - SAS' = macro-ciclo ENEM, 'Imported Assignments', etc.)."""
    m = PADRAO_CICLO_VESTIBULAR.match(nome_grupo.strip())
    if not m:
        return None
    vestibular = m.group("vest").upper()
    if vestibular not in ("ITA", "IME"):
        return None
    return int(m.group("ordem")), vestibular


def parsear_nome_assignment(nome: str) -> dict[str, Any] | None:
    """Extrai (rotulo_curto, materia_codigo, data) de '1_P1 - Matemática - 08/02/2026'.

    None para nomes fora da gramática (macro-ciclo ENEM, AMBIENTAÇÃO, etc.) —
    o chamador decide se registra aviso.
    """
    m = PADRAO_ASSIGNMENT_SIMULADO.match(nome.strip())
    if not m:
        return None
    return {
        "rotulo_curto": m.group("rotulo_curto"),
        "materia_codigo": codigo_materia(m.group("materia")),
        "data_aplicacao": parse_data_br(m.group("data")),
    }


# ─── Helpers de data ──────────────────────────────────────────────────────


def _data_do_iso(iso: str | None) -> date | None:
    if not iso:
        return None
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).date()


# ─── Mapeamento de entidades ──────────────────────────────────────────────


def mapear_aluno(usuario: dict[str, Any]) -> dict[str, Any] | None:
    """`usuario` = enrollment["user"]. None se não tiver SIS User ID (contas de
    teste/professor coladas em section de aluno não entram no SAS)."""
    sis = usuario.get("sis_user_id")
    if not sis:
        return None
    return {
        "matricula": str(sis),
        "nome": usuario.get("name") or str(sis),
        "ativo": True,
        "avatar_url": usuario.get("avatar_url"),
        "canvas_user_id": str(usuario["id"]),
        "canvas_criado_em": usuario.get("created_at"),
    }


def mapear_matricula(
    enrollment: dict[str, Any], *, aluno_id: str, turma_id: str
) -> dict[str, Any]:
    ativo_desde = _data_do_iso(enrollment.get("created_at")) or date.today()
    return {
        "aluno_id": aluno_id,
        "turma_id": turma_id,
        "ativo_desde": ativo_desde.isoformat(),
        "canvas_enrollment_id": str(enrollment["id"]),
        "canvas_section_id": str(enrollment["course_section_id"]),
        "enrollment_state": enrollment.get("enrollment_state"),
        "last_activity_at": enrollment.get("last_activity_at"),
        "last_attended_at": enrollment.get("last_attended_at"),
    }


def mapear_simulado(
    assignment: dict[str, Any],
    *,
    ciclo_id: str,
    materia_id: str | None,
    rotulo_curto: str | None,
    data_aplicacao: date,
    tipo: str | None,
) -> dict[str, Any]:
    return {
        "external_id": str(assignment["id"]),
        "ciclo_id": ciclo_id,
        "materia_id": materia_id,
        "nome": assignment["name"].strip(),
        "rotulo_curto": rotulo_curto,
        "data_aplicacao": data_aplicacao.isoformat(),
        "nota_maxima": float(assignment.get("points_possible") or 0.0),
        "e_agregado": False,
        "tipo": tipo,
        "quiz_id": str(assignment["quiz_id"]) if assignment.get("quiz_id") else None,
        "unlock_at": assignment.get("unlock_at"),
        "lock_at": assignment.get("lock_at"),
    }


def derivar_presente(submission: dict[str, Any]) -> bool:
    """Ausência real vem nativa do Canvas — sem heurística de zero.

    presente = não faltou (missing), não foi dispensado (excused) e a
    submission saiu do estado 'unsubmitted'.
    """
    if submission.get("missing") or submission.get("excused"):
        return False
    return submission.get("workflow_state") != "unsubmitted"


def mapear_nota(
    submission: dict[str, Any], *, aluno_id: str, simulado_id: str
) -> dict[str, Any]:
    presente = derivar_presente(submission)
    pontuacao = submission.get("score") if presente else None
    return {
        "aluno_id": aluno_id,
        "simulado_id": simulado_id,
        "pontuacao": pontuacao,
        "presente": presente,
        "late": bool(submission.get("late") or False),
        "graded_em": submission.get("graded_at"),
        "grader_canvas_user_id": (
            str(submission["grader_id"]) if submission.get("grader_id") else None
        ),
        "canvas_missing": submission.get("missing"),
        "canvas_excused": submission.get("excused"),
        "canvas_workflow_state": submission.get("workflow_state"),
    }


def extrair_email(canais: list[dict[str, Any]]) -> str | None:
    """Primeiro canal de email ativo do Communication Channels."""
    for canal in canais:
        if canal.get("type") == "email" and canal.get("workflow_state") == "active":
            return canal.get("address")
    return None
