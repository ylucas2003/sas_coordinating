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
    perfil: Perfil = "regular"
    tendencia: Tendencia = "estavel"
    zona: Zona = "cinzenta"
    media: float | None = None
    sparkline: list[float] = []


class Ciclo(BaseModel):
    id: str
    nome: str
    anoLetivo: int
    vestibularAlvo: VestibularAlvo | None = None
    periodoInicio: str
    periodoFim: str
    simuladoIds: list[str]


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
    media: float | None = None
    mediana: float | None = None
    desvioPadrao: float | None = None
    nPresentes: int | None = None


class Alerta(BaseModel):
    id: str
    categoria: CategoriaAlerta
    severidade: Severidade
    tagLabel: str
    titulo: str
    subtitulo: str
    tempoRelativo: str
    href: str
    sparkline: list[float] = []
