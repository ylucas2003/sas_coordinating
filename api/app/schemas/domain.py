"""Schemas Pydantic do domínio. Espelham os tipos JS em web/js/services/api.js
e a especificação em docs/05-data-and-stats.md.
"""

from typing import Literal

from pydantic import BaseModel

Modalidade = Literal["presencial", "online"]
Vestibular = Literal["ITA", "IME", "AFA", "EsPCEx", "EFOMM"]
VestibularAlvo = Literal["ITA", "IME"]   # apenas os 2 vestibulares no escopo do MVP
Perfil = Literal["ancora", "misterio", "regular"]
Tendencia = Literal["subindo", "estavel", "caindo"]
Zona = Literal["top", "cinzenta", "risco"]
Severidade = Literal["vermelho", "ambar", "verde", "cinza"]
TipoSimulado = Literal["fase_1", "fase_2"]
CategoriaAlerta = Literal[
    "QUEDA_RENDIMENTO",
    "SUBIDA_ATIPICA",
    "PROVA_MAL_CALIBRADA",
    "MATERIA_EM_RISCO",
    "DIFERENCA_ENTRE_SEDES",
    "PANORAMA_CICLO",
    "ZONA_TRANSICAO",
]


class Sede(BaseModel):
    id: str
    nome: str
    modalidade: Modalidade


class Turma(BaseModel):
    id: str
    nome: str
    sedeId: str
    anoLetivo: int


class Aluno(BaseModel):
    id: str
    nome: str
    turmaId: str
    sedeId: str
    vestibularesAlvo: list[Vestibular]
    ativo: bool = True
    email: str | None = None   # e-mail do Canvas — valida o primeiro acesso
    perfil: Perfil = "regular"
    tendencia: Tendencia = "estavel"
    zona: Zona = "cinzenta"
    media: float | None = None
    sparkline: list[float] = []
    temFoto: bool = False   # foto_perfil_storage IS NOT NULL — não expõe a key


class Ciclo(BaseModel):
    id: str
    nome: str
    # O número do ciclo dentro do ano. Já vinha do banco e era descartado no
    # mapeamento; a fileira de ciclos do Painel precisa dele para dizer "4" em
    # vez de "Ciclo 4 · ITA · 2026" quando o recorte já fixou ano e vestibular
    # (docs/32 §3.2).
    ordem: int
    anoLetivo: int
    vestibularAlvo: VestibularAlvo | None = None
    periodoInicio: str
    periodoFim: str
    simuladoIds: list[str]
    # Estado da ligação com o Canvas. `None` = o ciclo veio de lá e não há o
    # que enviar; 'divergente' = o coordenador escolheu não criar o grupo, e o
    # retry nunca reenvia sozinho (docs/18 §2.5). A rota não devolvia isto, e
    # por isso nenhuma tela conseguia mostrar que o ciclo estava assim.
    canvasEstado: str | None = None
    canvasErro: str | None = None


class MateriaResumo(BaseModel):
    codigo: str
    nome: str


class Simulado(BaseModel):
    id: str
    nome: str                             # nome original (preservado pra debug/ficha)
    rotuloCurto: str | None = None        # "P38", "P22"
    tipo: TipoSimulado | None = None      # fase_1 (combinada) | fase_2 (individual)
    materia: MateriaResumo | None = None  # None pra provas agregadas
    dataAplicacao: str
    cicloId: str
    cicloOrdem: int | None = None         # 1, 2, ..., 11
    vestibularAlvo: VestibularAlvo | None = None  # ITA | IME (herdado do ciclo)
    notaMaxima: float = 10
    anulado: bool = False
    # O veredicto do SAS sobre a coluna inteira (0043). `false` = a prova saiu
    # dos agregados porque o zero dela é prática de lançamento, não desempenho;
    # as notas individuais continuam visíveis, com a ressalva (docs/32 §1.2).
    notaConfiavel: bool = True
    motivoNotaNaoConfiavel: str | None = None
    origem: Literal["canvas", "sas"] = "canvas"
    # Sincronização SAS→Canvas (só relevante em origem='sas'): 'pendente' e
    # 'falhou' = o Assignment ainda não existe/reflete o SAS — a UI mostra o
    # limbo. canvasErro carrega o motivo da última falha.
    # 'divergente' = o coordenador escolheu não mandar ao Canvas (docs/18 §2.5).
    # Mesma lista do CHECK de simulado.canvas_estado (migration 0027).
    canvasEstado: Literal["sincronizado", "pendente", "falhou", "divergente"] = "sincronizado"
    canvasErro: str | None = None
    media: float | None = None
    mediana: float | None = None
    desvioPadrao: float | None = None
    nPresentes: int | None = None


class Alerta(BaseModel):
    id: str
    categoria: CategoriaAlerta
    #: Sobre QUEM é o alerta. Explícito, e não deduzido do `href`, para a faixa
    #: de decisão do Painel poder respeitar o recorte da tela (docs/33 §3).
    entidadeTipo: str
    entidadeId: str
    severidade: Severidade
    tagLabel: str
    titulo: str
    subtitulo: str
    tempoRelativo: str
    href: str
    sparkline: list[float] = []
