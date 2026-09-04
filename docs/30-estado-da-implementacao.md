# 30 — Estado da implementação da área do aluno

> Escrito em **30/08/2026**, no fim da passagem que construiu a área do aluno
> nova a partir do desenho de 29/08 ([24](24-jornada-do-aluno.md),
> [26](26-mecanicas-do-jogo.md), [27](27-tio-leo.md), [28](28-banco-do-aluno.md))
> e do inventário de buracos ([29](29-area-do-aluno-o-que-falta.md)).
>
> **As três tabelas abaixo são GERADAS** de
> [`web/src/dados/aluno/registro.ts`](../web/src/dados/aluno/registro.ts), não da
> memória de ninguém. `npm test` falha se o documento divergir do registro; para
> atualizar, mude o registro e rode `npm run inventario` dentro de `web/`.

<!-- INVENTARIO:INICIO -->
<!-- Gerado por web/src/dados/aluno/inventario.ts a partir de
     web/src/dados/aluno/registro.ts. NÃO EDITE ENTRE AS MARCAS À MÃO:
     `npm test` falha se esta seção divergir do registro. Para mudar,
     mude o registro e rode `npm run inventario` dentro de web/. -->

## 1 · LIGADO — 22 fontes

O endpoint existe e a tela consome de verdade. Nada aqui é mock.

- **`simulados`** — Filtra `presente = true` e descarta a falta — ver a fonte `presencaNosSimulados`.
- **`trajetoria`** — Rota pronta e sem tela até agora — docs/29 §A.5.
- **`heatmap`** — Rota pronta e sem tela até agora — docs/29 §A.5.
- **`questoesDoBanco`** — Filtrar por tópico exige matéria: a rota devolve 400 sem ela, e a folha de filtros impede a combinação. Em 02/09 ganhou `colecao=recentes\|arquivo`, traduzida para `extraido_por` na camada de consulta — o aluno e a URL não precisam do nome da coluna. O Arquivo é a página INTEIRA do caderno (0033) e o cartão de lá leva tarja dizendo qual número procurar.
- **`estatisticasDoBanco`** — Ganhou tela em 02/09 e virou a espinha da aba Estatísticas. `questoesPorAno` (denominador de "% da prova") e o filtro `fase` entraram junto: os dois estreitam a resposta INTEIRA, e é isso que mantém numerador e denominador no mesmo recorte. A ficha faz DUAS chamadas, uma por vestibular — `porVestibular` é agregado e não tem quebra por ano —, e as duas falham independentemente: série ausente é declarada na tela, nunca desenhada como zero. Nunca pagina, de propósito.
- **`estudo`** — ⚠️ `resolvida` e `acertou` NÃO são a mesma coisa e não se somam: a primeira é auto-declarada e pode existir sem resposta nenhuma; a segunda é conferida contra o gabarito, no servidor (0042). Ausência de linha = questão não tocada, que é a maioria.
- **`progressoDoBanco`** — Agrega no servidor de propósito: `GET /banco/estudo` devolve as linhas cruas, sem atributo de questão, e montar a tela com ela obrigaria o celular a baixar as ~2.700 questões para cruzar no navegador. Devolve SEMPRE o par (feitas, total) — contagem sem denominador é bug de produto. Usa `get_current_aluno`: é dado pessoal de menor, e o id sai do token.
- **`origemDaResolucao`** — O prompt de implementação a listava como sem-rota; o campo JÁ vem no schema (`schemas/banco.py`), então está ligada. O aluno lendo resolução de IA achando que é do professor é o achado mais desconfortável de docs/29 — a tela é obrigada a marcar.
- **`missaoDoDia`** — Deixou de ser mock em 04/09. O fixture pareava o código `7.2` com o nome "Termodinâmica", e na taxonomia de Física 7.2 é "Ondas e Acústica": o cartão lia a etiqueta e o treino lia o endereço, e como o endereço existia nada quebrava — só mentia. Agora nome e código saem da mesma linha de `topico_taxonomia`. O sorteio é determinístico pela data em America/Fortaleza (em UTC viraria às 21h, para todo mundo junto) e só entra tópico com 10+ questões OBJETIVAS: o `totalQuestoes` da taxonomia conta dissertativa, que a fila de treino descarta. Saiu do Sprint 6 porque "o mesmo desafio para todos" derruba a personalização que dependia de `acertoPorAssunto`.
- **`respostaNoTreino`** — Ligada em 02/09 (migration 0042). É a única fonte de acerto por assunto que NÃO depende do Sprint 6 — as questões do banco já são classificadas por tópico do edital. ⚠️ `acertou` é calculado no SERVIDOR contra o gabarito, nunca aceito do cliente; `null` é "não dá para dizer" (dissertativa ou sem gabarito), jamais "errou". E não muda a diretriz: alimenta o plano de estudo, NUNCA o XP — treino não é supervisionado.

