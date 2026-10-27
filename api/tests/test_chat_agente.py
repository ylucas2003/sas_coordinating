"""O motor do chat: janela do histórico, falha do provedor, streaming de verdade
e tools em paralelo (docs/43 §4.1, defeitos 2 e 4, e §4.2).

Tudo sem rede. O cliente da OpenAI é de mentira, mas os pedaços que ele produz
são `ChatCompletionChunk` de verdade, e as exceções são as classes do SDK
montadas sobre um `httpx.Response` de mentira — o formato que se testa é o que
chega em produção, não um parecido.

O teste que mais importa é o do batimento DURANTE o streaming
(`TestStreamingNaoCongelaOLoop`): ler o stream é bloqueante, e existe UM event
loop no processo (UVICORN_WORKERS=1). Se ele quebrar, a pergunta é a mesma de
test_desempenho_event_loop.py: quem voltou a fazer coisa síncrona no loop?
"""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import threading
import time
from collections.abc import Callable
from typing import Any

import httpx
import openai
import pytest
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.chat import agente, falha_do_provedor, perfis
from app.chat.ferramentas import Ferramenta, Registro, Sessao

_REQUISICAO = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")

#: Quanto uma tool "lenta" demora, de mentira. Em série, duas somariam o dobro.
DEMORA_DA_TOOL_S = 0.30
INTERVALO_DA_BATIDA_S = 0.005
#: Com o loop livre cabem ~70 batidas nos 350 ms de stream do teste. Exigimos
#: 10, como em test_desempenho_event_loop.py: folga para máquina lenta, e
#: impossível de alcançar com a leitura bloqueando o loop (aí dá 0 ou 1).
BATIDAS_MINIMAS = 10


# ─── O modelo de mentira ─────────────────────────────────────────────────


def _pedaco(delta: dict | None = None, *, uso: tuple[int, int] | None = None) -> ChatCompletionChunk:
    """Um pedaço de `stream=True` como o SDK entrega. Sem `delta`, é o último:
    `choices` vazio e só o uso, como chega com `include_usage`."""
    return ChatCompletionChunk.model_validate({
        "id": "teste",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "modelo-de-teste",
        "choices": [] if delta is None else [{"index": 0, "delta": delta, "finish_reason": None}],
        "usage": None if uso is None else {
            "prompt_tokens": uso[0], "completion_tokens": uso[1], "total_tokens": sum(uso),
        },
    })


def _texto(texto: str) -> ChatCompletionChunk:
    return _pedaco({"content": texto})


def _tool(
    index: int, *, id: str | None = None, nome: str | None = None, argumentos: str | None = None
) -> ChatCompletionChunk:
    """Um fragmento de tool_call: `id` e nome só no primeiro de cada `index`,
    os argumentos em pedaços de JSON — é assim que a OpenAI manda."""
    parcial: dict[str, Any] = {"index": index}
    if id is not None:
        parcial["id"] = id
        parcial["type"] = "function"
    funcao = {
        chave: valor
        for chave, valor in (("name", nome), ("arguments", argumentos))
        if valor is not None
    }
    if funcao:
        parcial["function"] = funcao
    return _pedaco({"tool_calls": [parcial]})


def _uso(entrada: int, saida: int) -> ChatCompletionChunk:
    return _pedaco(uso=(entrada, saida))


def _pede_tools(*chamadas: tuple[str, str, str]) -> list[ChatCompletionChunk]:
    """Uma resposta que só pede tools: (id, nome, argumentos), um pedaço cada."""
    return [
        _tool(i, id=id_, nome=nome, argumentos=argumentos)
        for i, (id_, nome, argumentos) in enumerate(chamadas)
    ]


def _completa(
    texto: str | None = None,
    *,
    tools: list[tuple[str, str, str]] | None = None,
    uso: tuple[int, int] = (0, 0),
) -> ChatCompletion:
    """A resposta inteira, de `stream=False`."""
    return ChatCompletion.model_validate({
        "id": "teste",
        "object": "chat.completion",
        "created": 0,
        "model": "modelo-de-teste",
        "choices": [{
            "index": 0,
            "finish_reason": "tool_calls" if tools else "stop",
            "message": {
                "role": "assistant",
                "content": texto,
                "tool_calls": [
                    {"id": i, "type": "function", "function": {"name": n, "arguments": a}}
                    for i, n, a in tools
                ] if tools else None,
            },
        }],
        "usage": {"prompt_tokens": uso[0], "completion_tokens": uso[1], "total_tokens": sum(uso)},
    })


class _StreamFalso:
    """O `Stream` do SDK, de mentira: itera os pedaços e sabe fechar.

    `demora_s` dorme com `time.sleep` antes de CADA pedaço — bloqueante de
    verdade, como esperar o próximo pedaço chegar pelo socket. `erro` levanta
    depois do último, como uma falha no meio da resposta.
    """

    def __init__(
        self, pedacos: list, *, demora_s: float = 0.0, erro: BaseException | None = None
    ) -> None:
        self._pedacos = list(pedacos)
        self._demora_s = demora_s
        self._erro = erro
        self.entregues = 0
        self.ultimo_pedaco_em: float | None = None
        self.fechado = threading.Event()

    def __iter__(self):
        for pedaco in self._pedacos:
            if self.fechado.is_set():
                return
            if self._demora_s:
                time.sleep(self._demora_s)
            self.entregues += 1
            self.ultimo_pedaco_em = time.perf_counter()
            yield pedaco
        if self._erro is not None:
            raise self._erro

    def close(self) -> None:
        self.fechado.set()


class _ModeloFalso:
    """Faz as vezes da classe `OpenAI` e do cliente que ela devolve.

    Cada `create()` consome o próximo roteiro: lista de pedaços (vira stream),
    um `_StreamFalso` pronto, uma `ChatCompletion` (para `stream=False`) ou
    uma exceção, que é levantada.
    """

    def __init__(self, *roteiros: Any) -> None:
        self._roteiros = list(roteiros)
        self.chamadas: list[dict[str, Any]] = []
        self.chat = type("Chat", (), {"completions": self})()

    def __call__(self, **_kwargs: Any) -> _ModeloFalso:
        return self

    def create(self, **kwargs: Any) -> Any:
        self.chamadas.append(kwargs)
        roteiro = self._roteiros.pop(0)
        if isinstance(roteiro, BaseException):
            raise roteiro
        if kwargs.get("stream"):
            return roteiro if isinstance(roteiro, _StreamFalso) else _StreamFalso(roteiro)
        assert isinstance(roteiro, ChatCompletion), "stream=False pede uma ChatCompletion"
        return roteiro


class _ClienteFalso:
    """Um cliente PostgREST de mentira: só identidade e se foi fechado."""

    def __init__(self, nome: str) -> None:
        self.nome = nome
        self.fechado = False

    def aclose(self) -> None:  # o nome do SyncPostgrestClient, síncrono
        self.fechado = True

    def __repr__(self) -> str:
        return f"<cliente {self.nome}>"


class _Fabrica:
    """`fabrica_de_cliente` de mentira: conta e guarda o que criou."""

    def __init__(self, *, falha: BaseException | None = None) -> None:
        self.criados: list[_ClienteFalso] = []
        self._falha = falha
        self._trava = threading.Lock()

    def __call__(self) -> _ClienteFalso:
        if self._falha is not None:
            raise self._falha
        with self._trava:
            cliente = _ClienteFalso(f"proprio-{len(self.criados) + 1}")
            self.criados.append(cliente)
        return cliente


def _ferramenta(
    nome: str, handler: Callable[..., Any], propriedades: dict | None = None, **extra: Any
) -> Ferramenta:
    return Ferramenta(
        nome=nome,
        descricao=f"Tool de teste {nome}.",
        parametros={"type": "object", "properties": propriedades or {}},
        escopo="coordenacao",
        handler=handler,
        **extra,
    )


