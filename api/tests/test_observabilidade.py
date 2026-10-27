"""O id de requisição que a casa herda do cliente (`observabilidade.py`).

O X-Request-Id é texto de quem chama, sem teto. Ia cru para a resposta, para
toda linha de log e para `evento_auditoria.request_id` — e no MCP, onde o
gatilho da 0072 recusa (42501) o INSERT do sas_mcp com request_id acima de
128 caracteres, um header de 129 apagava a chamada da trilha (revisão final de
26/10). O middleware é o MESMO na API e no MCP (app/main.py, app/mcp/app.py).

Rodar:  cd api && APP_ENV=dev ./.venv/bin/python -m pytest tests/test_observabilidade.py -q
"""

from __future__ import annotations

import re

import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.observabilidade import middleware_request_id, request_id_aceito, request_id_atual


def _app() -> Starlette:
    async def eco(request: Request) -> JSONResponse:
        # O que o resto da requisição vê: é este o id dos logs e da auditoria.
        return JSONResponse({"request_id": request_id_atual()})

    return Starlette(
        routes=[Route("/eco", eco)],
        middleware=[Middleware(BaseHTTPMiddleware, dispatch=middleware_request_id)],
    )


@pytest.mark.parametrize(
    "enviado",
    ["rid-do-teste", "0f8fad5b-d9cb-469f-a165-70867728950e", "00-4bf92f3577b34da6a3ce929d0e0e4736-01", "a" * 64],
)
def test_id_na_forma_aceita_e_herdado(enviado):
    with TestClient(_app()) as c:
        r = c.get("/eco", headers={"x-request-id": enviado})
    assert r.json()["request_id"] == r.headers["x-request-id"] == enviado


@pytest.mark.parametrize("enviado", ["a" * 65, "r" * 200, "-", "_x", "id com espaco", "rid;--", "a/b", ""])
def test_id_fora_da_forma_vira_um_nosso(enviado):
    with TestClient(_app()) as c:
        r = c.get("/eco", headers={"x-request-id": enviado})
    nosso = r.json()["request_id"]
    assert nosso != enviado and nosso == r.headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{12}", nosso)


def test_sem_header_o_id_e_nosso():
    with TestClient(_app()) as c:
        r = c.get("/eco")
    assert re.fullmatch(r"[0-9a-f]{12}", r.json()["request_id"])


def test_request_id_aceito_e_pura():
    assert request_id_aceito("abc_DEF-123") == "abc_DEF-123"
    # O "-" é o "sem requisição" do ContextVar: de fora, não vale.
    assert request_id_aceito("-") is None and request_id_aceito(None) is None
    assert request_id_aceito("a" * 64) and not request_id_aceito("a" * 65)
