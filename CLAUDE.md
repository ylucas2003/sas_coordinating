# SAS — contexto para o Claude Code

Interface de coordenação das turmas ITA/IME do Colégio Ari de Sá: acompanha o
desempenho de ~900 alunos em simulados e ciclos de provas voltados a ITA e IME,
e **sinaliza o que merece atenção** em vez de esperar que o coordenador saiba o
que procurar. Tem também área do aluno, com chat mentor.

Documentação de produto e de decisão em [docs/](docs/), numerada. **Antes de
abrir sprint, leia [docs/19-roadmap.md](docs/19-roadmap.md)** — é o único que diz
o que está feito, o que falta e o que vem. O que está
aqui é o que **não** se deduz lendo o código — e o que costuma estar errado nos
documentos.

## Onde os documentos mentem

Alguns `.md` descrevem um estado que já não existe. Quando divergirem do código,
**o código vence** — e vale corrigir o documento na passagem.

| Documento | O que ele diz | O que é verdade |
|---|---|---|
| [api/README.md](api/README.md) | "scaffold inicial, rotas devolvem listas vazias / 404" | O backend está completo e em produção: ingest, stats, alertas, chat com tools, sync do Canvas, lembretes por e-mail |
| [docs/00-tech-stack.md](docs/00-tech-stack.md) §Backend | Banco é Supabase hospedado | Postgres 16 + PostgREST em container, local e na VPS. Nada de Supabase desde 13/08/2026 |
| [docs/00](docs/00-tech-stack.md) §Deploy | Front na Vercel, backend em Render/Fly/Railway | VPS própria na Hostinger (São Paulo), `portalsas.online`, tudo num `docker compose`. (README corrigido em 22/08) |
| [docs/16-plano-migracao-react.md](docs/16-plano-migracao-react.md) | Migração em andamento, `web/js/` legado | **Terminada.** `web/js/` não existe mais; o front é React 19 + TS inteiro |
| [docs/03-design-system.md](docs/03-design-system.md) | verde = acima da meta, vermelho = abaixo; sombra em card; quatro raios; um tema só | **Histórico desde 05/09/2026.** Não existe verde na interface: acima do corte é preenchido, abaixo é vazado, e a intensidade carrega a distância. Sombra morreu, raios viraram três, e existe tema escuro. A régua é [docs/brief-claude-design-coordenacao.md](docs/brief-claude-design-coordenacao.md); o que foi feito está em [docs/37](docs/37-plano-refatoracao-visual-coordenacao.md) |
| [web/CLAUDE.md](web/CLAUDE.md) *(já corrigido)* | "`telas/Banco/` serve os dois cascos" | Não serve: o aluno tem `telas/Aluno/EstudarBanco.tsx`, e `perfil="aluno"` em `Banco.tsx` é código morto |
| [docs/00](docs/00-tech-stack.md) §Frontend *(já corrigido em 05/09)* | Tokens são `--color-navy`/`--color-amber` em `web/styles/tokens.css`; CSS Modules por tela | `tokens.css` **não existe** desde a fase 0 do [docs/39](docs/39-plano-refatoracao-design.md). Os tokens são os seis papéis em `--sas-*` (`papeis.css`), lidos direto; o CSS é global por prefixo de tela, e CSS Modules nunca aconteceu |
| Qualquer `.md` que fale de `/painel` com filtros, KPIs, busca e tabela | O Painel é a tela de varredura de 900 alunos | Desde a fase 2 do [docs/39](docs/39-plano-refatoracao-design.md) o Painel é **hub**: três cartões e a faixa de decisão. A tabela mora em `telas/CicloFicha/TabelaDoCiclo.tsx`. Os nomes `dominio/painel.ts`, `montarPainel`, `.painel-tabela__*` são herança |

## O ponto mais confuso do projeto: `get_supabase()` não fala com Supabase

O nome ficou por herança. O que ele devolve é um cliente **PostgREST** — que é
justamente o que o Supabase hospedava por baixo. Por isso os 273
`cliente.table(...)` espalhados pelo backend continuaram funcionando quando o
Supabase saiu: trocou-se o servidor, não o protocolo.

