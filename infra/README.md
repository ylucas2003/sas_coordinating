# Infra

Duas coisas, e só isto:

| Pasta | O quê |
|---|---|
| [`vps/`](vps/) | **A produção.** Scripts de provisionamento, compose, nginx da borda, TLS e cron do VPS. Ver [docs/15](../docs/15-plano-hospedagem-vps.md) |
| [`postgres/init/`](postgres/init/) | Papéis do Postgres criados na primeira subida do banco (`authenticator` e `sas_service`, usados pelo PostgREST) |

## O que havia aqui antes

Uma stack CDK que criava agendadores no AWS EventBridge para acordar o backend
periodicamente. Foi removida quando o sistema saiu do Render e passou a rodar
num VPS único: os quatro jobs viraram linhas de crontab no próprio host
(`vps/crontab-sas`), o que elimina a dependência de uma conta AWS, o segredo
que o `events.Connection` criava no Secrets Manager, e a exigência de que a API
fosse publicamente alcançável pelo EventBridge.

Se a stack ainda estiver deployada em alguma conta AWS, ela dispara contra uma
URL que não é mais a produção. Desligar com `cdk destroy SasSchedulerStack` e
apagar o parâmetro `/sas/scheduler/secret` do SSM — guardando o VALOR, porque
as quatro rotas continuam exigindo o header `X-Scheduler-Secret`.
