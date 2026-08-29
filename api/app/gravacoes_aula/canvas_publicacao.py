"""Leva o vídeo já publicado no YouTube até a página da aula no Canvas.

Etapa separada do pipeline de vídeo de propósito. Duas razões:

  - é barata (poucas chamadas HTTP) contra 45-90 min de download+ffmpeg, então
    dá para retentar sozinha sem tocar no YouTube;
  - é a ÚNICA parte que escreve num curso com ~900 alunos, e escrever no lugar
    errado é silencioso. Ter rota própria permite o ensaio (`simular=True`)
    antes de ligar cada curso.

O estado vive em `aula_gravacao.canvas_estado`, eixo INDEPENDENTE do `status`
do YouTube — que continua com seus terminais intactos (ver migration 0035).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from datetime import datetime
from typing import Any

from ..canvas_sync.cliente import ClienteCanvas
from ..config import get_settings
from . import pagina_canvas, publicador_youtube
from . import titulo as titulo_mod

_log = logging.getLogger(__name__)

_MAX_TENTATIVAS_CANVAS = 3
_MAX_POR_VARREDURA = 20

# Estados que a varredura pega. 'ambiguo' e 'conflito' ficam de FORA: são
# decisões de "não escrever" que exigem gente olhando, não retentativa cega.
#
# 'ignorado' ESTÁ aqui, e a distinção importa: ele não é uma recusa, é um "não
# agora" — quer dizer só que o curso estava desligado quando a rodada passou.
# Deixá-lo fora tornava o estado terminal, e isso quebrava as duas coisas que a
# migration 0035 manda fazer para ligar um curso: as aulas já carimbadas nunca
# voltavam ao pool quando o interruptor era ligado, e o ensaio `?simular=true`
# devolvia zero candidatas, porque o filtro da consulta roda ANTES do desvio
# que ignora o interruptor. Resgatar o que já foi carimbado em produção depende
# exatamente disto.
_CANVAS_RETENTAVEIS = ("pendente", "falhou", "ignorado")


def _data_da_aula(aula: dict[str, Any]) -> Any:
    bruto = aula.get("iniciada_em")
    if not bruto:
        return None
    with contextlib.suppress(ValueError):
        return datetime.fromisoformat(str(bruto).replace("Z", "+00:00")).astimezone(
            titulo_mod._FUSO_COLEGIO
        ).date()
    return None


# Ruído que aparece no título da conferência e não é assunto de aula.
_RUIDO_TITULO = (
    re.compile(r"\bprofa?\.?\s+[A-ZÀ-Ý][\wÀ-ÿ]*(?:\s+[A-ZÀ-Ý][\wÀ-ÿ]*)*", re.IGNORECASE),
    re.compile(r"\baula\s*\d+", re.IGNORECASE),
    re.compile(r"\d{1,2}/\d{1,2}(?:/\d{2,4})?"),
    re.compile(r"\d{1,2}[:h]\d{2}"),
    re.compile(r"\(\s*\)"),
    # O 581 nomeia a conferência com o prefixo do canal e a turma
    # ("SAS ITA/IME 2026 - Turma 1 e 2 - Inglês - ..."), e sem limpar isso a
    # página nascia "Aula - 28/08/2026 - SAS ITA/IME 2026 Turma 1 e 2 Inglês".
    # Nos outros três cursos não muda nada — não há esses pedaços no título.
    re.compile(r"\bSAS\s+(?:Preparat[óo]rio\s+)?ITA/IME\s*\d{0,4}", re.IGNORECASE),
    re.compile(r"\bTurma\s+\d(?:\s+e\s+\d)?", re.IGNORECASE),
)


def _assunto_da_conferencia(titulo_conferencia: str) -> str:
    """O assunto da aula, para compor o título da página criada.

    Nem toda conferência tem assunto. A Matemática escreve
    "Aula 08 - 25/08/2026 - Complexos: Forma Trigonométrica", e aí o assunto
    existe; já Física e Química escrevem só matéria, professor, número e hora
    ("Química - AULA 19 - 26/08/2026 - Prof. José Marques - 17:30"), e aí não
    há assunto nenhum. Concatenar o título inteiro produziria
    "Aula 19 - 26/08/2026 - Química - AULA 19 - 26/08/2026 - Prof. ...".

    Devolve "" quando não sobra nada — quem chama omite o segmento."""
    lido = pagina_canvas.parse_titulo_pagina(titulo_conferencia)
    if lido and lido.resto:
        return lido.resto
    texto = titulo_conferencia or ""
    for padrao in _RUIDO_TITULO:
        texto = padrao.sub(" ", texto)
    # Sobram separadores soltos entre os pedaços removidos.
    pedacos = [p.strip(" -–|") for p in texto.split("-")]
    limpo = " ".join(" ".join(p for p in pedacos if p).split())
    return limpo.strip(" -–|")


async def _pendurar_no_modulo(
    canvas: ClienteCanvas,
    *,
    curso_id: str,
    slug: str,
    titulo_pagina: str,
    data_aula: Any,
    modulo_padrao_id: str | None,
) -> tuple[str | None, str | None]:
    """Pendura a página recém-criada. Devolve (nome do módulo, motivo da falha).

    NUNCA propaga exceção: a página já existe e já tem o vídeo. Perder a
    publicação inteira porque a listagem de módulos falhou seria trocar um
    problema pequeno (página fora de módulo, que se arrasta) por um grande
    (aula sem vídeo, e a gravação some do Canvas em ~7 dias)."""
    try:
        brutos = await canvas.listar_modulos(curso_id)
        modulos = []
        for m in brutos:
            itens = await canvas.listar_itens_modulo(curso_id, str(m["id"]))
            modulos.append(
                pagina_canvas.ModuloCanvas(
                    id=str(m["id"]),
                    nome=m.get("name") or "",
                    itens=tuple(
                        pagina_canvas.ItemModulo(i.get("title") or "", i.get("position") or 0)
                        for i in itens
                    ),
                )
            )
        escolha = pagina_canvas.escolher_modulo(
            modulos,
            titulo_pagina=titulo_pagina,
            data_aula=data_aula,
            modulo_padrao_id=modulo_padrao_id,
        )
        if isinstance(escolha, pagina_canvas.SemModulo):
            return None, f"página fora de módulo: {escolha.motivo}"[:400]
        await canvas.criar_item_modulo(
            curso_id,
            escolha.modulo_id,
            titulo=titulo_pagina,
            page_url=slug,
            posicao=escolha.posicao,
        )
        return escolha.nome, None
    # A publicação do vídeo não pode cair por causa da arrumação.
    except Exception as exc:
        return None, f"página fora de módulo: {type(exc).__name__}: {exc}"[:400]


async def _publicar_uma(
    canvas: ClienteCanvas,
    aula: dict[str, Any],
    *,
    simular: bool,
    modulo_padrao_id: str | None = None,
) -> dict[str, Any]:
    """Devolve o que fazer/foi feito com uma aula. NÃO escreve no banco."""
    curso_id = aula["curso_id"]
    video_id = aula["youtube_video_id"]
    data_aula = _data_da_aula(aula)
    if data_aula is None:
        return {"canvas_estado": "falhou", "canvas_erro": "aula sem iniciada_em"}

    # Guard do vídeo privado: projeto de API não auditado força 'private', e
    # um vídeo privado embutido numa página vira "Video unavailable" para
    # ~900 alunos, com o banco dizendo "publicado".
    try:
        privacidade = await asyncio.to_thread(publicador_youtube.privacidade, video_id)
    # Falha ao LER a privacidade não é motivo para escrever às cegas.
    except Exception as exc:
        return {"canvas_estado": "falhou", "canvas_erro": f"não li a privacidade: {exc}"[:400]}
    if privacidade == "private":
        return {
            "canvas_estado": "falhou",
            "canvas_erro": "vídeo está 'private' no YouTube; embutir mostraria "
            "'Video unavailable' para os alunos",
        }

    numero = titulo_mod.extrair_numero_aula(aula["titulo"] or "")
    paginas = await canvas.listar_paginas(curso_id)
    escolha = pagina_canvas.escolher_pagina(paginas, numero_aula=numero, data_aula=data_aula)

    titulo_video = aula.get("youtube_titulo") or aula["titulo"]
    iframe = pagina_canvas.montar_iframe(titulo_video, video_id)

    if isinstance(escolha, pagina_canvas.Ambigua):
        titulos = ", ".join(p.get("title", "?") for p in escolha.candidatas[:3])
        return {
            "canvas_estado": "ambiguo",
            "canvas_erro": f"{len(escolha.candidatas)} páginas candidatas: {titulos}"[:400],
            "plano": "não escreve — precisa de gente",
        }

    if isinstance(escolha, pagina_canvas.Nenhuma):
        novo_titulo = pagina_canvas.titulo_pagina_padrao(
            numero, data_aula, _assunto_da_conferencia(aula["titulo"] or "")
        )
        if simular:
            return {"plano": "criar", "titulo_pagina": novo_titulo, "canvas_estado": "pendente"}
        criada = await canvas.criar_pagina(curso_id, titulo=novo_titulo, corpo=iframe)
        modulo, erro_modulo = await _pendurar_no_modulo(
            canvas,
            curso_id=curso_id,
            slug=criada.get("url") or "",
            titulo_pagina=novo_titulo,
            data_aula=data_aula,
            modulo_padrao_id=modulo_padrao_id,
        )
        return {
            "canvas_estado": "publicado",
            "canvas_pagina_url": criada.get("html_url"),
            "canvas_pagina_slug": criada.get("url"),
            "canvas_pagina_criada": True,
            "canvas_modulo_nome": modulo,
            # A página existe e tem o vídeo; ficar fora de módulo é pendência
            # de arrumação, não falha da publicação. Por isso vai em
            # `canvas_erro` e o estado continua 'publicado'.
            "canvas_erro": erro_modulo,
            "plano": "criada" if modulo else "criada (fora de módulo)",
        }

    pagina = escolha.pagina
    slug = pagina.get("url")
    completa = await canvas.obter_pagina(curso_id, slug)
    corpo = completa.get("body") or ""

    if pagina_canvas.ja_tem_este_video(corpo, video_id):
        # Idempotência: a varredura pode rodar mil vezes sem duplicar embed.
        return {
            "canvas_estado": "publicado",
            "canvas_pagina_url": pagina.get("html_url"),
            "canvas_pagina_slug": slug,
            "canvas_erro": None,
            "plano": "já estava lá",
        }

    if pagina_canvas.tem_outro_embed_youtube(corpo, video_id):
        return {
            "canvas_estado": "conflito",
            "canvas_pagina_url": pagina.get("html_url"),
            "canvas_pagina_slug": slug,
            "canvas_erro": f"'{pagina.get('title')}' já tem OUTRO vídeo embutido"[:400],
            "plano": "não escreve — página errada ou já resolvida à mão",
        }

    if simular:
        return {"plano": "embutir", "titulo_pagina": pagina.get("title"), "canvas_estado": "pendente"}

    await canvas.atualizar_pagina(
        curso_id, slug, corpo=pagina_canvas.corpo_com_embed(corpo, iframe)
    )
    return {
        "canvas_estado": "publicado",
        "canvas_pagina_url": pagina.get("html_url"),
        "canvas_pagina_slug": slug,
        "canvas_erro": None,
        "plano": "embutido",
    }


def varrer(cliente: Any, *, simular: bool = False, limite: int = _MAX_POR_VARREDURA) -> dict:
    """Uma passada por todas as aulas com vídeo e sem página.

    `simular=True` calcula tudo e NÃO escreve — nem no Canvas, nem no banco.
    É como se confere o casamento antes de ligar um curso."""
    settings = get_settings()
    cursos = {
        c["curso_id"]: c
        for c in cliente.table("curso_monitorado_gravacao").select("*").execute().data
    }
    # Curso desligado nem entra na consulta. Antes ele entrava, era carimbado
    # 'ignorado' e ocupava uma das 20 vagas da rodada — com três cursos
    # desligados e um ligado, as aulas mais antigas (que são as ignoradas, pela
    # ordenação) empurrariam para fora justamente as que têm trabalho a fazer.
    # No modo simular a lista é outra: ensaiar é para ANTES de ligar.
    ligados = [cid for cid, c in cursos.items() if c.get("publicar_no_canvas")]
    if not simular and not ligados:
        return {"status": "ok", "simulado": False, "analisadas": 0, "resultados": [],
                "nota": "nenhum curso com publicar_no_canvas ligado"}

    candidatas = (
        cliente.table("aula_gravacao")
        .select("id,curso_id,conferencia_id,titulo,iniciada_em,youtube_video_id,youtube_titulo,canvas_estado,canvas_tentativas")
        .not_.is_("youtube_video_id", "null")
        .in_("canvas_estado", list(_CANVAS_RETENTAVEIS))
        .lt("canvas_tentativas", _MAX_TENTATIVAS_CANVAS)
        .in_("curso_id", ligados if not simular else list(cursos))
        .order("iniciada_em", desc=False)
        .limit(limite)
        .execute()
        .data
    )

    resultados: list[dict[str, Any]] = []
    for aula in candidatas:
        curso = cursos.get(aula["curso_id"]) or {}
        # Cinto de segurança: a consulta acima já filtrou por curso ligado. NÃO
        # carimba 'ignorado' — carimbar tirava a aula do pool e era o que
        # impedia o curso de ser ligado depois. No modo simular o interruptor é
        # ignorado DE PROPÓSITO: ensaiar é para antes de ligar.
        if not simular and not curso.get("publicar_no_canvas"):
            continue

        async def _ida(a=aula, modulo=curso.get("canvas_modulo_id")):
            async with ClienteCanvas(
                base_url=settings.canvas_base_url, token=settings.canvas_api_token
            ) as canvas:
                return await _publicar_uma(canvas, a, simular=simular, modulo_padrao_id=modulo)

        try:
            r = asyncio.run(_ida())
        # Uma aula ruim não derruba as outras da varredura.
        except Exception as exc:
            r = {"canvas_estado": "falhou", "canvas_erro": f"{type(exc).__name__}: {exc}"[:400]}

        plano = r.pop("plano", None)
        if not simular:
            campos = dict(r)
            if r.get("canvas_estado") in ("falhou", "ambiguo", "conflito"):
                campos["canvas_tentativas"] = aula["canvas_tentativas"] + 1
            # NÃO escreve atualizado_em: esse carimbo é o relógio do corte por
            # esfriamento do pipeline de vídeo (ver _mais_velho_que em rotas.py).
            cliente.table("aula_gravacao").update(campos).eq("id", aula["id"]).execute()

        resultados.append(
            {"aula": (aula["titulo"] or "")[:44], "curso": aula["curso_id"],
             "estado": r.get("canvas_estado"), "plano": plano,
             "pagina": r.get("titulo_pagina") or r.get("canvas_pagina_url"),
             "erro": r.get("canvas_erro")}
        )

    return {"status": "ok", "simulado": simular, "analisadas": len(resultados),
            "resultados": resultados}