Consequência prática: **o backend nunca escreve SQL.** Não há ORM, não há
`psycopg` nas rotas (só no runner de migrations). Toda leitura e escrita é
`.table(...).select(...)/.insert(...)` — a API do PostgREST. Ver
[api/app/supabase_client.py](api/app/supabase_client.py), que explica os dois
modos e por que existem duas funções de cliente.

## Mapa

```
sas/
├── api/          FastAPI · ~15.500 linhas · o cérebro (stats, LLM, Canvas, e-mail)
│                 `api/app/mcp/` é OUTRO processo, na mesma imagem: o MCP da
│                 coordenação (`python -m app.mcp`, docs/43 §5), com PostgREST e
│                 login de banco próprios. Escrito, FORA de produção
├── web/          React 19 + TS + Vite · ~13.000 linhas
├── infra/
│   ├── vps/      stack de PRODUÇÃO — autônoma, não é override do compose da raiz
│   ├── postgres/ init dos papéis do PostgREST
│   └── cdk.out/  artefato morto do agendador AWS (EventBridge). O código-fonte
│                 saiu na migração pro VPS; hoje quem agenda é o cron do
│                 sistema — `infra/vps/crontab-sas` + `cron-sas.sh`. Vários
│                 comentários no backend ainda dizem "EventBridge": é resíduo
├── docs/         00→31, numerados; 14 e 15 são produção; **19 é o estado**
│                 (feito / pendente / próximo); 20 e 21 são o sprint mobile;
│                 22 e 23 são o banco de questões (há DOIS "23": o histórico
│                 do banco e o redesenho do casco); 24 e 25 são o
│                 brainstorming de 29/08 — jornada do aluno e coordenação;
│                 26, 27 e 28 são as mecânicas do jogo, o Tio Léo e o banco do
│                 aluno; 29 é o que falta para o aluno usar; **30 é GERADO** de
│                 `web/src/dados/aluno/registro.ts` e `npm test` quebra se ele
│                 envelhecer — é o estado da área do aluno, fonte por fonte;
│                 31 é a Sprint 5 (régua única, assistente com contexto,
│                 gráficos em camadas) — e o §0 dele é o levantamento que
│                 achou duas partes propostas já feitas sem registro;
│                 sprints.html é a mesma coisa em página; 36 é a faixa 1 e 2
│                 do aluno; **37 é a refatoração visual da coordenação** — a
│                 pilha de cor, o fim do semáforo e o padrão de campo, com o
│                 §6 dizendo o que NÃO foi verificado no browser; 38 é a
│                 cantina (cardápio, pedido do aluno, contas da cantina) — e o
│                 §1.1 dele lista os três lugares que quebram ao existir um
│                 TERCEIRO tipo de sessão, e o §10.2 diz o que NÃO foi
│                 verificado no browser; **39 é a refatoração de design da
│                 coordenação a partir da prancheta** (fases 0 a 5 feitas), e o
│                 §6 dele é a varredura de consistência — o que ela consertou e
│                 as seis coisas que ficaram, com caminho; **41 é a captação
│                 externa** (gente de fora, por resultado público de
│                 olimpíada/vestibular) — lê-se de trás pra frente: §15–§20
│                 são o modelo vigente, o resto é histórico; 42 é o horário
│                 de estudos do aluno (em produção); **43 é o das ferramentas
│                 do assistente e do MCP da coordenação** (nasceu 42 e passou a
│                 43 em 27/10) — Fases 0 a 3 em produção desde 27/10, menos
│                 o processo do MCP; o §0.1 e o §0.2 dele são as decisões do
│                 dono de 26 e 27/10, o §8 o que NÃO foi verificado (o §8.1,
│                 a prova de ponta a ponta de 27/10), o §9 a ordem do deploy
│                 e o §10 o MCP no `infra/vps` e como ligá-lo
├── banco-questoes/  pipeline do banco ITA·IME (PDF → JSON) e as taxonomias dos
│                 editais. Fora de `api/` de propósito — nada aqui roda em
│                 requisição. **As 934 questões NÃO estão aqui**: moram no
│                 Postgres desde 22/08 (docs/22 §13); `questoes_json/` é saída
│                 local, não versionada
└── docker-compose.yml   stack de DESENVOLVIMENTO (db + postgrest + api + web, e
                         o `postgrest_mcp` + `mcp` do MCP, só no loopback e
                         numa rede própria, `dados_mcp`)
```