| Fonte | O que é | Rota que alimenta | Em que telas aparece |
|---|---|---|---|
| `aluno` | Nome, turma, e-mail e foto do aluno logado | `GET /me` | casco, Jornada |
| `trocarSenha` | Troca da própria senha | `POST /me/senha` | casco (folha da conta) |
| `fotoDePerfil` | Foto de perfil do aluno, por rota autenticada | `GET/PUT/DELETE /me/foto` | casco |
| `simulados` | Simulados do aluno com nota, delta contra o próprio padrão e média da turma | `GET /me/simulados` | Hoje, Provas, Jornada |
| `simulado` | Ficha de um simulado: posição, percentil e comparação com grupos | `GET /me/simulado/{id}` | Hoje, Provas, Ficha do simulado |
| `questoesDoSimulado` | Resultado questão a questão: certas, erradas e em branco | `GET /me/simulado/{id}/questoes` | Ficha do simulado |
| `evolucao` | Evolução por matéria ao longo dos ciclos, aluno contra turma | `GET /me/evolucao` | Hoje, Provas, Jornada |
| `trajetoria` | Todas as notas do aluno em ordem cronológica, já em escala 0–10 | `GET /me/trajetoria` | Jornada |
| `heatmap` | Matriz matéria × simulado para o mapa de calor | `GET /me/heatmap` | Provas |
| `insight` | Bullets de IA sobre o ciclo mais recente | `GET /me/insight` | Hoje |
| `questoesDoBanco` | Página filtrada do acervo ITA·IME — a única rota paginada do projeto | `GET /banco/questoes?…&colecao` | Banco, Questão em tela cheia, Sessão de treino |
| `questaoDoBanco` | Uma questão por id legível (`ita_2019_fase1_q01`) | `GET /banco/questoes/{id}` | Questão em tela cheia |
| `taxonomia` | Árvore bloco → tópico do edital, com contagem em cada nível | `GET /banco/taxonomia` | Estudar (folha de filtros) |
| `estatisticasDoBanco` | Recorrência bruta de cada tópico, por ano, fase e vestibular | `GET /banco/estatisticas?materia&vestibular&fase` | Estatísticas (ranking, mapa do edital, ficha do assunto) |
| `listas` | Listas de questões montadas pelo aluno — as 5 rotas | `GET/POST/PATCH/DELETE /banco/listas…` | Minhas listas, Uma lista, Questão em tela cheia |
| `estudo` | Resolvida, anotação e a resposta do treino, por aluno e questão | `GET/PUT /banco/estudo` | Banco, Questão em tela cheia, Sessão de treino, Meu progresso |
| `progressoDoBanco` | Quanto do acervo o aluno marcou como feito — por matéria, por assunto e por ano | `GET /banco/progresso` | Meu progresso, Estudar (o subtítulo dos três campos) |
| `origemDaResolucao` | Se a resolução é do professor do Ari ou foi gerada por LLM no pipeline | `resolucaoOrigem em GET /banco/questoes` | Questão em tela cheia, Sessão de treino |
| `missaoDoDia` | O assunto do dia com 10 questões — o herói da aba Hoje, igual para toda a turma | `GET /missao/hoje` | Hoje, Sessão de treino |
| `conversaTioLeo` | Threads, streaming SSE e as 6 tools do aluno | `GET/POST /chat/threads…` | Tio Léo |
| `autenticacao` | Login por matrícula e senha, primeiro acesso e SSO do Canvas | `POST /auth/login · /auth/primeiro-acesso · /auth/canvas` | Login |
| `respostaNoTreino` | A alternativa que o aluno escolheu no treino e se ela bate com o gabarito | `PUT /banco/estudo/{id} · alternativaEscolhida` | Sessão de treino, Resumo do treino |

## 2 · DADO EXISTE, ROTA NÃO — 6 fontes

O servidor já sabe a resposta; só não há rota que a devolva. **Ordenada por
esforço crescente, porque esta tabela é a lista de tarefas mais barata do
projeto**: desmockar qualquer linha daqui é escrever uma rota curta sobre dado
que já está no Postgres, não inventar produto.

