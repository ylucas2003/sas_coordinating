# 37 — Refatoração visual da coordenação · plano e execução

> **Origem:** [brief-claude-design-coordenacao.md](brief-claude-design-coordenacao.md),
> que é a régua deste trabalho, e o canvas do Claude Design
> (projeto `a8bf25f7`, arquivos `Coordenação.dc.html` e `Kit de peças.dc.html`).
>
> **O que este trabalho é:** estender à coordenação o sistema de design que só
> a área do aluno tinha, e estender o **padrão de campo** às telas que
> empilhavam perguntas diferentes numa rolagem só.
>
> **O que ele não é:** uma reescrita. A coordenação está em produção, com
> usuários reais e dados de menores de idade. Fora da lista do §1, nada de
> comportamento mudou.
>
> O documento de estado é [19-roadmap.md](19-roadmap.md). Este aqui diz *como*,
> e *o que ficou de fora*.

---

## 0 · O levantamento — o que o código disse e os documentos não

Cinco achados, e **quatro deles mudaram o plano antes da primeira linha de
código.**

### 0.1 · Os dois lints estavam vermelhos na `main`

96 erros de ruff e 8 do Biome, pré-existentes. O cruzamento com os arquivos do
sprint em aberto dava intersecção **vazia**, e as versões batiam com os pins
(`ruff==0.16.4`, biome `2.5.10`) — não era deriva de versão nem culpa do
trabalho em curso.

Sem isso, "cada PR verde nos portões" não teria régua nenhuma. Virou o PR 0.

A raiz de 3 dos 4 erros de hook era supressão morta: os comentários eram
`eslint-disable`, que o Biome não lê desde a troca de linter.

### 0.2 · O canvas cobre o KIT, não as telas

O canvas entregou o **Kit de peças** — completo e excelente: os seis papéis, o
selo nos sete estados com o algoritmo de R1/R3 escrito, a régua com o traço
divergente, heatmap, os quatro gráficos, a tabela ordenada pelo pior, a barra
de filtros nos três estados, a tarja de procedência nos seis, o card de campo
nos três estados do subtítulo e o card de entrada.

**As oito telas não foram desenhadas.** Painel, Alunos, Ficha do aluno, Ficha
de ciclo, Administração e Login não têm autoridade visual no canvas. Elas
foram derivadas do Kit e das regras C1–C5, com a skill `frontend-design` —
decisão tomada explicitamente, e registrada aqui para o próximo a mexer saber
que a fonte é diferente da do Kit.

Duas divergências canvas × brief, resolvidas conforme a regra do prompt:

| Divergência | Quem venceu | Por quê |
|---|---|---|
| O canvas define tema só por `[data-tema]`; o brief pede três blocos | **brief** | é comportamento, não cor nem medida |
| O canvas chama os aliases de `aluno.css`/`coordenacao.css` | **repositório** | nome de arquivo não é decisão visual; `tokens.css` e `aluno-tokens.css` já existiam |

E uma micro-divergência preservada: o canvas dá `--grade` em 5% de opacidade e
o aluno usa 4,5%. Ficou 4,5% para o PR 1 não mudar um pixel da área do aluno.

### 0.3 · O PR 1 não podia ser "zero pixels" como estava descrito

Duas razões, e a segunda é a séria.

**As superfícies estão INVERTIDAS entre os dois sistemas.** Só 4 de 15 pares
candidatos coincidiam:

```
--color-bg       #eef1f7   ≠   --dia-fundo       #ffffff
--color-surface  #ffffff   ≠   --dia-superficie  #f4f7fc
--color-border   #eef1f7   ≠   --dia-borda       #dce6f7
```

A coordenação era fundo cinza com card branco; o sistema é o contrário.
Apontar os aliases para os papéis mudaria a tela inteira.

**E `data-tema` já estava estampado na raiz em todo boot.**
[`pecas/tema.ts`](../web/src/servicos/tema.ts) o aplica no escopo do módulo, e
`App.tsx` importa `CascoAluno` estaticamente. Hoje é inofensivo porque a
coordenação lia `--color-*`. No instante em que `--color-*` respondesse a
`[data-tema]`, **todo coordenador com `sas_tema_aluno=noite` no localStorage
veria a coordenação escura já no PR 1** — não no PR 7. O próprio comentário do
arquivo dizia que isso "nunca foi problema" pela razão que o PR 1 removia.

