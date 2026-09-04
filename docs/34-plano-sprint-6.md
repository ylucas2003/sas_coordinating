# 34 — Sprint 6 · O assunto entra no simulado

> **Origem:** [24-jornada-do-aluno.md §3 e §4](24-jornada-do-aluno.md), do
> brainstorming de 29/08/2026, e a proposta do
> [19-roadmap.md §3 · Sprint 6](19-roadmap.md).
>
> **Escopo:** o SAS passa a saber **em que assunto** o aluno erra, não só
> quanto ele tirou. É o pré-requisito duro da jornada do aluno (Sprint 7): sem
> assunto não há "o que eu mais erro", não há prioridade de estudo, e o Tio Léo
> não tem o que dizer além do que já diz.
>
> **Pronto quando:** um aluno abre a própria ficha e lê *"você acerta 41% em
> Termodinâmica, que vale 6,8% da prova — estude isto primeiro"*, com a
> matéria coberta declarada na tela; e a coordenação vê a mesma leitura por
> turma.

---

## 0 · O levantamento — o que o código e o banco dizem antes de escrever

Mesma regra das Sprints 4 e 5 e do polimento: **ler o código e medir o banco
antes de planejar** ([31 §0](31-plano-sprint-5.md), [32 §0](32-plano-sprint-4.md),
[33 §0](33-plano-polimento-coordenacao.md)). Rendeu sete achados, e **três
mudam o desenho da proposta**.

### 0.1 · O alvo é 1.030 questões, não 1.624 — e o docs/24 já dizia isso

Medido em produção, 04/09/2026:

| Matéria | Questões | Respostas gravadas | Taxonomia cobre? |
|---|---:|---:|---|
| Matemática | 360 | 84.894 | ✅ |
| Física | 360 | 84.480 | ✅ |
| Química | 310 | 76.868 | ✅ |
| Inglês | 300 | 71.116 | ❌ |
| Português | 294 | 57.115 | ❌ |
| **Total** | **1.624** | **374.473** | |
| **Coberto** | **1.030** | **246.242** | |

O `1.031 questões / 237.081 respostas` do [24 §3.1](24-jornada-do-aluno.md)
**já era o subconjunto coberto**, não o total — cresceu pouco em uma semana. A
alavanca segue de pé e é a maior do projeto: classificar 1.030 itens faz
246 mil respostas **já gravadas** passarem a dizer em que assunto o aluno erra,
sem coletar nada novo.

⚠️ Ao citar o tamanho, citar os dois números. "1.624 questões" superestima o
trabalho; "1.030" sozinho esconde que um terço do simulado fica de fora.

### 0.2 · O buraco de cobertura, medido pela primeira vez

O [24 §3.3](24-jornada-do-aluno.md) registra o buraco como *"o buraco de
cobertura que ninguém mediu ainda"*. Agora está medido: **594 questões (36,6%)
e 128.231 respostas (34,2%)** ficam fora da análise por assunto, por não haver
taxonomia de Inglês e Português.

E o Inglês da Fase 1 do ITA é **o único eliminatório**, com corte 5,0.

Isso não muda a decisão de 29/08 — cobrir só as três matérias —, mas dá o
número que a tela é obrigada a mostrar. Um terço não é rodapé.

### 0.3 · A P3 está metade pronta, e ninguém registrou

O índice de importância tem quatro passos no [24 §4.2](24-jornada-do-aluno.md).
Dois já existem, escritos para o banco de questões:

| Passo | O quê | Estado |
|---|---|---|
| 1 · normalizar por ano | `p(t,a) = ocorrências ÷ questões do ano` | ✅ **pronto**: `banco/estatisticas.py::recorrencia` devolve `porAno` (numerador) e `questoesPorAno` (denominador) |
| 2 · peso por recência | `w(a) = 0,5^((ref−a)/H)` | ⏳ não existe |
| 3 · o índice | `I(t) = Σ w·p ÷ Σ w` | ⏳ não existe |
| 4 · tendência separada | `T(t)` = média recente − média anterior | ✅ **pronto**: `dominio/serieDoAssunto.ts::tendenciaDaSerie`, janela de 5 anos, com teste |

A P3 não é construir um pipeline: é **acrescentar dois passos de aritmética**
sobre um endpoint que já devolve tudo de que eles precisam. Isso a torna P e
não M, e reforça o que o roadmap já dizia — ela **começa no dia um**, sem
esperar a classificação.