| Esforço | Fonte | O que é | Onde o dado JÁ está no servidor | Rota que a desmockaria | Telas |
|---|---|---|---|---|---|
| P | `meusErros` | Todas as questões erradas e em branco, agregadas por todos os simulados | `/me/simulado/{id}/questoes` já devolve isso por simulado — falta somar | `GET /me/erros` | Estudar (o elo quieto), Sessão de treino (origem `erros`) |
| P | `presencaNosSimulados` | Os simulados em que o aluno faltou — os quadrados vazados da corrente | `nota.presente`, hoje filtrado fora por `simulados_do_aluno` | `GET /me/simulados?incluirFaltas=true (ou um /me/presenca)` | Hoje, Jornada |
| P | `proximoSimulado` | Data do próximo simulado, para a contagem regressiva | `evento_agenda`, que já dispara e-mail ao aluno na véspera desde a Sprint 1 | `GET /me/agenda` | Hoje, casco (coluna direita) |
| P | `sequencia` | Simulados consecutivos sem faltar, corrente e recorde | `nota.presente` — o mesmo dado de `presencaNosSimulados` | `GET /me/jogo (docs/26 §9)` | Hoje, casco (coluna direita), Login |
| M | `cortePorMateria` | A nota de corte de cada matéria — 4,0, e 5,0 no Inglês eliminatório do ITA F1 | `criterio_classificacao` (0023), a mesma régua que a coordenação já lê | `GET /me/zona (mesma rota da zona)` | Hoje, Provas, Jornada, Extrato de XP |
| M | `zonaEDistancia` | Zona do aluno, distância até a próxima e o nome da régua que produziu o veredito | `classificacao_aluno.zona` + o avaliador de critérios (migration 0023) | `GET /me/zona` | Hoje, Jornada |

- **`meusErros`** — O material de estudo mais óbvio que temos, enterrado atrás de uma navegação.
- **`presencaNosSimulados`** — Do lado do aluno a falta é invisível hoje. Sem ela a corrente perde justamente o que dá peso à sequência.
- **`proximoSimulado`** — O e-mail sabe do simulado; a tela não. É o gancho diário do produto inteiro (docs/26 §2) e não tem fonte.
- **`sequencia`** — ⚠️ `/me/streak` EXISTE, mas com a semântica ANTIGA — "ciclos consecutivos acima da média da turma", que é relativa e premia posição, não progresso (docs/24 §1.1). Não foi ligada de propósito: ligar a rota errada seria pior que mockar.
- **`zonaEDistancia`** — A régua é obrigatória junto do rótulo (docs/24 §2): "risco" sem contra qual corte é só a má notícia.

## 3 · MOCK PURO — 13 fontes

Não existe nem dado. Desmockar é decisão de produto, migration, ou as duas.

| Esforço | Fonte | O que é | Especificada em | Depende de | Telas |
|---|---|---|---|---|---|
| P | `conquistas` | As medalhas sob as regras novas — só o que se verifica | docs/26 §6 | xp, sequencia e `conquista_aluno(aluno_id, chave, em)` | Jornada |
| P | `depoimentos` | "De quem já passou" — o cartão de aprovados | docs/24 §7 (brief) | conteúdo editorial de verdade | Jornada |
| P | `metaDoCiclo` | O alvo do ciclo — substituiu a meta semanal, que o dado não sustentava | docs/24 §7.3 | a decisão aberta "quem define a meta, aluno ou sistema" (docs/24 §9.1) | — nenhuma |
| M | `artefatosDoTioLeo` | Os artefatos novos do catálogo: barras_corte, extrato_xp, questao, plano, prova | docs/27 §7 | as tools novas em `tools_aluno.py` e as fontes que cada artefato mostra | Tio Léo |
| M | `escolhaDaFilaDeTreino` | Quais questões entram na sessão, e em que ordem | docs/28 §3 | acertoPorAssunto + importanciaDoAssunto | Sessão de treino |
| M | `extratoXp` | De onde vieram os pontos, linha por linha, com as que não pontuaram vazadas | docs/26 §3 | xp + cortePorMateria | Extrato de XP, Tio Léo (artefato) |
| M | `formulaMatematica` | Renderização de fórmula na resposta do Tio Léo | docs/27 §12 | a decisão aberta entre KaTeX empacotado e MathML via Temml | Tio Léo |
| M | `importanciaDoAssunto` | Fatia da prova ponderada por recência (meia-vida 5 anos) e a tendência ao lado | docs/24 §4 | `/banco/estatisticas`, que já dá a incidência bruta — falta a ponderação | — nenhuma |
| M | `xp` | XP total e do ciclo | docs/26 §3 | o cálculo de XP reusando o avaliador de critérios, e o backtest de docs/29 §H | casco (topo e coluna direita), Extrato de XP, Liga |
| G | `acertoPorAssunto` | Quanto o aluno acerta em cada tópico do edital | docs/24 §3 | classificar as 1.031 questões de simulado (`questao_topico`, Sprint 6) | Resumo do treino |
| G | `esquadrilha` | Time de 3 a 6 amigos cujo XP soma; ninguém é ranqueado por dentro | docs/26 §5.2 | xp + parecer de LGPD (docs/26 §5.3) | Jornada |
| G | `ganchoDeRetorno` | O gancho personalizado da tela de login — "sua sequência está esperando" | docs/29 §C | notificação (e-mail, push ou PWA), que não existe | Login |
| G | `liga` | Liga anônima do ciclo, com sobe-5 / desce-5 | docs/26 §5.1 | xp + a decisão de coordenação "gamificação pode ser competitiva?" | Liga, Jornada, casco (coluna direita) |

