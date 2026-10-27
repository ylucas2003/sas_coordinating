# 43 — As ferramentas do assistente e o MCP da coordenação

> Plano de 24/10/2026, com o **estado de 26/10**. Duas frentes que dividem uma
> fundação:
>
> 1. o **Tio Léo** (aluno, individual) e o **assistente da coordenação**
>    (coletivo) passam a ler a plataforma inteira, cada um no seu escopo, e
>    respondem mais rápido;
> 2. um **MCP** para a coordenação conectar a própria IA ao SAS.
>
> ⚠️ **Estado em 26/10: as Fases 0 a 3 estão escritas e testadas, e NADA delas
> está em produção.** Tudo mora no branch `feat/ferramentas-registro-unico`,
> ainda sem commit, testado local e em stacks descartáveis de Postgres 16 +
> PostgREST v12.2.3. O MCP não vai ao ar antes do portão de LGPD (§5.4). As
> **decisões do dono de 26/10** — nome real no MCP, administrador e
> coordenador conectando, aprovação por código no e-mail da conta de IA e o
> nome de cada nota contra o corte — já estão no código e moram em §0.1; a
> **revisão de segurança** que elas passaram na mesma tarde, com o que foi
> consertado e o que ficou de propósito, em §5.6. O que cada fase entregou
> está em §3.4, §4.4 e §5.5; o que mudou em relação a este plano, em §7.1; o
> que não foi verificado, em §8; a ordem do deploy, em §9; e o que a produção
> precisa para o MCP — nada disso aplicado —, em §10.
>
> Uma peça daqui JÁ está no ar, por fora do branch: o **piso de anonimato das
> rotas `/me`** (§4.4, "Privacidade"), levado sozinho pelo PR #114 (merge
> `fc461a2`) e implantado em 26/10 — o docs/19 conta como foi conferido.
>
> ⚠️ **Base e numeração (26/10)**: o `main` ganhou em 24/10 outra migration
> `0069`, já em produção, e outro `docs/42` (o horário de estudos) — por isso
> este plano, que nasceu 42, é o 43 desde 27/10. O branch foi reposto em cima dele,
> e as migrations daqui, que nasceram 0069 a 0072 — a primeira seria pulada sem
> erro pelo runner —, passaram a 0070 a 0073. O começo da §9 conta o que mudou.
>
> O modelo de referência é o MCP do produto da Solomon (`~/solomon-mcp`,
> TypeScript), em especial `docs/security-context/ARQUITETURA.md` de lá. Não é
> dependência: é de onde vieram os padrões da §2.

---

## 0 · Decisões tomadas em 24/10

| Decisão | Escolha |
|---|---|
| Quem conecta uma IA ao MCP | **A coordenação.** Não os alunos, e não só o dev |
| Por onde começar | **Fundação comum** (§3) → Tio Léo e assistente (§4) → MCP (§5) |

E as de desenho, fixadas em 24/10 ao abrir as Fases 2 e 3. A coluna da direita
diz como cada uma está no código em 26/10:

| Decisão | Escolha | No código |
|---|---|---|
| Por onde o MCP lê o banco | PostgREST **próprio** (`postgrest_mcp`), papel anônimo `sas_mcp`, sem `PGRST_JWT_SECRET` | ✅ — e com login próprio, o `autenticador_mcp`, que entrou depois da revisão de 24/10 (§7.1) |
| O token | **opaco**, `sas_mcp_` + `secrets.token_urlsafe(32)`, guardado só como sha256 | ✅ `app/mcp/tokens.py`, migration 0072 |
| Quem emite token e aprova conexão | **só o administrador** enquanto o portão da §5.4 está aberto (`MCP_EMISSAO_SO_ADMINISTRADOR=true`) | **Trocada pelo dono em 26/10** (§0.1, decisão 2): administrador e coordenador, cada um em nome da própria conta, e a chave passou a ter padrão `false`. Ligada, o "só o administrador" volta a valer para emitir, aprovar **e usar** (§5.3) |
| Nome ou matrícula do aluno | **matrícula** por padrão (`MCP_MOSTRAR_NOME_DO_ALUNO=false`) | **Trocada pelo dono em 26/10** (§0.1, decisão 1): o nome, com padrão `true`; o pseudônimo fica como opção de configuração |
| O que o MCP expõe | só as tools marcadas `expor_no_mcp` | ✅ 31 das 42 da coordenação; 29 com o pseudônimo ligado (§5.5) |
| Onde mora o authorization server | **na API**; o consentimento é rota React da coordenação | ✅ `app/routes/oauth_mcp.py` e `/conectar-ia` — que desde 26/10 é rota React **pública**, sem sessão: aprova quem digita o código enviado ao e-mail da conta de IA (§0.1, decisão 3; §5.3) |
| Numeração | uma migration por peça, na sequência do `main`: artefato do chat, papéis, token, OAuth | ✅ **0070** artefato do chat, **0071** papéis, **0072** token, **0073** OAuth — nasceram 0069 a 0072 e foram renumeradas em 26/10, porque o `main` ganhou em 24/10 uma `0069_bloco_horario_estudo`, já em produção (§9) |

### 0.1 · As decisões do dono em 26/10 — já no código

Tomadas depois das provas da manhã de 26/10 e implementadas na mesma tarde.
Não se reabrem; o que cada uma ainda pede está escrito nela e na §6.

| # | Decisão | Como ficou no código |
|---|---|---|
| 1 | **O MCP devolve o NOME real do aluno**, não a matrícula. O pseudônimo continua como opção de configuração. Com o nome liberado, entram no MCP as duas tools que só estavam fora por causa dele, `buscar_aluno_por_nome` e `listar_alertas`; `gerar_grafico`, `exportar_csv` e `navegar_para` continuam fora (são artefato de UI, sem uso fora do app). Os tetos de minimização continuam | `MCP_MOSTRAR_NOME_DO_ALUNO` com padrão `true` (`api/app/mcp/configuracao.py`, com a decisão e o art. 14 no comentário). Com o nome, o portão do pseudônimo não roda e o cadastro de alunos nem é lido (`servidor._despachar`); as `instructions` deixam de falar em matrícula e lembram que são adolescentes (`servidor.instrucoes`). As duas tools ganharam `expor_no_mcp` nos `METADADOS` de `chat/tools/lookup.py` e `chat/tools/contexto.py`, e a 0071 ganhou `SELECT` por coluna em `alerta` — sem `dados_brutos`, `hash_dedup` nem `resolvido_em`. Com o pseudônimo ligado, as duas saem do catálogo (`catalogo.SO_COM_NOME_DO_ALUNO`): a busca entregaria ao provedor o par nome ↔ matrícula, e o título do alerta, que traz o nome, seria recusado sempre |
| 2 | **Quem conecta: administrador E coordenador**, cada um em nome da própria conta. O administrador continua vendo e revogando todas as conexões | `MCP_EMISSAO_SO_ADMINISTRADOR` com padrão `false`, lido pela API (`routes/mcp_tokens.py`, `routes/oauth_mcp.py`), pelo MCP (`servidor._pode_consultar`) e por `scripts/criar_token_mcp.py`. O "só o administrador" segue como opção testada, e precisa do MESMO valor na API e no `mcp`. `GET /mcp/disponibilidade` não mudou de forma: só o padrão de `emissaoSoAdministrador` virou `false` |
| 3 | **A conta de IA se prova pelo e-mail.** No card de Conexões de IA o coordenador cadastra o e-mail da conta de IA dele — pode não ser o do SAS, pode ser mais de um. A conexão OAuth (claude.ai, ChatGPT) só é aprovada por um **código enviado a esse e-mail**, pelo SES que o motor de lembretes já usa: quem digita o código aprova, e a conexão nasce com o acesso do coordenador dono do e-mail. Aprovar **não exige sessão do SAS** — os dois conectores não dizem de quem é a conta, e a posse do e-mail é a prova. O token pessoal (Claude Code, Claude Desktop) continua emitido pelo coordenador logado, no card | O fluxo inteiro está na §5.3 ("A aprovação pelo e-mail da conta de IA"). Desde a revisão de segurança da mesma tarde (§5.6), o CADASTRO também prova a posse: o e-mail nasce aguardando e só aprova depois que quem o cadastrou digita, no card, o código que chegou a ele. Domínio puro em `api/app/mcp/emails_ia.py`; o card em `api/app/routes/mcp_emails_ia.py`; o consentimento sem sessão em `api/app/routes/oauth_mcp.py`; as tabelas `email_conta_ia_mcp` e `oauth_codigo_por_email_mcp` na 0073; as telas em `web/src/telas/Administracao/ConexoesDeIa.tsx` (seção "E-mails da sua IA") e `web/src/telas/ConectarIa/ConectarIa.tsx`, que virou página pública |
| 4 | **Nota × corte, na área do aluno: as duas notas ficam, cada uma com o nome do que é.** A da Hoje é a do último simulado (a nota do ciclo mais recente); a do Tio Léo e a de `/me/zona` é a que conta na régua. Nada muda no cálculo; muda o rótulo, para não parecer contradição | `web/src/dominio/notaContraCorte.ts` (`notasContraCorte`, `LEGENDA_DAS_NOTAS`, com teste ao lado), e `BarraCorte` ganhou a prop `notas`. Na Hoje, "Notas no último simulado"; no cartão `barras_corte` do Tio Léo, "Notas que contam na régua"; na zona, "Na régua X, a média que conta é Y…". Se a evolução não vem, as barras caem na nota da régua, e o rótulo acompanha |

⚠️ **A decisão 1 foi do dono, contra a recomendação do plano** — a matrícula,
escolhida em 24/10 (a linha "Nome ou matrícula" da tabela de cima) junto com o
levantamento de LGPD daquele dia, que só expunha ao MCP as tools que leem
aluno com o pseudônimo na frente. Nome de aluno é dado de adolescente indo a
um provedor de IA de fora da escola, e pede a **base legal do art. 14 da
LGPD** (tratamento no melhor interesse do adolescente), registrada antes de o
MCP subir em produção. O código diz isso no comentário de
`mostrar_nome_do_aluno`, e o portão continua sendo o `MCP_HABILITADO` (§5.4):
fora de dev/test, o processo não sobe sem ele.

---

## 1 · O estado de partida (levantado em 24/10)

> Retrato de ANTES das fases, mantido como registro. O que mudou está em §3.4,
> §4.4 e §5.5.

**Dois despachantes sem nada em comum.** `tools.executar` serve a coordenação e
`tools_aluno.executar_para_aluno` o aluno. Nenhum dos dois tem timeout,
proteção contra chamada repetida ou instrumentação, e os dois devolvem o texto
cru da exceção ao modelo. Uma terceira superfície (o MCP) seria a terceira
cópia.

**Cobertura.** O aluno tem 6 tools para 14 rotas `/me`: ficam de fora zona,
meta, agenda, heatmap, trajetória e vestibulares, e nada do banco do aluno
(progresso, importância, missão, listas). A coordenação tem 30 tools em quatro
domínios (alunos, simulados, ciclos, alertas), e nenhuma toca banco de
questões, régua, captação, cantina, sync do Canvas, gravações, auditoria ou
lembretes.

**Desempenho.** As tools de uma volta rodam em série (`agente.py`), a resposta
não é streaming de verdade (`stream=False`) e uma pergunta típica do aluno faz
pelo menos duas voltas ao modelo (`minhas_notas` → detalhe). Nenhum dos dois
prompts tem a data de hoje.

**Defeitos achados na revisão de 24/10** (entram na Fase 1):

1. `prompt_aluno.py` define streak pela métrica que saiu em 05/09 — contradiz
   a tool `meu_streak`;
2. `historico[-30:]` em `agente.py` pode começar numa mensagem `tool` órfã, e a
   OpenAI recusa a chamada (inferido do formato da API; não reproduzido);
3. a folha do Tio Léo promete "o que mais cai nas provas", que nenhuma tool
   entrega;
4. o erro cru da OpenAI (`falha chamando o modelo: {e}`) vai para a tela de um
   menor e para o banco;
5. o resultado de tool é cortado em 60 mil caracteres no meio do JSON;
6. `ArtefatoAluno.tsx` (547 linhas) não é importado por ninguém, e nenhuma tool
   do aluno produz artefato (docs/27 §7).

---

## 2 · O que se aprende com o Solomon

| Padrão de lá | Aqui |
|---|---|
| Um ponto de passagem para toda chamada de tool (`runToolCall`): tenant, gating, rate, disjuntor, timeout, instrumentação | **Adotar** — é a §3 |
| O tenant vem da sessão e **sobrescreve** o argumento (a invariante P1.7 deles) | **Já existia** para o aluno (`aluno_id` do JWT); vira regra do registro |
| Catálogo filtrado por superfície e rebloqueado na chamada (*double gate*) | **Adotar** — escopo aluno × coordenação |
| Erro do provedor nunca cru para o cliente (`chat/providerFailure.ts`) | **Adotar** — defeito 4 |
| Compactação determinística do resultado (cabeça + cauda, sem LLM) | **Adaptar** para JSON — defeito 5 |
| Disjuntor de chamada idêntica repetida | **Adotar**, por volta de resposta |
| Descrição de tool em blocos: quando usar / confirme / definições / exemplo | **Adotado** na Fase 1, nas tools do aluno e nas 11 novas da coordenação. No aluno, `[m]` e `[d]` no lugar de número de exemplo, para o `gpt-4o-mini` não copiá-lo |
| MCP externo com catálogo enxuto e `instructions` mínimas | **Adotado** na Fase 2: 31 tools desde 26/10 (29 com o pseudônimo ligado) e um parágrafo de `instructions` (`servidor.instrucoes`) |
| Compatibilidade com ChatGPT e Claude: RFC 9728 em vários caminhos, JSON Schema 2020-12 sem tupla, `instructions` no `initialize`, `/register` completo (commit `664ccb6` de lá) | **Feito** na Fase 3: RFC 9728 em dois caminhos, `instructions` no `initialize`, `/register` completo e schema normalizado para cliente estrito (`catalogo.normalizar_schema`). ⚠️ Nenhum dos dois conectores foi testado de verdade (§8) |
| System prompt monolítico de ~575 linhas | **Não adotado.** Roteiros sob demanda (§4.3, §4.4) |
| SQL cru (`pg_query`) do MCP de debug | **Não entrou**: não há tool de SQL. Se entrar, só para administrador e só pelo papel de leitura (§5.2) |

---

## 3 · A fundação: um registro, duas superfícies *(Fase 0)*

Mora em `api/app/chat/ferramentas.py`. Três peças:

- **`Sessao`** — quem está do outro lado, montada do JWT por `sessao_do_token`.
  Fail-closed: aluno sem `aluno_id`, coordenação sem `sub`, cantina e qualquer
  tipo desconhecido são recusados. É a mesma regra de `_usuario_do_token`, que
  passa a derivar dela.
- **`Ferramenta`** — nome, descrição, parâmetros, **escopo** (`aluno` ou
  `coordenacao`), `somente_leitura`, `expor_no_mcp` e timeout.
- **`Registro`** — o catálogo por escopo e o **despacho único**.

### 3.1 · Os dois escopos

| | Aluno (individual) | Coordenação (coletivo) |
|---|---|---|
| Vê no catálogo | só as tools de escopo `aluno` | só as de escopo `coordenacao` |
| Identidade | `aluno_id` do JWT, injetado; o do argumento é descartado | `aluno_id` é argumento legítimo: escolhe QUEM olhar |
| Comparação | só com agregados da turma (docs/27 §9) | qualquer aluno — as oito contas leem a escola inteira, não há recorte por sede |

### 3.2 · As invariantes, na ordem em que o despacho as aplica

1. **Escopo.** Tool fora do escopo da sessão responde "não existe" — a mesma
   resposta de um nome inventado, para não confirmar que a tool existe.
2. **Identidade.** No escopo do aluno, `aluno_id` do argumento é descartado e
   o do token é injetado.
3. **Argumentos.** Chave fora do schema é descartada (o modelo inventa
   parâmetro, e recusar custa uma volta inteira); parâmetro obrigatório
   faltando volta como erro de argumento, que o modelo consegue corrigir.
4. **Repetição.** A mesma tool com os mesmos argumentos, já respondida com
   sucesso **na mesma resposta**, não roda de novo: o dado não mudou em
   segundos, e o loop de oito voltas é o que mais custa.
5. **Prazo.** Cada tool tem timeout (padrão 90 s, abaixo dos 300 s do nginx).
6. **Erro.** Exceção interna é registrada no log com o stack e chega ao modelo
   como mensagem genérica — texto de exceção pode carregar URL do PostgREST
   (docs/14 §5, a mesma regra de `observabilidade.py`).
7. **Tamanho.** Resultado grande encolhe as listas mais longas mantendo
   começo e fim, e diz o que omitiu. O JSON nunca sai quebrado.
8. **Registro.** Toda chamada vira uma linha de log com ferramenta, escopo,
   desfecho e duração; a compactação, quando acontece, grava uma linha própria
   com o tamanho antes e depois. É o dado que falta para calibrar os timeouts.

### 3.3 · Critério de pronto da Fase 0

- O comportamento visível do chat não muda, exceto pelas invariantes 3 a 7.
- Testes de isolamento: o aluno não alcança tool de coordenação nem pelo nome;
  o `aluno_id` do argumento é ignorado; a cantina não abre sessão.
- A suíte inteira do backend verde e o `ruff` limpo.

### 3.4 · O que a Fase 0 entregou *(24/10)*

- `api/app/chat/ferramentas.py` — `Sessao`, `Ferramenta`, `Volta`, `Registro`
  e `serializar_para_modelo`. As tools ficaram onde estavam; o registro as
  recolhe de `tools/*.TOOLS` e `tools_aluno.TOOLS`.
- `tools.executar` e `tools_aluno.executar_para_aluno` **saíram**: não sobrou
  caminho paralelo ao registro. `_usuario_do_token` (`rotas.py`) deriva da
  `Sessao`, e o perfil é escolhido por ela.
- `tests/test_chat_ferramentas.py` — 45 testes, uma classe por invariante,
  mais a higiene que a conversão de tipo exige (o tipo do schema bate com a
  anotação do handler nos 57 parâmetros das 36 tools). O
  de event loop (`test_desempenho_event_loop.py`) passou a exercitar a tool
  pelo caminho de verdade; antes ele chamava `asyncio.to_thread` direto e
  continuaria verde se o agente voltasse a rodar a tool dentro do loop.