Contexto por camada em [api/CLAUDE.md](api/CLAUDE.md) e [web/CLAUDE.md](web/CLAUDE.md).

## Comandos

```sh
docker compose up                        # front :8080 · API :8000 · postgrest :3000 · db :5432
                                         # e postgrest_mcp :3001 · mcp :8001, só no loopback
docker compose run --rm migrate status   # ver migrations aplicadas/pendentes
docker compose run --rm migrate up       # aplicar

cd api && ./.venv/bin/python -m pytest tests/ -q   # 2623 testes (+31 pulados); 3 de test_canvas_publicacao.py falham também no main
cd api && ./.venv/bin/ruff check .                 # lint
cd web && npm test && npm run lint && npm run typecheck

./infra/vps/deploy.sh                    # deploy em produção (portões → rsync → build → smoke)
./infra/vps/deploy.sh --migrar           # idem, autorizando migrations pendentes
./infra/vps/deploy.sh --rapido           # pula os portões — SÓ depois de rodar as suítes à mão
./infra/vps/deploy.sh --verificar        # só o smoke test em https://portalsas.online
```

Num worktree sem `api/.env`, o `pytest` precisa de `APP_ENV=dev` na frente: o
default é `production`, e o guard recusa (armadilha 3). ⚠️ Em 26/10 o `pytest`
do `main` reprova em 3 testes de `api/tests/test_canvas_publicacao.py` (já
reprovava em 24/10), e com eles o portão do `deploy.sh`: os deploys saem com
`--rapido`, depois de rodar as suítes à mão e conferir que só esses 3 falham
(docs/19, docs/43 §9). E o `deploy.sh` sobe a ÁRVORE DE TRABALHO: deploy de
clone limpo no commit do merge, nunca de um worktree com trabalho por
commitar.

O MCP da coordenação, local (docs/43 §5). Em produção estão as tabelas e a
tela de Conexões de IA; o processo do MCP, não (docs/43 §10):

```sh
docker compose run --rm migrate up             # 0071–0073: papéis, token, OAuth
# a senha do login do postgrest_mcp, que a 0071 cria SEM senha — o comando
# (ALTER ROLE autenticador_mcp …) está no comentário do docker-compose.yml;
# de novo a cada down + up da 0071
docker compose restart postgrest postgrest_mcp # os dois cacheiam o schema
cd api && ./.venv/bin/python -m scripts.verificar_papeis_do_mcp \
    --mcp http://127.0.0.1:3001 --api http://127.0.0.1:3000 --ferramentas
cd api && ./.venv/bin/python -m scripts.criar_token_mcp --email <conta> --nome "Claude Code"
#   o token vai para um arquivo 0600 (nunca para o stdout); --listar e --revogar <id>
#   o cliente aponta para http://localhost:8001/mcp com `Authorization: Bearer <token>`
#   (não verificado com o Claude Code de verdade — docs/43 §8)
```

Até a 0071 e a senha existirem, o `postgrest_mcp` sai com erro no `docker
compose up` — nada da API depende dele.

O `docker` do PATH está quebrado nesta máquina (symlink para um
`/Volumes/Docker/` que não existe); o binário real é
`/Applications/Docker.app/Contents/Resources/bin/docker`.

## Armadilhas que já custaram caro

1. **O PostgREST cacheia o schema na inicialização.** Depois de qualquer
   migration que crie ou altere tabela, `docker compose restart postgrest` —
   senão as mudanças voltam **404**, e o 404 parece bug de código.

2. **Não existe paginação em lugar nenhum.** `PGRST_DB_MAX_ROWS` foi deixado
   sem valor de propósito ([infra/vps/docker-compose.yml](infra/vps/docker-compose.yml)):
   um teto truncaria leitura em silêncio e as estatísticas ficariam erradas
   *sem erro*. Dívida conhecida em `nota`, `v_nota_dimensoes` e
   `questao_resposta_aluno`. Ao mexer nessas tabelas, pense no volume.

