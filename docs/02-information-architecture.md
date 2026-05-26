# 02 — Arquitetura da informação

## Hierarquia conceitual

Toda a estrutura da ferramenta gira em torno de uma hierarquia de três níveis que se encaixam:

```
Aluno → Simulado → Ciclo
```

Mais dois eixos transversais que cortam essa hierarquia:

- **Sede** (presencial / online)
- **Tempo** (comparações com períodos anteriores)

Essa hierarquia define as quatro abas principais da topbar e a forma como o usuário navega entre níveis de detalhe.

## Os dois níveis de navegação

A navegação tem **dois níveis claramente separados, sem repetição entre eles**.

| Camada | Papel | Pergunta que responde |
|--------|-------|----------------------|
| Topbar horizontal | Contexto macro | "Que tipo de análise estou fazendo agora?" |
| Sidebar contextual | Recortes investigativos | "Que pergunta quero fazer dentro desse contexto?" |

**Regra fundamental: nunca repetir os mesmos itens nas duas navegações.** Topbar e sidebar têm papéis distintos; misturá-los gera dois menus competindo, problema típico de dashboards genéricos.

## Topbar — Navegação macro

Quatro abas, deliberadamente enxutas:

**Painel · Alunos · Simulados · Ciclos**

Cada aba representa um modo mental distinto de análise. Quatro é o teto — qualquer aba a mais começa a sobrepor conceitualmente com as existentes.

| Aba | Função |
|-----|--------|
| **Painel** | Vigilância e panorama. O que mudou, o que exige ação, desvios, anomalias, tendências críticas. Home do coordenador. |
| **Alunos** | Análise individual e acompanhamento pedagógico. Evolução, risco, desempenho desigual, perfis semelhantes. |
| **Simulados** | Análise de provas e comportamento coletivo. Dificuldade, variância, desempenho por matéria, comparação entre provas. |
| **Ciclos** | Análise longitudinal. Evolução ao longo do tempo, comparação histórica, projeções, desempenho consolidado. |

## Decisões deliberadas fora da topbar

Duas escolhas que poderiam ter virado abas, mas não viraram. Documentar o raciocínio aqui evita que alguém reverta essas decisões depois sem entender o motivo.

### Comparação não é aba, é ação dentro de cada contexto

Comparar alunos é uma operação dentro de Alunos. Comparar simulados é dentro de Simulados. Extrair "Comparativos" como aba separada cria sobreposição com tudo e força o coordenador a sair do contexto onde já está. Botão "Comparar" aparece dentro de cada aba quando faz sentido.

### Exportação não é aba, é ação global

Exportar é uma operação, não uma análise. Vira botão no canto superior direito da topbar (junto da busca e configurações), disponível em qualquer tela com dado tabular. Promover exportação a aba dá a ela peso visual igual ao das análises de verdade, o que distorce a hierarquia.

## Faixa de filtros globais

Logo abaixo da topbar, faixa fixa de filtros globais que afetam toda a visualização:

**Sede · Turma · Ciclo · Janela temporal · Matéria · Busca (`/`)**

Esses filtros não pertencem à navegação — são contexto. Misturá-los com sidebar ou topbar gera confusão hierárquica. Estado dos filtros persiste entre telas.

## Sidebar contextual

A sidebar muda conforme a aba ativa. Ela **não representa páginas ou entidades** — representa **perguntas e recortes investigativos**.

### Regras da sidebar

- Máximo de **5 itens** por aba (qualquer coisa além disso vira menu e perde o propósito)
- Itens formulados como **perguntas ou estados**, não como entidades
- Funcionam como **filtros que reconfiguram a tela ativa**, não como navegação para telas separadas
- Estado ativo destacado visualmente; pode ser combinado com filtros globais
- Combinação livre com os filtros globais (sidebar "Em risco" + filtro de sede + filtro de matéria)

### Por que filtros e não navegação separada

Decisão arquitetural importante. A sidebar reconfigura o conteúdo da tela ativa, em vez de levar a telas próprias. Vantagens:

- Mantém o coordenador ancorado em uma tela e ele aprende o layout
- Permite combinar recortes (sidebar "Em risco" + filtro de sede + filtro de matéria)
- Reduz drasticamente o número de telas a desenhar e manter
- O estado "Em risco" pode ser indicado visualmente (highlight na sidebar + pill no cabeçalho da tela ativa)

### Exemplo do princípio "perguntas, não entidades"

| Errado (entidades) | Correto (perguntas/recortes) |
|--------------------|------------------------------|
| Simulado S01 · S02 · S03 | Quem mais caiu? · Qual matéria puxou? · Houve dispersão? |
| Lista de IDs de aluno | Em risco · Em ascensão · Perfil irregular |

### Sidebars propostas por aba

#### Painel
- Alertas críticos
- Quedas recentes
- Subidas atípicas
- Variância suspeita
- Diferenças entre sedes

#### Alunos
- Em risco
- Em ascensão
- Perfil irregular
- Zona de corte (ITA / IME)
- Comparar alunos

#### Simulados
- Mais difíceis
- Maior variância
- Por matéria
- Distribuição
- Comparar simulados

#### Ciclos
- Evolução temporal
- Aprovação projetada
- Coortes históricas
- Compressão/dispersão
- Comparar ciclos

## Estrutura visual

```
┌────────────────────────────────────────────────────────┐
│ LOGO   Painel · Alunos · Simulados · Ciclos    🔍 ⤓ ⚙ │
├────────────────────────────────────────────────────────┤
│ Sede ▾ │ Turma ▾ │ Ciclo ▾ │ Tempo ▾ │ Matéria ▾     │
├──────────────┬─────────────────────────────────────────┤
│ Sidebar      │                                         │
│ contextual   │ Conteúdo principal                      │
│ (≤5 itens)   │                                         │
│              │                                         │
└──────────────┴─────────────────────────────────────────┘
```

Ações globais (busca, exportar, configurações) no canto superior direito da topbar, afastadas visualmente da navegação principal.

## Padrões de navegação

### Drill-down

Cada nível da hierarquia (Ciclo > Simulado > Aluno) é acessível clicando no nível superior. Da tela de ciclo, clicar num simulado leva à tela do simulado; dela, clicar num aluno leva à tela do aluno.

### Breadcrumb

Indicador de localização no canto superior esquerdo do corpo da tela, mostrando o caminho atual (ex: Ciclos > Ciclo 3 · 2026 > Simulado ITA Fase 1).

### Atalhos de teclado

- `/` — foca a busca
- `g p` — vai para Painel
- `g a` — vai para Alunos
- `g s` — vai para Simulados
- `g c` — vai para Ciclos
- `Esc` — fecha modal ou popover ativo

## Estados persistentes

- Filtros globais persistem entre navegação (Sede e Turma escolhidas continuam aplicadas ao trocar de aba)
- Última aba visitada é lembrada entre sessões
- Sidebar contextual reseta ao trocar de aba (estado contextual é por aba)
