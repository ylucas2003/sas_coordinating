"""Loop de tool-calling com OpenAI + streaming SSE.

Fluxo:
  1. Recebe histórico da thread (mensagens persistidas).
  2. Acrescenta nova mensagem do user e chama OpenAI com tools.
  3. Se a resposta tiver tool_calls, executa cada tool, anexa o resultado
     ao histórico, e chama OpenAI de novo.
  4. Quando a resposta vier sem tool_calls, é a resposta final pro usuário.

Streaming: usa o protocolo SSE custom abaixo (não o nativo do OpenAI
content delta, mas um nível acima — eventos semânticos que o front entende):

    event: start                     {"thread_id": "...", "mensagem_id": "..."}
    event: tool_call_start           {"tool_call_id": "...", "nome": "...", "args": {...}}
    event: tool_call_end             {"tool_call_id": "...", "resultado_resumido": "..."}
    event: token                     {"texto": "..."}
    event: end                       {"mensagem_id": "...", "tokens_in": N, "tokens_out": N}
    event: erro                      {"mensagem": "..."}

Cada `event` é uma linha `event: <name>` + uma `data: <json>`.

Limites:
  - MAX_TURNOS: até 8 iterações de tool calls antes de forçar uma resposta final.
  - MAX_MENSAGENS_HISTORICO: mantém só últimas N mensagens no contexto (FIFO).
  - Sem PII anonimization no MVP — nomes vão pra OpenAI. Decisão registrada.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from supabase import Client

from ..config import get_settings
from .prompt import PROMPT_TITULO, system_message
from .tools import HANDLERS, SCHEMAS, executar

try:
    from openai import OpenAI
    _SDK_DISPONIVEL = True
except ImportError:
    _SDK_DISPONIVEL = False

log = logging.getLogger("sas.chat.agente")

MAX_TURNOS = 8
MAX_MENSAGENS_HISTORICO = 30
TEMPERATURA = 0.2          # Determinístico — coordenador quer respostas reprodutíveis.
MODELO_PADRAO = "gpt-4o"   # Sweet spot custo/raciocínio. Override em settings.


# ─── Eventos SSE ─────────────────────────────────────────────────────────


@dataclass
class Evento:
    nome: str
    dados: dict[str, Any] = field(default_factory=dict)

    def formatar_sse(self) -> str:
        return f"event: {self.nome}\ndata: {json.dumps(self.dados, ensure_ascii=False)}\n\n"


# ─── Loop principal ───────────────────────────────────────────────────────


def gerar_resposta(
    cliente_db: Client,
    *,
    thread_id: str,
    historico: list[dict],
    nova_msg_user: str,
    modelo: str | None = None,
) -> AsyncIterator[Evento]:
    """Streaming SSE da resposta do agente.

    `historico` no formato OpenAI: lista de dicts {role, content, tool_calls?, tool_call_id?, name?}.
    `nova_msg_user` é o texto que o usuário acabou de mandar — adicionado ao histórico aqui.
    """
    return _gerar(cliente_db, thread_id, historico, nova_msg_user, modelo)


async def _gerar(
    cliente_db: Client,
    thread_id: str,
    historico: list[dict],
    nova_msg_user: str,
    modelo_override: str | None,
) -> AsyncIterator[Evento]:
    settings = get_settings()
    if not _SDK_DISPONIVEL or not settings.openai_api_key:
        yield Evento("erro", {"mensagem": "OpenAI não configurada (OPENAI_API_KEY ausente)."})
        return

    modelo = modelo_override or _modelo_padrao()
    client = OpenAI(api_key=settings.openai_api_key)

    # ── Histórico final que vai pra OpenAI ──
    mensagens: list[dict] = [system_message()]
    # Janela: mantém só as últimas N (mais o system fixo na frente).
    mensagens.extend(historico[-MAX_MENSAGENS_HISTORICO:])
    mensagens.append({"role": "user", "content": nova_msg_user})

    yield Evento("start", {"thread_id": thread_id})

    tokens_in_total = 0
    tokens_out_total = 0
    tool_calls_executadas: list[dict] = []
    texto_final = ""
    erro_fatal: str | None = None

    for turno in range(MAX_TURNOS):
        log.info("chat thread=%s turno=%d msgs=%d", thread_id, turno, len(mensagens))
        try:
            response = client.chat.completions.create(
                model=modelo,
                temperature=TEMPERATURA,
                messages=mensagens,
                tools=SCHEMAS,
                tool_choice="auto",
                stream=False,  # Streaming + tools no MVP é mais simples sem token-streaming.
            )
        except Exception as e:  # noqa: BLE001
            log.exception("erro na chamada OpenAI")
            erro_fatal = f"falha chamando o modelo: {e}"
            break

        usage = response.usage
        if usage:
            tokens_in_total += usage.prompt_tokens or 0
            tokens_out_total += usage.completion_tokens or 0

        choice = response.choices[0]
        msg = choice.message

        # ── Se vieram tool_calls, executa e continua ──
        if msg.tool_calls:
            # Anexa o turno do assistant ao histórico (mesmo sem content de texto).
            mensagens.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                nome = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                yield Evento("tool_call_start", {
                    "tool_call_id": tc.id,
                    "nome": nome,
                    "args": args,
                })

                resultado = executar(nome, cliente_db, args)
                tool_calls_executadas.append({
                    "id": tc.id, "nome": nome, "args": args, "resultado": resultado,
                })
                # OpenAI exige role='tool' com tool_call_id e content (string).
                mensagens.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": nome,
                    "content": json.dumps(resultado, ensure_ascii=False)[:60_000],
                })
                yield Evento("tool_call_end", {
                    "tool_call_id": tc.id,
                    "resumido": _resumir_resultado(resultado),
                })
            continue  # próximo turno

        # ── Sem tool_calls → resposta final ──
        texto_final = msg.content or ""
        # Streaming "fake" — manda o texto inteiro em chunks pra UI render incremental.
        for chunk in _quebra_chunks(texto_final, tamanho=40):
            yield Evento("token", {"texto": chunk})
        break
    else:
        # Esgotou MAX_TURNOS sem resposta final.
        erro_fatal = f"loop excedeu {MAX_TURNOS} turnos sem resposta final."

    if erro_fatal:
        yield Evento("erro", {"mensagem": erro_fatal})

    yield Evento("end", {
        "tokens_in": tokens_in_total,
        "tokens_out": tokens_out_total,
        "modelo": modelo,
        "texto_final": texto_final,
        "tool_calls": tool_calls_executadas,
    })


# ─── Gerador de título da thread ─────────────────────────────────────────


def gerar_titulo(primeira_pergunta: str, primeira_resposta: str) -> str | None:
    """Gera título curto pra thread a partir do primeiro turno. Sem tools."""
    settings = get_settings()
    if not _SDK_DISPONIVEL or not settings.openai_api_key:
        return None
    try:
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=20,
            messages=[
                {"role": "system", "content": PROMPT_TITULO},
                {"role": "user", "content": (
                    f"Pergunta: {primeira_pergunta[:300]}\n\n"
                    f"Resposta: {primeira_resposta[:500]}"
                )},
            ],
        )
        titulo = (resp.choices[0].message.content or "").strip().strip('"').strip("'")
        # Limpa pontuação final.
        if titulo.endswith("."):
            titulo = titulo[:-1]
        return titulo[:80] if titulo else None
    except Exception:
        log.exception("erro gerando título")
        return None


# ─── Helpers ─────────────────────────────────────────────────────────────


def _modelo_padrao() -> str:
    settings = get_settings()
    # Reusa o setting do insights se ele apontar pra um modelo "potente";
    # senão, default seguro.
    modelo = (settings.openai_modelo_insights or "").lower()
    if modelo and "mini" not in modelo:
        return settings.openai_modelo_insights
    return MODELO_PADRAO


def _quebra_chunks(texto: str, *, tamanho: int) -> list[str]:
    """Quebra string em pedaços do tamanho indicado — UI render incremental."""
    if not texto:
        return []
    return [texto[i : i + tamanho] for i in range(0, len(texto), tamanho)]


def _resumir_resultado(resultado: dict) -> str:
    """Resumo curto do retorno da tool — fica visível na trace do front."""
    if not isinstance(resultado, dict):
        return str(resultado)[:200]
    if "erro" in resultado:
        return f"erro: {resultado['erro'][:200]}"
    # Pega contagem se houver
    if "total" in resultado:
        return f"{resultado.get('total')} item(s)"
    if "nLinhas" in resultado:
        return f"{resultado.get('nLinhas')} linha(s)"
    if "alunos" in resultado:
        return f"{len(resultado.get('alunos') or [])} aluno(s)"
    if "simulados" in resultado:
        return f"{len(resultado.get('simulados') or [])} simulado(s)"
    if "ciclos" in resultado:
        return f"{len(resultado.get('ciclos') or [])} ciclo(s)"
    if "materias" in resultado:
        return f"{len(resultado.get('materias') or [])} matéria(s)"
    if "trajetoria" in resultado:
        return f"{len(resultado.get('trajetoria') or [])} nota(s)"
    if "similares" in resultado:
        return f"{len(resultado.get('similares') or [])} similar(es)"
    return "ok"
