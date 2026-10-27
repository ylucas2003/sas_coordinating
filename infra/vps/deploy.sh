#!/usr/bin/env bash
#
# Deploy de produção do SAS, em UM comando e UM arquivo.
#
#   ./infra/vps/deploy.sh                # portões locais → rsync → build → up → smoke
#   ./infra/vps/deploy.sh --migrar       # idem, autorizando as migrations pendentes
#   ./infra/vps/deploy.sh --rapido       # pula os portões locais (lint, teste, typecheck)
#   ./infra/vps/deploy.sh --estrito      # lint deixa de ser aviso e passa a bloquear
#   ./infra/vps/deploy.sh --verificar    # só o smoke test; não toca no servidor
#
# Roda da máquina de desenvolvimento. A parte que executa no servidor viaja por
# stdin (`ssh bash -s`), não de uma cópia em /opt/sas: o passo de deploy é
# sempre o deste arquivo, nunca o que sobrou de um deploy anterior.
#
# Pré-requisitos, cada um de uma vez só e fora daqui:
#   01-preparar-servidor.sh   usuário, firewall, docker, fuso     (servidor, root)
#   00-prep-root.sh           diretórios com o dono certo         (servidor, root)
#   03-tls.sh                 certificado e renovação             (servidor, root)
#
# Variáveis de ambiente:
#   SAS_VPS       destino ssh       (default sas@46.202.150.165)
#   SAS_DOMINIO   domínio público   (default portalsas.online)

set -euo pipefail

DESTINO="${SAS_VPS:-sas@46.202.150.165}"
DOMINIO="${SAS_DOMINIO:-portalsas.online}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

MIGRAR=0
RAPIDO=0
ESTRITO=0
SO_VERIFICAR=0
CONFIRMAR=1

log()   { printf '\n\033[1;34m▸ %s\033[0m\n' "$*"; }
ok()    { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
aviso() { printf '  \033[0;33m!\033[0m %s\n' "$*"; }
erro()  { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

ajuda() {
    # Imprime o cabeçalho até a primeira linha que não é comentário — assim a
    # ajuda não descola do arquivo quando o cabeçalho muda de tamanho.
    awk 'NR>1 && /^#/ { sub(/^# ?/, ""); print; next } NR>1 { exit }' "${BASH_SOURCE[0]}"
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --migrar)          MIGRAR=1 ;;
        --rapido)          RAPIDO=1 ;;
        --estrito)         ESTRITO=1 ;;
        --verificar)       SO_VERIFICAR=1 ;;
        --sem-confirmar)   CONFIRMAR=0 ;;
        --host)            DESTINO="$2"; shift ;;
        -h|--ajuda|--help) ajuda ;;
        *) erro "opção desconhecida: $1"; exit 1 ;;
    esac
    shift
done


# ─── 1. Portões locais ────────────────────────────────────────────────────
# Duas categorias, de propósito:
#
#   BLOQUEIA  teste e typecheck — dizem se o código está QUEBRADO.
#   AVISA     ruff e biome — dizem se o código está FEIO.
#
# Lint não bloqueia porque a árvore de hoje já tem achado herdado (120 no ruff,
# 8 no biome, a maioria de regra nova que entrou com a atualização do linter).
# Um portão que reprova sempre não protege nada: ensina o operador a passar
# `--rapido`, que desliga junto os testes, que são os que importam. Quem quiser
# o bloqueio tem `--estrito`.
#
# O build do Vite fica de fora: quem builda o front é o container, e o
# typecheck já pega quase tudo que quebraria lá.
portoes_locais() {
    log "Portões locais"

    reprovou_lint() {   # $1 = ferramenta, $2 = como rodar à mão
        if [[ $ESTRITO == 1 ]]; then
            erro "$1 reprovou — rode '$2'"; exit 1
        else
            aviso "$1 com achados (não bloqueia; use --estrito para bloquear) — '$2'"
        fi
    }

    if [[ -x "$RAIZ/api/.venv/bin/ruff" ]]; then
        (cd "$RAIZ/api" && ./.venv/bin/ruff check . >/dev/null 2>&1) \
            && ok "ruff" || reprovou_lint ruff "cd api && ./.venv/bin/ruff check ."
        (cd "$RAIZ/api" && ./.venv/bin/python -m pytest tests/ -q >/tmp/sas-pytest.log 2>&1) \
            && ok "pytest" || { erro "pytest reprovou:"; tail -25 /tmp/sas-pytest.log >&2; exit 1; }
    else
        aviso "api/.venv ausente — lint e teste da API pulados"
    fi

    if [[ -d "$RAIZ/web/node_modules" ]]; then
        (cd "$RAIZ/web" && npm run typecheck >/dev/null 2>&1) \
            && ok "typecheck" || { erro "typecheck reprovou — rode 'cd web && npm run typecheck'"; exit 1; }
        (cd "$RAIZ/web" && npm run lint >/dev/null 2>&1) \
            && ok "biome" || reprovou_lint biome "cd web && npm run lint"
        (cd "$RAIZ/web" && npm test >/tmp/sas-vitest.log 2>&1) \
            && ok "vitest" || { erro "testes do front reprovaram:"; tail -25 /tmp/sas-vitest.log >&2; exit 1; }
    else
        aviso "web/node_modules ausente — checagens do front puladas (rode 'cd web && npm install')"
    fi
}


