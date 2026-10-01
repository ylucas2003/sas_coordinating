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
from dataclasses import dataclass
from datetime import date, datetime
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


@dataclass(frozen=True)
class _Pendurada:
    #: Nulo = a página continua fora de módulo, e `erro` diz por quê.
    modulo: str | None
    #: Com `modulo` preenchido, é a nota de POR QUE a aula caiu no genérico —
    #: vira a dica do selo na tela, para quem vai arrastá-la.
    erro: str | None
    #: Id do módulo genérico quando esta chamada o criou ou o achou pelo nome.
    #: Quem chama grava no curso; aqui não se escreve no banco.
    generico_id: str | None = None


async def _ler_modulos(canvas: ClienteCanvas, curso_id: str) -> list[pagina_canvas.ModuloCanvas]:
    modulos = []
    for m in await canvas.listar_modulos(curso_id):
        itens = await canvas.listar_itens_modulo(curso_id, str(m["id"]))
        modulos.append(
            pagina_canvas.ModuloCanvas(
                id=str(m["id"]),
                nome=m.get("name") or "",
                itens=tuple(
                    pagina_canvas.ItemModulo(
                        i.get("title") or "", i.get("position") or 0, i.get("page_url")
                    )
                    for i in itens
                ),
            )
        )
    return modulos


async def _pendurar_no_modulo(
    canvas: ClienteCanvas,
    *,
    curso_id: str,
    slug: str,
    titulo_pagina: str,
    data_aula: date,
    modulo_padrao_id: str | None,
    modulo_generico_id: str | None = None,
) -> _Pendurada:
    """Garante que a página está em algum módulo.

    Em ordem: se já está pendurada, só registra onde; senão, o assunto e o
    módulo padrão decidem (`escolher_modulo`); se nada decidir, vai para o
    módulo genérico do curso, que é criado na primeira vez que faz falta.

    NUNCA propaga exceção: a página já existe e já tem o vídeo. Perder a
    publicação inteira porque a listagem de módulos falhou seria trocar um
    problema pequeno (página fora de módulo, que se arrasta) por um grande
    (aula sem vídeo, e a gravação some do Canvas em ~7 dias)."""
    try:
        modulos = await _ler_modulos(canvas, curso_id)
        ja = pagina_canvas.modulo_da_pagina(modulos, slug)
        if ja:
            return _Pendurada(ja.nome, None)

        generico = pagina_canvas.achar_modulo_generico(modulos, modulo_generico_id)
        # O genérico fica FORA da escolha por assunto. Senão a primeira aula de
        # um assunto novo, caída ali, puxaria as seguintes para o genérico
        # mesmo depois de a coordenação criar a trilha dele.
        escolha = pagina_canvas.escolher_modulo(
            [m for m in modulos if m is not generico],
            titulo_pagina=titulo_pagina,
            data_aula=data_aula,
            modulo_padrao_id=modulo_padrao_id,
        )
        nota = None
        if isinstance(escolha, pagina_canvas.SemModulo):
            if generico is None:
                criado = await canvas.criar_modulo(
                    curso_id, nome=pagina_canvas.NOME_MODULO_GENERICO, publicado=True
                )
                generico = pagina_canvas.ModuloCanvas(
                    id=str(criado["id"]),
                    nome=criado.get("name") or pagina_canvas.NOME_MODULO_GENERICO,
                    itens=(),
                )
            nota = f"em '{generico.nome}' porque {escolha.motivo}; arraste para a trilha certa"
            escolha = pagina_canvas.no_modulo_generico(generico, data_aula)

        await canvas.criar_item_modulo(
            curso_id,
            escolha.modulo_id,
            titulo=titulo_pagina,
            page_url=slug,
            posicao=escolha.posicao,
        )
        novo_generico = (
            generico.id if generico and generico.id != str(modulo_generico_id or "") else None
        )
        return _Pendurada(escolha.nome, nota and nota[:400], novo_generico)
    # A publicação do vídeo não pode cair por causa da arrumação.
    except Exception as exc:
        return _Pendurada(None, f"página fora de módulo: {type(exc).__name__}: {exc}"[:400])


