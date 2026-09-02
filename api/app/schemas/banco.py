"""Schemas do banco de questões ITA · IME (docs/22).

Fronteira HTTP em camelCase, como o resto do projeto (ver schemas/domain.py) —
o banco fala snake_case, a API fala a língua do front.

⚠️ `QuestaoVestibular` é questão de PROVA PASSADA. A questão de simulado-Quiz do
Canvas é outra coisa e mora em `questao` (migration 0010). Ver docs/22 §8.
"""

from typing import Literal

from pydantic import BaseModel

VestibularBanco = Literal["ITA", "IME"]
MateriaBanco = Literal["Física", "Química", "Matemática"]

# As duas coleções do acervo, em vocabulário de PRODUTO.
#
# A coluna que as separa é `extraido_por` (0031/0033), mas nem o aluno nem a URL
# precisam do nome dela: "recentes" e "arquivo" é o que a tela diz, e a tradução
# mora num lugar só (`consultas.MODOS_DA_COLECAO`). Trocar o método de extração
# de um lote no futuro não deve renomear nada na interface.
ColecaoBanco = Literal["recentes", "arquivo"]
Confianca = Literal["alta", "media", "baixa"]
DonoLista = Literal["aluno", "coordenacao"]


# ─── Taxonomia ───────────────────────────────────────────────────────────


class TopicoTaxonomia(BaseModel):
    codigo: str                 # '7.2'
    nome: str                   # 'Ondas e Acústica'
    assuntos: list[str]         # o que o edital enumera dentro do tópico
    totalQuestoes: int


class BlocoTaxonomia(BaseModel):
    codigo: str                 # '7'
    nome: str                   # 'Oscilações e Ondas Mecânicas'
    topicos: list[TopicoTaxonomia]
    totalQuestoes: int


class TaxonomiaMateria(BaseModel):
    materia: MateriaBanco
    blocos: list[BlocoTaxonomia]
    totalQuestoes: int
    # Questões da matéria que ninguém classificou. Não somem do filtro: some
    # delas seria dar ao aluno um recorte incompleto sem aviso (docs/22 §8).
    semClassificacao: int
    anos: list[int]
    fases: list[int]
    vestibulares: list[VestibularBanco]


# ─── Questão ─────────────────────────────────────────────────────────────


class TopicoDaQuestao(BaseModel):
    codigo: str
    nome: str
    blocoNome: str
    confianca: Confianca | None = None
    observacao: str | None = None


class QuestaoVestibular(BaseModel):
    id: str
    vestibular: VestibularBanco
    ano: int
    fase: int
    materia: MateriaBanco
    numero: int
    dissertativa: bool
    enunciadoMd: str
    # None quando dissertativa — 2ª fase não tem alternativa nem letra.
    alternativas: dict[str, str] | None = None
    gabarito: str | None = None
    # 'banca' = a letra é a publicada pela banca; 'sugerido' = deduzida
    # resolvendo a questão (acervo histórico sem gabarito oficial, confiança
    # alta apenas — 0031). None quando `gabarito` também é None.
    gabaritoOrigem: str | None = None
    gabaritoConfianca: Confianca | None = None
    imagemUrl: str | None = None
    usaImagemNoRender: bool
    resolucaoUrl: str | None = None
    # Resolução escrita no próprio cartão, para o acervo que o Ari não comenta
    # (tudo antes de 2019 — resolucao.py). Convive com resolucaoUrl; nunca as
    # duas ao mesmo tempo (CHECK da 0031).
    resolucaoMd: str | None = None
    resolucaoOrigem: str | None = None
    # 'visao' = página escaneada lida como imagem, o OCR não dá conta de prova
    # datilografada (docs/22, piloto 1973). O cartão troca texto por padrão e
    # imagem por consulta só nesse caso — em 'pipeline' é o inverso.
    extraidoPor: str | None = None
    topicos: list[TopicoDaQuestao]
    revisado: bool
    # Só preenchido para aluno autenticado (P6). None = perfil sem estudo.
    resolvida: bool | None = None
    anotacao: str | None = None


class PaginaQuestoes(BaseModel):
    """Paginada de propósito, e isso NÃO contradiz a armadilha 2 do CLAUDE.md.

    Lá o teto é proibido porque truncar leitura ESTATÍSTICA devolve número
    errado sem parecer errado. Aqui a resposta é navegação: uma página é
    resposta completa da pergunta feita, e a seguinte está a um clique. Quem
    agrega — `/banco/estatisticas` — nunca pagina. Ver docs/22 §2.2.
    """

    questoes: list[QuestaoVestibular]
    total: int
    pagina: int
    porPagina: int


# ─── Estatísticas ────────────────────────────────────────────────────────


class RecorrenciaTopico(BaseModel):
    codigo: str
    nome: str
    blocoNome: str
    total: int
    # {2018: 3, 2019: 5, ...} — só os anos com ocorrência.
    porAno: dict[int, int]
    porFase: dict[int, int]
    porVestibular: dict[str, int]


