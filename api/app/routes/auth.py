"""Endpoints de autenticação — login e primeiro acesso (criação de senha)."""

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, field_validator

from ..auditoria import registrar as auditar
from ..auth import criar_token, hash_senha, verificar_senha
from ..config import get_settings
from ..supabase_client import get_supabase

log = logging.getLogger("sas.auth")

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
async def login(body: LoginBody, request: Request) -> dict:
    # O /login NÃO tinha limitador nenhum — só o /primeiro-acesso tinha
    # (docs/14 §6.3). Com uma credencial compartilhada e token de 8h, isso
    # deixava a porta da coordenação sem nada contra força bruta.
    #
    # A chave inclui o usuário, e não só o IP: atrás do nginx todo mundo tem o
    # mesmo IP até o --forwarded-allow-ips estar certo, e chavear só por IP
    # transformaria o limite num balde único para todos.
    ip = request.client.host if request.client else "?"
    _limitar_tentativas(f"login:{ip}:{body.usuario.strip().lower()}")

    if body.tipo == "coordenador":
        # Uma conta por pessoa, com PBKDF2, em vez da credencial única do .env
        # (migration 0021). O `sub` do token passa a ser o id do usuário, e não
        # a string fixa "coordenador" — é o que torna auditoria possível.
        cliente = get_supabase()
        email = body.usuario.strip().lower()
        resp = (
            cliente.table("usuario_coordenacao")
            .select("id, nome, senha_hash, ativo, foto_perfil_storage")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        usuario = resp.data[0] if resp.data else None
        if not usuario or not usuario.get("ativo"):
            auditar(cliente, "login_falhou", ator_tipo="coordenador",
                    ator_id=email, ip=ip, detalhe={"motivo": "inexistente_ou_inativo"})
            raise HTTPException(status_code=401, detail="Credenciais inválidas")
        if not verificar_senha(body.senha, usuario["senha_hash"]):
            auditar(cliente, "login_falhou", ator_tipo="coordenador",
                    ator_id=email, ip=ip, detalhe={"motivo": "senha_incorreta"})
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        # Melhor esforço: falhar aqui não pode impedir alguém de entrar.
        try:
            cliente.table("usuario_coordenacao").update(
                {"ultimo_login_em": datetime.now(UTC).isoformat()}
            ).eq("id", usuario["id"]).execute()
        except Exception:
            log.warning("nao consegui registrar ultimo_login_em", exc_info=True)

        auditar(cliente, "login_ok", ator_tipo="coordenador",
                ator_id=usuario["id"], ip=ip, detalhe={"nome": usuario["nome"]})
        token = criar_token(
            {"sub": usuario["id"], "tipo": "coordenador", "nome": usuario["nome"]}
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "tipo": "coordenador",
            "aluno_id": None,
            "nome": usuario["nome"],
            "temFoto": usuario.get("foto_perfil_storage") is not None,
        }

    if body.tipo == "aluno":
        cliente = get_supabase()
        resp = (
            cliente.table("aluno")
            .select("id, nome, senha_hash, ativo, foto_perfil_storage")
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
        auditar(cliente, "login_ok", ator_tipo="aluno", ator_id=aluno["id"], ip=ip)
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
            "temFoto": aluno.get("foto_perfil_storage") is not None,
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
    if not get_settings().primeiro_acesso_autosservico:
        auditar(get_supabase(), "primeiro_acesso_bloqueado", ator_tipo="aluno",
                ator_id=body.matricula.strip(),
                ip=request.client.host if request.client else None)
        # 403 e não 404: a rota existe e o frontend continua podendo chamá-la.
        # Desligar é decisão de operação, não mudança de contrato — o que
        # importa aqui é não deixar a migração do front sem rota enquanto ela
        # acontece (docs/15 §Etapa 7, item 7.2).
        raise HTTPException(
            status_code=403,
            detail=(
                "O primeiro acesso é liberado pela coordenação. "
                "Procure a coordenação para receber sua senha."
            ),
        )

    matricula = body.matricula.strip()
    ip = request.client.host if request.client else "?"
    _limitar_tentativas(f"{ip}:{matricula}")

    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("id, nome, email, ativo, foto_perfil_storage")
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
        "temFoto": aluno.get("foto_perfil_storage") is not None,
    }
