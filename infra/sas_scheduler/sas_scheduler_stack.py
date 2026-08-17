"""Gatilhos agendados (EventBridge) que acordam o backend do SAS periodicamente.

Cada schedule só chama uma URL do FastAPI via HTTPS — toda a lógica de negócio
(sincronizar Canvas, avaliar alertas, cobrar professor) continua vivendo no
backend Python, não aqui. Ver docs/08-integracao-canvas.md para o contexto.

Rules:
  - CanvasSync         5 min   → /canvas-sync/run         (sync incremental, recompute-alvo)
  - AlertasCheck       1 h     → /alertas/verificar       (só reavalia alertas)
  - CobrancaProfessor  1 h     → /cobranca/verificar      (placeholder)
  - ReconcileDiario    ~3h BRT → /canvas-sync/reconciliar (recálculo completo, cura drift)

Todas autenticam com o header `X-Scheduler-Secret` (mesmo valor do SSM
/sas/scheduler/secret).
"""

from aws_cdk import (
    Duration,
    SecretValue,
    Stack,
    aws_events as events,
    aws_events_targets as targets,
)
from constructs import Construct


class SasSchedulerStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        api_base_url: str,
        scheduler_secret: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Autenticação compartilhada entre a AWS e o backend do SAS. O valor
        # canônico mora no parâmetro SSM /sas/scheduler/secret; o deploy o lê
        # e injeta aqui via env var (CloudFormation não aceita ssm-secure em
        # AWS::Events::Connection.ApiKeyValue — testado em 2026-07-04). O
        # Connection guarda o valor no Secrets Manager interno dele.
        connection = events.Connection(
            self,
            "SasApiConnection",
            authorization=events.Authorization.api_key(
                "X-Scheduler-Secret",
                SecretValue.unsafe_plain_text(scheduler_secret),
            ),
            description="Autenticação da API do SAS para os jobs agendados",
        )

        self._criar_schedule(
            id_prefix="CanvasSync",
            path="/canvas-sync/run",
            schedule=events.Schedule.rate(Duration.minutes(5)),
            connection=connection,
            api_base_url=api_base_url,
        )
        self._criar_schedule(
            id_prefix="AlertasCheck",
            path="/alertas/verificar",
            schedule=events.Schedule.rate(Duration.hours(1)),
            connection=connection,
            api_base_url=api_base_url,
        )
        self._criar_schedule(
            id_prefix="CobrancaProfessor",
            path="/cobranca/verificar",
            schedule=events.Schedule.rate(Duration.hours(1)),
            connection=connection,
            api_base_url=api_base_url,
        )
        # Reconcile completo 1x/dia às 6 UTC (~3h BRT) — cura o drift que o
        # recompute-alvo do sync incremental deixa. Pesado, mas de madrugada.
        self._criar_schedule(
            id_prefix="ReconcileDiario",
            path="/canvas-sync/reconciliar",
            schedule=events.Schedule.cron(hour="6", minute="0"),
            connection=connection,
            api_base_url=api_base_url,
        )

    def _criar_schedule(
        self,
        *,
        id_prefix: str,
        path: str,
        schedule: events.Schedule,
        connection: events.Connection,
        api_base_url: str,
    ) -> None:
        destino = events.ApiDestination(
            self,
            f"{id_prefix}Destination",
            connection=connection,
            endpoint=f"{api_base_url}{path}",
            http_method=events.HttpMethod.POST,
            description=f"Chama {path} no backend do SAS",
        )

        events.Rule(
            self,
            f"{id_prefix}Rule",
            schedule=schedule,
            targets=[targets.ApiDestination(destino)],
        )
