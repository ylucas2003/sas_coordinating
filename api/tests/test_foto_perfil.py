"""Foto de perfil (docs/sprints.html · SPRINT FOTO).

Três camadas testadas separadamente:

  1. `app/storage.py` — o par salvar/ler/remover no filesystem local, e a
     validação de assinatura de bytes (magic number) que impede um
     Content-Type mentiroso de passar como imagem válida.
  2. `app/routes/foto_perfil.py` — o autosserviço `/me/foto`, que resolve
     tabela e id pelo `tipo` do JWT (aluno x coordenador) em vez de duas
     rotas duplicadas.
  3. `app/routes/alunos.py` e `app/routes/auth.py` — a visão da coordenação
     sobre a foto de um aluno, e o `temFoto` que passa a viajar no login.

Convenção do arquivo (como em test_canvas_sob_controle.py): chama os
handlers `async def` diretamente com `asyncio.run`, com um `FakeCliente`
de `tests/fake_postgrest.py` no lugar do PostgREST — sem TestClient, sem
banco de verdade.
"""

from __future__ import annotations

import asyncio
import base64

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import storage
from app.routes import administracao, alunos, auth, foto_perfil
from tests.fake_postgrest import FakeCliente

# JPEG 1x1 real (assinatura correta) — o que o crop do browser produziria.
_JPEG_1X1 = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb004300030202020202"
    "03020202030303030406040404040408060605070806080808070808080809"
    "0a0c0a09090b090808090c0d0d0e0d0d0d0a0b0e0f0e0e0f0c0d0d0dffc90011"
    "080001000103012200021101031101ffc4001f0000010501010101010100000"
    "0000000000102030405060708090a0bffc400b5100002010303020403050504"
    "040000017d01020300041105122131410613516107227114328191a1082342b"
    "1c11552d1f02433627282090a161718191a25262728292a3435363738393a43"
    "4445464748494a535455565758595a636465666768696a737475767778797a8"
    "28384858687888a92939495969798999aa2a3a4a5a6a7a8a9aab2b3b4b5b6b7b"
    "8b9bac2c3c4c5c6c7c8c9cad2d3d4d5d6d7d8d9dae1e2e3e4e5e6e7e8e9eaf1f"
    "2f3f4f5f6f7f8f9faffda0008010100003f00fb"
    "d9"
)


class _FakeRequest:
    """Só o que os handlers leem de `Request`: `client.host`."""

    def __init__(self, ip: str | None = "203.0.113.7"):
        self.client = type("C", (), {"host": ip})() if ip else None


def _corpo_valido(base64_conteudo: str = "", content_type: str = "image/jpeg") -> foto_perfil.FotoPerfilBody:
    return foto_perfil.FotoPerfilBody(
        conteudo_base64=base64_conteudo or base64.b64encode(_JPEG_1X1).decode(),
        content_type=content_type,
        declaracao_autorizacao=True,
    )


# ─── storage.py ────────────────────────────────────────────────────────────


