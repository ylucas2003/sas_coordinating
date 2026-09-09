# 40 — A cantina depois do v1 · quatro fases

> ⚠️ **O nome do arquivo diz "retirada presencial" e o documento já não é só
> isso.** Nasceu com as três fases do QR Code; em 09/09 ganhou uma fase de
> desempenho e de ajustes de uso que não têm nada a ver com retirada. O arquivo
> não foi renomeado porque comentários no código apontam para `docs/40` com
> número de seção — renomear é trabalho de outra rodada, e o título aqui vale
> mais que o nome do arquivo.
>
> | Fase | O quê | Estado |
> |---|---|---|
> | **1** | Retirada presencial por QR Code | **✅ em produção** (§1 a §11) |
> | **2** | Desempenho e os ajustes de uso — doze frentes | **Planejada** (§12) |
> | **3** | Janela de horário para a leitura, com liberação avulsa | Planejada (§13) |
> | **4** | Reconhecimento facial antes de gerar o QR | Planejada (§14) |
>
> As fases são independentes no schema: cada uma acrescenta, nenhuma reescreve
> o que a anterior fez. **A 2 é a única que mexe fora da cantina** — a causa
> medida da lentidão está no chat e nos insights da coordenação (§12.1.1).

## 0 · Em uma frase

Hoje há dois jeitos de comer: pedir com antecedência, dentro do prazo
([docs/38](38-plano-cantina.md)), ou **chegar, mostrar um QR Code gerado na
hora, e a cantina lê** — a fase 1, no ar desde 07/09, com cada cantina
decidindo quais dos dois jeitos valem para cada refeição. A fase 2 não
acrescenta jeito nenhum: faz os dois que existem serem usáveis sem atrito.

---

# FASE 1 — a retirada presencial

## 1 · O que muda no modelo

**Nenhuma tabela nova.** `pedido_refeicao` já é o registro de "este aluno vai
comer este cardápio" (`UNIQUE(cardapio_id, aluno_id)`, docs/38 §2.3) — é
exatamente a trava que impede um aluno de contar duas vezes, então a retirada
presencial reaproveita a mesma linha em vez de abrir uma tabela paralela que
teria de reimplementar essa mesma trava.

```sql
-- migration 0051

ALTER TABLE pedido_refeicao
    ADD COLUMN modo text NOT NULL DEFAULT 'pedido'
        CHECK (modo IN ('pedido', 'presencial')),
    ADD COLUMN retirado_em timestamptz;
-- `retirado_em` é o campo que o docs/38 §8.1.3 já previa ("cabe depois sem
-- migration destrutiva"), só que generalizado: não é só "confirmar que
-- retirou o que pediu", é a PRÓPRIA conclusão do pedido presencial.
-- NULO = ainda não passou pela leitura do QR. Modo 'pedido' nunca tem
-- `retirado_em` preenchido no v1 — confirmar a retirada de quem PEDIU
-- continua fora de escopo (§15).

ALTER TABLE cantina
    ADD COLUMN aceita_pedido_almoco     boolean NOT NULL DEFAULT true,
    ADD COLUMN aceita_pedido_janta      boolean NOT NULL DEFAULT true,
    ADD COLUMN aceita_presencial_almoco boolean NOT NULL DEFAULT false,
    ADD COLUMN aceita_presencial_janta  boolean NOT NULL DEFAULT false;
-- A REGRA da casa — mesmo papel que `prazo_padrao_*` já tem: pré-preenche o
-- cardápio novo, e a cantina pode divergir dia a dia. O default mantém o
-- comportamento de hoje (só pedido) para toda cantina que já existe.

ALTER TABLE cardapio
    ADD COLUMN aceita_pedido     boolean NOT NULL DEFAULT true,
    ADD COLUMN aceita_presencial boolean NOT NULL DEFAULT false;
-- O valor absoluto do dia, como `pedidos_ate` já é. Publicar com os dois em
-- `false` é recusado (422) — um cardápio que não aceita nada não é
-- "publicado", é `sem_refeicao` disfarçado.
```

Se um terceiro modo aparecer um dia, estas quatro colunas em `cantina` viram
uma tabela — o mesmo raciocínio que os blocos de cardápio já usam (docs/38
§2.2). Por ora são duas refeições × dois modos: colunas bastam.

### 1.1 · A migration 0052 veio depois, e o motivo é uma ambiguidade que a 0051 criou

Reaproveitar `pedido_refeicao` tem um efeito que só apareceu com a feature no
ar: `v_pedidos_por_cardapio` conta **linhas**, e uma retirada presencial é uma
linha. O número do calendário passou a somar as duas portas, enquanto a
contagem por opção ("o que cozinhar") continua somando só quem escolheu prato.
Os dois números parecem que deviam bater, não batem — e isso vira chamado de
bug, não pergunta.

A **0052** quebra a view em `quantos` / `com_pedido` / `presenciais`.
⚠️ `quantos` **não mudou de significado** ("quantos vão comer") e a API segue
expondo `pedidos` com o mesmo sentido de sempre: as duas colunas novas são
acréscimo, e a tela só mostra a quebra quando existe presencial — um dia sem
nenhum continua exatamente como era.

⚠️ **Foi ela que consumiu o número 0052**, que este documento reservava para a
fase seguinte. Com a fase 2 levando três migrations — a **0053** (a observação
do bloco, §12.5.4), a **0054** (o valor carimbado no pedido, §12.11.2) e a
**0055** (a trava de um pedido por dia, §12.12.2) —, a Fase 3 é a **0056**
(§13.3) e a Fase 4 é a **0057** (§14.5).
Reintroduzir a colisão é pior do que parece: o runner usa o prefixo de quatro
dígitos como chave em `_migracoes_aplicadas`, então um arquivo novo com número
já aplicado é reportado como **"✓ aplicada"** sem nunca ter rodado — o portão
do `deploy.sh` deixa passar, as tabelas não nascem, e as rotas voltam 404, que
é o sintoma da armadilha 1 do CLAUDE.md e vai ser lido como bug de código.

## 2 · A máquina de estados por (cardápio, aluno)

Antes desta feature havia dois estados: sem linha, ou linha com itens. Agora
são quatro, e a transição entre eles é a regra mais importante do desenho —
**é assimétrica**, porque um `pedido` compromete a cozinha com um prato
específico e uma retirada presencial não compromete nada até o QR ser lido.

```
        (nenhuma linha)
         /            \
   PUT pedidos     POST retiradas
        |                |
        v                v
  modo=pedido      modo=presencial, retirado_em=NULL
   [FINAL]           /              \
                 PUT pedidos      POST confirmar (a cantina lê o QR)
                (vira pedido)             |
                      |                   v
                      v            modo=presencial, retirado_em=agora()
                modo=pedido                [FINAL]
                 [FINAL]
```

