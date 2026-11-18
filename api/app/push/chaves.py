"""A chave VAPID do servidor — o par P-256 que identifica o SAS aos serviços de push.

Uma variável só, `PUSH_VAPID_CHAVE_PRIVADA`: os 32 bytes do escalar privado em
base64url (o formato que `scripts/gerar_chave_vapid.py` imprime). A pública é
DERIVADA dela, então não existe par descasado para um deploy errar.

⚠️ **Trocar a chave mata todas as inscrições** (docs/45 §5.1). Cada inscrição nasce
amarrada à chave pública que o navegador recebeu em `applicationServerKey`; com
outra chave, o serviço de push recusa o envio (403) e todo aparelho precisa
ativar de novo. Trate como permanente e guarde junto dos outros segredos.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ..config import get_settings


def b64url(dados: bytes) -> str:
    """base64url SEM `=` — a forma que Web Push usa em todo lugar (RFC 8291 §2)."""
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def de_b64url(texto: str) -> bytes:
    """Aceita com ou sem `=`. O `PushSubscription.toJSON()` dos navegadores manda sem."""
    texto = texto.strip()
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


class ChaveVapidInvalida(ValueError):
    """A variável está preenchida e não é uma chave P-256 utilizável."""


@dataclass(frozen=True)
class ChaveVapid:
    privada: ec.EllipticCurvePrivateKey
    #: Ponto não comprimido (65 bytes, começa em 0x04) em base64url: é o
    #: `applicationServerKey` do navegador e o `k=` do cabeçalho Authorization.
    publica_b64url: str


def ler_chave(texto: str) -> ChaveVapid:
    """Interpreta o valor da variável. Levanta `ChaveVapidInvalida` com motivo legível."""
    try:
        bruto = de_b64url(texto)
    except (ValueError, TypeError) as erro:
        raise ChaveVapidInvalida("não é base64url") from erro
    if len(bruto) != 32:
        raise ChaveVapidInvalida(f"tem {len(bruto)} bytes; a chave privada P-256 tem 32")
    escalar = int.from_bytes(bruto, "big")
    try:
        privada = ec.derive_private_key(escalar, ec.SECP256R1())
    except ValueError as erro:
        # Zero ou um valor acima da ordem da curva.
        raise ChaveVapidInvalida("não é um escalar válido da curva P-256") from erro
    publica = privada.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return ChaveVapid(privada=privada, publica_b64url=b64url(publica))


@lru_cache
def chave_do_servidor() -> ChaveVapid | None:
    """A chave configurada, ou `None` — e `None` quer dizer push DESLIGADO.

    Chave ilegível não chega aqui em produção: `main._validar_configuracao`
    recusa subir antes. Em dev, ela também levanta, para o erro aparecer na hora
    e não como um "push desligado" que ninguém entende.
    """
    texto = get_settings().push_vapid_chave_privada
    if not texto:
        return None
    return ler_chave(texto)
