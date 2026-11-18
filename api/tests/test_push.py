"""Notificação push no aparelho (docs/45) — a capacidade, sem evento nenhum.

O que este arquivo prova, de baixo para cima:

  1. A cifra bate BYTE A BYTE com o vetor do Apêndice A da RFC 8291. É a prova de
     que o navegador vai conseguir decifrar — o fabricante não confere a cifra, só
     a assinatura, então um erro aqui passaria pelo 201 e sumiria no aparelho.
  2. O JWT VAPID tem a assinatura ES256 que a chave pública confere.
  3. A lista fechada de hosts recusa todo destino que não seja serviço de push
     (o SSRF do docs/45 §5.3).
  4. O envio lê cada resposta do fabricante do jeito certo — e, em particular,
     erro NOSSO (403) não conta contra o aparelho de ninguém.
  5. As rotas: dono só do JWT, cantina barrada, troca de dono no computador
     compartilhado, revogação só do que é seu, teto do botão de teste.

Mesma convenção de test_foto_perfil.py: handlers chamados direto, `FakeCliente`
no lugar do PostgREST. O fabricante é um `httpx.MockTransport`.
"""

from __future__ import annotations

import base64
import json
import os
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand
from fastapi import HTTPException

from app.push import chaves, cifra, endpoints, envio, vapid
from app.routes import push as rotas
from tests.fake_postgrest import FakeCliente


def _b64(texto: str) -> bytes:
    return chaves.de_b64url(texto)


def _ponto(chave: ec.EllipticCurvePublicKey) -> bytes:
    return chave.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def _hmac(chave: bytes, dados: bytes) -> bytes:
    h = hmac.HMAC(chave, hashes.SHA256())
    h.update(dados)
    return h.finalize()


