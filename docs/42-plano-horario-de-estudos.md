# 42 — Horário de estudos · o aluno monta a própria semana

> Decidido em **24/10/2026**, numa conversa de produto, e **implementado no
> mesmo dia — ainda sem deploy** (a migration `0069` não foi aplicada em produção;
> ver o §9, que diz o que foi e o que NÃO foi verificado). O estado é o
> [19](19-roadmap.md); a área do aluno, fonte por fonte, é o
> [30](30-estado-da-implementacao.md).
>
> A pergunta que a aba Estudar não respondia era **"quando"**. Os três campos
> dizem *o quê* (Banco), *o mundo* (Estatísticas) e *você* (Meu progresso);
> ninguém dizia quando estudar. Este é o quarto campo.

---

## 0 · O que ficou decidido

| # | Decisão | Por quê |
|---|---|---|
| 1 | **É ferramenta de planejamento, não mecânica de jogo.** Sem XP, sem sequência, sem "cumpri", sem meta. | Tempo de estudo não é verificável ([26 §1](26-mecanicas-do-jogo.md)): o horário é autodeclarado, e o SAS só premia o que verifica. Um botão "marcar como feito" é o primeiro passo para um streak de estudo, e o 26 §2 já fechou essa porta. |
| 2 | **O aluno monta tudo.** O SAS não propõe a semana. | Mais simples, e o aluno sabe o que a semana dele tem. |
| 3 | **Aula do colégio não é dado do SAS.** Se quiser ver as aulas na semana, o aluno cria os blocos dele. | O SAS não tem a grade de aulas hoje. Por isso o bloco tem **rótulo de texto livre**, e não só "assunto". |
| 4 | **Privado.** A coordenação não vê, e a rota nem existe para ela. | Dado autodeclarado de menor. Usar como sinal de alerta seria vigilância. |
| 5 | **Nome: "Horário de estudos".** O olho do cartão (a linha pequena em caixa-alta acima do título) é **"Quando"**. | — |
| 6 | **A estrutura da tela é a SEMANA EMPILHADA**: os sete dias numa lista só. | Saiu de uma exploração de quatro estruturas ([prompts-design-horario-de-estudos.md](prompts-design-horario-de-estudos.md): dia a dia, semana empilhada, régua do dia, semana em quadrados). Montar uma rotina é olhar a semana inteira, e a faixa de 7 dias com lista de UM dia — que este plano desenhava antes — a escondia atrás de um seletor. |

---

## 1 · O que NÃO entra na v1, e o porquê

- **Lembrete.** [30 §5](30-estado-da-implementacao.md) diz "sem notificação, o
  resto não é usado", e é verdade aqui também. Mas o motor de e-mail só avisa na
  véspera de simulado ([13](13-plano-p3-lembrete-aluno.md)); lembrete de bloco é
  outra regra, e tem que ser **opt-in** (menores). v2.
- **Assunto sugerido por bloco.** Dependeria de `importância × (1 − meu acerto)`,
  que ainda é em parte mock até o Sprint 6 classificar as questões de simulado
  ([30 §4](30-estado-da-implementacao.md)). Construir em cima de mock é fazer o
  aluno planejar a semana com um número inventado.
- **Aderência ("fiz / não fiz").** Ver decisão 1. ⚠️ Se um dia entrar, **nunca
  vira XP nem sequência**, e é decisão de produto à parte.
- **O Tio Léo lendo o horário.** Seria útil e é tentador, mas é mudança de
  superfície de dado do menor. Fica para quando o aluno disser que quer.

---

## 2 · O dado

Uma tabela, `bloco_horario_estudo` (migration `0069` — conferir se continua
livre; a última é a `0068`). Nome por extenso, como o resto do schema.

| Coluna | Tipo | Observação |
|---|---|---|
| `id` | `uuid` PK | |
| `aluno_id` | `uuid` FK → `aluno` `ON DELETE CASCADE` | |
| `dia_semana` | `smallint` `CHECK 1..7` | **ISO: 1 = segunda … 7 = domingo.** |
| `hora_inicio` | `time` | Sem fuso, e é de propósito (ver abaixo). |
| `duracao_minutos` | `int` `CHECK 15..480` | |
| `rotulo` | `text` `NOT NULL`, até 80 caracteres | Texto livre: "Termodinâmica", "Aula de Física", "Revisão". |
| `criado_em`, `atualizado_em` | `timestamptz` | |