def _perfil(*ferramentas: Ferramenta) -> agente.PerfilAgente:
    return agente.PerfilAgente(
        sessao=Sessao(tipo="coordenador", usuario="coord:teste"),
        system_message={"role": "system", "content": "teste"},
        modelo="modelo-de-teste",
        registro=Registro(list(ferramentas)),
    )


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    # Explícitos, para um `.env` local não decidir o caminho do teste.
    monkeypatch.setenv("CHAT_STREAMING", "true")
    monkeypatch.setenv("CHAT_TOOLS_EM_PARALELO", "true")
    monkeypatch.setattr(agente, "_SDK_DISPONIVEL", True)
    yield
    get_settings.cache_clear()


def _configurar(monkeypatch, **valores: str) -> None:
    from app.config import get_settings

    for chave, valor in valores.items():
        monkeypatch.setenv(chave, valor)
    get_settings.cache_clear()


@pytest.fixture
def modelo(monkeypatch) -> Callable[..., _ModeloFalso]:
    def instalar(*roteiros: Any) -> _ModeloFalso:
        falso = _ModeloFalso(*roteiros)
        monkeypatch.setattr(agente, "OpenAI", falso)
        return falso

    return instalar


def _gerar(perfil=None, *, historico=None, cliente_db=None, fabrica=None):
    return agente.gerar_resposta(
        cliente_db if cliente_db is not None else _ClienteFalso("compartilhado"),
        thread_id="T1",
        historico=historico or [],
        nova_msg_user="oi",
        perfil=perfil or _perfil(),
        fabrica_de_cliente=fabrica,
    )


def _rodar(perfil=None, **kwargs) -> list[tuple[str, float, dict]]:
    """(nome, instante, dados) de cada evento, na ordem em que saíram."""

    async def consumir():
        return [(e.nome, time.perf_counter(), e.dados) async for e in _gerar(perfil, **kwargs)]

    return asyncio.run(consumir())


def _dados(eventos: list[tuple[str, float, dict]], nome: str) -> list[dict]:
    return [dados for n, _, dados in eventos if n == nome]


def _tokens(eventos) -> list[str]:
    return [d["texto"] for d in _dados(eventos, "token")]


def _fim(eventos) -> dict:
    (fim,) = _dados(eventos, "end")
    return fim


def _sse(eventos) -> str:
    """O que o front recebe: o texto inteiro do SSE."""
    return "".join(agente.Evento(n, d).formatar_sse() for n, _, d in eventos)


# ─── Janela do histórico (defeito 2) ─────────────────────────────────────


def _resposta_com_tools(pergunta: str, ids: list[str], final: str) -> list[dict]:
    """Uma resposta como `rotas.py` a persiste e `_carregar_historico_openai` a
    devolve: a pergunta, UM assistant com todos os tool_calls da resposta, uma
    `tool` por chamada e o texto final."""
    return [
        {"role": "user", "content": pergunta},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": i, "type": "function", "function": {"name": "minhas_notas", "arguments": "{}"}}
                for i in ids
            ],
        },
        *({"role": "tool", "tool_call_id": i, "name": "minhas_notas", "content": "{}"} for i in ids),
        {"role": "assistant", "content": final},
    ]


def _resposta_simples(pergunta: str, final: str) -> list[dict]:
    return [{"role": "user", "content": pergunta}, {"role": "assistant", "content": final}]


def _conferir_formato_da_api(mensagens: list[dict]) -> None:
    """As duas regras da API que o fatiamento puro quebrava: toda `tool` vem
    logo depois do assistant que a pediu (ou de outra `tool` dele), e todo
    assistant com `tool_calls` tem as respostas todas logo em seguida."""
    pendentes: set[str] = set()
    for posicao, msg in enumerate(mensagens):
        if msg.get("role") == "tool":
            assert msg.get("tool_call_id") in pendentes, f"tool órfã na posição {posicao}: {msg}"
            pendentes.discard(msg["tool_call_id"])
            continue
        assert not pendentes, f"tool_calls sem resposta {pendentes} antes da posição {posicao}"
        if msg.get("role") == "assistant" and "tool_calls" in msg:
            assert msg["tool_calls"], f"tool_calls vazio na posição {posicao}"
            pendentes = {tc["id"] for tc in msg["tool_calls"]}
    assert not pendentes, f"o recorte acaba com tool_calls sem resposta: {pendentes}"


def _thread_longa() -> list[dict]:
    return [
        *_resposta_simples("oi", "olá!"),
        *_resposta_com_tools("minhas notas?", ["a1", "a2", "a3"], "média 7,2"),
        *_resposta_simples("e matemática?", "6,8"),
        {"role": "user", "content": "e o simulado?"},
        {"role": "assistant", "content": "⚠️ Erro: Tive um problema para gerar a resposta."},
        *_resposta_com_tools("e física?", ["b1"], "8,0"),
        *_resposta_com_tools("compara as duas", ["c1", "c2"], "física está à frente"),
    ]


class TestJanelaDoHistorico:
    def test_thread_curta_passa_inteira(self):
        historico = _thread_longa()
        assert agente.janela_do_historico(historico, 100) == historico

    def test_janela_que_abriria_numa_tool_orfa_comeca_na_pergunta_seguinte(self):
        historico = [
            *_resposta_com_tools("notas?", ["a", "b"], "7,5"),
            *_resposta_simples("e agora?", "tudo certo"),
        ]
        # A borda do defeito: as últimas 4 começam na `tool` "b", cujo pedido
        # ficou de fora. Era exatamente isto que ia para a OpenAI.
        assert historico[-4]["role"] == "tool"
        assert agente.janela_do_historico(historico, 4) == historico[-2:]

    def test_janela_que_abre_no_meio_de_uma_resposta_descarta_ate_a_pergunta(self):
        historico = [*_resposta_simples("a", "b"), *_resposta_simples("c", "d")]
        assert agente.janela_do_historico(historico, 3) == historico[-2:]

    def test_persistencia_parcial_tira_o_grupo_inteiro(self):
        # `rotas.py` grava uma linha por vez: se o processo morre entre as
        # duas `tool`, sobra um pedido de duas chamadas com uma resposta só.
        grupo = _resposta_com_tools("notas?", ["a", "b"], "7,5")
        incompleto = [m for m in grupo if m.get("tool_call_id") != "b"]
        historico = [*incompleto, *_resposta_simples("e agora?", "ok")]
        recorte = agente.janela_do_historico(historico, 30)
        assert recorte == [
            {"role": "user", "content": "notas?"},
            {"role": "assistant", "content": "7,5"},
            *_resposta_simples("e agora?", "ok"),
        ]
        _conferir_formato_da_api(recorte)

    def test_pedido_sem_nenhuma_resposta_no_fim_sai(self):
        historico = _resposta_com_tools("notas?", ["a"], "x")[:2]
        assert agente.janela_do_historico(historico, 30) == [historico[0]]

    def test_tool_que_nao_responde_ao_pedido_anterior_sai(self):
        grupo = _resposta_com_tools("notas?", ["a"], "7,5")
        intrusa = {"role": "tool", "tool_call_id": "zzz", "name": "x", "content": "{}"}
        sem_id = {"role": "tool", "tool_call_id": None, "name": "x", "content": "{}"}
        historico = [*grupo[:3], intrusa, sem_id, grupo[3]]
        assert agente.janela_do_historico(historico, 30) == grupo

    def test_resposta_sem_id_nao_fecha_o_pedido(self):
        historico = [
            {"role": "user", "content": "notas?"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "a", "type": "function"}]},
            {"role": "tool", "tool_call_id": None, "name": "x", "content": "{}"},
            {"role": "assistant", "content": "7,5"},
        ]
        assert agente.janela_do_historico(historico, 30) == [historico[0], historico[3]]

    def test_tool_calls_vazio_vira_assistant_comum(self):
        historico = [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "olá", "tool_calls": []},
        ]
        assert agente.janela_do_historico(historico, 30) == [
            {"role": "user", "content": "oi"},
            {"role": "assistant", "content": "olá"},
        ]

    def test_janela_sem_nenhuma_pergunta_fica_vazia(self):
        historico = _resposta_com_tools("notas?", ["a", "b", "c"], "7,5")
        # As últimas 4 são as três `tool` e o final: nenhuma pergunta.
        assert agente.janela_do_historico(historico, 4) == []

    @pytest.mark.parametrize("limite", [0, -1])
    def test_limite_nao_positivo_nao_vira_historico_inteiro(self, limite):
        # `historico[-0:]` é a lista INTEIRA: o zero tem que ser tratado à parte.
        assert agente.janela_do_historico(_thread_longa(), limite) == []

    def test_historico_vazio(self):
        assert agente.janela_do_historico([], 30) == []

    def test_nao_altera_o_historico_recebido(self):
        historico = _thread_longa()
        antes = copy.deepcopy(historico)
        agente.janela_do_historico(historico, 5)
        assert historico == antes

    def test_toda_janela_de_uma_thread_longa_e_aceita_pela_api(self):
        """As bordas todas de uma vez: de 1 até além do tamanho da thread."""
        historico = _thread_longa()
        for limite in range(1, len(historico) + 2):
            recorte = agente.janela_do_historico(historico, limite)
            _conferir_formato_da_api(recorte)
            if recorte:
                assert recorte[0]["role"] == "user", limite
            # Só recorta: nada inventado, nada fora de ordem, nada de fora da janela.
            cauda = historico[-limite:]
            posicoes = [next(i for i, m in enumerate(cauda) if m is r) for r in recorte]
            assert posicoes == sorted(posicoes), limite

    def test_o_agente_manda_ao_modelo_a_janela_recortada(self, modelo):
        # 11 mensagens de uma resposta com oito tools + 24 de conversa = 35: a
        # fatia de 30 abriria no meio das `tool`, com o pedido de fora.
        grupo = _resposta_com_tools("primeira", [f"x{i}" for i in range(8)], "ok")
        conversa = [m for i in range(12) for m in _resposta_simples(f"p{i}", f"r{i}")]
        historico = [*grupo, *conversa]
        assert historico[-agente.MAX_MENSAGENS_HISTORICO]["role"] == "tool"
        falso = modelo([_texto("ok")])
        _rodar(historico=historico)
        enviadas = falso.chamadas[0]["messages"]
        assert enviadas[0] == {"role": "system", "content": "teste"}
        assert enviadas[1]["role"] == "user"
        assert enviadas[-1] == {"role": "user", "content": "oi"}
        _conferir_formato_da_api(enviadas)