def decifrar(corpo: bytes, ua_private: ec.EllipticCurvePrivateKey, auth_secret: bytes) -> bytes:
    """O lado do NAVEGADOR (RFC 8291 §3.4), para a ida e volta."""
    salt, idlen = corpo[:16], corpo[20]
    as_public = corpo[21 : 21 + idlen]
    cifrado = corpo[21 + idlen :]
    ua_public = _ponto(ua_private.public_key())
    ecdh = ua_private.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), as_public))
    ikm = HKDFExpand(hashes.SHA256(), 32, b"WebPush: info\x00" + ua_public + as_public).derive(_hmac(auth_secret, ecdh))
    prk = _hmac(salt, ikm)
    cek = HKDFExpand(hashes.SHA256(), 16, b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDFExpand(hashes.SHA256(), 12, b"Content-Encoding: nonce\x00").derive(prk)
    texto = AESGCM(cek).decrypt(nonce, cifrado, None)
    assert texto.endswith(b"\x02"), "delimitador de último registro"
    return texto[:-1]


class Aparelho:
    """Um navegador de mentira: par de chaves e segredo, como o `PushManager` gera."""

    def __init__(self, endpoint: str = "https://fcm.googleapis.com/fcm/send/abc123"):
        self.privada = ec.generate_private_key(ec.SECP256R1())
        self.auth = os.urandom(16)
        self.endpoint = endpoint

    @property
    def p256dh(self) -> str:
        return chaves.b64url(_ponto(self.privada.public_key()))

    @property
    def auth_b64(self) -> str:
        return chaves.b64url(self.auth)

    def corpo(self, plataforma: str = "android") -> rotas.InscricaoBody:
        return rotas.InscricaoBody(
            endpoint=self.endpoint,
            chaves=rotas.ChavesDaInscricao(p256dh=self.p256dh, auth=self.auth_b64),
            plataforma=plataforma,
            descricao_aparelho="Android · Chrome",
        )


CHAVE = chaves.ler_chave(chaves.b64url(bytes(range(1, 33))))


# ─── 1. Cifra ──────────────────────────────────────────────────────────────


class TestCifra:
    def test_bate_com_o_vetor_da_rfc_8291(self):
        as_private = ec.derive_private_key(
            int.from_bytes(_b64("yfWPiYE-n46HLnH0KqZOF1fJJU3MYrct3AELtAQ-oRw"), "big"), ec.SECP256R1()
        )
        corpo = cifra.cifrar(
            _b64("V2hlbiBJIGdyb3cgdXAsIEkgd2FudCB0byBiZSBhIHdhdGVybWVsb24"),
            ua_public=_b64("BCVxsr7N_eNgVRqvHtD0zTZsEc6-VV-JvLexhqUzORcxaOzi6-AYWXvTBHm4bjyPjs7Vd8pZGH6SRpkNtoIAiw4"),
            auth_secret=_b64("BTBZMqHH6r4Tts7J_aSIgg"),
            salt=_b64("DGv6ra1nlYgDCS1FRnbzlw"),
            as_private=as_private,
        )
        # Cabeçalho de 86 bytes + texto cifrado, como a RFC os imprime no Apêndice A.
        esperado = _b64(
            "DGv6ra1nlYgDCS1FRnbzlwAAEABBBP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27ml"
            "mlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8"
        ) + _b64(
            "8pfeW0KbunFT06SuDKoJH9Ql87S1QUrdirN6GcG7sFz1y1sqLgVi1VhjVkHsUoEs"
            "bI_0LpXMuGvnzQ"
        )
        assert corpo == esperado

    def test_ida_e_volta_com_chaves_sorteadas(self):
        aparelho = Aparelho()
        corpo = cifra.cifrar(b'{"titulo":"oi"}', ua_public=_b64(aparelho.p256dh), auth_secret=aparelho.auth)
        assert decifrar(corpo, aparelho.privada, aparelho.auth) == b'{"titulo":"oi"}'

    def test_sal_e_chave_efemera_mudam_a_cada_mensagem(self):
        aparelho = Aparelho()
        um = cifra.cifrar(b"x", ua_public=_b64(aparelho.p256dh), auth_secret=aparelho.auth)
        outro = cifra.cifrar(b"x", ua_public=_b64(aparelho.p256dh), auth_secret=aparelho.auth)
        assert um[:16] != outro[:16]
        assert um[21:86] != outro[21:86]

    def test_recusa_texto_maior_que_o_serviço_aceita(self):
        aparelho = Aparelho()
        with pytest.raises(cifra.CorpoGrandeDemais):
            cifra.cifrar(b"x" * (cifra.LIMITE_DO_TEXTO + 1), ua_public=_b64(aparelho.p256dh), auth_secret=aparelho.auth)
        corpo = cifra.cifrar(b"x" * cifra.LIMITE_DO_TEXTO, ua_public=_b64(aparelho.p256dh), auth_secret=aparelho.auth)
        assert len(corpo) == 4096


# ─── 2. Chave e VAPID ──────────────────────────────────────────────────────


class TestChave:
    def test_publica_derivada_e_ponto_nao_comprimido(self):
        publica = _b64(CHAVE.publica_b64url)
        assert len(publica) == 65 and publica[0] == 0x04

    @pytest.mark.parametrize("texto", ["", "!!!", chaves.b64url(b"\x01" * 31), chaves.b64url(b"\x00" * 32)])
    def test_recusa_o_que_nao_e_chave(self, texto):
        with pytest.raises(chaves.ChaveVapidInvalida):
            chaves.ler_chave(texto)

    def test_o_script_gera_uma_chave_que_o_servidor_le(self):
        from scripts.gerar_chave_vapid import gerar

        privada, publica = gerar()
        assert chaves.ler_chave(privada).publica_b64url == publica


class TestVapid:
    def test_jwt_assinado_confere_com_a_chave_publica(self):
        endpoint = "https://web.push.apple.com/QGuQyavXutnMH_abc"
        cabecalho = vapid.cabecalho_authorization(endpoint, CHAVE, "https://portalsas.online", agora=1_000_000)
        assert cabecalho.startswith("vapid t=")
        token = cabecalho.split("t=", 1)[1].split(",", 1)[0]
        k = cabecalho.split("k=", 1)[1]
        assert k == CHAVE.publica_b64url

        h, c, s = token.split(".")
        assert json.loads(_b64(h)) == {"typ": "JWT", "alg": "ES256"}
        claims = json.loads(_b64(c))
        # `aud` é a ORIGEM, não a URL inteira (RFC 8292 §2).
        assert claims == {"aud": "https://web.push.apple.com", "exp": 1_000_000 + 12 * 3600, "sub": "https://portalsas.online"}
        assinatura = _b64(s)
        assert len(assinatura) == 64
        der = encode_dss_signature(int.from_bytes(assinatura[:32], "big"), int.from_bytes(assinatura[32:], "big"))
        publica = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), _b64(k))
        publica.verify(der, f"{h}.{c}".encode(), ec.ECDSA(hashes.SHA256()))  # levanta se não conferir


