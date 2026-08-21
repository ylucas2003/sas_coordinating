#!/usr/bin/env bash
# Roda o linter no arquivo que o Claude Code acabou de editar e devolve o
# resultado PARA ELE (não para o terminal do usuário).
#
# É o que fecha o ciclo: sem isto, um `useEffect` com dependência faltando ou
# um import quebrado só aparecem quando alguém roda `npm run lint` — que é
# depois do commit, quando o contexto já se perdeu. Com isto, aparece no
# mesmo turno em que o erro foi escrito.
#
# Ligado em .claude/settings.json como PostToolUse de Edit|Write|MultiEdit.
# Convenção de saída dos hooks: exit 2 manda o stderr de volta para o Claude.

set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# O payload do hook chega como JSON no stdin.
ENTRADA="$(cat)"
ARQUIVO="$(printf '%s' "$ENTRADA" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
print(d.get("tool_input", {}).get("file_path", ""))
' 2>/dev/null)"

[ -z "$ARQUIVO" ] && exit 0
[ -f "$ARQUIVO" ] || exit 0

case "$ARQUIVO" in
  */.venv/*|*/node_modules/*|*/dist/*|*/migrations/*) exit 0 ;;
esac

# Caminho RELATIVO à raiz do subprojeto, nunca absoluto: o macOS tem
# filesystem case-insensitive, e um `cd /Users/.../documents/sas` (minúsculo)
# faz o Biome comparar o caminho absoluto contra o `includes` do biome.json e
# concluir que o arquivo está fora do projeto — "no files were processed".
# Relativo ao diretório de onde a ferramenta roda, o problema não existe.
relativo_a() {  # $1 = subdiretório (api|web) → ecoa o caminho relativo ou vazio
  local base="$1" caminho="$ARQUIVO"
  case "$caminho" in
    */"$base"/*) printf '%s' "${caminho##*/"$base"/}" ;;
    *) printf '' ;;
  esac
}

saida=""

case "$ARQUIVO" in
  *.py)
    # Só o que está sob api/ — grading_prototype e infra têm regras próprias.
    case "$ARQUIVO" in
      */api/*) ;;
      *) exit 0 ;;
    esac
    RUFF="$RAIZ/api/.venv/bin/ruff"
    [ -x "$RUFF" ] || exit 0
    alvo="$(relativo_a api)"
    [ -z "$alvo" ] && exit 0
    saida="$(cd "$RAIZ/api" && "$RUFF" check "$alvo" --output-format concise 2>&1)"
    [ "${saida#All checks passed}" != "$saida" ] && saida=""
    ;;

  *.ts|*.tsx|*.js)
    case "$ARQUIVO" in
      */web/src/*) ;;
      *) exit 0 ;;
    esac
    BIOME="$RAIZ/web/node_modules/.bin/biome"
    [ -x "$BIOME" ] || exit 0
    alvo="$(relativo_a web)"
    [ -z "$alvo" ] && exit 0
    # `--reporter=github` dá uma linha por diagnóstico, com arquivo e linha —
    # curto o bastante para caber na devolutiva, específico o bastante para
    # eu ir direto no ponto. O detalhe completo sai com `npm run lint`.
    if ! saida="$(cd "$RAIZ/web" && "$BIOME" lint "$alvo" --reporter=github --max-diagnostics=20 2>&1)"; then
      :
    else
      saida=""
    fi
    # "No files were processed" NÃO é problema de código: é arquivo fora do
    # `includes` do biome.json. Sai calado em vez de acusar erro falso.
    case "$saida" in
      *"No files were processed"*) saida="" ;;
    esac
    ;;

  *) exit 0 ;;
esac

[ -z "${saida//[[:space:]]/}" ] && exit 0

printf 'Lint de %s:\n\n%s\n\nConserte o que for erro real antes de seguir. Se for falso positivo, diga por quê em vez de silenciar a regra.\n' \
  "${ARQUIVO#"$RAIZ"/}" "$saida" >&2
exit 2
