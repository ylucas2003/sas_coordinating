# 04 — Telas

Especificação detalhada das quatro telas principais. Cada tela responde a uma pergunta primária (princípio "uma pergunta por tela", ver [01-product-vision.md](01-product-vision.md)).

## Visão geral

| Tela | Pergunta primária | Metáfora visual |
|------|-------------------|-----------------|
| Painel | "O que merece minha atenção agora?" | Caixa de entrada inteligente |
| Alunos | "Como esse aluno está indo?" | Ficha de jogador |
| Simulados | "Esta prova foi difícil, ou a turma piorou?" | Raio-X da prova |
| Ciclos | "Esta safra está no caminho?" | Panorama longitudinal |

---

## 4.1 Painel — "O que merece sua atenção agora"

### Pergunta primária
"O que aconteceu desde a última vez que olhei? O que merece minha atenção?"

### Metáfora
Não é um dashboard tradicional. É uma **lista priorizada de cartões de alerta**, ordenados por severidade. Visualmente parece mais com uma caixa de entrada inteligente do que com um painel de métricas.

### Ordem de leitura ideal

1. **Mudanças relevantes** — o que aconteceu desde a última visita
   - Ex: "4 alunos entraram em zona crítica"
   - Ex: "Física caiu em 5 turmas"
   - Ex: "Sede Sul superou média histórica"

2. **Blocos investigativos** — recortes acionáveis
   - Alunos em risco
   - Matérias críticas
   - Desempenho por sede
   - Tendência de corte ITA / IME

3. **Visualizações históricas** — gráficos contextuais entram depois

### Estrutura visual

Cabeçalho da tela:
- Breadcrumb à esquerda: "Painel"
- Filtros aplicados visíveis à direita (Sede, Ciclo)
- Título grande: "O que merece sua atenção"
- Subtítulo cinza: "X alertas ordenados por severidade"
- Abas de categoria abaixo: Tudo · Alunos · Simulados · Sedes (com contagem em cada)

Corpo: lista vertical de cartões de alerta (10–12px de gap).

### Anatomia do cartão de alerta

- **Barra colorida vertical à esquerda (3px)** indicando severidade
  - Vermelho: queda crítica
  - Âmbar: atenção / prova mal calibrada
  - Verde: subida atípica
  - Cinza: panorama informativo
- **Linha 1:** tag de categoria + timestamp ("há 2 dias")
- **Linha 2:** título descritivo em uma linha, peso 500
- **Linha 3:** subtítulo de contexto em cinza (12px)
- **Direita:** mini-visualização inline (80×32px)
- **Final:** link de ação ("Ver alunos →", "Ver simulado →")

### Categorias de alerta

| Categoria | Quando dispara | Cor |
|-----------|----------------|-----|
| QUEDA DE RENDIMENTO | Aluno com queda significativa nos últimos N simulados | Vermelho |
| SUBIDA ATÍPICA | Aluno com tendência positiva consistente | Verde |
| PROVA POSSIVELMENTE MAL CALIBRADA | Variância 2× acima da média histórica | Âmbar |
| MATÉRIA EM RISCO | Desempenho consistentemente abaixo do histórico | Âmbar |
| DIFERENÇA ENTRE SEDES | Diferença estatisticamente significativa entre sedes | Âmbar |
| PANORAMA DO CICLO | Atualização de status do ciclo vs. coortes | Cinza |

Definições estatísticas das regras de disparo estão em [05-data-and-stats.md](05-data-and-stats.md).

### Estado vazio

Quando não há alertas:
> "Tudo tranquilo nesta semana. Última atualização: [data]. Veja o panorama dos ciclos →"

---

## 4.2 Alunos — "A ficha de jogador"

### Pergunta primária
"Como esse aluno está indo, em comparação a si mesmo, à turma e à meta?"

### Metáfora
Referência conceitual: perfis de atletas em sites esportivos (Sofascore, ESPN). Funciona porque condensa muita informação em hierarquia clara — status no topo, performance longitudinal no meio, comparações nos lados.