- **`conquistas`** — Sai "Top 15%", que premia posição. Sem a tabela de registro a celebração de tela cheia repete a cada abertura.
- **`depoimentos`** — Entregue como afordância com um botão. Citação de aprovado não se inventa.
- **`metaDoCiclo`** — ⚠️ NÃO foi construída. O hook existe e nenhuma tela o consome: a contagem regressiva ocupou o lugar que a meta teria na Hoje, e enquanto a decisão de quem define o alvo estiver aberta, um bloco de meta seria inventar produto.
- **`artefatosDoTioLeo`** — `histograma` e `linha_temporal` já são reais e continuam. `fonte_id` é injetado do JWT, nunca aceito como argumento.
- **`escolhaDaFilaDeTreino`** — As QUESTÕES são reais (`/banco/questoes`); o que é mock é o critério de escolha. Antes do Sprint 6 a sessão cai para matéria, escolhida pela mais distante do corte.
- **`extratoXp`** — A única tela que explica a régua de corte sem parecer boletim. As linhas com +0 nunca somem.
- **`formulaMatematica`** — Renderizada como TEXTO SIMPLES de propósito: nenhuma dependência entra antes da decisão. E o risco de docs/27 §10 segue de pé — fórmula bonita e errada aumenta a confiança do aluno numa resposta falsa.
- **`importanciaDoAssunto`** — ⚠️ ADIADA POR DECISÃO DE 02/09: a tela de Estatísticas ranqueia por INCIDÊNCIA BRUTA, sem ponderação por recência, e a tendência sai de código puro sobre a mesma série que o gráfico desenha (`dominio/serieDoAssunto.ts`). Sobrevive só como heurística interna da fila de treino (o fixture `ASSUNTOS` em `mocks.ts`, dentro de `ordenarFilaDeTreino`). Independe do Sprint 6 e continua sendo "B pode começar hoje" de docs/24 §8 — mas deixou de ser pré-requisito da missão do dia, que foi construída em 04/09 sem ela: um desafio igual para toda a turma não pondera nada por aluno (docs/35 §9).
- **`xp`** — ⚠️ Os números da tabela são primeira calibração e o backtest contra os 5 ciclos de 2026 é PORTÃO, não desejável (docs/26 §7). XP é derivado, nunca saldo gravado.
- **`acertoPorAssunto`** — O caminho crítico de tudo. Classificar 1.031 questões faz 237.081 respostas passarem a dizer em que assunto o aluno erra.
- **`esquadrilha`** — É dado de desempenho de um menor compartilhado com outro menor, por escolha do titular. Entrada só por código de convite, nunca por busca de aluno. Entregue como afordância, não como funcionalidade.
- **`ganchoDeRetorno`** — ⚠️ NÃO foi implementado, e a ausência é deliberada: antes do login o servidor não sabe quem está do outro lado, e mostrar a sequência de alguém a quem quer que abra a página é vazamento, não retenção. O gancho de verdade é notificação — e docs/29 §C registra que não existe PWA, manifest nem push. A porta mostra a metáfora, não um número de ninguém.
- **`liga`** — Os grupos TÊM de cruzar turma e sede: com ~900 alunos são 30 grupos, e um grupo que coincida com uma turma derruba o anonimato por dedução.

