# 38 — Cantina · cardápio, pedido do aluno e o terceiro tipo de sessão

> Estruturação, não implementação. O que está aqui é o desenho, o schema, as
> rotas, o faseamento e — principalmente — **o que ainda não foi decidido** (§8).
>
> **Decidido em 05/09** (§8.0), e já embutido no resto do documento:
> o **prazo do pedido é da cantina**, não do sistema; **quem não pediu não
> come**; **conceder o direito é só do administrador**; o direito é uma **flag
> pura**, sem vigência; **não há pedido fora do prazo**; o aluno vê **todos os
> dias com cardápio lançado**; **não há lembrete no v1**; almoço e janta são
> **cardápios diferentes**; a **restrição alimentar é registrada**; e o escopo
> é **só as turmas ITA/IME**, que são as únicas que existem neste banco.
>
> **Nada mais trava código** — o que resta em §8.1 tem proposta pronta.
>
> §9 responde à pergunta de tempo real — o cardápio aparecendo para o aluno sem
> refresh — com o custo de cada camada.

## 0 · O que foi pedido, em uma frase

Um grupo de alunos tem direito a alimentação (almoço e/ou janta). Esses alunos
ganham um card de cantina no painel; a cantina entra por uma porta própria
(`/login-cantina`), lança o cardápio do dia num calendário, define **quantas
opções de cada bloco** o aluno pode escolher, e vê os pedidos daquele dia. A
coordenação administra os dois lados: quem tem direito e quem é a cantina.

## 1 · A decisão que organiza o resto: a cantina é um TIPO de sessão, não um papel

Existem hoje dois níveis de identidade no SAS, e confundi-los derruba acesso
([api/app/auth.py](../api/app/auth.py) tem um ⚠️ inteiro sobre isso):

* **`tipo`** — que tipo de SESSÃO é. Hoje `aluno` ou `coordenador`. Decide
  tabela, namespace de chat e casco do front.
* **`papel`** — o que uma sessão de coordenação pode a mais. Hoje `coordenador`
  ou `administrador` (migration 0045).

A cantina é **`tipo`**, não `papel`. Não é coordenação com menos poder: é outra
pessoa, outra tabela de login, outro casco, e não pode ver aluno, nota, ciclo
nem chat. Um `papel: "cantina"` dentro de `usuario_coordenacao` passaria por
`get_current_coordenador` — que aceita todo papel de propósito — e abriria as 39
rotas de coordenação para a copeira. Não é uma opção.

### 1.1 · ⚠️ O terceiro tipo é a mudança mais perigosa deste plano

Adicionar `"cantina"` a `TIPOS_DE_SESSAO` quebra a premissa de todo lugar que
divide o mundo em "aluno" e "todo o resto". São três, e foram verificados um a
um. **Consertar os três é pré-requisito**, não faxina posterior:

