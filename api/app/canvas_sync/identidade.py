"""Quem é quem entre SAS e Canvas — resolvido pelo SAS, nunca pela pessoa.

O id interno do Canvas é um número sequencial que ninguém conhece (docs/18
§4.2). Pedir que a coordenação o procure na URL do perfil era o plano
inicial; é trabalho desnecessário, porque o `CANVAS_API_TOKEN` é de admin
da conta raiz e pode perguntar ao Canvas "qual o id de leonardo@aridesa?".

Duas direções, as duas melhor-esforço (Canvas fora do ar = None, nunca
exceção — ligar o SSO é conveniência, não pré-condição de nada):

  e-mail → id   ao criar/editar a conta da coordenação (administracao.py)
  id → e-mail   no primeiro login pelo Canvas de quem ainda não está
                ligado (auth_canvas.py): se o e-mail bater com uma conta,
                liga na hora e registra na auditoria.
"""

from __future__ import annotations

import logging

from ..config import get_settings
from .cliente import ClienteCanvas

log = logging.getLogger("sas.canvas.identidade")


def _cliente() -> ClienteCanvas | None:
    s = get_settings()
    if not s.canvas_base_url or not s.canvas_api_token:
        return None
    return ClienteCanvas(base_url=s.canvas_base_url, token=s.canvas_api_token)


async def id_pelo_email(email: str) -> str | None:
    """O id do Canvas de quem tem este e-mail — só se for UM resultado
    inequívoco. Dois ou zero devolvem None: é melhor deixar em branco do que
    ligar a conta errada."""
    ctx = _cliente()
    if ctx is None:
        return None
    alvo = email.strip().lower()
    try:
        async with ctx as canvas:
            achados = await canvas.buscar_usuarios_da_conta(
                get_settings().canvas_account_id, termo=alvo
            )
    except Exception as exc:  # melhor-esforço
        log.warning("canvas indisponível ao resolver %s: %s", alvo, exc)
        return None
    # A busca do Canvas é por substring; confere o e-mail exato.
    exatos = [
        u for u in achados
        if alvo in {str(u.get("login_id") or "").lower(), str(u.get("email") or "").lower()}
    ]
    if len(exatos) != 1:
        log.info("busca por %s no canvas devolveu %d exato(s)", alvo, len(exatos))
        return None
    return str(exatos[0]["id"])


async def email_pelo_id(canvas_user_id: str) -> str | None:
    """O e-mail primário de um usuário do Canvas."""
    ctx = _cliente()
    if ctx is None:
        return None
    try:
        async with ctx as canvas:
            perfil = await canvas.obter_perfil(canvas_user_id)
    except Exception as exc:  # melhor-esforço
        log.warning("canvas indisponível ao ler perfil %s: %s", canvas_user_id, exc)
        return None
    email = perfil.get("primary_email") or perfil.get("login_id")
    return str(email).strip().lower() if email else None