# ─── 2. O que exatamente vai subir ────────────────────────────────────────
# O rsync envia a ÁRVORE DE TRABALHO, não o HEAD. Então o que está sujo no git
# é o que vai para produção, e isso precisa aparecer ANTES, não depois.
resumo_e_confirmacao() {
    local commit sujos atras ramo
    atras=0
    if git -C "$RAIZ" rev-parse --git-dir >/dev/null 2>&1; then
        commit="$(git -C "$RAIZ" log -1 --format='%h %s')"
        sujos="$(git -C "$RAIZ" status --porcelain | wc -l | tr -d ' ')"
        # ⚠️ Árvore ATRASADA em relação ao remoto passava em silêncio até 05/09.
        # Como o rsync envia a árvore de trabalho, um `main` que não puxou sobe
        # sem os commits que já foram mergeados — e o deploy declara sucesso.
        # Aconteceu: o PR #40 foi mergeado no GitHub, o `deploy.sh` rodou de uma
        # árvore 10 commits atrás, e produção ficou sem a migration 0045 e sem
        # dois scripts. Ninguém percebeu até alguém ir procurar a coluna nova.
        #
        # `|| true` porque nem todo ramo tem upstream, e não ter é caso normal
        # (ramo local de teste), não erro que deva interromper o deploy.
        ramo="$(git -C "$RAIZ" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
        if git -C "$RAIZ" rev-parse --verify --quiet '@{u}' >/dev/null 2>&1; then
            git -C "$RAIZ" fetch --quiet 2>/dev/null || true
            atras="$(git -C "$RAIZ" rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)"
        fi
    else
        commit="sem git"; sujos=0
    fi

    log "Vai subir para PRODUÇÃO"
    printf '  destino     %s\n' "$DESTINO"
    printf '  domínio     https://%s\n' "$DOMINIO"
    printf '  commit      %s\n' "$commit"
    if [[ "$sujos" != "0" ]]; then
        printf '  \033[0;33mnão commitado  %s arquivo(s) — o rsync envia a árvore de trabalho\033[0m\n' "$sujos"
        git -C "$RAIZ" status --porcelain | head -10 | sed 's/^/      /' || true
        [[ "$sujos" -gt 10 ]] && printf '      … e mais %s\n' "$((sujos - 10))"
    fi
    if [[ "$atras" != "0" ]]; then
        printf '  \033[0;33mATRÁS DO REMOTO  %s commit(s) — `%s` não puxou\033[0m\n' "$atras" "$ramo"
        printf '  \033[0;33m                 o que já foi mergeado NÃO vai subir; rode `git pull` antes\033[0m\n'
        git -C "$RAIZ" log --oneline 'HEAD..@{u}' 2>/dev/null | head -5 | sed 's/^/      /' || true
        [[ "$atras" -gt 5 ]] && printf '      … e mais %s\n' "$((atras - 5))"
    fi
    printf '  migrations  %s\n' \
        "$([[ $MIGRAR == 1 ]] && echo 'AUTORIZADAS (--migrar)' || echo 'bloqueadas (use --migrar)')"

    if [[ $CONFIRMAR == 1 ]]; then
        printf '\n  Continuar? [s/N] '
        read -r resposta || resposta=""
        [[ "$resposta" =~ ^[sSyY]$ ]] || { echo "  abortado."; exit 130; }
    fi
}


# ─── 3. Enviar o código ───────────────────────────────────────────────────
# Por que rsync da árvore e não `git pull` no servidor: o repositório costuma
# ter trabalho não commitado, e um clone do GitHub subiria uma versão diferente
# da que foi testada acima. Quando o repo estiver sempre em dia, trocar por
# git pull no bloco remoto é trivial.
#
# NUNCA envia .env: os segredos de produção são gerados no servidor e ficam só
# lá. Como está em --exclude, o --delete também não o toca.
#
# ⚠️ A LISTA DE EXCLUDES ERA ESCRITA À MÃO, E NÃO CONHECIA O .gitignore.
#
# O efeito não era desperdício: era vazamento. `.auditoria-mobile/` está no
# .gitignore desde sempre e continha capturas do painel de um ALUNO REAL — nome,
# nota, "37º de 179", percentil por matéria. Como não estava em nenhum
# --exclude, ia para o VPS a cada deploy. E como `git status --porcelain` não
# lista arquivo ignorado, a tela de confirmação (`resumo_e_confirmacao`) nunca
# mencionou isso: o operador confirmava sem ter como saber.
#
# `--filter=':- .gitignore'` faz o rsync herdar a régua que o repositório já
# mantém, e fecha a classe inteira do problema em vez de tapar um buraco por
# vez. De quebra, o envio caiu de 4.870 arquivos / 1,63 GB para 842 / 36,7 MB —
# eram 929 MB de PDF original e 570 MB de provas resolvidas, todos gitignorados
# e nenhum deles usado em produção.
#
# Os quatro --exclude que SOBRAM não são redundância: nenhum deles está no
# .gitignore, e cada um tem um motivo próprio:
#   .git/              versionado por definição; o servidor não precisa do histórico
#   /dados/            é o storage de produção, que mora NO servidor — mandar o
#                      local por cima apagaria upload de verdade
#   .env               segredo gerado no servidor; em --exclude também para o
#                      --delete não o remover
#   .DS_Store          lixo do Finder; aparece em qualquer pasta aberta no Mac
CAMINHOS_QUE_O_GITIGNORE_NAO_COBRE=(
    --exclude '.git/'
    --exclude '/dados/'
    --exclude '.env'
    --exclude '.DS_Store'
)

