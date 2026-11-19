"""Eventos de push disparados pelo cron — POST /push/eventos/* (docs/45 §16).

Router SEPARADO de `routes/push.py`, como `gravacoes_aula/rotas.py` está separado
de `consulta.py`: lá tudo é da pessoa logada (JWT), aqui tudo é do agendador
(`X-Scheduler-Secret`). Misturar os dois num arquivo só é como se esquece um guard
numa rota nova.

Cada rota responde NA HORA com o que vai sair, e o fan-out roda depois, no
BackgroundTasks (docs/45 §9: nunca dentro da requisição de quem disparou). O
`cron-sas.sh` grava a resposta em `/var/log/sas/cron.log`; o resultado por
aparelho fica em `envio_push` e em `inscricao_push`.

Respostas, todas 200 — nenhuma delas é falha do agendador:

  desligado          sem chave VAPID; o cron pode rodar antes de o push ser ligado
  fora_do_horario    7h–22h de Fortaleza, seja qual for o horário do crontab
  ja_enviado         a vaga do dia já foi usada (`envio_push`, UNIQUE)
  sem_missao         o acervo não tem tópico elegível hoje
  ninguem_com_aparelho / todos_ja_mexeram
  aceito             o envio começou em segundo plano

Os handlers são `def`, como em `routes/push.py`: o cliente PostgREST é síncrono.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends

from ..auth import exigir_scheduler_secret
from ..banco.missao import FUSO_DA_ESCOLA
from ..push import missao_do_dia, registro
from ..push.chaves import chave_do_servidor
from ..supabase_client import get_supabase

router = APIRouter(prefix="/push/eventos", tags=["push"])


def _agora() -> datetime:
    """Ponto único do relógio, para o teste poder empurrá-lo."""
    return datetime.now(FUSO_DA_ESCOLA)


@router.post("/missao-do-dia")
def enviar_missao_do_dia(
    tarefas: BackgroundTasks, _: None = Depends(exigir_scheduler_secret)
) -> dict:
    """Avisa a missão de hoje a cada aluno com aparelho ativo (app/push/missao_do_dia.py).

    A ordem importa:

      1. `preparar` só LÊ — sorteio, aparelhos, cortes. Se o banco cair aqui, a
         vaga do dia continua livre e o próximo disparo ainda manda.
      2. `reservar` ocupa a vaga. Daqui em diante, nenhum outro disparo do mesmo
         dia manda nada — nem se este morrer no meio.
      3. O fan-out vai para depois da resposta.
    """
    if chave_do_servidor() is None:
        return {"status": "desligado"}
    agora = _agora()
    if not missao_do_dia.dentro_do_horario(agora):
        return {"status": "fora_do_horario", "hora": missao_do_dia.na_escola(agora).strftime("%H:%M")}

    cliente = get_supabase()
    preparo = missao_do_dia.preparar(cliente, agora)
    envio_id = registro.reservar(cliente, missao_do_dia.TIPO, preparo.dia.isoformat())
    if envio_id is None:
        return {"status": "ja_enviado", "dia": preparo.dia.isoformat()}

    if preparo.notificacao is None or not preparo.inscricoes:
        registro.concluir(
            cliente, envio_id, destinatarios=preparo.destinatarios,
            pulados=preparo.pulados, observacao=preparo.motivo,
        )
        return {"status": preparo.motivo, **preparo.resumo()}

    tarefas.add_task(
        registro.disparar, cliente, envio_id, preparo.inscricoes, preparo.notificacao,
        destinatarios=preparo.destinatarios, pulados=preparo.pulados,
    )
    return {"status": "aceito", **preparo.resumo()}
