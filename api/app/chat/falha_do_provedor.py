"""Falha do provedor do modelo: quem usa nunca lê o erro cru (docs/43 §4.1, defeito 4).

Até 24/10/2026 o agente fazia `erro_fatal = f"falha chamando o modelo: {e}"`, e
o texto da exceção do SDK da OpenAI atravessava o SSE até a tela — que, no Tio
Léo, é a de um menor de idade — e era gravado em `chat_mensagem` como
"⚠️ Erro: …" (`rotas.py`), de onde volta toda vez que a conversa reabre. Cota
esgotada virava "You exceeded your current quota, please check your plan and
billing details" na frente do aluno: um problema administrativo NOSSO, em
inglês, com o nome do fornecedor.

O desenho é o do `chat/providerFailure.ts` do MCP da Solomon: duas audiências.

  QUEM USA    recebe `FalhaDoProvedor.mensagem` — curta, em português, sem
              provedor, sem saldo, sem stack. Fail-closed: o que não se
              classifica cai na mensagem genérica, nunca no texto original.
  A EQUIPE    recebe `registrar` — a linha de log com o motivo real. Saldo,
              credencial e configuração sobem para ERROR com "[AÇÃO
              NECESSÁRIA]": é problema da nossa conta ou do nosso ambiente, e o
              aluno não tem o que fazer com ele.

Classifica pelos tipos do SDK quando o import funciona e por `status_code` e
`code` como reserva — o mesmo `code` que decide os casos em que a classe
mente: cota esgotada chega como `RateLimitError` (429) com `insufficient_quota`,
conversa longa demais como `BadRequestError` (400) com
`context_length_exceeded`, e configuração NOSSA — o modelo do env que não
existe, um parâmetro que o modelo recusa — como `NotFoundError` (404) com
`model_not_found` ou `BadRequestError` com `unsupported_parameter` e o `param`
que nós mandamos. Erro no MEIO do stream chega como `APIError` puro,
sem status (o `_streaming.py` do SDK monta só com o corpo); e queda de rede no
meio da leitura, como exceção do httpx, que o SDK não embrulha.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

try:
    import openai as _openai
except ImportError:  # o chat já degrada sem o SDK (agente.py); este módulo também
    _openai = None  # type: ignore[assignment]

try:
    import httpx as _httpx
except ImportError:
    _httpx = None  # type: ignore[assignment]

log = logging.getLogger("sas.chat.provedor")

TipoDeFalha = Literal[
    "saldo",
    "credencial",
    "configuracao",
    "limite",
    "sobrecarga",
    "prazo",
    "rede",
    "conversa_longa",
    "requisicao",
    "desconhecida",
]

#: Saldo, credencial e configuração dizem a MESMA coisa de propósito: "acabaram
#: os créditos" ou "o modelo configurado não existe" só transferem a quem
#: pergunta um problema que é da equipe. Também não promete que alguém "já foi
#: avisado": aqui nada pagina ninguém, só o log registra.
_FORA_DO_AR = (
    "O assistente está indisponível agora por um problema do nosso lado. "
    "Tente de novo mais tarde."
)

_MENSAGENS: dict[TipoDeFalha, str] = {
    "saldo": _FORA_DO_AR,
    "credencial": _FORA_DO_AR,
    "configuracao": _FORA_DO_AR,
    "limite": (
        "Chegaram muitas perguntas ao mesmo tempo e precisei parar esta resposta. "
        "Espere alguns segundos e mande de novo."
    ),
    "sobrecarga": (
        "O serviço que gera as respostas está sobrecarregado agora. "
        "Tente de novo em instantes."
    ),
    "prazo": (
        "A resposta demorou mais que o esperado e foi interrompida. Tente de novo; "
        "se a pergunta for ampla, dividir em partes ajuda."
    ),
    "rede": "Houve uma falha de conexão ao gerar a resposta. Tente de novo em instantes.",
    "conversa_longa": (
        "Esta conversa ficou longa demais para eu continuar. "
        "Comece uma nova conversa para seguir."
    ),
    "requisicao": (
        "Não consegui processar esta mensagem. Tente reformular a pergunta "
        "ou começar uma nova conversa."
    ),
    "desconhecida": "Tive um problema para gerar a resposta. Tente de novo em instantes.",
}

_PRECISA_ACAO: frozenset[TipoDeFalha] = frozenset({"saldo", "credencial", "configuracao"})

#: Os `code` documentados da OpenAI que bastam sozinhos para decidir o tipo,
#: venha a exceção de que classe vier. É o que mantém a classificação de pé no
#: erro do meio do stream, que não traz status.
#:
#: Os três de configuração são NOSSOS como a credencial: o modelo vem do env
#: (OPENAI_MODELO_ALUNO, OPENAI_MODELO_COORDENADOR) e os parâmetros, do código
#: (agente.py: max_tokens, temperature, stream_options). Um erro de digitação no
#: env fazia TODA mensagem de todo aluno falhar com o texto genérico, e a
#: equipe só via um WARNING (revisão antecipada do motor, 25/10). Um modelo de
#: raciocínio recusa `max_tokens` e `temperature` exatamente assim.
_POR_CODIGO: dict[str, TipoDeFalha] = {
    "insufficient_quota": "saldo",
    "invalid_api_key": "credencial",
    "model_not_found": "configuracao",
    "unsupported_parameter": "configuracao",
    "unsupported_value": "configuracao",
    "context_length_exceeded": "conversa_longa",
    "rate_limit_exceeded": "limite",
}

#: Os parâmetros que o agente manda e que vêm do código ou do env, nunca de quem
#: pergunta. Um 400 que aponta para um deles (`param` do corpo do erro) é
#: configuração nossa, qualquer que seja o `code`; um que aponta para
#: `messages` é do conteúdo, e segue "requisicao". `tools` entra: o schema das
#: tools é código nosso, e recusado, falha toda pergunta.
_PARAMETROS_NOSSOS: tuple[str, ...] = (
    "model",
    "max_tokens",
    "max_completion_tokens",
    "temperature",
    "tools",
    "tool_choice",
    "stream_options",
    "parallel_tool_calls",
)


@dataclass(frozen=True)
class FalhaDoProvedor:
    tipo: TipoDeFalha
    #: O texto que vai para a tela e para `chat_mensagem`. Nunca contém a
    #: mensagem original do provedor.
    mensagem: str
    #: Problema da NOSSA conta (saldo, credencial): exige gente, não nova tentativa.
    precisa_acao: bool


def mensagem_para_quem_usa(tipo: TipoDeFalha) -> str:
    """O texto amigável de um tipo — para quem já sabe o tipo sem ter exceção
    (o agente sem `OPENAI_API_KEY`, por exemplo)."""
    return _MENSAGENS[tipo]


def classificar(exc: BaseException) -> FalhaDoProvedor:
    """O tipo da falha e o texto seguro para quem usa. Puro: sem log."""
    tipo = _tipo(exc)
    return FalhaDoProvedor(
        tipo=tipo, mensagem=_MENSAGENS[tipo], precisa_acao=tipo in _PRECISA_ACAO
    )


def registrar(
    falha: FalhaDoProvedor,
    exc: BaseException,
    *,
    thread_id: str | None = None,
    modelo: str | None = None,
    usuario: str | None = None,
) -> None:
    """A linha de log da equipe, com o motivo real. Não lança.

    O `repr` da exceção vai AQUI e só aqui: log é interno. `status`, `code` e o
    `request_id` da OpenAI vão junto porque são o que um chamado de suporte com
    eles pede. Stack só no desconhecido — nos outros o tipo já diz onde olhar.
    """
    status = _status(exc)
    detalhes = (
        f"tipo={falha.tipo} thread={thread_id or '-'} modelo={modelo or '-'} "
        f"status={status if status is not None else '-'} "
        f"code={_codigo(exc) or '-'} param={_parametro(exc) or '-'} "
        f"request_id={getattr(exc, 'request_id', None) or '-'}"
    )
    # Truncado: o corpo de um 400 pode ser longo, e a linha é para ler.
    motivo = repr(exc)[:2000]
    extra = {"usuario": usuario} if usuario else None
    if falha.precisa_acao:
        log.error(
            "[AÇÃO NECESSÁRIA] falha do provedor do modelo %s: %s", detalhes, motivo, extra=extra
        )
    else:
        log.warning(
            "falha do provedor do modelo %s: %s",
            detalhes,
            motivo,
            extra=extra,
            exc_info=exc if falha.tipo == "desconhecida" else None,
        )


# ─── Classificação ───────────────────────────────────────────────────────


def _tipo(exc: BaseException) -> TipoDeFalha:
    # 1 · O `code` primeiro: é ele que separa cota esgotada de limite comum
    # (os dois são 429) e conversa longa de requisição inválida (os dois 400).
    codigo = _codigo(exc)
    if codigo in _POR_CODIGO:
        return _POR_CODIGO[codigo]
    if (_texto(getattr(exc, "type", None)) or "") == "insufficient_quota":
        return "saldo"

    # 2 · Os tipos do SDK. `APITimeoutError` é subclasse de
    # `APIConnectionError`: a ordem importa.
    if _openai is not None:
        if isinstance(exc, (_openai.AuthenticationError, _openai.PermissionDeniedError)):
            return "credencial"
        if isinstance(exc, _openai.NotFoundError):
            # Na rota do chat, 404 é o modelo do env que não existe (ou uma
            # base URL errada): configuração, com ou sem `code`.
            return "configuracao"
        if isinstance(exc, _openai.RateLimitError):
            return "limite"
        if isinstance(exc, _openai.InternalServerError):
            return "sobrecarga"
        if isinstance(exc, _openai.APITimeoutError):
            return "prazo"
        if isinstance(exc, _openai.APIConnectionError):
            return "rede"
        if isinstance(exc, _openai.BadRequestError):
            return "configuracao" if _parametro_nosso(exc) else "requisicao"

    # 3 · httpx cru: a leitura do stream não passa pelo `try` do SDK, e um
    # corte no meio da resposta chega assim. Prazo também vem antes (subclasse).
    if _httpx is not None:
        if isinstance(exc, _httpx.TimeoutException):
            return "prazo"
        if isinstance(exc, _httpx.TransportError):
            return "rede"

    # 4 · Reserva pelo status: para quando a classe não é a do SDK (outra
    # versão, um embrulho) mas o número veio.
    status = _status(exc)
    if status is not None:
        if status in (401, 403):
            return "credencial"
        if status == 404:
            return "configuracao"
        if status == 429:
            return "limite"
        if status in (408, 504):
            return "prazo"
        if status >= 500:  # 500, 502, 503 e o 529 de "sobrecarregado"
            return "sobrecarga"
        if status == 400:
            return "configuracao" if _parametro_nosso(exc) else "requisicao"

    # Erro no meio do stream: `APIError` sem status, só com o `type` do corpo.
    if (_texto(getattr(exc, "type", None)) or "") == "server_error":
        return "sobrecarga"

    if isinstance(exc, TimeoutError):
        return "prazo"
    if isinstance(exc, ConnectionError):
        return "rede"
    return "desconhecida"


def _codigo(exc: BaseException) -> str | None:
    return _do_corpo(exc, "code")


def _parametro(exc: BaseException) -> str | None:
    """O `param` do corpo do erro: qual parâmetro da requisição foi recusado."""
    return _do_corpo(exc, "param")


def _do_corpo(exc: BaseException, campo: str) -> str | None:
    valor = _texto(getattr(exc, campo, None))
    if valor:
        return valor
    # O SDK copia `code` e `param` do corpo; um embrulho que só guardou o corpo
    # ainda os tem.
    corpo = getattr(exc, "body", None)
    if isinstance(corpo, dict):
        return _texto(corpo.get(campo))
    return None


def _parametro_nosso(exc: BaseException) -> bool:
    """O 400 aponta para um parâmetro que o código ou o env decidem
    (`_PARAMETROS_NOSSOS`)? `tools[3].function.parameters` conta como `tools`."""
    parametro = _parametro(exc)
    return parametro is not None and re.split(r"[.\[]", parametro, maxsplit=1)[0] in _PARAMETROS_NOSSOS


def _status(exc: BaseException) -> int | None:
    for candidato in (
        getattr(exc, "status_code", None),
        getattr(getattr(exc, "response", None), "status_code", None),
    ):
        # `bool` é subclasse de `int`; um `True` não é status.
        if isinstance(candidato, int) and not isinstance(candidato, bool) and 100 <= candidato < 600:
            return candidato
    return None


def _texto(valor: Any) -> str | None:
    if not isinstance(valor, str):
        return None
    return valor.strip().lower() or None