# ─── 3. Lista fechada de hosts ─────────────────────────────────────────────


class TestEndpoints:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "https://fcm.googleapis.com/fcm/send/dpH5lCsTSSM:APA91b",
            "https://web.push.apple.com/QGuQyavXutnMH_abc",
            "https://updates.push.services.mozilla.com/wpush/v2/gAAAAA",
            "https://wns2-bl2p.notify.windows.com/w/?token=BQYAAA",
            "https://FCM.googleapis.com:443/fcm/send/x",
        ],
    )
    def test_aceita_os_servicos_dos_navegadores(self, endpoint):
        assert endpoints.validar(endpoint) == endpoint

    @pytest.mark.parametrize(
        "endpoint",
        [
            "http://fcm.googleapis.com/fcm/send/x",  # sem TLS
            "https://postgrest:3000/aluno",  # a rede do compose — o SSRF
            "https://localhost/x",
            "https://127.0.0.1/x",
            "https://169.254.169.254/latest/meta-data",
            "https://fcm.googleapis.com:8443/x",  # porta trocada
            "https://user:senha@fcm.googleapis.com/x",
            "https://fcm.googleapis.com.evil.com/x",
            "https://evilnotify.windows.com/x",  # sufixo sem o ponto
            "https://notify.windows.com/x",  # o sufixo sozinho não é host
            "javascript:alert(1)",
            "",
            "https://fcm.googleapis.com/" + "x" * 3000,
        ],
    )
    def test_recusa_todo_o_resto(self, endpoint):
        with pytest.raises(endpoints.EndpointRecusado):
            endpoints.validar(endpoint)


# ─── 4. Notificação e leitura das respostas ────────────────────────────────


class TestNotificacao:
    @pytest.mark.parametrize("url", ["https://evil.com", "//evil.com/x", "/\\evil.com", "javascript:alert(1)", "/a\nb"])
    def test_url_so_interna(self, url):
        with pytest.raises(ValueError):
            envio.Notificacao(tipo="teste", titulo="t", corpo="c", url=url)

    def test_texto_curto_e_legivel_pelo_service_worker(self):
        n = envio.Notificacao(tipo="teste", titulo="Saiu o resultado do P3", corpo="Toque para ver.", url="/provas", tag="resultado")
        assert json.loads(n.texto()) == {"titulo": "Saiu o resultado do P3", "corpo": "Toque para ver.", "url": "/provas", "tag": "resultado"}
        assert len(n.texto()) < 300

    @pytest.mark.parametrize(
        ("campo", "valor"),
        [("titulo", "x" * 81), ("titulo", "  "), ("corpo", "x" * 201), ("tipo", "Com Espaço"), ("topico", "x" * 33), ("ttl_segundos", -1)],
    )
    def test_limites(self, campo, valor):
        dados = {"tipo": "teste", "titulo": "t", "corpo": "c", campo: valor}
        with pytest.raises(ValueError):
            envio.Notificacao(**dados)

    @pytest.mark.parametrize(
        ("status", "leitura"),
        [(201, "ok"), (200, "ok"), (404, "morta"), (410, "morta"), (429, "transitoria"), (502, "transitoria"),
         (None, "transitoria"), (400, "erro_nosso"), (403, "erro_nosso"), (413, "erro_nosso")],
    )
    def test_le_cada_resposta_do_fabricante(self, status, leitura):
        assert envio.ler_status(status) == leitura


# ─── 5. O envio, com o fabricante falso ────────────────────────────────────


@pytest.fixture
def push_ligado(monkeypatch):
    monkeypatch.setattr(envio, "chave_do_servidor", lambda: CHAVE)
    monkeypatch.setattr(rotas, "chave_do_servidor", lambda: CHAVE)
    monkeypatch.setattr(rotas, "_testes", defaultdict(deque))


