"""Link de descadastro do rodapé — o que foi prometido à AWS no caso do SES.

Sem login e sem estado novo: o endereço vem na URL e a assinatura HMAC prova
que o link foi emitido por nós. Clicar grava em `email_invalido` com motivo
'descadastro', e a audiência da varredura seguinte já não o inclui.
"""

from __future__ import annotations

import hashlib
import hmac
from urllib.parse import quote

from ..config import get_settings
from .supressao import normalizar

_TAMANHO_TOKEN = 16   # 64 bits em hex — o que o link protege é um opt-out


def gerar_token(endereco: str) -> str:
    segredo = get_settings().segredo_lembrete.encode()
    assinatura = hmac.new(segredo, normalizar(endereco).encode(), hashlib.sha256)
    return assinatura.hexdigest()[:_TAMANHO_TOKEN]


def token_valido(endereco: str, token: str) -> bool:
    # compare_digest: comparação em tempo constante, mesmo padrão do resto do
    # auth do projeto.
    return hmac.compare_digest(gerar_token(endereco), (token or "").strip())


def montar_link(endereco: str) -> str:
    base = get_settings().api_base_url.rstrip("/")
    return (
        f"{base}/lembretes/descadastrar"
        f"?e={quote(normalizar(endereco))}&t={gerar_token(endereco)}"
    )
