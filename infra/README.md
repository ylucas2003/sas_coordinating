# Infra — agendadores (EventBridge)

Stack CDK (Python) que cria os gatilhos agendados que acordam o backend do SAS
periodicamente: sincronização com o Canvas, avaliação de alertas, e verificação
da fila de cobrança de professores. Contexto completo em
[`docs/08-integracao-canvas.md`](../docs/08-integracao-canvas.md).

**Importante:** isso só cria o *gatilho*. Toda a lógica de negócio continua no
FastAPI (`api/`) — as rotas abaixo ainda precisam ser criadas lá:

| Schedule | Intervalo | Rota que precisa existir no FastAPI |
|---|---|---|
| CanvasSync | a cada 5 min | `POST /canvas-sync/run` |
| AlertasCheck | a cada 1h | `POST /alertas/verificar` |
| CobrancaProfessor | a cada 1h | `POST /cobranca/verificar` |

Cada uma dessas rotas precisa validar o header `X-Scheduler-Secret` contra o
mesmo valor guardado no parâmetro SSM (ver abaixo) — sem isso, qualquer um na
internet pode chamar essas rotas.

## Pré-requisitos

- Node.js + AWS CDK CLI (já instalados nesta máquina: `node -v`, `cdk --version`)
- Conta AWS com credenciais configuradas (`aws configure`, ou variáveis
  `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN`)
- Python 3.9+

> Node instalado aqui é a v26, mais nova que as versões oficialmente testadas
> pelo CDK (v20/22/24 LTS). Funcionou no `cdk synth` — só emite um aviso,
> silenciado com `JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1`. Se aparecer
> algo estranho no dia a dia, o fallback é instalar Node 22 LTS via nvm.

## Setup (uma vez por conta/região AWS)

```bash
cd infra
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Provisiona os recursos que todo CDK app precisa (bucket de assets, etc.)
cdk bootstrap

# Cria o segredo compartilhado ANTES do primeiro deploy — o CloudFormation
# não cria SecureString diretamente, por isso isso é feito à parte.
aws ssm put-parameter \
  --name /sas/scheduler/secret \
  --type SecureString \
  --value "$(openssl rand -hex 32)"
```

## Deploy

```bash
source .venv/bin/activate
export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

# CloudFormation não aceita ssm-secure em AWS::Events::Connection.ApiKeyValue,
# então o deploy lê o segredo do SSM e injeta por env var:
export SAS_SCHEDULER_SECRET=$(aws ssm get-parameter --name /sas/scheduler/secret \
  --with-decryption --query Parameter.Value --output text)

cdk deploy -c apiBaseUrl=https://sas-coordinating.onrender.com
```

(`apiBaseUrl` também pode vir da variável de ambiente `SAS_API_BASE_URL` em
vez do `-c`.)

## Validar sem tocar na AWS

```bash
export SAS_API_BASE_URL=https://sas-api.example.com  # valor qualquer, só pra sintetizar
cdk synth
```
Gera o CloudFormation localmente, sem criar nada de verdade — útil pra revisar
o que vai ser criado antes de rodar `cdk deploy`.

## Custo esperado

Praticamente zero no volume atual (~300-1000 invocações/dia):
- EventBridge Scheduler/Rules: sem cobrança documentada pra regras no bus
  padrão (só o alvo é cobrado).
- API Destinations: US$ 0,20 por milhão de eventos.
- (Verificado direto na página oficial de pricing da AWS em 2026-07-04.)

## Próximos passos (fora do escopo desta stack)

1. Criar as 3 rotas no FastAPI (`/canvas-sync/run`, `/alertas/verificar`,
   `/cobranca/verificar`), cada uma validando `X-Scheduler-Secret`.
2. Implementar a lógica de cada uma (sync do Canvas, avaliação de alertas,
   verificação da fila de cobrança de professor via Z-API).
3. Escolher onde o FastAPI vai rodar (Render/Fly/Railway — ainda em aberto,
   ver `docs/06-open-questions.md`) antes do primeiro deploy real, já que
   `apiBaseUrl` precisa apontar pra essa URL final.
