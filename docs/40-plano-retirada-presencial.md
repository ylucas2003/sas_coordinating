# 40 — Retirada presencial · pegar a refeição sem ter pedido

> Três fases. A **1** está em implementação; a **2** e a **3** têm plano
> escrito e nenhuma linha de código.
>
> | Fase | O quê | Estado |
> |---|---|---|
> | **1** | Retirada presencial por QR Code | **Em implementação** (§1 a §11) |
> | **2** | Janela de horário para a leitura, com liberação avulsa | Planejada (§12) |
> | **3** | Reconhecimento facial antes de gerar o QR | Planejada (§13) |
>
> As três fases são independentes no schema: a 2 e a 3 acrescentam, nenhuma
> reescreve o que a anterior fez.

## 0 · Em uma frase

Hoje só existe um jeito de comer: pedir com antecedência, dentro do prazo
([docs/38](38-plano-cantina.md)). A fase 1 acrescenta um segundo jeito —
**chegar, mostrar um QR Code gerado na hora, e a cantina lê** — e deixa a
critério de cada cantina quais dos dois jeitos valem para cada refeição.

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
-- continua fora de escopo (§14).

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
Fase 2. Por isso a Fase 2 é a **0053** (§12.3) e a Fase 3 é a **0054** (§13.5).
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
| 10.2 | Presencial tem prazo (janela de horário)? | **Não na fase 1.** Vale enquanto o cardápio estiver publicado. A janela é a fase 2 (§12) |
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

# FASE 2 — a janela de retirada

## 12.1 · O que foi pedido

A leitura do QR passa a valer **só dentro de um intervalo de horário**, e o
intervalo é **da coordenação**, não da cantina. É uma grade **semanal fixa**: o
horário de todas as segundas, de todas as terças, de todos os sábados — não
data a data. Fora do intervalo, a coordenação tem, na tela de administração dos
alunos da cantina, um botão **"liberar o aluno"** que destrava aquela retirada.

## 12.2 · Decisões fechadas em 07/09

| # | Pergunta | Resposta |
|---|---|---|
| 12.2.1 | Dia da semana sem janela cadastrada significa o quê? | **Sem retirada** — fail-closed. A ausência de regra não é permissão |
| 12.2.2 | Quem clica em "liberar o aluno"? | **Qualquer coordenador.** A janela é sobre horário, não sobre direito — o aluno já tem a refeição garantida, e travar isso no administrador põe fila de menor esperando alguém aparecer |

⚠️ A 12.2.1 tem uma consequência que precisa de conserto no mesmo passo: **no
instante em que a fase 2 sobe, a fase 1 para de funcionar** se não houver grade
cadastrada. A migration nasce, por isso, **semeando a grade com o que já vale
hoje** — 00:00 às 23:59, todos os sete dias, nas duas refeições, para cada
cantina existente. Não é inventar política: é continuidade, e deixa a
coordenação estreitar deliberadamente em vez de descobrir o bloqueio pelo
aluno que ficou sem almoço.

## 12.3 · Schema — migration 0053

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
-- presencial naquele dia (§12.2.1) — a ausência de regra é recusa, não
-- permissão, e é por isso que a migration semeia (§12.2).

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

## 12.4 · Onde a regra é aplicada

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

## 12.5 · Rotas

| Rota | Guard | O quê |
|---|---|---|
| `GET /administracao/cantina/janelas` | `get_current_coordenador` | A grade 7 × 2 |
| `PUT /administracao/cantina/janelas` | **`get_current_administrador`** | Grava a grade inteira (é política da casa) |
| `POST /administracao/cantina/liberacoes` | `get_current_coordenador` | Libera um aluno num cardápio (§12.2.2) |
| `DELETE /administracao/cantina/liberacoes/{id}` | `get_current_coordenador` | Desfaz — errar o aluno na pressa da fila é previsível |

Toda liberação vai para `evento_auditoria`, canal `cantina`
(`retirada_liberada` / `retirada_liberacao_desfeita`), com o coordenador como
autor: é o ato de furar a própria regra, e sem autor e hora ninguém consegue
responder "quem liberou?".

## 12.6 · Telas

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

## 12.7 · Plano de implementação da Fase 2

1. **Migration 0053** + `.down.sql` + a semeadura do §12.2 + `restart postgrest`.
2. **Backend**: a checagem nos dois pontos do §12.4, as quatro rotas do §12.5,
   auditoria. *Testes: dentro/fora da janela, virada de meia-noite, dia sem
   linha (recusa), liberação vale, liberação de outro cardápio não vale,
   liberação desfeita volta a recusar.*
3. **Front da coordenação**: grade + botão liberar.
4. **Front do aluno e da cantina**: os textos de janela e o estado novo de
   leitura.