> Consequência: `tokens.css` passou a ter uma regra explícita — `--color-*`
> aponta para a paleta do DIA, nunca para os papéis — e ela ficou travada por
> teste até o PR do tema escuro, quando o teste inverteu de propósito.

### 0.4 · O PR 2 apontava para o lugar errado

O plano dizia que os três geradores leem os tokens em tempo de execução.
**Existe UMA chamada de `getPropertyValue` em todo `src/exportacao/`**, com
fallback cravado; o resto eram literais.

O vazamento real é por **cascata**: `exportar-aluno.js` insere o nó NO
documento atual e marca `body.imprimindo-panorama`; o `.panorama` é estilizado
por `layout.css`, com 31 usos de `var(--color-*)` em 13 tokens distintos. O
mesmo vale para o PDF da ficha, que imprime a página viva.

> Consequência: o conserto não foi apontar regra por regra, foi um bloco
> `@media print` que remapeia a paleta inteira. Qualquer tela que ganhe
> impressão depois já nasce protegida.

Achado de brinde: o PNG do panorama tinha uma **terceira** cópia da paleta
cravada no `.js`, divergente da tela e do papel em oito dos onze valores; o
gráfico rasterizado tinha uma **quarta**.

### 0.5 · Cinco tokens fantasma, usados e nunca definidos

`--color-verde`, `--color-vermelho`, `--color-ambar`, `--color-surface-2` e
`--color-surface-hover` apareciam em seis lugares e **não existiam em parte
alguma** — funcionavam só pelo valor alternativo do `var()`. Saíram.

---

## 1 · O que mudou DE PROPÓSITO

Fora desta lista, mesma URL, mesmo dado, mesma permissão, mesmo texto, mesmo
atalho, mesmo comportamento de filtro.

1. O semáforo verde/âmbar/vermelho saiu da tela inteira (R1–R7).
2. `toneMedia` desapareceu — e com ela `tonePctCritico` e o ternário inline do
   KPI "Cortados", que faziam a mesma coisa e não estavam no plano.
3. Toda tabela de aluno abre por **distância do corte**, ascendente, com o
   ordenador nomeado no cabeçalho.
4. Administração deixou de ser quatro abas e virou quatro campos.
5. Ficha de ciclo deixou de ser uma rolagem e virou três campos.
6. O Painel ganhou a faixa de entrada e perdeu dois estratos, por fusão.
7. Passou a existir tema escuro.
8. As fichas ganharam coluna lateral de 320px; Painel, Alunos e Banco não.

**Duas URLs mudaram, e as antigas continuam válidas:**

| Antes | Agora | O que acontece com o link antigo |
|---|---|---|
| `/administracao` = Contas | `/administracao` = hub; `/administracao/contas` = Contas | cai no hub, a um clique |
| `/ciclos/:id` = tudo | `/ciclos/:id` = entrada; `+/calibracao`, `/regua`, `/comparacao` | continua sendo a entrada |

---

## 2 · A ordem, e por que ela é essa

```
PR 0  zerar o lint          ← sem isso nenhum PR seguinte tem portão
PR 1  a pilha de tokens     ← fundação; errar aqui custa reescrever sete PRs
PR 2  a paleta de documento ← ANTES do tema escuro, nunca depois
PR 3  superfície e forma
PR 4  magnitude e olho
PR 5  o fim do semáforo
PR 6  a ordenação por distância (R6)
PR 7  o tema escuro         ← só depois de 2 e 5, senão é retrabalho
PR 8  as telas que mudam de estrutura (a→e)
PR 9  limpeza e documentos
```

---

## 3 · PR a PR

### PR 0 · Zerar o lint

**O que muda:** 96 erros de ruff (73 no `--fix`, 23 à mão) e 8 do Biome.
Nenhum arquivo de estilo tocado.

**Arquivos:** 49, quase todos em `api/`.

**Pronto quando:** os cinco portões verdes, literalmente. ✅

Três consertos mereceram nota: `arquivos.py` encadeia com `from None` porque o
403 do link de download é genérico de propósito; `sincronizar.py` manteve o
`continue` com noqa porque envolver o corpo em `contextlib.suppress` passaria a
engolir também o erro do `update`; e `pipeline.py` tinha três imports depois de
uma função — deriva, não circularidade.

