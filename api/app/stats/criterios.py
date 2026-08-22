"""Critérios de classificação — a régua do corte, num arquivo só.

Este módulo é a **única** definição de "quem passou". Antes dela a mesma regra
existia três vezes e já havia divergido: `TabelaPainel.tsx` pintava vermelho
abaixo de 5,0, `painel.ts` cortava abaixo de 5,0 e `thresholds.py` cortava
abaixo de 4,0 — e nenhum dos três implementava a regra real do ITA ou do IME
(docs/18 §1.1).

A regra é **dado, não código**: um `Criterio` é uma lista de `Predicado`, e a
régua pedagógica do colégio, a do ITA e a do IME são três valores do mesmo
formato. Isso é o que permitirá o coordenador criar as dele pela tela sem que
nenhum operador precise ser reescrito (docs/18 §1.10).

O avaliador é **puro**: não lê banco, não faz I/O. Quem carrega as notas é o
chamador. Isso o torna testável sem container e é o motivo de as notas entrarem
como `Mapping`, e não como `Client`.

Onde estão as regras: §1.5 do docs/18-plano-sprint-2.md. Cada predicado cita o
artigo do edital que o originou.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ─── Vocabulário ──────────────────────────────────────────────────────────

#: Média geral, e não uma matéria específica.
MEDIA_GERAL = None

#: Todas as matérias observadas, sem enumerar (usado pela régua do colégio,
#: que fala em "qualquer disciplina" em vez de listar).
TODAS = "*"

#: Pseudo-matéria: a média da 1ª fase entrando na média geral da 2ª.
#: O ITA compõe a média final com 20% da 1ª fase + 20% de cada uma das quatro
#: provas da 2ª (ITA §4.7) — modelar a 1ª fase como um "componente" de peso
#: igual é o que faz os cinco 20% caírem naturalmente.
FASE_1 = "fase_1"


@dataclass(frozen=True)
class Acertos:
    """Mínimo expresso em questões certas, não em nota.

    Os dois editais falam em acertos: o ITA pede 5 de 12 (§4.6.2.1) e o IME
    pede 4 de 10 em Química (Art. 40, IV). Guardar "4,1667" no lugar de "5 de
    12" dá veredito errado quando o simulado tem um número de questões
    diferente da prova real — e simulado com 10 ou 20 questões é o caso comum
    aqui, não a exceção.
    """

    acertos: int
    de: int

    @property
    def como_nota(self) -> float:
        """O mesmo mínimo na escala 0–10, para quando só a nota está disponível."""
        return self.acertos / self.de * 10


@dataclass(frozen=True)
class Predicado:
    """Um requisito. Falhar nele é ruim; o `Criterio` decide o que isso causa."""

    materia: str | None
    valor: float | Acertos
    operador: str = ">="
    #: Reprova sozinho, ignorando o combinador do critério. É o que faz o
    #: inglês do ITA eliminar na 1ª fase sem participar do "E" da régua.
    eliminatorio: bool = False
    #: Cobrado, mas fora do cálculo da média. ITA §4.6.5: "A pontuação de
    #: Inglês não é classificatória, portanto, não entra no cálculo da média."
    entra_na_media: bool = True
    #: O IME usa média ponderada (Art. 37, III); o ITA usa 20% para cada
    #: componente, que é peso igual.
    peso: float = 1.0
    #: Artigo do edital, ou de onde a regra veio. Aparece no motivo do corte.
    fonte: str = ""


@dataclass(frozen=True)
class Criterio:
    """Uma régua completa: o que se exige, como as falhas somam, e como ordenar."""

    slug: str
    nome: str
    #: Como as falhas dos predicados NÃO eliminatórios combinam para cortar:
    #:   "algum" → basta uma falhar (é o que os dois editais mandam)
    #:   "todos" → só corta se todas falharem (a régua pedagógica do colégio)
    combinador: str
    predicados: tuple[Predicado, ...]
    #: Ordem de precedência do desempate, por código de matéria.
    #: "media" é a média geral do próprio critério.
    desempate: tuple[str, ...] = ()
    fase: int | None = None
    descricao: str = ""


@dataclass(frozen=True)
class NotaDaMateria:
    """A nota de um aluno numa matéria, com os acertos quando conhecidos.

    `nota` está sempre em 0–10 (já normalizada por `utils.nota_real`).
    `acertos`/`total` vêm de `nota.pontuacao` e `simulado.nota_maxima`, que no
    Canvas são literalmente questões certas e número de questões.
    """

    nota: float
    acertos: float | None = None
    total: float | None = None


@dataclass(frozen=True)
class Veredito:
    aprovado: bool
    #: Legível: "Química 3,2 — mínimo 4,0 (ITA §4.6.6.5)". É o que transforma
    #: uma linha vermelha em "cortado por Química", que é a tese do produto.
    motivo: str | None
    media: float | None
    #: Chave de ordenação já pronta: o primeiro item separa não-cortados de
    #: cortados, o resto é o desempate em cascata. Maior é melhor.
    ordenacao: tuple[float, ...] = field(default_factory=tuple)


# ─── Avaliação ────────────────────────────────────────────────────────────


def _satisfaz(nota: NotaDaMateria, predicado: Predicado) -> bool:
    """O aluno cumpre este requisito?

    Compara em acertos quando o predicado é expresso em acertos E a prova
    informou o total; senão cai para a nota 0–10. A diferença importa: 4 de 12
    é 3,33 e 5 de 12 é 4,17 — comparar "4,17" contra uma prova de 10 questões
    aprovaria quem acertou 5 quando o edital exige proporção maior.
    """
    if isinstance(predicado.valor, Acertos):
        if nota.acertos is not None and nota.total == predicado.valor.de:
            esquerda, direita = nota.acertos, predicado.valor.acertos
        else:
            esquerda, direita = nota.nota, predicado.valor.como_nota
    else:
        esquerda, direita = nota.nota, predicado.valor

    if predicado.operador == ">=":
        return esquerda >= direita
    if predicado.operador == ">":
        return esquerda > direita
    if predicado.operador == "<=":
        return esquerda <= direita
    if predicado.operador == "<":
        return esquerda < direita
    raise ValueError(f"operador desconhecido: {predicado.operador!r}")


def _materias_avaliadas(
    predicado: Predicado, notas: dict[str, NotaDaMateria], criterio: Criterio
) -> list[str]:
    """Quais matérias este predicado cobra.

    `TODAS` expande para tudo que o aluno fez, menos o que outro predicado
    tirou da conta explicitamente — é assim que a régua do colégio diz
    "qualquer disciplina" e ainda deixa o inglês de fora da média.
    """
    if predicado.materia is MEDIA_GERAL:
        return []
    if predicado.materia != TODAS:
        return [predicado.materia]
    tratadas = {p.materia for p in criterio.predicados if p.materia not in (TODAS, MEDIA_GERAL)}
    return [codigo for codigo in notas if codigo not in tratadas]


def media_do_criterio(criterio: Criterio, notas: dict[str, NotaDaMateria]) -> float | None:
    """Média geral **segundo este critério** — nem toda matéria conta igual.

    Duas coisas mudam de régua para régua, e é por isso que a média não pode
    ser calculada fora daqui:

      - **quem entra:** o inglês do ITA é cobrado e fica fora (ITA §4.6.5); o
        do IME entra com peso 1 (Art. 37, III).
      - **quanto pesa:** o IME pondera 3 / 2,5 / 2,5 / 1 / 1; o ITA dá 20% a
        cada um dos cinco componentes, que é peso igual.

    Devolve None quando o aluno não tem nenhuma matéria que conte.
    """
    explicitos = [
        p
        for p in criterio.predicados
        if p.entra_na_media and p.materia not in (TODAS, MEDIA_GERAL)
    ]

    if explicitos:
        pares = [
            (notas[p.materia].nota, p.peso) for p in explicitos if p.materia in notas
        ]
    else:
        # Régua sem matérias enumeradas: entra tudo que o aluno fez, menos o
        # que algum predicado excluiu (o inglês do "Tio Leo").
        fora = {
            p.materia
            for p in criterio.predicados
            if not p.entra_na_media and p.materia not in (TODAS, MEDIA_GERAL)
        }
        pares = [(n.nota, 1.0) for codigo, n in notas.items() if codigo not in fora]

    peso_total = sum(peso for _, peso in pares)
    if peso_total == 0:
        return None
    return sum(nota * peso for nota, peso in pares) / peso_total


def _descrever(materia: str, nota: NotaDaMateria, predicado: Predicado) -> str:
    alvo = (
        f"{predicado.valor.acertos} de {predicado.valor.de} acertos"
        if isinstance(predicado.valor, Acertos)
        else f"{predicado.valor:.1f}".replace(".", ",")
    )
    obtido = f"{nota.nota:.1f}".replace(".", ",")
    sufixo = f" ({predicado.fonte})" if predicado.fonte else ""
    return f"{materia} {obtido} — mínimo {alvo}{sufixo}"


def avaliar(criterio: Criterio, notas: dict[str, NotaDaMateria]) -> Veredito:
    """Aplica um critério às notas de um aluno.

    Ordem importa: os eliminatórios são checados primeiro porque reprovam
    sozinhos, sem consultar o combinador — é o inglês do ITA na 1ª fase
    (§4.6.2.1) e a redação INAPTA do IME (Art. 65).

    Aluno sem nota nenhuma volta **aprovado com média None**, não cortado:
    ausência de dado não é mau desempenho, e tratá-la como corte foi o que já
    inflou o KPI "em zona de corte" uma vez (painel.ts §statusAluno).
    """
    media = media_do_criterio(criterio, notas)

    falhas: list[str] = []
    avaliou_algum = False

    for predicado in criterio.predicados:
        if predicado.materia is MEDIA_GERAL:
            if media is None:
                continue
            avaliou_algum = True
            alvo = NotaDaMateria(nota=media)
            if not _satisfaz(alvo, predicado):
                descricao = _descrever("Média geral", alvo, predicado)
                if predicado.eliminatorio:
                    return Veredito(False, descricao, media, _ordenar(False, criterio, notas, media))
                falhas.append(descricao)
            continue

        falhou_aqui: list[str] = []
        for codigo in _materias_avaliadas(predicado, notas, criterio):
            nota = notas.get(codigo)
            if nota is None:
                continue  # matéria não prestada não penaliza nem premia
            avaliou_algum = True
            if not _satisfaz(nota, predicado):
                falhou_aqui.append(_descrever(codigo.capitalize(), nota, predicado))

        if falhou_aqui and predicado.eliminatorio:
            return Veredito(
                False, falhou_aqui[0], media, _ordenar(False, criterio, notas, media)
            )
        # "Alguma disciplina abaixo do mínimo" é UMA falha, ainda que várias
        # matérias tenham falhado — senão o combinador "todos" nunca fecharia.
        if falhou_aqui:
            falhas.append(falhou_aqui[0])

    if not avaliou_algum:
        return Veredito(True, None, media, _ordenar(True, criterio, notas, media))

    requisitos = sum(
        1
        for p in criterio.predicados
        if not p.eliminatorio and (p.materia is not MEDIA_GERAL or media is not None)
    )
    if criterio.combinador == "todos":
        cortado = len(falhas) >= requisitos and bool(falhas)
    elif criterio.combinador == "algum":
        cortado = bool(falhas)
    else:
        raise ValueError(f"combinador desconhecido: {criterio.combinador!r}")

    return Veredito(
        aprovado=not cortado,
        motivo="; ".join(falhas) if cortado else None,
        media=media,
        ordenacao=_ordenar(not cortado, criterio, notas, media),
    )


def _ordenar(
    aprovado: bool,
    criterio: Criterio,
    notas: dict[str, NotaDaMateria],
    media: float | None,
) -> tuple[float, ...]:
    """Chave de ordenação decrescente: primeiro o bloco, depois o desempate.

    O primeiro elemento separa aprovados de cortados porque a coordenação pediu
    dois blocos: *"o cara pode ter a maior nota; se levou corte na matéria, fica
    depois do que não levou corte nenhum"* (docs/18 §1.6). Os demais seguem a
    ordem de precedência do edital — ITA §4.9.1.3, IME Art. 70 §2º.
    """
    chave = [1.0 if aprovado else 0.0]
    for termo in criterio.desempate:
        if termo == "media":
            chave.append(media if media is not None else float("-inf"))
        else:
            nota = notas.get(termo)
            chave.append(nota.nota if nota else float("-inf"))
    return tuple(chave)


# ─── Cor da célula ────────────────────────────────────────────────────────

#: Acima do corte por esta margem, a nota é confortável. Sai de "4,0 não é
#: corte, acho que deveria ser amarelo também" (Leo, 21/08 18h56): com corte
#: 4,0 isso faz 4,0–5,0 âmbar e ≥ 5,0 verde.
MARGEM_CONFORTAVEL = 1.0


def tom_da_nota(criterio: Criterio, materia: str, nota: float) -> str:
    """verde / ambar / vermelho — derivado do corte do próprio critério.

    Substitui o ternário fixo de `TabelaPainel.tsx`, que pintava vermelho
    abaixo de 5,0 sem relação nenhuma com a régua em uso.
    """
    corte = corte_da_materia(criterio, materia)
    if corte is None:
        return "verde" if nota >= 7 else "ambar" if nota >= 5 else "vermelho"
    if nota < corte:
        return "vermelho"
    if nota < corte + MARGEM_CONFORTAVEL:
        return "ambar"
    return "verde"


def corte_da_materia(criterio: Criterio, materia: str) -> float | None:
    """O mínimo que este critério exige nesta matéria, em 0–10."""
    generico: float | None = None
    for predicado in criterio.predicados:
        if predicado.materia is MEDIA_GERAL:
            continue
        valor = (
            predicado.valor.como_nota
            if isinstance(predicado.valor, Acertos)
            else float(predicado.valor)
        )
        if predicado.materia == materia:
            return valor
        if predicado.materia == TODAS:
            generico = valor
    return generico


# ─── Os três critérios embutidos ──────────────────────────────────────────
#
# Escritos como literais, e não carregados de lugar nenhum, porque é aqui que
# se lê e se altera a regra. A tabela `criterio_classificacao` (migration 0023)
# guarda os que o coordenador criar pela tela; estes são a semente dela.
#
# Um detalhe que não é óbvio: os PESOS reproduzem a conta do edital em vez de
# aproximá-la. Média ponderada das notas normalizadas com pesos iguais ao
# número de questões dá exatamente "acertos totais ÷ questões totais × 10" —
# que é a redação literal do ITA §4.6.5 e do IME Art. 40, I.


TIO_LEO = Criterio(
    slug="tio-leo",
    nome="Tio Leo",
    descricao=(
        "A régua pedagógica do Ari, ditada pela coordenação em 21/08/2026. "
        "Diverge dos editais de propósito: corta com E, não com OU."
    ),
    combinador="todos",
    predicados=(
        Predicado(TODAS, 4.0, fonte="régua do colégio: 40% da prova"),
        Predicado(MEDIA_GERAL, 5.0, fonte="régua do colégio: 50% da média"),
        # Eliminatório e fora da média — os dois de uma vez. Confirmado pela
        # coordenação em 22/08 e coerente com o ITA §4.6.5.
        Predicado(
            "ingles",
            4.0,
            eliminatorio=True,
            entra_na_media=False,
            fonte="eliminatório, fora da média",
        ),
    ),
    desempate=("media", "matematica", "fisica", "quimica", "ingles"),
)


ITA_FASE_1 = Criterio(
    slug="ita-f1",
    nome="ITA — Fase 1",
    fase=1,
    descricao="48 questões: 12 de Matemática, Física, Química e Inglês (§4.1.2).",
    combinador="algum",
    predicados=(
        Predicado("matematica", Acertos(5, 12), fonte="ITA §4.6.2.1"),
        Predicado("fisica", Acertos(5, 12), fonte="ITA §4.6.2.1"),
        Predicado("quimica", Acertos(5, 12), fonte="ITA §4.6.2.1"),
        # Cobrado como os outros, mas fora da média: "A pontuação de Inglês não
        # é classificatória, portanto, não entra no cálculo da média" (§4.6.5).
        Predicado(
            "ingles",
            Acertos(5, 12),
            entra_na_media=False,
            fonte="ITA §4.6.2.1 e §4.6.5",
        ),
        Predicado(MEDIA_GERAL, 5.0, fonte="ITA §4.6.2.2"),
    ),
    desempate=("media", "matematica", "fisica", "quimica"),
)


ITA_FASE_2 = Criterio(
    slug="ita-f2",
    nome="ITA — Fase 2",
    fase=2,
    descricao=(
        "Média final: 20% da 1ª fase + 20% de cada uma das quatro provas "
        "da 2ª (§4.7). Habilitado exige média ≥ 5,0 E ≥ 4,0 em cada (§4.9.1.1)."
    ),
    combinador="algum",
    predicados=(
        Predicado("matematica", 4.0, fonte="ITA §4.6.6.5"),
        Predicado("fisica", 4.0, fonte="ITA §4.6.6.5"),
        Predicado("quimica", 4.0, fonte="ITA §4.6.6.5"),
        Predicado("portugues", 4.0, fonte="ITA §4.6.6.5"),
        # A 1ª fase é o quinto componente de 20% da média final. Não impõe
        # mínimo aqui (quem não passou nela não chega à 2ª), só pesa.
        Predicado(FASE_1, 0.0, fonte="ITA §4.7"),
        # A redação elimina sozinha e não é média: §4.6.6.3.1.
        Predicado(
            "redacao",
            4.0,
            eliminatorio=True,
            entra_na_media=False,
            fonte="ITA §4.6.6.3.1",
        ),
        Predicado(MEDIA_GERAL, 5.0, fonte="ITA §4.9.1.1"),
    ),
    desempate=("media", "matematica", "fisica", "quimica", "portugues"),
)


IME_FASE_1 = Criterio(
    slug="ime-f1",
    nome="IME — Fase 1",
    fase=1,
    descricao=(
        "40 questões: 15 de Matemática, 15 de Física, 10 de Química (Art. 38). "
        "Sem Português e sem Inglês."
    ),
    combinador="algum",
    predicados=(
        # Pesos = número de questões, para a média reproduzir "menos de vinte
        # respostas certas em toda a prova" (Art. 40, I) sem aproximação.
        Predicado("matematica", Acertos(6, 15), peso=15, fonte="IME Art. 40, II"),
        Predicado("fisica", Acertos(6, 15), peso=15, fonte="IME Art. 40, III"),
        Predicado("quimica", Acertos(4, 10), peso=10, fonte="IME Art. 40, IV"),
        Predicado(MEDIA_GERAL, 5.0, fonte="IME Art. 40, I"),
    ),
    desempate=("media", "matematica", "fisica", "quimica"),
)


IME_FASE_2 = Criterio(
    slug="ime-f2",
    nome="IME — Fase 2",
    fase=2,
    descricao=(
        "Cinco provas com pesos 3 / 2,5 / 2,5 / 1 / 1 (Art. 37, III). "
        "Nota final é a média ponderada (Art. 63). Inglês ENTRA na média."
    ),
    combinador="algum",
    predicados=(
        Predicado("matematica", 4.0, peso=3.0, fonte="IME Art. 37 III-a; Art. 52"),
        Predicado("fisica", 4.0, peso=2.5, fonte="IME Art. 37 III-b; Art. 52"),
        Predicado("quimica", 4.0, peso=2.5, fonte="IME Art. 37 III-c; Art. 52"),
        Predicado("portugues", 4.0, peso=1.0, fonte="IME Art. 37 III-d; Art. 52"),
        # Ao contrário do ITA, aqui o inglês é prova da 2ª fase e pesa na média.
        Predicado("ingles", 4.0, peso=1.0, fonte="IME Art. 37 III-e; Art. 52"),
        # Conceito INAPTO (< 4,00) reprova, e a redação não é nota de média.
        Predicado(
            "redacao",
            4.0,
            eliminatorio=True,
            entra_na_media=False,
            fonte="IME Art. 50 §2º; Art. 65",
        ),
    ),
    # Art. 70 §2º — o IME desempata por Inglês, o ITA não.
    desempate=("media", "matematica", "fisica", "quimica", "portugues", "ingles"),
)


CRITERIOS: dict[str, Criterio] = {
    c.slug: c
    for c in (TIO_LEO, ITA_FASE_1, ITA_FASE_2, IME_FASE_1, IME_FASE_2)
}


def por_slug(slug: str) -> Criterio:
    """Critério pelo identificador. Levanta KeyError com a lista do que existe."""
    try:
        return CRITERIOS[slug]
    except KeyError:
        raise KeyError(
            f"critério {slug!r} não existe. Disponíveis: {', '.join(sorted(CRITERIOS))}"
        ) from None
