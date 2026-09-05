# Brief para o Claude Design — a aba Alunos

Terceiro ramo da coordenação, depois de
[brief-claude-design-provas.md](brief-claude-design-provas.md) e
[brief-claude-design-simulados.md](brief-claude-design-simulados.md).

Cole o bloco abaixo **na mesma conversa** em que o brief de `/provas` já foi
colado — ele conta com o sistema de design daquele (as sete regras do fim do
semáforo, os seis papéis de cor, os dois temas, o padrão de campo). Numa
conversa nova não se sustenta sozinho.

⚠️ **LGPD.** Este ramo é o que mais mostra dado pessoal de menor de idade —
nome, foto, e-mail, desempenho inteiro. Anonimize qualquer captura antes de
anexar (CLAUDE.md §6).

---

```
# O QUE VOCÊ VAI FAZER AGORA

O ramo ALUNOS tem duas telas, e o trabalho nelas é assimétrico:

    /alunos        a lista de 900          ← a mais NUA da coordenação
    /alunos/:id    a ficha do aluno        ← a mais BEM RESOLVIDA do produto

Não são dois redesenhos. A lista precisa de estrutura que ela nunca teve; a
ficha precisa de correções cirúrgicas e de você não estragar o que já está
certo. Leia a seção de cada uma antes de começar a desenhar qualquer coisa.

# A TENSÃO QUE ORGANIZA O RAMO

Em todo o resto do produto, uma nota é lida contra uma RÉGUA, e a régua é
escolhida: `tio-leo`, `ITA` ou `IME`. A tabela do ciclo tem um seletor. A
calibração tem. A comparação tem.

**A lista de alunos não tem.** Ela mostra uma coluna chamada "Zona" — top,
cinzenta, risco — que é uma leitura contra um corte, calculada com uma régua
que a tela nunca nomeia. E a ficha do aluno também não tem seletor, mas por um
motivo diferente e legítimo: o gráfico de evolução mistura ciclos de ITA e de
IME, e escolher um edital ali desenharia o corte errado em metade dos pontos.

Resultado: **o mesmo aluno pode ser lido de duas maneiras em duas telas, e
nenhuma das duas diz qual régua produziu o que está na tela.** O coordenador vê
"Zona: cinzenta" na lista e "abaixo do corte em Física" na ficha, e não tem
como saber se as duas frases estão falando da mesma régua.

R2 diz: *nunca se lê uma nota sem a régua ao lado*. Este ramo inteiro
desobedece. Resolver isso é o fio que costura as duas telas — e a solução não é
necessariamente colocar um seletor em cada uma; pode ser apenas **nomear**, com
honestidade, a régua que está em vigor, e a ficha já mostra como se faz: ela
imprime "régua Tio Leo" acima da barra de corte.

# TELA A · `/alunos` — a lista de 900

## O que ela é hoje

Título, subtítulo com a contagem, faixa de filtros (busca, turma, sede) e uma
tabela. Nada mais — sem KPIs, sem faixa de entrada, sem cards. É a tela mais
nua da coordenação e é um dos cinco destinos do menu principal.

Colunas: **Aluno** (avatar + nome) · Turma · Sede · Média · Tendência · Perfil ·
Zona · Trajetória · "Ver →".

Perfil, tendência e zona são as três classificações do produto:

    ZONA        top · cinzenta · risco          onde ele está contra o corte
    TENDÊNCIA   subindo · estável · caindo      para onde ele está indo
    PERFIL      âncora · mistério · regular     âncora = constante,
                                                mistério = variância alta

A tabela abre ordenada por ZONA, do risco para o topo.

## Os cinco problemas

**1 · A coluna "Trajetória" é uma mentira gráfica, e é o defeito mais grave
deste brief.**

Cada sparkline é desenhada na PRÓPRIA escala: o mínimo e o máximo são os
daquele aluno. Um aluno que oscilou entre 2,0 e 2,4 e um que subiu de 6,0 para
8,0 desenham **exatamente a mesma curva**. Novecentas linhas de uma forma que
parece comparável e não é.

Isso é a armadilha central deste produto na sua forma mais pura: um número
errado que não parece errado. E é pior numa coluna chamada "Trajetória", cujo
único propósito é comparação visual de relance.

Conserte com escala compartilhada — 0 a 10 para todas — e com a linha de corte
desenhada (R2). Uma trajetória inteiramente abaixo da régua e outra inteiramente
acima têm que ser distinguíveis sem leitura.

**2 · Cinco escalas semânticas na mesma linha.** Média (número), Tendência
(tag), Perfil (palavra), Zona (tag), Trajetória (gráfico). R7 diz: uma escala
semântica por tela — se uma coisa carrega a leitura, o resto fica neutro. Aqui
cinco disputam, e nenhuma ganha.

Decida qual carrega a varredura nesta tela e faça as outras ficarem quietas.
Zona e tendência dizem coisas parecidas de maneiras diferentes; perfil é a mais
sutil das três e a que menos gente entende.

**3 · A régua não aparece.** Ver a seção acima. A palavra "Zona" na tela não
tem, hoje, nada que diga contra o que ela foi calculada.

**4 · São 900 linhas sem paginação, sem virtualização e sem "carregar mais".**
Isso é decisão registrada do projeto e não vai mudar: um teto truncaria a
leitura em silêncio e as estatísticas ficariam erradas sem erro. Então a
ROLAGEM é a interação principal desta tela, e o desenho tem que assumir isso:
cabeçalho fixo, a contagem sempre visível, a posição na lista legível, e uma
densidade de linha que aguente 900 sem cansar.

**5 · Nada acima da tabela.** Sendo um dos cinco destinos do menu, ela chega
sem dizer nada antes da tabela. Decida se ela merece uma faixa de entrada —
e se merecer, aplique C1: perguntas, não objetos. "Quem entrou em risco desde
o último ciclo?" é uma pergunta; "Top 10" não é, e o card de melhores alunos é
justamente o que a regra proíbe: os melhores são os que menos precisam do
coordenador.

**Não transforme esta tela num hub de cards.** Ela responde a UMA pergunta —
quem são eles e como estão — e o padrão de campo entra onde uma tela mistura
perguntas diferentes. Aqui não mistura.

# TELA B · `/alunos/:id` — a ficha

## Comece pelo que está CERTO, e não mexa

Esta é a tela mais bem resolvida da coordenação. Quatro decisões dela já estão
no padrão que você deve preservar:

- **Duas colunas: principal + lateral de 320px.** A lateral existe porque esta
  é tela de LEITURA, não de varredura. As telas de varredura não têm coluna
  lateral, porque 320px sairiam direto da tarefa mais frequente do dia.
- **A barra de corte é literalmente a mesma peça que o ALUNO vê de si mesmo**,
  na área do aluno. É onde a coerência entre os dois produtos fica evidente, e
  é intencional.
- **O heatmap matérias × simulados já segue R1 e R3:** célula preenchida acima
  do corte, vazada abaixo, intensidade carregando a distância. Ele foi
  convertido antes das outras peças e serve de referência.
- **A ficha não tem seletor de régua, de propósito**, e o motivo é bom: a
  evolução mistura ciclos de ITA e de IME. Torne o motivo VISÍVEL em vez de
  esconder a ausência — hoje ela só imprime "régua Tio Leo" e não diz por quê.

## O que ela contém

    COLUNA PRINCIPAL
      cabeçalho: avatar grande, nome, "Turma 3A · Sede Aldeota · alvos: ITA, IME",
                 e o menu Exportar (cinco saídas)
      faixa de filtros do histórico (ciclo, fase, matéria)
      "Evolução do aluno" — gráfico em camadas, linha por matéria, corte em ouro
      "Histórico de simulados" — tabela compacta, editável
      "Heatmap matérias × simulados" — todo o histórico, ignora os filtros acima

    COLUNA LATERAL (320px)
      "Onde ele está"        barra de corte por matéria, com a régua nomeada
      "Classificações"       perfil · tendência · zona, como palavras
      "Perfis semelhantes"   tabela de alunos parecidos
      "Métricas internas"    três KPIs
      "Acesso do aluno"      texto explicativo + remover foto de perfil

## Os quatro problemas

**1 · "Perfis semelhantes" fala a língua do banco de dados.** O subtítulo, na
tela, para um coordenador pedagógico, diz:

    "kNN por vetor de features (média por matéria + desvio + tendência).
     12 resultados."

E a primeira coluna da tabela é **"Distância: 0,42"**.

Ninguém nesta escola sabe o que é kNN, e "distância 0,42" não significa nada
para quem decide chamar um aluno para conversar. A seção é útil — *"este aluno
se parece com estes, e aqueles melhoraram"* é uma informação de verdade —, mas
ela precisa ser dita em português. Reescreva o bloco inteiro: o título, o
subtítulo e o que cada coluna mostra.

⚠️ Cuidado com a linha vermelha do produto: **não vire um card de
recomendação que promete causalidade.** "Alunos parecidos com ele" é honesto;
"faça o que funcionou com eles" não é.

**2 · "Métricas internas" tem no nome a confissão.** Os três KPIs são "Média
recente", "Notas no histórico" e **"Janela: 9"** — que é o tamanho do vetor da
sparkline. É detalhe de implementação exposto como informação. Ou vira número
que significa alguma coisa para quem lê, ou sai.

**3 · Onze superfícies empilhadas.** Seis cards na coluna principal, cinco na
lateral, todos com a mesma borda, o mesmo raio e o mesmo peso. Numa tela de
leitura longa, isso vira listra. Estabeleça hierarquia dentro de cada coluna —
o que é a resposta e o que é o apoio.

**4 · Remover a foto de perfil usa o alerta nativo do navegador.** Um
`window.confirm` no meio de um produto que tem sistema de diálogo próprio, com
passo de confirmação e diff. É a única ação destrutiva da tela e é a única que
não usa a peça do sistema.

# O PROBLEMA DE PRODUTO — o mais importante das duas telas

O coordenador não abre a ficha de um aluno. Ele revisa os vinte que estão em
risco.

Hoje isso é: lista → rolar → clicar no aluno → ler → **voltar** → rolar até
onde estava → clicar no próximo. Quarenta navegações para vinte alunos, e a
posição na lista se perde a cada volta.

A única navegação lateral que existe é "Perfis semelhantes" — que leva a um
aluno parecido, e não ao próximo da lista que ele estava percorrendo. É útil
para outra coisa.

**Desenhe a revisão em sequência.** O recorte que a pessoa montou na lista
(turma 3A, zona de risco, ordenado pelo pior) deveria sobreviver à entrada na
ficha: "aluno 4 de 23", anterior e próximo, e a volta caindo no lugar de onde
saiu. Se a sua solução for outra, tudo bem — mas resolva o problema, porque ele
é o custo diário real deste ramo.

# LGPD — restrição de conteúdo, não de estilo

Esta é a tela que mais expõe dado pessoal de menor de idade: nome completo,
foto enviada pelo próprio aluno, e-mail, e o desempenho inteiro dele.

- Nos mocks, **nomes brasileiros inventados** e avatar como círculo com duas
  letras. Nenhuma foto de pessoa, em nenhum lugar.
- Não desenhe nada que exija asset, fonte ou serviço de terceiro. É a regra que
  tirou as fontes do Google Fonts deste projeto.
- A ficha imprime e exporta (PDF, PNG, CSV). Considere que o que você desenha
  pode sair da tela e virar papel na mesa de alguém.

# ESTADOS A DESENHAR

    /alunos       carregando · erro de carga · filtro sem resultado ·
                  aluno sem histórico (média e trajetória vazias — acontece
                      com quem entrou no meio do ano)

    /alunos/:id   normal · aluno não encontrado ·
                  aluno SEM simulado nenhum (gráfico, heatmap e barra de corte
                      sem nada — é o estado de quem acabou de entrar) ·
                  sem similares ("aluno ainda não tem features suficientes") ·
                  sem foto de perfil · erro ao salvar nota

O estado "aluno sem histórico" importa mais do que parece: ele é a chegada de
todo aluno novo, e hoje é uma sequência de peças vazias.

# O QUE ENTREGAR

1. **As duas telas, nos dois temas, em 1440×900.** A ficha também em 390×844 —
   é a tela que o brief mestre já pedia em celular.
2. **A coluna Trajetória consertada:** escala compartilhada, régua desenhada,
   mostrada em pelo menos seis linhas de exemplo que incluam um aluno todo
   abaixo do corte e um todo acima.
3. **A decisão sobre a régua**, aplicada nas duas telas: como a tela diz contra
   o que a Zona foi calculada, sem virar mais um seletor.
4. **O bloco "Perfis semelhantes" reescrito**, título e colunas, em português
   de gente.
5. **A navegação em sequência** entre alunos de um recorte, desenhada.
6. **Duas ou três linhas** dizendo qual das cinco escalas você escolheu para
   carregar a varredura da lista, e o que fez as outras quatro ficarem quietas.
```
