"""A missão do dia — um assunto do edital por dia, o MESMO para todos os alunos.

Até 04/09 o cartão da aba Hoje era fixture, e o fixture pareava o código `7.2`
com o nome "Termodinâmica". Na taxonomia de Física, 7.2 é "Ondas e Acústica";
Termodinâmica é 9.1. O cartão imprimia a ETIQUETA do fixture e a fila de treino
consultava o ENDEREÇO no banco real — como o endereço existia e devolvia
questões, nada quebrava: só mentia (docs/35 §9.1).

Daí as três regras deste módulo:

  1. **O nome vem da taxonomia**, na mesma linha de `topico_taxonomia` de onde
     sai o código. Nome escrito à mão em qualquer outro lugar é o bug de volta.
  2. **O sorteio é determinístico pela DATA**, e a data é a de America/Fortaleza
     (docs/35 §9.3). Em UTC o desafio viraria às 21h — e como todos veem o
     mesmo, viraria para todo mundo junto, bem na hora do estudo.
  3. **Só entra tópico com 10 questões RESPONDÍVEIS ou mais** — respondível é o
     que a fila de treino aceita, e são TRÊS condições, não uma
     (`Treino.tsx::respondivel`, lido em 04/09): não ser dissertativa, ter
     gabarito não vazio e ter ao menos uma alternativa. O `totalQuestoes` da
     taxonomia não olha nenhuma delas; cortar por ele — ou só por dissertativa —
     deixaria passar tópico que promete 10 e entrega menos, a mesma classe de
     bug que este módulo existe para consertar. Medido em 04/09 no banco de
     desenvolvimento: 58 dos 65 tópicos passam (Física 18/18 · Matemática 17/21
     · Química 23/26). Pela contagem anterior, que só descartava dissertativa,
     eram 59 — Química 11.3 ("Ácidos e Bases Orgânicas") prometia 10 e a fila
     entregava 9.

⚠️ A missão NÃO é personalizada, e isso é o desenho, não uma etapa faltando.
Era a personalização — `importância × (1 − meu acerto)`, docs/24 §4.5 — que a
prendia a classificar as 1.031 questões de simulado (Sprint 6) e a manteve
mockada até aqui. É também por isso que a razão fala de INCIDÊNCIA NO ACERVO e
nunca de "você acerta 41%": a segunda metade da frase antiga é pessoal e não
sobrevive a um desafio igual para todos (docs/35 §9.3).

⚠️ As 10 questões são o piso do ACERVO, não uma promessa por aluno: a fila de
treino também descarta o que o aluno já marcou como resolvido, e para ele a
sessão pode vir menor. O escape existe na tela ("incluir as que eu já
resolvi"), e é dela — a elegibilidade aqui garante que o assunto tem lastro.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from supabase import Client

from ..schemas.banco import MateriaBanco

# O relógio da escola. Todo aluno do SAS estuda em Fortaleza, e é a virada do
# dia DELE que troca a missão — ver a regra 2 do topo.
FUSO_DA_ESCOLA = ZoneInfo("America/Fortaleza")

# Sempre 10, e o front não escolhe: `Treino.tsx` usa `missao.quantidade` para
# dimensionar a sessão, então um número aqui e outro lá voltariam a ser duas
# verdades sobre a mesma coisa (docs/35 §9.3).
QUESTOES_DA_MISSAO = 10


class MissaoDoDia(BaseModel):
    """O desafio de hoje, em camelCase como o resto da fronteira.

    Espelhado em `web/src/dados/aluno/contratos.ts::MissaoDoDia`. `materia` e
    `topicoCodigo` são o ENDEREÇO que a fila de treino usa para consultar o
    acervo; `nome` é a ETIQUETA que a tela imprime — e as duas saem da mesma
    linha de `topico_taxonomia` de propósito.
    """

    materia: MateriaBanco
    topicoCodigo: str
    nome: str
    quantidade: int
    razao: str


def hoje_na_escola(agora: datetime | None = None) -> date:
    """A data corrente em America/Fortaleza — a semente do sorteio.

    `agora` existe para o teste poder empurrar o relógio; em produção ninguém
    passa nada.
    """
    momento = agora or datetime.now(FUSO_DA_ESCOLA)
    return momento.astimezone(FUSO_DA_ESCOLA).date()


def missao_do_dia(cliente: Client, dia: date | None = None) -> MissaoDoDia | None:
    """O assunto de hoje, igual para todo mundo. `None` quando não há elegível.

    `None` e não erro: acervo sem tópico com lastro é estado possível (banco
    novo, matéria ainda sem classificação), e a aba Hoje já tem a tela para
    ele — o convite "escolha um assunto para treinar". Um 500 aqui viraria uma
    faixa de erro no herói da tela por causa de dado que ninguém prometeu.
    """
    ids_por_topico = ids_respondiveis_por_topico(cliente)
    elegiveis = topicos_elegiveis(cliente, ids_por_topico)
    if not elegiveis:
        return None

    escolhido = sortear(elegiveis, dia or hoje_na_escola())

    # UNIÃO dos ids da matéria, e não soma das contagens por tópico: 564 das
    # 1.410 questões respondíveis do acervo estão em dois ou mais tópicos da
    # MESMA matéria (medido em 04/09), e a soma contaria cada uma delas uma vez
    # por tópico. O denominador inflava ~40% (Matemática: 738 ligações para 510
    # questões) e a frase impressa dizia "questões" mostrando uma proporção de
    # ligações — encolhida em torno de 30%.
    ids_da_materia: set[str] = set()
    for (materia, _), ids in ids_por_topico.items():
        if materia == escolhido["materia"]:
            ids_da_materia |= ids

    return MissaoDoDia(
        materia=escolhido["materia"],
        topicoCodigo=escolhido["codigo"],
        nome=escolhido["nome"],
        quantidade=QUESTOES_DA_MISSAO,
        razao=_razao(escolhido, len(ids_da_materia)),
    )


# ─── Elegibilidade ───────────────────────────────────────────────────────


def ids_respondiveis_por_topico(cliente: Client) -> dict[tuple[str, str], set[str]]:
    """{(materia, codigo): ids das questões que a FILA DE TREINO aceita}.

    Respondível é o que `Treino.tsx::respondivel` deixa entrar na sessão, e são
    três condições: `dissertativa = false`, gabarito não vazio e ao menos uma
    alternativa. Contar só a primeira — como a versão anterior desta função
    fazia — devolve um lastro maior do que a sessão consegue entregar: no acervo
    de 04/09 são 92 objetivas que a fila descarta, 70 sem gabarito e 22 sem
    alternativa. Prometer 10 sobre elas é a mentira de docs/35 §9.1 com outra
    roupa: o cartão promete um número que a sessão não tem como cumprir.

    Devolve os IDS, e não a contagem: uma questão tem uma linha por tópico, e é
    o conjunto que deixa quem chama juntar tópicos — o denominador da razão faz
    isso — sem contar ninguém duas vezes.

    Sem `.limit()` e sem paginação, como todo agregador de `app/banco/`: leitura
    truncada aqui devolveria um lastro menor do que o real e o tópico sumiria do
    sorteio sem erro nenhum (armadilha 2 do CLAUDE.md).
    """
    respondiveis = {
        linha["id"]
        for linha in (
            cliente.table("questao_vestibular")
            # A alternativa é tabela filha (0028), não coluna: vem por embed do
            # PostgREST, como em `consultas.py`. Só a letra — o que importa aqui
            # é existir alguma, e o texto multiplicaria o payload por nada.
            .select("id, gabarito, questao_vestibular_alternativa(letra)")
            .eq("dissertativa", False)
            .execute()
            .data
            or []
        )
        # `.strip()` porque é assim que `dominio/banco.ts::temGabarito` decide:
        # gabarito em branco não é letra a conferir, e a sessão pararia numa
        # questão sem correção possível.
        if (linha.get("gabarito") or "").strip()
        and (linha.get("questao_vestibular_alternativa") or [])
    }

    ligacoes = (
        cliente.table("questao_vestibular_topico")
        .select("questao_id, materia, topico_codigo")
        .execute()
        .data
        or []
    )

    ids_por_topico: dict[tuple[str, str], set[str]] = defaultdict(set)
    for ligacao in ligacoes:
        if ligacao["questao_id"] in respondiveis:
            ids_por_topico[(ligacao["materia"], ligacao["topico_codigo"])].add(
                ligacao["questao_id"]
            )
    # `dict` e não o defaultdict: quem consulta um tópico sem lastro deve levar
    # o default explícito, não criar chave nova por leitura.
    return dict(ids_por_topico)


def topicos_elegiveis(
    cliente: Client, ids_por_topico: dict[tuple[str, str], set[str]]
) -> list[dict[str, Any]]:
    """Os tópicos que podem ser sorteados, em ordem canônica e estável.

    A ordem é (materia, ordem do edital, codigo), e ela importa: o sorteio é um
    índice sobre esta lista, então uma ordem que dançasse entre requisições daria
    missões diferentes no mesmo dia — que é justamente o que "o mesmo desafio
    para todos" proíbe. `ordem` sozinha não basta porque ela é por matéria.

    A LISTA MUDA quando o acervo cresce: tópico novo elegível desloca o rodízio.
    É o preço de não gravar o sorteio em tabela, e é aceitável — o que não pode
    variar é a missão DENTRO de um dia.
    """
    linhas = (
        cliente.table("topico_taxonomia")
        .select("materia, codigo, nome, ordem")
        .execute()
        .data
        or []
    )
    lastro = {
        (linha["materia"], linha["codigo"]): len(
            ids_por_topico.get((linha["materia"], linha["codigo"]), set())
        )
        for linha in linhas
    }
    elegiveis = [
        {
            "materia": linha["materia"],
            "codigo": linha["codigo"],
            "nome": linha["nome"],
            "respondiveis": lastro[(linha["materia"], linha["codigo"])],
        }
        for linha in linhas
        if lastro[(linha["materia"], linha["codigo"])] >= QUESTOES_DA_MISSAO
    ]
    indice_da_ordem = {
        (linha["materia"], linha["codigo"]): int(linha.get("ordem") or 0) for linha in linhas
    }
    return sorted(
        elegiveis,
        key=lambda t: (
            t["materia"],
            indice_da_ordem[(t["materia"], t["codigo"])],
            t["codigo"],
        ),
    )


# ─── Sorteio ─────────────────────────────────────────────────────────────


def sortear(elegiveis: list[dict[str, Any]], dia: date) -> dict[str, Any]:
    """O tópico do dia. Mesma data e mesmo acervo ⇒ mesmo tópico, sempre.

    Rodízio, não sorteio com reposição: os dias são cortados em ciclos do
    tamanho da lista, e cada ciclo é uma PERMUTAÇÃO dela. Assim o assunto só
    repete depois de todos os outros terem saído — com os 58 elegíveis medidos
    em 04/09, quase dois meses — enquanto um `hash % n` repetiria em poucos dias
    por acaso e deixaria tópicos sem nunca aparecer.
    """
    quantos = len(elegiveis)
    ciclo, posicao = divmod(dia.toordinal(), quantos)
    return elegiveis[_permutacao_do_ciclo(quantos, ciclo)[posicao]]


def _permutacao_do_ciclo(quantos: int, ciclo: int) -> list[int]:
    """Os índices embaralhados de um ciclo, de forma reprodutível.

    Ordenar por digest em vez de `random.shuffle`: a sequência do `random` do
    Python não é garantida entre versões, e uma missão que trocasse de assunto
    quando a imagem da API é reconstruída deixaria de ser a mesma para todo
    mundo — que é a única coisa que este módulo promete. SHA-256 aqui é função
    de embaralhamento, não de segurança.
    """
    return sorted(
        range(quantos),
        key=lambda i: hashlib.sha256(f"{ciclo}:{i}".encode()).digest(),
    )


# ─── A razão ─────────────────────────────────────────────────────────────


def _razao(escolhido: dict[str, Any], respondiveis_da_materia: int) -> str:
    """Por que este assunto — e só o que é verificável.

    A frase antiga tinha duas metades ("Cai em 7% da prova do ITA. Você acerta
    41%.") e só a primeira sobrevive: a incidência sai do acervo, o acerto é
    pessoal e não existe num desafio igual para todos (docs/35 §9.3).

    O denominador é a MATÉRIA, e não o acervo inteiro: "3% de tudo que já caiu"
    misturaria Física com Química e não se leria sozinho. E é o MESMO conjunto
    do numerador — questões que dá para treinar, não todas as objetivas —,
    porque régua diferente nas duas pontas daria uma proporção que não é de
    coisa nenhuma.
    """
    fatia = (
        escolhido["respondiveis"] / respondiveis_da_materia if respondiveis_da_materia else 0
    )
    percentual = round(fatia * 100)
    quanto = f"{percentual}%" if percentual >= 1 else "menos de 1%"
    return (
        f"{quanto} das questões de {escolhido['materia']} que dá para treinar no acervo "
        f"de ITA e IME são deste assunto — {escolhido['respondiveis']} no total. "
        "O desafio de hoje é o mesmo para toda a turma."
    )