# ─── Falha do provedor (defeito 4) ───────────────────────────────────────

_TEXTO_CRU = "You exceeded your current quota, please check your plan and billing details."

#: O que não pode aparecer no texto de quem usa: fornecedor, cobrança, jargão.
_PROIBIDO_NA_TELA = re.compile(
    r"openai|gpt|quota|cota|saldo|billing|cr[eé]dit|token|\bapi\b|http|error|exception|traceback",
    re.IGNORECASE,
)


def _erro_do_sdk(
    classe: type, status: int, *, code: str | None = None, tipo: str | None = None,
    param: str | None = None,
):
    corpo = {"message": _TEXTO_CRU, "type": tipo, "param": param, "code": code}
    resposta = httpx.Response(status, request=_REQUISICAO, json={"error": corpo})
    return classe(f"Error code: {status} - {corpo}", response=resposta, body=corpo)


class _ErroDeOutroSdk(Exception):
    """Só `status_code`, `code` e `param`, sem ser classe do SDK: a
    classificação de reserva."""

    def __init__(
        self, *, status_code: int | None = None, code: str | None = None, param: str | None = None
    ) -> None:
        super().__init__(_TEXTO_CRU)
        self.status_code = status_code
        self.code = code
        self.param = param


_CASOS = [
    pytest.param(
        _erro_do_sdk(openai.RateLimitError, 429, code="insufficient_quota", tipo="insufficient_quota"),
        "saldo", id="cota-esgotada-chega-como-429",
    ),
    pytest.param(
        _erro_do_sdk(openai.RateLimitError, 429, code="rate_limit_exceeded", tipo="requests"),
        "limite", id="limite-comum",
    ),
    pytest.param(_erro_do_sdk(openai.RateLimitError, 429), "limite", id="limite-sem-code"),
    pytest.param(
        _erro_do_sdk(openai.AuthenticationError, 401, code="invalid_api_key"),
        "credencial", id="chave-invalida",
    ),
    pytest.param(_erro_do_sdk(openai.PermissionDeniedError, 403), "credencial", id="permissao"),
    pytest.param(_erro_do_sdk(openai.InternalServerError, 500), "sobrecarga", id="500"),
    pytest.param(_erro_do_sdk(openai.InternalServerError, 503), "sobrecarga", id="503"),
    pytest.param(_erro_do_sdk(openai.InternalServerError, 529), "sobrecarga", id="529"),
    pytest.param(
        _erro_do_sdk(openai.BadRequestError, 400, code="context_length_exceeded"),
        "conversa_longa", id="conversa-longa",
    ),
    pytest.param(
        _erro_do_sdk(openai.BadRequestError, 400, code="invalid_value"),
        "requisicao", id="requisicao",
    ),
    # Configuração NOSSA, como a credencial: o modelo vem do env e os
    # parâmetros, do código (revisão antecipada do motor, 25/10).
    pytest.param(
        _erro_do_sdk(openai.NotFoundError, 404, code="model_not_found", tipo="invalid_request_error"),
        "configuracao", id="modelo-do-env-que-nao-existe",
    ),
    pytest.param(_erro_do_sdk(openai.NotFoundError, 404), "configuracao", id="404-sem-code"),
    pytest.param(
        _erro_do_sdk(openai.BadRequestError, 400, code="unsupported_parameter", param="max_tokens"),
        "configuracao", id="modelo-de-raciocinio-recusa-max_tokens",
    ),
    pytest.param(
        _erro_do_sdk(openai.BadRequestError, 400, code="unsupported_value", param="temperature"),
        "configuracao", id="modelo-recusa-temperature",
    ),
    pytest.param(
        _erro_do_sdk(openai.BadRequestError, 400, code="invalid_value", param="stream_options"),
        "configuracao", id="parametro-nosso-com-code-generico",
    ),
    pytest.param(
        _erro_do_sdk(openai.BadRequestError, 400, param="tools[3].function.parameters"),
        "configuracao", id="schema-de-tool-recusado",
    ),
    pytest.param(
        # O mesmo 400, apontando para o CONTEÚDO: não é configuração.
        _erro_do_sdk(openai.BadRequestError, 400, code="invalid_value", param="messages[2].content"),
        "requisicao", id="conteudo-da-mensagem",
    ),
    pytest.param(openai.APITimeoutError(request=_REQUISICAO), "prazo", id="prazo"),
    pytest.param(openai.APIConnectionError(request=_REQUISICAO), "rede", id="rede"),
    pytest.param(
        # Erro no MEIO do stream: o SDK monta `APIError` puro, sem status.
        openai.APIError(
            _TEXTO_CRU, _REQUISICAO, body={"message": _TEXTO_CRU, "type": "server_error", "code": None}
        ),
        "sobrecarga", id="meio-do-stream",
    ),
    pytest.param(httpx.ReadTimeout(_TEXTO_CRU, request=_REQUISICAO), "prazo", id="httpx-prazo"),
    pytest.param(
        httpx.RemoteProtocolError(_TEXTO_CRU, request=_REQUISICAO), "rede", id="httpx-queda"
    ),
    pytest.param(ValueError(_TEXTO_CRU), "desconhecida", id="desconhecida"),
    pytest.param(
        _ErroDeOutroSdk(status_code=429, code="insufficient_quota"), "saldo", id="reserva-saldo"
    ),
    pytest.param(_ErroDeOutroSdk(status_code=429), "limite", id="reserva-429"),
    pytest.param(_ErroDeOutroSdk(status_code=401), "credencial", id="reserva-401"),
    pytest.param(_ErroDeOutroSdk(status_code=403), "credencial", id="reserva-403"),
    pytest.param(_ErroDeOutroSdk(status_code=503), "sobrecarga", id="reserva-503"),
    pytest.param(_ErroDeOutroSdk(status_code=529), "sobrecarga", id="reserva-529"),
    pytest.param(_ErroDeOutroSdk(status_code=504), "prazo", id="reserva-504"),
    pytest.param(
        _ErroDeOutroSdk(status_code=400, code="context_length_exceeded"),
        "conversa_longa", id="reserva-conversa-longa",
    ),
    pytest.param(_ErroDeOutroSdk(status_code=400), "requisicao", id="reserva-400"),
    pytest.param(
        _ErroDeOutroSdk(status_code=400, param="temperature"), "configuracao", id="reserva-400-parametro-nosso"
    ),
    pytest.param(_ErroDeOutroSdk(status_code=404), "configuracao", id="reserva-404"),
    pytest.param(
        _ErroDeOutroSdk(status_code=404, code="model_not_found"), "configuracao", id="reserva-model-not-found"
    ),
    pytest.param(
        # Um embrulho que só guardou o `code`, sem status: é ele que decide.
        _ErroDeOutroSdk(code="model_not_found"), "configuracao", id="reserva-so-o-code"
    ),
    pytest.param(
        _ErroDeOutroSdk(code="unsupported_parameter"), "configuracao", id="reserva-so-o-code-do-parametro"
    ),
]


