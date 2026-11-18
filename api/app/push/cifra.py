"""O corpo cifrado de uma mensagem Web Push — `aes128gcm` (RFC 8188 + RFC 8291).

O fabricante (Google, Apple, Mozilla, Microsoft) transporta o corpo e NÃO consegue
lê-lo: a chave nasce de um ECDH entre uma chave efêmera nossa e a chave pública do
aparelho, misturada ao segredo `auth` que só o navegador e nós temos. É a razão
de o docs/45 §2 poder dizer que o conteúdo vai cifrado de ponta a ponta.

A composição, passo a passo, é a da RFC 8291 §3.4 e Apêndice A — e os nomes das
variáveis aqui são os de lá, para conferir lendo os dois lado a lado. O teste usa
o vetor do Apêndice A (sal e chave efêmera fixos) e compara o corpo byte a byte.

O HKDF está desdobrado à mão — o *extract* é `_hmac_sha256`, o *expand* é o
`HKDFExpand` — em vez de usar o `HKDF` inteiro, porque a RFC publica os valores
intermediários (PRK_key, IKM, PRK, CEK, NONCE) e é por eles que se acha onde uma
composição errada diverge.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDFExpand

#: Tamanho do registro declarado no cabeçalho. Com uma mensagem só, ele só
#: precisa ser maior que o texto + 17 (delimitador e tag do GCM); 4096 é o que
#: a RFC 8291 usa e o que os navegadores esperam.
TAMANHO_DO_REGISTRO = 4096

#: O serviço de push aceita até 4096 bytes de CORPO cifrado (RFC 8030 §7.2).
#: Tirando cabeçalho (16 + 4 + 1 + 65 = 86) e tag + delimitador (17), sobram
#: 3993 de texto. Nossa notificação tem menos de 300; isto é a trava.
LIMITE_DO_TEXTO = 4096 - 86 - 17


class CorpoGrandeDemais(ValueError):
    pass


def _hmac_sha256(chave: bytes, dados: bytes) -> bytes:
    h = hmac.HMAC(chave, hashes.SHA256())
    h.update(dados)
    return h.finalize()


def _ponto(chave: ec.EllipticCurvePublicKey) -> bytes:
    return chave.public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)


def cifrar(
    texto: bytes,
    *,
    ua_public: bytes,
    auth_secret: bytes,
    salt: bytes | None = None,
    as_private: ec.EllipticCurvePrivateKey | None = None,
) -> bytes:
    """Devolve o corpo pronto para o POST (`Content-Encoding: aes128gcm`).

    `ua_public` é a `p256dh` do aparelho (65 bytes); `auth_secret`, a `auth`
    (16 bytes). `salt` e `as_private` só são passados pelo teste do vetor da
    RFC — em produção os dois são sorteados a cada mensagem, e reaproveitá-los
    repetiria o nonce do GCM.
    """
    if len(texto) > LIMITE_DO_TEXTO:
        raise CorpoGrandeDemais(f"{len(texto)} bytes; o limite é {LIMITE_DO_TEXTO}")
    if len(auth_secret) != 16:
        raise ValueError("auth_secret precisa ter 16 bytes")

    ua_chave = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_public)
    as_private = as_private or ec.generate_private_key(ec.SECP256R1())
    as_public = _ponto(as_private.public_key())
    salt = salt if salt is not None else os.urandom(16)

    # RFC 8291 §3.3 — o segredo compartilhado, amarrado às duas chaves públicas
    # e ao segredo de autenticação do aparelho.
    ecdh_secret = as_private.exchange(ec.ECDH(), ua_chave)
    key_info = b"WebPush: info\x00" + ua_public + as_public
    prk_key = _hmac_sha256(auth_secret, ecdh_secret)
    ikm = HKDFExpand(algorithm=hashes.SHA256(), length=32, info=key_info).derive(prk_key)

    # RFC 8188 §2.2 e §2.3 — chave de conteúdo e nonce, do mesmo PRK.
    prk = _hmac_sha256(salt, ikm)
    cek = HKDFExpand(algorithm=hashes.SHA256(), length=16, info=b"Content-Encoding: aes128gcm\x00").derive(prk)
    nonce = HKDFExpand(algorithm=hashes.SHA256(), length=12, info=b"Content-Encoding: nonce\x00").derive(prk)

    # Um registro só, e por isso o delimitador é 0x02 ("último registro"), sem
    # preenchimento. O tamanho do texto vaza para quem transporta — aceitável:
    # é uma notificação curta, e o docs/45 §2 já trata o tamanho como visível.
    cifrado = AESGCM(cek).encrypt(nonce, texto + b"\x02", None)

    cabecalho = salt + TAMANHO_DO_REGISTRO.to_bytes(4, "big") + bytes([len(as_public)]) + as_public
    return cabecalho + cifrado