enviar_codigo() {
    log "Enviando código (rsync)"
    rsync -az --delete --stats \
        --filter=':- .gitignore' \
        "${CAMINHOS_QUE_O_GITIGNORE_NAO_COBRE[@]}" \
        "$RAIZ/" "$DESTINO:/opt/sas/" | tail -4
}


# ─── 4. Build, migrations e subida — no servidor ──────────────────────────
# O bloco abaixo roda como o usuário `sas` (que está no grupo docker), NÃO como
# root, e viaja por stdin. É idempotente: não toca no .env nem no banco além
# das migrations autorizadas.
subir_no_servidor() {
    log "Build e subida no servidor"
    ssh -o BatchMode=yes "$DESTINO" "bash -s -- $MIGRAR $DOMINIO" <<'REMOTO'
set -euo pipefail

MIGRAR="${1:-0}"
DOMINIO="${2:-portalsas.online}"
RAIZ="/opt/sas"
STORAGE="/opt/sas/dados/storage"
UID_APP=10001          # usuário `sas` de DENTRO da imagem (api/Dockerfile)

ok()   { printf '  \033[0;32m✓\033[0m %s\n' "$*"; }
aviso(){ printf '  \033[0;33m!\033[0m %s\n' "$*"; }
erro() { printf '  \033[0;31m✗\033[0m %s\n' "$*" >&2; }

command -v docker >/dev/null || { erro "docker ausente — rode 01-preparar-servidor.sh"; exit 1; }
[[ -d "$RAIZ/infra/vps" ]] || { erro "código ausente em $RAIZ"; exit 1; }
cd "$RAIZ/infra/vps"

# ── Storage ──────────────────────────────────────────────────────────────
# A imagem prod roda como uid 10001 e NÃO é root. Um volume nomeado nasceria
# root e o upload falharia com PermissionError; por isso é bind mount com dono
# explícito (docs/14 §5). Este bloco NÃO usa sudo de propósito: dar sudo sem
# senha ao usuário de operação é privilégio permanente em troca da conveniência
# de uma execução. Quem cria o diretório, uma vez, é o 00-prep-root.sh.
[[ -d "$STORAGE" ]] || { erro "$STORAGE não existe — rode como root: bash $RAIZ/infra/vps/00-prep-root.sh"; exit 1; }
dono="$(stat -c '%u' "$STORAGE")"
[[ "$dono" == "$UID_APP" ]] || { erro "$STORAGE pertence ao uid $dono, deveria ser $UID_APP"; exit 1; }
ok "storage ok (uid $UID_APP)"

# ── Segredos ─────────────────────────────────────────────────────────────
if [[ -f .env ]]; then
    ok ".env preservado (segredos não são regerados)"
else
    cp .env.example .env
    # Sorteados aqui, no servidor: nunca trafegam por chat, e-mail ou git.
    for chave in POSTGRES_PASSWORD POSTGREST_PASSWORD JWT_SECRET_KEY SCHEDULER_SECRET; do
        sed -i "s|^${chave}=.*|${chave}=$(openssl rand -hex 32)|" .env
    done
    # A senha do login do postgrest_mcp (docs/43 §10), sorteada já no .env
    # novo para que ligar o MCP depois seja só acrescentar as outras linhas.
    # Fora do `sed` de cima de propósito: lá o segredo passa pelo argv, e esta
    # senha não passa por linha de comando nenhuma (`printf` é builtin). Vai
    # para o fim do arquivo, com ou sem a linha no .env.example. Gravada no
    # banco ela só é quando o MCP for ligado — até lá o login segue sem senha.
    sed -i '/^POSTGREST_MCP_PASSWORD=/d' .env
    # Um .env.example sem quebra de linha no fim — e o sed acima a mantém
    # ausente — faria o printf colar a senha na última linha dele, e as duas
    # chaves virariam uma só.
    if [[ -n "$(tail -c 1 .env)" ]]; then printf '\n' >> .env; fi
    printf 'POSTGREST_MCP_PASSWORD=%s\n' "$(openssl rand -hex 32)" >> .env
    # Senha da coordenação: legível, para alguém conseguir digitar.
    senha="$(openssl rand -base64 18 | tr -d '/+=' | head -c 20)"
    sed -i "s|^COORDENADOR_SENHA=.*|COORDENADOR_SENHA=${senha}|" .env
    chmod 600 .env
    ok ".env gerado com segredos aleatórios (chmod 600)"
    printf '\n  \033[1;33mSENHA DA COORDENAÇÃO: %s\033[0m\n  Anote agora — não será mostrada de novo.\n\n' "$senha"
fi

# O guard de boot recusa subir sem estas duas.
for obrigatoria in JWT_SECRET_KEY COORDENADOR_SENHA; do
    grep -qE "^${obrigatoria}=.+" .env || { erro "$obrigatoria vazia no .env — a API não sobe"; exit 1; }
done
grep -qE '^CANVAS_API_TOKEN=.+' .env || aviso "CANVAS_API_TOKEN vazia — o sync do Canvas não roda"
grep -qE '^OPENAI_API_KEY=.+'   .env || aviso "OPENAI_API_KEY vazia — insights e chat desligados (degrada limpo)"

# Comentário na mesma linha de uma chave VAZIA vira o valor dela: o compose lê
# `CHAVE=   # texto` como "# texto" (Compose v5.2.0; docs/43 §10.3 e §10.7).
# Só aviso, e só com o nome da chave: não se sabe se o .env de produção já tem
# uma linha assim numa chave opcional, e barrar quebraria um deploy que hoje
# funciona. O caso que derruba a API é barrado logo abaixo.
while IFS= read -r chave_com_comentario; do
    aviso "${chave_com_comentario%%=*}: comentário na mesma linha de uma chave vazia — o compose lê o comentário como valor"
done < <(grep -E '^[A-Z_][A-Z0-9_]*=[[:space:]]+#' .env || true)

# EMAIL_DESTINATARIO_TESTE preenchida, o guard de boot da API recusa subir em
# produção (main.py: qualquer valor não vazio reprova — todo e-mail de aluno
# iria para uma caixa só). Barrada AQUI, antes do build e do `up -d`, o deploy
# falha com os containers antigos no ar, em vez de derrubar a API no meio. É o
# espelho do guard, lendo a linha como o compose lê (cada forma conferida no
# Compose v5.2.0, docs/43 §10.7): vale a ÚLTIMA ocorrência, `export` e espaço
# na frente contam, e vazio é nada, só espaço, ou "" e '' — com ou sem
# comentário depois. `CHAVE=   # texto` NÃO é vazio. Assim nada que hoje sobe
# passa a ser barrado, nem um `EMAIL_DESTINATARIO_TESTE=""`.
vazia_para_o_compose=$'^[[:space:]]*((""|\'\')([[:space:]]+#.*)?[[:space:]]*)?$'
linha_email="$(grep -E '^[[:space:]]*(export[[:space:]]+)?EMAIL_DESTINATARIO_TESTE=' .env | tail -n 1 || true)"
if [[ -n "$linha_email" && ! "${linha_email#*=}" =~ $vazia_para_o_compose ]]; then
    erro "EMAIL_DESTINATARIO_TESTE preenchida no .env — o guard da API recusa subir em produção (main.py)"
    erro "deixe 'EMAIL_DESTINATARIO_TESTE=' sem nada depois do '=', nem comentário (docs/43 §10.3)"
    erro "nenhum container foi trocado — a stack segue no ar com a versão anterior"
    exit 1
fi

# ── MCP da coordenação: ligado ou desligado (docs/43 §10) ────────────────
# Ligado = o profile `mcp` ativo, o que aqui quer dizer COMPOSE_PROFILES=mcp
# no .env. Quem responde é o próprio compose — `config --services` lista só
# os serviços dos profiles ativos —, e não um grep no .env, que erraria um
# `COMPOSE_PROFILES=tools,mcp` ou o valor entre aspas. Desligado, nada do MCP
# roda neste deploy: nem a senha do login, nem o restart do postgrest_mcp,
# nem a espera pelo /mcp.
servicos="$(docker compose config --services </dev/null)" \
    || { erro "docker compose config falhou — o docker-compose.yml ou o .env estão inválidos"; exit 1; }
if grep -qx 'postgrest_mcp' <<<"$servicos"; then
    MCP_LIGADO=1
    ok "MCP da coordenação LIGADO (profile mcp ativo)"
else
    MCP_LIGADO=0
    ok "MCP da coordenação desligado (sem COMPOSE_PROFILES=mcp no .env)"
fi

# ── Imagens ──────────────────────────────────────────────────────────────
# `--profile tools` existe para incluir o `migrate`, que fica FORA do build
# default por estar num profile. As migrations viajam DENTRO da imagem: o rsync
# atualiza o disco do host, não a imagem, e `build api` não reconstrói o
# `migrate` — são imagens separadas do mesmo contexto. Foi assim que a 0021
# ficou invisível para o runner (docs/15 §Etapa 7, aprendizado 1).
echo "  … build (api, web, migrate)"
docker compose --profile tools build --quiet
ok "imagens construídas"

# ── Migrations ───────────────────────────────────────────────────────────
# ANTES do `up -d`, não depois: código novo contra schema velho devolve 500 na
# primeira tela que dependa da coluna nova.
#
# Falha FECHADO. Migration pendente sem autorização explícita interrompe o
# deploy aqui — a stack continua no ar com a versão anterior, que é o estado
# seguro.
# `</dev/null` e `-T` NÃO são opcionais: este trecho roda via `ssh bash -s`,
# com o script inteiro chegando por stdin. `docker compose run` lê stdin por
# padrão — e lia o RESTO DESTE SCRIPT: tudo daqui para baixo (migrations,
# up -d, restart do postgrest) era engolido em silêncio, o bash remoto
# terminava "com sucesso" e o smoke test batia no container antigo, que
# continuava no ar. Aconteceu no deploy da Sprint 2 (22/08/2026).
saida_status="$(docker compose run --rm -T migrate status </dev/null 2>&1)" || {
    erro "não consegui ler o status das migrations:"; echo "$saida_status" | tail -20 >&2; exit 1; }
echo "$saida_status" | tail -3 | sed 's/^/  /'

if grep -q 'pendente(s)' <<<"$saida_status"; then
    if [[ "$MIGRAR" == "1" ]]; then
        docker compose run --rm -T migrate up </dev/null || { erro "migration falhou — nada foi trocado"; exit 1; }
        ok "migrations aplicadas"
    else
        erro "há migration pendente e o deploy não foi autorizado a aplicá-la"
        erro "revise o SQL e rode de novo:  ./infra/vps/deploy.sh --migrar"
        erro "a stack segue no ar com a versão anterior — nada foi trocado"
        exit 2
    fi
else
    ok "schema em dia"
fi

# ── Senha do login do postgrest_mcp (só com o MCP ligado) ────────────────
# A 0071 cria o autenticador_mcp com PASSWORD NULL, e um `down` + `up` dela o
# recria assim. Por isso a senha é gravada A CADA deploy, depois das
# migrations e antes do `up -d`, e o postgrest_mcp já sobe entrando. Gravar a
# mesma senha de novo não derruba conexão nenhuma (docs/43 §10).
#
# Por onde ela passa, e por onde não: sai do .env pelo grep (o argv dele só
# leva o nome da chave), é conferida pela regex do bash e chega ao psql pelo
# PIPE — `printf` é builtin, então não há processo com ela no argv, nem aqui
# nem no container. NÃO vai no `environment:` do `db`, como a primeira versão
# da §10 propunha: mexer ali muda o hash do serviço, e o `up -d` recriaria o
# container do banco de produção. `-T` e o stdin do pipe pela armadilha 6.
# Os SET valem só para a sessão: com log_statement ligado, ou num erro (o
# log_min_error_statement padrão escreve o comando que falhou), o Postgres
# poria o ALTER ROLE, com a senha em claro, no log do container.
if [[ "$MCP_LIGADO" == "1" ]]; then
    senha_mcp="$(grep -E '^POSTGREST_MCP_PASSWORD=' .env | tail -n 1 | cut -d= -f2- || true)"
    if [[ -z "$senha_mcp" ]]; then
        aviso "POSTGREST_MCP_PASSWORD ausente no .env — o postgrest_mcp não vai entrar (docs/43 §10, como ligar)"
    elif [[ ! "$senha_mcp" =~ ^[0-9a-f]{64}$ ]]; then
        # Conferido ANTES de usar: é o formato do `openssl rand -hex 32`, e
        # qualquer outra coisa (aspas, espaço, \r) seria uma senha no banco e
        # outra na URI do postgrest_mcp, que o compose lê do mesmo .env.
        erro "POSTGREST_MCP_PASSWORD fora do formato do 'openssl rand -hex 32' (64 hexadecimais minúsculos, sem aspas)"
        erro "nenhum container foi trocado — a stack segue no ar com a versão anterior"
        exit 1
    elif printf '%s\n' \
            "SET log_statement = 'none';" \
            "SET log_min_error_statement = 'panic';" \
            "SET log_min_duration_statement = -1;" \
            "\\set senha ${senha_mcp}" \
            "ALTER ROLE autenticador_mcp PASSWORD :'senha';" \
        | docker compose exec -T db psql -X -q -v ON_ERROR_STOP=1 -U postgres -d sas >/dev/null; then
        ok "senha do autenticador_mcp gravada (o login do postgrest_mcp)"
    else
        erro "não consegui gravar a senha do autenticador_mcp — a migration 0071 está aplicada?"
        erro "nenhum container foi trocado — a stack segue no ar com a versão anterior"
        exit 1
    fi
    unset senha_mcp
fi

# ── Subida ───────────────────────────────────────────────────────────────
# Com o MCP desligado, o `up -d` não cria o postgrest_mcp nem o mcp — e, se
# eles sobraram de quando estava ligado, também não os PARA: desligar é
# `docker compose stop mcp postgrest_mcp` (docs/43 §10). O smoke de fora
# reprova o container que sobrou.
docker compose up -d </dev/null
ok "containers no ar"

# O PostgREST lê o schema UMA vez, no boot, e o cacheia. Sem este restart as
# tabelas e colunas novas voltam 404 — e o 404 parece bug de código
# (docs/14 §6.6).
#
# ⚠️ INCONDICIONAL, e isso é decisão, não descuido. Até 04/09 o restart só
# acontecia quando ESTA execução aplicava migration (`MIGROU == 1`), e a
# pergunta certa é outra: "o schema mudou desde que o postgrest bootou?".
# Um deploy que morresse entre o `up -d` acima e este restart — ssh caindo,
# Ctrl-C, `up -d` demorando — deixava o operador reexecutando o script, e aí
# o `migrate status` dizia "schema em dia", `MIGROU` ficava 0 e o restart
# NUNCA acontecia. O cache seguia sem conhecer a coluna nova indefinidamente,
# com o deploy declarando sucesso.
#
# O preço de rodar sempre são ~2 s. O preço de pular é a armadilha 1 do
# CLAUDE.md num sistema que parece no ar (docs/35 §13).
#
# Com o MCP ligado, o postgrest_mcp vai junto: ele cacheia o schema do mesmo
# jeito, e a tabela e a função da 0072 só aparecem para ele depois do restart
# (docs/43 §9). Desligado, ele não existe, e o restart nem o cita.
if [[ "$MCP_LIGADO" == "1" ]]; then
    docker compose restart postgrest postgrest_mcp </dev/null
    ok "postgrest e postgrest_mcp reiniciados (cache de schema)"
else
    docker compose restart postgrest </dev/null
    ok "postgrest reiniciado (cache de schema)"
fi

# ── O nginx pergunta o nome do api de novo ───────────────────────────────
# O `location /api/` e os dois do RFC 8414 têm nome FIXO no proxy_pass: o
# nginx resolve `api` uma vez, no boot, e de novo só num reload. O `up -d` que
# recria o api sem recriar o web — todo deploy com código novo da API, e o de
# ligar o MCP, que muda o .env — pode devolvê-lo com outro IP: o IPAM do
# Docker dá o menor livre, e ao ligar o MCP o postgrest_mcp nasce no mesmo
# `up -d`, na mesma rede, e pode tomar o IP velho do api (a revisão de 27/10
# reproduziu em ~10% das rodadas; docs/43 §10.7). Aí o /api/ inteiro dá 502, o
# laço abaixo reprova com a API saudável, e rodar o deploy de novo não resolve:
# o `up -d` não mexe no web.
#
# O reload é gracioso — os workers velhos terminam o que atendem, SSE do chat
# inclusive — e INCONDICIONAL, como o restart do postgrest: custa nada, e "o
# api mudou de IP?" não tem resposta barata daqui. Não é o jeito de aplicar
# um nginx.conf novo: o rsync troca o arquivo por rename, e o bind mount de
# arquivo único do web segue lendo o antigo; para isso, `restart web`. E não
# trocar por `depends_on: api: {restart: true}` no web: segura o /api/, mas
# derruba o site inteiro durante o stop do api. Falhar aqui não interrompe —
# o laço decide, e o log do web sai junto se ele reprovar.
if saida_reload="$(docker compose exec -T web nginx -s reload </dev/null 2>&1)"; then
    ok "nginx recarregado (o nome do api resolvido de novo)"
else
    aviso "o reload do nginx falhou — o /api/ pode seguir no IP velho do api:"
    printf '%s\n' "$saida_reload" | tail -n 3 | sed 's/^/      /'
fi

# ── Esperar o uvicorn atender ────────────────────────────────────────────
# Por que --resolve em vez de http://127.0.0.1: desde a Etapa 5 a porta 80
# redireciona para HTTPS, e 3xx NÃO é erro para o `curl -f` — uma checagem em
# http receberia o 301 com corpo vazio e comemoraria sem ter falado com a API.
# O --resolve fala HTTPS com o próprio host, sem sair para a internet e sem
# depender de DNS, mas com Host e SNI corretos para o certificado bater (mesma
# técnica do cron-sas.sh).
for _ in $(seq 1 30); do
    resp="$(curl -fsS --max-time 3 --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/api/health" 2>/dev/null || true)"
    [[ "$resp" == *'"status":"ok"'* ]] && break
    sleep 2
