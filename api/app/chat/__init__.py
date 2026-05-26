"""Chat com agente LLM — coordenador ↔ OpenAI com tools curadas.

Submódulos:
  rotas.py    — endpoints /chat (threads, mensagens, SSE)
  agente.py   — loop de tool-calling com a OpenAI
  prompt.py   — system prompt do assistente
  tools/      — registry de tools curadas (read-only) que o agente pode chamar
"""
