# 01 — Visão de produto

## Problema que estamos resolvendo

A coordenação das turmas ITM do Colégio Ari de Sá analisa hoje o desempenho dos alunos cruzando planilhas Excel manualmente. Esse processo tem três limitações graves:

1. **Trabalho braçal alto.** Cada análise envolve abrir múltiplas planilhas, cruzar referências e fazer cálculos repetitivos.
2. **Visão reativa, não proativa.** O coordenador só descobre que um aluno está em risco se for procurar especificamente — não existe nada que o alerte.
3. **Difícil enxergar tendências.** Comparar simulados ao longo de um ciclo, ou ciclos entre si, exige montagem manual de análises a cada vez.

## O que a ferramenta faz

Três coisas, em ordem de importância:

**1. Sinaliza proativamente o que merece atenção.** A tela inicial mostra alertas — quedas significativas, subidas atípicas, provas mal calibradas, diferenças entre sedes. O coordenador abre a ferramenta e é informado, não precisa saber o que procurar.

**2. Responde perguntas analíticas que exigem cruzamento de dados.** Quem caiu nos últimos 3 simulados? Esse simulado foi mais difícil ou a turma piorou? Como esse ciclo se compara ao anterior?

**3. Mostra o histórico organizado.** Ficha de cada aluno, distribuição de cada simulado, panorama de cada ciclo — sempre com referência comparativa.

## O que ela não é

- **Não é um sistema acadêmico completo.** Não trata frequência, mensalidade, comunicação com pais.
- **Não é uma ferramenta para alunos ou professores.** Acesso restrito à coordenação.
- **Não é um simples visualizador de planilhas.** Se fosse, o Excel já bastaria.
- **Não é um BI genérico.** É uma ferramenta pedagógica especializada.

## Princípios de design

Cinco princípios que guiam todas as decisões — visuais, de informação, de interação:

### Princípio 1 — Uma pergunta por tela

Cada tela responde a uma pergunta principal, com ramificações secundárias via drill-down. Não construir dashboards com 12 widgets concorrendo por atenção. Se uma tela está tentando responder a três perguntas, virar três telas.

### Princípio 2 — Da vigilância à consulta, não o contrário

O Painel mostra o que merece atenção agora; o coordenador navega para detalhes a partir dali. A ferramenta não obriga o usuário a saber o que procurar — ela o orienta.

### Princípio 3 — Comparação como cidadã de primeira classe

Nenhum número aparece sozinho. Toda métrica vem com referência: comparada ao simulado anterior, ao ciclo anterior, à outra sede, à coorte histórica. Um "7,2" não diz nada; "7,2 ↑ 0,4 vs. ciclo anterior" diz tudo.

### Princípio 4 — Cor como código semântico, não decoração

Cor significa algo — bom/ruim, acima/abaixo, atenção/normal. Matérias e turmas se diferenciam por posição e rótulo, não por cor. A paleta semântica está documentada em [03-design-system.md](03-design-system.md).

### Princípio 5 — Espaço em branco generoso

Densidade visual gera ansiedade. Mais telas com menos informação por tela é melhor que tela única empilhada.

## Os três pecados capitais a evitar

Padrões comuns em dashboards educacionais que devemos evitar conscientemente:

**1. A "parede de números."**
Cards de média, mediana, desvio, variância, mínimo, máximo lado a lado. Tecnicamente completo, cognitivamente inútil — o coordenador faz o trabalho de interpretação que a ferramenta deveria fazer por ele.

**2. Gráficos sem pergunta.**
Pizza de "distribuição de notas" que ninguém olha por mais de 2 segundos. Gráfico precisa responder a uma pergunta concreta. Se um gráfico não tem pergunta clara associada, ele sai da tela.

**3. Cor sem semântica.**
Usar cor para "diferenciar" matérias desperdiça o recurso visual mais poderoso da interface. Cor é reservada para significado.

## Usuários

Três perfis com necessidades distintas. A interface deve servir aos três, mas o Painel inicial muda conforme o perfil logado.

### Coordenador pedagógico
**Pergunta principal:** "quem precisa de intervenção esta semana?"
**Foco:** alunos individuais em risco ou em ascensão.
**Uso típico:** abre a ferramenta de manhã, escaneia alertas, drill-down em alunos críticos, prepara conversas e intervenções.

### Coordenador de área (matéria)
**Pergunta principal:** "como minha matéria está indo? as provas estão bem calibradas?"
**Foco:** desempenho por disciplina, calibração de provas, variância suspeita.
**Uso típico:** investiga simulados onde sua matéria teve desempenho fora do padrão.

### Direção
**Pergunta principal:** "como esta safra se compara às anteriores? as sedes estão alinhadas?"
**Foco:** comparação entre sedes, turmas, coortes históricas, projeção de aprovação.
**Uso típico:** análise periódica de panorama, em ciclos mensais ou trimestrais.

> **Decisão pendente:** validar com o cliente qual é o usuário primário. A hipótese de trabalho atual é coordenador pedagógico (ver [06-open-questions.md](06-open-questions.md)).
