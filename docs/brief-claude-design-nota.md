# Brief para o Claude Design — o diálogo de nota

Complementar de [brief-claude-design-provas.md](brief-claude-design-provas.md).

Cole o bloco abaixo **na mesma conversa** em que o brief de `/provas` já foi
colado — ele conta com o sistema de design daquele (as sete regras do fim do
semáforo, os seis papéis de cor, os dois temas) e com a tabela desenhada na
tela 3. Numa conversa nova ele não se sustenta sozinho.

⚠️ **LGPD.** Qualquer captura anexada mostra nome de menor. Anonimize antes
(CLAUDE.md §6).

---

```
# O QUE VOCÊ VAI FAZER AGORA

Uma peça só, e ela é a mais delicada do ramo: **o diálogo que abre ao clicar
numa nota da tabela.**

É a única superfície de ESCRITA de todo o brief. Tudo o mais que você desenhou
até aqui é leitura — alguém varrendo, comparando, julgando. Aqui alguém
digita, e o que digita se propaga para a média do aluno, a média da turma, a
estatística do simulado, o ranking do ciclo, a classificação contra a régua e,
se ele escolher, para o Canvas — o sistema de arquivo do colégio.

O diálogo existe, funciona e está em produção. Não é um esboço. O que está
errado nele é específico e está listado abaixo.

# COMO ELE FUNCIONA HOJE

## São dois diálogos irmãos, com o mesmo motor

    FICHA DE NOTA (largo)     abre da TABELA do ciclo, clicando numa célula.
                              Traz 6 KPIs de comparação com a turma + campos.

    EDIÇÃO DE NOTA (estreito) abre da ficha do aluno, clicando numa linha do
                              histórico. Só os campos.

Os dois compartilham o formulário, a validação e o fluxo. Trate-os como UMA
peça em dois tamanhos, não como duas peças.

## O fluxo tem três passos

**Passo 1 · Formulário.** Dois campos e nada mais:

    ☐ Presente na prova
    Pontuação  [ 14 ]   de 20 questões

O campo de pontuação recebe o foco automaticamente quando o aluno está
presente; quando está ausente, o foco vai para o checkbox — é o campo que a
pessoa provavelmente quer mexer. Desmarcar "presente" limpa a pontuação e
desabilita o campo.

**Passo 2 · Diff.** O mesmo card troca de conteúdo e mostra o que vai mudar:

    Confirmar as seguintes alterações?

    Pontuação    12  →  14
    Presente     Não →  Sim

Este passo existe por um motivo declarado: toda edição aqui altera nota de
aluno, e nota se propaga para estatística e ranking. Ver o que vai mudar antes
de confirmar é o que pega o erro de digitação silencioso. **Não elimine este
passo.**

**Passo 3 · A pergunta do Canvas**, dentro do mesmo diff:

    E no Canvas?
    ◉ Enviar agora — atualiza a nota da submission do aluno no Canvas.
    ○ Deixar só no site — o Canvas fica diferente, e isso aparece marcado aqui.

    [← Voltar]              [Confirmar e enviar ao Canvas]

O rótulo do botão primário muda conforme o rádio escolhido. Quando a operação
é irreversível (apagar um simulado leva as submissions junto), o botão vira
vermelho e o texto ganha "Irreversível". Essa escolha é obrigatória por
decisão de produto — o coordenador decide, a cada ação, se a mudança sobe.

## Os 6 KPIs de comparação (só na versão larga)

    Posição   #43 / 380      Nota      7,0      Acertos    14 / 20
    Média     5,2            Top 15%   8,4      Bottom 15% 2,1

# O QUE ESTÁ ERRADO — cinco defeitos, em ordem de gravidade

## 1 · O semáforo sobreviveu aqui, e só aqui

Este é o defeito grave e é a razão de este prompt existir.

Os KPIs de comparação são pintados por um ternário fixo:

    nota   ≥ 7  → verde ·  ≥ 5  → âmbar ·  resto → vermelho
    posição: top 15% → verde · metade superior → âmbar · resto → vermelho

**Isso é exatamente a "régua dupla" que o sistema baniu**: uma cor decidida por
um número mágico que não tem relação nenhuma com o corte da régua em vigor. Um
aluno com 6,5 numa matéria de corte 4,0 está confortavelmente aprovado e
aparece em ÂMBAR. Um aluno com 4,5 no Inglês F1 do ITA está REPROVADO — o
corte lá é 5,0 e é eliminatório — e aparece em âmbar também.

E o diálogo abre **por cima** da tabela, que já segue as sete regras: célula
preenchida acima do corte, vazada abaixo, com etiqueta de distância. O mesmo
aluno, o mesmo número, duas linguagens visuais separadas por 200 milissegundos.

**Redesenhe o bloco de comparação sob R1, R3 e R5.** A comparação com a turma é
o caso mais puro da R5 — média, top 15% e bottom 15% são REFERÊNCIA, cinza,
atrás do dado. A nota do aluno é DADO. E nenhum dos seis números tem direito a
uma cor que não venha do corte.

Sugestão que você pode recusar: os seis KPIs querem ser uma escala única — a
distribuição da turma com a régua desenhada e a posição do aluno marcada nela.
Seis números soltos numa grade é o desenho de quem não sabia o que comparar.

## 2 · A régua não está no diálogo

R2 diz: *nunca se lê uma nota sem a régua ao lado*. Este é o único lugar do
produto onde se **escreve** uma nota, e não há régua nenhuma à vista.

O coordenador digita "14 de 20" sem ver que o corte daquela matéria é 4,0 —
nem que naquela matéria específica ele é 5,0 e eliminatório. Traga o corte para
dentro, e faça o diálogo dizer, enquanto a pessoa digita, de que lado da régua
o número que ela está digitando cai.

## 3 · Duas unidades no mesmo diálogo, sem conversão à vista

Digita-se **pontuação bruta** ("14", de 20 questões). Lê-se **nota de 0 a 10**
("7,0"). O diff mostra bruto; a tabela atrás mostra 0–10; o KPI mostra os dois.
Nada na tela faz a conta à vista da pessoa.

Resolva. Quem digita 14 tem que ver 7,0 aparecer, e ver onde 7,0 cai contra o
corte, antes de apertar Salvar.

## 4 · Ausência é um checkbox genérico

"Presente na prova" é uma caixinha comum, do mesmo tamanho e peso de qualquer
outra. Mas **ausência e zero são coisas diferentes no domínio, e confundi-las
deturpa toda a média** — é um problema conhecido e caro deste produto. Uma nota
zero de alguém que fez a prova e uma ausência têm significados opostos, e essa
distinção está a um clique distraído de distância.

Trate presença como estado de primeira classe do registro, não como um campo do
formulário. Duas escolhas explícitas, com consequência escrita — "não conta na
média" contra "conta como zero" — valem mais que um checkbox.

## 5 · O diálogo não é acessível

Ele é uma `div` com overlay. Não tem `role="dialog"`, não tem `aria-modal`, não
tem `aria-labelledby`, não fecha no Escape e não prende o foco. Fecha por
clique no fundo e pelo botão Cancelar, e só.

A área do ALUNO do mesmo produto já faz tudo isso certo. A coordenação —
que é a metade usada oito horas por dia, muito no teclado — está atrás.

Isto não é decoração: um diálogo que não prende o foco deixa o Tab passear pela
tabela de 900 linhas atrás dele enquanto o coordenador acha que está no
formulário. Desenhe o foco de cada passo, o anel de foco visível nos dois
temas, e diga qual elemento recebe o foco ao abrir e para onde ele volta ao
fechar.

# A RESTRIÇÃO QUE MAIS APERTA: ele é usado em sequência

O coordenador não conserta uma nota. Ele conserta as sete notas que o Canvas
importou errado, seguidas, na mesma prova.

Hoje isso custa, por nota: clique na célula → digitar → Salvar → Confirmar.
Quatro ações, duas delas obrigatórias por segurança e que não vão sair.

**Desenhe o caminho de teclado que permite corrigir cinco notas seguidas sem
tocar no mouse.** Enter avança o passo? Onde o foco cai quando o diálogo fecha
— na célula que foi editada, ou na próxima? Existe "salvar e ir para a próxima"?
Se a sua resposta for que o diálogo é a peça errada para esse caso, diga isso
e proponha — mas não elimine o passo de confirmação.

# POR QUE MODAL, E NÃO TELA

O sistema tem uma regra que diz "o destino é tela inteira, com URL própria —
não acordeão, não modal, não aba". Ela **não se aplica aqui**, e vale entender
por quê antes de você tentar consertar.

Aquela regra é sobre DESTINO: um lugar onde a pessoa vai ficar, ler, voltar
depois. Isto é uma escrita focada, curta, sobre um objeto que está na tela
atrás — e ela precisa da tabela atrás para ter sentido, porque a pessoa está
comparando aquela nota com as vizinhas. Tirar da tela quebra a tarefa.

Modal está certo. O que está errado é o que tem dentro dele.

# ESTADOS A DESENHAR — todos, não só o feliz

    formulário, aluno presente com nota lançada
    formulário, aluno presente sem nota (célula vazia da tabela)
    formulário, aluno ausente
    erro de validação (vazio, negativo, acima do máximo de questões)
    "sem mudanças" — apertou Salvar sem mexer em nada; fecha sem chamar a API
    diff com uma mudança · diff com duas
    a pergunta do Canvas, opção normal e opção irreversível
    salvando (o que acontece entre Confirmar e o diálogo fechar)
    a API falhou — a mensagem hoje aparece como faixa na tela ATRÁS, depois de
        o diálogo já ter fechado. Isso está errado e é seu para resolver.
    sem estatística da turma (prova recém-lançada: os 6 KPIs não têm dado)
    versão estreita, sem os KPIs, aberta da ficha do aluno

# O QUE ENTREGAR

1. **Os três passos do diálogo largo, nos dois temas.**
2. **O diálogo estreito**, nos dois temas.
3. **O bloco de comparação com a turma redesenhado** sob R1/R3/R5, com a régua
   desenhada — é a peça central deste prompt.
4. **A lista de estados acima**, cada um desenhado.
5. **O caminho de teclado**, anotado sobre o desenho: o que recebe foco ao
   abrir, o que Enter faz em cada passo, o que Escape faz, para onde o foco
   volta ao fechar.
6. **Duas ou três linhas** dizendo o que você fez com a ausência e por quê.

As medidas são as de hoje e você pode discutir, mas não ignorar: **480px de
largura na versão larga, 420px na estreita, altura máxima `min(600px, 90dvh)`
com rolagem interna.** O teto de altura existe porque um diálogo mais alto que
a tela — com o teclado virtual aberto — não tinha como rolar. Não desenhe um
diálogo de 900px de altura.
```