done
[[ "$resp" == *'"status":"ok"'* ]] \
    && ok "API responde através do nginx" \
    || { erro "API não respondeu em /api/health"; docker compose logs --tail=40 api web; exit 1; }

# ── Esperar o MCP atender (só com ele ligado) ────────────────────────────
# POST sem token: o mcp de pé responde 401; enquanto ele sobe, o nginx
# devolve o 503 do `@mcp_fora_do_ar` (nginx.conf). Até 60 s, como a API: o
# processo pergunta ao postgrest_mcp com que papel fala antes de atender, e o
# resolver do nginx guarda por até 30 s o "não existe" de antes do `up -d`.
# Não interrompe o deploy: a API já subiu com o código novo, e o smoke de
# fora reprova o MCP que não respondeu.
if [[ "$MCP_LIGADO" == "1" ]]; then
    cod_mcp=000
    for _ in $(seq 1 30); do
        cod_mcp="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 \
            -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
            --data '{"jsonrpc":"2.0","id":1,"method":"ping"}' \
            --resolve "$DOMINIO:443:127.0.0.1" "https://$DOMINIO/mcp" 2>/dev/null || true)"
        [[ "$cod_mcp" == "401" ]] && break
        sleep 2
    done
    if [[ "$cod_mcp" == "401" ]]; then
        ok "MCP responde através do nginx (401 sem token)"
    else
        erro "o MCP não respondeu em /mcp (último código: $cod_mcp) — o smoke vai reprovar"
        docker compose logs --tail=40 mcp postgrest_mcp </dev/null || true
    fi
