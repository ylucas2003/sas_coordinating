# Custo em escala — medições e implementação futura

Status: **documento de planejamento** (nada daqui está implementado).

> **Implementação futura principal: Batch API em duas ondas (−50% em tudo).**
> Correção não é tempo-real — ninguém espera na tela — então o modo
> assíncrono da OpenAI corta o custo pela metade sem mudar nenhuma lógica
> de correção. As demais alavancas (rubrica madura, caching) são
> complementares ou alternativas. Detalhes na primeira seção abaixo.

Baseado em medições reais de 2026-07-06: prova ITA Mat 2026 2ª fase,
9 questões × 3 alunos reais = 27 correções completas no fluxo de dois
níveis (gpt-4o-mini + escalonamento gpt-4o).

## Baseline medido

| Métrica | Valor |
|---|---|
| Custo médio por questão/aluno (cascata) | **1,58¢** |
| Tokens médios por questão/aluno | mini: 2.396 in / 628 out · 4o: 3.786 in / 564 out |
| Escalonamentos médios por questão/aluno | 2,3 critérios |
| Fração do input de avaliação que é prefixo repetido (instruções + enunciado + rubrica) | **92%** (resposta do aluno ≈ 8%) |
| Rubrica (gerar + criticar, one-time por questão) | ~3¢ — amortizado, desprezível |

Preços de referência (por 1M tokens): gpt-4o-mini $0,15 in / $0,60 out
(cache: $0,075 in); gpt-4o $2,50 in / $10,00 out (cache: $1,25 in).

**Insight central: o custo do sistema não é a correção, é a desconfiança.**
O mini avaliar tudo custa $0,74 por 1000 alunos; os ~2,3 escalonamentos
pro gpt-4o custam ~$15. Ou seja, **~85% do custo é verificação**, e a taxa
de escalonamento cai com a maturidade da rubrica (medido ao vivo: Q08
escalonava 2 critérios/aluno antes da revisão humana e 0 depois).

## Cenários — 1000 alunos corrigindo a MESMA questão

| Cenário | Custo | Observação |
|---|---|---|
| Cascata como está hoje | $15,85 | baseline |
| **Batch API (−50%)** | **$7,92** | **a implementação principal** — não acumula com caching (OpenAI não aplica desconto de cache no Batch) |
| Prompt caching (síncrono, question-major) | $11,34 | alternativa ao Batch para o caminho síncrono |
| Rubrica madura (escalonamento → ~0, só mini) | $0,74 | alavanca operacional; com caching $0,57 |
| **Rubrica madura + Batch** | **~$0,37** | piso absoluto do sistema como desenhado (~40× o baseline) |

Regime realista com rubricas maduras: **$1–4 por 1000 alunos/questão**
(escalonamento nunca chega a zero por design — desconto de nota sempre
escalona para o modelo forte confirmar; esse custo é irredutível e
desejado). Prova de 9 questões × 1000 alunos: ~$143 hoje → ~$71 só com
Batch → ~$10–35 com Batch + rubricas maduras.

## Implementação principal — Batch API em duas ondas (−50%)

### Por que é a principal

- **−50% garantido em tudo** (entrada e saída, mini e 4o), sem depender
  de comportamento de cache nem de maturidade de rubrica.
- **Zero mudança na lógica de correção**: prompts, schemas, gatilhos e
  motor de nota ficam intactos — muda só o transporte das chamadas.
- Encaixa no caso de uso real: lote noturno, notas prontas de manhã.

### Como funciona o Batch da OpenAI

Sobe um arquivo JSONL onde cada linha é uma requisição normal de
`chat.completions` (com `response_format`/json_schema funcionando
normalmente), a OpenAI processa em até 24h (na prática costuma ser bem
menos) e devolve um arquivo de resultados. Fluxo da API:

1. `client.files.create(file=..., purpose="batch")` — upload do JSONL;
2. `client.batches.create(input_file_id=..., endpoint="/v1/chat/completions", completion_window="24h")`;
3. polling de `client.batches.retrieve(batch_id)` até `status == "completed"`;
4. baixar `output_file_id` (respostas) e `error_file_id` (falhas individuais).

Cada linha do JSONL: `{"custom_id": ..., "method": "POST",
"url": "/v1/chat/completions", "body": {model, messages, response_format, ...}}`.

### O desenho em duas ondas

A cascata tem dependência sequencial — o escalonamento só existe depois
que a resposta do mini chega e os gatilhos determinísticos rodam. Logo:

1. **Onda 1**: batch único com as N×Q avaliações do gpt-4o-mini → aguardar;
2. rodar os gatilhos localmente (`avaliador._gatilhos_de_escalonamento`,
   Python puro, custo zero) sobre cada resposta;
3. **Onda 2**: segundo batch só com os critérios escalonados pro gpt-4o;
4. montar as avaliações finais e passar pelo motor de nota
   (`pontuacao.calcular_nota`) — nada muda daqui em diante.