def _linha(aparelho: Aparelho, **extra) -> dict:
    return {
        "id": extra.pop("id", f"i-{aparelho.endpoint[-6:]}"),
        "endpoint": aparelho.endpoint,
        "chave_p256dh": aparelho.p256dh,
        "chave_auth": aparelho.auth_b64,
        "plataforma": "android",
        "aluno_id": "a1",
        "usuario_coordenacao_id": None,
        "falhas_seguidas": 0,
        "ultimo_envio_ok_em": None,
        "criada_em": datetime.now(UTC).isoformat(),
        **extra,
    }


def _fabricante(respostas: dict[str, int], recebidos: list[httpx.Request] | None = None) -> httpx.Client:
    def tratar(req: httpx.Request) -> httpx.Response:
        if recebidos is not None:
            recebidos.append(req)
        return httpx.Response(respostas.get(str(req.url), 201), text="motivo do fabricante")

    return httpx.Client(transport=httpx.MockTransport(tratar))


N = envio.Notificacao(tipo="teste", titulo="Avisos do SAS ligados", corpo="Toque para abrir.", url="/", tag="teste", topico="teste")


class TestEnvio:
    def test_entregue_e_decifravel_no_aparelho(self, push_ligado):
        aparelho = Aparelho()
        db = {"inscricao_push": {"i1": _linha(aparelho, id="i1", falhas_seguidas=3)}}
        recebidos: list[httpx.Request] = []
        r = envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({}, recebidos))

        assert r.como_dict() == {"tentadas": 1, "entregues": 1, "removidas": 0, "falhas": 0}
        req = recebidos[0]
        assert req.headers["Content-Encoding"] == "aes128gcm"
        assert req.headers["TTL"] == "86400"
        assert req.headers["Topic"] == "teste"
        assert req.headers["Authorization"].startswith("vapid t=")
        assert json.loads(decifrar(req.content, aparelho.privada, aparelho.auth))["url"] == "/"
        linha = db["inscricao_push"]["i1"]
        assert linha["falhas_seguidas"] == 0 and linha["ultimo_status_http"] == 201 and linha["ultimo_envio_ok_em"]

    def test_so_os_aparelhos_do_dono(self, push_ligado):
        meu, alheio = Aparelho("https://fcm.googleapis.com/fcm/send/meu"), Aparelho("https://fcm.googleapis.com/fcm/send/alheio")
        db = {"inscricao_push": {"i1": _linha(meu, id="i1"), "i2": _linha(alheio, id="i2", aluno_id="a2")}}
        recebidos: list[httpx.Request] = []
        envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({}, recebidos))
        assert [str(r.url) for r in recebidos] == [meu.endpoint]

    @pytest.mark.parametrize("status", [404, 410])
    def test_inscricao_morta_e_apagada(self, push_ligado, status):
        aparelho = Aparelho()
        db = {"inscricao_push": {"i1": _linha(aparelho, id="i1")}}
        r = envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({aparelho.endpoint: status}))
        assert r.removidas == 1 and db["inscricao_push"] == {}

    def test_erro_nosso_nao_conta_contra_o_aparelho(self, push_ligado):
        """Chave VAPID errada dá 403 em TODO envio. Contar isso como falha do
        aparelho apagaria, em dez envios, a inscrição de todo mundo."""
        aparelho = Aparelho()
        db = {"inscricao_push": {"i1": _linha(aparelho, id="i1", falhas_seguidas=9)}}
        r = envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({aparelho.endpoint: 403}))
        linha = db["inscricao_push"]["i1"]
        assert r.falhas == 1 and r.removidas == 0
        assert linha["falhas_seguidas"] == 9 and linha["ultimo_status_http"] == 403

    def test_transitorio_conta_falha(self, push_ligado):
        aparelho = Aparelho()
        db = {"inscricao_push": {"i1": _linha(aparelho, id="i1", falhas_seguidas=2)}}
        envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({aparelho.endpoint: 503}))
        assert db["inscricao_push"]["i1"]["falhas_seguidas"] == 3

    def test_desiste_com_falhas_demais_e_nada_entregue_ha_uma_semana(self, push_ligado):
        antigo = (datetime.now(UTC) - timedelta(days=8)).isoformat()
        recente = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        velho, novo = Aparelho("https://fcm.googleapis.com/fcm/send/velho"), Aparelho("https://fcm.googleapis.com/fcm/send/novo")
        db = {"inscricao_push": {
            "i1": _linha(velho, id="i1", falhas_seguidas=9, ultimo_envio_ok_em=antigo),
            "i2": _linha(novo, id="i2", falhas_seguidas=9, ultimo_envio_ok_em=recente),
        }}
        envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({velho.endpoint: 503, novo.endpoint: 503}))
        assert list(db["inscricao_push"]) == ["i2"]
        assert db["inscricao_push"]["i2"]["falhas_seguidas"] == 10

    def test_linha_com_host_fora_da_lista_nao_recebe_post(self, push_ligado):
        """A rota já recusa — mas a linha pode ter entrado por outro caminho."""
        intrusa = Aparelho("https://postgrest:3000/aluno")
        db = {"inscricao_push": {"i1": _linha(intrusa, id="i1")}}
        recebidos: list[httpx.Request] = []
        r = envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({}, recebidos))
        assert recebidos == [] and r.removidas == 1

    def test_sem_chave_o_envio_recusa(self, monkeypatch):
        monkeypatch.setattr(envio, "chave_do_servidor", lambda: None)
        db = {"inscricao_push": {"i1": _linha(Aparelho(), id="i1")}}
        with pytest.raises(RuntimeError):
            envio.enviar_para_dono(FakeCliente(db), envio.Dono("aluno_id", "a1"), N, http=_fabricante({}))


