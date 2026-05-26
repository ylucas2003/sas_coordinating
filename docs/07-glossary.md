# 07 — Glossário

Vocabulário do domínio. Termos usados consistentemente em toda a documentação e na própria interface.

## Termos de domínio educacional

**Aluno ITM**
Aluno matriculado em turma especializada em vestibulares militares e altamente competitivos (ITA, IME, AFA, EsPCEx, EFOMM).

**Simulado**
Prova aplicada à turma para simular o vestibular-alvo. Pode ser de 1ª fase (objetiva) ou 2ª fase (discursiva).

**Ciclo**
Conjunto de simulados agrupados num período definido. Tipicamente cobre 1ª e 2ª fases de um conjunto temático ou cronológico de provas. Definido pela coordenação no início do ano letivo.

**Coorte**
Grupo de alunos do mesmo ano letivo na turma ITM. Permite comparações históricas ("a coorte de 2024 nesse mesmo ponto do ano...").

**Sede**
Unidade física ou modalidade de ensino. No Ari de Sá, divide-se em presencial e online.

**Nota de corte**
Pontuação mínima projetada para aprovação em determinado vestibular. Atualizada anualmente pela coordenação com base nos resultados reais.

**Vestibular-alvo**
Vestibular para o qual a turma ou o aluno está se preparando. Define a nota de corte usada nas classificações de zona.

## Termos de classificação de aluno

**Âncora**
Aluno consistentemente no top 15% nos últimos 5 simulados, com baixa variabilidade. Atua como "âncora" da média da turma. Definição estatística em [05-data-and-stats.md](05-data-and-stats.md).

**Mistério**
Aluno cuja variância de desempenho entre simulados é anormalmente alta. A nota num simulado não prediz bem a do próximo. Geralmente indica algo emocional, método de estudo inconsistente, ou perfil de ansiedade em prova.

**Regular**
Classificação default. Aluno que não é âncora nem mistério. Maior parte dos alunos.

**Zona Top**
Aluno cuja média recente está confortavelmente acima da nota de corte do vestibular-alvo (com margem de segurança).

**Zona Cinzenta**
Aluno cuja média recente oscila em torno da nota de corte. Pequenas variações o colocam dentro ou fora da meta de aprovação. **Esses são os alunos onde intervenção rende mais.**

**Zona de Risco**
Aluno cuja média recente está significativamente abaixo da nota de corte. Aprovação no vestibular-alvo é improvável sem mudança expressiva.

**Tendência ↑ Subindo**
Aluno cuja regressão linear das últimas N notas mostra coeficiente angular positivo significativo.

**Tendência → Estável**
Aluno sem tendência clara de subida ou queda.

**Tendência ↓ Caindo**
Aluno cuja regressão linear das últimas N notas mostra coeficiente angular negativo significativo.

## Termos estatísticos relevantes

**Média**
Soma das notas dividida pelo número de alunos.

**Mediana**
Valor central das notas ordenadas. Menos sensível a outliers que a média.

**Desvio padrão**
Medida de dispersão das notas. Quanto maior, mais espalhadas estão as notas em torno da média.

**Variância**
Desvio padrão ao quadrado. No contexto da ferramenta, "variância alta" num simulado pode indicar prova mal calibrada ou turma muito heterogênea.

**Distribuição**
Forma do histograma das notas. Pode ser:
- **Unimodal** — um pico central (esperado)
- **Bimodal** — dois picos (indica grupo dividido em dois níveis)
- **Comprimida** — barras altas e estreitas (turma convergindo)
- **Dispersa** — barras baixas e largas (turma heterogênea)

**Coorte histórica**
Conjunto de dados de turmas anteriores no mesmo ponto do calendário. Usado para benchmarking ("a turma de 2026 neste momento está performando como a turma de 2024").

**Quartil / Percentil**
Posição relativa de um aluno na distribuição. Top 25% = quartil superior; top 10% = 90º percentil; etc.

## Termos da interface

**Painel**
Aba inicial da interface. Mostra alertas e panorama. Nome substitui "tela inicial" ou "dashboard".

**Sidebar contextual**
Coluna lateral esquerda dentro de cada aba. Lista recortes investigativos formulados como perguntas/estados, não como entidades. Funciona como filtro, não como navegação.

**Filtros globais**
Faixa fixa abaixo da topbar com: Sede, Turma, Ciclo, Janela temporal, Matéria, Busca. Persistem entre abas.

**Topbar**
Barra horizontal superior com as quatro abas principais (Painel · Alunos · Simulados · Ciclos) e ações globais (busca, exportar, configurações).

**Drill-down**
Padrão de navegação de cima para baixo na hierarquia: Ciclo → Simulado → Aluno. Cada nível abre via clique.

**Breadcrumb**
Indicador de localização no canto superior esquerdo do corpo da tela.

**Cartão de alerta**
Componente principal do Painel. Anatomia descrita em [04-screens.md](04-screens.md).

**Sparkline**
Mini gráfico de linha sem eixos, usado inline para indicar tendência em pouco espaço.

**Heatmap**
Grade colorida onde a intensidade da cor codifica um valor numérico. Usado na ficha do aluno para mostrar notas por matéria × simulado.

**Modo de comparação**
View especial acessível pelo botão "Comparar". Mostra 2-4 entidades lado a lado com métricas alinhadas e deltas destacados.

**Estado vazio**
Tela ou seção que aparece quando filtros aplicados retornam zero resultados. Sempre acompanhado de mensagem amigável e sugestão de ajuste.

**Skeleton loader**
Estrutura cinza claro que aparece enquanto a tela carrega, replicando o layout final. Substitui spinners.

## Convenções de nomenclatura

**Para evitar inconsistência em código e textos:**

| Conceito | Sempre usar | Não usar |
|----------|-------------|----------|
| Aluno em zona crítica | "Em risco" | "Em perigo", "Crítico", "Reprovando" |
| Página inicial | "Painel" | "Dashboard", "Home", "Início" |
| Aba | "Aba" | "Página", "Seção", "Módulo" |
| Sidebar | "Sidebar contextual" ou "menu contextual" | "Menu lateral", "Navegação secundária" |
| Simulado mal calibrado | "Possivelmente mal calibrado" | "Defeituoso", "Errado", "Com problema" |
| Aluno com nota anormalmente alta | "Subida atípica" | "Outlier", "Aluno suspeito" |
| Coordenador | "Coordenação" no plural; "coordenador" no singular | "Coordenadores" (preferir genérico) |
