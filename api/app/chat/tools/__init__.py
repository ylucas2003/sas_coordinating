"""Registry de tools curadas que o agente pode chamar.

Cada tool é uma função Python pura (recebe um Supabase Client + kwargs,
devolve dict/list) acompanhada de um schema JSON (formato OpenAI function
tools) descrevendo nome, descrição e parâmetros.

Convenções:
  - Toda tool é READ-ONLY. O agente não escreve no banco.
  - Tools devolvem dicionários simples (JSON-serializáveis). Strings, ints,
    floats, listas, dicts. Sem objetos do Supabase nem datetime.
  - Erros viram `{"erro": "mensagem legível"}` — o LLM aprende a falar disso.
  - Sempre retornam ALGO (mesmo que vazio); nunca None.

Registry exporta:
  - SCHEMAS  : lista de schemas no formato OpenAI ([{type:"function", function:{...}}])
  - HANDLERS : dict {nome_tool: callable(cliente, **args) -> dict}
"""

from __future__ import annotations

from typing import Any, Callable

from . import artefato, comparar, heuristicas, lookup, stats

# ─── Registry ─────────────────────────────────────────────────────────────

_MODULOS = (lookup, stats, comparar, heuristicas, artefato)

SCHEMAS: list[dict[str, Any]] = []
HANDLERS: dict[str, Callable] = {}

for mod in _MODULOS:
    for schema, handler in mod.TOOLS:
        SCHEMAS.append({"type": "function", "function": schema})
        HANDLERS[schema["name"]] = handler


def executar(nome: str, cliente, args: dict) -> dict:
    """Despacha uma chamada de tool. Devolve sempre um dict serializável."""
    fn = HANDLERS.get(nome)
    if fn is None:
        return {"erro": f"tool '{nome}' não existe"}
    try:
        return fn(cliente, **(args or {}))
    except TypeError as e:
        # Argumentos inválidos (LLM passou kwargs errados).
        return {"erro": f"argumentos inválidos para '{nome}': {e}"}
    except Exception as e:  # noqa: BLE001
        return {"erro": f"erro ao executar '{nome}': {type(e).__name__}: {e}"}
