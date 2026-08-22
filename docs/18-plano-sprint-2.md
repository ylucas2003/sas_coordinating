# 18 — Sprint 2 · Critérios de classificação, Canvas sob controle, auditoria e identidade

> **Origem:** conversa com o Leonardo (coordenação) no WhatsApp em 21/08/2026,
> 18h39–19h15 — 15 mensagens e 15 áudios. O que ele pediu está na
> [§9](#9--o-que-veio-do-leo); o que decidimos por causa disso está em cada parte.
>
> **Escopo:** a régua de classificação, a escrita no Canvas, a trilha de
> auditoria e o método de login. A [Sprint 1](10-problemas-e-visao.md#210-sprint-1--escopo-e-divisão-17082026)
> fez o simulado nascer no SAS e o motor de lembretes; esta trata do que a
> coordenação **vê** e **decide** em cima disso.
>
> **Pronto quando:** o coordenador abre o painel e vê a lista ordenada pela régua
> certa — não-cortados primeiro, desempate em cascata, cores coerentes com o
> corte —, edita uma nota e **escolhe** se aquilo sobe para o Canvas, a escolha
> fica registrada numa linha do tempo auditável, e o aluno entra sem senha porque
> o Canvas já sabe quem ele é.

---

> **Estado (22/08/2026, fim do dia): EM PRODUÇÃO.** PRs #11, #12 e #13
> mergeados; deploy feito; migrations `0020`–`0027` aplicadas na VPS. P1–P3
> verificadas no browser com dados reais; P2 verificada também contra o Canvas
> real (curso de testes `694`); SSO verificado como aluno. 120 testes no
> backend, 91 no front. O que sobrou é de produto, não de código — está no
> [19-roadmap.md §2](19-roadmap.md#2--pendências-da-sprint-2--o-que-sobrou-sem-código).

## Divisão em 4 partes

Diferente da Sprint 1, **isto não é uma corrente**. Três partes são independentes
entre si e só a P3 depende de outra:

```
P1  critérios ─────────────┐
                           │
P2  Canvas ────▶ P3  auditoria
                           │
P4  identidade ────────────┘
    (destravada pela Developer Key, fora do nosso controle)
```

| Parte | O quê | Demonstrável quando |
|---|---|---|
| **P1** | [Critérios de classificação](#p1--critérios-de-classificação) | o painel classifica pelas réguas do Tio Leo, do ITA e do IME |
| **P2** | [Canvas sob controle](#p2--canvas-sob-controle) | nada sobe ao Canvas sem alguém clicar |
| **P3** | [Auditoria compartimentada](#p3--auditoria-compartimentada) | dá para responder "quem mudou isso, quando, e escolheu o quê" |
| **P4** | [Identidade e acesso](#p4--identidade-e-acesso) | o aluno entra pelo Canvas; a topbar tem logo e botão de sair |

> ⚠️ **Sendo honesto sobre tamanho:** as quatro partes completas não cabem num
> sprint, cabem em dois. A [ordem de execução](#5--ordem-de-execução) é desenhada
> para que, se o tempo acabar no meio, o que ficou pronto seja coerente — e não
> meia funcionalidade em quatro lugares.

---

## 0 · Pré-voo — não é parte, mas trava tudo

Nada aqui é código, e cada item bloqueia alguma coisa adiante.

### 0.1 O banco local está em `0019` — três migrations atrasadas

Verificado em 22/08/2026 (`_migracoes_aplicadas`): a última aplicada é
`0019_motor_lembretes`. Faltam:

| Migration | Sem ela |
|---|---|
| `0020_lembrete_aluno` | — |
| `0021_usuario_coordenacao` | **o login da coordenação não funciona local** — o código já lê essa tabela ([auth.py](../api/app/routes/auth.py)) |
| `0022_evento_auditoria` | **a P3 inteira não tem onde gravar** |

```sh
docker compose run --rm migrate status
docker compose run --rm migrate up
docker compose restart postgrest        # armadilha nº1 do CLAUDE.md
```

### 0.2 Resolver a branch — ✅ era falso alarme

`fix/login-html-redirect` parecia ter 4 commits pendentes, mas isso era contra um
`main` **local desatualizado** (parado no PR #8). Contra `origin/main` (PR #10) o
`diff` é **vazio**: a branch já está inteiramente mergeada. Nada a preservar.

O sprint sai de `origin/main`, uma branch por parte — `feat/criterios-classificacao`
é a da P1.

### 0.3 Criar a Developer Key do Canvas

**Não é dependência de terceiro** — verificado em 22/08/2026 contra
`aridesa.instructure.com`: o dono do `CANVAS_API_TOKEN` é o usuário `Admin`
(id 7387), administra a conta raiz `1` (Colégio Ari de Sá), e
`GET /accounts/1/developer_keys` devolve **HTTP 200** — ou seja, tem permissão de
gerenciar chaves. Existem **0** hoje.

Criar em `Admin → Developer Keys → + Developer Key → + API Key`:

| Campo | Valor |
|---|---|
| Key Name | `SAS — portalsas.online` |
| Redirect URIs | `https://portalsas.online/auth/canvas/callback`<br>`http://localhost:8080/auth/canvas/callback` |
| Estado | ligar para **ON** depois de criar |

`client_id` e `client_secret` vão para o `api/.env` como `CANVAS_CLIENT_ID` /
`CANVAS_CLIENT_SECRET`. Cinco minutos, sem espera.

> ⚠️ O `CANVAS_API_TOKEN` **não serve** para SSO: ele autentica o SAS *como o
> Admin*, e toda requisição diz "sou o id 7387". Nunca responde "quem é o browser
> na minha frente?", que é a única coisa que o login precisa saber.

### 0.4 Mandar as três perguntas ao Leo

Listadas na [§9.2](#92-ainda-aberto). Nenhuma bloqueia a P1 — todas caem sobre
código que se escreve sem elas.

---

## P1 · Critérios de classificação

### 1.1 Por quê: a regra do corte existe três vezes, e já divergiu

| Onde | O que diz | O que decide |
|---|---|---|
| [`TabelaPainel.tsx:27`](../web/src/telas/Painel/TabelaPainel.tsx#L27) | `nota >= 7 ? verde : nota >= 5 ? ambar : vermelho` | a cor da célula |
| [`painel.ts:329`](../web/src/dominio/painel.ts#L329) | `notas.every(n => n >= 5)` | linha cortada/aprovada + KPI "em zona de corte" |
| [`thresholds.py`](../api/app/stats/thresholds.py) | `NOTA_CORTE_FASE_2 = 4.0`, só Fase 2 | `classificacao_aluno.zona` |

Front e backend discordam há tempo (5,0 contra 4,0) e **nenhum dos dois
implementa a regra real do ITA nem a do IME**. Foi isso que o Leo viu às 18h56:
um 4,0 pintado de vermelho porque `4 < 5`.

Não é erro de digitação — é consequência de a regra ser código copiado em vez de
dado. Enquanto o limiar é constante, dá para viver com três cópias. Quando o
coordenador puder **criar** critérios ([§1.10](#110-futuro-critérios-criados-pelo-coordenador)),
cada operador novo teria de ser escrito em TypeScript **e** em Python — e a
divergência deixa de ser um número errado e vira "o filtro que eu criei mostra
coisa diferente em cada tela".

### 1.2 Decisão: a regra vira dado, e o servidor é dono dela

1. **Um avaliador só, em Python, no backend.** O front não reimplementa regra de
   corte — pede o veredito e desenha.
2. **A regra é uma estrutura de dados**, não uma função com constantes. Tio Leo,
   ITA e IME viram três valores do mesmo formato.
3. **A cor é saída do avaliador**, não uma quarta regra.

**O custo, dito com honestidade:** hoje o painel calcula em memória e trocar de
fase é instantâneo; passa a ser uma chamada de rede (~200 ms, cacheável no React
Query). Como ele já baixa os ~1500 alunos inteiros sem paginação, a chamada extra
é barata — e compra a impossibilidade de as duas pontas divergirem de novo.

### 1.3 Onde a regra mora: um arquivo, legível por quem entende do domínio

**Arquivo novo:** `api/app/stats/criterios.py`. É ele que se abre para ler ou
mudar uma regra — mesmo princípio que já rege o
[`thresholds.py`](../api/app/stats/thresholds.py) ("ficam num arquivo só pra
coordenação editar à mão"), agora aplicado à regra inteira e não só aos números.

Contém três coisas, nesta ordem:

1. as **estruturas** (`Criterio`, `Predicado`) — o vocabulário;
2. o **avaliador** — função **pura**, sem I/O, testável sem banco;
3. os **três critérios embutidos** como literais, cada predicado com o artigo do
   edital citado no comentário ao lado.

Nada de regra espalhada por rota, serviço ou query. Quem quiser saber por que um
aluno foi cortado abre **um** arquivo.

> **Convenção da casa:** o comentário explica o *porquê* e cita a fonte. Aqui a
> fonte é o edital, e a citação é o artigo — `# ITA §4.6.5: inglês não é
> classificatório` vale mais que qualquer paráfrase.

### 1.4 A estrutura de um critério

```
Criterio
  nome           "ITA — Fase 1"
  fase           1 | 2
  combinador     "todos" (E) | "algum" (OU)   ← liga só os predicados NÃO eliminatórios
  predicados     [Predicado, ...]
  desempate      ["media", "matematica", "fisica", ...]

Predicado
  materia        "matematica" | ... | "*" (todas)  |  None → média geral
  operador       ">=" | ">" | "<=" | "<" | "entre"
  valor          nota (0–10)  ou  {acertos: N, de: M}
  eliminatorio   bool   ← True: reprova sozinho, ignora o combinador
  entra_na_media bool   ← False: cobrado mas fora do cálculo da média
  peso           float  ← 1.0 salvo quando o edital pesa diferente
```

Os três campos finais não são enfeite; sem eles nenhum dos critérios da
[§1.5](#15-os-três-critérios-embutidos) é representável:

- **`eliminatorio`** — o inglês do ITA na Fase 1 reprova sozinho, sem consultar o
  `E`/`OU` do critério.
- **`entra_na_media`** — esse mesmo inglês é cobrado e **não** entra na média
  (ITA §4.6.5). No IME é o oposto: entra, com peso 1.
- **`peso`** — o IME usa média ponderada (3 / 2,5 / 2,5 / 1 / 1), não simples.

**`valor` aceita "acertos de N" de propósito.** Os editais expressam o mínimo da
1ª fase em acertos, não em nota: o ITA pede 5 de 12 (= 4,1667) e o IME pede 4 de
10 (= 4,00). Simulado com número de questões diferente da prova real dá veredito
errado se a conta sair só da nota normalizada.

O avaliador devolve, por aluno, **o veredito e o motivo**:

```
{ aprovado: bool,
  predicado_que_falhou: "quimica < 4,0 (3,2)",   ← alimenta tooltip e badge
  valor_ordenacao: [media, mat, fis, qui, ing],  ← desempate em cascata
  tom: "verde" | "ambar" | "vermelho" }
```

O motivo não é extra: transforma "linha vermelha" em *"cortado por Química 3,2"*.
A tese do produto é sinalizar o que merece atenção — aqui ela sai de graça.

### 1.5 Os três critérios embutidos

#### 1.5.1 "Tio Leo" — a régua pedagógica do Ari

Ditada no áudio das 19h02, com as respostas de 22/08:

| | |
|---|---|
| Corte | reprova alguma disciplina (`< 40%`) **E** média geral `< 50%` |
| Inglês | **eliminatório sozinho**, corte 4,0, **fora da média** |
| Vale para | ITA e IME indistintamente |
| Ordenação | não-cortados primeiro; cortados no fim, independente da nota |
| Desempate | média → Matemática → Física → Química → Inglês → mantém empate |

O `E` é decisão explícita da coordenação e diverge dos dois editais (que são
`OU`). É intencional: este critério é a régua **pedagógica** do colégio, não a do
vestibular. É exatamente por isso que existem três critérios e não um.

**Ordem de grandeza no banco de hoje** (626 alunos com nota; estimativa — junta
F1 e F2 e usa todas as notas em vez da janela de 5):

| | Alunos |
|---|---|
| Reprovam alguma matéria (< 4,0) | 483 |
| Média geral < 5,0 | 437 |
| **Cortados com `E`** | **433** |
| Cortados com `OU` (referência) | 487 |

#### 1.5.2 ITA — [Edital Vestibular 2026 (retificado)](https://www.vestibular.ita.br/instrucoes/edital_2026_retificado.pdf)

**Fase 1** — 48 questões: 12 Matemática, 12 Física, 12 Química, 12 Inglês (§4.1.2)

| Regra | Fonte |
|---|---|
| Mínimo **5 acertos em cada** conjunto de 12 — **incluindo Inglês** | §4.6.2.1 |
| Média final ≥ **5,0000** | §4.6.2.2 |
| Média F1 = (acertos Mat + Fís + Quím) ÷ 36 × 10. **"A pontuação de Inglês não é classificatória, portanto, não entra no cálculo da média."** | §4.6.5 |
| Além disso: estar entre os 560 melhores (ampla) ou 140 (cotas) | §4.6.2.3–4 |

> O corte por vaga (560/140) **não entra no critério**: é limite de convocação do
> ITA, não régua de desempenho. Simular isso sobre 1500 alunos de um colégio não
> significa nada.

**Fase 2** — Mat/Fís/Quím dissertativas (10 questões cada) + Português (15 objetivas + redação)

| Regra | Fonte |
|---|---|
| Eliminado com **redação < 4,00** ou **≤ 5 acertos** das 15 de Português | §4.6.6.3.1 |
| Reprovado se **qualquer** matéria da F2 (Mat, Fís, Quím, Port) < **4,00** | §4.6.6.5 |
| Média geral: **20% F1 + 20% Mat + 20% Fís + 20% Quím + 20% Port** | §4.7 |
| Habilitado: média ≥ 5,0000 **e** ≥ 4,00 em cada disciplina | §4.9.1.1 |
| Desempate: Matemática → Física → Química → Português → **data de nascimento mais antiga** | §4.9.1.3 |

**Consequência imediata:** o [`thresholds.py`](../api/app/stats/thresholds.py)
exclui inglês do corte por completo (`MATERIAS_PARA_CORTE` tem só
Mat/Fís/Quím/Port). **Está errado para o ITA** — lá o inglês elimina — e também
erra ao incluir Português na Fase 1, onde ele não é cobrado.

#### 1.5.3 IME — [Edital CFG Ativa 2026/2027](https://inscricoes.ime.eb.br/documentos/Edital_CFG_ATIVA_2026_2027.pdf)

**Fase 1** — 40 questões: 15 Matemática, 15 Física, 10 Química. **Sem Português e sem Inglês** (Art. 38)

Eliminado quem se enquadrar em qualquer situação do **Art. 40**:

| | Condição |
|---|---|
| I | nota da prova objetiva < **5,00** (menos de 20 acertos no total) |
| II | Matemática com menos de **6 acertos** (de 15) |
| III | Física com menos de **6 acertos** (de 15) |
| IV | Química com menos de **4 acertos** (de 10) |

**Fase 2** — cinco provas, com pesos (Art. 37, III):

| Prova | Peso |
|---|---|
| Matemática (discursiva) | **3** |
| Física (discursiva) | **2,5** |
| Química (discursiva) | **2,5** |
| Português (objetiva + redação) | **1** |
| **Inglês** (objetiva) | **1** |

| Regra | Fonte |
|---|---|
| Reprovado com **< 4,00 em qualquer** prova da 2ª fase | Art. 52 e 64 |
| Redação: APTO se ≥ 4,00, INAPTO se < 4,00 — INAPTO reprova | Art. 50 §2º, Art. 65 |
| Nota final = **média ponderada** das provas da 2ª fase | Art. 63 |
| Desempate: Mat → Fís → Quím → Português → **Inglês** → **maior idade** | Art. 70 §2º |

#### 1.5.4 O que difere entre os dois

| | ITA | IME |
|---|---|---|
| Inglês na Fase 1 | sim — eliminatório, **fora da média** | não existe |
| Inglês na Fase 2 | não existe | sim — **peso 1, dentro da média** |
| Português na Fase 1 | não existe | não existe |
| Composição da média | 20% cada (F1 + 4 provas da F2) | **ponderada** 3 / 2,5 / 2,5 / 1 / 1 |
| Mínimos da Fase 1 | 5 de 12 em cada uma das 4 | 6/15 · 6/15 · 4/10 |
| Fim do desempate | data de nascimento mais antiga | maior idade (e Inglês entra antes) |

### 1.6 Ordenação

Ordenar é parte da definição do critério, não do componente de tabela. Duas
regras que a [`ordenacao.ts`](../web/src/componentes/ui/ordenacao.ts) não tem:

1. **Dois blocos.** Não-cortados primeiro, cortados depois — *"o cara pode ter a
   maior nota; se levou corte na matéria, fica depois do que não levou corte
   nenhum"* (Leo, 19h03).
2. **Desempate em cascata**, na ordem que o critério declara. Hoje
   [`valorOrdenacao()`](../web/src/dominio/painel.ts) devolve um número só.

### 1.7 Migration `0023` — critérios como dado

`criterio_classificacao` + `predicado_criterio` (tabela filha, **não** `jsonb`,
para a coordenação ler o critério num `SELECT` e entender — legibilidade de
schema é padrão da casa) com `versao` desde o começo. Os três embutidos entram
como carga inicial a partir dos literais de `criterios.py`.

> **Não se chama `metrica`:** já existe [`metrica_simulado`](../api/migrations/0001_schema_inicial.sql)
> e significa outra coisa (média, mediana, desvio, quartis de um simulado).

### 1.8 Rota

`GET /ciclos/{id}/classificacao?criterio=<slug|id>` → lista ordenada com
veredito, motivo e posição.

### 1.9 Front — o que morre

- `statusAluno()` ([painel.ts:311-330](../web/src/dominio/painel.ts#L311-L330)) **apagado**
- o ternário de cor em [`TabelaPainel.tsx:27`](../web/src/telas/Painel/TabelaPainel.tsx#L27) **apagado** — `NotaBadge` recebe o tom pronto
- KPI "Em zona de corte" ([Painel.tsx:201](../web/src/telas/Painel/Painel.tsx#L201)) e a legenda ([Painel.tsx:368](../web/src/telas/Painel/Painel.tsx#L368)) passam a citar a régua do critério ativo
- seletor de critério: Tio Leo · ITA · IME

### 1.10 Futuro: critérios criados pelo coordenador

Pedido: *"criar rotas e UI para o coordenador criar filtros — por exemplo, nota 7
em Mat/Fís/Quím e maior que 4 em Português"*. **Fora do sprint**, mas o formato
acima nasce pronto: é o mesmo `Criterio` com outros valores.

Duas coisas ficam decididas agora porque são caras depois: as **tabelas** de
[§1.7](#17-migration-0023--critérios-como-dado), e **critério imutável — editar
cria versão**. Sem `versao`, editar um critério muda retroativamente os números
de quem já o usou, em silêncio. Os três embutidos seguem no arquivo e são a
semente da tabela: o arquivo é a fonte da verdade das regras embutidas, a tabela
guarda as que o coordenador criar. Um formato, um avaliador.

### 1.11 Pronto quando

Os três critérios rodam sobre dados reais; o avaliador tem teste unitário sem
banco; `0023` faz `up`/`down`/`up` limpos; `grep -rn ">= 5" web/src/dominio
web/src/telas` não devolve regra de corte; e um aluno com Química 3,2 e média 6,7
devolve veredito **diferente** sob "Tio Leo" (aprovado, regra `E`) e sob "ITA"
(cortado, §4.9.1.1).

---

## P2 · Canvas sob controle

### 2.1 Por quê: decisão de produto do Leo

- **Nada sobe automaticamente.** Toda alteração que fosse chamar uma rota de
  escrita no Canvas passa por uma UI em que o coordenador decide se quer mudar lá
  também. *"Pode abrir um pop-upzinho"* (19h05).
- **Divergir é aceitável.** Se ele disser não, *"fica diferente mesmo"*. Isso faz
  da divergência um **estado legítimo**, que precisa ser visível e persistido —
  nunca tratado como erro.
- **Não criar curso nem aluno no Canvas** — *"puxando de lá já está bom"* (19h13).

### 2.2 A superfície completa: cinco pontos de escrita

| Rota | Chama | Hoje |
|---|---|---|
| `POST /ciclos` | `criar_assignment_group` ([ciclos.py:101](../api/app/routes/ciclos.py#L101)) | automático |
| `POST /simulados/agendar` | `criar_assignment` ([simulados.py:153](../api/app/routes/simulados.py#L153)) | automático |
| `PATCH /simulados/{id}` | `atualizar_assignment` | automático — *"toda edição faz write-back no Canvas"* |
| `DELETE /simulados/{id}` | `apagar_assignment` ([simulados.py:702](../api/app/routes/simulados.py#L702)) | automático ⚠️ |
| `PATCH /notas/{aluno}/{simulado}` | `atualizar_nota_submission` ([notas.py:98](../api/app/routes/notas.py#L98)) | automático e **obrigatório** |

São cinco, e não dois. O `DELETE` é o único irreversível: apagar o simulado no
SAS apaga o Assignment no Canvas **com as submissions dos alunos junto**. Ali o
pop-up deixa de ser conveniência e vira proteção.

Meio caminho já existe: `POST /simulados/{id}/retry-canvas`
([simulados.py:624](../api/app/routes/simulados.py#L624)) já é um botão
"sincronizar agora". O padrão nasce dele.

### 2.3 Contrato uniforme

- **Backend:** toda rota de mutação recebe `sincronizar_canvas: bool`, **sem
  default**. A rota nunca decide sozinha; o `await canvas.…` sai do corpo das
  cinco e vira uma chamada num lugar só.
- **Front:** um componente de confirmação compartilhado, hospedado no
  [`DialogoComDiff`](../web/src/componentes/dialogos/DialogoComDiff.tsx) — ele já
  mostra o que vai mudar; ganha a linha "e no Canvas?", com **"enviar agora"** /
  **"deixar só no site"**.

### 2.4 Nota: "sempre o Canvas + alterações do SAS"

Decisão de 22/08, e mais simples que as alternativas que estavam na mesa:

```
nota.valor_canvas   ← o sync escreve SEMPRE. Sem guarda, sem exceção.
nota.valor_sas      ← a edição do coordenador. NULL se nunca editaram.
valor exibido       = COALESCE(valor_sas, valor_canvas)
```

**O sync não precisa de guarda nenhuma** — ele nunca toca em `valor_sas`. O
Canvas segue fluindo por baixo, a edição fica por cima, e a divergência é
derivável (`valor_sas IS NOT NULL AND valor_sas <> valor_canvas`), não um estado
a manter sincronizado.

Isso resolve o conflito temporal que motivou a regra atual:

| Quando | Evento | `valor_canvas` | `valor_sas` | Exibido |
|---|---|---|---|---|
| Segunda | professor corrige no Canvas | 6,0 | — | 6,0 |
| Terça | coordenador edita no SAS, escolhe não enviar | 6,0 | **8,0** | **8,0** |
| Quarta | professor recorrige no Canvas | **7,0** | 8,0 | **8,0** |

A correção do professor **não se perde** (está em `valor_canvas`) e a do
coordenador **não evapora** — que era o problema descrito no cabeçalho de
[`notas.py`](../api/app/routes/notas.py): *"o coordenador corrigia a nota e ela
sumia sozinha"*.

**Efeito colateral bom:** `valor_canvas` guarda o histórico que o Leo queria
preservar ("fica o registro da nota anterior lá no Canvas") — só que **dentro do
SAS**, e reverter passa a ser uma leitura de tabela.

**O que muda em [`notas.py`](../api/app/routes/notas.py):** a ordem "Canvas
primeiro, banco depois" com falha abortando a edição deixa de ser necessária. O
docstring precisa ser reescrito junto — ele documenta um invariante que deixa de
valer.

### 2.5 Estado de sincronização e uma armadilha

`simulado` já tem `canvas_estado` / `canvas_erro` / `canvas_tentativas`. Não é
conceito novo: estende-se a `ciclo` e acrescenta-se um valor.

```
pendente     → vai mandar, ainda não deu
falhou       → tentou, deu erro, tenta de novo
sincronizado → igual nos dois lados
divergente   → o coordenador ESCOLHEU não mandar. Nunca reenviar sozinho.
```

> ⚠️ **A armadilha.** `reprocessar_canvas_pendentes` varre
> `canvas_estado in ('pendente','falhou')` e reenvia
> ([agendamento.py:197](../api/app/canvas_sync/agendamento.py#L197)). Gravar "o
> coordenador disse não" como `pendente` faz o job **mandar pro Canvas sozinho em
> minutos**, desfazendo a decisão em silêncio. `divergente` existe para o retry
> ignorar por definição — e é o que alimenta o badge "difere do Canvas" na tela.
> Sem badge, "fica diferente mesmo" vira diferente **e invisível**.

`nota` **não** recebe `canvas_estado`: com o modelo da [§2.4](#24-nota-sempre-o-canvas--alterações-do-sas)
a divergência é derivada das duas colunas, e um estado a mais só criaria uma
segunda verdade para manter em dia.

### 2.6 Lembretes não dependem do Canvas

Um simulado criado no SAS e ainda não sincronizado **dispara os lembretes de
professor normalmente** (decisão de 22/08). O motor de lembretes é do SAS e não
deve depender de sistema externo para funcionar.

Consequência a tratar: um professor pode ser lembrado de uma prova que não existe
no Canvas. O badge de divergência precisa aparecer **também na agenda e no
lembrete**, não só na tela do simulado.

### 2.7 Migration `0024`

```sql
ALTER TABLE nota  ADD COLUMN valor_canvas numeric;   -- o sync escreve sempre
ALTER TABLE nota  ADD COLUMN valor_sas    numeric;   -- edição do coordenador
ALTER TABLE ciclo ADD COLUMN canvas_estado text;     -- + valor 'divergente'
```

Backfill: `valor_canvas = pontuacao` para tudo que já existe. **Junto,
obrigatoriamente:** a guarda em `reprocessar_canvas_pendentes`.

### 2.8 Pronto quando

`grep -n "await canvas\." api/app/routes/` não devolve nada; editar uma nota sem
sincronizar, rodar o sync duas vezes e o valor do SAS continuar de pé; as cinco
rotas passam pelo mesmo componente de confirmação; e o `DELETE` tem confirmação
reforçada avisando que leva as submissions junto.

---

## P3 · Auditoria compartimentada

Pedido do Leo (19h06): *"separo um grupo de logs só de sincronização… a gente
consegue puxar na linha do tempo todas as alterações que foram feitas… para a
gente rodar algum script depois caso alguém faça merda"*.

### 3.1 Já existem dois sistemas — o erro seria criar um terceiro

| Tabela | Registra |
|---|---|
| `canvas_sync_execucao` | execuções da **máquina** — job de 5 min, backfill: tipo, status, resumo, erro ([upsert.py:508](../api/app/ingest/upsert.py#L508)) |
| `evento_auditoria` | ações **humanas** — quem fez o quê ([0022](../api/migrations/0022_evento_auditoria.sql)) |

A separação certa já está posta. O Leo pediu a segunda, e ela hoje só grava
`login_ok`, `login_falhou` e `primeiro_acesso_bloqueado` — apesar de o próprio
COMMENT da 0022 prometer `nota_editada` e `acesso_resetado`.

### 3.2 Compartimentar é uma coluna, não uma tabela

`evento_auditoria.canal` (`'canvas'`, `'nota'`, `'simulado'`, `'acesso'`).

- **Tabela separada** mata o valor do registro: a pergunta real é "o que
  aconteceu naquela tarde?", e a resposta cruza canais. Separar obriga a `UNION`
  para reconstruir a única coisa que interessa.
- **Prefixo em `acao`** (`canvas.nota.enviada`) compartimenta por convenção —
  funciona até alguém escrever `canvas_nota_enviada` e sumir do filtro.
- **Coluna** compartimenta como dado: indexável, filtrável na UI, e permite
  retenção diferente por canal — o que importa aqui, porque são dados de menores
  e a 0022 já invoca o art. 37 da LGPD como justificativa.

### 3.3 Registrar a decisão, não só a ação

```
acao:    "nota_editada"
canal:   "canvas"
detalhe: { valor_antes, valor_depois, valor_canvas,
           sincronizar_canvas: false,     ← a escolha do coordenador
           motivo_corte: "quimica 3,2" }
```

Sem `sincronizar_canvas` no registro, daqui a três meses ninguém distingue
"escolheu não mandar" de "tentou e falhou" — exatamente a diferença que o estado
`divergente` existe para marcar.

O `request_id` já está lá ([auditoria.py](../api/app/auditoria.py) via
`request_id_atual()`) e é o que costura, numa linha só da timeline, uma edição
que toca SAS + Canvas + recálculo de estatística. Não precisa inventar; precisa
usar.

### 3.4 O log não pode ser load-bearing

[`auditoria.registrar()`](../api/app/auditoria.py) engole a própria exceção **de
propósito**: *"auditoria que derruba a operação auditada é pior que auditoria
ausente"*. Certo para login. Mas se o script de reversão ler dali, um INSERT que
falhou em silêncio produz um script **incompleto e confiante** — o pior resultado
possível. E não há como transacionar: o backend fala PostgREST, sem transação
entre tabelas.

A saída é não pedir isso ao log:

- **Reversibilidade mora na linha** — `valor_canvas` fica em `nota`, gravado no
  mesmo upsert da edição. Reverter é ler a tabela, não o log.
- **Narrativa mora no log** — quem, quando, por qual request, com qual decisão.

Assim o melhor-esforço continua correto, porque nada crítico depende dele.

### 3.5 Migration `0025` e pronto quando

`evento_auditoria.canal`, mais os eventos que faltam (`nota_editada`,
`simulado_criado`, `simulado_removido`, `ciclo_criado`, `enviado_ao_canvas`,
`acesso_resetado`). **Pronto quando:** editar uma nota e escolher "não enviar"
produz um evento em que dá para distinguir *escolheu não mandar* de *tentou e
falhou*, e a tela de linha do tempo filtra por canal e por ator.

---

## P4 · Identidade e acesso

### 4.1 Os números que decidem

Consultados no banco em 22/08/2026:

| | |
|---|---|
| Alunos ativos | 876 |
| Com `canvas_user_id` | **876 — 100%** |
| Com e-mail | 876 |
| **Com senha no SAS** | **1** |

Domínio dos e-mails (vindos do Canvas): **775 gmail.com**, 31 hotmail,
**15 aridesa.edu.br**, 9 outlook, resto pulverizado.

Duas leituras:

1. **Não existe Google Workspace institucional para os alunos.** O e-mail no
   Canvas é conta pessoal, cadastrada pela família.
2. **Não existe base instalada de senha.** Trocar o método de login agora custa
   **zero migração** — e essa janela fecha no dia em que a coordenação
   provisionar os 876.

### 4.2 Decisão: Canvas SSO (OAuth2, fluxo de redirect)

O Canvas é o provedor de identidade.

- **O mapeamento já existe:** a chave que o OAuth devolve é o `canvas_user_id`,
  que já está em `aluno` e já é usado pelo write-back de nota
  ([notas.py:146](../api/app/routes/notas.py#L146)).
- **"Já logado entra direto"** funciona como o Leo imaginou: o redirect encontra
  a sessão do Canvas no browser e volta sem tela nenhuma.
- **O papel vem do enrollment** do Canvas — resolve "decidir aluno ou coordenador
  pelo login" (pedido dele às 18h45) sem procurar em duas tabelas nem arriscar
  enumeração de usuário.

**Custa duas coisas.** A **Developer Key** ([§0.3](#03-pedir-a-developer-key-do-canvas)),
e um **fallback**: se o login depender do Canvas, Canvas fora do ar = ninguém
entra, nem a coordenação. Matrícula + senha continua existindo como porta dos
fundos.

### 4.3 O que sai da lista por causa disso

| Item | Situação |
|---|---|
| Primeiro acesso com **CPF + nome + RA** (Leo, 19h15) | **descartado.** O motivo do CPF era verificar identidade — *"a gente vê, esse cara tá falando a verdade"*. O Canvas já fez isso. Além disso **não existe CPF no schema**, em nenhuma migration, e o Canvas não fornece o dado |
| **Coordenador consultar a senha do aluno** (Leo, 19h15) | **impossível como pedido** — PBKDF2-SHA256, 600k iterações ([0012](../api/migrations/0012_senha_pbkdf2.sql)): hash de mão única, ninguém lê a senha. Com SSO o problema deixa de existir; o fallback segue sendo `POST /alunos/{id}/resetar-acesso`, que já existe |

### 4.4 A topbar da coordenação

Vinte minutos, mesmo arquivo, e é o que o Leo nota primeiro
([`Topbar.tsx`](../web/src/componentes/layout/Topbar.tsx)):

- **Botão de sair** — `sessao.encerrar()` já existe ([sessao.ts](../web/src/servicos/sessao.ts))
  e o aluno já tem o botão ([ShellAluno.tsx:82](../web/src/telas/Aluno/ShellAluno.tsx#L82))
- **Logo do Ari** ao lado do asterisco do SAS

⚠️ O logo entra como **asset local**. Nada de CDN — regra 5 do [CLAUDE.md](../CLAUDE.md).

### 4.5 Google fica fora, e por quê

Plus, **nunca método único** — uns 85 alunos não têm conta Google. O que ele
entrega aqui é menor do que parece: sem domínio institucional não dá para
restringir por `hd`, e a identidade atestada é "quem controla aquele Gmail" — que
pode ser a mãe ou o irmão.

A parte técnica é rápida: login usa só `openid`/`email`/`profile`, escopos **não
sensíveis**, então a revisão pesada (semanas a meses) não se aplica. O que se
aplica é **brand verification** — automatizada, "alguns minutos", ou 2–3 dias
úteis se cair em revisão manual.

**O que segura são três pré-requisitos que não são código:** domínio verificado
no Google Search Console; **política de privacidade pública hospedada no mesmo
domínio** — que **não existe** e trata de dados de ~900 menores, então quem manda
nela é a LGPD e o DPO do colégio, não o Google; e uma **homepage pública** (hoje
`portalsas.online` cai direto no login).

> ⚠️ Publicado como *External*, qualquer pessoa com conta Google chega à tela de
> consentimento. O backend precisa rejeitar identidade Google que não bata com um
> `aluno` — senão é porta aberta, não login.

Os dois primeiros pré-requisitos **já são devidos de qualquer jeito**: o
[14 §5.4](14-plano-producao.md) registra que não existe caminho de exclusão de
dado pessoal no sistema. O Google só força algo que o projeto já deve.

### 4.6 Painel de administrador — **prioridade confirmada (22/08)**

Perguntado ao Leo às 18h55 (*"vai ter um acesso para administrador? para poder
gerenciar os logins?"*) e confirmado como prioridade em 22/08. Sai da lista de
"corta se faltar tempo" e entra no escopo firme da P4.

A tabela `usuario_coordenacao` existe desde a [0021](../api/migrations/0021_usuario_coordenacao.sql),
mas **não há nenhuma rota de CRUD**: hoje uma conta de coordenação só nasce por
`INSERT` na mão. Falta:

- **CRUD de `usuario_coordenacao`** — criar, renomear, desativar, resetar senha.
  Nunca deletar: desativar preserva a autoria na trilha de auditoria da P3
- **Tela de quem já acessou** — alunos com primeiro acesso feito, com
  `ultimo_login_em`, e o botão de liberar novo acesso que já existe em
  [`AcessoDoAluno.tsx`](../web/src/telas/AlunoFicha/AcessoDoAluno.tsx)
- **Só coordenação chega aqui** — a rota exige `get_current_coordenador`

> O SSO da [§4.2](#42-decisão-canvas-sso-oauth2-fluxo-de-redirect) resolve *quem é*
> a pessoa; o painel de administrador resolve *quem pode entrar*. São
> complementares — o Canvas não decide quem tem acesso ao SAS.

### 4.7 Migration `0026` e pronto quando

`usuario_coordenacao.canvas_user_id`. **Pronto quando:** um aluno já logado no
Canvas abre `portalsas.online` e entra sem digitar nada; o papel vem do
enrollment; e derrubar o Canvas não impede a coordenação de entrar pelo fallback.

---

## 5 · Ordem de execução

As partes são independentes, mas a ordem de **execução** não é a ordem de
numeração — a fundação vem primeiro para que o resto fique barato.

**Onda 1 · fundação** — não depende de resposta de ninguém
[1.3](#13-onde-a-regra-mora-um-arquivo-legível-por-quem-entende-do-domínio) ·
[1.7](#17-migration-0023--critérios-como-dado) ·
[1.8](#18-rota) · [2.3](#23-contrato-uniforme) ·
[2.7](#27-migration-0024) · [3.5](#35-migration-0025-e-pronto-quando)

**Onda 2 · o que o Leo vê**
[1.5.1](#151-tio-leo--a-régua-pedagógica-do-ari) (quando as respostas chegarem) →
[1.9](#19-front--o-que-morre) · [1.6](#16-ordenação) ·
[2.4](#24-nota-sempre-o-canvas--alterações-do-sas) · badge de divergência ·
[4.4](#44-a-topbar-da-coordenação)

**Onda 2b · P4** — destravada, já que a Developer Key não depende de terceiro
([§0.3](#03-criar-a-developer-key-do-canvas)): SSO + painel de administrador
([§4.6](#46-painel-de-administrador--prioridade-confirmada-2208)) +
[topbar](#44-a-topbar-da-coordenação)

**Onda 3 · corta se o tempo acabar**
regra de corte na Fase 1 (hoje `_notas_fase2_por_aluno_materia` filtra
`tipo != 'fase_2'` de propósito) · envio em lote ao Canvas · tela de linha do
tempo da auditoria

**O corte natural é o fim da Onda 2:** entrega a classificação certa, a
sincronização sob controle e a auditoria gravando — coerente de ponta a ponta.

---

## 6 · Migrations

| # | O quê | Parte |
|---|---|---|
| `0023` | `criterio_classificacao` + `predicado_criterio` + `versao` | P1 |
| `0024` | `nota.valor_canvas` / `nota.valor_sas` · `ciclo.canvas_estado` | P2 |
| `0025` | `evento_auditoria.canal` | P3 |
| `0026` | `usuario_coordenacao.canvas_user_id` | P4 |

Toda migration com par `.down.sql`, e `restart postgrest` depois de cada `up` que
crie ou altere tabela.

---

## 7 · Riscos

1. ~~**O `E` do critério "Tio Leo" contraria o áudio das 19h03.**~~ ✅
   **Resolvido em 22/08:** confirmado que é `E` mesmo, e que os ~50 alunos que
   passam na média com uma matéria abaixo de 4 **não** são cortados. A régua
   pedagógica diverge do edital de propósito.
2. **Volume sem paginação.** A rota de classificação lê `nota` inteira; não existe
   paginação em lugar nenhum e `PGRST_DB_MAX_ROWS` está sem valor de propósito.
   `_carregar_notas_com_simulado` já pagina em lotes de 1000 — o avaliador deve
   reusar, não reinventar.
3. ~~**Developer Key fora do controle do time.**~~ ✅ **Resolvido em 22/08:** o
   token do SAS é admin da conta raiz e pode criar a chave
   ([§0.3](#03-criar-a-developer-key-do-canvas)). O risco que sobra é operacional:
   é preciso ter o **login** da conta `Admin` no painel do Canvas, não só o token.
4. **Escrita no Canvas real durante o desenvolvimento.** O `CANVAS_API_TOKEN` do
   `.env` é de admin e funciona: um teste descuidado altera nota ou apaga
   Assignment do colégio de verdade. Todo teste da P2 usa **mock**; verificação
   contra o Canvas real é passo manual e deliberado.

---

## 8 · Fora do escopo, de propósito

- **UI de criação de critérios pelo coordenador** ([§1.10](#110-futuro-critérios-criados-pelo-coordenador))
- **Criar curso ou aluno no Canvas** — descartado pelo Leo às 19h13
- **Primeiro acesso com CPF** — descartado pelo Canvas SSO
- **Login com Google** ([§4.5](#45-google-fica-fora-e-por-quê))

---

## 9 · O que veio do Leo

### 9.1 Fechado por ele

| Quando | O quê |
|---|---|
| 18h45 | perfil (aluno/coordenador) decidido pelo login, não por toggle |
| 18h54 | botão de sair; logo do Ari na topbar |
| 18h55 | quer acesso de administrador para gerenciar logins |
| 18h56–57 | 4,0 não é corte — deveria ser amarelo; cores das disciplinas seguem régua errada |
| 19h02–03 | a regra de corte e a ordem de desempate ([§1.5.1](#151-tio-leo--a-régua-pedagógica-do-ari)) |
| 19h04–05 | Canvas só por botão, com pop-up de confirmação |
| 19h13 | não criar curso nem aluno no Canvas — puxar já basta |

### 9.2 Fechado em 22/08 — nada aberto

1. **Professor recorrige no Canvas depois da edição no SAS — o painel mostra
   qual?** → **a do SAS, com aviso visível de que difere do Canvas.** As duas
   notas continuam existindo ([§2.4](#24-nota-sempre-o-canvas--alterações-do-sas));
   a do coordenador é a exibida.
2. **Painel de administrador é prioridade?** → **sim.** Entra no escopo firme da
   P4 ([§4.6](#46-painel-de-administrador--prioridade-confirmada-2208)).
3. **A régua do "Tio Leo" está certa com `E`?** → **sim, assim mesmo.** Os ~50
   alunos que passam na média com uma matéria abaixo de 4 não são cortados.

**Não há decisão pendente com a coordenação.** O que falta é operacional:
criar a Developer Key ([§0.3](#03-criar-a-developer-key-do-canvas)) e entregar o
arquivo do logo do Ari ([§4.4](#44-a-topbar-da-coordenação)).

---

## Fontes

- [Edital Vestibular ITA 2026 (retificado)](https://www.vestibular.ita.br/instrucoes/edital_2026_retificado.pdf)
- [Edital CFG Ativa 2026/2027 — IME](https://inscricoes.ime.eb.br/documentos/Edital_CFG_ATIVA_2026_2027.pdf)
- [CA/CFG — Instituto Militar de Engenharia](https://vestibular.ime.eb.br/cfg/)

---

## 10 · O que falta (22/08/2026)

Nada de código nas quatro partes. O que sobrou é operacional ou depende de
decisão fora do time:

| | O quê | Quem |
|---|---|---|
| 1 | **Criar a Developer Key** no Canvas ([§0.3](#03-criar-a-developer-key-do-canvas)) e pôr `CANVAS_CLIENT_ID` / `CANVAS_CLIENT_SECRET` no `.env`. Sem ela o botão "Entrar com o Canvas" não aparece | Yan, 5 min |
| 2 | **Testar o SSO com um aluno real** — é a única parte não verificada ponta a ponta | Yan |
| 3 | **Preencher `canvas_user_id` do Leo** na conta de coordenação (painel de administrador) para ele entrar pelo Canvas | Yan |
| 4 | **Verificar escrita no Canvas real** — nota com "enviar agora", simulado, ciclo. Todo teste do sprint usou mock ou "só no site"; o Canvas do colégio não foi tocado | Yan, deliberado |
| 5 | **Deploy**: `./infra/vps/deploy.sh --migrar` (0020→0026) | Yan |
| 6 | **Confirmar com o Leo** os ~50 alunos do [§7](#7--riscos), olhando a lista real | Leo |

### Fora do sprint, anotado durante a implementação

- **`ShellAluno` redireciona o logout para `/login.html`** — resquício da
  migração React; a rota é `/login`. Não mexi porque está fora do escopo e
  o aluno hoje não entra (1 senha em 876).
- **Regra de corte na Fase 1 via `classificacao_aluno.zona`** —
  `thresholds.py` e `_classificar_zona_por_materia` continuam existindo
  para o stats engine (alertas, perfil). O painel não os usa mais; o
  campo `zona` da lista de alunos ainda sim. Unificar é a A5 da Onda 3.
- **Envio em lote ao Canvas** (C5) — cada objeto tem seu botão; "enviar N
  pendências do ciclo" fica para depois.
- **Container `web` do compose estava em nginx antigo** (imagem de 18/08)
  e o Docker desta máquina não consegue puxar `node:22-alpine`
  (credential helper quebrado — mesmo sintoma do symlink do CLAUDE.md).
  O front foi verificado com o Vite rodando no host, na :8080.

