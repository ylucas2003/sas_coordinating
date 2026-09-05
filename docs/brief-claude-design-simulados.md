# Brief para o Claude Design — do hub à prova específica

Complementar de [brief-claude-design-provas.md](brief-claude-design-provas.md).

Cole o bloco abaixo **na mesma conversa** em que o brief de `/provas` já foi
colado. Ele cobre as três telas que ficaram de fora da primeira entrega — o hub,
a lista de provas e a ficha de uma prova — e conta com o sistema de design
daquele brief. Numa conversa nova não se sustenta sozinho.

⚠️ **LGPD.** Qualquer captura anexada mostra nome de menor. Anonimize antes
(CLAUDE.md §6).

---

```
# O QUE VOCÊ VAI FAZER AGORA

Você desenhou a entrada do ciclo. Faltam as três telas do OUTRO caminho —
aquele que o coordenador percorre quando a pergunta não é sobre o ciclo, e sim
sobre UMA prova:

    /provas               o hub de dois cards            ← a bifurcação
    /provas/simulados     a lista de ~255 provas
    /simulados/:id        a ficha de uma prova           ← a mais densa das três

Elas ficaram de fora porque o briefing anterior deu vinte parágrafos à entrada
do ciclo e três linhas a cada uma destas. A culpa é do briefing. Aqui está a
densidade que faltava.

# A COLISÃO QUE ORGANIZA AS TRÊS TELAS — leia antes de desenhar

O ciclo tem um campo chamado CALIBRAÇÃO cuja pergunta é **"A prova estava
boa?"**. A ficha de simulado responde **exatamente a mesma pergunta**.

Isso não é um erro a corrigir. São duas alturas legítimas da mesma pergunta, e
o seu trabalho é fazer com que elas não pareçam duas respostas concorrentes:

    CALIBRAÇÃO do ciclo    "as provas DESTE CICLO estavam boas?"
                           doze histogramas em pequenos múltiplos, escala
                           compartilhada, comparação entre matérias e fases.
                           É a tela de ACHAR a prova estranha.

    FICHA DO SIMULADO      "esta prova aqui estava boa?"
                           um histograma grande, as quebras por matéria e por
                           sede, e as notas individuais.
                           É a tela de ENTENDER a prova que você achou.

Uma é o mapa, a outra é o lugar. Desenhe a passagem entre elas: da calibração
do ciclo se clica numa matéria e se cai aqui, e daqui se volta ao ciclo. O
histograma tem que ser reconhecidamente a MESMA peça nos dois tamanhos — se o
coordenador não reconhecer, ele vai achar que são dois dados diferentes.

# TELA A · `/provas` — o hub de dois cards

Dois cards de campo, nomes fixos pelo dono do produto: **"Ciclos completos"** e
**"Provas específicas"**.

    CICLOS COMPLETOS
    "4 ciclos · Ciclo 4 · ITA em andamento, fecha em 6 dias"

    PROVAS ESPECÍFICAS
    "255 provas · 3 sem nota lançada · 1 falhou no Canvas"

## O problema desta tela

Dois cards num monitor de 1440px é quase nada, e a saída fácil — dois
retângulos enormes centralizados — faz a tela parecer um menu de instalador.
É uma tela de BIFURCAÇÃO e ela precisa justificar a própria existência em
menos de um segundo de leitura.

A pergunta que o desenho tem que responder é: **por que alguém escolheria
"provas específicas" em vez de "ciclos completos"?** A resposta é o que separa
os dois cards de verdade:

- vai para o CICLO quem quer saber como um grupo de alunos está fechando
  contra a régua — é a leitura por PESSOA;
- vai para a PROVA quem quer saber se um instrumento de medida funcionou —
  é a leitura por INSTRUMENTO.

Os subtítulos vivos devem reforçar isso, não só contar objetos. E as pendências
operacionais ("3 sem nota lançada", "1 falhou no Canvas") pertencem ao segundo
card, porque falha de prova é problema de instrumento.

Desenhe os três estados de C2 (carregando · vazio · com dado). O estado vazio
desta tela é real: colégio no começo do ano, zero ciclos e zero provas.

# TELA B · `/provas/simulados` — a lista

~255 provas. Tabela: **rótulo curto** ("P17") com o selo do Canvas quando ele
não está normal · matéria · fase · vestibular · ciclo · data · média · mediana ·
σ · n · "Ver →". Botão primário: "Agendar simulado".

Filtros em faixa de pílulas: busca, vestibular, fase, ciclo, matéria, período.
A busca casa nome E rótulo curto — quem procura "P17" não digita o nome
inteiro, e quem procura "Termodinâmica" não sabe o rótulo.

## Duas coisas estruturais que você precisa desenhar

**1 · A tela tem DOIS conjuntos de natureza diferente.** Prova agendada (data
no futuro) não tem média, mediana, desvio nem n — ela ainda não aconteceu.
Misturá-la na tabela principal faria a tela parecer quebrada, com quatro
colunas vazias em algumas linhas. Por isso elas vivem numa seção própria,
acima.

Uma prova agendada tem outras coisas: data, matéria, fase, se já foi ao Canvas,
e a possibilidade de ser desmarcada. É um objeto com outro estado de vida.
**Desenhe as duas seções como parentes, não como irmãs gêmeas** — e resolva o
caso de zero agendados, que é o normal na maior parte do ano.

**2 · Existe um calendário anual que começa escondido.** É uma grade do ano
inteiro marcando os dias com prova, e o coordenador liga quando quer ver o
ritmo de aplicação — "estamos concentrando provas demais em setembro?". Hoje é
um toggle. Decida se ele merece ser mais que isso, e desenhe-o: é a única peça
do produto que mostra o CALENDÁRIO em vez da tabela.

# TELA C · `/simulados/:id` — a ficha de uma prova

A mais densa das três, e a que mais precisa de você. Hoje ela é **um único card
gigante com seis seções empilhadas dentro**, sem hierarquia nenhuma entre elas.

## O que ela contém

**Cabeçalho.** Nome da prova · selo do Canvas · "Fase 1 · aplicado em 14/08 ·
380 presentes". E botões que aparecem e somem conforme o estado:

    "✏ Editar simulado"          sempre
    "↑ Enviar ao Canvas"         só quando o estado é DIVERGENTE
    "↻ Tentar de novo no Canvas" só quando FALHOU
    "✕ Desmarcar"                só quando é prova do SAS e ninguém fez ainda

Uma barra de ações cujo conteúdo muda é um problema de desenho de verdade:
resolva onde as ações condicionais moram sem que a barra dance de tamanho a
cada prova aberta.

**Duas ressalvas que mudam o significado de tudo na tela.** Uma prova pode ser
`anulada`, e pode estar `fora das estatísticas`. A segunda vem hoje com um
parágrafo que é a melhor escrita do produto e está renderizado como subtítulo
cinza:

    "Esta prova não entra nas médias, nos histogramas nem nos alertas.
     As notas dela não representam desempenho. As notas individuais continuam
     abaixo, e continuam no histórico de cada aluno."

Isso não é uma nota de rodapé — é a informação mais importante da tela quando
ela existe. Se o coordenador não ler, ele vai comparar essa prova com as outras
e chegar à conclusão errada. **Desenhe isso como estado da tela inteira, não
como etiqueta.** E note a delicadeza: a prova está fora das médias mas as notas
individuais continuam valendo para o histórico de cada aluno. As duas metades
precisam aparecer.

**Cinco KPIs:** média · mediana · desvio padrão · presentes · ausentes.

**A distribuição.** Histograma com bins de 0,5 ponto, a linha de corte com a
zona reprovada sombreada, e a peça de gráfico em camadas do produto — leigo →
insight → estatística —, onde a camada estatística acrescenta KDE e eixo Y
absoluto. Esta ficha não escolhe régua: usa a do colégio, fixa.

**Quebra por matéria.** As provas irmãs aplicadas no MESMO DIA — média,
mediana, desvio, presentes, e a linha leva para a ficha daquela irmã. É como se
compara Física e Química do mesmo dia. Quando não há irmãs, a seção diz
"Simulado sem irmãos por matéria no mesmo dia".

**Quebra por sede.** Mesmas colunas, por sede.

**Notas individuais.** ~380 linhas: aluno · pontuação · "Ver →" · "Editar".
Quem está ausente aparece com uma etiqueta no lugar da nota. Clicar na linha
vai para a ficha do aluno; "Editar" abre o diálogo de nota.

## O que está errado nesta tela

**1 · Não há hierarquia.** Seis seções de importância radicalmente diferente
têm exatamente o mesmo peso visual, dentro de um card só. A distribuição é a
resposta à pergunta da tela; as notas individuais são um anexo de 380 linhas; e
as duas parecem igualmente importantes. Estabeleça a hierarquia.

**2 · O histograma ainda tem semáforo, e ele contamina duas telas.** As linhas
verticais são desenhadas assim hoje:

    média    → VERMELHO
    mediana  → ÂMBAR
    corte    → ouro

A média não é um alerta: ela é REFERÊNCIA, e R5 diz que referência é cinza,
atrás do dado. Vermelho está reservado para a etiqueta de distância e para a
falha operacional (R4). Do jeito que está, o olho lê a média como um problema.

Isso importa em dobro porque **o mesmo componente desenha os doze histogramas
da CALIBRAÇÃO do ciclo**. Consertar aqui conserta as duas telas; deixar passar
mantém um vermelho gritando doze vezes lá.

**3 · Ausência está pintada de âmbar.** Na tabela de notas, quem faltou aparece
com uma etiqueta âmbar. Ausência não é um estado ruim — é AUSÊNCIA DE DADO, e o
sistema já tem forma para isso: cinza, glifo, e nunca confundida com zero. Um
âmbar ali diz "atenção, quase ruim", que é justamente a leitura errada.

**4 · A tabela de notas tem duas colunas de cabeçalho vazio** ("Ver →" e
"Editar" penduradas sem rótulo), e a linha inteira já é clicável. Três alvos de
clique concorrentes na mesma linha, um deles invisível.

# ESTADOS A DESENHAR

    /provas               vazio (nenhum ciclo, nenhuma prova) · carregando · com dado
    /provas/simulados     com agendados · SEM agendados (o caso comum) ·
                          calendário aberto e fechado · filtro sem resultado
    /simulados/:id        normal · ANULADA · FORA DAS ESTATÍSTICAS ·
                          sem notas lançadas ainda (a prova aconteceu, o
                              Canvas não trouxe: cinco KPIs em travessão) ·
                          sem irmãs por matéria · Canvas falhou · não encontrada

O estado "sem notas lançadas" é o mais frequente logo depois de uma aplicação,
e hoje ele é cinco travessões e um gráfico vazio. É a mesma doença do ciclo sem
provas que você já resolveu — resolva aqui do mesmo jeito.

# O QUE ENTREGAR

1. **As três telas, nos dois temas, em 1440×900.**
2. **A ficha de simulado em DOIS estados adicionais:** "fora das estatísticas"
   e "sem notas lançadas".
3. **O histograma corrigido** — média e mediana como REFERÊNCIA, o corte em
   ouro —, mostrado nos dois tamanhos: grande na ficha da prova, pequeno no
   múltiplo da calibração do ciclo. É a peça que amarra este brief ao anterior.
4. **A barra de ações condicionais** do cabeçalho, nos quatro estados.
5. **Duas ou três linhas** sobre como você separou as duas leituras de "a prova
   estava boa?" — o mapa e o lugar — sem que pareçam respostas concorrentes.
```
