"""Endpoint de autenticação por senha — só a coordenação passa por aqui.

O que MUDOU em 04/09 (docs/35 §11.5), e por quê:

  * saiu o ramo `tipo == "aluno"`. O aluno entra só pelo Canvas
    (`routes/auth_canvas.py`), que já era como 876 de 876 entravam na prática;
  * saiu `/auth/primeiro-acesso` junto. Ele criava e redefinia a senha do
    aluno — sem senha de aluno, não há o que criar nem o que redefinir. O
    `POST /alunos/{id}/resetar-acesso`, que era o fallback da coordenação para
    o mesmo problema, saiu pelo mesmo motivo.

⚠️ **Consequência permanente, aceita de olhos abertos:** Canvas fora do ar =
nenhum aluno entra. Para a coordenação não vale — ela fica com e-mail + senha,
que é justamente por que a coordenação NÃO entra pelo Canvas.

O token de quem entra aqui carrega o `papel` (0045). Ver o ⚠️ de `app/auth.py`
sobre por que o papel viaja num claim próprio e não no `tipo`.
"""

import logging
import time
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from postgrest.exceptions import APIError
from pydantic import BaseModel

from ..auditoria import registrar as auditar
from ..auth import PAPEIS_DE_COORDENACAO, criar_token, verificar_senha
from ..supabase_client import ClienteDados, get_supabase

log = logging.getLogger("sas.auth")

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    # Continua no corpo mesmo com um único valor válido: o front manda o modo
    # da tela, e uma mensagem clara para quem manda "aluno" é melhor do que um
    # 422 de campo desconhecido para o aluno que tem link antigo salvo.
    tipo: str = "coordenador"
    usuario: str  # e-mail da conta de coordenação
    senha: str


# Rate limit in-memory do login: 5 tentativas por ip:usuario a cada 15 min.
# Por processo/worker — suficiente para o porte do SAS; um limitador
# distribuído (Redis) só se o deploy escalar horizontalmente.
#
# ⚠️ Ele protege MENOS do que parece com mais de um worker, e agora essa é a
# única barreira contra força bruta na porta da coordenação — a do aluno
# deixou de existir junto com a senha dele (docs/35 §11.2).
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


_ERRO_ALUNO_ENTRA_PELO_CANVAS = (
    "O acesso do aluno é pelo Canvas — use o botão \"Entrar com o Canvas\" na "
    "tela de login. Não existe mais senha de aluno no SAS."
)

# O que o login precisa da conta, sem o `papel` — ver `_buscar_conta`.
_COLUNAS_DA_CONTA = "id, nome, senha_hash, ativo, foto_perfil_storage"

# `undefined_column` do Postgres (42703), que o PostgREST repassa como 400 e o
# postgrest-py levanta como APIError. Verificado contra o PostgREST v12.2.3 do
# compose: pedir uma coluna que a tabela não tem devolve
# {"code":"42703", "message":"column usuario_coordenacao.papel does not exist"}.
_ERRO_COLUNA_INEXISTENTE = "42703"


def _buscar_conta(cliente: ClienteDados, email: str) -> dict | None:
    """A conta de coordenação com esse e-mail, com `papel` quando a coluna existe.

    O segundo SELECT existe porque a coluna `papel` (migration 0045) pode
    simplesmente não estar na base contra a qual esta API roda: depois de
    `migrations/0045_papel_usuario_coordenacao.down.sql`, numa base restaurada
    de backup anterior a 04/09, ou num ambiente onde o `migrate up` ainda não
    passou — o banco do compose de desenvolvimento está exatamente assim em
    04/09 (`_migracoes_aplicadas` para na 0044), então quem subir esta branch
    localmente sem `migrate up` cai aqui. Nesse estado o PostgREST recusa o
    select INTEIRO com 42703, e o APIError sobe antes de qualquer tratamento
    de papel: sem este retry, `/auth/login` devolve 500
    para a coordenação inteira, que é justamente quem não tem segunda porta —
    o aluno entra pelo Canvas, ela não.

    Volta a linha sem a chave `papel`, e quem chama já trata a ausência como
    coordenador — o papel menos poderoso.
    """
    try:
        resp = (
            cliente.table("usuario_coordenacao")
            .select(f"{_COLUNAS_DA_CONTA}, papel")
            .eq("email", email)
            .limit(1)
            .execute()
        )
    except APIError as erro:
        if erro.code != _ERRO_COLUNA_INEXISTENTE:
            raise
        log.warning(
            "usuario_coordenacao.papel nao existe nesta base (a 0045 nao esta "
            "aplicada) — entrando como coordenador"
        )
        resp = (
            cliente.table("usuario_coordenacao")
            .select(_COLUNAS_DA_CONTA)
            .eq("email", email)
            .limit(1)
            .execute()
        )
    return resp.data[0] if resp.data else None