### PR 1 · A pilha de tokens

**O que muda:** `paleta.css` (hexadecimais, uma vez cada) e `papeis.css` (os
seis papéis, os três blocos de tema). `tokens.css` e `aluno-tokens.css` viram
alias e param de decidir cor.

**Arquivos:** `styles/paleta.css`, `styles/papeis.css`, `styles/tokens.css`,
`styles/aluno-tokens.css`, `src/main.tsx`.

**Pronto quando:** nenhum valor resolvido muda. ✅ — 97 tokens resolvidos pela
cadeia nova e comparados com o valor antigo, nos dois temas, todos idênticos.

### PR 2 · A paleta de documento

**O que muda:** `documento.css` com `--doc-*`, clara e fixa, mais o bloco
`@media print` que remapeia `--color-*` e `--sas-*` na hora de imprimir.

**Arquivos:** `styles/documento.css`, `src/main.tsx`,
`src/exportacao/exportar-aluno.js`.

**Pronto quando:** o dossiê sai idêntico. ⚠️ **Não verificado** — ver §6.

Os valores divergentes do caminho PNG foram **preservados** como `--doc-png-*`
em vez de unificados: o portão era sair idêntico, e unificar exige gerar o PNG
e olhar.

### PR 3 · Superfície e forma

**O que muda:** as superfícies invertem; `--shadow-card` e `--shadow-float`
morrem (14 usos em 8 arquivos, oito dos quais **já tinham borda** e somavam fio
+ sombra + fundo); quatro raios viram três; entra a grade de 24px; entra a
tecla de 3px no botão primário.

**Pronto quando:** nenhuma sombra sobra. ✅ (aparência não verificada, §6)

> **Um erro cometido aqui, e o guarda que ele gerou.** Ao aposentar sete
> entradas de `--coord-*`, um `*/` foi junto e comentou o bloco seguinte. Sete
> tokens sumiram e `npm run build` **passou** — `var()` indefinido não é erro
> de build: a propriedade é descartada em silêncio e a cor some sem nada no
> console. Daí `dominio/tokensCss.test.ts`, que segue a cadeia paleta → papéis
> → alias e falha se algum alias não chegar a um literal.

### PR 4 · Magnitude e olho

**O que muda:** o numeral de KPI vai de 34px/700 (o mesmo peso do título ao
lado) para 40px/800 com tracking −0.035em, na cor MAGNITUDE. O rótulo vira o
olho de 10px em caixa alta espaçada.

Nenhum asset novo, e nenhum poderia entrar: a Plus Jakarta Sans já é variável
na faixa 200–800 e já é servida localmente.

### PR 5 · O fim do semáforo

**O que muda:** R1, R3, R4, R5 e R7. `dominio/selo.ts` traduz nota + corte em
preenchido/vazado com intensidade contínua; a barra de severidade do cartão de
alerta some; as tags viram contorno; a comparação vira cinza; os KPIs ficam
neutros.

**Pronto quando:** nenhum verde de semáforo sobra na coordenação. ✅

⚠️ O backend **não foi tocado**. `Severidade` e `TomNota` continuam
`'verde' | 'ambar' | 'vermelho'`, calculados a partir do corte da régua em
vigor — o que mudou é o que o front desenha com eles.

⚠️ A régua **não foi reimplementada**. `selo.ts` recebe o corte que
`corteDaMateria` lê do que o servidor resolveu.

A legenda da ajuda do Painel foi reescrita para explicar a FORMA. Legenda
desatualizada é pior que nenhuma: ensina a ler errado.

### PR 6 · A ordenação por distância (R6)

**O que muda:** o Painel ganha `distancia` como ordenação **padrão**, o
ordenador aparece nomeado numa faixa acima da tabela, e entra a coluna
"Distância". A tela de Alunos abre por zona (risco → topo), que é o que
responde à mesma pergunta com o dado que ela tem.

A distância é medida contra o corte **de cada matéria**. Um escalar único
mentiria sobre a matéria que mais elimina — o Inglês da F1 do ITA, com 5,0.

⚠️ Nulo afunda nos dois sentidos: aluno sem nota não foi mal, não foi medido.

**Testes:** 22 em `dominio/selo.test.ts`.

### PR 7 · O tema escuro