- Suíte do backend: 833 passando, 15 pulados, `ruff` limpo. ⚠️ **Cinco
  falhas que já existiam** no `origin/main` de 24/10 e não vêm daqui —
  `test_canvas_publicacao.py` (3), `test_colecao_banco.py` (1) e
  `test_lembretes.py` (1). Conferido num checkout limpo.

---

## 4 · Tio Léo e o assistente *(Fase 1)*

### 4.1 · Corrigir os seis defeitos da §1

Na ordem: 1 e 2 (uma linha e um alinhamento de janela com teste), 4
(classificar a falha do provedor, como o `providerFailure.ts`), 3 (o texto da
folha passa a prometer só o que existe) e 6 (prop de renderizador de artefato
em `Conversa` e `Mensagem`, e tools que produzem os tipos do docs/27 §7). O 5
já sai na Fase 0.

### 4.2 · Desempenho

- **Contexto do turno montado do JWT, nunca do browser:** data de hoje, ciclo
  corrente, vestibular alvo, régua e próximo simulado. Corta voltas — o modelo
  deixa de chamar `minhas_notas` só para saber em que ciclo está. O preâmbulo
  que o browser manda continua desligado para o aluno (`rotas.py`).
- **Tools compostas** — `meu_panorama` devolve numa chamada o que hoje são três.
- **Tools em paralelo** dentro da volta. ⚠️ O cliente PostgREST cacheado
  multiplexa tudo numa conexão HTTP/2, e um GOAWAY derruba as outras streams
  (`supabase_client.py`): em paralelo, cada tool usa `criar_cliente_supabase()`.
- **Streaming de verdade** da resposta final.

### 4.3 · Cobertura e playbooks

**Aluno:** zona e distância, meta, agenda, trajetória, progresso no banco,
importância por tópico, missão do dia, questões do banco por tópico e a
**resolução oficial** (a mitigação do docs/27 §10).

**Coordenação:** banco de questões, a régua como objeto (o que corta, por qual
artigo), estado do sync do Canvas e das gravações, auditoria e lembretes.
Captação e cantina ficam para decidir (§6).

**Playbooks** em markdown curto, carregados sob demanda por uma tool, em vez de
crescer o system prompt. Aluno: revisar simulado, plano de estudo, explicar
questão. Coordenação: diagnóstico de ciclo, alunos em risco, preparo de
reunião. Os mesmos arquivos viram `prompts` do MCP.

### 4.4 · O que a Fase 1 entregou *(24 a 26/10, fora de produção)*

Caminhos relativos a `api/app/` quando não dizem o contrário.

**Os seis defeitos da §1**

| # | Como ficou | Onde |
|---|---|---|
| 1 | O prompt define sequência como presença (simulados seguidos sem faltar), a mesma conta de `meu_streak`, e diz que XP, liga, conquistas e extrato não existem | `chat/prompt_aluno.py` |
| 2 | `janela_do_historico` substitui o `historico[-30:]`: começa numa mensagem `user`, descarta `tool` órfã e tira o grupo assistant + tools a que falta resposta | `chat/agente.py` |
| 3 | A promessa da folha ficou e ganhou tool: `o_que_mais_cai` | `chat/tools_aluno_banco.py` |
| 4 | `classificar` dá o tipo da falha (saldo, credencial, configuração, limite, sobrecarga, prazo, rede, conversa longa, requisição, desconhecida) e um texto amigável. O motivo cru vai só para o log, e em ERROR com `[AÇÃO NECESSÁRIA]` quando é saldo, credencial ou configuração. Vale também para a falta de `OPENAI_API_KEY` e para as oito voltas esgotadas | `chat/falha_do_provedor.py` |
| 5 | Saiu na Fase 0 | `chat/ferramentas.py::serializar_para_modelo` |
| 6 | As tools do aluno anexam o cartão, o servidor o grava e a folha o desenha | "Cartões", abaixo |

**Desempenho**

| O quê | Como | Chave de ambiente |
|---|---|---|
| Contexto do turno | `chat/contexto_do_turno.py`. Os dois escopos recebem a data de hoje no horário da escola. O aluno recebe também os alvos, a régua em vigor com zona e distância, o próximo simulado e a sequência, montados só do `aluno_id` do JWT. O cache é por aluno: 120 s (abaixo da cadência de 5 min do sync), no máximo 1.024 alunos, e o PUT `/me/vestibulares` chama `esquecer`. Roda em `asyncio.to_thread`. Leitura que falha sai do texto sozinha; no pior caso sobra só a data | — |
| Tool composta | `meu_panorama`, sobre `stats/aluno_panorama.py::panorama_do_aluno`: 15 idas ao PostgREST, contra 32 das funções chamadas uma a uma (medido no fake). O preâmbulo com cache frio faz 14 | — |
| Tools em paralelo | Até 3 por resposta (`MAX_TOOLS_SIMULTANEAS`), cada uma com cliente PostgREST próprio, porque o cacheado multiplexa tudo numa conexão HTTP/2 (`supabase_client.py`). A vaga só volta quando a thread termina de fato, inclusive a abandonada pelo prazo (`ferramentas.RespostaDePrazo`) | `CHAT_TOOLS_EM_PARALELO` (padrão `true`) |
| Streaming de verdade | `stream=True`, lido numa thread própria (`agente._LeitorDoStream`); o token sai a cada pedaço. Com a chave desligada, volta a resposta inteira picada em 40 caracteres | `CHAT_STREAMING` (padrão `true`) |
| Modelo do Tio Léo | Deixou de ser constante em `perfis.py` | `OPENAI_MODELO_ALUNO` (padrão `gpt-4o-mini`) |

As três chaves estão em `config.py` e **ainda não estão no `api/.env.example`
nem no `infra/vps/.env.example`**.

**Cobertura: 59 tools no registro, 17 do aluno e 42 da coordenação**

| Escopo | Módulo | Tools |
|---|---|---|
| aluno | `chat/tools_aluno.py` (as de antes, e a porta única que o registro recolhe) | `minhas_notas`, `meu_desempenho_em_simulado` (agora com o cartão `prova`), `minha_evolucao`, `meu_streak`, `minhas_questoes_erradas`, `meu_insight_do_ciclo` |
| aluno | `chat/tools_aluno_situacao.py` | `meu_panorama`, `minha_zona`, `minha_agenda_do_ciclo`, `minha_trajetoria`, `distribuicao_do_simulado` |
| aluno | `chat/tools_aluno_banco.py` | `o_que_mais_cai`, `missao_de_hoje`, `questoes_do_banco`, `resolucao_oficial`, `meu_progresso_no_banco` |
| coordenação | `chat/tools/banco_questoes.py` | `topicos_do_edital`, `buscar_questoes_do_banco`, `recorrencia_no_banco` |
| coordenação | `chat/tools/reguas.py` | `reguas_de_corte`, `cortados_pela_regua` |
| coordenação | `chat/tools/rotinas.py` | `estado_do_sync_canvas`, `pendencias_canvas_do_ciclo`, `estado_das_gravacoes`, `lembretes_agendados` |
| coordenação | `chat/tools/trilha.py` | `historico_de_alteracoes` |
| coordenação | `chat/tools/lookup.py` | `buscar_aluno_por_matricula`, mais as de antes |
| os dois | `chat/roteiros.py` | `roteiro_do_mentor` (aluno) e `roteiro_da_coordenacao` |

Além das 11 novas, a coordenação tem as 30 de antes. Nenhuma tool nova copia
regra: todas compõem funções de domínio, e as que não existiam foram tiradas
das rotas antes (os pré-requisitos, abaixo).

- **`METADADOS` por módulo** (`ferramentas.py`): um dict opcional com
  `prazo_s` (de 0 a 300 s, o corte do nginx) e `expor_no_mcp`. Chave
  desconhecida, nome que não é tool do módulo, tipo errado ou `expor_no_mcp`
  numa tool do aluno fazem o import falhar com `ValueError`. Hoje só
  `cortados_pela_regua` tem prazo próprio (150 s); as outras ficam nos 90 s.
- **Tetos no handler**, escritos na descrição como "até N":
  `buscar_aluno_por_nome` 20, `notas_simulado` 100, `alunos_em_risco` e
  `alunos_destaque` 50, `listar_alunos` 100, `alunos_similares` 20, a
  trajetória 100. `listar_alunos` perdeu o `.limit(500)` da leitura, que
  deixava `total` e a ordem errados com ~900 alunos. No MCP, um segundo teto
  de 50 vale para todo parâmetro de limite (§5.3).
- **Ficaram de fora, por ordem expressa da rodada**: `minhas_listas`
  (aluno) e `simular_regua` (coordenação). Ver §7.1.

**Roteiros**: 8 arquivos em `chat/roteiros/<escopo>/<nome>.md`, carregados
sob demanda pelas duas tools acima, em vez de crescer o prompt. Do aluno:
`antes_da_prova`, `explicar_questao`, `plano_da_semana` e `revisar_simulado`.
Da coordenação: `alunos_em_risco`, `conferir_a_regua`, `diagnostico_do_ciclo`
e `preparar_reuniao`, que são também os `prompts` do MCP (§5.5). Pasta vazia ou
arquivo malformado impedem a API de subir.

**Cartões (o defeito 6)**

- O catálogo é FECHADO e tem duas pontas que precisam bater:
  `ferramentas.TIPOS_DE_ARTEFATO` no servidor — aluno: `barras_corte`,
  `questao`, `lista_questoes`, `prova`, `linha_temporal`, `histograma`;
  coordenação: `histograma`, `linha_temporal`, `csv`, `navegacao` — e
  `CATALOGO_DE_ARTEFATOS` em `web/src/dominio/chatStream.ts`. Um teste de cada
  lado confere o do aluno.
- A tool devolve o cartão no campo **aninhado** `artefato: {tipo, titulo?,
  payload}`, nunca com `tipo` no topo. `csv` e `navegacao` só nascem das tools
  próprias (`exportar_csv`, `navegar_para`). O modelo recebe no lugar só
  `{tipo, anexado}`, para não redesenhar o cartão em texto.
- O servidor grava em `chat_artefato`, no catálogo do escopo da sessão,
  com cada INSERT isolado (`rotas._talvez_salvar_artefato`): um cartão que falha
  não leva mais a resposta junto. A migration **0070** amplia o CHECK da 0038
  para os quatro tipos novos.
- Questão e prova vêm por id das rotas que já existem: do payload sai só o
  identificador. Detalhes de cada tipo no docs/27 §7.
- No front: a prop `renderArtefato` em `Conversa` e `Mensagem`, o
  `ArtefatoAluno` passado pela `FolhaTioLeo`, e `artefatosNaResposta`
  aplicado pela própria `Conversa`, nos dois cascos (web/CLAUDE.md).

**Pré-requisitos de domínio**: regra que as tools precisavam e que morava
dentro de rota. O comportamento HTTP ficou igual, salvo os acréscimos
listados abaixo.

| Regra | Agora em |
|---|---|
| "tópico exige matéria" e o estudo do aluno na página | `banco/consultas.py::validar_filtros`, `FiltroInvalido`, `anexar_estudo_do_aluno` |
| descrever uma régua; as matérias conhecidas; "não consegui ler as réguas criadas" | `stats/criterios.py::descrever_criterio`, `MATERIAS_CONHECIDAS`; `stats/criterios_repo.py::listar_com_estado` |
| pendências do Canvas por ciclo | `canvas_sync/pendencias.py::pendencias_do_ciclo` |
| o sync está atrasado? | `canvas_sync/estado.py::ultimo_sync` (o `/health/ready` também usa) |
| o painel das gravações e a situação de cada aula | `gravacoes_aula/consulta.py::painel`, `situacao_de`; as regras da rodada em `gravacoes_aula/regras_da_rodada.py` |
| consultar a trilha e dar nome aos atores | `auditoria.py::consultar`, `nomes_dos_atores` |
| texto de erro sem URL nem credencial | `texto_seguro.py::texto_seguro` |
| a trajetória do aluno (eram três cópias) | `stats/aluno_dados.py::trajetoria_do_aluno` |

`despachante.filtro_ts`, `despachante.enviados_nas_ultimas_24h` e
`criterios_repo.RE_SLUG` viraram públicos, e `TestAcoplamento` (em
`tests/test_chat_tools_coordenacao.py`) prova que `app.chat.tools` não importa
rota nem o pipeline de vídeo.

**Privacidade**

- **Piso de anonimato no domínio** (`stats/aluno_dados.py`,
  `PISO_DE_ANONIMATO = 10` e `MINIMO_DO_GRUPO_DE_15 = 3`). Com menos de 10 notas
  na prova, nenhum número da turma sai para o aluno: nem média, nem grupo de
  15%, nem posição, nem percentil, nem distribuição, nem o tempo médio de prova.
  O grupo de 15% só sai com ao menos 3 pessoas, o que pede 20 notas. Vale nas
  rotas `/me` e nas tools, e `test_as_tools_nao_reaplicam_o_piso` impede
  cópia dele nas tools. O limite conhecido (o ataque de diferença) está
  escrito junto da constante e no §6. **Este item já está no ar**: o PR #114
  (`3b9cb62`, merge `fc461a2`) levou SÓ o piso a produção em 26/10 — nada do
  zero não computável, do `deltaSelf`, de campo novo, do prompt do insight, do
  chat ou do MCP (a mensagem do commit diz isso) —, com
  `tests/test_piso_de_anonimato.py`.
- **O zero não computável** (`aluno_dados.conta_como_desempenho`): a nota
  com `computavel = false`, ou de prova marcada como não confiável, fica na
  lista com a marca, sem `deltaSelf` e fora da base do delta das outras.
  `meu_panorama` e `minhas_notas` a põem em `naoContam`, com o motivo em
  palavras e sem o número.
- **O cache do insight** (`stats/insight_aluno.py::_chave_do_cache`) passou a
  ter o prompt na chave: bullets gerados pelo prompt antigo, que cravava 4,0 e
  5,0 e a sequência velha, deixam de ser servidos.
- **Coordenação**: `listar_alertas` filtra pelos valores que o banco grava
  (`vermelho`, `ambar`, `verde`, `cinza`) e aceita os nomes antigos
  convertidos; `relatorio_ciclo` passou a levar `alunoId` e matrícula, e
  `comparar_alunos` o `alunoId`, sem o que o pseudônimo do MCP não troca o nome;
  `materias_problematicas` não pede mais `simulado.fase`, a coluna que a 0003
  removeu e que fazia a tool falhar sempre (42703).

**O que muda para quem já usa as rotas** quando o branch for ao ar, todos
acréscimos ou `null` novos. ⚠️ Os `null` do piso — em `/me/simulado/{id}`, em
`/me/simulado/{id}/questoes`, o `mediaGeral` de `/me/simulados`, a série
`turma` de `/me/evolucao` e o `mediaTurma` do insight — **já valem em produção
desde 26/10** (PR #114). O que só este branch leva é o resto da tabela:

| Rota | O que muda |
|---|---|
| `GET /me/simulado/{id}` | `grupos.geral`, `top15`, `bottom15`, `posicao` e `percentil` podem vir `null` (piso) |
| `GET /me/simulado/{id}/questoes` | `duracaoMediaSegundos` vem `null` abaixo do piso |
| `GET /me/simulados` | `mediaGeral` pode vir `null`; ganha `computavel`, `motivoNaoComputavel`, `notaConfiavel` e `anoLetivoId`; o `deltaSelf` deixa de contar a nota que não é desempenho |
| `GET /me/evolucao` | a série `turma` deixa de fora a prova abaixo do piso |
| `GET /me/insight` | o `mediaTurma` que vai à OpenAI segue o piso, e a chave do cache muda (os bullets se regeram) |
| `GET /me/zona` | ganha `reguaSlug`, `reguaDescricao`, `vestibularesAlvo`, `reguaCobraMedia`, `materiaComMenosFolga` e `reguaDoColegio` |
| `GET /me/jogo` | o recorde passa a ser o do ano letivo corrente, e não de todo o histórico |
| `GET /gravacoes-aula` | cada aula ganha `situacao` |
| `GET /auditoria` | `canais` passa a 9; sem `incluir_logins`, as leituras do MCP ficam fora da linha do tempo, como os logins |

O front já trata cada um desses `null` dizendo por que o número falta
(`ProvaFicha`, `Provas`, `Jornada`, `Hoje`), em vez de sumir com ele.

### 4.5 · Como a Fase 1 foi verificada

- **Testes**: suíte inteira do backend — 2623 passando e 31 pulados em 27/10. Só falham 3
  de `tests/test_canvas_publicacao.py`, que falham também no `main` e
  reprovam o portão do `deploy.sh` (§9). Front — 1025 testes em 49 arquivos, lint e typecheck verdes. Os
  arquivos novos do chat são
  `tests/test_chat_agente.py`, `test_chat_contexto_do_turno.py`,
  `test_chat_roteiros.py`, `test_chat_persistencia_de_artefatos.py`,
  `test_chat_tools_aluno.py`, `test_chat_tools_coordenacao.py` (com o
  `FakeRico`, que confere tabela, coluna, embed e filtro contra o schema das
  migrations, `tests/esquema_das_migrations.py`) e os `test_dominio_*.py`.
- **No browser, em 26/10**, contra uma stack descartável (`sas-e2e-*`, removida
  no fim): a folha do Tio Léo em 390 px e em 1440 px, nos dois temas, com os
  seis tipos de cartão desenhados a partir de uma conversa semeada pelas tools
  reais e gravada como `_stream_mensagem` grava; a tela cheia do cartão; a
  releitura ao reabrir. **Nenhuma mensagem foi mandada ao modelo**: a escolha
  de tool pelo `gpt-4o-mini` não foi vista. Dois defeitos achados ali foram
  consertados: a promessa de corte da renovação no OAuth (§5.3) e o plural de
  "1 questão". Três ficaram, com captura: a migalha de 3 níveis que esconde o
  item atual no celular (`web/styles/casco.css`); dois números diferentes para
  "suas notas contra o corte" (a Hoje usa o ciclo mais recente, o cartão e
  `/me/zona` usam a nota que vale na régua — decisão de produto, §6); e dois
  controles com o mesmo nome acessível, "Abrir em tela cheia", no cartão da
  questão.
- **Os três achados foram resolvidos na tarde de 26/10.** A migalha ganhou um
  bloco de celular no fim de `web/styles/casco.css` (visto no browser em
  390 px: "Integr… › Aulas · Canvas ↔ Yo…", "Cardápios › Quarta, 9 de set"), e
  `/conectar-ia`, onde o defeito apareceu, saiu do casco (§5.5). As duas notas
  ficaram com nome, pela decisão 4 do dono (§0.1). Os dois controles agora se
  chamam "Ampliar este cartão — " seguido do olho do cartão
  (`telas/Aluno/TioLeo/ArtefatoAluno.tsx`) e "Abrir a questão N (ITA 2023,
  fase 1) numa tela só dela"
  (`telas/Aluno/pecas/CartaoQuestaoAluno.tsx`): o nome diz qual questão,
  porque o Estudar lista dezenas delas.