class TestClassificacaoDaFalha:
    @pytest.mark.parametrize(("exc", "tipo"), _CASOS)
    def test_tipo_e_texto_seguro(self, exc, tipo):
        falha = falha_do_provedor.classificar(exc)
        assert falha.tipo == tipo
        assert falha.precisa_acao is (tipo in ("saldo", "credencial", "configuracao"))
        assert falha.mensagem == falha_do_provedor.mensagem_para_quem_usa(tipo)
        assert _TEXTO_CRU not in falha.mensagem
        assert str(exc) not in falha.mensagem

    @pytest.mark.parametrize("tipo", list(falha_do_provedor._MENSAGENS))
    def test_nenhuma_mensagem_fala_de_fornecedor_nem_de_cobranca(self, tipo):
        mensagem = falha_do_provedor.mensagem_para_quem_usa(tipo)
        assert not _PROIBIDO_NA_TELA.search(mensagem), mensagem
        assert len(mensagem) < 200

    def test_conversa_longa_manda_comecar_outra(self):
        assert "nova conversa" in falha_do_provedor.mensagem_para_quem_usa("conversa_longa")

    def test_voltas_esgotadas_tambem_e_texto_de_gente(self):
        assert not _PROIBIDO_NA_TELA.search(agente.MENSAGEM_VOLTAS_ESGOTADAS)
        assert "turnos" not in agente.MENSAGEM_VOLTAS_ESGOTADAS


class TestRegistroDaFalha:
    def test_saldo_pede_acao_em_error_com_o_motivo_real(self, caplog):
        exc = _erro_do_sdk(openai.RateLimitError, 429, code="insufficient_quota")
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falha_do_provedor.registrar(
            falha_do_provedor.classificar(exc), exc, thread_id="T9", modelo="m", usuario="aluno:A1"
        )
        (registro,) = caplog.records
        assert registro.levelno == logging.ERROR
        assert registro.getMessage().startswith("[AÇÃO NECESSÁRIA]")
        assert repr(exc) in registro.getMessage()
        assert "tipo=saldo" in registro.getMessage()
        assert "thread=T9" in registro.getMessage()
        assert "status=429" in registro.getMessage()
        assert "code=insufficient_quota" in registro.getMessage()
        assert registro.usuario == "aluno:A1"

    def test_credencial_tambem_pede_acao(self, caplog):
        exc = _erro_do_sdk(openai.AuthenticationError, 401)
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falha_do_provedor.registrar(falha_do_provedor.classificar(exc), exc)
        (registro,) = caplog.records
        assert registro.levelno == logging.ERROR
        assert "[AÇÃO NECESSÁRIA]" in registro.getMessage()

    def test_modelo_que_nao_existe_pede_acao(self, caplog):
        # Erro de digitação em OPENAI_MODELO_ALUNO: toda mensagem de todo aluno
        # falha. Era WARNING com stack, igual a uma falha qualquer.
        exc = _erro_do_sdk(openai.NotFoundError, 404, code="model_not_found")
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falha_do_provedor.registrar(falha_do_provedor.classificar(exc), exc, modelo="gpt-4o-mni")
        (registro,) = caplog.records
        assert registro.levelno == logging.ERROR
        assert registro.getMessage().startswith("[AÇÃO NECESSÁRIA]")
        for trecho in ("tipo=configuracao", "modelo=gpt-4o-mni", "status=404", "code=model_not_found"):
            assert trecho in registro.getMessage(), trecho

    def test_parametro_recusado_diz_qual(self, caplog):
        exc = _erro_do_sdk(openai.BadRequestError, 400, code="unsupported_parameter", param="max_tokens")
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falha_do_provedor.registrar(falha_do_provedor.classificar(exc), exc)
        (registro,) = caplog.records
        assert registro.levelno == logging.ERROR
        assert "[AÇÃO NECESSÁRIA]" in registro.getMessage()
        assert "param=max_tokens" in registro.getMessage()

    def test_limite_e_aviso_sem_alarme(self, caplog):
        exc = _erro_do_sdk(openai.RateLimitError, 429, code="rate_limit_exceeded")
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falha_do_provedor.registrar(falha_do_provedor.classificar(exc), exc)
        (registro,) = caplog.records
        assert registro.levelno == logging.WARNING
        assert "[AÇÃO NECESSÁRIA]" not in registro.getMessage()
        assert repr(exc) in registro.getMessage()
        assert registro.exc_info is None

    def test_desconhecida_leva_o_stack(self, caplog):
        exc = ValueError("o que foi isso")
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falha_do_provedor.registrar(falha_do_provedor.classificar(exc), exc)
        (registro,) = caplog.records
        assert registro.levelno == logging.WARNING
        assert registro.exc_info is not None


