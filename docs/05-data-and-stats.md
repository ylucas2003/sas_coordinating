## 05 — Dados e estatística

Definições operacionais de métricas, regras de alerta e classificações de aluno. Este documento é a fonte da verdade para o backend implementar as queries e para o frontend exibir os resultados consistentemente.

> **Status:** hipóteses iniciais propostas pela equipe técnica. Limiares numéricos precisam ser **calibrados com dados reais** antes do MVP — ver questão 5 em [06-open-questions.md](06-open-questions.md).

## Modelo de dados conceitual

```
Aluno  ────────┐
               │ N:N (matrícula em turma)
Turma  ────────┤
               │
Sede   ────────┘

Simulado ──── 1:N ──── NotaAluno (nota total + nota por matéria)
   │
   └── pertence a ──── Ciclo  ──── pertence a ──── AnoLetivo
```

### Entidades

**Aluno**
- id (string · UUID ou matrícula)
- nome
- turma (referência)
- sede (referência)
- vestibulares-alvo (lista) — ITA, IME, AFA, EsPCEx, EFOMM
- ativo (boolean — alunos que saíram permanecem para histórico)

**Turma**
- id
- nome (ex: "3ª série A — ITM")
- sede (referência)
- anoLetivo
- alunos (lista)

**Sede**
- id
- nome (ex: "Centro", "Online")
- modalidade — `presencial` | `online`

**Simulado**
- id
- nome (ex: "Simulado ITA Fase 1 — Março/2026")
- fase — `1a` | `2a`
- dataAplicacao
- ciclo (referência)
- notaMaxima (geralmente 10 ou 100, depende do padrão)
- aplicadoEm (lista de turmas)
- anulado (boolean — simulado descartado mantém o registro)

**NotaAluno**
- aluno (referência)
- simulado (referência)
- notaTotal
- notasPorMateria — `{ matematica, fisica, quimica, portugues, redacao, ... }`
- presente (boolean — aluno faltou ≠ aluno tirou zero)

**Ciclo**
- id
- nome (ex: "Ciclo 3 · 2026")
- anoLetivo
- periodoInicio, periodoFim
- simulados (lista)

**AnoLetivo**
- ano (ex: 2026)
- coortes (alunos matriculados no ano)

### Matérias

Conjunto fechado por enquanto: Matemática, Física, Química, Português, Redação. Configurável por sede/turma no futuro, se necessário.

## Métricas de simulado

Calculadas por (simulado, recorte). O recorte pode ser: todo o simulado, uma turma específica, uma sede, uma matéria.

| Métrica | Definição |
|---------|-----------|
| `media` | Média aritmética das notas dos alunos presentes |
| `mediana` | Valor central das notas ordenadas |
| `desvioPadrao` | √(variância amostral) |
| `variancia` | Σ(xᵢ − média)² / (n − 1) |
| `min`, `max` | Mínimo e máximo |
| `quartis` | Q1, Q2 (= mediana), Q3 |
| `nPresentes`, `nAusentes` | Contagens |
| `histograma` | Bins fixos: passos de 0,5 ponto (configurável); contagem por bin |

**Faltas** entram como aluno não-incluído na média; aparecem no count separado.
**Simulados anulados** ficam ocultos por default, com toggle "incluir anulados" para investigação.

## Classificação de aluno

Cada aluno recebe **três classificações independentes**, sempre calculadas sobre a janela dos últimos 5 simulados (configurável).

### 1. Perfil — `Âncora | Mistério | Regular`

| Perfil | Critério (proposta inicial) |
|--------|------------------------------|
| **Âncora** | Mediana das notas nos últimos 5 simulados está no top 15% da turma **E** desvio padrão das notas < 25% do desvio padrão da turma |
| **Mistério** | Desvio padrão das notas nos últimos 5 simulados > 2× a mediana de desvios padrões dos alunos da turma |
| **Regular** | Não atende a Âncora nem Mistério (default) |

### 2. Tendência — `↑ Subindo | → Estável | ↓ Caindo`

Calculada por **regressão linear simples** das últimas 5 notas (x = índice do simulado, y = nota).

| Tendência | Critério |
|-----------|----------|
| **↑ Subindo** | Coeficiente angular > +0,15 ponto/simulado **e** p-valor < 0,1 |
| **↓ Caindo** | Coeficiente angular < −0,15 ponto/simulado **e** p-valor < 0,1 |
| **→ Estável** | Caso contrário |

### 3. Zona — `Top | Cinzenta | Risco`

Calculada com base na nota de corte do vestibular-alvo principal do aluno e na média dos últimos 5 simulados.

| Zona | Critério |
|------|----------|
| **Top** | Média recente ≥ nota de corte + margem (ex: corte + 0,5) |
| **Cinzenta** | Média recente entre (nota de corte − 0,5) e (nota de corte + 0,5) |
| **Risco** | Média recente < nota de corte − 0,5 |

Aluno com múltiplos vestibulares-alvo: usa o de menor nota de corte (mais permissivo).

## Regras de alerta

Cada alerta tem uma categoria, um critério estatístico de disparo e uma severidade (vermelho · âmbar · verde · cinza).

### Categorias

