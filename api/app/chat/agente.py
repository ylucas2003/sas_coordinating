"""Loop de tool-calling com OpenAI + streaming SSE.

Fluxo:
  1. Recebe histórico da thread (mensagens persistidas) e recorta a janela que
     vai ao modelo (`janela_do_historico`).
  2. Acrescenta nova mensagem do user e chama OpenAI com tools.
  3. Se a resposta tiver tool_calls, executa as tools — ao mesmo tempo, quando
     são mais de uma —, anexa os resultados ao histórico NA ORDEM PEDIDA, e
     chama OpenAI de novo.
  4. Quando a resposta vier sem tool_calls, é a resposta final pro usuário.

Streaming: o modelo responde em pedaços (`stream=True`) e cada pedaço de texto
sai como `token` assim que chega (docs/43 §4.2). O protocolo SSE abaixo não é o
delta nativo da OpenAI, mas um nível acima — eventos semânticos que o front
entende (web/src/dominio/chatStream.ts):

    event: start                     {"thread_id": "..."}
    event: tool_call_start           {"tool_call_id": "...", "nome": "...", "args": {...}}
    event: tool_call_end             {"tool_call_id": "...", "resumido": "..."}
    event: token                     {"texto": "..."}
    event: end                       {"texto_final": "...", "tool_calls": [...],
                                      "tokens_in": N, "tokens_out": N, "modelo": "..."}
    event: erro                      {"mensagem": "..."}

Cada `event` é uma linha `event: <name>` + uma `data: <json>`. Com tools em
paralelo, os `tool_call_start` da volta saem todos antes, na ordem pedida, e
cada `tool_call_end` sai quando AQUELA tool termina; o front casa os dois pelo
`tool_call_id`. O `erro` leva sempre texto para quem usa, nunca o da exceção
(`falha_do_provedor.py`).

Limites:
  - MAX_TURNOS: até 8 voltas de tool calls; passou disso, a resposta acaba em
    `erro`, sem resposta final.
  - MAX_MENSAGENS_HISTORICO: mantém só as últimas N mensagens no contexto.
  - Sem PII anonimization no MVP — nomes vão pra OpenAI. Decisão registrada.
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import threading
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from supabase import Client

from ..config import get_settings
from ..supabase_client import criar_cliente_supabase
from . import falha_do_provedor
from .ferramentas import RespostaDePrazo, Volta, serializar_para_modelo
from .perfis import PerfilAgente
from .prompt import PROMPT_TITULO

try:
    from openai import OpenAI
    _SDK_DISPONIVEL = True
except ImportError:
    _SDK_DISPONIVEL = False

log = logging.getLogger("sas.chat.agente")

MAX_TURNOS = 8
MAX_MENSAGENS_HISTORICO = 30

# Teto de saída por chamada. Sem isto a resposta era ilimitada: o modelo podia
# gerar até o limite da janela, e com MAX_TURNOS=8 o custo de UMA mensagem não
# tinha teto superior nenhum (docs/14 §6.4). 1500 tokens cobrem com folga a
# resposta pedagógica mais longa que o prompt pede.
MAX_TOKENS_RESPOSTA = 1500
TEMPERATURA = 0.2          # Determinístico — respostas reprodutíveis.

#: Quantas THREADS de tool em paralelo uma resposta ocupa ao mesmo tempo. Cada
#: tool roda numa thread do executor padrão do asyncio, que é DIVIDIDO com o
#: resto da API — a cantina inclusive — e tem min(32, CPUs + 4) threads: seis na
#: VPS de 2 vCPU (docs/15). Sem teto, um "compare estes oito alunos" tomaria o
#: executor inteiro, e o resto da API voltaria a esperar o chat, agora por outro
#: caminho (docs/40 §12.1.1).
#:
#: Conta thread, e não tarefa: a tool que estoura o prazo devolve o erro ao
#: modelo, mas a thread dela segue rodando, e a vaga só volta quando ela
#: termina (`_Vagas`). Contando tarefa, com o banco lento seis tools tomavam o
#: executor inteiro em uns 90 s (revisão antecipada do motor, 25/10). O preço:
#: com as vagas todas presas em threads abandonadas, a tool seguinte da mesma
#: resposta espera uma delas terminar — o executor da API não é o que cede.
MAX_TOOLS_SIMULTANEAS = 3

#: O que se lê quando as voltas acabam sem resposta final. O motivo técnico vai
#: para o log, não para a tela nem para o banco (docs/43 §4.1, defeito 4).
MENSAGEM_VOLTAS_ESGOTADAS = (
    "Não consegui fechar a resposta: a pergunta pediu consultas demais de uma vez. "
    "Tente perguntar uma coisa de cada vez."
)

#: A mesma frase do registro (`ferramentas.py`), para o caso de uma exceção
#: escapar dele: o modelo lê isto, e não o texto da exceção.
_FALHA_DA_TOOL = (
    "A consulta '{nome}' falhou do nosso lado. Não repita a chamada; "
    "diga ao usuário que esse dado não está disponível agora."
)


# ─── Eventos SSE ─────────────────────────────────────────────────────────


@dataclass
class Evento:
    nome: str
    dados: dict[str, Any] = field(default_factory=dict)

    def formatar_sse(self) -> str:
        return f"event: {self.nome}\ndata: {json.dumps(self.dados, ensure_ascii=False)}\n\n"


# ─── Janela do histórico ─────────────────────────────────────────────────


def janela_do_historico(historico: list[dict], limite: int) -> list[dict]:
    """As últimas `limite` mensagens, recortadas num formato que a API aceita.

    O fatiamento puro (`historico[-30:]`) podia começar numa mensagem `tool`
    cujo assistant com `tool_calls` ficou fora da janela, e a OpenAI recusa a
    chamada INTEIRA ("messages with role 'tool' must be a response to a
    preceding message with 'tool_calls'"). Como a folha do Tio Léo reabre
    sempre a thread mais recente, thread longa é o caso normal, não a borda
    (docs/43 §1, defeito 2).

    Três regras, nesta ordem:
      1. a janela começa numa mensagem do usuário — o que vem antes dela é o
         meio de uma resposta, sem a pergunta que a explicava;
      2. toda `tool` responde a um `tool_calls` do assistant imediatamente
         anterior a ela (a API quer as respostas logo depois do pedido);
      3. todo assistant com `tool_calls` tem TODAS as respostas logo depois. Se
         falta alguma — persistência parcial: `rotas.py` grava uma linha por
         vez —, sai o grupo inteiro, porque meio par a API também recusa.

    Pura: devolve lista nova e não altera as mensagens recebidas.
    """
    if limite <= 0:
        return []
    janela = historico[-limite:]
    inicio = next((i for i, m in enumerate(janela) if m.get("role") == "user"), len(janela))
    janela = janela[inicio:]

    recorte: list[dict] = []
    i = 0
    while i < len(janela):
        msg = janela[i]
        i += 1
        if msg.get("role") == "tool":
            # Órfã: as respostas legítimas saem junto com o pedido, logo abaixo.
            continue
        if msg.get("role") != "assistant" or "tool_calls" not in msg:
            recorte.append(msg)
            continue
        if not msg["tool_calls"]:
            # `tool_calls: []` a API também recusa; sem pedido, é um assistant comum.
            recorte.append({k: v for k, v in msg.items() if k != "tool_calls"})
            continue
        pedidos = [p.get("id") if isinstance(p, dict) else None for p in msg["tool_calls"]]
        respostas: dict[Any, dict] = {}
        while i < len(janela) and janela[i].get("role") == "tool":
            respostas.setdefault(janela[i].get("tool_call_id"), janela[i])
            i += 1
        if all(p is not None and p in respostas for p in pedidos):
            recorte.append(msg)
            recorte.extend(r for tid, r in respostas.items() if tid in pedidos)
        # Senão o grupo inteiro fica de fora (regra 3).
    return recorte


# ─── Loop principal ───────────────────────────────────────────────────────


def gerar_resposta(
    cliente_db: Client,
    *,
    thread_id: str,
    historico: list[dict],
    nova_msg_user: str,
    perfil: PerfilAgente,
    modelo: str | None = None,
    preambulo: str | None = None,
    fabrica_de_cliente: Callable[[], Any] | None = None,
) -> AsyncIterator[Evento]:
    """Streaming SSE da resposta do agente.

    `historico` no formato OpenAI: lista de dicts {role, content, tool_calls?, tool_call_id?, name?}.
    `nova_msg_user` é o texto que o usuário acabou de mandar — adicionado ao histórico aqui.
    `perfil` define prompt, tools e modelo (coordenador ou aluno — ver perfis.py).
    `preambulo` é o contexto da tela (chat/navegacao.py), colado imediatamente
    antes da mensagem do usuário — nunca no system, que é fixo e cacheável.
    `fabrica_de_cliente` dá a cada tool EM PARALELO o próprio cliente PostgREST
    (padrão: `criar_cliente_supabase`). Só é chamada quando a volta pede mais
    de uma tool; com uma só, vale o `cliente_db`. E não é chamada para a
    chamada idêntica que só espera a primeira: essa não vai ao banco.
    """
    return _gerar(
        cliente_db, thread_id, historico, nova_msg_user, perfil, modelo, preambulo,
        fabrica_de_cliente,
    )


async def _gerar(
    cliente_db: Client,
    thread_id: str,
    historico: list[dict],
    nova_msg_user: str,
    perfil: PerfilAgente,
    modelo_override: str | None,
    preambulo: str | None = None,
    fabrica_de_cliente: Callable[[], Any] | None = None,
) -> AsyncIterator[Evento]:
    settings = get_settings()
    if not _SDK_DISPONIVEL or not settings.openai_api_key:
        # Configuração NOSSA, como a credencial recusada: quem pergunta lê o
        # mesmo texto, e o nome da variável fica no log (docs/43 §4.1, defeito 4).
        log.error(
            "[AÇÃO NECESSÁRIA] chat sem OPENAI_API_KEY ou sem o SDK da OpenAI: "
            "o assistente está desligado"
        )
        yield Evento("erro", {"mensagem": falha_do_provedor.mensagem_para_quem_usa("credencial")})
        return

    modelo = modelo_override or perfil.modelo
    client = OpenAI(api_key=settings.openai_api_key)
    fabrica = fabrica_de_cliente or criar_cliente_supabase

    # ── Histórico final que vai pra OpenAI ──
    mensagens: list[dict] = [perfil.system_message]
    # Janela: as últimas N (mais o system fixo na frente), recortadas para a
    # API aceitar — o fatiamento puro podia abrir num `tool` órfão (defeito 2).
    mensagens.extend(janela_do_historico(historico, MAX_MENSAGENS_HISTORICO))
    # O contexto da tela cola no turno, não no system: ele muda a cada
    # mensagem, e o system precisa ficar idêntico para o cache valer.
    if preambulo:
        mensagens.append({"role": "system", "content": preambulo})
    mensagens.append({"role": "user", "content": nova_msg_user})

    yield Evento("start", {"thread_id": thread_id})

    tokens_in_total = 0
    tokens_out_total = 0
    tool_calls_executadas: list[dict] = []
    texto_final = ""
    erro_fatal: str | None = None
    # Uma por resposta, não por thread: é o que o registro usa para não rodar
    # duas vezes a mesma consulta dentro das oito voltas (docs/43 §3.2, inv. 4).
    volta = Volta()
    # Também da resposta, e não de cada volta: a thread que o prazo abandonou
    # numa volta ainda ocupa o executor na seguinte (MAX_TOOLS_SIMULTANEAS).
    vagas = _Vagas()
    # Tudo o que já saiu como `token`, somadas as voltas. Com streaming, o
    # texto de uma volta que termina pedindo tools ("vou olhar suas notas") já
    # foi lido quando o pedido aparece; o `texto_final` é este, para o que fica
    # salvo ser o que a pessoa viu.
    exibido = ""

    # O que tem de parar junto se o gerador for fechado no meio (o cliente
    # desconectou): a leitura do stream e as tools ainda no ar.
    leitor: _LeitorDoStream | None = None
    no_ar: set[asyncio.Task[dict]] = set()
    try:
        for turno in range(MAX_TURNOS):
            log.info("chat thread=%s turno=%d msgs=%d", thread_id, turno, len(mensagens))
            parametros: dict[str, Any] = {
                "model": modelo,
                "temperature": TEMPERATURA,
                "max_tokens": MAX_TOKENS_RESPOSTA,
                # Cópia: a requisição é montada noutra thread, e esta lista
                # continua crescendo aqui.
                "messages": list(mensagens),
                "tools": perfil.schemas,
                "tool_choice": "auto",
            }
            resposta = _RespostaDoModelo()
            try:
                if settings.chat_streaming:
                    # Uma thread abre e lê o stream; aqui só chegam os pedaços
                    # (o porquê está em `_LeitorDoStream`).
                    leitor = _LeitorDoStream(
                        functools.partial(
                            client.chat.completions.create,
                            **parametros,
                            stream=True,
                            stream_options={"include_usage": True},
                        )
                    )
                    separador = _separador(exibido)
                    while (pedaco := await leitor.proximo()) is not None:
                        texto = resposta.absorver(pedaco)
                        if not texto:
                            continue
                        if separador:
                            exibido += separador
                            yield Evento("token", {"texto": separador})
                            separador = ""
                        exibido += texto
                        yield Evento("token", {"texto": texto})
                    leitor = None
                else:
                    # ⚠️ `to_thread` e não a chamada direta: o cliente da OpenAI é o
                    # SÍNCRONO, e este `async def` roda no ÚNICO event loop do processo
                    # (`UVICORN_WORKERS=1`, invariante do CLAUDE.md). Chamado direto,
                    # ele congela a API inteira enquanto o modelo pensa — e uma volta de
                    # tool calling passa de 60s com folga, tanto que o nginx reserva
                    # 300s para ela. Quem esperava era todo mundo: o balcão da cantina
                    # parava de ler QR porque um coordenador abriu o assistente
                    # (docs/40 §12.1.1).
                    resposta.absorver_completa(
                        await asyncio.to_thread(
                            client.chat.completions.create, **parametros, stream=False
                        )
                    )
            except Exception as e:
                # Antes era `f"falha chamando o modelo: {e}"`: o texto cru do SDK
                # ia para a tela de um menor e para `chat_mensagem`. Agora quem
                # usa lê o texto da falha, e o motivo vai para o log (docs/43
                # §4.1, defeito 4).
                if leitor is not None:
                    leitor.parar()
                    leitor = None
                falha = falha_do_provedor.classificar(e)
                falha_do_provedor.registrar(
                    falha, e, thread_id=thread_id, modelo=modelo, usuario=perfil.sessao.usuario
                )
                erro_fatal = falha.mensagem
                break

            tokens_in_total += resposta.tokens_in
            tokens_out_total += resposta.tokens_out
            chamadas = resposta.chamadas()

            # ── Se vieram tool_calls, executa e continua ──
            if chamadas:
                # Anexa o turno do assistant ao histórico (mesmo sem content de texto).
                mensagens.append({
                    "role": "assistant",
                    "content": resposta.texto,
                    "tool_calls": [c.para_o_modelo() for c in chamadas],
                })

                resultados: dict[int, dict] = {}
                if settings.chat_tools_em_paralelo and len(chamadas) > 1:
                    for c in chamadas:
                        yield Evento("tool_call_start", c.evento_de_inicio())
                    tarefas = _disparar_em_paralelo(perfil, chamadas, volta, cliente_db, fabrica, vagas)
                    no_ar.update(tarefas)
                    pendentes = set(tarefas)
                    while pendentes:
                        prontas, pendentes = await asyncio.wait(
                            pendentes, return_when=asyncio.FIRST_COMPLETED
                        )
                        # Duas que terminam juntas saem na ordem pedida: o
                        # evento fica determinístico.
                        for tarefa in sorted(prontas, key=tarefas.__getitem__):
                            no_ar.discard(tarefa)
                            i = tarefas[tarefa]
                            resultados[i] = tarefa.result()
                            yield Evento("tool_call_end", {
                                "tool_call_id": chamadas[i].id,
                                "resumido": _resumir_resultado(resultados[i]),
                            })
                else:
                    for i, c in enumerate(chamadas):
                        yield Evento("tool_call_start", c.evento_de_inicio())
                        # O registro roda a tool numa thread, pelo mesmo motivo da
                        # chamada ao modelo: as tools leem o banco pelo cliente
                        # PostgREST, que é síncrono, e uma tool que varre notas
                        # segurava o loop junto com o modelo. Escopo, prazo e as
                        # outras guardas também moram lá (docs/43 §3.2).
                        resultados[i] = await _executar_tool(perfil, c, cliente_db, volta)
                        yield Evento("tool_call_end", {
                            "tool_call_id": c.id,
                            "resumido": _resumir_resultado(resultados[i]),
                        })

                # NA ORDEM PEDIDA, não na de chegada: é a dos `tool_calls` do
                # assistant acima, e é nela que `rotas.py` persiste — a mesma
                # sequência volta como histórico na mensagem seguinte.
                for i, c in enumerate(chamadas):
                    tool_calls_executadas.append({
                        "id": c.id, "nome": c.nome, "args": c.args, "resultado": resultados[i],
                    })
                    # OpenAI exige role='tool' com tool_call_id e content (string).
                    mensagens.append({
                        "role": "tool",
                        "tool_call_id": c.id,
                        "name": c.nome,
                        "content": serializar_para_modelo(resultados[i]),
                    })
                continue  # próximo turno

            # ── Sem tool_calls → resposta final ──
            if settings.chat_streaming:
                texto_final = exibido
            else:
                texto_final = resposta.texto
                # Streaming "fake" — o texto inteiro em pedaços de 40, para a UI
                # renderizar aos poucos. É o caminho de `CHAT_STREAMING=false`.
                for trecho in _quebra_chunks(texto_final, tamanho=40):
                    yield Evento("token", {"texto": trecho})
            break
        else:
            # Esgotou MAX_TURNOS sem resposta final.
            log.warning(
                "chat thread=%s: %d voltas de tool calling sem resposta final",
                thread_id, MAX_TURNOS,
            )
            erro_fatal = MENSAGEM_VOLTAS_ESGOTADAS
    finally:
        # Gerador fechado no meio (o cliente desconectou) ou tarefa cancelada:
        # a thread do stream é avisada e fecha a conexão no próximo pedaço, e
        # as tools ainda no ar são canceladas. Nada aqui espera — este bloco
        # também roda quando o coletor finaliza um gerador abandonado.
        if leitor is not None:
            leitor.parar()
        for tarefa in no_ar:
            tarefa.cancel()

    if erro_fatal:
        yield Evento("erro", {"mensagem": erro_fatal})

    yield Evento("end", {
        "tokens_in": tokens_in_total,
        "tokens_out": tokens_out_total,
        "modelo": modelo,
        "texto_final": texto_final,
        "tool_calls": tool_calls_executadas,
    })


# ─── O que o modelo respondeu ────────────────────────────────────────────


@dataclass
class _Chamada:
    """Um tool_call do modelo, já montado — venha do stream ou da resposta inteira."""

    id: str
    nome: str
    #: O JSON cru, como o modelo mandou: é ele que volta no histórico.
    argumentos: str
    args: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        try:
            valor = json.loads(self.argumentos or "{}")
        except json.JSONDecodeError:
            valor = {}
        self.args = valor if isinstance(valor, dict) else {}

    @property
    def chave(self) -> str:
        """A consulta, para achar o mesmo pedido duas vezes na mesma volta.

        Pelos argumentos CRUS: dois pedidos que só ficam iguais depois da
        conversão de tipo do registro (`"1"` e `1`) rodam os dois — custa uma
        consulta a mais, não uma resposta errada."""
        return f"{self.nome}:{json.dumps(self.args, sort_keys=True, ensure_ascii=False, default=str)}"

    def para_o_modelo(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {"name": self.nome, "arguments": self.argumentos},
        }

    def evento_de_inicio(self) -> dict[str, Any]:
        return {"tool_call_id": self.id, "nome": self.nome, "args": self.args}


@dataclass
class _RespostaDoModelo:
    """Uma chamada ao modelo, venha ela em pedaços (stream) ou inteira."""

    partes: list[str] = field(default_factory=list)
    #: Os tool_calls em montagem, por `index`. No stream, o `id` e o nome
    #: chegam no primeiro pedaço de cada um, e os argumentos em fragmentos de
    #: JSON espalhados pelos seguintes — às vezes intercalados com os de outro.
    pedidos: dict[int, dict[str, Any]] = field(default_factory=dict)
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def texto(self) -> str:
        return "".join(self.partes)

    def absorver(self, pedaco: Any) -> str:
        """Soma um `ChatCompletionChunk`; devolve o texto novo dele ("" se não houver)."""
        self._somar_uso(pedaco.usage)
        # Com `include_usage`, o último pedaço vem com `choices` vazio e o uso.
        if not pedaco.choices:
            return ""
        delta = pedaco.choices[0].delta
        for parcial in delta.tool_calls or []:
            pedido = self.pedidos.setdefault(
                parcial.index, {"id": "", "nome": "", "argumentos": []}
            )
            if parcial.id:
                pedido["id"] = parcial.id
            if parcial.function is not None:
                if parcial.function.name:
                    pedido["nome"] = parcial.function.name
                if parcial.function.arguments:
                    pedido["argumentos"].append(parcial.function.arguments)
        if delta.content:
            self.partes.append(delta.content)
        return delta.content or ""

    def absorver_completa(self, resposta: Any) -> None:
        """A resposta inteira, de `stream=False`."""
        self._somar_uso(resposta.usage)
        msg = resposta.choices[0].message
        if msg.content:
            self.partes.append(msg.content)
        for i, tc in enumerate(msg.tool_calls or []):
            self.pedidos[i] = {
                "id": tc.id, "nome": tc.function.name, "argumentos": [tc.function.arguments or ""],
            }

    def chamadas(self) -> list[_Chamada]:
        return [
            _Chamada(id=p["id"], nome=p["nome"], argumentos="".join(p["argumentos"]))
            for _, p in sorted(self.pedidos.items())
        ]

    def _somar_uso(self, uso: Any) -> None:
        if uso:
            self.tokens_in += uso.prompt_tokens or 0
            self.tokens_out += uso.completion_tokens or 0


# ─── O stream, lido numa thread ──────────────────────────────────────────


class _LeitorDoStream:
    """A resposta em stream do modelo, lida numa thread e entregue ao loop.

    ⚠️ O cliente da OpenAI é o SÍNCRONO: abrir o stream (conectar, esperar o
    cabeçalho) e iterá-lo (esperar cada pedaço) bloqueiam. Feito direto neste
    `async def`, isso congelaria o ÚNICO event loop do processo
    (`UVICORN_WORKERS=1`) pela resposta inteira — e o balcão da cantina já
    parou assim (docs/40 §12.1.1, tests/test_desempenho_event_loop.py). Então
    uma thread lê, e cada pedaço atravessa para o loop por
    `call_soon_threadsafe` numa `asyncio.Queue` — que não é thread-safe e por
    isso só é tocada de dentro do loop.

    Thread própria, e não `to_thread`: a leitura dura a resposta toda, e o
    executor padrão é dividido com o resto da API (ver MAX_TOOLS_SIMULTANEAS).
    """

    def __init__(self, abrir: Callable[[], Any]) -> None:
        self._abrir = abrir
        self._loop = asyncio.get_running_loop()
        self._fila: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        self._parar = threading.Event()
        # O contexto vai junto para o `request_id` dos logs (observabilidade.py)
        # valer também na thread, como vale no `to_thread`.
        contexto = contextvars.copy_context()
        threading.Thread(
            target=contexto.run, args=(self._ler,), name="sas-chat-stream", daemon=True
        ).start()

    async def proximo(self) -> Any | None:
        """O próximo pedaço; `None` no fim; a exceção da thread, se ela falhou."""
        tipo, valor = await self._fila.get()
        if tipo == "erro":
            raise valor
        return valor if tipo == "pedaco" else None

    def parar(self) -> None:
        """Quem lia foi embora: só SINALIZA. A thread confere o sinal a cada
        pedaço e, no próximo que chegar, para de ler e fecha o stream ela
        mesma — não segue lendo para ninguém até o modelo terminar. Roda no
        loop, e por isso não espera nada.

        Não fecha o stream daqui. O httpx e o httpcore não garantem fechar por
        uma thread uma resposta que outra ainda está lendo — o estado do h11 e
        do pool seria mexido pelas duas sem trava comum —, e o ganho nem
        existe na produção: no Linux, fechar o socket não acorda o recv() de
        quem está bloqueado nele; a thread só sairia no próximo pedaço de
        qualquer jeito (revisão antecipada do motor, 25/10)."""
        self._parar.set()

    # ── Daqui para baixo, roda na thread ──

    def _ler(self) -> None:
        # Quem lê a fila espera um desfecho, e sem ele esperaria para sempre:
        # este é o de reserva, se a thread morrer por algo que não é Exception.
        desfecho: tuple[str, Any] = (
            "erro", RuntimeError("a leitura do stream terminou sem desfecho"),
        )
        stream: Any = None
        try:
            stream = self._abrir()
            if self._parar.is_set():
                return  # parou enquanto abria; o `finally` fecha
            for pedaco in stream:
                if self._parar.is_set():
                    return
                self._entregar("pedaco", pedaco)
            desfecho = ("fim", None)
        except Exception as e:
            desfecho = ("erro", e)
        finally:
            # Fecha AQUI, na thread que lê — a única que toca o stream —, e
            # ANTES de avisar: a conexão volta ao pool a tempo de a próxima
            # volta do modelo reaproveitá-la.
            if stream is not None:
                _fechar_stream(stream)
            # Depois de `parar` ninguém mais lê.
            if not self._parar.is_set():
                self._entregar(*desfecho)

    def _entregar(self, tipo: str, valor: Any) -> None:
        try:
            self._loop.call_soon_threadsafe(self._fila.put_nowait, (tipo, valor))
        except RuntimeError:
            # O loop já fechou (processo desligando): não há mais quem leia.
            self._parar.set()


def _fechar_stream(stream: Any) -> None:
    fechar = getattr(stream, "close", None)
    if callable(fechar):
        try:
            fechar()
        except Exception:
            log.debug("fechar o stream do modelo falhou", exc_info=True)


# ─── Tools ───────────────────────────────────────────────────────────────


async def _executar_tool(
    perfil: PerfilAgente, chamada: _Chamada, cliente: Any, volta: Volta
) -> dict:
    """Uma tool pelo registro, que a roda numa thread com prazo e as guardas do
    docs/43 §3.2. O `try` é a última linha: uma exceção que escapasse dele
    derrubaria a resposta inteira — e, em paralelo, viraria tarefa com exceção
    que ninguém lê."""
    try:
        return await perfil.executar(chamada.nome, cliente, chamada.args, volta)
    except Exception:
        log.exception("ferramenta %s escapou do registro", chamada.nome)
        return {"erro": _FALHA_DA_TOOL.format(nome=chamada.nome)}


@dataclass
class _Vagas:
    """O que as tools em paralelo de UMA resposta dividem — e que só volta
    quando a THREAD da tool termina, não quando a tarefa responde.

    `threads` é o teto de MAX_TOOLS_SIMULTANEAS. `compartilhado` é a trava do
    cliente do request, para quando a tool não ganhou cliente próprio: uma tool
    por vez nele. As duas ficam presas enquanto a thread que o prazo abandonou
    roda — ela segue ocupando o executor, e segue usando o cliente.
    """

    threads: asyncio.Semaphore = field(
        default_factory=lambda: asyncio.Semaphore(MAX_TOOLS_SIMULTANEAS)
    )
    compartilhado: asyncio.Lock = field(default_factory=asyncio.Lock)


def _disparar_em_paralelo(
    perfil: PerfilAgente,
    chamadas: list[_Chamada],
    volta: Volta,
    cliente_db: Any,
    fabrica: Callable[[], Any],
    vagas: _Vagas,
) -> dict[asyncio.Task[dict], int]:
    """Uma tarefa por tool da volta, cada uma com o PRÓPRIO cliente PostgREST.

    ⚠️ O cliente cacheado (`get_supabase`) multiplexa tudo numa conexão HTTP/2,
    e um GOAWAY numa stream derruba as outras (supabase_client.py): duas tools
    lendo por ele ao mesmo tempo podiam levar uma à outra junto.
    """
    primeira: dict[str, asyncio.Task[dict]] = {}
    tarefas: dict[asyncio.Task[dict], int] = {}
    for i, chamada in enumerate(chamadas):
        tarefa = asyncio.create_task(
            _rodar_em_paralelo(
                perfil, chamada, volta,
                cliente_db=cliente_db, fabrica=fabrica, vagas=vagas,
                depois_de=primeira.get(chamada.chave),
            ),
            name=f"sas-chat-tool:{chamada.nome}",
        )
        primeira.setdefault(chamada.chave, tarefa)
        tarefas[tarefa] = i
    return tarefas


async def _rodar_em_paralelo(
    perfil: PerfilAgente,
    chamada: _Chamada,
    volta: Volta,
    *,
    cliente_db: Any,
    fabrica: Callable[[], Any],
    vagas: _Vagas,
    depois_de: asyncio.Task[dict] | None,
) -> dict:
    if depois_de is not None:
        # A mesma consulta duas vezes na mesma volta: espera a primeira, e o
        # registro responde "repetida" como responderia em série (docs/43 §3.2,
        # invariante 4). `wait`, e não `await`: o desfecho dela não é deste.
        await asyncio.wait({depois_de})
        if _deu_certo(depois_de):
            # Deu certo, o "repetida" sai do registro sem ir ao banco: nem
            # cliente nem vaga (revisão antecipada do motor, 25/10). `None`
            # falha fechado se isso um dia deixar de valer — a tool quebraria
            # com a falha genérica do registro, em vez de dividir um cliente.
            # Se a primeira falhou, esta roda de verdade, como em série.
            return await _executar_tool(perfil, chamada, None, volta)

    await vagas.threads.acquire()
    devolver: list[Callable[[], None]] = [vagas.threads.release]
    cliente: Any = None
    try:
        cliente = await _cliente_proprio(fabrica)
        if cliente is None:
            # Sem cliente próprio, o compartilhado atende UMA tool por vez.
            await vagas.compartilhado.acquire()
            devolver.append(vagas.compartilhado.release)
        resultado = await _executar_tool(
            perfil, chamada, cliente_db if cliente is None else cliente, volta
        )
    except BaseException:
        # Cancelada no meio — o cliente da conversa desconectou. A thread da
        # tool pode seguir rodando com o cliente, e ele fica para o coletor; a
        # vaga e a trava voltam, porque a resposta acabou.
        _devolver(devolver)
        raise

    if isinstance(resultado, RespostaDePrazo):
        # Passou do prazo: o modelo já tem o erro, mas a thread segue rodando,
        # ocupando o executor e lendo por este cliente. Fechá-lo agora trocaria
        # a linha de log com a duração real por uma falha que não houve. Vaga,
        # trava e cliente voltam quando ela terminar de fato.
        resultado.thread.add_done_callback(
            functools.partial(_ao_fim_da_thread, devolver, cliente)
        )
        return resultado
    # Todo outro desfecho — sucesso, erro de domínio, "repetida", argumento
    # inválido, tool inexistente, falha interna — é de thread que já terminou:
    # o cliente fecha agora, e não no coletor.
    try:
        if cliente is not None:
            await asyncio.to_thread(_fechar_cliente, cliente)
    finally:
        _devolver(devolver)
    return resultado


def _deu_certo(tarefa: asyncio.Task[dict]) -> bool:
    """A tarefa respondeu sem erro — e então o registro guardou a consulta."""
    if tarefa.cancelled() or tarefa.exception() is not None:
        return False
    resultado = tarefa.result()
    return isinstance(resultado, dict) and "erro" not in resultado


def _devolver(devolver: list[Callable[[], None]]) -> None:
    for liberar in reversed(devolver):
        liberar()


def _ao_fim_da_thread(
    devolver: list[Callable[[], None]], cliente: Any, _fim: asyncio.Future[None]
) -> None:
    """A thread que o prazo abandonou terminou: o que ela segurava volta. Roda
    no loop, como callback do Future da `RespostaDePrazo` — não espera nada."""
    if cliente is not None:
        _fechar_em_segundo_plano(cliente)
    _devolver(devolver)


def _fechar_em_segundo_plano(cliente: Any) -> None:
    """Fecha o cliente numa thread, sem esperar: quem chama é um callback do loop."""
    try:
        asyncio.get_running_loop().run_in_executor(None, _fechar_cliente, cliente)
    except RuntimeError:
        # O executor já está desligando (o processo, ou o `asyncio.run` de um
        # teste, terminando): fecha aqui mesmo — não sobra o que travar.
        _fechar_cliente(cliente)


async def _cliente_proprio(fabrica: Callable[[], Any]) -> Any | None:
    """Um cliente novo, montado numa thread: o httpx lê o pacote de
    certificados do disco ao nascer, e no loop isso seria um bloqueio por tool."""
    try:
        return await asyncio.to_thread(fabrica)
    except Exception:
        log.warning(
            "tool em paralelo sem cliente próprio; vai pelo compartilhado, uma por vez",
            exc_info=True,
        )
        return None


def _fechar_cliente(cliente: Any) -> None:
    """Fecha a conexão do cliente extra, se ele souber fechar. Nunca lança.

    `SyncPostgrestClient` fecha por `aclose()` — que, apesar do nome, é
    síncrono —, um httpx por `close()`, e o `Client` do supabase-py não tem
    nenhum dos dois.
    """
    for nome in ("close", "aclose"):
        metodo = getattr(cliente, nome, None)
        if not callable(metodo):
            continue
        try:
            retorno = metodo()
            if asyncio.iscoroutine(retorno):
                # Fechamento assíncrono não tem loop nesta thread para rodar.
                retorno.close()
        except Exception:
            log.debug("fechar o cliente da tool falhou", exc_info=True)
        return


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


def _quebra_chunks(texto: str, *, tamanho: int) -> list[str]:
    """Quebra string em pedaços do tamanho indicado — UI render incremental."""
    if not texto:
        return []
    return [texto[i : i + tamanho] for i in range(0, len(texto), tamanho)]


def _separador(exibido: str) -> str:
    """O que vai entre o texto de uma volta e o da seguinte, no stream.

    O texto de uma volta que terminou pedindo tools já foi lido quando a
    seguinte começa a escrever; sem quebra, as duas frases grudariam.
    """
    if not exibido or exibido.endswith("\n\n"):
        return ""
    return "\n" if exibido.endswith("\n") else "\n\n"


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