1. **[api/app/routes/foto_perfil.py:59-65](../api/app/routes/foto_perfil.py#L59-L65)**
   — `_entidade_do_usuario` faz `if tipo == "aluno": … ; return "coordenador",
   "usuario_coordenacao", user["sub"]`. O docstring dela diz, literalmente, "só
   'aluno' ou 'coordenador' chegam aqui" — e essa frase deixa de ser verdade no
   minuto em que a cantina existe. Uma sessão de cantina passaria a **ler e
   escrever `usuario_coordenacao` por id**. Conserto: `elif == "coordenador"` e
   `raise 403` no fim, que é o que
   [api/app/chat/rotas.py:100-119](../api/app/chat/rotas.py#L100-L119) já faz
   certo — e faz certo porque foi corrigido depois de uma vulnerabilidade real
   com exatamente esta forma (token de download virando sessão de coordenação).
2. **[web/src/App.tsx](../web/src/App.tsx)** — `RotaProtegida` faz
   `tipo() === 'aluno' ? <AppAluno/> : <AppCoordenacao/>`. A cantina cairia no
   casco da coordenação. As rotas dariam 403, mas a tela monta — e tela que
   monta para dar erro ensina a pessoa a desconfiar do produto. Vira switch de
   três com default → `/login`.
3. **[web/src/servicos/sessao.ts](../web/src/servicos/sessao.ts)** — o array
   `TIPOS` precisa de `'cantina'`, senão `tipo()` devolve `null`, `RotaProtegida`
   nunca acerta e a sessão nasce morta.

O chat NÃO precisa de conserto: `namespace_do_usuario` já é fail-closed e a
cantina simplesmente não terá chat. É o comportamento certo — não mexer.

## 2 · Schema

Três migrations, uma por fase (§7). **Cada uma exige
`docker compose restart postgrest`** — o schema cache é lido na inicialização e
sem o restart as tabelas novas voltam 404, que parece bug de código
(CLAUDE.md, armadilha 1).

### 2.1 · A cantina e suas contas — migration 0047

```sql
CREATE TABLE cantina (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome                    text NOT NULL,
    ativo                   boolean NOT NULL DEFAULT true,
    -- A REGRA de prazo da casa, que pré-preenche cada cardápio novo (§8.0.1).
    -- Não é o prazo: o prazo é `cardapio.pedidos_ate`, e a cantina pode
    -- sobrescrever dia a dia. Isto existe para ela não redigitar um
    -- timestamp por dia útil, 200 vezes por ano.
    prazo_padrao_dias_antes int  NOT NULL DEFAULT 1 CHECK (prazo_padrao_dias_antes >= 0),
    prazo_padrao_hora       time NOT NULL DEFAULT '20:00',
    criado_em               timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE usuario_cantina (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cantina_id      uuid NOT NULL REFERENCES cantina(id),
    email           text NOT NULL,
    nome            text NOT NULL,
    senha_hash      text NOT NULL,
    ativo           boolean NOT NULL DEFAULT true,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    ultimo_login_em timestamptz
);

CREATE UNIQUE INDEX idx_usuario_cantina_email ON usuario_cantina (lower(email));
```

Espelho fiel de
[0021_usuario_coordenacao.sql](../api/migrations/0021_usuario_coordenacao.sql),
inclusive o índice case-insensitive — o mesmo motivo vale aqui (ninguém deve
criar `Copa@` e `copa@` como contas diferentes).

**O prazo tem DOIS níveis, e os dois são da cantina** (§8.0.1). A regra
(`prazo_padrao_*`) é a política da casa e vive aqui; o prazo real
(`cardapio.pedidos_ate`) é absoluto, vive no cardápio do dia e pode divergir da
regra sempre que a cantina quiser. Guardar só a regra tornaria "este cardápio
ainda aceita pedido?" uma conta em vez de uma comparação — e essa pergunta é
feita em toda leitura do aluno.

**Por que `cantina` separada de `usuario_cantina`, se hoje a cantina é uma só:**
o cardápio precisa pertencer a algo que sobreviva à rotatividade de quem
trabalha lá. Desativar a conta da Dona Maria não pode órfãos os cardápios de
março. Custa uma tabela de quatro colunas e resolve o dia em que houver
cantina do fundamental e cantina do médio.

### 2.2 · O cardápio — migration 0048

```sql
CREATE TABLE cardapio (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cantina_id    uuid NOT NULL REFERENCES cantina(id),
    data          date NOT NULL,
    refeicao      text NOT NULL CHECK (refeicao IN ('almoco', 'janta')),
    -- Nulo enquanto rascunho; PUBLICAR sem prazo é recusado pela API. Não é
    -- NOT NULL porque montar o cardápio e decidir o prazo são dois momentos,
    -- e obrigar o prazo na primeira digitação trava a montagem da semana.
    pedidos_ate   timestamptz,
    publicado_em  timestamptz,
    -- "Não haverá refeição neste dia" — sábado, feriado, recesso. É diferente
    -- de "ainda não lancei", e a diferença importa: sem ela o alarme da
    -- coordenação ("cardápio de amanhã não lançado") mente todo fim de semana.
    sem_refeicao  boolean NOT NULL DEFAULT false,
    criado_por    uuid REFERENCES usuario_cantina(id),
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cantina_id, data, refeicao)
);

CREATE TABLE cardapio_bloco (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cardapio_id        uuid NOT NULL REFERENCES cardapio(id) ON DELETE CASCADE,
    nome               text NOT NULL,   -- "Guarnição", "Vegetariano", "Proteínas", "Salada"
    ordem              int  NOT NULL,
    escolhas_minimas   int  NOT NULL DEFAULT 0 CHECK (escolhas_minimas >= 0),
    escolhas_maximas   int  NOT NULL DEFAULT 1 CHECK (escolhas_maximas >= escolhas_minimas),
    UNIQUE (cardapio_id, ordem)
);

CREATE TABLE cardapio_opcao (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bloco_id   uuid NOT NULL REFERENCES cardapio_bloco(id) ON DELETE CASCADE,
    nome       text NOT NULL,   -- "Arroz", "Frango Grelhado", "Proteína de Soja"
    ordem      int  NOT NULL,
    disponivel boolean NOT NULL DEFAULT true,
    UNIQUE (bloco_id, ordem)
);
```

Três decisões embutidas aqui, e cada uma tem alternativa:

* **`publicado_em` nulo = rascunho.** O calendário pedido ("dias marcados ou
  não") tem no mínimo dois estados, mas na prática são três: sem cardápio,
  rascunho e publicado. A cantina monta a semana na sexta à tarde — sem
  rascunho, ou ela publica cardápio pela metade ou digita tudo de uma vez.

* **`escolhas_maximas` vive no BLOCO, não no cardápio.** É o que a foto pede:
  "Guarnição: escolha 2, Proteína: escolha 1". `escolhas_minimas` entra junto
  porque "escolher uma proteína é obrigatório" é uma regra real e custa uma
  coluna — sem ela, essa regra viraria validação escondida no front.

* **O bloco é texto livre, não taxonomia fixa.** Guarnição/Vegetariano/
  Proteínas/Salada é o cardápio de HOJE, não uma lei. Uma tabela de blocos
  canônicos obrigaria migration toda vez que a cantina inventar "Sobremesa". O
  preço é que agregar "quanto de proteína no ano" exige casar por nome — e isso
  não é uma pergunta que alguém faz.

⚠️ **Copiar NUNCA copia `pedidos_ate`.** O prazo é absoluto; copiar a segunda
para a terça carregando o timestamp da segunda entrega um cardápio publicado
com prazo já vencido — ninguém pede, e a cantina descobre no balcão. O copiar
recalcula a partir da `prazo_padrao_*` da cantina para a data nova.

**O verbo que faz esse modelo funcionar na prática é copiar — de DIA para DIA,
dentro da mesma refeição.** Almoço e janta são cardápios diferentes (§8.0.8), e
copiar entre eles não serve para nada. Na foto, Segunda e Terça são quase
idênticas. Sem "copiar de outro dia", a cantina digita 15
linhas por dia, 5 dias por semana, e abandona o produto na terceira semana. O
`POST /cantina/cardapios/{id}/copiar-de/{origem}` não é conveniência: é o que
decide se a ferramenta é usada.

### 2.3 · O direito e o pedido — migration 0049

```sql
CREATE TABLE direito_refeicao_aluno (
    aluno_id uuid NOT NULL REFERENCES aluno(id),
    refeicao text NOT NULL CHECK (refeicao IN ('almoco', 'janta')),
    PRIMARY KEY (aluno_id, refeicao)
);
-- A FK para `aluno` basta, e isso é uma decisão, não um acaso (§8.0.10): o
-- SAS só conhece as turmas ITA/IME, e o benefício é delas. Não há segundo
-- cadastro de aluno, nem aluno "só da cantina".
--
-- SEM vigência, de propósito (§8.0.4): a linha existe = tem direito; some =
-- não tem. `ativo_desde`/`ativo_ate`, como `matricula_turma` faz, foram
-- recusados — quem revogou e quando é pergunta de AUDITORIA, não de estado, e
-- `evento_auditoria` já responde. Duas datas a mais criariam três leituras
-- possíveis do mesmo aluno ("tem direito", "tinha", "vai ter") em toda tela e
-- em toda consulta, para uma pergunta que ninguém fez ainda.

CREATE TABLE pedido_refeicao (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cardapio_id   uuid NOT NULL REFERENCES cardapio(id),
    aluno_id      uuid NOT NULL REFERENCES aluno(id),
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cardapio_id, aluno_id)
);

CREATE TABLE pedido_refeicao_item (
    pedido_id uuid NOT NULL REFERENCES pedido_refeicao(id) ON DELETE CASCADE,
    opcao_id  uuid NOT NULL REFERENCES cardapio_opcao(id),
    PRIMARY KEY (pedido_id, opcao_id)
);

CREATE INDEX idx_pedido_refeicao_cardapio ON pedido_refeicao (cardapio_id);
CREATE INDEX idx_pedido_refeicao_aluno    ON pedido_refeicao (aluno_id);
```

**A flag "almoço e/ou janta" é uma TABELA, não duas colunas booleanas.** Zero,
uma ou duas linhas por aluno resolvem o "e/ou" sem estado impossível. É
exatamente o desenho de
[`vestibular_alvo_aluno`](../api/migrations/0001_schema_inicial.sql) — precedente
do próprio projeto para "um conjunto enumerado por aluno", e o schema é para ser
lido por quem entende do domínio.

Quem concedeu e quando **não** viram colunas: vão para `evento_auditoria`
([api/app/auditoria.py](../api/app/auditoria.py)), que é onde o resto do
projeto guarda "quem fez o quê", com canal próprio `cantina`.

### 2.4 · ⚠️ Volume — a armadilha 2 chega aqui pela primeira vez de verdade

Não existe paginação em lugar nenhum do SAS, e `PGRST_DB_MAX_ROWS` está sem
valor de propósito. `pedido_refeicao_item` é a primeira tabela do projeto que
cresce por *dia útil × aluno × item*: 200 dias × 2 refeições × N alunos × ~4
itens. Com 100 alunos com direito são ~160 mil linhas no primeiro ano; com 900,
1,4 milhão.

Três consequências que precisam estar no código desde o primeiro commit:

1. **Nenhuma rota devolve "os pedidos".** Toda leitura é filtrada por
   `cardapio_id` — um dia, uma refeição. O histórico do aluno é filtrado por
   `aluno_id` com janela de data.
2. **A contagem de produção é uma VIEW agregada**, `v_contagem_pedidos_por_opcao
   (cardapio_id, bloco, opcao, quantos)`, não uma soma feita em Python sobre as
   linhas cruas. Somar no cliente traz a tabela inteira pelo PostgREST.
3. Os dois índices acima entram junto com as tabelas, não depois.

### 2.5 · Editar cardápio que já tem pedido

`pedido_refeicao_item` referencia `cardapio_opcao` por id. Se a cantina renomear
"Frango Grelhado" para "Peixe" depois de 40 pedidos, 40 alunos pediram peixe sem
saber. A API recusa, com mensagem explícita:

* **renomear ou apagar** opção que já tem pedido → 409;
* **`disponivel = false`** → sempre permitido (acabou o frango), e o pedido de
  quem escolheu aparece marcado para a cantina resolver no balcão;
* **acrescentar** opção nova → sempre permitido.

A alternativa (gravar o nome dentro do item, como snapshot) desnormaliza para
proteger contra um caso que a recusa já resolve — e a recusa ensina a cantina a
publicar direito.

### 2.6 · Restrição alimentar — desenho mínimo *(decidido, §8.0.9)*

```sql
ALTER TABLE aluno ADD COLUMN restricao_alimentar text;

COMMENT ON COLUMN aluno.restricao_alimentar IS
    'Restrição alimentar em texto livre, preenchida pela coordenação. Aparece
     para a cantina ao lado do pedido do aluno, e em lugar nenhum mais.';
```

Coluna em `aluno`, não tabela nova: é um campo por pessoa, sem histórico e sem
cardinalidade — e `aluno` já carrega colunas que o ingest do Canvas não toca
(`senha_hash`, `foto_perfil_storage`). "Estamos simplificando" é a instrução.

Três restrições que **fazem parte do desenho**, não são zelo extra:

* **quem preenche é a coordenação**, na mesma tela em que concede o direito —
  não o aluno. Autodeclaração de saúde por menor abre um problema de
  consentimento que este produto não tem estrutura para resolver;
* **aparece só na lista de pedidos da cantina**, ao lado do nome. Não entra em
  ficha, painel, exportação de dossiê nem chat;
* é **a primeira informação de saúde no SAS**. Não muda a arquitetura, mas muda
  o que um vazamento significaria — e por isso a alteração deste campo é
  auditada como a concessão do direito (canal `cantina`).

## 3 · Rotas

Arquivo novo: `api/app/routes/cantina.py`, registrado em
[api/app/main.py](../api/app/main.py) junto dos outros.

### 3.1 · Autenticação

`POST /auth/login` ganha o ramo `tipo == "cantina"`, reusando a rota existente —
o rate-limit por `ip:usuario`, a auditoria de `login_ok`/`login_falhou` e o
formato de resposta já estão lá, e uma rota paralela duplicaria os três. O token
carrega `tipo: "cantina"`, `sub` = id do usuário e `cantina_id`.

Guard novo em `auth.py`: `get_current_cantina`. E `get_current_coordenador`
**não** muda — a cantina não passa por ele.

### 3.2 · Aluno — `get_current_aluno`

| Rota | O quê |
|---|---|
| `GET /me/cantina` | Meus direitos + **todos os cardápios publicados de hoje em diante** + meus pedidos + o prazo de cada um |
| `PUT /me/cantina/pedidos/{cardapio_id}` | Grava/substitui o pedido inteiro (idempotente) |
| `DELETE /me/cantina/pedidos/{cardapio_id}` | Desisti |

Três validações no `PUT`, todas no servidor:
o aluno tem direito **àquela refeição**; `now() < pedidos_ate`; a contagem por
bloco respeita `escolhas_minimas`/`escolhas_maximas`. O backend nunca escreve
SQL, então nada disso é `CHECK` — é Python, e por isso precisa de teste.

⚠️ **O prazo é duro, e é a única regra com consequência de verdade** (§8.0.2):
depois dele o `PUT` e o `DELETE` devolvem **409**, porque quem não pediu não
come. A recusa é do servidor, não da tela — a tela pode estar aberta desde
antes do prazo, e um botão desabilitado no cliente não é uma regra.

O aluno **pode trocar** o pedido quantas vezes quiser até o prazo: o `PUT` é
idempotente e substitui os itens inteiros. É consequência de o prazo existir —
com um instante em que a contagem congela, mudar de ideia antes dele não custa
nada a ninguém.

**O aluno vê todos os dias já publicados, não só o próximo** (§8.0.6). Se a
cantina lança a semana na sexta, ele resolve a semana na sexta. Cada dia tem o
seu prazo, e é o prazo que governa — não a posição na lista.

⚠️ **Com teto de 30 dias à frente.** Não existe paginação em lugar nenhum
(CLAUDE.md, armadilha 2); "todos os publicados" sem janela vira a resposta
crescendo em silêncio no dia em que alguém lançar o semestre inteiro. Trinta
dias cobrem qualquer antecedência real de cardápio.

### 3.3 · Cantina — `get_current_cantina`

| Rota | O quê |
|---|---|
| `GET /cantina/calendario?ano=&mes=` | Um objeto por dia: `sem-cardapio` / `rascunho` / `aberto` / `fechado` / `sem-refeicao`, + nº de pedidos |
| `GET/POST/PUT /cantina/cardapios[/{id}]` | Montar o cardápio, blocos e opções |
| `POST /cantina/cardapios/{id}/publicar` | Rascunho → publicado |
| `POST /cantina/cardapios/{id}/copiar-de/{origem_id}` | O verbo do §2.2 |
| `GET /cantina/cardapios/{id}/contagem` | **O que cozinhar** — agregado pela view |
| `GET /cantina/cardapios/{id}/pedidos` | **O que servir** — linha por aluno |

Toda rota filtra por `cantina_id` do token, nunca por parâmetro — senão uma
cantina lê o cardápio da outra trocando um id na URL.

**São cinco estados no calendário, não dois, e o prazo é que os cria** (§8.0.1).
`aberto` e `fechado` são o mesmo cardápio publicado antes e depois de
`pedidos_ate`, e a diferença é a que a cantina mais precisa ler: em `fechado` a
contagem é **final**, e é ela que vai para o fogão. Um calendário que só diz
"lancei / não lancei" obriga a cantina a conferir a hora de cabeça.

⚠️ **Depois do prazo ninguém acrescenta pedido — nem a cantina** (§8.0.5). A
alternativa (a cantina inclui o aluno que esqueceu, marcado como exceção) foi
recusada por simplicidade, e o custo dela é conhecido e aceito: **o aluno que
esquecer é resolvido no balcão, fora do sistema.** O ganho é que a contagem de
`fechado` é definitiva de verdade — nada entra depois dela, então o número que
vai para o fogão é o número que a tela mostrou.

**A cantina pode esticar o prazo depois de publicar; encurtar, só para um
instante ainda no futuro.** Esticar não tira nada de ninguém. Encurtar para o
passado fecharia o pedido retroativamente para quem ainda ia pedir, e é
exatamente a forma de o aluno ficar sem almoço sem ter feito nada errado.

### 3.4 · Coordenação

| Rota | Guard |
|---|---|
| `GET /cantina/calendario`, `GET /cantina/cardapios/{id}` | `get_current_coordenador` (leitura) |
| `GET /administracao/direito-refeicao` (a lista) | `get_current_coordenador` (leitura) |
| `PUT/DELETE /alunos/{id}/direito-refeicao` | **`get_current_administrador`** |
| `POST /administracao/direito-refeicao/lote` | **`get_current_administrador`** |
| `GET/POST/PATCH /administracao/cantinas` e `/usuarios-cantina` | `get_current_administrador` |

Criar login para outra pessoa é do administrador — é a regra que a migration
0045 estabeleceu e não há motivo para a cantina ser exceção.

**Conceder o direito também é só do administrador** (§8.0.3). Ler continua de
qualquer coordenador, e a divisão é a mesma de
[Contas.tsx](../web/src/telas/Administracao/Contas.tsx): ver é de todo mundo,
mexer é de um só, e o que a pessoa não pode **nem aparece** na tela — botão que
existe para dar 403 ensina a desconfiar do produto.

⚠️ **A concessão em lote existe por causa dessa decisão, não apesar dela.** Com
uma única pessoa autorizada, ligar o direito de 80 alunos um a um é o tipo de
tarefa que não acontece — e o que não acontece na véspera do primeiro dia letivo
derruba a feature inteira. `POST …/lote` recebe uma lista de alunos e a
refeição, e a tela dá seleção múltipla.

Toda concessão e revogação vai para `evento_auditoria` no canal `cantina`
(`direito_refeicao_concedido` / `direito_refeicao_revogado`), com o
administrador como ator. É benefício com consequência financeira: sem autor e
data, "quem liberou este aluno?" não tem resposta.

## 4 · Front do aluno

**O card entra em [Hoje.tsx](../web/src/telas/Aluno/Hoje.tsx), e não na barra de
navegação.** A barra tem quatro destinos e a lista sai do que o aluno vem fazer
(docs/24 §7.1); um quinto ícone de garfo ao lado de "Jornada" diz que comer e
estudar têm o mesmo peso no produto, e não têm.

Posição: **entre `<MissaoDeHoje/>` e `<BlocoDaSequencia/>`**. A tela é ordenada
por "o que eu faço agora", e escolher o almoço é literalmente isso — é a única
coisa da tela que **expira**. Fica abaixo da missão porque a missão é o herói e
não se mexe nisso.

⚠️ **O CARD É A ÚNICA PORTA DE `/cantina`.** A tela não está na barra de quatro
destinos — de propósito —, então toda saída quieta dele precisa levar lá. Uma
linha sem link deixa a tela inalcançável, e foi o defeito da primeira escrita.

São **cinco** estados, e a ordem de prioridade entre eles é regra: mora em
`dominio/cantina.ts::cardDaCantina`, com teste ao lado, e não dentro do
componente.

* **prazo aberto, sem pedido** → o card cheio, com o **prazo em magnitude**
  ("escolha até as 20h de hoje"). É o único momento em que ele compete com a
  missão, e deve competir — perder esse prazo custa o almoço, não um lembrete.
  Vence os outros: um cardápio de quarta ainda por pedir é mais urgente que o
  de terça já resolvido.
* **prazo aberto, já pedi** → linha quieta com o resumo ("arroz · feijão ·
  frango grelhado · *trocar*"), no padrão do `EloQuieto`.
* **prazo vencido, com pedido para um dia que ainda vem** → linha quieta com o
  resumo e *ver*. É a resposta a "o que eu vou comer amanhã?", e a falta dela
  era o defeito: o card sumia, e com ele a única porta da tela. O link não diz
  "trocar" porque o servidor recusaria com 409.
* **prazo vencido, sem pedido, HOJE** → linha quieta e factual: *"sem almoço
  reservado hoje"*. Não é punição nem cobrança — é para o aluno **não caminhar
  até o balcão à toa**, que é o único desfecho ruim que ainda dá para evitar
  nesse ponto. Só vale para hoje: dizer isso de quinta-feira seria cobrança
  sobre o que ainda nem chegou.
* **sem direito, ou sem cardápio publicado** → não existe. Some, não vira
  estado vazio.

⚠️ **Nenhum "+XP" perto disso, e nenhuma cor de alerta.** O card é o único
elemento da área do aluno que não fala de estudo; puxá-lo para o vocabulário do
jogo confunde o que o produto premia (docs/26 §1).

A tela `/cantina` lista **todos os dias já publicados** (§8.0.6), um bloco por
dia, cada um com o seu prazo e o seu estado. O card em Hoje continua tratando
só do **próximo prazo aberto** — ele responde "o que eu faço agora", e uma
lista de duas semanas ali dentro seria um formulário no meio da tela do herói.

Arquivos: `web/src/telas/Aluno/Cantina.tsx` (tela cheia em `/cantina`, dentro do
casco), `web/styles/aluno-cantina.css`, e o bloco novo dentro de `Hoje.tsx`.

⚠️ **A fonte precisa de entrada em
[web/src/dados/aluno/registro.ts](../web/src/dados/aluno/registro.ts)** — hook
exportado sem registro não compila `costura.test.ts`, e docs/30 é gerado dali.

## 5 · Front da cantina — o terceiro casco

`web/src/telas/Cantina/`, e ele é deliberadamente pobre: marca, nome de quem
entrou, sair. Sem rail, sem topbar, sem busca de aluno, sem chat.

```
CascoCantina.tsx    marca · nome · sair, e nada mais
Calendario.tsx      o mês, com os três estados do §3.3
CardapioDoDia.tsx   blocos, opções, limites, publicar, copiar-de
PedidosDoDia.tsx    duas leituras, e elas são trabalhos diferentes
```

`PedidosDoDia` tem **duas** leituras porque são dois momentos do dia: a
**contagem** ("47 arroz, 31 feijão, 12 proteína de soja") é o que se lê de manhã
para cozinhar; a **lista por aluno** é o que se lê no balcão ao meio-dia. Uma
tela só com a lista obriga a cantina a contar no papel.

[CalendarioAnual.tsx](../web/src/componentes/ui/CalendarioAnual.tsx) já existe e
serve de base — hoje ele marca dias com simulado; o de cantina marca três
estados e é clicável para um destino, não para um toggle.

`web/src/telas/Login/LoginCantina.tsx` em `/login-cantina`, rota irmã de
`/login` em [App.tsx](../web/src/App.tsx), fora de `RotaProtegida`.

## 6 · Front da coordenação

Um campo novo no
[HubAdministracao](../web/src/telas/Administracao/HubAdministracao.tsx),
seguindo as cinco regras do padrão de campo — a pergunta que ele responde é
**"a cantina está em dia?"**, não "cantina". Subtítulo é dado vivo (C2):
*"cardápio de amanhã não lançado · 87 alunos com direito"* — a falha que importa
(cardápio de amanhã em branco às 18h de hoje) aparece na tela de entrada, que é
onde falha precisa aparecer.

⚠️ **O card leva ao CALENDÁRIO (`/cantina`), não à tela de contas.** A resposta
à pergunta "a cantina está em dia?" é o mês lançado, não a lista de quem lança.
Foi o contrário na primeira escrita, e o efeito foi um defeito de navegação
real: `/cantina` ficou **órfã** — nenhum link do casco da coordenação apontava
para ela, porque a decisão de não pôr a cantina no rail (§8.1.4) estava certa
mas não tinha caminho substituto. Agora as duas telas levam uma à outra, e é
por isso que o link existe nos dois sentidos: com um card só apontando para uma
delas, a outra volta a ser alcançável só digitando a URL.

Destino `/administracao/cantina`, tela inteira (C3), com duas metades no
desenho de [Contas.tsx](../web/src/telas/Administracao/Contas.tsx): em cima as
contas da cantina; embaixo a lista de alunos com o direito, com busca, filtro
por refeição e **seleção múltipla** para a concessão em lote.

⚠️ **A cantina como ESTABELECIMENTO tem ciclo de vida próprio, e ele mora aqui**
— criar, renomear, ajustar a regra de prazo e desativar. A primeira escrita
esqueceu disso: o botão era só "Nova conta" e ficava escondido atrás de "já
existe cantina", então a PRIMEIRA cantina não tinha como nascer. A tela dizia
"crie a cantina antes de criar contas" e não oferecia onde — estado vazio que
dá uma instrução sem oferecer o caminho é pior que estado vazio mudo.

⚠️ **Desativar a CANTINA não é desativar as contas dela uma a uma.**
`_login_da_cantina` confere `cantina.ativo` além de `usuario_cantina.ativo`,
então desligar o estabelecimento tranca todo mundo de uma vez — inclusive uma
conta criada depois. É o botão para "a cantina saiu do colégio", não para "a
Dona Maria saiu de férias". Nenhum dos dois apaga linha: a linha apagada
viraria um uuid sem nome em `cardapio.criado_por` e na trilha de auditoria.

⚠️ Depois de §8.0.3 esta é a **primeira tela da coordenação em que as duas
metades são de escrita exclusiva do administrador**. Para o coordenador comum
ela é uma tela de leitura inteira — e precisa ser desenhada como tal, não como
a mesma tela com botões cinzas: o que ele não pode não aparece. Ele continua
entrando porque as duas perguntas ("quantos alunos comem aqui", "a cantina
lançou o cardápio de amanhã") são de coordenação, mesmo sem poder mexer.

O cardápio em si a coordenação lê em `/cantina`, reusando o calendário da §5 em
modo leitura. **Sem entrada no rail no v1** — são cinco destinos hoje e a
cantina não é trabalho diário de coordenação (ver §8.8).

## 7 · Faseamento

> **Estado em 05/09: as quatro fases estão ESCRITAS e verificadas fora do
> browser.** 530 testes no backend (+27), 392 no front (+23), ruff, Biome,
> `tsc` e `npm run build` limpos, as três migrations aplicadas no compose e um
> smoke ponta a ponta exercitando as três sessões contra a API de verdade
> (§10). **Não está em produção** — falta o deploy e a verificação no browser.

Quatro fases. A ordem não é arbitrária: **a fase perigosa é a primeira e vai
sozinha**, para o risco de segurança ser revisado sem cardápio nenhum no
caminho.

**✅ Fase 0 · O terceiro tipo de sessão** — migration 0047, `TIPOS_DE_SESSAO`, os
três consertos fail-closed do §1.1, `get_current_cantina`, o ramo do login,
`/login-cantina`, casco vazio. *Entregável verificável: uma conta de cantina
entra e vê uma tela em branco; e uma sessão de cantina leva 403 em `/me/foto`,
no chat e nas 39 rotas de coordenação.* Esta fase merece `/security-review`.

**✅ Fase 1 · O cardápio** — migration 0048, calendário, editor, publicar,
copiar-de. *Entregável: a cantina lança a semana da foto e ela aparece marcada
no calendário.* Ninguém pede nada ainda.

**✅ Fase 2 · O direito e o pedido** — migration 0049, a flag na coordenação, o
card em Hoje, a tela `/cantina` do aluno, as validações do §3.2. *Entregável:
um aluno com direito escolhe o almoço e a cantina vê o pedido.*

**✅ Fase 3 · A leitura** — a view agregada, contagem de produção, lista por aluno,
o campo no hub, a leitura da coordenação, exportação/impressão da lista.

**Fora do escopo, decidido em 05/09 (§8.0.7): não há lembrete.** O motor de
e-mail já está em produção ([12](12-plano-p2-motor-lembretes.md),
[13](13-plano-p3-lembrete-aluno.md)) e um disparo antes de `pedidos_ate` seria
barato — mas fica de fora por ora.

⚠️ Registrado porque a combinação **cobra um preço**: com "não pediu, não come"
(§8.0.2), sem exceção no balcão (§8.0.5) e sem lembrete, **o aluno que esquecer
fica sem almoço, e o sistema não terá avisado nem terá remédio**. É uma escolha
de simplicidade legítima; é também a primeira coisa a revisitar se a
coordenação começar a receber reclamação.

## 8 · Decisões

### 8.0 · Fechadas em 05/09

| # | Pergunta | Resposta | O que ela mudou aqui |
|---|---|---|---|
| **8.0.1** | Até quando o aluno escolhe? | **A cantina define** — não o sistema | `cantina.prazo_padrao_*` (a regra) + `cardapio.pedidos_ate` (o prazo do dia, absoluto). Publicar sem prazo é recusado; copiar recalcula em vez de copiar; o calendário ganhou `aberto`/`fechado` (§2.1, §2.2, §3.3) |
| **8.0.2** | Quem não pediu, come? | **Não come** | O prazo virou a única regra com consequência real: 409 depois dele, no servidor. O card ganhou um quarto estado (§3.2, §4) |
| **8.0.3** | Conceder o direito é de quem? | **Só do administrador** | `PUT/DELETE …/direito-refeicao` sob `get_current_administrador`; leitura segue de qualquer coordenador; **concessão em lote** deixou de ser luxo (§3.4, §6) |
| **8.0.4** | O direito tem vigência? | **Não — é flag pura.** Linha existe = tem; some = não tem | `direito_refeicao_aluno` fica com duas colunas. "Quem revogou e quando" é auditoria, não estado (§2.3) |
| **8.0.5** | A cantina inclui pedido fora do prazo? | **Não** | Nada entra depois de `pedidos_ate` — a contagem de `fechado` é definitiva. O aluno que esquecer é resolvido no balcão, fora do sistema (§3.3) |
| **8.0.6** | Quanto o aluno enxerga à frente? | **Todos os dias com cardápio lançado** | `GET /me/cantina` devolve os publicados de hoje em diante, com teto de 30 dias; a tela lista todos, o card trata só do próximo prazo (§3.2, §4) |
| **8.0.7** | Lembrete antes do prazo? | **Não, por enquanto** | Fica registrado o preço: sem lembrete, sem exceção e sem prato padrão, quem esquece fica sem almoço e o sistema não avisou (§7) |
| **8.0.8** | Almoço e janta compartilham o cardápio? | **São diferentes** | Dois cardápios por dia, de verdade. O "copiar-de" é dia→dia dentro da mesma refeição; copiar entre refeições sai do escopo (§2.2) |
| **8.0.9** | Registrar restrição alimentar? | **Pode registrar** | `aluno.restricao_alimentar`, preenchida pela coordenação, visível só na lista de pedidos da cantina (§2.6) |
| **8.0.10** | A cantina serve só ITA/IME? | **Sim — são os únicos alunos que existem neste banco** | Nenhum cadastro paralelo de aluno, nenhuma importação extra do Canvas. A verificação está em §8.0.10.1 |

#### 8.0.10.1 · Por que "só existem essas" é verdade no código

Verificado em 05/09, e vale registrar porque é a base de um "não" caro de
reverter:

* **um único escritor cria linha em `aluno`** — `upsert_alunos_em_lote`
  ([ingest/upsert.py](../api/app/ingest/upsert.py)). Todo o resto do backend só
  faz `select` ou `update` nessa tabela;
* ele tem **dois chamadores**: o pipeline do XLSX e
  [canvas_sync/sincronizar.py](../api/app/canvas_sync/sincronizar.py);
* o sync do Canvas só enxerga cursos que casam com
  `^\d{4}\s+\d+o\s+ITA/IME\s+Simulados$`
  ([mapeador.py](../api/app/canvas_sync/mapeador.py)), e **falha** se não achar
  nenhum;
* o SSO do Canvas **não cria aluno**: ele procura por `canvas_user_id` e
  devolve `None` quando não acha ([auth_canvas.py](../api/app/routes/auth_canvas.py)).

Ou seja: quem não está matriculado no curso de simulados não tem linha, não tem
matrícula e **não consegue entrar**. Se um dia a cantina precisar servir o
colégio inteiro, isso deixa de ser uma flag e vira importação de alunos — um
sprint próprio, não um ajuste.

### 8.1 · Abertas com proposta pronta — nenhuma trava código

| # | Pergunta | Proposta |
|---|---|---|
| 8.1.1 | Uma cantina ou várias? | Entidade separada mesmo sendo uma só hoje (§2.1) |
| 8.1.2 | O que a cantina vê do aluno? | **Nome, turma e a restrição alimentar** (§8.0.9). Nada além disso: nenhum endpoint dela toca `nota`, `simulado` ou ficha (CLAUDE.md, armadilha 6) |
| 8.1.3 | Confirmação de retirada? | Fora do v1; `retirado_em` em `pedido_refeicao` cabe depois sem migration destrutiva |
| 8.1.4 | A cantina entra no rail da coordenação? | Não no v1 — entra por Administração |
| 8.1.5 | Há cobrança, ou é benefício? | **Benefício binário, sem preço.** Se um dia houver aluno pagante, entram preço, fatura e conciliação — e isso não é uma coluna, é outro produto |
| 8.1.6 | `janta` ou `jantar` no `CHECK`? | Está `'janta'`, a palavra que a coordenação usou. É `CHECK`: trocar depois custa migration |

## 9 · Tempo real — o cardápio aparecendo sem o aluno dar refresh

Resposta curta: **é mais fácil neste projeto do que costuma ser** — o caminho de
SSE já está aberto de ponta a ponta — mas as duas camadas mais baratas
provavelmente já entregam o que se quer, e o empurrão de verdade cobra um preço
novo.

### 9.1 · O que já existe (verificado)

| Peça | Onde | Estado |
|---|---|---|
| nginx pronto para streaming | [infra/vps/nginx.conf](../infra/vps/nginx.conf), `location /api/` | ✅ `proxy_buffering off`, `proxy_cache off`, `chunked_transfer_encoding on`, `proxy_read_timeout 300s` — posto ali para o chat |
| SSE no servidor | [api/app/chat/rotas.py](../api/app/chat/rotas.py) | ✅ `StreamingResponse(media_type="text/event-stream")` + `X-Accel-Buffering: no` |
| Parser de SSE no cliente | [web/src/servicos/http.ts](../web/src/servicos/http.ts) | ✅ sobre `fetch` + `ReadableStream`, **porque `EventSource` não manda `Authorization`** — que é justamente a pedra em que esse tipo de feature tropeça |
| Um processo só | [infra/vps/.env.example](../infra/vps/.env.example) | ✅ `UVICORN_WORKERS=1`, com "NÃO aumente" escrito ao lado |

O último item é o que mais barateia: com **um** processo, o fan-out é um
`dict[aluno_id, asyncio.Queue]` em memória. Não precisa de `LISTEN/NOTIFY`, e
portanto não precisa colocar `psycopg` nas rotas — coisa que hoje só o runner de
migrations tem (CLAUDE.md).

### 9.2 · As três camadas, do mais barato ao mais caro

**Camada 0 · uma linha.** `refetchOnWindowFocus: true` no hook da cantina — hoje
é `false` para o app inteiro ([main.tsx](../web/src/main.tsx)), e a justificativa
escrita lá ("os dados do SAS só mudam quando entra planilha nova") **deixa de
valer para esta tela**: aqui muda porque outra pessoa publicou. Cobre o caso
real, que é o aluno **voltar** ao app — não ficar olhando.

**Camada 1 · ~10 linhas.** `refetchInterval` que se autodesliga, no padrão já
usado por `usePainelGravacoes` ([consultas.ts](../web/src/hooks/consultas.ts)):
revalida a cada 60 s **enquanto** a tela da cantina está aberta e existe prazo
aberto; devolve `false` fora disso. Latência ≤ 60 s. Custo desprezível — só
quem tem direito e está com a tela aberta consulta.

**Camada 2 · SSE, ~meio dia.** `GET /me/cantina/stream`, e o `publicar` empurra
`{tipo: "cardapio_publicado", data, refeicao}` para as filas dos alunos com
direito àquela refeição. Latência < 1 s. Três custos que **não** existem hoje:

1. **heartbeat a cada ~30 s** (`: ping`), senão o `proxy_read_timeout 300s`
   derruba a conexão em silêncio — o chat nunca esbarra nisso porque a resposta
   dele streama sem parar do início ao fim;
2. **reconexão com backoff no cliente.** O `streamSSE` de hoje é one-shot: o
   chat pede uma resposta e acaba. Um stream que fica aberto por horas precisa
   voltar sozinho depois de túnel, wi-fi trocado e tela bloqueada;
3. **uma conexão aberta por aluno com o app aberto.** É uma classe de recurso
   que esta API nunca teve.

⚠️ E cria uma **armadilha nova**: o fan-out em memória depende de
`UVICORN_WORKERS=1`. Se alguém subir os workers, cada processo passa a ter as
suas filas e **metade dos alunos para de receber evento, sem erro nenhum** —
exatamente o tipo de falha silenciosa que a lista de armadilhas do CLAUDE.md
existe para prevenir. Se a Camada 2 entrar, essa linha entra junto.

### 9.3 · Recomendação

**Camadas 0 e 1 no v1; SSE só se a leitura na tela pedir.** O cardápio é
publicado horas ou um dia antes do prazo — ninguém está com a tela aberta no
segundo da publicação, e a diferença entre 60 s e 1 s é invisível para o aluno
que abriu o app agora. O que ele percebe é abrir e ver o cardápio de hoje, e
isso a Camada 0 já dá.

O que faz o SSE valer a pena não é a publicação: é **`disponivel = false`** —
acabou o frango às 11h40, com o prazo ainda aberto. Aí um minuto de atraso vira
aluno pedindo o que não existe. Se esse caso acontecer na prática, é o gatilho
para subir a camada.

## 10 · O que foi verificado, e o que não foi

### 10.1 · Verificado

| O quê | Como |
|---|---|
| As regras puras do servidor | `api/tests/test_cantina.py` — 27 testes: os cinco estados, o prazo no fuso da escola, o teto e o mínimo por bloco, opção indisponível, opção de outro cardápio, escolha repetida |
| **Os cinco guards de segurança** | No mesmo arquivo, e são irmãos de `test_auth_chat.py`: a cantina não passa por coordenação, aluno nem administrador; `papel_da_sessao` a ignora; a coordenação não passa pelo guard dela; token sem `cantina_id` é recusado; **`foto_perfil._entidade_do_usuario` levanta em vez de devolver a entidade de coordenação** |
| As regras puras do cliente | `web/src/dominio/cantina.test.ts` — 23 testes: a data que não escorrega um dia, as quatro escalas do prazo, a pendência do pedido, o ida-e-volta do `datetime-local`, a grade do mês |
| O fluxo inteiro contra a API real | Smoke de 37 passos no compose: administrador cria cantina e conta → cantina entra pela porta de verdade → lança, publica e copia (com o prazo **recalculado**, não copiado) → aluno sem direito não vê nada → com direito pede, erra o teto, troca → a cantina lê a contagem agregada e a lista do balcão → os cinco 403 de fronteira |
| As três migrations | Aplicadas no compose com `migrate up` + `restart postgrest`. As duas views respondem pelo PostgREST, e a contagem devolve **0 para opção sem pedido** em vez de omiti-la |
| Os portões | `pytest` 530 ✓, `ruff` ✓, `npm test` 392 ✓, `npm run lint` ✓, `tsc --noEmit` ✓, `npm run build` ✓, `npm run inventario` regenerou o docs/30 |

### 10.2 · **NÃO** verificado — e é a mesma lacuna do §6 do docs/37

⚠️ **Nada disto foi aberto no browser.** O MCP `chrome` não conseguiu anexar —
havia uma instância do Chrome segurando o perfil `chrome-devtools-mcp` —, e o
CLAUDE.md do `web/` é explícito: *"para qualquer afirmação sobre usabilidade,
layout ou desempenho, use ele — não deduza da leitura do TSX."* Então o que
segue é lista de tarefas, não de dúvidas:

* a grade do calendário nos cinco estados, e se os dois cartões de refeição
  cabem numa casa de 118px sem quebrar em 7 colunas;
* o editor a 360px — é a largura em que a faixa de filtros da coordenação já
  quebrou quatro vezes (docs/33);
* o card em Hoje nos quatro estados, e se o prazo em 30px convive com a missão
  logo acima sem competir com ela;
* o casco da cantina no tema escuro: ele usa `--color-*`, que têm os três
  blocos de tema, mas isso é dedução da pilha de cor, não observação;
* o alvo de 44px nas pílulas de opção do aluno, que é onde a escolha realmente
  acontece — no celular, andando.

### 10.3 · Fora do escopo desta entrega

O **deploy**. `./infra/vps/deploy.sh --migrar` aplica as três migrations em
produção; ⚠️ e o `restart postgrest` **não é opcional** — sem ele as sete
tabelas novas voltam 404 e o 404 parece bug de código (CLAUDE.md, armadilha 1).
Antes disso, a coordenação precisa criar a cantina e a primeira conta por
`/administracao/cantina`, porque **não há seed**: cantina que nasce sozinha é
conta de acesso que ninguém pediu.
