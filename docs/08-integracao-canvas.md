# 08 — Integração Canvas (pesquisa para a Etapa 3 de arquitetura)

Documento vivo consolidando a investigação feita para substituir o import manual de planilha por sincronização direta com a API do Canvas. Serve como contexto para a conversa de arquitetura (Etapa 3 do roadmap — ver `project_roadmap_canvas_whatsapp` na memória). Tudo aqui foi validado (ou explicitamente marcado como não validado) contra a conta real do Canvas do Ari de Sá (`aridesa.instructure.com`, account id 1), usando o token já configurado em `api/.env` (`CANVAS_BASE_URL` / `CANVAS_API_TOKEN`). Todas as chamadas de teste foram **somente leitura**.

---

## 1. Etapa 1 — Estado atual do SAS (antes de qualquer mudança)

### 1.1 Dados mocados/estáticos remanescentes

- [web/js/screens/aluno/simulados.js:52-66](../web/js/screens/aluno/simulados.js#L52-L66) — `mockDotGrid()`: grid de questão certa/errada gerado por PRNG seeded a partir da nota agregada, não do gabarito real.
- [web/js/screens/aluno/simulados.js:399-414](../web/js/screens/aluno/simulados.js#L399-L414) — `_mockAssuntos()`: sorteia assuntos fictícios (lista fixa por matéria) pras questões erradas.
- [web/js/screens/aluno/painel.js:456-473](../web/js/screens/aluno/painel.js#L456-L473) — card "IA · Insight do ciclo": UI estática, sem chamada de API, botão desabilitado.
- [api/app/ingest/upsert.py:67](../api/app/ingest/upsert.py#L67) — nome do aluno cai pro `codigo` como placeholder se vier vazio da planilha (cosmético).
- Achado colateral: [web/js/screens/painel-aluno.js](../web/js/screens/painel-aluno.js) é código órfão (345 linhas, não importado em lugar nenhum) — foi substituído por `web/js/screens/aluno/{shell,painel,simulados}.js`.
- `arco/` (raiz do repo) é só protótipo de design (HTML/JSX standalone), não é código vivo — nada em `web/` o referencia.

### 1.2 Dependência do import de planilha

Cadeia: `web/js/screens/importar.js` → `POST /uploads` ([api/app/routes/uploads.py:56](../api/app/routes/uploads.py#L56)) → `processar_planilha()` em background ([api/app/ingest/pipeline.py](../api/app/ingest/pipeline.py)) → `api/app/ingest/upsert.py`.

**Tabelas que só são populadas por esse caminho** (nenhuma outra rota cria linhas nelas): `materia`, `aluno`, `matricula_turma`, `ciclo` (update), `simulado`, `nota`. Não existe hoje nenhum endpoint de criação alternativo para essas entidades.

**Único escape manual:** `PATCH /simulados/{id}` ([api/app/routes/simulados.py:266](../api/app/routes/simulados.py#L266)) e `PATCH /notas/{aluno_id}/{simulado_id}` ([api/app/routes/notas.py:35](../api/app/routes/notas.py#L35)) — só corrigem pontualmente, não substituem criação em massa.

O frontend assume essa dependência explicitamente: `web/js/main.js:36,140-143` — o evento `sas:dados-atualizados`, disparado ao fim de um import, limpa o cache inteiro de telas e dados.

### 1.3 Fluxos sem dado real

- Card de insight de IA (painel do aluno) — sem backend.
- Grid de questão-a-questão e assuntos por questão — sem granularidade no banco hoje (ver seção 3.3 abaixo — isso muda com o Canvas).
- `painel-aluno.js` órfão.
- `arco/` — só protótipo visual.

---

## 2. Etapa 2 — O que o Canvas cobre (mapeamento teórico via `docs/canvas-api/`)

| Tabela SAS | Endpoint Canvas | Nota |
|---|---|---|
| `aluno` | [Users](canvas-api/reference/users.md) + [Enrollments](canvas-api/reference/enrollments.md) | `sis_user_id` = chave estável já usada (`aluno.matricula`) |
| `matricula_turma` | [Enrollments](canvas-api/reference/enrollments.md) + [Sections](canvas-api/reference/sections.md) | `Section.name` bate com o padrão `{ano}o {trilha} {sede}` já parseado |
| `ciclo` | [Assignment Groups](canvas-api/reference/assignment_groups.md) | ver achado da seção 3.2 — mais simples do que se pensava |
| `simulado` | [Assignments](canvas-api/reference/assignments.md) (+ [Quizzes](canvas-api/reference/quizzes.md) quando aplicável) | `id`→`external_id`, `points_possible`→`nota_maxima`, `due_at`→`data_aplicacao` |
| `nota` | [Submissions](canvas-api/reference/submissions.md) | `score`, `missing`, `excused`, `workflow_state` — resolve a heurística de "zero vs ausência" |

### 2.1 O gap mais importante: mecanismo de webhook

- **PNS** ([guides/pns.md](canvas-api/guides/pns.md)) é LTI 1.3 e só documenta o notice type `LtiContextCopyNotice` (cópia de conteúdo entre cursos) — inútil pra nota/matrícula/simulado.
- A única doc com os eventos que precisamos (`GRADE_CHANGE`, `SUBMISSION_CREATED`, `SUBMISSION_UPDATED`, `QUIZ_SUBMITTED`) é [webhooks_subscriptions_for_plagiarism_platform.md](canvas-api/reference/webhooks_subscriptions_for_plagiarism_platform.md) — mas o próprio texto diz: *"This is intended for use with Canvas' Plagiarism Detection Platform. For general-purpose event subscriptions see Live Events."* Não é o caminho genérico.
- **Live Events** (o mecanismo real de propósito geral) é citado por nome mas **não está no mirror local** (`docs/canvas-api/`) — historicamente exige provisionamento/acordo separado com a Instructure (fila SQS/Kinesis ou HTTPS). **Não confirmado se está disponível pra essa conta.**
- **Alternativa 100% documentada e já validada:** `GET /courses/:id/gradebook_history/feed` ([gradebook_history.md](canvas-api/reference/gradebook_history.md#L160-L176)) dá um feed incremental, ordenado por data, de todas as versões de submissão — permite polling "desde o último cursor" sem depender de push.

**Conclusão da Etapa 2:** dá pra sincronizar as 4 tabelas inteiramente via REST + polling frequente, sem depender de nenhum webhook de verdade — isso já elimina o import manual. O "verdadeiro" `Canvas → Webhook →` do documento original de requisitos depende de confirmar com o admin do Canvas (ou a Instructure) se Live Events está habilitado; sem isso, "webhook" na prática vira polling frequente.

---

## 3. Validação ao vivo — estrutura real da conta Canvas

Testado com o token admin (`leonardo@aridesa.com.br`, conta "Colégio Ari de Sá", account id 1).

### 3.1 Cursos (345 no total)

Estrutura por ano + série: cursos por matéria (`{ano} {série}o ITA/IME {Matéria} {N}`, ex. `3o ITA/IME Matemática 1`) **separados** de um curso dedicado a simulados por ano: **`{ano} 3o ITA/IME Simulados`** (ex.: id 577 = 2026, 551 = 2025, 525 = 2024, 367 = 2023, 306 = 2022). **É nesse curso "Simulados" que os assignments/quizzes de prova ficam** — não nos cursos de matéria.

Sections confirmam o padrão já conhecido: `{ano}o ITA/IME {sede}` (ex. `3o ITA/IME AD`, `MF`, `SAS`).

### 3.2 Gramática real dos Assignments (curso Simulados)

`{ciclo}_P{n} - {Matéria} - {data}` — ex.: `1_P1 - Matemática - 08/02/2026`. **Diferente** do formato do header da planilha (`Matéria - Pn (id)`) — o parser de `api/app/ingest/header.py` não é reaproveitável direto, precisa de regex nova (mas o princípio é o mesmo).

Simulados macro-ciclo estilo ENEM também estão nesse curso, com gramática própria: `1° CICLO - 1º DIA (CADERNO AZUL) - Linguagens e Códigos (16/04/2026)`.

**Achado que simplifica tudo:** `GET /courses/577/assignment_groups` retorna grupos já nomeados `"1° CICLO - IME"`, `"2° CICLO - ITA"`, ..., `"1° CICLO - SAS"`, `"5° CICLO SAS"`. **O Assignment Group já É o `ciclo` + `vestibular_alvo`, sem precisar de regex.** Grupos com vestibular "SAS" são o macro-ciclo ENEM (mesmo que a pipeline atual descarta). Existe também um grupo cesto-padrão `"Imported Assignments"` pra itens sem grupo explícito.

Nem todo simulado é Quiz: a maioria dos assignments tem `quiz_id` preenchido (dá acesso a detalhe por questão via Quiz Submission Questions), mas simulados de reforço/reposição às vezes são só Assignment manual (`quiz_id: null`) — sem granularidade de questão nesses casos.

### 3.3 Submissions confirmam a promessa da Etapa 2

Amostra real (assignment 5582, "1_P1 - Matemática"):
```
user_id 697: score=None, missing=True,  workflow_state="unsubmitted"   ← ausência real
user_id 717: score=11.0, missing=False, workflow_state="graded"        ← nota real
```
Resolve na prática a dúvida em aberto sobre zeros-vs-ausência — o Canvas já distingue nativamente, sem heurística.

---

## 4. Inventário — o que dá pra extrair sobre um aluno

Testado com o aluno real id 295 ("ABEL DE MATOS OLIVEIRA MARQUES", matrícula/`sis_user_id` 20413958).

### 4.1 Confirmado com dado real

| Categoria | Fonte | Campos |
|---|---|---|
| Identidade | [Users](canvas-api/reference/users.md) | nome completo, `sis_user_id`, `login_id`, `avatar_url`, `created_at`, `time_zone`, `locale` |
| Contato | [Communication Channels](canvas-api/reference/communication_channels.md) | e-mail ativo; token de push (irrelevante) |
| Login | [Logins](canvas-api/reference/logins.md) | `unique_id`, `created_at` da conta, `workflow_state` |
| Matrícula por curso/turma | [Enrollments](canvas-api/reference/enrollments.md) | curso, `course_section_id`, `enrollment_state`, `last_activity_at`, `last_attended_at`, nota agregada do curso (`current_score`/`final_score`) — histórico multi-ano confirmado (2020→2023 pra esse aluno) |
| Nota por simulado | [Submissions](canvas-api/reference/submissions.md) (curso Simulados) | `score`, `missing`, `excused`, `workflow_state`, `late`, `graded_at`, `grader_id` |
| **Progresso em conteúdo de estudo** | [Modules](canvas-api/reference/modules.md) + `?student_id=` | Cursos por matéria têm módulos de aula organizados por assunto (ex.: curso Matemática 1 → "Combinatória" com 10 aulas, "Probabilidade", "Geometria Espacial", "Revisão"). Por aluno: `state: completed/started/locked` + `completed_at`. É engajamento real com conteúdo, não só nota — achado novo, não estava no roadmap original. |

### 4.2 O recurso existe na API, mas essa escola não usa (testado, veio vazio)

- **Responsáveis/pais vinculados** (`/users/:id/observers`) — vazio. **Não tem telefone de aluno nem de responsável disponível via Canvas** — relevante pro projeto de cobrança via WhatsApp (essa informação precisará vir de outra fonte).
- **Custom Gradebook Columns** — vazio no curso Simulados.
- **Groups** — vazio no curso Simulados.
- **Submission comments** — nenhum nas amostras testadas.
- **Page-view history** (`/users/:id/history`) — vazio pro token admin (provavelmente escopado ao próprio usuário logado).

### 4.3 Existe na doc, não testado ao vivo (baixa prioridade pro domínio ITA/IME)

- **Outcomes/Outcome Results** — tentativa deu erro de contexto (aluno testado não matriculado no curso certo); domínio de nota bruta (não competência) torna improvável que a escola use.
- **Grade Change Log / Gradebook History** — auditoria de alteração de nota (quem, quando, de quanto pra quanto).
- **Quiz Submission Questions** — resposta certa/errada por questão (documentado na Etapa 2, não re-testado nessa rodada).

---

## 5. Inventário — o que dá pra extrair sobre um simulado

Testado com o simulado real id 5582 ("1_P1 - Matemática - 08/02/2026", quiz_id 2929) e o assignment de redação 5660 ("1_P5 - Redação").

### 5.1 Identificação e agrupamento

`id`, `name`, `due_at`, `points_possible`, `assignment_group_id` (= ciclo + vestibular, confirmado na seção 3.2), `position`, `workflow_state` (published/unpublished), `created_at`/`updated_at`.

### 5.2 Janela de aplicação — achado novo: overrides por aluno

Além de `unlock_at`/`lock_at` do simulado em si, existem **overrides individuais** ([Assignment Overrides](canvas-api/reference/assignment_extensions.md)): no simulado 5582 havia 5 grupos de exceção — "5 alunos" com prazo num dia diferente, e 4 alunos isolados cada um com sua própria janela (`due_at`/`unlock_at`/`lock_at` próprios). É claramente **segunda chamada/reposição** tratada dentro do próprio Canvas, aluno a aluno. **Isso não existe no schema do SAS hoje** — a planilha só traz uma data de aplicação única por simulado.

### 5.3 Configuração da prova (quando é Quiz)

`quiz_type`, `time_limit` (limite de tempo — null no caso testado), `allowed_attempts` (1 tentativa), `shuffle_answers` (false), `scoring_policy`, `question_count` (15), `question_types` (`multiple_choice_question`), `show_correct_answers`.

### 5.4 Conteúdo real das questões — via Quiz Statistics

Não é só estatística: `question_statistics` ([quiz_statistics.md](canvas-api/reference/quiz_statistics.md)) devolve **o texto completo de cada questão**, com fórmulas/LaTeX/imagens embutidas, e cada alternativa com `text`, `correct` (bool) e `responses` (quantos escolheram). Dá pra reconstruir **a prova inteira com gabarito**, não só o resultado certo/errado.

### 5.5 Estatística agregada da prova

`score_average`, `score_high`, `score_low`, `score_stdev`, histograma de notas (`scores`), `correct_count_average`, `incorrect_count_average`, e **`duration_average`** — tempo médio (em segundos) que os alunos levaram na prova. Nenhum desses existe hoje no SAS, que só guarda a nota bruta e recalcula média/mediana/desvio por conta própria a partir dela.

### 5.6 Estatística por questão, por alternativa — granularidade máxima

Pra cada alternativa de cada questão: quantas respostas recebeu e **a lista de `user_ids`/nomes de quem escolheu aquela alternativa especificamente**. Dá pra saber não só que o aluno errou a questão 3, mas **qual alternativa errada ele marcou** — mata de vez o `_mockAssuntos()`/`mockDotGrid()` (seção 1.1) pros simulados que são Quiz.

### 5.7 Quando o simulado é upload manual (ex.: Redação)

Testado no assignment "1_P5 - Redação": `submission_types: online_upload`, `rubric: None` (a escola não usa rubrica pra redação), nota lançada manualmente (`score: 6.7`), e **o arquivo do aluno existe como anexo** (`attachments: 1`, recuperável via Submission Files se um dia quisermos reprocessar/OCR o texto).

### 5.8 Não existe nativamente

- **"Assunto"/tema por questão** — não é campo do Canvas. Mas com o **texto completo da questão** disponível (seção 5.4), dá pra automatizar essa classificação (ex.: via LLM) em vez de manter a lista fixa mocada em `_mockAssuntos()`.
- **Rubrica** — recurso existe na API (`rubric_settings`), mas essa escola não usa pra redação.
- **Quiz Reports** (relatório de análise de item em CSV) — endpoint existe ([quiz_reports.md](canvas-api/reference/quiz_reports.md)), não testado (é assíncrono, precisa gerar antes de baixar); baixa prioridade, já temos o mesmo dado via Quiz Statistics.

---

## 6. Gap — o que já está no banco SAS hoje vs. o que o Canvas oferece

Conferido contra `api/migrations/0001_schema_inicial.sql`.

| Categoria | Campo Canvas | Guardado no banco hoje? |
|---|---|---|
| Identidade | nome | ✅ `aluno.nome` |
| Identidade | `sis_user_id` | ✅ `aluno.matricula` ([0001:66](../api/migrations/0001_schema_inicial.sql#L66)) |
| Identidade | `login_id`, `avatar_url`, `created_at` (Canvas), `time_zone`, `locale` | ❌ nenhuma coluna |
| Contato | e-mail | ❌ nenhuma coluna |
| Login | tudo | ❌ não se aplica — SAS tem auth próprio (`aluno.senha_hash`, 0009_auth.sql) |
| Matrícula/turma | curso/Section | ✅ via `matricula_turma.turma_id` → `turma.section_original` ([0001:41](../api/migrations/0001_schema_inicial.sql#L41)) — guarda o Section **parseado**, não o `course_section_id` numérico do Canvas |
| Matrícula/turma | `enrollment_state`, período | 🟡 parcial — `matricula_turma.ativo_desde/ativo_ate` é aproximação própria, não o estado bruto do Canvas |
| Matrícula/turma | `last_activity_at`, `last_attended_at` | ❌ nenhuma coluna |
| Matrícula/turma | nota agregada do curso | ❌ não guardado — SAS calcula suas próprias agregações (`classificacao_aluno`, `metrica_simulado`) a partir da nota por simulado |
| Nota | `score` | ✅ `nota.pontuacao` |
| Nota | `missing`/`excused`/`workflow_state` | 🟡 **colapsados** num único boolean `nota.presente` na hora do import — a nuance original se perde |
| Nota | `late`, `graded_at`, `grader_id` | ❌ nenhuma coluna |
| Progresso em módulos | `state`/`completed_at` por módulo | ❌ não existe tabela pra isso hoje |

**Leitura geral (aluno):** identidade básica e nota bruta estão cobertas. Contato, avatar/timezone, atividade/último acesso, quem corrigiu e quando, a distinção fina de ausência (missing vs excused vs late), e progresso em módulos **não têm coluna nenhuma hoje** — não por decisão, mas porque o schema atual só reflete o que a planilha sempre trouxe, e a planilha nunca trouxe esses campos.

### 6.1 Simulado

| Categoria | Campo Canvas | Guardado no banco hoje? |
|---|---|---|
| Identificação | `id`, `name`, `due_at`, `points_possible` | ✅ `simulado.external_id`/`nome`/`data_aplicacao`/`nota_maxima` ([0001:117-130](../api/migrations/0001_schema_inicial.sql#L117-L130)) |
| Agrupamento | `assignment_group_id` (ciclo + vestibular) | ✅ via `simulado.ciclo_id` — mas a coluna `ciclo.ordem` é hoje extraída por regex do header da planilha, não lida direto do Assignment Group |
| Janela de aplicação por aluno (overrides) | `Assignment Override` (due/unlock/lock por subgrupo) | ❌ não existe — `simulado.data_aplicacao` é uma data única pro simulado inteiro |
| Configuração da prova | `quiz_type`, `time_limit`, `allowed_attempts`, `shuffle_answers`, `question_count`, `question_types` | ❌ nenhuma coluna |
| Conteúdo da questão + gabarito | `question_statistics[].question_text`/`answers[].text`/`correct` | ❌ não existe tabela pra questão nenhuma hoje |
| Estatística agregada da prova | `score_average/high/low/stdev`, histograma, `duration_average` | 🟡 parcial — `metrica_simulado` ([0001:206-223](../api/migrations/0001_schema_inicial.sql#L206-L223)) guarda média/mediana/desvio/histograma **calculados pelo próprio SAS** a partir da nota; `duration_average` não tem equivalente |
| Estatística por questão/alternativa (quem marcou o quê) | `answers[].responses`/`user_ids` | ❌ não existe tabela pra isso hoje |
| Redação: anexo do aluno | `Submission.attachments` | ❌ não guardado — só a nota final (`nota.pontuacao`) |

**Leitura geral (simulado):** o SAS hoje guarda o resultado final (nota, média, desvio) mas não guarda **nem a prova em si** (questões, gabarito, configuração) **nem o processo** (quem respondeu o quê, quanto tempo levou, se teve prazo estendido). Tudo isso é novo — não é substituição de uma coluna existente, é uma camada de dado que a planilha nunca trouxe.

---

## 7. Decisões em aberto (consolidado, pra revisitar na Etapa 3)

1. **Live Events está disponível pra essa conta?** — precisa confirmar com admin do Canvas / Instructure. Não bloqueia começar (polling já resolve), mas muda o desenho de longo prazo.
2. **Backfill histórico:** só a partir de agora, ou reprocessar 2020–2026 (já confirmado que os dados existem e são acessíveis)?
3. **Upload de planilha:** mantém como fallback manual, ou desativa assim que o sync novo for validado?
4. **Frequência de polling** aceitável para notas (afeta todo o pipeline de stats/alertas que recalcula em cima disso).
5. ✅ **RESOLVIDO — Expandir o schema.** Ver plano completo na seção 8.
6. **Contato para o projeto de WhatsApp:** confirmado que não vem do Canvas (nem aluno nem responsável) — precisa de fonte alternativa.
7. ✅ **RESOLVIDO — Progresso em módulos entra no escopo.** Ver `modulo`/`aluno_modulo_progresso` na seção 8.
8. ✅ **RESOLVIDO — Questão/gabarito/estatística por alternativa vão pro banco** (não fica só sob demanda). Ver `questao`/`questao_alternativa`/`questao_resposta_aluno` na seção 8.
9. ✅ **RESOLVIDO (por ora) — Overrides de prazo por aluno ficam de fora.** Sem caso de uso concreto ainda; reavaliar se aparecer demanda de produto (ver seção 8).
10. **Classificação automática de assunto por questão:** já que o texto completo da questão está disponível (seção 5.4), vale a pena usar LLM pra classificar assunto automaticamente (substituindo `_mockAssuntos()` por algo real, mesmo que não seja 100% preciso)? — continua em aberto, é decisão de produto/IA, não de schema.
11. ✅ **RESOLVIDO (por ora) — Anexo de redação fica de fora do escopo.** Reavaliar se surgir necessidade de reprocessamento (OCR/LLM).

---

## 8. Plano de implementação — expansão de schema

Cobre as decisões 5, 7, 8, 9 e 11 acima. Organizado por tabela; tudo em colunas novas (nenhuma remoção), pra não quebrar `api/app/ingest/upsert.py` nem a lógica de stats já existente.

### 8.1 `aluno` — colunas novas

```sql
ALTER TABLE aluno ADD COLUMN email text;
ALTER TABLE aluno ADD COLUMN avatar_url text;
ALTER TABLE aluno ADD COLUMN canvas_user_id text;           -- id numérico do Canvas, distinto de matricula/sis_user_id
ALTER TABLE aluno ADD COLUMN canvas_criado_em timestamptz;  -- created_at do Canvas ≠ criado_em (quando entrou no SAS)
```
`login_id`/`time_zone`/`locale` ficam de fora — baixo valor de produto sem um uso concreto.

### 8.2 `matricula_turma` — colunas novas

```sql
ALTER TABLE matricula_turma ADD COLUMN canvas_enrollment_id text;
ALTER TABLE matricula_turma ADD COLUMN canvas_section_id text;   -- complementa turma.section_original (nome parseado) com o id bruto
ALTER TABLE matricula_turma ADD COLUMN enrollment_state text;    -- estado bruto do Canvas, sem reinterpretar em ativo_desde/ativo_ate
ALTER TABLE matricula_turma ADD COLUMN last_activity_at timestamptz;
ALTER TABLE matricula_turma ADD COLUMN last_attended_at timestamptz;
```
Nota agregada por curso (`current_score`) fica de fora — o SAS já calcula suas próprias agregações a partir da nota por simulado; guardar as duas seria fonte de divergência.

### 8.3 `nota` — colunas novas (preservando `presente`)

```sql
ALTER TABLE nota ADD COLUMN late boolean NOT NULL DEFAULT false;
ALTER TABLE nota ADD COLUMN graded_em timestamptz;
ALTER TABLE nota ADD COLUMN grader_canvas_user_id text;
ALTER TABLE nota ADD COLUMN canvas_missing boolean;
ALTER TABLE nota ADD COLUMN canvas_excused boolean;
ALTER TABLE nota ADD COLUMN canvas_workflow_state text;
```
`presente` continua existindo — toda a lógica de stats já depende dele. Passa a ser **derivado** de `canvas_missing`/`canvas_excused`/`canvas_workflow_state` na sincronização, em vez de decidido e descartado na hora do import.

### 8.4 `simulado` — colunas novas

```sql
ALTER TABLE simulado ADD COLUMN quiz_id text;        -- se preenchido, dá pra buscar detalhe por questão
ALTER TABLE simulado ADD COLUMN unlock_at timestamptz;
ALTER TABLE simulado ADD COLUMN lock_at timestamptz;
ALTER TABLE simulado ADD COLUMN duracao_media_segundos numeric(8,2);  -- Canvas dá pronto, SAS não calcula sozinho
```
`ciclo.vestibular_alvo` já existe desde `0003_vestibular_e_fase.sql` — Assignment Group mapeia direto, sem coluna nova.

### 8.5 Tabelas novas — questão + gabarito + resposta por aluno

```sql
CREATE TABLE questao (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    simulado_id         uuid NOT NULL REFERENCES simulado(id),
    canvas_question_id  text NOT NULL,
    posicao             int NOT NULL,
    texto               text NOT NULL,
    pontos              numeric(5,2),
    UNIQUE (simulado_id, canvas_question_id)
);

CREATE TABLE questao_alternativa (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    questao_id        uuid NOT NULL REFERENCES questao(id),
    canvas_answer_id  text NOT NULL,
    texto             text NOT NULL,
    correta           boolean NOT NULL,
    UNIQUE (questao_id, canvas_answer_id)
);

CREATE TABLE questao_resposta_aluno (
    aluno_id        uuid NOT NULL REFERENCES aluno(id),
    questao_id      uuid NOT NULL REFERENCES questao(id),
    alternativa_id  uuid REFERENCES questao_alternativa(id),
    correta         boolean NOT NULL,
    PRIMARY KEY (aluno_id, questao_id)
);
```
Só populável quando `simulado.quiz_id` existe — fica vazia pros simulados de upload manual (esperado, não é bug).

### 8.6 Tabelas novas — progresso em módulo

```sql
CREATE TABLE modulo (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    materia_id         uuid REFERENCES materia(id),
    canvas_module_id   text NOT NULL UNIQUE,
    nome               text NOT NULL,
    posicao            int NOT NULL
);

CREATE TABLE aluno_modulo_progresso (
    aluno_id       uuid NOT NULL REFERENCES aluno(id),
    modulo_id      uuid NOT NULL REFERENCES modulo(id),
    estado         text NOT NULL CHECK (estado IN ('locked','unlocked','started','completed')),
    completado_em  timestamptz,
    PRIMARY KEY (aluno_id, modulo_id)
);
```

### 8.7 Fora do escopo por agora (decisões 9 e 11)

- **Overrides de prazo por aluno** (segunda chamada/reposição) — exigiria uma tabela `simulado_prazo_individual`; sem caso de uso de produto ainda.
- **Anexo de redação** — se decidido guardar depois, é um `anexo_url`/`anexo_storage_path` simples em `nota` ou tabela separada.

### 8.8 Próximo passo

Escrever a migration real (`api/migrations/0010_expansao_canvas.sql` + `.down.sql`) com tudo acima, e ajustar `api/app/ingest/upsert.py` (ou o módulo novo `canvas_sync/`, ver seção "Etapa 3" na conversa) pra popular essas colunas/tabelas.

### 8.9 Disparo dos jobs — decidido: AWS (EventBridge)

Quem acorda o backend pra rodar a sincronização/alertas/cobrança de professor: **EventBridge (Rules + API Destinations)**, definido como infra-as-code em [`infra/`](../infra/) usando AWS CDK (Python). Decisões já tomadas nessa conversa:

- **Frequência do sync de notas:** curta e fixa, a cada 5 min (opção escolhida entre polling fixo curto/espaçado/manual/por horário).
- **Escopo:** só gatilho — a lógica de negócio (verificar Canvas, avaliar alerta, mandar WhatsApp) continua toda no FastAPI, não migra pra Lambda.
- **Ferramenta de provisionamento:** AWS CDK em Python (não Terraform) — gera CloudFormation nativamente (sem precisar de state backend próprio) e usa a mesma linguagem do resto do backend.
- **Custo:** validado contra a página oficial de pricing da AWS — no volume atual (~300-1.000 invocações/dia) fica dentro do que não é cobrado (regra agendada no bus padrão não tem cobrança documentada; só o alvo — API Destination — custa US$ 0,20/milhão de eventos).

3 schedules definidos (`infra/sas_scheduler/sas_scheduler_stack.py`): `CanvasSync` (5 min → `/canvas-sync/run`), `AlertasCheck` (1h → `/alertas/verificar`), `CobrancaProfessor` (1h → `/cobranca/verificar`). Autenticação via header `X-Scheduler-Secret`, valor guardado num parâmetro SSM SecureString (não no CloudFormation, pra não vazar segredo no template). Stack já validada com `cdk synth` local — falta só criar as 3 rotas correspondentes no FastAPI (nenhuma existe ainda) e fazer o primeiro `cdk deploy` real, quando a URL final do backend estiver decidida.