**O que muda:** `--color-*` passa a apontar para `--sas-*`; entra o seletor na
topbar; `pecas/tema.ts` vira `servicos/tema.ts` com chave `sas_tema` (lendo
`sas_tema_aluno` uma vez, para ninguém perder a escolha).

Cor cravada varrida: 12 `color: #fff` que eram texto sobre a ação (na noite a
ação é ouro, e branco sobre ouro reprova em AA), 14 tintas de navy que sumiriam
no fundo escuro, e a coluna congelada do Painel, que tinha `#ecf0fa` cravado.

Nos gráficos: o **heatmap** tinha um degradê vermelho → âmbar → verde — o
último semáforo do app, e escala divergente onde ela tem de ser sequencial de
matiz único ancorada no corte. A paleta de séries tinha seis cores, duas delas
verde e vermelho.

**Pronto quando:** as superfícies abrem nos dois temas sem contraste reprovado
e sem cor cravada fora de `paleta.css`. ⚠️ **Contraste não verificado** — §6.

### PR 8 · As telas que mudam de estrutura

**a) Administração** — quatro abas viram quatro campos, divididos por pergunta.
Entram as três peças compartilhadas em `componentes/ui/Campo.tsx`. `AbasAdmin`
foi apagada. ✅

**b) Ficha de ciclo** — três campos. O toggle "avançado" morre porque a tela é
dele.

> ⚠️ **O dossiê custou uma solução.** Ele colhe os `<svg>` já desenhados da
> árvore, e a entrada deixou de desenhá-los. Redesenhá-los num segundo lugar
> manteria dois desenhos do mesmo gráfico, que divergem no primeiro ajuste —
> então a fonte é montada **fora da tela**, com as mesmas peças, só enquanto o
> dossiê é gerado. `left: -10000px` e não `display: none`: sem layout os
> `<svg>` saem com dimensão zero.

**c) Painel** — a faixa de entrada entra (e rola para fora, não é sticky), e os
quatro estratos viram dois. Régua, fase e ordenação viram grupos da barra de
filtros, cada um com `resumo`.

**d) Ficha do aluno** — coluna lateral de 320px, e a `BarraCorte` do aluno
reusada literalmente.

> ⚠️ O heatmap traz matéria por NOME e a régua guarda o corte por CÓDIGO. Sem
> o mapa nome→código, o Inglês eliminatório seria lido contra 4,0.

**e) Login** — os quatro arcos concêntricos viram a treliça de cobogó do login
do aluno, noutro ângulo. E a porta errada passa a dizer para onde ir.

### PR 9 · Limpeza

`--coord-*` inteiro (22 entradas) saiu sem leitor. CSS órfão do toggle do
avançado e dos arcos do login. O estado das integrações perdeu o verde de
sucesso — só a falha tem cor (R4).

---

## 4 · Riscos

| Risco | Estado |
|---|---|
| A coordenação escurecer sem seletor, por `data-tema` global | fechado no PR 1 pela regra do alias, travado por teste, e aberto de propósito no PR 7 |
| O dossiê sair preto à noite | fechado no PR 2 pelo `@media print` |
| O dossiê de ciclo sair sem gráficos depois da divisão em campos | fechado na 8b pela fonte fora da tela |
| `var()` indefinido sumir em silêncio | fechado pelo `tokensCss.test.ts` |
| Contraste reprovado no tema escuro | **ABERTO** — não verificado, §6 |
| Layout quebrado em 390px nas telas novas | **ABERTO** — não verificado, §6 |

---

## 5 · Decisões

1. **`--color-*` aponta para a paleta do dia até o PR 7.** Papel responde a
   tema; alias não podia responder antes de existir seletor.
2. **Os quatro nomes de raio ficam, colapsados sobre três valores.** Renomear
   os 99 usos no mesmo commit em que a forma muda tiraria a chance de ver o que
   a forma fez.
3. **O semáforo sobrevive em `documento.css`, e só lá.** A substituição precisa
   ser redesenhada para papel antes de trocar, e o portão do PR 2 era o dossiê
   sair idêntico. Dívida conhecida — e o brief usa a impressão como um dos
   argumentos *contra* o semáforo.
4. **Hooks levam prefixo `use`, não `usar`.** É contrato do React, não
   preferência de idioma.
5. **O Painel não virou hub de campos.** Lá um campo domina esmagadoramente —
   a varredura —, e virar hub cobraria um clique a mais na tarefa mais
   frequente do dia, todo dia.
