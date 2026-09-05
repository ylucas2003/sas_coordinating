# Brief para o Claude Design — a coordenação do SAS

Companheiro de [brief-claude-design-aluno.md](brief-claude-design-aluno.md).
Aquele criou o sistema; este o estende para a outra metade do produto.

Cole o bloco abaixo inteiro no Claude Design. Anexe, se tiver:

- capturas da coordenação de HOJE (Painel, Alunos, Ficha do aluno, Ficha de
  ciclo, Login) — são o **antes**, não a referência;
- capturas da área do ALUNO nos dois temas (Hoje, Provas, Jornada) — essas são
  a **referência de direção**, e valem mais que qualquer descrição aqui.

⚠️ **LGPD.** Toda captura da coordenação mostra nome de menor de idade. Anonimize
antes de anexar (nomes fictícios, avatares sem foto) — é a mesma regra que tirou
as fontes do Google Fonts (CLAUDE.md §6).

---

```
# O QUE VOCÊ VAI FAZER

O SAS tem dois produtos dentro do mesmo repositório: a ÁREA DO ALUNO, que já foi
desenhada e tem um sistema de design próprio, coerente e bem documentado; e a
COORDENAÇÃO, que é mais antiga e ficou para trás. Elas hoje não parecem o mesmo
sistema — namespaces de token isolados de propósito, regras que se contradizem
de frente, e uma delas sem tema escuro.

Sua tarefa tem duas metades. A primeira é **estender o sistema de design da área
do aluno para a coordenação**, resolvendo as contradições a favor do aluno. A
segunda é **estender o PADRÃO DE CAMPO** — a estrutura de cards-que-abrem-tela
que a aba Estudar do aluno usa, e que foi a coisa que mais reduziu poluição
visual na história do projeto — às telas da coordenação que hoje empilham
perguntas diferentes numa rolagem só.

Cinco telas mudam de estrutura, e não só de pele: Painel, Ficha do aluno, Ficha
de ciclo, Administração e Login.

Isto NÃO é "deixar a coordenação parecida com um app de jogo". A coordenação é
uma ferramenta profissional usada oito horas por dia para varrer 900 alunos. O
que se herda do aluno é o RIGOR — cor é papel, superfície tem borda e nunca
sombra, o numeral grande é o herói, o vazio é vazado — não a brincadeira.

# CONTEXTO — o que é este produto

O SAS acompanha ~900 estudantes do terceiro ano do ensino médio do Colégio Ari
de Sá (Fortaleza, Brasil) que se preparam para o ITA e o IME, as duas academias
de engenharia mais disputadas do país. Eles fazem simulados em ciclos ao longo
do ano; cada simulado é corrigido e vira nota de 0 a 10.

A coordenação é a metade da plataforma que a EQUIPE usa. A promessa dela, em uma
frase: **sinalizar o que merece atenção, em vez de esperar que o coordenador
saiba o que procurar.**

## Quem usa, e o que essa pessoa faz de verdade

Dois ou três coordenadores pedagógicos. Não são analistas de dados. O trabalho
real deles, em ordem de frequência:

1. **Varrer.** Abrir o painel do ciclo em curso e achar, entre 900 linhas, quem
   caiu, quem está abaixo do corte e em quantas matérias. É a tarefa dominante,
   e é ela que o desenho tem de servir primeiro.
2. **Descer num aluno.** Abrir a ficha, ver a trajetória, comparar com alunos
   parecidos, decidir se chama para conversar.
3. **Julgar a prova, não o aluno.** Quando a turma inteira vai mal, a pergunta é
   se a prova estava mal calibrada. Histograma, média, desvio.
4. **Operar.** Importar notas, conferir o que o Canvas sincronizou, agendar
   simulado, mandar lembrete para professor, criar acesso.

## O problema visual de hoje — o que você está consertando

- **Semáforo em tudo.** Verde/âmbar/vermelho aparecem ao mesmo tempo no KPI, na
  tag, na célula do heatmap, na barra do cartão de alerta e no delta. Cinco
  coisas gritando na mesma tela, e nenhuma delas ganha.
- **Duas réguas na mesma tela.** A célula da tabela usa o corte da régua em
  vigor, que o servidor calcula. Mas o KPI "Média geral" logo acima dela usa um
  ternário fixo — verde ≥ 7, âmbar ≥ 5 — que não tem relação nenhuma com o corte.
  O mesmo número pode estar verde em cima e vermelho embaixo.
- **Sombra em vez de borda.** Cards flutuam sobre o fundo com duas sombras
  empilhadas. É o que faz qualquer tela parecer template.
- **Sem tema escuro.** O aluno tem dois temas. A coordenação tem um. E o próprio
  documento de design da coordenação promete os dois desde o começo.
- **Numeral sem peso.** O KPI, que é a coisa mais importante da tela, é 32px em
  peso 700 — o mesmo peso do título ao lado dele.

## Vocabulário do domínio — use estes termos, são do produto

- CICLO: uma rodada completa de simulados, Fase 1 + Fase 2. ~5 por ano.
  Nomeados "Ciclo 4 · ITA · 2026".
- SIMULADO: uma prova. Tem fase (1 ou 2), matéria, data e nota de 0 a 10.
- FASE 1 / FASE 2: as duas fases do vestibular. A F1 é objetiva, a F2 discursiva.
- RÉGUA / CRITÉRIO: o conjunto de cortes em vigor. São TRÊS réguas e o
  coordenador escolhe qual está olhando: `tio-leo` (a pedagógica do colégio),
  `ITA` e `IME` (as do edital). **Todo aluno é avaliado contra ITA E IME.**
- CORTE: a nota mínima que a régua exige naquela matéria. 4,0 é o padrão. O
  Inglês da Fase 1 do ITA é a ÚNICA matéria ELIMINATÓRIA, com corte 5,0.
  O corte é o conceito central do produto e vira o elemento visual central:
  uma linha.
- ZONA: `top` · `cinzenta` · `risco`. Onde o aluno está contra o corte.
- PERFIL: `âncora` (constante) · `mistério` (variância alta) · `regular`.
- TENDÊNCIA: `subindo` · `estável` · `caindo`.
- SEDE e TURMA: os dois recortes organizacionais. Uma sede tem várias turmas.
- MATÉRIAS: matemática, física, química, português, inglês, redação.
- ALERTA: o cartão do painel. Sete categorias: QUEDA_RENDIMENTO,
  SUBIDA_ATIPICA, PROVA_MAL_CALIBRADA, MATERIA_EM_RISCO, DIFERENCA_ENTRE_SEDES,
  PANORAMA_CICLO, ZONA_TRANSICAO.
- BANCO: o acervo de questões reais de provas do ITA e do IME, classificadas
  por tópico do edital.
- CANVAS: o LMS do colégio, de onde vêm as notas e para onde vão os simulados.

## Idioma e escrita

TUDO em português do Brasil: rótulo, título, mensagem de erro, estado vazio, e
também nome de arquivo, componente, variável e classe CSS. É a convenção do
projeto inteiro, não preferência de exibição.

Número sempre com vírgula decimal ("6,4"). Nota sempre com uma casa. Sentence
case em título e botão. O único lugar com CAIXA ALTA é o rótulo de olho.

# A DECISÃO QUE ORGANIZA TUDO: o semáforo sai

Esta é a decisão mais consequente do brief e ela já está tomada. Leia inteira
antes de desenhar qualquer coisa.

**Não existe verde nesta interface. Não existe semáforo verde-e-vermelho.**

É a mesma regra da área do aluno, e pelo mesmo motivo declarado lá: o semáforo
era o que mais puxava a idade da tela para baixo. Mas na coordenação ela custa
mais caro, porque a cor não era decoração — era o mecanismo de varredura. Então
o que entra no lugar precisa varrer melhor, não só ficar mais bonito.

## Por que o semáforo era pior do que parecia

1. **Ele mistura duas comparações.** "Acima do corte" e "acima da média
   histórica" são perguntas diferentes e hoje as duas usam verde. O olho não
   sabe qual está lendo.
2. **Ele tem três baldes onde o dado é contínuo.** 3,9 e 0,4 são o mesmo
   vermelho. A distância do corte é a informação, e ela se perde.
3. **Ele não sobrevive ao daltonismo nem à impressão.** ~8% dos homens não
   distinguem verde de vermelho, e o dossiê do ciclo sai em PDF preto e branco.
4. **Ele deixa a régua invisível.** Pintar a célula esconde ONDE está o corte.

## O que entra no lugar — SETE REGRAS

Estas sete regras substituem, juntas, tudo o que o semáforo fazia. Elas são o
coração deste brief.

**R1 · PREENCHIDO É ACIMA, VAZADO É ABAIXO.**
A célula, a barra e o selo de nota acima do corte são PREENCHIDOS na cor DADO.
Abaixo do corte são VAZADOS — contorno sem preenchimento, fundo transparente.
A varredura deixa de ser leitura de matiz e vira leitura de FORMA: um aluno em
risco é uma linha de buracos numa grade cheia, e o olho acha um buraco mais
rápido do que acha um vermelho no meio de outros vermelhos. Funciona no
daltonismo e funciona impresso.

**R2 · A RÉGUA É OURO E ESTÁ SEMPRE DESENHADA.**
Toda escala de nota mostra a linha de corte, em OURO, rotulada. Nunca se lê uma
nota sem a régua ao lado. E o corte NÃO é sempre 4,0: o Inglês da F1 do ITA é
5,0 e eliminatório. Uma linha só para todas as matérias mentiria justamente
sobre a matéria que mais elimina — quando o corte da matéria diverge do
majoritário, ele vira um traço curto sobre a própria barra.

**R3 · A INTENSIDADE CARREGA A DISTÂNCIA.**
Acima do corte, a saturação do preenchimento cresce com a distância acima.
Abaixo, a espessura e a opacidade do contorno crescem com a distância abaixo.
Escala sequencial de MATIZ ÚNICO, ancorada no corte — nunca divergente de duas
cores. Isso devolve o contínuo que os três baldes jogavam fora.

**R4 · ALERTA SÓ NA ETIQUETA, NUNCA NA SUPERFÍCIE.**
Vermelho existe para dois casos e só dois:
  (a) a ETIQUETA que diz a distância abaixo do corte — "−1,4";
  (b) a FALHA OPERACIONAL — prova sem nota lançada, sync do Canvas falhou,
      aluno sem dado nenhum.
Nunca pinta linha de tabela, célula, cartão, barra ou número.

**R5 · A COMPARAÇÃO É CINZA.**
Média histórica, média da turma, simulado anterior, banda de meta, valor de
fundo: tudo REFERÊNCIA, cinza azulado, atrás do dado. Toda métrica vem com
referência comparativa — essa regra já existe no projeto e o semáforo a apagava.

**R6 · A ORDENAÇÃO FAZ O TRABALHO QUE A COR FAZIA.**
Se o olho não pode achar o aluno em risco pela cor, a tela tem de ENTREGÁ-LO.
Toda tabela de aluno abre ordenada por **distância do corte, ascendente** — o
pior primeiro — e o ordenador em vigor é visível e nomeado no cabeçalho.
Isto é mudança de produto, não de pele, e é o que torna a proibição do verde
viável em vez de temerária. Sem R6, as outras seis não bastam.

**R7 · SILÊNCIO: uma escala semântica por tela.**
Se o heatmap carrega a leitura, os KPIs e as tags acima dele ficam neutros. Duas
coisas gritando é o mesmo que nenhuma.

## O que a R1 significa na prática, célula a célula

    nota 8,7 · corte 4,0   →  ▉ preenchido, saturação alta
    nota 5,2 · corte 4,0   →  ▒ preenchido, saturação baixa
    nota 4,0 · corte 4,0   →  ▒ preenchido, mínimo — está NO corte, passou
    nota 3,6 · corte 4,0   →  ▢ vazado, contorno fino     + etiqueta −0,4
    nota 0,8 · corte 4,0   →  ▢ vazado, contorno grosso   + etiqueta −3,2
    sem nota               →  célula vazia com hachura diagonal, cinza
    ausente                →  glifo de ausência, cinza — NÃO é zero

A última linha importa: ausência e zero são coisas diferentes no domínio e a
interface nunca pode confundi-las.

# O SISTEMA DE DESIGN

## Regra mestra: cor é papel, nunca decoração

Seis papéis. Uma cor serve ao seu papel e a nada mais. Não invente cor nova.

| Papel      | Na coordenação é                                              |
|------------|---------------------------------------------------------------|
| ACAO       | o que se aperta: botão primário, link, aba ativa               |
| VALOR      | a RÉGUA — linha de corte, banda de meta, o critério em vigor   |
| DADO       | o valor medido: barra, ponto, linha, célula cheia, seleção     |
| REFERENCIA | a comparação: histórico, média da turma, prova anterior        |
| ALERTA     | só a etiqueta de distância e a falha operacional               |
| MAGNITUDE  | todo numeral grande                                            |

Cinco desses seis papéis são idênticos aos da área do aluno. A troca é uma só:
onde o aluno tem SEQUENCIA (a chama, a corrente de simulados), a coordenação tem
REFERENCIA. Faz sentido — o aluno precisa de hábito, o coordenador precisa de
comparação.

⚠️ **O ouro perde um segundo emprego.** Hoje o ouro é ao mesmo tempo acento
institucional e marca de "isto foi gerado por LLM". No sistema novo o ouro é a
RÉGUA e nada mais. A marca de conteúdo gerado passa a ser FORMA — um glifo mais
o olho "gerado" — nunca cor. Ver "A tarja de procedência".

## Dois temas, mesmos papéis

    /* DIA */
    --fundo: #FFFFFF;      --superficie: #F4F7FC;   --borda: #DCE6F7;
    --acao: #1B3F8B;       --acao-base: #12275A;    --acao-texto: #FFFFFF;
    --valor: #F2C94C;      --valor-texto: #B07D12;
    --dado: #2E6BE6;       --dado-claro: #7FB6FF;
    --referencia: #8A93A8; --alerta: #E0452F;
    --magnitude: #0F1B33;  --texto: #16233D;        --texto-2: #5C6883;

    /* NOITE */
    --fundo: #050A18;      --superficie: #0C1530;   --borda: #1B2B57;
    --acao: #FFCE3A;       --acao-base: #C79A16;    --acao-texto: #050A18;
    --valor: #FFCE3A;      --valor-texto: #FFCE3A;
    --dado: #2F6BFF;       --dado-claro: #7FB6FF;
    --referencia: #6E85B8; --alerta: #FF6B4A;
    --magnitude: #FFFFFF;  --texto: #E6EDFB;        --texto-2: #6E85B8;

São exatamente os valores da área do aluno, mais REFERENCIA, que é novo. Duas
trocas entre os temas são intencionais e a regra que as explica é uma só: **a
ação é sempre a cor de maior contraste com o fundo** — navy no dia, ouro na
noite. A magnitude acompanha. Todo o resto é constante entre os temas.

⚠️ Na noite, ACAO e VALOR são o mesmo amarelo. Isso é herdado e está certo para
o aluno, mas na coordenação cria um risco real: um botão e uma linha de corte no
mesmo gráfico ficariam indistinguíveis. **Resolva por forma, não por cor** — a
régua é sempre um traço fino tracejado com rótulo, o botão é sempre um retângulo
sólido com raio. Se ainda assim colidirem numa tela específica, a régua ganha o
ouro e o botão daquela tela vira fantasma (vazado).

⚠️ No dia a superfície leva borda de 2px; na noite, 1px. Mesma peça, dois temas —
quem troca é o token, não o componente.

## A arquitetura de tokens — como implementar sem quebrar 7.200 linhas

Hoje há dois conjuntos isolados de propósito: `--alu-*` (aluno) e `--color-*`
(coordenação). Eles não podem simplesmente virar um, porque ~7.200 linhas de CSS
e três geradores de documento leem `--color-*`. Desenhe pensando nesta pilha de
CINCO arquivos:

    paleta.css       os hexadecimais, UMA vez cada, sem semântica nenhuma
                     (--dia-*, --noite-*). É o que impede as cópias de divergirem.

    papeis.css       os seis papéis, mapeados por tema: --sas-acao, --sas-valor,
                     --sas-dado, --sas-referencia, --sas-alerta, --sas-magnitude.
                     Aqui vivem os três blocos de tema (padrão dia,
                     @media prefers-color-scheme: dark, [data-tema]).

    aluno.css        --alu-*  = alias dos papéis. Compatibilidade, some com o tempo.
    coordenacao.css  --color-* = alias dos papéis. Idem.

    documento.css    --doc-*: paleta FIXA CLARA, que NÃO responde a tema nenhum.
                     Só para os geradores de PDF/PNG. Ver "Armadilhas".

Assim o tema escuro é UMA decisão em UM arquivo, e não duas que vão divergir; e a
migração acontece tela a tela, sem um commit gigante que ninguém consegue revisar.

## Forma

- **Raio: três valores e só três.** 18px em superfície, 12px em elemento pequeno,
  999px em pílula. (Hoje são quatro — 10, 14, 16 e 18 — e ninguém sabe qual usar.)
- **Superfície: borda, NUNCA sombra flutuante.** É a regra que sozinha mais
  aproxima a coordenação do aluno. As duas sombras de card morrem.
  A superfície se separa do fundo pela borda e pelo tom, não pela profundidade.
- **A grade de fundo entra.** A mesma do aluno: grade quadrada de 24px, quase
  imperceptível, sob o conteúdo. É o que amarra os dois produtos na primeira
  olhada, antes de qualquer leitura.
- **A tecla, só no botão primário, a 3px.** `box-shadow: 0 3px 0 0 <acao-base>`,
  e ao ser pressionado desce 3px e perde a sombra. Sem blur, nunca. Todo o resto
  da interface é chapado — tecla em tudo deixa de significar "aperte aqui".
  4px como no aluno seria demais para quem clica trezentas vezes por dia; 0
  perderia a única peça de física do sistema.
- **Sem CAIXA ALTA em botão.** O aluno tem "COMEÇAR"; aqui é "Exportar".
- Alvo de toque mínimo 44px, inclusive nas pílulas de filtro.

## Tipografia

Plus Jakarta Sans, servida localmente, variável na faixa 200–800. É a mesma dos
dois produtos e já carrega o peso 800 — adotar MAGNITUDE não custa asset nenhum.

| Uso                  | Tamanho    | Peso | Observação                          |
|----------------------|------------|------|-------------------------------------|
| MAGNITUDE (KPI)      | 32–44px    | 800  | tracking −0.035em, tabular, lh 0.95 |
| Título de tela       | 26–28px    | 700  | sentence case                       |
| Migalha da topbar    | 19px       | 700  |                                     |
| Título de seção      | 16–17px    | 600  |                                     |
| Texto corrente       | 14–15px    | 400  | line-height 1.6                     |
| Rótulo e metadado    | 13px       | 400  | cinza                               |
| OLHO (eyebrow)       | 10px       | 700  | CAIXA ALTA, letter-spacing 0.12em   |
| Cabeçalho de tabela  | 12–13px    | 500  | cinza, sentence case                |
| Tag / pílula         | 12–13px    | 500  |                                     |

Regras:
- **O olho substitui o rótulo de KPI.** Hoje é 11px sentence case cinza; passa a
  ser o olho de 10px espaçado. É pequena a mudança e é enorme o efeito.
- **Numeral SEMPRE tabular.** Nota, média e contagem vivem em coluna; sem isso
  os dígitos dançam de linha para linha.
- Três pesos no corpo (400, 500, 600/700) mais o 800 exclusivo da magnitude.
- Sem negrito no meio de frase. Negrito é de título e rótulo.

## A tarja de procedência — unifique quatro dialetos em um

A coordenação hoje tem TRÊS marcas visuais diferentes para dizer de onde um
número ou um estado veio, e o aluno tem uma quarta:

    SeloCanvas       "no Canvas" · "enviando…" · "falhou no Canvas" · "só no SAS"
    SeloGravacao     a aula tem gravação
    InsightsPainel   "Geradas automaticamente a partir das estatísticas…"
    TarjaFonte       (aluno) MOCK · SEM ROTA

São quatro desenhos para a mesma pergunta: **de onde veio isto?** Desenhe UM
componente que responda a pergunta inteira, no canto da superfície, e que
funcione nos dois produtos. Ele carrega no mínimo:

    MEDIDO      veio de nota lançada. É o padrão e não precisa de marca.
    GERADO      veio do LLM. Glifo + o olho "gerado". Nunca ouro.
    DIVERGENTE  o SAS e o Canvas dizem coisas diferentes, e foi por escolha.
    PENDENTE    escrito aqui, o Canvas ainda não confirmou.
    FALHOU      o Canvas recusou.
    EXEMPLO     número de exemplo, o dado ainda não existe (o MOCK do aluno).

A regra que justifica isso existir: **quem lê o número e acredita é quem mais
precisa saber de onde ele veio.** É a razão pela qual a tarja do aluno passou a
aparecer também em produção, e ela vale igual para o coordenador.

## Densidade — a ÚNICA coisa que não se copia do aluno

O aluno lê uma coluna de 640px, uma coisa por vez, com ritmo generoso. A
coordenação varre uma tabela de 900 linhas por 14 colunas com a coluna do nome
congelada à esquerda. **O sistema é o mesmo; o RITMO não é.**

Não aplique o espaçamento do aluno na tabela. A tabela tem métrica própria:
linha de 40–44px, padding horizontal de 10–20px, fio entre linhas mais claro que
a borda do card — senão a tabela vira grade e o olho para em cada linha.

O que a coordenação herda do ritmo do aluno é o espaço ENTRE blocos, não o
espaço DENTRO da tabela.

# RESTRIÇÕES QUE NÃO SÃO NEGOCIÁVEIS

- **Nenhum asset de terceiro.** Sem CDN, sem Google Fonts, sem biblioteca de
  ícone remota, sem pixel de telemetria. Os dados são de menores de idade, e
  isso é regra de LGPD do projeto, não preferência. Ícones como SVG inline.
- **Nenhum gráfico com biblioteca.** Todos os gráficos do projeto são SVG
  escrito à mão. Chart.js e equivalentes estão fora por decisão registrada.
- **Nenhuma foto de pessoa em mockup.** Avatar é círculo com duas letras.
- **Nenhum nome real de aluno.** Invente nomes brasileiros plausíveis.
- **Nenhuma marca real de terceiro.** Nada de brasão do ITA ou do IME.
- **Proibidos:** pizza, donut, 3D, velocímetro, gradiente colorido, brilho, neon,
  sombra pesada, mais de 5 cores categóricas, visual de BI genérico.
- **Contraste WCAG AA em todo texto, nos dois temas.** O ouro puro reprova como
  letra sobre fundo claro: use `--valor-texto` sempre que o ouro for texto, e
  `--valor` só para traço e preenchimento.
- **Foco de teclado visível em tudo** — a coordenação é usada muito no teclado, e
  já existe atalho global "/" para a busca.
- Respeite `prefers-reduced-motion`.

# A ARQUITETURA — o casco e as superfícies

O casco fica como está estruturalmente; muda a pele. Ele já foi redesenhado
recentemente e a decisão é boa.

    RAIL à esquerda, 88px fechado / 228px aberto no hover e no foco.
    Cinco destinos, ícone sempre, rótulo quando aberto:
      Painel · Alunos · Provas · Banco · Administração
    Marca no topo, logo do colégio no rodapé.

    TOPBAR de 72px: migalhas à esquerda; busca global de aluno (atalho "/",
    navega para a ficha, é NAVEGAÇÃO); sino; avatar.

    <main> no resto.

⚠️ **Duas buscas, e elas não competem.** A da topbar é NAVEGAÇÃO — digite de
qualquer tela e vá para a ficha do aluno. A da barra de filtros é RECORTE —
peneira as linhas da tela em que você está. O desenho tem de deixar essa
diferença óbvia, porque hoje ela não é.

⚠️ **Não existe sidebar de filtros.** Filtro é uma FAIXA HORIZONTAL de pílulas
acima da tabela, em oito superfícies. A faixa colapsa sozinha quando passa de
uma linha e mostra, no lugar, o resumo do que está ativo. Um filtro em vigor
nunca pode ficar invisível.

⚠️ **A coluna lateral existe, mas não em toda tela.** A área do aluno tem uma
coluna direita de 320px com widgets persistentes, e ela funciona lá porque a
coluna central é de leitura, com 640px. Aqui a regra é outra e é simples:

    TELA DE LEITURA   ficha do aluno, ficha de ciclo, ficha de simulado
                      → coluna lateral de 320px, com o contexto que hoje vive
                        espalhado pelo cabeçalho: a régua em vigor, o ciclo, o
                        estado no Canvas, as ações e as entradas relacionadas.

    TELA DE VARREDURA painel, alunos, banco
                      → SEM coluna lateral. A tabela tem 14 colunas e o nome
                        congelado à esquerda; 320px do lado direito saem direto
                        da tarefa mais frequente do dia.

As superfícies, ao todo: Painel · Alunos · Ficha do aluno · Provas (duas abas:
Ciclos e Simulados) · Ficha de simulado · Ficha de ciclo · Banco · Importar ·
Auditoria · Calibração · Administração · Integrações · Sincronização de aulas ·
Login.

# O PADRÃO DE CAMPO — como uma tela pesada vira várias leves

Este padrão já existe no produto, na aba ESTUDAR da área do aluno, e é a coisa
que mais reduziu poluição visual em toda a história do projeto. Ele entra na
coordenação, e as regras abaixo são a razão de ele funcionar — copiar a
aparência sem elas dá um menu bonito e inútil.

A doença que ele cura está descrita no código que o criou: as duas metades da
tela antiga "misturavam o que fazer AGORA com o acervo inteiro na mesma
rolagem, e o acervo — que é a coisa grande — ficava abaixo da dobra". Uma
rolagem só, duas escalas de atenção, e a maior perdia.

## As cinco regras

**C1 · A DIVISÃO É POR PERGUNTA, NUNCA POR TIPO DE OBJETO NEM POR RECÊNCIA.**
Esta é a regra inteira; as outras quatro são consequência. Na aba do aluno os
três campos são "o material", "o mundo" e "você" — três perguntas diferentes, e
é isso que faz cada card ter um destino óbvio.

O erro que esta regra existe para impedir tem nome, e ele é sedutor: cortar os
campos por objeto ("último simulado", "último ciclo") ou por recorte ("melhores
alunos"). Ninguém abre a ferramenta querendo "o último simulado"; abre querendo
saber **se a prova estava boa**. O card certo é o da pergunta:

    ERRADO  "Último simulado"   →  CERTO  "A prova estava boa?"
                                          Física · P4 · 28/08
                                          média 4,2 · 38% abaixo do corte

    ERRADO  "Último ciclo"      →  CERTO  "Como está fechando?"
                                          Ciclo 4 · 5 de 6 provas aplicadas
                                          62 cortados · fecha em 6 dias

    ERRADO  "Melhores alunos"   →  CERTO  "Quem mudou de zona?"
                                          9 saíram do risco · 4 entraram

A terceira troca é a mais importante e vale o parágrafo: os melhores alunos são
exatamente os que menos precisam do coordenador. Um card de "melhores alunos" é
bonito e ninguém clica nele duas vezes. A promessa do produto é sinalizar o que
merece ATENÇÃO. (Reconhecimento e celebração são produto legítimo — mas é
produto do ALUNO, não da varredura, e não entra aqui.)

**C2 · O SUBTÍTULO É DADO VIVO, NÃO DESCRIÇÃO.**
"412 de 1.030 questões marcadas", nunca "veja seu progresso". É o que separa um
hub de um menu: cada card relata o próprio estado, e por isso a tela de entrada
já informa antes de qualquer clique.

E ele **não chuta**. Desenhe os três estados de cada card, sempre:

    carregando   o subtítulo genérico, sem número
    vazio        a frase que convida ("Comece a marcar o que já resolveu")
    com dado     o par, com o número real

Número fixo escrito no desenho envelhece calado. Se o dado ainda não existe no
servidor, o card leva a tarja de procedência dizendo "exemplo".

**C3 · O DESTINO É TELA INTEIRA, COM URL PRÓPRIA.**
Não acordeão, não modal, não aba. É a separação de rolagens que faz o padrão
funcionar — cada campo passa a ter a página inteira para respirar, e a tela de
entrada volta a caber acima da dobra.

**C4 · A VOLTA É UM CHEVRON DE 44px NA MESMA LINHA DO TÍTULO.**
Nunca um "← Voltar" em linha própria acima do título: a 390px isso empurra o
título para fora da dobra, e o título é o que diz onde a pessoa está. É chevron
`‹`, não seta — a seta promete "desfazer", o chevron diz "subir um nível". O
nome acessível diz o DESTINO ("Voltar para Administração"), não "voltar".

**C5 · O ELO QUIETO, PARA O QUE NÃO MERECE UM CARD.**
O que precisa ser alcançável mas não é um campo vira um link discreto abaixo dos
cards, com contagem. E ele **some quando está vazio** — atalho para uma lista
vazia é convite para uma tela vazia. Some também quando a consulta FALHA: "0
pendências" para quem tem 34 é a mentira mais cara da tela.

## Anatomia do card de campo

    ┌──────────────────────────────────────────────┬────────┐
    │ OLHO EM CAIXA ALTA                           │        │
    │ Título grande                                │  SVG   │
    │ 27px · peso 800 · tracking −0.02em           │ 70×70  │
    │ subtítulo com dado vivo, 14px, texto-2       │ traço  │
    └──────────────────────────────────────────────┴────────┘

Superfície normal do sistema: borda, raio de 18px, sem sombra. Como é um bloco
tocável, ele afunda 2px ao ser pressionado — menos que a tecla de 3px do botão
primário, porque um card do tamanho de uma tela inteira afundando 3px parece
solto. O ícone é SVG em traço fino de 1.4, na cor DADO, decorativo: quem nomeia
o destino é o texto.

## Onde ele entra, e onde NÃO entra

Entra onde a tela junta perguntas diferentes numa rolagem só: **Administração**
(hoje quatro abas de ferramentas sem relação entre si) e **Ficha de ciclo** (a
tela mais densa do produto).

**Não** transforme o Painel num hub de campos. Na aba do aluno nenhum dos três
campos domina — eles são equivalentes. No Painel um campo domina esmagadoramente:
a varredura. Virar hub cobraria um clique a mais na tarefa mais frequente do dia,
todo dia. O que o Painel recebe é a FAIXA DE ENTRADA, descrita na tela 2.

# AS TELAS A DESENHAR

Oito telas e um kit. Desenhe cada uma **nos dois temas**, em 1440×900. Ficha do
aluno, Administração e login precisam também de 390×844.

## 1 · O KIT DE PEÇAS — faça primeiro

Uma prancheta com todas as peças, nos dois temas, porque é ela que garante que
as sete telas seguintes sejam o mesmo sistema:

- KPI com olho, magnitude e sufixo; variante com delta e referência cinza.
- Selo de nota: preenchido, vazado, no corte, sem nota, ausente.
- Cartão de alerta: tag de categoria, título, subtítulo, mini-visualização,
  link de ação. **Sem barra colorida de severidade** — a severidade vira ordem
  e etiqueta.
- Tag / pílula de filtro: repouso, hover, ativa, com contagem.
- Botão: primário com tecla de 3px, secundário fantasma, terciário link.
- Barra de filtros: aberta, colapsada com resumo, vazia.
- Tabela: cabeçalho, linha, linha de média da turma, coluna congelada, coluna
  de destaque, hover, ordenador visível.
- Heatmap: célula cheia, célula vazada, célula sem dado, agrupamento por ciclo.
- Histograma com a régua de ouro sobreposta e a curva de referência cinza.
- Linha de evolução com banda de referência e ponto do simulado anterior.
- Sparkline 80×32, traço 1.5px, sem eixo.
- Dot plot: a turma em cinza, o aluno em DADO, a régua em ouro.
- Tarja de procedência, os seis estados.
- Estado vazio: mensagem amigável + sugestão de ajuste do filtro.
- Esqueleto de carregamento: estrutura em cinza, nunca spinner.
- Avatar, migalha, aba, diálogo, folha lateral.
- **Card de campo** (C1–C2): olho, título de 27px/800, subtítulo com dado vivo,
  ícone de 70×70. Desenhe os TRÊS estados do subtítulo — carregando, vazio, com
  dado — lado a lado, porque é neles que o padrão costuma ser implementado
  errado.
- **Cabeça de campo** (C4): chevron de 44px e título na mesma linha.
- **Elo quieto** (C5): link discreto com contagem, e o estado em que ele some.
- **Card de entrada**: a versão baixa do card de campo, de ~110px, que vai na
  faixa do Painel — olho, uma linha de título, uma linha de números.

## 2 · PAINEL — redesenho

A tela mais importante e a que mais precisa. Hoje ela tem QUATRO ESTRATOS antes
de o olho chegar no dado: um cabeçalho com quatro controles (ajuda, ranking/A–Z,
fase, seletor de régua), a barra de filtros logo abaixo, a faixa de decisão, e
uma fileira de quatro KPIs. Só então a tabela alunos × matérias/fases.

⚠️ **Aqui a poluição se resolve por FUSÃO, não por divisão.** O cabeçalho de
controles e a barra de filtros são a mesma coisa — dois sistemas de recorte
empilhados — e devem virar um. A faixa de decisão e os KPIs também dizem a mesma
coisa em duas alturas. Meta: **um** estrato de recorte e **um** de resumo.

O que ela precisa responder, em ordem, sem rolagem:
1. Qual ciclo, qual fase, qual régua estou olhando. (O seletor de régua é
   estrutural, não um filtro qualquer — ele muda TODA a leitura da tela.)
2. Quantos alunos estão abaixo do corte, e em quantas matérias.
3. QUEM são eles — e aqui vale a R6: a tabela abre pelo pior.
4. O que mudou desde o simulado anterior.

Desenhe:
- **A faixa de entrada** — uma linha de três cards de entrada (~110px), acima do
  estrato de recorte, cortados por PERGUNTA conforme a regra C1: "A prova estava
  boa?" · "Como está fechando o ciclo?" · "Quem mudou de zona?". Cada um leva a
  uma tela que já existe (ficha do simulado, ficha do ciclo, a varredura já
  filtrada).

  ⚠️ Ela **rola para fora** — não é sticky. Você a vê ao chegar e ela some
  assim que o trabalho começa. É assim que o Painel ganha os cards sem cobrar
  espaço permanente da tarefa dominante. Mantenha-a em UMA linha e baixa o
  bastante para o cabeçalho da tabela ainda aparecer a 900px de altura.
- A faixa de identificação do recorte, com a régua em vigor em destaque e o
  corte que ela impõe por matéria visível ou a um clique.
- Os KPIs em MAGNITUDE, com olho, e cada um com sua referência cinza ao lado.
  Nenhum KPI colorido (R7 — a tabela abaixo é que carrega a leitura).
- A tabela, com a coluna do nome congelada, os selos preenchidos/vazados, a
  linha de média da turma, e o ordenador nomeado no cabeçalho.
- Os cartões de alerta, ordenados por severidade, sem barra colorida.
- Um bloco de leitura gerada por LLM, com a tarja "gerado".

## 3 · ALUNOS — a lista de 900

O teste de fogo da R1: uma tabela longa em que a varredura precisa funcionar sem
cor semântica. Mostre o comportamento de rolagem, o cabeçalho fixo, a barra de
filtros colapsada com resumo, e a busca de recorte.

## 4 · FICHA DO ALUNO — redesenho

Também em 390×844. É a tela em que o coordenador decide se chama o aluno para
conversar, e a que mais se aproxima do que o aluno vê de si mesmo — então é onde
a coerência entre os dois produtos fica evidente. Reuse a barra de corte da área
do aluno literalmente: as mesmas matérias contra a mesma linha de ouro.

Precisa ter: identificação e turma; as matérias contra o corte; a trajetória ao
longo dos ciclos com banda de referência; perfil e tendência como palavras, não
como cores; alunos similares; o histórico simulado a simulado; e as ações
(exportar dossiê, ver no Canvas, editar nota).

## 5 · FICHA DE CICLO — redesenho pelo padrão de campo

A tela mais densa do produto e a que mais sofre da doença que o padrão de campo
cura: hoje ela empilha, numa rolagem só, seis matérias × duas fases × histograma
× média × mediana × desvio × percentis × delta entre fases — com um toggle
"avançado" que já é uma tentativa pobre de esconder metade.

Aplique C1: três perguntas, três campos, três telas.

    CALIBRAÇÃO    "A prova estava boa?"
                  por matéria, F1 e F2: histograma com a régua de ouro, média,
                  mediana, desvio, percentis, e o delta entre as fases. É aqui
                  que vive todo o avançado de hoje — e ele deixa de precisar de
                  toggle, porque a tela é dele.
                  subtítulo vivo: "6 matérias · 2 fora do padrão histórico"

    RÉGUA         "Quem passou?"
                  a classificação do ciclo contra o critério em vigor, os
                  cortados, e quem mudou de zona desde o ciclo anterior.
                  subtítulo vivo: "62 de 900 cortados · régua Tio Léo"

    COMPARAÇÃO    "Onde estamos diferentes?"
                  sede × sede, turma × turma, e este ciclo contra o anterior.
                  subtítulo vivo: "2 sedes · 12 turmas · maior diferença 1,4"

O que fica na tela de entrada, acima dos três campos: a identidade do ciclo
(nome, vestibular, ano, datas, quantas provas de quantas já aplicadas) e no
máximo três KPIs em MAGNITUDE. Nada mais.

Elo quieto (C5): as pendências — "3 provas sem nota lançada", "1 simulado não
foi ao Canvas". Some quando não há nenhuma, e some também se a consulta falhar.

O dossiê do ciclo em PDF continua saindo desta tela, e ele é UM documento com
tudo — os campos dividem a leitura na tela, não o documento impresso.

## 6 · FICHA DE SIMULADO

Uma prova, uma matéria, uma data. Distribuição, quem faltou, quem zerou, o
estado no Canvas. É onde a tarja de procedência mais trabalha.

## 7 · ADMINISTRAÇÃO — redesenho pelo padrão de campo

Também em 390×844 — é a tela em que o padrão fica mais legível, e foi a 390px
que ele nasceu.

O caso mais limpo do brief: hoje ela é **quatro abas** de ferramentas sem relação
nenhuma entre si, que é literalmente o desenho que a aba do aluno substituiu por
cards. Vire quatro campos, cada um com subtítulo vivo:

    CONTAS       "Quem tem acesso"
                 "3 coordenadores · 1 sem entrar há 40 dias"

    AUDITORIA    "O que aconteceu"
                 "34 eventos hoje · 2 alterações de nota"

    INTEGRAÇÕES  "O Canvas está de pé?"
                 "última sincronização há 12 min · 2 simulados falharam"

    CALIBRAÇÃO   "Quanto vale cada assunto"
                 "meia-vida 18 meses · reordena o que o aluno vê"

⚠️ O subtítulo de Integrações é o que mais justifica a regra C2: hoje, para
descobrir que dois simulados falharam no Canvas, é preciso entrar na aba. Com o
dado vivo no card, a falha aparece na tela de entrada — que é onde uma falha
precisa aparecer.

Elo quieto (C5): a importação por planilha foi aposentada, mas a rota continua
existindo para explicar o que mudou. Ela é elo quieto, nunca um quinto card —
oferecer o card seria oferecer um caminho de escrita que o produto não tem mais.

## 8 · LOGIN — redesenho

Também em 390×844. Precisa **conversar com o login do aluno**, que já existe e
tem uma fachada modernista de cobogó — uma treliça de quadrados com o mesmo
ritmo da grade de fundo. Não é coincidência e não pode ser tratada como duas
decisões separadas: o login da coordenação é a mesma fachada, outro ângulo.

Duas portas, e elas são diferentes: a coordenação entra por e-mail e senha; há
também "Entrar com o Canvas" (SSO). O aluno entra SÓ pelo Canvas. Se alguém
digitar credencial de aluno aqui, a tela tem de dizer para onde ir.

# OS DADOS REAIS — use estes tipos e estes números nos mocks

    Aluno       nome, turma, sede, vestibular alvo (ITA | IME),
                zona (top | cinzenta | risco),
                perfil (âncora | mistério | regular),
                tendência (subindo | estável | caindo)

    Nota        0 a 10, uma casa decimal, vírgula. Pode ser nula (sem
                lançamento) e pode ser ausência — que NÃO é zero.

    Ciclo       "Ciclo 4 · ITA · 2026", Fase 1 + Fase 2, ~5 por ano

    Simulado    fase (1|2), matéria, data, nota, estado no Canvas
                (sincronizado | pendente | falhou | divergente)

    Critério    'tio-leo' | 'ITA' | 'IME'; corte por matéria, padrão 4,0;
                inglês F1 do ITA = 5,0 e ELIMINATÓRIO

    Stats       n, média, mediana, desvio, IQR, p10/p25/p75/p90, moda,
                assimetria, curtose, bimodal, % aprovados, % zona crítica

    Alerta      categoria (as sete acima), tag, título, subtítulo,
                tempo relativo, sparkline de 6 a 10 pontos, link

Escala e ordem de grandeza para os mocks parecerem reais:

    ~900 alunos · 2 sedes · ~12 turmas · 6 matérias · ~5 ciclos por ano
    média de turma tipicamente entre 3,8 e 6,2
    entre 25% e 45% dos alunos abaixo do corte em pelo menos uma matéria
    matemática e física puxam para baixo; português e inglês para cima

# AS ARMADILHAS — leia antes de entregar

**1 · O PDF não pode escurecer.** Três geradores de documento (PDF por
`window.print`, PNG por SVG→canvas, CSV) leem os tokens de cor em tempo de
execução para montar o nó fora da tela. Se os tokens da coordenação passarem a
responder ao tema, o coordenador que trabalha à noite gera um dossiê preto.
Por isso `documento.css` existe e é uma paleta clara FIXA: o documento impresso
não tem tema.

**2 · O servidor manda nome de cor.** Os tipos `Severidade` e `TomNota` são
literais `'verde' | 'ambar' | 'vermelho'`, calculados no backend a partir do
corte da régua em vigor. Banir o verde na tela NÃO é só CSS. A tradução certa,
que não exige mexer no backend agora:

    verde     → preenchido, saturação alta      (bem acima do corte)
    ambar     → preenchido, saturação baixa     (acima, mas na margem)
    vermelho  → vazado + etiqueta de distância  (abaixo do corte)
    cinza     → sem dado

O nome do campo continua sendo `tom`; o que muda é o que o front desenha com
ele. Renomear no backend é limpeza posterior, não pré-requisito.

**3 · A régua dupla que o redesenho mata de graça.** Existe hoje uma função no
front que decide a cor da média com um ternário fixo (≥7 verde, ≥5 âmbar), sem
relação nenhuma com o corte em uso — enquanto a célula da tabela logo abaixo usa
o corte de verdade. O sistema novo elimina essa função, porque não há mais cor
para ela produzir. Não a reintroduza sob outro nome.

**4 · A faixa de filtros mede a si mesma.** Ela colapsa quando o conteúdo passa
de uma linha, o que significa medir altura e reagir. Qualquer desenho que mude
a altura das pílulas mexe nesse laço. Mantenha a pílula com altura fixa.

**5 · O rail abre por CSS, não por estado.** `:has(.rail:hover)` e
`:focus-within`. Não desenhe nada que exija JavaScript para o rail abrir.

**6 · O Banco já foi construído duas vezes.** A tela do banco de questões existe
em duas implementações — uma para cada casco — porque a da coordenação é toda em
tokens da coordenação e não sobrevive ao tema escuro do aluno. O sistema
unificado é o que torna possível voltarem a ser uma só. Desenhe o Banco de modo
que a MESMA tela sirva os dois, mudando só o que a permissão esconde.

# O QUE ENTREGAR

1. **O kit de peças**, nos dois temas, como prancheta única.
2. **As sete telas**, nos dois temas, 1440×900 — e ficha do aluno, Administração
   e login também em 390×844.
3. **A folha de tokens**: a paleta crua, os seis papéis, os dois temas, e os
   aliases de compatibilidade. Em CSS, na estrutura de cinco arquivos descrita.
4. **Um documento curto de decisões** — o que você mudou em relação ao que
   existe, e por quê. Especialmente onde as sete regras da substituição do
   semáforo e as cinco do padrão de campo obrigaram a mudar comportamento, e não
   só aparência.

Onde este documento e qualquer imagem anexada discordarem, **este documento
vence, sempre**.
```