class TestStorage:
    def _settings_local(self, tmp_path):
        return type("S", (), {
            "storage_dir": str(tmp_path), "storage_bucket": "sas-uploads",
            "jwt_secret_key": "x" * 32, "api_base_url": "http://localhost:8000",
        })()

    def test_salva_le_e_remove(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))

        caminho = storage.salvar_foto_perfil(
            entidade="aluno", entidade_id="a1", conteudo=_JPEG_1X1, content_type="image/jpeg"
        )
        assert caminho == "fotos-perfil/aluno/a1.jpg"

        lido = storage.ler_foto_perfil(caminho)
        assert lido is not None
        conteudo, content_type = lido
        assert conteudo == _JPEG_1X1
        assert content_type == "image/jpeg"

        storage.remover_foto_perfil(caminho)
        assert storage.ler_foto_perfil(caminho) is None

    def test_substituir_nao_acumula_arquivo(self, tmp_path, monkeypatch):
        """Path é determinístico por entidade_id — reenviar substitui, não duplica."""
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        storage.salvar_foto_perfil(entidade="aluno", entidade_id="a1", conteudo=_JPEG_1X1, content_type="image/jpeg")
        storage.salvar_foto_perfil(entidade="aluno", entidade_id="a1", conteudo=_JPEG_1X1, content_type="image/jpeg")
        assert list((tmp_path / "fotos-perfil" / "aluno").iterdir()) == [tmp_path / "fotos-perfil" / "aluno" / "a1.jpg"]

    def test_recusa_bytes_que_nao_batem_com_o_content_type(self, tmp_path, monkeypatch):
        """Um PNG de verdade declarado como image/jpeg é recusado — a
        assinatura dos bytes manda, não a palavra do cliente."""
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        png_de_verdade = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
        with pytest.raises(ValueError, match="não é uma imagem"):
            storage.salvar_foto_perfil(
                entidade="aluno", entidade_id="a1", conteudo=png_de_verdade, content_type="image/jpeg"
            )

    def test_recusa_maior_que_o_limite(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        grande = _JPEG_1X1 + b"\x00" * storage.TAMANHO_MAXIMO_FOTO_BYTES
        with pytest.raises(ValueError, match="maior que o limite"):
            storage.salvar_foto_perfil(entidade="aluno", entidade_id="a1", conteudo=grande, content_type="image/jpeg")

    def test_ler_foto_inexistente_devolve_none_em_vez_de_levantar(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        assert storage.ler_foto_perfil("fotos-perfil/aluno/fantasma.jpg") is None

    def test_remover_inexistente_nao_levanta(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        storage.remover_foto_perfil("fotos-perfil/aluno/fantasma.jpg")  # não deve levantar

    @pytest.mark.parametrize("content_type", ["image/gif", "text/html", "application/pdf"])
    def test_recusa_content_type_fora_da_lista(self, content_type):
        assert storage.content_type_de_foto_valido(content_type, _JPEG_1X1) is False


# ─── FotoPerfilBody (validação de corpo) ────────────────────────────────────


class TestFotoPerfilBody:
    def test_recusa_sem_confirmar_autorizacao(self):
        with pytest.raises(ValidationError, match="autorização"):
            foto_perfil.FotoPerfilBody(
                conteudo_base64=base64.b64encode(_JPEG_1X1).decode(),
                content_type="image/jpeg",
                declaracao_autorizacao=False,
            )

    def test_recusa_content_type_nao_suportado(self):
        with pytest.raises(ValidationError):
            foto_perfil.FotoPerfilBody(
                conteudo_base64=base64.b64encode(_JPEG_1X1).decode(),
                content_type="image/gif",
                declaracao_autorizacao=True,
            )


# ─── /me/foto — autosserviço (aluno e coordenador pela mesma rota) ─────────


class TestMeFoto:
    def _db(self):
        return {
            "aluno": {"a1": {"id": "a1", "nome": "Ana", "foto_perfil_storage": None}},
            "usuario_coordenacao": {"c1": {"id": "c1", "nome": "Leo", "foto_perfil_storage": None}},
        }

    def _settings_local(self, tmp_path):
        return type("S", (), {
            "storage_dir": str(tmp_path), "storage_bucket": "sas-uploads",
            "jwt_secret_key": "x" * 32, "api_base_url": "http://localhost:8000",
        })()

    def test_sem_foto_devolve_null(self, tmp_path, monkeypatch):
        db = self._db()
        monkeypatch.setattr(foto_perfil, "get_supabase", lambda: FakeCliente(db))
        resultado = asyncio.run(foto_perfil.obter_minha_foto(user={"tipo": "aluno", "aluno_id": "a1"}))
        assert resultado == {"fotoDataUrl": None}

    def test_aluno_envia_le_e_remove_a_propria_foto(self, tmp_path, monkeypatch):
        db = self._db()
        monkeypatch.setattr(foto_perfil, "get_supabase", lambda: FakeCliente(db))
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        user = {"tipo": "aluno", "aluno_id": "a1"}

        resposta = asyncio.run(foto_perfil.salvar_minha_foto(_corpo_valido(), _FakeRequest(), user))
        assert resposta == {"ok": True}
        assert db["aluno"]["a1"]["foto_perfil_storage"] == "fotos-perfil/aluno/a1.jpg"
        assert db["aluno"]["a1"]["foto_perfil_atualizada_em"] is not None

        eventos_salvar = [e for e in db["evento_auditoria"].values() if e["acao"] == "foto_perfil_definida"]
        assert len(eventos_salvar) == 1
        assert eventos_salvar[0]["ator_tipo"] == "aluno" and eventos_salvar[0]["ator_id"] == "a1"

        lida = asyncio.run(foto_perfil.obter_minha_foto(user=user))
        assert lida["fotoDataUrl"].startswith("data:image/jpeg;base64,")

        removida = asyncio.run(foto_perfil.remover_minha_foto(_FakeRequest(), user))
        assert removida == {"ok": True}
        assert db["aluno"]["a1"]["foto_perfil_storage"] is None
        eventos_remover = [e for e in db["evento_auditoria"].values() if e["acao"] == "foto_perfil_removida"]
        assert eventos_remover[0]["detalhe"]["por_titular"] is True

        # arquivo saiu do disco de verdade, não só a coluna
        assert not (tmp_path / "fotos-perfil" / "aluno" / "a1.jpg").exists()

    def test_coordenador_usa_a_mesma_rota_para_a_propria_conta(self, tmp_path, monkeypatch):
        db = self._db()
        monkeypatch.setattr(foto_perfil, "get_supabase", lambda: FakeCliente(db))
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        user = {"tipo": "coordenador", "sub": "c1"}

        asyncio.run(foto_perfil.salvar_minha_foto(_corpo_valido(), _FakeRequest(), user))
        assert db["usuario_coordenacao"]["c1"]["foto_perfil_storage"] == "fotos-perfil/coordenador/c1.jpg"
        # não vazou pro namespace do aluno
        assert db["aluno"]["a1"]["foto_perfil_storage"] is None

    def test_conteudo_base64_invalido_vira_422(self, tmp_path, monkeypatch):
        db = self._db()
        monkeypatch.setattr(foto_perfil, "get_supabase", lambda: FakeCliente(db))
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        corpo = _corpo_valido(base64_conteudo="isto não é base64 válido!!!")
        with pytest.raises(HTTPException) as exc:
            asyncio.run(foto_perfil.salvar_minha_foto(corpo, _FakeRequest(), {"tipo": "aluno", "aluno_id": "a1"}))
        assert exc.value.status_code == 422

    def test_bytes_que_nao_sao_a_imagem_declarada_vira_422(self, tmp_path, monkeypatch):
        """`content_type` passa na validação do Pydantic (é um dos aceitos),
        mas os bytes não são JPEG de verdade — pega na camada de storage."""
        db = self._db()
        monkeypatch.setattr(foto_perfil, "get_supabase", lambda: FakeCliente(db))
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        corpo = _corpo_valido(base64_conteudo=base64.b64encode(b"nao e uma imagem, so texto").decode())
        with pytest.raises(HTTPException) as exc:
            asyncio.run(foto_perfil.salvar_minha_foto(corpo, _FakeRequest(), {"tipo": "aluno", "aluno_id": "a1"}))
        assert exc.value.status_code == 422

    def test_remover_sem_foto_e_no_op(self, tmp_path, monkeypatch):
        db = self._db()
        monkeypatch.setattr(foto_perfil, "get_supabase", lambda: FakeCliente(db))
        resposta = asyncio.run(foto_perfil.remover_minha_foto(_FakeRequest(), {"tipo": "aluno", "aluno_id": "a1"}))
        assert resposta == {"ok": True}
        assert db.get("evento_auditoria", {}) == {}


# ─── visão da coordenação sobre a foto de um aluno ─────────────────────────


class TestFotoDoAlunoPelaCoordenacao:
    def _settings_local(self, tmp_path):
        return type("S", (), {
            "storage_dir": str(tmp_path), "storage_bucket": "sas-uploads",
            "jwt_secret_key": "x" * 32, "api_base_url": "http://localhost:8000",
        })()

    def test_404_para_aluno_inexistente(self, monkeypatch):
        db = {"aluno": {}}
        monkeypatch.setattr(alunos, "get_supabase", lambda: FakeCliente(db))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(alunos.foto_do_aluno("fantasma"))
        assert exc.value.status_code == 404

    def test_coordenacao_le_a_foto_do_aluno(self, tmp_path, monkeypatch):
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        caminho = storage.salvar_foto_perfil(
            entidade="aluno", entidade_id="a1", conteudo=_JPEG_1X1, content_type="image/jpeg"
        )
        db = {"aluno": {"a1": {"id": "a1", "foto_perfil_storage": caminho}}}
        monkeypatch.setattr(alunos, "get_supabase", lambda: FakeCliente(db))

        resultado = asyncio.run(alunos.foto_do_aluno("a1"))
        assert resultado["fotoDataUrl"].startswith("data:image/jpeg;base64,")

    def test_coordenacao_remove_foto_impropria_com_auditoria_diferenciada(self, tmp_path, monkeypatch):
        """`por_titular: False` é o que distingue, na auditoria, "o aluno tirou
        a própria foto" de "a coordenação tirou a foto de alguém"."""
        monkeypatch.setattr(storage, "get_settings", lambda: self._settings_local(tmp_path))
        caminho = storage.salvar_foto_perfil(
            entidade="aluno", entidade_id="a1", conteudo=_JPEG_1X1, content_type="image/jpeg"
        )
        db = {"aluno": {"a1": {"id": "a1", "foto_perfil_storage": caminho}}}
        monkeypatch.setattr(alunos, "get_supabase", lambda: FakeCliente(db))

        resultado = asyncio.run(
            alunos.remover_foto_do_aluno("a1", _FakeRequest(), coordenador={"sub": "c1"})
        )
        assert resultado == {"ok": True}
        assert db["aluno"]["a1"]["foto_perfil_storage"] is None
        assert not (tmp_path / "fotos-perfil" / "aluno" / "a1.jpg").exists()

        evento = next(e for e in db["evento_auditoria"].values() if e["acao"] == "foto_perfil_removida")
        assert evento["ator_tipo"] == "coordenador" and evento["ator_id"] == "c1"
        assert evento["detalhe"]["por_titular"] is False


class TestFotoDoCoordenadorPelaAdministracao:
    def test_404_para_conta_inexistente(self, monkeypatch):
        db = {"usuario_coordenacao": {}}
        monkeypatch.setattr(administracao, "get_supabase", lambda: FakeCliente(db))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(administracao.foto_do_coordenador("fantasma"))
        assert exc.value.status_code == 404

    def test_sem_foto_devolve_null(self, monkeypatch):
        db = {"usuario_coordenacao": {"c1": {"id": "c1", "foto_perfil_storage": None}}}
        monkeypatch.setattr(administracao, "get_supabase", lambda: FakeCliente(db))
        assert asyncio.run(administracao.foto_do_coordenador("c1")) == {"fotoDataUrl": None}


# ─── temFoto no login ──────────────────────────────────────────────────────
# Os três testes de aluno que ficavam aqui (login por matrícula, e o
# `/primeiro-acesso` devolvendo `temFoto` de quem já tinha conta) saíram em
# 04/09: a senha de aluno e a rota de primeiro acesso deixaram de existir
# (docs/35 §11.5). O `temFoto` do aluno continua sendo entregue — pelo token do
# SSO, montado em `routes/auth_canvas.py::_sessao_para` — e é lá que ele se
# prova agora.


class TestTemFotoNoLogin:
    def _conta(self, foto):
        from app import auth as auth_core

        return {
            "usuario_coordenacao": {
                "c1": {
                    "id": "c1", "nome": "Leo", "ativo": True, "email": "leo@exemplo.com",
                    "papel": "coordenador",
                    "senha_hash": auth_core.hash_senha("senhaSegura1"),
                    "foto_perfil_storage": foto,
                }
            }
        }

    def _login(self, monkeypatch, db):
        monkeypatch.setattr(auth, "get_supabase", lambda: FakeCliente(db))
        auth._tentativas_por_chave.clear()
        return asyncio.run(auth.login(
            auth.LoginBody(tipo="coordenador", usuario="leo@exemplo.com", senha="senhaSegura1"),
            _FakeRequest(),
        ))

    def test_coordenador_com_foto_recebe_temfoto_true(self, monkeypatch):
        resposta = self._login(monkeypatch, self._conta("fotos-perfil/coordenador/c1.jpg"))
        assert resposta["temFoto"] is True

    def test_coordenador_sem_foto_recebe_temfoto_false(self, monkeypatch):
        resposta = self._login(monkeypatch, self._conta(None))
        assert resposta["temFoto"] is False

    def test_aluno_do_sso_leva_temfoto_no_token(self, monkeypatch):
        """O que substituiu o login por matrícula: o `temFoto` do aluno viaja
        no JWT que o callback do Canvas devolve (o front o lê do fragmento)."""
        from jose import jwt

        from app import config
        from app.auth import ALGORITHM
        from app.routes import auth_canvas

        db = {"aluno": {"a1": {
            "id": "a1", "nome": "Ana", "ativo": True, "canvas_user_id": "300",
            "foto_perfil_storage": "fotos-perfil/aluno/a1.jpg",
        }}}
        token, tipo = auth_canvas._sessao_para(FakeCliente(db), "300")
        assert tipo == "aluno"
        payload = jwt.decode(token, config.get_settings().jwt_secret_key, algorithms=[ALGORITHM])
        assert payload["temFoto"] is True and payload["aluno_id"] == "a1"
