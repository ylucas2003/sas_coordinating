# 44 — Turmas de 1º e 2º ano na plataforma

> **Estado em 05/11/2026:** planejado, com as decisões de produto fechadas. A etapa 1
> está no branch `feat/turmas-1o-2o-ano`. Nada disto está em produção, e nenhum aluno
> de 1º ou 2º ano entrou no SAS.
>
> Protótipo clicável, com dados fictícios:
> [prancheta, linha D](https://claude.ai/artifact/AYowaAdL4BwWMSGdJZ5sU1).

## 1 · Decisões

| Decisão | Por quê | Quem |
|---|---|---|
| O rail tem um bloco por turma: **3º e cursinho**, **1º ano** e **2º ano**, cada um com Painel, Alunos e Provas e recolhível. Banco e Administração ficam fora dos blocos | A coordenação quer as turmas separadas. Com os blocos à vista não existe modo escondido, então ninguém olha a turma errada sem perceber | Usuário, 05/11 |
| 1º e 2º ano nunca aparecem juntos | Fazem provas diferentes, e somar os dois mistura números que não se comparam | Leo, 05/11 |
| 3º e cursinho são o que já está na plataforma: o curso 577 inteiro, sem provas novas | Pedido explícito | Usuário, 05/11 |
| **Só AP e AG entram. AP é IME, AG é ITA.** ASC, NTD, AR e Atividade de Resolução ficam de fora | Pedido explícito | Leo, 05/11 |
| AP6 e AG6 (Geografia, Biologia e História) também entram | São AP e AG, mesmo que a legenda do manual não as marque como IME ou ITA | Usuário, 05/11 |
| As réguas são as mesmas do 3º (Tio Léo, ITA e IME). A aprovação da escola com 7 por disciplina não é usada | AP é IME e AG é ITA | Usuário, 05/11 |
| Provas sem nota no Canvas são só registradas (§6) | Pedido explícito | Usuário, 05/11 |

Quando alguém disser "boletim" neste assunto, quer dizer **notas de provas normais**. Não é
o boletim oficial do Portal Ari de Sá, nem as fórmulas de média do manual.

## 2 · O que o Canvas tem

Medido em 05/11/2026, só com leitura.

| Série | Curso em 2026 | Anos com o mesmo padrão | Alunos ativos |
|---|---|---|---|
| 3º e cursinho | `2026 3o ITA/IME Simulados` (577) | já sincronizado | 1.093 |
| 1º ano | `2026 1o ITA/IME Avaliações` (578) | 552, 527, 384 | 47 |
| 2º ano | `2026 2o ITA/IME Avaliações` (579) | 553, 528, 404 | 60 |

O ano tem três etapas, e cada etapa tem um grupo de AP e um de AG. **Cada grupo tem
exatamente 9 provas nas seis matérias de vestibular, o mesmo tamanho dos ciclos do 3º,
mais 3 de Geografia, Biologia e História:**

- AP: `AP1` (Mat, Fís, Quí), `AP2` (Mat), `AP3` (Fís), `AP4` (Quí), `AP5` (Por, Red, Ing),
  `AP6` (Geo, Bio, His)
- AG: `AG1` (Mat, Fís, Quí, Ing), `AG2` (Mat), `AG3` (Quí), `AG4` (Fís), `AG5` (Por, Red),
  `AG6` (Geo, Bio, His)

A fonte das siglas é o Manual do Aluno 2026, págs. 33 a 39. O PDF está na página "Manual
do Aluno" dos cursos e só abre em pré-visualização, porque o download está desativado.

Volume com 72 provas por série e por ano: no máximo 8,5 mil notas em 2026, 6,7 mil em
2025, 6,0 mil em 2024 e 6,3 mil em 2023. O banco local tinha 78 mil notas na medição.

Mais de 95% das matrículas dos ativos têm atividade recente e todas têm SIS e e-mail, então
o login pelo Canvas funciona sem mudança na autenticação. Dos alunos do 1º de 2025, 40 de
48 foram para o 2º de 2026; do 2º de 2025, 37 de 45 foram para o 3º de 2026. Quatro alunos
do 2º de 2026 também estão no curso 577.

## 3 · Modelo

**Cada grupo de AP ou AG vira um `ciclo` comum, e não existe conceito novo de etapa.** Com
`vestibular_alvo` IME ou ITA, o que já existe passa a valer: réguas, inferência de fase,
ficha da prova, histograma e alerta de prova mal calibrada. O esquema de colunas da tabela
vale para as seis matérias de vestibular; as outras três exigem ajuste (§4, etapa 4).

| Grupo no Canvas | `serie` | `ordem` | `vestibular_alvo` |
|---|---|---|---|
| 1ª etapa, AP | do curso | 1 | IME |
| 1ª etapa, AG | do curso | 2 | ITA |
| 2ª etapa, AP | do curso | 3 | IME |
| 2ª etapa, AG | do curso | 4 | ITA |
| 3ª etapa, AP | do curso | 5 | IME |
| 3ª etapa, AG | do curso | 6 | ITA |

Migration `0078`, a etapa 1:

- `curso_canvas (ano_letivo_id, serie, canvas_course_id)` sucede
  `ano_letivo.canvas_course_id`, que só comporta um curso por ano.
- `ciclo.serie`, com a chave passando a ser `(ano_letivo_id, serie, ordem)`.
- `turma.serie_do_curso`.

Tudo o que existe nasce 3. **Um bloco é uma série, então não há coluna de bloco.**

## 4 · Etapas

**1. Dados.** A migration acima e o sync gravando `curso_canvas`. Nada muda na tela.

**2. Casco.**

- Rail em blocos, com a lista rolando para o Sair não sair da tela em notebook. O rail é
  `height: 100dvh` e, com tudo aberto, passa da altura de uma tela de notebook.
- No celular, a troca vira um seletor no topo da tela, porque a barra inferior não comporta
  os blocos.
- Rotas novas com prefixo, como `/1ano/alunos`. `/painel`, `/alunos` e `/provas` continuam
  sendo 3º e cursinho, porque estão em link salvo e em e-mail. Fichas (`/alunos/:id`,
  `/ciclos/:id`, `/simulados/:id`) mantêm o endereço, e a API informa a série.
- Recorte por série em `useAlunos`, `useCiclos`, `useSimulados`, `useAlertas`, `useTurmas`
  e `useSedes`, e nas rotas deles. O filtro de alertas fica no servidor, porque
  `GET /alertas` limita a 100.
- `cicloPadrao`, a referência de médias de `routes/alunos.py` e o `useRecorteDaTela` passam
  a respeitar a série.
- Os blocos de 1º e 2º ano ficam escondidos enquanto não houver aluno neles.

**3. Importação, com o acesso fechado.**

- Descobrir os cursos `{ano} {1|2}o ITA/IME Avaliações`.
- Trocar as leituras de `ano_letivo(canvas_course_id)` por `curso_canvas` em agendamento,
  escrita, simulados, notas e ciclos.
- Ler grupo e prova conforme o §5.
- Cadastrar Biologia, História e Geografia em `materia`, `MATERIAS_CANONICAS` e
  `criterios.MATERIAS_CONHECIDAS`. Fica nesta etapa, e não na 1, porque `GET /materias`
  alimenta filtros: antes da hora, as três apareceriam nas telas do 3º.
- Passar a série do curso em `upsert_turma`, senão 1º e 2º caem na mesma turma `SEM_SECTION`.
- Criar um portão de acesso. Hoje o login abre no instante em que o sync grava o aluno, e
  é preciso poder importar e conferir antes.
- Restringir por série a audiência de lembretes e o próximo simulado do aluno, que hoje são
  por ano letivo.
- Importar 2026 e depois 2025, conferindo os números contra o Canvas.

**4. Ajustes.**

- Dar lugar a Geografia, Biologia e História na tabela do ciclo: o `ESQUEMA` de
  `dominio/painel.ts` é fixo por vestibular e não tem essas colunas.
- Na régua Tio Léo, o corte 4 vale para qualquer matéria (`TODAS`), então as três contam.
  Nas réguas ITA e IME elas não existem, e `inferir_fase_simulados` marca AP6 e AG6 como
  2ª fase. Conferir com a coordenação se a leitura faz sentido na tela.
- `_carregar_ciclo_anterior` busca `ordem - 1` com o mesmo vestibular. Nas séries novas, o
  anterior de mesmo vestibular é `ordem - 2`.
- O prompt do Tio Léo diz que o aluno tem 16 a 18 anos.
- A missão do dia cobre o edital inteiro, então o 1º ano recebe conteúdo que não viu.
- Chat e MCP precisam aceitar a série, com `GRANT` por coluna no papel do MCP.
- O nome da sede vem da section, que no 1º e no 2º ano é o nome do curso.

**5. Abertura.** Mostrar os blocos à coordenação e, depois, liberar o acesso aos alunos.

## 5 · Armadilhas

- **Prova com `points_possible = 0` tem nota de verdade.** É discursiva, com nota direta de
  0 a 10: `1_AG2 - Matemática` tem 45 de 48 notas no 1º ano. `nota_real` devolve `None` para
  máximo 0, então ela sumiria sem erro. Na importação, a nota máxima dessas provas é 10.
- **Atividade de Resolução parece prova.** Vale 0,5 ponto e tem nomes como
  `1_AP1 - Matemática - 10/02/2026 (Atividade de Resolução)` e
  `1_AG1 - Matemática (ATIVIDADE DE RESOLUÇÃO) - 30/03/2026`. Se entrasse, 0,5 de 0,5 viraria
  nota 10.
- **O curso de um ano traz cópias do ano anterior**, inclusive dentro de grupos do ano certo:
  12 provas em 578, como `1_AP5 - Português - 12/03/2025`. Vale a data da prova.
- **Os nomes variam.** Exemplos: `1_ AP2`, `Inglês- 12/03`, `3ª ETAPA` e `3º ETAPA` no mesmo
  ano, e `AP3 - Física - 09/09/2024` sem o número da etapa. Etapa e tipo vêm do grupo;
  número e matéria, do nome.
- **`turma.serie` não diz o bloco.** Vale 0 em "AD Online", "PB" e "Escolas Parceiras SAS".
  Use `turma.serie_do_curso`.
- **O sync escolhe o curso de maior ano**, e o desempate é a ordem em que o Canvas lista. Por
  isso `PADRAO_CURSO_SIMULADOS` exige `3o` desde a etapa 1: um "2027 2o ITA/IME Simulados"
  poderia desviar o sync de produção sem erro.
- **Não rodar o sync atual em 578 ou 579 para testar.** Ele sobrescreve o curso do ano, e
  simulado agendado e nota editada iriam para o curso errado.
- **Matrículas não fecham.** Nenhum código preenche `ativo_ate` nem desativa aluno. No banco
  local eram 1.764 abertas, nenhuma fechada, e 345 alunos com mais de uma. Com três séries
  isso vira o caso normal na virada do ano.

## 6 · Registrado, sem ação

- **Provas sem nota no Canvas.** Exemplos: `1_AG2 - Matemática` no 2º ano (0 de 61) e
  `1_AG4 - Física` nos dois anos. Por decisão do usuário, não fazemos nada: elas aparecem sem
  nota.
- **Quem faltou à AP e fez a ASC aparece como falta**, porque a ASC não entra.
- **Fora do escopo:** média da etapa, média anual, recuperação, frequência e o boletim oficial.
