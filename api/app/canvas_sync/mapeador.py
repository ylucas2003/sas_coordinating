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
    remover_acentos,
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
# O "3o" é literal de propósito: o sync pega o curso de MAIOR ano, e o desempate
# entre cursos do mesmo ano é a ordem em que o Canvas os lista. Um "2027 2o ITA/IME
# Simulados" poderia tomar o lugar do curso do 3º sem erro nenhum (docs/44 §5).
PADRAO_CURSO_SIMULADOS = re.compile(
    r"^(?P<ano>\d{4})\s+3o\s+ITA/IME\s+Simulados\s*$",
    re.IGNORECASE,
)

# "2026 1o ITA/IME Avaliações" → (2026, 1). O curso de provas do 1º e do 2º ano
# (docs/44 §2). O 3º tem outro nome, e por isso o padrão aceita só 1 e 2.
PADRAO_CURSO_AVALIACOES = re.compile(
    r"^(?P<ano>\d{4})\s+(?P<serie>[12])o\s+ITA/IME\s+Avalia[cç][oõ]es\s*$",
    re.IGNORECASE,
)

# "2026 - 1ª ETAPA - AP's" → (2026, 1, "AP"), lido do nome SEM acento e em
# minúsculas: "º" vira "o" e "ª" vira "a" ao tirar o acento, e o Canvas tem os
# dois ("3ª ETAPA" e "3º ETAPA" no mesmo curso).
PADRAO_GRUPO_ETAPA = re.compile(
    r"^(?P<ano>\d{4})\s*-\s*(?P<etapa>[1-3])\s*[ao°]?\s*etapa\s*-\s*(?P<tipo>ap|ag)\b"
)

# "1_AP1 - Matemática - 09/02/2026", também sem acento e em minúsculas. Tolera o
# que o Canvas tem de verdade: "1_ AP2" e "Inglês- 12/03". Qualquer coisa depois
# da data recusa o nome, e é assim que a Atividade de Resolução fica de fora.
PADRAO_PROVA_ETAPA = re.compile(
    r"^(?P<etapa>[1-3])_\s*(?P<tipo>ap|ag)(?P<numero>\d+)\s*-\s*(?P<materia>[a-z ]+?)"
    r"\s*-\s*(?P<data>\d{2}/\d{2}/\d{4})\s*$"
)

# "course files/1° CICLO" → 1 (só o ÚLTIMO segmento do full_name importa —
# subpastas de ano antigo tipo "1° CICLO/2025" têm último segmento "2025",
# que não bate aqui, e ficam de fora sem lógica extra).
PADRAO_PASTA_CICLO = re.compile(r"^(?P<ciclo>\d+)\s*[°ºo]\s*CICLO$", re.IGNORECASE)