3. **`APP_ENV` tem default `production` e o guard falha fechado.**
   [`_validar_configuracao`](api/app/main.py) recusa subir com segredo de dev,
   senha demo, CORS com localhost. Local funciona porque `APP_ENV=dev` é
   declarado explicitamente. Nunca troque esse default.

4. **O Docker escreve no iptables por cima do ufw.** Na stack de produção só o
   serviço `web` tem `ports:`. Publicar a porta do `db` ou do `postgrest` os
   expõe na internet mesmo com firewall fechado — e o papel anônimo do
   PostgREST tem acesso total ao schema.

5. **O tempo real da cantina depende de `UVICORN_WORKERS=1`.** O barramento de
   eventos ([api/app/cantina_eventos.py](api/app/cantina_eventos.py)) mantém uma
   fila por assinante **na memória do processo**. Com dois workers, cada um teria
   as suas e metade dos assinantes pararia de receber evento **sem erro
   nenhum** — a tela só ficaria velha. O `UVICORN_WORKERS=1` já era invariante
   declarada por causa das travas do sync e do despachante; este é o terceiro
   motivo. Subir os workers exige trocar o barramento por `LISTEN/NOTIFY`, e aí
   `psycopg` entra nas rotas pela primeira vez (docs/38 §9.3.2).

6. **`docker compose run` dentro de `ssh bash -s` engole o script.** A parte
   remota do `deploy.sh` viaja por stdin; qualquer comando que leia stdin lê o
   resto do script e o deploy "termina com sucesso" sem aplicar nada — foi
   assim no deploy da Sprint 2. Todo `compose run` ali leva `-T </dev/null`.

7. **Dados de menores de idade (LGPD).** Nada de asset ou telemetria de
   terceiro no front — foi por isso que as fontes saíram do Google Fonts. Vale
   para qualquer CDN, pixel ou serviço externo que alguém pense em adicionar.

8. **O MCP tem PostgREST e login de banco PRÓPRIOS — nunca o `authenticator`
   da API.** O `postgrest_mcp` entra como `autenticador_mcp` (0071: `NOINHERIT`,
   membro só do `sas_mcp`, senha definida por fora da migration), sem
   `PGRST_JWT_SECRET` e com `PGRST_DB_CONFIG=false`, e o `mcp` só enxerga a
   rede `dados_mcp`. Com o login da API, um `pgrst.*` gravado no papel ou um
   `SET ROLE` numa requisição levavam ao `sas_service` — provado num Postgres
   descartável em 24/10 (docs/43 §5.2). Não "simplifique" apontando o MCP para
   o `postgrest` da API: o guard de boot e a sonda de privilégio recusam subir
   (`api/app/mcp/configuracao.py`, `dados.exigir_papel_restrito`). E a
   armadilha 4 vale em dobro: em produção nenhum dos dois ganha `ports:`, porque
   o anônimo do `postgrest_mcp` lê a lista branca sem token. Pelo mesmo motivo
   o token que o MCP aceita é **OPACO** (só o sha256 em `token_mcp`), **nunca
   JWT**: sem `PGRST_JWT_SECRET` no PostgREST e sem `JWT_SECRET_KEY` no
   processo, nenhum JWT — nem forjado — troca o papel ou abre o MCP
   ([api/CLAUDE.md](api/CLAUDE.md), Autenticação).

9. **O MCP manda dado de menor a um provedor de IA de fora.** Desde 26/10, por
   decisão do dono, ele devolve o NOME do aluno (`MCP_MOSTRAR_NOME_DO_ALUNO`,
   padrão `true`; o pseudônimo virou opção): é a armadilha 7 levada ao
   servidor. Fora de dev o processo não sobe sem `MCP_HABILITADO=true`, e esse
   portão espera a base legal do art. 14 da LGPD (docs/43 §5.4). Tool nova da
   coordenação nasce FORA do MCP (`expor_no_mcp` nos `METADADOS`), e
   `api/tests/test_chat_exposicao_no_mcp.py` reprova tool sem decisão; tool
   exposta que passar a ler coluna nova precisa de migration, porque a lista
   branca da 0071 é por coluna.

