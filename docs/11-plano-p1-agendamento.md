# 11 — Plano de implementação · P1 · O simulado nasce no SAS

> **Escopo:** a primeira das 5 partes da Sprint 1 ([10-problemas-e-visao.md §2.10](10-problemas-e-visao.md#210-sprint-1--escopo-e-divisão-17082026)).
> **Objetivo:** inverter a fonte da verdade. O ciclo e o simulado passam a ser
> **criados no SAS**, e é o SAS que cria os objetos correspondentes no Canvas.
> **Não entra aqui:** motor de disparos, lembretes, professores, WhatsApp (P2–P5).

**Pronto quando:** o coordenador cria um ciclo e um simulado no SAS, os dois
aparecem no Canvas, e nem o sync de 5 min nem o reconcile das 3h desfazem nada
do que ele preencheu.

> **Estado (18/08/2026): implementado e verificado ponta a ponta no ambiente
> local** — migration 0018 aplicada no Postgres local, todas as etapas da §7
> exercitadas contra o curso sandbox do Canvas (`SAS · testes (não usar)`,
> id 694) e a não-sobrescrita provada contra o curso real 577 (só leitura).
> **Pendente:** aplicar a 0018 no Supabase (fora do ar desde 13/08 — NXDOMAIN)
> e deploy da API/web. V1/V2/V3 verificados: token escreve; ordens não colidem
> entre ITA/IME; um curso por ano (2026 = 577).

---

## 1 · Decisões fechadas

| Questão | Decisão |
|---|---|
| Falha na criação no Canvas | **Híbrido** para simulado: tenta no request, se falhar nasce em `canvas_estado='falhou'` e o sync de 5 min reprocessa. **Transacional** para ciclo (§3.4) |
| Ambiente de teste | **Não existe** — criar um curso `SAS · testes (não usar)` na conta antes de escrever código |
| Escopo da escrita | Criação **e** edição (`POST` e `PUT`) |
| Regra retroativa pros 148 simulados atuais | `origem='canvas'` por DEFAULT → a regra de não-sobrescrita vale **só pros novos** |
| **Assignment ou Quiz** | **Assignment.** Sem `quiz_id`, sem detalhe por questão — ver §1.1 |
| **Criar ciclo também** | **Sim.** "Agendar" = criar, e criar sincroniza com o Canvas. Puxa `POST /assignment_groups` pra dentro de P1 — ver §1.2 |
| Desmarcar simulado | `DELETE` do Assignment no Canvas + `cancelado_em` preenchido no SAS (histórico preservado, aluno não vê prova fantasma) |
| Nº de questões no agendamento | **Sempre conhecido** — `nota_maxima` é campo obrigatório na tela |
| Hora do simulado | Default **07:00**, editável no formulário |
| Testes automatizados | **Criar `api/tests/`** com o teste de round-trip dos nomes (§4.2) |
| Simulado futuro nas estatísticas | **Só conta a partir da data.** Agendados aparecem em seção separada — ver §6 |
| Criar o curso do ano no SAS | **Fora do escopo.** Curso carrega matrículas e turmas, que são do Canvas por origem administrativa |

### 1.1 · Consequência de ter escolhido Assignment

Um Assignment puro nasce sem `quiz_id`, e `quiz_id` é o portão de tudo que é por
questão: a tabela `questao` ([0010:75-83](../api/migrations/0010_expansao_canvas.sql)),
o Quiz Statistics (texto da questão + gabarito + distribuição das alternativas)
e `duracao_media_segundos`. O simulado criado pelo SAS nasce equivalente ao que
[08 §3.3](08-integracao-canvas.md) chama de *"reforço/reposição"*.

⚠️ **E não dá pra converter depois.** Se alguém montar a prova como Quiz no Canvas,
o Quiz cria um Assignment **próprio** — e a prova fica com duas colunas no diário.
Combinar com o coordenador: prova criada pelo SAS não vira Quiz.

### 1.2 · O que "criar o ciclo" acrescenta

O ciclo no SAS é o Assignment Group do Canvas (`"3° CICLO - ITA"`,
[08 §3.2](08-integracao-canvas.md)). Criar ciclo no SAS = criar o grupo lá.
Endpoint existe: `POST /api/v1/courses/:course_id/assignment_groups`
([assignment_groups.md:173](canvas-api/reference/assignment_groups.md)), só precisa
de `name`.

Isso acrescenta três coisas ao plano — e **eleva o risco da verificação V2** de
"talvez" para "provavelmente bloqueia" (§2.2).

```
        criar CICLO                       criar SIMULADO
             │                                  │
POST /courses/:id/assignment_groups   POST /courses/:id/assignments
      name: "3° CICLO - ITA"            name: "3_P2 - Matemática - 20/09/2026"
             │                          assignment_group_id: ◀── do ciclo
             ▼                                  ▼
      ciclo.canvas_assignment_group_id    simulado.external_id
```

---

## 2 · Pré-voo — verificações antes da primeira linha de código

### V1 · O token do Canvas tem permissão de escrita?

Hoje o token é usado **só para leitura** ([`cliente.py`](../api/app/canvas_sync/cliente.py)
só tem `_get`). Nada garante que ele possa criar.

```bash
# 1. criar o curso de teste pela UI do Canvas: "SAS · testes (não usar)"
# 2. anotar o course_id e:
curl -X POST "$CANVAS_BASE_URL/api/v1/courses/$COURSE_TESTE/assignments" \
  -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"assignment":{"name":"teste sas","points_possible":10,"published":true}}'

curl -X POST "$CANVAS_BASE_URL/api/v1/courses/$COURSE_TESTE/assignment_groups" \
  -H "Authorization: Bearer $CANVAS_API_TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"9° CICLO - ITA"}'
```

**403** → P1 trava aqui; depende de quem administra o Canvas. **201** → segue.

### V2 · ⚠️ Um `ciclo` do SAS pode representar dois grupos do Canvas

**Esta é a verificação que decide o tamanho de P1.**

No Canvas os grupos são **ciclo + vestibular**: `"1° CICLO - IME"`, `"2° CICLO - ITA"`.
No SAS, `ciclo` é `UNIQUE (ano_letivo_id, ordem)` — **sem o vestibular na chave**
([0001:105-114](../api/migrations/0001_schema_inicial.sql)) — e o colapso é
deliberado: [`detectar_vestibulares_por_ciclo`](../api/app/ingest/header.py#L186)
documenta *"prioriza ITA > IME"* quando a mesma ordem aparece com mais de um.

Enquanto o SAS só **lia**, isso passou batido (aparentemente as ordens se alternam
entre ITA e IME). Mas se o coordenador puder **criar** `3° Ciclo ITA` e depois
`3° Ciclo IME`, o segundo `INSERT` viola a UNIQUE. Não é mais risco teórico: é o
caminho normal de uso.

```bash
curl -s "$CANVAS_BASE_URL/api/v1/courses/$COURSE_ID/assignment_groups?per_page=100" \
  -H "Authorization: Bearer $CANVAS_API_TOKEN" | jq -r '.[].name' | sort
```

| Resultado | Consequência |
|---|---|
| Ordens **não** se repetem entre ITA e IME | segue o plano como está |
| Ordens **se repetem** | migration extra: chave de `ciclo` vira `(ano_letivo_id, ordem, vestibular_alvo)`. Toca `upsert_ciclo`, o sync e tudo que consulta ciclo — **entra na estimativa** |

❓ Mesmo se hoje não se repetirem: a tela vai **permitir** criar os dois? Se sim,
a migration é necessária de qualquer forma.

### V3 · Um curso de simulados por ano, ou mais de um?

O sync descobre curso por nome (`{ano} 3o ITA/IME Simulados`,
[`PADRAO_CURSO_SIMULADOS`](../api/app/canvas_sync/mapeador.py#L36)) e **não guarda
o `course_id`**. Criando de fora, o SAS precisa dele.

```bash
curl -s "$CANVAS_BASE_URL/api/v1/accounts/1/courses?per_page=100&state[]=available" \
  -H "Authorization: Bearer $CANVAS_API_TOKEN" | jq -r '.[] | "\(.id)\t\(.name)"' | grep -i simulado
```

Um por ano → `canvas_course_id` mora em `ano_letivo` (§3.3) e some da UI.
Mais de um → a tela precisa oferecer escolha e a coluna sobe pro `ciclo`.

---

## 3 · Modelo — o que entra no banco (migration 0018)

### 3.1 · `evento_agenda` — a âncora do motor

Tabela genérica: *"algo marcado numa data"*. Existe em P1 mas só é usada de
verdade em P2, quando `regra_lembrete` e `disparo` penduram nela.

**A direção da FK importa:** é `simulado.evento_agenda_id`, e **não**
`evento_agenda.simulado_id`. Assim o motor nunca conhece o domínio — requisito de
[§2.2.2](10-problemas-e-visao.md#222-motor-e-aplicações).

```sql
CREATE TABLE evento_agenda (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo           text NOT NULL CHECK (tipo IN ('simulado')),
    titulo         text NOT NULL,
    data_evento    date NOT NULL,
    hora_evento    time NOT NULL DEFAULT '07:00',
    criado_por     text,
    cancelado_em   timestamptz,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_evento_agenda_data ON evento_agenda(data_evento);
```

`criado_por` é texto (e-mail) de propósito: **não existe tabela de usuário** — o
coordenador é uma credencial em [`config.py`](../api/app/config.py). Vira FK quando existir.

`cancelado_em` em vez de boolean porque P2 vai precisar saber *quando*, pra decidir
o que fazer com os disparos já materializados.

### 3.2 · `simulado` — fase pré-aplicação

```sql
ALTER TABLE simulado ALTER COLUMN external_id DROP NOT NULL;

ALTER TABLE simulado ADD COLUMN evento_agenda_id uuid REFERENCES evento_agenda(id);
ALTER TABLE simulado ADD COLUMN origem text NOT NULL DEFAULT 'canvas'
    CHECK (origem IN ('canvas','sas'));
ALTER TABLE simulado ADD COLUMN canvas_estado text NOT NULL DEFAULT 'sincronizado'
    CHECK (canvas_estado IN ('sincronizado','pendente','falhou'));
ALTER TABLE simulado ADD COLUMN canvas_erro text;
ALTER TABLE simulado ADD COLUMN canvas_tentativas int NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX idx_simulado_sas_unico
    ON simulado (ciclo_id, rotulo_curto, materia_id) WHERE origem = 'sas';
```

⚠️ **Não trocar a UNIQUE de `external_id` por índice parcial.** A tentação é
`CREATE UNIQUE INDEX ... WHERE external_id IS NOT NULL`, mas isso quebra o sync:
[`upsert_simulados_em_lote`](../api/app/ingest/upsert.py#L285) usa
`on_conflict="external_id"`, e o Postgres só aceita índice **parcial** como árbitro
de `ON CONFLICT` se o `WHERE` for repetido na query — coisa que o PostgREST não
emite. A UNIQUE simples resolve: pela semântica padrão do Postgres, **múltiplos
NULL não conflitam entre si**.

Os `DEFAULT` fazem o backfill dos 148 legados de graça — eles nascem
`origem='canvas'` e continuam espelho do Canvas, como hoje.

O índice único não cobre `materia_id IS NULL` (`NULL <> NULL`), então a checagem
explícita na rota (§4.5) é a guarda de verdade contra duplo clique.

### 3.3 · Onde o Canvas é criado

```sql
ALTER TABLE ano_letivo ADD COLUMN canvas_course_id text;
ALTER TABLE ciclo      ADD COLUMN canvas_assignment_group_id text;
```

`canvas_course_id` mora em **`ano_letivo`**, não em `ciclo`: é um curso por ano
(`{ano} 3o ITA/IME Simulados`), e assim um ciclo **novo** já sabe onde nascer antes
de existir no Canvas. *(Se V3 mostrar mais de um curso por ano, a coluna sobe pro ciclo.)*

Sem script de backfill: o sync já tem os dois valores em mãos
([`sincronizar.py:191-208`](../api/app/canvas_sync/sincronizar.py)) — basta passá-los
adiante e a primeira rodada preenche tudo.

⚠️ **Sem `canvas_assignment_group_id`, o Assignment criado cai no grupo padrão, o
sync vê `ciclo_id is None` e pula** ([`sincronizar.py:219-220`](../api/app/canvas_sync/sincronizar.py)) —
o simulado ficaria órfão no Canvas, invisível pro SAS. É a peça que fecha o round-trip.

### 3.4 · Por que ciclo é transacional e simulado não

Um ciclo que existe no SAS mas não no Canvas **não serve pra nada** — nenhum
simulado pode ser criado nele. Um simulado em limbo, sim: o coordenador já
registrou a data e P2 pendura o lembrete nela. Por isso `ciclo` não ganha
`canvas_estado`: falhou, devolve erro e ele tenta de novo.

`ciclo` também não ganha `origem`. O `nome` no SAS é derivado de
(ordem, vestibular, ano) nos dois caminhos — não há nada a proteger do sync.

---

## 4 · Backend — arquivo por arquivo

### 4.1 · `canvas_sync/cliente.py` — escrita

Entram `_post`/`_put`/`_delete` e quatro métodos de domínio:

```python
async def criar_assignment_group(self, course_id: str, *, nome: str) -> dict
async def criar_assignment(self, course_id: str, *, assignment: dict) -> dict
async def atualizar_assignment(self, course_id: str, assignment_id: str, *, assignment: dict) -> dict
async def apagar_assignment(self, course_id: str, assignment_id: str) -> dict
```

Corpo do POST de assignment ([assignments.md:764](canvas-api/reference/assignments.md)):

```json
{"assignment": {
  "name": "3_P2 - Matemática - 20/09/2026",
  "points_possible": 20,
  "due_at": "2026-09-20T07:00:00-03:00",
  "assignment_group_id": 4312,
  "submission_types": ["on_paper"],
  "published": true
}}
```

⚠️ **`_post` NÃO pode reusar a política de retry do `_get`.** Duas razões:

1. `_get` trata **403 como rate limit** e repete — mas 403 num POST é "sem
   permissão", e repetir só atrasa o erro.
2. Repetir um POST que talvez tenha chegado **cria objeto duplicado**. Não há
   chave de idempotência na API do Canvas.

Regra: **POST não repete.** Falhou → `canvas_estado='falhou'`, e o reprocessamento
(§4.4) resolve. `PUT` e `DELETE` são idempotentes e podem repetir.

⚠️ `published: true` é obrigatório: o sync descarta assignment não publicado
([`sincronizar.py:219`](../api/app/canvas_sync/sincronizar.py)). Consequência a
registrar — publicar com `due_at` futuro **pode disparar a notificação nativa do
Canvas pro aluno** ([§2.3.4](10-problemas-e-visao.md#234-o-canvas-ajuda-com-o-agendamento-levantamento)).
Inofensivo em P1, mas é o risco de duplicação que P3 precisa checar.

`-03:00` fixo no `due_at`: o Brasil não tem horário de verão desde 2019.

### 4.2 · `canvas_sync/mapeador.py` — compor os nomes

Dois inversos exatos dos parsers que já existem:

| Nova função | Inverso de | Exemplo |
|---|---|---|
| `compor_nome_assignment(ordem, rotulo, materia_nome, data)` | [`parsear_nome_assignment`](../api/app/canvas_sync/mapeador.py#L91) | `3_P2 - Matemática - 20/09/2026` |
| `compor_nome_grupo_ciclo(ordem, vestibular)` | [`parsear_grupo_ciclo`](../api/app/canvas_sync/mapeador.py#L79) | `3° CICLO - ITA` |

A matéria vem de `materia.nome` (canônico), não do que o usuário digitou.

**É aqui que entra `api/tests/`**, com o teste que garante
`parsear(compor(x)) == x` pros dois. É o que impede a gramática de sair de
sincronia consigo mesma daqui a três meses — e o projeto não tem suíte nenhuma
hoje (pytest já está no venv, falta só o diretório).

### 4.3 · A regra de não-sobrescrita — o coração de P1

> *Campo originado no SAS nunca é sobrescrito pelo sync.*

Em [`sincronizar.py`](../api/app/canvas_sync/sincronizar.py), antes de
`upsert_simulados_em_lote`: consultar quais `external_id` do lote já existem com
`origem='sas'` e separar em **dois lotes**.

| Lote | Payload | Campos |
|---|---|---|
| `origem='canvas'` | completo, como hoje | tudo de `mapear_simulado` |
| `origem='sas'` | reduzido | só `external_id`, `quiz_id`, `unlock_at`, `lock_at` |

`nome`, `rotulo_curto`, `nota_maxima`, `data_aplicacao`, `tipo`, `ciclo_id` e
`materia_id` deixam de vir do Canvas para os simulados do SAS. Notas, presença e
questões continuam vindo de lá — **não são do SAS**
([§2.3.5](10-problemas-e-visao.md#235-fonte-da-verdade--decidido-sas-origina-canvas-recebe)).

⚠️⚠️ **Dois lotes, não um lote com chaves faltando.** O upsert em massa do
PostgREST usa a **união das chaves** de todas as linhas do array; quem não tiver
uma chave recebe o DEFAULT da coluna. Misturar payload completo e reduzido no
mesmo array **zera `nome` das linhas reduzidas**. Duas chamadas separadas.

Segundo ponto no mesmo laço: hoje o simulado é reconhecido pelo **nome**, e nome
fora da gramática é descartado com aviso
([`sincronizar.py:221-227`](../api/app/canvas_sync/sincronizar.py)). Para
`origem='sas'` a ordem inverte — **casar por `external_id` primeiro**. Se já é
conhecido e é do SAS, segue pelo caminho reduzido independentemente do nome, e
ninguém renomeando à mão no Canvas consegue derrubá-lo do SAS.

### 4.4 · Reprocessamento dos que ficaram em limbo

Entra **dentro de `/canvas-sync/run`** (5 min), não num schedule novo: é o mesmo
assunto, já tem trava contra execução sobreposta, e **não exige `cdk deploy`** —
P1 fecha sem tocar em [infra/](../infra/).

Laço: `WHERE canvas_estado IN ('pendente','falhou') AND canvas_tentativas < 5`.

⚠️ **Antes de re-POSTar, procurar.** Um POST que deu timeout pode ter criado o
Assignment mesmo assim. Então: `GET /courses/:id/assignments?search_term={nome}`,
comparar nome exato — achou, adota o `id` e marca `sincronizado`; não achou, cria.
Sem isso, rede instável duplica prova no Canvas.

### 4.5 · Rotas

| Rota | O que faz |
|---|---|
| `POST /ciclos` | cria o Assignment Group no Canvas e a linha de `ciclo` — **transacional** |
| `POST /simulados/agendar` | fluxo híbrido: grava, tenta criar, devolve o estado |
| `PATCH /simulados/{id}` | ganha write-back e `data_aplicacao` |
| `DELETE /simulados/{id}` | apaga o Assignment no Canvas e marca `cancelado_em` |
| `GET /simulados` | passa a devolver `origem` e `canvasEstado` |

Na criação do simulado, antes de tudo: **409** se já existir no mesmo
`(ciclo, rótulo, matéria)` — guarda de duplo clique.

No `PATCH`, para `origem='sas'` com `external_id`, depois do UPDATE local sai um
`PUT` pro Canvas com `name` / `points_possible` / `due_at`. Três detalhes:

- **`nome` deixa de ser editável direto** em simulado do SAS: é *derivado* de
  (ciclo, rótulo, matéria, data). Nome livre quebraria a gramática que o próprio
  sync lê. Ele edita as partes; o nome se recompõe.
- **Remarcar** (`data_aplicacao`) atualiza três coisas: `simulado`,
  `evento_agenda.data_evento` e o `due_at` no Canvas. É a operação de que P2 vai
  precisar pra regerar disparos quando a data muda — por isso entra agora.
- **`anulado` não tem par no Canvas** e continua só no SAS.

`nota_maxima` = **número de questões** (convenção do projeto) = `points_possible`.

### 4.6 · `schemas/domain.py`

`Simulado` ganha `origem` e `canvasEstado`. Sem isso a UI não tem como mostrar o
limbo — e limbo invisível é pior do que erro na cara.

---

## 5 · Frontend

Vanilla JS, sem build ([web/js/](../web/js/)).

| Arquivo | Mudança |
|---|---|
| [screens/simulados.js](../web/js/screens/simulados.js) | botão **"Novo simulado"** + seção *"Agendados"* (§6) |
| `components/criar-simulado.js` *(novo)* | diálogo, reusa [ui/dialog.js](../web/js/components/ui/dialog.js) |
| [screens/ciclos.js](../web/js/screens/ciclos.js) | botão **"Novo ciclo"** (ordem + vestibular) |
| [components/tabela-simulados.js](../web/js/components/tabela-simulados.js) | selo quando `canvasEstado != 'sincronizado'` |
| [services/api.js](../web/js/services/api.js) + [http-client.js](../web/js/services/http-client.js) | `criarCiclo`, `agendarSimulado`, `cancelarSimulado` |

Campos do formulário — é o **mínimo que a gramática do nome exige**, não escolha
de produto:

```
Ciclo      [ 3° Ciclo · ITA · 2026 ▾ ]  + novo
Rótulo     [ P2 ]
Matéria    [ Matemática ▾ ]
Data       [ 20/09/2026 ]   Hora [ 07:00 ]
Questões   [ 20 ]                        → points_possible
Tipo       [ Fase 2 ▾ ]

  Vai criar no Canvas:  3_P2 - Matemática - 20/09/2026
```

O preview do nome não é enfeite: é a única forma de o coordenador ver que SAS e
Canvas vão falar a mesma língua.

⚠️ **`tipo` é preenchido à mão aqui.** Hoje ele é *inferido* agrupando irmãos por
`Pn` ([`inferir_fase_simulados`](../api/app/ingest/header.py)), o que só funciona
depois que os irmãos existem. No agendamento não existem. E como `tipo` passa a ser
campo do SAS, a inferência **para de rodar** pra esses simulados — é o que o lote
reduzido de §4.3 garante.

Selo de estado: `pendente`/`falhou` → **"não está no Canvas"** em cor de alerta,
`canvas_erro` no title, botão "tentar de novo". `sincronizado` → nada. Estado
normal não merece pixel.

---

## 6 · O simulado passa a existir antes de ter nota

Todo o SAS foi escrito assumindo **simulado = coisa já aplicada**. Não há nenhum
filtro por data no motor estatístico. Um simulado criado com 30 dias de
antecedência aparece, vazio, em seis lugares:

| Onde | O que acontece |
|---|---|
| [simulados.py:87](../api/app/routes/simulados.py#L87) | ordenado por data desc → o futuro aparece **em primeiro** na lista, tudo vazio |
| [metricas.py:61-67](../api/app/stats/metricas.py#L61) | filtra só `anulado`/`e_agregado` → entra no recálculo |
| [metricas.py:242](../api/app/stats/metricas.py#L242) | grava linha de `metrica_simulado` com `n_presentes=0` e tudo NULL |
| [ciclo_estatisticas.py:183](../api/app/stats/ciclo_estatisticas.py#L183) | vira ponto vazio no gráfico de evolução do ciclo |
| `atualizar_periodo_ciclo` | `periodo_fim` do ciclo pula pra data futura |
| tools do chat | o assistente pode responder "o último simulado" com um que não aconteceu |

**Regra adotada:** simulado só entra em análise quando `data_aplicacao <= hoje`.
Uma condição a mais nas consultas acima, e na tela de Simulados os agendados
aparecem numa seção *"Agendados (3)"* separada, em cima — não misturados.

Isso não é polimento: é o que impede P1 de parecer que quebrou o sistema no dia
em que o primeiro simulado for agendado.

---

## 7 · Ordem de execução

| # | Etapa | Verificação |
|---|---|---|
| 0 | Pré-voo V1/V2/V3 (§2) + curso de teste criado | `curl` devolve 201 nos dois POSTs |
| 1 | *(condicional a V2)* migration da chave de `ciclo` | ITA e IME de mesma ordem coexistem no banco |
| 2 | Migration 0018 (§3) | `migrate up` e `migrate down` limpos, nos dois sentidos |
| 3 | Sync passa a gravar `canvas_course_id` e `canvas_assignment_group_id` | rodar o sync; colunas preenchidas em todos os ciclos e anos |
| 4 | `cliente.py`: `_post`/`_put`/`_delete` + os dois `compor_*` + `api/tests/` | round-trip passa; script solto cria grupo e assignment no curso de teste |
| 5 | `POST /ciclos` (transacional) | cria ciclo no SAS → grupo aparece no Canvas |
| 6 | `POST /simulados/agendar` (híbrido) | agenda → aparece no Canvas → `canvas_estado='sincronizado'` |
| 7 | **Regra de não-sobrescrita** (§4.3) | agenda, roda `/canvas-sync/run` **e** `/canvas-sync/reconciliar`, confere que nada mudou |
| 8 | Reprocessamento dos pendentes (§4.4) | token inválido de propósito → `falhou`; corrige → o sync seguinte adota |
| 9 | `PATCH` com write-back + remarcar + `DELETE` | renomeia, remarca, cancela; confere no Canvas e depois do sync |
| 10 | Filtro de simulado futuro (§6) | agenda pra daqui a 30 dias; nada muda em média, gráfico ou alerta |
| 11 | Telas de criação + selo de estado | fluxo ponta a ponta pela UI |

**A etapa 7 é a que fecha o "pronto quando"** — é a única cujo teste exige rodar o
reconcile inteiro.

---

## 8 · Riscos

| Risco | Sinal | O que fazer |
|---|---|---|
| Token sem permissão de escrita | 403 no V1 | **bloqueia P1 inteiro** — depende de quem administra o Canvas. Descobrir no dia 1 |
| `ciclo` não comporta ITA+IME na mesma ordem | V2 mostra ordens repetidas, ou a tela permite criar as duas | migration de chave composta **antes** de tudo (etapa 1) |
| Lote misto no upsert (§4.3) | `nome` NULL / violação de NOT NULL | dois lotes; testar com um simulado de cada origem no mesmo ciclo |
| POST duplicado por retry | dois objetos com o mesmo nome | POST não repete + `search_term` antes de recriar |
| Assignment no grupo errado | simulado no Canvas que o SAS não vê | sintoma de `canvas_assignment_group_id` vazio — etapa 3 vem antes da 6 de propósito |
| Prova criada pelo SAS virar Quiz depois | duas colunas no diário pra mesma prova | combinar com o coordenador (§1.1) |
| Publicar notifica aluno cedo demais | aviso de prova em D-30 | registrar; é a checagem que P3 já precisa fazer |

---

## 9 · O que P1 deixa em aberto de propósito

- **A edição ilusória dos 148 legados continua** ([§1.2](10-problemas-e-visao.md#12-dados-e-ingestão)).
  O write-back só vale pra `origem='sas'`. Mas agora a UI **consegue distinguir os
  dois casos** (tem `origem`) — pré-requisito pra avisar o coordenador. Bloco B.
- **Criar o curso do ano** (`{ano} 3o ITA/IME Simulados`) fica de fora — decidido.
  Curso carrega matrículas e turmas, que [§2.3.5](10-problemas-e-visao.md#235-fonte-da-verdade--decidido-sas-origina-canvas-recebe)
  atribui ao Canvas por origem administrativa. O curso continua sendo criado à mão
  lá, e o sync o descobre pelo nome como já faz.
- **Sem detalhe por questão** nos simulados criados pelo SAS (§1.1).
- **`evento_agenda` nasce quase vazia** — intencional: P2 pendura nela sem
  migration de reestruturação.
- **Write-back de nota** — bloco B, não muda aqui.
- **`/cobranca/verificar` → `/disparos/processar`** — renomeação é de P2.
