"""Interpreta os nomes das colunas da planilha do Canvas.

O LMS produz nomes ricos em metadados, por exemplo:

    1_P1 - Matemática - 09/02/2025 (4255)
    3_P10 - Física - 12/04/2025 (4573)
    1° CICLO - 1º DIA - Humanas (03/04/2025) (4563)      ← ENEM/SAS, descartado
    1° CICLO - IME Final Score                            ← marcador de vestibular
    1 FASE ITA - MATEMÁTICA - 05/10 (4897)

O processamento é em 3 passadas (orquestradas pelo pipeline):

  1. `detectar_vestibulares_por_ciclo(cabecalho)`
     → varre o cabeçalho atrás de "N° CICLO - VESTIBULAR Final Score"
     → devolve {ordem_ciclo: 'ITA' | 'IME'}

  2. `parsear_coluna(indice, nome, ano_fallback)` em cada coluna
     → identifica se é identificação / section / simulado / ignorada

  3. `inferir_fase_simulados(colunas)`
     → agrupa simulados por (ciclo_ordem, rotulo_curto) e marca fase_1/fase_2
     conforme a regra "2+ matérias core compartilham Pn = Fase 1".
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal


# ─── Tipos públicos ───────────────────────────────────────────────────────


TipoColuna = Literal[
    "identificacao",   # Student, ID, SIS User ID, SIS Login ID
    "section",         # Section
    "simulado",        # coluna de prova individual
    "ignorada",        # Current Score, Final Points, macros ENEM, SAS, etc.
]


@dataclass(frozen=True)
class ColunaIdentificacao:
    tipo: Literal["identificacao", "section"]
    indice: int
    campo: Literal["nome", "id", "sis_user_id", "sis_login_id", "section"]


@dataclass
class ColunaSimulado:
    """Mutável por causa da fase, que é definida só na 3ª passada."""
    tipo: Literal["simulado"] = "simulado"
    indice: int = 0
    nome_original: str = ""
    rotulo_curto: str | None = None        # "P1", "P22"
    materia_codigo: str | None = None       # matematica, fisica, ...
    data_aplicacao: date | None = None
    external_id: str = ""
    ciclo_ordem: int | None = None
    fase: Literal["fase_1", "fase_2"] | None = None


@dataclass(frozen=True)
class ColunaIgnorada:
    tipo: Literal["ignorada"] = "ignorada"
    indice: int = 0
    nome_original: str = ""
    motivo: str = ""


Coluna = ColunaIdentificacao | ColunaSimulado | ColunaIgnorada


# ─── Padrões de reconhecimento ────────────────────────────────────────────


# Mapeamento de matéria normalizada (sem acentos, lowercase) → código canônico.
MATERIAS_CANONICAS: dict[str, str] = {
    "matematica": "matematica",
    "fisica":     "fisica",
    "quimica":    "quimica",
    "portugues":  "portugues",
    "ingles":     "ingles",
    "redacao":    "redacao",
}

# Matérias "core" — sua presença/agrupamento determina Fase 1 vs Fase 2.
MATERIAS_CORE: frozenset[str] = frozenset({"matematica", "fisica", "quimica"})


# Coluna de prova individual:
#   "1_P1 - Matemática - 09/02/2025 (4255)"
#   "3_P10 - Física - 12/04/2025 (4573)"
PADRAO_SIMULADO = re.compile(
    r"""
    ^
    (?P<ciclo_ordem>\d+)_
    (?P<rotulo_curto>P\d+)\s*-\s*
    (?P<materia>[^-]+?)\s*-\s*
    (?P<data>\d{2}/\d{2}/\d{4})
    \s*\(\s*(?P<external_id>\d+)\s*\)
    \s*$
    """,
    re.VERBOSE,
)


# Macro-ciclo estilo ENEM (Humanas, Linguagens e Códigos, Ciências da Natureza
# e suas Tecnologias, Matemática e suas Tecnologias). Sempre descartado.
PADRAO_MACROCICLO_ENEM = re.compile(
    r"""
    ^
    (?P<ciclo_ordem>\d+)[°º]\s+CICLO
    .*?
    \((?P<data>\d{2}/\d{2}/\d{4})\)
    \s*
    \(\s*(?P<external_id>\d+)\s*\)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)


