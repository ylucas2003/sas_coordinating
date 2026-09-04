"""Recorrência por tópico no banco de questões ITA · IME (docs/22 §P4).

Responde "o que mais cai": quantas vezes cada tópico do edital apareceu, e como
essa contagem se distribui por ano, por fase e por vestibular. É o que alimenta
o `Histograma` e a `LinhaTemporal` do front — SVG à mão, sem Chart.js
(docs/22 §P4).

⚠️ **Aqui não há teto e não há paginação, e é de propósito.** A armadilha 2 do
CLAUDE.md continua valendo em cheio: uma leitura truncada devolveria uma
recorrência ERRADA sem parecer errada — o tópico apareceria com 4 ocorrências
em vez de 11 e ninguém veria erro nenhum, só um número. A paginação da
`GET /banco/questoes` não contradiz isso porque lá a resposta é navegação, e uma
página é resposta completa da pergunta feita (docs/22 §2.2). Quem agrega, lê a
tabela inteira. Não "conserte" pondo um `.limit()` aqui.

O PostgREST não faz GROUP BY: a agregação é em Python, com `Counter`, sobre as
linhas lidas. São ~934 questões e ~1.100 ligações no banco todo — barato, e o
mesmo padrão do `stats/` ao lado.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from supabase import Client

from ..schemas.banco import EstatisticasBanco, MateriaBanco, RecorrenciaTopico, VestibularBanco
from .importancia import carregar_parametro, indice_de_importancia, ranking_0_a_100


def recorrencia(
    cliente: Client,
    materia: MateriaBanco,
    vestibular: VestibularBanco | None = None,
    fase: int | None = None,
) -> EstatisticasBanco:
    """Recorrência de cada tópico da matéria, no recorte pedido.

    Todos os tópicos do edital entram, inclusive os que nunca caíram: "esse
    assunto não apareceu em oito anos" é informação de estudo, e some se a
    lista só trouxer os tópicos com ocorrência.

    Ordem: recorrência decrescente, desempate pela ordem do edital. O front
    pode reordenar (`TabelaOrdenavel`); o default é a leitura que dá nome ao
    endpoint.

    ⚠️ `vestibular` e `fase` estreitam **a resposta inteira** — `porAno`,
    `anos`, `questoesPorAno`, `totalQuestoes` e `semClassificacao` —, e não só
    a contagem por tópico. É o que mantém numerador e denominador no mesmo
    recorte: filtrar só o de cima faria "% da prova" de uma questão de 2ª fase
    ser dividido pela prova inteira, e o número sairia menor que a verdade sem
    nenhum erro na tela. Por isso os dois são parâmetro daqui, e não uma
    peneira no front sobre uma resposta larga.
    """
    questoes = _carregar_questoes(cliente, materia, vestibular, fase)
    ligacoes = _carregar_ligacoes(cliente, materia)
    topicos = _carregar_topicos(cliente, materia)

    questoes_por_id = {questao["id"]: questao for questao in questoes}

    total_por_topico: Counter[str] = Counter()
    por_ano: dict[str, Counter[int]] = defaultdict(Counter)
    por_fase: dict[str, Counter[int]] = defaultdict(Counter)
    por_vestibular: dict[str, Counter[str]] = defaultdict(Counter)
    classificadas: set[str] = set()

    for ligacao in ligacoes:
        questao = questoes_por_id.get(ligacao["questao_id"])
        # Fora do recorte pedido (outro vestibular) — a ligação não sabe filtrar
        # sozinha, ela só guarda questao_id.
        if questao is None:
            continue
        codigo = ligacao["topico_codigo"]
        # Questão mista soma nos DOIS tópicos, de propósito: ela caiu nos dois
        # assuntos, e dividir a ocorrência pela metade subestimaria ambos
        # (docs/22 §1.5). Por isso a soma dos tópicos pode passar do total.
        total_por_topico[codigo] += 1
        por_ano[codigo][int(questao["ano"])] += 1
        por_fase[codigo][int(questao["fase"])] += 1
        por_vestibular[codigo][questao["vestibular"]] += 1
        classificadas.add(questao["id"])

    # ── O índice de importância (docs/34 §3) ──
    #
    # Calculado AQUI, e não no front, para todo mundo ver o mesmo número: é a
    # garantia que a meia-vida fixa compra (docs/24 §4.2), e ela é mais fácil de
    # sustentar com um cálculo só. O front continua desenhando a série.
    #
    # ⚠️ O denominador sai deste mesmo recorte. `vestibular` e `fase` já
    # estreitaram `questoes` lá em cima, então numerador e denominador não têm
    # como divergir — que é justamente o erro silencioso que o docstring de
    # `recorrencia` descreve.
    parametro = carregar_parametro(cliente)
    questoes_por_ano = dict(sorted(Counter(int(q["ano"]) for q in questoes).items()))
    importancias = {
        topico["codigo"]: indice_de_importancia(
            dict(por_ano[topico["codigo"]]), questoes_por_ano, parametro
        )
        for topico in topicos
    }
    ranking = ranking_0_a_100(importancias)

    recorrencias = [
        RecorrenciaTopico(
            codigo=topico["codigo"],
            nome=topico["nome"],
            blocoNome=topico["bloco_nome"],
            total=total_por_topico.get(topico["codigo"], 0),
            porAno=dict(sorted(por_ano[topico["codigo"]].items())),
            porFase=dict(sorted(por_fase[topico["codigo"]].items())),
            porVestibular=dict(sorted(por_vestibular[topico["codigo"]].items())),
            importancia=importancias[topico["codigo"]],
            importanciaRanking=ranking[topico["codigo"]],
        )
        for topico in topicos
    ]
    ordem_no_edital = {topico["codigo"]: int(topico.get("ordem") or 0) for topico in topicos}
    recorrencias.sort(key=lambda r: (-r.total, ordem_no_edital.get(r.codigo, 0), r.codigo))

    return EstatisticasBanco(
        materia=materia,
        topicos=recorrencias,
        # Crescente: esta lista é o eixo x da série temporal por ano.
        #
        # ⚠️ É também o DOMÍNIO da série, e o front tem de preenchê-la contra
        # esta lista: `porAno` só traz os anos com ocorrência, e plotar as
        # chaves do dicionário comprimiria o tempo, sumindo com o buraco — que
        # é justamente a informação. E o domínio começa onde há acervo (o do
        # ITA em 2008, o do IME em 1996 — migration 0031), nunca num ano
        # cravado no código: ausência de prova não é zero.
        anos=sorted({int(questao["ano"]) for questao in questoes}),
        # O denominador de "% da prova": as questões que a banca cobrou em
        # cada ano deste recorte. Um `Counter` sobre as questões já lidas —
        # não sai da soma dos tópicos, porque questão mista soma nos dois de
        # propósito e a soma passa do total (docs/22 §1.5).
        questoesPorAno=questoes_por_ano,
        totalQuestoes=len(questoes),
        # As 40 sem classificação não podem sumir da tela: o aluno estudaria um
        # recorte incompleto sem saber que é incompleto (docs/22 §8, risco 3).
        semClassificacao=len(questoes) - len(classificadas),
        # Com que régua o ranking foi feito. Mesma razão de o Painel mostrar
        # "régua: Tio Leo" ao lado do número: um ranking sem a régua à vista
        # não é conferível.
        meiaVidaAnos=parametro.meia_vida_anos,
        versaoParametro=parametro.versao,
    )


def _carregar_questoes(
    cliente: Client,
    materia: MateriaBanco,
    vestibular: VestibularBanco | None,
    fase: int | None = None,
) -> list[dict[str, Any]]:
    """Só as colunas que a agregação usa. Tabela inteira, sem teto — ver o
    docstring do módulo e docs/22 §2.2.

    O recorte é aplicado AQUI e em nenhum outro lugar: as ligações não sabem
    filtrar sozinhas (só guardam `questao_id`), e o laço de `recorrencia`
    descarta a ligação cuja questão ficou de fora. Estreitar esta consulta
    estreita tudo o que vem depois, de uma vez só.
    """
    consulta = (
        cliente.table("questao_vestibular")
        .select("id, ano, fase, vestibular")
        .eq("materia", materia)
    )
    if vestibular:
        consulta = consulta.eq("vestibular", vestibular)
    if fase is not None:
        consulta = consulta.eq("fase", fase)
    return consulta.execute().data or []


def _carregar_ligacoes(cliente: Client, materia: MateriaBanco) -> list[dict[str, Any]]:
    """Filtra por `materia` na própria ligação (metade da FK composta da 0028):
    sem isso viriam as três matérias, e o código '1.1' de Química somaria no
    '1.1' de Física."""
    return (
        cliente.table("questao_vestibular_topico")
        .select("questao_id, topico_codigo")
        .eq("materia", materia)
        .execute()
        .data
        or []
    )


def _carregar_topicos(cliente: Client, materia: MateriaBanco) -> list[dict[str, Any]]:
    return (
        cliente.table("topico_taxonomia")
        .select("codigo, nome, bloco_nome, ordem")
        .eq("materia", materia)
        .order("ordem")
        .execute()
        .data
        or []
    )
