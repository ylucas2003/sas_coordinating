# 03 — Design system

## Paleta semântica

Paleta restrita, onde cada cor carrega significado fixo em toda a plataforma. Cor é tratada como linguagem, não como decoração.

| Cor | Significado | Uso |
|-----|-------------|-----|
| **Verde** | Acima da meta · tendência positiva | Subidas, alunos em zona segura, médias acima do histórico |
| **Âmbar** | Atenção · zona cinzenta | Alertas moderados, alunos próximos da nota de corte, variância alta |
| **Vermelho** | Abaixo da meta · tendência negativa | Quedas, alunos em risco, médias abaixo do histórico |
| **Azul (navy)** | Neutro · informativo · seleção | Cor da marca institucional, links, estado ativo, pílula selecionada |
| **Ouro** | Acento institucional | Detalhes editoriais e ícone de leitura gerada por LLM |
| **Cinza** | Contexto e referência | Comparações históricas, valores de fundo |

### Tokens de cor

Os valores em vigor estão em [web/styles/tokens.css](../web/styles/tokens.css) —
é ele que manda. A tabela abaixo é o resumo dos que carregam significado.

| Token | Valor | Uso |
|-------|-------|-----|
| `--color-navy` | `#1B3F8B` | Cor primária da marca |
| `--color-navy-soft` | `#E7EDF9` | Fundo de avatar e de ícone |
| `--color-navy-tint` | `#EAF0FB` | Fundo de tag informativa |
| `--color-gold` | `#F2C94C` | Acento institucional |
| `--color-red` | `#D9354A` | Semântica negativa |
| `--color-green` | `#2E8C5A` | Semântica positiva |
| `--color-amber` | `#D4A82E` | Semântica de atenção — **traço**, não texto |
| `--color-amber-text` | `#B08419` | O mesmo âmbar escurecido até passar em AA sobre fundo claro |
| `--color-bg` | `#EEF1F7` | Fundo fora do casco |
| `--color-surface` | `#FFFFFF` | Fundo de cards |
| `--color-surface-inset` | `#F6F8FC` | Fundo da área de conteúdo |
| `--color-text-primary` | `#16233D` | Títulos |
| `--color-text-secondary` | `#5C6883` | Texto secundário |
| `--color-text-tertiary` | `#8A93A8` | Hints, metadados |
| `--color-border` | `#EEF1F7` | Fios de card |
| `--color-divider` | `#F2F5FA` | Fio entre linhas de tabela — mais claro que o de card |

Cinza é sempre azulado. O neutro puro ao lado do navy lê como sujeira.

### Regras de uso

- **Texto sobre fundo colorido:** usar versão escura da mesma família de cor, nunca preto puro
- **No máximo 2-3 cores semânticas por tela**
- **Nunca usar cor só para diferenciar** (categorias sem ordem semântica viram cinza com rótulo)

## Tipografia

Família primária: **Plus Jakarta Sans** (já em uso nos mockups). Alternativas válidas: Inter, Geist.

### Escala tipográfica

| Uso | Tamanho | Peso |
|-----|---------|------|
| Número de KPI | 32–40px | 700 |
| Título de tela | 28px | 700 |
| Migalha da topbar | 19px | 700 |
| Título de seção / cartão | 16–17px | 400 |
| Texto corrente | 14–15px | 400 |
| Rótulos e metadados | 13–14px (cinza) | 400 |
| Cabeçalho de tabela | 13px (cinza) | 400 |
| Tag / pílula | 13px | 400 |

### Regras tipográficas

- **Três pesos:** 400 (corrente), 500 (ênfase pontual) e 700, reservado a
  título de tela, migalha e número de KPI. O 700 é o que dá hierarquia sem
  precisar de régua nem de caixa alta — antes eram só dois pesos, e títulos e
  corpo brigavam pela mesma atenção.
- **Sentence case em todo lugar.** Sem Title Case, sem ALL CAPS.
- **Número sempre em `tabular-nums`.** Nota, média e contagem vivem em coluna;
  sem isso os dígitos dançam de linha para linha.
- **Sem negrito no meio de frases.** Negrito é para títulos e rótulos.
- **`line-height: 1.7`** para texto corrente; `1.3` para títulos.

## Espaçamento e ritmo

- Usar **rem** para ritmo vertical: 1rem, 1.5rem, 2rem
- Usar **px** para gaps internos de componentes: 8px, 12px, 16px
- **Espaçamento generoso** entre seções (densidade visual gera ansiedade)

## Bordas, cantos e sombras

- **Bordas finas** (0,5px ou 1px) em cinza muito claro (`rgba(20,30,80,0.06)`)
- **Cantos arredondados moderados:**
  - 8px para componentes (botões, inputs, tags)
  - 16px para cards grandes
  - 999px (pill) apenas para tags pequenas