<!-- INVENTARIO:FIM -->

## O que fazer a seguir

Sai das tabelas 2 e 3, e a ordem é de dependência, não de gosto.

### 1 · As cinco rotas da tabela 2 — todas pequenas, e destravam metade das telas

São o item mais barato do projeto inteiro: o dado já está no Postgres, e cada
uma é uma leitura curta sobre tabela existente.

| | O que escrever | Destrava |
|---|---|---|
| 1 | `GET /me/agenda` — o próximo `evento_agenda` do aluno | a contagem regressiva, que é o **gancho diário do produto** e hoje não tem fonte |
| 2 | `GET /me/simulados` deixar de filtrar `presente = true` | o quadrado vazado da falta, que é o que dá peso à sequência |
| 3 | `GET /me/erros` — agrega `/me/simulado/{id}/questoes` | a origem `erros` do treino, que hoje só sabe agregar por matéria |
| 4 | `GET /me/jogo` — sequência e recorde por `nota.presente` | tirar a sequência do mock, e aposentar `/me/streak` |
| 5 | `GET /me/zona` — zona, distância por matéria e o nome da régua | o corte por matéria em quatro telas, e a escada da Jornada |

⚠️ **`/me/streak` continua no ar medindo a coisa errada.** Ela devolve "ciclos
consecutivos acima da média da turma" — métrica relativa, que premia posição e
não progresso (docs/24 §1.1). Nenhuma tela nova a consome. Quando a 4 entrar, a
rota antiga sai junto, senão ficam duas verdades sobre o mesmo número.

### 2 · Antes de qualquer XP: o backtest

Rodar a tabela de docs/26 §3 contra os 5 ciclos reais de 2026 e ver quantos
alunos ficam abaixo de 200 XP, se o topo se descola, e se as linhas de progresso
pessoal de fato mudam a liga. **É portão, não desejável** (docs/29 §H) — os
números que estão no mock são primeira calibração e não devem chegar ao aluno
sem serem aferidos.

E a decisão de arquitetura que fica cara depois: **XP é derivado de `nota`,
nunca saldo gravado.** Nota é corrigida e simulado é anulado; recalcular faz a
correção se propagar sozinha (docs/29 §B.1).

### 3 · Uma migration pequena com retorno grande

`alternativa_escolhida` e `acertou` em `questao_estudo_aluno` (docs/28 §3). É a
**única fonte de acerto por assunto que não depende do Sprint 6**, porque as
questões do banco já são classificadas. Sem ela a sessão de treino esquece tudo
ao fechar a aba, e o resumo final não sobrevive a um F5.

### 4 · O Sprint 6, que é o caminho crítico do resto

Classificar as 1.031 questões de simulado em `questao_topico` faz 237.081
respostas passarem a dizer **em que assunto** o aluno erra. É o que transforma o
plano de estudo e a fila de treino de mock em produto.

> Atualizado em 04/09: a **missão do dia** saiu desta lista. Ela virou rota
> (`GET /missao/hoje`, docs/35 §9) com um desafio igual para toda a turma,
> sorteado pela data — e sem personalização não há o que pesar por aluno, então
> ela deixou de depender do Sprint 6.

O índice de importância (docs/24 §4) **pode começar antes**: só depende do que já
está no Postgres, e é ele que falta para `/banco/estatisticas` — hoje ligada no
papel e sem tela — virar "o que estudar" em vez de "o que já caiu".

### 5 · Notificação, senão o resto não é usado

Sem ela, sequência, liga e contagem regressiva perdem o gatilho e o aluno só
descobre tudo se lembrar de abrir. Não existe PWA, manifest nem push
(docs/29 §C); o motor de lembretes por e-mail existe desde a Sprint 1 e é a
ponte barata.

### 6 · Por último, Liga e Esquadrilha

São as maiores, e a Liga está travada numa decisão que não é técnica —
"gamificação pode ser competitiva?" (docs/24 §9.1). A Esquadrilha depende ainda
de parecer de LGPD: é dado de desempenho de um menor compartilhado com outro
menor, por escolha do titular.

---

## O que ficou incompleto nesta passagem

⚠️ Esta seção existe porque um inventário que esconde buraco é pior que nenhum.
Ela sai dos relatórios dos revisores, não da memória de quem escreveu.