| Código | Categoria | Critério (proposta inicial) | Severidade |
|--------|-----------|------------------------------|------------|
| `QUEDA_RENDIMENTO` | Queda de rendimento | Média dos últimos 3 simulados ≥ 1,5 ponto abaixo da média dos 3 anteriores | Vermelho |
| `SUBIDA_ATIPICA` | Subida atípica | Média dos últimos 3 simulados ≥ 1,5 ponto acima da média dos 3 anteriores | Verde |
| `PROVA_MAL_CALIBRADA` | Possivelmente mal calibrada | Desvio padrão do simulado ≥ 2× desvio padrão médio histórico (mesmo ciclo / mesma fase) | Âmbar |
| `MATERIA_EM_RISCO` | Matéria em risco | Média da matéria em ≥ 3 simulados consecutivos < média histórica − 1 desvio padrão | Âmbar |
| `DIFERENCA_ENTRE_SEDES` | Diferença entre sedes | Teste-t de Welch entre médias de duas sedes com p < 0,05 e |Δ| ≥ 0,5 | Âmbar |
| `PANORAMA_CICLO` | Panorama do ciclo | Atualização periódica de status (gerada no fim do ciclo) | Cinza |
| `ZONA_TRANSICAO` | Mudança de zona | Aluno transitou de Top→Cinzenta, Cinzenta→Risco (ou inverso) entre dois cálculos consecutivos | Vermelho (descida) / Verde (subida) |

> Todos os limiares numéricos acima (1,5 ponto, 2× desvio, 1 desvio padrão, p < 0,05) são pontos de partida razoáveis que precisam ser **calibrados com dados reais dos últimos 6 meses** antes do MVP. Ver questão 5 em [06-open-questions.md](06-open-questions.md).

### Estrutura de um alerta

- `id`
- `categoria` — uma das acima
- `severidade` — `vermelho | ambar | verde | cinza`
- `entidadeAfetada` — referência a Aluno, Simulado, Turma ou Sede
- `titulo` — string descritiva ("Aluno 023 caiu 1,8 pontos em 3 simulados")
- `subtitulo` — contexto adicional ("Matéria de Física · Turma 3B · há 2 dias")
- `disparadoEm` — timestamp
- `dadosBrutos` — payload mínimo para gerar mini-visualização (sparkline, mini-histograma)
- `resolvido` — boolean (coordenação pode marcar alertas como resolvidos)

### Política de auto-arquivar

Proposta inicial: alertas não-resolvidos somem após 30 dias **se a condição que os disparou não persiste**. Configurável.

## Similaridade entre alunos ("Perfis semelhantes")

Usada no painel lateral da ficha de aluno. Cada aluno recebe um vetor de features:

- Médias por matéria nos últimos 5 simulados (5 features — uma por matéria)
- Desvio padrão geral nos últimos 5 simulados (1 feature)
- Coeficiente angular da tendência (1 feature)

Total: 7 features. Normalizadas via z-score em relação à turma.

**Cálculo de similaridade:** distância euclidiana entre vetores. Os 5 alunos mais próximos do aluno-foco aparecem como "perfis semelhantes".

Alternativa mais sofisticada (para v2): clustering (k-means) sobre todos os alunos da coorte, e mostrar outros membros do cluster do aluno-foco.

## Comparações temporais

Toda métrica exibida na interface deve vir com **referência comparativa**. Os tipos de comparação suportados:

| Tipo | Implementação |
|------|---------------|
| vs. simulado anterior | Simulado imediatamente anterior na mesma janela (mesma turma/sede) |
| vs. ciclo anterior | Média do mesmo recorte no ciclo anterior |
| vs. coorte histórica | Média do mesmo recorte no mesmo ponto do calendário em anos anteriores (alinhada por semana do ano letivo, não por data absoluta) |
| vs. histórico geral | Média acumulada de todas as edições anteriores do mesmo tipo de prova |

A escolha do tipo de comparação é decisão do componente que exibe a métrica; o backend expõe todas as comparações relevantes na resposta.

## Taxa de aprovação projetada

Métrica exibida em Ciclos. Calculada como:

```
taxa_aprovacao_projetada(vestibular) =
   (alunos cuja média dos últimos 5 simulados ≥ nota de corte do vestibular)
   / (total de alunos ativos da coorte)
```

Para cada vestibular-alvo configurado (ITA, IME, AFA, EsPCEx, EFOMM), expor a taxa separadamente.

> **Nota:** essa é uma projeção naïve baseada na média recente. Modelos mais sofisticados (regressão considerando trajetória, perfil, similaridade com coortes históricas aprovadas) são possíveis em v2. Validar com a coordenação se a projeção naïve é informativa o suficiente para o MVP.

## Atualização e pipeline

**Frequência prevista de upload:** a cada simulado aplicado (decisão pendente — ver 06).

**Pipeline conceitual:**
1. Upload de planilha (CSV/XLSX) → ingestão
2. Validação (alunos conhecidos, schema correto, ausências marcadas, anulações sinalizadas)
3. Persistência das `NotaAluno` no banco
4. Recálculo das classificações de aluno afetadas
5. Avaliação das regras de alerta sobre o estado novo
6. Notificação (opcional, v2) de novos alertas relevantes

Cada etapa é candidata a tarefa assíncrona; o frontend só lê o estado consolidado.

## Convenções numéricas para UI

- Notas exibidas com **uma casa decimal e vírgula** ("7,2" não "7.20")
- Deltas exibidos com sinal e cor semântica ("↑ 0,4", "↓ 1,5")
- Percentuais com zero casas decimais por padrão ("38%"), uma casa quando for ambíguo ("38,5%")
- `n` (contagens) sempre inteiro
- "Sem dados" exibido como "—", nunca como "0" ou "null"
