"""Schemas do horário de estudos (docs/42).

Fronteira HTTP em camelCase, como o resto do projeto (ver schemas/domain.py).

⚠️ Os limites NÃO estão em `Field(ge=…, le=…)` de propósito: o 422 automático do
Pydantic fala em inglês ("Input should be greater than or equal to 15") para um
aluno de 17 anos. Quem valida é `app/horario_estudos.py`, que devolve a frase em
português — o mesmo motivo de `PUT /me/vestibulares` validar à mão.
"""

from pydantic import BaseModel


class BlocoDeEstudo(BaseModel):
    id: str
    diaSemana: int          # ISO: 1 = segunda … 7 = domingo
    horaInicio: str         # "19:00" — resolução de minuto, sem segundos
    duracaoMinutos: int
    rotulo: str


class HorarioDeEstudos(BaseModel):
    # Ordenado por dia e hora. A semana inteira, sem paginação: o teto de 60
    # blocos por aluno é o que mantém "sem paginação" honesto (docs/42 §2).
    blocos: list[BlocoDeEstudo]


class CriarBlocos(BaseModel):
    # LISTA de dias: "segunda a sexta, 19h, 1h30" é um gesto, não cinco, e um
    # INSERT de várias linhas no PostgREST é um comando só — atômico, num backend
    # que não tem transação (docs/42 §3).
    diasSemana: list[int]
    horaInicio: str
    duracaoMinutos: int
    rotulo: str


class AtualizarBloco(BaseModel):
    """Campo ausente não é mexido. Editar o bloco de UM dia não mexe nos outros:
    quem criou "seg a sex" e quer só a quarta diferente edita só a quarta."""

    diaSemana: int | None = None
    horaInicio: str | None = None
    duracaoMinutos: int | None = None
    rotulo: str | None = None
