"""SSO pelo Canvas — a porta única do aluno (docs/18 §4.2, docs/35 §11.5).

O fluxo de redirect inteiro só é verificável com client_id/secret reais (e foi:
rodou em produção em 04/09). O que se prova aqui é o que não depende do Canvas:
o `state` (CSRF) é assinado, expira e nunca vira open redirect; e o mapeamento
canvas_user_id → sessão devolve ALUNO, e só aluno.

⚠️ Este arquivo tinha cinco testes a mais, e todos provavam coisas que
deixaram de existir: `_sessao_para` preferindo coordenador a aluno, e
`_ligar_coordenador_pelo_email` casando conta de coordenação pelo e-mail no
primeiro login. Os dois eram o SSO da coordenação, que saiu (docs/35 §11.6).
No lugar deles entra o teste que fixa a regra nova: id de coordenação não abre
sessão nenhuma por aqui.
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
            },
            "aluno": {
                "a1": {"id": "a1", "nome": "Ana", "ativo": True, "canvas_user_id": "300"},
                "a2": {"id": "a2", "nome": "Inativa", "ativo": False, "canvas_user_id": "400"},
            },
        }

    def test_aluno(self):
        token, tipo = auth_canvas._sessao_para(FakeCliente(self._db()), "300")
        assert tipo == "aluno" and token

    def test_coordenacao_nao_entra_pelo_canvas(self):
        """A regra nova (docs/35 §11.6): o id 100 é de uma conta de
        coordenação ATIVA e mesmo assim não abre sessão. Quem é da coordenação
        entra por e-mail + senha, e só."""
        assert auth_canvas._sessao_para(FakeCliente(self._db()), "100") == (None, None)

    def test_aluno_inativo_nao_entra(self):
        assert auth_canvas._sessao_para(FakeCliente(self._db()), "400") == (None, None)

    def test_identidade_sem_conta_e_recusada(self):
        """O Canvas diz quem é; o SAS decide quem entra. Sem linha, sem sessão."""
        assert auth_canvas._sessao_para(FakeCliente(self._db()), "999") == (None, None)