class TestFalhaNoAgente:
    def test_cota_esgotada_vira_texto_amigavel_e_o_cru_some(self, modelo, caplog):
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        modelo(_erro_do_sdk(openai.RateLimitError, 429, code="insufficient_quota"))
        eventos = _rodar()

        assert [n for n, _, _ in eventos] == ["start", "erro", "end"]
        (erro,) = _dados(eventos, "erro")
        assert erro["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("saldo")
        # Nada do texto cru chega ao front — e o que chega é o que `rotas.py`
        # grava em `chat_mensagem` ("⚠️ Erro: {mensagem}").
        sse = _sse(eventos)
        assert _TEXTO_CRU not in sse
        assert "quota" not in sse.lower()
        assert _fim(eventos)["texto_final"] == ""
        # A equipe, por outro lado, recebe o motivo real.
        assert any(
            "[AÇÃO NECESSÁRIA]" in r.getMessage() and _TEXTO_CRU in r.getMessage()
            for r in caplog.records
        )

    def test_falha_no_meio_do_stream(self, modelo):
        meio = openai.APIError(
            _TEXTO_CRU, _REQUISICAO, body={"message": _TEXTO_CRU, "type": "server_error", "code": None}
        )
        modelo(_StreamFalso([_texto("Sua média"), _texto(" no ciclo")], erro=meio))
        eventos = _rodar()

        assert _tokens(eventos) == ["Sua média", " no ciclo"]
        (erro,) = _dados(eventos, "erro")
        assert erro["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("sobrecarga")
        assert _TEXTO_CRU not in _sse(eventos)
        # Texto parcial não é resposta: o que fica salvo é só o erro (rotas.py).
        assert _fim(eventos)["texto_final"] == ""

    def test_falha_depois_de_pedir_tools_nao_roda_as_tools(self, modelo):
        rodou: list[str] = []
        perfil = _perfil(_ferramenta("consultar", lambda cliente: rodou.append("x") or {"ok": 1}))
        modelo(_StreamFalso(
            [_tool(0, id="c1", nome="consultar", argumentos="{}")],
            erro=openai.APIConnectionError(request=_REQUISICAO),
        ))
        eventos = _rodar(perfil)
        assert rodou == []
        assert _dados(eventos, "tool_call_start") == []
        assert _dados(eventos, "erro")[0]["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("rede")

    def test_falha_sem_streaming(self, modelo, monkeypatch):
        _configurar(monkeypatch, CHAT_STREAMING="false")
        modelo(openai.APITimeoutError(request=_REQUISICAO))
        eventos = _rodar()
        assert _dados(eventos, "erro")[0]["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("prazo")
        assert "Request timed out" not in _sse(eventos)

    def test_voltas_esgotadas_viram_texto_amigavel(self, modelo):
        perfil = _perfil(
            _ferramenta("consultar", lambda cliente, n=0: {"n": n}, {"n": {"type": "integer"}})
        )
        falso = modelo(*(
            _pede_tools((f"c{i}", "consultar", f'{{"n": {i}}}')) for i in range(agente.MAX_TURNOS)
        ))
        eventos = _rodar(perfil)

        assert len(falso.chamadas) == agente.MAX_TURNOS
        (erro,) = _dados(eventos, "erro")
        assert erro["mensagem"] == agente.MENSAGEM_VOLTAS_ESGOTADAS
        assert "loop" not in _sse(eventos)

    def test_modelo_do_aluno_errado_no_env_vira_acao_necessaria(self, modelo, monkeypatch, caplog):
        """OPENAI_MODELO_ALUNO com erro de digitação: o aluno lê o mesmo texto
        da credencial recusada, e a equipe, o ERROR com o nome do modelo."""
        _configurar(monkeypatch, OPENAI_MODELO_ALUNO="gpt-4o-mni")
        caplog.set_level(logging.WARNING, logger="sas.chat.provedor")
        falso = modelo(_erro_do_sdk(openai.NotFoundError, 404, code="model_not_found", tipo="invalid_request_error"))
        perfil = perfis.perfil_aluno(Sessao(tipo="aluno", usuario="aluno:A1", aluno_id="A1", nome="Ana"))
        eventos = _rodar(perfil)

        assert falso.chamadas[0]["model"] == "gpt-4o-mni"
        (erro,) = _dados(eventos, "erro")
        assert erro["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("credencial")
        assert _TEXTO_CRU not in _sse(eventos)
        (registro,) = [r for r in caplog.records if r.name == "sas.chat.provedor"]
        assert registro.levelno == logging.ERROR
        assert "[AÇÃO NECESSÁRIA]" in registro.getMessage()
        assert "modelo=gpt-4o-mni" in registro.getMessage()
        assert registro.usuario == "aluno:A1"

    def test_sem_chave_nao_diz_o_nome_da_variavel(self, monkeypatch, caplog):
        _configurar(monkeypatch, OPENAI_API_KEY="")
        caplog.set_level(logging.ERROR, logger="sas.chat.agente")
        eventos = _rodar()
        (erro,) = _dados(eventos, "erro")
        assert erro["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("credencial")
        assert "OPENAI" not in _sse(eventos)
        assert any("[AÇÃO NECESSÁRIA]" in r.getMessage() for r in caplog.records)


# ─── Streaming de verdade (§4.2) ─────────────────────────────────────────


class TestStreaming:
    def test_os_tokens_chegam_em_ordem_e_em_varios_eventos(self, modelo):
        falso = modelo([_texto("Olá"), _texto(", "), _texto("tudo"), _texto(" bem?"), _uso(12, 4)])
        eventos = _rodar()

        assert _tokens(eventos) == ["Olá", ", ", "tudo", " bem?"]
        fim = _fim(eventos)
        assert fim["texto_final"] == "Olá, tudo bem?"
        assert (fim["tokens_in"], fim["tokens_out"]) == (12, 4)
        assert fim["modelo"] == "modelo-de-teste"
        (chamada,) = falso.chamadas
        assert chamada["stream"] is True
        assert chamada["stream_options"] == {"include_usage": True}

    def test_tool_call_montada_de_argumentos_fragmentados(self, modelo):
        vistos: list[str] = []

        def consultar(cliente, aluno_id: str):
            vistos.append(aluno_id)
            return {"aluno": aluno_id, "media": 7.5}

        perfil = _perfil(_ferramenta("consultar", consultar, {"aluno_id": {"type": "string"}}))
        falso = modelo(
            [
                _tool(0, id="c1", nome="consultar", argumentos=""),
                _tool(0, argumentos='{"alu'),
                _tool(0, argumentos='no_id": "A0'),
                _tool(0, argumentos='23"}'),
                _uso(10, 5),
            ],
            [_texto("Sua média é 7,5."), _uso(20, 7)],
        )
        eventos = _rodar(perfil)

        assert vistos == ["A023"]
        (inicio,) = _dados(eventos, "tool_call_start")
        assert inicio == {"tool_call_id": "c1", "nome": "consultar", "args": {"aluno_id": "A023"}}
        # A segunda volta leva o pedido montado e a resposta, no formato da API.
        segunda = falso.chamadas[1]["messages"]
        assert segunda[-2] == {
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": "c1",
                "type": "function",
                "function": {"name": "consultar", "arguments": '{"aluno_id": "A023"}'},
            }],
        }
        assert segunda[-1]["role"] == "tool"
        assert segunda[-1]["tool_call_id"] == "c1"
        fim = _fim(eventos)
        # O uso das duas voltas, somado.
        assert (fim["tokens_in"], fim["tokens_out"]) == (30, 12)
        assert fim["tool_calls"] == [{
            "id": "c1",
            "nome": "consultar",
            "args": {"aluno_id": "A023"},
            "resultado": {"aluno": "A023", "media": 7.5},
        }]
        assert fim["texto_final"] == "Sua média é 7,5."

    def test_dois_tool_calls_intercalados_no_stream(self, modelo):
        perfil = _perfil(
            _ferramenta("notas", lambda cliente, ciclo: {"ciclo": ciclo}, {"ciclo": {"type": "string"}}),
            _ferramenta("faltas", lambda cliente: {"faltas": 0}),
        )
        falso = modelo(
            [
                _tool(0, id="c1", nome="notas", argumentos='{"ci'),
                _tool(1, id="c2", nome="faltas", argumentos="{"),
                _tool(0, argumentos='clo": "C3"}'),
                _tool(1, argumentos="}"),
            ],
            [_texto("pronto")],
        )
        eventos = _rodar(perfil, fabrica=_Fabrica())
        assert _dados(eventos, "tool_call_start") == [
            {"tool_call_id": "c1", "nome": "notas", "args": {"ciclo": "C3"}},
            {"tool_call_id": "c2", "nome": "faltas", "args": {}},
        ]
        argumentos = [tc["function"]["arguments"] for tc in falso.chamadas[1]["messages"][-3]["tool_calls"]]
        assert argumentos == ['{"ciclo": "C3"}', "{}"]

    def test_texto_antes_das_tools_fica_no_texto_final(self, modelo):
        """O que a pessoa viu é o que fica salvo: a frase que o modelo escreveu
        antes de pedir a tool já estava na tela quando o pedido apareceu."""
        perfil = _perfil(_ferramenta("consultar", lambda cliente: {"ok": True}))
        falso = modelo(
            [_texto("Vou olhar."), _tool(0, id="c1", nome="consultar", argumentos="{}")],
            [_texto("Pronto.")],
        )
        eventos = _rodar(perfil)
        assert _tokens(eventos) == ["Vou olhar.", "\n\n", "Pronto."]
        assert _fim(eventos)["texto_final"] == "".join(_tokens(eventos))
        assert falso.chamadas[1]["messages"][-2]["content"] == "Vou olhar."

    def test_sem_streaming_o_caminho_antigo_continua(self, modelo, monkeypatch):
        _configurar(monkeypatch, CHAT_STREAMING="false")
        texto = "a" * 100
        falso = modelo(_completa(texto, uso=(9, 3)))
        eventos = _rodar()
        assert falso.chamadas[0]["stream"] is False
        assert "stream_options" not in falso.chamadas[0]
        assert _tokens(eventos) == ["a" * 40, "a" * 40, "a" * 20]
        fim = _fim(eventos)
        assert fim["texto_final"] == texto
        assert (fim["tokens_in"], fim["tokens_out"]) == (9, 3)

    def test_sem_streaming_com_tools(self, modelo, monkeypatch):
        _configurar(monkeypatch, CHAT_STREAMING="false")
        perfil = _perfil(_ferramenta("consultar", lambda cliente, x: {"x": x}, {"x": {"type": "string"}}))
        modelo(
            _completa(tools=[("c1", "consultar", '{"x": "1"}')], uso=(5, 1)),
            _completa("feito", uso=(6, 2)),
        )
        eventos = _rodar(perfil)
        assert [n for n, _, _ in eventos] == [
            "start", "tool_call_start", "tool_call_end", "token", "end",
        ]
        fim = _fim(eventos)
        assert fim["tool_calls"][0]["resultado"] == {"x": "1"}
        assert (fim["tokens_in"], fim["tokens_out"]) == (11, 3)

    @pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
    def test_thread_que_morre_sem_desfecho_nao_deixa_a_resposta_pendurada(self, modelo):
        """Quem lê a fila espera um desfecho: se a thread morresse por algo que
        não é `Exception`, sem a reserva a resposta ficaria esperando para
        sempre — e o nginx só a cortaria em 300 s."""

        class _Morte(BaseException):
            pass

        modelo(_Morte())
        eventos = _rodar()
        (erro,) = _dados(eventos, "erro")
        assert erro["mensagem"] == falha_do_provedor.mensagem_para_quem_usa("desconhecida")

    def test_fechar_o_gerador_para_a_leitura_e_fecha_o_stream(self, modelo):
        """O cliente desconectou no meio da resposta: a thread não pode seguir
        lendo o modelo para ninguém."""
        stream = _StreamFalso([_texto(f"{i} ") for i in range(50)], demora_s=0.02)
        modelo(stream)

        async def cenario():
            gerador = _gerar()
            async for evento in gerador:
                if evento.nome == "token":
                    break
            await gerador.aclose()

        asyncio.run(cenario())
        assert stream.fechado.wait(2.0), "o stream não foi fechado"
        time.sleep(0.1)
        assert stream.entregues < 50, "a thread seguiu lendo depois do fechamento"

    def test_parar_so_sinaliza_e_quem_fecha_e_a_thread_que_le(self):
        """`parar` roda no loop e NÃO toca o stream: o httpx não garante fechar
        de uma thread a resposta que outra ainda está lendo, e no Linux isso nem
        acorda o recv() bloqueado (revisão antecipada do motor, 25/10). Quem
        fecha é a própria thread do stream, no próximo pedaço que chegar — e
        esse pedaço não é entregue a ninguém."""
        libera = threading.Event()
        fechado_por: list[str] = []

        class _StreamQueEspera:
            def __iter__(self):
                yield _texto("um")
                libera.wait(2)  # o modelo ainda gerando o próximo pedaço
                yield _texto("dois")
                yield _texto("três")

            def close(self) -> None:
                fechado_por.append(threading.current_thread().name)

        async def cenario():
            leitor = agente._LeitorDoStream(_StreamQueEspera)
            primeiro = await leitor.proximo()
            leitor.parar()
            await asyncio.sleep(0.1)
            antes_do_pedaco = list(fechado_por)
            libera.set()
            for _ in range(200):
                if fechado_por:
                    break
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.05)
            return primeiro, antes_do_pedaco, leitor._fila.qsize()

        primeiro, antes_do_pedaco, na_fila = asyncio.run(cenario())
        assert primeiro.choices[0].delta.content == "um"
        assert antes_do_pedaco == [], "parar() fechou o stream de outra thread"
        assert fechado_por == ["sas-chat-stream"], fechado_por
        assert na_fila == 0, "a thread entregou pedaço depois de parar"

    def test_parar_enquanto_o_stream_abre_fecha_o_que_abriu(self):
        """Parou antes de `create()` voltar: o stream que nasce depois é fechado
        pela própria thread, sem um pedaço lido."""
        abrindo = threading.Event()
        pode_abrir = threading.Event()
        stream = _StreamFalso([_texto("nunca lido")])

        def abrir() -> _StreamFalso:
            abrindo.set()
            pode_abrir.wait(2)
            return stream

        async def cenario():
            leitor = agente._LeitorDoStream(abrir)
            await asyncio.to_thread(abrindo.wait, 2)
            leitor.parar()
            pode_abrir.set()
            fechou = await asyncio.to_thread(stream.fechado.wait, 2)
            return fechou, leitor._fila.qsize()

        fechou, na_fila = asyncio.run(cenario())
        assert fechou, "o stream aberto depois de parar ficou aberto"
        assert stream.entregues == 0
        assert na_fila == 0


class TestStreamingNaoCongelaOLoop:
    def test_o_loop_bate_enquanto_os_pedacos_chegam(self, modelo):
        """Ler o stream é bloqueante PEDAÇO A PEDAÇO: cada `next()` espera o
        socket. Iterado dentro do loop, o loop parava a cada espera — e a
        resposta inteira de um coordenador congelava o balcão da cantina."""
        palavras = ["um ", "dois ", "três ", "quatro ", "cinco ", "seis"]
        stream = _StreamFalso([*(_texto(p) for p in palavras), _uso(5, 6)], demora_s=0.05)
        modelo(stream)

        async def bater(contador: list[int], parar: asyncio.Event) -> None:
            while not parar.is_set():
                contador[0] += 1
                await asyncio.sleep(INTERVALO_DA_BATIDA_S)

        async def cenario():
            contador = [0]
            parar = asyncio.Event()
            batendo = asyncio.create_task(bater(contador, parar))
            eventos = [(e.nome, time.perf_counter(), e.dados) async for e in _gerar()]
            parar.set()
            await batendo
            return contador[0], eventos

        batidas, eventos = asyncio.run(cenario())
        assert batidas >= BATIDAS_MINIMAS, (
            f"só {batidas} batidas durante o stream — a leitura voltou a "
            "acontecer dentro do event loop"
        )
        assert _tokens(eventos) == palavras
        # Streaming de verdade: o primeiro token sai antes de o último pedaço
        # existir. Com o texto montado e picado no fim, sairia depois.
        primeiro_token = next(t for n, t, _ in eventos if n == "token")
        assert stream.ultimo_pedaco_em is not None
        assert primeiro_token < stream.ultimo_pedaco_em


# ─── Tools em paralelo (§4.2) ────────────────────────────────────────────


class TestToolsEmParalelo:
    def test_duas_tools_lentas_levam_o_tempo_de_uma_com_clientes_proprios(self, modelo):
        # A barreira prova a sobreposição sem depender de relógio: em série, a
        # primeira tool esperaria a segunda até o timeout e quebraria.
        barreira = threading.Barrier(2, timeout=5)
        recebidos: dict[str, Any] = {}

        def lenta(nome: str):
            def handler(cliente):
                barreira.wait()
                time.sleep(DEMORA_DA_TOOL_S)
                recebidos[nome] = cliente
                return {"tool": nome}

            return handler

        perfil = _perfil(_ferramenta("a", lenta("a")), _ferramenta("b", lenta("b")))
        modelo(_pede_tools(("c1", "a", "{}"), ("c2", "b", "{}")), [_texto("pronto")])
        fabrica = _Fabrica()
        compartilhado = _ClienteFalso("compartilhado")
        eventos = _rodar(perfil, fabrica=fabrica, cliente_db=compartilhado)

        inicios = [t for n, t, _ in eventos if n == "tool_call_start"]
        fins = [t for n, t, _ in eventos if n == "tool_call_end"]
        assert len(inicios) == len(fins) == 2
        duracao = max(fins) - min(inicios)
        assert duracao < 2 * DEMORA_DA_TOOL_S * 0.85, f"{duracao:.3f}s: parece série"
        assert [d["resultado"] for d in _fim(eventos)["tool_calls"]] == [{"tool": "a"}, {"tool": "b"}]

        # Cada tool com o PRÓPRIO cliente, e nenhuma com o compartilhado
        # (HTTP/2 multiplexado: um GOAWAY derrubaria as duas).
        assert len(fabrica.criados) == 2
        assert {id(recebidos["a"]), id(recebidos["b"])} == {id(c) for c in fabrica.criados}
        assert compartilhado not in recebidos.values()
        assert all(c.fechado for c in fabrica.criados), "o cliente extra não foi fechado"
        assert compartilhado.fechado is False

    def test_ordem_das_mensagens_tool_e_a_pedida_nao_a_de_chegada(self, modelo):
        def lenta(cliente):
            time.sleep(0.2)
            return {"tool": "lenta"}

        perfil = _perfil(
            _ferramenta("lenta", lenta), _ferramenta("rapida", lambda cliente: {"tool": "rapida"})
        )
        falso = modelo(_pede_tools(("c1", "lenta", "{}"), ("c2", "rapida", "{}")), [_texto("ok")])
        eventos = _rodar(perfil, fabrica=_Fabrica())

        assert [d["tool_call_id"] for d in _dados(eventos, "tool_call_start")] == ["c1", "c2"]
        # Cada `tool_call_end` sai quando AQUELA tool termina...
        assert [d["tool_call_id"] for d in _dados(eventos, "tool_call_end")] == ["c2", "c1"]
        # ...mas o histórico e o `end` seguem a ordem do pedido.
        segunda = falso.chamadas[1]["messages"]
        assert [m["tool_call_id"] for m in segunda if m["role"] == "tool"] == ["c1", "c2"]
        assert [tc["id"] for tc in _fim(eventos)["tool_calls"]] == ["c1", "c2"]

    def test_desligado_roda_em_serie_com_o_cliente_do_request(self, modelo, monkeypatch):
        _configurar(monkeypatch, CHAT_TOOLS_EM_PARALELO="false")
        recebidos: list[Any] = []

        def anotar(cliente):
            recebidos.append(cliente)
            return {"ok": True}

        perfil = _perfil(_ferramenta("a", anotar), _ferramenta("b", anotar))
        modelo(_pede_tools(("c1", "a", "{}"), ("c2", "b", "{}")), [_texto("ok")])
        fabrica = _Fabrica()
        compartilhado = _ClienteFalso("compartilhado")
        eventos = _rodar(perfil, fabrica=fabrica, cliente_db=compartilhado)

        assert [n for n, _, _ in eventos if n.startswith("tool_call")] == [
            "tool_call_start", "tool_call_end", "tool_call_start", "tool_call_end",
        ]
        assert fabrica.criados == []
        assert recebidos == [compartilhado, compartilhado]

    def test_uma_tool_so_usa_o_cliente_do_request(self, modelo):
        recebidos: list[Any] = []
        perfil = _perfil(_ferramenta("a", lambda cliente: recebidos.append(cliente) or {"ok": 1}))
        modelo(_pede_tools(("c1", "a", "{}")), [_texto("ok")])
        fabrica = _Fabrica()
        compartilhado = _ClienteFalso("compartilhado")
        _rodar(perfil, fabrica=fabrica, cliente_db=compartilhado)
        assert fabrica.criados == []
        assert recebidos == [compartilhado]

    def test_a_fabrica_padrao_e_criar_cliente_supabase(self, modelo, monkeypatch):
        fabrica = _Fabrica()
        monkeypatch.setattr(agente, "criar_cliente_supabase", fabrica)
        perfil = _perfil(_ferramenta("a", lambda cliente: {"ok": 1}), _ferramenta("b", lambda cliente: {"ok": 2}))
        modelo(_pede_tools(("c1", "a", "{}"), ("c2", "b", "{}")), [_texto("ok")])
        _rodar(perfil)  # sem `fabrica`
        assert len(fabrica.criados) == 2

    def test_teto_de_tools_simultaneas(self, modelo, monkeypatch):
        monkeypatch.setattr(agente, "MAX_TOOLS_SIMULTANEAS", 2)
        trava = threading.Lock()
        agora = [0]
        pico = [0]

        def contar(cliente, n: int):
            with trava:
                agora[0] += 1
                pico[0] = max(pico[0], agora[0])
            time.sleep(0.05)
            with trava:
                agora[0] -= 1
            return {"n": n}

        perfil = _perfil(_ferramenta("contar", contar, {"n": {"type": "integer"}}))
        modelo(
            _pede_tools(*((f"c{i}", "contar", f'{{"n": {i}}}') for i in range(5))),
            [_texto("ok")],
        )
        eventos = _rodar(perfil, fabrica=_Fabrica())
        assert pico[0] == 2
        assert [tc["resultado"] for tc in _fim(eventos)["tool_calls"]] == [{"n": i} for i in range(5)]

    @staticmethod
    def _contador_de_threads(demora_s: float) -> tuple[Callable[..., dict], list[int]]:
        """Uma tool que mede quantas THREADS dela rodam ao mesmo tempo."""
        trava = threading.Lock()
        agora = [0]
        pico = [0]

        def lenta(cliente, n: int):
            with trava:
                agora[0] += 1
                pico[0] = max(pico[0], agora[0])
            time.sleep(demora_s)
            with trava:
                agora[0] -= 1
            return {"n": n}

        return lenta, pico

    def test_o_teto_conta_a_thread_que_o_prazo_abandonou(self, modelo, monkeypatch):
        """A tool que estoura o prazo devolve o erro ao modelo, mas a thread
        dela segue rodando — e a vaga só volta quando ela termina. Contando a
        TAREFA, com teto 1 e quatro tools assim eram quatro threads ao mesmo
        tempo (revisão antecipada do motor, 25/10)."""
        monkeypatch.setattr(agente, "MAX_TOOLS_SIMULTANEAS", 1)
        lenta, pico = self._contador_de_threads(0.2)
        perfil = _perfil(_ferramenta("lenta", lenta, {"n": {"type": "integer"}}, prazo_s=0.05))
        modelo(
            _pede_tools(*((f"c{i}", "lenta", f'{{"n": {i}}}') for i in range(3))),
            [_texto("ok")],
        )
        eventos = _rodar(perfil, fabrica=_Fabrica())
        assert pico[0] == 1, f"{pico[0]} threads de tool ao mesmo tempo com teto 1"
        assert all("passou de" in tc["resultado"]["erro"] for tc in _fim(eventos)["tool_calls"])

    def test_a_vaga_presa_vale_tambem_na_volta_seguinte(self, modelo, monkeypatch):
        """As vagas são da RESPOSTA: as threads que o prazo abandonou numa volta
        ainda ocupam o executor quando o modelo pede as tools da seguinte."""
        monkeypatch.setattr(agente, "MAX_TOOLS_SIMULTANEAS", 2)
        lenta, pico = self._contador_de_threads(0.2)
        perfil = _perfil(_ferramenta("lenta", lenta, {"n": {"type": "integer"}}, prazo_s=0.05))
        modelo(
            _pede_tools(("a1", "lenta", '{"n": 1}'), ("a2", "lenta", '{"n": 2}')),
            _pede_tools(("b1", "lenta", '{"n": 3}'), ("b2", "lenta", '{"n": 4}')),
            [_texto("ok")],
        )
        eventos = _rodar(perfil, fabrica=_Fabrica())
        assert pico[0] == 2, f"{pico[0]} threads de tool ao mesmo tempo com teto 2"
        assert len(_fim(eventos)["tool_calls"]) == 4

    def test_o_cliente_extra_fecha_em_todo_desfecho_de_thread_terminada(self, modelo):
        """Só não fecha no prazo, quando a thread ainda pode estar lendo por
        ele. Antes, só o sucesso fechava: erro de domínio, argumento inválido,
        tool inexistente e falha interna deixavam o cliente HTTP/2 aberto até o
        coletor (revisão antecipada do motor, 25/10)."""

        def quebra(cliente):
            raise RuntimeError("http://postgrest:3000/nota?select=* senha=segredo")

        perfil = _perfil(
            _ferramenta("consultar", lambda cliente, n: {"n": n}, {"n": {"type": "integer"}}),
            _ferramenta("dominio", lambda cliente: {"erro": "este simulado não tem detalhe por questão"}),
            _ferramenta("quebra", quebra),
        )
        modelo(
            _pede_tools(
                ("c1", "consultar", '{"n": 1}'),
                ("c2", "dominio", "{}"),
                ("c3", "quebra", "{}"),
                ("c4", "consultar", '{"n": "um"}'),  # argumento inválido
                ("c5", "inventada", "{}"),  # tool que não existe
            ),
            [_texto("ok")],
        )
        fabrica = _Fabrica()
        eventos = _rodar(perfil, fabrica=fabrica)
        resultados = [tc["resultado"] for tc in _fim(eventos)["tool_calls"]]
        assert resultados[0] == {"n": 1}
        assert all("erro" in r for r in resultados[1:]), resultados
        assert len(fabrica.criados) == 5
        assert [c.nome for c in fabrica.criados if not c.fechado] == []

    def test_no_prazo_o_cliente_so_fecha_quando_a_thread_termina(self, modelo):
        vistos: list[bool] = []

        def lenta(cliente):
            time.sleep(0.2)
            # Ainda aberto: fechá-lo no prazo derrubaria a leitura dela no meio.
            vistos.append(cliente.fechado)
            return {"ok": True}

        perfil = _perfil(
            _ferramenta("lenta", lenta, prazo_s=0.05), _ferramenta("rapida", lambda cliente: {"ok": 1})
        )
        # A resposta final demora mais que a thread abandonada: ela termina com
        # o loop no ar, como em produção, e não no desligamento do teste.
        modelo(
            _pede_tools(("c1", "lenta", "{}"), ("c2", "rapida", "{}")),
            _StreamFalso([_texto("ok")], demora_s=0.4),
        )
        fabrica = _Fabrica()
        eventos = _rodar(perfil, fabrica=fabrica)
        assert "passou de" in _fim(eventos)["tool_calls"][0]["resultado"]["erro"]
        assert vistos == [False]
        assert len(fabrica.criados) == 2
        assert all(c.fechado for c in fabrica.criados), "o cliente da tool abandonada ficou aberto"

    def test_a_chamada_identica_que_so_espera_nao_cria_cliente(self, modelo):
        perfil = _perfil(_ferramenta("consultar", lambda cliente, n: {"n": n}, {"n": {"type": "integer"}}))
        modelo(
            _pede_tools(("c1", "consultar", '{"n": 1}'), ("c2", "consultar", '{"n": 1}')),
            [_texto("ok")],
        )
        fabrica = _Fabrica()
        eventos = _rodar(perfil, fabrica=fabrica)
        assert len(fabrica.criados) == 1
        assert fabrica.criados[0].fechado
        assert "já foi feita" in _fim(eventos)["tool_calls"][1]["resultado"]["erro"]

    def test_a_identica_depois_de_uma_que_falhou_roda_de_verdade(self, modelo):
        """Erro não conta como consulta feita (invariante 4): a segunda roda,
        como rodaria em série, com o próprio cliente."""
        clientes: list[Any] = []

        def instavel(cliente, n: int):
            clientes.append(cliente)
            return {"erro": "sem dado agora"} if len(clientes) == 1 else {"n": n}

        perfil = _perfil(_ferramenta("instavel", instavel, {"n": {"type": "integer"}}))
        modelo(
            _pede_tools(("c1", "instavel", '{"n": 1}'), ("c2", "instavel", '{"n": 1}')),
            [_texto("ok")],
        )
        fabrica = _Fabrica()
        eventos = _rodar(perfil, fabrica=fabrica)
        assert [tc["resultado"] for tc in _fim(eventos)["tool_calls"]] == [{"erro": "sem dado agora"}, {"n": 1}]
        assert clientes == fabrica.criados and len(clientes) == 2
        assert all(c.fechado for c in clientes)

    def test_a_mesma_consulta_duas_vezes_na_volta_roda_uma_vez(self, modelo):
        """Invariante 4 do registro (docs/43 §3.2): em série a segunda chamada
        idêntica volta como "repetida"; em paralelo tem de continuar assim."""
        rodadas: list[int] = []

        def consultar(cliente, n: int):
            rodadas.append(n)
            return {"n": n}

        perfil = _perfil(_ferramenta("consultar", consultar, {"n": {"type": "integer"}}))
        modelo(
            _pede_tools(("c1", "consultar", '{"n": 1}'), ("c2", "consultar", '{"n": 1}')),
            [_texto("ok")],
        )
        eventos = _rodar(perfil, fabrica=_Fabrica())
        assert rodadas == [1]
        primeira, segunda = (tc["resultado"] for tc in _fim(eventos)["tool_calls"])
        assert primeira == {"n": 1}
        assert "já foi feita" in segunda["erro"]

    def test_sem_cliente_proprio_vai_pelo_compartilhado_uma_por_vez(self, modelo):
        trava = threading.Lock()
        agora = [0]
        pico = [0]
        recebidos: list[Any] = []

        def contar(cliente):
            with trava:
                agora[0] += 1
                pico[0] = max(pico[0], agora[0])
                recebidos.append(cliente)
            time.sleep(0.05)
            with trava:
                agora[0] -= 1
            return {"ok": True}

        perfil = _perfil(_ferramenta("a", contar), _ferramenta("b", contar))
        modelo(_pede_tools(("c1", "a", "{}"), ("c2", "b", "{}")), [_texto("ok")])
        compartilhado = _ClienteFalso("compartilhado")
        eventos = _rodar(
            perfil, fabrica=_Fabrica(falha=RuntimeError("sem backend")), cliente_db=compartilhado
        )
        assert pico[0] == 1, "duas tools ao mesmo tempo no cliente compartilhado"
        assert recebidos == [compartilhado, compartilhado]
        assert [tc["resultado"] for tc in _fim(eventos)["tool_calls"]] == [{"ok": True}] * 2

    def test_desconectar_no_meio_cancela_as_tools_no_ar(self, modelo):
        def lenta(cliente):
            time.sleep(0.3)
            return {"ok": True}

        perfil = _perfil(_ferramenta("a", lenta), _ferramenta("b", lenta))
        modelo(_pede_tools(("c1", "a", "{}"), ("c2", "b", "{}")), [_texto("ok")])

        async def cenario():
            gerador = _gerar(perfil, fabrica=_Fabrica())
            inicios = 0
            async for evento in gerador:
                inicios += evento.nome == "tool_call_start"
                if inicios == 2:
                    break
            # O que o Starlette faz quando o cliente some: cancela a tarefa que
            # está esperando o próximo evento — aqui, as duas tools.
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(gerador.__anext__(), timeout=0.05)
            await asyncio.sleep(0.01)
            return [
                t for t in asyncio.all_tasks()
                if t.get_name().startswith("sas-chat-tool:") and not t.done()
            ]

        assert asyncio.run(cenario()) == []


class TestPrazoNaVolta:
    def test_o_modelo_repete_a_consulta_abandonada_e_ela_roda_de_novo(self, modelo):
        """O cenário da revisão antecipada do motor (25/10), pelo loop: c1
        estoura o prazo, a thread dela termina com sucesso enquanto o modelo
        pensa, e c2 — a mesma consulta — chega depois. Antes, c2 ouvia "já foi
        feita... o resultado está acima", de um resultado que o modelo nunca
        viu."""
        rodadas: list[int] = []

        def lenta(cliente):
            rodadas.append(1)
            if len(rodadas) == 1:
                time.sleep(0.2)
            return {"dado": 42}

        perfil = _perfil(_ferramenta("lenta", lenta, prazo_s=0.05))
        modelo(
            _pede_tools(("c1", "lenta", "{}")),
            # A segunda volta chega depois de a thread abandonada terminar.
            _StreamFalso(_pede_tools(("c2", "lenta", "{}")), demora_s=0.4),
            [_texto("ok")],
        )
        eventos = _rodar(perfil)
        c1, c2 = (tc["resultado"] for tc in _fim(eventos)["tool_calls"])
        assert "passou de" in c1["erro"]
        assert c2 == {"dado": 42}
        assert len(rodadas) == 2


# ─── O modelo do Tio Léo (docs/43 §6) ────────────────────────────────────


class TestModeloDoAluno:
    _SESSAO = Sessao(tipo="aluno", usuario="aluno:A1", aluno_id="A1", nome="Ana")

    def test_vem_da_configuracao(self, monkeypatch):
        _configurar(monkeypatch, OPENAI_MODELO_ALUNO="modelo-do-tio-leo")
        assert perfis.perfil_aluno(self._SESSAO).modelo == "modelo-do-tio-leo"

    def test_padrao_continua_o_mini(self, monkeypatch):
        monkeypatch.delenv("OPENAI_MODELO_ALUNO", raising=False)
        _configurar(monkeypatch)
        assert perfis.perfil_aluno(self._SESSAO).modelo == "gpt-4o-mini"
