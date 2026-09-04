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
│                 sprints.html é a mesma coisa em página
├── banco-questoes/  pipeline do banco ITA·IME (PDF → JSON) e as taxonomias dos
│                 editais. Fora de `api/` de propósito — nada aqui roda em
│                 requisição. **As 934 questões NÃO estão aqui**: moram no
│                 Postgres desde 22/08 (docs/22 §13); `questoes_json/` é saída
│                 local, não versionada
└── docker-compose.yml   stack de DESENVOLVIMENTO (db + postgrest + api + web)
```

Contexto por camada em [api/CLAUDE.md](api/CLAUDE.md) e [web/CLAUDE.md](web/CLAUDE.md).

## Comandos

```sh
docker compose up                        # front :8080 · API :8000 · postgrest :3000 · db :5432
docker compose run --rm migrate status   # ver migrations aplicadas/pendentes
docker compose run --rm migrate up       # aplicar

cd api && ./.venv/bin/python -m pytest tests/ -q   # 331 testes (+15 pulados)
cd api && ./.venv/bin/ruff check .                 # lint
cd web && npm test && npm run lint && npm run typecheck

./infra/vps/deploy.sh                    # deploy em produção (portões → rsync → build → smoke)
./infra/vps/deploy.sh --migrar           # idem, autorizando migrations pendentes
./infra/vps/deploy.sh --verificar        # só o smoke test em https://portalsas.online
```

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

5. **`docker compose run` dentro de `ssh bash -s` engole o script.** A parte
   remota do `deploy.sh` viaja por stdin; qualquer comando que leia stdin lê o
   resto do script e o deploy "termina com sucesso" sem aplicar nada — foi
   assim no deploy da Sprint 2. Todo `compose run` ali leva `-T </dev/null`.

6. **Dados de menores de idade (LGPD).** Nada de asset ou telemetria de
   terceiro no front — foi por isso que as fontes saíram do Google Fonts. Vale
   para qualquer CDN, pixel ou serviço externo que alguém pense em adicionar.

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
    `usageStatistics` **desligados**, pela mesma regra de LGPD do item 6.
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
