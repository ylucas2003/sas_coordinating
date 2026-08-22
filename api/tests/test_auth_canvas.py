"""SSO pelo Canvas — o que dá para provar sem a Developer Key (docs/18 §4.2).

O fluxo de redirect só é verificável de ponta a ponta com client_id/secret
reais. O que se prova aqui: o `state` (CSRF) é assinado, expira, e nunca
vira open redirect; e o mapeamento canvas_user_id → sessão prefere
coordenador a aluno e recusa quem não existe.
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException
from jose import jwt

from app import config
from app.auth import ALGORITHM
from app.routes import auth_canvas
from tests.fake_postgrest import FakeCliente


class TestState:
    def test_assina_e_verifica_destino(self):
        state = auth_canvas._assinar_state("/painel")
        assert auth_canvas._verificar_state(state) == "/painel"

    def test_destino_absoluto_vira_raiz(self):
        """Open redirect: um state com URL externa não pode levar o usuário
        para fora depois do login."""
        for ruim in ("https://evil.example", "//evil.example", "javascript:alert(1)"):
            assert auth_canvas._verificar_state(auth_canvas._assinar_state(ruim)) == "/"

    def test_state_adulterado_e_recusado(self):
        state = auth_canvas._assinar_state("/")
        with pytest.raises(HTTPException) as exc:
            auth_canvas._verificar_state(state[:-4] + "xxxx")
        assert exc.value.status_code == 400

    def test_state_vencido_e_recusado(self):
        s = config.get_settings()
        vencido = jwt.encode(
            {"n": "x", "p": "/", "exp": int(time.time()) - 1}, s.jwt_secret_key, algorithm=ALGORITHM
        )
        with pytest.raises(HTTPException):
            auth_canvas._verificar_state(vencido)


class TestSessaoPara:
    def _db(self):
        return {
            "usuario_coordenacao": {
                "c1": {"id": "c1", "nome": "Leo", "ativo": True, "canvas_user_id": "100"},
                "c2": {"id": "c2", "nome": "Ex", "ativo": False, "canvas_user_id": "200"},
            },
            "aluno": {
                "a1": {"id": "a1", "nome": "Ana", "ativo": True, "canvas_user_id": "300"},
                "a2": {"id": "a2", "nome": "Dup", "ativo": True, "canvas_user_id": "100"},
            },
        }

    def test_coordenador_antes_de_aluno(self):
        """Um coordenador também matriculado em curso entra como coordenador."""
        token, tipo = auth_canvas._sessao_para(FakeCliente(self._db()), "100")
        assert tipo == "coordenador" and token

    def test_aluno(self):
        token, tipo = auth_canvas._sessao_para(FakeCliente(self._db()), "300")
        assert tipo == "aluno" and token

    def test_coordenador_inativo_nao_entra(self):
        assert auth_canvas._sessao_para(FakeCliente(self._db()), "200") == (None, None)

    def test_identidade_sem_conta_e_recusada(self):
        """O Canvas diz quem é; o SAS decide quem entra. Sem linha, sem sessão."""
        assert auth_canvas._sessao_para(FakeCliente(self._db()), "999") == (None, None)
