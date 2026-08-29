"""Casa uma aula gravada com a página dela no Canvas, e monta o embed.

Módulo PURO: nenhuma chamada de rede, para que a parte perigosa seja testável
sem tocar num curso de verdade. O I/O vive em canvas_publicacao.py.

Os professores já mantêm, à mão, uma página por aula com um iframe do YouTube
dentro. Isto aqui replica esse padrão — não inventa formato.

A ARMADILHA QUE DEFINE O DESENHO: o número da aula se repete entre semestres.
No curso 692 existem "Aula 07 - 15/04/2026" e "Aula 07 - 15/05/2026", além da
conferência "AULA 7" de 27/08/2026. Casar por número colaria o vídeo novo na
aula de abril — num curso com ~900 alunos, e sem ninguém perceber. Por isso o
casamento exige DATA COMPLETA e o número nunca decide sozinho.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

# Formatos REAIS de título de página, medidos em 29/08/2026:
#   "Aula 06 - 21/08/2026 - MCUV e Aceleração angular"        (692)
#   "Aula 07 - 24/08/2026 -  Trigonometria: Soma de Arcos"    (691, espaço duplo)
#   "AULA 20 - 19/08/2026 - Funções Inorgânicas"              (693, maiúsculo)
#   "AULA 14 - 17/06 - Anotações | Resolução do Simulado 03"  (693, SEM ano)
_PADRAO_TITULO_PAGINA = re.compile(
    r"^\s*aula\s*0*(?P<numero>\d+)\s*[-–]\s*"
    r"(?P<dia>\d{1,2})/(?P<mes>\d{1,2})(?:/(?P<ano>\d{2,4}))?"
    r"\s*[-–]?\s*(?P<resto>.*)$",
    re.IGNORECASE,
)

_PADRAO_EMBED = re.compile(r"youtube\.com/embed/([A-Za-z0-9_-]{6,})", re.IGNORECASE)

# Sem ano no título, a data sozinha não distingue "17/06" deste ano do mesmo
# título do semestre passado. O `created_at` da página serve de segundo cinto.
DIAS_TOLERANCIA_SEM_ANO = 45


@dataclass(frozen=True)
class TituloPagina:
    numero: int
    dia: int
    mes: int
    ano: int | None
    resto: str


@dataclass(frozen=True)
class Escolhida:
    pagina: dict[str, Any]


@dataclass(frozen=True)
class Nenhuma:
    pass


@dataclass(frozen=True)
class Ambigua:
    candidatas: list[dict[str, Any]]


Escolha = Escolhida | Nenhuma | Ambigua


def parse_titulo_pagina(title: str) -> TituloPagina | None:
    m = _PADRAO_TITULO_PAGINA.match(title or "")
    if not m:
        return None
    ano = m.group("ano")
    if ano is not None:
        ano = int(ano)
        if ano < 100:  # "26" -> 2026
            ano += 2000
    return TituloPagina(
        numero=int(m.group("numero")),
        dia=int(m.group("dia")),
        mes=int(m.group("mes")),
        ano=ano,
        resto=" ".join(m.group("resto").split()),
    )


def _criada_perto_de(pagina: dict[str, Any], quando: date) -> bool:
    """Sem ano no título, só aceita a página se ela foi criada perto da aula."""
    bruto = pagina.get("created_at") or pagina.get("updated_at")
    if not bruto:
        return False  # sem como confirmar o ano: melhor não escrever
    try:
        criada = datetime.fromisoformat(str(bruto).replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return abs((criada - quando).days) <= DIAS_TOLERANCIA_SEM_ANO


def escolher_pagina(
    paginas: list[dict[str, Any]], *, numero_aula: int | None, data_aula: date
) -> Escolha:
    """Devolve a única página da aula, ou recusa.

    NUNCA casa só por número — ver a armadilha no topo do módulo. Empate
    devolve Ambigua, e quem chama não escreve: falhar de forma visível é
    melhor que colar no lugar errado de forma silenciosa."""
    candidatas = []
    for p in paginas:
        alvo = parse_titulo_pagina(p.get("title") or "")
        if alvo is None:
            continue
        if alvo.dia != data_aula.day or alvo.mes != data_aula.month:
            continue
        if alvo.ano is not None:
            if alvo.ano != data_aula.year:
                continue
        elif not _criada_perto_de(p, data_aula):
            continue
        # O número entra só como desempate, nunca como critério sozinho.
        if numero_aula is not None and alvo.numero != numero_aula:
            continue
        candidatas.append(p)

    if not candidatas:
        return Nenhuma()
    if len(candidatas) > 1:
        return Ambigua(candidatas)
    return Escolhida(candidatas[0])


def montar_iframe(titulo_video: str, video_id: str) -> str:
    """Markup idêntico ao que os professores já usam à mão.

    `html.escape` no título: uma aspas dupla no nome do professor quebraria o
    atributo e comeria o resto da tag."""
    return (
        '<p style="text-align: center;">'
        f'<iframe title="{html.escape(titulo_video, quote=True)}" '
        f'src="https://www.youtube.com/embed/{video_id}" '
        'width="780" height="420" allowfullscreen="allowfullscreen" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
        'gyroscope; picture-in-picture; web-share" '
        'frameborder="0" loading="lazy"></iframe></p>'
    )


def ja_tem_este_video(corpo: str, video_id: str) -> bool:
    """É o que torna a varredura idempotente: pode rodar mil vezes."""
    return video_id in _PADRAO_EMBED.findall(corpo or "")


def tem_outro_embed_youtube(corpo: str, video_id: str) -> bool:
    """Página com OUTRO vídeo é ou a página errada, ou já resolvida à mão.
    Nos dois casos, não se escreve por cima."""
    return any(v != video_id for v in _PADRAO_EMBED.findall(corpo or ""))


def corpo_com_embed(corpo_atual: str | None, iframe: str) -> str:
    """PREPEND. O conteúdo do professor é preservado inteiro, abaixo do vídeo.
    Nunca `corpo = iframe` — isso apagaria o material da aula."""
    atual = (corpo_atual or "").strip()
    return f"{iframe}\n{atual}" if atual else iframe


def titulo_pagina_padrao(numero: int | None, data_aula: date, assunto: str) -> str:
    """Título da página criada quando não existe uma.

    Tem de ser parseável por `parse_titulo_pagina`: é isso que fecha a janela
    do POST sem retry — se o POST estourar o timeout mas tiver criado a
    página, a varredura seguinte a encontra em vez de criar uma segunda."""
    prefixo = f"Aula {numero:02d}" if numero is not None else "Aula"
    limpo = " ".join((assunto or "").split())
    # Sem assunto, o título para na data em vez de ganhar um "- " órfão:
    # nem toda conferência traz assunto (ver _assunto_da_conferencia).
    base = f"{prefixo} - {data_aula:%d/%m/%Y}"
    return (f"{base} - {limpo}" if limpo else base)[:255]
