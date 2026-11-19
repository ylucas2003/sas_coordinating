"""O registro de cada envio de evento — e a trava que impede o mesmo evento de sair duas vezes.

docs/45 §9: evento que vai para muita gente registra o envio. Aqui o registro é
também a idempotência (migration 0082): a linha é RESERVADA antes do primeiro
POST, com `UNIQUE (tipo, referencia)`, e o segundo pedido do mesmo envio encontra
a vaga ocupada e não manda nada.

Reservar antes, e não gravar depois: se o processo morrer no meio (deploy, falta
de memória), a linha fica sem `concluido_em` e o envio NÃO se repete naquele dia.
É o lado certo de errar. Perder um aviso da missão custa um dia; mandar o mesmo
aviso duas vezes para a turma inteira é o que faz o aluno desligar os avisos — e
desligar vale para todo tipo de aviso, não só para aquele.

A atomicidade é do Postgres, não deste processo: `ON CONFLICT DO NOTHING` no
índice único. Uma trava em memória não serviria, porque o segundo disparo pode
vir de outro container (`docker compose run`) ou de depois de um restart.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from .envio import Notificacao, ResultadoDoEnvio, enviar_para_inscricoes

log = logging.getLogger("sas.push")

TABELA = "envio_push"


def reservar(cliente: Any, tipo: str, referencia: str) -> str | None:
    """Ocupa a vaga do envio. Devolve o id, ou `None` se ela já estava ocupada.

    `ignore_duplicates=True` vira `Prefer: resolution=ignore-duplicates` — o
    `ON CONFLICT DO NOTHING` do PostgREST —, e com `return=representation` a
    resposta traz só as linhas INSERIDAS: lista vazia quer dizer "já existia".
    Sem exceção para traduzir, e sem a corrida de "ler para ver se existe e
    depois inserir", em que dois disparos simultâneos passariam os dois.
    """
    linhas = (
        cliente.table(TABELA)
        .upsert(
            {"tipo": tipo, "referencia": referencia},
            on_conflict="tipo,referencia",
            ignore_duplicates=True,
            returning="representation",
        )
        .execute()
    ).data or []
    return str(linhas[0]["id"]) if linhas else None


def concluir(
    cliente: Any,
    envio_id: str,
    *,
    destinatarios: int = 0,
    pulados: int = 0,
    resultado: ResultadoDoEnvio | None = None,
    observacao: str | None = None,
) -> None:
    """Fecha a linha com o que aconteceu. Chamado também quando não houve envio."""
    contagem = (resultado or ResultadoDoEnvio()).como_dict()
    cliente.table(TABELA).update(
        {
            "concluido_em": datetime.now(UTC).isoformat(),
            "destinatarios": destinatarios,
            "pulados": pulados,
            **contagem,
            "observacao": observacao[:300] if observacao else None,
        }
    ).eq("id", envio_id).execute()


def disparar(
    cliente: Any,
    envio_id: str,
    inscricoes: list[dict[str, Any]],
    notificacao: Notificacao,
    *,
    destinatarios: int,
    pulados: int,
) -> ResultadoDoEnvio | None:
    """O fan-out e o fechamento da linha. Roda no BackgroundTasks, depois da resposta.

    Ninguém lê o retorno em produção — a resposta HTTP já saiu. O que fica é a
    linha de `envio_push` e o log, e por isso a falha também fecha a linha: sem
    isso, "interrompido" e "ainda rodando" seriam o mesmo `concluido_em` nulo.
    """
    try:
        resultado = enviar_para_inscricoes(cliente, inscricoes, notificacao)
    except Exception as erro:
        log.exception("push: envio '%s' (%s) interrompido", notificacao.tipo, envio_id)
        try:
            concluir(
                cliente, envio_id, destinatarios=destinatarios, pulados=pulados,
                observacao=f"interrompido: {type(erro).__name__}",
            )
        except Exception:
            log.exception("push: nem o registro do envio %s fechou", envio_id)
        return None
    concluir(cliente, envio_id, destinatarios=destinatarios, pulados=pulados, resultado=resultado)
    log.info(
        "push: envio '%s' (%s) — %d pessoa(s), %d pulada(s), %s",
        notificacao.tipo, envio_id, destinatarios, pulados, resultado.como_dict(),
    )
    return resultado
