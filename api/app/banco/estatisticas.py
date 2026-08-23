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


def recorrencia(
    cliente: Client,
    materia: MateriaBanco,
    vestibular: VestibularBanco | None = None,
) -> EstatisticasBanco:
    """Recorrência de cada tópico da matéria, opcionalmente só de um vestibular.

    Todos os tópicos do edital entram, inclusive os que nunca caíram: "esse
    assunto não apareceu em oito anos" é informação de estudo, e some se a
    lista só trouxer os tópicos com ocorrência.

    Ordem: recorrência decrescente, desempate pela ordem do edital. O front
    pode reordenar (`TabelaOrdenavel`); o default é a leitura que dá nome ao
    endpoint.
    """
    questoes = _carregar_questoes(cliente, materia, vestibular)
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

    recorrencias = [
        RecorrenciaTopico(
            codigo=topico["codigo"],
            nome=topico["nome"],
            blocoNome=topico["bloco_nome"],
            total=total_por_topico.get(topico["codigo"], 0),
            porAno=dict(sorted(por_ano[topico["codigo"]].items())),
            porFase=dict(sorted(por_fase[topico["codigo"]].items())),
            porVestibular=dict(sorted(por_vestibular[topico["codigo"]].items())),
        )
        for topico in topicos
    ]
    ordem_no_edital = {topico["codigo"]: int(topico.get("ordem") or 0) for topico in topicos}
    recorrencias.sort(key=lambda r: (-r.total, ordem_no_edital.get(r.codigo, 0), r.codigo))

    return EstatisticasBanco(
        materia=materia,
        topicos=recorrencias,
        # Crescente: esta lista é o eixo x da série temporal por ano.
        anos=sorted({int(questao["ano"]) for questao in questoes}),
        totalQuestoes=len(questoes),
        # As 40 sem classificação não podem sumir da tela: o aluno estudaria um
        # recorte incompleto sem saber que é incompleto (docs/22 §8, risco 3).
        semClassificacao=len(questoes) - len(classificadas),
    )


def _carregar_questoes(
    cliente: Client, materia: MateriaBanco, vestibular: VestibularBanco | None
) -> list[dict[str, Any]]:
    """Só as colunas que a agregação usa. Tabela inteira, sem teto — ver o
    docstring do módulo e docs/22 §2.2."""
    consulta = (
        cliente.table("questao_vestibular")
        .select("id, ano, fase, vestibular")
        .eq("materia", materia)
    )
    if vestibular:
        consulta = consulta.eq("vestibular", vestibular)
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