### Buracos de produto, visíveis para o aluno

- **O mapa de calor de Provas tem 111 colunas, não 25.** O bloco se chama
  "matéria por ciclo" e o eixo real é *simulado* — e como cada simulado tem uma
  matéria só, a grade nasce **98,3% vazia**. Trocar o eixo para ciclo desliga
  `/me/heatmap`, que era um objetivo declarado; é decisão de produto, e precisa
  ser tomada.
- **O extrato de XP ignora o `:id` da rota.** O aluno abre a ficha de um
  simulado e o extrato mostra outro — o mock tem um só. Está comentado no
  código, mas é uma contradição na cara de quem usa.
- **Em produção não existe marca nenhuma de placeholder.** A tarja MOCK só
  aparece em desenvolvimento, então "você acerta 41%" chega ao aluno com a mesma
  cara de um número verificado. O brief manda marcar visivelmente o que é
  placeholder; isso ainda não foi resolvido.
- **Do acervo não dá para pôr questão numa lista.** O botão existe no cartão e
  a mutação está pronta e real; falta a tela escolher em qual lista, já que o
  aluno pode ter várias.
- **A profundidade da paginação não volta.** O recorte de filtro volta pela URL;
  a página não, então voltar de uma questão recomeça na página 1.
- **"Próxima questão" anda dentro da prova, não do recorte filtrado.** A tela
  da questão não recebe o filtro de onde veio.
- **A sessão de treino é volátil.** Sair descarta as respostas sem confirmar, e
  F5 no resumo cai no convite — consequência direta de não existir a tabela do
  item 3 acima.
- **A origem `erros` do treino não revisa as questões erradas.** Erro de
  simulado é `questao`; a fila é `questao_vestibular`; não há join. A tela
  agrega por matéria e diz isso ao aluno com todas as letras.

### Dívidas de código

- **`alu-tecla--pequena` tem 36px de altura**, abaixo do alvo de 44px, e é usada
  em nove telas. O conserto é uma linha no token — não um remendo por tela.
- **Duas classes CSS em inglês** (`-fill`, `hero`), ambas seguindo padrão que já
  existia no repositório. Renomear vale, mas de uma vez, nos dois lados.
- **`Situacao` e `Escudo` moram em `Jornada.tsx` e a Liga os importa de lá** —
  abrir `/liga` carrega o módulo inteiro da Jornada.
- **`corteMajoritario` é cópia literal do cálculo de `pecas/BarraCorte.tsx`.**
- **`contratos.ts` não reexporta `TopicoTaxonomia` nem `BlocoTaxonomia`.**
- **O tópico do mock não existe na taxonomia real**, então `/treino/prioridade`
  filtra por um código que traz outro assunto. Contido — a tela mostra o tópico
  real da questão — mas o mock precisa usar códigos que existem.

### Desvios conscientes do desenho

- **Nenhuma celebração** (a regra das duas escalas, 300ms e tela cheia). Depende
  de `conquista_aluno` para não repetir a cada abertura.
- **Fórmula matemática sai como texto simples.** A decisão entre KaTeX e MathML
  está aberta (docs/27 §12) e nenhuma dependência entra antes dela.
- **Não existe grotesca condensada.** O desenho pedia uma segunda família; o
  projeto só serve Plus Jakarta Sans, e nenhuma dependência nova foi autorizada.
  O peso 800 com tracking negativo é a aproximação.
- **O balão do aluno no chat é branco, não near-black.** Near-black sobre a cor
  DADO dá 3,6:1 e reprova AA; branco dá 4,5:1.
- **`histograma` e `linha_temporal` desenham com a paleta da coordenação.** São
  componentes compartilhados, e trocar a paleta deles mexeria na coordenação.
- **As três alturas da folha do Tio Léo não são manobráveis.** Ela abre no meio
  e sobe sozinha quando há artefato; não há arrasto.

### O que não foi visto rodando

O Chrome do MCP ficou preso por um dos agentes durante quase toda a passagem.
**Hoje, Provas, Jornada, Login e o gráfico de corte foram verificados no
browser** com sessão real — 360px e 1440px, nos dois temas, sem transbordo
horizontal. **Estudar, o treino, a questão em tela cheia e a folha do Tio Léo
não foram**: o que existe sobre eles é leitura de CSS e bancada isolada, não
observação. É a primeira coisa a fazer antes de considerar o sprint fechado.
