"""Utilitários de autenticação JWT.

- Alunos: autenticados por matrícula + senha (MD5).
- Coordenadores: autenticados por e-mail + senha configurada via env.
- Scheduler (AWS EventBridge): segredo compartilhado no header X-Scheduler-Secret.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import get_settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8 horas

_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return hashlib.md5(senha.encode()).hexdigest()


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