- **Sombras discretas:** `0 1px 2px rgba(20,30,80,0.02), 0 4px 14px rgba(20,30,80,0.05)`
- **Sem sombras pesadas, gradientes coloridos, brilhos ou efeitos neon**

## Componentes recorrentes

### Cartão de alerta (Painel)

Anatomia:

- Barra colorida vertical à esquerda (3px) indicando severidade
- Tag de categoria no topo (QUEDA DE RENDIMENTO, PROVA MAL CALIBRADA, etc.) — 11px, peso 500
- Título descritivo em uma linha — 14px, peso 500
- Subtítulo de contexto em cinza — 12px
- Mini-visualização inline à direita (sparkline, mini-histograma, etc.)
- Link de ação à direita ("Ver aluno →", "Ver simulado →")

### Tag de status

Pequena, 11px, peso 500, fundo claro da família de cor, texto na versão escura da mesma família, padding 2px 8px, border-radius 999px.

### Mini-visualizações inline

Caixas de 80×32px com sparkline, mini-histograma ou mini-comparação. Sem eixos, sem rótulos — só forma. Stroke 1.5px.

### Filtro pill (faixa global)

Padding 4px 12px, border-radius 999px, fundo cinza claro, texto cinza médio. Estado ativo: fundo navy, texto branco.

### Botão de ação

- **Primário:** fundo navy, texto branco, padding 8px 16px, border-radius 8px
- **Secundário:** fundo transparente, borda navy 0,5px, texto navy
- **Terciário (link):** sem fundo, texto navy, hover sublinha

## O que evitar visualmente

- Gradientes coloridos, sombras pesadas, brilhos, efeitos neon
- Gráficos de pizza, donut, 3D, velocímetros
- Mais de 2-3 cores semânticas por tela
- Ícones excessivamente decorativos
- Visual de BI genérico (Power BI, Tableau padrão)
- Cantos arredondados em bordas de um lado só (border-radius só com border completa)
- Densidade alta sem hierarquia

## Biblioteca de gráficos

Cada tipo de pergunta tem um tipo de gráfico fixo. Consistência ao longo do uso constrói familiaridade.

| Pergunta | Gráfico |
|----------|---------|
| Evolução temporal de uma métrica | Linha com pontos visíveis |
| Comparação entre 3-6 categorias | Barras horizontais |
| Distribuição de notas | Histograma com curva sobreposta |
| Posição de um aluno no grupo | Dot plot ou box plot com ponto destacado |
| Aluno × matéria × simulado | Heatmap |
| Comparar duas distribuições | Histogramas sobrepostos com transparência |
| Tendência em espaço pequeno | Sparkline (mini linha sem eixos) |

### Regras para gráficos

- **Toda métrica vem com referência comparativa** (médias históricas em cinza, banda de meta, ponto do simulado anterior, etc.)
- **Cor com significado** — verde/âmbar/vermelho para gradiente de desempenho, cinza para referência
- **Eixos discretos** — sem grid pesado, ticks mínimos, números formatados (7,2 não 7.20000)
- **Tooltips ricos** ao hover, mostrando valor exato + contexto

### Proibidos

Pizza, donut, 3D, gauges/velocímetros, gráficos com mais de 5 cores categóricas.

## Microinterações

Pequenos detalhes que separam "ferramenta interna" de "produto profissional":

- **Tooltips ricos** em qualquer ponto de gráfico — número exato + contexto
- **Transições suaves** entre estados de filtro — animar em vez de piscar
- **Skeleton loaders** enquanto carrega — estrutura em cinza, não spinner
- **Estados vazios bem desenhados** — quando filtro retorna zero, mensagem amigável + sugestão de ajuste
- **Atalhos de teclado** documentados em [02-information-architecture.md](02-information-architecture.md)
- **Modo claro e escuro** — trabalhar à noite em sala de coordenação é comum

## Acessibilidade

- Contraste mínimo WCAG AA em todos os textos
- Foco visível em todos os elementos interativos
- Hierarquia de cabeçalhos (h1 > h2 > h3) consistente
- Tooltips e estados de cor sempre acompanhados de texto ou ícone (cor nunca é o único indicador)

## Referências de inspiração visual

- **Linear** (linear.app) — tipografia, espaçamento, atalhos de teclado
- **Stripe Dashboard** — densidade informacional sem ansiedade visual
- **Sofascore** / **ESPN player profiles** — hierarquia visual da tela de aluno
- **Notion** — sidebar contextual, breadcrumb, navegação
- **Pirsch Analytics** / **Plausible** — gráficos minimalistas com semântica de cor
