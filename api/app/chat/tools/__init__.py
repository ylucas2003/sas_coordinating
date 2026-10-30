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

Quem DESPACHA não é este módulo: é `chat/ferramentas.py` (docs/43 §3), o
registro único que recolhe estas tools e as do aluno e aplica as guardas
(escopo, argumentos, prazo, erro) num lugar só.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import (
    artefato,
    banco_questoes,
    captacao,
    comparar,
    contexto,
    heuristicas,
    lookup,
    reguas,
    relatorios,
    rotinas,
    stats,
    trilha,
)

# ─── Registry ─────────────────────────────────────────────────────────────

# Os quatro do fim são a cobertura do docs/43 §4.3: banco de questões, régua
# como objeto, rotinas automáticas (sync, gravações, lembretes) e auditoria. A
# captação externa entrou em 30/10 (a IA lê o que o coordenador lê).
_MODULOS = (
    lookup, stats, comparar, heuristicas, relatorios, artefato, contexto,
    banco_questoes, reguas, rotinas, trilha, captacao,
)

SCHEMAS: list[dict[str, Any]] = []
HANDLERS: dict[str, Callable] = {}

for mod in _MODULOS:
    for schema, handler in mod.TOOLS:
        SCHEMAS.append({"type": "function", "function": schema})
        HANDLERS[schema["name"]] = handler
