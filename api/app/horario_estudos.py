"""Horário de estudos do aluno (docs/42): blocos de dia, hora, duração e rótulo.

É a semana que o aluno monta sozinho. Autodeclarada e privada — não alimenta XP,
sequência nem liga (tempo de estudo não é verificável, docs/26 §1), e nenhuma
rota da coordenação lê isto (docs/42 §0).

**Por que um bloco por vez, e não "troca a semana inteira".** `PUT
/me/vestibulares` apaga e reinsere em duas chamadas, e lá é aceitável: a tabela
tem duas linhas. Aqui não. O backend não tem transação — a camada de dados é o
PostgREST, e `psycopg` só existe no runner de migrations —, então um `insert`
que falhasse depois do `delete` faria o aluno perder a semana que montou, sem
erro visível. Cada operação abaixo é UMA chamada ao banco; e criar vários dias de
uma vez é um INSERT de várias linhas, que o PostgREST executa como um comando só.

⚠️ **Toda leitura e escrita filtra por `aluno_id`, e o `aluno_id` sai do token.**
PATCH e DELETE filtram por `id` E `aluno_id`: só por `id`, um aluno apagaria o
bloco de outro adivinhando um uuid. Bloco alheio e bloco inexistente dão a mesma
resposta (`BlocoInexistente`, 404) para a rota não confirmar que o uuid existe.

⚠️ **Sobreposição é recusada aqui, não no banco** — um EXCLUDE por intervalo pede
`btree_gist`, que o runner não instala (ver a migration 0069). "Tenho duas coisas
às 19h" é justamente o erro que a ferramenta existe para pegar. Blocos que se
encostam (um termina às 19:00, outro começa às 19:00) NÃO se sobrepõem.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from supabase import Client

from .schemas.horario_estudos import BlocoDeEstudo

DIAS_DA_SEMANA = range(1, 8)  # ISO: 1 = segunda … 7 = domingo
DURACAO_MINIMA = 15
DURACAO_MAXIMA = 480
TAMANHO_MAXIMO_DO_ROTULO = 80
#: O teto é o que mantém "sem paginação" honesto: a semana inteira volta numa
#: leitura só (CLAUDE.md, armadilha 2), e 60 blocos é mais do que uma semana de
#: estudo tem.
TETO_DE_BLOCOS = 60
MINUTOS_NO_DIA = 24 * 60

_NOME_DO_DIA = {
    1: "Segunda-feira",
    2: "Terça-feira",
    3: "Quarta-feira",
    4: "Quinta-feira",
    5: "Sexta-feira",
    6: "Sábado",
    7: "Domingo",
}

# "19:00" da API ou "19:00:00" que o PostgREST devolve para uma coluna `time`.
_HORA = re.compile(r"^(\d{1,2}):(\d{2})(?::00(?:\.0+)?)?$")


class BlocoInvalido(ValueError):
    """O valor não faz sentido, de qualquer jeito: a rota responde 422."""


class ConflitoDeHorario(ValueError):
    """O valor é válido, mas bate com o que o aluno já tem: a rota responde 409."""


class BlocoInexistente(LookupError):
    """Não existe, ou existe e é de outro aluno: a rota responde 404 nos dois casos."""


# ─── Regras puras ─────────────────────────────────────────────────────────


def minutos_de(hora: str) -> int:
    """`"19:00"` → 1140. Aceita também `"19:00:00"`, que é o que o banco devolve."""
    achou = _HORA.match(hora.strip()) if isinstance(hora, str) else None
    if achou is None:
        raise BlocoInvalido('A hora precisa estar no formato "19:00".')
    horas, minutos = int(achou.group(1)), int(achou.group(2))
    if horas > 23 or minutos > 59:
        raise BlocoInvalido("Essa hora não existe.")
    return horas * 60 + minutos


def hora_de(minutos: int) -> str:
    """1140 → `"19:00"`. A API fala sempre `"HH:MM"`, nunca o `"19:00:00"` do banco."""
    return f"{minutos // 60:02d}:{minutos % 60:02d}"


def sobrepoe(inicio_a: int, duracao_a: int, inicio_b: int, duracao_b: int) -> bool:
    """Dois intervalos se cruzam? Encostar não é cruzar: 18:00–19:00 e 19:00–20:30
    convivem, e é como alguém monta uma tarde de estudo em sequência."""
    return inicio_a < inicio_b + duracao_b and inicio_b < inicio_a + duracao_a


def validar_bloco(dia: int, inicio: int, duracao: int, rotulo: str) -> str:
    """Valida os quatro campos e devolve o rótulo já aparado.

    As mensagens são frases para o aluno ler, não códigos — o front mostra o
    `detail` como está.
    """
    if isinstance(dia, bool) or dia not in DIAS_DA_SEMANA:
        raise BlocoInvalido("Escolha um dia da semana, de segunda a domingo.")
    if isinstance(duracao, bool) or not DURACAO_MINIMA <= duracao <= DURACAO_MAXIMA:
        raise BlocoInvalido(
            f"A duração precisa ficar entre {DURACAO_MINIMA} minutos e "
            f"{DURACAO_MAXIMA // 60} horas."
        )
    if inicio + duracao > MINUTOS_NO_DIA:
        raise BlocoInvalido(
            "O bloco não pode passar da meia-noite. Para estudar até mais tarde, "
            "faça dois blocos."
        )
    limpo = (rotulo or "").strip()
    if not limpo:
        raise BlocoInvalido("Diga o que você vai estudar neste bloco.")
    if len(limpo) > TAMANHO_MAXIMO_DO_ROTULO:
        raise BlocoInvalido(
            f"O nome do bloco pode ter até {TAMANHO_MAXIMO_DO_ROTULO} caracteres."
        )
    return limpo


def _recusar_se_cruzar(
    dia: int, inicio: int, duracao: int, existentes: list[BlocoDeEstudo]
) -> None:
    for outro in existentes:
        if outro.diaSemana != dia:
            continue
        inicio_outro = minutos_de(outro.horaInicio)
        if sobrepoe(inicio, duracao, inicio_outro, outro.duracaoMinutos):
            fim_outro = inicio_outro + outro.duracaoMinutos
            raise ConflitoDeHorario(
                f"{_NOME_DO_DIA[dia]} já tem “{outro.rotulo}” das "
                f"{hora_de(inicio_outro)} às {hora_de(fim_outro)}. "
                "Escolha outro horário."
            )


# ─── Banco ────────────────────────────────────────────────────────────────

_COLUNAS = "id, dia_semana, hora_inicio, duracao_minutos, rotulo"


def _para_bloco(linha: dict[str, Any]) -> BlocoDeEstudo:
    return BlocoDeEstudo(
        id=str(linha["id"]),
        diaSemana=int(linha["dia_semana"]),
        horaInicio=hora_de(minutos_de(linha["hora_inicio"])),
        duracaoMinutos=int(linha["duracao_minutos"]),
        rotulo=linha["rotulo"],
    )


def listar(cliente: Client, aluno_id: str) -> list[BlocoDeEstudo]:
    """A semana inteira do aluno, por dia e hora.

    Ordena em Python, e não por `.order("hora_inicio")`, para a ordem não
    depender de como cada cliente serializa uma coluna `time`.
    """
    linhas = (
        cliente.table("bloco_horario_estudo")
        .select(_COLUNAS)
        .eq("aluno_id", aluno_id)
        .execute()
    ).data or []
    blocos = [_para_bloco(linha) for linha in linhas]
    return sorted(blocos, key=lambda b: (b.diaSemana, minutos_de(b.horaInicio), b.id))


def criar(
    cliente: Client,
    aluno_id: str,
    dias: list[int],
    hora_inicio: str,
    duracao_minutos: int,
    rotulo: str,
) -> list[BlocoDeEstudo]:
    """Cria um bloco por dia, num INSERT só.

    Tudo é validado ANTES de escrever, contra a semana inteira: se um dos dias
    cruza com um bloco existente, nenhum é criado. Com um insert por dia, "seg a
    sex" falharia na quarta deixando segunda e terça criadas, e o aluno veria um
    erro e uma semana pela metade.
    """
    escolhidos = sorted(set(dias))
    if not escolhidos:
        raise BlocoInvalido("Escolha ao menos um dia da semana.")
    inicio = minutos_de(hora_inicio)
    limpo = ""
    for dia in escolhidos:
        limpo = validar_bloco(dia, inicio, duracao_minutos, rotulo)

    existentes = listar(cliente, aluno_id)
    if len(existentes) + len(escolhidos) > TETO_DE_BLOCOS:
        raise ConflitoDeHorario(
            f"O horário comporta até {TETO_DE_BLOCOS} blocos. "
            "Apague algum antes de criar outro."
        )
    for dia in escolhidos:
        _recusar_se_cruzar(dia, inicio, duracao_minutos, existentes)

    criadas = (
        cliente.table("bloco_horario_estudo")
        .insert(
            [
                {
                    "aluno_id": aluno_id,
                    "dia_semana": dia,
                    "hora_inicio": hora_de(inicio),
                    "duracao_minutos": duracao_minutos,
                    "rotulo": limpo,
                }
                for dia in escolhidos
            ]
        )
        .execute()
    ).data or []
    return sorted(
        (_para_bloco(linha) for linha in criadas),
        key=lambda b: (b.diaSemana, minutos_de(b.horaInicio)),
    )


def atualizar(
    cliente: Client,
    aluno_id: str,
    bloco_id: str,
    dia_semana: int | None = None,
    hora_inicio: str | None = None,
    duracao_minutos: int | None = None,
    rotulo: str | None = None,
) -> BlocoDeEstudo:
    """Edita UM bloco. `None` num campo = não mexer nele.

    Valida o bloco como ele FICA (os campos novos sobre os antigos), e a conta
    de sobreposição ignora o próprio bloco: sem isso, mudar só o rótulo de um
    bloco o faria cruzar consigo mesmo.
    """
    existentes = listar(cliente, aluno_id)
    atual = next((b for b in existentes if b.id == bloco_id), None)
    if atual is None:
        raise BlocoInexistente("Esse bloco não existe.")

    dia = atual.diaSemana if dia_semana is None else dia_semana
    inicio = minutos_de(atual.horaInicio if hora_inicio is None else hora_inicio)
    duracao = atual.duracaoMinutos if duracao_minutos is None else duracao_minutos
    limpo = validar_bloco(dia, inicio, duracao, atual.rotulo if rotulo is None else rotulo)
    _recusar_se_cruzar(dia, inicio, duracao, [b for b in existentes if b.id != bloco_id])

    # `.eq("aluno_id", …)` de novo, ainda que o bloco tenha saído da lista DESTE
    # aluno: a leitura e a escrita são duas chamadas, e a escrita não confia na
    # leitura para decidir de quem é a linha.
    gravadas = (
        cliente.table("bloco_horario_estudo")
        .update(
            {
                "dia_semana": dia,
                "hora_inicio": hora_de(inicio),
                "duracao_minutos": duracao,
                "rotulo": limpo,
                "atualizado_em": datetime.now(UTC).isoformat(),
            }
        )
        .eq("id", bloco_id)
        .eq("aluno_id", aluno_id)
        .execute()
    ).data or []
    if not gravadas:
        raise BlocoInexistente("Esse bloco não existe.")
    return _para_bloco(gravadas[0])


def apagar(cliente: Client, aluno_id: str, bloco_id: str) -> None:
    """Apaga UM bloco do aluno. Bloco de outro aluno se comporta como inexistente."""
    apagadas = (
        cliente.table("bloco_horario_estudo")
        .delete()
        .eq("id", bloco_id)
        .eq("aluno_id", aluno_id)
        .execute()
    ).data or []
    if not apagadas:
        raise BlocoInexistente("Esse bloco não existe.")
