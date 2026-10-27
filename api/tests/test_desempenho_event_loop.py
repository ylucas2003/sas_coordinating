"""O event loop continua atendendo enquanto o LLM pensa (docs/40 §12.1.1).

Este arquivo existe por causa de um defeito que **não dava erro**: o cliente da
OpenAI é o SÍNCRONO, e ele era chamado direto de dentro de `async def`. Com
`UVICORN_WORKERS=1` — invariante do CLAUDE.md, por causa das travas do sync, do
despachante e do barramento SSE da cantina — existe **um** event loop no
processo inteiro. Uma chamada bloqueante ali dentro congela a API para todo
mundo: o balcão da cantina parava de ler QR porque um coordenador tinha aberto o
assistente, e nenhum log dizia isso.

⚠️ **O teste mede concorrência, não velocidade.** Ele não afirma que a chamada
do modelo é rápida — ela é lenta e continua sendo. Afirma que, enquanto ela
acontece, o loop segue vivo. Por isso o relógio é um contador de batidas, e não
um `time.time()` de ponta a ponta: o que se quer provar é que OUTRA coisa correu
no meio.

Se algum destes quebrar, a pergunta certa não é "o mock está lento?" — é "quem
voltou a chamar coisa síncrona direto do loop?".

Desde o streaming de verdade (docs/43 §4.2) o modelo tem DOIS caminhos: com
`stream=True`, abrir e ler o stream acontece na thread do `_LeitorDoStream`;
com `CHAT_STREAMING=false`, a chamada inteira vai por `to_thread`, como antes.
Os dois testes rodam nos dois, porque cada caminho bloquearia o loop por um
motivo diferente. O batimento DURANTE a leitura do stream, pedaço a pedaço,
está em test_chat_agente.py.
"""

import asyncio
import time
from dataclasses import dataclass

import pytest
from openai.types.chat import ChatCompletionChunk

from app.chat import agente
from app.chat.ferramentas import Ferramenta, Registro, Sessao

from .fake_postgrest import FakeCliente

#: Quanto o "modelo" demora, de mentira. Grande o bastante para caber muitas
#: batidas de 5 ms, pequeno o bastante para o arquivo inteiro rodar rápido.
DEMORA_DO_MODELO_S = 0.30
INTERVALO_DA_BATIDA_S = 0.005
#: Com o loop livre, cabem ~60 batidas em 300 ms. Exigimos 10: folga enorme
#: para máquina lenta ou CI ocupado, e ainda assim impossível de alcançar se a
#: chamada estiver bloqueando (aí o número é 0 ou 1).
BATIDAS_MINIMAS = 10


# ─── O modelo de mentira ──────────────────────────────────────────────────


@dataclass
class _Mensagem:
    content: str
    tool_calls: None = None


@dataclass
class _Escolha:
    message: _Mensagem


@dataclass
class _Resposta:
    choices: list
    usage: None = None


