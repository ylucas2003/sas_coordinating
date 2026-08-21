# 12 — Plano de implementação · P2 · Motor de lembretes + e-mail (⭐ v0)

> **Escopo:** a segunda das 5 partes da Sprint 1 ([10-problemas-e-visao.md §2.10](10-problemas-e-visao.md#210-sprint-1--escopo-e-divisão-17082026)).
> **Objetivo:** o motor genérico de disparos existir e ser provado ponta a ponta
> com o caso mais barato possível: o coordenador pede um lembrete **a si mesmo**
> e recebe o e-mail na hora certa.
> **Não entra aqui:** lembrete de aluno (P3), professores/requerimentos (P4),
> WhatsApp (P5), qualquer UI de gestão de calendário ([§2.6](10-problemas-e-visao.md#26-a-tela-de-gestão-do-calendário)).

**Pronto quando:** o coordenador agenda um simulado, marca *"me lembrar X dias
antes"*, e o e-mail chega no horário certo — com a falha de envio registrada
como **estado no banco** quando não chega.

> **Estado (18/08/2026): implementado e verificado ponta a ponta no ambiente
> local, INCLUINDO o envio real** — remetente `ylucas2003@gmail.com` verificado
> no SES, credencial do IAM user `sas` no `.env`, boto3 no container, e-mail
> entregue pelo tick com `enviado` + `assunto`/`corpo` gravados. Também
> verificado: 0019 up/down/up limpos; falha de envio vira `falhou` + erro +
> tentativas (provado em condição real: a 1ª tentativa falhou por config e o
> tick seguinte re-tentou e entregou); teto de 5 tira da fila; remarque regera
> (antigo `cancelado`, novo com `enviar_em` recalculado, destinatário
> preservado); guarda cancela disparo de evento cancelado sem enviar; delegate
> `/cobranca/verificar` = `/disparos/processar`; agendar com lembrete sem SES →
> 422 sem criar nada. **Tudo que ainda falta — nenhum item de código — está
> rastreado na [§9](#9--o-que-falta-20082026).**
>
> Três armadilhas descobertas na verificação, já tratadas:
> 1. **Schema cache do PostgREST**: tabela recém-migrada aceita SELECT mas
>    devolve 404 vazio em INSERT/UPDATE até o reload. O runner
>    ([migrate.py](../api/scripts/migrate.py)) agora manda
>    `NOTIFY pgrst, 'reload schema'` ao fim de todo up/down.
> 2. **Filtro de timestamptz no PostgREST**: o cliente não encoda o `+` de
>    `+00:00` na query string (vira espaço → erro de sintaxe no Postgres).
>    Filtros de tempo usam sufixo `Z` (`_filtro_ts` no
>    [despachante.py](../api/app/lembretes/despachante.py)) — primeiro filtro
>    por timestamp do projeto; vale lembrar nos próximos.
> 3. **`AWS_PROFILE` no `api/.env` quebra o boto3 no container**: o botocore
>    valida o profile mesmo com credencial explícita, e `~/.aws` não existe lá
>    dentro ("The config profile (sas) could not be found"). Comentado no
>    `.env` — era só conveniência de CLI manual.

O que a P1 já deixou pronto (e este plano só consome, não mexe):

- `evento_agenda` criada e populada pelo agendamento
  ([0018:19-36](../api/migrations/0018_agendamento_simulado.sql),
  [simulados.py:203](../api/app/routes/simulados.py#L203))
- **Remarcar** já atualiza `evento_agenda.data_evento`
  ([simulados.py:519-527](../api/app/routes/simulados.py#L519-L527)) — o gancho
  da regeração de disparos
- **Cancelar** já preenche `evento_agenda.cancelado_em`
  ([simulados.py:653-658](../api/app/routes/simulados.py#L653-L658)) — o gancho
  do cancelamento de disparos
- O tick horário `CobrancaProfessor` já bate em `/cobranca/verificar` desde
  julho, hoje num placeholder que devolve `not_implemented`
  ([cobranca.py:19-21](../api/app/routes/cobranca.py#L19-L21),
  [sas_scheduler_stack.py:68-74](../infra/sas_scheduler/sas_scheduler_stack.py#L68-L74))
- O contrato **"falha vira estado no banco, nunca exceção"** já é o padrão do
  projeto ([agendamento.py:87-103](../api/app/canvas_sync/agendamento.py#L87-L103))
  — o disparo segue o mesmo desenho do `canvas_estado`

---

## 1 · Decisões

As três primeiras eram as perguntas A7/A8/A9 da [Parte 4](10-problemas-e-visao.md#bloco-a--coordenação)
— **fechadas com o usuário em 18/08/2026**. O resto é decisão de engenharia
deste plano.

| # | Questão | Decisão |
|---|---|---|
| ✅ A7 | Disparos materializados ou calculados no tick? | **Materializados** na criação da regra, **regerados** quando a data do evento muda. A guarda de reverificação no envio (§4.3) torna disparo desatualizado inofensivo — vira no-op, não dano |
| ✅ A8 | Janela de silêncio no motor ou na regra? | **Sem janela em P2** — o e-mail sai no horário calculado, seja ele qual for. Com o coordenador como único destinatário, o incômodo é dele e ele escolheu assim. **Reavaliar antes de P3/P4**, quando aluno e professor entram; se a janela voltar, mora no motor (`calcular_enviar_em` é o gancho) |
| ✅ A9 | Idempotência: marca antes ou depois do envio? | **Antes** — claim por UPDATE condicional (`agendado`→`enviando`); só quem ganhou o claim envia. Falha → `falhou` + retry no tick seguinte, com teto de tentativas. Risco assumido: **melhor duplicar que perder** |
| | Onde mora o despachante | Rota nova **`POST /disparos/processar`**; `/cobranca/verificar` vira delegate fino pra ela. **Sem tocar em [infra/](../infra/)** — o tick existente já serve; renomear o path no CDK fica pro próximo deploy de infra que existir por outro motivo |
| | Granularidade | **1 hora** (tick existente), aceita em [§2.3.2](10-problemas-e-visao.md#232-o-que-falta). Se incomodar: pendurar o despachante também no sync de 5 min é uma linha, mesma jogada do reprocessamento da P1 |
| | Provedor | **AWS SES via boto3** (decidido no doc 10). Sandbox basta em P2: verificar remetente + e-mail do coordenador. **Pedido de produção abre no dia 1** — é prazo de terceiro e P3 precisa |
| | Destinatário do disparo | Gravado como **texto (e-mail) na materialização** — resolvido de `evento_agenda.criado_por`, fallback `settings.coordenador_email`. É o histórico exigido pelo motor: o disparo diz pra quem foi, mesmo que a config mude depois |
| | Hora do envio | `data_evento − X dias`, **na `hora_evento` do evento** ("3 dias antes da prova" = mesmo horário, 3 dias antes). Default 07:00 herda do evento |
| | Conteúdo do e-mail | **Composto no instante do envio** a partir do evento (dado fresco), não na materialização. O que saiu fica gravado no disparo (`assunto`, `corpo`) — histórico literal |
| | UI | Campo opcional no diálogo de agendar ([agendar-simulado.js](../web/js/components/agendar-simulado.js)). **Sem tela de gestão de lembrete** — isso é a tela de calendário (§2.6), fora de P2 |
| | SES não configurado | Agendar **com** lembrete → **422 com mensagem clara**. Degradar em silêncio aqui seria lembrete que nunca chega — pior que erro na cara |
| | Cadência (repetição) | **Fora.** A regra de P2 é um tiro só (`dias_antes`). P4 estende a materialização (1 regra → N disparos), não o despachante — é por isso que regra e disparo são tabelas separadas |
| | Nomenclatura | **`lembrete`/`disparo`, nunca "alerta"** — `alerta` já é sinal pedagógico do SAS ([routes/alertas.py](../api/app/routes/alertas.py)). Aviso explícito do doc 10 |

### 1.1 · O que "motor genérico" significa na prática

O requisito de [§2.2.2](10-problemas-e-visao.md#222-motor-e-aplicações): o motor
não conhece o domínio. Concretamente:

- `regra_lembrete` aponta pra `evento_agenda`, **nunca** pra `simulado`. Mesma
  direção de FK da P1 (`simulado.evento_agenda_id`, não o contrário).
- O despachante lê `disparo` → `regra_lembrete` → `evento_agenda` e **para aí**.
  Título e data do e-mail vêm do evento; ele não sabe que é um simulado.
- Quem sabe de simulado é a **rota de agendamento** (aplicação), que cria a
  regra — exatamente como ela já cria o evento.

P3 muda o *gatilho* (regra criada automaticamente, não a pedido) e P4 muda a
*materialização* (cadência: 1 regra → dezenas de disparos) e a *condição de
parada* (requerimento pendente). O despachante — claim, guarda, envio, estado —
não muda em nenhuma das duas. É esse o teste de que o motor ficou certo.

---

## 2 · Pré-voo — antes da primeira linha de código

### V1 · SES: identidades verificadas e envio de teste

Conta AWS já existe (EventBridge roda nela, `us-east-1`). Em sandbox o SES só
envia **de** e **para** endereços verificados:

```bash
# 1. verificar remetente e destinatário (cada um recebe e-mail de confirmação)
aws ses verify-email-identity --email-address ylucas2003@gmail.com --region us-east-1
aws ses verify-email-identity --email-address leonardobruno@aridesa.com --region us-east-1

# 2. depois de confirmar os dois links, envio de teste:
aws ses send-email --region us-east-1 \
  --from ylucas2003@gmail.com \
  --destination "ToAddresses=leonardobruno@aridesa.com" \
  --message "Subject={Data='teste SAS'},Body={Text={Data='motor de lembretes'}}"
```

**E-mail chegou** (olhar também a pasta de spam) → segue. **Não chegou / erro
de permissão** → resolver IAM (`ses:SendEmail`) antes de qualquer código.

✅ **Remetente de desenvolvimento: `ylucas2003@gmail.com`** (decidido
18/08/2026). O definitivo — uma caixa que o colégio controle, ex.
`sas@aridesa.com` — é decidido **antes de entrar no ar**; trocar é só verificar
a identidade nova no SES e mudar `email_remetente` no `.env`.

⚠️ Remetente `@gmail.com` saindo pela Amazon tende a cair em spam (SPF/DKIM
não alinham com o gmail.com). Aceitável em dev; inaceitável no definitivo.

### V2 · Abrir o pedido de produção do SES — hoje

Não bloqueia P2 (1 destinatário verificado), mas **bloqueia P3** (~873 alunos)
e o prazo é da AWS (~24h, pode mais). Abrir no console junto com V1 e deixar
correndo em paralelo. Conferir também os limites atuais de sandbox — mudam de
tempos em tempos.

### V3 · O tick está vivo?

O schedule existe desde julho, mas vale confirmar que segue batendo:
`grep` no log da API por `POST /cobranca/verificar` na última hora. Se o
deploy/host mudou desde então, é aqui que se descobre — e o fallback pra
desenvolver é trivial (`curl` manual com o header `X-Scheduler-Secret`).

---

## 3 · Modelo — migration 0019

Duas tabelas. Nomes do vocabulário do doc 10 (§2.2.3): **regra** é a intenção
("me lembre 3 dias antes"), **disparo** é a mensagem concreta com estado.

### 3.1 · `regra_lembrete`

```sql
CREATE TABLE regra_lembrete (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_agenda_id   uuid NOT NULL REFERENCES evento_agenda(id),
    destinatario_tipo  text NOT NULL CHECK (destinatario_tipo IN ('coordenador')),
    canal              text NOT NULL CHECK (canal IN ('email')),
    dias_antes         int  NOT NULL CHECK (dias_antes >= 0),
    criado_em          timestamptz NOT NULL DEFAULT now(),
    cancelada_em       timestamptz
);
CREATE INDEX idx_regra_lembrete_evento ON regra_lembrete(evento_agenda_id);
```

Os CHECKs de um valor só são deliberados — mesmo padrão de
`evento_agenda.tipo IN ('simulado')` da P1: documentam a intenção e P3/P4/P5
**alargam** (`'aluno'`, `'professor'`; `'whatsapp'`) sem reestruturar.

`dias_antes = 0` é válido: "no dia, na hora do evento".

### 3.2 · `disparo`

```sql
CREATE TABLE disparo (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    regra_lembrete_id  uuid NOT NULL REFERENCES regra_lembrete(id),
    destinatario       text NOT NULL,
    canal              text NOT NULL CHECK (canal IN ('email')),
    enviar_em          timestamptz NOT NULL,
    estado             text NOT NULL DEFAULT 'agendado'
        CHECK (estado IN ('agendado', 'enviando', 'enviado', 'falhou', 'cancelado')),
    tentativas         int NOT NULL DEFAULT 0,
    erro               text,
    assunto            text,
    corpo              text,
    enviado_em         timestamptz,
    criado_em          timestamptz NOT NULL DEFAULT now(),
    atualizado_em      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_disparo_fila ON disparo(enviar_em)
    WHERE estado IN ('agendado', 'falhou');
```

`assunto`/`corpo` ficam NULL até o envio — são preenchidos com o que **saiu de
fato** (decisão §1). `atualizado_em` é mantido pela aplicação a cada transição;
é o que permite resgatar claim órfão (§3.3).

### 3.3 · Máquina de estados do disparo

```
                 claim (CAS)              ok
   agendado ───────────────▶ enviando ────────▶ enviado
      │                        │   ▲
      │                        │   │ retry: tick seguinte,
      │                 falha  ▼   │ tentativas < 5
      │                      falhou┘
      │
      └────▶ cancelado   (evento cancelado, regra cancelada,
                          ou regeração por remarque)
```

- **Claim** = `UPDATE disparo SET estado='enviando' WHERE id=? AND estado IN
  ('agendado','falhou')`. Zero linhas afetadas → outro processo pegou; segue o
  baile. É toda a idempotência: tick duplicado (retry da AWS, deploy no meio)
  não produz dois envios.
- **Teto**: `falhou` continua elegível pra fila de propósito — é o retry. Quem
  o aposenta é o filtro `tentativas < 5` da query do despachante. Espelha
  `canvas_tentativas` da P1, incluindo o resgate manual futuro (zerar o
  contador) quando houver UI pra isso.
- **Claim órfão**: `enviando` com `atualizado_em` > 30 min atrás = processo
  morreu entre claim e envio. O despachante o move pra `falhou`
  (tentativa +1, erro explicando). ⚠️ Trade assumido: pode duplicar um e-mail
  que chegou a sair antes do crash — pro lembrete de coordenador, duplicar é
  inofensivo e perder não é.
- `cancelado` e `enviado` são **terminais**.

---

## 4 · Backend — arquivo por arquivo

Pacote novo **`api/app/lembretes/`** — não `canvas_sync/` (o motor não conhece
o Canvas) e não `alertas` (nome proibido, §1).

### 4.1 · `lembretes/motor.py` — materialização e regeração

Funções puras onde der (são elas que os testes cobrem):

```python
def calcular_enviar_em(data_evento: date, hora_evento: time, dias_antes: int) -> datetime
    # data_evento − dias_antes, na hora_evento, fuso -03:00 fixo (mesma
    # decisão _FUSO da P1). Sem janela de silêncio (decisão A8, §1) — o
    # horário calculado é o horário do envio.

def criar_regra_com_disparo(cliente, *, evento: dict, dias_antes: int, destinatario: str) -> dict
    # INSERT regra + INSERT disparo (1 em P2). enviar_em no passado?
    # Cria mesmo assim — vence no próximo tick e o coordenador recebe
    # na hora. Melhor que recusar "lembrete de amanhã" agendado hoje.

def regerar_disparos_do_evento(cliente, evento_id: str) -> None
    # disparos 'agendado'/'falhou' das regras ativas do evento → 'cancelado';
    # materializa de novo com a data_evento atual. 'enviado' não se toca:
    # é histórico.

def cancelar_disparos_do_evento(cliente, evento_id: str) -> None
    # tudo que não é terminal → 'cancelado'. Chamado no DELETE do simulado.
```

### 4.2 · `lembretes/despachante.py` — o tick

```python
async def processar_disparos_vencidos(cliente) -> dict:
    # 1. resgate: 'enviando' velho (>30 min) → 'falhou'           (§3.3)
    # 2. fila: estado IN ('agendado','falhou') AND enviar_em <= now()
    #          AND tentativas < 5
    # 3. por disparo:
    #    a. claim (CAS) — perdeu, pula                            (§3.3)
    #    b. GUARDA: relê regra → evento. Evento cancelado, regra
    #       cancelada → disparo vira 'cancelado', nada sai        (§4.3)
    #    c. compõe assunto/corpo do evento (dado fresco)
    #    d. envia (email.py)
    #    e. ok → 'enviado' + enviado_em + assunto/corpo gravados
    #       falha → 'falhou' + tentativas+1 + erro[:500]
    # devolve contagens {enviados, falharam, cancelados, pulados}
```

Envio **sequencial**, sem paralelismo — volume de P2 é unitário e P3 vai querer
espaçamento entre envios de qualquer forma.

### 4.3 · A guarda — o coração do motor

A decisão de [§2.4.4](10-problemas-e-visao.md#244-detecção-de-entrega--decidido-em-camadas-com-guarda-antes-do-envio):
**o disparo é decidido no instante do envio, não do agendamento.** Disparo
materializado é intenção, não ordem.

Em P2 a condição é só "o evento ainda está de pé" — parece pouco, mas é o
*slot* onde P4 encaixa "o requerimento ainda está pendente" sem tocar no resto
do despachante. A guarda existir desde o v0 é o que garante que ela não será
esquecida quando passar a importar de verdade.

Cinto e suspensório de propósito: o remarque **regera** disparos (§4.1) *e* a
guarda reverifica no envio. A regeração dá o histórico limpo; a guarda cobre a
corrida (remarque entre o SELECT e o envio) e qualquer caminho futuro que
esqueça de regerar.

### 4.4 · `lembretes/email.py` — SES

```python
def enviar_email(*, destinatario: str, assunto: str, corpo: str) -> None
    # boto3 sesv2/ses send_email, texto puro. Sem config → LembreteNaoConfigurado
    # (exceção clara, nunca silêncio). Sem retry próprio: quem re-tenta é a
    # máquina de estados do disparo, não o cliente HTTP.
```

Em [config.py](../api/app/config.py), seguindo o padrão das seções existentes:

```python
# E-mail (motor de lembretes, lembretes/email.py). Sem credencial → agendar
# com lembrete devolve 422; o resto do sistema não muda.
aws_ses_regiao: str = "us-east-1"
aws_ses_access_key_id: str = ""
aws_ses_secret_access_key: str = ""
email_remetente: str = ""
```

Em [requirements.txt](../api/requirements.txt): `boto3` (pinado na versão
corrente ao instalar).

### 4.5 · Rotas

| Rota | O que faz |
|---|---|
| `POST /disparos/processar` *(nova, `routes/disparos.py`)* | `exigir_scheduler_secret` → `processar_disparos_vencidos`. Devolve as contagens |
| `POST /cobranca/verificar` *(vira delegate)* | chama a mesma função e se anota como deprecated no docstring — é o path que o EventBridge conhece; o rename no CDK fica pro próximo deploy de infra |
| `POST /simulados/agendar` | payload ganha **`lembrarDiasAntes: int \| None`**. Preenchido → depois de criar o evento, `criar_regra_com_disparo` com destinatário de `evento.criado_por` (fallback `settings.coordenador_email`). SES sem config → **422 antes de criar qualquer coisa** |
| `PATCH /simulados/{id}` | no ramo que já atualiza `evento_agenda.data_evento` ([simulados.py:519-527](../api/app/routes/simulados.py#L519-L527)): + `regerar_disparos_do_evento`. Mudança de `hora_evento` idem |
| `DELETE /simulados/{id}` | no ramo que já preenche `cancelado_em` ([simulados.py:653-658](../api/app/routes/simulados.py#L653-L658)): + `cancelar_disparos_do_evento` |

A ordem dentro do agendar: evento → simulado → Canvas → **lembrete por último**.
Se o lembrete falhar (bug, banco), o agendamento já está de pé — lembrete é
acessório do evento, nunca o contrário.

### 4.6 · `schemas/domain.py`

`AgendarSimuladoBody` ganha `lembrarDiasAntes: int | None = None`
(validação `ge=0`). A resposta do agendar não muda — o diálogo já mostra
sucesso, e estado de disparo na UI é assunto da tela de calendário (§2.6).

### 4.7 · Testes — `api/tests/test_lembretes.py`

A suíte nasceu na P1 (round-trip dos nomes); P2 adiciona os do motor, todos
sobre as funções puras:

- `calcular_enviar_em`: caso normal, `dias_antes=0`, fuso `-03:00` presente.
- Composição do e-mail: título e data do evento aparecem; assunto não vazio.
- A máquina de estados como função de transição, se extraída pura: claim sobre
  `enviado`/`cancelado` é recusado.

O claim concorrente (CAS) e a guarda exigem banco — ficam na verificação manual
da §6 (curl duplo), não na suíte.

---

## 5 · Frontend

Vanilla JS, sem build. Uma tela só:

| Arquivo | Mudança |
|---|---|
| [components/agendar-simulado.js](../web/js/components/agendar-simulado.js) | Linha nova no formulário: `☐ Me lembrar por e-mail [ 3 ] dias antes` — checkbox + número (default 3, min 0). Marcado → `lembrarDiasAntes` no payload |
| [services/api.js](../web/js/services/api.js) | typedef de `agendarSimulado` ganha o campo |

Erro 422 do SES sem config já aparece pelo caminho de erro normal do diálogo.
Nada além disso: sem selo, sem listagem de disparos — v0 se verifica pela caixa
de entrada e pelo banco, e a UI de acompanhamento pertence à tela de calendário.

---

## 6 · Ordem de execução

| # | Etapa | Verificação |
|---|---|---|
| 0 | Pré-voo V1/V2/V3 (§2) — identidades SES, pedido de produção aberto, tick vivo | `aws ses send-email` chega na caixa do coordenador |
| 1 | Migration 0019 (§3) | `migrate up` e `migrate down` limpos, nos dois sentidos |
| 2 | `email.py` + config + boto3 | script solto envia e-mail real via o módulo |
| 3 | `motor.py` + testes | suíte passa |
| 4 | `despachante.py` + `POST /disparos/processar` + delegate em `/cobranca/verificar` | disparo inserido à mão com `enviar_em` no passado → `curl` no processar → e-mail chega, estado `enviado`, assunto/corpo gravados |
| 5 | **Idempotência**: dois `curl` simultâneos no processar | um envio só; contagens batem |
| 6 | **Falha vira estado**: credencial SES inválida de propósito | `falhou` + `erro` no banco; corrige credencial → tick seguinte entrega; `tentativas` bateu 5 → para de tentar |
| 7 | Agendar com `lembrarDiasAntes` (rota + UI) | fluxo ponta a ponta pela UI: agenda com lembrete pra daqui a pouco → e-mail chega sem nenhum curl |
| 8 | **Remarcar** regera | remarca o simulado; disparo antigo `cancelado`, novo `agendado` com `enviar_em` recalculado |
| 9 | **Cancelar** cancela + guarda | cancela o simulado com disparo vencendo; nada sai. Repor: cancelar **entre** o SELECT e o envio é coberto pela guarda (teste de código, não manual) |
| 10 | Tick real | esperar o `CobrancaProfessor` da AWS processar sozinho um disparo — fecha o "pronto quando" sem intervenção manual |

**A etapa 10 é a que fecha o "pronto quando"** — é a única que prova o caminho
EventBridge → API → SES sem ninguém no teclado.

---

## 7 · Riscos

| Risco | Sinal | O que fazer |
|---|---|---|
| IAM sem `ses:SendEmail` / conta sem SES habilitado | erro no V1 | resolver no dia 1 — é o único bloqueio duro de P2 |
| E-mail cai em spam (remetente `@gmail.com` via Amazon, sem DKIM alinhado) | some da caixa de entrada | aceitável em dev — conferir a pasta de spam antes de concluir que o envio falhou; o remetente definitivo (caixa do colégio + DKIM) resolve antes de entrar no ar |
| Tick morto (deploy/host mudou desde julho) | V3 sem log de `POST /cobranca/verificar` | desenvolvimento segue por `curl`; religar o schedule antes da etapa 10 |
| Claim órfão duplica e-mail | crash entre claim e envio, resgate reenvia | assumido (§3.3) — duplicar lembrete de coordenador é inofensivo; revisitar quando o canal for WhatsApp |
| Regeração esquecida em algum caminho de edição futuro | lembrete com data velha | a guarda no envio é a rede — no pior caso o disparo velho vira no-op, não mensagem errada |
| Lembrete criado e SES quebra depois | `falhou` acumulando | é o comportamento desenhado: estado no banco + teto de 5; visibilidade fina fica pra tela de calendário |
| `enviar_em` em horário de verão | — | não existe desde 2019; `-03:00` fixo, mesma decisão da P1 |

---

## 8 · O que P2 deixa em aberto de propósito

- **Saída do sandbox SES + tratamento de bounces (SNS)** — obrigatório antes de
  P3 (873 endereços de aluno, alguns inválidos), desnecessário com 1 destinatário.
  O pedido de produção virou a saga da §9.1; a infra de bounce virou
  **compromisso assumido com a AWS** (§9.2), não mais "fica pra P3".
- **Remetente definitivo** — `ylucas2003@gmail.com` é só de desenvolvimento.
  Antes de entrar no ar: caixa do colégio (ex. `sas@aridesa.com`) verificada no
  SES.
- **DKIM / verificação do domínio `aridesa.com`** — depende de quem controla o
  DNS do colégio. P2 vive com remetente verificado individualmente.
- **Janela de silêncio** — decidida como *sem janela* enquanto o destinatário é
  o próprio coordenador. Reabrir antes de P3 (aluno recebendo às 2h da manhã é
  outra conversa); se voltar, o gancho é `calcular_enviar_em`.
- **Renomear `/cobranca/verificar` no CDK** — o delegate resolve; o rename
  pega carona no próximo `cdk deploy` que existir por outro motivo.
- **Cadência / repetição na regra** — P4. A materialização é o ponto de
  extensão (1 regra → N disparos); despachante não muda.
- **`destinatario_tipo` `'aluno'` e `'professor'`, canal `'whatsapp'`** —
  alargamento de CHECK em P3/P4/P5.
- **UI de acompanhamento de disparos** (estado, histórico, reenviar) — tela de
  calendário ([§2.6](10-problemas-e-visao.md#26-a-tela-de-gestão-do-calendário)).
- **Espaçamento entre envios em lote** — P3; o despachante sequencial já deixa
  o lugar óbvio pra dormir entre envios.
- **Variação de texto anti-robô** — só faz sentido no WhatsApp (P5).

---

## 9 · O que falta (20/08/2026)

A P2 **em código está pronta e verificada** (Estado, no topo). O que resta é
entorno — e nenhum item bloqueia o uso local. Em ordem de urgência:

### 9.1 · SES: sair do sandbox — ⏳ em reanálise · trava P3

A saga até aqui:

| Quando | O que houve |
|---|---|
| 18/08 | Pedido aberto **pela API** (`aws sesv2 put-account-details`, tipo Transactional, caso de uso em inglês) — o console novo trava o botão "Solicitar acesso à produção" atrás de verificação de domínio; a API não tem esse portão. **Caso 178722538000720** |
| 20/08 | AWS respondeu pedindo detalhes — frequência de envio, como a lista de destinatários é mantida, tratamento de bounces/complaints/descadastro, exemplo do e-mail — e recomendou explicitamente **identidade de domínio verificada** |
| 20/08 | A primeira resposta enviada no caso não cobriu as perguntas ("Aceito que use meu email…"). A resposta ponto a ponto, com o e-mail real de exemplo, foi redigida e precisa ser **colada no caso** (Support Center → caso → Responder) |

- **Próximo passo:** colar a resposta completa no caso e aguardar ~24h.
- Status consultável a qualquer momento: `aws sesv2 get-account` →
  `Details.ReviewDetails.Status`. Hoje: `DENIED` (aguardando reanálise);
  aprovado vira `GRANTED` e a cota salta de 200/dia pra ~50 mil/dia.
- Enquanto não aprovar, **P3 não pode enviar** — 873 alunos não cabem no
  sandbox nem seriam verificáveis um a um.

### 9.2 · SNS de bounces e complaints — compromisso com a AWS · pré-requisito de P3

Na resposta ao caso afirmamos que bounces/complaints serão processados via SNS
com remoção automática de endereços inválidos **antes de qualquer envio em
volume** — agora é compromisso, não só plano. Escopo: tópico SNS para
bounce/complaint do SES → endpoint na API → marcar o endereço como inválido no
banco e excluí-lo dos próximos disparos. Pequeno, e pode ser feito já, antes
mesmo da aprovação — inclusive fortalece a reanálise de §9.1.

### 9.3 · Domínio do colégio + remetente definitivo — depende do DNS do colégio

`ylucas2003@gmail.com` é remetente **de desenvolvimento** (e cai em spam por
natureza: gmail saindo pela Amazon não alinha SPF/DKIM). Antes de entrar no
ar: verificar `aridesa.com.br` no SES (3 registros CNAME de DKIM — gerados na
hora, é colar no DNS) e trocar `EMAIL_REMETENTE` pra uma caixa do colégio
(ex. `sas@aridesa.com`). A própria AWS recomendou isso no caso — andar com
esse item em paralelo ajuda a aprovação de §9.1.

### 9.4 · Etapa 7 pela UI — opcional · 2 min

Agendar um simulado com o checkbox de lembrete pela interface, ponta a ponta.
No sandbox o **destinatário** também precisa ser verificado, e o destinatário
do lembrete é `coordenador_email` (Leonardo). Pro teste solo: apontar
`COORDENADOR_EMAIL` pro remetente verificado no `.env` local — com o efeito
colateral de que o login local do coordenador passa a ser esse e-mail (mesma
senha).

### 9.5 · Produção do SAS — pendência herdada da P1, com decisão embutida

Aplicar 0018+0019 no banco de produção e deploy da API/web. A decisão
embutida: **onde é produção agora?** O Supabase caiu em 13/08 (NXDOMAIN) e o
ambiente corrente é Postgres+PostgREST no Docker local. A **etapa 10 da §6**
(tick do EventBridge processando um disparo sozinho, sem ninguém no teclado)
só fecha depois desse deploy.

### 9.6 · Depois: P3

Com §9.1 e §9.2 resolvidos, a P3 (lembrete de aluno) fica barata: alargar
`destinatario_tipo` pra `'aluno'`, regra automática "simulado amanhã",
espaçamento entre envios em lote — e **reabrir a conversa da janela de
silêncio** (a decisão A8 de "sem janela" valia pro coordenador que escolheu
isso pra si; aluno recebendo e-mail às 2h da manhã é outra conversa). Antes de
ligar, checar também as notificações nativas do Canvas
([10 §2.3.4](10-problemas-e-visao.md#234-o-canvas-ajuda-com-o-agendamento-levantamento))
pra não avisar o aluno duas vezes.
