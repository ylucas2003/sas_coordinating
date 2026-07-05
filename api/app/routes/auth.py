"""Endpoint de login — emite JWT para alunos e coordenadores."""

import hmac

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..auth import criar_token, verificar_senha
from ..config import get_settings
from ..supabase_client import get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    tipo: str     # "aluno" | "coordenador"
    usuario: str  # matrícula (aluno) ou e-mail (coordenador)
    senha: str


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