---

## 5 · O MCP da coordenação *(Fases 2 e 3)*

### 5.1 · Forma

- **Processo próprio**, mesma imagem da API, entrada `python -m app.mcp`,
  serviço `mcp` no compose. Transporte Streamable HTTP em `/mcp`, atrás do
  nginx. Um serviço separado porque o MCP vai ter credencial de banco
  diferente da API (§5.2) e porque o tráfego de um cliente externo não pode
  disputar o único event loop da API (`UVICORN_WORKERS=1`).
- **As ferramentas são as do registro** com `expor_no_mcp=True`, só de escopo
  `coordenacao`. As `instructions` do servidor são mínimas; o método fica nas
  descrições e nos playbooks.

Como ficou, em `api/app/mcp/`, com o SDK oficial (`mcp==1.30.0`: o porquê da
versão, e do `uvicorn` que subiu para 0.31.1 junto com a API, está comentado
em `api/requirements.txt`) e o `Server` de **baixo nível** — não o FastMCP,
porque as tools já existem e a validação, o prazo e o erro são os do registro:

- `/mcp` é Streamable HTTP **stateless e em JSON**, só POST (GET e DELETE
  levam 405), com a proteção de DNS rebinding do SDK ligada: `Host` fora da
  lista leva 421, `Origin` de browser leva 403. `/health` responde sem banco e
  sem token, porque é o HEALTHCHECK herdado da imagem da API.
- O uvicorn sobe programático, com o app como objeto: **um processo só**, de
  propósito, porque os tetos moram na memória dele. `--stdio` só sobe em
  dev/test.
- A ordem de uma chamada: identidade → limite por minuto → papel → catálogo →
  teto de linhas → registro (cliente PostgREST novo) → pseudônimo →
  serialização → auditoria.
- `tools/list` traz as 31 tools com `readOnlyHint` (29 com o pseudônimo
  ligado); `prompts/list` traz os 4 roteiros da coordenação; `resources`, `completion` e `logging` respondem
  "Method not found".
- A API não importa o SDK (`test_a_api_nao_importa_o_sdk_do_mcp`), e o MCP
  não importa `app.main` nem router: o guard de boot de lá exigiria os
  segredos que este processo não pode ter.

### 5.2 · Menor privilégio por construção

> ⚠️ **Reescrito em 26/10.** A primeira versão desta seção mandava dar
> `GRANT sas_leitura TO authenticator`, pôr `PGRST_JWT_SECRET` no PostgREST da
> API e o MCP mandar um JWT com `role: sas_leitura`. A revisão de 24/10 provou,
> num Postgres descartável, que login e PostgREST compartilhados com a API
> levavam ao `sas_service` (acesso total): por `pgrst.*` gravado no papel de
> login e por `SET ROLE` dentro de uma requisição. **Não reintroduza nada
> disso no `infra/vps`.** O desenho abaixo é o das migrations 0071 e 0072.

- **PostgREST próprio, `postgrest_mcp`**, no mesmo banco, com:
  - login próprio, **`autenticador_mcp`** (0071): `LOGIN NOINHERIT`, membro só
    do `sas_mcp` e sem herdar, `CONNECTION LIMIT 10`, `statement_timeout`
    de 30 s. A migration o cria com `PASSWORD NULL`; a senha vem de
    `POSTGREST_MCP_PASSWORD` e a operação a define no banco (o comando está no
    `docker-compose.yml` da raiz). Com o login da API, o `authenticator`, o
    MCP alcançava o `sas_service`;
  - `PGRST_DB_ANON_ROLE=sas_mcp` e **sem `PGRST_JWT_SECRET`**: sem segredo, o
    PostgREST recusa todo Bearer (PGRST300), e nenhum JWT, nem forjado, troca
    o papel;
  - `PGRST_DB_CONFIG=false` (segunda camada: config do PostgREST guardada no
    banco não vale) e pool de 3;
  - rede própria, `dados_mcp`: o serviço `mcp` só enxerga o `postgrest_mcp`,
    nem o banco, nem o PostgREST da API, nem a API.
- **Três papéis** (0071): `sas_leitura` (NOLOGIN; `SELECT` **por coluna** numa
  lista branca que é exatamente o que as 31 tools expostas leem — desde 26/10
  com as colunas de `alerta` que `listar_alertas` lê, sem `dados_brutos`,
  `hash_dedup` nem `resolvido_em`), `sas_mcp`
  (NOLOGIN; membro de `sas_leitura`, mais o estreito da 0072: `INSERT` por
  coluna na trilha, sem `id` nem `ocorrido_em`, e `EXECUTE` em
  `mcp_conferir_token`) e o login acima. Sem `DEFAULT PRIVILEGES`: tabela e
  coluna novas nascem invisíveis ao MCP (falha fechada). Credencial, conversa,
  cantina, captação e `token_mcp` ficam de fora; a trilha, só `INSERT`.
- **O gatilho da trilha** (0072, `evento_auditoria_so_do_mcp`): o `sas_mcp` só
  grava `mcp_ferramenta_chamada` (e a prova do verificador,
  `mcp_verificacao_papeis`, sem ator), no canal `mcp`, com ator
  `coordenador` e teto de tamanho por coluna. Até 26/10 aceitava qualquer
  `mcp_*`, e um MCP comprometido forjava "a administradora X revogou a conexão
  Y" na linha do tempo padrão. As ações do card de e-mails
  (`mcp_email_ia_cadastrado`; `mcp_email_ia_confirmado`, desde a revisão de
  segurança de 26/10 a que dá ao e-mail o poder de aprovar; e
  `mcp_email_ia_removido`), que dizem quem pode aprovar conexão, também só a
  API grava, e o verificador sonda cada uma (`_ACOES_SO_DA_API` em
  `scripts/verificar_papeis_do_mcp.py`).
- **As seis tabelas do OAuth** (0073: `oauth_cliente_mcp`, `oauth_pedido_mcp`,
  `email_conta_ia_mcp`, `oauth_codigo_por_email_mcp`, `oauth_codigo_mcp` e
  `oauth_refresh_mcp`) levam `REVOKE ALL` de PUBLIC, `sas_leitura` e `sas_mcp`:
  o MCP leva 42501 nelas, para ler e para escrever — provado na stack
  descartável da manhã de 26/10 para as quatro de então, e por `SET ROLE
  sas_mcp` direto no Postgres, à tarde, para as duas do e-mail. Quem as lê e
  escreve é a API. O verificador tem `oauth_` em `PREFIXOS_PROIBIDOS` e as seis
  em `TABELAS_PROIBIDAS` (`email_conta_ia_mcp` está lá pelo nome, porque não
  começa com `oauth_`): é a trava que impede alguém de pô-las na lista branca.
- **No boot**, o MCP recusa subir fora de dev/test com configuração insegura
  (`configuracao.validar_configuracao_do_mcp`: segredo da API no ambiente,
  `POSTGREST_URL` do PostgREST da API, `POSTGREST_TOKEN` preenchido…) e
  pergunta ao PostgREST com que papel fala (`dados.exigir_papel_restrito`): um
  que lê `usuario_coordenacao` impede o processo de subir.
- **A prova é contra o Postgres**, não contra o fake dos testes:
  `scripts/verificar_papeis_do_mcp.py` (por HTTP, lista branca lida das
  migrations, `--ferramentas` roda cada tool exposta) e, no PR,
  `tests/test_migrations_do_mcp.py`.
- Mesmo que uma tool tenha bug, o MCP não consegue escrever: o papel não deixa.

### 5.3 · Identidade e token

- **Token OPACO, nunca JWT**: `sas_mcp_` + `secrets.token_urlsafe(32)`, e só o
  sha256 em hex fica em `token_mcp` (0072). O MCP não tem `JWT_SECRET_KEY` (o
  guard recusa subir com segredo da API no ambiente); `get_current_user`
  recusa o token do MCP por construção, e um JWT de sessão nunca abre o MCP — a
  mesma separação que fechou o token de download (`test_auth_chat.py`).
- **Conferido A CADA requisição** pela RPC `mcp_conferir_token` (SECURITY
  DEFINER, `search_path` fixo, só o `sas_mcp` executa): devolve conta e papel
  só com token não revogado, não vencido e conta ativa. Sem cache — revogar ou
  desativar a conta vale na próxima requisição.
