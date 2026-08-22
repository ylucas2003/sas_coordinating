"""Separação entre token de SESSÃO e token de CAPACIDADE.

O bug que estes testes existem para não deixar voltar: o token de download de
arquivo (app/storage.py) era assinado com a mesma `JWT_SECRET_KEY` e o mesmo
HS256 do token de sessão, e `get_current_user` (app/auth.py) validava só
assinatura e `exp`. O aluno recebe esse token em claro — a URL vem no corpo de
`GET /me/simulado/{id}/arquivo` — e bastava reapresentá-lo como `Bearer` no
chat: o `else` de `chat/rotas.py` lhe dava o perfil de COORDENAÇÃO, com as
tools que leem qualquer um dos ~900 alunos.

São três barreiras agora, e cada uma tem teste aqui:
  1. `get_current_user` recusa `tipo` fora de `TIPOS_DE_SESSAO`;
  2. `_usuario_do_token` não devolve namespace de coordenação por omissão;
  3. o token de download é assinado com chave DERIVADA, então nem chega a ser
     um JWT válido para o verificador de sessão.

Rodar:  cd api && ./.venv/bin/python -m pytest tests/ -q
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from jose import jwt

SEGREDO = "segredo-de-teste-com-mais-de-32-caracteres"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    """APP_ENV=dev para o guard de boot deixar `create_app()` subir."""
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("JWT_SECRET_KEY", SEGREDO)
    yield
    get_settings.cache_clear()


def _token_de_download() -> str:
    """O que `storage.gerar_url_download_arquivo` produzia com a chave de sessão.

    Assinado aqui com a `JWT_SECRET_KEY` crua de propósito: é exatamente o
    token que o atacante tinha em mãos antes da correção.
    """
    return jwt.encode(
        {
            "tipo": "download_arquivo",
            "caminho": "simulados/123-prova.pdf",
            "nome": "prova.pdf",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        SEGREDO,
        algorithm="HS256",
    )


def test_token_de_download_nao_abre_sessao_no_chat():
    """O ataque, ponta a ponta. Recusado na dependência, antes do banco —
    por isso este teste roda sem cliente nenhum, como o do webhook do SES."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    cliente = TestClient(create_app())
    resposta = cliente.get(
        "/chat/threads",
        headers={"Authorization": f"Bearer {_token_de_download()}"},
    )
    assert resposta.status_code == 401


def test_token_sem_tipo_nao_abre_sessao():
    """Um JWT válido e sem `tipo` também não é sessão."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    token = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) + timedelta(hours=1)},
        SEGREDO,
        algorithm="HS256",
    )
    cliente = TestClient(create_app())
    assert cliente.get(
        "/chat/threads", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 401


@pytest.mark.parametrize("tipo", ["download_arquivo", "servico", "", None])
def test_usuario_do_token_recusa_o_que_nao_e_sessao(tipo):
    """Segunda barreira: nem por omissão o namespace vira de coordenação."""
    from app.chat.rotas import _usuario_do_token

    with pytest.raises(HTTPException) as erro:
        _usuario_do_token({"tipo": tipo, "sub": "qualquer"})
    assert erro.value.status_code == 403


def test_usuario_do_token_recusa_coordenador_sem_sub():
    """O default `'coordenador'` colapsava todo token sem `sub` num balde só."""
    from app.chat.rotas import _usuario_do_token

    with pytest.raises(HTTPException) as erro:
        _usuario_do_token({"tipo": "coordenador"})
    assert erro.value.status_code == 403


def test_usuario_do_token_aceita_sessao_legitima():
    """Não-regressão: aluno e coordenador continuam tendo namespace próprio."""
    from app.chat.rotas import _usuario_do_token

    assert _usuario_do_token({"tipo": "aluno", "aluno_id": "a1"}) == "aluno:a1"
    assert _usuario_do_token({"tipo": "coordenador", "sub": "u9"}) == "coord:u9"


def test_download_e_sessao_nao_compartilham_mais_a_chave():
    """A separação criptográfica: o token de download deixa de ser sequer um
    JWT válido para o verificador de sessão, e vice-versa."""
    from jose import JWTError

    from app.storage import _segredo_download, ler_token_download

    assert _segredo_download() != SEGREDO

    # O token antigo (assinado com a chave de sessão) não passa mais no leitor.
    with pytest.raises(JWTError):
        ler_token_download(_token_de_download())

    # E um token de sessão não é aceito como download.
    sessao = jwt.encode(
        {
            "sub": "a1",
            "tipo": "aluno",
            "aluno_id": "a1",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        },
        SEGREDO,
        algorithm="HS256",
    )
    with pytest.raises(JWTError):
        ler_token_download(sessao)


def test_download_continua_indo_e_voltando(monkeypatch, tmp_path):
    """Não-regressão do download: assinar e ler com a chave derivada funciona."""
    from app.config import get_settings
    from app.storage import gerar_url_download_arquivo, ler_token_download

    monkeypatch.setenv("STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("API_BASE_URL", "http://localhost:8000")
    get_settings.cache_clear()

    url = gerar_url_download_arquivo("simulados/1-prova.pdf", nome_download="prova.pdf")
    token = url.split("token=", 1)[1]

    from urllib.parse import unquote

    assert ler_token_download(unquote(token)) == ("simulados/1-prova.pdf", "prova.pdf")
