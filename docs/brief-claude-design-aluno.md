# Brief para o Claude Design — área do aluno do SAS

Cole o bloco abaixo inteiro no Claude Design e anexe as imagens geradas
(`Login`, `Hoje`, `Estudar`, `Provas`, `Jornada`, celular e desktop).
As imagens são **referência de direção**, não gabarito de pixel — o texto manda.

---

```
# ⚠️ LEIA ISTO ANTES DE OLHAR AS IMAGENS

As imagens anexadas foram geradas ANTES de uma decisão de produto que mudou a
camada de jogo. Elas continuam valendo integralmente para DIREÇÃO VISUAL —
paleta, tipografia, densidade, forma, hierarquia. Elas estão ERRADAS quanto às
mecânicas.

A decisão: **o produto só pontua aquilo que consegue verificar que o aluno fez.**
Marcar uma questão como resolvida é autodeclarado — o aluno pode marcar cinquenta
sem abrir nenhuma. Nota de simulado, presença e posição vêm do sistema acadêmico
e são verificadas. Então a economia do jogo inteira migrou do "dia" para o
"simulado".

O que nas imagens está defasado, e o que construir no lugar:

| Nas imagens | Construa |
|---|---|
| Corrente de 7 quadradinhos com "S T Q Q S S D" | Corrente com UM QUADRADO POR SIMULADO DO CICLO (são ~5), não por dia da semana |
| "SEQUÊNCIA 12" ao lado de uma chama | "12 SIMULADOS SEM FALTAR" — a sequência conta provas, não dias |
| "META DA SEMANA 34/50" com barra | CONTAGEM REGRESSIVA para o próximo simulado: "FALTAM 12 DIAS PARA O P5" |
| XP subindo aos poucos, todo dia | XP em BLOCOS, um por simulado, com um extrato detalhado |
| "TERMINA EM 2 DIAS" na liga | "TERMINA COM O CICLO" — a liga é por ciclo, não semanal |

E uma tela que não existe em imagem nenhuma e precisa existir: o EXTRATO DE XP,
descrito adiante. É provavelmente o momento mais forte do produto.

Onde a imagem e este documento discordarem, **este documento vence, sempre**.

# CONTEXTO — o que é este produto

Você vai construir o mockup navegável da ÁREA DO ALUNO do SAS, a plataforma de
coordenação das turmas ITA/IME do Colégio Ari de Sá (Fortaleza, Brasil).

Quem usa: ~900 estudantes de 16 a 18 anos do terceiro ano do ensino médio, que
se preparam para os vestibulares do ITA (Instituto Tecnológico de Aeronáutica) e
do IME (Instituto Militar de Engenharia) — as duas academias de engenharia mais
disputadas do país. Eles fazem simulados em ciclos ao longo do ano, e cada
simulado é corrigido e vira nota.

O problema que a área do aluno tem hoje: ela é um BOLETIM. Mostra seis
indicadores que olham todos para trás, e não responde "o que eu faço agora".
Não existe nenhum motivo para o aluno abrir o app numa terça-feira comum,
porque nota só muda a cada três semanas.

O que estamos construindo: um CICLO DE TREINO E PROVA. Entre os simulados o
aluno treina livre — o banco de questões (2.693 questões reais de provas do ITA
e do IME, classificadas por tópico do edital) sugere o que estudar, sem pontuar,
porque não há como verificar que foi feito. No dia do simulado ele pontua: XP por
comparecer, por cada matéria acima do corte, por passar na régua completa, por
superar o próprio padrão e pela faixa de classificação na escola.

A metáfora é ATLETA E CORRIDA, não app de idioma: treino não pontua, prova
pontua. O boletim deixa de ser o hero da tela e vira consequência do jogo.

Isto é um JOGO, e precisa parecer um — a linguagem visual e a "juice" são de
Duolingo. NÃO é um dashboard de SaaS, NÃO é um app de fitness, e NÃO tem mascote.
Mas a ECONOMIA não é a do Duolingo: não existe recompensa diária, porque não
existe atividade diária verificável.

## Vocabulário do domínio — use estes termos, eles são do produto

- CICLO: uma rodada completa de simulados. ~5 por ano letivo. Nomeados
  "Ciclo 4 · ITA · 2026".
- SIMULADO: uma prova. Tem fase (1 ou 2), matéria, data e nota de 0 a 10.
- CORTE: a nota mínima. 4,0 por matéria como padrão. Inglês na Fase 1 do ITA é
  a ÚNICA matéria eliminatória, com corte 5,0. O corte é o conceito central do
  produto e vira o elemento visual central: uma linha.
- ZONA: risco → cinzenta → top. Como o aluno está contra o corte.
- TÓPICO / ASSUNTO: a classificação do edital. "Termodinâmica", "Estequiometria".
  Só existe taxonomia para Matemática, Física e Química — Português, Inglês e
  Redação NÃO têm, e a interface é obrigada a dizer isso onde faltar.
- SEQUÊNCIA: SIMULADOS consecutivos sem faltar. Nunca dias. (E nunca escreva
  "ofensiva" — é a palavra do Duolingo.)
- XP: pontos ganhos NO SIMULADO. Nunca por questão treinada.
- EXTRATO: a lista item a item de como o XP de um simulado foi formado.
- TREINO: resolver questões do banco entre os simulados. Não paga XP, e a
  interface nunca deve sugerir que paga.
- MATÉRIAS: matemática, física, química, português, inglês, redação.

## Idioma e escrita

TUDO em português do Brasil: rótulos, títulos, mensagens de erro, estados
vazios, e também os nomes de arquivo, componente, variável e classe CSS. É a
convenção do projeto inteiro, não uma preferência de exibição.

Tom: direto, encorajador e honesto. Nunca falsa positividade. Verbo no
imperativo nos botões ("Começar", "Treinar", "Ver"), e a ação mantém o mesmo
nome do começo ao fim do fluxo. Número sempre com vírgula decimal ("6,4").

# O SISTEMA DE DESIGN

## Regra mestra: cor é papel, nunca decoração

Seis papéis. Uma cor serve ao seu papel e a nada mais. Não invente cor nova, não
use verde em lugar nenhum, e nunca faça semáforo verde-e-vermelho.

| Papel      | O que é                                          |
|------------|--------------------------------------------------|
| ACAO       | o que se aperta                                   |
| VALOR      | XP, conquista, e a linha de corte                 |
| DADO       | barras acima do corte, progresso, aba ativa       |
| SEQUENCIA  | a chama e a corrente de dias                      |
| ALERTA     | só a etiqueta de distância e o valor abaixo do corte |
| MAGNITUDE  | todo numeral grande                               |

## Dois temas, mesmos papéis

Declare tudo como custom property em `:root`, redefina os valores sob
`@media (prefers-color-scheme: dark)` e sob `[data-tema="noite"]` / `[data-tema="dia"]`,
para que o seletor manual vença nos dois sentidos.

    /* DIA */
    --alu-fundo: #FFFFFF;      --alu-superficie: #F4F7FC;  --alu-borda: #DCE6F7;
    --alu-acao: #1B3F8B;       --alu-acao-base: #12275A;   --alu-acao-texto: #FFFFFF;
    --alu-valor: #F2C94C;      --alu-valor-texto: #B07D12;
    --alu-dado: #2E6BE6;       --alu-dado-claro: #7FB6FF;
    --alu-sequencia: #FF6B4A;  --alu-alerta: #E0452F;
    --alu-magnitude: #0F1B33;  --alu-texto-2: #5C6883;

    /* NOITE */
    --alu-fundo: #050A18;      --alu-superficie: #0C1530;  --alu-borda: #1B2B57;
    --alu-acao: #FFCE3A;       --alu-acao-base: #C79A16;   --alu-acao-texto: #050A18;
    --alu-valor: #FFCE3A;      --alu-valor-texto: #FFCE3A;
    --alu-dado: #2F6BFF;       --alu-dado-claro: #7FB6FF;
    --alu-sequencia: #FF6B4A;  --alu-alerta: #FF6B4A;
    --alu-magnitude: #FFFFFF;  --alu-texto-2: #6E85B8;

Duas trocas entre os temas são intencionais e a regra que as explica é uma só:
**a ação é sempre a cor de maior contraste com o fundo** — navy no dia, ouro na
noite. A magnitude acompanha. Todo o resto é constante.

`--alu-valor-texto` existe porque ouro puro reprova em contraste como TEXTO
sobre fundo claro. Use `--alu-valor` para traço e preenchimento,
`--alu-valor-texto` sempre que o ouro for letra.

## As seis regras que fazem parecer jogo

1. TECLA DE 4px. O botão primário tem `box-shadow: 0 4px 0 0 var(--alu-acao-base)`
   e ao ser pressionado desce 4px e perde a sombra (`transform: translateY(4px)`).
   Sem blur, nunca. **Só botão e bloco tocável** ganham isso; todo o resto é
   chapado. É a regra que sozinha faz mais diferença que todas as outras.
2. VAZIO É VAZADO. Qualquer coisa não conquistada, travada ou abaixo do corte é
   desenhada como contorno sem preenchimento. No tema noite isso lê como
   segmento queimado de letreiro; no dia, como não-preenchido. Nunca pinte de
   vermelho o que está abaixo do corte — só a etiqueta de distância é ALERTA.
3. A CONTAGEM REGRESSIVA APERTA. O bloco do próximo simulado fica discreto
   quando faltam semanas e ganha peso conforme a data chega — na véspera é o
   elemento mais forte da tela. É o substituto da chama nervosa do Duolingo:
   a urgência é real e verificável, em vez de inventada.
   Respeite `prefers-reduced-motion`.
4. A BARRA ANDA MESMO NO ERRO. Numa sessão de treino, uma resposta errada ainda
   avança um pouco o progresso da sessão.
5. CELEBRAÇÃO EM DUAS ESCALAS. Recompensa pequena e repetida: estouro de 300ms.
   Marco — cruzar o corte, passar na régua completa pela primeira vez, entrar no
   top 10, um novo recorde de sequência: tela cheia. Usar a grande em tudo mata
   as duas.
6. SILENCIE O QUE NÃO É O JOGO. Texto secundário deliberadamente apagado, para a
   cor do jogo dominar.

## Forma e tipografia

- Raio: 18px em superfície, 12px em elemento pequeno, 999px em pílula.
- Superfície: no dia, borda de 2px `--alu-borda`; na noite, 1px `--alu-borda`.
  **Nunca sombra flutuante** — é o que faz qualquer tela parecer template.
- Tipografia: uma grotesca condensada pesada para número e título (40 a 64px no
  celular, até 72px no desktop) e uma sans humanista arredondada para corpo
  (15 a 17px). Rótulo de olho ("eyebrow") em maiúscula pequena espaçada, 10px.
  Numerais tabulares em toda parte.
- No projeto real a família de corpo é **Plus Jakarta Sans**, servida
  localmente. Se precisar de uma segunda família, escolha algo com licença OFL —
  ela terá de ser auto-hospedada.

## Restrições que não são negociáveis

- **Nenhum asset de terceiro.** Sem CDN, sem Google Fonts, sem biblioteca de
  ícone remota, sem pixel de telemetria. Os dados são de menores de idade e isso
  é regra de LGPD do projeto, não preferência. Ícones como SVG inline.
- **Nenhum gráfico com biblioteca.** Todos os gráficos do projeto são SVG
  escrito à mão. Chart.js e equivalentes estão fora por decisão registrada.
- **Nenhuma foto de pessoa.** Avatar é círculo com duas letras. Se houver foto
  real, ela vem de rota autenticada da própria API.
- **A grade de fundo e a fachada do login são o MESMO motivo, em duas escalas.**
  O fundo de todas as telas tem uma grade quadrada quase imperceptível; a
  ilustração do login mostra um prédio modernista cuja fachada é um cobogó — uma
  treliça de quadrados — com exatamente o mesmo ritmo. Não é coincidência e não
  pode ser tratada como duas decisões separadas.
- **Nenhuma marca real de terceiro.** Nada de brasão do ITA, do IME ou de
  qualquer instituição. O selo do colégio é asset nosso e entra como placeholder
  circular no mockup.
- **Nenhum número institucional inventado.** Onde um número não vier de dado,
  marque visivelmente como placeholder.

# A ARQUITETURA — quatro abas e o chat

A estrutura segue o que o aluno vem fazer, não o modelo de dados.

    /              → HOJE      · o que eu faço agora
    /estudar       → ESTUDAR   · o que eu preciso treinar
    /provas        → PROVAS    · como eu fui
    /jornada       → JORNADA   · estou evoluindo
    /login         → a porta

    Dentro de Estudar:
    /estudar/assuntos     → "o que mais cai": importância × meu acerto
    /estudar/listas       → minhas listas
    /estudar/listas/:id   → uma lista

    FORA das abas, em tela cheia, sem barra inferior e sem o botão do Tio Léo:
    /treino/:origem        → a sessão de treino
    /treino/:origem/resumo → o fim da sessão
    /questao/:id           → uma questão

    `origem` é o que torna a sessão explicável, e aparece na URL:
    /treino/prioridade · /treino/erros · /treino/lista/:id · /treino/assunto/7.2
    A tela tem de saber dizer POR QUE são essas questões e não outras — "por que
    estou vendo isto" é a pergunta que mata a confiança numa recomendação quando
    não tem resposta.

    O treino e a questão são rotas de TOPO, não filhas de /estudar, porque ambas
    são alcançadas de vários lugares: o botão COMEÇAR da Hoje, os cartões de
    Estudar, a lista de erros em Provas e um artefato do Tio Léo. O id da questão
    é legível e estável ('ita_2019_fase1_q01'), então o link sobrevive.

    Tio Léo (chat) → botão flutuante em todas as abas; abre uma folha no
                     celular e um painel lateral no desktop. Não é rota.

No celular: barra inferior de 4 itens, item ativo com sublinhado de 2px na cor
DADO — nunca pílula preenchida.
No desktop (1440x900): três colunas — rail de 240px à esquerda com os 4 itens
empilhados e o perfil no rodapé; coluna central de 640px com o mesmo ritmo do
celular; coluna direita de 320px com os widgets persistentes (sequência, XP,
contagem regressiva, liga). Sem barra inferior no desktop.

## O que vai dentro de cada aba

HOJE
- Barra de topo: sequência (chama coral + número), XP (ficha de ouro + número),
  avatar.
- HERO — a missão do dia: "12 questões de Termodinâmica", com a razão
  ("Cai em 7% da prova do ITA. Você acerta 41%.") e o botão "COMEÇAR".
  Este é o elemento maior da tela. A nota NÃO é o hero.
- Corrente da sequência: um quadrado por SIMULADO DO CICLO (~5), preenchido
  quando o aluno compareceu, vazado quando faltou, e anelado no próximo.
  Nunca uma semana de dias.
- Contagem regressiva: "FALTAM 12 DIAS PARA O P5 · ITA · FASE 1", com uma barra
  medindo o intervalo entre o simulado anterior e o próximo.
- "ONDE VOCÊ ESTÁ": 5 barras (MAT FÍS QUÍ POR ING) contra a linha de corte
  dourada em 4,0. A barra abaixo do corte é vazada e leva uma etiqueta "−0,8".
- "O QUE SEU CICLO MOSTRA": até 3 bullets de insight.

ESTUDAR — duas metades, e NÃO um controle segmentado
⚠️ Uma versão anterior deste brief pedia três abas ("Prioridade", "Meus erros",
"Banco") num controle segmentado. Está revogado. Aquilo punha em paralelo três
coisas de naturezas diferentes — duas listas curtas que terminam em "treinar" e
um acervo de 2.693 questões que se busca — e obrigava o aluno a escolher uma aba
antes de ver qualquer coisa, numa tela cujo trabalho é dizer o que fazer.

PRIMEIRA METADE — "TREINAR AGORA", o topo e a razão da tela existir. Três
cartões empilhados, cada um uma ORIGEM do mesmo fluxo de treino, cada um com um
botão à direita:
- "Recomendado" — "Termodinâmica · 12 questões", com a razão numa linha quieta
  abaixo: "Cai em 7% da prova do ITA e você acerta 41%." Botão "COMEÇAR", na cor
  ACAO, com a borda de 4px. Este é o cartão mais destacado dos três.
- "Seus erros" — "34 questões que você errou nos simulados". Botão "REVISAR".
- "Sua lista" — "8 questões que você separou". Botão "TREINAR".
Abaixo dos três, um link discreto: "O que mais cai →".
Acima dos cartões, a tira de COBERTURA: um strip com 1px de borda e sem
preenchimento, rótulo "COBERTURA" e a linha "Cobre Matemática, Física e Química.
Português, Inglês e Redação ainda não."

SEGUNDA METADE — "TODAS AS QUESTÕES", o acervo, separada da primeira por um
divisor. NÃO se chama "Banco": "banco de questões" é vocabulário interno, não do
aluno.
- Um campo de busca JÁ VISÍVEL, nunca atrás de uma aba — o acervo é o maior
  ativo do produto e esconder a busca o desperdiça.
- Ao lado, um botão "Filtrar" que abre uma FOLHA com matéria, vestibular, fase,
  ano e assunto. No celular o filtro NUNCA é coluna lateral. Com filtro ativo, o
  botão mostra a contagem e uma linha de pílulas removíveis aparece sob a busca.
- ⚠️ O grupo ASSUNTO fica DESABILITADO enquanto nenhuma matéria for escolhida,
  com a linha "Escolha uma matéria primeiro — o mesmo código de assunto existe
  nas três e significa coisa diferente em cada uma." Não é preciosismo: a API
  devolve 400 nessa combinação, porque '1.1' é "Fundamentos" em Física,
  "Conjuntos e Lógica" em Matemática e "Estrutura Atômica" em Química, e juntar
  os três daria ao aluno um recorte errado sem erro nenhum na tela.
- A folha tem, fixo na base, um botão primário "VER N QUESTÕES", com o N mudando
  conforme as pílulas são tocadas.
- Sempre visível acima da lista, a contagem do recorte atual: "248 questões".

A QUESTÃO EM TELA CHEIA (/questao/:id) — é para onde tocar num cartão leva:
- topo com seta de voltar, "12 DE 248" ao centro em maiúscula pequena, e o ícone
  de adicionar à lista à direita;
- a origem, a imagem, as etiquetas de tópico e o botão "VER GABARITO";
- revelado, o gabarito mostra a letra grande, um botão "VER A RESOLUÇÃO" e um
  campo de anotação com o placeholder "Anote o que te travou nesta questão…";
- na base, FIXA, a barra de navegação da leitura: "← ANTERIOR", a marca de
  resolvida ao centro, "PRÓXIMA →". É assim que se anda entre questões, sem
  voltar à lista a cada uma.
- Abaixo, a lista paginada de cartões de questão.

O CARTÃO DE QUESTÃO é a peça mais importante desta aba:
- no topo, em maiúscula pequena, a origem: "ITA · 2019 · FASE 1 · Q12";
- o enunciado é uma IMAGEM da questão original — nunca texto redigitado — com
  largura máxima de 100% do cartão, porque o PNG tem largura variável e estoura
  a tela sem isso;
- abaixo, as etiquetas de tópico do edital. Uma etiqueta cuja classificação é
  incerta leva um pequeno ponto de alerta e o rótulo "classificação incerta";
- o gabarito fica ESCONDIDO atrás de um botão "Ver gabarito"; revelado, mostra a
  letra grande e um segundo botão "Ver a resolução";
- no rodapé do cartão, três ações: uma marca de resolvida (preenchida na cor
  DADO quando ativa), um ícone de anotação e um de adicionar à lista;
- se a questão for dissertativa, não há alternativa nem gabarito — mostre uma
  etiqueta "DISSERTATIVA" e só o botão da resolução. Isso não é defeito: 420 das
  questões são de 2ª fase e são assim por natureza.

/estudar/assuntos — "O QUE MAIS CAI"
Deixa de responder "o que já caiu" e passa a responder "o que estudar": lista de
tópicos ordenada por importância, cada um com a fatia da prova, a tendência
(subindo ou caindo na banca, com os dois números visíveis) e o meu acerto.

/estudar/listas — MINHAS LISTAS
Lista de listas, cada uma com título, contagem e data. Uma lista aberta mostra
seus cartões e um botão "TREINAR ESTA LISTA".

SESSÃO DE TREINO — a tela que o botão "COMEÇAR" da aba Hoje abre
Não é a lista do banco. É uma fila, uma questão por vez, em tela cheia, SEM
barra de navegação inferior e sem o botão do Tio Léo.
- No topo: um X à esquerda, uma barra de progresso fina ocupando a largura
  (preenchida na cor DADO), e "5/12" à direita.
- Abaixo, em maiúscula pequena: "TERMODINÂMICA · IME 2016".
- A imagem da questão, ocupando o máximo de largura possível.
- Quatro a cinco alternativas empilhadas, cada uma um bloco tocável de altura
  confortável com a letra num quadrado à esquerda e o texto ao lado, com a
  borda de 4px embaixo. A selecionada ganha borda na cor DADO e a letra
  preenchida.
- Na base, um botão primário "RESPONDER" ocupando a largura.
- Estado de resposta certa: a alternativa correta fica preenchida na cor DADO e
  surge uma faixa na base com "Você acertou", a resolução resumida e o botão
  "PRÓXIMA".
- Estado de resposta errada: a escolhida fica vazada com fio ALERTA, a correta
  fica preenchida, e a faixa da base diz qual era e oferece "Ver a resolução"
  além de "PRÓXIMA".
- ⚠️ NUNCA mostre XP nesta tela, em nenhum estado. Treino não pontua — só o
  simulado pontua — e um "+20 XP" aqui contradiz a regra central do produto.

FIM DA SESSÃO: uma tela de resumo com quantas questões, quantas o aluno acertou,
os assuntos que apareceram, e uma linha dizendo o que isso mudou no plano dele.
Um botão "Voltar para Hoje" e um secundário "Treinar mais". Sem XP, sem
confete — a celebração grande é reservada ao simulado.

PROVAS
- HERO: último simulado — nome, nota grande, delta vs. o próprio padrão, e três
  leituras (aplicado em, posição, percentil).
- HEATMAP "MATÉRIA POR CICLO": grade 5×5, intensidade de azul codificando a
  nota, célula abaixo do corte vazada com fio coral. Legenda pequena.
- Lista de todos os simulados: rótulo, data, nota e delta.
- Ficha de um simulado (rota filha): nota, comparação com a turma, e a lista de
  questões marcando certa / errada / em branco. Botão para o PDF da prova.

JORNADA
- HERO "ONDE VOCÊ ESTÁ": três faixas empilhadas (RISCO, CINZENTA, TOP) como
  contornos, com um ponto marcando o aluno, a fronteira dourada rotulada
  "CORTE 8,0" e uma linha de cota com a distância. A faixa RISCO é vazada.
- "SUA TRAJETÓRIA": linha ao longo dos ciclos C1..C5 contra a linha de corte,
  com o cruzamento marcado, e a média da turma tracejada.
- Cartão da LIGA: "Liga Ouro · 6º de 34 · faltam 262 XP para subir" + "VER".
- CONQUISTAS: 4 medalhas quadradas, as travadas vazadas com barra de progresso.
- Cartão "DE QUEM JÁ PASSOU": depoimento de aprovados. Não invente citações —
  use o cartão como afordância com um link "Ler".

LIGA (rota /liga, alcançada pelo cartão da Jornada — NÃO é uma aba)
- Cabeçalho com o escudo, "Liga Ouro", "TERMINA COM O CICLO · 34 PARTICIPANTES".
  A liga é por CICLO, não por semana: o XP só se move quando sai nota.
- 10 linhas com posição, marca do participante e XP do ciclo, com zonas de
  subida e descida marcadas por fios verde e coral, e a linha do próprio aluno
  destacada com a palavra "VOCÊ".
- ⚠️ ANÔNIMA: nenhum nome, nenhuma inicial, nenhum apelido. Cada participante é
  um glifo geométrico. É restrição de privacidade de menores, não estética.

EXTRATO DE XP (rota /provas/:id/extrato, aberta ao tocar o simulado mais recente)
Esta tela NÃO tem imagem de referência. É o momento mais forte do produto: o
aluno vê, item por item, de onde vieram os pontos dele.
- Cabeçalho com o simulado e o total ganho, em MAGNITUDE, muito grande.
- Uma lista de linhas, cada uma com o rótulo do evento, o valor em ouro à direita,
  e uma linha secundária dizendo o que foi verificado. Por exemplo:
  "Compareceu / +100 / presença confirmada"
  "Matemática acima do corte / +40 / 6,8 · corte 4,0"
  "Física acima do corte / +40 / 7,4 · corte 4,0"
  "Química abaixo do corte / +0 / 3,2 · faltaram 0,8"  ← linha VAZADA, sem ouro
  "Passou na régua completa / +200 / critério Tio Leo"
  "Superou seu padrão / +100 / +0,7 acima da sua média"
  "Top 50 da escola / +150 / 47º de 312"
- As linhas que não pontuaram aparecem VAZADAS e com +0, nunca somem: é onde o
  aluno entende o que faltou, e é a única tela que explica a régua de corte sem
  parecer boletim.
- Ao fim, o total e o quanto ele subiu na liga.

TIO LÉO — o mentor, presente em todas as abas
O botão flutuante existe sobre todas as telas: um círculo com uma faísca, no
canto inferior direito, acima da barra de navegação e respeitando a safe area.
Tocá-lo abre a folha do Tio Léo.

A FOLHA. No celular é um bottom sheet com três alturas — espiada (só o campo de
escrita e uma linha de sugestão), meio (metade da tela, o padrão) e cheio. A
folha tem 24px de raio nos cantos de cima, uma alça curta e centrada no topo
para arrastar, e o fundo atrás dela escurece. Um artefato grande empurra a folha
para "cheio" sozinho. No desktop não é folha: é um painel lateral de 400px à
direita, e a página continua utilizável.

O CABEÇALHO DA FOLHA: um círculo com a faísca, o nome "Tio Léo" e, abaixo em
minúsculo, "mentor de estudos". À direita, um ícone de histórico de conversas e
um X.

AS MENSAGENS. Duas formas bem distintas:
- do aluno: um balão alinhado à direita, preenchido na cor DADO, com o texto em
  near-black, raio 18px com o canto inferior direito menor;
- do Tio Léo: SEM balão. Texto solto sobre o fundo da folha, alinhado à
  esquerda, largura total. É o que dá peso à resposta e deixa o artefato
  respirar.

ENQUANTO ELE PENSA: três pontos pulsando na cor DADO. Quando ele consulta um
dado, aparece acima da resposta uma linha discreta em maiúscula pequena com um
ícone de check — "CONSULTEI SUAS NOTAS DO CICLO 4" — que é o rastro da
ferramenta, não decoração: o aluno precisa saber que o número veio do sistema e
não da cabeça do modelo.

FÓRMULAS aparecem dentro do texto, renderizadas de verdade — fração empilhada,
raiz com radical, índice e expoente, seta de reação química. Nunca como código
entre crases. Uma fórmula longa demais para a largura rola sozinha na
horizontal, dentro do próprio bloco, sem empurrar a folha.

ARTEFATOS são cartões dentro da resposta, com 16px de raio, 1px de borda e um
cabeçalho em maiúscula pequena. Cada um tem, no canto superior direito, um ícone
de expandir. Os tipos, e desenhe pelo menos três deles nos artboards:
- GRÁFICO: a distribuição de notas do simulado, com uma marca destacada na
  posição do próprio aluno e o rótulo "VOCÊ";
- QUESTÃO: a imagem da questão de prova, o vestibular e o ano em maiúscula
  pequena, o gabarito, e um botão "Ver a resolução";
- EXTRATO: as linhas de XP do último simulado, com as que não pontuaram vazadas
  e com +0;
- MINHAS MATÉRIAS: as barras contra a linha de corte;
- PROVA: capa com nome, data e um botão "Abrir a prova" — nunca o PDF embutido;
- LISTA DE QUESTÕES: três linhas com assunto e um botão "Treinar".

ARTEFATO EXPANDIDO: tela cheia, sobre a folha, com um X no topo. É onde a
questão e o gráfico ficam legíveis num aparelho de 390px.

ESTADO VAZIO, a primeira abertura: a faísca grande, "Oi, Rafael", uma linha
dizendo o que ele faz — "Eu vejo suas notas, seus erros e o que mais cai nas
provas" — e quatro sugestões tocáveis, cada uma uma pílula com borda de 1px:
"Como fui no último simulado?", "O que eu mais erro em Química?", "O que estudar
hoje?", "Quanto falta pro meu corte?".

ESTADO DE ERRO: uma linha no lugar da resposta dizendo o que houve e o que
fazer, com um botão "Tentar de novo". Sem pedir desculpa e sem ser vago.

⚠️ NUNCA DESENHE, em nenhum artboard do Tio Léo: link externo ou URL visível
(proibido no produto — é vetor de phishing para menores), nota nominal de um
colega (só agregado da turma e a marca do próprio aluno), PDF renderizado dentro
da conversa, ou botão de compartilhar.

LOGIN
- É a ÚNICA tela do produto que pode ser ilustrada. Ilustração vetorial chapada:
  horizonte ao amanhecer, pista em perspectiva, uma linha dourada contínua no
  horizonte (a mesma linha de corte de todas as outras telas) e um planador
  subindo acima dela deixando um rastro pontilhado que É uma curva de nota.
- Gancho de retorno: "Sua sequência de 12 dias está esperando", com a corrente.
- Formulário: matrícula e senha, botão "ENTRAR", botão secundário "Entrar com o
  Canvas", links "Primeiro acesso" e "Esqueci a senha".

# OS DADOS REAIS — use estes tipos nos mocks

São os tipos TypeScript que o front já usa hoje contra a API. Se os seus dados
de exemplo tiverem exatamente esta forma, trocar mock por fetch depois é uma
linha por tela.

    export interface SimuladoDoAluno {
      id: string; nome: string | null; rotulo: string | null;
      dataAplicacao: string | null; tipo: string | null; materia: string | null;
      nota: number;
      deltaSelf: number | null;   // diferença para a própria média histórica
      mediaGeral: number | null; nPresentes: number;
      cicloId: string | null; cicloOrdem: number | null;
      vestibularAlvo: string | null; novo: boolean;
    }

    export interface GruposComparacao {
      voce: number | null; geral: number | null;
      top15: number | null; bottom15: number | null;
    }

    export interface DetalheSimuladoAluno {
      id: string; nome: string | null; rotulo: string | null;
      dataAplicacao: string | null; tipo: string | null; materia: string | null;
      vestibularAlvo: string | null; nota: number; deltaSelf: number | null;
      posicao: number; total: number; percentil: number;
      grupos: GruposComparacao | null;
    }

    export type ResultadoQuestao = 'correta' | 'errada' | 'em_branco';

    export interface QuestaoDoAluno {
      posicao: number | null; resultado: ResultadoQuestao;
      textoResumo?: string | null; assunto?: string | null;
      alternativaCorreta?: string | null;
    }

    export interface QuestoesDoSimulado {
      temGabarito: boolean; temMinhasRespostas: boolean;
      questoes: QuestaoDoAluno[];
      acertos: number; erros: number; emBranco: number;
      duracaoMediaSegundos: number | null;
    }

    export interface EvolucaoAluno {
      ciclos: Array<{ label: string }>;
      materias: Record<string, { aluno: Array<number | null>; turma: Array<number | null> }>;
    }

    export interface Streak { count: number; label: string; }

    export interface InsightDoAluno {
      disponivel: boolean; cicloOrdem: number | null;
      cicloNome: string | null; bullets: string[];
    }

Tipos que ainda NÃO existem na API e que você vai criar como mock — mantenha
estes nomes, eles já estão acordados:

    export interface Sequencia {
      simulados: number;         // simulados consecutivos sem faltar
      melhor: number;            // recorde
      ciclo: boolean[];          // um por simulado do ciclo: compareceu?
      proximoEm: string | null;  // data ISO do próximo simulado
    }

    export interface Xp { total: number; ciclo: number; }

    export interface LinhaExtrato {
      rotulo: string;            // "Matemática acima do corte"
      xp: number;                // 0 quando não pontuou — a linha ainda aparece
      evidencia: string;         // "6,8 · corte 4,0" — o que foi verificado
    }

    export interface ExtratoXp {
      simuladoId: string; simuladoNome: string;
      linhas: LinhaExtrato[]; total: number; posicaoLiga: number | null;
    }

    export interface AssuntoPrioritario {
      topicoCodigo: string; nome: string; materia: string;
      importancia: number;   // 0..1 — fatia da prova, ponderada por recência
      meuAcerto: number;     // 0..1
      tendencia: number;     // + subindo na banca, − caindo
      nQuestoes: number;     // base amostral; abaixo de 3 não entra no ranking
    }

    export interface MissaoDoDia {
      topicoCodigo: string; nome: string; materia: string;
      quantidade: number; razao: string; xpPrevisto: number;
    }

    export interface QuestaoDoBanco {
      id: string;                     // 'ita_2019_fase1_q01' — legível e estável
      vestibular: 'ITA' | 'IME'; ano: number; fase: 1 | 2;
      materia: string; numero: number;
      dissertativa: boolean;          // 2ª fase: sem alternativa e sem gabarito
      imagemUrl: string | null;       // o enunciado é IMAGEM, não texto
      gabarito: string | null;        // letra A–E, ausente nas dissertativas
      resolucaoUrl: string | null;
      topicos: Array<{ codigo: string; nome: string; confianca: 'alta' | 'media' | 'baixa' }>;
      alternativas: Array<{ letra: string; texto: string }>;
      resolvida: boolean; anotacao: string | null;
      alternativaEscolhida: string | null; acertou: boolean | null;
    }

    export interface SessaoTreino {
      topicoNome: string; materia: string;
      questoes: QuestaoDoBanco[];
      indiceAtual: number; acertos: number;
    }

    export interface PosicaoLiga {
      posicao: number; glifo: string; xpSemana: number; euMesmo: boolean;
    }

# O QUE ENTREGAR

Um mockup NAVEGÁVEL de verdade: os quatro itens da navegação trocam de tela, o
cartão da liga abre a liga, um simulado da lista abre a ficha, e o botão do Tio
Léo abre a gaveta do chat. Nada de tela solta.

E um fluxo em particular precisa funcionar de ponta a ponta, porque é o mais
usado do produto e é o mais fácil de entregar pela metade:

    lista de questões → toca num cartão → a questão em tela cheia
                                        → "PRÓXIMA" anda para a seguinte
                                          DENTRO DO RECORTE DE FILTRO ATUAL
                                        → voltar retorna à lista NA MESMA
                                          POSIÇÃO DE ROLAGEM
    lista → "Filtrar" → a folha → toca pílulas → "VER N QUESTÕES"
                                        → a folha fecha e a lista atualiza
    lista → busca → resultados, ou o estado de "nada encontrado"

A paginação é por botão "CARREGAR MAIS", nunca rolagem infinita: o aluno tem de
voltar da questão para o mesmo ponto da lista, e rolagem infinita perde essa
posição.

⚠️ AS SEIS PRIMEIRAS SÃO OBRIGATÓRIAS E NÃO PODEM SER RESUMIDAS. Metade delas
é o banco de questões, que é o maior ativo do produto — 2.693 questões reais de
prova — e o único conteúdo que o aluno consome nos ~20 dias entre um simulado e
outro. Um mockup sem navegação entre questões, sem filtro e sem busca não é
avaliável.

Artboards, nesta ordem de prioridade:
1. Hoje — celular, tema noite
2. Estudar, A TELA INTEIRA: os três cartões de treinar E, abaixo, a busca, o
    botão Filtrar e a lista de questões — celular, noite
3. Uma questão em tela cheia, com a barra de anterior/próxima na base —
    celular, noite
4. A folha de filtros aberta sobre a lista — celular, noite
5. Sessão de treino, uma questão com alternativas — celular, noite
6. Sessão de treino, estado de resposta errada — celular, noite
7. Provas — celular, noite
8. Jornada — celular, noite
9. Login — celular, noite
10. Hoje — celular, tema dia
11. A mesma questão com o gabarito revelado e o campo de anotação — celular, noite
12. A lista com filtros ativos e as pílulas removíveis — celular, noite
13. Busca sem resultado — celular, noite
14. Extrato de XP — celular, noite. SEM imagem de referência; construa do texto
15. Tio Léo, folha em altura média com uma conversa — celular, noite
16. Tio Léo, folha cheia com um artefato de gráfico e uma fórmula no texto —
    celular, noite
17. Tio Léo, artefato de questão expandido em tela cheia — celular, noite
18. Tio Léo, estado vazio da primeira abertura — celular, noite
19. Hoje — desktop 1440x900, noite
20. Estudar, Provas e Jornada — desktop, noite
21. Tio Léo, painel lateral — desktop, noite
22. "O que mais cai" (/estudar/assuntos) — celular, noite
23. Liga — celular, noite
24. Celebração de cruzar o corte — celular, noite, tela cheia

Estados que precisam existir, porque é onde todo mockup mente:
- CARREGANDO: esqueleto com a forma do conteúdo, nunca um spinner.
- VAZIO: aluno sem simulado corrigido ainda, e aluno sem nenhuma questão
  resolvida. Tela vazia é convite para agir, com um botão, não um aviso triste.
- ERRO: diga o que houve e o que fazer. Sem pedir desculpa, sem ser vago.
- SEM COBERTURA: onde a análise por assunto não alcança Português, Inglês e
  Redação, a tela precisa dizer.

Piso de qualidade, sem anunciar:
- Celular primeiro. 390px é o alvo; nada pode transbordar a 360px.
- Todo campo com fonte de 16px, senão o iOS dá zoom ao focar.
- Alvo de toque mínimo de 44px.
- Foco de teclado visível em tudo que é interativo.
- `prefers-reduced-motion` respeitado — inclusive pela chama nervosa.
- `env(safe-area-inset-bottom)` na barra inferior.
- Contraste AA em todo texto. É o motivo de `--alu-valor-texto` existir.

Como entregar o código, para a importação ser rápida:
- React 19 + TypeScript. Sem CSS Modules — o projeto usa classes com prefixo por
  tela como namespace. Prefixe tudo com `alu-`.
- Um arquivo CSS por tela, com as custom properties num arquivo de tokens
  separado.
- Nomes de componente, arquivo, variável e classe em PORTUGUÊS.
- Comentário explica o PORQUÊ, nunca o quê. Uma decisão não óbvia sem comentário
  é uma decisão perdida.
- Roteamento com react-router-dom, rotas reais como listadas acima.
- Nenhuma dependência nova além de react, react-dom e react-router-dom.

# COMO USAR AS IMAGENS ANEXADAS

Elas fixam direção — paleta, peso tipográfico, densidade, onde o olho cai. NÃO
são gabarito de pixel, e o texto dentro delas está errado em vários pontos
porque todo gerador erra letra. Onde a imagem e este documento discordarem,
**este documento vence**.
```
