# 25 — A leitura da coordenação · filtros, cartões e o acesso

> **Origem:** os mesmos três áudios do Yan de **29/08/2026** que geraram o
> [24-jornada-do-aluno.md](24-jornada-do-aluno.md). Aqui fica o que é do lado
> da coordenação. Nada implementado — plano e desenho. O estado é
> [19-roadmap.md](19-roadmap.md).

Quatro incômodos, em ordem de tamanho crescente:

1. Os filtros ([§1](#1--os-filtros)) — barato, e o que mais irrita hoje.
2. Planilha demais, cartão de menos ([§2](#2--planilha-onde-a-planilha-ganha)).
3. Ninguém entende o que é "criar um acesso de coordenação" ([§3](#3--o-acesso-de-coordenação--o-que-o-código-já-responde)) — e o
   código já responde; o produto é que não conta.
4. O chat do coordenador é raso demais para o que virou ([§4](#4--o-chat-do-coordenador)).

---

## 1 · Os filtros

### 1.1 O que existe hoje, tela a tela

Levantado do código em 29/08.

| Tela | Grupos de filtro | Busca? | Componente |
|---|---|---|---|
| `/painel` | Ciclo (única) · Sede · Turmas | sim, **fora** da faixa | `BarraFiltros` |
| `/alunos` | Turma · Sede | não | `BarraFiltros` |
| `/provas` → Ciclos | Vestibular · Ano letivo · Período (datas) | não | `BarraFiltros` |
| `/provas` → Simulados | Vestibular · Fase · Ciclo · Disciplina | não | `BarraFiltros` |
| `/auditoria` | Canal · Incluir também | não | `BarraFiltros` |
| `/administracao` | Primeiro acesso · Buscar | sim, **dentro** da faixa | `BarraFiltros` |
| `/banco` | Matéria · Vestibular · Fase · Ano · Assunto | sim | **`banco-filtros`, um `<aside>` próprio** |

**Dois achados que o inventário entrega de graça:**

- **A busca não tem lugar fixo.** No Painel ela mora nos controles do
  cabeçalho; na Administração é um grupo da faixa; no Banco é o topo da
  sidebar; nas outras quatro telas não existe. Três posições e uma ausência
  para a mesma ideia.
- **O "componente único de filtro" não é único.** C.1 está marcado ✅ no
  [19 §1](19-roadmap.md), e é verdade para seis telas — mas o `/banco` nasceu
  depois, com sidebar própria (`FiltrosBanco.tsx`). São dois sistemas de novo,
  que foi exatamente o problema que C.1 existiu para resolver.

### 1.2 "Todos os filtros já vêm carregados" — e é de propósito

O comentário de cabeçalho de `BarraFiltros.tsx` diz, textualmente:

> *"Aqui todos os grupos ficam abertos: o custo de esconder um filtro é o
> usuário não saber que ele existe, e são poucos o bastante para caber numa
> linha."*

O incômodo do áudio é o contra-exemplo dessa aposta: **no Painel os grupos não
cabem em uma linha.** Sede e Turmas são pílulas por *valor*, não por
categoria — com ~900 alunos são dezenas de pílulas antes de a tabela começar.

**Proposta:** manter a regra, mudar o limiar. Faixa aberta por padrão;
**colapsa quando passa de uma linha**, com o resumo do que está ativo no lugar
(`Ciclo 4 · ITA · 2026 · 2 turmas`), e um botão de expandir. O estado
colapsado/aberto memorizado por tela, não global — quem trabalha no Painel e
quem trabalha em Provas quer coisas diferentes.

⚠️ **O que não fazer:** colapsar tudo por padrão. Isso é voltar ao
`PainelFiltros` lateral que o redesenho do casco tirou
([23-plano-redesenho-casco.md](23-plano-redesenho-casco.md)), e reintroduz
exatamente o problema que o comentário acima descreve.

### 1.3 Os "nomes grandes" — e a boa notícia

O incômodo é concreto e o exemplo do áudio é exato: as pílulas de ciclo dizem
**`Ciclo 4 · ITA · 2026`**. Isso é `ciclo.nome`, montado assim na ingestão:

```python
# api/app/ingest/pipeline.py:350
nome_ciclo = f"Ciclo {ciclo_ordem_efetiva} · {vestibular_efetivo} · {ano_fallback}"
```

**Três informações coladas numa string — e as três já existem em coluna
separada:** `ciclo.ordem`, `ciclo.vestibular_alvo` (migration `0003`) e
`ano_letivo`. O Painel é que descarta as duas últimas e mostra só o nome.

Ou seja, o que o áudio pediu — *"quebrar esses filtros em mais abas: qual o
número do ciclo, qual o vestibular, qual a data"* — **não precisa de migration
nenhuma**. É a C.2 do [docs/10 §C.2](10-problemas-e-visao.md#c2--split-ano--vestibular--ciclo-no-painel),
hoje parada na Sprint 4 · P3, com a hierarquia já desenhada lá:

```
Ano letivo  (fixo no topo, muda pouco)
   └── Vestibular   ITA · IME
          └── Ciclo   1 · 2 · 3 · 4
```

Cada nível estreitando o seguinte, e as pílulas passando a dizer `4` em vez de
`Ciclo 4 · ITA · 2026`.

### 1.4 A barra de pesquisa

Pedida no áudio, e o inventário do [§1.1](#11-o-que-existe-hoje-tela-a-tela)
mostra por quê: ela existe em três telas, em três lugares diferentes. Duas
perguntas antes de codar:

- **É busca de conteúdo da tela** (achar um aluno na tabela do Painel — o que
  já faz) **ou busca global** (digitar um nome de qualquer lugar e ir para a
  ficha)? São produtos diferentes. Ver [§5](#5--decisões-em-aberto), item 2.
- Se global, ela é o lugar natural do `⌘K` — e aí não pertence à faixa de
  filtros, pertence ao casco.

**Recomendação:** primeiro padronizar a busca da tela como um grupo da
`BarraFiltros` nas sete telas (barato, e resolve o incômodo declarado);
busca global só depois, e como decisão separada.

### 1.5 Tamanho

| Item | Tamanho | Depende de |
|---|---|---|
| Colapso da faixa com resumo do ativo, memorizado por tela | **P** | — |
| Busca padronizada em todas as telas | **P** | — |
| Split ano → vestibular → ciclo | **M** | é a Sprint 4 · P3 |
| `/banco` adotar a `BarraFiltros` | **M** | dívida de C.1 |

---

## 2 · Planilha: onde a planilha ganha

O áudio 2: *"devemos evitar esse esquema de planilhas... somente em poucos
lugares da coordenação faz sentido termos planilhas mesmo. Na maioria dos
lugares, cards bonitinhos."*

Concordar sem qualificar seria um erro: **o SAS existe porque a coordenação
acompanha ~900 alunos**, e comparar 900 linhas é o que tabela faz e cartão não
faz. A régua útil é outra: **tabela é para comparar, cartão é para decidir.**

| Tela | Hoje | Proposta |
|---|---|---|
| `/painel` | tabela de alunos | **fica tabela** — é a tela de varrer 900 pessoas. Ganha uma faixa de cartões de decisão *acima* dela (quantos em risco, quantos mudaram de zona, o que exige ação hoje) |
| `/alunos` | tabela | **fica tabela** — mesma razão |
| `/provas` · Ciclos | tabela | **vira cartão.** São ~4 ciclos por ano; cada um é uma decisão, não uma linha de comparação |
| `/provas` · Simulados | tabela | **fica tabela**, com o estado do Canvas visível na linha |
| `/administracao` | duas tabelas | **fica** — é lista administrativa |
| `/auditoria` | tabela | **fica** — é registro cronológico, o formato é o certo |
| Ficha do aluno | misto | **mais cartão** — é a tela onde se decide sobre uma pessoa |

Note que a conclusão é quase o oposto do palpite do áudio: **a maioria das
telas de coordenação é de comparação, e tabela é o formato certo.** O que
falta não é trocar tabela por cartão — é **o cartão de decisão que hoje não
existe em lugar nenhum**: o bloco que diz "isto aqui merece sua atenção hoje",
que é a promessa do `CLAUDE.md` ("sinaliza o que merece atenção em vez de
esperar que o coordenador saiba o que procurar") e que hoje só vive dentro dos
alertas.

---

## 3 · O acesso de coordenação — o que o código já responde

O áudio 1 lista quatro dúvidas. **As quatro têm resposta no código**, e
nenhuma está escrita em lugar visível. Isso, por si, é o achado: se o autor do
produto não sabe, o coordenador também não vai saber.

### 3.1 As respostas

| Pergunta do áudio | Resposta |
|---|---|
| Criar um acesso de coordenação cria também um acesso no Canvas? | **Não.** O SAS nunca escreve usuário no Canvas. `POST` de coordenador só grava em `usuario_coordenacao` e sorteia uma senha inicial, mostrada **uma vez** |
| A pessoa precisa ter ligação com o Canvas? | **Não.** Uma conta só com e-mail e senha funciona inteira. O Canvas é opcional e só troca a forma de entrar |
| Como criar acesso para quem já tem conta no Canvas? | Do mesmo jeito — **usando o mesmo e-mail do Canvas**. O SAS acha o `canvas_user_id` pelo e-mail, agora (botão "Ligar ao Canvas") ou sozinho no primeiro login pelo Canvas |
| Se eu tenho conta no Canvas e sou coordenador, entro como coordenador direto? | **Não.** Alguém tem que ter criado o seu acesso antes |

A última é a que importa, e o comentário de `auth_canvas.py` diz a regra em
uma frase:

> *"não cria aluno: identidade que o Canvas atesta mas não existe em `aluno` é
> recusada. **O Canvas diz QUEM é; o SAS decide quem ENTRA.**"*

Vale igual para coordenação: sem linha em `usuario_coordenacao`, o login pelo
Canvas é recusado — por mais admin que a pessoa seja lá dentro. É a decisão
certa (o Portão 1 de [docs/14](14-plano-producao.md) existe para isso: o que
impede um estranho de virar coordenador), e é invisível.

### 3.2 O fluxo completo, como ele de fato é

```
  coordenador existente
        │
        ├─ cria a conta: nome + e-mail          ──►  usuario_coordenacao
        │                                             (senha sorteada,
        │                                              mostrada UMA vez)
        │
        └─ o e-mail é o mesmo do Canvas?
                 │
                 ├─ sim ──► liga na hora ("Ligar ao Canvas") ──┐
                 │          ou sozinho, no 1º login pelo Canvas │
                 │                                              ▼
                 └─ não ──► conta entra só por senha    "entra pelo Canvas"
```

### 3.3 O que mudar — e não é o modelo, é a explicação

O modelo está certo. O que falta é o produto contar o que ele faz:

1. **Um parágrafo na tela de Administração**, antes do botão de criar: *"Isto
   cria um acesso ao SAS. Não cria nada no Canvas. Use o mesmo e-mail do
   Canvas e a pessoa poderá entrar pelo botão do Canvas."* Hoje esse texto
   existe pela metade, como legenda de campo.
2. **Entregar a senha sem passar por WhatsApp.** A senha sorteada aparece uma
   vez e alguém a copia num canal qualquer. O motor de e-mail existe desde a
   Sprint 1 — um convite por link expira, não vaza em conversa, e é auditável.
   ⚠️ Depende de decidir se coordenação recebe e-mail transacional
   ([§5](#5--decisões-em-aberto), item 3).
3. **Mensagem de recusa que ensine.** Quem entra pelo Canvas sem ter acesso no
   SAS recebe uma recusa genérica. Deveria dizer o que fazer: *"peça a um
   coordenador para criar seu acesso com este e-mail."*
4. **Papéis.** Hoje `usuario_coordenacao` é um papel só: quem entra pode tudo,
   inclusive criar outros acessos e ver auditoria. Com mais de duas pessoas
   isso vira decisão ([§5](#5--decisões-em-aberto), item 4).

---

## 4 · O chat do coordenador

O áudio 3: *"o chat com o coordenador tem que ter muito mais [tools], talvez
até pensar no MCP... uma produção de fato de conteúdo denso para a coordenação,
que a coordenação realmente consiga usar. Cruzamento de dados. Inicialmente
surgiu como 'tudo que está na plataforma tem que ser mostrado de maneira
conversacional'. E hoje é mais do que isso."*

### 4.1 De onde ele parte

**26 tools**, em `api/app/chat/tools/`: leitura (`obter_aluno`,
`listar_ciclos`, `notas_simulado`…), análise (`alunos_em_risco`,
`tendencia_aluno`, `materias_problematicas`, `alunos_similares`,
`comparar_ciclos`, `trajetoria_aluno`, `histograma_simulado`) e saída
(`relatorio_aluno`, `relatorio_ciclo`, `gerar_grafico`, `exportar_csv`).

**A base é boa.** Gráfico e CSV já saem do chat como artefato
(`Artefato.tsx`). O diagnóstico do áudio — "isso virou mais que espelhar a
plataforma" — está certo, e o gargalo não é a lista de tools.

### 4.2 Os três gargalos reais

> *Sobraram dois — o primeiro já estava resolvido quando este documento foi escrito (30/08).*

1. ~~**O chat é modal e bloqueia a tela.**~~ ✅ **Já estava resolvido quando
   este documento foi escrito**, e ninguém tinha registrado: o `.chat-overlay`
   saiu na migração React (`c1e0a5f`) e o painel passou a empurrar o conteúdo
   acima de 900px. Ver [10 §1.6.4](10-problemas-e-visao.md#164-o-chat-bloqueia-a-navegação-enquanto-está-aberto).
2. ~~**Ele não sabe onde a pessoa está.**~~ ✅ **Feito na Sprint 5 · P2**
   (escrito, fora de produção): o contexto da tela viaja com cada mensagem e
   vira preâmbulo do turno, e o `navegar_para` faz o caminho de volta.
3. **Cada tool responde uma pergunta; nada compõe.** "Cruzamento de dados" no
   sentido do áudio é o modelo encadear tools — e para isso ele precisa de
   tools que devolvam *dado*, não texto pronto. Vale auditar quais das 26 já
   devolvem estrutura encadeável e quais devolvem prosa.

Sobra o terceiro. Os outros dois foram fechados: o primeiro já estava, e o
segundo saiu na **Sprint 5 · P2** ([31-plano-sprint-5.md](31-plano-sprint-5.md)).
O áudio não pediu sprint nova — pediu que ela subisse de prioridade, e ela subiu.
A auditoria do gargalo 3 (quais das 30 tools devolvem *dado* e quais devolvem
prosa) segue por fazer.

### 4.3 Sobre MCP

O áudio levanta MCP como caminho. **Vale separar duas coisas:**

- **MCP como protocolo interno** (trocar o formato de tool da OpenAI por um
  servidor MCP dentro do backend) — **não traz nada.** As 26 tools já rodam,
  já são testadas, e o loop de agente já existe em `agente.py`. Seria
  reescrever fundação estável.
- **MCP como porta de entrada** (o coordenador usar o SAS de dentro do Claude
  Code / Claude Desktop, com as ferramentas dele misturadas às nossas) — **é
  outra coisa, e é interessante**: o `.mcp.json` deste repositório já mostra o
  padrão funcionando com `postgres` e `chrome`.

⚠️ **A segunda opção tem um porém que precisa ser dito antes de qualquer
protótipo:** um servidor MCP do SAS expõe dado de menor de idade a um cliente
fora da nossa infra. A regra 6 do `CLAUDE.md` e o `docs/14 §5` valem inteiros
aqui. É decisão, não implementação ([§5](#5--decisões-em-aberto), item 5).

### 4.4 "Conteúdo denso que a coordenação consiga usar"

O que o áudio descreve — um documento, não uma resposta de chat — já tem
metade pronta: `relatorio_aluno` e `relatorio_ciclo` existem, `gerar_grafico` e
`exportar_csv` viram artefato na conversa, e o `/banco` já exporta lista em PDF
e Word (Sprint Banco · P5).

**O que falta é o artefato composto:** um dossiê de ciclo com texto, gráfico e
tabela juntos, que se salva e se leva para a reunião. É o mesmo motor de
exportação da P5 do banco, apontado para outro conteúdo.

---

## 5 · Decisões em aberto

| # | Decisão | Trava | Quem decide |
|---|---|---|---|
| 1 | **A faixa de filtros colapsa por padrão ou só quando estoura a linha?** | §1.2 | Yan |
| 2 | **A busca é da tela ou é global (`⌘K`)?** São produtos diferentes | §1.4 | Yan + coordenação |
| 3 | **Coordenação recebe e-mail transacional?** Sem isso, a senha inicial continua saindo por canal informal | §3.3, item 2 | Coordenação |
| 4 | **Existem papéis dentro da coordenação, ou todo mundo pode tudo?** Hoje: todo mundo pode tudo, inclusive criar acesso e ler auditoria | §3.3, item 4 | Coordenação |
| 5 | **Servidor MCP do SAS para uso fora da plataforma?** Expõe dado de menor a cliente fora da nossa infra | §4.3 | Yan + LGPD |
| 6 | **Ciclos vira cartão?** É a única troca de formato que o §2 recomenda de fato | Yan |

---

## 6 · Relação com o que já está planejado

Quase nada aqui é sprint nova. É prioridade:

| Incômodo do áudio | Já existe como | Estado |
|---|---|---|
| Nomes grandes de filtro | Sprint 4 · P3 (C.2) | proposta |
| Range de período | Sprint 4 · P4 (C.3) | proposta |
| Chat que bloqueia a tela | D.1 | ✅ **já estava feito** (migração React) |
| Chat sem saber a rota | Sprint 5 · P2 (D.4) | ✅ escrita, fora de produção |
| Chat com lacunas de tool | Sprint 5 · P3 (D.3) | ✅ escrita, fora de produção — 30 tools |
| **Colapso da faixa de filtros** | — | **novo** |
| **Busca padronizada** | — | **novo** |
| **`/banco` fora da `BarraFiltros`** | — | **novo (dívida de C.1)** |
| **Explicar o acesso de coordenação** | — | **novo** |
| **Cartão de decisão no Painel** | — | **novo** |
| **Dossiê de ciclo como artefato** | — | **novo** |