Índice em `(aluno_id, dia_semana, hora_inicio)`.

⚠️ **`time`, não `timestamptz`.** Uma rotina semanal não tem instante absoluto:
"toda terça às 19h" é hora de parede. Guardar com fuso inventaria um problema
de horário de verão que o dado não tem.

⚠️ **O bloco não atravessa a meia-noite**: `hora_inicio + duracao ≤ 24h`. Quem
estuda das 23h à 1h faz dois blocos. Evita um bloco que pertence a dois dias na
faixa da semana.

**Sem sobreposição.** O servidor devolve **409** (e não 422: o valor é válido, só
bate com o que o aluno já tem) se o bloco cruzar outro do mesmo aluno no mesmo
dia. 422 fica para o que não faz sentido de jeito nenhum — duração de 5 minutos,
hora que não existe, rótulo vazio. É o erro que a ferramenta existe para pegar ("tenho duas
coisas às 19h"), e afrouxar depois é barato; apertar depois não é. Se o aluno
quiser "Física ou Química", cria dois blocos de meia hora.

Teto de **60 blocos por aluno**. Não há paginação no projeto de propósito
([CLAUDE.md](../CLAUDE.md), armadilha 2), e o teto é o que mantém "sem
paginação" honesto aqui.

---

## 3 · A API

Rotas em `/me/horario-estudos`, todas com `Depends(get_current_aluno)`
([api/app/routes/horario_estudos.py](../api/app/routes/horario_estudos.py)).

| Rota | O quê |
|---|---|
| `GET /me/horario-estudos` | `{ blocos: [...] }`, ordenado por dia e hora. |
| `POST /me/horario-estudos` | Cria. Recebe `diasSemana: [1,2,3,4,5]` + hora, duração e rótulo, e cria **um bloco por dia num INSERT só** — tudo ou nada. `201`; `409` se cruzar ou passar de 60 blocos; `422` se o valor não faz sentido. |
| `PATCH /me/horario-estudos/{id}` | Edita um bloco; campo ausente não é mexido. `404` se não existe **ou é de outro aluno**. |
| `DELETE /me/horario-estudos/{id}` | Apaga um bloco. `204`; `404` como acima. |

⚠️ O `DELETE` responde 204 sem corpo, e o `del` do `http.ts` sempre tenta ler
JSON: o parse vazio falha **depois** de a exclusão já ter acontecido. A solução é a
que `apagarLista` já usa (`servicos/banco.ts`): engolir só o erro de parse e
propagar o `ErroApi`. Não se mexeu no cliente HTTP compartilhado.

### Por que um bloco por vez, e não "troca a semana inteira"

⚠️ `PUT /me/vestibulares` apaga e reinsere em duas chamadas, e lá é aceitável: a
tabela tem 2 linhas. Aqui não. O backend **não tem transação** — as rotas falam
PostgREST, e `psycopg` só existe no runner de migrations (CLAUDE.md, "o ponto
mais confuso"). Se o `insert` falhar depois do `delete`, o aluno perde a semana
que montou, sem erro visível.

CRUD por bloco evita isso: cada chamada é atômica. E `dias_semana` na criação é
o que impede que isso vire cinco chamadas — um INSERT de várias linhas no
PostgREST é **um comando só**. "Segunda a sexta, 19h, 1h30" é um gesto, não
cinco.

⚠️ **PATCH e DELETE filtram por `id` E `aluno_id` da sessão.** Só por `id`, um
aluno apagaria o bloco de outro adivinhando um uuid. Tem teste para isso.

---

## 4 · A tela

### 4.1 O cartão em Estudar

[`Estudar.tsx`](../web/src/telas/Aluno/Estudar.tsx) ganha o quarto
`alu-campo-cartao`, com `to="/estudar/horario"`:

- **olho** "Quando" · **título** "Horário de estudos"
- **subtítulo com dado vivo, em três estados** (padrão do campo, sem chutar):
  - consulta falhou → "Não deu para carregar agora"
  - sem bloco nenhum → "Monte a sua semana de estudo"
  - com blocos → o próximo bloco ("Hoje, 19:00 · Termodinâmica") ou, se
    acabou o dia, o primeiro de amanhã
- um ícone no mesmo `viewBox` de 70 e `var(--alu-dado)` dos outros três

⚠️ **O layout muda.** No desktop os cartões são `flex-row` e comentados como
"três cartões de 200px numa coluna de 640px"
([aluno-estudar.css:1540](../web/styles/aluno-estudar.css#L1540)). Com quatro,
cada um fica com ~150px e "Banco de questões" já quebra em duas linhas. Vira
**grade 2×2 a partir de 900px**; no celular continua coluna. Atualizar os dois
comentários que dizem "três" (o do CSS e o cabeçalho de `Estudar.tsx`).

### 4.2 O destino: `/estudar/horario`

`EstudarHorario.tsx`, dentro do casco, ao lado de `EstudarProgresso`; abre com
`<CabecaDoCampo titulo="Horário de estudos" />`.

⚠️ **Não é uma grade 7×horas.** [24 §7](24-jornada-do-aluno.md): "a área do
aluno não deve ter tabela nenhuma", e uma grade de planilha também não cabe em
390px. A estrutura é a **semana empilhada**: os sete dias numa lista só, cada um
uma seção, **todos os blocos à vista sem escolher dia**.

1. **Uma linha de contexto** no topo: "Próximo simulado: P5, em 12 dias" e
   "Semana: 11h30 planejadas", um fato em cada ponta. É **fato ao lado de fato**,
   sem "você deveria" e sem barra de meta. O simulado some quando não há (e `null`
   é comum); o total aparece sempre que há um bloco.
2. **Sete seções**, sempre as sete, cada uma com o nome do dia, o total do dia e
   um "+" redondo de 44px que cria um bloco naquele dia. Hoje é a única seção que
   muda de cor (DADO), com um ponto cheio e "· HOJE".
3. **O bloco é um cartão tocável** — o horário grande, o rótulo e "até 20:30 ·
   1h30" — e tocar nele abre a edição. Só **um** cartão da semana leva a marca de
   "PRÓXIMO · EM 1H20" (borda de 2px em DADO), esteja em que dia estiver. Dia sem
   bloco é uma linha **vazada** "Sem bloco", e a linha inteira cria um.
4. **"Adicionar bloco"** colado na base da coluna (`position: sticky`), deixando
   livre o canto do botão flutuante do Tio Léo no celular.
5. **O bloco é lido como uma frase**, numa [`Folha`](../web/src/telas/Aluno/pecas/Folha.tsx):
   "TODA seg ter qua qui sex · ÀS 19:00 · POR 1h30 · ESTUDAR Termodinâmica", mais
   "Termina às 20:30". Dias de escolha múltipla ao criar (é o gesto de "segunda a
   sexta" de uma vez) e de escolha única ao editar — editar o bloco de quarta não
   mexe no de segunda. Editar tem um "Apagar bloco" **quieto, não vermelho**, com
   confirmação em duas etapas: a cor ALERTA é da etiqueta de distância e do que
   está abaixo do corte, e apagar um bloco do próprio horário não é nada disso.

⚠️ **Um plano, nunca um registro.** Nenhum bloco é riscado, apagado ou marcado
quando o horário passa: sem check, sem "feito", sem barra, sem XP. Quem passou fica
igual a quem não passou ([26 §2](26-mecanicas-do-jogo.md)).

⚠️ **O vazio é o caso comum**, então ele é desenhado primeiro e **ensina o gesto**
(como o de `EstudarProgresso`): o texto mostra "segunda a sexta, 19h, 1h30" como
exemplo do que dá para criar de uma vez.

⚠️ **Falha de consulta nunca vira estado vazio.** "Monte a sua semana" para quem
montou doze blocos é a mentira mais cara da tela. Erro tem a própria mensagem e
um "Tentar de novo", dizendo que o horário continua gravado.

### 4.3 A aba Hoje

[`Hoje.tsx`](../web/src/telas/Aluno/Hoje.tsx) ganha **uma linha**, não um bloco:
"Próximo: hoje, 19:00 · Termodinâmica →", que leva a `/estudar/horario`.

- **Some** se o aluno não tem bloco nenhum. A Hoje não pode cobrar quem não usa.
- Sugestão de lugar: depois da cantina e antes da sequência. A cantina é a única
  coisa da tela que **expira**, e a missão é o herói. A posição final se decide
  vendo a tela no browser.
- ⚠️ Nada de XP, sequência ou tom de cobrança aqui. É o que o aluno escreveu,
  devolvido a ele.

---

## 5 · Onde o código mora

- **Regra pura em `web/src/dominio/horarioEstudos.ts`**, com teste ao lado:
  minutos ↔ "HH:MM", duração por extenso ("1h30"), soma da semana, **próximo
  bloco a partir de (dia, hora)**, sobreposição, e a conversão
  `getDay()` ↔ ISO.
- **Hooks**: `hooks/horarioEstudos.ts`, leitura **e** escrita no mesmo arquivo — como
  `hooks/cantina.ts`, porque a superfície é pequena e de um assunto só, e separar
  faria a invalidação atravessar arquivos para nada. Leitura com `staleTime: 0`,
  como o resto do `/me`. As chamadas HTTP estão em `servicos/api.ts` e os tipos em
  `tipos/horarioEstudos.ts`. A fonte **não** passa pelo `dados/aluno/index.ts`: o
  `index` é a costura de mock/real das fontes que ainda podem ser mock, e esta nasce
  real.
- **Registro**: entrada `horarioEstudos` em
  [registro.ts](../web/src/dados/aluno/registro.ts), estado `'real'`, e depois
  `npm run inventario` para regenerar o [30](30-estado-da-implementacao.md).
  O registro é o que faz a fonte aparecer no doc 30; o `inventario.test.ts`
  quebra se o doc envelhecer.
- **Backend**: um módulo de regras (`api/app/horario_estudos.py` — limites,
  sobreposição, teto, e as quatro operações no banco), um router próprio
  (`api/app/routes/horario_estudos.py`, só fronteira) e os schemas
  (`api/app/schemas/horario_estudos.py`), com os tipos espelhados em
  `web/src/tipos/horarioEstudos.ts`. Router próprio, e não mais quatro rotas em
  `me.py`, porque `me.py` é proxy do que o aluno **lê** sobre as próprias notas, e
  aqui o aluno **escreve**.

---

## 6 · Armadilhas que já dá para ver

1. **`getDay()` do JavaScript é 0 = domingo; o banco é 1 = segunda … 7 = domingo.**
   Erro de um dia, em silêncio, em todo bloco de domingo e de segunda. A
   conversão fica **num lugar só**, em `dominio/`, com teste cobrindo domingo
   e segunda.
2. **O PostgREST devolve `time` como `"19:00:00"`.** O front trabalha com
   `"19:00"`. Normaliza num ponto só, na borda do contrato.
3. **O PostgREST cacheia o schema.** Depois da migration:
   `docker compose restart postgrest`, senão a rota nova volta **404** e parece
   bug de código (CLAUDE.md, armadilha 1). Em produção, `deploy.sh --migrar`.
4. **"Hoje" é o relógio do aparelho.** Aceitável: o colégio e os alunos estão
   num fuso só. Registrado aqui para não parecer esquecimento.
5. **Tema escuro e `--alu-*`.** O cartão e a tela leem os tokens `--alu-*` e
   nenhuma cor nova. O "dia selecionado" é **preenchido** e os outros
   **vazados**, igual ao resto do produto — não existe verde nem semáforo.
6. **O portão do browser.** É a terceira vez seguida que um plano deixa "nada foi
   visto rodando" aberto ([37 §6](37-plano-refatoracao-visual-coordenacao.md),
   [38 §10.2](38-plano-cantina.md), [39 §6](39-plano-refatoracao-design.md)).
   Esta entrega só fecha com screenshot a **1440, 390 e 360px, claro e escuro**,
   pelo MCP `chrome`.

---

## 7 · Ordem de trabalho

| Etapa | O que | Portão |
|---|---|---|
| 1 | Migration `0069` + `.down.sql` | `docker compose run --rm migrate up`, depois `restart postgrest` |
| 2 | Rotas + schemas | `pytest`: criar em vários dias, sobreposição → 409, fora do intervalo → 422, teto de 60, **PATCH/DELETE de bloco de outro aluno → 404**, sessão de coordenação → recusada |
| 3 | `dominio/horarioEstudos.ts` | `npm test`, com os casos de domingo, segunda e meia-noite |
| 4 | Hooks + registro + `npm run inventario` | `npm test` (a `costura` e o `inventario` passam) |
| 5 | O cartão em Estudar (2×2), `EstudarHorario`, a linha na Hoje | `npm run typecheck && npm run lint` |
| 6 | Verificação no browser | os três tamanhos, os dois temas, e os três estados do subtítulo |
| 7 | Deploy | `./infra/vps/deploy.sh --migrar`, depois `--verificar` |

---

## 8 · Ainda aberto, e pequeno

- **Sobreposição rejeitada** é o padrão adotado (§2). Se na prática o aluno
  reclamar, afrouxa para um aviso.
- **A semana começa na segunda.** Se alguém quiser domingo primeiro, é só ordem
  de exibição; o dado não muda.
- **Hora em passos livres** (`<input type="time">`) ou de 15 em 15 minutos. Vale
  ver como o `<input type="time">` se comporta no Safari do iPhone antes de
  decidir; o Simulator ainda não está disponível nesta máquina
  ([20 §2](20-mobile.md)).
- **O teto de duração nos atalhos é 3h** (a API aceita até 8h). Quem quiser mais
  faz dois blocos encostados — encostar não é sobrepor.

---

## 9 · O que foi verificado, e o que NÃO foi

Escrito porque é a **quarta vez** que um plano deste projeto precisa dizer isto
([37 §6](37-plano-refatoracao-visual-coordenacao.md), [38 §10.2](38-plano-cantina.md),
[39 §6](39-plano-refatoracao-design.md)): *"funcionou"* sem dizer onde é tão
perigoso quanto não ter testado.

**Verificado (24/10/2026), contra um banco descartável, um PostgREST próprio e um
Chrome headless — nunca contra o stack de dev nem contra produção:**

- **A migration `0069`**, em Postgres 16 de verdade: `up`, nove entradas inválidas
  recusadas pelo próprio banco (dia 0 e 8, duração de 14 e de 481 minutos, bloco que
  passa da meia-noite, hora com segundos, rótulo em branco ou de 81 caracteres, aluno
  inexistente), o `ON DELETE CASCADE` e o `down`.
- **A API de ponta a ponta**, por HTTP, passando pelo PostgREST: criar "seg a sex" em
  um gesto, `horaInicio` voltando `"19:00"` (e não o `"19:00:00"` do banco), 409 de
  sobreposição **sem deixar nenhum bloco criado**, 422 de valor inválido, 401 sem
  token, 403 para sessão de coordenação, **uma segunda aluna recebendo 404 ao editar
  ou apagar o bloco da primeira — e o bloco continuando intacto**, e o `DELETE` em 204.
- **A tela**, a **360, 390 e 1440px, nos temas dia e noite**: o estado vazio, a
  semana com os dados de exemplo, a folha (criar, conflito ao vivo, editar, confirmar
  e apagar), editar e apagar **de verdade pela tela** (o Postgres confirma), a falha
  de consulta (a tela diz "Não deu para carregar", o cartão em Estudar também, e a
  Hoje esconde a linha — nenhuma diz "Monte a sua semana"), e **nenhum transbordo
  horizontal** em nenhuma das telas novas.
- **Os testes**: 51 novos no backend e 41 novos no front.

**NÃO verificado:**

- ⚠️ **Safari do iPhone.** O Simulator não está disponível ([20 §2](20-mobile.md)).
  Em particular o `<input type="time">` — no iOS ele abre um seletor próprio —, o
  `position: sticky` do botão da base com a barra de endereço que encolhe, e o
  teclado sobre a folha. A verificação foi em Chrome.
- **Produção.** A migration não foi aplicada lá. O `deploy.sh --migrar` aplica e já
  reinicia o PostgREST (cache de schema, armadilha 1 do CLAUDE.md).
- **Aparelho de verdade e leitor de tela.** Há `aria-label`, `aria-pressed`,
  `role="alert"` e foco visível, mas ninguém navegou com VoiceOver.
- **Muitos blocos.** O teto é 60, e a tela foi vista com 8. Sete seções com doze
  blocos cada é uma rolagem longa que ninguém mediu.
- **O relógio é o do aparelho**, e a tela foi verificada com um relógio de mentira
  fixo em terça, 17:40 (para o "PRÓXIMO · EM 1H20" ser determinístico). A virada da
  meia-noite e o domingo à noite estão cobertos por teste de domínio, não pela tela.

**Já era assim antes desta entrega, e fica fora dela:** em `/estudar` a página
transborda 6px na horizontal. É o ponto da tarja "sem rota" (`.alu-tarja--ponto`,
`right: -6px`) do elo "Revisar os 34 erros dos seus simulados" — medido na árvore
**sem** estas mudanças, com o mesmo culpado. A seta desse elo também cai para a
segunda linha no desktop.