async def _publicar_uma(
    canvas: ClienteCanvas,
    aula: dict[str, Any],
    *,
    simular: bool,
    modulo_padrao_id: str | None = None,
    modulo_generico_id: str | None = None,
) -> dict[str, Any]:
    """Devolve o que fazer/foi feito com uma aula. NÃO escreve no banco.

    A chave `_modulo_generico_id`, quando vem, é o módulo genérico que esta
    aula criou ou achou pelo nome — `varrer` a tira do dict e grava no curso."""
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
        pendurada = await _pendurar_no_modulo(
            canvas,
            curso_id=curso_id,
            slug=criada.get("url") or "",
            titulo_pagina=novo_titulo,
            data_aula=data_aula,
            modulo_padrao_id=modulo_padrao_id,
            modulo_generico_id=modulo_generico_id,
        )
        return {
            "canvas_estado": "publicado",
            "canvas_pagina_url": criada.get("html_url"),
            "canvas_pagina_slug": criada.get("url"),
            "canvas_pagina_criada": True,
            **_campos_do_modulo(pendurada),
            "plano": "criada" if pendurada.modulo else "criada (fora de módulo)",
        }

    pagina = escolha.pagina
    slug = pagina.get("url")
    completa = await canvas.obter_pagina(curso_id, slug)
    corpo = completa.get("body") or ""

    async def _pendurar_existente() -> _Pendurada:
        # A página do professor quase sempre já está num módulo, e aí isto só
        # registra qual. Antes nada era registrado, e toda aula embutida numa
        # página existente aparecia na tela como "fora de módulo".
        return await _pendurar_no_modulo(
            canvas,
            curso_id=curso_id,
            slug=slug or "",
            titulo_pagina=pagina.get("title") or "",
            data_aula=data_aula,
            modulo_padrao_id=modulo_padrao_id,
            modulo_generico_id=modulo_generico_id,
        )

    if pagina_canvas.ja_tem_este_video(corpo, video_id):
        # Idempotência: a varredura pode rodar mil vezes sem duplicar embed.
        if simular:
            # Pendurar escreve no Canvas, e o ensaio não escreve.
            return {"plano": "já estava lá", "titulo_pagina": pagina.get("title"),
                    "canvas_estado": "pendente"}
        pendurada = await _pendurar_existente()
        return {
            "canvas_estado": "publicado",
            "canvas_pagina_url": pagina.get("html_url"),
            "canvas_pagina_slug": slug,
            **_campos_do_modulo(pendurada),
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
    pendurada = await _pendurar_existente()
    return {
        "canvas_estado": "publicado",
        "canvas_pagina_url": pagina.get("html_url"),
        "canvas_pagina_slug": slug,
        **_campos_do_modulo(pendurada),
        "plano": "embutido",
    }


def _campos_do_modulo(p: _Pendurada) -> dict[str, Any]:
    """A página existe e tem o vídeo; ficar fora de módulo é pendência de
    arrumação, não falha da publicação. Por isso o motivo vai em `canvas_erro`
    e o estado continua 'publicado'."""
    campos: dict[str, Any] = {"canvas_modulo_nome": p.modulo, "canvas_erro": p.erro}
    if p.generico_id:
        campos["_modulo_generico_id"] = p.generico_id
    return campos


def _guardar_generico(cliente: Any, cursos: dict[str, dict], curso_id: str, modulo_id: str) -> None:
    """Grava o id para que a próxima aula não precise achar pelo nome — e para
    que renomear o módulo no Canvas não faça nascer um segundo."""
    cliente.table("curso_monitorado_gravacao").update(
        {"canvas_modulo_generico_id": modulo_id}
    ).eq("curso_id", curso_id).execute()
    cursos[curso_id]["canvas_modulo_generico_id"] = modulo_id


def _rependurar(
    cliente: Any, cursos: dict[str, dict], ligados: list[str], *, ja_vistas: set[str], limite: int
) -> list[dict[str, Any]]:
    """Segunda chance para página publicada e fora de módulo.

    'publicado' é terminal na primeira fase, então uma página que ficou fora
    de módulo ficava assim para sempre. Ficam aqui dois grupos: as aulas de
    antes do módulo genérico, e as embutidas em página do professor, que nunca
    tiveram o módulo registrado — boa parte delas já está num módulo, e aí
    isto só anota qual, sem escrever no Canvas.

    Mais nova primeiro: é a que o aluno está procurando esta semana."""
    settings = get_settings()
    orfas = (
        cliente.table("aula_gravacao")
        .select("id,curso_id,titulo,iniciada_em,canvas_pagina_slug")
        .eq("canvas_estado", "publicado")
        .is_("canvas_modulo_nome", "null")
        .not_.is_("canvas_pagina_slug", "null")
        .in_("curso_id", ligados)
        .order("iniciada_em", desc=True)
        .limit(limite + len(ja_vistas))
        .execute()
        .data
    )
    # Quem a primeira fase acabou de tentar não repete na mesma rodada.
    orfas = [a for a in orfas if a["id"] not in ja_vistas][:limite]

    resultados: list[dict[str, Any]] = []
    for aula in orfas:
        data_aula = _data_da_aula(aula)
        if data_aula is None:
            continue
        curso = cursos[aula["curso_id"]]

        async def _ida(a=aula, d=data_aula, c=curso) -> _Pendurada:
            async with ClienteCanvas(
                base_url=settings.canvas_base_url, token=settings.canvas_api_token
            ) as canvas:
                slug = a["canvas_pagina_slug"]
                # O título do item é o da página como ela está AGORA, que é o
                # que o professor escreveu — a aula guarda só o da conferência.
                pagina = await canvas.obter_pagina(a["curso_id"], slug)
                return await _pendurar_no_modulo(
                    canvas,
                    curso_id=a["curso_id"],
                    slug=slug,
                    titulo_pagina=pagina.get("title") or "",
                    data_aula=d,
                    modulo_padrao_id=c.get("canvas_modulo_id"),
                    modulo_generico_id=c.get("canvas_modulo_generico_id"),
                )

        try:
            p = asyncio.run(_ida())
        # Uma aula ruim não derruba as outras.
        except Exception as exc:
            p = _Pendurada(None, f"página fora de módulo: {type(exc).__name__}: {exc}"[:400])

        if p.generico_id:
            _guardar_generico(cliente, cursos, aula["curso_id"], p.generico_id)
        cliente.table("aula_gravacao").update(
            {"canvas_modulo_nome": p.modulo, "canvas_erro": p.erro}
        ).eq("id", aula["id"]).execute()
        resultados.append(
            {"aula": (aula["titulo"] or "")[:44], "curso": aula["curso_id"],
             "modulo": p.modulo, "erro": p.erro}
        )
    return resultados


def varrer(cliente: Any, *, simular: bool = False, limite: int = _MAX_POR_VARREDURA) -> dict:
    """Uma passada por todas as aulas com vídeo e sem página; depois, pelas
    que já têm página mas ficaram fora de módulo (`_rependurar`).

    `simular=True` calcula tudo e NÃO escreve — nem no Canvas, nem no banco.
    É como se confere o casamento antes de ligar um curso. A segunda fase não
    roda no ensaio: ela escreve em página que já existe, não decide página."""
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

        async def _ida(
            a=aula,
            modulo=curso.get("canvas_modulo_id"),
            generico=curso.get("canvas_modulo_generico_id"),
        ):
            async with ClienteCanvas(
                base_url=settings.canvas_base_url, token=settings.canvas_api_token
            ) as canvas:
                return await _publicar_uma(
                    canvas, a, simular=simular,
                    modulo_padrao_id=modulo, modulo_generico_id=generico,
                )

        try:
            r = asyncio.run(_ida())
        # Uma aula ruim não derruba as outras da varredura.
        except Exception as exc:
            r = {"canvas_estado": "falhou", "canvas_erro": f"{type(exc).__name__}: {exc}"[:400]}

        plano = r.pop("plano", None)
        generico_id = r.pop("_modulo_generico_id", None)
        if generico_id and not simular:
            _guardar_generico(cliente, cursos, aula["curso_id"], generico_id)
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

    rependuradas = (
        []
        if simular
        else _rependurar(
            cliente, cursos, ligados,
            ja_vistas={a["id"] for a in candidatas}, limite=limite,
        )
    )
    return {"status": "ok", "simulado": simular, "analisadas": len(resultados),
            "resultados": resultados, "rependuradas": rependuradas}