fi

# ── Backfill das séries por aluno (migration 0066) ───────────────────────
# A tabela nasce vazia, e sem ela a coordenação veria sparklines e "alunos
# parecidos" vazios até o próximo recálculo da classificação. `--se-vazia` faz o
# script trabalhar só na primeira vez; nos deploys seguintes ele responde
# "nada a fazer". `-T </dev/null` pelo motivo da armadilha 6 do CLAUDE.md:
# `compose exec` lê stdin, e o stdin deste bloco é o resto do script.
docker compose exec -T api python -m app.stats.serie_recente --se-vazia </dev/null \
    && ok "séries por aluno em dia" \
    || erro "backfill das séries falhou — rode: docker compose exec api python -m app.stats.serie_recente"

docker compose ps --format "  {{.Service}}\t{{.Status}}"
REMOTO
}


# ─── 5. Smoke test, pelo HTTPS público ────────────────────────────────────
# De fora, pelo domínio real: é o caminho que o coordenador e o aluno fazem.
# Cada caso aqui é uma falha que JÁ aconteceu neste projeto (docs/15 §9.7).
FALHAS=0
codigo()  { curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMINIO$1" 2>/dev/null || echo 000; }
esperar() {
    local caminho="$1" esperado="$2" rotulo="$3" obtido
    obtido="$(codigo "$caminho")"
    if [[ "$obtido" == "$esperado" ]]; then
        ok "$rotulo ($caminho → $obtido)"
    else
        erro "$rotulo ($caminho → $obtido, esperado $esperado)"
        FALHAS=$((FALHAS + 1))
    fi
}

# A resposta inteira — cabeçalhos (`-i`) e corpo —, com o status na última
# linha. $1 = caminho; o resto vai ao curl como opção.
pedir() {
    local caminho="$1"; shift
    curl -sS -i --max-time 20 -w '\n%{http_code}' "$@" "https://$DOMINIO$caminho" 2>/dev/null || printf '\n000'
}
status_de() { tail -n 1 <<<"$1"; }
# O index.html do Vite tem o <div id="root"> (web/index.html); nada que a API,
# o mcp ou o 503 do nginx devolvem tem.
e_o_spa()   { grep -q 'id="root"' <<<"$1"; }
e_json()    { grep -qiE '^content-type: *application/json' <<<"$1"; }

METADADOS_DO_OAUTH=(
    /.well-known/oauth-protected-resource/mcp     # RFC 9728, o mcp
    /.well-known/oauth-protected-resource
    /.well-known/oauth-authorization-server/api   # RFC 8414, a API
    /.well-known/oauth-authorization-server
)

# ── MCP da coordenação, nos dois modos (docs/43 §9, passo 8; §10) ────────
# Quem diz se ele está LIGADO é o servidor — o profile `mcp` ativo no compose
# —, não a resposta: com o profile ativo, um 503 é o mcp fora do ar, e não
# "desligado"; sem ele, um 401 é container que sobrou de pé depois de
# desligar (o `up -d` não para serviço de profile inativo). Sem ssh, decide
# pela resposta e diz que não conferiu.
#
# Em qualquer modo, o index.html do SPA no /mcp é FALHA: é o nginx.conf sem
# as locations do MCP, o de antes delas, que dava HTML com 200 à IA.
verificar_mcp() {
    local ligado servicos r cod caminho codigos=""
    if servicos="$(ssh -o BatchMode=yes "$DESTINO" \
            'cd /opt/sas/infra/vps && docker compose config --services' 2>/dev/null)"; then
        if grep -qx 'mcp' <<<"$servicos"; then ligado=1; else ligado=0; fi
    else
        ligado="?"
    fi

    r="$(pedir /mcp)"
    if e_o_spa "$r"; then
        erro "GET /mcp → $(status_de "$r") com o index.html do SPA — o nginx está sem as locations do MCP (docs/43 §10)"
        FALHAS=$((FALHAS + 1))
    fi

    r="$(pedir /mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
        --data '{"jsonrpc":"2.0","id":1,"method":"ping"}')"
    cod="$(status_de "$r")"
    if e_o_spa "$r"; then
        erro "POST /mcp → $cod com o index.html do SPA — o nginx está sem as locations do MCP (docs/43 §10)"
        FALHAS=$((FALHAS + 1))
    elif [[ "$cod" == "401" ]] && grep -qiE '^www-authenticate:.*resource_metadata' <<<"$r"; then
        if [[ "$ligado" == "0" ]]; then
            erro "profile mcp inativo, mas POST /mcp → 401: sobrou o mcp de pé — 'docker compose stop mcp postgrest_mcp'"
            FALHAS=$((FALHAS + 1))
        else
            ok "MCP ligado: POST /mcp sem token → 401 com resource_metadata"
        fi
        # Ligado, cada metadado é JSON de quem o publica — e não o SPA.
        for caminho in "${METADADOS_DO_OAUTH[@]}"; do
            r="$(pedir "$caminho")"
            if [[ "$(status_de "$r")" == "200" ]] && e_json "$r"; then
                ok "metadado do OAuth em JSON ($caminho)"
            else
                erro "metadado do OAuth ($caminho → $(status_de "$r"), esperado 200 com JSON)"
                FALHAS=$((FALHAS + 1))
            fi
        done
    elif [[ "$cod" == "401" ]]; then
        erro "POST /mcp → 401 SEM resource_metadata no WWW-Authenticate — o mcp está sem MCP_EMISSOR_OAUTH, e o conector não acha o OAuth"
        FALHAS=$((FALHAS + 1))
    elif [[ "$cod" == "503" ]]; then
        case "$ligado" in
            1) erro "profile mcp ATIVO, mas POST /mcp → 503: o mcp não está atendendo — 'docker compose logs mcp postgrest_mcp'"
               FALHAS=$((FALHAS + 1)) ;;
            0) ok "MCP desligado (profile mcp inativo): POST /mcp → 503 do nginx" ;;
            *) aviso "POST /mcp → 503: MCP desligado ou fora do ar — sem ssh, não perguntei ao servidor qual dos dois" ;;
        esac
        # Desligado, os metadados não existem — mas também não podem ser o SPA.
        for caminho in "${METADADOS_DO_OAUTH[@]}"; do
            r="$(pedir "$caminho")"
            if e_o_spa "$r"; then
                erro "metadado do OAuth ($caminho → $(status_de "$r") com o index.html do SPA)"
                FALHAS=$((FALHAS + 1))
            else
                codigos+=" $(status_de "$r")"
            fi
        done
        # `if`, e não `[[ … ]] && ok`: como último comando da função, a lista
        # falsa faria verificar_mcp devolver 1, e o `set -e` sairia daqui sem
        # o resumo.
        if [[ -n "$codigos" ]]; then
            ok "metadados do OAuth fora do SPA (→$codigos)"
        fi
    else
        erro "POST /mcp → $cod, esperado 401 (ligado) ou 503 (desligado)"
        FALHAS=$((FALHAS + 1))
    fi
}