10. **Conectar o claude.ai ou o ChatGPT é provar a posse de um e-mail, e o
    e-mail sai pelo SES.** A conexão OAuth é aprovada pelo código de 6 dígitos
    enviado ao e-mail da conta de IA que o coordenador cadastrou e CONFIRMOU —
    o cadastro manda outro código antes, e o e-mail que só aguarda não recebe
    nem aprova — sem sessão do SAS (decisão do dono de 26/10, docs/43 §5.3 e
    §5.6). Erro do SES vai ao log só com o e-mail mascarado e o tipo da
    exceção: a mensagem do `MessageRejected` traz o endereço. O código passa por
    `api/app/lembretes/email.py`: com `EMAIL_DESTINATARIO_TESTE` preenchido ele
    vai para a caixa de TESTE; sem SES fora de dev, não sai nada e só o log
    sabe; e as chaves do SES na API fazem também o despachante dos lembretes
    (`/disparos/processar`, de hora em hora no `crontab-sas`) passar a enviar
    o que estiver na fila de `disparo` — o e-mail de produção está adiado desde
    21/08 (docs/15 §2). O token pessoal (Claude Code) não passa por e-mail: é
    emitido pelo coordenador logado.

## Convenções

- **Português em tudo**: nomes de arquivo, função, variável, coluna de banco.
  O schema é para ser lido por quem entende do domínio, não só por quem
  programa.
- **Comentário explica o *porquê*, não o *quê*** — e cita a fonte (`docs/14 §4.1`).
  É o padrão do projeto inteiro; ao editar, mantenha.
- `async def` nos endpoints, type hints em toda função, `async/await` em toda I/O.
- Toda migration tem par `.down.sql`.

## Ferramentas ligadas neste repositório

- **Lint automático**: um hook `PostToolUse` roda ruff (`.py`) ou Biome
  (`.ts/.tsx/.js` de `web/src/`) no arquivo recém-editado e devolve o resultado
  na hora — [.claude/hooks/lint-arquivo-editado.sh](.claude/hooks/lint-arquivo-editado.sh).
- **MCP** ([.mcp.json](.mcp.json)):
  - `chrome` — abre o site de verdade: erro de console, requisição de rede,
    trace de performance, screenshot. É como se verifica usabilidade e
    desempenho sem chutar. Configurado com `performanceCrux` e
    `usageStatistics` **desligados**, pela mesma regra de LGPD da armadilha 7.
    O `--viewport 1440x900` é só o padrão de abertura: a ferramenta `emulate`
    troca para celular (`390x844x3,mobile,touch`), throttla rede e CPU.
  - `postgres` — `EXPLAIN`, índice faltando, saúde do banco. Em
    `--access-mode restricted` (leitura). Aponta para o Postgres do compose;
    para outro banco, exporte `SAS_DATABASE_URI`.
  - `mobile` — Simulator do iOS e emulador do Android, para o que o Chrome não
    emula com fidelidade (Safari real, notch, teclado). **Hoje não enxerga
    aparelho nenhum**: falta o Xcode completo — só o Command Line Tools está
    instalado, e o `simctl` não vem nele. Ver [docs/20-mobile.md §2](docs/20-mobile.md).
    Nunca usar as ferramentas de aparelho em nuvem com dado real de aluno.
- **Skills** ([.claude/skills/](.claude/skills/)), copiadas para o repositório em
  vez de instaladas globalmente, para a régua ficar versionada e o diff dela
  aparecer no git:
  - `frontend-design` (Anthropic) — direção visual ao criar ou redesenhar tela.
  - `web-design-guidelines` (Vercel) — revisa UI contra 103 regras de toque,
    safe-area, foco e formulário. As regras vivem em `regras.md` no próprio
    diretório da skill; o `SKILL.md` foi alterado de propósito para ler a cópia
    local em vez de buscar por HTTP a cada revisão.
