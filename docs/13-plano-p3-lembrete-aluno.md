# 13 — Plano de implementação · P3 · Lembrete de aluno

> **Escopo:** a terceira das 5 partes da Sprint 1 ([10-problemas-e-visao.md §2.10](10-problemas-e-visao.md#210-sprint-1--escopo-e-divisão-17082026)).
> **Objetivo:** o mesmo motor da P2, novo destinatário — os alunos do simulado
> são avisados na véspera **sem ninguém pedir**.
> **Não entra aqui:** professores/requerimentos (P4), WhatsApp (P5), tela de
> gestão do calendário ([§2.6](10-problemas-e-visao.md#26-a-tela-de-gestão-do-calendário)),
> lembrete de insight de ciclo ([§2.5](10-problemas-e-visao.md#25-aplicação-2--lembretes-de-aluno-e-de-coordenador)).

**Pronto quando:** os alunos do simulado do dia seguinte recebem **um** e-mail,
listando todas as provas do dia, sem ninguém pedir — com endereço inválido
retirado da lista sozinho e cada envio registrado como estado no banco.

> **Estado (20/08/2026): etapas 1–12 implementadas; 60 testes passando,
> incluindo os 8 da P2 inalterados** (o gate do refactor da etapa 5). O que
> falta é o que depende de banco e de terceiro — migration aplicada, AWS
> configurada, envio real — rastreado na [§10](#10--o-que-falta-20082026).
>
> Duas coisas mudaram em relação ao plano original, as duas descobertas ao
> implementar:
> 1. **A deduplicação da varredura espelha o índice único, não os estados
>    vivos.** `enviado` é terminal mas continua ocupando a chave. Deduplicar
>    só contra os vivos fazia a varredura tentar recriar, no tick seguinte ao
>    envio das 18:00, o disparo de cada aluno — e o INSERT quebrava a rodada
>    pelo resto do dia. Virou `ocupa_chave()`, com teste de regressão.
> 2. **Entrou um fake do PostgREST na suíte**
>    ([tests/fake_postgrest.py](../api/tests/fake_postgrest.py)). A varredura é
>    a única peça do motor cuja lógica não cabe em função pura — ela é
>    reconciliação, e os bugs dela só aparecem na *segunda* rodada. Foi ele que
>    pegou o item 1.

O que muda em relação à P2, e é só isso — mas cada linha vira um problema novo:

| | P2 | P3 |
|---|---|---|
| Destinatário | 1, conhecido (`coordenador_email`) | ~873, **derivados** do simulado |
| Gatilho | o coordenador pede | automático, na criação do simulado |
| Materialização | na criação da regra | **tardia**, na véspera (o elenco muda) |
| Volume por tick | 1 e-mail | centenas — ritmo, orçamento e teto |
| Endereço ruim | não existe | existe, e derruba a reputação da conta |
| Agrupamento | 1 evento = 1 e-mail | **1 dia = 1 e-mail**, com N provas dentro |

O que a P2 já deixou pronto e este plano **consome sem reescrever**: a máquina
de estados do `disparo` (claim, retry, teto, claim órfão), a guarda antes do
envio, o cliente SES, o tick e o delegate `/cobranca/verificar`. O despachante
ganha ritmo e orçamento; a lógica de *quando* e *para quem* não entra nele.

---

## 1 · Decisões

As quatro primeiras foram fechadas com o usuário em **20/08/2026**; o resto é
decisão de engenharia deste plano.

| # | Questão | Decisão |
|---|---|---|
| ✅ | Um e-mail por prova ou por dia? | **Por dia.** Um disparo por (aluno, dia), com todas as provas daquele dia no corpo. Em dia de 3 provas o aluno recebe 1 e-mail, não 3 — e o volume cai de ~2.6k para ~873 |
| ✅ | Simulados que vieram do Canvas (sem `evento_agenda`) | **Ficam de fora.** Coerente com a inversão da P1: quem quer lembrete agenda no SAS. Sem mexer no sync, sem risco de duplicar. ⚠️ O silêncio é invisível — ver risco em §7 |
| ✅ | Quem é a audiência | **Alunos ativos do ano letivo do ciclo**: `matricula_turma.ativo_ate IS NULL` em turma do `ano_letivo` do ciclo, `aluno.ativo = true`, com `email` preenchido e não inválido. Sem filtro por vestibular alvo (todo aluno é avaliado contra ITA **e** IME) |
| ✅ | SNS de bounces ([12 §9.2](12-plano-p2-motor-lembretes.md#92--sns-de-bounces-e-complaints--compromisso-com-a-aws--pré-requisito-de-p3)) | **Entra como etapa 0 deste plano.** É pré-requisito real dos 873 envios, é compromisso assumido no caso da AWS, e pode ser feito antes da aprovação — inclusive ajuda a reanálise |
| | Quando a regra nasce | **No agendamento**, junto com o evento — checkbox marcado por default ("avisar os alunos"). Regra é intenção; desmarcar depois = cancelar a regra |
| | Quando os disparos nascem | **Na véspera** (materialização tardia), não na criação da regra. O elenco de alunos de daqui a 40 dias não é o de hoje: matrícula entra, sai, e-mail é descoberto pelo sync. Materializar cedo seria congelar uma lista errada |
| | Isso contradiz a decisão A7 da P2? | **Não.** A7 é "materializado, não calculado no envio" — segue valendo: o disparo existe no banco antes do envio, com estado. O que muda é *quando* ele é materializado. O que a P2 chamou de "P4 estende a materialização" está acontecendo aqui, uma parte antes |
| | Hora do envio | **18:00 (BRT) da véspera**, fixa — não herda a hora do evento. Resolve a janela de silêncio (A8, reaberta): prova às 7h com `dias_antes=1` mandaria e-mail às 7h da manhã, e prova à noite mandaria às 22h. Configurável em `LEMBRETE_ALUNO_HORA` |
| | `dias_antes` do aluno | **1, fixo em P3.** O schema aceita outros; a UI não oferece. Cadência ("3 dias antes, 1 dia antes, no dia") é P4 |
| | A qual regra o disparo do digest pertence | À **regra âncora** do dia = a do evento de menor `(hora_evento, id)`. Determinístico, e re-ancorado pela varredura quando a âncora é cancelada |
| | Idempotência da materialização | Coluna nova **`disparo.chave_idempotencia`** (`aluno-dia:{data}:{aluno_id}`) com índice único parcial que **ignora `cancelado`** — varredura repetida não duplica, e regeração (cancelar + recriar) continua possível |
| | Guarda e composição por tipo | O despachante **delega** a decisão final e o texto à *aplicação* do `destinatario_tipo` (§1.1). O motor continua sem saber o que é simulado |
| | Ritmo | Envio sequencial com espaçamento (`EMAIL_ENVIOS_POR_SEGUNDO`, default 5) + **orçamento de tempo por tick** (default 240s). O que não coube sai no tick seguinte — a fila é durável |
| | Latência do tick | O despachante passa a rodar **também no fim do `/canvas-sync/run` (5 min)**, além do tick horário. Sem tocar em [infra/](../infra/), como na P2 |
| | Teto de segurança | `EMAIL_TETO_DIARIO` (default **150**) — o sandbox do SES corta em 200/24h e estourar é conta suspensa. Sobe para o teto real quando a produção sair |
| | Rede de dev | `EMAIL_DESTINATARIO_TESTE` redireciona **todo** envio para um endereço só (destinatário real no assunto), e `LEMBRETE_ALUNO_ATIVO=false` desliga a varredura. Sem isso, um `curl` errado manda e-mail para 873 alunos reais |
| | Descadastro | Link no rodapé com HMAC → grava em `email_invalido` com motivo `descadastro`. Foi o que respondemos à AWS; é uma rota e nenhum estado novo |
| | Reply-To | `coordenador_email`. Aluno responde o lembrete — e a resposta não pode cair na caixa pessoal do dev |
| | Conteúdo | Texto puro, sem nota, sem dado de desempenho: **título, data, hora e local do dia**. É e-mail de menor de idade saindo em massa; quanto menos dado, melhor |

### 1.1 · Motor e aplicações — o refactor que a P3 obriga

A P2 provou que o despachante não precisa conhecer o domínio; a P3 é onde isso
para de ser retórica. A guarda do aluno **não** é "o evento está de pé" (o
digest sobrevive ao cancelamento de uma das provas do dia) e o texto não é o de
um evento só. Se isso for para dentro do `despachante.py`, o motor vira
domínio na primeira aplicação nova — exatamente o que [§2.2.2](10-problemas-e-visao.md#222-motor-e-aplicações) proíbe.

A separação, então, fica explícita no código:

```
lembretes/
  motor.py         ← materialização simples, cálculo de horário     (genérico)
  despachante.py   ← fila, claim, retry, ritmo, orçamento, envio    (genérico)
  email.py         ← SES                                            (genérico)
  aplicacoes/
    __init__.py         ← registry por destinatario_tipo
    coordenador.py      ← a lógica da P2, movida sem mudar comportamento
    aluno_simulado.py   ← audiência, varredura da véspera, digest   (domínio)
```

Duas funções por aplicação, e o despachante só conhece essas duas:

| Hook | Quem implementa | O que faz |
|---|---|---|
| `materializar(cliente)` | só `aluno_simulado` | roda no início do tick: cria/reconcilia os disparos da véspera |
| `preparar(cliente, regra, disparo) -> Mensagem \| None` | as duas | **é a guarda + a composição**: `None` = o mundo mudou, o disparo vira `cancelado` sem sair nada |

O `coordenador.py` é recorte literal do que está em
[despachante.py](../api/app/lembretes/despachante.py) hoje (evento cancelado →
`None`; senão `compor_email`). **Nenhuma mudança de comportamento na P2** — e é
assim que se sabe que o corte foi no lugar certo.

---

## 2 · Pré-voo — antes da primeira linha de código

### V1 · SES fora do sandbox — bloqueio duro, e não é nosso

873 destinatários não cabem em sandbox (200/24h, e cada endereço precisaria ser
verificado um a um). O caso **178722538000720** está em reanálise
([12 §9.1](12-plano-p2-motor-lembretes.md#91--ses-sair-do-sandbox---em-reanálise--trava-p3)).

```bash
aws sesv2 get-account --region us-east-1 \
  --query '{status:Details.ReviewDetails.Status,cota:SendQuota}'
```

`GRANTED` → segue. `DENIED`/`PENDING` → **todo o resto deste plano pode ser
construído e verificado** com `EMAIL_DESTINATARIO_TESTE` apontando para o
endereço verificado; só o envio real para alunos espera. Não parar por isso.

### V2 · O Canvas já avisa esse aluno? — checar antes de ligar

Aviso explícito de [§2.3.4](10-problemas-e-visao.md#234-o-canvas-ajuda-com-o-agendamento-levantamento):
o Canvas notifica alunos sobre prazos sozinho, com frequência por aluno. Se
estiver ligado, o aluno recebe dois.

```bash
# canal de comunicação de um aluno de amostra e a preferência de "due date"
curl -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_BASE_URL/api/v1/users/<canvas_user_id>/communication_channels"
curl -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  "$CANVAS_BASE_URL/api/v1/users/<id>/communication_channels/<ch>/notification_preferences"
```

Interessa `due_date` / `assignment_created` / `assignment_due_date_changed`.
Tudo `never` → seguimos donos do canal. Algo em `immediately`/`daily` → decidir
**com o coordenador**: desligar no Canvas (é conta dele) ou não mandar o nosso.

### V3 · Quantos alunos têm e-mail? — mede o silêncio antes de prometer cobertura

O lembrete só existe para quem tem `aluno.email`. A coluna é preenchida pelo
sync ([sincronizar.py:527](../api/app/canvas_sync/sincronizar.py#L527)), e quem
não tem também **não consegue fazer o primeiro acesso** ([auth.py:150](../api/app/routes/auth.py#L150)) — o número serve para as duas coisas.

```sql
SELECT count(*) FILTER (WHERE email IS NOT NULL)  AS com_email,
       count(*) FILTER (WHERE email IS NULL)      AS sem_email,
       count(*) FILTER (WHERE email IS NULL AND email_verificado_em IS NOT NULL)
                                                  AS sem_email_ja_tentado
FROM aluno WHERE ativo;
```

`sem_email_ja_tentado` alto = o Canvas não tem o dado, e nenhum sync novo
resolve. É informação para o coordenador, não bug — mas precisa ser dita antes
de "os alunos são avisados".

### V4 · O tick aguenta uma rodada longa?

Uma rodada de P3 leva minutos, não milissegundos. Antes de confiar nela:
rodar `/disparos/processar` com ~50 disparos de teste e observar (a) se o
EventBridge re-entrega a chamada por timeout e (b) se a segunda entrada
atropela a primeira. A trava não-bloqueante do sync
([canvas_sync/rotas.py:31](../api/app/canvas_sync/rotas.py#L31)) existe
exatamente por isso e é o padrão a copiar — o claim por disparo já torna o
atropelo inofensivo, mas rodada dupla é desperdício e log sujo.

### V5 · A rede de segurança de desenvolvimento vem antes do envio

`EMAIL_DESTINATARIO_TESTE` e `LEMBRETE_ALUNO_ATIVO` (§4.8) são a **etapa 1**, não
um detalhe de configuração. Enquanto não existirem, nenhuma linha da varredura
roda com o banco de verdade.

---

## 3 · Modelo — migration 0020

Nenhuma tabela nova para o motor: a P2 acertou o desenho. O que entra é o
alargamento previsto, mais a chave de idempotência e a lista de endereços
queimados.

```sql
-- 1 · destinatário aluno (alargamento previsto em 0019)
ALTER TABLE regra_lembrete DROP CONSTRAINT regra_lembrete_destinatario_tipo_check;
ALTER TABLE regra_lembrete ADD  CONSTRAINT regra_lembrete_destinatario_tipo_check
    CHECK (destinatario_tipo IN ('coordenador', 'aluno'));

-- 2 · contexto da aplicação + idempotência da materialização
ALTER TABLE disparo ADD COLUMN contexto jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE disparo ADD COLUMN chave_idempotencia text;

CREATE UNIQUE INDEX idx_disparo_chave ON disparo(chave_idempotencia)
    WHERE chave_idempotencia IS NOT NULL AND estado <> 'cancelado';

-- 3 · endereços que não recebem mais nada
CREATE TABLE email_invalido (
    endereco   text PRIMARY KEY,
    motivo     text NOT NULL CHECK (motivo IN ('bounce', 'complaint', 'descadastro')),
    detalhe    text,
    criado_em  timestamptz NOT NULL DEFAULT now()
);

-- 4 · contagem do teto diário (SELECT por enviado_em)
CREATE INDEX idx_disparo_enviado_em ON disparo(enviado_em) WHERE estado = 'enviado';
```

Com os comentários que o schema do projeto exige:

- `disparo.contexto` — *"Dado opaco para o motor e significativo para a aplicação
  (`destinatario_tipo`). Lembrete de aluno guarda `{dia, aluno_id}`; P4 guardará
  o requerimento. O despachante nunca lê este campo."*
- `disparo.chave_idempotencia` — *"Identidade natural do disparo, definida pela
  aplicação. O índice único ignora `cancelado` de propósito: disparo cancelado
  libera a chave, e é isso que permite a varredura recriar o que o remarque
  desfez."*
- `email_invalido` — *"Endereços que não recebem mais nada: bounce permanente e
  complaint vindos do SNS do SES, descadastro pedido pelo destinatário.
  Deliberadamente **não** é coluna em `aluno`: professor (P4) cai na mesma
  lista."*

⚠️ **Reload do schema cache do PostgREST** — armadilha 1 da P2. O runner
([migrate.py](../api/scripts/migrate.py)) já manda `NOTIFY pgrst` ao fim de todo
up/down; só não esquecer ao aplicar por fora.

---

## 4 · Backend — arquivo por arquivo

### 4.1 · `lembretes/aplicacoes/__init__.py` — o registry

```python
@dataclass(frozen=True)
class Mensagem:
    assunto: str
    corpo: str

# destinatario_tipo → módulo da aplicação
_APLICACOES = {"coordenador": coordenador, "aluno": aluno_simulado}

def materializar_pendentes(cliente) -> dict[str, int]
    # chama .materializar() de quem tiver; devolve contagens por aplicação

def preparar(cliente, *, regra: dict, disparo: dict) -> Mensagem | None
    # despacha por regra['destinatario_tipo']; tipo desconhecido → None
    # (cancela e loga — nunca envia texto que ninguém compôs)

MATERIALIZA_SOZINHA = {"aluno"}
    # quem cuida da própria materialização; motor.regerar/cancelar não mexe
```

### 4.2 · `aplicacoes/coordenador.py` — a P2, movida

`preparar` = releitura fresca de regra + evento; `cancelada_em` ou
`cancelado_em` preenchidos → `None`; senão `compor_email` (que fica em
`motor.py`, é genérico). Sem `materializar` — quem materializa é a rota de
agendar, como sempre foi.

### 4.3 · `aplicacoes/aluno_simulado.py` — o novo

**Audiência** (função pura sobre listas já carregadas):

```python
def resolver_audiencia(cliente, *, ano_letivo_id: str) -> list[tuple[str, str]]
    # [(aluno_id, email)] — turmas do ano letivo → matrícula ativa →
    # aluno ativo com e-mail → menos os de email_invalido.
```

⚠️ **Não montar isso com `.in_()` de ~900 ids.** O PostgREST recebe o filtro na
query string e uma lista desse tamanho estoura o limite de URL. Carregar as
três tabelas inteiras (`turma` do ano, `matricula_turma` com `ativo_ate` nulo,
`aluno` ativo) e cruzar em memória — são milhares de linhas, não milhões, e é o
que [routes/alunos.py:39](../api/app/routes/alunos.py#L39) já faz.

**Varredura da véspera** — roda em todo tick, e é *reconciliação*, não
"criar uma vez":

```python
def materializar(cliente) -> dict[str, int]:
    # 0. LEMBRETE_ALUNO_ATIVO desligado → no-op
    # 1. dia = amanhã (BRT)
    # 2. eventos vivos de `dia` COM regra de aluno ativa → nenhum? cancela
    #    os disparos vivos do dia e sai
    # 3. âncora = regra do evento de menor (hora_evento, id)
    # 4. re-ancora disparos vivos do dia que apontam pra regra cancelada
    # 5. audiência − quem já OCUPA a chave do dia (inclusive 'enviado',
    #    que é terminal mas não libera a chave) → INSERT em lotes,
    #    chave 'aluno-dia:{dia}:{aluno_id}', enviar_em = dia−1 às 18:00,
    #    contexto {'dia', 'aluno_id'}
    # 6. disparo vivo de quem saiu da audiência (saiu da turma, e-mail
    #    queimado) → 'cancelado'
```

Os disparos do dia são achados por `chave_idempotencia LIKE
'aluno-dia:{dia}:%'` — filtro em coluna de texto, sem depender de operador
jsonb no PostgREST (a armadilha 2 da P2 ensinou a desconfiar da query string).

⚠️ **Duas listas, não uma** — e confundi-las foi o primeiro bug real:
`ocupados` (tudo que não é `cancelado`, espelhando o índice único) decide quem
**já tem** lembrete; `vivos` (o subconjunto que ainda pode mudar de estado)
decide quem pode ser re-ancorado ou cancelado. E-mail já enviado é histórico:
não se re-ancora, não se cancela, e **não se recria**.

**Guarda + composição:**

```python
def preparar(cliente, *, regra, disparo) -> Mensagem | None:
    # dia = disparo['contexto']['dia']  (NÃO a data da regra âncora —
    #   ela pode ter sido remarcada pra outro dia)
    # eventos = vivos naquele dia, com regra de aluno ativa, ordenados por hora
    # vazio → None (o dia esvaziou; o disparo vira 'cancelado', nada sai)
    # senão → digest
```

```
Assunto: Simulados de amanhã (21/08) — 2 provas

Olá, Fulano.

Amanhã, 21/08/2026, você tem:

  07:00 · 1° CICLO - P3 - Matemática
  09:30 · 1° CICLO - P4 - Física

Bons estudos.

— SAS · Colégio Ari de Sá
Não quer mais receber estes lembretes? <link de descadastro>
```

A composição é função pura (`compor_digest(nome, dia, eventos) -> Mensagem`) e é
o que os testes cobrem.

⚠️ **Uma prova do dia cancelada não cancela o e-mail** — ela some da lista. Só
quando o dia inteiro esvazia é que `preparar` devolve `None`. Essa é a razão de
a guarda ter saído do despachante.

### 4.4 · `lembretes/despachante.py` — ritmo, orçamento, teto

Muda pouco, e nada da máquina de estados:

| Onde | Mudança |
|---|---|
| início do tick | `aplicacoes.materializar_pendentes(cliente)` antes da fila — a varredura precede o envio no mesmo tick, **isolada num try**: materializar e enviar são independentes, e um erro na varredura não pode segurar o que já está materializado (o erro vai no resultado do tick) |
| guarda + texto | o bloco de `cancelada_em`/`compor_email` vira `aplicacoes.preparar(...)`; `None` → `cancelado`, como hoje |
| ritmo | `sleep(1 / EMAIL_ENVIOS_POR_SEGUNDO)` entre envios |
| orçamento | laço para quando passa de `LEMBRETES_ORCAMENTO_SEGUNDOS`; devolve `restantes` nas contagens |
| teto diário | conta `enviado` de hoje antes do laço; ao bater `EMAIL_TETO_DIARIO`, para com `motivo='teto_diario'` — não marca `falhou` (não é erro, e não pode gastar tentativa) |
| ordem da fila | `enviar_em` (já é) — o mais atrasado primeiro, sempre |

O `_carregar_contexto` passa a trazer `destinatario_tipo` (o registry precisa)
e o resto da releitura migra para dentro das aplicações.

### 4.5 · `lembretes/email.py` — configuration set, teste, Reply-To

```python
def enviar_email(*, destinatario, assunto, corpo) -> None:
    # EMAIL_DESTINATARIO_TESTE preenchido → manda pra ele, com o destinatário
    #   real prefixado no assunto ("[para: aluno@x] ...").
    #   É a rede que impede 873 e-mails reais saírem de um curl de teste.
    # ConfigurationSetName=EMAIL_CONFIGURATION_SET  → é o que faz o SES
    #   publicar bounce/complaint no SNS (§4.6)
    # ReplyToAddresses=[coordenador_email]
```

### 4.6 · Bounces e descadastro — a etapa 0

**Lado AWS** (uma vez, com o CLI — mesma conta do EventBridge):

```bash
aws sns create-topic --name sas-ses-eventos --region us-east-1
aws sesv2 create-configuration-set --configuration-set-name sas-lembretes --region us-east-1
aws sesv2 create-configuration-set-event-destination \
  --configuration-set-name sas-lembretes \
  --event-destination-name sns-bounces \
  --event-destination "Enabled=true,SnsDestination={TopicArn=<arn>},MatchingEventTypes=BOUNCE,COMPLAINT,REJECT" \
  --region us-east-1
aws sns subscribe --topic-arn <arn> --protocol https \
  --notification-endpoint https://<api>/email/eventos-ses/<token>
```

**Lado SAS** — `routes/email_eventos.py`:

| Rota | O que faz |
|---|---|
| `POST /email/eventos-ses/{token}` | Endpoint público (SNS não manda header customizado) — a autenticação é o **token no path** (`SES_WEBHOOK_TOKEN`) mais conferência do `TopicArn` contra `SES_SNS_TOPIC_ARN`. `SubscriptionConfirmation` → GET no `SubscribeURL` (só se o ARN bater). `Notification` → `interpretar_evento_ses` |
| `GET /lembretes/descadastrar` | `?e=<email>&t=<hmac>`; HMAC confere → `email_invalido` motivo `descadastro` → página de confirmação. Link do rodapé de todo lembrete de aluno |

```python
def interpretar_evento_ses(payload: dict) -> list[tuple[str, str, str]]
    # [(endereco, motivo, detalhe)] — função pura, testável:
    #   Bounce/Permanent  → ('bounce', bounceSubType)
    #   Bounce/Transient  → IGNORA (o retry do disparo cuida)
    #   Complaint         → ('complaint', ...)
```

⬜ **Verificação de assinatura do SNS fica de fora** (token no path + ARN
conferido é a barreira). O que o endpoint faz no pior caso — marcar um endereço
como inválido — é reversível por `DELETE` na tabela, e não vaza nada. Se o
endpoint virar alvo, a assinatura entra depois sem mudar o resto.

### 4.7 · Rotas de simulado

| Rota | Mudança |
|---|---|
| `POST /simulados/agendar` | body ganha **`avisarAlunos: bool = True`**. Verdadeiro → depois do evento, cria a regra `destinatario_tipo='aluno'`, `dias_antes=1`, **sem materializar** (a varredura faz, na véspera). Sem SES configurado, `avisarAlunos` não dá 422 como o lembrete do coordenador: **degrada com aviso no corpo da resposta** — o lembrete de aluno é acessório do simulado, não pode impedir o agendamento |
| `PATCH /simulados/{id}` | já chama `regerar_disparos_do_evento`; o motor passa a **pular regras de `MATERIALIZA_SOZINHA`** — regerar um digest com um destinatário só produziria lixo. Quem reconcilia é a varredura |
| `DELETE /simulados/{id}` | `cancelar_disparos_do_evento` idem: cancela a **regra** de aluno, mas **não** os disparos dela — o digest pode pertencer a um dia que ainda tem outras provas. A varredura re-ancora ou cancela no tick seguinte |
| `GET /simulados` | (opcional, 10 linhas) `avisaAlunos: bool` no payload, para a UI mostrar |

⚠️ Essas três linhas de `MATERIALIZA_SOZINHA` são o ponto mais fácil de errar
do plano inteiro: sem elas, remarcar um simulado cria um disparo órfão com
`destinatario` vazio, e cancelar uma prova cala o dia todo.

### 4.8 · `config.py` + `.env.example`

```python
# Lembrete de aluno (P3, docs/13). Desligado por default: ligar exige decisão.
lembrete_aluno_ativo: bool = False
lembrete_aluno_hora: str = "18:00"        # véspera, BRT
email_envios_por_segundo: float = 5.0
lembretes_orcamento_segundos: int = 240
email_teto_diario: int = 150              # sandbox corta em 200/24h
email_destinatario_teste: str = ""        # preenchido → TUDO vai pra cá
email_configuration_set: str = ""         # bounces/complaints no SNS
ses_sns_topic_arn: str = ""
ses_webhook_token: str = ""
lembrete_token_secret: str = ""           # HMAC do link de descadastro
```

### 4.9 · Testes — `api/tests/test_lembretes.py` (continuação)

Tudo função pura; banco fica na verificação manual da §6:

- `compor_digest`: 1 prova, 3 provas ordenadas por hora, nome do aluno, link de
  descadastro presente, assunto não vazio.
- `momento_envio_aluno`: véspera às 18:00, fuso `-03:00`, virada de mês.
- `escolher_ancora`: menor `hora_evento`; empate resolvido por id (estável).
- `chave_idempotencia`: formato e estabilidade (mesmo aluno, mesmo dia → mesma
  chave; e-mail trocado **não** muda a chave).
- `filtrar_audiencia`: exclui aluno inativo, matrícula encerrada, e-mail nulo,
  e-mail em `email_invalido`; não duplica aluno com duas matrículas.
- `interpretar_evento_ses`: bounce permanente entra, transiente é ignorado,
  complaint entra, payload desconhecido não explode.
- `aplicar_destinatario_teste` e o HMAC do descadastro (ida, volta, adulteração).

E uma suíte de **fluxo** — `api/tests/test_lembrete_aluno_fluxo.py`, sobre o
fake do PostgREST (`tests/fake_postgrest.py`): materializa 1 por aluno, não
duplica na segunda rodada, duas provas no mesmo dia continuam um e-mail só,
aluno que sai da turma é cancelado, cancelar uma prova re-ancora, dia
esvaziado não envia, remarque cancela e rematerializa, falha vira estado e
re-tenta, teto para sem gastar tentativa, endereço queimado não recebe.

⚠️ O fake **não** substitui a §6: ali o índice único é imitado em Python, o
claim não tem concorrência real e o schema cache do PostgREST não existe.

---

## 5 · Frontend

| Arquivo | Mudança |
|---|---|
| [components/agendar-simulado.js](../web/js/components/agendar-simulado.js) | Segunda linha no bloco de lembrete, **marcada por default**: `☑ Avisar os alunos por e-mail na véspera`. Legenda pequena com o que vai acontecer: *"~873 alunos recebem um e-mail às 18:00 do dia anterior"* — o número vem de `GET /alunos` já carregado, ou é texto fixo |
| [services/api.js](../web/js/services/api.js) | typedef de `agendarSimulado` ganha `avisarAlunos` |

Nada além disso. Estado de disparo, histórico e reenvio são a tela de
calendário ([§2.6](10-problemas-e-visao.md#26-a-tela-de-gestão-do-calendário)) —
mesma fronteira que a P2 respeitou.

---

## 6 · Ordem de execução

| # | Etapa | Verificação |
|---|---|---|
| 0 ⏳ | Pré-voo V2/V3/V4 (§2) — Canvas duplicando?, cobertura de e-mail, tick longo | os três números anotados; V1 (SES) corre em paralelo, sem bloquear |
| 1 ✅ | **Rede de dev**: `EMAIL_DESTINATARIO_TESTE` + `LEMBRETE_ALUNO_ATIVO` (§4.8, §4.5) | com a variável preenchida, um envio para `qualquer@dominio` chega no endereço de teste com `[para: ...]` no assunto |
| 2 ⏳ | Migration 0020 (§3) | `migrate up`/`down`/`up` limpos; índice único rejeita chave duplicada e **aceita** depois de cancelar |
| 3 ✅ | Bounces: SNS + configuration set + `POST /email/eventos-ses` (§4.6) | `aws sns publish` de um payload de bounce → linha em `email_invalido`; SNS confirma a subscription sozinho |
| 4 ✅ | Descadastro (§4.6) | clicar no link do rodapé → confirmação; o endereço some da audiência na varredura seguinte |
| 5 ✅ | `aplicacoes/` + mover a P2 pra `coordenador.py` (§4.1, §4.2) | **a suíte da P2 passa igual** e um lembrete de coordenador ainda chega — o refactor é invisível |
| 6 ✅ | `aluno_simulado.py` + testes (§4.3, §4.9) | suíte passa; audiência de um ciclo real bate com a contagem do V3 |
| 7 ✅ | Ritmo/orçamento/teto no despachante (§4.4) | 60 disparos de teste: saem espaçados, o orçamento corta a rodada, o tick seguinte continua de onde parou, o teto diário para sem gastar tentativa |
| 8 ✅ | Rota + UI de `avisarAlunos` (§4.7, §5) | agendar simulado pra amanhã pela UI → regra de aluno criada, **nenhum disparo ainda** |
| 9 ✅ | **Varredura**: `LEMBRETE_ALUNO_ATIVO=true`, ainda com destinatário de teste | 1 disparo por aluno da audiência, `enviar_em` = hoje 18:00; rodar de novo **não duplica** |
| 10 ✅ | **Digest**: segundo simulado no mesmo dia | continua **um** disparo por aluno; o corpo passa a listar as duas provas, em ordem de hora |
| 11 ✅ | **Cancelar uma das duas** | e-mail sai com a prova restante. Cancelar a última → disparos do dia `cancelado`, nada sai |
| 12 ✅ | **Remarcar** para outro dia | disparos do dia antigo cancelados; na véspera do dia novo, materializa de novo com a audiência daquele momento |
| 13 ⏳ | **Envio real** (depende do V1 aprovado) | tirar `EMAIL_DESTINATARIO_TESTE`, subir `EMAIL_TETO_DIARIO`, e deixar o tick rodar sozinho na véspera de um simulado de verdade |

✅ = código escrito e coberto pela suíte (60 testes) · ⏳ = depende de banco,
da AWS ou do coordenador. As etapas 9–12 estão ✅ pela suíte de fluxo sobre o
fake do PostgREST; **a confirmação no Postgres de verdade é a [§10](#10--o-que-falta-20082026)**.

**A etapa 13 é a que fecha o "pronto quando"** — e é a única que depende de
terceiro (§7). Da 1 à 12 tudo é verificável hoje, em sandbox.

⚠️ Ordem deliberada: a **rede de dev é a etapa 1** e os **bounces vêm antes da
audiência**. Nas duas, o custo de inverter é irreversível — e-mail que saiu não
volta, e reputação queimada no SES trava a conta inteira.

---

## 7 · Riscos

| Risco | Sinal | O que fazer |
|---|---|---|
| **SES ainda em sandbox na hora de ligar** | `get-account` em `DENIED`/`PENDING` | etapas 1–12 seguem em destinatário de teste; só a 13 espera. Andar em paralelo com a identidade de domínio ([12 §9.3](12-plano-p2-motor-lembretes.md#93--domínio-do-colégio--remetente-definitivo--depende-do-dns-do-colégio)), que é o que a AWS pediu |
| **873 e-mails reais saindo de um teste** | — | `EMAIL_DESTINATARIO_TESTE` + `LEMBRETE_ALUNO_ATIVO=false` + `EMAIL_TETO_DIARIO=150`. Três redes, de propósito: é o erro que não tem desfazer |
| **Aluno recebe dois avisos** (nosso + Canvas) | V2 com preferência ligada | decidir com o coordenador antes da etapa 13; desligar de um lado |
| **Aluno sem e-mail não recebe, e ninguém sabe** | V3 com `sem_email` alto | número dito ao coordenador na entrega; o mesmo dado já afeta o primeiro acesso |
| **Simulado criado direto no Canvas não avisa ninguém** | prova acontece, e-mail nenhum saiu | decisão consciente (§1). ⬜ Se doer, o remendo é o sync criar `evento_agenda` para simulado futuro sem evento — meia hora, e fica registrado aqui |
| **Bounce em massa suspende a conta** | taxa de rejeição subindo no console do SES | etapa 3 antes de qualquer volume; `email_invalido` corta o endereço na primeira falha permanente |
| **Rodada estourando o timeout do EventBridge** | entregas re-tentadas no log | trava não-bloqueante + claim por disparo: atropelo é desperdício, não dano. O orçamento por tick mantém a rodada curta |
| **Remarque/cancelamento mexendo no digest** | disparo órfão, dia calado | `MATERIALIZA_SOZINHA` (§4.7) + reconciliação a cada tick. E o pior caso se cura sozinho: disparo cancelado libera a chave, e a varredura recria com `enviar_em` no passado — sai no tick seguinte |
| **Corrida entre varredura e envio no mesmo tick** | cancelamento às 17:59 | a varredura roda **antes** da fila no mesmo tick; a janela restante é de segundos e se cura no tick seguinte |
| **Aluno responde o lembrete** | resposta na caixa do dev | `ReplyToAddresses = coordenador_email` desde o primeiro envio |
| **Dado de menor de idade em massa** | — | conteúdo mínimo (título, data, hora), sem nota nem desempenho; nada de link autenticado no corpo |

---

## 8 · O que P3 deixa em aberto de propósito

- **Cadência** (3 dias antes + 1 dia antes + no dia) — P4 estende a
  materialização, não o despachante. `dias_antes` já está no schema.
- **Lembrete de insight de ciclo novo** ([§2.5](10-problemas-e-visao.md#25-aplicação-2--lembretes-de-aluno-e-de-coordenador))
  — é outra aplicação no registry, e agora custa um arquivo.
- **WhatsApp para aluno** — P5, e a pergunta "aluno também recebe por WhatsApp?"
  segue aberta no doc 10. O digest ajuda: 873 mensagens/dia de prova, não 2.6k.
- **UI de acompanhamento** (quem recebeu, quem falhou, reenviar) — tela de
  calendário (§2.6).
- **Preferência por aluno** ("quero receber 3 dias antes") — não pedido por
  ninguém; o descadastro cobre o caso extremo.
- **Verificação de assinatura do SNS** (§4.6) — token no path por ora.
- **Bounce transiente** — ignorado; quem re-tenta é a máquina de estados.
- **Ligar o despachante no tick de 5 min** — está no plano (§1) porque é uma
  linha; se atrapalhar o sync, volta a ser só horário.
- **Renomear `/cobranca/verificar` no CDK** — segue esperando um `cdk deploy`
  que exista por outro motivo, como na P2.

---

## 9 · Dependências externas

Nenhuma delas é código, e duas não são nossas:

| Dependência | De quem | Trava o quê |
|---|---|---|
| Saída do sandbox do SES (caso 178722538000720) | AWS | só a etapa 13 |
| Identidade de domínio + remetente do colégio ([12 §9.3](12-plano-p2-motor-lembretes.md#93--domínio-do-colégio--remetente-definitivo--depende-do-dns-do-colégio)) | DNS do colégio | entrega decente; hoje `@gmail.com` via Amazon cai em spam |
| Preferências de notificação do Canvas (V2) | conta do coordenador | ligar sem duplicar |
| Produção do SAS ([12 §9.5](12-plano-p2-motor-lembretes.md#95--produção-do-sas--pendência-herdada-da-p1-com-decisão-embutida)) | nós, mas com decisão pendente | o endpoint público do SNS (§4.6) precisa de URL estável, e o tick real precisa de host |

---

## 10 · O que falta (20/08/2026)

Nenhum item é código novo. Em ordem de urgência:

### 10.1 · Aplicar a 0020 e repetir as etapas 9–12 no Postgres

O fake da suíte imita o índice único parcial em Python. O que ele **não** prova:
o índice de verdade, o CAS do claim sob concorrência, e o schema cache do
PostgREST (armadilha 1 da P2 — tabela recém-migrada devolve 404 em INSERT até
o `NOTIFY pgrst`, que o runner já manda sozinho).

```bash
cd api && ./.venv/bin/python -m scripts.migrate up     # e down, e up de novo
```

Depois: agendar um simulado pra amanhã com o checkbox marcado, chamar
`POST /disparos/processar` e conferir 1 disparo por aluno — com
`EMAIL_DESTINATARIO_TESTE` preenchido, sempre.

### 10.2 · Pré-voo V2 e V3 (§2) — dois números e uma decisão

- **V3** (o `SELECT` de cobertura de e-mail) diz quantos alunos ficam de fora
  em silêncio. É número pro coordenador, não bug.
- **V2** (preferências de notificação do Canvas) decide se o aluno vai receber
  dois avisos. **Precisa do coordenador**, e é a única pendência que pode
  obrigar a mudar algo antes de ligar.

### 10.3 · AWS: tópico SNS, configuration set, assinatura

Comandos na §4.6. O endpoint `/email/eventos-ses/{token}` precisa de URL
pública — depende de [12 §9.5](12-plano-p2-motor-lembretes.md#95--produção-do-sas--pendência-herdada-da-p1-com-decisão-embutida)
(onde é produção agora, depois do Supabase). Enquanto isso, o fluxo é
testável mandando o payload do SNS direto no endpoint local.

### 10.4 · Sair do sandbox do SES — trava a etapa 13

Caso 178722538000720, em reanálise ([12 §9.1](12-plano-p2-motor-lembretes.md#91--ses-sair-do-sandbox---em-reanálise--trava-p3)).
Com o tratamento de bounces agora **implementado** (§4.6), a reanálise tem o
que a AWS pediu — vale dizer isso no caso.

### 10.5 · Ligar: `LEMBRETE_ALUNO_ATIVO=true`

Última linha, de propósito: o default é desligado. Ligar depois de 10.1, 10.2
e 10.4 — e com `EMAIL_TETO_DIARIO` subido pro limite real da conta.