6. **A comparação de ciclo é entrega parcial, e a tela diz isso.** Ver §7.

---

## 6 · Verificação — o que foi provado e o que não foi

**Provado:**

- os cinco portões verdes em todos os dez PRs
  (`npm test`, `lint`, `typecheck`; `pytest`, `ruff`);
- 369 testes no front (+28 novos: 22 em `selo.test.ts`, 6 em `tokensCss.test.ts`)
  e 503 na API;
- **o PR 1 não muda um valor resolvido** — 97 tokens comparados nos dois temas;
- a cadeia paleta → papéis → alias não tem elo quebrado nem ciclo, por teste;
- nenhum `--color-*` aponta para a paleta crua, e o bloco de impressão não
  vaza papel — por teste;
- `npm run build` verde em todos os PRs.

**⚠️ NÃO verificado, e é a lacuna deste trabalho:**

**Nada foi visto rodando no browser.** A verificação exigia login de
coordenação; a senha oferecida (`leonardobruno@aridesa.com.br`) é a de
produção e o banco local a recusa, e a partir daí o classificador de
permissões desta sessão passou a recusar interação com a tela de login. Sem
sessão, o app redireciona para `/login` e nenhuma tela da coordenação abre.

Em consequência, **não foram verificados**:

- contraste WCAG AA no tema escuro, nas catorze superfícies;
- layout em 390×844 nas telas que mudaram de estrutura;
- o dossiê de aluno e o panorama de ciclo antes/depois do PR 2;
- o PNG do panorama (por isso os `--doc-png-*` foram preservados em vez de
  unificados);
- console e rede — erro de console e requisição repetida denunciam hook mal
  escrito, e o sprint mobile achou três defeitos que só existem em runtime;
- a skill `web-design-guidelines` contra as telas novas.

**O que fazer antes de deployar:** subir `docker compose up`, entrar com uma
conta de coordenação do banco local, e percorrer as catorze superfícies nos
dois temas e nos dois tamanhos. As três telas com maior risco são o Painel
(fusão da barra de filtros, que **mede a si mesma** para colapsar), a ficha do
aluno (grid de duas colunas) e a ficha de ciclo (a fonte do dossiê fora da
tela).

---

## 7 · O que ficou pela metade, e por quê

### 7.1 · Comparação de ciclo — sede × sede e turma × turma

O brief pede três comparações. Só "este ciclo contra o anterior" tem dado:
`evolucaoTemporal` traz `cicloAnteriorMedia` por prova.

As outras duas exigem recorte que `GET /ciclos/{id}/estatisticas` não devolve.
Somar notas por sede no front seria refazer estatística no cliente — o mesmo
erro que a régua de corte ensinou a não cometer. **A tela diz o que falta**, em
vez de fingir que a pergunta foi respondida.

> Para fechar: um recorte por sede e por turma no endpoint de estatísticas do
> ciclo.

### 7.2 · A tarja de procedência unificada

O brief pede **um** componente com seis estados (medido, gerado, divergente,
pendente, falhou, exemplo), substituindo `SeloCanvas`, `SeloGravacao`,
`InsightsPainel` e a `TarjaFonte` do aluno. O Kit o desenha.

**Não foi feito.** Os quatro dialetos continuam. É um PR próprio, toca quatro
componentes em dois produtos, e o ouro precisa perder o emprego de marcar
conteúdo de LLM ao mesmo tempo — trocar isso junto com o resto tiraria a régua
de comparação de todo o trabalho.

### 7.3 · O Banco continua construído duas vezes

`telas/Banco/` e `telas/Aluno/EstudarBanco.tsx` são duas implementações da
mesma tela. A razão registrada era que a da coordenação é toda em tokens da
coordenação e não sobrevive ao tema escuro do aluno.

**Essa razão acabou de morrer:** desde o PR 7 os dois lêem os mesmos papéis.
Reunificá-las passou a ser possível, e continua sendo trabalho próprio.

### 7.4 · A coluna lateral só entrou na ficha do aluno

O brief a pede em três telas de leitura: ficha do aluno, ficha de ciclo e ficha
de simulado. A de ciclo virou hub e não precisa mais; a **ficha de simulado**
ficou sem.

### 7.5 · O semáforo no documento impresso

Ver decisão 3.