⚠️ E cria uma obrigação: `tendenciaDaSerie` já usa janela de 5 anos no front.
A meia-vida de 5 anos do índice **é outro parâmetro** com o mesmo valor. Ou os
dois passam a ler o mesmo lugar, ou daqui a um ano alguém muda um e não o
outro — o padrão que a Sprint 2 combateu na régua de corte.

### 0.4 · Os vocabulários de matéria batem — não há tradutor a escrever

`topico_taxonomia.materia` e `materia.nome` usam **as mesmas strings**:
`Física`, `Matemática`, `Química`. A FK composta
`(materia, topico_codigo) → topico_taxonomia` liga direto, sem tabela de
mapeamento e sem normalização. São 65 tópicos (18 Fís + 21 Mat + 26 Quím).

Uma preocupação a menos, e vale registrar porque o oposto seria caro.

### 0.5 · 11% das questões não têm enunciado em texto — ele está na imagem

Este é **o achado que muda a P2**. Medido nas três matérias cobertas:

| Matéria | Questões | Com `<img>` | **Só imagem** |
|---|---:|---:|---:|
| Física | 360 | 295 (82%) | 39 |
| Matemática | 360 | 264 (73%) | 42 |
| Química | 310 | 200 (65%) | 34 |
| **Total** | **1.030** | **759 (74%)** | **115 (11%)** |

"Só imagem" = menos de 40 caracteres de texto útil depois de remover as tags.
O enunciado inteiro é um PNG:

```html
<p style="text-align: center;"><img src="/courses/577/files/103064/preview"></p>
```

A proposta diz *"aponte o `classificar.py` para o HTML do Quiz Statistics"*.
Para 915 questões isso basta. Para **115 não há o que ler**, e para boa parte
das outras 644 com imagem o texto é parcial — a figura carrega o circuito, o
gráfico ou a geometria.

Some-se que a URL é **relativa do Canvas** e exige token para buscar. A
infraestrutura existe (`ClienteCanvas.baixar_bytes`,
`scripts/canvas_backfill_arquivos.py`), mas é trabalho que a proposta não
previa.