@router.post("/login")
async def login(body: LoginBody, request: Request) -> dict:
    # A chave inclui o usuário, e não só o IP: atrás do nginx todo mundo tem o
    # mesmo IP até o --forwarded-allow-ips estar certo, e chavear só por IP
    # transformaria o limite num balde único para todos.
    ip = request.client.host if request.client else "?"
    _limitar_tentativas(f"login:{ip}:{body.usuario.strip().lower()}")

    if body.tipo == "aluno":
        raise HTTPException(status_code=400, detail=_ERRO_ALUNO_ENTRA_PELO_CANVAS)
    if body.tipo != "coordenador":
        raise HTTPException(status_code=400, detail="tipo deve ser 'coordenador'")

    # Uma conta por pessoa, com PBKDF2, em vez da credencial única do .env
    # (migration 0021). O `sub` do token é o id do usuário, e não a string fixa
    # "coordenador" — é o que torna auditoria possível.
    cliente = get_supabase()
    email = body.usuario.strip().lower()
    usuario = _buscar_conta(cliente, email)
    if not usuario or not usuario.get("ativo"):
        auditar(cliente, "login_falhou", ator_tipo="coordenador",
                ator_id=email, ip=ip, detalhe={"motivo": "inexistente_ou_inativo"})
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not verificar_senha(body.senha, usuario["senha_hash"]):
        auditar(cliente, "login_falhou", ator_tipo="coordenador",
                ator_id=email, ip=ip, detalhe={"motivo": "senha_incorreta"})
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    # Fail-closed: papel desconhecido vale como coordenador — o papel MENOS
    # poderoso. São dois casos, e os dois chegam aqui: a linha veio sem a chave
    # `papel` (o fallback de `_buscar_conta`, base sem a 0045) ou veio com um
    # valor que o guard não reconhece. O CHECK da 0045 impede o segundo no
    # banco; isto aqui é o cinto, para uma linha estranha não virar
    # administrador por acidente.
    papel = usuario.get("papel")
    if papel not in PAPEIS_DE_COORDENACAO:
        papel = "coordenador"

    # Melhor esforço: falhar aqui não pode impedir alguém de entrar.
    try:
        cliente.table("usuario_coordenacao").update(
            {"ultimo_login_em": datetime.now(UTC).isoformat()}
        ).eq("id", usuario["id"]).execute()
    except Exception:
        log.warning("nao consegui registrar ultimo_login_em", exc_info=True)

    auditar(cliente, "login_ok", ator_tipo="coordenador",
            ator_id=usuario["id"], ip=ip,
            detalhe={"nome": usuario["nome"], "papel": papel})
    token = criar_token({
        "sub": usuario["id"],
        # `tipo` continua "coordenador" para os dois papéis: é o tipo da
        # SESSÃO, e é o que o chat, a foto de perfil e o casco do front leem.
        "tipo": "coordenador",
        "papel": papel,
        "nome": usuario["nome"],
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "tipo": "coordenador",
        "papel": papel,
        "aluno_id": None,
        "nome": usuario["nome"],
        "temFoto": usuario.get("foto_perfil_storage") is not None,
    }
