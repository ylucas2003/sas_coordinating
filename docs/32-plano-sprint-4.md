# 32 — Sprint 4 · Dado e leitura

> **Origem:** a proposta da [Sprint 4](19-roadmap.md#sprint-4--dado-e-leitura--5-partes)
> — o que os Blocos B e C do [docs/10](10-problemas-e-visao.md) deixaram
> pendente, mais as duas partes que a Onda 3 da Sprint 2 cortou por falta de
> tempo ([18 §5](18-plano-sprint-2.md)).
>
> **Escopo:** o número para de mudar de significado conforme a origem do dado.
> Um zero que é abandono deixa de contar como nota; a planilha e o Canvas param
> de se sobrescrever em silêncio; o Painel para de misturar 2025, 2026 e 2027
> na mesma fileira de pílulas; e o coordenador manda o ciclo inteiro para o
> Canvas num clique em vez de N.
>
> **Pronto quando:** o coordenador abre a ficha de um aluno que "tirou zero" e
> vê escrito que ele não marcou nenhuma alternativa; escolhe *2026 → ITA* no
> Painel e a fileira de ciclos encolhe de 23 para 8; e clica em "enviar as 6
> pendências deste ciclo" vendo, antes de confirmar, exatamente quais são.

---

## 0 · O levantamento — o que o código já respondia

Este sprint foi proposto em 22/08, antes do redesenho do casco, do banco de
questões e da Sprint 5. **Antes de escrever qualquer linha, li o código e medi o
banco.** Duas das cinco partes não são o que a proposta diz — e é o mesmo padrão
que a Sprint 5 encontrou ([31 §0](31-plano-sprint-5.md)), o que sugere que a
leitura antes do plano vira regra da casa, não exceção.

| Parte | O que a proposta diz | O que é verdade |
|---|---|---|
| **P1** · B.3 Zero × ausência | "precisa de decisão antes de código: medir primeiro" | ✅ **medido em produção** — e são **dois problemas, não um** ([§1.2](#12--o-achado-que-reorganiza-a-parte-b3-são-dois-problemas)). O individual são 122 células; **71% dos zeros do sistema estão em oito provas de 2023** onde o professor lançou 0 para quem faltou. Só o primeiro é regra de negócio |
| **P2** · B.4 Precedência planilha × Canvas | "hoje quem escreve por último vence" | ✅ **a pergunta que a destravava está respondida**: a planilha **nunca foi usada em produção** — zero uploads. A parte deixa de ser "arbitrar precedência" e vira "aposentar o caminho", que é o que o próprio docs/10 recomendava |
| **P3** · C.2 Split ano/vestibular/ciclo | "a sidebar descarta os dois" | ⏳ **intocado, e pior que o descrito**: a API ordena os ciclos só por `ordem`, então a fileira sai `IME 2026 · ITA 2027 · IME 2025 · ITA 2025 · ITA 2026 …` |
| **P4** · C.3 Range de período | proposto | ✅ **já está feito e testado** — `RangeDatas` + `intersectaPeriodo`, com predicado de interseção, extremos abertos e período nulo tratado. **Sai do sprint** |
| **P6** · Envio em lote ao Canvas | "hoje cada objeto tem seu botão" | ⏳ intocado — e **pior**: o ciclo não tem botão nenhum. `POST /ciclos/{id}/enviar-canvas` existe na API, está exportado em `servicos/api.ts`, e **nenhuma linha do front o chama** |

**Efeito no escopo: quatro partes, não cinco — e uma delas encolheu de M para
P.** A P4 sai inteira; a P2 vira "tirar do caminho" em vez de "arbitrar"; a P1
ganha a medição que a destravava, e ela mostra um problema maior do que o
proposto; a P3 e a P6 crescem, porque cada uma tem um defeito que a proposta não
conhecia.

⚠️ **Uma lição de método, cara o bastante para ficar escrita.** A primeira
versão deste plano mediu tudo no banco de desenvolvimento e afirmou sobre
produção. Estava errada em três pontos: produção tem **4× as notas**,
representa ausência de um jeito que o snapshot não representava, e — o que
mudou o desenho da P1 — **tem os dados de 2023, onde mora 71% do problema**.
Ler o dev e concluir sobre produção teria produzido uma migration que resolve
4,4% do caso e não vê o resto. **Medição que vira decisão de produto se faz
contra produção**, e neste projeto isso é uma consulta por ssh — está em
[`api/scripts/medir_zeros_b3.sql`](../api/scripts/medir_zeros_b3.sql).

### 0.1 · A P4 já está feita

[`dominio/ciclos.ts`](../web/src/dominio/ciclos.ts) tem `intersectaPeriodo`,
[`BarraFiltros.tsx`](../web/src/componentes/ui/filtros/BarraFiltros.tsx) tem o
corpo `RangeDatas`, e [`Ciclos.tsx`](../web/src/telas/Ciclos/Ciclos.tsx#L75-L85)
liga os dois. Os quatro pontos do [docs/10 §C.3](10-problemas-e-visao.md#c3--range-de-período-em-ciclos):

1. **Extremos abertos** — ✅ `if (!periodo.inicio && !periodo.fim) return true`,
   e cada lado testado sozinho em [`ciclos.test.ts`](../web/src/dominio/ciclos.test.ts#L31-L32).
2. **"Ciclo pode ter período nulo?"** — ✅ a pergunta tem resposta: **pode, e
   existe um agora.** `Ciclo 1 · ITA · 2027` está no banco com
   `periodo_inicio` nulo. O front trata (`return false` — não intersecta nada);
   a API mascara com `or ""` em [`_linha_para_ciclo`](../api/app/routes/ciclos.py#L37-L47),
   e por isso o `str` obrigatório do schema não quebra. Fica anotado como
   dívida: o schema declara obrigatório o que o banco permite nulo.
3. **Convive com "Ano letivo"?** — ✅ convive; os dois filtram junto.
4. **Presets ("este ano", "último trimestre")** — ⏳ **é a única coisa que
   sobra.** Tamanho P, vira item de polimento, não parte de sprint.

---

## 1 · P1 · Zero × ausência nas estatísticas (B.3)

### 1.1 · A medição, contra produção

[docs/10 §B.3](10-problemas-e-visao.md#b3--zero--ausência-nas-estatísticas)
fechou com *"Sugestão: medir primeiro — quantos casos são, e como se
distribuem — antes de escolher a regra."* Medido em **30/08 contra produção**,
com [`api/scripts/medir_zeros_b3.sql`](../api/scripts/medir_zeros_b3.sql):

| | |
|---|---|
| Notas | **102.143** — 44.638 presentes, 57.505 ausentes |
| Zeros com `presente = true` | **2.756** — **6,17% das notas presentes** |
| Delas, quantas o Canvas chamou de falta | **nenhuma** — 2.755 `graded`, 1 `pending_review`, zero `missing` |
| Com dado de questão (dá para olhar por dentro) | **284** (10,3%) |
| **Sem** dado de questão | **2.472** (89,7%) |

E dentro das 284 com evidência:

| Evidência | Casos | Leitura |
|---|---|---|
| **Nenhuma alternativa marcada** | **122** (43%) | abriu e não respondeu |
| Respondeu tudo e errou tudo | 140 | zero legítimo |
| Respondeu parte | 22 | zona cinzenta |

**O sinal é forte e ficou mais forte que no dev:** a fração média de questões em
branco é **0,0033** entre as 29.308 notas maiores que zero e **0,4959** entre os
zeros. **Cento e cinquenta vezes.** Entre os zeros com dado de questão, metade
da prova, em média, está em branco.

> ⚠️ **Medir no dev e afirmar sobre produção foi o erro da primeira versão
> deste plano.** Produção tem 4× as notas, representa ausência de outro jeito
> (57.505 linhas `presente = false`, contra 9 no snapshot), e — o que importa
> mais — **tem dados de 2023 que o snapshot não tem**, e é neles que mora a
> maior parte do problema. Fica como regra da casa: **número que vira decisão
> de produto se confere em produção.**

### 1.2 · O achado que reorganiza a parte: B.3 são DOIS problemas

Os 2.756 zeros não são uma população. São duas, com causas diferentes, e **só
uma delas é regra de negócio.**

#### Problema A · o zero individual de quem não respondeu — 122 células (4,4%)

Evidência direta por aluno: a prova era quiz, as respostas estão gravadas, e
**nenhuma alternativa foi marcada**. É ausência escrita como nota. Regra
barata, segura e verificável.

#### Problema B · a prova cujo zero é prática de lançamento — ~1.959 células (71%)

**Oito provas de 2023 concentram 71% de todos os zeros do sistema.** Não é
distribuição, é concentração:

| Prova | Presentes | Zeros | % | Média dos não-zero | Alunos entre 0 e 1 | Questões |
|---|---|---|---|---|---|---|
| `6_P17 - Matemática - 01/07/2023` | 455 | **325** | 71% | 3,84 | **3** | 0 |
| `6_P18 - Física - 02/07/2023` | 432 | **314** | 73% | 3,78 | 8 | 0 |
| `5_P15 - Física - 04/06/2023` | 454 | 253 | 56% | 2,66 | 34 | 0 |
| `5_P14 - Matemática - 28/05/2023` | 454 | 232 | 51% | 3,97 | 10 | 0 |
| `4_P12 - Física - 09/05/2023` | 450 | 226 | 50% | 4,22 | 27 | 0 |
| `3_P9 - Física - 23/04/2023` | 443 | 225 | 51% | 3,63 | 28 | 0 |
| `4_P11 - Química - 08/05/2023` | 453 | 219 | 48% | 4,35 | 9 | 0 |
| `4_P11 - Matemática - 08/05/2023` | 389 | 165 | 42% | 3,32 | 31 | 0 |

**Quatro coisas dizem que isto não é prova difícil:**

1. **A distribuição é bimodal com um buraco.** Em `6_P17 - Matemática`: **325
   alunos em exatamente 0,00 e 3 alunos entre 0 e 1**, e depois uma curva
   normal centrada em 3,84 com máximo 8,10. Prova difícil produz curva
   contínua — muitos 0,5, muitos 0,8. Um pico de 325 com vale de 3 do lado não
   é dificuldade; é **outra coisa entrando na mesma coluna**.
2. **Metade delas é Fase 1** — objetiva, múltipla escolha. Tirar exatamente
   zero chutando 12 questões de 5 alternativas tem probabilidade de ~7%. Não
   71%.
3. **Nenhuma das oito é quiz** — `quiz_id` nulo em todas. São Assignments com
   nota lançada à mão, e é por isso que não há dado por questão para conferir.
4. **As provas irmãs do mesmo dia foram corrigidas para muito menos gente.** Em
   01/07/2023, `6_P17 - Matemática` tem **455 notas com `graded_at`** e
   `6_P17 - Química` tem **124**. Mesma sessão, mesmos alunos. A diferença não
   é quem fez a prova; é quem o professor lançou.

**A leitura:** nessas provas o professor lançou **0 para quem não compareceu**,
em vez de deixar sem nota. É prática de lançamento, não desempenho.

#### E o efeito é uma história que não aconteceu

Os oito não estão espalhados: caem em **quatro ciclos consecutivos de 2023**,
entre abril e julho. Antes e depois, o dado é limpo. É o que a média de ciclo
mostra hoje, e o que ela mostra quando as oito provas saem:

| Ciclo (2023) | Suspeitos | **Média hoje** | **Sem os suspeitos** |
|---|---|---|---|
| Ciclo 2 · ITA | 0 | 6,44 | 6,44 |
| Ciclo 3 · ITA | 1 | **5,23** | 5,95 |
| Ciclo 4 · ITA | 3 | **4,33** | 6,18 |
| Ciclo 5 · ITA | 2 | **4,61** | 6,23 |
| Ciclo 6 · ITA | 2 | **4,41** | 6,47 |
| Ciclo 7 · ITA | 0 | 6,63 | 6,63 |
| Ciclo 8 · IME | 0 | 6,68 | 6,68 |
| Ciclo 9 · IME | 0 | 6,19 | 6,19 |
| Ciclo 10 · ITA | 0 | 6,91 | 6,91 |

**Hoje o SAS conta que a turma de 2023 despencou de 6,4 para 4,3 entre abril e
julho e se recuperou sozinha em agosto.** Tirando as oito provas, a série fica
lisa — 6,44 · 5,95 · 6,18 · 6,23 · 6,47 · 6,63 — e contínua com os ciclos de
antes e de depois.

Uma queda de dois pontos que aparece exatamente onde estão as provas com pico
em zero, e some exatamente quando elas saem, **não é desempenho**. É o
artefato entrando na conta. E é a evidência mais forte deste plano: não depende
de interpretar distribuição, depende de a série voltar a fazer sentido.

⚠️ **É também o que o produto usa como linha de base.** O alerta
`PROVA_MAL_CALIBRADA` compara o desvio de um simulado com o histórico do mesmo
ciclo e fase ([`thresholds.py`](../api/app/stats/thresholds.py)); a comparação
entre ciclos e qualquer leitura ano a ano bebem da mesma fonte. Um histórico
com um buraco de dois pontos não erra só a tela de 2023 — **ele erra a régua
com que 2025 e 2026 são lidos.**

⚠️ **E a verdade não volta pelo sync.** O Canvas afirma que são zeros
corrigidos — `canvas_missing = false`, `graded_at` preenchido. Não há campo a
reler, não há reconcile que conserte. **O dado original se perdeu em 2023**, e
qualquer coisa que o SAS faça aqui é inferência.

### 1.3 · O que a P1 entrega, e o que ela não entrega

A **média não está contaminada por ausência de verdade** — esse era o B.1, e já
está corrigido: [`calcularMediasVirtuais`](../web/src/dominio/painel.ts#L232-L295)
documenta que ausência é `null`, nunca zero, e o motor filtra `presente = true`
em todas as leituras. Em produção a ausência real é explícita e vem do Canvas:
**57.496 das 57.505 linhas `presente = false` são `canvas_missing = true`**.

O impacto do **Problema A** na média é pequeno — **entre +0,04 e +0,16 por
simulado**, medido um a um. Ou seja: **o Problema A não é sobre a média da
turma.** É sobre não escrever "0,0" na ficha de um aluno que não respondeu
nada, e não empurrá-lo para a zona de risco por isso. O ganho é individual.

O **Problema B** é outra escala: numa prova com 71% de zeros, a média divulgada
é **1,10** quando a média de quem realmente fez é **3,84**. Aí o número
agregado está errado por um fator de três — e é ele que aparece em "prova mal
calibrada", na trajetória do aluno e em qualquer comparação entre ciclos.

### 1.4 · As duas regras propostas

#### Para o Problema A — regra de negócio, e é estreita de propósito

> **Um zero deixa de contar quando o aluno não marcou nenhuma alternativa.**

- Vale só onde há dado de questão: **284 zeros, 122 afetados**.
- Para os demais zeros com dado de questão, **o zero conta**. Quem respondeu
  tudo e errou tudo tirou zero.
- Para os zeros **sem** dado de questão que não caem no Problema B — Fase 2,
  Redação, discursiva — **o zero conta**, e a tela diz que ali não há como
  distinguir. Um zero em Redação é nota de verdade com muito mais frequência
  que um zero em Matemática objetiva.
- **A regra dos "2+ zeros no mesmo dia" sai.** Em produção ela pega **414
  células** — dez vezes mais que no dev — e, onde dá para conferir, **73
  confirmam e 12 contradizem: 14% de erro**, apagando `pontuacao` de quem
  respondeu. E das 414 ela não tem como conferir **329**. Um proxy que erra 14%
  no verificável e opera às cegas em 79% dos casos não é regra; é dano.

⚠️ **Ressalva sobre a evidência.** Hoje `alternativa_id IS NULL` junta dois
baldes do Canvas: `none` (em branco) e `other` (marcou fora das alternativas) —
[`_BUCKETS_SEM_ALTERNATIVA`](../api/app/canvas_sync/questoes.py#L34). Em
múltipla escolha `other` é raro, mas a regra ficaria apoiada numa conflação.
**Separar os dois faz parte do trabalho**, e só então a regra é sobre "em
branco" de fato.

#### Para o Problema B — o zero daquelas oito provas é falta

> **Nas oito provas identificadas, e só nelas, `pontuacao = 0` significa
> ausência.** A nota acima de zero fica como está.

Esta regra substituiu a proposta anterior ("tirar as oito provas inteiras da
estatística") depois de duas conferências. **A troca é uma melhoria, e veio do
usuário em 04/09.**

**Por que é melhor que excluir a prova.** Excluir jogava fora as ~130 notas
verdadeiras de cada prova — justamente as de quem compareceu — e, pior,
*inflava* a média do ciclo, porque as oito eram provas genuinamente difíceis
(média de 2,7 a 4,4 entre quem fez). Manter a prova e derrubar só os zeros
preserva o dado bom e devolve um número honesto:

| Ciclo (2023) | Hoje | Excluindo a prova | **Derrubando só os zeros** |
|---|---|---|---|
| Ciclo 2 · ITA | 6,44 | 6,44 | 6,44 |
| Ciclo 3 · ITA | **5,23** | 5,95 | **5,73** |
| Ciclo 4 · ITA | **4,33** | 6,18 | **5,51** |
| Ciclo 5 · ITA | **4,61** | 6,23 | **5,66** |
| Ciclo 6 · ITA | **4,41** | 6,47 | **6,08** |
| Ciclo 7 · ITA | 6,63 | 6,63 | 6,63 |
| Ciclo 10 · ITA | 6,91 | 6,91 | 6,91 |

A coluna da direita é a leitura certa: uma depressão **suave** entre abril e
julho, que é real (as provas eram difíceis), no lugar de um desabamento que não
foi.

##### A conferência que fecha o caso: a prova irmã

Para cada uma das oito, comparei **quantos alunos ficaram acima de zero** com
**quantos alunos a prova irmã do mesmo dia avaliou**. Se a hipótese estiver
certa, os dois números têm de descrever o mesmo grupo — o de quem compareceu:

| Prova | Com nota | Zeros | **Acima de zero** | **Irmã do mesmo dia** | Diferença |
|---|---|---|---|---|---|
| `6_P17 · Matemática · 01/07` | 455 | 325 | **130** | **128** | +2 |
| `6_P18 · Física · 02/07` | 432 | 314 | **118** | **120** | −2 |
| `3_P9 · Física · 23/04` | 443 | 225 | **218** | **224** | −6 |
| `5_P14 · Matemática · 28/05` | 454 | 232 | **222** | **231** | −9 |
| `5_P15 · Física · 04/06` | 454 | 253 | **200** | **212** | −12 |
| `4_P12 · Física · 09/05` | 450 | 226 | **222** | **238** | −16 |
| `4_P11 · Química · 08/05` | 453 | 219 | **234** | — | — |
| `4_P11 · Matemática · 08/05` | 389 | 165 | **224** | — | — |

**Seis das oito batem com a irmã dentro de 2 a 16 alunos** — 1% a 7%. São seis
confirmações independentes da mesma mecânica, cada uma vinda de um professor
diferente que lançou nota do jeito certo no mesmo dia.

As duas últimas são o par de 08/05: **elas são irmãs uma da outra**, e as duas
estão na lista, então não há terceiro para arbitrar. Mas elas concordam entre
si — **234 e 224 acima de zero**, diferença de 4% — o que reproduz o mesmo
padrão: cerca de 230 compareceram naquele dia, e o resto virou zero nas duas.

> Isto tira o Problema B do terreno da inferência estatística. Não é mais "a
> distribuição tem forma estranha": é **uma contagem de presença que sete
> lançamentos independentes confirmam**.

##### O erro que a regra assume, medido

Onde "acima de zero" é *menor* que a irmã, a diferença é o número máximo de
zeros legítimos que a regra converteria em falta por engano: **entre 2 e 16
alunos por prova**. É pequeno, é conhecido, e é ordens de grandeza menor que o
erro de hoje — 200 a 325 faltas por prova contadas como nota.

⚠️ **A regra vale para estas oito e nada mais.** Não é um detector, não é um
limiar, não roda sozinha em prova nenhuma. Qualquer prova futura entra na lista
por decisão humana, com a mesma conferência de irmã registrada.

### 1.5 · Como implementar

**Princípio: não destruir o fato do Canvas.** O que o Canvas diz (`presente`,
`pontuacao`) fica; o que o SAS conclui vira coluna própria, derivada e
reversível. É a mesma escolha da `0024` para `pontuacao`, e pelo mesmo motivo.
Vale para os dois problemas — só muda o nível: um marca a **nota**, o outro
marca a **prova**.

#### Problema A · nota a nota

1. **Migration `0039`**:
   - `nota.computavel boolean NOT NULL DEFAULT true` — "esta nota entra na
     estatística".
   - `nota.motivo_nao_computavel text` — `'todas_em_branco'` por enquanto; a
     coluna existe para a próxima regra não precisar de migration.
   - `questao_resposta_aluno.balde_sem_alternativa text` (`'none'` / `'other'` /
     null), para a ressalva do [§1.4](#14--as-duas-regras-propostas).
   - `simulado.nota_confiavel boolean NOT NULL DEFAULT true` +
     `simulado.motivo_nota_nao_confiavel text` — é o Problema B, na mesma
     migration porque é a mesma ideia e não vale duas paradas do PostgREST.
   - Par `.down.sql`, e `docker compose restart postgrest` depois do `up`
     (armadilha 1 do `CLAUDE.md`).

2. **Um único avaliador**, novo módulo `api/app/stats/computavel.py`:
   `avaliar_computavel(cliente, *, simulado_ids)` conta brancos por
   (aluno, simulado) e grava `computavel`/`motivo`. Chamado dos **dois**
   caminhos de entrada:
   - no sync, depois de `_sincronizar_questoes_gated`, sobre
     `resumo.simulados_tocados` ([`sincronizar.py`](../api/app/canvas_sync/sincronizar.py#L334-L360));
   - no ingest, na etapa 5e, no lugar da regra do mesmo dia.

   > ⚠️ **A ordem importa e é a falha silenciosa mais provável do sprint.** A
   > evidência mora em `questao_resposta_aluno`, que o sync popula **depois** da
   > nota. Avaliar antes classifica tudo como computável e some com o efeito
   > **sem erro nenhum**. Tem teste próprio no [§1.6](#16--testes).

3. **Os pontos de leitura passam a filtrar por `computavel`.** Hoje "nota que
   conta" é `.eq("presente", True)`, repetido em `stats/metricas.py`,
   `stats/classificacao.py`, `stats/classificacao_ciclo.py`,
   `stats/ciclo_estatisticas.py`, `stats/alertas.py`, `stats/aluno_dados.py` e
   nas tools do chat — **15 lugares**. Não sair replicando
   `.eq("computavel", True)` em 15 arquivos: extrair um helper em
   `stats/utils.py` (`filtro_nota_valida(query)`) e passar tudo por ele, senão a
   16ª leitura nasce errada.

4. **Retirar a regra destrutiva** do `pipeline.py` e transformar
   `limpar_zeros_provaveis_ausencias.py` em `backfill_computavel.py` (dry-run
   por padrão, como o atual). **O que a regra antiga já apagou é recuperável**:
   o Canvas tem o valor, e um `/canvas-sync/reconciliar` completo o traz de
   volta.

#### Problema B · prova a prova

5. **A lista das oito é DADO, não código.** `simulado.zero_e_ausencia = true`
   + `motivo`, gravado por migration de dados com o `external_id` de cada uma.
   Lista curta, auditável, revertível por um `UPDATE`.

   > ⚠️ **Por que não `if simulado_id in [...]` no processamento**, que é o
   > caminho mais curto e o errado, por dois motivos mecânicos:
   >
   > 1. **Onde a regra parecida já mora, ela nunca roda.** A regra dos "2+
   >    zeros no mesmo dia" está em `ingest/pipeline.py` — o caminho da
   >    planilha, que **nunca executou em produção** ([§2.4](#24--como-implementar)).
   >    Uma trava escrita ali não teria efeito nenhum.
   > 2. **O sync desfaz.** `mapear_nota` reescreve `presente` e `pontuacao` a
   >    cada rodada, de hora em hora. Qualquer correção precisa ser
   >    **reaplicada depois do sync**, não aplicada uma vez.
   >
   > Como dado + avaliador pós-sync, a regra sobrevive à rodada seguinte, e
   > quem abrir o banco vê por que aquela prova é diferente. Como `if` no meio
   > do código, ela evapora e ninguém sabe que existiu.

6. **O avaliador do item 2 lê a marca** e grava, nas notas com `pontuacao = 0`
   dessas provas, `computavel = false` e
   `motivo_nao_computavel = 'zero_por_falta_lancada'`. As notas acima de zero
   ficam intactas e a prova **continua** na estatística — com a média de quem
   de fato a fez.

   > É a mesma coluna e o mesmo avaliador do Problema A. A diferença é só a
   > origem da evidência: lá, as respostas em branco do aluno; aqui, a marca na
   > prova. Um caminho de escrita, dois motivos.

#### Comum aos dois

7. **Front** — a célula e a coluna dizem o que o produto decidiu ignorar:
   - zero não computável: marca discreta e título
     (`"0,0 — nenhuma alternativa marcada; não entra na média"`) em
     `TabelaPainel.tsx`, na ficha do aluno e na `FichaNota`;
   - prova não confiável: faixa no cabeçalho da coluna e na ficha do simulado,
     dizendo o motivo.

   Regra da casa: **um número que o produto decidiu ignorar precisa dizer que
   ignorou.** Senão o coordenador vê a média mudar e não sabe por quê — e foi
   exatamente assim que a régua da Sprint 5 assustou.

8. **Recálculo** — `recalcular_metricas` + `recalcular_classificacoes` depois do
   backfill; senão o cache contradiz a tela, como aconteceu na `0037`
   ([31 §Estado](31-plano-sprint-5.md)).

### 1.6 · Testes

- `avaliar_computavel`: todas em branco → não computável; uma marcada → conta;
  simulado sem questão → conta (não há evidência); balde `other` → conta.
- **Teste de ordem** (item 2): avaliar antes de as respostas chegarem não pode
  marcar ninguém como não computável.
- `filtro_nota_valida`: média de um simulado com 3 notas, uma não computável,
  bate com a média das 2 — e o mesmo teste rodado contra cada superfície
  (Painel, ficha de ciclo, ficha de aluno, tool do chat), porque são 15 pontos
  de leitura e o risco é esquecer um.
- `nota_confiavel = false`: a prova sai da média do ciclo e **continua**
  aparecendo na trajetória do aluno.
- Regressão: nenhuma nota com `presente = false` muda de estado.

### 1.7 · O que precisa da coordenação, e o que não precisa

| | Precisa? |
|---|---|
| **Problema A** — a regra do zero sem alternativa marcada | **Não bloqueia.** É estreita (122 de 102.143), apoiada em evidência direta por aluno, e conservadora. Segue como default se ninguém responder |
| **Problema B** — o zero das oito provas de 2023 vira falta | **Sim, e é a única coisa da P1 que precisa.** Não é decisão técnica: é o histórico de 2023 de uma turma que já saiu, e a pergunta é se ele continua afirmando que ~2.000 alunos zeraram provas às quais a contagem de presença diz que não compareceram |

**As duas são independentes** — o A anda enquanto o B espera.

---

## 2 · P2 · Precedência entre ingest de planilha e sync do Canvas (B.4)

### 2.1 · O que já está resolvido

Para **`nota.pontuacao`, a arbitragem existe desde a Sprint 2.** A migration
[`0024`](../api/migrations/0024_nota_valor_sas_e_canvas.sql) criou
`pontuacao_canvas` / `pontuacao_sas` e um trigger que resolve
`pontuacao = COALESCE(pontuacao_sas, pontuacao_canvas)`. O trigger trata write
antigo — que só manda `pontuacao` — como vindo do Canvas, que é exatamente o que
o ingest da planilha é. Logo: **planilha e Canvas disputam `pontuacao_canvas`,
Canvas ganha na próxima rodada, e a edição do coordenador sobrevive às duas.**
Está certo, e é a regra que o docs/10 previu ("Canvas vence sempre").

### 2.2 · O que sobrou — e é um defeito de verdade

**`nota.presente` não tem arbitragem nenhuma.** Não existe `presente_canvas` /
`presente_sas`. O `PATCH /notas/{aluno}/{simulado}` grava `presente` direto
([`notas.py`](../api/app/routes/notas.py#L137-L149)); o sync grava por cima com
`derivar_presente(submission)`. Consequência:

> O coordenador marca um aluno como ausente, escolhe **não** mandar ao Canvas
> (o `divergente` que a coordenação pediu em 21/08), e a próxima rodada do sync
> desfaz — em silêncio, sem badge, sem auditoria.

É a mesma perda que a `0024` consertou para a nota, num campo que ela não
cobriu. No snapshot de 22/08 não mordia porque **ninguém tinha editado nota
ainda** — `pontuacao_sas` nulo nas 26.810 linhas — o que faria deste o momento
barato de consertar. ⬜ **Confirmar em produção** (`SELECT count(*) FROM nota
WHERE pontuacao_sas IS NOT NULL`): se o Leo já editou alguma, o conserto deixa
de ser preventivo e passa a ter dado a recuperar.

### 2.3 · A assimetria do `origem='sas'`

O sync respeita campo originado no SAS: simulados `origem='sas'` seguem por um
**lote reduzido** que só toca `quiz_id`, `unlock_at` e `lock_at`
([`sincronizar.py`](../api/app/canvas_sync/sincronizar.py#L214-L262)).

**O ingest não faz esse teste.** `upsert_simulado` casa por `external_id` — que
a planilha extrai do próprio nome da coluna, `"1_P1 - Matemática - 09/02/2025
(12345)"`, e é o id do Assignment — e escreve `nome`, `nota_maxima`, `tipo`,
`materia_id`, `ciclo_id`, `rotulo_curto` sem olhar `origem`. Uma planilha
importada depois de o coordenador ter agendado o simulado no SAS **apaga a
identidade que o SAS declarou**, exatamente a regra que a P1 da Sprint 1
estabeleceu.

### 2.4 · Como implementar

**O passo 0 está feito, e ele decide a parte.** `SELECT count(*), max(criado_em)
FROM upload` **em produção**, conferido no VPS em 30/08:

```
uploads | ultimo
      0 | nunca
```

**A planilha nunca foi usada em produção.** Nem uma vez. Todas as 102.143 notas
entraram pelo sync do Canvas. E a tela ainda está lá, como aba de Administração
([`AbasAdmin.tsx`](../web/src/componentes/layout/AbasAdmin.tsx) · "Importar
planilha"), oferecendo um caminho de escrita que ninguém escolheu e que
sobrescreve dado do Canvas sem arbitragem nenhuma.

[docs/10 §B.4](10-problemas-e-visao.md#b4--precedência-entre-ingest-de-planilha-e-sync-do-canvas)
já previu esta resposta: *"se não for [usada], o caminho mais barato é aposentar
o `importar` em vez de arbitrar precedência."* **É o que a P2 passa a ser.**

⚠️ **Um "nunca foi usada" não é um "não serve".** A planilha foi como o projeto
nasceu, e é o plano B se o Canvas cair ou se um ano histórico precisar entrar
de novo. Aposentar aqui quer dizer **tirar do caminho de quem clica**, não
apagar o código:

- `POST /uploads` responde **410 Gone** com o motivo, em vez de aceitar.
- A aba "Importar planilha" sai da `AbasAdmin`; `/importar` vira uma página que
  explica que o Canvas é a entrada e como fazer carga histórica.
- `app/ingest/` **fica inteiro**, rodável por script — como
  `banco-questoes/` já é: código que não roda em requisição.
- E aí a pergunta de precedência **evapora**: com um só escritor, não há o que
  arbitrar.

> ✅ **Decidido em 30/08: aposentar.** A aba sai, o código fica. Com isso a P2
> vai de **M para P** e **não tem migration** — e a pergunta de precedência
> deixa de existir em vez de ser respondida, que é a melhor forma de responder
> uma pergunta.

**Os dois itens abaixo ficam registrados como o caminho não tomado** — é o que
vale se a coordenação um dia reabrir a planilha, e é o que explica por que a
`0040` não existe.

1. **`origem` no ingest.** Antes do `upsert_simulados_em_lote`, carregar os
   `external_id` com `origem='sas'` e mandá-los por um lote reduzido, espelhando
   o que o sync já faz. Um simulado nascido no SAS não perde identidade porque
   alguém subiu uma planilha.
2. **Migration `0040` — `presente` ganha o mesmo tratamento da `0024`:**
   `presente_canvas` / `presente_sas`, o trigger existente
   (`nota_resolver_pontuacao`, renomeado para `nota_resolver_valores`) passando a
   resolver os dois pares, e backfill `presente_canvas := presente`. O
   `PATCH` escreve `presente_sas`; o sync escreve `presente_canvas`; o badge de
   divergência que já existe para nota passa a cobrir presença.

3. **A tabela de precedência vira documento**, não folclore:

| Campo | Dono | Quem pode sobrescrever |
|---|---|---|
| `nota.pontuacao_canvas` | Canvas | sync, ingest |
| `nota.pontuacao_sas` | coordenador | só o `PATCH` |
| `nota.presente_canvas` | Canvas | sync, ingest |
| `nota.presente_sas` | coordenador | só o `PATCH` |
| `nota.computavel` | SAS (derivado) | o avaliador da [P1](#1--p1--zero--ausência-nas-estatísticas-b3) |
| `simulado.*` com `origem='canvas'` | Canvas | sync, ingest |
| `simulado.*` com `origem='sas'` | SAS | ninguém — só as rotas do SAS |

---

## 3 · P3 · Split ano / vestibular / ciclo no Painel (C.2)

### 3.1 · O estado, medido

A `BarraFiltros` do Painel tem três grupos: **Ciclo** (`PillsUnica`), **Sede** e
**Turmas** ([`Painel.tsx`](../web/src/telas/Painel/Painel.tsx#L134-L172)). O
grupo Ciclo lista **os 23 ciclos do banco**, numa fileira, na ordem que a API
devolve — e a API ordena por `ordem` e só ([`ciclos.py`](../api/app/routes/ciclos.py#L173-L182)).
O resultado real:

```
Ciclo 1 · IME · 2026   Ciclo 1 · ITA · 2027   Ciclo 1 · IME · 2025
Ciclo 2 · ITA · 2025   Ciclo 2 · ITA · 2026   Ciclo 3 · ITA · 2026
Ciclo 3 · ITA · 2025   Ciclo 4 · ITA · 2026   …
```

Três anos e dois vestibulares intercalados, e "Ciclo 7" existindo duas vezes
(IME 2026 e ITA 2025) com o mesmo rótulo curto. Sem migration para consertar:
`Ciclo` já carrega `anoLetivo` e `vestibularAlvo`
([`domain.py`](../api/app/schemas/domain.py)); a tela é que os ignora.

**E o default é arbitrário — literalmente.** O Painel abre em `ciclos[0]`, e
`ciclos[0]` é o primeiro dos **três** ciclos com `ordem = 1`. Como o `.order()`
tem uma coluna só e não há critério de desempate, **qual dos três vem primeiro
não está definido**: hoje sai `Ciclo 1 · IME · 2026`, e nada garante que
continue saindo. O Painel abre num ciclo que ninguém escolheu.

Distribuição atual:

| Ano | ITA | IME |
|---|---|---|
| 2027 | 1 | — |
| 2026 | 8 | 3 |
| 2025 | 8 | 3 |

### 3.2 · Como implementar

**Só front. Nenhuma migration, nenhuma rota nova.**

1. **`web/src/dominio/painelFiltros.ts`** — lógica pura, espelhando o que
   `dominio/ciclos.ts` já faz para a tela de Ciclos, e testada do mesmo jeito.
   Reaproveitar em vez de reinventar: `montarOpcoes` e `contarPorChip` de lá
   servem quase inteiros.
2. **Hierarquia Ano → Vestibular → Ciclo**, cada nível estreitando o seguinte:
   - **Ano** — pílulas de seleção **múltipla**, e **todas marcadas** ao abrir.
   - **Vestibular** — idem.
   - **Ciclo** — `PillsUnica`, só os que sobraram, agrupados por ano
     decrescente e, dentro do ano, por vestibular e `ordem`.

   > ⚠️ **Corrigido em 03/09, por decisão do Yan.** A versão anterior deste
   > plano dizia *seleção única* nos dois primeiros eixos, com um default
   > calculado. Está errado por dois motivos, e a correção melhorou o desenho:
   >
   > 1. **A tela mostra UM ciclo por vez.** Ano e vestibular só encurtam a
   >    fileira de onde esse ciclo sai — nunca chegam à tabela. O argumento
   >    "misturar ITA e IME na mesma tabela não tem significado" não se aplica:
   >    a tabela continua sendo de um ciclo só, e um ciclo tem um vestibular só.
   > 2. **`/provas` → Ciclos já filtra esses dois eixos, em seleção múltipla**
   >    (`FiltroCiclos`, em `dominio/ciclos.ts`). Fazer o Painel de outro jeito
   >    criaria duas gramáticas para o mesmo filtro — o problema que a C.1
   >    existiu para fechar.
   >
   > **Consequência de "tudo marcado" que precisa estar escrita:** conjunto
   > vazio deixa de significar "sem filtro". Em `ciclos.ts`, vazio deixa tudo
   > passar (a tela nasce sem nada marcado); aqui, desmarcar o último ano tem
   > de **esvaziar** a fileira, não devolvê-la inteira. É a mesma operação com
   > a semântica invertida, e por isso `painelFiltros.ts` **não** reusa
   > `aplicarFiltros` — compartilhar o predicado faria uma das duas telas
   > mentir. O "Limpar filtros" desta faixa volta para TUDO marcado.
3. **Consertar o default do ciclo** junto: dentro do recorte, o ciclo mais
   recente com simulado aplicado.
4. **`useRecorteDaTela` acompanha** — `ano` e `vestibular` entram no
   `RecorteDaTela` ([`contextoDaTela.ts`](../web/src/dominio/contextoDaTela.ts#L14-L21)),
   senão o assistente responde sobre um recorte que a tela não está mostrando.
   Campos fechados, como os outros; nada de string livre.
5. **Trocar de ano ou vestibular reseta o ciclo** para o default do novo
   recorte — não pode ficar apontando para um ciclo que sumiu da fileira.

### 3.3 · Fora de escopo, de propósito

- **Memorizar a escolha entre visitas.** É item do polimento avulso
  ("faixa de filtros … memorizado por tela", [19 §3](19-roadmap.md)), vale para
  as sete telas, e resolver só no Painel cria a inconsistência que a C.1 fechou.
- **Ordenar a rota `GET /ciclos`.** Mexer no `.order()` mexe em `/provas` e no
  chat junto. A ordenação vira responsabilidade da tela; a rota fica anotada
  como dívida de baixo risco.

### 3.4 · Testes

`painelFiltros.test.ts`: ano estreita vestibular; vestibular estreita ciclo;
trocar ano invalida o ciclo escolhido; o default ignora ano sem simulado
aplicado; ciclo sem período não quebra a escolha.

---

## 4 · P6 · Envio em lote ao Canvas (C5)

### 4.1 · O inventário de pendências, e o buraco no meio dele

São três tipos de objeto que podem estar fora de sincronia:

| Objeto | Estado | Rota que resolve | Front |
|---|---|---|---|
| Ciclo (Assignment Group) | `canvas_estado` ∈ {`divergente`, `falhou`} | `POST /ciclos/{id}/enviar-canvas` | ❌ **ninguém chama** |
| Simulado (Assignment) | idem, com `origem='sas'` | `POST /simulados/{id}/retry-canvas` | ✅ `Simulados.tsx`, `SimuladoFicha.tsx` |
| Nota (Submission) | derivado: `pontuacao_sas ≠ pontuacao_canvas` | `PATCH /notas/…` com `sincronizar_canvas` | ✅ só uma por vez, dentro da `FichaNota` |

**O buraco:** `enviarCicloAoCanvas` está definido em
[`servicos/api.ts`](../web/src/servicos/api.ts#L232-L233) e **nenhum arquivo o
importa**. Um ciclo criado com `sincronizar_canvas: false` fica em `divergente`
para sempre — e `GET /ciclos` nem devolve `canvas_estado`
([`_linha_para_ciclo`](../api/app/routes/ciclos.py#L37-L47) não o seleciona),
então a tela não teria como mostrar que ele está assim. **Isso não é o lote:
é o unitário faltando.** Entra aqui porque é onde a tela nasce.

### 4.2 · Como implementar

1. **Expor o estado do ciclo** — `canvas_estado` e `canvas_erro` no `select` e
   no schema `Ciclo`; `SeloCanvas` (que já existe) passa a aparecer na
   `CicloFicha` e na tabela de `/provas`.
2. **`GET /ciclos/{id}/pendencias-canvas`** — devolve a lista, por tipo, com o
   motivo de cada uma. Rota de leitura, sem efeito. É ela que alimenta o
   diálogo de confirmação: **o coordenador vê o que vai subir antes de subir**,
   que é a regra de 21/08 ("nada sobe ao Canvas sem alguém clicar") aplicada ao
   lote.
3. **`POST /ciclos/{id}/enviar-canvas-lote`** — executa, com quatro exigências:
   - **Ordem obrigatória: grupo do ciclo → assignments → notas.** Um Assignment
     não entra num Assignment Group que não existe; mandar fora de ordem
     produz falha que parece do Canvas.
   - **Resultado por item**, nunca um "ok" agregado. Sucesso parcial é o caso
     normal, e um lote que diz "sucesso" tendo falhado em 3 de 12 é pior que
     não ter lote.
   - **Idempotente** — reexecutar não duplica nada; cada item reusa a função de
     escrita unitária de [`escrita.py`](../api/app/canvas_sync/escrita.py), que
     já é o único lugar por onde o SAS escreve no Canvas. **Não abrir um segundo
     caminho de escrita.**
   - **Auditoria: um evento por item, mais um do lote.** É o que distingue
     "escolheu não mandar" de "mandou e falhou" daqui a três meses
     ([18 §3.3](18-plano-sprint-2.md)).
4. **Volume.** Notas divergentes de um ciclo podem ser centenas, e
   `atualizar_nota_submission` é **uma requisição por aluno**. O Canvas tem
   `POST /courses/:id/assignments/:id/submissions/update_grades` — uma chamada
   por assignment, assíncrona, devolvendo um `Progress` — e o
   [`ClienteCanvas`](../api/app/canvas_sync/cliente.py) **não tem esse método**.
   Decisão: **v1 sequencial com teto explícito** (e a UI dizendo quantas ficaram
   de fora, nunca truncando em silêncio); o método em lote entra como melhoria
   medida, não como aposta.
5. **UI na `CicloFicha`** — um bloco "N pendências no Canvas" acima da
   `TabelaSimuladosDoCiclo`, com o diálogo de confirmação listando item a item,
   e o resultado por linha depois.

### 4.3 · Risco específico

⚠️ **Escrita no Canvas real durante o desenvolvimento.** O `CANVAS_API_TOKEN` do
`.env` é de admin do colégio (risco 4 do [18 §7](18-plano-sprint-2.md#7--riscos)).
Um lote descuidado altera dezenas de objetos de verdade de uma vez — é a
diferença entre esta parte e todas as outras do sprint. **Todo teste com mock**;
a verificação contra o Canvas real é passo manual, deliberado, num ciclo
escolhido de propósito.

---

## 5 · Migrations

| # | O quê | Parte |
|---|---|---|
| `0043` | `nota.computavel` + `nota.motivo_nao_computavel` · `questao_resposta_aluno.balde_sem_alternativa` · `simulado.nota_confiavel` + `simulado.motivo_nota_nao_confiavel` · **e a view `v_nota_dimensoes`**, que ganhou as duas colunas | P1 — os dois problemas na mesma migration: é a mesma ideia em dois níveis, e não vale duas paradas do PostgREST |
| `0043b` | Migration de **dados**: marca as oito provas de 2023 por `external_id`, com o motivo escrito | P1 · Problema B — **só depois do aval da coordenação** ([§1.7](#17--o-que-precisa-da-coordenação-e-o-que-não-precisa)) |
| ~~`0040`~~ | ~~`nota.presente_canvas` / `presente_sas`~~ | **Não será feita.** A P2 aposentou a planilha em 30/08 ([§2.4](#24--como-implementar)); com um só escritor não há o que arbitrar. Fica descrita em [§2.4](#24--como-implementar) como o caminho não tomado |

> ⚠️ **Renumerada de `0039` para `0043` em 03/09.** Quando este plano foi
> escrito, a última migration era a `0038`; entre a escrita e a execução, o
> trabalho do banco de questões consumiu `0039`–`0042`.

> ⚠️ **A view entrou na migration depois.** `metricas.py` e a regra
> `DIFERENCA_ENTRE_SEDES` de `alertas.py` leem de `v_nota_dimensoes`, não de
> `nota` — sem as colunas lá, dois pontos de leitura continuariam somando o que
> o resto do sistema parou de somar, e a divergência apareceria como número
> diferente na mesma tela, sem erro. As colunas entram **no fim** da lista da
> view: `CREATE OR REPLACE VIEW` só aceita acrescentar ao final, e o `.down`
> precisa de `DROP` + `CREATE`, porque replace não sabe remover coluna.

**Uma migration só, portanto.** Um sprint que começou com duas e termina com
uma porque a resposta foi "esse caminho não é usado" é o resultado certo.

⬜ **Antes da `0039`, uma conferência de 30 segundos** que está no
[`medir_zeros_b3.sql`](../api/scripts/medir_zeros_b3.sql) (bloco 9): se
`notas_editadas_pelo_sas > 0` em produção, o `presente` sem arbitragem
([§2.2](#22--o-que-sobrou--e-é-um-defeito-de-verdade)) deixa de ser risco
teórico e volta para a mesa.

Toda migration com par `.down.sql`, e `docker compose restart postgrest` depois
de cada `up` que crie ou altere tabela.

---

## 5.1 · Estado da execução *(03/09/2026)*

**Onda 1 e Onda 2 escritas.** Localmente verdes: **358 testes** na API (eram
331) e **299** no front (eram 294); `0043` aplicada, revertida e reaplicada no
banco local, com `docker compose restart postgrest` e as colunas conferidas por
`curl` no PostgREST — inclusive na view.

| Parte | Estado | Onde |
|---|---|---|
| **P1 · Problema A** | ✅ escrito | `0043`, `stats/computavel.py`, `filtro_nota_valida` + `simulado_entra_no_agregado` nas **18** leituras, `balde_sem_alternativa` no sync, `scripts/backfill_computavel.py` (o `limpar_zeros_provaveis_ausencias.py` foi apagado), marca na célula do Painel |
| **P1 · Problema B** | ⬜ **travado** | As colunas, o filtro e a ressalva na tela estão de pé; falta só a `0043b`, que são oito `UPDATE`. Espera o aval da coordenação |
| **P2** | ✅ escrito | `POST /uploads` → 410, aba fora da `AbasAdmin`, `/importar` virou página que explica, `scripts/importar_planilha.py` |
| **P3** | ✅ escrito | `ciclo.ordem` exposto, `dominio/painelFiltros.ts` + teste, faixa do Painel com Ano e Vestibular, default de ciclo consertado, `anos`/`vestibulares` no recorte do chat |
| **P6** | ✅ escrito | `canvas_estado` do ciclo exposto, `GET /pendencias-canvas`, `POST /enviar-canvas-lote`, bloco na `CicloFicha`, `SeloCanvas` na tabela de `/provas` |

⬜ **Falta a verificação visual** (Painel a 1440 e a 390/360, bloco de
pendências, célula riscada). O perfil do MCP `chrome` estava tomado por outra
sessão na hora de escrever.

⬜ **Falta o backfill contra produção** e o `recalcular_metricas` depois dele —
até lá, `computavel` é `true` em toda linha e nada muda de número.

---

## 6 · Ordem de execução

**Onda 0 — a medição contra produção · ✅ FEITA em 30/08**
[`api/scripts/medir_zeros_b3.sql`](../api/scripts/medir_zeros_b3.sql), somente
leitura, rodado contra produção. É o que produziu o
[§1.1](#11--a-medição-contra-produção) e o
[§1.2](#12--o-achado-que-reorganiza-a-parte-b3-são-dois-problemas) — e o que
mostrou que a P1 era duas partes, não uma. O script fica versionado: a mesma
medição vai precisar ser refeita depois do backfill, para comprovar o efeito.

```sh
ssh sas@46.202.150.165 'cd /opt/sas/infra/vps && docker compose exec -T db \
    psql -U postgres -d sas' < api/scripts/medir_zeros_b3.sql
```

**Onda 1 — o que não depende de decisão de ninguém**
[P3](#3--p3--split-ano--vestibular--ciclo-no-painel-c2) (só front, isolado) ·
[P2](#2--p2--precedência-entre-ingest-de-planilha-e-sync-do-canvas-b4) no
caminho de aposentar, que virou tamanho P e não tem migration ·
**Problema A da [P1](#1--p1--zero--ausência-nas-estatísticas-b3)** — a `0039`
inteira, o avaliador, o helper de leitura e as marcas na tela.

**Onda 1b — espera o aval da coordenação**
**Problema B da P1**: a `0039b`, que são oito `UPDATE` com motivo escrito. A
migration `0039` já cria as colunas, então esta onda é só o dado — e pode
entrar dias depois, sem novo deploy de schema.

**Onda 2 — o que fecha um buraco visível**
[P6](#4--p6--envio-em-lote-ao-canvas-c5), começando pelo unitário do ciclo, que
é o defeito de verdade.

**O corte natural continua sendo o fim da Onda 1** — o número honesto, o filtro
que não mistura anos e uma entrada de dado só. A P6 é a que fica de fora se o
tempo acabar, e fica inteira: meia P6 é pior que nenhuma, porque um lote que
manda parte sem dizer o que ficou é exatamente o que ela existe para evitar.

---

## 7 · Riscos

1. **A `zona` dos alunos se move pela segunda vez em duas semanas.** A Sprint 5
   já mudou quem aparece em "risco" (o Tio Leo corta com E). O Problema A muda
   de novo, para menos — **122 células em 102.143**, efeito pequeno. Mas o
   Problema B move a **média de oito provas de 2023 de ~1,1 para ~3,8**, e isso
   é grande e visível em qualquer comparação histórica. Segunda mudança seguida
   na mesma tela: avisar antes, com o número na mão.
2. **O avaliador da P1 depende de ordem dentro do sync.** Rodar antes de
   `questao_resposta_aluno` estar populado classifica tudo como computável e
   some com o efeito **sem erro nenhum**. É a falha silenciosa mais provável do
   sprint; por isso tem teste de ordem próprio.
3. **`.eq("presente", True)` está em 15 lugares.** Trocar por um helper e
   esquecer um deixa duas verdades no produto. O teste que protege é o de média
   com nota não computável, rodado contra cada superfície (Painel, ficha de
   ciclo, ficha de aluno, tool do chat).

6. **A tentação de automatizar o Problema B.** Um detector de "pico em zero"
   pegaria as oito provas — e também toda Redação, onde o pico é legítimo.
   Seria **exatamente o erro da regra dos "2+ zeros no mesmo dia"**: uma
   heurística plausível que apaga dado bom em silêncio. Oito linhas de
   `UPDATE` com motivo escrito são mais honestas que um classificador.
4. **Escrita em lote no Canvas real** — [§4.3](#43--risco-específico).
5. **Volume sem paginação** (armadilha 2 do `CLAUDE.md`). O avaliador da P1 lê
   `questao_resposta_aluno`, que tem **237.081 linhas**. `PGRST_DB_MAX_ROWS`
   está sem valor de propósito: sem paginar, a leitura sai truncada **sem erro**.
   Reusar a paginação de `_carregar_notas_com_simulado`, não reinventar.

---

## 8 · O que este sprint deixa anotado, e não conserta

- **Presets de período** em `/provas` ("este ano", "último trimestre") — o
  único item aberto da C.3. Tamanho P, vai para o polimento.
- **`Ciclo.periodoInicio` declarado `str` obrigatório** num campo que o banco
  permite nulo, mascarado por um `or ""` na API. Existe um ciclo nulo agora.
- **`GET /ciclos` ordena só por `ordem`** — a ordenação passa a ser da tela.
- **`ClienteCanvas` sem `update_grades` em lote** — decidido em [§4.2](#42--como-implementar).
- **19 simulados com `nota_maxima = 0`** no banco, todos Fase 2. O fallback de
  10,0 em `recalcular_simulado` salva hoje (a maior pontuação de todos é ≤ 10),
  mas é armadilha esperando uma prova de 15 pontos entrar com
  `points_possible = 0` no Canvas.

---

## Fontes

- [10-problemas-e-visao.md](10-problemas-e-visao.md) — §B.3, §B.4, §C.2, §C.3
- [18-plano-sprint-2.md](18-plano-sprint-2.md) — §5 (Onda 3), §2.4, §7
- [19-roadmap.md](19-roadmap.md) — §3
- [31-plano-sprint-5.md](31-plano-sprint-5.md) — o método do levantamento
- **Produção (`portalsas.online`), conferida em 30/08 por `psql` no VPS:**
  102.143 notas, 1.523 alunos, 255 simulados, 2.756 zeros com presença,
  57.505 linhas com `presente = false`, **0 uploads de planilha**
- Snapshot de desenvolvimento (cópia de produção de 22/08), de onde vem a
  distribuição da evidência por questão: 26.810 notas, 237.081 respostas,
  152 simulados, 23 ciclos
