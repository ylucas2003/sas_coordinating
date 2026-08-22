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
    imagemUrl: str | None = None
    usaImagemNoRender: bool
    resolucaoUrl: str | None = None
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


class AtualizarEstudo(BaseModel):
    resolvida: bool | None = None
    anotacao: str | None = None
