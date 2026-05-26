# 06 — Decisões pendentes

Lista viva de decisões que precisam ser tomadas antes ou durante a implementação. Algumas precisam de conversa com o cliente (coordenação do Ari de Sá); outras dependem de validação técnica.

## Decisões de produto

### 1. Quem é o usuário primário?

**Contexto:** definimos três perfis (coordenador pedagógico, coordenador de área, direção), mas o Painel inicial muda conforme o perfil logado.

**Decisão necessária:** confirmar com o cliente qual é o usuário primário e, portanto, qual versão do Painel é a default.

**Hipótese de trabalho atual:** coordenador pedagógico.

**Como validar:** conversa com 2-3 coordenadores reais; perguntar quem abre o sistema com mais frequência e para quais decisões.

---

### 2. Origem e formato dos dados de simulado

**Contexto:** o upload de planilhas é o ponto mais frágil do projeto. Formatos inconsistentes, grafias diferentes de nomes entre planilhas, alunos que entram e saem no meio do ciclo, simulados anulados, notas revisadas — tudo isso pode quebrar o pipeline.

**Decisões necessárias:**
- Vai existir um template fixo de planilha? Quem produz?
- Os alunos têm matrícula única ou identificamos por nome?
- Como tratar correções retroativas de notas?
- Quem tem permissão de upload?
- Frequência de upload (a cada simulado, semanal, etc.)?

**Como validar:** conversa com quem produz hoje as planilhas + amostra de planilhas reais dos últimos 6 meses.

---

### 3. Definição operacional de "ciclo"

**Contexto:** "ciclo" é o conceito central da análise longitudinal, mas a documentação inicial não foi clara.

**Decisões necessárias:**
- Ciclo é uma entidade fixa, criada no início do ano letivo, ou um agrupamento dinâmico que a coordenação cria sob demanda?
- Quem tem permissão para definir / alterar ciclos?
- Um simulado pode estar em mais de um ciclo simultaneamente?

**Hipótese de trabalho atual:** entidade fixa, criada no início do ano letivo pela coordenação, definindo quais simulados compõem cada ciclo. Comparações entre ciclos arbitrários acontecem via filtros, não criando novos ciclos.

**Como validar:** conversa com coordenação pedagógica.

---

### 4. Quais vestibulares-alvo entram na "zona de corte"?

**Contexto:** a classificação de zona (Top / Cinzenta / Risco) e a taxa de aprovação projetada dependem das notas de corte dos vestibulares-alvo.

**Decisões necessárias:**
- Quais vestibulares: ITA, IME, AFA, EsPCEx, EFOMM, outros?
- A nota de corte é por aluno (declaração do aluno) ou padrão da turma?
- Quem atualiza as notas de corte a cada ano e com que critério?

**Hipótese de trabalho atual:** ITA + IME como padrão; AFA e EsPCEx como adicionais; nota de corte por turma, ajustável anualmente pela coordenação.

**Como validar:** conversa com direção pedagógica.

---

### 5. Quais limiares numéricos usar nas regras de alerta?

**Contexto:** as regras de alerta em [05-data-and-stats.md](05-data-and-stats.md) têm limiares numéricos (queda de 1,5 ponto, variância 2× histórica, etc.) que são pontos de partida razoáveis mas precisam ser calibrados.

**Decisões necessárias:**
- Os limiares atuais geram alertas demais (ruído) ou de menos (não detectam coisas importantes)?
- Devem ser configuráveis pela coordenação ou fixos no código?

**Como validar:** simulação com dados reais dos últimos 6 meses; revisar se os alertas que teriam aparecido correspondem ao que a coordenação considera relevante.

---

## Decisões de design

### 6. Modo escuro é prioridade do MVP?

**Contexto:** mencionado no design system como "trabalhar à noite em sala de coordenação é comum", mas duplica o esforço de design.

**Decisão necessária:** entra no MVP ou fica para v2?

**Recomendação:** v2. Lançar primeiro com modo claro bem feito; adicionar escuro depois se houver demanda.

---

### 7. Modo de comparação: lado-a-lado ou sobreposto?

**Contexto:** a função "Comparar" aparece em Alunos, Simulados e Ciclos. Duas formas comuns:
- Lado-a-lado: colunas paralelas, cada entidade com seus dados completos
- Sobreposto: gráficos sobrepostos, deltas destacados

**Recomendação:** lado-a-lado para até 4 entidades; sobreposto a partir de 5. Decidir após primeiros mockups.

---

### 8. Granularidade do drill-down no heatmap matérias × simulados

**Contexto:** o heatmap na ficha do aluno mostra notas por matéria por simulado. Clicar numa célula deve abrir o quê?

**Opções:**
- Tooltip detalhado (não sai da tela)
- Modal com detalhes da matéria no simulado
- Navegação direta para o simulado

**Recomendação:** tooltip detalhado + opção de clique que abre o simulado filtrado pela matéria.

---

## Decisões técnicas

### 9. Stack de frontend e backend

**Decisão necessária:** definir tecnologias antes de início da implementação.

**Sugestões iniciais (sujeitas a validação técnica):**
- Frontend: React + TypeScript + Vite
- Visualizações: Recharts ou Visx (não D3 puro)
- Backend: a definir conforme infraestrutura do colégio
- Banco: PostgreSQL (suporta bem queries analíticas)
- Autenticação: provedor único (Google Workspace, Microsoft 365 ou similar)

---

### 10. Hospedagem e infraestrutura

**Decisões necessárias:**
- Hospedagem em nuvem ou on-premise?
- Restrições de dados (LGPD — dados de menores de idade)?
- Backup e recuperação?

**Como validar:** conversa com TI do colégio.

---

### 11. Quem mantém a ferramenta no longo prazo?

**Contexto:** ferramentas internas tendem a ser construídas e depois abandonadas se não houver dono claro.

**Decisão necessária:**
- Time de TI do colégio assume manutenção?
- Vendor externo (quem está construindo) tem contrato de manutenção?
- Quem responde quando algo quebra?

---

## Próximos passos sugeridos

Em ordem de prioridade:

1. **Validar com 2-3 coordenadores reais** — observar uso de planilhas atuais, entender perguntas frequentes, calibrar prioridades (atende às questões 1, 2, 3, 5)
2. **Definir vestibulares-alvo e notas de corte** — questão 4
3. **Resolver decisões técnicas de infraestrutura** — questões 9, 10, 11
4. **Construir protótipo navegável das 4 telas principais** com dados sintéticos
5. **Calibrar limiares de alerta** com dados reais — questão 5
6. **Lançar MVP em uma turma piloto** antes de expandir