→ **Decisão D1**, em [§5](#5--o-que-preciso-que-você-decida).

### 0.6 · O `classificar.py` não é automático

O [24 §3.4](24-jornada-do-aluno.md) diz que *"o pipeline do banco já faz
exatamente isto"*. Faz — mas o fluxo é `listar → um humano (ou agente) lê →
patch JSON → aplicar`. Não há classificador rodando sozinho.

Para 1.030 questões isso é lote de leitura, não de execução. O tamanho **G** da
proposta está certo; o que estava implícito é que o custo é de tokens e
revisão, não de CPU. A regra do banco continua valendo: no máximo 3 blocos
distintos por questão, mínimo 1 tópico.

### 0.7 · A P4 não tem nada, e a P1 remove uma coluna morta

Nenhum módulo de `stats/` lê tópico. A P4 é escrita do zero.

E `questao.assunto` (migration 0015, comentada como *"gancho sem classificador
ainda"*) tem **0 linhas preenchidas** em produção. Nada lê, nada escreve — a
dívida sai sem migração de dados.

---

## 1 · P1 · `questao_topico` — a ligação N:N

**Tamanho: P** (era M; o levantamento tirou o tradutor de matéria e a migração
de dados).

Espelha `questao_vestibular_topico`, que já está em produção e funciona:

```sql
CREATE TABLE questao_topico (
    questao_id    uuid NOT NULL REFERENCES questao(id) ON DELETE CASCADE,
    materia       text NOT NULL,
    topico_codigo text NOT NULL,
    confianca     text CHECK (confianca IN ('alta','media','baixa')),
    observacao    text,
    PRIMARY KEY (questao_id, materia, topico_codigo),
    FOREIGN KEY (materia, topico_codigo)
        REFERENCES topico_taxonomia(materia, codigo)
);
```

**Por que não a coluna `assunto` da 0015** — três razões, e a primeira sozinha
decide:

| | |
|---|---|
| Questão mista é a regra, não exceção | uma coluna `text` guarda um assunto só. No banco de vestibular a soma dos tópicos **passa** do total, de propósito ([22 §1.5](22-plano-banco-questoes.md)) |
| A FK composta é obrigatória | `1.1` existe nas três matérias e significa coisa diferente em cada uma (migration 0028) |
| Duas estruturas para a mesma ideia são duas formas de errar | é o argumento que a própria 0028 usa |

A `0015.assunto` sai na mesma migration. Com 0 linhas preenchidas, é `DROP
COLUMN` e o `.down.sql` a recria vazia.

⚠️ Depois da migration, `docker compose restart postgrest` — armadilha 1.

---

## 2 · P2 · Classificar as 1.030

**Tamanho: G.** É o grosso do sprint.

Entrada: `questao.texto` (HTML do Quiz Statistics, com LaTeX e imagem
embutidos), agrupado por simulado. Saída: patch JSON no formato que o
`classificar.py` já aplica.

**Ordem de ataque, e ela não é arbitrária:** por **respostas afetadas**, não
por matéria. Uma questão de um simulado aplicado a 300 alunos destrava 300
respostas; uma de um simulado de 40, destrava 40. Classificar em ordem
decrescente de impacto significa que **a P4 pode ligar antes da P2 terminar**,
com cobertura declarada na tela.

**As 115 sem texto** → D1.

**O portão de qualidade:** amostra de 30 questões classificadas duas vezes, de
forma independente, medindo concordância no bloco (não no tópico). Abaixo de
~80% de concordância no bloco, o problema é a instrução, não o classificador —
e vale consertar antes das outras 1.000.

---

## 3 · P3 · Índice de importância

**Tamanho: P** (era M — ver [§0.3](#03--a-p3-está-metade-pronta-e-ninguém-registrou)).

Falta o passo 2 e o passo 3:

```
w(a) = 0,5 ^ ((ano_referência − a) / H)          H = 5 anos
I(t) = Σ_a w(a)·p(t,a) ÷ Σ_a w(a)
```

`I(t)` continua na unidade de `p` — *"esse tópico vale ~4% da prova, hoje"* —
e é isso que vai à tela. O ranking 0–100 pode acompanhar, mas como **segunda
linha**: percentual da prova é informação, índice normalizado é só ordenação.

**Meia-vida e não janela**, e o motivo está no [24 §4.2](24-jornada-do-aluno.md):
a janela cria degrau — quando 2019 sai dela o número pula sem que nada tenha
acontecido no mundo. A exponencial decai liso e nenhum ano some.

**A tendência fica separada do índice**, já pronta. Na tela, os dois visíveis:
*"caía em 6% das questões até 2015 · cai em 2% desde 2020 ▼"*. O índice diz
quanto estudar; a tendência diz por quê.

Onde `H` mora → **D2**. Onde o cálculo roda → **D3**.

⚠️ **O recorte é do índice inteiro, não só do numerador.** É a mesma armadilha
que a `recorrencia` já documenta: filtrar só o de cima faz "% da prova" de uma
questão de 2ª fase ser dividido pela prova inteira, e o número sai menor que a
verdade **sem nenhum erro na tela**. `vestibular` e `fase` estreitam a resposta
toda, e o índice herda isso de graça por ser calculado sobre ela.

---

## 4 · P4 · Acerto por assunto

**Tamanho: M.** Escrita do zero.

```
acerto(aluno, t) = respostas certas do aluno em questões de t ÷ respostas do aluno em t
prioridade(aluno, t) = I(t) × (1 − acerto(aluno, t))
```

Cai muito **e** eu erro muito.

**Três travas, e nenhuma é opcional:**

1. **Piso de amostra.** Com menos de ~5 questões do aluno no tópico, `acerto`
   é puxado para a média da turma. Sem isso um único erro vira 0% e o tópico
   salta para o topo — a lista passa a ordenar ruído.
2. **A tela declara o que cobre.** Onde houver leitura por assunto, tem que
   estar escrito quais matérias ela abrange, e que Inglês e Português ficam de
   fora — os **594 itens** da [§0.2](#02--o-buraco-de-cobertura-medido-pela-primeira-vez).
   Mesma regra que a 0028 já aplica às questões sem classificação: *"o aluno
   estudaria um recorte incompleto sem saber que é incompleto"*. Um plano de
   revisão que ignora o Inglês eliminatório em silêncio é **pior que nenhum
   plano**, porque o aluno conclui que está coberto.
3. **Respeitar `nota.computavel`.** Migration 0043, em produção desde 03/09: se
   a nota não entra na estatística porque o aluno não marcou nada, as respostas
   em branco dela não podem entrar no acerto por assunto. Senão a mesma prova
   sai de uma conta e entra na outra, e duas telas mostram números diferentes
   do mesmo aluno.

**A leitura é em duas dimensões, não lista.** Importância × meu acerto, quatro
quadrantes — é o mesmo gráfico em camadas da Sprint 5 · P5: o leigo lê o
quadrante, o interessado lê os eixos, o curioso lê os números.

---

## 5 · O que preciso que você decida

O roadmap dizia **"pré-voo: nenhum"**. Depois do levantamento, são três — e
nenhuma delas estava visível antes de medir o banco.

### D1 · As 115 questões cujo enunciado é só imagem

Onze por cento do alvo, e mais 644 com texto parcial ([§0.5](#05--11-das-questões-não-têm-enunciado-em-texto--ele-está-na-imagem)).

| Opção | O que custa | O que entrega |
|---|---|---|
| **a · Visão** — buscar o PNG no Canvas e classificar com modelo multimodal | tokens de visão + o download autenticado | cobertura ~100% |
| **b · Deixar fora**, declarado na tela como `semClassificacao` | nada | ~89%, com o buraco visível |
| **c · Passada humana** nas 115 | tempo de alguém que entenda do edital | ~100%, e a mais confiável |

**Recomendo (a)**, com (b) como rede: o projeto já tem precedente de leitura
por visão — o piloto ITA 1973, `extraido_por = 'visao'` ([23](23-banco-questoes-historico.md)) — e o
resíduo que a visão não resolver cai em (b), que é a regra da casa de qualquer
jeito. Mas o custo é seu para aprovar.

### D2 · Onde mora a meia-vida `H`

O [24 §4.2](24-jornada-do-aluno.md) diz duas coisas que **não cabem juntas**:
*"parâmetro, não constante espalhada… mora num lugar só"* e *"mudá-lo é decisão
de coordenação, não deploy"*.

| Opção | Consequência |
|---|---|
| **a · `thresholds.py`** — é calibração, e é onde calibração mora ([api/CLAUDE.md](../api/CLAUDE.md)) | mudar exige deploy |
| **b · Linha no banco**, como a régua de corte virou dado na Sprint 2 | a coordenação muda sozinha; custa uma migration e uma tela |

**Recomendo (a) agora, (b) quando alguém pedir.** O número foi decidido em
29/08 e não há sinal de que vá mudar; construir a tela de edição antes do
primeiro pedido é adiantar trabalho que pode não ser preciso. Mas se a
intenção é que o Leo mexa nisso, (b) desde já evita retrabalho.

⚠️ Em qualquer das duas, `H` e o `ANOS_DA_JANELA = 5` do front passam a ler o
mesmo lugar — ver [§0.3](#03--a-p3-está-metade-pronta-e-ninguém-registrou).

### D3 · O índice é calculado no servidor ou no front?

Hoje a série e a tendência são **front**, funções puras em
`dominio/serieDoAssunto.ts`. O índice poderia seguir ali.

| Opção | Consequência |
|---|---|
| **a · Front**, junto da série | zero ida ao servidor; mas o ranking de 65 tópicos vira trabalho do celular do aluno, e `H` precisa viajar no payload |
| **b · Servidor**, em `banco/estatisticas.py` | um número só para todo mundo, `H` fica de um lado só; mas duplica a lógica de série que já existe no front |

**Recomendo (b)** — a garantia que o [24 §4.2](24-jornada-do-aluno.md) compra
com a meia-vida fixa é *"todo mundo vê o mesmo número"*, e ela é mais fácil de
sustentar com um cálculo só. O front continua desenhando a série; o índice
chega pronto.

### O que vou decidir sozinho, se você não disser o contrário

- Ordem de classificação da P2 por **respostas afetadas**, não por matéria.
- O acerto por assunto **respeita `nota.computavel`**.
- O piso de amostra da P4 começa em **5 questões**, ajustável depois do
  backtest.
- `questao.assunto` sai na mesma migration da P1.

---

## 6 · Ordem e dependências

```
dia 1   P3 ─────────────────────────►  (não depende de nada; 2 passos de aritmética)
dia 1   P1 ──┐
             ├─► P2 (lote, por impacto) ──┐
             │                            ├─► P4
             └────────────────────────────┘
```

- **P3 anda sozinha** e entrega valor antes de qualquer classificação: "o que
  mais cai no ITA/IME" já é resposta útil para a coordenação, sobre as 2.773
  questões de vestibular que **já estão classificadas**.
- **P4 pode ligar antes de a P2 terminar**, se a P2 for por impacto — com a
  cobertura declarada na tela, como manda a trava 2.

## 7 · Portões

- Migration com par `.down.sql`; `up`/`down`/`up` limpos antes do PR.
- `docker compose restart postgrest` depois da P1 — armadilha 1.
- A concordância da amostra de 30 ([§2](#2--p2--classificar-as-1030)) medida e
  registrada **antes** das outras 1.000.
- Nenhuma tela de assunto sem a frase de cobertura. É trava, não polimento.
- Verificação a 360px nos dois cascos e nos dois temas.
