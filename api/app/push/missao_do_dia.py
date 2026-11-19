"""O aviso da missão do dia, o primeiro evento de push (docs/45 §16).

Todo dia, no horário do crontab (`infra/vps/crontab-sas`), cada aluno com
aparelho ativo recebe o assunto de hoje: "Missão de hoje: Polinômios · 10
questões de Matemática". É o mesmo cartão da aba Hoje, dito na tela bloqueada.

As oito perguntas do contrato (docs/45 §9), respondidas aqui:

  1. Quem recebe: aluno ATIVO (`aluno.ativo`, a mesma régua do login em
     `routes/auth_canvas.py::_sessao_para`) com aparelho ativado, MENOS quem já
     mexeu numa questão do assunto de hoje, hoje. Cobrar a missão de quem já
     está nela é o aviso que ensina a ignorar os avisos.
  2. Quando: agendado, uma vez por dia, pelo cron. Não passa pelo motor de
     lembretes (0019): lá o destinatário é um e-mail e o disparo é por pessoa;
     aqui é um envio só para a turma.
  3. O texto: o assunto e a matéria, que são OS MESMOS para todos — nada de
     nota, acerto ou posição (regra 4 do §2: a tela bloqueada é pública).
  4. Vale até a missão virar: o TTL acaba à meia-noite de Fortaleza. Depois
     disso o aviso falaria de um assunto que já não é o da tela. Urgência
     normal: não é motivo para acordar o aparelho em economia de bateria.
  5. Agrupa: `tag` e `Topic` fixos. O aviso de hoje substitui o de ontem na
     central de notificações, e um aparelho desligado o dia inteiro recebe só o
     mais novo quando volta, nunca a fila da semana.
  6. Horário de silêncio: a rota recusa fora das 7h–22h de Fortaleza, seja qual
     for o horário do crontab. Um cron mal escrito ou um disparo à mão de
     madrugada não acorda ninguém.
  7. Desligar só este tipo: ainda não. Com um tipo só, "Desativar" na seção
     Avisos neste aparelho É o desligar deste aviso. A preferência por tipo
     entra com o segundo evento (§9, item 7).
  8. E-mail: não existe e-mail da missão. É só push.

E a regra de evento para muita gente: o envio é registrado e trava em
`envio_push` (app/push/registro.py), e o fan-out roda DEPOIS da resposta ao cron
(routes/push_eventos.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from ..banco.missao import FUSO_DA_ESCOLA, MissaoDoDia, missao_e_questoes_do_dia
from ..lembretes.despachante import filtro_ts
from .envio import TABELA as TABELA_DE_INSCRICOES
from .envio import Notificacao

TIPO = "missao-do-dia"

#: Fora disto a rota não manda (pergunta 6). Fim exclusivo: 22h00 já é silêncio.
PRIMEIRA_HORA = time(7, 0)
ULTIMA_HORA = time(22, 0)

#: O que o envio precisa de cada inscrição, e o `aluno_id` para os cortes.
COLUNAS = "id, aluno_id, endpoint, chave_p256dh, chave_auth, falhas_seguidas, ultimo_envio_ok_em, criada_em"


def na_escola(agora: datetime) -> datetime:
    return agora.astimezone(FUSO_DA_ESCOLA)


def dentro_do_horario(agora: datetime) -> bool:
    return PRIMEIRA_HORA <= na_escola(agora).time() < ULTIMA_HORA


def inicio_do_dia(agora: datetime) -> datetime:
    """Meia-noite de hoje em Fortaleza — a mesma virada que troca a missão."""
    local = na_escola(agora)
    return datetime.combine(local.date(), time(0, 0), tzinfo=FUSO_DA_ESCOLA)


def segundos_ate_virar(agora: datetime) -> int:
    """Até a próxima meia-noite de Fortaleza: depois dela, a missão é outra."""
    virada = inicio_do_dia(agora) + timedelta(days=1)
    return max(60, int((virada - na_escola(agora)).total_seconds()))


def notificacao(missao: MissaoDoDia, agora: datetime) -> Notificacao:
    """O texto da tela bloqueada. O assunto no título, que é o que se lê de relance."""
    unidade = "questão" if missao.quantidade == 1 else "questões"
    titulo = f"Missão de hoje: {missao.nome}"
    corpo = f"{missao.quantidade} {unidade} de {missao.materia}. O desafio é o mesmo para toda a turma."
    if len(titulo) > 80:
        # Nome de tópico comprido não cabe no título; vai inteiro no corpo.
        titulo = "Missão de hoje"
        corpo = f"{missao.nome}: {missao.quantidade} {unidade} de {missao.materia}."[:200]
    return Notificacao(
        tipo=TIPO,
        titulo=titulo,
        corpo=corpo,
        # A aba Hoje, e não `/treino/prioridade`: um toque depois da meia-noite
        # abriria o treino do assunto NOVO debaixo de um aviso que fala do antigo.
        # Na Hoje o nome do assunto está escrito antes do "Começar".
        url="/",
        tag=TIPO,
        topico=TIPO,
        ttl_segundos=segundos_ate_virar(agora),
        urgencia="normal",
    )


def alunos_que_ja_mexeram(cliente: Any, questoes: frozenset[str], desde: datetime) -> set[str]:
    """Quem respondeu, pulou ou anotou alguma questão do assunto de hoje, hoje.

    `questao_estudo_aluno.atualizado_em` muda em toda escrita (`banco/listas.py::
    atualizar_estudo`), e é a única pegada que o treino deixa.

    O filtro do banco é SÓ a data; o recorte pelas questões do assunto é feito
    aqui. Mandar os ids num `in_` poria uma lista de tamanho do acervo na URL —
    Polinômios sozinho tem 102 —, enquanto o que mudou hoje é pouco.

    `filtro_ts` porque o `+` do fuso viraria espaço na query string (armadilha do
    motor de lembretes, `lembretes/despachante.py`).
    """
    if not questoes:
        return set()
    linhas = (
        cliente.table("questao_estudo_aluno")
        .select("aluno_id, questao_id")
        .gte("atualizado_em", filtro_ts(desde.astimezone(UTC)))
        .execute()
    ).data or []
    return {str(linha["aluno_id"]) for linha in linhas if linha.get("questao_id") in questoes}


def alunos_inativos(cliente: Any) -> set[str]:
    """`aluno.ativo = false`: quem saiu do colégio e o login já recusa.

    Pela negativa porque são poucos, e o corte se aplica a quem tem aparelho
    sem precisar de embed nem de lista de ids na URL.
    """
    linhas = cliente.table("aluno").select("id").eq("ativo", False).execute().data or []
    return {str(linha["id"]) for linha in linhas}


@dataclass
class Preparo:
    """O que vai sair hoje — calculado ANTES de ocupar a vaga do dia."""

    dia: date
    notificacao: Notificacao | None = None
    inscricoes: list[dict[str, Any]] = field(default_factory=list)
    destinatarios: int = 0
    pulados: int = 0
    #: Por que não há o que mandar. `None` quando há.
    motivo: str | None = None

    def resumo(self) -> dict[str, Any]:
        return {
            "dia": self.dia.isoformat(),
            "destinatarios": self.destinatarios,
            "pulados": self.pulados,
            "aparelhos": len(self.inscricoes),
        }


def preparar(cliente: Any, agora: datetime) -> Preparo:
    """Sorteia, lista os aparelhos e aplica os cortes. Só leitura.

    Só leitura de propósito: roda antes de `registro.reservar`, e um erro aqui
    (banco fora) não gasta a vaga do dia — o próximo disparo ainda pode mandar.
    """
    dia = na_escola(agora).date()
    sorteio = missao_e_questoes_do_dia(cliente, dia)
    if sorteio is None:
        return Preparo(dia=dia, motivo="sem_missao")
    missao, questoes = sorteio

    inscricoes = (
        cliente.table(TABELA_DE_INSCRICOES)
        .select(COLUNAS)
        .not_.is_("aluno_id", "null")
        .execute()
    ).data or []
    if not inscricoes:
        return Preparo(dia=dia, motivo="ninguem_com_aparelho")

    inativos = alunos_inativos(cliente)
    inscricoes = [i for i in inscricoes if str(i["aluno_id"]) not in inativos]
    com_aparelho = {str(i["aluno_id"]) for i in inscricoes}
    ja_mexeram = alunos_que_ja_mexeram(cliente, questoes, inicio_do_dia(agora)) & com_aparelho
    alvo = [i for i in inscricoes if str(i["aluno_id"]) not in ja_mexeram]

    return Preparo(
        dia=dia,
        notificacao=notificacao(missao, agora),
        inscricoes=alvo,
        destinatarios=len(com_aparelho - ja_mexeram),
        pulados=len(ja_mexeram),
        motivo=None if alvo else "todos_ja_mexeram" if com_aparelho else "ninguem_com_aparelho",
    )