# Identificadores de vestibular dentro do nome da coluna (placar consolidado):
#   "1° CICLO - IME Current Points"
#   "2° CICLO - ITA Final Score"
#   "1° CICLO - SAS Unposted Current Score"
PADRAO_CICLO_VESTIBULAR = re.compile(
    r"^(?P<ordem>\d+)[°º]\s+CICLO\s*-\s*(?P<vest>ITA|IME|SAS|AFA|EsPCEx|EFOMM|ENEM)\b",
    re.IGNORECASE,
)


# Padrões a descartar (calculamos nosso próprio agregado).
PADROES_IGNORADOS: tuple[re.Pattern[str], ...] = (
    re.compile(r"current\s+points",        re.IGNORECASE),
    re.compile(r"final\s+points",          re.IGNORECASE),
    re.compile(r"current\s+score",         re.IGNORECASE),
    re.compile(r"unposted\s+current",      re.IGNORECASE),
    re.compile(r"unposted\s+final",        re.IGNORECASE),
    re.compile(r"final\s+score",           re.IGNORECASE),
    re.compile(r"imported\s+assignments",  re.IGNORECASE),
    re.compile(r"^ambienta",               re.IGNORECASE),  # provas de treino
    # Colunas órfãs "1 FASE ITA - MATÉRIA - dd/mm (id)" e seu placar consolidado
    # "1º FASE ITA - 2025 …" são descartadas inteiras (decisão do usuário 2026-05-25).
    re.compile(r"^\s*1[º°]?\s*FASE\s+ITA\b",  re.IGNORECASE),
)


# ─── Helpers básicos ──────────────────────────────────────────────────────


