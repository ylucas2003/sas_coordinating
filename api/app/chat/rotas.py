"""Rotas HTTP do chat.

Endpoints:
  GET  /chat/threads                            — lista threads do usuario
  POST /chat/threads                            — cria thread (sem msgs)
  GET  /chat/threads/{thread_id}                — detalhe + mensagens
  PATCH /chat/threads/{thread_id}               — renomeia / arquiva
  DELETE /chat/threads/{thread_id}              — apaga (cascade nas msgs)
  POST /chat/threads/{thread_id}/mensagens      — envia msg, devolve SSE

Autenticação: JWT (Bearer) — aceita aluno E coordenador. As threads vivem em
namespaces separados por tipo (`coord:<sub>` / `aluno:<aluno_id>`), então um
aluno nunca enxerga threads da coordenação nem de outro aluno.

Tools do coordenador podem ler dados de qualquer aluno (decisão do produto);
o aluno recebe um perfil de tools restrito aos próprios dados.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..auth import get_current_user
from ..config import get_settings
from ..supabase_client import get_supabase
from . import agente, navegacao, perfis

log = logging.getLogger("sas.chat.rotas")

router = APIRouter(prefix="/chat", tags=["chat"])


def _verificar_teto_de_uso(cliente, usuario: str) -> None:
    """Recusa a mensagem se o usuário passou do teto de uso do chat.

    Os campos `tokens_in`/`tokens_out` já eram gravados em `chat_mensagem`
    desde a 0008, mas nenhuma query os lia para decidir coisa alguma — eram
    auditoria post-mortem, não freio (docs/14 §6.4). Aqui eles viram o freio.

    Uma única leitura cobre os dois tetos: puxa as mensagens do usuário nas
    últimas 24h e conta em memória. O `!inner` é embed do PostgREST pela FK
    `chat_mensagem.thread_id → chat_thread.id`, porque quem carrega o dono é a
    thread, não a mensagem.

    Falha ABERTO de propósito: se a consulta der erro, a mensagem passa. Um
    teto que derruba o chat inteiro quando o banco tosse é pior que um teto
    que ocasionalmente não conta.
    """
    settings = get_settings()
    agora = datetime.now(timezone.utc)
    try:
        resp = (
            cliente.table("chat_mensagem")
            .select("tokens_in,tokens_out,criada_em,chat_thread!inner(usuario_id)")
            .eq("chat_thread.usuario_id", usuario)
            .gte("criada_em", (agora - timedelta(hours=24)).isoformat())
            .execute()
        )
        linhas = resp.data or []
    except Exception:  # noqa: BLE001
        log.exception("teto de uso do chat: consulta falhou, liberando a mensagem")
        return

    corte_hora = agora - timedelta(hours=1)
    mensagens_hora = 0
    tokens_dia = 0
    for linha in linhas:
        tokens_dia += (linha.get("tokens_in") or 0) + (linha.get("tokens_out") or 0)
        criada = linha.get("criada_em")
        if not criada:
            continue
        try:
            quando = datetime.fromisoformat(criada.replace("Z", "+00:00"))
        except ValueError:
            continue
        if quando >= corte_hora:
            mensagens_hora += 1

    if mensagens_hora >= settings.chat_limite_mensagens_hora:
        raise HTTPException(
            status_code=429,
            detail="Você atingiu o limite de mensagens desta hora. Tente de novo mais tarde.",
        )
    if tokens_dia >= settings.chat_limite_tokens_dia:
        raise HTTPException(
            status_code=429,
            detail="Você atingiu o limite de uso do chat por hoje. Ele volta amanhã.",
        )


def _usuario_do_token(user: dict) -> str:
    """Namespace do dono da thread em chat_thread.usuario_id.

    Fail-closed de propósito, em cima do `get_current_user` que já recusa token
    fora de `TIPOS_DE_SESSAO` (app/auth.py). São duas camadas porque esta função
    decide DE QUEM é a thread: um `else` genérico aqui devolvia namespace de
    coordenação para qualquer token que não fosse de aluno, e o default
    `'coordenador'` no `sub` ainda colapsava todos eles num balde só.
    """
    tipo = user.get("tipo")

    if tipo == "aluno":
        return f"aluno:{user['aluno_id']}"

    if tipo == "coordenador":
        sub = user.get("sub")
        if not sub:
            raise HTTPException(status_code=403, detail="Token sem identidade de coordenação")
        return f"coord:{sub}"

    raise HTTPException(status_code=403, detail="Token não autoriza uso do chat")


# ─── Schemas ─────────────────────────────────────────────────────────────


class ThreadResumo(BaseModel):
    id: str
    titulo: str
    arquivada: bool
    criadaEm: str = Field(..., alias="criadaEm")
    ultimaMsgEm: str = Field(..., alias="ultimaMsgEm")

    class Config:
        populate_by_name = True


class MensagemPersistida(BaseModel):
    id: str
    ordem: int
    papel: str
    conteudo: str | None = None
    toolCalls: list[dict] | None = None
    toolCallId: str | None = None
    nomeTool: str | None = None
    artefatos: list[dict] = Field(default_factory=list)
    criadaEm: str


class ThreadDetalhe(BaseModel):
    id: str
    titulo: str
    arquivada: bool
    criadaEm: str
    ultimaMsgEm: str
    mensagens: list[MensagemPersistida] = Field(default_factory=list)


class NovaThread(BaseModel):
    titulo: str | None = None


class PatchThread(BaseModel):
    titulo: str | None = None
    arquivada: bool | None = None


class NovaMensagem(BaseModel):
    conteudo: str
    #: Em que tela o usuário estava ao mandar isto (docs/31 §P2). Opcional:
    #: cliente antigo, ou tela sem nada a declarar, seguem funcionando.
    contexto: navegacao.ContextoDaTela | None = None


# ─── GET /chat/threads ────────────────────────────────────────────────────


@router.get("/threads", response_model=list[ThreadResumo])
async def listar_threads(
    incluir_arquivadas: bool = False,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    cliente = get_supabase()
    usuario = _usuario_do_token(user)
    q = (
        cliente.table("chat_thread")
        .select("id, titulo, arquivada, criada_em, ultima_msg_em")
        .eq("usuario_id", usuario)
        .order("ultima_msg_em", desc=True)
        .limit(80)
    )
    if not incluir_arquivadas:
        q = q.eq("arquivada", False)
    resp = q.execute()
    return [
        {
            "id": r["id"],
            "titulo": r["titulo"],
            "arquivada": r["arquivada"],
            "criadaEm": r["criada_em"],
            "ultimaMsgEm": r["ultima_msg_em"],
        }
        for r in (resp.data or [])
    ]


# ─── POST /chat/threads ───────────────────────────────────────────────────


@router.post("/threads", response_model=ThreadResumo)
async def criar_thread(
    body: NovaThread,
    user: dict = Depends(get_current_user),
) -> dict:
    cliente = get_supabase()
    usuario = _usuario_do_token(user)
    titulo = (body.titulo or "Nova conversa").strip()[:80] or "Nova conversa"
    resp = (
        cliente.table("chat_thread")
        .insert({"usuario_id": usuario, "titulo": titulo})
        .execute()
    )
    r = resp.data[0]
    return {
        "id": r["id"],
        "titulo": r["titulo"],
        "arquivada": r["arquivada"],
        "criadaEm": r["criada_em"],
        "ultimaMsgEm": r["ultima_msg_em"],
    }


# ─── GET /chat/threads/{id} ───────────────────────────────────────────────


@router.get("/threads/{thread_id}", response_model=ThreadDetalhe)
async def obter_thread(
    thread_id: str = Path(...),
    user: dict = Depends(get_current_user),
) -> dict:
    cliente = get_supabase()
    usuario = _usuario_do_token(user)
    t = _carregar_thread_ou_404(cliente, thread_id, usuario)

    msgs_resp = (
        cliente.table("chat_mensagem")
        .select("id, ordem, papel, conteudo, tool_calls, tool_call_id, nome_tool, criada_em")
        .eq("thread_id", thread_id)
        .order("ordem")
        .execute()
    )
    mensagens = msgs_resp.data or []

    # Artefatos atrelados às mensagens
    msg_ids = [m["id"] for m in mensagens]
    artefatos_por_msg: dict[str, list[dict]] = {}
    if msg_ids:
        art_resp = (
            cliente.table("chat_artefato")
            .select("id, mensagem_id, tipo, titulo, payload, url_export, criado_em")
            .in_("mensagem_id", msg_ids)
            .execute()
        )
        for a in (art_resp.data or []):
            artefatos_por_msg.setdefault(a["mensagem_id"], []).append({
                "id": a["id"],
                "tipo": a["tipo"],
                "titulo": a.get("titulo"),
                "payload": a.get("payload"),
                "urlExport": a.get("url_export"),
            })

    return {
        "id": t["id"],
        "titulo": t["titulo"],
        "arquivada": t["arquivada"],
        "criadaEm": t["criada_em"],
        "ultimaMsgEm": t["ultima_msg_em"],
        "mensagens": [
            {
                "id": m["id"],
                "ordem": m["ordem"],
                "papel": m["papel"],
                "conteudo": m.get("conteudo"),
                "toolCalls": m.get("tool_calls"),
                "toolCallId": m.get("tool_call_id"),
                "nomeTool": m.get("nome_tool"),
                "artefatos": artefatos_por_msg.get(m["id"], []),
                "criadaEm": m["criada_em"],
            }
            for m in mensagens
        ],
    }


# ─── PATCH /chat/threads/{id} ─────────────────────────────────────────────


@router.patch("/threads/{thread_id}", response_model=ThreadResumo)
async def atualizar_thread(
    body: PatchThread,
    thread_id: str = Path(...),
    user: dict = Depends(get_current_user),
) -> dict:
    cliente = get_supabase()
    usuario = _usuario_do_token(user)
    _carregar_thread_ou_404(cliente, thread_id, usuario)

    patch: dict[str, Any] = {}
    if body.titulo is not None:
        novo = body.titulo.strip()[:80] or "Nova conversa"
        patch["titulo"] = novo
    if body.arquivada is not None:
        patch["arquivada"] = body.arquivada
    if not patch:
        raise HTTPException(status_code=400, detail="nada a atualizar")

    resp = (
        cliente.table("chat_thread")
        .update(patch)
        .eq("id", thread_id)
        .execute()
    )
    r = resp.data[0]
    return {
        "id": r["id"],
        "titulo": r["titulo"],
        "arquivada": r["arquivada"],
        "criadaEm": r["criada_em"],
        "ultimaMsgEm": r["ultima_msg_em"],
    }


# ─── DELETE /chat/threads/{id} ────────────────────────────────────────────


@router.delete("/threads/{thread_id}")
async def apagar_thread(
    thread_id: str = Path(...),
    user: dict = Depends(get_current_user),
) -> dict:
    cliente = get_supabase()
    usuario = _usuario_do_token(user)
    _carregar_thread_ou_404(cliente, thread_id, usuario)
    cliente.table("chat_thread").delete().eq("id", thread_id).execute()
    return {"removido": thread_id}


# ─── POST /chat/threads/{id}/mensagens → SSE ──────────────────────────────


@router.post("/threads/{thread_id}/mensagens")
async def enviar_mensagem(
    body: NovaMensagem,
    thread_id: str = Path(...),
    user: dict = Depends(get_current_user),
):
    cliente = get_supabase()
    usuario = _usuario_do_token(user)
    _carregar_thread_ou_404(cliente, thread_id, usuario)
    texto = (body.conteudo or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="mensagem vazia")
    if len(texto) > 4000:
        raise HTTPException(status_code=400, detail="mensagem muito longa (max 4000 chars)")
    _verificar_teto_de_uso(cliente, usuario)

    # Perfil define prompt/tools/modelo: aluno conversa com o mentor (tools
    # restritas ao próprio aluno_id); coordenador com o assistente staff.
    tipo = user.get("tipo")
    preambulo: str | None = None
    if tipo == "aluno":
        perfil = perfis.perfil_aluno(user["aluno_id"], user.get("nome") or "")
        # O contexto de tela NÃO vale para o aluno, e o `preambulo` fica None.
        #
        # Todo o isolamento do mentor está em `perfil_aluno`, que amarra as
        # tools ao `aluno_id` do JWT. O preâmbulo passaria por fora desse
        # portão: ele resolve nomes no banco com o cliente de serviço, então um
        # aluno que POSTasse `contexto.entidade = {tipo: "aluno", id: <outro>}`
        # leria o nome de um colega dentro do próprio system message — dado de
        # menor de idade (CLAUDE.md §6). Além disso as telas do aluno nem estão
        # em `derivarContexto`, que só conhece as rotas da coordenação.
    elif tipo == "coordenador":
        perfil = perfis.perfil_coordenador()
        # Montado AQUI, com o cliente do request: ele lê o banco para nomear as
        # entidades, e o nome que o browser mandou é descartado.
        preambulo = navegacao.preambulo(cliente, body.contexto)
    else:
        # Nunca por omissão: o perfil de coordenação carrega as tools que leem
        # QUALQUER aluno, e era para cá que caía um token de download.
        raise HTTPException(status_code=403, detail="Token não autoriza uso do chat")

    return StreamingResponse(
        _stream_mensagem(cliente, thread_id, usuario, texto, perfil, preambulo),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # evita buffering no proxy
        },
    )


# ─── Streaming ────────────────────────────────────────────────────────────


async def _stream_mensagem(
    cliente,
    thread_id: str,
    usuario: str,
    texto_user: str,
    perfil,
    preambulo: str | None = None,
) -> AsyncIterator[bytes]:
    """Roda o agente e persiste tudo ao final.

    Persistência:
      1. Salva msg do user (ordem = N).
      2. Roda agente (emite SSE).
      3. Salva msg(s) intermediárias de tool_calls/tool_results.
      4. Salva msg final do assistant.
      5. Atualiza ultima_msg_em e (se for o 1º turno) gera título auto.
    """
    historico = _carregar_historico_openai(cliente, thread_id)
    proxima_ordem = _proxima_ordem(cliente, thread_id)

    # 1. Salva msg do user.
    msg_user_resp = (
        cliente.table("chat_mensagem")
        .insert({
            "thread_id": thread_id,
            "ordem": proxima_ordem,
            "papel": "user",
            "conteudo": texto_user,
        })
        .execute()
    )
    msg_user_id = msg_user_resp.data[0]["id"]
    yield Evento_para_bytes("user_salvo", {"mensagem_id": msg_user_id})

    proxima_ordem += 1

    # 2. Stream do agente.
    texto_final = ""
    tool_calls_acumuladas: list[dict] = []
    tokens_in = 0
    tokens_out = 0
    modelo_usado = None
    erro = None

    async for evt in agente.gerar_resposta(
        cliente,
        thread_id=thread_id,
        historico=historico,
        nova_msg_user=texto_user,
        perfil=perfil,
        preambulo=preambulo,
    ):
        # Emite o evento bruto pro front.
        yield evt.formatar_sse().encode("utf-8")
        if evt.nome == "end":
            texto_final = evt.dados.get("texto_final") or ""
            tool_calls_acumuladas = evt.dados.get("tool_calls") or []
            tokens_in = evt.dados.get("tokens_in", 0)
            tokens_out = evt.dados.get("tokens_out", 0)
            modelo_usado = evt.dados.get("modelo")
        if evt.nome == "erro":
            erro = evt.dados.get("mensagem")

    if erro:
        # Persiste a falha como mensagem do assistant (pra ficar visível pro user).
        cliente.table("chat_mensagem").insert({
            "thread_id": thread_id,
            "ordem": proxima_ordem,
            "papel": "assistant",
            "conteudo": f"⚠️ Erro: {erro}",
        }).execute()
        cliente.table("chat_thread").update(
            {"ultima_msg_em": datetime.now(timezone.utc).isoformat()}
        ).eq("id", thread_id).execute()
        return

    # 3. Persiste tool_calls como assistant turn + tool turns.
    if tool_calls_acumuladas:
        assistant_tools_resp = (
            cliente.table("chat_mensagem")
            .insert({
                "thread_id": thread_id,
                "ordem": proxima_ordem,
                "papel": "assistant",
                "conteudo": None,
                "tool_calls": [
                    {"id": tc["id"], "name": tc["nome"], "arguments": tc["args"]}
                    for tc in tool_calls_acumuladas
                ],
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "modelo": modelo_usado,
            })
            .execute()
        )
        assistant_tool_msg_id = assistant_tools_resp.data[0]["id"]
        proxima_ordem += 1

        # Tool result messages
        for tc in tool_calls_acumuladas:
            tool_msg_resp = (
                cliente.table("chat_mensagem")
                .insert({
                    "thread_id": thread_id,
                    "ordem": proxima_ordem,
                    "papel": "tool",
                    "conteudo": json.dumps(tc["resultado"], ensure_ascii=False)[:60_000],
                    "tool_call_id": tc["id"],
                    "nome_tool": tc["nome"],
                })
                .execute()
            )
            tool_msg_id = tool_msg_resp.data[0]["id"]
            proxima_ordem += 1

            # Artefatos: se o resultado for de gerar_grafico ou exportar_csv,
            # cria registro em chat_artefato pra UI renderizar.
            _talvez_salvar_artefato(cliente, tool_msg_id, tc["nome"], tc["resultado"])

    # 4. Resposta final do assistant.
    msg_final_resp = (
        cliente.table("chat_mensagem")
        .insert({
            "thread_id": thread_id,
            "ordem": proxima_ordem,
            "papel": "assistant",
            "conteudo": texto_final,
            "tokens_in": tokens_in if not tool_calls_acumuladas else None,
            "tokens_out": tokens_out if not tool_calls_acumuladas else None,
            "modelo": modelo_usado,
        })
        .execute()
    )
    msg_final_id = msg_final_resp.data[0]["id"]

    # 5. Atualiza thread e gera título auto se for o 1º turno.
    titulo_novo = None
    eh_primeira_resposta = _historico_tem_apenas_user(historico) or len(historico) == 0
    if eh_primeira_resposta and texto_final:
        titulo_novo = agente.gerar_titulo(texto_user, texto_final)

    update_patch: dict = {"ultima_msg_em": datetime.now(timezone.utc).isoformat()}
    # Atualiza também pro caso de erro mais cedo, mas aqui sempre marca.
    if titulo_novo:
        update_patch["titulo"] = titulo_novo
    cliente.table("chat_thread").update(update_patch).eq("id", thread_id).execute()

    if titulo_novo:
        yield Evento_para_bytes("titulo", {"titulo": titulo_novo})
    yield Evento_para_bytes("mensagem_salva", {"mensagem_id": msg_final_id})


# ─── Helpers ─────────────────────────────────────────────────────────────


def Evento_para_bytes(nome: str, dados: dict) -> bytes:
    return f"event: {nome}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n".encode("utf-8")


def _carregar_thread_ou_404(cliente, thread_id: str, usuario: str) -> dict:
    resp = (
        cliente.table("chat_thread")
        .select("id, titulo, arquivada, criada_em, ultima_msg_em, usuario_id")
        .eq("id", thread_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"thread {thread_id} não encontrada")
    t = resp.data[0]
    if t["usuario_id"] != usuario:
        # Não vaza existência: 404 mesmo.
        raise HTTPException(status_code=404, detail=f"thread {thread_id} não encontrada")
    return t


def _carregar_historico_openai(cliente, thread_id: str) -> list[dict]:
    """Reconstrói a lista de mensagens no formato OpenAI a partir do banco."""
    resp = (
        cliente.table("chat_mensagem")
        .select("ordem, papel, conteudo, tool_calls, tool_call_id, nome_tool")
        .eq("thread_id", thread_id)
        .order("ordem")
        .execute()
    )
    historico: list[dict] = []
    for m in (resp.data or []):
        papel = m["papel"]
        if papel == "user":
            historico.append({"role": "user", "content": m.get("conteudo") or ""})
        elif papel == "assistant":
            entry: dict = {"role": "assistant", "content": m.get("conteudo") or ""}
            if m.get("tool_calls"):
                entry["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False),
                        },
                    }
                    for tc in m["tool_calls"]
                ]
            historico.append(entry)
        elif papel == "tool":
            historico.append({
                "role": "tool",
                "tool_call_id": m.get("tool_call_id"),
                "name": m.get("nome_tool"),
                "content": m.get("conteudo") or "",
            })
    return historico


def _historico_tem_apenas_user(historico: list[dict]) -> bool:
    """True se o histórico ainda não tem assistant respondendo (= é o 1º turno real)."""
    return not any(m.get("role") == "assistant" for m in historico)


def _proxima_ordem(cliente, thread_id: str) -> int:
    resp = (
        cliente.table("chat_mensagem")
        .select("ordem")
        .eq("thread_id", thread_id)
        .order("ordem", desc=True)
        .limit(1)
        .execute()
    )
    if not resp.data:
        return 0
    return int(resp.data[0]["ordem"]) + 1


def _talvez_salvar_artefato(cliente, mensagem_id: str, nome_tool: str, resultado: dict) -> None:
    """Persiste artefato se a tool gerou um (gráfico, CSV ou link de navegação)."""
    if not isinstance(resultado, dict):
        return
    if "erro" in resultado:
        return
    tipo = resultado.get("tipo")
    if nome_tool == "gerar_grafico" and tipo in {"histograma", "linha_temporal"}:
        cliente.table("chat_artefato").insert({
            "mensagem_id": mensagem_id,
            "tipo": tipo,
            "titulo": resultado.get("titulo"),
            "payload": resultado.get("payload"),
        }).execute()
    elif nome_tool == "navegar_para" and tipo == "navegacao":
        # Persistido como os outros artefatos: reabrir a conversa amanhã tem
        # que devolver os mesmos links clicáveis, não um texto órfão.
        cliente.table("chat_artefato").insert({
            "mensagem_id": mensagem_id,
            "tipo": "navegacao",
            "titulo": resultado.get("titulo"),
            "payload": resultado.get("payload"),
        }).execute()
    elif nome_tool == "exportar_csv" and resultado.get("tipo") == "csv":
        # Salva o conteúdo no payload (no MVP — pra escala, subir pro Storage).
        cliente.table("chat_artefato").insert({
            "mensagem_id": mensagem_id,
            "tipo": "csv",
            "titulo": resultado.get("titulo"),
            "payload": {
                "conteudo": resultado.get("conteudo"),
                "nLinhas": resultado.get("nLinhas"),
            },
        }).execute()
