"""Consultas do banco de questões ITA · IME (docs/22 §P2).

Camada de leitura: recebe filtro, devolve os tipos da fronteira
(`schemas/banco.py`). Sem HTTP aqui — `routes/banco.py` só valida, chama e
devolve (docs/22 §7.2), o que permite testar a montagem sem subir a API.

⚠️ `questao_vestibular` é questão de PROVA PASSADA de ITA/IME. A questão de
simulado-Quiz do Canvas é `questao` (0010) e não tem nada a ver — é o erro de
leitura mais provável do schema hoje (api/CLAUDE.md).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, get_args

from supabase import Client

from ..schemas.banco import (
    BlocoTaxonomia,
    EstudoQuestao,
    MateriaBanco,
    PaginaQuestoes,
    QuestaoVestibular,
    TaxonomiaMateria,
    TopicoDaQuestao,
    TopicoTaxonomia,
)

POR_PAGINA_PADRAO = 20
# Teto de página. Não é o teto proibido da armadilha 2 do CLAUDE.md: aquele
# trunca leitura ESTATÍSTICA e devolve número errado sem parecer errado. Este
# limita NAVEGAÇÃO, e a página seguinte está a um clique (docs/22 §2.2).
POR_PAGINA_MAXIMO = 100

# `topico` reservado para "questões que ninguém classificou". As 40 de Química
# (docs/22 §1.4) aparecem na árvore de assuntos com a contagem; sem este valor
# a contagem seria um número que o aluno vê e não consegue abrir — pior do que
# não mostrar. Não colide com código de tópico: os do edital são "N.M".
TOPICO_SEM_CLASSIFICACAO = "sem-assunto"

# Explícito em vez de `*` porque `arquivo_origem` e `importado_em` são de
# operação, não de produto: servem para achar o JSON que gerou uma linha errada
# (docs/22 §7.5) e não têm por que atravessar a fronteira HTTP.
# A alternativa é tabela filha (0028), não coluna: vem por embed do PostgREST,
# numa ida só. Duas consultas separadas dariam N+1 na listagem de 20 questões.
_COLUNAS_QUESTAO = (
    "id, vestibular, ano, fase, materia, numero, dissertativa, enunciado_md, "
    "gabarito, imagem_url, usa_imagem_no_render, resolucao_url, revisado, "
    "questao_vestibular_alternativa(letra, texto)"
)
_COLUNAS_LIGACAO = "questao_id, materia, topico_codigo, confianca, observacao"
_COLUNAS_TAXONOMIA = (
    "materia, codigo, nome, bloco_codigo, bloco_nome, ordem, "
    "topico_taxonomia_assunto(ordem, texto)"
)


@dataclass(frozen=True)
class FiltrosQuestoes:
    """O que a rota aceita em `GET /banco/questoes` (docs/22 §2.1).

    `pagina` é 1-based — é o que a URL mostra e o que o front conta. A tradução
    para o intervalo do PostgREST (0-based, inclusivo nas duas pontas) acontece
    num lugar só, em `listar_questoes`.
    """

    materia: str | None = None
    vestibular: str | None = None
    ano: int | None = None
    fase: int | None = None
    topico: str | None = None
    busca: str | None = None
    pagina: int = 1
    por_pagina: int = POR_PAGINA_PADRAO


# ─── Taxonomia ───────────────────────────────────────────────────────────


def listar_taxonomia(cliente: Client, materia: str | None = None) -> list[TaxonomiaMateria]:
    """Árvore bloco→tópico com a contagem de questões em cada nível.

    Sem `materia`, devolve as três, na ordem canônica do schema.

    Contagem: no TÓPICO uma questão mista aparece nas duas contagens, de
    propósito — é a promessa da recorrência (docs/22 §1.5). No BLOCO e na
    MATÉRIA a contagem é de questões DISTINTAS, senão o total da matéria
    deixaria de bater com as 323/288/323 de fato existentes e o número perderia
    sentido. Daí a soma dos tópicos poder ser maior que o total do bloco.
    """
    linhas_taxonomia = _carregar_taxonomia(cliente, materia)
    questoes = _carregar_questoes_rasas(cliente, materia)
    ligacoes = _carregar_ligacoes_da_materia(cliente, materia)

    questoes_por_materia: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for questao in questoes:
        questoes_por_materia[questao["materia"]].append(questao)

    ids_por_topico: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ligacao in ligacoes:
        ids_por_topico[(ligacao["materia"], ligacao["topico_codigo"])].add(ligacao["questao_id"])

    resultado: list[TaxonomiaMateria] = []
    for nome_materia in _materias_pedidas(materia):
        linhas_da_materia = [l for l in linhas_taxonomia if l["materia"] == nome_materia]
        if not linhas_da_materia:
            continue

        questoes_da_materia = questoes_por_materia.get(nome_materia, [])
        ids_da_materia = {q["id"] for q in questoes_da_materia}
        classificadas: set[str] = set()

        # dict preserva inserção, e as linhas já vêm ordenadas por `ordem` — é
        # assim que a ordem do edital chega na tela sem reordenar nada aqui.
        blocos: dict[str, dict[str, Any]] = {}
        for linha in linhas_da_materia:
            # Interseção com os ids da matéria: a ligação guarda `materia` por
            # conta própria (é metade da FK composta), e uma divergência entre
            # ela e a da questão contaria a questão na matéria errada.
            ids = ids_por_topico.get((nome_materia, linha["codigo"]), set()) & ids_da_materia
            classificadas |= ids

            bloco = blocos.setdefault(
                linha["bloco_codigo"],
                {"nome": linha["bloco_nome"], "topicos": [], "ids": set()},
            )
            bloco["topicos"].append(
                TopicoTaxonomia(
                    codigo=linha["codigo"],
                    nome=linha["nome"],
                    assuntos=_assuntos_do_topico(linha),
                    totalQuestoes=len(ids),
                )
            )
            bloco["ids"] |= ids

        resultado.append(
            TaxonomiaMateria(
                materia=nome_materia,  # type: ignore[arg-type]
                blocos=[
                    BlocoTaxonomia(
                        codigo=codigo,
                        nome=dados["nome"],
                        topicos=dados["topicos"],
                        totalQuestoes=len(dados["ids"]),
                    )
                    for codigo, dados in blocos.items()
                ],
                totalQuestoes=len(questoes_da_materia),
                semClassificacao=len(ids_da_materia - classificadas),
                # Filtro de tela: o ano mais recente primeiro, que é por onde o
                # aluno começa. Em `estatisticas.py` a lista vai crescente,
                # porque lá ela é eixo x de série temporal.
                anos=sorted({int(q["ano"]) for q in questoes_da_materia}, reverse=True),
                fases=sorted({int(q["fase"]) for q in questoes_da_materia}),
                vestibulares=sorted({q["vestibular"] for q in questoes_da_materia}),  # type: ignore[misc]
            )
        )
    return resultado


# ─── Listagem ────────────────────────────────────────────────────────────


def listar_questoes(cliente: Client, filtros: FiltrosQuestoes) -> PaginaQuestoes:
    """Página filtrada de questões.

    A ordem é `ano desc, numero asc, id asc`. O `id` no fim não é enfeite:
    (ano, numero) se repete entre vestibular, fase e matéria — sem um critério
    total, o Postgres é livre para devolver os empates em ordem diferente a
    cada requisição, e aí a virada de página repete uma questão e perde outra.
    """
    pagina = max(1, filtros.pagina)
    por_pagina = min(max(1, filtros.por_pagina), POR_PAGINA_MAXIMO)

    ids_do_topico: list[str] | None = None
    if filtros.topico == TOPICO_SEM_CLASSIFICACAO:
        ids_do_topico = _ids_sem_classificacao(cliente, filtros.materia)
    elif filtros.topico:
        ids_do_topico = _ids_por_topico(cliente, filtros.materia, filtros.topico)
    if ids_do_topico is not None and not ids_do_topico:
        return PaginaQuestoes(questoes=[], total=0, pagina=pagina, porPagina=por_pagina)

    consulta = cliente.table("questao_vestibular").select(_COLUNAS_QUESTAO, count="exact")
    if filtros.materia:
        consulta = consulta.eq("materia", filtros.materia)
    if filtros.vestibular:
        consulta = consulta.eq("vestibular", filtros.vestibular)
    if filtros.ano is not None:
        consulta = consulta.eq("ano", filtros.ano)
    if filtros.fase is not None:
        consulta = consulta.eq("fase", filtros.fase)
    if ids_do_topico is not None:
        consulta = consulta.in_("id", ids_do_topico)
    if filtros.busca and filtros.busca.strip():
        # Busca textual sobre o enunciado, que é o texto extraído do PDF — traz
        # sujeira de OCR junto ("Valor: 0,25", número de página solto). Dívida
        # registrada, não consertada aqui (docs/22 §8, risco 5).
        consulta = consulta.ilike("enunciado_md", f"%{filtros.busca.strip()}%")

    inicio = (pagina - 1) * por_pagina
    resposta = (
        consulta.order("ano", desc=True)
        .order("numero")
        .order("id")
        .range(inicio, inicio + por_pagina - 1)
        .execute()
    )
    linhas = resposta.data or []
    total = int(resposta.count) if resposta.count is not None else len(linhas)

    return PaginaQuestoes(
        questoes=montar_questoes(cliente, linhas),
        total=total,
        pagina=pagina,
        porPagina=por_pagina,
    )


def obter_questao(cliente: Client, questao_id: str) -> QuestaoVestibular | None:
    """Uma questão pelo id legível (`ita_2019_fase1_q01`). None se não existe."""
    resposta = (
        cliente.table("questao_vestibular")
        .select(_COLUNAS_QUESTAO)
        .eq("id", questao_id)
        .limit(1)
        .execute()
    )
    linhas = resposta.data or []
    if not linhas:
        return None
    return montar_questoes(cliente, linhas)[0]


def montar_questoes(
    cliente: Client, linhas: Sequence[Mapping[str, Any]]
) -> list[QuestaoVestibular]:
    """Linhas cruas → questões da fronteira, com os tópicos já resolvidos.

    Pública porque `listas.py` monta questão a partir de linhas que ele mesmo
    leu (a lista tem ordem própria) e não deveria reimplementar a junção.
    """
    if not linhas:
        return []

    ids = [linha["id"] for linha in linhas]
    ligacoes = (
        cliente.table("questao_vestibular_topico")
        .select(_COLUNAS_LIGACAO)
        .in_("questao_id", ids)
        .execute()
        .data
        or []
    )
    # A taxonomia inteira são ~100 linhas nas três matérias: uma requisição só
    # sai mais barata que decidir quais matérias a página contém.
    indice = _indice_taxonomia(_carregar_taxonomia(cliente, None))

    topicos_por_questao: dict[str, list[tuple[int, str, TopicoDaQuestao]]] = defaultdict(list)
    for ligacao in ligacoes:
        codigo = ligacao["topico_codigo"]
        meta = indice.get((ligacao["materia"], codigo), {})
        topicos_por_questao[ligacao["questao_id"]].append(
            (
                int(meta.get("ordem") or 0),
                codigo,
                TopicoDaQuestao(
                    codigo=codigo,
                    # Fallback no próprio código: a FK composta impede órfão,
                    # mas um nome vazio na tela esconderia o tópico do aluno.
                    nome=meta.get("nome") or codigo,
                    blocoNome=meta.get("bloco_nome") or "",
                    confianca=ligacao.get("confianca"),
                    observacao=ligacao.get("observacao"),
                ),
            )
        )

    return [
        _para_questao(
            linha,
            [item[2] for item in sorted(topicos_por_questao.get(linha["id"], []), key=lambda t: t[:2])],
        )
        for linha in linhas
    ]


def anexar_estudo(
    questoes: Sequence[QuestaoVestibular],
    estudo_por_questao: Mapping[str, EstudoQuestao],
) -> list[QuestaoVestibular]:
    """Preenche `resolvida`/`anotacao` das questões com o estudo do aluno (P6).

    Só o casco do aluno chama isto. Para a coordenação os dois campos ficam
    None — que é diferente de `false`: um diz "este perfil não tem estudo", o
    outro diz "este aluno não resolveu". Sem linha em `questao_estudo_aluno` a
    questão é não-tocada, e a leitura certa para a tela é `false`.
    """
    for questao in questoes:
        estudo = estudo_por_questao.get(questao.id)
        questao.resolvida = estudo.resolvida if estudo else False
        questao.anotacao = estudo.anotacao if estudo else None
    return list(questoes)


# ─── Tradução da fronteira ───────────────────────────────────────────────


def _para_questao(
    linha: Mapping[str, Any], topicos: list[TopicoDaQuestao]
) -> QuestaoVestibular:
    """A única tradução snake_case → camelCase do módulo.

    Uma função só, de propósito: espalhar a conversão é como um `enunciadoMd`
    vira `enunciado_md` em metade das respostas sem ninguém notar.
    """
    return QuestaoVestibular(
        id=linha["id"],
        vestibular=linha["vestibular"],
        ano=int(linha["ano"]),
        fase=int(linha["fase"]),
        materia=linha["materia"],
        numero=int(linha["numero"]),
        dissertativa=bool(linha.get("dissertativa")),
        enunciadoMd=linha.get("enunciado_md") or "",
        # Dissertativa não tem alternativa nem letra de gabarito: são 420 e 469
        # das 934, e é o esperado, não falta de dado (docs/22 §8, risco 4).
        alternativas=_alternativas_da_questao(linha),
        gabarito=linha.get("gabarito"),
        imagemUrl=linha.get("imagem_url"),
        usaImagemNoRender=bool(linha.get("usa_imagem_no_render")),
        resolucaoUrl=linha.get("resolucao_url"),
        topicos=topicos,
        revisado=bool(linha.get("revisado")),
    )


# ─── Leitura crua ────────────────────────────────────────────────────────


def _materias_pedidas(materia: str | None) -> list[str]:
    """A ordem canônica vem do próprio Literal do schema — uma lista à parte
    aqui envelheceria calada no dia em que entrasse uma quarta matéria."""
    canonicas = list(get_args(MateriaBanco))
    if materia:
        return [materia] if materia in canonicas else []
    return canonicas


def _carregar_taxonomia(cliente: Client, materia: str | None) -> list[dict[str, Any]]:
    consulta = cliente.table("topico_taxonomia").select(_COLUNAS_TAXONOMIA)
    if materia:
        consulta = consulta.eq("materia", materia)
    return consulta.order("materia").order("ordem").execute().data or []


def _indice_taxonomia(linhas: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Chave (materia, codigo) porque '1.1' existe nas três matérias e significa
    coisa diferente em cada uma — indexar só por código misturaria as três em
    silêncio, que é exatamente o que a PK composta da 0028 evita."""
    return {(linha["materia"], linha["codigo"]): dict(linha) for linha in linhas}


