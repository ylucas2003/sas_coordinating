# 10 — Problemas observados e visão de futuro

> **Status:** visão e planos. Boa parte já virou entrega — **o estado de cada
> item está no [19-roadmap.md](19-roadmap.md)**, que é o documento a ler antes
> de abrir sprint. Aqui as marcações ✅ indicam o que já está em produção.
> **Propósito:** juntar num lugar só (a) o que incomoda hoje usando o sistema e
> (b) o que o SAS precisa ser daqui a 6–18 meses, pra depois priorizar.
>
> Marcações:
> - 🔴 problema confirmado por uso real
> - 🟡 suspeita / precisa observar mais
> - ⬜ hipótese do dev, ainda não validada
> - ❓ pergunta que precisa de resposta antes de decidir

---

# Parte 0 — Mapa

Tudo que foi conversado cai em **quatro blocos**, com graus de dependência muito
diferentes entre si:

| Bloco | O que é | Origem | Depende de |
|---|---|---|---|
| **A · Coordenação** | operar o simulado antes dele acontecer: agenda, lembretes, cobrança de professores | áudios 1 e 2 | nada — mas é o maior |
| **B · Integridade do dado** | write-back no Canvas, zero ≠ ausência, média da turma | uso + leitura do código | nada |
| **C · Interface** | filtros unificados, ordenação, range de período, split ano/vestibular/ciclo | uso | nada entre si — são independentes |
| **D · Assistente** | painel não-modal, paridade de tools, apresentação inicial | uso | write-back (só se o chat for escrever) |

Grafo de dependências dentro do bloco A — o único que tem ordem obrigatória:

```
  Cadastro de professores ─┐
                           ├──▶ Requerimento de questões (§2.4)
  Motor de agenda (§2.3) ──┤
                           ├──▶ Lembretes aluno/coordenador (§2.5)
                           │
                           └──▶ Tela de calendário (§2.6)
```

**Leitura de urgência** (sugestão, não decisão):