5. **Portões** de sempre, browser incluído.

## 12.8 · Em aberto na fase 2

* **A janela é por cantina ou da escola?** O schema põe em `cantina` por
  consistência; com uma cantina só, dá no mesmo hoje.
* **Feriado dentro da grade semanal.** A grade não conhece calendário: numa
  terça de feriado ela continua "aberta". Hoje isso é coberto de lado, porque
  sem cardápio publicado não há o que retirar — mas se um dia alguém publicar
  cardápio em feriado, a janela não vai discordar.

---

# FASE 3 — reconhecimento facial

## 13.1 · O que foi pedido, e o que ficou decidido

Nem o pedido nem o QR saem sem o aluno **passar por comparação facial**: a foto
cadastrada dele contra uma batida **na hora**, via AWS Rekognition
`CompareFaces`, **sem liveness**. E com travamento contra **carregar** imagem —
tem de fotografar no momento.

| # | Pergunta | Resposta em 07/09 |
|---|---|---|
| 13.1.1 | Onde a verificação acontece? | **No celular do aluno, ao gerar o QR** |
| 13.1.2 | E quem não tem foto cadastrada? | **Bloqueia** — e a coordenação ganha um fluxo de cadastro de foto |

## 13.2 · ⚠️ O que a decisão 13.1.1 custa — e por que precisa estar escrito

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

## 13.3 · ⚠️ LGPD — o degrau mais alto do projeto

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

## 13.4 · Fluxo

```
aluno toca "Pegar pessoalmente"
   └─ front abre a câmera (getUserMedia) e captura UM frame
       └─ POST /me/cantina/retiradas/{id}  { imagem: <frame> }
           ├─ backend busca a foto cadastrada (aluno.foto_perfil_storage)
           │   └─ sem foto → 422 "procure a coordenação" (13.1.2)
           ├─ Rekognition CompareFaces(referência, frame)
           │   ├─ Similarity < limiar → 422, permite tentar de novo (N vezes)
           │   └─ ≥ limiar → grava a linha presencial e emite o token
           └─ descarta o frame em memória — nada vai para o Storage
```

⚠️ **Nunca `<input type="file">`, nem com `capture`** — `capture` é dica ao
sistema, não trava. O caminho é `getUserMedia` + `canvas.drawImage` do frame do
vídeo. E o servidor não confia no cliente: quem compara é o backend, sempre.

## 13.5 · Schema e configuração — migration 0054

```sql
ALTER TABLE cantina ADD COLUMN exige_face_presencial boolean NOT NULL DEFAULT false;

CREATE TABLE consentimento_biometria (
    aluno_id     uuid PRIMARY KEY REFERENCES aluno(id),
    registrado_por uuid NOT NULL REFERENCES usuario_coordenacao(id),
    criado_em    timestamptz NOT NULL DEFAULT now(),
    revogado_em  timestamptz
);
-- Sem consentimento vigente, a comparação não roda — e o aluno cai no mesmo
-- caminho de quem não tem foto (13.1.2). Revogar é `revogado_em`, não DELETE:
-- provar que houve consentimento em determinada data é o ponto da tabela.
```

Envs novas: região e credencial do Rekognition (a AWS já está na stack por SES
e S3), e o limiar como configuração, não literal no código.

## 13.6 · Plano de implementação da Fase 3

1. **Antes de tudo**: consentimento e base legal resolvidos com a escola
   (§13.3.1). Este passo não é de código e bloqueia os outros.
2. **Migration 0054** + `restart postgrest`.
3. **Cadastro de foto pela coordenação** — pré-requisito da 13.1.2, e mutirão
   antes de ligar: sem foto, ninguém retira.
4. **Backend**: `CompareFaces` atrás de uma função própria (testável com
   mock), o ramo novo no `POST /me/cantina/retiradas/{id}`, auditoria sem
   imagem, teto de tentativas.
5. **Front do aluno**: captura por `getUserMedia`, tratamento de permissão
   negada, tentativas e o desfecho "procure a coordenação".
6. **Front da cantina**: a foto cadastrada na confirmação (§13.2), se a decisão
   da escola permitir.
7. **Portões** + browser real com câmera — aqui não há como deduzir do TSX.

## 13.7 · Em aberto na fase 3

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

## 14 · Fora de escopo nas três fases

* Confirmação de retirada para quem **pediu** — o `retirado_em` da fase 1 é só
  do modo presencial. É o item que docs/38 §8.1.3 já deixava aberto.
* Cobrar diferente por modo: `valor_almoco`/`valor_janta` (docs/38 §8.2) não
  distinguem modo, e presencial soma no mesmo total de tabela.
* Teto de "quantos presenciais por dia" — não foi pedido; entraria como mais
  uma regra de cantina se aparecer.