def _carregar_questoes_rasas(cliente: Client, materia: str | None) -> list[dict[str, Any]]:
    """As 934 questões, só com o que a contagem precisa.

    Sem paginação e sem teto: aqui a resposta é AGREGADA, e uma leitura
    truncada devolveria contagem errada sem parecer errada — é a armadilha 2 do
    CLAUDE.md, e vale igual (docs/22 §2.2). Quem pagina é `listar_questoes`.
    """
    consulta = cliente.table("questao_vestibular").select("id, materia, ano, fase, vestibular")
    if materia:
        consulta = consulta.eq("materia", materia)
    return consulta.execute().data or []


def _carregar_ligacoes_da_materia(cliente: Client, materia: str | None) -> list[dict[str, Any]]:
    consulta = cliente.table("questao_vestibular_topico").select("questao_id, materia, topico_codigo")
    if materia:
        consulta = consulta.eq("materia", materia)
    return consulta.execute().data or []


def _alternativas_da_questao(linha: dict[str, Any]) -> dict[str, str] | None:
    """As alternativas embutidas viram o dicionário {letra: texto} da fronteira.

    Ordena pela letra: o PostgREST não garante ordem em recurso embutido, e
    alternativa fora de ordem alfabética é erro que o olho não perdoa.
    None e não `{}` na dissertativa — dicionário vazio faria o front renderizar
    uma lista de alternativas sem nenhuma.
    """
    linhas = linha.get("questao_vestibular_alternativa") or []
    if not linhas:
        return None
    return {item["letra"]: item["texto"] for item in sorted(linhas, key=lambda x: x["letra"])}


