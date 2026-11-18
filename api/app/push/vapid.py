"""O cabeçalho VAPID — como o serviço de push sabe que o envio é do SAS (RFC 8292).

Um JWT ES256 curto, assinado com a chave do servidor, cujo `aud` é a ORIGEM do
endpoint (`https://fcm.googleapis.com`, não a URL inteira). O serviço confere a
assinatura contra a chave pública que o navegador recebeu ao se inscrever: um
envio com outra chave leva 403, e é por isso que inscrição não sobrevive à troca
de chave (app/push/chaves.py).

O `sub` é o contato que o fabricante usa se o nosso servidor se comportar mal.
Vai para a Google e para a Apple, então é o endereço do SITE, nunca o e-mail de
uma pessoa (docs/45 §2, regra 3).

Assinado com o `cryptography` direto, e não com o `python-jose`: o JWS ES256 quer
a assinatura crua (r‖s, 64 bytes), o `cryptography` devolve DER, e a conversão é
três linhas que dá para ler — melhor que confiar no que outra biblioteca faz por
dentro.
"""

from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from .chaves import ChaveVapid, b64url

#: Validade do token. A RFC 8292 §2 limita a 24 h; a Apple recusa `exp` longo
#: demais, e 12 h dá folga para relógio torto sem chegar perto do teto.
VALIDADE_SEGUNDOS = 12 * 3600


def audiencia(endpoint: str) -> str:
    partes = urlsplit(endpoint)
    return f"{partes.scheme}://{partes.netloc}"


def _jwt(claims: dict, chave: ec.EllipticCurvePrivateKey) -> str:
    cabecalho = b64url(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
    corpo = b64url(json.dumps(claims, separators=(",", ":")).encode())
    assinado = f"{cabecalho}.{corpo}".encode("ascii")
    r, s = decode_dss_signature(chave.sign(assinado, ec.ECDSA(hashes.SHA256())))
    return f"{cabecalho}.{corpo}.{b64url(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def cabecalho_authorization(endpoint: str, chave: ChaveVapid, contato: str, *, agora: float | None = None) -> str:
    """`vapid t=<jwt>, k=<chave pública>` — o esquema da RFC 8292 §3."""
    momento = int(agora if agora is not None else time.time())
    token = _jwt({"aud": audiencia(endpoint), "exp": momento + VALIDADE_SEGUNDOS, "sub": contato}, chave.privada)
    return f"vapid t={token}, k={chave.publica_b64url}"