# "1472-26 - P2 - MATEMÁTICA (1º CICLO) - 3ª SÉRIE - ..." → P2 + "MATEMÁTICA".
# Não tenta capturar o ciclo daqui (o parênteses às vezes traz outra coisa,
# ex. "QUÍMICA  (2ª FASE)" — o ciclo vem de fora, da pasta onde o arquivo está).
PADRAO_ARQUIVO_SIMULADO = re.compile(
    r"""
    ^
    (?:\d+-\d+\s*-\s*)?           # código sequencial opcional: "1472-26 - "
    P(?P<numero>\d+)\s*-\s*
    (?P<materias>.+?)
    \s*\(                          # para na primeira abertura de parênteses
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Separa "MATEMÁTICA, FÍSICA E QUÍMICA" em tokens — cadernos combinados de
# ciclo cedo têm mais de uma matéria no mesmo arquivo.
_PADRAO_SEPARADOR_MATERIAS = re.compile(r"\s*,\s*|\s+[Ee]\s+")


# ─── Parsing de nomes ─────────────────────────────────────────────────────


def parsear_ano_curso_simulados(nome_curso: str) -> int | None:
    m = PADRAO_CURSO_SIMULADOS.match(nome_curso.strip())
    return int(m.group("ano")) if m else None


def parsear_curso_avaliacoes(nome_curso: str) -> tuple[int, int] | None:
    """'2026 1o ITA/IME Avaliações' → (2026, 1). None para qualquer outro curso."""
    m = PADRAO_CURSO_AVALIACOES.match(nome_curso.strip())
    return (int(m.group("ano")), int(m.group("serie"))) if m else None


def parsear_grupo_etapa(nome_grupo: str) -> tuple[int, int, str] | None:
    """"2026 - 1ª ETAPA - AP's" → (2026, 1, 'AP').

    None para tudo que não é AP nem AG: ASC, NTD, AR, listas e simulados
    nacionais ficam de fora por decisão da coordenação (docs/44 §1).
    """
    m = PADRAO_GRUPO_ETAPA.match(remover_acentos(nome_grupo))
    if not m:
        return None
    return int(m.group("ano")), int(m.group("etapa")), m.group("tipo").upper()


def ciclo_da_etapa(etapa: int, tipo: str) -> tuple[int, str]:
    """(3, 'AG') → (6, 'ITA'). Cada etapa tem dois ciclos, a AP antes da AG, e a AP
    é no estilo do IME e a AG no do ITA (Manual do Aluno 2026; docs/44 §3). O front
    desfaz a conta em `dominio/blocos.ts::nomeCurtoDoCiclo`."""
    return (etapa - 1) * 2 + (1 if tipo == "AP" else 2), "IME" if tipo == "AP" else "ITA"


def e_atividade_de_resolucao(nome: str) -> bool:
    """A "prova recorrigida" vale 0,5 ponto e não é prova (docs/44 §5). O Canvas
    escreve RESOLUÇÃO e também RESOLÇÃO."""
    return "resol" in remover_acentos(nome)


def parsear_nome_avaliacao(nome: str) -> dict[str, Any] | None:
    """'1_AP1 - Matemática - 09/02/2026' → etapa, tipo, rótulo, matéria e data.

    None para nome fora da gramática; o chamador decide se registra aviso.
    """
    m = PADRAO_PROVA_ETAPA.match(remover_acentos(nome))
    if not m:
        return None
    tipo = m.group("tipo").upper()
    return {
        "etapa": int(m.group("etapa")),
        "tipo": tipo,
        "rotulo_curto": f"{tipo}{int(m.group('numero'))}",
        "materia_codigo": codigo_materia(m.group("materia")),
        "data_aplicacao": parse_data_br(m.group("data")),
    }


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


def parsear_pasta_ciclo(full_name: str) -> int | None:
    """`full_name` de uma pasta do Canvas (`GET /courses/:id/folders`) → ordem
    do ciclo, ou None se não for uma pasta de ciclo (ou for subpasta de ano
    antigo dentro de uma)."""
    ultimo_segmento = full_name.strip().split("/")[-1].strip()
    m = PADRAO_PASTA_CICLO.match(ultimo_segmento)
    return int(m.group("ciclo")) if m else None


def _dividir_materias(bruto: str) -> list[str]:
    return [token.strip() for token in _PADRAO_SEPARADOR_MATERIAS.split(bruto) if token.strip()]


def parsear_nome_arquivo_simulado(nome_arquivo: str) -> dict[str, Any] | None:
    """Extrai (rotulo_curto, materias_codigos) do nome de um Course File de
    prova. None para nomes fora da gramática — o chamador decide se registra
    aviso. Matéria(s) que não mapeiam em `codigo_materia` são descartadas;
    se nenhuma sobrar, o arquivo inteiro é tratado como não reconhecido."""
    m = PADRAO_ARQUIVO_SIMULADO.match(nome_arquivo.strip())
    if not m:
        return None
    materias_codigos = [
        codigo
        for token in _dividir_materias(m.group("materias"))
        if (codigo := codigo_materia(token)) is not None
    ]
    if not materias_codigos:
        return None
    return {
        "rotulo_curto": f"P{m.group('numero')}",
        "materias_codigos": materias_codigos,
    }


# ─── Composição de nomes (P1 — o SAS cria no Canvas) ─────────────────────
#
# Inversos exatos dos parsers acima. O agendamento compõe o nome que o
# próprio sync vai ler de volta — o teste de round-trip em
# tests/test_mapeador_roundtrip.py garante que as duas gramáticas não saem
# de sincronia.


def compor_nome_assignment(
    *,
    ciclo_ordem: int,
    rotulo_curto: str,
    materia_nome: str,
    data_aplicacao: date,
) -> str:
    """(1, 'P2', 'Matemática', 2026-02-08) → '1_P2 - Matemática - 08/02/2026'.

    `materia_nome` deve ser o nome CANÔNICO (materia.nome do banco), não o
    que o usuário digitou — é ele que parsear_nome_assignment reconhece."""
    return (
        f"{ciclo_ordem}_{rotulo_curto} - {materia_nome} - "
        f"{data_aplicacao.strftime('%d/%m/%Y')}"
    )


def compor_nome_grupo_ciclo(*, ordem: int, vestibular: str) -> str:
    """(3, 'ITA') → '3° CICLO - ITA' — o padrão dos Assignment Groups do curso."""
    return f"{ordem}° CICLO - {vestibular.upper()}"


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
    nota_maxima: float | None = None,
) -> dict[str, Any]:
    """`nota_maxima` substitui o `points_possible` do Canvas. Serve à prova
    discursiva do 1º e do 2º ano, lançada com 0 ponto e nota direta de 0 a 10:
    com máximo 0, `nota_real` devolveria None e a prova sumiria (docs/44 §5)."""
    return {
        "external_id": str(assignment["id"]),
        "ciclo_id": ciclo_id,
        "materia_id": materia_id,
        "nome": assignment["name"].strip(),
        "rotulo_curto": rotulo_curto,
        "data_aplicacao": data_aplicacao.isoformat(),
        "nota_maxima": (
            nota_maxima if nota_maxima is not None
            else float(assignment.get("points_possible") or 0.0)
        ),
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