def _assuntos_do_topico(linha: dict[str, Any]) -> list[str]:
    """Os assuntos do edital, na ordem do edital — que é `ordem`, não o texto."""
    linhas = linha.get("topico_taxonomia_assunto") or []
    return [item["texto"] for item in sorted(linhas, key=lambda x: x["ordem"])]


def _ids_sem_classificacao(cliente: Client, materia: str | None) -> list[str]:
    """Ids das questões sem NENHUMA linha em `questao_vestibular_topico`.

    Duas leituras e uma diferença de conjuntos, porque o PostgREST não faz
    `NOT EXISTS`. É barato: as duas tabelas somam ~2.300 linhas de uma coluna
    só, e a alternativa — peneirar no cliente — daria total e paginação
    errados, que é justamente o que a §2.2 diz para não fazer.
    """
    consulta = cliente.table("questao_vestibular").select("id")
    if materia:
        consulta = consulta.eq("materia", materia)
    todas = {linha["id"] for linha in (consulta.execute().data or [])}

    ligacao = cliente.table("questao_vestibular_topico").select("questao_id")
    if materia:
        ligacao = ligacao.eq("materia", materia)
    classificadas = {linha["questao_id"] for linha in (ligacao.execute().data or [])}

    return sorted(todas - classificadas)


def _ids_por_topico(cliente: Client, materia: str | None, topico: str) -> list[str]:
    """Ids das questões classificadas no tópico, para filtrar a listagem.

    Duas passadas em vez de embed `!inner` do PostgREST: com o embed filtrado, o
    array de tópicos que volta junto viria PODADO ao tópico filtrado, e uma
    questão mista apareceria na tela com um tópico só.

    ⚠️ Sem `materia`, o mesmo código casa nas três matérias — '1.1' é
    "Fundamentos", "Conjuntos e Lógica" e "Estrutura Atômica" conforme a
    matéria (0028). A rota deve exigir as duas coisas juntas.

    O `.in_()` que consome esta lista viaja na query string. O maior tópico do
    banco tem dezenas de questões, longe do limite de URL que já mordeu o
    projeto em `lembretes/aplicacoes/aluno_simulado.py` com ~900 ids.
    """
    consulta = cliente.table("questao_vestibular_topico").select("questao_id").eq("topico_codigo", topico)
    if materia:
        consulta = consulta.eq("materia", materia)
    linhas = consulta.execute().data or []
    return sorted({linha["questao_id"] for linha in linhas})
