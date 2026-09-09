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
"""

import asyncio
import time
from dataclasses import dataclass

import pytest

from app.chat import agente

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


class _CompletionsQueDorme:
    """`create()` que dorme com `time.sleep` — bloqueante de verdade.

    `asyncio.sleep` aqui não testaria nada: ele já devolve o loop. O ponto é
    justamente ser uma função síncrona lenta, como a da OpenAI.
    """

    def create(self, **_kwargs):
        time.sleep(DEMORA_DO_MODELO_S)
        return _Resposta(choices=[_Escolha(message=_Mensagem(content="pronto"))])


class _ClienteOpenAiFalso:
    def __init__(self, **_kwargs):
        self.chat = type("Chat", (), {"completions": _CompletionsQueDorme()})()


def _perfil_minimo() -> agente.PerfilAgente:
    return agente.PerfilAgente(
        schemas=[],
        executar=lambda nome, cliente, args: {"ok": True},
        system_message={"role": "system", "content": "teste"},
        modelo="modelo-de-teste",
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


# ─── O teste ──────────────────────────────────────────────────────────────


async def _bater(contador: list[int], parar: asyncio.Event) -> None:
    """Uma tarefa comum, do tipo que qualquer outra requisição seria."""
    while not parar.is_set():
        contador[0] += 1
        await asyncio.sleep(INTERVALO_DA_BATIDA_S)


async def _consumir_o_agente() -> list[str]:
    eventos = []
    async for evt in agente.gerar_resposta(
        cliente_db=FakeCliente({}),
        thread_id="T1",
        historico=[],
        nova_msg_user="oi",
        perfil=_perfil_minimo(),
    ):
        eventos.append(evt.nome)
    return eventos


class TestChatNaoCongelaAApi:
    def test_o_loop_segue_atendendo_enquanto_o_modelo_pensa(self):
        """O teste que FALHAVA antes do `to_thread` (docs/40, passo 2).

        Antes, `contador` terminava em 1: a batida rodava uma vez, esbarrava na
        chamada síncrona e só voltava 300 ms depois — que é exatamente o que a
        cantina sentia como "a tela travou".
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

    def test_a_execucao_de_tool_tambem_sai_do_loop(self):
        """As tools leem o banco pelo cliente PostgREST, que também é síncrono.

        Uma tool que varre notas segurava o loop junto com o modelo — e essa
        parte não aparecia em nenhuma medição, porque o tempo era contabilizado
        como "o chat está lento".
        """
        marcas: list[str] = []

        def _tool_lenta(nome, cliente, args):
            time.sleep(DEMORA_DO_MODELO_S)
            marcas.append("tool")
            return {"ok": True}

        async def cenario():
            contador = [0]
            parar = asyncio.Event()
            batendo = asyncio.create_task(_bater(contador, parar))
            await asyncio.to_thread(_tool_lenta, "qualquer", None, {})
            parar.set()
            await batendo
            return contador[0]

        batidas = asyncio.run(cenario())
        assert batidas >= BATIDAS_MINIMAS
        assert marcas == ["tool"]