Convenção de `custom_id` para religar respostas aos alunos:
`{questao}|{aluno}|avaliacao` na Onda 1 e
`{questao}|{aluno}|escalonamento_{criterio_id}` na Onda 2.

### O que precisa ser construído

Um novo CLI `corrigir_lote.py` (o `corrigir_prova.py` síncrono continua
existindo para correção individual/depuração):

- separar, em `avaliador.py`, a **montagem** da requisição (messages +
  schema) da **execução** — hoje as duas coisas acontecem juntas na
  chamada síncrona; a montagem passa a ser reutilizada pelo modo lote;
- gerar o JSONL da Onda 1 (todos os alunos × questões), submeter, poll;
- aplicar gatilhos, gerar o JSONL da Onda 2, submeter, poll;
- consolidar, calcular notas e salvar os mesmos relatórios de hoje
  (marcando `modo: "batch"` nos metadados de execução);
- tratar o `error_file_id`: falhas individuais não abortam o lote
  (mesmo espírito do executor atual — falha de um aluno/questão é
  reportada explicitamente, média marcada como parcial).

Alternativa híbrida válida: Onda 1 em batch, escalonamentos síncronos —
mais simples e quase tão barato quando as rubricas já estão maduras
(poucos escalonamentos).

### Restrições

- **Não acumula com prompt caching** — o lote é processado de forma
  distribuída, sem prefixo quente; escolher um por execução. Batch ganha
  no preço puro ($7,92 vs $11,34).
- Latência: duas janelas de espera (cada onda até 24h, tipicamente bem
  menos). Aceitável para lote noturno; inaceitável para devolutiva
  imediata na tela — para esse caminho, usar o síncrono com caching.

## Alavanca complementar — Rubrica madura (operacional, multiplica com o Batch)

Não é passo de implementação: é o fluxo de revisão humana existente.
Rubrica recém-gerada dispara gatilhos porque vem com defeitos típicos:
critérios amarrados ao método oficial, resultados esperados sem formas
equivalentes/aproximações decimais. Cada defeito vira escalonamento
(`confere_nao_verificavel_textualmente`, `comparacao_contradiz_rubrica`,
descontos indevidos).

Ciclo (validado 6× nas questões Q1–Q5 e Q8):

1. Gerar rubrica (`gerar_rubrica.py`) e corrigir os primeiros ~20 alunos —
   nesse volume a rubrica já viu todos os métodos alternativos que existem.
2. Olhar os relatórios: escalonamentos recorrentes no mesmo critério =
   sinal de rubrica imatura (o relatório registra os gatilhos por critério).
3. Revisão humana do `rubrica.json`: desamarrar critérios do método,
   listar formas equivalentes + aproximações decimais nos
   `resultados_esperados`, registrar erros comuns discriminantes.
   Marcar `revisada_por_humano: true`.
4. Gatilhos param de disparar para alunos corretos; só escalona quem
   errou de verdade (que é o escalonamento que queremos pagar).

É o que leva o Batch de $7,92 para ~$0,37 por 1000 alunos (Onda 2 quase
vazia). Cuidado documentado: generalizar critério sem âncora discriminante
troca injustiça por leniência (episódio Q08/aluno_02 — corrigido
adicionando o fato matemático discriminante como evidência esperada).
O teste ideal de uma revisão é o par (aluno certo, aluno errado) na
mesma questão.

## Alternativa ao Batch — Prompt caching (para o caminho síncrono)

Só faz sentido onde o Batch não cabe (devolutiva imediata). OpenAI cobra
meio preço por tokens de prefixo repetido entre chamadas (automático,
prefixo ≥ 1024 tokens, cache expira em ~5–10 min).

- **Ordenar as correções por questão** (question-major): todas as
  respostas da q01, depois q02, etc. Hoje o `corrigir_prova.py` é
  aluno-major (paraleliza questões de UM aluno).
- **Garantir a ordem no prompt**: instruções + enunciado + rubrica
  primeiro, resposta do aluno por último (cache só vale para prefixo).
  Conferir em `prompts.py` / `avaliador.py` antes de ativar.

Ganho: −28% no cenário atual ($15,85 → $11,34); −23% no regime só-mini
($0,74 → $0,57).

## Ordem sugerida de implementação

1. **Nada** — enquanto o volume for de validação (dezenas de alunos),
   o custo síncrono atual é irrelevante (~12¢/prova).
2. **Batch em duas ondas (`corrigir_lote.py`)** — a implementação
   principal; construir quando houver o primeiro lote real de centenas
   de alunos. Pré-requisito técnico: separar montagem de requisição da
   execução em `avaliador.py`.
3. **Question-major + caching** — só se surgir um caminho síncrono de
   volume (devolutiva imediata na tela); caso contrário, o Batch cobre.
4. O amadurecimento de rubrica corre em paralelo como fluxo operacional
   (revisar `rubrica.json` após os primeiros ~20 alunos de cada questão).