### Tela de listagem (entrada)

Aba "Alunos" sem aluno selecionado:
- Lista de alunos filtrada pela sidebar contextual ("Em risco", "Em ascensão", etc.)
- Tabela compacta com: avatar/iniciais, nome, turma, sede, tendência (sparkline), classificação de perfil, ação ("Ver →")
- Click em qualquer linha abre a ficha individual

### Ficha individual — anatomia

**Cabeçalho**
- Avatar com iniciais (44×44px, navy)
- Nome (peso 500), turma e sede em cinza abaixo
- Três tags de status à direita:
  - **Perfil:** Âncora · Mistério · Regular
  - **Tendência:** ↑ Subindo · → Estável · ↓ Caindo
  - **Zona:** Top · Cinzenta · Risco

Definições de cada classificação em [05-data-and-stats.md](05-data-and-stats.md).

**Linha do tempo principal (largura total)**

Gráfico de linha mostrando a evolução das notas em todos os simulados.

Camadas:
1. Linha do aluno (navy, 2px, com pontos visíveis)
2. Média da turma (cinza tracejado)
3. Banda Top 20% (verde translúcido)
4. Linha pontilhada horizontal: nota de corte ITA
5. Linha pontilhada horizontal: nota de corte IME (cor diferente)

Eixo X: nome curto de cada simulado; eixo Y: nota.
Hover em qualquer ponto: tooltip com nota + posição + delta vs. anterior.

**Heatmap matérias × simulados**

Grade colorida:
- Linhas: matérias (Matemática, Física, Química, Português, Redação)
- Colunas: simulados (do mais antigo ao mais recente)
- Células: nota do aluno na matéria daquele simulado, codificada por cor (vermelho → âmbar → verde)
- Hover na célula: tooltip com nota exata + média da turma na mesma célula

Útil para enxergar instantaneamente desigualdade entre matérias e evolução por área.

**Painel lateral direito**

"Perfis semelhantes" — 3 a 5 mini-cards de alunos com padrão de desempenho parecido (ver definição de similaridade em [05-data-and-stats.md](05-data-and-stats.md)).

Cada mini-card:
- Avatar + nome
- Sparkline da evolução de notas
- Mesma classificação de perfil (âncora/mistério/regular)
- Link "Comparar →" abre modo de comparação lado-a-lado

### Sidebar contextual

- Em risco
- Em ascensão
- Perfil irregular
- Zona de corte (ITA / IME)
- Comparar alunos

---

## 4.3 Simulados — "O raio-X da prova"

### Pergunta primária
"Esta prova foi mais difícil, ou a turma piorou? Onde o desempenho caiu?"

### Metáfora
Um raio-X da prova: distribuição completa, decomposição por matéria, tabela individual. Permite interpretar a queda/subida de média ao olhar a forma da distribuição, não só o número.

### Tela de listagem (entrada)

Aba "Simulados" sem simulado selecionado:
- Cards de simulados em grid, ordenados pela sidebar contextual ("Mais difíceis", "Maior variância", etc.)
- Cada card: nome, data, média, delta vs. anterior, mini-histograma
- Click abre a ficha do simulado

### Ficha do simulado — anatomia

**Cabeçalho**
- Nome do simulado (ex: "Simulado ITA Fase 2 — Outubro/2026")
- Tags: ciclo a que pertence, data de aplicação, nº de alunos
- Métricas-resumo em linha: Média · Mediana · Desvio · Variância — cada uma com delta vs. histórico

**Esquerda (60%) — Distribuição**

Histograma das notas:
- Barras coloridas pelo gradiente vermelho → âmbar → verde
- **Sobreposta em cinza translúcido:** curva do simulado anterior (para comparação visual de deslocamento, alargamento ou compressão)
- Marcadores verticais: média atual (navy) e média histórica (cinza tracejado)
- Marcadores de notas de corte ITA / IME se aplicável