# ─── 6. Rotas ──────────────────────────────────────────────────────────────


class _Req:
    client = type("C", (), {"host": "203.0.113.7"})()


ALUNO = {"tipo": "aluno", "sub": "u-aluno", "aluno_id": "a1"}
OUTRO_ALUNO = {"tipo": "aluno", "sub": "u-outro", "aluno_id": "a2"}
COORDENADOR = {"tipo": "coordenador", "sub": "c1", "papel": "coordenador"}
CANTINA = {"tipo": "cantina", "sub": "k1"}


@pytest.fixture
def db(monkeypatch):
    dados: dict = {"inscricao_push": {}}
    monkeypatch.setattr(rotas, "get_supabase", lambda: FakeCliente(dados))
    return dados


class TestRotas:
    def test_configuracao(self, push_ligado):
        assert rotas.configuracao(ALUNO) == {"ativo": True, "chavePublica": CHAVE.publica_b64url}
        assert rotas.configuracao(COORDENADOR)["ativo"] is True
        assert rotas.configuracao(CANTINA) == {"ativo": False, "chavePublica": None}

    def test_configuracao_sem_chave(self, monkeypatch):
        monkeypatch.setattr(rotas, "chave_do_servidor", lambda: None)
        assert rotas.configuracao(ALUNO) == {"ativo": False, "chavePublica": None}

    @pytest.mark.parametrize("usuario", [CANTINA, {"tipo": "desconhecido", "sub": "x"}, {"tipo": "aluno", "sub": "x"}])
    def test_fail_closed_por_tipo(self, push_ligado, db, usuario):
        aparelho = Aparelho()
        for chamada in (
            lambda: rotas.inscrever(aparelho.corpo(), _Req(), usuario),
            lambda: rotas.listar(usuario),
            lambda: rotas.revogar("00000000-0000-0000-0000-000000000000", _Req(), usuario),
            lambda: rotas.desativar_neste_aparelho(rotas.RemocaoBody(endpoint=aparelho.endpoint), _Req(), usuario),
            lambda: rotas.testar(usuario),
        ):
            with pytest.raises(HTTPException) as erro:
                chamada()
            assert erro.value.status_code == 403
        assert db["inscricao_push"] == {}

    def test_inscreve_e_o_dono_vem_do_jwt(self, push_ligado, db):
        resp = rotas.inscrever(Aparelho().corpo(), _Req(), ALUNO)
        linha = db["inscricao_push"][resp["id"]]
        assert linha["aluno_id"] == "a1" and linha["usuario_coordenacao_id"] is None
        evento = next(iter(db["evento_auditoria"].values()))
        assert evento["acao"] == "push_aparelho_ativado"
        assert "endpoint" not in json.dumps(evento["detalhe"])

    def test_coordenacao_inscreve_na_propria_coluna(self, push_ligado, db):
        resp = rotas.inscrever(Aparelho().corpo("desktop"), _Req(), COORDENADOR)
        linha = db["inscricao_push"][resp["id"]]
        assert linha["usuario_coordenacao_id"] == "c1" and linha["aluno_id"] is None

    def test_ativar_de_novo_nao_duplica_nem_audita_de_novo(self, push_ligado, db):
        aparelho = Aparelho()
        um = rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        outro = rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        assert um == outro and len(db["inscricao_push"]) == 1
        assert len(db["evento_auditoria"]) == 1

    def test_confirmar_atualiza_so_o_que_ja_e_seu(self, push_ligado, db):
        aparelho = Aparelho()
        resp = rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        db["inscricao_push"][resp["id"]]["vista_em"] = "2026-01-01T00:00:00+00:00"
        assert rotas.confirmar(aparelho.corpo(), ALUNO) == {"registrada": True, "id": resp["id"]}
        assert db["inscricao_push"][resp["id"]]["vista_em"] > "2026-01-01"

    def test_confirmar_nunca_cria(self, push_ligado, db):
        """O aparelho revogado na lista de OUTRO aparelho não pode voltar sozinho."""
        assert rotas.confirmar(Aparelho().corpo(), ALUNO) == {"registrada": False, "id": None}
        assert db["inscricao_push"] == {}

    def test_confirmar_nunca_transfere(self, push_ligado, db):
        """Quem entra depois num computador compartilhado não herda os avisos de quem saiu."""
        aparelho = Aparelho()
        rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        assert rotas.confirmar(aparelho.corpo(), OUTRO_ALUNO) == {"registrada": False, "id": None}
        (linha,) = db["inscricao_push"].values()
        assert linha["aluno_id"] == "a1"

    def test_confirmar_cantina_da_403(self, push_ligado, db):
        with pytest.raises(HTTPException) as erro:
            rotas.confirmar(Aparelho().corpo(), CANTINA)
        assert erro.value.status_code == 403

    def test_computador_compartilhado_troca_o_dono(self, push_ligado, db):
        aparelho = Aparelho()
        rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        rotas.inscrever(aparelho.corpo(), _Req(), COORDENADOR)
        (linha,) = db["inscricao_push"].values()
        assert linha["usuario_coordenacao_id"] == "c1" and linha["aluno_id"] is None
        assert rotas.listar(ALUNO) == {"aparelhos": []}

    @pytest.mark.parametrize(
        "endpoint", ["https://postgrest:3000/aluno", "http://fcm.googleapis.com/x", "https://exemplo.com/push"]
    )
    def test_recusa_endpoint_fora_da_lista(self, push_ligado, db, endpoint):
        with pytest.raises(HTTPException) as erro:
            rotas.inscrever(Aparelho(endpoint).corpo(), _Req(), ALUNO)
        assert erro.value.status_code == 422 and db["inscricao_push"] == {}

    def test_recusa_chave_que_nao_e_ponto_da_curva(self, push_ligado, db):
        corpo = Aparelho().corpo()
        corpo.chaves.p256dh = chaves.b64url(b"\x04" + b"\x01" * 64)
        with pytest.raises(HTTPException) as erro:
            rotas.inscrever(corpo, _Req(), ALUNO)
        assert erro.value.status_code == 422

    def test_inscrever_sem_chave_no_servidor_da_503(self, monkeypatch, db):
        monkeypatch.setattr(rotas, "chave_do_servidor", lambda: None)
        with pytest.raises(HTTPException) as erro:
            rotas.inscrever(Aparelho().corpo(), _Req(), ALUNO)
        assert erro.value.status_code == 503

    def test_listar_sem_endpoint_nem_chaves(self, push_ligado, db):
        rotas.inscrever(Aparelho().corpo(), _Req(), ALUNO)
        (aparelho,) = rotas.listar(ALUNO)["aparelhos"]
        assert set(aparelho) == {"id", "plataforma", "descricao", "criadaEm", "vistaEm", "ultimoEnvioOkEm", "ultimoStatusHttp"}

    def test_revogar_so_o_que_e_seu(self, push_ligado, db):
        meu = rotas.inscrever(Aparelho("https://fcm.googleapis.com/fcm/send/meu").corpo(), _Req(), ALUNO)["id"]
        alheio = rotas.inscrever(Aparelho("https://fcm.googleapis.com/fcm/send/alheio").corpo(), _Req(), OUTRO_ALUNO)["id"]
        with pytest.raises(HTTPException) as erro:
            rotas.revogar(alheio, _Req(), ALUNO)
        assert erro.value.status_code == 404 and alheio in db["inscricao_push"]
        assert rotas.revogar(meu, _Req(), ALUNO) == {"ok": True}
        assert meu not in db["inscricao_push"]

    def test_revogar_id_que_nao_e_uuid_da_404_e_nao_500(self, push_ligado, db):
        with pytest.raises(HTTPException) as erro:
            rotas.revogar("nao-e-uuid", _Req(), ALUNO)
        assert erro.value.status_code == 404

    def test_desativar_neste_aparelho(self, push_ligado, db):
        aparelho = Aparelho()
        rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        corpo = rotas.RemocaoBody(endpoint=aparelho.endpoint)
        assert rotas.desativar_neste_aparelho(corpo, _Req(), OUTRO_ALUNO) == {"removida": False}
        assert rotas.desativar_neste_aparelho(corpo, _Req(), ALUNO) == {"removida": True}
        assert db["inscricao_push"] == {}

    def test_teste_manda_e_tem_teto(self, push_ligado, db, monkeypatch):
        aparelho = Aparelho()
        rotas.inscrever(aparelho.corpo(), _Req(), ALUNO)
        rotas.inscrever(Aparelho("https://fcm.googleapis.com/fcm/send/alheio").corpo(), _Req(), OUTRO_ALUNO)
        recebidos: list[httpx.Request] = []
        cliente_real = httpx.Client
        monkeypatch.setattr(
            envio.httpx, "Client",
            lambda **kw: cliente_real(transport=httpx.MockTransport(lambda r: (recebidos.append(r), httpx.Response(201))[1]), **kw),
        )

        for _ in range(rotas.TESTES_POR_HORA):
            assert rotas.testar(ALUNO) == {"tentadas": 1, "entregues": 1, "removidas": 0, "falhas": 0}
        with pytest.raises(HTTPException) as erro:
            rotas.testar(ALUNO)
        assert erro.value.status_code == 429
        assert {str(r.url) for r in recebidos} == {aparelho.endpoint}
        texto = json.loads(decifrar(recebidos[0].content, aparelho.privada, aparelho.auth))
        assert texto["tag"] == "teste" and texto["url"] == "/"
        assert recebidos[0].headers["TTL"] == "600"