def _pedaco(delta: dict | None = None, uso: dict | None = None) -> ChatCompletionChunk:
    """Um pedaço de `stream=True` no formato do SDK. Sem `delta`, é o último:
    `choices` vazio e o uso, como chega com `include_usage`."""
    return ChatCompletionChunk.model_validate({
        "id": "teste",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "modelo-de-teste",
        "choices": [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": None}],
        "usage": uso,
    })


class _CompletionsQueDorme:
    """`create()` que dorme com `time.sleep` — bloqueante de verdade.

    `asyncio.sleep` aqui não testaria nada: ele já devolve o loop. O ponto é
    justamente ser uma função síncrona lenta, como a da OpenAI. Com
    `stream=True` a demora é a de abrir o stream (o modelo pensando antes do
    primeiro pedaço), e ela acontece igual.
    """

    def create(self, **kwargs):
        time.sleep(DEMORA_DO_MODELO_S)
        if kwargs.get("stream"):
            uso = {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}
            return iter([_pedaco({"content": "pronto"}), _pedaco(uso=uso)])
        return _Resposta(choices=[_Escolha(message=_Mensagem(content="pronto"))])


class _ClienteOpenAiFalso:
    def __init__(self, **_kwargs):
        self.chat = type("Chat", (), {"completions": _CompletionsQueDorme()})()


def _perfil_minimo(registro: Registro | None = None) -> agente.PerfilAgente:
    return agente.PerfilAgente(
        sessao=Sessao(tipo="coordenador", usuario="coord:teste"),
        system_message={"role": "system", "content": "teste"},
        modelo="modelo-de-teste",
        registro=registro or Registro([]),
    )


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    monkeypatch.setattr(agente, "OpenAI", _ClienteOpenAiFalso)
    monkeypatch.setattr(agente, "_SDK_DISPONIVEL", True)
    yield
    get_settings.cache_clear()


@pytest.fixture(params=["stream", "resposta_inteira"])
def caminho_do_modelo(request, monkeypatch) -> str:
    """Os dois caminhos de `agente.py`: `stream=True` e `CHAT_STREAMING=false`."""
    from app.config import get_settings

    monkeypatch.setenv("CHAT_STREAMING", "true" if request.param == "stream" else "false")
    get_settings.cache_clear()
    return request.param


# ─── O teste ──────────────────────────────────────────────────────────────


async def _bater(contador: list[int], parar: asyncio.Event) -> None:
    """Uma tarefa comum, do tipo que qualquer outra requisição seria."""
    while not parar.is_set():
        contador[0] += 1
        await asyncio.sleep(INTERVALO_DA_BATIDA_S)


async def _consumir_o_agente(perfil: agente.PerfilAgente | None = None) -> list[str]:
    eventos = []
    async for evt in agente.gerar_resposta(
        cliente_db=FakeCliente({}),
        thread_id="T1",
        historico=[],
        nova_msg_user="oi",
        perfil=perfil or _perfil_minimo(),
    ):
        eventos.append(evt.nome)
    return eventos


class TestChatNaoCongelaAApi:
    def test_o_loop_segue_atendendo_enquanto_o_modelo_pensa(self, caminho_do_modelo):
        """O teste que FALHAVA antes do `to_thread` (docs/40, passo 2).

        Antes, `contador` terminava em 1: a batida rodava uma vez, esbarrava na
        chamada síncrona e só voltava 300 ms depois — que é exatamente o que a
        cantina sentia como "a tela travou". No caminho de stream, quem tira a
        espera do loop é a thread do `_LeitorDoStream`, que abre o stream.
        """

        async def cenario():
            contador = [0]
            parar = asyncio.Event()
            batendo = asyncio.create_task(_bater(contador, parar))
            eventos = await _consumir_o_agente()
            parar.set()
            await batendo
            return contador[0], eventos

        batidas, eventos = asyncio.run(cenario())

        assert batidas >= BATIDAS_MINIMAS, (
            f"só {batidas} batidas durante {DEMORA_DO_MODELO_S}s de modelo — "
            "o event loop ficou bloqueado, alguém voltou a chamar o cliente "
            "síncrono direto de dentro de async def"
        )
        assert "token" in eventos, "o agente precisa ter respondido de verdade"

    def test_a_execucao_de_tool_tambem_sai_do_loop(self, monkeypatch, caminho_do_modelo):
        """As tools leem o banco pelo cliente PostgREST, que também é síncrono.

        Uma tool que varre notas segurava o loop junto com o modelo — e essa
        parte não aparecia em nenhuma medição, porque o tempo era contabilizado
        como "o chat está lento".

        Passa pelo caminho de verdade: o agente pede a tool, e quem a executa é
        o registro (`chat/ferramentas.py`). A versão anterior chamava
        `asyncio.to_thread` direto no teste, e por isso continuaria verde se o
        agente voltasse a executar a tool dentro do loop. Aqui o modelo de
        mentira é INSTANTÂNEO, para que toda batida conte a favor da tool.
        """
        marcas: list[str] = []

        def _tool_lenta(cliente):
            time.sleep(DEMORA_DO_MODELO_S)
            marcas.append("tool")
            return {"ok": True}

        registro = Registro([
            Ferramenta(
                nome="tool_lenta",
                descricao="Tool de teste que demora como uma varredura de notas.",
                parametros={"type": "object", "properties": {}},
                escopo="coordenacao",
                handler=_tool_lenta,
            )
        ])
        monkeypatch.setattr(agente, "OpenAI", _ClienteQuePedeTool)

        async def cenario():
            contador = [0]
            parar = asyncio.Event()
            batendo = asyncio.create_task(_bater(contador, parar))
            eventos = await _consumir_o_agente(_perfil_minimo(registro))
            parar.set()
            await batendo
            return contador[0], eventos

        batidas, eventos = asyncio.run(cenario())
        assert marcas == ["tool"], "a tool precisa ter rodado pelo registro"
        assert "tool_call_end" in eventos
        assert batidas >= BATIDAS_MINIMAS, (
            f"só {batidas} batidas durante {DEMORA_DO_MODELO_S}s de tool — a "
            "execução da tool voltou a acontecer dentro do event loop"
        )


@dataclass
class _Funcao:
    name: str
    arguments: str


@dataclass
class _ChamadaDeTool:
    id: str
    function: _Funcao


class _CompletionsQuePedeTool:
    """Primeira chamada pede `tool_lenta`; a segunda responde. Sem demora.

    Com `stream=True` o pedido chega como chega da OpenAI: em pedaços, com o
    tool_call identificado pelo `index`."""

    def __init__(self):
        self.chamadas = 0

    def create(self, **kwargs):
        self.chamadas += 1
        if kwargs.get("stream"):
            if self.chamadas == 1:
                return iter([
                    _pedaco({"tool_calls": [{
                        "index": 0,
                        "id": "c1",
                        "type": "function",
                        "function": {"name": "tool_lenta", "arguments": ""},
                    }]}),
                    _pedaco({"tool_calls": [{"index": 0, "function": {"arguments": "{}"}}]}),
                ])
            return iter([_pedaco({"content": "pronto"})])
        if self.chamadas == 1:
            mensagem = _Mensagem(content="")
            mensagem.tool_calls = [_ChamadaDeTool("c1", _Funcao("tool_lenta", "{}"))]
        else:
            mensagem = _Mensagem(content="pronto")
        return _Resposta(choices=[_Escolha(message=mensagem)])


class _ClienteQuePedeTool:
    def __init__(self, **_kwargs):
        self.chat = type("Chat", (), {"completions": _CompletionsQuePedeTool()})()