**Direita (40%) — Por matéria**

Barras horizontais comparativas:
- Cada barra: uma matéria
- Comprimento: média da matéria neste simulado
- Linha vertical sobreposta: média histórica da mesma matéria
- Delta numérico à direita ("Mat: 7,2 ↓ 0,5 vs. histórico")

**Abaixo — Tabela de notas individuais**

Tabela completa, ordenável e filtrável:
- Posição (#) | Aluno | Turma | Sede | Nota total | Mat | Fís | Quím | Port | Red | Tendência | Ação
- Linhas alternadas com fundo cinza muito claro
- Hover destaca a linha inteira
- Click no nome abre a ficha do aluno

### Sidebar contextual

- Mais difíceis
- Maior variância
- Por matéria
- Distribuição
- Comparar simulados

---

## 4.4 Ciclos — "O panorama"

### Pergunta primária
"Esta safra está no caminho da aprovação? Como ela se compara aos ciclos anteriores e às coortes históricas?"

### Metáfora
Vista longitudinal e agregada. Organizada em quatro quadrantes, sem ser densa — cada quadrante responde a uma sub-pergunta.

### Tela de listagem (entrada)

Aba "Ciclos" sem ciclo selecionado:
- Linha do tempo horizontal mostrando os ciclos do ano letivo
- Card de cada ciclo: nome, período, média final, taxa de aprovação projetada
- Click no ciclo abre a ficha

### Ficha do ciclo — anatomia

**Cabeçalho**
- Nome do ciclo (ex: "Ciclo 3 · 2026")
- Período coberto
- Simulados que o compõem (lista clicável)
- Métricas-resumo em linha: Média do ciclo · Taxa de aprovação ITA projetada · Taxa IME

**Quadrante superior esquerdo — Evolução interna**
Linha do tempo das médias dos simulados que compõem o ciclo. Mostra a trajetória interna do ciclo.

**Quadrante superior direito — Comparação histórica**
Barras agrupadas comparando este ciclo com:
- Ciclo anterior do mesmo grupo
- Mesmo ciclo do ano passado (coorte histórica)
- Mesmo ciclo de 2 anos atrás

**Quadrante inferior esquerdo — Distribuição final**
Histograma da distribuição final do ciclo, com marcadores das notas de corte de vestibulares-alvo (ITA, IME, AFA, EsPCEx). Indica visualmente quantos alunos estão acima de cada corte.

**Quadrante inferior direito — Destaques**
Lista compacta:
- Top 5 alunos do ciclo
- Top 5 maiores subidas durante o ciclo
- Top 5 maiores quedas durante o ciclo

Cada item linka para a ficha do aluno.

### Sidebar contextual

- Evolução temporal
- Aprovação projetada
- Coortes históricas
- Compressão/dispersão
- Comparar ciclos

---

## Padrões compartilhados entre telas

### Cabeçalho de tela

Estrutura comum em todas as telas:
- Breadcrumb pequeno em cinza no topo
- Título grande (22px, peso 500) à esquerda
- Subtítulo descritivo em cinza
- Pílulas de filtro ativo no canto direito do cabeçalho

### Estado de carregamento

Skeleton loaders em cinza claro, replicando a estrutura da tela. Nunca usar spinners.

### Estado vazio

Quando filtros aplicados retornam zero resultados:
- Ilustração simples ou ícone em cinza claro
- Texto amigável ("Nenhum aluno atende a esses critérios")
- Sugestão de ajuste ("Tente remover o filtro de sede")

### Modo de comparação

Acessível pelo botão "Comparar" dentro de Alunos / Simulados / Ciclos. Abre uma view lado-a-lado:
- 2 a 4 entidades em colunas
- Métricas alinhadas em linhas
- Diferenças destacadas visualmente (deltas coloridos)
- Botão "Sair do modo comparação" no topo

### Exportação

Botão global no canto superior direito da topbar. Em qualquer tela tabular, exporta a view atual (com filtros aplicados) como CSV.