- 🔥 **B tem sangramento ativo.** As funções de edição apagam o próprio trabalho
  do coordenador em até 5 minutos, hoje, sem avisar ([§1.2](#12-dados-e-ingestão)).
  É o único item da lista que está causando dano enquanto não é tratado.
- 💰 **C é barato e independente.** Nenhum item de interface depende de outro nem
  de migration. São ganhos imediatos que não travam nada.
- 🏗️ **A é o que muda o produto**, e o que exige mais decisão antes de código —
  começando pela pergunta de como se detecta entrega ([§2.4.4](#244-o-ponto-mais-frágil-como-o-sistema-sabe-que-entregou)).
- 🧭 **D é o mais fácil de subestimar.** Tirar o overlay é trivial; dar paridade
  de tools ao assistente é um trabalho contínuo que acompanha todo o resto.

**Como ler este documento:** a Parte 1 é diagnóstico (o que está errado hoje), a
Parte 2 é desenho (o que fazer), a Parte 3 são as escolhas que não dá pra ter dos
dois jeitos, e a Parte 4 é a lista de perguntas que travam decisão.

---

# Parte 1 — Problemas observados

## 1.1 Processo do coordenador (fora do sistema)

🔴 **A dor grande hoje é requerer as questões dos professores, na mão.**
O coordenador pede o simulado a cada professor individualmente e mantém, por
fora, um controle de quem enviou e quem está pendente. É trabalho de secretaria,
recorrente, e o sistema hoje não participa dele em nada. Detalhamento da solução
em [§2.4](#24-aplicação-1--requerimento-de-questões-aos-professores).

🔴 **Não existe agenda no sistema.** Simulado não é uma coisa que se *agenda* no
SAS — ele aparece depois, quando o dado chega do Canvas. Ou seja: o sistema só
conhece o passado. Tudo que é "vai acontecer" (simulado marcado, prazo de
professor, lembrete de aluno) vive fora, na cabeça e na planilha do coordenador.

## 1.2 Dados e ingestão

⬜ **Zero não distingue ausência de abandono.** `pontuacao=0` com `presente=true`
provavelmente é aluno que largou a prova, mas entra na estatística como
desempenho real — puxa média, dispara alerta falso, contamina o insight.
Regra de corte ainda não definida.

⬜ **Duas portas de entrada de dados que podem divergir.** Upload de planilha
(`api/app/ingest`) e sync do Canvas (`api/app/canvas_sync`) alimentam as mesmas
tabelas. Sem regra explícita de precedência, um reprocessamento pode sobrescrever
o outro.

⬜ **Taxonomia de assunto das questões não existe.** A migration 0015 abriu o
campo, mas sem vocabulário controlado o backfill vira texto livre — e aí não dá
pra agregar "aluno vai mal em cinemática" com confiança.

⬜ **Telefone e e-mail de professor não existem em lugar nenhum.** Não vêm do
Canvas (ver [08-integracao-canvas.md](08-integracao-canvas.md) §4.2). Sem
cadastro próprio, nenhum fluxo de cobrança sai do papel.

🔴 **As funções de edição escrevem só no banco local — o Canvas não fica sabendo,
e o sync desfaz a edição.** Foram construídas quando a planilha era a fonte da
verdade. Hoje o Canvas é, e isso inverteu o sentido da escrita sem que o código
acompanhasse.

O caminho hoje é de mão única:

```
coordenador edita  →  PATCH /notas/{aluno}/{simulado}  →  UPSERT em `nota`  →  ✅ tela atualiza
                                                                                    ↓
                       CanvasSync (5 min) ou ReconcileDiario (3h)  →  UPSERT em `nota` ← Canvas
                                                                                    ↓
                                                                       ❌ edição sumiu
```

Confirmado no código: [notas.py](../api/app/routes/notas.py) só faz upsert na
tabela `nota` e recalcula estatísticas — não há chamada ao Canvas em lugar
nenhum. E [upsert_notas_em_lote](../api/app/ingest/upsert.py#L315) faz
`on_conflict="aluno_id,simulado_id"`, ou seja, **sobrescreve** `pontuacao` e
`presente` com o valor do Canvas. A edição não conflita, não avisa: some.

O mesmo vale para `PATCH /simulados/{id}`. Cruzando os campos que ele aceita com
os que [mapear_simulado](../api/app/canvas_sync/mapeador.py#L182-L204) reescreve:

| Campo editável | Existe no Canvas? | Destino do sync |
|---|---|---|
| `nome` | `assignment.name` | 🔴 sobrescrito |
| `nota_maxima` | `assignment.points_possible` | 🔴 sobrescrito |
| `rotulo_curto` | derivado do nome | 🔴 sobrescrito |
| `anulado` | não existe | ✅ sobrevive (conceito só do SAS) |

Ou seja: das quatro edições de simulado, três são ilusórias e uma é real — sem
nada na interface distinguindo umas das outras.

## 1.3 Análise e estatística

⬜ **Limiares de alerta nunca foram calibrados com dado real.** Os números em
`stats/thresholds.py` são chute razoável de projeto, não resultado de observação.
Risco nos dois sentidos: ruído (coordenador ignora tudo) ou silêncio.

## 1.4 Operação e infraestrutura

🔴 **Supabase caiu e derrubou a produção junto** (NXDOMAIN, 13/08/2026). Não há
plano de contingência nem separação entre "banco indisponível" e "sistema fora".

⬜ **O agendador só sabe fazer heartbeat.** Ver [§2.3](#23-o-motor--eventos-agenda-e-disparos) —
é a limitação estrutural que bloqueia as duas frentes novas.

## 1.5 Interface e uso

🔴 **Ciclos não tem filtro por período.** A tela mostra a coluna *Período*
(`08/02/2026 → 08/03/2026`) mas só filtra por Vestibular e Ano letivo
([ciclos.js:12-18](../web/js/screens/ciclos.js#L12-L18)). Com 22 ciclos e
crescendo, não dá pra perguntar "o que rolou entre março e maio".

**Direção: filtro lateral de intervalo, com semântica de interseção** — o ciclo
entra se *encostar* no intervalo, não precisa estar contido nele.

O dado já existe: `Ciclo.periodoInicio` / `periodoFim`
([domain.py:56-63](../api/app/schemas/domain.py#L56-L63)), alimentados por
`atualizar_periodo_ciclo` a partir do min/max das datas dos simulados.

O predicado de interseção — vale escrever explícito, porque é onde esse tipo de
filtro costuma sair errado:

```
ciclo.periodoInicio <= range.fim  E  ciclo.periodoFim >= range.inicio
```

Não é "início E fim dentro do range" (isso seria contenção, o que o pedido
descarta). Um ciclo de 08/02 a 08/03 tem que aparecer num range de 01/03 a 30/04,
mesmo cruzando só 8 dias.

Decisões pendentes:

- ❓ **Extremos abertos.** Preencher só o início ("de março pra frente") deve
  funcionar? Se sim, o campo vazio vira infinito daquele lado — o predicado
  acima já suporta, mas a UI precisa permitir.
- ⚠️ **Ciclo sem período.** `atualizar_periodo_ciclo` só roda quando há simulados
  com data; um ciclo recém-criado e vazio pode ter período nulo. O schema declara
  os campos como `str` obrigatório, então ou isso nunca acontece na prática, ou é
  um erro esperando o primeiro ciclo vazio. Precisa ser checado — e, se puder ser
  nulo, decidir se esse ciclo some ou aparece sempre.
- ⚠️ **Redundância com o filtro "Ano letivo".** Os dois recortam tempo. Um range
  de 01/12/2025 a 31/01/2026 com "Ano letivo = 2026" marcado produz uma
  combinação que o usuário provavelmente não quis. ❓ Range substitui o filtro de
  ano, ou convivem (e aí quem manda)?
- ⚠️ **O range quebra o padrão de chips com contagem.** Todos os filtros laterais
  hoje são listas de opções discretas com contagem (`ITA · 16`). Um intervalo não
  tem opções pra contar. É o primeiro filtro de outro tipo no produto — e por
  isso interage diretamente com a decisão de unificar o formato dos filtros
  (acima): o componente unificado precisa aceitar mais de um tipo de conteúdo
  dentro da seção colapsável, não só chips.
- ❓ Presets ("este ano", "último trimestre", "ciclo atual") junto com os dois
  campos de data? Resolve o caso comum sem obrigar a digitar datas.

🔴 **As tabelas não são ordenáveis — o cabeçalho não é clicável em lugar nenhum.**
Alunos, Simulados e Ciclos abrem direto numa tabela, e em todas as três os `<th>`
são texto morto: sem handler, sem estado de ordenação, sem indicador
([alunos.js:127-137](../web/js/screens/alunos.js#L127-L137),
[ciclos.js:118-124](../web/js/screens/ciclos.js#L118-L124),
[tabela-simulados.js:55-66](../web/js/components/tabela-simulados.js#L55-L66)).

A ordem é fixa e vem do backend — em Alunos, `.order("nome")` no
[alunos.py:95](../api/app/routes/alunos.py#L95). O coordenador não tem como
perguntar "quem tem a menor média?" sem ler 873 linhas.

E a ordem default nem sempre ajuda: a tela de Ciclos intercala anos (*Ciclo 1 ·
IME · 2026*, *Ciclo 1 · IME · 2025*, *Ciclo 2 · ITA · 2026*, *Ciclo 2 · ITA ·
2025*…), o que é justamente o caso em que poder reordenar por ano resolve na hora.

**Direção: cabeçalho clicável ordena — clique alterna asc/desc, com indicador
visível de qual coluna está ativa.** Ordenação no cliente basta: 873 alunos e 148
simulados são volumes pequenos e já vêm inteiros pro browser (não há paginação).

Pontos que precisam de decisão antes de codar:

- ⚠️ **Nulos.** Em Alunos há aluno com Média `—`. Ordenar tratando `—` como zero
  jogaria esses alunos pro topo do "pior desempenho" sem que eles tenham ido mal.
  Nulos devem afundar nos dois sentidos.
- ⚠️ **Colunas categóricas têm ordem semântica, não alfabética.** *Zona* é
  Risco → Cinzenta → Top; *Tendência* é Queda → Estável → Alta. Ordenar por
  alfabeto ("Cinzenta, Risco, Top") não significa nada.
- ⚠️ **Colunas não ordenáveis.** *Trajetória* é sparkline, e a coluna de ação
  ("Ver →") é vazia. Precisam ser explicitamente marcadas como não clicáveis —
  senão o usuário clica e nada acontece, o que é pior que não ter.
- ❓ **O toggle Ranking / A–Z do Painel vira o quê?** Ele é ordenação disfarçada
  de toggle, e único no produto. Com cabeçalho ordenável em toda parte, ou ele
  some (Ranking = ordenar por Média desc, A–Z = ordenar por Aluno asc), ou o
  Painel fica sendo a exceção de novo — o mesmo padrão do problema dos filtros,
  acima.
- ❓ Ordenação persiste ao trocar de filtro ou reseta? E entre visitas à tela?

🔴 **Existem dois sistemas de filtro lateral no produto, e eles não se parecem.**

| | Painel | Alunos · Simulados · Ciclos |
|---|---|---|
| Classes | `psb-*` ([painel.js:456-476](../web/js/screens/painel.js#L456-L476)) | `sim-filtros__*` ([sim-filtros.js](../web/js/components/sim-filtros.js)) |
| Ícone por seção | sim | não |
| Expandir / minimizar | sim | não |
| Contagem por opção | não | sim (`· 281`) |
| Seleção | única | múltipla (chips) |
| "Limpar filtros" | não | sim |

**Direção: padronizar tudo no formato do Painel** — seção com ícone, expansível e
minimizável.

⚠️ Com uma ressalva importante: o formato do Painel é hoje o mais *pobre* dos
dois em conteúdo. Ele não tem contagem por opção, não tem seleção múltipla e não
tem "limpar filtros" — e essas três coisas são úteis (a contagem `AD · 376`
responde uma pergunta antes mesmo de clicar). Padronizar não pode significar
perder isso.

O alvo, então, é **o contêiner do Painel + o conteúdo dos chips**: uma seção
colapsável com ícone, e dentro dela os chips com contagem. Na prática isso é um
componente único de filtro lateral, extraído para `web/js/components/ui/`, já que
hoje o `buildSecao` do Painel é função local e o `sim-filtros` é componente
compartilhado pelas outras três telas.

❓ Seleção múltipla vale para o Painel também? Hoje ele é single-select por
natureza (um ciclo por vez monta a tabela). Se o Painel continuar single-select e
o resto multi-select, o componente precisa suportar os dois modos — o que é
normal, mas precisa ser decidido antes e não descoberto no meio.

🔴 **O filtro "Ciclos" achata três dimensões numa lista só.** O header do Painel
já anuncia as três — *"Ciclo 1 · IME · 2026"* — mas a sidebar oferece uma lista
plana de nomes de ciclo. Para chegar num recorte, o coordenador precisa saber de
cor qual item da lista corresponde a qual combinação de vestibular e ano.

O dado já existe: `Ciclo` tem `anoLetivo` e `vestibularAlvo`
([domain.py:56-60](../api/app/schemas/domain.py#L56-L60)). É a sidebar
([painel.js:479-487](../web/js/screens/painel.js#L479-L487)) que descarta os dois
e renderiza só `c.nome`. Ou seja: **problema de navegação, não de modelagem** —
não precisa de migration.

### Como separar

As três não são eixos independentes — um ciclo *pertence* a um ano e (hoje) a um
vestibular. Então o desenho natural é **hierarquia, não três filtros paralelos**:

```
Ano       2026 · 2025 · 2024        ← escopo mais amplo, muda pouco
  ↓
Vestibular  ITA · IME               ← ver ❓ abaixo
  ↓
Ciclo     Ciclo 1 · Ciclo 2 · …     ← lista já filtrada pelos dois acima
```

Cada nível estreita o seguinte. Ano provavelmente merece ser um seletor fixo no
topo da sidebar (raramente muda), não uma seção expansível como as outras.

✅ **Resolvido pela observação: vestibular é filtro, não lente.** A tela de
Ciclos mostra ciclos separados por vestibular — *Ciclo 1 · IME · 2026*, *Ciclo 2
· ITA · 2026* — e são 22 ciclos no total. Um ciclo pertence mesmo a um
vestibular. Então a hierarquia Ano → Vestibular → Ciclo se sustenta.

**E a tela de Ciclos já faz exatamente essa separação** (filtros "Vestibular" e
"Ano letivo" na sidebar). Ou seja: o Painel é a exceção, não a regra. O que
falta é trazer o Painel para o padrão que o resto do produto já usa — o que
resolve este item junto com o de padronização de formato, acima.

🔴 **A média final da turma conta ausência como zero — confirmado no código.**
Na tela: Matemática 5,4 · Física 4,9 · Química 4,3, mas *Média da turma* = **1,3**,
e "Em zona de corte" acusa **800 de 873**.

A causa está em [`calcularMediasVirtuais`](../web/js/screens/painel.js#L194-L210):

```js
// Retorna valor de uma coluna (real ou virtual). Ausente = 0.
return notasAluno[alunoId]?.[col.sim.id] ?? 0;
```

E em [`mediasPorCol`](../web/js/screens/painel.js#L696-L713) as colunas reais
filtram nulos (`.filter(v => v != null)`) enquanto as virtuais não filtram nada —
porque o valor virtual nunca é nulo, já foi convertido em 0. Com ~250 de 873
alunos por simulado, 5,0 × 250/873 ≈ 1,4, que é o número da tela.

Contamina cinco coisas, não uma: a linha da média, os dois KPIs do cabeçalho, a
ordenação do ranking e a cor do nome do aluno. Diagnóstico completo e correção em
[B.1](#b1--ausência-contando-como-zero-na-média--confirmado).

🔴 **Ciclos não tem filtro por período.** A tela mostra a coluna *Período*
(`08/02/2026 → 08/03/2026`) mas só filtra por Vestibular e Ano letivo
([ciclos.js:12-18](../web/js/screens/ciclos.js#L12-L18)). Com 22 ciclos e
crescendo, não dá pra perguntar "o que rolou entre março e maio".

**Direção: filtro lateral de intervalo, com semântica de interseção** — o ciclo
entra se *encostar* no intervalo, não precisa estar contido nele.

O dado já existe: `Ciclo.periodoInicio` / `periodoFim`
([domain.py:56-63](../api/app/schemas/domain.py#L56-L63)), alimentados por
`atualizar_periodo_ciclo` a partir do min/max das datas dos simulados.

O predicado de interseção — vale escrever explícito, porque é onde esse tipo de
filtro costuma sair errado:

```
ciclo.periodoInicio <= range.fim  E  ciclo.periodoFim >= range.inicio
```

Não é "início E fim dentro do range" (isso seria contenção, o que o pedido
descarta). Um ciclo de 08/02 a 08/03 tem que aparecer num range de 01/03 a 30/04,
mesmo cruzando só 8 dias.

Decisões pendentes:

- ❓ **Extremos abertos.** Preencher só o início ("de março pra frente") deve
  funcionar? Se sim, o campo vazio vira infinito daquele lado — o predicado
  acima já suporta, mas a UI precisa permitir.
- ⚠️ **Ciclo sem período.** `atualizar_periodo_ciclo` só roda quando há simulados
  com data; um ciclo recém-criado e vazio pode ter período nulo. O schema declara
  os campos como `str` obrigatório, então ou isso nunca acontece na prática, ou é
  um erro esperando o primeiro ciclo vazio. Precisa ser checado — e, se puder ser
  nulo, decidir se esse ciclo some ou aparece sempre.
- ⚠️ **Redundância com o filtro "Ano letivo".** Os dois recortam tempo. Um range
  de 01/12/2025 a 31/01/2026 com "Ano letivo = 2026" marcado produz uma
  combinação que o usuário provavelmente não quis. ❓ Range substitui o filtro de
  ano, ou convivem (e aí quem manda)?
- ⚠️ **O range quebra o padrão de chips com contagem.** Todos os filtros laterais
  hoje são listas de opções discretas com contagem (`ITA · 16`). Um intervalo não
  tem opções pra contar. É o primeiro filtro de outro tipo no produto — e por
  isso interage diretamente com a decisão de unificar o formato dos filtros
  (acima): o componente unificado precisa aceitar mais de um tipo de conteúdo
  dentro da seção colapsável, não só chips.
- ❓ Presets ("este ano", "último trimestre", "ciclo atual") junto com os dois
  campos de data? Resolve o caso comum sem obrigar a digitar datas.

🔴 **As tabelas não são ordenáveis — o cabeçalho não é clicável em lugar nenhum.**
Alunos, Simulados e Ciclos abrem direto numa tabela, e em todas as três os `<th>`
são texto morto: sem handler, sem estado de ordenação, sem indicador
([alunos.js:127-137](../web/js/screens/alunos.js#L127-L137),
[ciclos.js:118-124](../web/js/screens/ciclos.js#L118-L124),
[tabela-simulados.js:55-66](../web/js/components/tabela-simulados.js#L55-L66)).

A ordem é fixa e vem do backend — em Alunos, `.order("nome")` no
[alunos.py:95](../api/app/routes/alunos.py#L95). O coordenador não tem como
perguntar "quem tem a menor média?" sem ler 873 linhas.

E a ordem default nem sempre ajuda: a tela de Ciclos intercala anos (*Ciclo 1 ·
IME · 2026*, *Ciclo 1 · IME · 2025*, *Ciclo 2 · ITA · 2026*, *Ciclo 2 · ITA ·
2025*…), o que é justamente o caso em que poder reordenar por ano resolve na hora.

**Direção: cabeçalho clicável ordena — clique alterna asc/desc, com indicador
visível de qual coluna está ativa.** Ordenação no cliente basta: 873 alunos e 148
simulados são volumes pequenos e já vêm inteiros pro browser (não há paginação).

Pontos que precisam de decisão antes de codar:

- ⚠️ **Nulos.** Em Alunos há aluno com Média `—`. Ordenar tratando `—` como zero
  jogaria esses alunos pro topo do "pior desempenho" sem que eles tenham ido mal.
  Nulos devem afundar nos dois sentidos.
- ⚠️ **Colunas categóricas têm ordem semântica, não alfabética.** *Zona* é
  Risco → Cinzenta → Top; *Tendência* é Queda → Estável → Alta. Ordenar por
  alfabeto ("Cinzenta, Risco, Top") não significa nada.
- ⚠️ **Colunas não ordenáveis.** *Trajetória* é sparkline, e a coluna de ação
  ("Ver →") é vazia. Precisam ser explicitamente marcadas como não clicáveis —
  senão o usuário clica e nada acontece, o que é pior que não ter.
- ❓ **O toggle Ranking / A–Z do Painel vira o quê?** Ele é ordenação disfarçada
  de toggle, e único no produto. Com cabeçalho ordenável em toda parte, ou ele
  some (Ranking = ordenar por Média desc, A–Z = ordenar por Aluno asc), ou o
  Painel fica sendo a exceção de novo — o mesmo padrão do problema dos filtros,
  acima.
- ❓ Ordenação persiste ao trocar de filtro ou reseta? E entre visitas à tela?

🔴 **Existem dois sistemas de filtro lateral no produto, e eles não se parecem.**

| | Painel | Alunos · Simulados · Ciclos |
|---|---|---|
| Classes | `psb-*` ([painel.js:456-476](../web/js/screens/painel.js#L456-L476)) | `sim-filtros__*` ([sim-filtros.js](../web/js/components/sim-filtros.js)) |
| Ícone por seção | sim | não |
| Expandir / minimizar | sim | não |
| Contagem por opção | não | sim (`· 281`) |
| Seleção | única | múltipla (chips) |
| "Limpar filtros" | não | sim |

**Direção: padronizar tudo no formato do Painel** — seção com ícone, expansível e
minimizável.

⚠️ Com uma ressalva importante: o formato do Painel é hoje o mais *pobre* dos
dois em conteúdo. Ele não tem contagem por opção, não tem seleção múltipla e não
tem "limpar filtros" — e essas três coisas são úteis (a contagem `AD · 376`
responde uma pergunta antes mesmo de clicar). Padronizar não pode significar
perder isso.

O alvo, então, é **o contêiner do Painel + o conteúdo dos chips**: uma seção
colapsável com ícone, e dentro dela os chips com contagem. Na prática isso é um
componente único de filtro lateral, extraído para `web/js/components/ui/`, já que
hoje o `buildSecao` do Painel é função local e o `sim-filtros` é componente
compartilhado pelas outras três telas.

❓ Seleção múltipla vale para o Painel também? Hoje ele é single-select por
natureza (um ciclo por vez monta a tabela). Se o Painel continuar single-select e
o resto multi-select, o componente precisa suportar os dois modos — o que é
normal, mas precisa ser decidido antes e não descoberto no meio.

🔴 **O filtro "Ciclos" achata três dimensões numa lista só.** O header do Painel
já anuncia as três — *"Ciclo 1 · IME · 2026"* — mas a sidebar oferece uma lista
plana de nomes de ciclo. Para chegar num recorte, o coordenador precisa saber de
cor qual item da lista corresponde a qual combinação de vestibular e ano.

O dado já existe: `Ciclo` tem `anoLetivo` e `vestibularAlvo`
([domain.py:56-60](../api/app/schemas/domain.py#L56-L60)). É a sidebar
([painel.js:479-487](../web/js/screens/painel.js#L479-L487)) que descarta os dois
e renderiza só `c.nome`. Ou seja: **problema de navegação, não de modelagem** —
não precisa de migration.

### Como separar

As três não são eixos independentes — um ciclo *pertence* a um ano e (hoje) a um
vestibular. Então o desenho natural é **hierarquia, não três filtros paralelos**:

```
Ano       2026 · 2025 · 2024        ← escopo mais amplo, muda pouco
  ↓
Vestibular  ITA · IME               ← ver ❓ abaixo
  ↓
Ciclo     Ciclo 1 · Ciclo 2 · …     ← lista já filtrada pelos dois acima
```

Cada nível estreita o seguinte. Ano provavelmente merece ser um seletor fixo no
topo da sidebar (raramente muda), não uma seção expansível como as outras.

✅ **Resolvido pela observação: vestibular é filtro, não lente.** A tela de
Ciclos mostra ciclos separados por vestibular — *Ciclo 1 · IME · 2026*, *Ciclo 2
· ITA · 2026* — e são 22 ciclos no total. Um ciclo pertence mesmo a um
vestibular. Então a hierarquia Ano → Vestibular → Ciclo se sustenta.

**E a tela de Ciclos já faz exatamente essa separação** (filtros "Vestibular" e
"Ano letivo" na sidebar). Ou seja: o Painel é a exceção, não a regra. O que
falta é trazer o Painel para o padrão que o resto do produto já usa — o que
resolve este item junto com o de padronização de formato, acima.

🟡 **A média final da turma não conversa com as médias por matéria.** Na tela:
Matemática 5,4 · Física 4,9 · Química 4,3, mas *Média da turma* = **1,3** — e o
KPI "Em zona de corte" acusa **800 de 873**. Por aluno o cálculo fecha (6,7 /
8,7 / 10,0 → 8,6). A hipótese mais provável é que a média final agrega os 873
alunos do ciclo, enquanto as médias por matéria só consideram quem tem nota —
o que faz o número final ser puxado por centenas de alunos sem dado ou com zero.
Se for isso, é a mesma raiz do problema de [§1.2](#12-dados-e-ingestão) (zero ≠
ausência) aparecendo no lugar mais visível do produto: o primeiro número que o
coordenador lê ao abrir o sistema. Precisa de confirmação no dado antes de virar
diagnóstico.

## 1.6 Assistente (chat)

### 1.6.1 A abertura não mostra o que o assistente sabe fazer

Hoje a tela inicial da conversa são **4 frases fixas em código**
([conversa.js:10-15](../web/js/components/chat/conversa.js#L10-L15)) sob o título
*"Algumas perguntas pra começar:"*. Contra **21 ferramentas** disponíveis, isso
expõe menos de um quinto da superfície — e o resto o coordenador só descobre por
tentativa.

Três defeitos concretos:

1. **Lista plana e estática.** Quatro exemplos não organizam nada; não dizem que
   existem categorias (buscar, comparar, diagnosticar, gerar artefato).
2. **Não sabe onde o usuário está.** O launcher é montado uma vez e ignora a
   rota. Se o coordenador abre o chat na ficha do Ciclo 6, as sugestões são as
   mesmas de sempre — nada sobre o Ciclo 6.
3. 🔴 **O aluno vê sugestões de coordenador.** `SUGESTOES_INICIAIS` é global e
   o `conversaPanel` é o mesmo para os dois perfis —
   [main.js:151-155](../web/js/main.js#L151-L155) só troca o rótulo do FAB de
   "Assistente" para "Mentor". Ou seja, um aluno abre o Mentor e lê *"Quais
   alunos estão em risco no momento?"*. As tools dele são outras (as 6 de
   `tools_aluno.py`), o prompt é outro, só as sugestões não são.

### 1.6.2 Inventário: o que o assistente tem hoje

**Coordenador — 21 tools** (`api/app/chat/tools/`):

| Módulo | Tools |
|---|---|
| `lookup` (6) | `buscar_aluno_por_nome` · `obter_aluno` · `listar_ciclos` · `listar_simulados` · `obter_simulado` · `listar_materias` |
| `stats` (4) | `estatisticas_ciclo` · `trajetoria_aluno` · `histograma_simulado` · `notas_simulado` |
| `heuristicas` (4) | `alunos_em_risco` · `alunos_destaque` · `tendencia_aluno` · `materias_problematicas` |
| `relatorios` (3) | `relatorio_aluno` · `historico_aluno` · `relatorio_ciclo` |
| `comparar` (2) | `comparar_ciclos` · `alunos_similares` |
| `artefato` (2) | `gerar_grafico` · `exportar_csv` |

**Aluno — 6 tools** (`tools_aluno.py`): `minhas_notas` ·
`meu_desempenho_em_simulado` · `minha_evolucao` · `meu_streak` ·
`minhas_questoes_erradas` · `meu_insight_do_ciclo`.

### 1.6.3 Lacunas: o que é navegável na plataforma e o chat não alcança

O alvo declarado é **paridade**: tudo que existe como tela, filtro ou número no
produto tem que ser alcançável pela conversa. Cruzando as telas com as tools:

| Superfície do produto | Onde vive | Tool? |
|---|---|---|
| **Alertas** | `routes/alertas.py` · `ui/alert-card.js` | ❌ nenhuma |
| **Insights do ciclo (coordenação)** | `stats/insights.py` · `ui/insights-painel.js` | ❌ nenhuma |
| **Sedes e turmas** | `routes/dimensoes.py` | ❌ nenhuma |
| **Questões (visão coordenação)** | `canvas_sync/questoes.py` · migration 0015 | ❌ nenhuma |
| **Arquivos de prova** | `routes/arquivos.py` · migration 0017 | ❌ nenhuma |
| **Listar alunos por zona / perfil / turma / sede** | tela Alunos | 🟡 parcial — só os extremos (`alunos_em_risco`, `alunos_destaque`) |
| **Comparar alunos · comparar simulados** | função "Comparar" ([04-screens](04-screens.md)) | 🟡 parcial — só `comparar_ciclos` |
| **Heatmap matéria × simulado** | ficha do aluno | ❌ nenhuma |
| **Navegar até uma tela** | toda a plataforma | ❌ o chat não consegue mandar o usuário pra lugar nenhum |
| **Editar nota / anular simulado** | Painel, ficha do simulado | ❌ chat é read-only |

Duas coisas saltam dessa tabela:

⚠️ **Os alertas e os insights — o coração "proativo" do produto, segundo o
README — são justamente o que o assistente não enxerga.** Ele consegue calcular
quem está em risco na hora, mas não consegue ler o que o próprio sistema já
sinalizou.

⚠️ **A assimetria de questões está invertida.** O *aluno* consegue perguntar quais
questões errou (`minhas_questoes_erradas`); o *coordenador* não tem nenhuma tool
de questão. Quem precisa da visão agregada é quem não a tem.

❓ Escrita pelo chat ("marca fulano como ausente no P22") entra no escopo? Dado
[§2.7](#27-bloco-b--escrita-de-volta-no-canvas-write-back), só faz sentido
depois do write-back — senão o chat passa a produzir a mesma edição fantasma.

### 1.6.4 O chat bloqueia a navegação enquanto está aberto

🔴 Hoje o "drawer" é **modal de fato**: `.chat-overlay.is-aberto` tem `inset: 0`
com `pointer-events: auto` ([chat.css:48-62](../web/styles/chat.css#L48-L62)),
cobrindo a página inteira, e o clique nele fecha o chat
([launcher.js](../web/js/components/chat/launcher.js)). Resultado: **ou você
conversa, ou você usa o sistema.** Perguntar "quais alunos estão em risco?" e ir
olhar a ficha de um deles exige fechar a conversa.

Isso é o oposto do que o assistente deveria ser: um copiloto que acompanha a
navegação.

Detalhamento da solução em [§2.8](#28-bloco-d--assistente-como-copiloto).


---

# Parte 2 — Visão de futuro

## 2.1 O que muda no posicionamento

O README diz hoje: *"ferramenta analítica e investigativa, não ERP escolar"*.
Os dois áudios empurram o produto para além disso: além de **ler o passado**
(análise de desempenho), o SAS passa a **operar o futuro** — agendar, cobrar,
lembrar, acompanhar prazo.

É uma mudança de natureza, não de tamanho. Vale nomear a tensão em vez de deixá-la
implícita: ⚠️ *coordenar um simulado* é exatamente o tipo de função que o README
tentou excluir ao dizer "não ERP escolar". Duas leituras possíveis:

- **(a) O posicionamento se amplia:** o SAS é a central de operação do ITM —
  analisa *e* executa. O argumento a favor: quem analisa o resultado é quem
  monta a prova; separar as duas coisas em ferramentas diferentes é artificial.
- **(b) O posicionamento se mantém, e a operação é um módulo lateral** que serve
  a análise (sem simulado montado no prazo, não há dado pra analisar).

❓ **Decidir isso antes de desenhar a navegação** — muda se "Coordenação" é uma
aba entre iguais ou o novo centro do produto.
## 2.2 Módulo Coordenação — o que os dois áudios pedem

Os áudios chegaram como dois assuntos (agenda/lembretes e cobrança de
professores), mas descrevem **uma coisa só**: o SAS passar a operar o simulado
antes dele acontecer. Vale tratá-los assim, porque a ordem de construção depende
disso — o segundo não existe sem o primeiro.

### 2.2.1 A linha do tempo do simulado

É a estrutura que organiza tudo. Hoje o SAS só existe do lado direito:

```
   D-30        D-21        D-14         D-7        D+0         D+1
    │           │           │            │          │           │
    │           │           │            │      aplicação   correção
    │           │           │            │          │           │
    ├───────────┴───────────┴────────────┤          │           ├─────────────▶
    │        ZONA CEGA — nada disso                 │           │   o SAS de hoje
    │        existe no sistema hoje                 │           │   começa aqui
    │                                               │           │   (sync do Canvas)
    └── agendar · distribuir · cobrar · receber ────┘
```

Tudo que os áudios pedem mora na zona cega. E é justamente onde está o trabalho
manual do coordenador — o sistema hoje ajuda a *analisar* o simulado e não ajuda
em nada a *produzi-lo*.

### 2.2.2 Motor e aplicações

Separar isso é o que evita construir a cobrança de professor como um caso
especial que não serve pra mais nada:

```
┌─────────────────────────────────────────────────────┐
│  MOTOR: eventos de agenda + regras + disparos       │  ← §2.3
│  (não sabe o que é professor, aluno ou simulado)    │
└─────────────────────────────────────────────────────┘
        ▲                    ▲                    ▲
        │                    │                    │
  Requerimento de       Lembretes de         Lembretes de
  questões (§2.4)       aluno (§2.5)         coordenador (§2.5)
```

O motor é genérico: "nesta data, para este destinatário, por este canal, com esta
repetição, enquanto esta condição for verdadeira". As aplicações é que dizem quem
é o destinatário e o que encerra a cobrança.

### 2.2.3 Modelo conceitual

| Entidade | O que é | Novo? |
|---|---|---|
| **Professor** | nome, disciplina(s), e-mail, telefone com WhatsApp | 🆕 não existe |
| **Evento de agenda** | algo marcado numa data. 1º tipo: simulado | 🆕 |
| **Requerimento** | *"o professor X deve N questões de matéria Y para o simulado Z"* | 🆕 |
| **Regra de lembrete** | a cadência — quem, quando, com que repetição, até quando | 🆕 |
| **Disparo** | uma mensagem concreta: destinatário, canal, horário, estado | 🆕 |
| Simulado | já existe, mas hoje só nasce *depois* de aplicado | ♻️ ganha fase pré-aplicação |

⚠️ **A decisão estrutural mais importante do módulo: a unidade de cobrança é o
Requerimento, não o professor.**

A matriz que o coordenador preenche (professor × matéria × quantidade) não é uma
tela de configuração — cada célula preenchida **é uma linha de Requerimento**, e é
ela que se cobra, que tem prazo e que é dada por entregue.

A diferença é prática: um professor que dá Física e Matemática no mesmo simulado
tem **dois** entregáveis. Se a cobrança for modelada por professor, ele entrega
Física, o sistema o marca como resolvido e **para de cobrar a Matemática** — o
fluxo falha exatamente no professor mais sobrecarregado. Modelado por
requerimento, isso não acontece.

### 2.2.4 Estados do requerimento

```
   pendente ──────────────▶ entregue
      │                        ▲
      │                        │
      └──▶ cancelado ──────────┘
           (simulado desmarcado
            ou questões redistribuídas)
```

*Atrasado* não é estado — é derivado da distância até a data do evento. Tratar
como estado obriga alguém a "virar a chave" e cria uma máquina que sai de sincronia
com o calendário.

❓ Falta um estado de **escalonamento** ("cobrei 14 vezes e nada")? Ver §2.4.

### 2.2.5 Os três destinatários

O áudio 1 cita explicitamente lembretes para aluno e coordenador, não só
professor. São três públicos com gatilhos diferentes:

| Destinatário | O que dispara | Exemplo | O que encerra |
|---|---|---|---|
| **Professor** | requerimento pendente | *"faltam 21 dias e você deve 6 questões de Física"* | entrega |
| **Aluno** | evento se aproximando | *"simulado de Matemática amanhã, 7h"* | a data passar |
| **Coordenador** | estado agregado | *"3 professores pendentes a 7 dias do P27"* | nada — é informativo |

Note que só o do professor tem condição de parada dependente de uma ação. Os
outros dois são bem mais simples — e por isso são o melhor lugar pra validar o
motor antes de encarar a cobrança inteira.

---

## 2.3 O motor — eventos, agenda e disparos

### 2.3.1 Como funciona hoje (levantamento)

O que existe é **EventBridge como relógio**, não como barramento de eventos:

```
EventBridge Rule (cron fixo)  →  ApiDestination (HTTPS POST)  →  rota FastAPI
                                 header X-Scheduler-Secret        (toda a lógica)
```

Definido em [infra/sas_scheduler/sas_scheduler_stack.py](../infra/sas_scheduler/sas_scheduler_stack.py),
são **4 schedules estáticos**, escritos em código e criados no `cdk deploy`:

| Schedule | Intervalo | Rota | Estado |
|---|---|---|---|
| `CanvasSync` | 5 min | `/canvas-sync/run` | implementado |
| `AlertasCheck` | 1 h | `/alertas/verificar` | implementado |
| `CobrancaProfessor` | 1 h | `/cobranca/verificar` | **placeholder — retorna `not_implemented`** |
| `ReconcileDiario` | 06:00 UTC | `/canvas-sync/reconciliar` | implementado |

Três propriedades importantes desse desenho:

1. **A AWS não sabe nada de domínio.** Ela só acorda a API no horário. Nenhum
   dado de negócio trafega no evento — o payload é vazio.
2. **Os schedules são de código, não de dados.** Criar um novo hoje exige editar
   a stack e fazer deploy. Não há como a aplicação criar um agendamento em runtime.
3. **Não existe estado de disparo.** Ninguém registra "esse lembrete foi enviado",
   "falhou", "foi respondido". A cobrança já tem o gatilho de pé há um mês, batendo
   de hora em hora numa rota que não faz nada.

### 2.3.2 O que falta

O gap é (2) e (3): agendamento **por instância** e **estado de entrega**.

**Recomendação: manter o EventBridge como relógio e mover a agenda para o banco.**

```
EventBridge (tick 1h, já existe)
        ↓
POST /cobranca/verificar   ← o "despachante"
        ↓
  SELECT dos disparos que venceram agora   (tabela no Postgres)
        ↓
  envia (Z-API + e-mail) e grava resultado  (idempotente por disparo)
```

Por que essa e não "um schedule da AWS por lembrete":

- O volume é baixíssimo (dezenas de professores × alguns simulados). Um tick
  horário varrendo uma tabela resolve com folga.
- A regra de cadência muda de ideia — mudar uma linha de SQL é barato; recriar
  centenas de schedules na AWS não é.
- Cancelamento fica trivial: professor entregou → os disparos pendentes dele
  simplesmente não são mais selecionados. Com schedules na AWS, seria preciso
  deletar cada um.
- O histórico de "o que foi enviado, quando, por qual canal, com que resultado"
  é requisito de qualquer jeito — e ele mora no banco, não na AWS.

O custo dessa escolha é **granularidade de 1 hora** e um tick que roda sempre,
mesmo sem nada a fazer. Ambos irrelevantes no volume atual.

### 2.3.3 Decisões do motor

❓ **Disparos materializados ou calculados?** Materializar (gravar todas as linhas
futuras na criação do evento) dá rastreabilidade e permite editar um disparo
específico; calcular a cada tick evita inconsistência quando a data do simulado
muda. Provavelmente materializar + regerar ao alterar o evento.

✅ **Independente dessa escolha: todo disparo reverifica o estado antes de sair**
(decisão de [§2.4.4](#244-detecção-de-entrega--decidido-em-camadas-com-guarda-antes-do-envio)).
Isso reduz o peso da pergunta acima — se a checagem final é sempre no envio, um
disparo materializado desatualizado não causa dano, só um no-op.

❓ **Janela de silêncio.** Nada deve sair às 2h da manhã. Onde mora essa regra —
no motor (global) ou na regra de lembrete (por aplicação)?

❓ **Idempotência.** Se o tick rodar duas vezes (retry da AWS, deploy no meio),
o disparo não pode sair duplicado. Marca-se antes ou depois do envio? Antes
arrisca perder mensagem; depois arrisca duplicar. Provavelmente antes + retry
explícito no estado `falhou`.

### 2.3.4 O Canvas ajuda com o agendamento? (levantamento)

❓ levantada ao definir a sprint: *"o Canvas disponibiliza um webhook disparado
quando chega o momento do evento? isso economizaria infra."*

**Resposta: não. O Canvas não tem nenhum evento disparado por tempo.** Tudo que
ele emite é disparado por *ação de alguém*:

| Mecanismo | O que emite | Disparado por |
|---|---|---|
| **Live Events / Subscriptions** | `SUBMISSION_CREATED`, `SUBMISSION_UPDATED`, `ATTACHMENT_CREATED`, `QUIZ_SUBMITTED`, `GRADE_CHANGE` | ação do usuário |
| **PNS** (Platform Notification Service) | `LtiHelloWorldNotice`, `LtiAssetProcessorSubmissionNotice`, `LtiContextCopyNotice` | ação/contexto |

Nada no catálogo é do tipo "a data chegou" ou "faltam N dias"
([subscriptions_appendix.md](canvas-api/guides/subscriptions_appendix.md),
[pns.md](canvas-api/guides/pns.md)).

Faz sentido: *"faltam 21 dias para o simulado"* é uma condição sobre o tempo, e
ninguém no Canvas está observando o relógio por nós. **O tick continua sendo
nosso** — a recomendação de §2.3.2 não muda.

#### Onde o webhook ajuda de verdade

⭐ **`ATTACHMENT_CREATED` e `SUBMISSION_CREATED` avisam no instante em que um
arquivo é enviado.** Se o professor entregar via Canvas, a camada 1 da detecção
([§2.4.4](#244-detecção-de-entrega--decidido-em-camadas-com-guarda-antes-do-envio))
deixa de precisar de consulta periódica. O webhook não economiza o relógio,
economiza a *verificação*.

⚠️ **Descoberta lateral: o Canvas já notifica alunos sobre prazos sozinho.**
([notification_preferences.md](canvas-api/reference/notification_preferences.md))
Frequência configurável por aluno (`immediately`/`daily`/`weekly`/`never`), pelos
canais de comunicação do Canvas. Não substitui o motor — sem customização de
cadência, sem WhatsApp — mas **pode duplicar**. ❓ Checar o que está ligado hoje
antes de mandar lembrete de aluno.

---

### 2.3.5 Fonte da verdade — decidido: SAS origina, Canvas recebe

✅ **Decisão (17/08/2026):** o SAS deixa de ser espectador do Canvas. O simulado
**nasce no SAS** no momento do agendamento, e o SAS cria o Assignment
correspondente no Canvas via API.

Viável: `POST /api/v1/courses/:course_id/assignments`
([assignments.md:759](canvas-api/reference/assignments.md)) aceita `name`,
`points_possible`, `due_at`, `unlock_at`, `published`.

#### A formulação precisa: fonte da verdade **por domínio**

"Centralizar tudo no Canvas" está errado — mas "centralizar tudo no SAS" também,
e por um motivo concreto: **o SAS não produz as notas.** O aluno faz a prova no
Canvas, o Canvas corrige e é ele quem sabe se a submission veio `missing`,
`excused` ou `unsubmitted`. Não dá pra ser fonte da verdade de um dado que você
não gera.

O desenho que sustenta os dois lados:

| Domínio | Dono | Por quê |
|---|---|---|
| Agenda, eventos, lembretes, disparos | **SAS** | não existe no Canvas |
| Professores, requerimentos, distribuição de questões | **SAS** | não existe no Canvas |
| Ciclos, classificação, zona, alertas, insights | **SAS** | conceitos do SAS |
| Identidade do simulado (nome, data, escala, publicação) | **SAS** | passa a nascer no agendamento |
| Submissões, notas, presença/ausência, questões | **Canvas** | produzidos pelo ato de fazer a prova |
| Matrículas, turmas, alunos | **Canvas** | origem administrativa do colégio |

O **Assignment é o objeto de fronteira**: criado pelo SAS, preenchido pelo Canvas.

#### A regra operacional que faz "casado" funcionar

> **Campo originado no SAS nunca é sobrescrito pelo sync.**

Hoje é o oposto: [`mapear_simulado`](../api/app/canvas_sync/mapeador.py#L182-L204)
reescreve `nome`, `nota_maxima` e `rotulo_curto` a cada reconcile
([§1.2](#12-dados-e-ingestão)). Com a inversão, esses três passam a ser escritos
**pelo SAS no Canvas**, e o sync tem que parar de trazê-los de volta. O sync
continua trazendo notas, presença e questões — que continuam sendo do Canvas.

#### O que essa decisão resolve de graça

1. ⭐ **Some o problema de casamento.** A alternativa "evento só no SAS, casa
   depois" exigiria heurística de nome/data pra ligar o evento ao Assignment que
   apareceu. Criando o Assignment, o SAS recebe o `id` na resposta e grava direto
   em `external_id` — determinístico, sem heurística.
2. **O simulado existe desde o agendamento.** Hoje ele só nasce depois de
   aplicado, o que é a raiz da "zona cega" de [§2.2.1](#221-a-linha-do-tempo-do-simulado).
3. **Canvas para de ficar desatualizado.** Se o SAS é quem define nome e escala,
   professor e aluno olhando o Canvas veem a mesma coisa que a coordenação.

#### O que ela custa

⚠️ **Puxa o write-back ([§2.7](#27-bloco-b--escrita-de-volta-no-canvas-write-back))
para dentro da sprint.** Não o write-back de *notas* — esse continua sendo o item
do bloco B — mas o de *assignment*, que é a mesma infra: cliente Canvas com
escrita, tratamento de falha, e a decisão de o que fazer quando o Canvas recusa.

⚠️ **Falha na criação vira estado, não exceção.** Se o SAS agenda mas o Canvas
recusa (permissão, curso errado, rede), o simulado fica num limbo: existe no SAS,
não existe no Canvas. ❓ O agendamento é transacional (não salva se o Canvas
falhar) ou o simulado nasce em `pendente_no_canvas` com retry?

⚠️ **Em que curso o Assignment é criado?** O sync descobre os cursos por nome
(`{ano} 3o ITA/IME Simulados`). Criando de fora, o SAS precisa saber o
`course_id` de destino — e escolher, quando houver mais de um.

❓ **E os simulados que já existem?** Os 148 atuais nasceram no Canvas. A regra
"campo do SAS não é sobrescrito" vale retroativamente pra eles, ou só pros novos?

---

## 2.4 Aplicação 1 — Requerimento de questões aos professores

Objetivo: eliminar a cobrança manual. O coordenador cria o simulado, distribui as
questões, e **nunca mais toca no assunto** até as questões chegarem.

### 2.4.1 Cadastro de professores (novo)

Aba de gestão de professores. Campos mínimos:

| Campo | Obrigatório | Nota |
|---|---|---|
| Nome | sim | |
| Disciplina | sim | ❓ uma só, ou várias? Professor que dá Física e Matemática existe? |
| E-mail | sim | canal de notificação |
| Telefone | sim | **precisa ter WhatsApp ativo** |

❓ O professor tem acesso à plataforma (login) ou é apenas destinatário de
notificação? Muda muito o escopo — ver §2.4.4.

### 2.4.2 Criação do simulado pelo coordenador

1. Escolhe o **tipo**: `ITA Fase 1`, `ITA Fase 2`, `IME Fase 1`, `IME Fase 2`,
   ou **modelo aberto** (livre).
2. Define a **data**.
3. **Distribui as questões** numa UI simples: matriz professor × matéria, um
   número em cada célula. Cada célula preenchida vira um Requerimento (§2.2.3).
4. Ao salvar, o sistema **cria o evento de agenda e instancia o fluxo base** —
   o coordenador não configura cadência nenhuma.

❓ O tipo do simulado pré-preenche a distribuição (ITA F1 = tantas de Matemática,
tantas de Física…)? Seria o maior ganho de tempo da tela — o coordenador só
ajustaria quem faz o quê, não quanto.

### 2.4.3 Fluxo base (definido por nós, não pelo coordenador)

Cadência por **requerimento pendente**, contada a partir da data do simulado:

| Distância do simulado | Frequência | Total acumulado |
|---|---|---|
| 4 semanas antes | 1 notificação, uma vez | 1 |
| 3 semanas antes | 1 por dia | ~8 |
| 2 semanas antes até a entrega | 2 por dia | ~36 |

Todas por **WhatsApp e e-mail**, em paralelo. Só dispara se o requerimento ainda
estiver `pendente`.

⚠️ Somando: um professor que só entrega na véspera recebe da ordem de **35-40
mensagens por requerimento** — e o dobro disso se tiver duas matérias. Vale
confirmar se é isso mesmo, e ver o escalonamento em §2.4.6.

### 2.4.4 Detecção de entrega — decidido: em camadas, com guarda antes do envio

✅ **Decisão (17/08/2026):** não é uma opção só. São três sinais de entrega e uma
regra de guarda.

| Camada | Sinal | Natureza |
|---|---|---|
| 1 | **Arquivo salvo** correspondente àquele professor na plataforma | prova real |
| 2 | **Entrega por e-mail** detectada | prova real |
| 3 | **Botão no WhatsApp** ("enviei") | declaração |

⚠️ **A guarda é o mais importante do desenho: antes de disparar qualquer
mensagem, consultar o banco.** O professor pode ter entrado na plataforma e
carregado o arquivo sem avisar ninguém — cobrar quem acabou de entregar é
exatamente o que queima o fluxo.

Isso tem consequência direta no motor: **o disparo é decidido no instante do
envio, não no instante do agendamento.** Mesmo com disparos materializados
(§2.3.3), cada um passa por uma reverificação de estado antes de sair. Um disparo
materializado é uma *intenção*, não uma ordem.

#### O que isso puxa pra dentro do escopo

- 🆕 **Fluxo de salvamento do arquivo do professor.** A camada 1 exige que exista
  um lugar onde o arquivo do professor fica associado a ele.
  ❓ Quem salva: o próprio professor (exige login/área de professor) ou o
  coordenador salvando o que recebeu? Muda o tamanho da sprint.
- 🆕 **Ingestão de e-mail.** A camada 2 exige ler uma caixa de entrada e casar
  remetente + anexo com um requerimento. É a camada mais cara das três e a única
  que precisa de infraestrutura nova além do provedor de envio.
  ❓ Vale nesta sprint, ou entra depois das camadas 1 e 3?

#### O conflito entre declaração e prova

❓ **O que acontece quando o professor aperta o botão e não existe arquivo?** As
camadas 1 e 2 são prova; a 3 é palavra. Elas vão divergir. Opções:

- **Confiar com prazo de carência:** para a cobrança por N dias; se o arquivo não
  aparecer, ela volta. Respeita o professor sem desligar a rede de segurança.
- **Responder pedindo o arquivo:** o botão vira início de conversa, não fim.
- **Avisar o coordenador:** "fulano declarou entrega mas não há arquivo".

⬜ Sugestão: carência + aviso ao coordenador. Nunca aceitar a declaração como
estado final `entregue` — no máximo como `entrega_declarada`, que é um estado a
mais na máquina de §2.2.4.

### 2.4.5 Canais — WhatsApp (Z-API) e e-mail

Infraestrutura: **Z-API, com uma ou duas instâncias no telefone do Ari**.

⚠️ Z-API é WhatsApp não-oficial. O número do Ari é o ativo em risco: se for
bloqueado, o colégio perde um canal real, não só uma feature. Mitigações que são
responsabilidade nossa:

- **Nunca mandar mensagens idênticas.** Variar o texto por disparo (templates com
  variações, não uma string fixa) — repetição literal em volume é o padrão que o
  WhatsApp classifica como robô.
- **Pedir aos professores** que reajam às mensagens do Ari de Sá e **salvem o
  contato** — interação de volta e contato salvo são os sinais mais fortes contra
  bloqueio.
- ⬜ Espaçar os envios (não disparar N professores no mesmo segundo) e respeitar
  janela de horário.

❓ Uma ou duas instâncias? Duas permitem separar tráfego (professores num número,
alunos noutro), limitando o estrago se uma cair. Custo maior.

❓ E-mail sai por onde? Não há provedor de e-mail no projeto hoje.

### 2.4.6 Escalonamento

❓ A cadência de §2.4.3 é agressiva e não tem saída: se o professor simplesmente
não responde, o sistema continua mandando 2×/dia até a data. Duas alternativas a
considerar, ambas mais úteis que mais mensagens:

- **Teto + escalonamento:** a partir de X mensagens sem resposta, para de cobrar
  o professor e passa a avisar o coordenador — que é quem pode agir de verdade.
- **Plano B automático:** a N dias do simulado com requerimento pendente, alertar
  que aquele bloco de questões precisa de outra origem.

---
## 2.5 Aplicação 2 — Lembretes de aluno e de coordenador

Citada no áudio 1 ("posso criar lembretes para aluno, para coordenador de
determinadas situações") e deixada com escopo limitado de propósito. Vale manter
assim, mas registrar por quê ela importa:

**É o caminho mais barato de validar o motor.** Um lembrete de aluno não depende
de cadastro novo (o aluno já existe, com e-mail vindo do Canvas), não depende de
detecção de entrega, e não tem risco de bloqueio de WhatsApp se for só por e-mail.
Prova o motor ponta a ponta com uma fração do escopo da cobrança de professor.

Candidatos de gatilho, todos derivados de dados que já existem:

| Destinatário | Gatilho | Origem do dado |
|---|---|---|
| Aluno | simulado marcado para amanhã | evento de agenda |
| Aluno | insight do ciclo novo disponível | migration 0016 |
| Coordenador | resumo de requerimentos pendentes | §2.4 |
| Coordenador | alerta disparado sobre aluno da sua sede | `routes/alertas.py` |

❓ Aluno recebe por WhatsApp também, ou só e-mail? São ~873 alunos — volume que
muda completamente o cálculo de risco do Z-API, e o argumento pela segunda
instância dedicada.

---

## 2.6 A tela de gestão do calendário

Aba **Coordenação**, pedida no áudio 1: *"uma página de gestão desse calendário
com as principais ações que podem ser feitas"*.

Já existe um [`calendario-anual.js`](../web/js/components/calendario-anual.js) em
uso na tela de Simulados ("Mostrar calendário · 64 dia(s)"), mas ele é
**retrospectivo** — mostra o que foi aplicado. A tela nova é prospectiva e
editável, o que é outro componente.

❓ Quais ações entram no primeiro corte? Candidatas, em ordem de valor aparente:

| Ação | Depende de |
|---|---|
| Criar simulado (data + tipo + matriz de distribuição) | §2.4.2 |
| Ver status de cobrança por professor num evento | §2.4.4 |
| Marcar requerimento como recebido | §2.4.4 opção (b) |
| Editar data do evento (com regeração dos disparos) | §2.3.3 |
| Disparar lembrete manual agora | motor |
| Cancelar evento | máquina de estados §2.2.4 |

⚠️ **Editar a data é a ação que mais exige do motor.** Mover um simulado de 20/05
para 03/06 invalida todos os disparos já materializados. Se a decisão de §2.3.3
for "materializar", essa tela obriga a ter regeração desde o primeiro dia.

---

## 2.7 Bloco B — Escrita de volta no Canvas (write-back)

Fecha o buraco de [§1.2](#12-dados-e-ingestão). O princípio: **o Canvas é a fonte
da verdade, então toda edição tem que passar por ele.**

```
coordenador edita
      ↓
PUT no Canvas  ────── falhou? → erro na tela, nada muda no banco
      ↓ ok
grava local (otimista) + deixa o sync confirmar
```

Escrever no Canvas primeiro e só depois no banco é o que garante que o sync
seguinte *confirme* a edição em vez de desfazê-la.

### Endpoints disponíveis

Já documentados em [submissions.md](canvas-api/reference/submissions.md):

| Uso | Endpoint |
|---|---|
| Uma nota | `PUT /courses/:id/assignments/:id/submissions/:user_id` → `submission[posted_grade]` |
| Em lote | `POST /courses/:id/assignments/:id/submissions/update_grades` → `grade_data[<id>][posted_grade]` |

O de lote responde com um objeto `Progress` (assíncrono) — exige polling, não é
fire-and-forget.

### Mapeamento de `presente=false`

O sync deriva ausência de três sinais
([derivar_presente](../api/app/canvas_sync/mapeador.py#L207-L215)): `missing`,
`excused`, ou `workflow_state == "unsubmitted"`. Para escrever de volta há dois
candidatos no PUT:

- `submission[excuse]=true` → marca dispensado. Semanticamente "não conta", que
  não é a mesma coisa que faltou.
- `submission[late_policy_status]="missing"` → marca faltante. Mais próximo do
  que o coordenador quer dizer.

❓ Qual dos dois? Provavelmente `late_policy_status=missing`, mas precisa de
teste no Canvas real — e de verificar se o round-trip volta idêntico pelo
`derivar_presente`.

### O que fazer com os campos que não têm par no Canvas

- `anulado` é conceito só do SAS — continua local, sem write-back. Precisa ficar
  visualmente distinto na UI dos campos que vão pro Canvas.
- `nome`, `nota_maxima`, `rotulo_curto` têm par (`assignment.name`,
  `points_possible`). ❓ O SAS deve poder renomear assignment no Canvas, ou esses
  campos viram somente-leitura? Editar `points_possible` de um assignment já
  aplicado mexe na nota de todo mundo — provavelmente deve ser bloqueado.

### Pontos de atenção

⚠️ **Autoria.** O token do Canvas é único e de serviço
([cliente.py](../api/app/canvas_sync/cliente.py#L29-L37)). Toda edição vai
aparecer no `grade_change_log` do Canvas como sendo do dono do token, não do
coordenador que clicou. ❓ Isso é aceitável, ou precisa de log próprio no SAS
registrando quem editou o quê?

⚠️ **Simulados que vêm de quiz.** Sobrescrever `posted_grade` num assignment de
quiz é permitido, mas é override manual — vale confirmar que o Canvas não
recalcula por cima depois.

⚠️ **Falha parcial.** Hoje o PATCH sempre "dá certo". Com Canvas no caminho,
passa a existir estado de erro real (rede, permissão, assignment travado). A UI
precisa parar de assumir sucesso.

⚠️ **Enquanto isso não existe**, as funções de edição estão prometendo algo que
não cumprem. Vale decidir o interino: desabilitar, ou avisar na tela que a edição
é temporária.

## 2.8 Bloco D — Assistente como copiloto

Três mudanças que se sustentam: o painel deixa de bloquear a tela, passa a saber
onde o usuário está, e ganha paridade com o que a plataforma oferece.

### Painel persistente, não modal

O pedido é "um modal que permite navegar no site". Vale nomear com precisão: o
que resolve isso **não é um modal** — modal, por definição, bloqueia o fundo. O
que se quer é um **painel não-modal persistente**, que convive com a página.

A boa notícia é que a arquitetura já está pronta: o launcher é montado uma única
vez em `document.body`, fora da árvore de telas, e sobrevive à troca de rota
([main.js:147-155](../web/js/main.js#L147-L155)). O que impede a navegação é o
overlay — remover `.chat-overlay` e o `pointer-events: auto` já libera o fundo.

O que abre junto com essa mudança:

❓ **Sobrepor ou empurrar?** O drawer tem 460px fixos à direita e cobre o
conteúdo. A tabela do Painel é larga — sobrepor esconde as colunas da direita
justamente enquanto se conversa sobre elas. Empurrar (reduzir a largura útil da
página) custa reflow, mas mantém tudo visível. A classe `.chat-aberto` já é
aplicada no `body`, então o gancho pra empurrar existe.

❓ **Esc ainda fecha?** Fechar no Esc e no clique-fora são convenções *de modal*.
Num painel persistente elas passam a atrapalhar — o usuário aperta Esc pra sair
de um dropdown da página e perde a conversa. Provavelmente: clique-fora nunca
fecha; Esc só fecha se o foco estiver dentro do painel.

❓ Painel redimensionável / ancorável (direita, esquerda, inferior)? Fora do
primeiro corte, mas muda a estrutura CSS — melhor decidir antes.

### Consciência de contexto

Com o painel convivendo com a navegação, o chat passa a poder saber **em que tela
o usuário está** — hoje ele ignora a rota completamente. Isso vale nos dois
sentidos:

- **Página → chat:** abrir na ficha do Ciclo 6 e ver sugestões sobre o Ciclo 6;
  perguntar "e a Física?" sem precisar dizer de qual ciclo.
- **Chat → página:** o assistente responder com links que navegam de fato ("os
  três em risco são A, B e C" com cada nome clicável indo pra ficha). É o
  contrário da paridade de [§1.6.3](#163-lacunas-o-que-é-navegável-na-plataforma-e-o-chat-não-alcança),
  e provavelmente a tool mais barata de todas: uma que devolve rota.

### Apresentação da abertura

O problema de [§1.6.1](#161-a-abertura-não-mostra-o-que-o-assistente-sabe-fazer)
é de **discoverability**: 21 tools não cabem em 4 chips. Direções a discutir:

- **Agrupar por intenção**, não listar exemplos soltos — *Encontrar* · *Diagnosticar*
  · *Comparar* · *Gerar relatório/gráfico/CSV*. Cada grupo com um exemplo clicável.
- **Sugestões derivadas do contexto** (ver acima) em vez de constantes.
- **Uma saída explícita de "o que você sabe fazer?"** que liste a superfície
  inteira — o único jeito honesto de expor 21 capacidades.
- **Separar as sugestões por perfil** — corrige o bug do aluno ver texto de
  coordenador. Mínimo: `SUGESTOES_INICIAIS` vira parâmetro do `conversaPanel`.

### Fechar as lacunas de tools

Ordem sugerida pela distância entre "existe no produto" e "o chat não vê":

1. **`listar_alertas` e `insights_do_ciclo`** — o proativo do produto, e hoje
   invisível pro assistente.
2. **`listar_alunos` com filtros** (zona, perfil, turma, sede) — replica a tela
   Alunos, que é a mais usada.
3. **`listar_sedes` / `listar_turmas`** — sem isso o chat não responde nada
   recortado por sede, e sede é filtro de primeira classe na UI.
4. **Questões na visão da coordenação** — fecha a assimetria com o aluno.
5. **`comparar_alunos` / `comparar_simulados`** — "Comparar" é função declarada
   em [04-screens](04-screens.md) e só existe pra ciclos.
6. **`navegar_para`** — devolve rota; habilita o chat → página.

❓ Existe teto prático de quantas tools cabem num prompt antes da escolha degradar?
Com 21 já é bastante; indo pra ~30 vale considerar agrupar por perfil de uso ou
usar seleção em dois níveis. Decidir antes de simplesmente ir somando.

## 2.9 Frentes fora dos quatro blocos

| Frente | Estado | Nota |
|---|---|---|
| Webhooks do Canvas (fim do import manual) | não iniciado | dado entra sozinho, sem planilha |
| UI de gráficos em camadas | não iniciado | |
| Correção de discursivas por LLM | protótipo validado | ver [projeto](../api/grading_prototype/) |

---

## 2.10 Sprint 1 — escopo e divisão (17/08/2026)

Sprint restrita ao **bloco A**. Decisões fechadas:

| Questão | Decisão |
|---|---|
| Por onde começar | **Motor + lembrete de aluno** |
| Canais | **WhatsApp + e-mail** — WhatsApp por último ([P5](#p5--whatsapp-z-api)) |
| Detecção de entrega | **Em camadas** + guarda de reverificação antes de todo envio ([§2.4.4](#244-detecção-de-entrega--decidido-em-camadas-com-guarda-antes-do-envio)) |
| Fonte da verdade | **SAS origina, Canvas recebe** ([§2.3.5](#235-fonte-da-verdade--decidido-sas-origina-canvas-recebe)) |

### Divisão em 5 partes

Cada parte termina com **algo demonstrável**, e cada uma depende só da anterior.

```
P1 ──────▶ P2 ──────▶ P3 ─────▶ P4 ───────▶ P5
agenda    motor      lembrete   cobrança    WhatsApp
          +e-mail    de aluno   +professor
          (v0: só o
          coordenador)
          └────── risco baixo ──────┘        └ risco alto ┘
```

O v0 está em **P2**: coordenador cria evento → associa lembrete a si mesmo →
recebe o e-mail. Ninguém de fora envolvido, e ele mesmo valida.

---

#### P1 · O simulado nasce no SAS  ✅ em produção (Sprint 1)

Inverte a fonte da verdade. É a base de tudo — sem simulado agendado não há
evento, sem evento não há disparo.

- Schema: `evento_agenda`; `simulado` ganha fase pré-aplicação
- Cliente Canvas com **escrita**: `POST /courses/:id/assignments`
- Regra no sync: **campo originado no SAS não é sobrescrito**
- Tela mínima de agendamento (data + tipo + curso de destino)

**Pronto quando:** o coordenador agenda um simulado no SAS, ele aparece no Canvas,
e o reconcile das 3h não desfaz nada.

⚠️ Decidir aqui: agendamento transacional ou `pendente_no_canvas` com retry.

---

#### P2 · Motor + e-mail, com o coordenador como primeiro destinatário  ⭐ v0  ✅ em produção (Sprint 1)

> **Estado (20/08/2026): implementada e verificada ponta a ponta, com envio
> real** — plano e detalhes em [12-plano-p2-motor-lembretes.md](12-plano-p2-motor-lembretes.md).
> O que ainda falta é entorno, não código, e está rastreado em
> [12 §9](12-plano-p2-motor-lembretes.md#9--o-que-falta-20082026): reanálise
> do pedido de produção do SES (trava P3), SNS de bounces (prometido à AWS),
> domínio do colégio + remetente definitivo, e produção do SAS (0018+0019 +
> deploy + decidir onde é produção pós-Supabase).

**O v0 do produto inteiro:** o coordenador cria um evento, associa um lembrete
**a si mesmo**, e recebe o e-mail na hora marcada. Nada de externo além do
provedor de e-mail, nenhum terceiro envolvido, e ele mesmo verifica se funcionou.

- Schema: `regra_lembrete`, `disparo`
- Despachante lendo os disparos vencidos no tick horário
- **Reverificação de estado antes do envio** ([§2.4.4](#244-detecção-de-entrega--decidido-em-camadas-com-guarda-antes-do-envio))
- Idempotência e janela de silêncio
- Provedor de e-mail (não existe nenhum no projeto hoje)
- UI mínima no evento: *"me lembrar X dias antes"*

**Pronto quando:** o coordenador agenda um simulado, pede um lembrete pra si
mesmo, e o e-mail chega no horário certo — com a falha de envio registrada como
estado no banco quando não chega.

#### Provedor de e-mail — decidido: AWS SES

✅ **Decisão (17/08/2026):** AWS SES. Mesma conta que já roda o EventBridge
(`us-east-1` nos [.env.example](../infra/.env.example#L19)), sem fornecedor novo,
e custo na casa de centavos por disparo — ~R$ 1 para os 873 alunos.

⚠️ **Sandbox é o item de maior prazo, e precisa começar já.** Conta SES nova
entra em *sandbox*: só envia para endereços **verificados um a um**, com teto
baixo (ordem de 200/dia). Sair disso exige pedir **acesso de produção** à AWS —
um chamado que costuma sair em ~24h, mas pode demorar mais.

A boa notícia é o encaixe com a sprint:

| Fase | Destinatários | Sandbox serve? |
|---|---|---|
| **P2** (v0) | 1 — o próprio coordenador | ✅ sim, basta verificar o e-mail dele |
| **P3** | ~873 alunos | ❌ precisa de acesso de produção |

**Ou seja: P2 começa hoje, e o pedido de produção corre em paralelo pra estar
pronto em P3.** Não bloqueia nada se for aberto agora.

Dois itens que também têm prazo de terceiros:

- ❓ **Verificação de domínio (DKIM) do `aridesa.com`.** Exige criar registros DNS
  — depende de quem controla o DNS do colégio. A alternativa é verificar só um
  endereço remetente: mais rápido, mas a entrega fica pior e o e-mail aparece
  como enviado "via amazonses.com".
- ⚠️ **Tratamento de bounces.** A AWS suspende quem acumula taxa alta de rejeição.
  Com 873 endereços de aluno vindos do Canvas, alguns estarão inválidos. Precisa
  de tópico SNS de bounce/complaint e de marcar o endereço como inválido no banco
  — pequeno, mas obrigatório antes de P3. Não é necessário em P2.

**Como foi na prática (18–20/08/2026):** limites de sandbox confirmados na
conta: 200 e-mails/24h, 1/s. O pedido de produção foi aberto em 18/08 **pela
API** (`aws sesv2 put-account-details`) — o console novo trava o botão atrás
de verificação de domínio, que a API não exige. A AWS respondeu em 20/08
pedindo detalhes (frequência, origem das listas, bounces, exemplo de e-mail)
e recomendando identidade de **domínio** verificada; caso 178722538000720, em
reanálise. Saga completa e próximos passos em
[12 §9.1](12-plano-p2-motor-lembretes.md#91--ses-sair-do-sandbox---em-reanálise--trava-p3).

**Por que e-mail e não notificação no site:** não existe nenhuma infra de
notificação no front hoje (sem SSE, sem badge, sem central) — seria construir
uma UI inteira só pra testar o motor, e descartá-la depois, já que aluno e
professor não vão ser notificados in-app. O e-mail é necessário em P3 de qualquer
forma, não tem UI nenhuma, e exercita o caminho de código que interessa: envio
externo, que falha de verdade. ⬜ Se conseguir conta de provedor virar burocracia,
in-app é o plano B — destrava sem depender de ninguém.

⚠️ **Não chamar isso de "alerta".** `alerta` já é conceito do SAS
([`routes/alertas.py`](../api/app/routes/alertas.py), `stats/alertas.py`): sinal
pedagógico sobre aluno, gerado pelo sistema. O que o coordenador cria aqui é
**lembrete** — ele escolhe, é sobre uma data, e é só dele. Misturar os dois nomes
no schema custa caro depois.

⚠️ Renomear `/cobranca/verificar`. O nome nasceu para um caso só e o endpoint
passa a despachar lembrete de coordenador, de aluno e cobrança de professor.
`/disparos/processar` diz o que faz.

---

#### P3 · Lembrete de aluno  ✅ em produção (Sprint 1)

> **Plano de implementação (20/08/2026):** [13-plano-p3-lembrete-aluno.md](13-plano-p3-lembrete-aluno.md).
> Decisões fechadas ali: **um e-mail por dia** (digest das provas do dia, não um
> por prova), audiência = alunos ativos do ano letivo do ciclo, só simulados
> agendados no SAS, e o **SNS de bounces entra como etapa 0**. A única trava
> externa é a saída do sandbox do SES ([12 §9.1](12-plano-p2-motor-lembretes.md#91--ses-sair-do-sandbox---em-reanálise--trava-p3)).

Mesmo canal, novo destinatário — quase de graça depois de P2. O que muda é o
gatilho (derivado do evento, não escolhido a dedo) e a escala.

- Regra "simulado amanhã" → lembrete automático de aluno
- Espaçamento de envio em lote

**Pronto quando:** os alunos do simulado do dia seguinte recebem o e-mail sem
ninguém pedir.

⚠️ Antes de ligar: checar se as notificações nativas do Canvas já avisam o aluno
do mesmo simulado ([§2.3.4](#234-o-canvas-ajuda-com-o-agendamento-levantamento)) —
senão ele recebe dois.

---

#### P4 · Professores, requerimentos e cobrança por e-mail  ⏳ proposto para a Sprint 3 ([19 §3](19-roadmap.md#3--próximos-ciclos--proposta))

O fluxo do áudio 2 inteiro, funcionando — só que num canal só.

- Cadastro de professores (tela + schema)
- Matriz de distribuição professor × matéria na criação do simulado
- `requerimento` + máquina de estados ([§2.2.4](#224-estados-do-requerimento))
- Fluxo base com a cadência de [§2.4.3](#243-fluxo-base-definido-por-nós-não-pelo-coordenador)
- **Detecção camada 1:** fluxo de salvamento do arquivo do professor
- Tela de acompanhamento: quem entregou, quem não

**Pronto quando:** o coordenador distribui as questões e a cobrança roda sozinha
por e-mail até a entrega — sem ele tocar em nada.

❓ Fica pra depois (confirmar): **ingestão de e-mail** (camada 2 da detecção). É a
camada mais cara — ler caixa de entrada e casar remetente + anexo com
requerimento — e o fluxo funciona sem ela.

---

#### P5 · WhatsApp (Z-API)  ⏳ proposto para a Sprint 3 — decisão em aberto ([19 §4](19-roadmap.md#4--decisões-em-aberto))

Deixado por último de propósito: quando chegar aqui, **tudo já está provado**. O
WhatsApp entra como um canal a mais num motor que já funciona, não como parte de
um sistema não testado.

- Integração Z-API (instância no telefone do Ari)
- **Proteções anti-bloqueio desde o primeiro disparo:** variação de texto por
  mensagem, espaçamento entre envios, janela de horário
- **Detecção camada 3:** botão de resposta → estado `entrega_declarada`
- Orientação aos professores: salvar o contato, reagir às mensagens

**Pronto quando:** a mesma cobrança de P4 sai nos dois canais, e o botão do
WhatsApp pausa a cobrança sem marcar como entregue.

⭐ **Isso resolve sozinho a tensão que estava em aberto.** O risco era o Z-API
estrear disparando para os ~873 alunos. Com o WhatsApp em P5, o canal estreia na
cobrança de professor — dezenas de pessoas, não centenas — e os lembretes de
aluno já estarão rodando por e-mail desde P3.

❓ Última decisão pendente: alunos passam a receber por WhatsApp também depois de
P5, ou ficam só no e-mail? Uma ou duas instâncias Z-API depende disso.

---

# Parte 3 — Tensões e trade-offs

1. **Analítico × operacional.** [§2.1](#21-o-que-muda-no-posicionamento). O README
   diz "não ERP escolar" e o bloco A é exatamente operação. Escolher, não empilhar.
2. **Pressão × risco de bloqueio.** Quanto mais agressiva a cobrança
   ([§2.4.3](#243-fluxo-base-definido-por-nós-não-pelo-coordenador)), maior a
   chance do número do Ari cair. A cadência é decisão de risco, não de UX.
3. **Detecção automática de entrega × esforço.**
   ([§2.4.4](#244-o-ponto-mais-frágil-como-o-sistema-sabe-que-entregou)) Marcar
   manualmente é feio mas funciona amanhã; upload do professor é certo mas puxa
   login, permissão e storage junto.
4. **Agenda no banco × schedules na AWS.**
   ([§2.3.2](#232-o-que-falta)) Recomendação é banco; o custo é granularidade de 1h.
5. **Canvas como fonte da verdade × edição no SAS.** Quanto mais o SAS escreve de
   volta, mais ele vira um segundo gradebook. Onde fica a fronteira do que o SAS
   pode alterar ([§2.7](#27-bloco-b--escrita-de-volta-no-canvas-write-back))?
6. **Padronizar × não regredir.** Unificar os filtros no formato do Painel custa
   as contagens e o multi-select, se for feito literalmente
   ([§1.5](#15-interface-e-uso)).

---

# Parte 4 — Perguntas em aberto

Agrupadas pelos blocos do [mapa](#parte-0--mapa). As ⭐ travam decisões grandes —
sem elas, o resto do bloco não avança.

## Bloco A · Coordenação

| # | Pergunta | Trava |
|---|---|---|
| ⭐ A1 | **Como o sistema sabe que o professor entregou?** | todo o §2.4 |
| ⭐ A2 | "Coordenação" é aba lateral ou o novo centro do produto? | navegação, posicionamento |
| A3 | Professor tem login na plataforma ou é só destinatário? | cadastro, opção (a) de entrega |
| A4 | Professor tem uma disciplina ou várias? | cadastro, modelagem do requerimento |
| A5 | O tipo de simulado pré-preenche a distribuição de questões? | UI de criação |
| A6 | Teto de cobrança / escalonamento pro coordenador? | fluxo base |
| A7 | Disparos materializados na criação ou calculados no tick? | modelagem do motor |
| A8 | Janela de silêncio mora no motor ou na regra? | motor |
| A9 | Idempotência: marca antes ou depois do envio? | motor |
| A10 | Uma ou duas instâncias Z-API? | infra, custo, risco de bloqueio |
| A11 | ~~Provedor de e-mail?~~ ✅ **AWS SES** — pedido de produção aberto 18/08 (caso 178722538000720), **em reanálise** após pedido de detalhes da AWS; ver [12 §9.1](12-plano-p2-motor-lembretes.md#91--ses-sair-do-sandbox---em-reanálise--trava-p3) | P3 |
| A12 | Aluno recebe por WhatsApp ou só e-mail? (~873 pessoas) | risco de bloqueio |
| A13 | Quais ações entram na 1ª versão da tela de calendário? | escopo |

## Bloco B · Integridade do dado

| # | Pergunta | Trava |
|---|---|---|
| B1 | ~~Desabilitar ou avisar até o write-back existir?~~ ✅ **nenhum dos dois** — a edição fica como está e é consertada de uma vez em [B.2](#b2--write-back-de-notas-no-canvas) | — |
| B2 | ~~A média final inclui alunos sem nota?~~ ✅ **sim, como zero** — bug confirmado; regra decidida: média sobre as matérias feitas | pronto pra corrigir |
| B3 | Regra de corte para `pontuacao=0` com `presente=true` | todas as estatísticas |
| B4 | `excuse` ou `late_policy_status=missing` pra marcar ausência no Canvas? | write-back |
| B5 | SAS pode alterar `nome` / `points_possible` do assignment, ou vira read-only? | write-back |
| B6 | Autoria da edição: token de serviço basta, ou precisa log próprio no SAS? | auditoria |
| B7 | Precedência entre ingest de planilha e sync do Canvas | reprocessamento |

## Bloco C · Interface

| # | Pergunta | Trava |
|---|---|---|
| C1 | O filtro lateral unificado suporta single **e** multi-select? | componente compartilhado |
| C2 | O toggle Ranking / A–Z do Painel some quando o cabeçalho virar ordenável? | tabelas |
| C3 | Ordenação persiste ao trocar filtro / entre visitas? | tabelas |
| C4 | Ciclo pode ter período nulo? Se sim, entra ou sai do range? | filtro de período |
| C5 | Range de período substitui o filtro "Ano letivo" ou convivem? | filtro de período |

## Bloco D · Assistente

| # | Pergunta | Trava |
|---|---|---|
| D1 | Painel sobrepõe o conteúdo ou empurra a página? | layout |
| D2 | Esc e clique-fora ainda fecham o painel? | interação |
| D3 | Escrita pelo chat entra no escopo (depois do write-back)? | tools, depende de B |
| D4 | Teto prático de nº de tools antes da escolha degradar? | arquitetura do agente |

## Já resolvidas

| Pergunta | Resposta |
|---|---|
| Vestibular é filtro ou lente? | **Filtro** — os ciclos são criados por vestibular (Ciclo 1 · IME · 2026). A tela de Ciclos já separa; o Painel é a exceção. |
| Fonte da verdade da nota: SAS ou Canvas? | **"Sempre o Canvas + alterações do SAS"** — as duas colunas convivem (`pontuacao_canvas`, `pontuacao_sas`); o SAS exibe a sua, marca a divergência, e nada sobe ao Canvas sem o coordenador escolher. Decidido em 22/08 ([18 §2.4](18-plano-sprint-2.md#24-nota-sempre-o-canvas--alterações-do-sas)). |
| Qual a regra de corte? | **Dado, não código** — cinco réguas embutidas (Tio Leo · ITA F1/F2 · IME F1/F2) avaliadas no servidor, cada predicado com o artigo do edital. A do colégio corta com `E`, as dos editais com `OU`, de propósito ([18 §1.5](18-plano-sprint-2.md#15-os-três-critérios-embutidos)). |
| Como o aluno entra? | **Pelo Canvas** (OAuth2). 876/876 já tinham `canvas_user_id` e só 1 tinha senha — trocar o método custou zero migração. Matrícula + senha fica como fallback ([18 §4](18-plano-sprint-2.md#p4--identidade-e-acesso)). |
| Lembrete dispara se o simulado não está no Canvas? | **Sim** — o motor é do SAS e não depende de sistema externo (22/08). |

---

# Parte 5 — Planos de implementação (blocos B, C, D)

Fora da Sprint 1, que é só o bloco A ([§2.10](#210-sprint-1--escopo-e-divisão-17082026)).
Os três blocos abaixo são independentes entre si e podem correr em qualquer ordem.

---

## Plano B · Integridade do dado

### B.1 — Ausência contando como zero na média  🔴 confirmado  ⏳ proposto para a Sprint 3

**Diagnóstico.** Em [`calcularMediasVirtuais`](../web/js/screens/painel.js#L194-L210)
o acesso à nota é:

```js
// Retorna valor de uma coluna (real ou virtual). Ausente = 0.
return notasAluno[alunoId]?.[col.sim.id] ?? 0;
```

Aluno sem nota entra na média como **zero**. E em
[`mediasPorCol`](../web/js/screens/painel.js#L696-L713) as duas famílias de coluna
são tratadas de forma diferente:

| Coluna | Filtro | Efeito |
|---|---|---|
| Real (Matemática, Física…) | `.filter(v => v != null)` | ✅ média só de quem fez |
| Virtual (Média Final) | `.filter(v => v != null)` | ❌ **não filtra nada** — o valor virtual nunca é nulo, já virou 0 |

**Confere com a tela:** Matemática 5,4 / Física 4,9 / Química 4,3, mas Média Final
**1,3**. Com ~250 de 873 alunos por simulado (`n` = 251/252/253 na tela de
Simulados), 5,0 × 250/873 ≈ 1,4.

**Alcance — é maior que a linha da média.** O mesmo zero contamina:

1. A linha *"Média da turma"*.
2. O KPI **"Em zona de corte: 800 de 873"** — a maioria está cortada por ausência.
3. O KPI **"Média geral"** do cabeçalho.
4. A **ordenação do ranking** — quem não fez prova afunda como se tivesse ido mal.
5. [`statusNomeAluno`](../web/js/screens/painel.js#L816-L823), que pinta o nome de
   vermelho comparando `>= 5`.

**Correção.**

1. `v()` devolve `null` para ausência, não `0`.
2. `media()` passa a ignorar nulos.
3. ✅ **Regra decidida (17/08/2026): média sobre as matérias que o aluno fez**,
   sem exigir mínimo. Quem fez 2 de 3 tem a média das 2. Consequência aceita:
   quem fez só 1 também recebe média cheia dessa única nota, ficando comparável a
   quem fez as três. Se incomodar depois, o ajuste é adicionar um piso.
4. Aluno sem nota nenhuma no ciclo sai do denominador de todos os KPIs.

**Ordem:** primeiro item do bloco B. É contido (um arquivo), não tem dependência
externa, e conserta o número mais visível do produto.

⚠️ Esperar o impacto: a média geral vai **subir muito** e o "em zona de corte" vai
**despencar**. Vale avisar a coordenação antes, senão parece que o sistema quebrou.

---

### B.2 — Write-back de notas no Canvas  ✅ implementado (17/08/2026) · refeito na Sprint 2 com escolha do coordenador ([18 §2](18-plano-sprint-2.md#p2--canvas-sob-controle))

**Diagnóstico** em [§1.2](#12-dados-e-ingestão), desenho em
[§2.7](#27-bloco-b--escrita-de-volta-no-canvas-write-back).

**Como ficou:** `PATCH /notas/{aluno}/{simulado}` grava **no Canvas primeiro**
(`atualizar_nota_submission` no cliente, reusando a infra de escrita do P1) e só
depois no banco. Falha no Canvas aborta a edição com o motivo na tela — nota não
tem estado de limbo, diferente do agendamento: nota é dado do Canvas, gravar
local sem gravar lá recriaria a edição fantasma. Ausência vai como
`late_policy_status='missing'` + nota apagada, que `derivar_presente()` lê de
volta como ausente (round-trip verificado). Pendente: um teste real de ponta a
ponta contra o Canvas de produção, com um caso escolhido de propósito.

**Ordem de implementação:**

✅ **Decidido: sem etapa interina.** Nada de desabilitar nem de avisar na UI — a
edição fica exatamente como está e é consertada de uma vez quando B.2 for feito.

⚠️ Consequência assumida: **a perda silenciosa continua até B.2 entrar.** Isso
transforma "quando fazer B.2" na decisão que importa. Enquanto isso, o custo zero
é avisar a coordenação de viva voz pra não usar o botão de editar — não exige
código nenhum.

1. **Cliente Canvas com escrita.** `PUT /courses/:id/assignments/:id/submissions/:user_id`
   com `submission[posted_grade]`. Se a Sprint 1 rodar antes, essa infra já existe
   (P1 cria assignment) e este item herda o cliente pronto.
3. **Inverter a ordem do PATCH:** Canvas primeiro, banco depois. Falha no Canvas =
   erro na tela, nada gravado.
4. **Ausência:** `submission[late_policy_status]="missing"` (❓ B4 — testar o
   round-trip contra [`derivar_presente`](../api/app/canvas_sync/mapeador.py#L207-L215)).
5. **Campos de simulado:** tornar `nome`/`nota_maxima`/`rotulo_curto` read-only na
   UI **ou** escrevê-los no Canvas — nunca deixar como está. Se a Sprint 1 rodar,
   a regra "campo do SAS não é sobrescrito" já resolve isso por outro caminho.
6. **Estado de erro na UI.** Hoje o PATCH sempre "dá certo"; passa a poder falhar.

---

### B.3 — Zero × ausência nas estatísticas

Distinto de B.1: lá é ausência virando zero no **cálculo da média**; aqui é zero
**real** que provavelmente é abandono de prova.

O Canvas já distingue nativamente
([`derivar_presente`](../api/app/canvas_sync/mapeador.py#L207-L215) usa `missing`,
`excused`, `workflow_state`), então o dado existe — falta a regra de negócio.

❓ Precisa de decisão antes de código: `pontuacao=0` com `presente=true` conta,
não conta, ou vira uma terceira categoria? Sugestão: medir primeiro — quantos
casos são, e como se distribuem — antes de escolher a regra.

---

### B.4 — Precedência entre ingest de planilha e sync do Canvas

Baixa urgência enquanto a planilha não for usada. A regra provável: **Canvas
vence sempre**, e o ingest de planilha vira ferramenta de carga histórica, não
caminho corrente. ⬜ Confirmar se a planilha ainda é usada; se não for, o caminho
mais barato é aposentar o `importar` em vez de arbitrar precedência.

---

## Plano C · Interface

Quatro itens, todos sem migration e sem dependência externa. **A ordem importa**
só entre C.1 e os dois seguintes.

### C.1 — Componente único de filtro lateral  ✅ implementado (`PainelFiltros.tsx`)

É a base de C.2 e C.3, e por isso vem primeiro.

**Hoje são dois sistemas** ([§1.5](#15-interface-e-uso)): `psb-*` no Painel
(ícone + colapsável, single-select, sem contagem) e `sim-filtros__*` nas outras
três (chips com contagem, multi-select, "limpar filtros").

**Alvo:** contêiner do Painel + conteúdo dos chips, em `web/js/components/ui/`.

1. Extrair `buildSecao` do [painel.js](../web/js/screens/painel.js#L456-L476) para
   um componente — seção com ícone, expansível, memorizando aberto/fechado.
2. Mover `sim-filtros` para dentro dele como um dos tipos de conteúdo.
3. **O componente precisa aceitar mais de um tipo de corpo**: chips (hoje) e
   intervalo de datas (C.4). Não desenhar só pra chips.
4. ❓ Suportar single **e** multi-select (o Painel é single por natureza — um ciclo
   monta a tabela).
5. Migrar as quatro telas.

⚠️ Padronizar não pode custar as contagens (`AD · 376`) nem o multi-select. O
formato do Painel é hoje o mais pobre dos dois em conteúdo.

### C.2 — Split ano / vestibular / ciclo no Painel

Depende de C.1. Sem migration: `Ciclo` já tem `anoLetivo` e `vestibularAlvo`
([domain.py:56-63](../api/app/schemas/domain.py#L56-L63)); a sidebar é que
descarta os dois.

Hierarquia **Ano → Vestibular → Ciclo**, cada nível estreitando o seguinte.
Ano provavelmente fixo no topo (muda pouco), não seção colapsável.

⬜ Já resolvido: vestibular é **filtro**, não lente — a tela de Ciclos já faz essa
separação. O Painel é a exceção a corrigir.

### C.3 — Range de período em Ciclos

Depende de C.1 (é o corpo não-chip do componente).

Predicado de **interseção**, não contenção:

```
ciclo.periodoInicio <= range.fim  E  ciclo.periodoFim >= range.inicio
```

1. Extremos abertos: só início ou só fim preenchido funciona (campo vazio =
   infinito daquele lado).
2. ⚠️ Verificar antes: **ciclo pode ter período nulo?** `atualizar_periodo_ciclo`
   só roda quando há simulados com data, mas o schema declara `periodoInicio` como
   `str` obrigatório. Ou nunca acontece, ou quebra no primeiro ciclo vazio.
3. ❓ Convive com o filtro "Ano letivo" ou o substitui?
4. ⬜ Presets ("este ano", "último trimestre") resolvem o caso comum sem digitar data.

### C.4 — Ordenação por cabeçalho  ✅ implementado (`TabelaOrdenavel.tsx`)

Independente de C.1 — pode ser feito em paralelo ou antes.

Ordenação no cliente: 873 alunos e 148 simulados já vêm inteiros pro browser, sem
paginação. Nada muda na API.

1. Componente de `<thead>` ordenável: clique alterna asc/desc, indicador na coluna
   ativa, colunas explicitamente marcadas como não-ordenáveis (*Trajetória* é
   sparkline; a última é só "Ver →").
2. **Nulos afundam nos dois sentidos.** Aluno com Média `—` não pode aparecer no
   topo do "pior desempenho".
3. **Categóricas têm ordem semântica:** *Zona* = Risco → Cinzenta → Top;
   *Tendência* = Queda → Estável → Alta. Alfabético não significa nada.
4. Aplicar em [alunos.js](../web/js/screens/alunos.js#L127-L137),
   [ciclos.js](../web/js/screens/ciclos.js#L118-L124) e
   [tabela-simulados.js](../web/js/components/tabela-simulados.js#L55-L66).
5. ❓ O toggle **Ranking / A–Z** do Painel some (vira ordenar por Média desc /
   Aluno asc) ou o Painel fica de fora?
6. ❓ A ordenação persiste ao trocar filtro? Entre visitas?

---

## Plano D · Assistente

### D.1 — Painel não-modal  (o mais barato do documento)

Remover `.chat-overlay` e o `pointer-events: auto`
([chat.css:48-62](../web/styles/chat.css#L48-L62)). A arquitetura já sustenta: o
launcher é montado uma vez em `document.body`, fora da árvore de telas
([main.js:147-155](../web/js/main.js#L147-L155)).

Junto vem:
1. ❓ Sobrepor ou empurrar? A classe `.chat-aberto` já é aplicada no `body` — o
   gancho pra empurrar existe. A tabela do Painel é larga; sobrepor esconde as
   colunas da direita justo enquanto se conversa sobre elas.
2. ❓ Esc e clique-fora deixam de fechar? São convenções de modal.
3. ⬜ Redimensionar / ancorar fica pra depois, mas muda a estrutura CSS — decidir antes.

### D.2 — Apresentação da abertura

1. 🔴 **Corrigir o vazamento de perfil primeiro:** `SUGESTOES_INICIAIS` é constante
   global ([conversa.js:10-15](../web/js/components/chat/conversa.js#L10-L15)) e o
   aluno lê *"Quais alunos estão em risco?"* no Mentor. Vira parâmetro do
   `conversaPanel`.
2. Agrupar por intenção (*Encontrar · Diagnosticar · Comparar · Gerar*) em vez de
   4 frases soltas — 21 tools não cabem em 4 chips.
3. Saída explícita de "o que você sabe fazer", única forma honesta de expor a
   superfície inteira.
4. Sugestões derivadas da rota atual (depende de D.4).

### D.3 — Fechar as lacunas de tools

Ordem por distância entre "existe no produto" e "o chat não vê"
([§1.6.3](#163-lacunas-o-que-é-navegável-na-plataforma-e-o-chat-não-alcança)):

| # | Tool | Por quê |
|---|---|---|
| 1 | `listar_alertas`, `insights_do_ciclo` | o proativo do produto, hoje invisível pro assistente |
| 2 | `listar_alunos` com filtros (zona, perfil, turma, sede) | replica a tela mais usada |
| 3 | `listar_sedes`, `listar_turmas` | sem isso não responde nada recortado por sede |
| 4 | questões na visão da coordenação | fecha a assimetria: o aluno tem, o coordenador não |
| 5 | `comparar_alunos`, `comparar_simulados` | "Comparar" é função declarada e só existe pra ciclos |

❓ Teto prático de tools antes da escolha degradar? Com 21 já é bastante; indo pra
~30, considerar agrupamento por perfil ou seleção em dois níveis.

### D.4 — Consciência de rota (chat ↔ página)

Só faz sentido depois de D.1 — sem navegação simultânea, contexto de rota não tem
utilidade.

1. **Página → chat:** o launcher passa a saber a rota e a entidade em tela.
2. **Chat → página:** tool `navegar_para` que devolve rota; respostas com nomes
   clicáveis. Provavelmente a tool mais barata de todas e a que mais aproxima da
   paridade que o produto quer.

---

# Parte 6 — Classificação por complexidade

Só as correções levantadas em conversa, **fora da Sprint 1**. Duas dimensões
separadas de propósito: *esforço* (quanto código e quantos arquivos) e *risco*
(chance de quebrar algo, ou de depender de validação externa). Elas não andam
juntas — a correção da média é pequena em esforço e alta em visibilidade.

| # | Correção | Esforço | Risco | Plano |
|---|---|---|---|---|
| 1 | Painel do chat deixa de bloquear a navegação | **Trivial** | baixo | [D.1](#d1--painel-não-modal--o-mais-barato-do-documento) |
| 2 | Sugestões do chat por perfil (aluno vê texto de coordenador) | **Trivial** | baixo | [D.2](#d2--apresentação-da-abertura) |
| 3 | Média deixa de contar ausência como zero | **Pequeno** | ⚠️ **alto impacto visível** | [B.1](#b1--ausência-contando-como-zero-na-média--confirmado) |
| 4 | Split ano / vestibular / ciclo no Painel | **Pequeno** | baixo | [C.2](#c2--split-ano--vestibular--ciclo-no-painel) |
| 5 | Range de período em Ciclos | **Pequeno** | baixo | [C.3](#c3--range-de-período-em-ciclos) |
| 6 | Ordenação clicando no cabeçalho | **Pequeno-médio** | baixo | [C.4](#c4--ordenação-por-cabeçalho) |
| 7 | Apresentação da abertura do assistente | **Médio** | baixo | [D.2](#d2--apresentação-da-abertura) |
| 8 | Filtros laterais unificados no formato do Painel | **Médio** | médio | [C.1](#c1--componente-único-de-filtro-lateral) |
| 9 | Tools faltantes do assistente | **Médio (aberto)** | baixo | [D.3](#d3--fechar-as-lacunas-de-tools) |
| 10 | Edição escrevendo no Canvas (write-back) | **Grande** | ⚠️ **alto** | [B.2](#b2--write-back-de-notas-no-canvas) |

### Por que cada um caiu onde caiu

**1 · Trivial.** Apagar o elemento `.chat-overlay` e o `pointer-events: auto`
([chat.css:48-62](../web/styles/chat.css#L48-L62)). O launcher já é montado fora
da árvore de telas e já sobrevive à troca de rota — a arquitetura não muda.
*Vira Pequeno se a decisão for "empurrar" em vez de "sobrepor"*: aí mexe no
layout de todas as telas.

**2 · Trivial.** `SUGESTOES_INICIAIS` é constante global
([conversa.js:10-15](../web/js/components/chat/conversa.js#L10-L15)); vira
parâmetro do `conversaPanel`. É um bug de uma linha com efeito desproporcional —
hoje o aluno lê *"Quais alunos estão em risco?"* no Mentor.

**3 · Pequeno em código, alto em impacto.** Muda `v()` e `media()` num arquivo.
Mas propaga para cinco lugares (linha da média, dois KPIs, ordenação do ranking,
cor do nome) e **os números da tela vão mudar muito**: a média sobe, o "em zona de
corte" despenca. Exige conferir contra o dado real e avisar a coordenação antes,
senão parece que o sistema quebrou.

**4 · Pequeno.** Sem migration e sem API: `Ciclo` já traz `anoLetivo` e
`vestibularAlvo`. É reescrever `buildCicloItems` como hierarquia de três níveis.

**5 · Pequeno.** O predicado de interseção são duas comparações. O que há de novo
é a UI de intervalo — primeiro filtro do produto que não é chip. Uma incógnita
antes: **ciclo pode ter período nulo?**

**6 · Pequeno-médio.** A ordenação em si é fácil (dado já vem inteiro pro browser,
sem paginação, API não muda). O volume vem de aplicar em **três implementações
diferentes** de tabela e de escrever comparador por coluna — nulos afundando,
*Zona* como Risco→Cinzenta→Top, colunas não-ordenáveis marcadas.

**7 · Médio.** Não é código difícil, é decisão de desenho: 21 tools não cabem em
4 chips. Exige inventar o agrupamento por intenção e a saída de "o que sei fazer".
Fica melhor depois de D.4 (contexto de rota), que dá sugestões de verdade.

**8 · Médio, e o de maior superfície de regressão da lista.** Dois sistemas a
fundir e **quatro telas a migrar**. O componente precisa aceitar chips *e*
intervalo de datas, single *e* multi-select, sem perder as contagens. É a peça de
que 4 e 5 dependem — o que sobe a aposta.

**9 · Médio, mas de escopo aberto.** Cada tool isolada é pequena (schema +
handler + consulta). O que não fecha é a lista: são cinco categorias e a paridade
com o produto é alvo móvel. Nunca fica "pronto" — vale tratar como fluxo, não
como tarefa.

**10 · Grande, e o único que pode estragar dado de produção.** Não é tamanho de
código: é sistema externo, semântica de ida e volta da ausência, campos que podem
ou não ser escritos, estado de erro numa UI que hoje assume sucesso, e autoria
diluída no token de serviço. Precisa de teste contra o Canvas real.

### Ordem sugerida

A ordem por complexidade **não** é a melhor ordem de execução, por três motivos:

```
1 · 2 · 3     →   4 · 5   →   6      →   7 · 9    →   10
triviais +        dependem     independente  contínuo      depois de P1
a média           de 8*        de tudo
```

- **Começar por 1, 2 e 3.** Custam pouco e o item 3 conserta o número mais visível
  do produto.
- **4 e 5 dependem do 8** se forem feitos dentro do componente unificado. ⬜ Dá
  pra fazer os dois "na marra" antes e migrar depois — mais rápido agora, retrabalho
  garantido. Recomendo fazer o 8 primeiro e os dois em cima dele.
- **6 é independente de todo o resto** — pode entrar a qualquer momento, inclusive
  em paralelo com a Sprint 1.
- **10 fica por último de propósito:** depois de **P1** da Sprint 1, que já constrói
  o cliente Canvas com escrita, o tratamento de falha e a regra "campo do SAS não é
  sobrescrito". Fazendo antes, essa infra é construída duas vezes.