# ─── 7. A guarda de subida ─────────────────────────────────────────────────


class TestGuardaDeSubida:
    def _settings(self, **push):
        from app.config import Settings

        return Settings(
            app_env="production", jwt_secret_key="x" * 40, coordenador_senha="forte-o-bastante",
            scheduler_secret="s", cors_allow_origins="https://portalsas.online", **push,
        )

    def test_chave_vazia_sobe(self):
        from app.main import _validar_configuracao

        _validar_configuracao(self._settings())

    def test_chave_valida_sobe(self):
        from app.main import _validar_configuracao

        _validar_configuracao(self._settings(push_vapid_chave_privada=chaves.b64url(bytes(range(1, 33)))))

    @pytest.mark.parametrize(
        "push",
        [
            {"push_vapid_chave_privada": "nao-e-chave"},
            {"push_vapid_chave_privada": base64.b64encode(b"x" * 32).decode(), "push_vapid_contato": "portalsas.online"},
            {"push_vapid_chave_privada": chaves.b64url(bytes(range(1, 33))), "push_vapid_contato": "https://localhost"},
        ],
    )
    def test_chave_ou_contato_torto_nao_sobe(self, push):
        from app.main import _validar_configuracao

        with pytest.raises(RuntimeError, match="PUSH_VAPID"):
            _validar_configuracao(self._settings(**push))
