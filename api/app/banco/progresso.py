"""Progresso do aluno no acervo ITA · IME — o que ele marcou, de quanto existe.

Responde "quanto do banco eu já fiz", em três recortes: por matéria, por assunto
do edital e por ano de prova. É o que alimenta a tela **Meu progresso**.

**Por que existe uma rota agregada, se `GET /banco/estudo` já devolve as linhas
do aluno.** Porque aquela devolve as linhas CRUAS, sem nenhum atributo da
questão: para montar esta tela o celular teria de baixar as ~2.700 questões do
acervo, cruzar com as marcações no navegador e só então contar. Numa rede de
escola isso é a diferença entre uma tela que abre e uma que não abre. A
agregação é barata aqui — são duas leituras de coluna única e um `Counter`, o
mesmo padrão de `estatisticas.py` ao lado.

⚠️ **Sem paginação e sem teto, como todo agregador do projeto.** É a armadilha 2
do CLAUDE.md: uma leitura truncada devolveria "168 de 400" no lugar de "168 de
842" — número errado, sem nada na tela parecendo errado. Quem pagina é
`GET /banco/questoes`, e lá a resposta é navegação (docs/22 §2.2).

⚠️ **"Feitas" é `resolvida`, que é AUTO-DECLARADO.** O aluno aperta "Marcar
resolvida" e ninguém confere nada. Este módulo não sabe, e não deve saber, se
ele acertou: acerto de treino é `questao_estudo_aluno.acertou` (0042) e acerto
de prova é outra fonte inteira (o simulado, via Canvas). Somar as três, ou tirar
média entre elas, produz um número que não significa coisa nenhuma.

⚠️ **Ausência de linha = não tocado**, e é a maioria — é justamente a informação
principal da tela. Por isso a contagem parte do ACERVO e marca o que o aluno
fez, nunca o contrário: partir das marcações faria a tela abrir vazia para quem
tem zero e não ter denominador nenhum para mostrar.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from supabase import Client

from ..schemas.banco import (
    ProgressoDoAluno,
    ProgressoPorAno,
    ProgressoPorAssunto,
    ProgressoPorMateria,
)
from .consultas import TOPICO_SEM_CLASSIFICACAO

# O rótulo da linha das órfãs. Fica aqui, e não no front, porque acompanha o
# código sentinela que a torna clicável — os dois viajam juntos ou a linha vira
# um número que o aluno vê e não consegue abrir (docs/22 §1.4).
NOME_SEM_CLASSIFICACAO = "Sem classificação de assunto"


def progresso_do_aluno(cliente: Client, aluno_id: str) -> ProgressoDoAluno:
    """Os três recortes de uma vez, cada um já com o seu denominador.

    Uma resposta só, e não uma rota por recorte: os três saem exatamente das
    mesmas duas leituras, e três chamadas dariam ao celular a chance de mostrar
    "168 de 842" numa seção e um total diferente na seção de baixo, se uma
    delas falhasse.
    """
    questoes = _carregar_questoes(cliente)
    ligacoes = _carregar_ligacoes(cliente)
    topicos = _carregar_topicos(cliente)
    feitas = _ids_resolvidas(cliente, aluno_id)

    # Só as marcações que apontam para questão existente. Uma questão apagada
    # do acervo deixa a linha de estudo órfã (o ON DELETE CASCADE da 0029 cuida
    # disso no banco, mas a leitura não depende de ter cuidado): contá-la faria
    # `feitas` passar de `total`, e uma barra de 103% parece bug de código.
    por_id = {q["id"]: q for q in questoes}
    feitas = feitas & por_id.keys()

    return ProgressoDoAluno(
        feitas=len(feitas),
        total=len(questoes),
        porMateria=_por_materia(questoes, feitas),
        porAssunto=_por_assunto(questoes, ligacoes, topicos, feitas),
        porAno=_por_ano(questoes, feitas),
        # Crescente: é o eixo x da grade. O ano sem marcação continua na lista,
        # senão a grade comprime o tempo e o buraco — que é a informação — some.
        anos=sorted({int(q["ano"]) for q in questoes}),
    )


def _por_materia(
    questoes: list[dict[str, Any]], feitas: set[str]
) -> list[ProgressoPorMateria]:
    """Maior buraco primeiro: é a ordem que a tela usa, e ela é uma decisão de
    produto, não de componente. Ordenar no front trocaria a régua por uma
    ordenação local, e duas telas mostrariam prioridades diferentes."""
    total: Counter[str] = Counter()
    marcadas: Counter[str] = Counter()
    for questao in questoes:
        materia = questao["materia"]
        total[materia] += 1
        if questao["id"] in feitas:
            marcadas[materia] += 1

    linhas = [
        ProgressoPorMateria(
            materia=materia,  # type: ignore[arg-type]
            feitas=marcadas.get(materia, 0),
            total=quantas,
        )
        for materia, quantas in total.items()
    ]
    linhas.sort(key=lambda l: (-(l.total - l.feitas), l.materia))
    return linhas


def _por_assunto(
    questoes: list[dict[str, Any]],
    ligacoes: list[dict[str, Any]],
    topicos: list[dict[str, Any]],
    feitas: set[str],
) -> list[ProgressoPorAssunto]:
    """Todo tópico do edital entra, inclusive o que o aluno nunca abriu — e
    inclusive o que nunca caiu, com `total = 0`.

    ⚠️ A soma dos assuntos PASSA do total da matéria, e é de propósito: questão
    mista soma nos dois tópicos, porque ela caiu nos dois assuntos e dividir a
    ocorrência pela metade subestimaria ambos (docs/22 §1.5). É por isso que
    esta lista não vira pizza, rosca nem barra empilhada em 100%: fechariam em
    mais de 100% e pareceriam defeito.
    """
    por_id = {q["id"]: q for q in questoes}

    ids_do_topico: dict[tuple[str, str], set[str]] = defaultdict(set)
    classificadas_por_materia: dict[str, set[str]] = defaultdict(set)
    for ligacao in ligacoes:
        questao = por_id.get(ligacao["questao_id"])
        if questao is None:
            continue
        # A ligação guarda `materia` por conta própria — é metade da FK composta
        # da 0028 — e uma divergência entre ela e a da questão contaria a
        # questão na matéria errada. Vale a da QUESTÃO.
        materia = questao["materia"]
        ids_do_topico[(materia, ligacao["topico_codigo"])].add(questao["id"])
        classificadas_por_materia[materia].add(questao["id"])

    linhas = [
        ProgressoPorAssunto(
            materia=topico["materia"],
            codigo=topico["codigo"],
            nome=topico["nome"],
            blocoNome=topico["bloco_nome"] or "",
            feitas=len(ids_do_topico[(topico["materia"], topico["codigo"])] & feitas),
            total=len(ids_do_topico[(topico["materia"], topico["codigo"])]),
        )
        for topico in topicos
    ]

    # As que ninguém classificou não podem sumir: o aluno leria um recorte
    # incompleto sem saber que é incompleto (docs/22 §8, risco 3). Entram como
    # uma linha por matéria, com o código sentinela que `GET /banco/questoes`
    # aceita — então ela abre, como qualquer outra.
    por_materia: dict[str, set[str]] = defaultdict(set)
    for questao in questoes:
        por_materia[questao["materia"]].add(questao["id"])
    for materia, todas in sorted(por_materia.items()):
        orfas = todas - classificadas_por_materia[materia]
        if not orfas:
            continue
        linhas.append(
            ProgressoPorAssunto(
                materia=materia,  # type: ignore[arg-type]
                codigo=TOPICO_SEM_CLASSIFICACAO,
                nome=NOME_SEM_CLASSIFICACAO,
                blocoNome="",
                feitas=len(orfas & feitas),
                total=len(orfas),
            )
        )

    linhas.sort(key=lambda l: (l.materia, -(l.total - l.feitas), l.nome))
    return linhas


def _por_ano(questoes: list[dict[str, Any]], feitas: set[str]) -> list[ProgressoPorAno]:
    """A grade matéria × ano.

    Só entra o par que EXISTE no acervo. A célula ausente é "não houve prova
    dessa matéria nesse ano" — e a tela precisa poder desenhá-la diferente de
    "houve prova e você não fez nenhuma". Emitir `0 de 0` apagaria a diferença,
    e o aluno leria buraco de acervo como buraco de estudo (migration 0031: o
    acervo do IME começa em 1996 e o do ITA em 2008).
    """
    total: Counter[tuple[str, int]] = Counter()
    marcadas: Counter[tuple[str, int]] = Counter()
    for questao in questoes:
        chave = (questao["materia"], int(questao["ano"]))
        total[chave] += 1
        if questao["id"] in feitas:
            marcadas[chave] += 1

    return [
        ProgressoPorAno(
            materia=materia,  # type: ignore[arg-type]
            ano=ano,
            feitas=marcadas.get((materia, ano), 0),
            total=quantas,
        )
        for (materia, ano), quantas in sorted(total.items())
    ]


# ─── Leitura crua ────────────────────────────────────────────────────────


def _carregar_questoes(cliente: Client) -> list[dict[str, Any]]:
    """O acervo inteiro, só com o que a contagem usa. Sem teto — é o
    denominador, e truncá-lo devolveria progresso errado sem parecer errado."""
    return (
        cliente.table("questao_vestibular").select("id, materia, ano").execute().data or []
    )


def _carregar_ligacoes(cliente: Client) -> list[dict[str, Any]]:
    return (
        cliente.table("questao_vestibular_topico")
        .select("questao_id, materia, topico_codigo")
        .execute()
        .data
        or []
    )


def _carregar_topicos(cliente: Client) -> list[dict[str, Any]]:
    return (
        cliente.table("topico_taxonomia")
        .select("materia, codigo, nome, bloco_nome, ordem")
        .order("ordem")
        .execute()
        .data
        or []
    )


def _ids_resolvidas(cliente: Client, aluno_id: str) -> set[str]:
    """As questões que ESTE aluno marcou como resolvidas.

    ⚠️ `aluno_id` vem do token e de nenhum outro lugar — a rota usa
    `get_current_aluno`. É dado pessoal de menor de idade; aceitar o id pela URL
    poria o progresso de qualquer aluno a um número de distância.

    Filtra `resolvida = true` no servidor: uma linha pode existir só por causa
    de uma anotação ou de uma resposta de treino, e contá-la como feita
    inflaria o numerador sem que ninguém tivesse marcado nada.
    """
    linhas = (
        cliente.table("questao_estudo_aluno")
        .select("questao_id")
        .eq("aluno_id", aluno_id)
        .eq("resolvida", True)
        .execute()
        .data
        or []
    )
    return {linha["questao_id"] for linha in linhas}
