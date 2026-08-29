"""Compõe o título do vídeo no padrão do canal "Ari Resolve".

    SAS ITA/IME 2026 - Turma 1 e 2 - Prof Renan - Aula 5 (20/08/2026)

O Canvas não tem padrão: cada professor nomeia a conferência do seu jeito, e
os três formatos que existem hoje nos cursos monitorados são

    Física - Prof. Renan - AULA 5 - 17:30 (20/08/2026)
    Aula 07 - 24/08/2026 - Trigonometria: Soma de Arcos
    Química - AULA 19 - 26/08/2026 - Prof. José Marques - 17:30

O professor é extraído do título QUANDO EXISTE, e só cai no padrão do curso
quando não existe: Física já teve Renan e Ryan em semanas diferentes, então
tratar o professor como propriedade fixa do curso erraria o nome em metade
das aulas.
"""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

# A data sai do `iniciada_em` (UTC) e não do texto do título: o texto é
# datilografado à mão e já veio errado (uma conferência de 25/06 intitulada
# "AULA 13 - 11/06"). Converter para o fuso do colégio importa — uma aula que
# começa 21h BRT já é o dia seguinte em UTC.
_FUSO_COLEGIO = ZoneInfo("America/Sao_Paulo")

# "Prof. Renan", "Prof José Marques", "profa. Ana Paula". Para no primeiro
# separador para não engolir o resto do título.
_PADRAO_PROFESSOR = re.compile(
    r"prof[a]?\.?\s+([A-ZÀ-Ý][\wÀ-ÿ]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]*)*)",
    re.IGNORECASE,
)
_PADRAO_NUMERO_AULA = re.compile(r"aula\s*0*(\d+)", re.IGNORECASE)

# O curso "SAS Preparatório ITA/IME 2026" (581) já nomeia a conferência no
# padrão do canal — ex.: "SAS ITA/IME 2026 - Turma 1 e 2 - Inglês - Prof
# Daniel Nicolas - 17:30 (28/08/2026)". Recompor a partir dos pedaços daria
# um título com o prefixo duplicado:
#   "SAS ITA/IME 2026 - Turma 1 e 2 - Prof Daniel - SAS ITA/IME 2026 - ... (28/08/2026) (28/08/2026)"
# Nesses casos o título é aproveitado como está; só a data é reescrita.
_PADRAO_JA_NO_CANAL = re.compile(r"^\s*SAS\s+ITA/IME\b", re.IGNORECASE)

# Sufixos datilografados que saem do fim antes de a data real entrar: "(28/08/2026)"
# e o "- 17:30", que é hora de agenda e não faz parte do padrão do canal.
_SUFIXO_DATA = re.compile(r"\s*\(\s*\d{1,2}/\d{1,2}/\d{2,4}\s*\)\s*$")
_SUFIXO_HORA = re.compile(r"\s*[-–]\s*\d{1,2}[:h]\d{2}\s*$")
# Data sem parênteses no fim, como em "RESOLUÇÃO SIMULADO 03 - 20/05/2026".
_DATA_SOLTA_NO_FIM = re.compile(r"\s*[-–]\s*\d{1,2}/\d{1,2}/\d{2,4}\s*$")


def ja_no_padrao_do_canal(titulo_canvas: str) -> bool:
    return bool(_PADRAO_JA_NO_CANAL.match(titulo_canvas))


def _normalizar_titulo_do_canal(titulo_canvas: str, local: datetime) -> str:
    """Reaproveita o título como está, trocando a data do fim pela real.

    A data é reescrita mesmo quando já existe porque o texto é digitado à mão
    e já veio errado na prática — houve conferência de 25/06 intitulada
    "AULA 13 - 11/06"."""
    base = titulo_canvas.strip()
    # Em ordem: primeiro a data entre parênteses, depois a hora que ficava
    # antes dela. Invertida, a hora não estaria no fim e escaparia.
    base = _SUFIXO_DATA.sub("", base)
    base = _SUFIXO_HORA.sub("", base)
    return f"{base.rstrip(' -–')} ({local:%d/%m/%Y})"


def _turma_do_curso(nome_curso: str) -> str:
    """Os cursos "(2º SEMESTRE)" reúnem as duas turmas — é o que o canal
    chama de "Turma 1 e 2"."""
    normalizado = nome_curso.upper()
    if "2º SEMESTRE" in normalizado or "2O SEMESTRE" in normalizado:
        return "Turma 1 e 2"
    if "TURMA 1" in normalizado:
        return "Turma 1"
    if "TURMA 2" in normalizado:
        return "Turma 2"
    return "Turma 1 e 2"


def extrair_professor(titulo_canvas: str) -> str | None:
    m = _PADRAO_PROFESSOR.search(titulo_canvas)
    if not m:
        return None
    # Nomes vêm com ruído colado ("Renan - AULA 5"); o regex já para no
    # separador, mas espaço sobrando ainda passa.
    return " ".join(m.group(1).split()) or None


def extrair_numero_aula(titulo_canvas: str) -> int | None:
    m = _PADRAO_NUMERO_AULA.search(titulo_canvas)
    return int(m.group(1)) if m else None


def compor_titulo(
    *,
    titulo_canvas: str,
    nome_curso: str,
    iniciada_em: datetime,
    professor_padrao: str | None = None,
) -> str:
    """Monta o título no padrão do canal, omitindo o que não der para saber.

    Segmento sem informação some em vez de virar "Prof ?" ou "Aula 0" — um
    título com lacuna honesta é melhor que um com dado inventado.

    É IDEMPOTENTE: aplicar sobre o próprio resultado devolve o mesmo texto.
    Isso importa porque a saída daqui já começa com "SAS ITA/IME", e sem o
    desvio abaixo uma reexecução empilharia prefixo a cada rodada."""
    local = iniciada_em.astimezone(_FUSO_COLEGIO)
    if ja_no_padrao_do_canal(titulo_canvas):
        return _normalizar_titulo_do_canal(titulo_canvas, local)

    professor = extrair_professor(titulo_canvas) or professor_padrao
    numero = extrair_numero_aula(titulo_canvas)

    partes = [f"SAS ITA/IME {local.year}", _turma_do_curso(nome_curso)]
    if professor:
        partes.append(f"Prof {professor}")
    if numero is not None:
        partes.append(f"Aula {numero}")
    else:
        # Sem número (tira-dúvidas, plantão), o assunto da conferência é o
        # que resta para diferenciar um vídeo do outro na listagem do canal.
        # A data/hora datilografada sai daqui: ela reapareceria no fim do
        # título montado, produzindo "... - 20/05/2026 - 08:00 (20/05/2026)".
        assunto = _SUFIXO_DATA.sub("", titulo_canvas.strip())
        assunto = _SUFIXO_HORA.sub("", assunto)
        assunto = _DATA_SOLTA_NO_FIM.sub("", assunto)
        partes.append(assunto.rstrip(" -–") or titulo_canvas.strip())

    return f"{' - '.join(partes)} ({local:%d/%m/%Y})"
