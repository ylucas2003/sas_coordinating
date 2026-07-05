"""Endpoints de autenticação — login e primeiro acesso (criação de senha)."""

import hmac
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from ..auth import criar_token, hash_senha, verificar_senha
from ..config import get_settings
from ..supabase_client import get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    tipo: str     # "aluno" | "coordenador"
    usuario: str  # matrícula (aluno) ou e-mail (coordenador)
    senha: str


class PrimeiroAcessoBody(BaseModel):
    matricula: str
    email: str
    senha_nova: str

    @field_validator("senha_nova")
    @classmethod
    def _senha_minima(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("a senha precisa ter pelo menos 8 caracteres")
        return v


# Rate limit in-memory do primeiro acesso: 5 tentativas por ip:matricula a
# cada 15 min. Por processo/worker — suficiente para o porte do SAS; um
# limitador distribuído (Redis) só se o deploy escalar horizontalmente.
_JANELA_TENTATIVAS_SEGUNDOS = 15 * 60
_MAX_TENTATIVAS_POR_JANELA = 5
_tentativas_por_chave: dict[str, list[float]] = defaultdict(list)


def _limitar_tentativas(chave: str) -> None:
    agora = time.monotonic()
    recentes = [
        t for t in _tentativas_por_chave[chave]
        if agora - t < _JANELA_TENTATIVAS_SEGUNDOS
    ]
    if len(recentes) >= _MAX_TENTATIVAS_POR_JANELA:
        _tentativas_por_chave[chave] = recentes
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Aguarde alguns minutos e tente de novo.",
        )
    recentes.append(agora)
    _tentativas_por_chave[chave] = recentes


@router.post("/login")
async def login(body: LoginBody) -> dict:
    settings = get_settings()

    if body.tipo == "coordenador":
        usuario_ok = hmac.compare_digest(
            body.usuario.encode(), settings.coordenador_email.encode()
        )
        senha_ok = hmac.compare_digest(
            body.senha.encode(), settings.coordenador_senha.encode()
        )
        if not (usuario_ok and senha_ok):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        token = criar_token({"sub": "coordenador", "tipo": "coordenador", "nome": "Coordenação"})
        return {
            "access_token": token,
            "token_type": "bearer",
            "tipo": "coordenador",
            "aluno_id": None,
            "nome": "Coordenação",
        }

    if body.tipo == "aluno":
        cliente = get_supabase()
        resp = (
            cliente.table("aluno")
            .select("id, nome, senha_hash, ativo")
            .eq("matricula", body.usuario)
            .limit(1)
            .execute()
        )
        if not resp.data:
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        aluno = resp.data[0]
        if not aluno.get("ativo"):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        if aluno.get("senha_hash") is None:
            raise HTTPException(
                status_code=401,
                detail=(
                    "Sua conta ainda não tem senha de acesso. "
                    "Use 'Primeiro acesso' na tela de login para criá-la."
                ),
            )
        if not verificar_senha(body.senha, aluno["senha_hash"]):
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        token = criar_token({
            "sub": aluno["id"],
            "tipo": "aluno",
            "nome": aluno["nome"],
            "aluno_id": aluno["id"],
        })
        return {
            "access_token": token,
            "token_type": "bearer",
            "tipo": "aluno",
            "aluno_id": aluno["id"],
            "nome": aluno["nome"],
        }

    raise HTTPException(status_code=400, detail="tipo deve ser 'aluno' ou 'coordenador'")


_ERRO_PRIMEIRO_ACESSO = (
    "Não foi possível validar seus dados. Confira a matrícula e o e-mail "
    "cadastrado no Canvas, ou procure a coordenação."
)


@router.post("/primeiro-acesso")
async def primeiro_acesso(body: PrimeiroAcessoBody, request: Request) -> dict:
    """Cria (ou redefine) a senha do aluno validando matrícula + e-mail do Canvas.

    Serve tanto para o primeiro acesso quanto para "esqueci minha senha" — a
    validação é a mesma. Todas as falhas devolvem a MESMA mensagem 401 para
    não vazar existência de matrícula nem estado do e-mail.
    """
    matricula = body.matricula.strip()
    ip = request.client.host if request.client else "?"
    _limitar_tentativas(f"{ip}:{matricula}")

    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("id, nome, email, ativo")
        .eq("matricula", matricula)
        .limit(1)
        .execute()
    )
    aluno = resp.data[0] if resp.data else None
    email_confere = (
        aluno is not None
        and aluno.get("ativo")
        and aluno.get("email")
        and aluno["email"].strip().lower() == body.email.strip().lower()
    )
    if not email_confere:
        raise HTTPException(status_code=401, detail=_ERRO_PRIMEIRO_ACESSO)

    cliente.table("aluno").update(
        {"senha_hash": hash_senha(body.senha_nova)}
    ).eq("id", aluno["id"]).execute()

    # Auto-login: devolve o mesmo shape do POST /auth/login.
    token = criar_token({
        "sub": aluno["id"],
        "tipo": "aluno",
        "nome": aluno["nome"],
        "aluno_id": aluno["id"],
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "tipo": "aluno",
        "aluno_id": aluno["id"],
        "nome": aluno["nome"],
    }