* **`modo=pedido` é porta sem volta.** Depois do primeiro `PUT
  /me/cantina/pedidos/{id}`, o aluno **continua podendo trocar os itens** até
  o prazo — isso não muda em nada (docs/38 §3.2) — mas não pode mais virar
  presencial naquele cardápio. Ver §11.2: essa leitura ("trava o modo, não o
  conteúdo") é interpretação minha e vale confirmar.
* **`modo=presencial` sem `retirado_em` é reversível.** Gerar o QR não
  compromete nada: o aluno pode gerar de novo, ou desistir e virar `pedido` —
  o `PUT` de pedido, chamado sobre uma linha presencial ainda não lida,
  sobrescreve modo e itens. É o cenário da conversa: gerou às 7h, ninguém leu,
  ele muda de ideia às 11h e pede.
* **`retirado_em` preenchido é final dos dois lados.** O aluno já comeu; não
  há desfazer.

Duas recusas do servidor decorrem disso, e nenhuma validação de tela substitui:

* **`POST /me/cantina/retiradas/{cardapio_id}`** → **409** se já existe
  `modo=pedido` ("Você já fez o pedido — não dá para trocar para retirada
  presencial.");
* **`PUT /me/cantina/pedidos/{cardapio_id}`** → **409**, novo, se a linha já
  tem `retirado_em` ("Esta refeição já foi retirada.").

## 3 · Rotas novas

Todas em [api/app/routes/cantina.py](../api/app/routes/cantina.py), nos routers
que já existem.

| Rota | Guard | O quê |
|---|---|---|
| `POST /me/cantina/retiradas/{cardapio_id}` | `get_current_aluno` | Cria (ou renova) a linha `presencial`; devolve `{token, expiraEm}` |
| `DELETE /me/cantina/retiradas/{cardapio_id}` | `get_current_aluno` | Desiste — apaga a linha, só se `retirado_em IS NULL` |
| `POST /cantina/retiradas/confirmar` | `get_current_cantina` | Body `{token}`. A leitura do QR — §4 |

O `POST` do aluno passa pelas mesmas verificações que `_cardapio_aberto_para`
já faz (cardápio publicado, não `sem_refeicao`, aluno tem direito à refeição —
docs/38 §3.2), **exceto a do prazo**: presencial não olha `pedidos_ate`, é
justamente o caminho de quem não se planejou. Duas recusas próprias:

* **422** se `cardapio.aceita_presencial = false`;
* **422** se `data != hoje` no fuso da escola (§11.1).

`PUT /me/cantina/pedidos/{cardapio_id}` ganha só a recusa do `retirado_em`.
Fora isso não muda: continua idempotente, continua validando escolhas por
bloco.

## 4 · O token e a leitura atômica

O QR carrega um **token assinado**, não o `aluno_id` cru — um print de tela não
pode virar crachá reutilizável por outra pessoa nem sobreviver ao dia.
Conteúdo: `{pedido_id, cardapio_id, aluno_id, exp, uso: "retirada"}`, HS256 com
a mesma chave de sessão ([api/app/auth.py](../api/app/auth.py)), expiração
curta (**2 minutos**), e a tela do aluno renova sozinha enquanto o QR estiver
visível. O claim `uso` existe porque um token sem propósito declarado é a
mesma classe de furo do docs/38 §1.1 — token de download virando sessão.

Não precisa de tabela de tokens nem de rotina de limpeza: quem invalida o token
velho é a condição da própria leitura. `POST /cantina/retiradas/confirmar`:

1. Verifica assinatura, `uso` e `exp` — **422** se inválido ou vencido ("Peça
   para o aluno atualizar a tela.").
2. Confere que `cardapio.cantina_id` bate com a cantina do token de sessão —
   **403** se for de outra cantina.
3. Faz o UPDATE **condicional** — nunca ler-depois-escrever, que abriria
   corrida entre duas leituras simultâneas do mesmo QR:
   ```python
   cliente.table("pedido_refeicao") \
       .update({"retirado_em": _agora().isoformat()}) \
       .eq("id", pedido_id) \
       .eq("modo", "presencial") \
       .is_("retirado_em", "null") \
       .execute()
   ```
   Zero linhas afetadas = **409** "Já retirado" — e cobre de graça o caso de o
   aluno ter virado `pedido` nesse meio-tempo, porque aí `modo="presencial"`
   também não bate. Uma linha = sucesso, e a resposta carrega nome, turma,
   refeição e restrição alimentar: a mesma régua de dado que a cantina já tem
   hoje, nada além (docs/38 §8.1.2).

É a mesma classe de solução que o resto do backend usa — PostgREST sem SQL cru,
`WHERE` como trava de corrida. Não introduz `psycopg` nas rotas nem lock
explícito.

## 5 · Tempo real

Sem mexer no formato do barramento
([api/app/cantina_eventos.py](../api/app/cantina_eventos.py)): a confirmação
publica `Evento(tipo="retirada", cantina_id, refeicao, data, aluno_id)`.
`para_o_aluno` já casa por `aluno_id` sem alteração nenhuma — o filtro de
privacidade existente cobre o caso novo de graça; `para_a_cantina` idem, para o
placar da tela "Ler código" em outra sessão da mesma cantina.

O evento não carrega o "Bom almoço" pronto: carrega o aviso de refazer
`GET /me/cantina`, e a tela decide o texto olhando `retiradoEm`. Regra de
sempre — o stream avisa, quem decide é a rota normal (docs/38 §9.3).

## 6 · Front do aluno

Onde hoje só existe "Escolher" (`BlocoDaCantina`/`DiaDaCantina`, docs/38 §4):
quando o cardápio aceita os dois modos, duas ações lado a lado — **"Fazer
pedido"** e **"Pegar pessoalmente"**; quando aceita só um, aparece só ele, sem
escolha para fazer. A tela do QR:

* QR grande, com o rótulo da refeição e do dia, renovado silenciosamente antes
  de expirar;
* link discreto "Prefiro fazer o pedido", que some quando o `modo` já não for
  `presencial`;
* quando `retiradoEm` chega (SSE + refetch), vira confirmação — **"Bom
  almoço!"** / **"Boa janta!"**, sem XP e sem cor de alerta, mesma régua do
  resto da área do aluno (docs/38 §4).

## 7 · Front da cantina — "Ler código"

Item novo no nav do casco
([CascoCantina.tsx](../web/src/telas/Cantina/CascoCantina.tsx)), não dentro do
fluxo por dia — é tela que fica aberta o serviço inteiro, com a câmera ligada.
Cada leitura:

* **sucesso** → ficha rápida: nome, turma, refeição e a restrição alimentar
  **em destaque** se houver; volta a escanear sozinha, sem exigir toque;
* **já retirado** → mostra a hora da retirada original; não é erro, na maioria
  das vezes é segunda passagem por engano;
* **token inválido ou vencido** → pede para o aluno atualizar a tela;
* **refeição trocada** (QR de janta lido no almoço) → mostra a refeição do
  token com destaque. Não é bloqueado no servidor — o token é válido —, é
  sinalizado para quem está lendo.

`CardapioDoDia.tsx` (o editor) ganha os dois toggles `aceita_pedido` /
`aceita_presencial`, com a mesma trava de "não publica com os dois desligados"
espelhada do servidor. `PedidosDoDia` ganha uma linha à parte para o presencial
— pendentes e retirados —, porque presencial não tem prato para contar (§10.1)
e misturar com a contagem por opção esconderia o dado.

## 8 · Front da coordenação

Nas quatro telas de leitura (docs/38 §6,
[NaCoordenacao.tsx](../web/src/telas/Cantina/NaCoordenacao.tsx)): a lista ganha
a marca de modo — **"retirada na hora"** / **"retirada na hora · retirado"**.
Não é dado sensível como a restrição alimentar (é rótulo de fluxo), então
aparece igual para administrador e coordenador comum.

⚠️ **E a lista deixou de se chamar "quem pediu".** Ela é mista desde esta fase,
e num dia em que a cantina liga só a retirada na hora o título afirmaria
"pediu" sobre fichas todas carimbadas com o contrário. O par
`rotuloDaContagem`/`contagemPorModo` resolve isso em toda superfície: "N
pedidos" quando só há pedido, "N vão comer" quando há os dois.

⚠️ **Vocabulário: há dois, e é de propósito.** Cantina e coordenação dizem
**"retirada na hora"**; a área do aluno diz **"pegar pessoalmente"**. Não é
descuido — quem lê a tela do aluno tem 16 anos e não trabalha na copa. O que é
defeito é as duas palavras aparecerem no MESMO cartão, e foi assim que a
primeira escrita saiu.

## 9 · Plano de implementação da Fase 1

Sete passos, na ordem. Cada um tem entregável verificável — a ordem existe para
o passo de segurança ser revisável sozinho, como no docs/38 §7.

**Passo 1 · Migration 0051 + par `.down.sql`.** ⚠️ `docker compose restart
postgrest` depois de aplicar, senão tudo volta 404 (CLAUDE.md, armadilha 1).

**Passo 2 · O token, isolado.** Assinar e verificar em módulo próprio, com
teste antes de qualquer rota: válido, expirado, assinatura trocada, campo
faltando, token de outro propósito.

**Passo 3 · As três rotas novas + a recusa nova no `PUT`.** A máquina de
estados do §2 inteira, incluindo o UPDATE condicional do §4. *Entregável:
`pytest` cobrindo cada transição permitida e cada proibida — inclusive duas
confirmações simultâneas do mesmo token, em que a segunda tem de dar 409.*

**Passo 4 · Os flags de modo nas leituras.** `GET /me/cantina`,
`GET /cantina/cardapios/{id}`, o `PUT` do editor, `publicar` recusando os dois
desligados, contagem com o bloco de presencial. *Entregável: smoke ponta a
ponta no compose, no formato do docs/38 §10.1.*

**Passo 5 · Front do aluno.** Escolha de modo, tela do QR com renovação,
confirmação "Bom almoço", estados novos em `dominio/cantina.ts` com teste ao
lado. Biblioteca de **geração** de QR entra aqui — npm, no bundle, nunca CDN
(CLAUDE.md, armadilha 7).

**Passo 6 · Front da cantina.** Toggles no editor, "Ler código" com
câmera, linha de presencial na contagem. Biblioteca de **leitura** de QR entra
aqui. ⚠️ Câmera exige HTTPS ou `localhost` — IP na rede local não serve.

**Passo 7 · Front da coordenação + portões.** Marca de modo nas listas, e
então `pytest`, `ruff`, `npm test`, `npm run lint`, `tsc --noEmit`,
`npm run build`, `npm run inventario`. ⚠️ E **o browser** — é a lacuna que
docs/38 §10.2 e docs/37 §6 deixaram aberta duas vezes, e aqui é pior: câmera e
QR não têm como ser deduzidos do TSX.

**Fora deste plano, de propósito**: o deploy. Precisa de
`./infra/vps/deploy.sh --migrar`, do `restart postgrest`, e de a cantina ligar
o modo presencial em pelo menos uma refeição — senão nada aparece e parece bug
(a quarta variação do "publiquei e ninguém vê" do docs/38 §3.3.2).

## 10 · Decisões fechadas em 07/09

| # | Pergunta | Resposta |
|---|---|---|
| 10.1 | Presencial escolhe itens (blocos/opções)? | **Não.** É declaração de presença, sem prato — a contagem por opção nunca inclui presencial |
| 10.2 | Presencial tem prazo (janela de horário)? | **Não na fase 1.** Vale enquanto o cardápio estiver publicado. A janela é a fase 3 (§13) |
| 10.3 | Dá para trocar de modo depois de escolher? | **Assimétrico.** `pedido` é final assim que enviado; `presencial` é reversível até o QR ser lido |

## 11 · Em aberto na fase 1

### 11.1 · Presencial só vale para o cardápio de hoje

Implementado assim: 422 se `cardapio.data != hoje`. O QR é para ser lido na
hora; gerar um para daqui a três dias não avisa a cozinha de nada real e polui
a lista de pendentes. Se um dia a resposta virar "qualquer dia publicado",
basta remover a checagem.

### 11.2 · "Pedido final" também congela os itens?

Li a decisão 10.3 como **trava de modo, não de conteúdo**: o aluno continua
trocando arroz por batata até o prazo, como já funciona hoje. Se a intenção era
mais restritiva, isso *remove* uma capacidade que está em produção — melhor
dizer antes de mexer no `PUT`.

---

# FASE 2 — o que falta para a cantina ser usada sem atrito

> Doze frentes, decididas em 09/09. Onze são de uso do dia a dia — nome,
> exportação, lista, recorte por cantina, senha, um destino novo no casco, o QR
> que gira, o tema claro por padrão o relatório de custos e a segunda cantina —, e **uma é de
> desempenho**, que é a que faz as outras onze parecerem piores do que são.
>
> ⚠️ **A frente de desempenho sai da cantina.** A causa medida está no chat e
> nos insights da coordenação, que congelam a API inteira; e no hub da cantina,
> que baixa 9,31 MB de notas para escrever uma linha de resumo. Está nesta fase
> porque é o que trava a cantina — não porque é código de cantina.
>
> Esta fase **não tem nada a ver com retirada presencial**, e é a razão de o
> documento ter deixado de se chamar só por ela (§0).

## 12.0 · Como esta fase foi levantada

Nada aqui saiu de leitura de código: cada número abaixo foi medido em **09/09**
contra o compose local (1.409 alunos, 78.107 notas) e conferido contra o
tamanho real da produção (2.050 alunos). Onde o número for de laboratório e não
de produção, está dito.

O pedido original tinha uma frase — *"o site está demorando, tanto para o
coordenador como para a cantina"* —, e a medição achou **quatro causas
independentes**, nenhuma delas na cantina. É por isso que a F1 vem primeiro no
plano de implementação: as outras seis são melhorias de tela, e melhoria de
tela em cima de API congelada não se percebe.

## 12.1 · F1 · Desempenho

### 12.1.1 · A API tem uma thread só, e a chamada de LLM a segura inteira

Três fatos que, isolados, são escolhas legítimas, e juntos são o defeito:

| Fato | Onde | Consequência |
|---|---|---|
| `UVICORN_WORKERS=1` | [infra/vps/.env.example](../infra/vps/.env.example) | Um processo, um event loop. Invariante declarada, com **três** motivos (travas do sync, despachante, barramento SSE da cantina) — não pode subir |
| Os handlers são `async def` e o cliente de dados é **síncrono** | `get_supabase()` devolve `SyncPostgrestClient`; zero `run_in_threadpool` no backend inteiro | Toda ida ao PostgREST bloqueia o loop. ~4 ms cada no compose — tolerável sozinho |
| O cliente da OpenAI é o **síncrono**, dentro de `async def` | [chat/agente.py:135](../api/app/chat/agente.py), `gerar_titulo` (:238), [stats/insight_aluno.py:108](../api/app/stats/insight_aluno.py), [stats/insights.py:191](../api/app/stats/insights.py) | **A API inteira para** durante a chamada. O nginx reserva 300 s para uma volta de tool calling do chat |

O pior caso não é o chat: é [ciclos.py:583-627](../api/app/routes/ciclos.py), que com
`insights=true` faz **quatro chamadas de LLM em série** numa requisição só.

⚠️ **É esta a única causa que explica os dois lados lentos ao mesmo tempo.** O
coordenador abre o assistente; o balcão, que só quer ver quem chegou, entra na
mesma fila e não tem como saber por quê. Não há erro, não há log: a tela
demora.

**O conserto:** `await asyncio.to_thread(...)` nas cinco chamadas. Uma linha
cada, o resto do módulo intacto, e o loop volta a atender enquanto o modelo
pensa. Não é paralelismo — é tirar do caminho.

Por que não trocar para `AsyncOpenAI` agora: é o conserto certo a prazo, e
custa mais que uma linha por chamada porque muda a forma dos três módulos. Fica
registrado no §12.9 junto com o irmão dele — o **streaming do chat é falso**
hoje: a resposta chega inteira e [agente.py:209](../api/app/chat/agente.py) a
pica em pedaços de 40 caracteres para parecer que digita.

### 12.1.2 · O hub da cantina baixa 9,31 MB de notas para escrever uma linha

O card "Alunos com direito" mostra `3 de 2050 alunos · 3 almoço · 3 janta`.
Para montar essa frase, [useResumoDosDireitos](../web/src/telas/Cantina/NaCoordenacao.tsx)
chama `useAlunos()` → `GET /alunos` → [listar_alunos](../api/app/routes/alunos.py),
que é a leitura mais cara do produto: turmas, sedes, classificações,
vestibulares, sparklines, simulados, **todas as notas** e direitos.

Medido no compose, só a chamada de `nota`:

```
GET /nota?select=aluno_id,simulado_id,pontuacao
  → 78.107 linhas · 9,31 MB · 267 ms de rede + 25 ms de parse
```

E os 267 ms são de loop **bloqueado** (§12.1.1), somando-se à fila de todo
mundo. Em produção são 2.050 alunos, não 1.409.

⚠️ O comentário que já está no hook explica por que ele **não** usa
`useDireitos()`: aquele traz a restrição alimentar junto, e é dado de saúde de
menor. A regra continua valendo — a rota nova devolve **contagem, não lista**.

**O conserto:** `GET /administracao/cantina/resumo`, que responde os três
números por contagem no banco, e o hub para de chamar `/alunos`.

⚠️ Isto **não conserta `listar_alunos`** — só tira o hub de cima dela. A tela
`/alunos` continua baixando tudo, e isso é a armadilha 2 do CLAUDE.md (não
existe paginação em lugar nenhum) esperando a vez dela. Fica no §12.9.

### 12.1.3 · Um N+1 de verdade, e uma contagem feita duas vezes

[cantina_do_aluno](../api/app/routes/cantina.py) chama `_montar_cardapio`
**dentro do `for`** — uma ida ao PostgREST por cardápio. Uma semana lançada com
almoço e janta são ~10 idas em série, e essa rota tem `refetchInterval` de 60 s
por aluno com direito.

`cardapio_para_a_coordenacao` faz ~9 idas, e `_contagem` roda **duas vezes** na
mesma requisição: uma direta, outra dentro de `_pedidos_do_cardapio` só para
descobrir o nome das opções.

**O conserto:** blocos e opções de todos os cardápios numa consulta só
(`in_("cardapio_id", ids)`), agrupados em memória; e o resultado de `_contagem`
passado adiante em vez de recalculado.

### 12.1.4 · O front inteiro cabe num arquivo, e ele desce em toda rota

Não existe um `lazy()` no projeto; [App.tsx](../web/src/App.tsx) importa as 29
telas estaticamente e [main.tsx](../web/src/main.tsx) importa as ~35 folhas de
CSS de todas elas. Medido no `dist` de 07/09:

| Asset | Bruto | Gzip | Quem precisa |
|---|---|---|---|
| `index.js` | 1,0 MB | **306 KB** | tudo junto: os três cascos e o banco de questões |
| `katex.js` (+ 19 fontes) | 256 KB | 75 KB | só `/banco` e as resoluções — mas tem `modulepreload`, então desce sempre |
| `index.css` | 252 KB | 40 KB | render-blocking, com as folhas de todas as telas |

São ~420 KB de JS+CSS antes do primeiro pixel, **iguais em `/login-cantina` no
celular do balcão e no `/painel` do coordenador**.

**O conserto:** `lazy()` por casco (coordenação, aluno, cantina) e por tela
pesada (`/banco` com o KaTeX, o chat, `/ao-vivo` com o jsQR).

⚠️ **O CSS é a parte delicada, não o JS.** A ordem dos imports de `main.tsx` é
regra, não estilo: `paleta` → `papeis` → `forma` → `base`, e `documento.css`
**por último** porque o `@media print` dele remapeia a paleta inteira e blocos
`:root` de mesma especificidade são decididos por ordem. Dividir exige manter
essa ordem dentro de cada pedaço; o que é global (tokens, base, campo, filtros,
procedência, casco) fica na entrada, e só as folhas de tela viajam.

⚠️ E cada fronteira de `Suspense` precisa de um fallback que **não pisque**: o
casco já desenhado com o miolo em esqueleto, nunca tela branca. Piscar é a
forma mais fácil de trocar 300 KB por uma impressão de lentidão maior.

### 12.1.5 · Como se mede

Em **produção, logado**, com o MCP `chrome`: Lighthouse e trace em três rotas —
`/login-cantina`, `/cantina` (coordenação) e `/cardapios` (cantina) —, em
1440×900 e em 390×844 com rede throttlada. E, do lado do servidor, o tempo de
resposta de `GET /alunos`, `GET /me/cantina` e `GET /administracao/cantina/cardapios/{id}`.

| | Antes | Depois | Onde |
|---|---|---|---|
| JS+CSS na entrada (gzip) | **421 KB** | **130 KB** | build |
| O que o balcão baixa em `/login-cantina` | 421 KB | 130 KB + 5 KB do casco | browser |
| KaTeX na entrada | 75 KB, em toda rota | 0 — só em `/banco` e no chat | build |
| Requisições em `/login-cantina` | — | 4 (documento, JS, CSS, fonte) | browser |
| Idas ao PostgREST em `GET /me/cantina`, semana lançada | 1 + 2×N cardápios | 4, fixas | teste |
| A view de contagem por requisição da ficha | 2× | 1× | teste |
| O que o hub da cantina baixa para o card de direitos | 9,31 MB (78.107 notas) | 0 byte de corpo (contagem no header) | medido |
| Requisição comum com um LLM de 300 ms em curso | 0 batidas | ≥ 10 batidas | teste |
| LCP `/login-cantina` (390px, 4G) | | | ⏳ produção |
| LCP `/cantina` coordenação | | | ⏳ produção |

As linhas de produção continuam vazias: o passo 1 depende de acesso logado a
`portalsas.online`. Tudo o mais foi medido — no build, no browser local contra o
`dist` de verdade, ou por teste que falha se o número voltar.

### 12.1.6 · O browser, com sessão de verdade *(09/09)*

Verificado no compose, logado nos DOIS cascos — a conta `dev@local`
(administrador) e a conta da cantina, esta última com a senha trocada **pela
rota nova**, que é como a F7 acabou testada de ponta a ponta: o servidor
recusou `cantina123` com "precisa de pelo menos 12 caracteres" e aceitou a
definida.

| O quê | Resultado |
|---|---|
| Hub com quatro cards, nomes novos e o gesto de exportar | ✅ e o gatilho é **irmão** do link na árvore de acessibilidade, não filho |
| Tema claro por padrão | ✅ com `localStorage` limpo. Com `sas_tema: noite` gravado, o escuro vence — que é a regra |
| Tela de custos, os quatro recortes, as barras e o XLSX | ✅ |
| Lista de trabalho e o diálogo do aluno | ✅ |
| "Visualizar pedidos" com dia e refeição pré-preenchidos | ✅ |
| Casco da cantina com três destinos | ✅ os rótulos quebram em duas linhas em 390px — cabe, e confirma que três é o teto |
| Transbordo em 390×844 nas cinco rotas de cantina da coordenação | ✅ **0** em todas |
| Console | ✅ nenhum erro em toda a sessão |

⚠️ **Quatro defeitos saíram daí, e nenhum deles apareceria em portão nenhum:**

1. **A lista era impossível de abrir.** `.cant-lista__abrir` tinha
   `display: contents`, que tira a CAIXA do elemento: o botão continuava na
   árvore de acessibilidade, sem área para receber clique. HTML certo, tipos
   certos, teste passando, tela quebrada;
2. **"1 refeições"** no card de custos — a tela de custos acertava o singular,
   o card não;
3. **A migalha de `/cantina/custos` dizia "Cantina › Cardápios › Custos"**, um
   caminho que não existe: toda rota nova sob `/cantina` precisa entrar no mapa
   de `migalhas.tsx`, ou passa a afirmar que está dentro do calendário;
4. **As telas de destino ainda tinham os nomes antigos** ("Quem come aqui?",
   "Quem lança o cardápio?") enquanto os cards que levam até elas já diziam os
   novos. Foi a renomeação da §12.2 que criou a incoerência.

⚠️ **O que continua NÃO verificado:** as telas do ALUNO — o card em Hoje, a
tela do cardápio e, principalmente, **o QR girando**. O aluno entra só pelo SSO
do Canvas, que exige a Developer Key e não existe no compose. A rotação está
coberta por 25 testes (15 no servidor, 10 no cliente), mas ninguém a viu girar.

A última linha é a que prova o §12.1.1, e hoje ela não tem número porque
ninguém mediu — é também o teste do passo 2 (§12.7).

## 12.2 · F2 · Os cards do hub deixam de perguntar

O `titulo` de [CartaoDeCampo](../web/src/componentes/ui/Campo.tsx) é sempre uma
pergunta ("O que foi lançado?"). No hub da cantina ele passa a ser **nome**, na
mesma fonte branca grande:

| Etiqueta | Nome | Rota |
|---|---|---|
| Cardápios | **Cardápios lançados** | `/cantina/cardapios` |
| Direitos | **Alunos com direito** | `/cantina/direitos` |
| Acesso | **Administrar cantinas** | `/cantina/acesso` |

A etiqueta do terceiro deixa de ser "Administrar cantinas" para não repetir o
nome duas vezes no mesmo cartão.

⚠️ **Só a cantina muda nesta fase, e isso cria dois dialetos**: o Painel, a
Administração e a ficha de ciclo continuam perguntando, em 10 cards. É
deliberado — ver a cantina primeiro e decidir depois —, e fica no §12.9 para
não virar inconsistência esquecida.

## 12.3 · F3 · Exportar de dentro do card do hub

Cada um dos três cards ganha um ícone discreto no canto, que abre PDF ou CSV.

⚠️ **O card inteiro é um `<Link>`** ([Campo.tsx](../web/src/componentes/ui/Campo.tsx),
`return <Link className={classe} to={para!}>{conteudo}</Link>`). Um `<button>`
dentro de uma âncora é HTML inválido e armadilha de teclado. Então o gesto é
**irmão** do link, não filho: o cartão passa a viver num invólucro
`position: relative`, com o link ocupando a área e o botão posicionado por cima
— dois alvos honestos, dois pontos de tabulação, e os 44 px de toque de cada
um preservados.

Cada card exporta o recorte que o próprio número promete:

| Card | O que sai |
|---|---|
| Cardápios lançados | a grade do período (§12.5.3) |
| Alunos com direito | nome, turma, almoço/janta. **Sem o texto da restrição** — a régua do §12.4 vale aqui também |
| Administrar cantinas | cantinas, contas ativas, prazo padrão e valores |

## 12.4 · F4 · A lista de quem vai comer vira lista de trabalho

Hoje a lista já existe nas duas telas e já traz o que cada um escolheu na
própria linha. O que falta é poder **trabalhar** nela:

* **Busca e pílulas**, na `BarraFiltros` que outras oito superfícies já usam:
  busca por nome ou matrícula, pílulas de `pediu` / `retirada na hora` /
  `retirado` / `com restrição`;
* **ordenação** por nome, turma ou hora do pedido — hoje é sempre por nome, e
  "quem deixou para a última hora" é pergunta real na véspera do prazo;
* **a hora na linha** ("pediu 18:42", "retirado 12:07"). O dado já viaja na
  resposta (`pedidoEm`, `retiradoEm`) e hoje só aparece no export;
* **o clique no aluno**, abrindo um diálogo sobre a lista: nome, turma, o que
  escolheu bloco a bloco, hora e modo. Diálogo e não rota própria porque a
  tarefa é conferir vários em sequência, e perder o lugar na lista a cada um
  seria trocar um problema por outro.

⚠️ **O filtro também recorta o que o botão exporta.** Um botão que exporta a
lista inteira enquanto a tela mostra 44 de 47 é um botão que mente, e o
descobrimento disso acontece na cozinha.

⚠️ **A restrição alimentar não muda de régua**: a coordenação continua vendo a
marca "tem restrição alimentar", sem o texto, com caminho para
`/cantina/direitos`, onde revelar é deliberado (docs/38 §2.6). No balcão o
texto aparece — quem cozinha precisa dele.

No celular a mesma lista, com a barra colapsando como nas outras telas.
⚠️ 390 px é exatamente onde a faixa de filtros da coordenação já quebrou quatro
vezes (docs/33), e o bloco de celular vai **depois** da regra-base, senão perde
por ordem sem aviso (docs/21 §13, aprendizado 4).

## 12.5 · F5 · Os dois exports, com os campos do processo real

A coordenação mandou a planilha e a grade que usa hoje — um formulário do
Google e uma tabela semanal. O modelo do SAS bate quase inteiro com eles:
`cardapio_bloco.nome` são "Guarnição", "Vegetariano", "Proteínas", "Salada", e
`escolhas_minimas`/`escolhas_maximas` são a coluna "Obs!" ("máximo 2 opções").
Três coisas não batem, e cada uma tem um destino diferente.

### 12.5.1 · "Tamanho" vira BLOCO — e "Local da refeição" não é campo nenhum

**A coluna "LOCAL DA REFEIÇÃO" da planilha, com "Cantina" e "Food", não é um
atributo do pedido: são as duas CANTINAS** (confirmado em 09/09). O formulário
do Google precisava dessa coluna porque era um formulário só para as duas; o
SAS não precisa, porque cada cantina já tem cardápio, prazo, contas e valores
próprios. No export ela vira a coluna **Cantina**, derivada do cardápio.

O que isso desarma está na §12.12, e não é pouco.

Sobra o **Tamanho** (500g/750g), que não existe no SAS e entra **sem schema
novo**: a cantina cadastra um bloco "Tamanho" com as duas opções, mínimo e
máximo 1. O aluno escolhe como escolhe salada, a coluna aparece sozinha no
export, e a contagem de produção passa a dizer quantos 750g — que é informação
de panela, não de planilha.

O preço: para o modelo ele é um prato, e aparece na contagem por opção junto
com o feijão. E a cantina precisa cadastrá-lo em cada cardápio — o "copiar-de"
resolve, e o editor avisa quando falta.

⚠️ **O editor avisa, e não obriga** (decisão de 09/09). Cardápio sem o bloco
"Tamanho" mostra um aviso com um botão "criar", já com 500g e 750g preenchidos.
Obrigar quebraria a janta que não tem tamanho; não avisar deixaria a coluna
sumir da planilha da coordenação, que leria isso como defeito do sistema.

### 12.5.2 · A planilha de pedidos: uma coluna por bloco, a semana num arquivo

```
Data      Hora   Aluno         Turma  Cantina  Modo     Tamanho  Salada            Guarnição              Proteína
08/09/26  17:14  Ana Beatriz   ITA-A  Food     pedido   750g     Salada de Folhas  Arroz; Feijão; Farofa  Frango Grelhado
08/09/26  17:16  Caio Rocha    ITA-B  do Ari   pedido   500g     Salada de Rúcula  Baião; Batata Frita    Maminha Grelhada
09/09/26  18:42  Ana Beatriz   ITA-A  Food     na hora  —        —                 —                      —
```

* **Uma coluna por bloco**, na ordem do cardápio — é o que a planilha do Google
  faz, e é o que deixa a coluna somável no Excel;
* **um arquivo cobre o intervalo** ("08/09 a 11/09 · ALMOÇO"), com data e
  refeição em coluna. ⚠️ **Quem faz isso é o XLSX do §12.11.3, e não um segundo
  gerador no cliente.** O CSV da tela continua sendo de UM dia — ele é o gesto
  rápido de quem está servindo agora, e a aba *Pedidos* do relatório já cobre o
  período inteiro com as mesmas colunas. Dois geradores para a mesma planilha
  divergiriam no primeiro caso de borda. ⚠️ Cardápios de dias diferentes podem ter blocos
  diferentes: as colunas são a **união** dos blocos do intervalo, e a célula
  fica vazia no dia em que aquele bloco não existiu. A planilha antiga
  resolvia isso repetindo o conjunto de colunas por dia, o que é ilegível
  depois da terceira quarta-feira;
* **quem pega na hora não tem prato** (docs/40 §10.1): a linha vem com "—" nas
  colunas de bloco e o modo dizendo o que aconteceu. Não é dado faltando.

O CSV continua no dialeto que já existe em
[exportar.ts](../web/src/telas/Cantina/exportar.ts): `;`, vírgula decimal e BOM
UTF-8, que é o que o Excel pt-BR abre sem perguntar nada.

### 12.5.3 · A grade do cardápio, como a cozinha já a desenha

```
              Terça      Quarta     Quinta     Obs!
Guarnição  1  Arroz      Arroz      Arroz      máximo 2 opções
           2  Feijão     Feijão     Feijão     A escolha da opção 4
           3  Macarrão   Macarrão   Macarrão   anula a 1 e a 2
Proteínas  1  Maminha    Maminha    Maminha    máximo 2 opções
           2  Frango     Frango     Frango
Salada     1  Folhas     Folhas     Folhas     máximo 1 opção
```

Blocos nas linhas, dias nas colunas, opções numeradas — e a coluna da direita
juntando o que o SAS já sabe (`escolhas_minimas`/`escolhas_maximas`) com o
texto livre da §12.5.4. PDF em paisagem, porque a semana não cabe em retrato.

⚠️ **A grade existe DUAS vezes, e não é descuido**: como aba do XLSX
(§12.11.3) e como PDF impresso, no botão "Imprimir a grade" do calendário da
cantina. **Não se prega planilha na parede** — a folha impressa é a tabela que
a cozinha usa hoje, e o XLSX serve a outra pergunta, que é fechar a conta do
mês. O que NÃO existe é um CSV da grade: para mexer nos números, o XLSX já
está lá.

### 12.5.4 · Migration 0053 — a observação do bloco

```sql
ALTER TABLE cardapio_bloco ADD COLUMN observacao text;
COMMENT ON COLUMN cardapio_bloco.observacao IS
    'Texto livre da cantina sobre a regra do bloco ("a escolha da opção 4 anula a 1 e a 2"). Vive no BLOCO porque é lá que a regra vive: "máximo 2 opções" já é escolhas_maximas, e o que sobra é o que o número não expressa. É ESCRITO, não vigiado — o servidor não recusa a combinação (docs/40 §12.5.4).';
```

⚠️ **A regra fica escrita e não vigiada.** O aluno pode marcar a combinação que
a observação proíbe, e ela chega à cozinha. É a decisão de 09/09 (§12.8), e o
preço dela está aqui para ser revisitado no dia em que aparecer o primeiro
pedido impossível: vigiar exige um par de opções incompatíveis no schema e
validação nos dois lados — é uma feature, não um ajuste.

A observação aparece em três lugares: no editor da cantina, na tela de pedido
do aluno (senão a regra não chega em quem escolhe) e na coluna "Obs!" do
export.

## 12.6 · F6 · A cantina escolhida, e não "a primeira ativa"

[SeletorDeCantina](../web/src/telas/Cantina/SeletorDeCantina.tsx) **se esconde
quando há menos de duas cantinas**, e `_cantina_padrao` escolhe a primeira
ativa em silêncio. Com uma cantina, o coordenador nunca vê de qual cardápio
está falando.

Passa a aparecer **sempre**, no topo do calendário, preenchido com a cantina
atual, com o recorte na URL (`?cantina=`) como já é hoje.

⚠️ **Isto reverte uma decisão escrita no próprio arquivo** — *"um seletor com
uma opção é um controle que não decide nada"*. A reversão tem motivo: com uma
cantina o seletor não **decide**, mas **informa**, e "de qual cantina é este
cardápio?" é pergunta que se faz mesmo havendo uma só. O comentário do arquivo
muda junto; deixá-lo dizendo o contrário do código é como este documento
começou (§0).

O resumo do card no hub passa a **somar todas as cantinas ativas**, dizendo "em
2 cantinas" quando houver mais de uma. `_cantina_padrao` continua caindo na
primeira ativa quando não vem parâmetro — compatibilidade —, mas a tela sempre
manda.

## 12.7 · F7 · Senha manual, sem guardar senha

O pedido foi "ver as senhas da cantina e poder trocá-las". Ver não é possível
sem trocar de regime: `usuario_cantina.senha_hash` é **PBKDF2 de mão única**,
como o de `usuario_coordenacao`, e [cantina.py](../api/app/routes/cantina.py)
diz isso em comentário — *"depois disto ninguém — nem o sistema — lê a senha de
volta"*. Guardar texto legível exporia contas que alcançam nome, turma e
restrição alimentar de menores.

**O que resolve a necessidade sem guardar nada:** o diálogo de criar e o de
redefinir passam a oferecer duas saídas — *gerar uma* (o
`secrets.token_urlsafe(12)` de hoje) ou *definir esta*, digitada pelo
administrador. **Quem define, sabe** — e a vontade de "ver" era, na prática, a
de conseguir dizer a senha para a cantina.

A tela passa a mostrar o que dá para saber com honestidade: *"senha definida em
09/09, por Leonardo Bruno"*, que já existe em `evento_auditoria` (canal
`cantina`, `senha_cantina_redefinida`) e hoje não aparece em lugar nenhum.

A mesma escolha entra em `/administracao/contas`, para as contas de
coordenação: é o mesmo hash e a mesma tela de administração, e deixar só a
cantina com a opção criaria duas regras para a mesma coisa.

⚠️ Senha digitada precisa de piso: comprimento mínimo, recusa no **servidor**
(não só no campo) e nada de senha igual ao e-mail. O guard de configuração já
recusa subir com senha demo ([`_validar_configuracao`](../api/app/main.py)) —
a mesma severidade vale aqui.

## 12.8 · F8 · A cantina ganha um terceiro destino, e o segundo muda de nome

O casco da cantina tem dois destinos ([CascoCantina.tsx](../web/src/telas/Cantina/CascoCantina.tsx)),
e é por serem dois que a barra inferior do celular funciona (docs/21 §13).
Passam a ser três.

### 12.8.1 · "Ler código" vira "Validar entrega"

"Ler" descreve o gesto; **"validar" descreve o que acontece** — e é o verbo
certo para quem está servindo. O substantivo é que exigiu cuidado: o comentário
do casco existe justamente para impedir a palavra errada, *"'Ler código', e não
'Pedidos ao vivo': aqui ninguém pediu nada"*, e é a mesma razão pela qual o
docs/40 §8 tirou "quem pediu" do título da lista.

**"Entrega" é verdade para os dois públicos** — quem pediu na véspera e quem
chegou sem pedir —, enquanto "pedido" seria falso exatamente sobre as pessoas a
quem o QR serve. O comentário do arquivo muda junto, senão passa a explicar uma
decisão que não é mais a que está no código.

### 12.8.2 · A aba nova: "Visualizar pedidos"

Dois campos no topo — dia e almoço/janta —, já preenchidos com **hoje** e com a
refeição do horário atual; a lista aparece sem nenhum clique. Trocar o dia é um
campo, não uma viagem pelo calendário.

```
Visualizar pedidos                    [↓ exportar]

Dia [ 09/09/2026 ▾ ]   ( Almoço )( Janta )

44 vão comer · 41 com pedido · 3 de retirada na hora
┌────────────────────────────────────────┐
│ Ana Beatriz    ITA-A   pediu 17:14   › │
│ Caio Rocha     ITA-B   pediu 17:16   › │
```

A tela é a **mesma** lista de `PedidosDoDia`, com os ganhos do §12.4 (busca,
pílulas, ordenação, hora na linha, diálogo do aluno) e a exportação do §12.5.2
no topo. O que muda é a porta.

⚠️ **As duas portas continuam existindo, e é de propósito.**
`/cardapios/:data/:refeicao` chega pelo calendário — é o caminho de quem está
montando a semana. `/pedidos` chega pela data — é o caminho de quem está
servindo hoje. Mesma tela, duas perguntas diferentes.

⚠️ **Três destinos são o teto da barra inferior.** Em 390 px, três rótulos com
alvo de 44 px cabem; o quarto obrigaria a virar só-ícone, e ícone sem rótulo em
casco que se usa uma vez por dia é adivinhação. Se um dia houver o quarto, a
barra muda de desenho — não se aperta.

## 12.9 · F9 · O QR que muda a cada 10 segundos, com nome e foto

Hoje o código é um JWT assinado que vale **120 s**
([cantina_token.py](../api/app/cantina_token.py)), renovado sozinho pelo hook.
Duas mudanças:

### 12.9.1 · Nome e foto na tela do QR

O aluno passa a ver o próprio nome e a própria foto acima do código. Não é
enfeite: **o print resolve a cópia no tempo, a foto resolve a cópia no
espaço.** Quem mostrar o celular de outro aparece com a cara de outro, e quem
serve olha para a pessoa de qualquer jeito.

⚠️ É mais fraco do que a foto na tela da CANTINA (§14.2, fase 4), porque o
print carrega a foto junto — só funciona se quem serve comparar. Estreita a
fresta; quem a fecha continua sendo a fase 4.

Sem foto cadastrada, iniciais no lugar. Bloquear quem não tem foto é decisão da
fase 4, não desta.

### 12.9.2 · O código muda a cada 10 s, e sem pedir nada à rede

O caminho direto — baixar `SEGUNDOS_DE_VALIDADE` para 10 — foi recusado por
dois motivos medidos, não teóricos:

1. **Não sobra folga para uma falha de rede.** O comentário do
   [hook](../web/src/hooks/cantina.ts) já descreve o caso: com o wi-fi
   associado e sem rota (o handoff de AP no corredor), o POST **pendura** em
   vez de rejeitar. Com 120 s dá tempo de o erro aparecer enquanto o código
   velho ainda vale; com 10 s o aluno fica sem QR na frente da fila;
2. **Cada renovação é uma escrita.** Seis por minuto, por aluno com a tela
   aberta, numa API de uma thread só (§12.1.1).

**O desenho:** o servidor entrega uma **semente assinada** (a validade de 120 s
de hoje) e o aparelho **deriva** o código da janela de 10 s a partir dela, por
HMAC, sem rede. O balcão lê, e o servidor recalcula e compara.

```
servidor → semente assinada (120 s) + o instante DELE
   ↓
celular deriva, offline:
   0–10 s   código A
  10–20 s   código B      ← o print de A já não vale
  20–30 s   código C
   ↓
balcão lê → servidor recalcula e aceita a janela atual e a anterior
```

⚠️ **Aceitar a janela anterior não é folga, é requisito.** Entre o aluno
mostrar e a câmera focar passam segundos, e um código que morre no instante
exato transformaria a fila em repetição.

⚠️ **O relógio do celular não é confiável, e por isso a contagem é relativa.**
A semente viaja com o instante do servidor; o aparelho conta o tempo decorrido
a partir dele, em vez de ler a hora do mundo. Assim um celular adiantado em
três minutos continua gerando o código certo — e some a necessidade de aceitar
também a janela seguinte, que é onde este tipo de desenho costuma abrir a
fresta que queria fechar.

O que **não** muda: a leitura continua atômica no servidor (o `UPDATE`
condicional do §4), a semente continua assinada, e a tela do aluno continua sem
botão de atualizar.

⚠️ **Depende da F1.** A semente segue em 120 s justamente porque a renovação
dela ainda passa pela API — e enquanto o event loop congelar (§12.1.1), toda
renovação pode pendurar.

## 12.10 · F10 · O tema claro por padrão

Hoje o primeiro acesso cai no `prefers-color-scheme` do aparelho
([tema.ts](../web/src/servicos/tema.ts), `preferidoPeloSistema`). Na prática,
**quem decide o tema do SAS é a configuração do Chrome de quem abre** — e é por
isso que a coordenação aparece escura sem ninguém ter pedido escuro.

Passa a nascer **claro em todo lugar**: coordenação, cantina, área do aluno e a
porta. O botão de trocar continua nos três cascos, e a escolha gravada em
`sas_tema` continua vencendo o default — quem já clicou no sol alguma vez não
perde nada.

⚠️ **Isto muda a área do aluno, e ela foi desenhada com o escuro em mente**
(docs/24 §7.2): é o casco que se usa à noite, no celular. A decisão de 09/09 foi
tomada com esse custo na mesa — vale mais um produto com **um** padrão do que um
padrão que depende do aparelho de quem abre. Se aparecer reclamação de aluno, o
remédio já está na tela: o botão está lá e a escolha dele persiste.

⚠️ `preferidoPeloSistema()` **não sai do arquivo** — sai do caminho do default.
Mantê-la escrita é o que permite voltar atrás em uma linha, e o comentário do
módulo passa a dizer por que ela não é mais chamada. Apagar a função esconderia
que a escolha existiu.

O cuidado é um só, e já está escrito no arquivo: o atributo é estampado **no
escopo do módulo, antes do primeiro render**, justamente para não piscar. O
default novo entra no mesmo lugar — qualquer coisa que dependa de `useEffect`
reintroduz o flash que aquele trecho existe para evitar.

## 12.11 · F11 · O custo da refeição, do cadastro ao relatório

### 12.11.1 · Metade disto já existe

A migration `0050` (docs/38 §8.2) já deu à cantina `valor_almoco` e
`valor_janta`, editáveis em `/cantina/acesso` — que é a aba "Administrar
cantinas" —, e `PedidosDoDia` já soma `pedidos × valor` ao lado da contagem. **O
cadastro do valor por refeição que você pediu está no ar.**

O que não existe é o valor **sobreviver ao tempo**, e o relatório.

### 12.11.2 · O valor é carimbado no pedido — migration 0054

```sql
ALTER TABLE pedido_refeicao ADD COLUMN valor_cobrado numeric(10,2);
COMMENT ON COLUMN pedido_refeicao.valor_cobrado IS
    'Quanto valia a refeição no instante em que este pedido foi feito. Existe para o relatório não reescrever o passado quando o preço muda: sem ele, subir o almoço em abril mudaria o custo de março (docs/40 §12.11.2). NÃO é cobrança — não há fatura, nem "quem pagou" (docs/38 §8.1.5).';
```

Por que **no pedido** e não numa tabela de vigência: o pedido é o fato, e o
preço no instante do fato é atributo dele. Vigência depende de alguém cadastrar
a data certa, e uma data errada reescreve o mês inteiro sem avisar.

```
preço do almoço: R$ 18,00 até 15/03 · R$ 21,00 a partir de 16/03

com carimbo    10 × 18,00 + 12 × 21,00 = R$ 432,00   ✓
sem carimbo    22 × 21,00              = R$ 462,00   ✗  30 reais que ninguém gastou
```

⚠️ **A coluna é anulável, e o passado não tem carimbo.** Os pedidos que já
existem em produção nasceram sem ele. O backfill usa o valor cadastrado hoje —
aceitável **porque o preço nunca mudou até agora**, e isso é uma afirmação
verificável, não uma suposição. Fica registrado como decisão: preencher com o
valor de hoje é diferente de fingir que sempre houve carimbo.

⚠️ **Isto continua não sendo cobrança.** Nada de fatura, "quem pagou" ou
conciliação — a fronteira do docs/38 §8.1.5 segue de pé. Mas o recorte **por
aluno** (§12.11.3) é o que mais se aproxima dela: é leitura, e no dia em que
alguém pedir "manda a conta do aluno", a resposta deixa de ser um relatório e
vira outro produto.

### 12.11.3 · A planilha sai do SERVIDOR, com gráfico de verdade

`openpyxl` **já está** em `api/requirements.txt` — hoje só para *ler* o XLSX do
Canvas ([ingest/reader.py](../api/app/ingest/reader.py)) — e ele **escreve
gráficos nativos do Excel**. No navegador isso não existe: nem SheetJS nem
exceljs escrevem gráfico, e a biblioteca ainda pesaria ~1 MB no bundle que a F1
está cortando.

Rota nova: `GET /administracao/cantina/relatorio.xlsx?de=&ate=&cantina=`, sob
`get_current_coordenador`.

⚠️ **É a primeira rota de exportação da API.** O docs/38 §8.2 registrou "não
existe rota de exportação — o export é só do lado do cliente" como escolha
consciente; ela muda **aqui e só aqui**, porque gráfico em XLSX não tem como
ser feito no navegador. O CSV e o PDF de hoje continuam no cliente: não se
migra o que já funciona.

| Aba | O quê |
|---|---|
| **Pedidos** | uma linha por aluno-dia, as colunas do §12.5.2, mais o valor carimbado |
| **Custos · por dia** | dia × refeição, quantidade e total, com gráfico de barras |
| **Custos · por turma** | turma × refeição, com gráfico |
| **Custos · por aluno** | aluno, quantas refeições, total |
| **Custos · por cantina** | só aparece quando houver mais de uma |
| **Cardápio** | a grade semanal do §12.5.3 |

⚠️ **Esta rota nasce com `asyncio.to_thread`.** Montar um XLSX de ~40 mil linhas
é trabalho de CPU, síncrono, e sem isso ele congela o event loop exatamente
como o LLM da §12.1.1 — a fase 2 consertaria o congelamento e o traria de volta
pela porta que ela mesma abriu. `write_only` no openpyxl, pelo mesmo motivo de
memória.

A restrição alimentar **não entra** no relatório da coordenação — mesma régua
do §12.4.

### 12.11.4 · A tela: o quarto card do hub

`Custos / Quanto a cantina custou`, com o resumo no próprio card ("setembro ·
R$ 4.320 · 240 refeições"). Tela inteira com seletor de período, os quatro
recortes, os gráficos e a tabela, e o mesmo gesto de exportar dos outros cards
(§12.3) — que aqui baixa o XLSX da §12.11.3.

⚠️ **O hub tem duas composições de grade declaradas** (dois cards para o
coordenador comum, três para o administrador), e o comentário do arquivo
explica que são duas composições justamente para não haver buraco. Com o quarto
card elas viram **três e quatro** — e continuam sendo duas composições, não uma
grade de quatro com uma célula vazia.

**Quem vê o custo:** qualquer coordenador. Cadastrar o valor continua sendo do
administrador, em `/cantina/acesso` — ver quanto custou não é o mesmo que
decidir quanto custa, e é a mesma divisão que `/cantina/direitos` já usa.

⚠️ **Os gráficos são SVG à mão.** O `package.json` não tem biblioteca de
gráfico e `GraficoEmCamadas.tsx` é desenhado no braço; o relatório segue o mesmo
caminho. Nada de CDN (CLAUDE.md, armadilha 7), e a skill `dataviz` do
repositório é a régua de cor e de forma.

## 12.12 · F12 · Duas cantinas de verdade

"Food" é **uma cantina**, não um local de consumo — descoberto em 09/09, lendo
a planilha do processo atual. Isso não acrescenta uma feature: **desarma três
premissas** que hoje são verdadeiras só porque existe uma cantina cadastrada.

### 12.12.1 · O que para de valer quando a Food entrar

| Onde | O que assume hoje | O que acontece com duas |
|---|---|---|
| [cantina_do_aluno](../api/app/routes/cantina.py) | busca cardápio por refeição e data, **sem filtrar cantina** | o aluno vê dois almoços do mesmo dia, sem saber de quem é cada um |
| `direito_refeicao_aluno` | chave `(aluno_id, refeicao)` | não há onde dizer em que cantina o aluno come — e, pela decisão abaixo, não precisa haver |
| `pedido_refeicao` | `UNIQUE(cardapio_id, aluno_id)` | a trava é por **cardápio**: pedir nos dois almoços do mesmo dia passa, e as duas cozinham |

⚠️ **Nenhuma das três dá erro.** É o mesmo padrão que o docs/38 §1.1 registrou
no `foto_perfil.py`: premissa verdadeira até deixar de ser, e o dia em que
deixa não vem com aviso — vem com comida a mais na conta.

### 12.12.2 · O aluno escolhe, e a trava sobe para o DIA — migration 0055

Decisão de 09/09: o aluno vê as duas cantinas e decide a cada dia.

```sql
ALTER TABLE pedido_refeicao
    ADD COLUMN data     date,
    ADD COLUMN refeicao text;
-- preenchidas a partir do cardápio, e então a trava sobe de nível:
CREATE UNIQUE INDEX pedido_refeicao_um_por_dia
    ON pedido_refeicao (aluno_id, data, refeicao);
```

⚠️ **É desnormalização, e ela só é segura por causa de um fato verificado:**
`data` e `refeicao` são **imutáveis depois de criado o cardápio** — o
`CardapioBody`, corpo do editor, não tem esses campos; eles só existem em
`NovoCardapioBody`. O comentário da coluna precisa dizer isso, porque no dia em
que alguém acrescentar "mover cardápio de dia", a cópia passa a divergir em
silêncio.

Por que não uma trigger: **restrição de unicidade que atravessa tabela não
existe no Postgres**, e uma trigger teria de resolver concorrência à mão — dois
pedidos simultâneos passariam pela checagem antes de qualquer um gravar. O
índice único é a única forma que o banco garante sozinho.

⚠️ **A trava cobre os dois modos.** Pedido e retirada presencial são linhas da
mesma tabela, então declarar presença na Food e pedir na do Ari no mesmo almoço
passa a ser recusado — que é o comportamento certo, e hoje não é o que
acontece.

⚠️ **O backfill vem antes do índice, e a migration confere antes de criá-lo.**
Os pedidos existentes não têm `data`/`refeicao` (um `UPDATE ... FROM cardapio`
resolve), e se houver duplicata já gravada — improvável com uma cantina, mas
verificável — a criação do índice falha e a migration para no meio.

### 12.12.3 · A tela do aluno passa a dizer de quem é cada cardápio

`GET /me/cantina` devolve o nome da cantina em cada dia, e a tela agrupa por dia
com as duas opções lado a lado. Feito o pedido numa delas, a outra mostra "você
já pediu na Food hoje" — **e não some**: trocar de ideia é cancelar numa e pedir
na outra, e uma opção invisível não ensina isso a ninguém.

### 12.12.4 · O que isto muda nas outras frentes

* **§12.5.1** — "Local da refeição" **deixa de ser bloco**. É a cantina, que já
  existe no modelo. Só "Tamanho" vira bloco;
* **§12.5.2** — a planilha ganha a coluna **Cantina**, derivada do cardápio e
  não escolhida pelo aluno;
* **§12.6** — o seletor sempre visível deixa de ser preparação e vira
  necessidade: com duas cantinas, "de quem é este cardápio?" é a primeira
  pergunta de toda tela da coordenação;
* **§12.11** — o recorte "por cantina" do relatório deixa de ser coluna que
  nasce pronta para o futuro e passa a ser o recorte da negociação com dois
  fornecedores.

## 12.13 · Decisões fechadas em 09/09

| # | Pergunta | Resposta |
|---|---|---|
| 12.13.1 | O conserto do LLM entra nesta fase, mesmo não sendo cantina? | **Entra** — é a causa raiz, e sem ela o resto não se percebe |
| 12.13.2 | Como dividir o bundle? | Por **casco + telas pesadas** (KaTeX só em `/banco`, jsQR só em `/ao-vivo`) |
| 12.13.3 | Onde medir? | **Produção, logado** — é o número que as pessoas sentem |
| 12.13.4 | O que dói hoje? | As telas de cantina no balcão e na coordenação, e a área do aluno |
| 12.13.5 | Os cards passam a nomear em vez de perguntar? | **Sim, e só na cantina** por ora |
| 12.13.6 | O que cada card exporta? | O recorte que o próprio número promete |
| 12.13.7 | Formato e lugar do gesto de exportar? | **PDF caprichado + CSV**, ícone no canto do card, irmão do link |
| 12.13.8 | O que falta na lista de quem vai comer? | Busca, pílulas, ordenação, hora na linha e o diálogo do aluno — e o mesmo no balcão, adaptado |
| 12.13.9 | Onde entram "Tamanho" e "Local da refeição"? | Como **blocos do cardápio** — sem schema novo |
| 12.13.10 | Formato da planilha de pedidos? | Uma coluna por bloco, **a semana num arquivo** |
| 12.13.11 | Formato do cardápio? | A **grade semanal** com a coluna "Obs!" |
| 12.13.12 | A regra "a opção 4 anula a 1 e a 2" é vigiada? | **Não** — vira texto de observação no bloco |
| 12.13.13 | Como o coordenador escolhe a cantina? | Seletor **sempre visível**; o resumo do hub soma todas |
| 12.13.14 | Como "ver a senha"? | **Não se vê** — define-se. Manual ou gerada, nas duas telas de conta |
| 12.13.15 | A senha manual vale também para a coordenação? | **Sim** — mesmo hash, mesma tela, uma regra só |
| 12.13.16 | Nome da aba de ler o QR? | **"Validar entrega"** — "pedido" seria falso sobre quem o QR serve |
| 12.13.17 | Como a cantina chega ao dia na aba nova? | **Dois campos**, já em hoje e na refeição do horário |
| 12.13.18 | Como o QR muda a cada 10 s? | **Derivado no aparelho**, de uma semente assinada de 120 s |
| 12.13.19 | Quem nasce com tema claro? | **Todo mundo** — coordenação, cantina, aluno e a porta. `prefers-color-scheme` deixa de decidir |
| 12.13.20 | O botão de trocar tema fica? | **Fica**, nos três cascos, e a escolha gravada vence o default |
| 12.13.21 | O valor da refeição sobrevive ao tempo? | **Sim** — carimbado no pedido (migration `0054`), para o relatório não reescrever o passado |
| 12.13.22 | Onde o XLSX é gerado? | **No servidor**, com `openpyxl` — é a primeira rota de exportação da API, e existe porque gráfico em XLSX não se faz no navegador |
| 12.13.23 | Recortes do relatório? | Dia × refeição, turma, aluno e cantina |
| 12.13.24 | Onde vive o relatório? | **Quarto card do hub**, legível por qualquer coordenador; cadastrar o valor segue do administrador |
| 12.13.25 | "Food" é o quê? | **Uma cantina** — não um local de consumo. "Local da refeição" deixa de ser bloco |
| 12.13.26 | Com duas cantinas, quem escolhe? | **O aluno**, dia a dia. A trava sobe para `(aluno, dia, refeição)`, migration `0055` |
| 12.13.27 | Como entregar os 15 passos? | **Numa tanda só** — com o preço registrado no §12.14: o diff mexe em senha, tema, três migrations e uma trava de unicidade |

## 12.14 · Plano de implementação da Fase 2

Quinze passos. A ordem não é arbitrária: **desempenho primeiro**, porque é o
único item cujo efeito desaparece se for medido depois de a tela mudar; a
exportação do hub por último, porque reaproveita o que a §12.5 constrói; e o QR
rotativo depois da F1, porque depende dela (§12.9.2).

**Passo 1 · A medição do "antes".** Produção, logado, MCP `chrome`.
*Entregável: a tabela do §12.1.5 com a coluna "Antes" preenchida.* Sem isto, o
resto é opinião.

**Passo 2 · O event loop.** `asyncio.to_thread` nas cinco chamadas de LLM.
*Entregável: um teste que hoje falharia — com um mock de LLM dormindo 2 s em
curso, uma requisição comum responde em menos de 100 ms.*

**Passo 3 · O resumo do hub.** `GET /administracao/cantina/resumo` por
contagem, e o hub deixa de chamar `/alunos`. *Entregável: a aba de rede do hub
sem a chamada de 9 MB.*

**Passo 4 · O N+1 e o `staleTime`.** Blocos de todos os cardápios numa consulta,
`_contagem` uma vez só, e o `staleTime: 0` alinhado ao que o SSE já invalida em
**três** consultas — `cardapio`, `contagem` e `pedidos`.

⚠️ **`useTokenDeRetirada` fica de fora, e não é esquecimento.** O `staleTime: 0`
e o `gcTime: 0` dele existem para o QR nunca aparecer vencido por um instante
ao voltar à tela, e o comentário do hook diz isso. "Alinhar" essa consulta às
outras quebraria a F9 — que é a única desta fase que depende de o código estar
sempre fresco.

*Entregável: o número de idas ao PostgREST por requisição, antes e depois.*

**Passo 5 · O bundle.** `lazy()` por casco e por tela pesada, com o CSS junto e
a ordem preservada. *Entregável: `dist/assets` com um arquivo por casco, KaTeX
fora da entrada, e a navegação sem piscar.*

**Passo 6 · As três migrations.** A **0053** (a observação do bloco, §12.5.4) e
a **0054** (o valor carimbado no pedido, §12.11.2), cada uma com seu
`.down.sql`, mais o backfill do valor de hoje (§12.11.2) e ⚠️ `docker compose
restart postgrest` — senão as colunas novas voltam 404, e o 404 parece bug de
código (CLAUDE.md, armadilha 1). A **0055** é a mais delicada das três: backfill de
`data`/`refeicao`, conferência de duplicata e só então o índice único
(§12.12.2). A observação entra no editor, na tela do aluno e no export.

**Passo 7 · F12 · Duas cantinas.** O filtro de cantina na leitura do aluno, o
nome da cantina em cada dia, a tela agrupando as duas opções, e a recusa nova
quando já existe pedido do dia. *Entregável: um aluno com direito a almoço,
duas cantinas publicando o mesmo dia — ele vê as duas, pede numa, e a segunda
recusa com a frase certa em vez de aceitar.*

**Passo 8 · F2, F6 e F10 · as três pequenas.** Nomes dos cards e seletor sempre
visível — são a mesma tela, e o comentário do `SeletorDeCantina` é corrigido no
mesmo diff. O tema claro por padrão entra aqui porque é da mesma natureza: uma
linha em `tema.ts` e o comentário do módulo dizendo por que
`preferidoPeloSistema()` continua escrita e não é mais chamada. *Entregável: um
navegador em modo escuro abrindo o produto claro, sem piscar.*

**Passo 9 · F7 · A senha.** Escolha "gerar / definir" nas duas telas de conta,
piso de senha no servidor, e a linha de auditoria aparecendo na tela.
*Entregável: teste de que senha fraca é recusada pelo SERVIDOR, mesmo com o
campo do front contornado.*

**Passo 10 · F5 · Os dois exports.** Os blocos de Tamanho e Local (que são
cadastro, não código), a planilha da semana e a grade. *Entregável: os dois
arquivos abertos no Excel pt-BR e num visualizador de PDF, com uma semana
real.*

**Passo 11 · F4 · A lista de trabalho.** Busca, pílulas, ordenação, hora e o
diálogo — na coordenação e no balcão, com o filtro recortando o export.

**Passo 12 · F8 · O terceiro destino.** A aba "Visualizar pedidos" sobre a
lista do passo 10, e o rótulo "Validar entrega". *Entregável: as duas portas
levando à mesma lista, e a barra inferior com três destinos sem transbordo em
390 px.*

**Passo 13 · F9 · O QR rotativo.** A derivação no aparelho, a verificação por
janelas no servidor, e o nome e a foto na tela. *Entregável: teste de janela —
código da janela atual passa, o da anterior passa, o de duas atrás não; e um
celular com o relógio adiantado em 3 min continua sendo lido.*

**Passo 14 · F11 · O custo.** A rota do XLSX no servidor — com
`asyncio.to_thread` e `write_only` desde a primeira linha (§12.11.3) —, o quarto
card e a tela de relatório. *Entregável: o arquivo aberto no Excel com os
gráficos desenhados, e um mês inteiro gerado sem a API parar de responder.*

**Passo 15 · F3 e os portões.** O gesto de exportar nos cards do hub, e então
`pytest`, `ruff`, `npm test`, `npm run lint`, `tsc --noEmit`, `npm run build`,
`npm run inventario`. ⚠️ **E o browser** — feito em 09/09, com sessão de
verdade nos dois cascos, e o que ele achou está na §12.1.6: quatro defeitos que
nenhum portão pegaria, um deles uma tela impossível de clicar.

⚠️ **O que ficou de fora, e é a mesma lacuna de sempre:** as telas do ALUNO. Ele
entra só pelo SSO do Canvas, que precisa da Developer Key e não existe no
compose — então o QR girando nunca foi visto girar. E a medição do "antes"/
"depois" em produção (passo 1) continua pendente de acesso logado a
`portalsas.online`.

**Fora deste plano, de propósito**: o deploy.

⚠️ **Os quinze passos vão numa tanda só** (decisão de 09/09), e o preço fica
escrito: o diff mexe em senha, em tema, em três migrations e numa trava de
unicidade que muda o que o produto aceita gravar. Se em algum momento ele ficar
grande demais para ser revisado com atenção, o corte natural é **depois do
passo 7** — desempenho e schema de um lado, telas do outro.

## 12.15 · Em aberto na fase 2

* **A propagação dos nomes** para os outros 10 cards do produto (Painel,
  Administração, ficha de ciclo). Decidido ver a cantina primeiro (§12.2).
* **`listar_alunos` continua baixando tudo.** Esta fase tira o hub de cima
  dela; a tela `/alunos` segue com 9,31 MB por carregamento, e é a armadilha 2
  do CLAUDE.md chegando pela porta da frente.
* **`AsyncOpenAI` em vez de `to_thread`**, e com ele o streaming de verdade no
  chat — hoje o texto chega inteiro e é picado em 40 caracteres para parecer
  que digita.
* **A exclusão mútua entre opções** (§12.5.4), hoje só escrita.
* **Tamanho como bloco** aperta no dia em que a cozinha quiser cruzar tamanho
  com prato: bloco não sabe que "750g" qualifica a proteína, não a salada.
* **O direito continua global** (`aluno_id`, `refeicao`), porque quem escolhe a
  cantina é o aluno (§12.12.2). Se um dia a escola quiser dizer "este aluno só
  come na Food", aí sim o direito ganha `cantina_id` — e a tela do aluno deixa
  de ter escolha.
* **A foto na tela da CANTINA** na confirmação continua na fase 4 (§14.2) — é
  ela que fecha a fresta que a foto na tela do aluno só estreita.
* **A trava automatizada de transbordo** continua não existindo (docs/21 §13), e
  esta fase acrescenta superfície nova em celular — inclusive o terceiro
  destino da barra.

---

# FASE 3 — a janela de retirada

## 13.1 · O que foi pedido

A leitura do QR passa a valer **só dentro de um intervalo de horário**, e o
intervalo é **da coordenação**, não da cantina. É uma grade **semanal fixa**: o
horário de todas as segundas, de todas as terças, de todos os sábados — não
data a data. Fora do intervalo, a coordenação tem, na tela de administração dos
alunos da cantina, um botão **"liberar o aluno"** que destrava aquela retirada.

## 13.2 · Decisões fechadas em 07/09

| # | Pergunta | Resposta |
|---|---|---|
| 13.2.1 | Dia da semana sem janela cadastrada significa o quê? | **Sem retirada** — fail-closed. A ausência de regra não é permissão |
| 13.2.2 | Quem clica em "liberar o aluno"? | **Qualquer coordenador.** A janela é sobre horário, não sobre direito — o aluno já tem a refeição garantida, e travar isso no administrador põe fila de menor esperando alguém aparecer |

⚠️ A 13.2.1 tem uma consequência que precisa de conserto no mesmo passo: **no
instante em que a fase 3 sobe, a fase 1 para de funcionar** se não houver grade
cadastrada. A migration nasce, por isso, **semeando a grade com o que já vale
hoje** — 00:00 às 23:59, todos os sete dias, nas duas refeições, para cada
cantina existente. Não é inventar política: é continuidade, e deixa a
coordenação estreitar deliberadamente em vez de descobrir o bloqueio pelo
aluno que ficou sem almoço.

## 13.3 · Schema — migration 0056

```sql
CREATE TABLE janela_retirada (
    cantina_id  uuid NOT NULL REFERENCES cantina(id),
    dia_semana  int  NOT NULL CHECK (dia_semana BETWEEN 0 AND 6),  -- 0 = domingo
    refeicao    text NOT NULL CHECK (refeicao IN ('almoco', 'janta')),
    hora_inicio time NOT NULL,
    hora_fim    time NOT NULL,
    PRIMARY KEY (cantina_id, dia_semana, refeicao),
    CONSTRAINT janela_ordenada CHECK (hora_fim > hora_inicio)
);
-- Grade SEMANAL, não calendário: é o que foi pedido, e poupa a coordenação de
-- redigitar horário 200 vezes por ano. Linha ausente = não há retirada
-- presencial naquele dia (§13.2.1) — a ausência de regra é recusa, não
-- permissão, e é por isso que a migration semeia (§13.2).

CREATE TABLE liberacao_retirada (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id     uuid NOT NULL REFERENCES aluno(id),
    cardapio_id  uuid NOT NULL REFERENCES cardapio(id),
    liberado_por uuid NOT NULL REFERENCES usuario_coordenacao(id),
    criado_em    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aluno_id, cardapio_id)
);
-- A exceção é presa a um CARDÁPIO (uma refeição de um dia), não ao aluno: uma
-- liberação sem prazo viraria direito paralelo em duas semanas, e ninguém
-- lembraria de tirar. Morre sozinha quando o dia acaba.
```

## 13.4 · Onde a regra é aplicada

Nos **dois** momentos, e por motivos diferentes:

* **Ao gerar** (`POST /me/cantina/retiradas/{id}`) — recusa 422 com o texto da
  janela ("A retirada de hoje é das 11h30 às 13h30"). É gentileza com
  consequência: sem isso o aluno caminha até o balcão com um QR que já nasceu
  morto, e descobre na frente da fila.
* **Ao ler** (`POST /cantina/retiradas/confirmar`) — recusa **409** com texto
  próprio, distinto de "já retirado", porque a ação seguinte é outra: falar com
  a coordenação, não sair da fila.

Nos dois casos a liberação é alternativa à janela: vale se `agora` está dentro
do intervalo **ou** existe `liberacao_retirada` para aquele aluno e cardápio.

⚠️ Sobra uma borda conhecida e aceita: gerar às 13h29 e chegar ao balcão às
13h31 dá 409. É o mesmo desenho do prazo do pedido (docs/38 §3.2) — quem
decide é o servidor no instante da ação, não a tela que já estava aberta.

## 13.5 · Rotas

| Rota | Guard | O quê |
|---|---|---|
| `GET /administracao/cantina/janelas` | `get_current_coordenador` | A grade 7 × 2 |
| `PUT /administracao/cantina/janelas` | **`get_current_administrador`** | Grava a grade inteira (é política da casa) |
| `POST /administracao/cantina/liberacoes` | `get_current_coordenador` | Libera um aluno num cardápio (§13.2.2) |
| `DELETE /administracao/cantina/liberacoes/{id}` | `get_current_coordenador` | Desfaz — errar o aluno na pressa da fila é previsível |

Toda liberação vai para `evento_auditoria`, canal `cantina`
(`retirada_liberada` / `retirada_liberacao_desfeita`), com o coordenador como
autor: é o ato de furar a própria regra, e sem autor e hora ninguém consegue
responder "quem liberou?".

## 13.6 · Telas

* **Coordenação · grade** (`/cantina/acesso`, junto do resto da política da
  cantina): sete linhas × duas colunas, hora de início e fim. Para o
  coordenador comum, leitura; escrita só do administrador, e o que ele não pode
  **não aparece** (docs/38 §6).
* **Coordenação · liberar** (`/cantina/direitos`, onde ela já mexe em quem
  come): botão "Liberar" por aluno, que só faz sentido no dia — então mostra a
  refeição de hoje e o estado (`dentro da janela` / `fora, liberado` / `fora`).
* **Aluno**: a tela do QR passa a mostrar a janela em texto, e fora dela não
  gera nada — explica o horário e diz para procurar a coordenação.
* **Cantina**: a tela "Ler código" ganha o quinto estado de leitura —
  *fora do horário* —, visualmente distinto de *já retirado*.

## 13.7 · Plano de implementação da Fase 3

1. **Migration 0056** + `.down.sql` + a semeadura do §13.2 + `restart postgrest`.
2. **Backend**: a checagem nos dois pontos do §13.4, as quatro rotas do §13.5,
   auditoria. *Testes: dentro/fora da janela, virada de meia-noite, dia sem
   linha (recusa), liberação vale, liberação de outro cardápio não vale,
   liberação desfeita volta a recusar.*
3. **Front da coordenação**: grade + botão liberar.
4. **Front do aluno e da cantina**: os textos de janela e o estado novo de
   leitura.
5. **Portões** de sempre, browser incluído.

## 13.8 · Em aberto na fase 3

* **A janela é por cantina ou da escola?** O schema põe em `cantina` por
  consistência; com uma cantina só, dá no mesmo hoje.
* **Feriado dentro da grade semanal.** A grade não conhece calendário: numa
  terça de feriado ela continua "aberta". Hoje isso é coberto de lado, porque
  sem cardápio publicado não há o que retirar — mas se um dia alguém publicar
  cardápio em feriado, a janela não vai discordar.

---

# FASE 4 — reconhecimento facial

## 14.1 · O que foi pedido, e o que ficou decidido

Nem o pedido nem o QR saem sem o aluno **passar por comparação facial**: a foto
cadastrada dele contra uma batida **na hora**, via AWS Rekognition
`CompareFaces`, **sem liveness**. E com travamento contra **carregar** imagem —
tem de fotografar no momento.

| # | Pergunta | Resposta em 07/09 |
|---|---|---|
| 14.1.1 | Onde a verificação acontece? | **No celular do aluno, ao gerar o QR** |
| 14.1.2 | E quem não tem foto cadastrada? | **Bloqueia** — e a coordenação ganha um fluxo de cadastro de foto |

## 14.2 · ⚠️ O que a decisão 14.1.1 custa — e por que precisa estar escrito

Verificar no celular do aluno protege **menos** do que verificar no balcão, e a
diferença não é teórica:

1. **O cliente é do usuário.** Um app adulterado posta a imagem que quiser no
   endpoint. Sem liveness e sem *attestation*, a verificação no celular é uma
   barreira de conveniência, não de segurança.
2. **Verificar quem gera não é verificar quem retira.** Nada impede o aluno
   verificado passar o celular (ou o print, dentro dos 2 minutos) para outra
   pessoa levar a refeição.
3. **Sem liveness, foto de foto passa.** Uma imagem na tela de outro celular
   apontada para a câmera tende a ser aceita pelo `CompareFaces`.

Duas coisas baratas encolhem a fresta sem mudar a decisão, e entram no plano:

* **o token de 2 minutos vira o principal aliado** — ele já força a verificação
  a acontecer quase no balcão, e não às 7 da manhã;
* **a tela da cantina mostra a foto cadastrada do aluno na confirmação**, ao
  lado do nome. Quem serve olha para a pessoa de qualquer jeito; ver a foto
  fecha, com olho humano, exatamente o buraco que o liveness fecharia com
  máquina. ⚠️ Isso é exposição nova de imagem de menor para a copa — precisa de
  decisão consciente, e é a alternativa mais barata que existe aqui.

## 14.3 · ⚠️ LGPD — o degrau mais alto do projeto

Biometria de menor de idade é **dado pessoal sensível** (LGPD art. 11), e o SAS
nunca tratou nada nessa categoria: a restrição alimentar foi chamada de "a
primeira informação de saúde do produto" (docs/38 §2.6) e é um degrau abaixo
disto. Três requisitos que **não são zelo, são parte da entrega**:

1. **Base legal e consentimento específico dos responsáveis**, registrado —
   não derivado do aceite geral de uso da plataforma. Quem responde por isso é
   a escola, não a engenharia; sem isso, a fase não sobe.
2. **A imagem batida na hora não é armazenada.** Compara e descarta. Ficam
   apenas resultado, escore e carimbo de tempo em `evento_auditoria` — nunca a
   imagem, nunca o vetor facial.
3. **Desligável sem deploy**: `cantina.exige_face_presencial boolean` (coluna,
   como os `aceita_*` da fase 1 — é configuração, não *feature flag*). Se
   houver questionamento jurídico, a escola desliga na hora.

## 14.4 · Fluxo

```
aluno toca "Pegar pessoalmente"
   └─ front abre a câmera (getUserMedia) e captura UM frame
       └─ POST /me/cantina/retiradas/{id}  { imagem: <frame> }
           ├─ backend busca a foto cadastrada (aluno.foto_perfil_storage)
           │   └─ sem foto → 422 "procure a coordenação" (14.1.2)
           ├─ Rekognition CompareFaces(referência, frame)
           │   ├─ Similarity < limiar → 422, permite tentar de novo (N vezes)
           │   └─ ≥ limiar → grava a linha presencial e emite o token
           └─ descarta o frame em memória — nada vai para o Storage
```

⚠️ **Nunca `<input type="file">`, nem com `capture`** — `capture` é dica ao
sistema, não trava. O caminho é `getUserMedia` + `canvas.drawImage` do frame do
vídeo. E o servidor não confia no cliente: quem compara é o backend, sempre.

## 14.5 · Schema e configuração — migration 0057

```sql
ALTER TABLE cantina ADD COLUMN exige_face_presencial boolean NOT NULL DEFAULT false;

CREATE TABLE consentimento_biometria (
    aluno_id     uuid PRIMARY KEY REFERENCES aluno(id),
    registrado_por uuid NOT NULL REFERENCES usuario_coordenacao(id),
    criado_em    timestamptz NOT NULL DEFAULT now(),
    revogado_em  timestamptz
);
-- Sem consentimento vigente, a comparação não roda — e o aluno cai no mesmo
-- caminho de quem não tem foto (14.1.2). Revogar é `revogado_em`, não DELETE:
-- provar que houve consentimento em determinada data é o ponto da tabela.
```

Envs novas: região e credencial do Rekognition (a AWS já está na stack por SES
e S3), e o limiar como configuração, não literal no código.

## 14.6 · Plano de implementação da Fase 4

1. **Antes de tudo**: consentimento e base legal resolvidos com a escola
   (§14.3.1). Este passo não é de código e bloqueia os outros.
2. **Migration 0057** + `restart postgrest`.
3. **Cadastro de foto pela coordenação** — pré-requisito da 14.1.2, e mutirão
   antes de ligar: sem foto, ninguém retira.
4. **Backend**: `CompareFaces` atrás de uma função própria (testável com
   mock), o ramo novo no `POST /me/cantina/retiradas/{id}`, auditoria sem
   imagem, teto de tentativas.
5. **Front do aluno**: captura por `getUserMedia`, tratamento de permissão
   negada, tentativas e o desfecho "procure a coordenação".
6. **Front da cantina**: a foto cadastrada na confirmação (§14.2), se a decisão
   da escola permitir.
7. **Portões** + browser real com câmera — aqui não há como deduzir do TSX.

## 14.7 · Em aberto na fase 4

* **Limiar de similaridade e número de tentativas.** Proposta: 90% e três
  tentativas, depois cai para a coordenação. Precisa de calibração com fotos
  reais — foto de cadastro antiga de adolescente envelhece rápido.
* **Custo.** `CompareFaces` é da ordem de US$ 0,001 por chamada; 900 alunos × 2
  refeições × 200 dias ≈ 360 mil chamadas/ano ≈ US$ 360/ano. Pequeno, mas o
  projeto já levou um susto de US$ 379 numa hora com LLM (api/CLAUDE.md): o
  teto entra no desenho, não depois.
* **Foto cadastrada desatualizada** — quem re-tira? Se o aluno mudou de visual,
  ele fica travado no balcão até alguém trocar a foto.

---

## 15 · Fora de escopo nas quatro fases

* Confirmação de retirada para quem **pediu** — o `retirado_em` da fase 1 é só
  do modo presencial. É o item que docs/38 §8.1.3 já deixava aberto.
* Cobrar diferente por modo: `valor_almoco`/`valor_janta` (docs/38 §8.2) não
  distinguem modo, e presencial soma no mesmo total de tabela.
* Teto de "quantos presenciais por dia" — não foi pedido; entraria como mais
  uma regra de cantina se aparecer.
