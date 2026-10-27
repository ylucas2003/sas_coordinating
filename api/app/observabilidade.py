"""Log estruturado, id de requisição e handler global de erro.

Antes disto o backend não tinha nada: zero `exception_handler` (um 500 saía
como traceback órfão do uvicorn, sem rota, sem usuário, sem correlação), zero
configuração de logging (o `log.info` do sync podia nem aparecer, dependendo do
arranque), e nenhum formato que um coletor conseguisse ler (docs/14 §5, ops).

O id de requisição é o que costura tudo: entra no header da resposta, aparece
em toda linha de log daquela requisição, e é o único dado que a mensagem de
erro entrega ao usuário — de modo que "deu erro na tela" vira uma busca de um
termo no log, em vez de arqueologia por horário.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from fastapi.responses import JSONResponse

# ContextVar e não thread-local: o FastAPI atende em async, e várias
# requisições compartilham a mesma thread.
_request_id: ContextVar[str] = ContextVar("request_id", default="-")

#: O X-Request-Id que o cliente manda só é herdado nesta forma; fora dela, o
#: id é nosso. O header é texto de quem chama, sem teto, e ia cru para a
#: resposta, para toda linha de log e para `evento_auditoria.request_id`. No
#: MCP isso apagava a trilha: o gatilho da 0072 recusa (42501) INSERT do
#: sas_mcp com request_id acima de 128 caracteres, `registrar_chamada` engole
#: a falha, e um header de 129 fazia o tools/call devolver o dado sem linha
#: nenhuma na auditoria (revisão final de 26/10). Há proxy que manda id longo
#: sem má-fé — o do Heroku vai a 200 —, e o nginx da VPS não o sobrescreve.
#: 64 cabe num uuid com hífens e num traceparent; o primeiro caractere
#: alfanumérico deixa de fora o "-", que é o "sem requisição" do ContextVar.
_REQUEST_ID_ACEITO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")


def request_id_atual() -> str:
    return _request_id.get()


def request_id_aceito(valor: str | None) -> str | None:
    """O id de requisição de FORA, se ele tem a forma que a casa aceita; senão None."""
    if valor and _REQUEST_ID_ACEITO.fullmatch(valor):
        return valor
    return None


class _FormatadorJSON(logging.Formatter):
    """Uma linha JSON por evento — o que um coletor consegue indexar.

    Texto solto do uvicorn misturado com access log é exatamente o que torna
    'por que o sync do Canvas parou?' impossível de responder.
    """

    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime(record.created)),
            "nivel": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or request_id_atual(),
        }
        # As três últimas são da linha que `chat/ferramentas.py` grava a cada
        # chamada de tool: sem elas o campo some do JSON em silêncio, e a
        # duração por tool que o docs/43 §8 quer medir vira só texto.
        for chave in (
            "rota", "metodo", "status", "usuario", "duracao_ms",
            "ferramenta", "escopo", "desfecho",
        ):
            if (valor := getattr(record, chave, None)) is not None:
                evento[chave] = valor
        if record.exc_info:
            evento["excecao"] = self.formatException(record.exc_info)
        return json.dumps(evento, ensure_ascii=False)


def configurar_logging() -> None:
    """Chamado uma vez, no create_app.

    LOG_FORMATO=texto volta ao formato legível — útil em dev, onde JSON numa
    linha é pior de ler do que texto.
    """
    nivel = os.environ.get("LOG_NIVEL", "INFO").upper()
    formato = os.environ.get("LOG_FORMATO", "json").lower()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _FormatadorJSON()
        if formato == "json"
        else logging.Formatter("%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    )

    raiz = logging.getLogger()
    raiz.handlers.clear()
    raiz.addHandler(handler)
    raiz.setLevel(nivel)

    # O access log do uvicorn duplicaria o que o middleware já registra, com
    # menos contexto (sem request id, sem usuário).
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.access").propagate = False
    # httpx loga uma linha por chamada ao PostgREST — são milhares por rodada
    # de recálculo, e afogam o resto.
    logging.getLogger("httpx").setLevel("WARNING")


async def middleware_request_id(request: Request, call_next):
    """Gera (ou herda) o id, mede a duração e registra o fim da requisição.

    Herda só o id na forma de `request_id_aceito`; o resto é trocado por um
    nosso, que volta no header da resposta — é por ele que quem chamou acha a
    linha de log.
    """
    rid = request_id_aceito(request.headers.get("X-Request-Id")) or uuid.uuid4().hex[:12]
    _request_id.set(rid)
    inicio = time.perf_counter()

    resposta = await call_next(request)

    duracao = int((time.perf_counter() - inicio) * 1000)
    resposta.headers["X-Request-Id"] = rid

    # /health é chamado pelo Docker a cada 30s e /health/ready pelo cron:
    # registrá-los são ~3 mil linhas/dia que não informam nada.
    #
    # `endswith` e não igualdade: com `--root-path /api` o caminho que chega
    # aqui é `/api/health`, não `/health`. A comparação exata parecia certa e
    # não filtrava nada.
    caminho = request.url.path
    if not (caminho.endswith("/health") or caminho.endswith("/health/ready")):
        logging.getLogger("sas.http").info(
            "requisição concluída",
            extra={
                "rota": request.url.path,
                "metodo": request.method,
                "status": resposta.status_code,
                "duracao_ms": duracao,
            },
        )
    return resposta


async def handler_erro_nao_tratado(request: Request, exc: Exception) -> JSONResponse:
    """Um ponto único onde todo 500 passa.

    Sem isto o traceback saía sem rota, sem método e sem nada que permitisse
    reproduzir — e não havia lugar para contar erro nem disparar alerta.

    O corpo devolve o `request_id` e mais nada: mensagem de exceção pode
    carregar a URL do PostgREST ou trecho de token (docs/14 §5, ops).
    """
    logging.getLogger("sas.erro").exception(
        "erro não tratado",
        extra={"rota": request.url.path, "metodo": request.method},
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Erro interno. Informe o código abaixo ao suporte.",
            "request_id": request_id_atual(),
        },
        headers={"X-Request-Id": request_id_atual()},
    )