def remover_acentos(s: str) -> str:
    """Normaliza string para comparação (remove acentos, lowercase, strip)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    ).lower().strip()


def codigo_materia(nome: str) -> str | None:
    """'Matemática' / 'matematica' / ' MATEMÁTICA ' → 'matematica'."""
    chave = remover_acentos(nome)
    return MATERIAS_CANONICAS.get(chave)


def parse_data_br(s: str, ano_fallback: int | None = None) -> date | None:
    """Aceita 'dd/mm/aaaa' e 'dd/mm' (usa ano_fallback nesse caso)."""
    s = s.strip()
    try:
        if len(s) == 5:  # dd/mm
            if ano_fallback is None:
                return None
            return datetime.strptime(f"{s}/{ano_fallback}", "%d/%m/%Y").date()
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None


# ─── Passada 1: detectar vestibular-alvo por ciclo ────────────────────────


def detectar_vestibulares_por_ciclo(cabecalho: list[str]) -> dict[int, str]:
    """Varre o cabeçalho atrás de marcadores de vestibular e devolve
    {ordem_ciclo: 'ITA' | 'IME'}.

    Quando um mesmo ciclo aparece com mais de um vestibular nas colunas
    read-only (ex.: ciclo 1 tem "IME Final" E "SAS Final"), prioriza ITA > IME
    sobre os demais. Ciclos cujo único marcador é SAS/ENEM/AFA/etc. ficam
    **fora** do mapa — o pipeline descarta esses ciclos por completo.
    """
    encontrados: dict[int, set[str]] = defaultdict(set)
    for nome in cabecalho:
        m = PADRAO_CICLO_VESTIBULAR.match(nome.strip())
        if m:
            encontrados[int(m.group("ordem"))].add(m.group("vest").upper())

    resultado: dict[int, str] = {}
    for ordem, vestibulares in encontrados.items():
        if "ITA" in vestibulares:
            resultado[ordem] = "ITA"
        elif "IME" in vestibulares:
            resultado[ordem] = "IME"
        # SAS, ENEM, AFA, EsPCEx, EFOMM → omitidos → ciclo descartado
    return resultado


# ─── Passada 2: parsear cada coluna individualmente ───────────────────────


def parsear_coluna(indice: int, nome: str, ano_fallback: int | None = None) -> Coluna:
    """Classifica uma coluna do header e extrai metadados quando aplicável.

    `ano_fallback` é usado para colunas que trazem só dd/mm (1ª Fase ITA).
    """
    nome_limpo = nome.strip()
    nome_normalizado = remover_acentos(nome_limpo)

    # ── colunas de identificação fixas ──
    if nome_normalizado == "student":
        return ColunaIdentificacao(tipo="identificacao", indice=indice, campo="nome")
    if nome_normalizado == "id":
        return ColunaIdentificacao(tipo="identificacao", indice=indice, campo="id")
    if nome_normalizado == "sis user id":
        return ColunaIdentificacao(tipo="identificacao", indice=indice, campo="sis_user_id")
    if nome_normalizado == "sis login id":
        return ColunaIdentificacao(tipo="identificacao", indice=indice, campo="sis_login_id")
    if nome_normalizado == "section":
        return ColunaIdentificacao(tipo="section", indice=indice, campo="section")

    # ── descartes conhecidos (placares consolidados, ambientação) ──
    for padrao in PADROES_IGNORADOS:
        if padrao.search(nome_limpo):
            return ColunaIgnorada(
                indice=indice,
                nome_original=nome_limpo,
                motivo="placar/agregado do LMS — recalculamos do zero",
            )

    # ── macro-ciclo ENEM/SAS — sempre descartar ──
    if PADRAO_MACROCICLO_ENEM.match(nome_limpo):
        return ColunaIgnorada(
            indice=indice,
            nome_original=nome_limpo,
            motivo="prova ENEM/SAS — fora do escopo (somente ITA/IME)",
        )

    # ── colunas de prova individual (formato dominante) ──
    m = PADRAO_SIMULADO.match(nome_limpo)
    if m:
        return ColunaSimulado(
            indice=indice,
            nome_original=nome_limpo,
            rotulo_curto=m.group("rotulo_curto"),
            materia_codigo=codigo_materia(m.group("materia")),
            data_aplicacao=parse_data_br(m.group("data")),
            external_id=m.group("external_id"),
            ciclo_ordem=int(m.group("ciclo_ordem")),
            fase=None,               # preenchido na passada 3
        )

    return ColunaIgnorada(
        indice=indice,
        nome_original=nome_limpo,
        motivo="formato não reconhecido",
    )


# ─── Passada 3: inferir fase de cada simulado por agrupamento Pn ──────────


def inferir_fase_simulados(colunas: list[Coluna]) -> None:
    """Agrupa simulados por (ciclo, Pn) e marca cada um como fase_1 ou fase_2.

    Regra:
      - se o grupo tem 2+ matérias core (Mat/Fis/Quim) → fase_1 (prova combinada)
      - caso contrário → fase_2 (matéria individual ou bloco de linguagem)

    Aplica-se apenas aos simulados que ainda não têm fase definida (os de
    1ª Fase ITA já chegam marcados na passada 2).
    """
    grupos: dict[tuple[int | None, str | None], list[ColunaSimulado]] = defaultdict(list)
    for col in colunas:
        if isinstance(col, ColunaSimulado) and col.fase is None:
            grupos[(col.ciclo_ordem, col.rotulo_curto)].append(col)

    for cols in grupos.values():
        materias_core = {c.materia_codigo for c in cols if c.materia_codigo in MATERIAS_CORE}
        fase_decidida: Literal["fase_1", "fase_2"] = (
            "fase_1" if len(materias_core) >= 2 else "fase_2"
        )
        for c in cols:
            c.fase = fase_decidida


# ─── Section → (série, trilha, sede) ──────────────────────────────────────


@dataclass(frozen=True)
class SectionParsed:
    serie: int | None
    trilha: str | None
    sede_codigo: str
    modalidade: Literal["presencial", "online"]


PADRAO_SECTION = re.compile(r"^(?P<serie>\d+)o\s+(?P<trilha>\w+)\s+(?P<sede>\w+)$", re.IGNORECASE)


def parsear_section(section: str) -> SectionParsed:
    """Decompõe '3o ITA AD' em (3, 'ITA', 'AD', 'presencial').

    Casos especiais:
      - 'Online' → sede_codigo='ONLINE', modalidade='online'.
      - Qualquer outra string fora do padrão cai como sede de código igual ao
        próprio Section (uppercase) e modalidade presencial.
    """
    valor = section.strip()
    if remover_acentos(valor) == "online":
        return SectionParsed(serie=None, trilha=None, sede_codigo="ONLINE", modalidade="online")

    m = PADRAO_SECTION.match(valor)
    if m:
        return SectionParsed(
            serie=int(m.group("serie")),
            trilha=m.group("trilha").upper(),
            sede_codigo=m.group("sede").upper(),
            modalidade="presencial",
        )

    return SectionParsed(
        serie=None,
        trilha=None,
        sede_codigo=valor.upper().replace(" ", "_"),
        modalidade="presencial",
    )
