"""Utilitários de autenticação JWT.

- Alunos: autenticados por matrícula + senha (PBKDF2-HMAC-SHA256, formato versionado).
- Coordenadores: autenticados por e-mail + senha configurada via env.
- Scheduler (AWS EventBridge): segredo compartilhado no header X-Scheduler-Secret.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

# Hash de senha: pbkdf2_sha256$<iteracoes>$<salt_hex>$<hash_hex>.
# O prefixo identifica algoritmo+parâmetros gravados no próprio hash, então
# mudar as constantes abaixo não invalida senhas existentes.
PBKDF2_ITERACOES = 600_000
_PREFIXO_HASH = "pbkdf2_sha256"

_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    salt = secrets.token_hex(16)
    derivado = hashlib.pbkdf2_hmac(
        "sha256", senha.encode(), bytes.fromhex(salt), PBKDF2_ITERACOES
    )
    return f"{_PREFIXO_HASH}${PBKDF2_ITERACOES}${salt}${derivado.hex()}"


def verificar_senha(senha: str, senha_hash: Optional[str]) -> bool:
    """Confere a senha contra o hash armazenado.

    NULL ou formato desconhecido (ex.: md5 legado zerado pela migration 0012)
    nunca autenticam.
    """
    if not senha_hash:
        return False
    partes = senha_hash.split("$")
    if len(partes) != 4 or partes[0] != _PREFIXO_HASH:
        return False
    _, iteracoes_str, salt, esperado = partes
    try:
        iteracoes = int(iteracoes_str)
        derivado = hashlib.pbkdf2_hmac(
            "sha256", senha.encode(), bytes.fromhex(salt), iteracoes
        )
    except ValueError:
        return False
    return hmac.compare_digest(derivado.hex(), esperado)


def criar_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def _decodificar(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Não autenticado"
        )
    try:
        return _decodificar(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )


async def get_current_aluno(user: dict = Depends(get_current_user)) -> dict:
    if user.get("tipo") != "aluno":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a alunos autenticados",
        )
    return user


async def get_current_coordenador(user: dict = Depends(get_current_user)) -> dict:
    if user.get("tipo") != "coordenador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito à coordenação",
        )
    return user


async def exigir_scheduler_secret(
    x_scheduler_secret: Optional[str] = Header(default=None, alias="X-Scheduler-Secret"),
) -> None:
    """Autentica chamadas máquina-a-máquina do scheduler (AWS EventBridge).

    O mesmo valor vive em SCHEDULER_SECRET (backend) e no parâmetro SSM
    /sas/scheduler/secret (AWS) — ver infra/README.md. Sem o secret
    configurado no ambiente, as rotas agendadas ficam indisponíveis (503)
    em vez de abertas.
    """
    settings = get_settings()
    if not settings.scheduler_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SCHEDULER_SECRET não configurado no servidor",
        )
    if not x_scheduler_secret or not hmac.compare_digest(
        x_scheduler_secret, settings.scheduler_secret
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="scheduler secret inválido",
        )