class EstatisticasBanco(BaseModel):
    materia: MateriaBanco
    topicos: list[RecorrenciaTopico]
    anos: list[int]
    # {2019: 30, 2020: 30, ...} — quantas questões a banca cobrou em cada ano
    # DENTRO deste recorte. É o denominador de "% da prova", e existe porque
    # ele NÃO é derivável dos tópicos: questão mista soma nos dois tópicos de
    # propósito (docs/22 §1.5), então somar `total` por ano superestima o
    # tamanho da prova e o percentual sai menor que a verdade.
    #
    # Contagem bruta não compara bancas — ITA e IME têm número de questões
    # diferente por ano, e o formato do ITA muda em 2019 —, e é por isso que o
    # eixo Y padrão da ficha do assunto é percentual e não contagem.
    questoesPorAno: dict[int, int]
    totalQuestoes: int
    semClassificacao: int


# ─── Listas ──────────────────────────────────────────────────────────────


class ListaResumo(BaseModel):
    id: str
    titulo: str
    donoTipo: DonoLista
    totalQuestoes: int
    criadaEm: str
    atualizadaEm: str


class Lista(ListaResumo):
    questoes: list[QuestaoVestibular]


class CriarLista(BaseModel):
    titulo: str


class AtualizarLista(BaseModel):
    titulo: str | None = None
    # Ordem completa e explícita. Reordenar é mandar a lista inteira: evita
    # o vaivém de "mover para cima" virar N requisições fora de ordem.
    questaoIds: list[str] | None = None


# ─── Estudo do aluno ─────────────────────────────────────────────────────


class EstudoQuestao(BaseModel):
    questaoId: str
    resolvida: bool
    anotacao: str | None = None
    # A resposta da sessão de treino (0042). Só a última sobrevive.
    #
    # ⚠️ `acertou` e `resolvida` NÃO são a mesma coisa e não se somam:
    # `resolvida` é auto-declarado ("eu fiz esta") e pode ser marcado sem nunca
    # ter respondido; `acertou` é conferido contra o gabarito. A tela de
    # progresso mostra `resolvida` e é obrigada a dizer que não é correção.
    alternativaEscolhida: str | None = None
    # None = questão sem gabarito (dissertativa ou não importado). É "não dá
    # para dizer", nunca "errou" — quem desenhar isso como erro mente.
    acertou: bool | None = None


# ─── Progresso do aluno no acervo ────────────────────────────────────────
#
# ⚠️ TODO NÚMERO VEM COM O SEU PAR. "412 questões" não é progresso; "412 de
# 2.693" é. Um campo `feitas` sem o `total` ao lado é bug de produto, não
# economia de payload — o aluno não tem como saber se 412 é muito ou pouco.
#
# ⚠️ E "FEITAS" NÃO É "ACERTOS". A contagem é de `resolvida`, que é
# auto-declarado: o aluno marcou que resolveu. Não passou por correção nenhuma.
# A tela pode dizer "o que você marcou como feito"; nunca "seu domínio" nem
# "seu acerto". Quem mede acerto é o simulado, e é outra fonte (0042 e
# `/me/simulado/{id}/questoes`) — as duas não se somam nem se tiram média.


class ParDeProgresso(BaseModel):
    """Quantas o aluno marcou, de quantas existem naquele recorte."""

    feitas: int
    total: int


class ProgressoPorMateria(ParDeProgresso):
    materia: MateriaBanco


class ProgressoPorAssunto(ParDeProgresso):
    materia: MateriaBanco
    # `consultas.TOPICO_SEM_CLASSIFICACAO` no lugar do código do edital quando
    # a linha são as questões que ninguém classificou. Vale como filtro em
    # `GET /banco/questoes`, então a linha é clicável como as outras.
    codigo: str
    nome: str
    blocoNome: str


class ProgressoPorAno(ParDeProgresso):
    materia: MateriaBanco
    ano: int


class ProgressoDoAluno(BaseModel):
    feitas: int
    total: int
    porMateria: list[ProgressoPorMateria]
    porAssunto: list[ProgressoPorAssunto]
    # Só os pares (matéria, ano) que EXISTEM no acervo. A ausência de um par é
    # "não houve prova dessa matéria nesse ano", que é diferente de "houve e
    # você não fez nenhuma" — e a grade precisa distinguir os dois, senão o
    # aluno lê um buraco de acervo como buraco de estudo.
    porAno: list[ProgressoPorAno]
    # O domínio do eixo x da grade. Preencher contra ele é o que impede o ano
    # sem marcação de sumir e comprimir o tempo.
    anos: list[int]


class AtualizarEstudo(BaseModel):
    resolvida: bool | None = None
    anotacao: str | None = None
    # A letra marcada no treino. `""` limpa a resposta, como em `anotacao`.
    #
    # ⚠️ `acertou` NÃO entra aqui de propósito: quem conta se acertou é o
    # servidor, comparando com `questao_vestibular.gabarito`. Aceitá-lo do
    # cliente deixaria o acerto a um `curl` de distância de discordar do banco —
    # e é dele que sai a leitura de em que assunto o aluno erra.
    alternativaEscolhida: str | None = None