- **Quem conecta: administrador e coordenador** (decisão 2 de 26/10,
  `MCP_EMISSAO_SO_ADMINISTRADOR=false`, o padrão). Cada um emite e aprova em
  nome da própria conta; o coordenador vê e revoga só as suas (a de outro é
  404, e não 403: dizer "existe, mas não é sua" contaria quem tem conexão), e o
  administrador vê e revoga todas — "administrador" reconferido na TABELA, não
  no JWT de 8 h (`routes/mcp_tokens.py`). Com a chave em `true` volta o "só o
  administrador" de 24/10, nas três pontas: só ele emite, só ele aprova
  conexão OAuth, e o MCP confere o papel da tabela a cada requisição —
  tools/call, tools/list e prompts/* recusam conta que não é administradora.
  Rebaixar vale na hora. A chave precisa do MESMO valor na API e no `mcp`.
- **Fase 2:** token pessoal emitido pelo coordenador logado, em Administração
  → Conexões de IA (ou por `scripts/criar_token_mcp.py`), mostrado uma vez,
  vence em 90 dias (`MCP_VALIDADE_DO_TOKEN_DIAS`) e é revogável. Serve Claude
  Code, Claude Desktop e `mcp-remote`. Não passa pelo e-mail da conta de IA.
- **Fase 3:** OAuth com o authorization server **na API**
  (`routes/oauth_mcp.py`, 0073): metadado do RFC 8414, cadastro dinâmico do RFC
  7591 (aberto, com teto por IP, teto do total por hora e faxina dos clientes
  nunca usados), `/oauth/authorize` com PKCE S256 e `resource` (RFC 8707), a
  tela de consentimento `/conectar-ia` — rota React **pública** desde 26/10,
  aprovada pelo código enviado ao e-mail da conta de IA (abaixo) —, código de
  uso único, `/oauth/token` e `/oauth/revoke`. O access token é uma linha de
  `token_mcp` com origem `oauth` (1 h), conferida pela mesma RPC; o refresh
  gira a cada uso e a conexão vale 30 dias da aprovação. O MCP publica o RFC
  9728 em dois caminhos, e o 401 aponta para ele.
- **As regras do OAuth que custaram revisão** (`routes/oauth_mcp.py`):
  - **Nenhum erro do `/oauth/authorize` redireciona.** O `/authorize` é
    anônimo e o cadastro é aberto: um 302 de erro para a `redirect_uri` que o
    próprio app cadastrou faria de portalsas.online um redirecionador para
    qualquer site (RFC 9700 §4.11.2). O erro vira uma página 400, 429 ou 503
    — HTML sem script, com CSP `default-src 'none'` — que mostra o host e
    oferece a volta como link, levando `error`, `state` e `iss`. Quem não pede
    HTML recebe o mesmo erro em JSON. O único 302 que sobra leva a
    `/conectar-ia?pedido=…`; só a resposta dada na tela volta ao app — a
    aprovação, que pede o código do e-mail, e a recusa, que a pessoa clica
    vendo o host (a mesma escolha que o link da página de erro já oferecia).
  - **O host que a tela mostra é o host que recebe o código, letra por
    letra.** A `redirect_uri` só se cadastra escrita como o browser a escreve
    (o `URL.host` do WHATWG): só caracteres do RFC 3986 (a `\` fica de fora),
    autoridade só com host e porta, sem a porta padrão por extenso, sem zero
    à esquerda na porta, IPv6 comprimido e sem IPv4 embutido, e punycode que
    decodifica. https para qualquer host; http só de loopback, onde a porta
    pode variar (RFC 8252 §7.3). O front compara `new URL(destino).host` com
    `hostDaVolta(redirectHost)` sem reler o texto. A prova foi um fuzz
    diferencial de 450 mil URIs entre o Python e o Node, sem divergência.
  - **O nome da conexão** é `<nome declarado> (<host de volta>)`, até 80
    caracteres: o host fica sempre inteiro no fim, e quem encolhe é o nome.
    O nome sozinho não prova nada, porque qualquer app se cadastra como
    "Claude".
  - **Tetos e faxina.** O cadastro aceita 20 por hora por IP e 30 por hora no
    total (contados no banco; passou, 503). O `/token` e o `/revoke` dividem 60
    por minuto por IP, e o `/authorize` tem outros 60, com no máximo 10
    pedidos abertos por app (429) e 200 no total (503), com `Retry-After`. O
    próprio `/authorize` apaga, no máximo uma vez por minuto, os pedidos
    vencidos sem decisão e — desde a revisão de segurança de 26/10 (§5.6) —
    os RECUSADOS vencidos, levando junto os códigos por e-mail deles
    (CASCADE); e o `/register` apaga, uma vez por hora, o cliente que passou
    7 dias sem pedido nem conexão. Os aprovados ficam, porque são história: o
    código do RFC e o refresh apontam para eles. Todos configuráveis por
    `MCP_OAUTH_*` (`mcp/configuracao.py`).
  - **O refresh gira sem tolerância.** Reapresentar um refresh já girado, ou
    um código já usado, derruba a conexão inteira e grava o motivo na trilha.
    Revogar na tela corta o access e o refresh (`_girar_refresh` recusa a
    conexão revogada) — e por isso a tela promete o corte
    (`REVOGACAO_OAUTH_CORTA_RENOVACAO = true` em
    `web/src/dominio/conexoesDeIa.ts`).
- **A aprovação pelo e-mail da conta de IA** (decisão 3 de 26/10). É a única
  porta de aprovação: sem e-mail e código, nem a sessão de administrador
  aprova. Peças: `app/mcp/emails_ia.py` (puro, sem I/O),
  `routes/mcp_emails_ia.py`, `routes/oauth_mcp.py` e as duas tabelas novas da
  0073.
  - **O card**, sob sessão de coordenação. É o contrato de 26/10 com a
    **confirmação de posse** que a revisão de segurança da mesma tarde
    acrescentou (§5.6): o e-mail nasce aguardando e só aprova depois de
    confirmado.
    - `GET /mcp/emails-ia` devolve os ATIVOS da própria conta,
      `[{id, email, criadoEm, confirmadoEm, ultimoUsoEm}]`, do mais antigo
      ao mais novo; `confirmadoEm` nulo quer dizer aguardando o código.
    - `POST /mcp/emails-ia {email}` cadastra AGUARDANDO, normalizado em
      minúsculas e na forma do `<input type="email">` com ponto no domínio,
      e manda ao e-mail um código de 6 dígitos de confirmação: 201 com o
      item (`confirmadoEm: null`). 409 se o e-mail já está CONFIRMADO e
      ativo em qualquer conta, ou ativo — aguardando ou confirmado — nesta;
      400 acima de 10 ativos por conta; 422 na forma; 429 nos tetos do
      código de confirmação (20 por hora por conta, 5 por dia por e-mail);
      503 se o código não saiu, e o e-mail fica na lista, aguardando.
    - `POST /mcp/emails-ia/{id}/confirmar {codigo}`: 200 com o item e
      `confirmadoEm` preenchido (confirmar de novo devolve o mesmo item);
      400 com UMA frase para código errado, vencido, trocado ou sem
      tentativas; 404 para id torto, de outra conta ou removido; 409 se outra
      conta confirmou o mesmo e-mail no meio do caminho.
    - `POST /mcp/emails-ia/{id}/reenviar`: 202 `{"enviado": true}`; o código
      anterior morre e as tentativas voltam a 5. 409 se já está confirmado;
      404, 429 e 503 como acima.
    - `POST /mcp/emails-ia/{id}/remover` devolve `{id, removidoEm}` e nunca
      apaga a linha.

    Um e-mail, um dono — entre os CONFIRMADOS: o que só aguarda não tranca
    outra conta, porque quem digitou o e-mail alheio não pode impedir o dono
    da caixa de cadastrá-lo (é o desvio consciente do "409 se já cadastrado
    por qualquer conta" do contrato de 26/10); fica com o e-mail quem
    confirmar primeiro. Quando dois cadastros, ou duas confirmações, chegam
    juntos, valem os índices parciais da 0073: `uq_email_conta_ia_mcp_confirmado`
    (o e-mail, entre os ativos confirmados) e `uq_email_conta_ia_mcp_na_conta`
    (conta e e-mail, entre os ativos). O removido para de receber código na
    hora, e o código que já tinha saído para de aprovar; as conexões que ele
    aprovou ficam, e se revogam em Conexões de IA. Cada um vê e remove só os
    seus — o administrador também (o de outra conta é 404). Cadastrar não
    passa pelo portão do administrador: um e-mail sozinho não dá acesso a
    nada.
  - **O consentimento, sem sessão**: `GET /oauth/pedidos/{id}` devolve o app
    e o host de volta (`{id, cliente: {nome, redirectHost}, expiraEm}`), ou
    404 se não existe, venceu ou já foi decidido. `POST …/codigo {email}`
    responde **202 `{"enviado": true}` SEMPRE**, igual e no mesmo tempo para
    e-mail cadastrado ou não: o que depende do e-mail roda numa tarefa de
    fundo, DEPOIS da resposta (`_preparar_codigo`), que grava uma linha de
    código para qualquer e-mail digitado (só o HMAC dele) e só envia quando há
    cadastro ativo E confirmado, de conta que pode conectar
    (`_cadastro_que_aprova`). Os tetos, em memória, contam qualquer e-mail —
    senão o próprio 429 contaria quem está cadastrado: 20 por hora por IP, 5
    por pedido, 10 por e-mail por dia (`MCP_OAUTH_CODIGOS_*`).
  - **O código**: 6 dígitos de `secrets`, 10 minutos, 5 tentativas, uso
    único, guardado só como HMAC preso ao pedido E ao e-mail
    (`oauth_codigo_por_email_mcp`). HMAC com chave derivada da
    `JWT_SECRET_KEY`, e não sha256 puro como o resto do OAuth: um milhão de
    valores se acham num segundo, e a chave fica no ambiente da API, que o MCP
    não pode ter. Vale só o mais recente de (pedido, e-mail), e cada
    conferência gasta a tentativa ANTES de comparar, num UPDATE condicional.
  - `POST …/aprovar {email, codigo}` devolve `{redirecionarPara}`, com `code`,
    `state` e `iss`, ou 400 `{erro}` com UMA frase só para código errado,
    vencido, já usado, de outro pedido, de outro e-mail ou com as tentativas
    esgotadas. Só depois do código certo a mensagem diz o que houve (o e-mail
    foi removido ou não está confirmado; a conta não pode conectar), e a tela
    a mostra como veio: o código já foi gasto, e pedir outro não adiantaria
    (§5.6). ⚠️ Por isso não enumerar e-mail depende também destas frases do
    backend — `_CODIGO_RECUSADO` e os três 429 do `/codigo` não podem variar
    com o e-mail. A conexão nasce em nome do
    coordenador DONO do e-mail, reconferido na hora — ativo, e administrador
    se a chave da regra 2 estiver ligada —, e a trilha grava
    `mcp_oauth_aprovado` com o e-mail mascarado (`a***@dominio`) e o id do
    cadastro, nunca o código.
  - `POST …/recusar` devolve `{redirecionarPara}` com `error=access_denied` e
    o `state`, sem código e sem sessão: tirar acesso nunca depende de poder
    dar acesso. Vai ao log, não à trilha — é anônimo, e quem enche a trilha à
    vontade a torna inútil —; `mcp_oauth_recusado` deixou de ser gravada, e o
    CHECK da 0073 aceita a decisão sem autor.
  - **O e-mail** sai pelo SES de `lembretes/email.py` (`_enviar_codigo`), com
    o código no CORPO — o assunto aparece na tela bloqueada do celular —, o
    host de volta, sem o nome que o app declarou (texto livre de quem se
    cadastrou), e o "nunca compartilhe nem repasse este código" de todo OTP
    (revisão de 26/10, §5.6). Se o SES recusa o envio, o log leva só o e-mail
    mascarado e o TIPO do erro: a mensagem do `MessageRejected` traz o
    endereço inteiro. Sem SES configurado, em dev o código vai ao log, que é
    como se testa na máquina; fora de dev ele NUNCA vai ao log (quem o lesse
    aprovaria conexão em nome de qualquer um): nada é enviado, o log ganha um
    ERROR `[AÇÃO NECESSÁRIA]`, e a tela continua dizendo que, se o e-mail
    estiver cadastrado e confirmado no SAS, o código chegou lá
    (`avisoDoCodigoPedido`, em `web/src/dominio/conexoesDeIa.ts`). O código de
    confirmação do card segue as mesmas regras de envio e de log
    (`_enviar_codigo_de_confirmacao`), mas, como quem o pede está logado,
    responde 503 quando não sai. O que isso pede da produção está na §9.
- **Toda chamada de tool vai para a auditoria** (`mcp/auditoria_mcp.py`):
  quem, por qual conexão, qual ferramenta, o desfecho, a duração e quantas
  linhas. Nunca argumento nem resultado (regra de `auditoria.py`). O request
  id e o IP, que vêm de fora, passam por uma régua antes do INSERT — um
  `X-Request-Id` de 129 caracteres fazia o gatilho recusar a linha, e a
  chamada saía sem rastro (revisão final de 26/10) —, e o INSERT que falha é
  ERROR com `[AÇÃO NECESSÁRIA]`.
- **Tetos**, em memória (o MCP é um processo só): 120 tools/call por minuto
  por token, com a primeira recusa auditada; 240 requisições por minuto por
  token, de qualquer método, que voltam 429 sem ir ao banco; 20 tokens
  recusados por minuto por IP; e no máximo 50 linhas nos parâmetros de limite
  das tools (LGPD art. 6º, III).
- **Nome ou matrícula:** desde 26/10 o MCP devolve o nome do aluno
  (`MCP_MOSTRAR_NOME_DO_ALUNO=true`, o padrão — decisão 1, §0.1). Com `false`
  volta o pseudônimo: a matrícula no lugar do nome, o resultado que traria um
  nome que ele não sabe trocar recusado inteiro, e as duas tools de
  `catalogo.SO_COM_NOME_DO_ALUNO` fora do catálogo.

### 5.4 · ⚠️ LGPD — o portão antes do MCP em produção

Conectar uma IA de fora envia dado de menor a um provedor terceiro: é a mesma
regra da armadilha 7 do CLAUDE.md, aplicada ao servidor. Em 26/10 o dono
decidiu o que o MCP devolve — o **nome** do aluno (§0.1, decisão 1) — e quem
conecta (decisão 2). O que falta antes de abrir:

- a **base legal do art. 14 da LGPD** para mandar nome e desempenho de
  adolescente a um provedor de IA de fora, registrada — é o que a decisão 1
  pede, e o que o comentário de `mostrar_nome_do_aluno`
  (`mcp/configuracao.py`) avisa;
- sob que **conta do provedor**, com que retenção, a coordenação conecta (§6).
  O e-mail da conta de IA (decisão 3) prova QUEM aprova; não diz em que plano
  do provedor o dado cai.

O portão no código é `MCP_HABILITADO`: fora de dev/test, o processo do MCP não
sobe sem `true` explícito. O `infra/vps` **ainda não tem** o `postgrest_mcp`
nem o `mcp`; o que entra lá quando o portão abrir está na §10, e a ordem do
deploy na §9.

O que o código faz para reduzir o que sai, e o que ele não resolve:

- **Minimização**, nos dois modos: no máximo 50 linhas por parâmetro de limite
  (`MCP_TETO_DE_LINHAS`), por cima do "até N" de cada handler; e o
  `instructions` pede perguntas estreitas e lembra que são adolescentes ("use
  o que vier deles só para responder ao que foi perguntado").
- **Fora do MCP**: os três artefatos de UI — `navegar_para`, `gerar_grafico` e
  `exportar_csv` —, sem uso fora do app; régua, rotinas e trilha, por decisão
  aberta (§6); e `roteiro_da_coordenacao`, porque os roteiros vão como
  `prompts`. As listas estão em `tests/test_chat_exposicao_no_mcp.py`, e tool
  nova da coordenação sem decisão de exposição reprova.
- **O pseudônimo, agora como opção** (`mcp/pseudonimo.py`, ligado com
  `MCP_MOSTRAR_NOME_DO_ALUNO=false`): o nome do aluno vira `Aluno
  <matrícula>`. O resultado é convertido antes na mesma forma JSON que vai ser
  serializada, e o que traria um nome que ele não sabe trocar — nome em texto
  livre, dict de aluno sem `alunoId` nem matrícula — é **recusado inteiro**
  (`recusa_lgpd`), sem nome nem matrícula no motivo que vai ao log. Com ele,
  `buscar_aluno_por_nome` e `listar_alertas` saem do catálogo (§0.1). ⚠️
  **Pseudônimo não é anonimização**: a matrícula é o SIS User ID do Canvas, e
  quem é da escola a reidentifica.
- O chat **do app** já manda nome de aluno à OpenAI desde antes destas fases,
  e as três tools novas que leem por aluno (`cortados_pela_regua`,
  `pendencias_canvas_do_ciclo`, `historico_de_alteracoes`) seguem a mesma
  prática. Nenhuma delas vai ao MCP.

### 5.5 · O que as Fases 2 e 3 entregaram *(24 a 26/10, fora de produção)*

| Peça | Onde |
|---|---|
| O processo do MCP | `api/app/mcp/`: `__main__` (uvicorn de um processo, ou `--stdio` em dev), `app` (o Starlette: `/mcp`, `/health`, o metadado do RFC 9728 e os tetos `FalhasDeTokenPorIp` e `RequisicoesPorToken`), `servidor` (o `Server` de baixo nível, a ordem da chamada, `LimitePorMinuto` e a regra de administrador), `catalogo` (as tools do registro no formato do SDK, com schema normalizado e teto de linhas), `pseudonimo`, `tokens`, `auditoria_mcp`, `dados` (cliente PostgREST novo por operação e a sonda de privilégio do boot) e `configuracao` (as `MCP_*` e o guard de boot) |
| Banco | migrations **0071** (os três papéis e o login; desde 26/10 com as colunas de `alerta`), **0072** (`token_mcp`, a RPC `mcp_conferir_token`, o INSERT estreito na trilha e o gatilho dela) e **0073** (as seis tabelas do OAuth — as quatro do protocolo e, desde 26/10, `email_conta_ia_mcp`, com as colunas da confirmação de posse, e `oauth_codigo_por_email_mcp` — e a FK `token_mcp.oauth_cliente_id`), cada uma com o `.down.sql` |
| Compose de dev | serviços `postgrest_mcp` (127.0.0.1:3001) e `mcp` (127.0.0.1:8001), e a rede `dados_mcp` (`docker-compose.yml` da raiz) |
| Rotas da API | `routes/mcp_tokens.py`: `GET /mcp/disponibilidade`, `GET` e `POST /mcp/tokens`, `POST /mcp/tokens/{id}/revogar`. `routes/mcp_emails_ia.py` (26/10): `GET` e `POST /mcp/emails-ia`, `POST /mcp/emails-ia/{id}/confirmar` e `POST /mcp/emails-ia/{id}/reenviar` (a confirmação de posse, da revisão de segurança — §5.6) e `POST /mcp/emails-ia/{id}/remover`. `routes/oauth_mcp.py`: o RFC 8414 na raiz e com o caminho do emissor, `/oauth/register`, `/oauth/authorize`, `/oauth/token`, `/oauth/revoke` e o consentimento, **sem sessão** desde 26/10 (`GET /oauth/pedidos/{id}`, `POST …/codigo`, `POST …/aprovar`, `POST …/recusar`). Sem emissor, URL pública e URL do app configurados, as rotas do OAuth dão 404 |
| Auditoria | canal `mcp`. `mcp_ferramenta_chamada`, uma por `tools/call`, com ferramenta, desfecho, duração e linhas — nunca argumento nem resultado. E as que só a API grava: `mcp_token_emitido`, `mcp_token_revogado`, `mcp_oauth_aprovado` (desde 26/10 com o e-mail mascarado e o id do cadastro), `mcp_email_ia_cadastrado`, `mcp_email_ia_confirmado` (o que dá ao e-mail o poder de aprovar) e `mcp_email_ia_removido`, as três com o e-mail mascarado. `mcp_oauth_recusado` não é mais gravada: a recusa é anônima e vai ao log. As leituras saem da linha do tempo padrão (`auditoria.ACOES_SEM_ALTERACAO`) e voltam com `incluir_logins` |
| Scripts | `scripts/criar_token_mcp.py` (emite, lista e revoga; o token vai para um arquivo 0600, nunca para o stdout) e `scripts/verificar_papeis_do_mcp.py` (a prova de privilégio contra o PostgREST de verdade; com `--ferramentas`, preenche também o `nome` de `buscar_aluno_por_nome`) |
| Front | `telas/Administracao/ConexoesDeIa.tsx` (Administração → Conexões de IA, com a seção "E-mails da sua IA" desde 26/10 — e, desde a revisão de segurança, o aviso de que quem lê a caixa conecta com o acesso da conta e, na linha do e-mail que aguarda, o campo do código, Confirmar e "Não chegou? Enviar outro código" —, e o cartão "Que IA lê o SAS?" no hub), `telas/ConectarIa/ConectarIa.tsx` (`/conectar-ia?pedido=…`: desde 26/10 página PÚBLICA, em `App.tsx` fora da `RotaProtegida`, carregada por `lazy()`, sem casco e sem nenhuma chamada a rota de sessão — um 401 ali derrubaria a pessoa no login; as etapas são o e-mail, o código de 6 dígitos e Aprovar, com Recusar nas duas), `dominio/conexoesDeIa.ts`, `dominio/voltaDoLogin.ts` (`/login?proximo=…`: a coordenação volta ao link de origem depois de entrar, para qualquer rota protegida; o caso do consentimento saiu dele) e `styles/conexoes-de-ia.css` |
| Testes | `tests/test_mcp_catalogo.py`, `test_mcp_emails_ia.py` (26/10), `test_mcp_pseudonimo.py`, `test_mcp_rotas.py`, `test_mcp_servidor.py`, `test_mcp_tokens.py`, `test_migrations_do_mcp.py`, `test_oauth_mcp.py` (o consentimento reescrito para o código por e-mail, com remetente falso), `test_observabilidade.py` e `test_chat_exposicao_no_mcp.py`, que roda as tools expostas pelo registro contra uma escola sintética — as 31 com o nome, e as 29 também pelo pseudônimo real. No front, `dominio/conexoesDeIa.test.ts`, `voltaDoLogin.test.ts` e `notaContraCorte.test.ts` |

**As 31 tools expostas** — as 29 abaixo, que valem também com o pseudônimo,
mais `buscar_aluno_por_nome` e `listar_alertas`, que só entram com o nome
(decisão 1): `alunos_destaque`, `alunos_em_risco`,
`alunos_similares`, `buscar_aluno_por_matricula`, `buscar_questoes_do_banco`,
`comparar_alunos`, `comparar_ciclos`, `comparar_simulados`,
`estatisticas_ciclo`, `histograma_simulado`, `historico_aluno`,
`insights_do_ciclo`, `listar_alunos`, `listar_ciclos`, `listar_materias`,
`listar_sedes`, `listar_simulados`, `listar_turmas`, `materias_problematicas`,
`notas_simulado`, `obter_aluno`, `obter_simulado`, `questoes_do_simulado`,
`recorrencia_no_banco`, `relatorio_aluno`, `relatorio_ciclo`,
`tendencia_aluno`, `topicos_do_edital` e `trajetoria_aluno`. As listas
`EXPOSTAS` (e as partes dela, como `EXPOSTAS_COM_O_NOME`) e `FORA_DO_MCP`
estão em `tests/test_chat_exposicao_no_mcp.py`, e uma tool nova da
coordenação sem decisão de exposição reprova
(`test_tudo_o_mais_da_coordenacao_fica_fora`). A lista branca da 0071 é
exatamente o que essas 31 leem: tool exposta que passar a ler coluna nova
precisa de migration nova, senão leva 42501.

**Como foi verificado, na manhã de 26/10 — ANTES das decisões do dono.** ⚠️
Estas provas rodaram no modo de então: matrícula no lugar do nome, só o
administrador conectando e o consentimento pela sessão do SAS. Provam o
transporte, o privilégio e a dança do OAuth; não provam os padrões novos (o
parágrafo seguinte diz o que provou estes). Numa stack descartável (`sas-e2e-*`):
Postgres 16 com as migrations, os dois PostgREST, e a API e o MCP do worktree,
o MCP sem segredo da API e sem chave da OpenAI. Foram 590 conferências em seis
scripts, todas verdes, mais o verificador de novo com um token real (148):

- o verificador de papéis com `--ferramentas`: 209;
- login → token pela API → as 29 tools pelo cliente oficial do SDK
  (`streamable_http_client`), sem nenhum nome dos 12 alunos sintéticos em 32
  mil caracteres de saída, e uma linha de auditoria por chamada: 85;
- o OAuth inteiro por HTTP, e pelo `OAuthClientProvider` do próprio SDK, que
  fez a dança sozinho até um `tools/call`: 79;
- privilégio — o catálogo do Postgres, uma sessão TCP como `autenticador_mcp`,
  o PostgREST do MCP, JWT forjados (inclusive um assinado com a
  `JWT_SECRET_KEY` da API) e o guard de boot apontado para o PostgREST da API:
  130;
- as rotas `/me` com o piso de anonimato: 76; extras: 11.

Os consertos da revisão final foram provados numa segunda stack (`sas-rf-*`):
27 de 27, e o verificador com 152 de 152. As duas stacks foram removidas. No
browser, as telas de Conexões de IA e de consentimento foram vistas em 390 e
1440 px, nos dois temas (§4.5) — as telas de então, com o consentimento pela
sessão.

**Como foi verificado depois das decisões (tarde de 26/10).**

- **Backend, contra Postgres 16 e PostgREST v12.2.3 de verdade** (containers,
  rede e portas próprios, `emailsia-e2e-*`, removidos no fim; a API em
  processo, pelo `TestClient`, com o emissor `https://portalsas.online/api`
  configurado e um remetente falso no lugar do SES): 36 de 36 conferências. O
  `migrate up` de 0001 a 0073; o card (201 normalizado com o `+` do alias, 409
  por outra conta, a recusa do índice parcial reconhecida pelo nome, o CHECK
  do e-mail normalizado); `GET /oauth/pedidos/{id}` sem sessão; o `/codigo`
  com a MESMA resposta para e-mail cadastrado e não cadastrado, o e-mail só
  para o cadastrado e uma linha de código, em HMAC, para os dois; o código
  errado com a frase genérica e a tentativa gasta antes de comparar; o
  `/aprovar` em nome da DONA do e-mail — uma coordenadora, não administradora
  —, com `no-store`, o último uso gravado, o código marcado como usado e a
  trilha com o e-mail mascarado e sem o código; o `/oauth/token` com o access
  em nome dela; a recusa sem autor e sem evento na trilha; a faxina do pedido
  vencido levando o código junto (CASCADE); o `sas_mcp` lendo as colunas de
  `alerta` que a tool lê e o `aluno` da busca por nome, e NÃO lendo
  `alerta.dados_brutos`, `alerta.hash_dedup`, `email_conta_ia_mcp` nem
  `oauth_codigo_por_email_mcp` (por `SET ROLE` direto no Postgres); e o
  `down` e o `up` da 0073.
- **Mutação** no backend das decisões: 36 mutantes, 34 pegos; os 2 que
  sobram são equivalentes (checagens que o UPDATE condicional da tentativa e
  o `_decidir` já garantem). Um dos que escaparam na primeira passada era um
  buraco de verdade e ganhou teste.
- **Front no browser**, pelo `chrome-devtools-mcp` com perfil próprio, contra
  uma API FALSA que segue o contrato (não contra o backend real, escrito em
  paralelo): Conexões de IA com os e-mails e o `/conectar-ia` público, em 390
  e 1440 px, claro e escuro, sem transbordo e sem erro no console.
- **Não rodaram de novo** depois das decisões: o processo do MCP com o cliente
  do SDK (as 31 tools com o nome, inclusive as duas novas) e o verificador de
  papéis contra um `postgrest_mcp` (§8).
- **Os consertos da revisão de segurança** (§5.6): cada um com teste que falha
  no código de antes, e a 0073 com a confirmação de posse contra Postgres 16 e
  PostgREST v12.2.3 de verdade, em containers descartáveis já removidos: 33 de
  33 conferências.

A revisão de segurança destas decisões — três lentes, o que cada uma achou, o
que foi consertado e o que ficou de propósito — está na §5.6.

**Pendências conhecidas**, todas fora de produção:

- Na lista de Conexões de IA o host de volta não tem campo à parte: aparece
  só no fim do nome da conexão (`<nome declarado> (<host>)`), e um nome
  declarado que imita um host antes do real ainda engana quem lê depressa. O
  nome do app e a validade da concessão na conexão OAuth são a ponta (a) da
  §5.6.
- `GET /mcp/disponibilidade` não diz se o nome do aluno é mostrado. Desde
  26/10 as duas telas afirmam, sem condição, que o nome dos alunos vai ao
  provedor; com o pseudônimo ligado (`MCP_MOSTRAR_NOME_DO_ALUNO=false`) elas
  diriam que sai mais do que sai — o lado seguro do erro, mas um erro. O
  conserto é o mesmo de antes: a disponibilidade dizer o modo (só o processo
  do MCP lê a chave hoje).
- A tela de auditoria não tem rótulo para as ações `mcp_*` (`ACAO_LABEL` em
  `telas/Auditoria/Auditoria.tsx`), inclusive as três do e-mail da conta de
  IA, nem para os canais `cantina` e `captacao`, e a pílula "Entradas no
  sistema" não diz que traz também as leituras da IA.
- Sem SES fora de dev, nada sai, e o sintoma depende da porta. No card, o
  cadastro responde 503 e o e-mail fica aguardando: ninguém confirma, e sem
  e-mail confirmado nenhuma conexão OAuth se aprova. No consentimento, o
  `/codigo` responde 202 como sempre e só o log sabe (ERROR `[AÇÃO
  NECESSÁRIA]`) — é o preço de não contar quem está cadastrado; a operação é
  que tem de olhar essa linha (§9).
- Um id malformado (22P02) ainda vira "falhou do nosso lado" em tools antigas,
  como `obter_aluno` e `estatisticas_ciclo`. As novas conferem o uuid antes; o
  conserto geral seria o despacho traduzir o 22P02.
- `api/requirements.lock` não foi regenerado: ainda diz `uvicorn==0.30.6` e não
  tem o `mcp`. A imagem não depende dele (o Dockerfile instala o
  `requirements.txt`), mas o registro do conjunto exato ficou velho.
- As `MCP_*` (inclusive os tetos do código, `MCP_OAUTH_CODIGOS_*`, e os
  padrões novos das decisões 1 e 2), o `POSTGREST_MCP_PASSWORD` e o
  `SAS_MCP_TOKEN` não estão no `api/.env.example` nem no
  `infra/vps/.env.example`: o branch não os mexe. As linhas que eles precisam
  ganhar estão na §10.
- Risco aceito no teto da casa: um IP sozinho ocupa os 200 pedidos abertos e
  os reocupa a cada 10 minutos. Enquanto durar, nenhuma conexão OAuth NOVA se
  faz (503); as que existem e o token pessoal seguem. Mitigação não feita: um
  teto por IP de pedidos criados.
- Os dois baixos da lente 2 que ficaram abertos — nenhum teto de tokens por
  conta, e a regra do só-administrador lida de dois ambientes — estão na
  §5.6, com o caminho.
- Retenção: as linhas de `oauth_codigo_por_email_mcp` de um pedido APROVADO
  ficam com ele, inclusive as de e-mail sem cadastro (só HMAC). O volume é
  limitado pelos tetos, mas não há política de retenção. E a faxina do
  recusado (§5.6) é um segundo DELETE, por `aprovado = false`, que não usa o
  índice parcial `idx_oauth_pedido_mcp_sem_decisao`: com a tabela pequena é
  desprezível; se os aprovados crescerem muito, um índice parcial resolve
  (migration nova, com `.down`).

### 5.6 · Revisão de segurança de 26/10

Na tarde de 26/10, com as quatro decisões já no código, três revisões
adversariais olharam o branch, cada uma por uma lente — o código por e-mail, o
nome real e a exposição, e a tela pública —, com reproduções próprias contra
as rotas de verdade, o banco falso e o remetente falso dos testes: nada saiu
pelo SES, nada foi à OpenAI. Depois, uma correção por lente conferiu cada
achado, consertou o que era real — cada conserto com um teste que falha no
código de antes — e escreveu o porquê do que não mexeu. A lente 2 aprovou; as
lentes 1 e 3 reprovaram.

**Lente 1 — o código por e-mail** (`routes/oauth_mcp.py`,
`routes/mcp_emails_ia.py`, `mcp/emails_ia.py`, a 0073). Ficaram de pé,
reproduzidos: não enumerar e-mail, o chute do código, o reuso do código, a
aprovação em nome do dono certo, o e-mail removido e a conta desativada
reconferidos no `/codigo` e no `/aprovar`, a corrida de duas aprovações, a
sessão que não aprova nada e a trilha sem nada em claro.

| Achado | Gravidade | Desfecho |
|---|---|---|
| A recusa anônima deixava o pedido RECUSADO fora da faxina e do teto de pedidos abertos, que só olhavam `decidido_em IS NULL`: linhas de até ~4 KB gravadas sem sessão e sem teto — ~351 MB por dia por IP, a 60 `/authorize` por minuto. Era o buraco que a revisão de 25/10 fechou, reaberto pela recusa sem sessão | alta | **Consertado.** `_apagar_pedidos_vencidos` apaga também o recusado vencido (`aprovado = false`), levando os códigos por e-mail dele (CASCADE); o aprovado fica, porque é história. Testes `test_recusa_anonima_vencida_e_varrida_e_o_aprovado_fica` e `test_recusado_que_ainda_vale_nao_e_varrido` (`test_oauth_mcp.py`). Sobra um acúmulo passageiro, limitado pelos tetos durante os 10 minutos do pedido (§5.5, retenção) |
| O e-mail INTEIRO no log de produção quando o SES recusa o envio: o `MessageRejected` do botocore traz o endereço no texto, e o `log.exception` gravava a exceção no campo `excecao`. Com o SES em sandbox, todo e-mail de fora é não verificado — seria todo pedido | média | **Consertado.** `_enviar_codigo` loga só o e-mail mascarado e o TIPO do erro, como já fazia o envio da confirmação. Teste `test_erro_do_ses_nao_vaza_o_email_inteiro_no_log` (`test_oauth_mcp.py`) |
| O código é o fator único, e se repassa: um app se cadastra como "Claude", com volta para `https://claude.ai`, e quem chama o `/aprovar` com os 6 dígitos recebe o código do OAuth no corpo e o troca pelo token, sem redirect nenhum. O e-mail só dizia "se não foi você, ignore" | média | **Em parte.** A estrutura é a decisão 3 e fica ("aprovar é ter a caixa de entrada", abaixo). A lacuna barata foi consertada: o e-mail diz "nunca compartilhe nem repasse este código" (`emails_ia.mensagem_do_codigo`). Teste `test_a_mensagem_do_codigo_avisa_para_nao_compartilhar` (`test_mcp_emails_ia.py`) |
| Quem sabe o e-mail de um coordenador gasta os 10 códigos do dia dele, de qualquer IP: ele recebe 10 e-mails, e o pedido de verdade leva 429 até o dia seguinte. E o teto vive em memória, num LRU de 10 mil chaves: 10 mil e-mails distintos despejam a contagem, e um restart a zera | média | **Troca deliberada** ("a trava por e-mail", abaixo) |
| O cadastro do e-mail não provava a posse | baixa | **Consertado** pela lente 3, que achou a mesma raiz |

**Lente 2 — o nome real e a exposição.** Aprovou, com quatro baixos.
Conferiu pelo HTTP, com o `REGISTRO` de verdade e uma escola sintética: 31
tools com o nome e 29 com o pseudônimo, e a diferença é exatamente
`buscar_aluno_por_nome` e `listar_alertas`; os três artefatos de UI fora nos
dois modos; os tetos (`limite=1000` volta no máximo 20 na busca e 50 nos
alertas); nenhum nome nas 31 chamadas com o pseudônimo; a emissão e a
revogação com o padrão novo (o dono forjado no corpo é ignorado, o
coordenador vê só as suas, o administrador rebaixado com o JWT velho também);
e o GRANT de `alerta`, coluna por coluna — lido no código, não contra
Postgres e PostgREST de verdade.

| Achado | Gravidade | Desfecho |
|---|---|---|
| A regra do só-administrador é lida de dois ambientes. Com o padrão `false`, o descompasso perigoso é religá-la só na API: a tela passa a dizer "só o administrador" e corta a emissão e as renovações do OAuth, mas o `mcp`, sem a chave, segue aceitando os tokens pessoais dos coordenadores — por até 90 dias, com o nome dos alunos. Ao contrário (só no `mcp`), a tela emite e aprova o que o MCP recusa | baixa | **Aberto.** A §10 põe a chave numa linha só, lida pelos dois, e a ponta (e), abaixo, faz cada processo dizer no log o valor com que subiu. O conserto de verdade é exigir a chave explícita nos dois fora de dev, como o `MCP_HABILITADO`, ou lê-la de um lugar só (do banco, pela RPC) |
| Não há teto de tokens por conta. Os tetos do MCP — 120 `tools/call` e 240 requisições por minuto, e a proteção do pool de 3 do `postgrest_mcp` — são por token, e com a decisão 2 todo coordenador emite quantos quiser: 13 tokens multiplicam os tetos por 13. O de 50 linhas por chamada continua valendo | baixa | **Aberto.** Caminho: um teto de tokens pessoais ativos por conta na emissão, e um limite por conta além do por token |
| `buscar_aluno_por_nome` monta o ILIKE sem escapar `%`, `_` e `\`: `nome='__'` passa no mínimo de 2 caracteres e lista a escola em ordem alfabética, até o teto de 20 | baixa | Ponta (c), abaixo |
| Sete textos ainda descreviam o padrão de antes (só o administrador; a matrícula): a 0072, `scripts/criar_token_mcp.py` (duas vezes), `servidor.MENSAGEM_SO_ADMINISTRADOR` — que vai ao modelo e ao usuário — e partes deste documento | baixa | O documento foi acertado nesta rodada; o código é a ponta (d) |

**Lente 3 — a tela pública** (`/conectar-ia` e o card de e-mails). Ficaram de
pé: a volta (`destinoDaVolta` recusa host diferente, `javascript:`, http fora
do loopback e a `\` da revisão de 25/10), a mesma frase depois de pedir o
código para e-mail cadastrado ou não, a página que não lê sessão nem chama
rota de sessão ao desenhar (conferido por SSR) e os campos do contrato, que
batem com o backend.

| Achado | Gravidade | Desfecho |
|---|---|---|
| O card cadastrava o e-mail sem prova de posse: um domínio digitado errado (`gmial.com`) ou uma caixa compartilhada davam a quem lê a caixa o acesso da conta à coordenação — nomes de menores | média | **Consertado** com a confirmação de posse (abaixo). A cadeia do revisor — cadastrar, pedir o código, aprovar e trocar pelo token — passava no código de antes e agora para no `/aprovar` (400). Testes, entre outros, `test_cadastrar_nasce_aguardando_e_manda_o_codigo_so_ao_email` e `test_confirmar_com_o_codigo_certo_tira_o_hash_e_audita` (`test_mcp_emails_ia.py`) e `test_email_que_aguarda_confirmacao_nao_recebe_nem_aprova` (`test_oauth_mcp.py`) |
| Os erros do consentimento: depois do código CERTO, o `/aprovar` explica o que houve (o e-mail foi removido, a conta não pode conectar), e a tela trocava isso pela frase genérica "peça outro código" — um laço, porque nesses dois casos o código novo nunca chega. Os três 429 viravam "espere alguns minutos", inclusive o de um dia | baixa | **Consertado**: nos 400 e 429 a tela mostra a frase do servidor (`fraseDoServidor`), e o ramo 403, que era código morto, saiu. ⚠️ Daí em diante, não enumerar e-mail depende também das frases do backend (§5.3). Testes em `web/src/dominio/conexoesDeIa.test.ts` |
| Os erros do card: o 400 do teto de 10 e-mails virava "confira o e-mail" | baixa | **Consertado**: 400 é o teto, 422 é a forma, e entraram o 429 e o 503; o 403, morto, saiu. Mesmo arquivo de teste |
| O aviso "O código tem 6 dígitos." ficava fora do `aria-describedby` do campo, que acendia `aria-invalid` sem dizer por quê | baixa | **Consertado**, sem teste automático: a etapa depende de estado interno, não chega por SSR, e o repositório não tem jsdom. Conferido pela leitura e pelo typecheck |

**A confirmação de posse do e-mail** — o conserto do achado médio da lente 3,
e o que ele muda no contrato de 26/10 (as respostas, uma por uma, estão na
§5.3, "O card"):

1. `POST /mcp/emails-ia {email}` grava o cadastro AGUARDANDO
   (`confirmadoEm: null`) e manda ao e-mail um código de 6 dígitos de
   confirmação. Grava antes de enviar: o índice recusa o repetido antes de
   sair qualquer e-mail. Se o código não sai — o SES recusou, ou não está
   configurado fora de dev —, a resposta é 503 e o e-mail fica na lista,
   aguardando: quem pede está logado e é dono do cadastro, e não há o que
   esconder.
2. Quem cadastrou digita o código no card, logado:
   `POST /mcp/emails-ia/{id}/confirmar {codigo}` preenche `confirmadoEm`, e a
   trilha grava `mcp_email_ia_confirmado` — a ação que dá ao e-mail o poder de
   aprovar —, com o e-mail mascarado.
3. "Não chegou? Enviar outro código": `POST /mcp/emails-ia/{id}/reenviar`
   mata o código anterior e devolve as 5 tentativas.
4. Só o e-mail ativo E confirmado recebe o código de aprovar e aprova
   (`_cadastro_que_aprova` e `_dono_do_codigo` exigem `confirmado_em`). O que
   aguarda nem recebe; no `/aprovar`, depois do código certo, cai na mesma
   frase do e-mail sem cadastro.

O código de confirmação é o mecanismo do de aprovar — HMAC com a chave
derivada da `JWT_SECRET_KEY`, com um prefixo próprio que o separa do de
aprovar, 10 minutos, 5 tentativas gastas antes de comparar, uso único —, preso
ao id do cadastro, que nasce na API: nem o mesmo endereço cadastrado de novo
aceita o código antigo. Os tetos dele ficam em memória, como os do `/codigo`:
20 por hora por conta e 5 por dia por e-mail, somados entre contas —
constantes de `routes/mcp_emails_ia.py`, não `MCP_*`. O e-mail de confirmação
diz que quem lê a caixa conecta uma IA aos dados do SAS, pede para não digitar
nem repassar o código e não leva o nome de quem cadastrou: no engano, iria
para um estranho.

O card mostra, junto do campo, que quem lê a caixa conecta com o acesso da
conta, e que só se cadastra uma caixa que só a própria pessoa lê
(`avisoDaCaixaDoEmail`, no `aria-describedby`). A linha do e-mail que aguarda
traz o campo do código (`autocomplete="one-time-code"`, sem `maxLength`),
Confirmar e "Não chegou? Enviar outro código", com a espera de 30 s nas linhas
cujo código saiu naquela tela; depois de confirmar, o foco vai para a situação
da linha.

Um e-mail, um dono — mas só entre os CONFIRMADOS: o 409 entre contas vale para
o e-mail confirmado e ativo, e o que só aguarda tranca apenas a própria conta
(§5.3). É um desvio consciente do "409 se já cadastrado por qualquer conta" do
contrato: sem ele, qualquer coordenador trancaria o dono da caixa cadastrando o
e-mail dele sem confirmar. Fica com o e-mail quem confirmar primeiro.

A 0073 foi editada no lugar, sem 0074, porque nunca foi commitada nem subiu à
produção: `email_conta_ia_mcp` ganhou `confirmado_em`,
`hash_codigo_de_confirmacao`, `confirmacao_expira_em` e
`tentativas_de_confirmacao` (de 0 a 5), três CHECKs
(`codigo_so_enquanto_aguarda`, `uso_so_depois_de_confirmado`,
`confirmado_depois_de_criado`) e os dois índices parciais no lugar do
`uq_email_conta_ia_mcp_ativo`. Provada contra Postgres 16 e PostgREST v12.2.3
de verdade, em containers descartáveis já removidos: 33 de 33 conferências,
inclusive o `down` e o `up`. ⚠️ Uma base que já tenha a 0073 ANTIGA aplicada
(uma stack descartável de antes) guarda a mesma versão, e o `up` não a
reaplica: lá, `migrate down --to 0072` e `up`, ou recriar o volume (§9). No
browser, nada disso foi visto (§8).

**O que ficou de propósito, e por quê**

- **A trava por e-mail.** O teto de 10 códigos por e-mail por dia
  (`MCP_OAUTH_CODIGOS_POR_EMAIL_POR_DIA`), chaveado pelo sha256 do e-mail e
  não pelo IP, é o que segura o chute: 10 códigos de 5 tentativas são 50
  chutes por dia contra um milhão de valores, ~1,8% por ano por e-mail, o
  padrão de OTP. E é o que limita o que qualquer caixa recebe. O MESMO teto
  deixa quem sabe o e-mail de um coordenador esgotar os códigos do dia dele, e
  não há como separar os dois: o `/codigo` é anônimo (decisão 3), e o pedido
  de verdade e o abuso ao mesmo e-mail são idênticos. Chavear pelo IP tiraria
  a trava e devolveria o bombardeio da caixa e o chute, com IP rotativo. O
  coordenador trancado segue com o token pessoal, que não passa pelo e-mail, e
  pode cadastrar e confirmar outro e-mail; encurtar a janela é chave de
  produto, não conserto. O LRU de 10 mil chaves que despeja a contagem é
  freado pelos tetos por IP (20 por hora) e por pedido (5); um botnet é outro
  modelo de ameaça, e se um dia preocupar, a contagem vai para o banco.
- **Aprovar é ter a caixa de entrada.** É a consequência da decisão 3 do dono:
  sem sessão do SAS e sem segundo fator, quem tem os 6 dígitos aprova em nome
  do coordenador dono do e-mail — quem lê a caixa junto, ou quem os recebe
  repassados num golpe. O host que a tela e o e-mail mostram não protege
  quando o app é do atacante, porque o `/aprovar` devolve o código do OAuth a
  quem o chamou. O que reduz isso sem reabrir a decisão: a confirmação de
  posse no cadastro, o aviso do card, o "nunca repasse" no e-mail, a trilha
  (`mcp_oauth_aprovado`, com o e-mail mascarado e o id do cadastro) e a
  conexão na lista de Conexões de IA, que se revoga ali, com o corte do
  refresh. Fechar de vez pede reabrir a decisão 3 — exigir a sessão para
  aprovar, por exemplo —, e isso é do dono.
- **Dois cadastros aguardando o mesmo e-mail**, em contas diferentes,
  convivem: é o preço de nenhum coordenador sequestrar o e-mail alheio. O dono
  da caixa pode receber até 5 e-mails de confirmação por dia vindos do card de
  outra pessoa.
- **Os tetos dos códigos moram em memória** (a API é um processo só,
  `UVICORN_WORKERS=1`, armadilha 5): zeram a cada deploy.

**As pontas que estão sendo fechadas agora**, em paralelo a este texto:

- (a) a conexão OAuth aparece na lista de Conexões de IA com o nome do app e a
  validade da concessão — os 30 dias da aprovação —, não a do access de 1 h
- (b) o e-mail de IA confirmado numa conta que foi desativada deixa de
  trancar o cadastro: é liberado quando outra conta o cadastra, com auditoria
  — antes, o 409 o prendia à conta desativada, sem tela que o removesse
- (c) `buscar_aluno_por_nome` escapa os curingas do ILIKE (`%`, `_` e `\`)
- (d) os textos do padrão antigo — só o administrador; a matrícula — corrigidos
  no código: a 0072, `scripts/criar_token_mcp.py` e
  `servidor.MENSAGEM_SO_ADMINISTRADOR`
- (e) a API e o MCP registram no log, ao subir, o valor efetivo das duas
  configurações (`MCP_EMISSAO_SO_ADMINISTRADOR` e `MCP_MOSTRAR_NOME_DO_ALUNO`),
  o que torna visível o descompasso do primeiro baixo da lente 2, sem
  impedi-lo
- (f) a Jornada do aluno passa a dizer que a média é "a que conta na régua"
  (decisão 4)

---

## 6 · Decisões em aberto

A coluna do meio diz o que o código faz enquanto ninguém decide — o padrão é
sempre o lado que expõe menos, salvo onde o dono decidiu o contrário (§0.1).
As fechadas ficam na tabela, riscadas, para quem chega por aqui achar a
resposta.

| Decisão | Hoje no código | Trava |
|---|---|---|
| ~~O MCP devolve **nome** do aluno ou só **matrícula**?~~ **FECHADA em 26/10 pelo dono: o nome** (§0.1, decisão 1) | `MCP_MOSTRAR_NOME_DO_ALUNO=true`, o padrão; o pseudônimo fica como opção, e as telas já dizem que o nome vai ao provedor. Segue aberto o que a decisão pede: a **base legal do art. 14 da LGPD**, registrada | MCP em produção |
| Sob que **conta de IA** a coordenação conecta (conta pessoal, conta do colégio com retenção desligada)? | **Em parte**: quem aprova a conexão OAuth prova a posse do e-mail da conta de IA, e a conexão nasce com o acesso do coordenador dono dele (decisão 3). Que conta do provedor é essa, e com que retenção, o código não decide: qualquer cliente que fale MCP conecta com o token pessoal | MCP em produção |
| ~~Quando abre o **portão de administrador** — quem mais emite, aprova e consulta?~~ **FECHADA em 26/10 pelo dono: administrador e coordenador** (decisão 2) | `MCP_EMISSAO_SO_ADMINISTRADOR=false`, o padrão; `true` volta ao só-administrador nas três pontas, e precisa do MESMO valor na API e no `mcp` | — |
| **Captação** (dado de gente de fora) e **cantina** entram no MCP? | Não entram, e não há tool delas nem no chat do app | — |
| **Régua, rotinas** (sync, gravações, lembretes) e **trilha** de auditoria entram no MCP? | Estão no chat da coordenação e fora do MCP (`METADADOS` dos módulos `reguas`, `rotinas` e `trilha`) | — |
| O Tio Léo continua `gpt-4o-mini`? | **Fechada em parte**: o modelo passou a ser configurável (`OPENAI_MODELO_ALUNO`, padrão `gpt-4o-mini`). Trocar é decisão de custo (docs/27 §12) | custo do chat |
| Quando uma prova **fecha** para a comparação com a turma? | O piso de 10 protege uma leitura, não a diferença entre duas: quem lê a mesma prova com 10 e depois com 11 notas tira a 11ª. O conserto é mostrar a comparação só com a prova fechada (`aluno_dados.PISO_DE_ANONIMATO`). Vale igual em produção, onde o piso está desde 26/10 (PR #114) | privacidade do aluno |
| ~~A Hoje e o Tio Léo mostram **a mesma nota contra o corte**?~~ **FECHADA em 26/10 pelo dono** (decisão 4): não, e cada uma diz qual é | "Notas no último simulado" na Hoje (o ciclo mais recente, de `/me/evolucao`); "Notas que contam na régua" no cartão `barras_corte` e na zona (`/me/zona`). O cálculo não mudou (`web/src/dominio/notaContraCorte.ts`) | — |

---

## 7 · Fases

| Fase | O quê | Pronto quando | Estado em 26/10 — nada em produção |
|---|---|---|---|
| **0** | Registro único, despacho com as oito invariantes, testes de isolamento | §3.3 | ✅ feita (§3.4) |
| **1** | Os seis defeitos, desempenho, cobertura e playbooks | cada item com teste; o Tio Léo visto no browser, coisa que o docs/30 diz nunca ter acontecido | 🔨 escrita, com teste, e **vista no browser** numa stack descartável: a folha e os seis tipos de cartão (§4.5). Os três achados do browser foram resolvidos na tarde de 26/10. Falta uma conversa de verdade, com o `gpt-4o-mini` escolhendo as tools |
| **2** | MCP local por token pessoal, PostgREST e login próprios (§5.2), auditoria | um Claude Code conectado lê um ciclo e não consegue ler `usuario_coordenacao` | 🔨 provado com o cliente oficial do SDK (o protocolo que o Claude Code e o `mcp-remote` falam) e com o verificador de papéis (§5.5) — na manhã de 26/10, ainda no modo matrícula e só-administrador. Depois das decisões, o processo do MCP não rodou de novo. O Claude Code de verdade não foi conectado, e o portão da §5.4 está fechado |
| **3** | OAuth para conectores | claude.ai e ChatGPT completam `tools/call` | 🔨 o `OAuthClientProvider` do SDK completou o fluxo e um `tools/call` pela rede local, com o consentimento de então, pela sessão (§5.5). A aprovação pelo código no e-mail da conta de IA (decisão 3) foi provada com a API contra Postgres e PostgREST de verdade e remetente falso: nenhum e-mail saiu pelo SES. claude.ai e ChatGPT não conectaram: pedem URL pública em HTTPS, e isso é produção |

### 7.1 · O que mudou em relação ao plano, e por quê

| O plano dizia | O que foi feito | Por quê |
|---|---|---|
| §5.2, na versão de 24/10: `GRANT sas_leitura TO authenticator`, `PGRST_JWT_SECRET` no PostgREST da API e o MCP mandando um JWT com `role: sas_leitura` | **PostgREST próprio** (`postgrest_mcp`) com **login próprio** (`autenticador_mcp`: NOINHERIT, membro só do `sas_mcp`), sem JWT secret e com `PGRST_DB_CONFIG=false` | A revisão de 24/10 provou, num Postgres descartável, que login e PostgREST divididos com a API chegavam ao `sas_service`: por `pgrst.*` gravado no papel de login e por `SET ROLE` dentro de uma requisição. Com o login próprio as duas portas fecham no Postgres, e não numa opção do PostgREST. A decisão de 24/10 já tinha trocado o PostgREST, mas ainda com o `authenticator`; o login próprio veio da revisão daquele dia, em 25/10 (0071) |
| §5.3: um token assinado com chave derivada | **Token opaco**, só o sha256 no banco, conferido a cada requisição pela RPC `mcp_conferir_token` | O MCP não guarda segredo nenhum; um JWT de sessão nunca abre o MCP e o token do MCP nunca abre a API, por construção; e revogar vale na requisição seguinte, sem cache |
| "Só o administrador emite" | Até a tarde de 26/10, só o administrador emitia, aprovava **e usava**: `tools/call`, `tools/list` e `prompts/*` recusavam a conta que não era administradora naquela hora, na tabela. Desde a decisão 2 do dono, administrador e coordenador conectam (padrão `false`), e o só-administrador ficou como opção — que, ligada, vale de novo nas três pontas | O "usa" entrou porque, sem ele, um administrador rebaixado, ou um token emitido com a regra desligada, continuava lendo a escola por até 90 dias (revisões de 24/10 e de 26/10). Quem conecta é decisão do dono (§0.1) |
| §5.3: o consentimento na tela da coordenação, aprovado pela sessão do SAS | **Consentimento público**, aprovado pelo código enviado ao e-mail da conta de IA, que o coordenador cadastra no card; recusar não pede nada | Decisão 3 do dono (26/10): o claude.ai e o ChatGPT abrem a tela no browser em que a IA está, que nem sempre tem sessão do SAS, e não dizem de quem é a conta. A posse do e-mail é a prova |
| §5.4: matrícula no lugar do nome, por padrão | **O nome, por padrão**; o pseudônimo como opção, e duas tools a mais no MCP (`buscar_aluno_por_nome`, `listar_alertas`) | Decisão 1 do dono (26/10), contra a recomendação do plano. Pede a base legal do art. 14 da LGPD antes de produção (§0.1) |
| O OAuth da Fase 3, com o caminho óbvio sendo o authorization server do próprio SDK (`mcp.server.auth`) | **Authorization server na API, em FastAPI direto**, sem o SDK (`routes/oauth_mcp.py`) | Importar o `mcp.server.auth` puxaria o SDK inteiro para dentro da API (há teste de que ela não o importa). E o SDK 1.30.0 tem lacunas verificadas: `none` fora do metadado, `issuer` com barra final, `/register` recusando cliente sem `refresh_token`, `/revoke` exigindo segredo de cliente público e o Basic exigindo `client_id` no corpo |
| §4.3: "progresso no banco ... listas" do aluno; "a régua como objeto" da coordenação | `minhas_listas` e `simular_regua` **ficaram fora** | O levantamento de 24/10 deu `minhas_listas` como prioridade baixa e `simular_regua` como dispensável, e a rodada mandou não fazê-las (`tests/test_chat_tools_aluno.py` trava a ausência da primeira). As duas continuam possíveis; nenhuma tem pendência registrada no código |
| Nada sobre o tamanho do que sai | **Tetos de minimização** em duas camadas: no handler de cada tool (o "até N" da descrição) e, no MCP, 50 linhas em todo parâmetro de limite | LGPD art. 6º, III. `listar_alunos` aceitava `limite=1000` |
| §4.3 e docs/27 §9: comparação só com agregados, como regra do prompt | O **piso de anonimato** virou regra do domínio, em `stats/aluno_dados.py`, e vale para rota, tool e insight | Em 25/10 o piso estava só na saída de duas tools, e a mesma média da turma saía inteira por GET `/me/simulados`, `/me/evolucao`, `/me/simulado/{id}` e `/me/insight` — e saía em produção. Em 26/10 o piso foi a produção sozinho, pelo PR #114 (`fc461a2`), antes do resto do branch (docs/19) |

---

## 8 · O que não foi verificado

Atualizado em 26/10, depois das provas da §4.5 e da §5.5 — as da manhã e as
da tarde, depois das decisões do dono.

**O modelo**

- **Nenhuma fase chamou a OpenAI.** Não se viu o `gpt-4o-mini` escolher as
  tools novas, nem obedecer às regras novas do prompt (cartão "logo abaixo",
  resolução oficial antes de resolver, régua junto da zona). O catálogo do
  aluno manda ~12 mil caracteres de descrição a cada chamada, e o da
  coordenação ~35 mil, ~4,4 mil tokens a mais que antes; a escolha não foi
  medida (`SAS_TESTE_ESCOLHA_TOOL=1` em `tests/test_chat_tools.py` chama a
  OpenAI de verdade e não foi rodado).
- O streaming foi provado sobre o SDK da OpenAI com transporte falso, não com a
  OpenAI; nem o tempo até o primeiro token atrás do nginx.
- O defeito 2 foi deduzido do formato da API da OpenAI, não reproduzido.
- `GET /me/insight` com chave da OpenAI: a chave ficou vazia de propósito em
  todas as provas.

**O volume**

- O prazo padrão de 90 s e o teto de 3 tools simultâneas são estimativa: não
  há medida de duração por tool em produção. O registro grava a medida;
  recalibrar com ela.
- Nada foi medido com os ~900 alunos de produção: o `statement_timeout` de 30 s
  do `autenticador_mcp`, os tetos por minuto do MCP, o preâmbulo (14 idas com
  o cache frio), as tools do aluno que leem o acervo inteiro sem cache
  (`o_que_mais_cai` sem matéria, `missao_de_hoje`, `meu_progresso_no_banco`),
  a contagem de `disparo` por `atualizado_em`, que não tem índice, e o
  `listar_alunos`, que agora lê a `classificacao_aluno` inteira.
- Os tetos do código por e-mail (20 por hora por IP, 5 por pedido, 10 por
  e-mail por dia) não foram medidos com uso real. O "mesmo tempo" do `/codigo`
  para e-mail cadastrado ou não é por construção — a resposta sai antes de
  procurar o e-mail —, e não foi cronometrado.

**O banco de verdade**

- As tools de rotinas, régua e trilha rodaram contra o `FakeRico`, que confere
  coluna, embed e filtro contra o schema das migrations, e só parte delas
  contra um PostgREST de verdade. Ficaram sem dado real: o `LIKE` com `%` no
  meio (`chave_idempotencia`, `nota/%/<simulado>`), o `or=` de vários prefixos
  de `auditoria.consultar` e o `count` de `disparo` com `lt`/`gte`.

**O MCP e o OAuth**

- O Claude Code de verdade (a CLI) não foi conectado: `claude mcp add` mexe na
  configuração do usuário. O cliente das provas foi o SDK oficial em Python,
  pela rede local. Claude Desktop e `mcp-remote` também não.
- O OAuth não foi completado pelos conectores reais do claude.ai nem do
  ChatGPT: os dois pedem URL pública em HTTPS, que é produção, atrás da §5.4.
  Com a decisão 3, eles também não foram vistos abrindo o `/conectar-ia` no
  browser da IA, nem a pessoa indo e voltando entre a tela e a caixa de
  e-mail.
- O emissor com caminho (`https://portalsas.online/api`) e o nginx: nas provas
  pela rede o emissor era `http://127.0.0.1:58000`, sem caminho, e a rota do
  RFC 8414 com o caminho do emissor não passou pela rede — a prova da tarde
  configurou o emissor com caminho, mas com a API em processo, sem rede nem
  nginx. As `location`s da §10 não foram aplicadas nem testadas.
- **Depois das decisões de 26/10, o processo do MCP não rodou de novo**: as 31
  tools com o nome pelo cliente do SDK (inclusive `buscar_aluno_por_nome` e
  `listar_alertas`), as `instructions` novas num `initialize` de verdade e o
  verificador de papéis com `--ferramentas` contra um `postgrest_mcp`. A lista
  branca nova de `alerta` foi provada por `SET ROLE sas_mcp` direto no
  Postgres, não pelo PostgREST do MCP.
- Um **coordenador** usando o MCP de ponta a ponta: a aprovação em nome de uma
  coordenadora e o `/oauth/token` dela foram provados na API; um `tools/call`
  com o token dela, não.
- **O e-mail de verdade pelo SES**: nenhum código saiu por ele. Os testes e a
  prova da tarde usaram remetente falso, e não se viu o e-mail chegar (prazo,
  caixa de spam, como o cliente mostra o código). Nem o SES de produção: o
  docs/15 §2 adiou o e-mail em 21/08 ("SES, sandbox e conta AWS saem do
  caminho crítico"), e se hoje há credencial e saída do sandbox em produção
  não foi conferido — o `.env` não se lê.
- A validade de 30 dias da conexão OAuth e a de 90 dias do token pessoal: só o
  vencimento do token pessoal foi simulado, no banco.
- O modo `--stdio`.
- O `uvicorn` 0.31.1 sobe também na API (a mesma imagem), e a suíte não
  exercita o uvicorn: conferir com `./infra/vps/deploy.sh --verificar` depois
  do deploy.

**O browser**

- As telas foram vistas pelo `chrome-devtools-mcp` com perfil próprio e sem
  janela, porque o perfil do MCP `chrome` desta máquina estava preso a outra
  sessão. Safari e aparelho de verdade não foram vistos: o MCP `mobile` não
  enxerga aparelho sem o Xcode.
- A conversa do Tio Léo foi semeada pelas tools reais e gravada como o
  servidor grava, sem modelo: o que se viu é o desenho dos cartões e a
  releitura, não uma resposta.
- O que mudou na tarde de 26/10 — os e-mails da IA no card, o `/conectar-ia`
  público, os textos do nome e de quem conecta — foi visto só contra uma API
  falsa que segue o contrato, não contra o backend real. Os rótulos das duas
  notas (decisão 4) têm teste de domínio; contra dado real, não foram vistos.
- Os consertos da revisão de segurança (§5.6) foram vistos só por SSR: a linha
  do e-mail que aguarda — o campo do código, a espera de 30 s, o foco depois de
  confirmar —, o layout dela a 390 px e as frases novas do consentimento. No
  browser, nem contra a API falsa.
- Os três achados da manhã estão no fim da §4.5, resolvidos à tarde.

---

## 9 · A ordem do deploy

O branch leva duas coisas que vão ao ar em momentos diferentes: **o chat e o
banco do MCP** (Fases 0 e 1, as rotas de Conexões de IA e do OAuth e as
migrations 0070 a 0073), que podem ir sem o MCP; e **o MCP** (`postgrest_mcp`,
`mcp`, nginx), que **não vai a produção antes do portão de LGPD** (§5.4, §6).

**Antes de tudo — a base do branch e a numeração, acertadas em 26/10.** O
branch saiu do `f38b4dd`. Em 24/10 o `main` ganhou os PRs #112 e #113 (o
horário de estudos do aluno), com a migration `0069_bloco_horario_estudo.sql` —
**já aplicada em produção**, segundo o docs/19 do `main` — e um
`docs/42-plano-horario-de-estudos.md`. Em 26/10 a árvore foi reposta em cima do
`main` daquele dia (`1bf281c`), ainda sem commit:

- **As migrations daqui passaram a 0070 a 0073.** Nasceram 0069 a 0072, e o
  runner (`api/scripts/migrate.py`) guarda só a VERSÃO como chave de
  `_migracoes_aplicadas`: com o `0069` do horário já registrado, a
  `0069_chat_artefato_tipos_do_aluno` apareceria como aplicada e nunca rodaria,
  e os cartões do Tio Léo voltariam ao sintoma da migration faltando, sem
  aviso. Hoje são `0070_chat_artefato_tipos_do_aluno`, `0071_papeis_do_mcp`,
  `0072_token_mcp` e `0073_oauth_mcp`, e com elas mudaram as referências que o
  código faz aos números — entre elas `_MIGRATIONS_DO_MCP = ("0071_",
  "0072_")` em `scripts/verificar_papeis_do_mcp.py`, os testes que leem as
  migrations pelo prefixo e os nomes de teste que citam o número. ⚠️ Uma base
  que já tenha rodado a numeração antiga (as stacks descartáveis das provas)
  guarda 0069 a 0072 com os nomes velhos, e o runner não confere o nome: lá,
  recrie o volume em vez de migrar por cima.
- **Dois documentos 42 — e este passou a 43 (27/10).** O `main` trouxe o
  `docs/42-plano-horario-de-estudos.md`, e este plano também nasceu 42. O
  código deste branch o citava como "docs/42" ~240 vezes, em 108 arquivos, e o
  do horário cita o 42 dele (o `registro.ts` diz "docs/42 §0" na fonte
  `horarioEstudos`, e a `Hoje.tsx`, "docs/42 §4.3"): com os dois, nenhuma
  citação dizia de qual se tratava. Mudaram só as linhas que o branch
  escreveu — linha igual à do `fc461a2`, ou que fala do horário, ficou como
  estava —, e as do horário seguem no 42.
- **Os conflitos da reposição**, resolvidos à mão: `api/app/main.py` (os dois
  lados puseram um import de rota no mesmo ponto; ficaram os dois, em ordem
  alfabética), `web/src/servicos/api.ts` (dois `import type` no mesmo ponto;
  ficaram os dois) e `docs/19-roadmap.md` (os dois blocos novos entraram no
  MESMO ponto; o do horário, já em produção, ficou primeiro).
  `registro.ts`, `CascoAluno.tsx` e `Hoje.tsx` juntaram sem conflito, e o
  `docs/30-estado-da-implementacao.md` foi gerado de novo (`npm run inventario`
  dentro de `web/`): os dois lados tinham escrito "30 fontes" no título do
  LIGADO, e com as duas fontes novas são 31.
- **O piso de anonimato já foi a produção sozinho**, pelo PR #114 (commit
  `3b9cb62`, merge `fc461a2`, sem migration), mergeado e implantado em 26/10
  (docs/19). Ele mexe em `api/app/stats/aluno_dados.py`,
  `api/tests/test_piso_de_anonimato.py`, `web/src/tipos/aluno.ts` e nas telas
  `Hoje`, `Jornada`, `ProvaFicha` e `Provas` do aluno, que este branch também
  mexe. O branch foi movido para cima do `fc461a2` no mesmo dia (é a base dele
  quando esta seção foi fechada), e esses sete arquivos são os que os dois
  lados mexeram. Antes de abrir o PR, `git merge-base HEAD origin/main` tem de
  dar `fc461a2` ou um commit depois dele.

**Primeiro passo — o chat e o banco, sem o MCP**

0. ⚠️ **O portão do `deploy.sh` está vermelho no `main`.** Os 3 testes de
   `api/tests/test_canvas_publicacao.py` falham também no `main`, e o `pytest`
   dos portões locais reprova por eles. Por isso os deploys de 26/10 saíram
   com `--rapido` (que pula lint, teste e typecheck) **depois de rodar as
   suítes à mão**. Aqui, igual: num clone limpo no commit do merge — o
   `deploy.sh` sobe a árvore de trabalho, e este worktree não serve —, rodar
   `pytest` (com `APP_ENV=dev`), `ruff`, `npm test`, `npm run lint` e `npm run
   typecheck`, conferir que só aquelas 3 falham, e então
   `./infra/vps/deploy.sh --migrar --rapido`. Consertar os 3 é o que devolve
   o portão.
1. `./infra/vps/deploy.sh --migrar` (com o `--rapido` do passo 0). O
   `deploy.sh` aplica as migrations ANTES do `up -d` e reinicia o `postgrest`
   sempre depois (armadilha 1), que é a ordem que estas pedem:
   - **A 0070 antes do código das tools com cartão.** Sem ela o CHECK de
     `chat_artefato` recusa os quatro tipos novos: o aluno vê o cartão ao vivo,
     o INSERT falha (isolado, com log) e o cartão some ao reabrir.
   - **0071 a 0073** criam os papéis — que são do cluster, não só do banco —,
     `token_mcp` e as seis tabelas do OAuth, inclusive as dos e-mails da
     conta de IA. O `autenticador_mcp` nasce com `PASSWORD NULL`, então
     ninguém entra com ele enquanto a senha não for definida, e sem o MCP no
     ar não há por que defini-la. As rotas `/mcp/tokens` e `/mcp/emails-ia`
     precisam das tabelas, e o PostgREST da API só as enxerga depois do
     restart que o `deploy.sh` já faz; sem as variáveis do OAuth, as rotas
     `/oauth/*` dão 404.
2. Depois do deploy, `./infra/vps/deploy.sh --verificar`: o `uvicorn` subiu
   de 0.30.6 para 0.31.1 na mesma imagem, e a suíte não o exercita.
3. Saber o que muda para quem usa: as rotas `/me` da tabela da §4.4 — o piso
   já está no ar desde o PR #114; o que chega agora é o zero não computável,
   o `deltaSelf`, os campos novos de `/me/zona` e o recorde do ano letivo —,
   os nomes das duas notas contra o corte (decisão 4), e o **cache do
   insight**, cuja chave mudou de novo (agora com o prompt): cada aluno que
   abrir a Hoje gera outra vez os bullets do ciclo, uma chamada à OpenAI por
   aluno e ciclo.
4. Com `MCP_HABILITADO` fora do `.env`, a tela de Conexões de IA diz "o
   servidor MCP está desligado neste ambiente", mas administrador e
   coordenador conseguem emitir token mesmo assim (o padrão da decisão 2) —
   um token que nada aceita enquanto o MCP não existir e que vence em 90
   dias. O card de e-mails também funciona, e não dá acesso a nada sozinho.

**Segundo passo — o MCP, quando o portão abrir**

1. O que a §5.4 ainda pede: a base legal do art. 14 da LGPD registrada e a
   conta do provedor (§6). Nome × matrícula e quem conecta já foram decididos
   pelo dono (§0.1).
2. O `.env` de produção ganha a senha do login e as `MCP_*` (§10).
   - **E o SES, para o código do e-mail da conta de IA** (decisão 3). Sem ele
     nenhuma conexão OAuth se aprova fora de dev: o `/codigo` responde 202
     como sempre, nada é enviado, e o log ganha um ERROR `[AÇÃO NECESSÁRIA]`.
     O token pessoal segue funcionando. A API lê `AWS_SES_ACCESS_KEY_ID`,
     `AWS_SES_SECRET_ACCESS_KEY` e `EMAIL_REMETENTE` (`lembretes/email.py`),
     e o `mcp` não pode tê-las (o guard dele recusa subir com a chave do SES
     no ambiente). Três cuidados, todos do código como está: (a)
     **`EMAIL_DESTINATARIO_TESTE` vazio** — o código passa por
     `lembretes/email.enviar_email`, que manda tudo para a caixa de teste
     quando ela está preenchida; (b) o SES **fora do sandbox**, ou só os
     endereços verificados recebem; (c) as chaves na API ligam junto o
     despachante do motor de lembretes (`/disparos/processar`, de hora em
     hora no `crontab-sas`), que envia o que estiver `agendado` ou `falhou` em
     `disparo` abaixo do teto de tentativas — conferir essa fila antes. Os
     lembretes de aluno seguem atrás de `LEMBRETE_ALUNO_ATIVO`, e o webhook do
     SNS continua fora (sem `SES_WEBHOOK_TOKEN`, `main.py` não o registra):
     enviar não depende dele. O docs/15 §2 adiou o e-mail em 21/08; esta é a
     primeira peça que o põe de volta no caminho crítico.
3. O compose ganha os dois serviços e as redes, e o `deploy.sh` ganha o passo
   da senha (§10). **A senha do `autenticador_mcp` é definida por fora da
   migration**, depois do `migrate up`, e a cada deploy: um `down` + `up` da
   0071 recria o login sem senha, e o PostgREST 12.2.3 sem senha sai com
   código 1 (com `restart: unless-stopped`, fica tentando até ela existir).
4. `docker compose restart postgrest postgrest_mcp`: os dois cacheiam o schema.
5. O `mcp` sobe e pergunta ao `postgrest_mcp` com que papel fala: se lê
   `usuario_coordenacao`, recusa subir. Com o `postgrest_mcp` fora do ar por
   mais de ~18 s, sai, e volta pelo `restart`.
6. O nginx ganha as `location`s da §10, e o container `web` precisa recarregar
   o `nginx.conf`.
7. A prova, de dentro da rede (o `postgrest_mcp` não tem porta publicada):
   `docker compose exec -T api python -m scripts.verificar_papeis_do_mcp --mcp
   http://postgrest_mcp:3000 --api http://postgrest:3000 --ferramentas
   </dev/null`. Cada rodada grava duas linhas na trilha. Nas provas ele
   rodou do host, pelo `.venv`; de dentro do container não foi testado (sem o
   `infra/postgres/init` na imagem, a conferência do init é pulada).
8. Os smokes: `POST https://portalsas.online/mcp` sem token dá 401 com
   `resource_metadata` no `WWW-Authenticate`; `GET
   /.well-known/oauth-protected-resource/mcp` e `GET
   /.well-known/oauth-authorization-server/api` devolvem JSON, e não o
   `index.html` do SPA, que é o que o nginx de hoje devolve.

**Para desfazer**: pare o `postgrest_mcp` antes do `down` da 0071 (o DROP ROLE
com ele conectado deixa sessão órfã). O `down` da 0072 apaga todos os tokens,
e o token em claro não se recupera. O `down` da 0073 revoga as conexões OAuth e
mantém as linhas delas em `token_mcp`, mas derruba as seis tabelas — os
e-mails das contas de IA cadastrados no card se perdem, e cada um cadastra de
novo.

---

## 10 · Para produção — o `infra/vps` do MCP *(preparado em 27/10, DESLIGADO)*

> ⚠️ **Reescrita em 27/10.** Até aqui esta seção era a proposta para o MCP
> **ligado**, sem nada aplicado. Desde o branch `feat/infra-mcp-desligado` o
> `infra/vps` tem o MCP **desligado por padrão**: os serviços estão no compose,
> as locations no nginx e o passo da senha no `deploy.sh`, mas nada do MCP sobe
> enquanto o `.env` não o ligar. O que a proposta dizia e deixou de valer está
> em §10.6. Onde a §9 (segundo passo) divergir desta seção, vale esta.

### 10.1 · O que foi aplicado em 27/10

O primeiro passo da §9: o `main` em `ca4c68f` (merge do PR #115) foi a produção
com as migrations 0070 a 0073. Desde então o cluster tem os papéis
`sas_leitura` e `sas_mcp` e o login `autenticador_mcp`, **com `PASSWORD
NULL`** — ninguém entra com ele —, e o banco tem `token_mcp` e as seis tabelas
do OAuth. A API serve as rotas de Conexões de IA (`/mcp/tokens`,
`/mcp/emails-ia`) e as do OAuth, que dão 404 sem as variáveis (§9, primeiro
passo). O `infra/vps` não mudou nesse deploy: nenhum serviço do MCP, nenhuma
location no nginx, nenhuma senha no login.

### 10.2 · O que entra no `infra/vps`, e o que o próximo deploy muda

Três arquivos — cada decisão está comentada no próprio arquivo, com o porquê:

- **`docker-compose.yml`**: `postgrest_mcp` e `mcp` no profile `mcp`, que só
  fica ativo com `COMPOSE_PROFILES=mcp` no `.env`; as redes `borda_mcp` (nginx
  ↔ mcp) e `dados_mcp` (mcp ↔ postgrest_mcp); e o `web` também na
  `borda_mcp`. O `mcp` roda a imagem `sas-api` — a que o build do `api` produz —,
  sem build próprio. Nenhum dos dois tem `ports:` (armadilha 4).
- **`nginx.conf`**: `location = /mcp` e os quatro `/.well-known` do OAuth, com
  `proxy_pass` por variável e o resolver do Docker (`127.0.0.11`), para o nginx
  subir com o mcp parado. Com ele fora do ar, `/mcp` e os dois do RFC 9728 dão
  **503** com uma linha de texto ("O MCP da coordenação não está no ar neste
  servidor."), pela location `@mcp_fora_do_ar`, em vez do `index.html` do SPA
  com 200. Os dois do RFC 8414 vão à API, que responde 404 em JSON enquanto o
  OAuth estiver desligado. Nenhum `add_header` nas locations novas, e o `/mcp`
  SOBRESCREVE o `X-Forwarded-For` com `$remote_addr`.
- **`deploy.sh`**: pergunta ao compose se o MCP está ligado (`config
  --services`); só com ele ligado grava a senha do login, reinicia o
  `postgrest_mcp` e espera o 401 do `/mcp`; num `.env` novo, sorteia também a
  `POSTGREST_MCP_PASSWORD`. O `--verificar` ganha os smokes do MCP nos dois
  modos (§10.5).

**O próximo deploy, com o MCP desligado, muda só a borda:**

- o container `web` é **recriado** — ganhou a rede `borda_mcp` — e sobe com o
  `nginx.conf` novo. (Um deploy que não recriasse o `web` deixaria o nginx com o
  arquivo velho na memória.)
- `/mcp` e `/.well-known/oauth-protected-resource[/mcp]` deixam de dar 200 com o
  SPA e passam a dar 503 com texto; `/.well-known/oauth-authorization-server[/api]`
  deixam o SPA pelo 404 da API. O resto da borda é o mesmo — SPA,
  `/conectar-ia`, `/api/`, `/assets/` e os headers de segurança (§10.7).
- nasce a rede `sas_borda_mcp`, só com o `web`; a `sas_dados_mcp` só nasce com
  o MCP ligado.
- `db`, `postgrest`, `api` e `migrate` têm o MESMO hash de serviço de `ca4c68f`,
  e o `db` não é recriado (provado com `up -d`, §10.7). O `api` é recriado assim
  mesmo, **com o mesmo código**: este branch mexeu em
  `api/tests/test_migrations_do_mcp.py`, e `api/tests/` entra na imagem pelo
  `COPY . .` (não está no `api/.dockerignore`) — imagem nova, container novo.
- o `deploy.sh` diz "MCP da coordenação desligado", não toca no login e
  reinicia só o `postgrest`, como antes. Nada pede `--migrar`.

### 10.3 · Como ligar

Antes, nesta ordem: o portão de LGPD (§5.4 — a base legal do art. 14
registrada e a conta do provedor, §6) e o SES para o código do e-mail da conta
de IA, com os três cuidados da §9 (segundo passo, item 2). Depois, **só
acrescentar linhas ao `.env` e rodar o deploy**:

1. No servidor, como `sas`, em `/opt/sas/infra/vps`, acrescentar ao `.env` —
   sem aspas, cada chave uma vez:

   ```sh
   COMPOSE_PROFILES=mcp                          # liga o postgrest_mcp e o mcp
   POSTGREST_MCP_PASSWORD=                       # openssl rand -hex 32 (ver abaixo)
   MCP_HABILITADO=true                           # o portão: sem ele o mcp não sobe
   MCP_URL_PUBLICA=https://portalsas.online/mcp
   MCP_EMISSOR_OAUTH=https://portalsas.online/api
   MCP_URL_DO_APP=https://portalsas.online       # só a API: para onde o /oauth/authorize manda
   # As decisões de 26/10 já são o padrão nos dois processos. Só para mudar —
   # e então vale para a API e para o mcp de uma vez, porque é a mesma linha:
   # MCP_EMISSAO_SO_ADMINISTRADOR=false
   # MCP_MOSTRAR_NOME_DO_ALUNO=true
   # O SES, só da API, se ainda não estiver no .env:
   AWS_SES_ACCESS_KEY_ID=
   AWS_SES_SECRET_ACCESS_KEY=
   EMAIL_REMETENTE=
   EMAIL_DESTINATARIO_TESTE=                     # VAZIO: preenchido, o código vai para a caixa de teste
   ```

   A senha, sem passar pela tela nem pelo argv de processo nenhum (`printf` é
   builtin do bash): `printf 'POSTGREST_MCP_PASSWORD=%s\n' "$(openssl rand -hex
   32)" >> .env`. Um `.env` que o `deploy.sh` gerou depois deste branch já tem
   a linha — confira antes com `grep -c '^POSTGREST_MCP_PASSWORD=' .env`. Com a
   chave duplicada, o compose e o deploy usam os dois a ÚLTIMA (conferido no
   Compose v5.2.0), mas uma só é o certo.
2. `./infra/vps/deploy.sh` — com o `--rapido` do passo 0 da §9 enquanto aquele
   portão estiver vermelho, e sem `--migrar`: as migrations do MCP estão
   aplicadas desde 27/10. Em ordem, o deploy: constrói `sas-api`, que é também
   a imagem do mcp → confere as migrations → **grava a senha no
   `autenticador_mcp`** → `up -d`, que cria o `postgrest_mcp` e o `mcp` e
   recria o `api` (o `.env` mudou, e ele o lê pelo `env_file`) → reinicia
   `postgrest` e `postgrest_mcp` → espera o `/api/health` e o 401 do `/mcp` →
   smoke. O `web` não é recriado: o nginx acha o mcp pelo resolver, em até
   30 s (`valid=30s`).
3. O smoke do fim tem de dizer "MCP ligado: POST /mcp sem token → 401 com
   resource_metadata" e os quatro metadados em JSON.
4. A prova de papéis, de dentro da rede (§9, segundo passo, item 7): `docker
   compose exec -T api python -m scripts.verificar_papeis_do_mcp --mcp
   http://postgrest_mcp:3000 --api http://postgrest:3000 --ferramentas
   </dev/null`.
5. No log, as linhas de `MCP_EMISSAO_SO_ADMINISTRADOR` e
   `MCP_MOSTRAR_NOME_DO_ALUNO` da API e do mcp têm de ser iguais
   (`registrar_no_log`, §5.6). Depois, conectar uma IA (§5.3).

Faltando uma linha, nada abre por engano — cada falta falha fechado:

| Faltou | O que acontece |
|---|---|
| `COMPOSE_PROFILES=mcp` | o MCP segue desligado: nenhum container, e o smoke diz "desligado" |
| `POSTGREST_MCP_PASSWORD` | o deploy avisa e segue; o `postgrest_mcp` vai sem senha, o Postgres recusa, e ele reinicia em laço; o smoke reprova (profile ativo, `/mcp` → 503) |
| senha fora do formato | o deploy para antes do `up -d`, e os containers seguem na versão anterior |
| `MCP_HABILITADO=true` ou `MCP_URL_PUBLICA` | o guard do mcp recusa subir; o smoke reprova |
| `MCP_EMISSOR_OAUTH` | o mcp sobe sem OAuth, só com token pessoal; o smoke reprova o 401 sem `resource_metadata` |
| `MCP_URL_DO_APP` | a API deixa o OAuth desligado (404); o smoke reprova os metadados do RFC 8414 |

### 10.4 · Como desligar

1. Tirar `mcp` do `COMPOSE_PROFILES` e pôr `MCP_HABILITADO=false` (a tela de
   Conexões de IA volta a dizer que o servidor está desligado).
2. `docker compose stop mcp postgrest_mcp && docker compose rm -f mcp
   postgrest_mcp`. **O `up -d` não para serviço de profile inativo**, e o
   `docker compose down` com o profile já fora do `.env` também não o remove
   (provado em 27/10): sem este passo, o MCP segue no ar. Nomeado, o serviço
   responde ao `stop` mesmo com o profile inativo.
3. `./infra/vps/deploy.sh`: recria o `api` com o `.env` novo, e o smoke diz
   "desligado" — ou reprova com "sobrou o mcp de pé", se o passo 2 faltou.
4. Opcional, para voltar ao estado de 27/10: `echo "ALTER ROLE
   autenticador_mcp PASSWORD NULL;" | docker compose exec -T db psql -U
   postgres -d sas`. Os tokens emitidos seguem no banco, e nada os aceita.

### 10.5 · O que o `deploy.sh --verificar` confere

Quem diz se o MCP está ligado é o servidor — o profile `mcp` ativo no compose,
perguntado por ssh —, e não a resposta: com o profile ativo, um 503 é o mcp
fora do ar, e não "desligado"; sem o profile, um 401 é container que sobrou de
pé. Antes de tudo, `GET /mcp` com o `index.html` do SPA reprova nos dois modos:
é o `nginx.conf` sem estas locations.

| `POST /mcp` sem token | profile `mcp` no servidor | Resultado |
|---|---|---|
| o `index.html` do SPA | qualquer | FALHA — o nginx sem as locations do MCP |
| 401 com `resource_metadata` | ativo | ok, e os quatro metadados têm de vir em JSON, com 200 |
| 401 com `resource_metadata` | inativo | FALHA — sobrou o mcp de pé |
| 401 sem `resource_metadata` | qualquer | FALHA — o mcp sem `MCP_EMISSOR_OAUTH` |
| 503 | inativo | ok, "desligado" — e nenhum metadado pode ser o SPA |
| 503 | ativo | FALHA — o mcp não está atendendo |
| 503 | sem ssh | aviso — desligado ou fora do ar, sem saber qual |
| outro (o 405 do nginx velho, por exemplo) | qualquer | FALHA |

O "só o web publica porta" segue igual: nenhum dos dois serviços novos tem
`ports:`.

### 10.6 · O que a proposta anterior dizia e não vale mais

- **A senha no `environment:` do `db`, para o `\getenv` do psql.** Mudaria o
  hash do `db`, e o `up -d` recriaria o container do banco de produção. Agora a
  senha sai do `.env` pelo `grep`, é conferida contra `^[0-9a-f]{64}$` (o
  formato do `openssl rand -hex 32`) e chega ao psql pelo PIPE, como `\set` —
  nenhum argv a leva, nem no servidor. E a sessão desliga `log_statement`,
  `log_min_error_statement` e `log_min_duration_statement` antes do `ALTER
  ROLE`: sem isso, num erro ou com `log_statement` ligado, o Postgres poria o
  comando, com a senha em claro, no log do container (§10.7).
- **`${X:?}` nos serviços do MCP** — a senha, `MCP_HABILITADO`,
  `MCP_URL_PUBLICA`, `MCP_EMISSOR_OAUTH`. O compose interpola o arquivo INTEIRO
  antes de aplicar os profiles: com `:?`, faltar uma delas quebraria todo
  `docker compose` da stack com o MCP desligado — deploy, cron, `ps` (provado
  no Compose v5.2.0). Os padrões agora falham fechado na hora de subir: senha
  vazia, que o login recusa, e `MCP_HABILITADO=false`, que o guard recusa. A
  trava de `api/tests/test_migrations_do_mcp.py` que exigia `:?` em produção
  passou a aceitar o padrão vazio, com o porquê escrito no teste.
- **`build:` próprio no `mcp`.** O build do deploy roda com `--profile tools`,
  e o `--profile` da linha de comando SUBSTITUI o `COMPOSE_PROFILES` do `.env`
  (conferido): o `mcp` nunca seria reconstruído e subiria o código do primeiro
  deploy. Agora é `image: sas-api`, com `pull_policy: never`.
- **Exigir a `POSTGREST_MCP_PASSWORD` num `.env` existente, com o `grep -qE`
  das obrigatórias, e acrescentá-la à mão.** Exigir quebraria o deploy de quem
  não ligou o MCP. O deploy não acrescenta nada a um `.env` que já existe; com
  o MCP ligado e sem a senha, avisa e segue — o `postgrest_mcp` falha fechado,
  e o smoke reprova.
- **O restart incondicional `restart postgrest postgrest_mcp`.** Com o profile
  inativo o serviço não existe; o `postgrest_mcp` só entra no restart com o MCP
  ligado.
- **"O container `web` precisa recarregar o `nginx.conf`"** (§9, segundo
  passo, item 6). Quem o faz é o próximo deploy, que recria o `web`; ligar o
  MCP depois não mexe no `web`.
- **O mcp parado dando o 502 cru do nginx.** A proposta não tinha resposta para
  ele; agora é o 503 do `@mcp_fora_do_ar`, com `resolver_timeout 5s` (desligado,
  o DNS do Docker repassa a pergunta para fora, e o padrão de 30 s seguraria a
  requisição). Os dois do RFC 9728 também sobrescrevem o `X-Forwarded-For`,
  porque o mcp confia nele.
- **"Os smokes do `--verificar` ganham os três da §9, passo 8."** Ganharam,
  adaptativos (§10.5).

### 10.7 · Como foi provado *(27/10, na máquina local)*

Em stacks descartáveis — containers e redes com o prefixo `sas-infra-teste-`,
portas altas só em `127.0.0.1`, `.env` falso —, com Docker 29.6.1 e Compose
v5.2.0. Nada rodou contra o servidor.

- **A interpolação.** Um compose mínimo com `${X:?}` num serviço de profile
  inativo: `docker compose config` falha ("required variable … is missing a
  value") com o profile ligado ou não. E `--profile tools`, com
  `COMPOSE_PROFILES=mcp` no `.env`, deixa os serviços do `mcp` de fora.
- **O `config`** do `infra/vps/docker-compose.yml` (cópia num diretório
  temporário, com `.env` falso): desligado, `db postgrest api web`; ligado,
  mais `postgrest_mcp` e `mcp`, este com a imagem `sas-api`; ligado sem
  nenhuma `MCP_*`, a URI do `postgrest_mcp` sai sem senha e `MCP_HABILITADO`,
  `false`.
- **O hash.** `config --hash '*'` do compose de `ca4c68f` e do deste branch,
  no mesmo diretório: só o `web` muda. O `config --hash` do Compose v5 não
  inclui o conteúdo do `env_file` — o `api` dá o mesmo hash com e sem
  `MCP_HABILITADO` no `.env` —, e por isso a prova do `db` é a de baixo.
- **O `db` não é recriado.** O compose de produção de `ca4c68f`, `up -d db
  postgrest` num projeto `-p sas-infra-teste-recriar`; trocado pelo deste
  branch, `up -d` com o MCP desligado e depois ligado: o MESMO container do
  `db` e do `postgrest` nas três vezes.
- **O `env_file` e a imagem compartilhada**, num projeto mínimo com o desenho
  do `mcp`: acrescentar `MCP_HABILITADO=true` ao `.env` recria quem o lê (o
  `api` pelo `env_file`, o `mcp` pela interpolação); mudar o código do `api` e
  rodar o build do deploy recria os dois com a mesma imagem nova; sem imagem
  nenhuma, o `up -d` constrói o `api` e sobe o `mcp` sem tentar pull. E nem
  `docker compose down` nem `docker compose --profile tools down` removeram o
  `mcp` com o profile dele inativo.
- **O passo da senha**, extraído do bloco remoto do `deploy.sh` e rodado como
  está contra o `db` do compose de produção, com papéis que imitam a 0071 e
  `log_statement = 'all'` no servidor. Desligado, não toca no banco. Ligado sem
  senha, avisa e segue. Maiúsculas, 63 caracteres ou aspas: para antes do psql.
  Com a senha, o login entra com ela e recusa outra, e o `postgrest_mcp` do
  compose de produção, com a URI do mesmo `.env`, serve as colunas da lista
  branca e recusa a de fora (42501). De novo: idempotente. Depois de `PASSWORD
  NULL` (o `down` + `up` da 0071), o `postgrest_mcp` reinicia em laço até o
  passo seguinte, que o devolve. Sem o login, para com erro. Em todos os casos
  a senha não apareceu no argv de processo nenhum (`docker`, `grep`, `tail` e
  `cut` registrados) nem no log do Postgres; o controle — o mesmo `ALTER ROLE`
  sem os `SET` — apareceu lá, em claro.
- **O nginx**, na imagem do `web/Dockerfile` (`nginxinc/nginx-unprivileged:1.27-alpine`,
  nginx 1.27.5), com este `nginx.conf`, certificado autoassinado e upstreams
  falsos `api` e `mcp` que ecoam caminho e cabeçalhos. Sem o `mcp`: sobe, e
  `/mcp` e os dois do RFC 9728 dão o 503, com os headers de segurança. Com ele:
  `/mcp` chega com `X-Forwarded-For`, `X-Real-IP` e `X-Forwarded-Proto` forjados
  SOBRESCRITOS, e o nginx o achou sem ser reiniciado. Nos dois modos:
  `/api/alunos?x=1` chega como `/alunos?x=1`; `/`, `/conectar-ia` e rota
  profunda seguem com CSP `frame-ancestors 'none'` e `X-Frame-Options: DENY`;
  cada `.well-known` vai para quem deve, com o caminho inteiro.
- **O `--verificar`**: a seção de smoke do `deploy.sh`, rodada como está
  contra essa stack, com o `ssh` respondendo pelo compose dela. Ligado e certo,
  e desligado (no bash 3.2 do macOS e no 5 do Homebrew): zero falhas. Profile
  ativo com o mcp parado, mcp sobrando com o profile inativo, 401 sem
  `resource_metadata`, e o `nginx.conf` de `ca4c68f` nos dois modos: reprovam.
  Sem ssh: aviso.
- `bash -n` e `shellcheck` 0.10.0 (pela imagem oficial, sem rede) no
  `deploy.sh` e no bloco remoto extraído: os mesmos achados de antes, nenhum
  novo. A suíte do backend: 2627 passando, 27 pulados e os 3 de
  `test_canvas_publicacao.py` falhando — os 4 testes de produção do compose em
  `test_migrations_do_mcp.py`, antes pulados, passaram a rodar.

**O que não foi verificado:**

- nada no servidor: nem o `deploy.sh`, nem o `--verificar`, nem a versão do
  Compose de lá;
- o `web` em duas redes no Linux do VPS, com o ufw e o iptables do Docker — a
  porta publicada e a rota de saída; a prova foi no Docker Desktop;
- o processo `app.mcp` de verdade atrás deste nginx, e a API de verdade nos
  `.well-known` do RFC 8414: os upstreams eram ecos;
- o `verificar_papeis_do_mcp` de dentro do container (§9, segundo passo, item
  7);
- a versão de correção do nginx de produção: `1.27-alpine` é tag móvel, e a
  prova usou 1.27.5;
- o pior caso do `valid=30s`: na prova, o nginx achou o mcp em ~1 s.

`/mcp/`, com barra, cai no SPA como qualquer caminho desconhecido: a location é
exata, como o endereço que a IA configura.

### 10.8 · O que segue valendo da proposta

**Uma chave, dois processos.** `MCP_EMISSAO_SO_ADMINISTRADOR` é UMA linha do
`.env`, lida pela API (pelo `env_file`) e pelo `mcp` (pela interpolação no
compose), as duas com o padrão `false` da decisão 2 — um `:-true` na
interpolação desfaria a decisão no deploy. Cada processo lê a do seu ambiente,
e nada os obriga a concordar: religada só na API, a tela diz "só o
administrador" e o `mcp` segue aceitando os tokens dos coordenadores; só no
`mcp`, a tela emite e aprova o que o MCP recusa (§5.6, lente 2). Por isso ela
nunca vai para o `environment:` de um só dos dois. `MCP_MOSTRAR_NOME_DO_ALUNO`
(padrão `true`, decisão 1) só o `mcp` lê. Os outros `MCP_*` do processo do mcp
(limite por minuto, teto de linhas…) ficam no padrão do código: ele não tem
`env_file`, e mudar um deles pede a linha no `environment:` dele.

Os tetos do código de aprovar, todos com padrão no código e só no `.env` para
mudar (`mcp/configuracao.py`; só a API os lê):

| Variável | Padrão | O que limita |
|---|---|---|
| `MCP_OAUTH_CODIGOS_POR_PEDIDO` | 5 | códigos enviados por pedido de conexão |
| `MCP_OAUTH_CODIGOS_POR_EMAIL_POR_DIA` | 10 | códigos por e-mail por dia, de qualquer IP — a trava da §5.6 |
| `MCP_OAUTH_CODIGOS_POR_IP_POR_HORA` | 20 | pedidos de código por IP por hora |

Os do código de confirmação do card (20 por hora por conta, 5 por dia por
e-mail) são constantes de `routes/mcp_emails_ia.py`, sem variável.

**Sem SES configurado em produção, o código não sai.** Nem o de aprovar, nem o
de confirmação: nada é enviado, e só fica um ERROR `[AÇÃO NECESSÁRIA]` no log.
O `/codigo` responde 202 como sempre, e o card, 503. Sem SES, nenhum e-mail se
confirma e nenhuma conexão OAuth se aprova; o token pessoal segue (§9). O
`mcp` não pode ter as chaves do SES: o guard dele recusa subir com elas no
ambiente — e não as tem, porque não tem `env_file`.

O `MCP_EMISSOR_OAUTH` tem de ser IDÊNTICO nos dois processos: o cliente
compara o `issuer` do RFC 8414 com o `authorization_servers` do RFC 9728 letra
por letra, e uma barra a mais o faz descartar o metadado. E ele supõe que a API
continue sob `/api`, com o nginx tirando o prefixo. `/api/oauth/*` já passa
pelo `location /api/`, que tira o `/api`. Opcional, e não feito: `limit_req` em
`/mcp`, `/api/oauth/token` e `/api/oauth/register`, como teto por IP real na
borda — os tetos do processo dependem do IP certo.

**Os `.env.example` precisam ganhar as linhas**, e este branch não os mexe nem
os leu (a regra de nunca ler `.env*`): fica para quem abrir o PR.
`infra/vps/.env.example`: `POSTGREST_MCP_PASSWORD=` vazia (o `deploy.sh` a
sorteia num `.env` novo — e a acrescenta mesmo se o exemplo não tiver a linha)
e o bloco de §10.3 **comentado**, com `# COMPOSE_PROFILES=mcp`: descomentado,
todo servidor novo nasceria com o MCP ligado. `api/.env.example`: as `MCP_*`
de §10.3, com os padrões `MCP_EMISSAO_SO_ADMINISTRADOR=false` e
`MCP_MOSTRAR_NOME_DO_ALUNO=true`, e os três tetos, comentados.