verificar() {
    log "Verificação em https://$DOMINIO"

    esperar "/api/health"            200 "API viva"
    esperar "/"                      200 "front servido"
    # Rota profunda tem que cair no index (React Router), não dar 404.
    esperar "/alunos/A023"           200 "rota profunda no SPA"
    # E asset inexistente tem que dar 404 HONESTO. Se devolver 200, o fallback
    # de SPA está engolindo /assets/ e todo erro de módulo vira
    # "Unexpected token '<'" no browser (docs/15 §9.2).
    esperar "/assets/nao-existe.js"  404 "asset inexistente dá 404"
    esperar "/api/docs"              404 "superfície da API fechada"

    # Readiness pode legitimamente estar 503 (sync do Canvas atrasado) sem que
    # o deploy tenha falhado — por isso é aviso, não falha.
    local pronto
    pronto="$(codigo /api/health/ready)"
    if [[ "$pronto" == "200" ]]; then
        ok "readiness ok (banco + sync recentes)"
    else
        aviso "readiness devolveu $pronto — $(curl -sS --max-time 10 "https://$DOMINIO/api/health/ready" | head -c 200)"
    fi

    # O index recém-publicado precisa apontar para assets que existem: é o modo
    # de falha clássico de deploy com hash no nome (HTML novo, bundle velho —
    # ou o contrário).
    local asset
    asset="$(curl -sS --max-time 20 "https://$DOMINIO/" 2>/dev/null | grep -o '/assets/[A-Za-z0-9._-]*\.js' | head -1 || true)"
    if [[ -n "$asset" ]]; then
        esperar "$asset" 200 "bundle referenciado pelo index existe"
    else
        aviso "não achei referência a /assets/*.js no index — build do front?"
    fi

    # Headers de segurança: um add_header dentro de location apaga todos os
    # herdados do server, em silêncio e passando no `nginx -t` (docs/15 §9.3).
    local cabecalhos ausentes=""
    cabecalhos="$(curl -sSI --max-time 20 "https://$DOMINIO/" 2>/dev/null | tr 'A-Z' 'a-z')"
    for h in content-security-policy x-content-type-options referrer-policy x-frame-options strict-transport-security; do
        grep -q "^$h:" <<<"$cabecalhos" || ausentes+=" $h"
    done
    [[ -z "$ausentes" ]] && ok "headers de segurança presentes" \
                         || { erro "headers ausentes:$ausentes"; FALHAS=$((FALHAS + 1)); }

    # HTTP tem que redirecionar, não servir.
    local http
    http="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 20 "http://$DOMINIO/" 2>/dev/null || echo 000)"
    [[ "$http" == "301" ]] && ok "http → https (301)" \
                           || { erro "http devolveu $http, esperado 301"; FALHAS=$((FALHAS + 1)); }

    verificar_mcp

    # A regra que sustenta a segurança da stack: só o `web` publica porta. Se o
    # db ou o postgrest aparecerem aqui, estão na internet — o Docker escreve
    # no iptables por cima do ufw (docs/14 §5).
    local publicadas
    publicadas="$(ssh -o BatchMode=yes "$DESTINO" \
        'cd /opt/sas/infra/vps && docker compose ps --format "{{.Service}} {{.Ports}}"' 2>/dev/null \
        | grep -E '0\.0\.0\.0|:::' | awk '{print $1}' | sort -u | tr '\n' ' ' | xargs || true)"
    if [[ "$publicadas" == "web" ]]; then
        ok "só o web publica porta"
    else
        erro "portas publicadas por: ${publicadas:-nenhum} — esperado só 'web'"
        FALHAS=$((FALHAS + 1))
    fi

    echo
    if [[ $FALHAS -eq 0 ]]; then
        printf '  \033[0;32m● produção respondendo em https://%s\033[0m\n\n' "$DOMINIO"
    else
        printf '  \033[0;31m● %s verificação(ões) falharam\033[0m\n' "$FALHAS"
        printf '    logs:  ssh %s '"'"'cd /opt/sas/infra/vps && docker compose logs --tail=60 api web'"'"'\n\n' "$DESTINO"
        return 3
    fi
}


# ─── Fluxo ────────────────────────────────────────────────────────────────
if [[ $SO_VERIFICAR == 1 ]]; then
    verificar
    exit $?
fi

ssh -o BatchMode=yes -o ConnectTimeout=10 "$DESTINO" true 2>/dev/null \
    || { erro "sem acesso ssh a $DESTINO (chave? VPN? host certo?)"; exit 1; }

[[ $RAPIDO == 1 ]] && aviso "portões locais pulados (--rapido)" || portoes_locais
resumo_e_confirmacao
enviar_codigo
subir_no_servidor \
    || { saida=$?; erro "o deploy no servidor falhou (exit $saida)"; exit $saida; }
verificar
