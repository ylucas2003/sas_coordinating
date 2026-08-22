"""Login pelo Canvas — OAuth2 por redirect (docs/18 §4.2).

Por que o Canvas é o provedor de identidade: 876 de 876 alunos ativos já
têm `canvas_user_id`, e só 1 tem senha no SAS (22/08/2026). A escola já
provisionou e verificou essas contas; pedir CPF + nome + RA para "ver se o
cara está falando a verdade" (coordenação, 21/08 19h15) seria refazer o que
o Canvas fez.

O fluxo, em três passos, nenhum deles com JS de terceiro no front:

  GET /auth/canvas/iniciar   → 302 para {canvas}/login/oauth2/auth com um
                               `state` assinado (CSRF).
  GET /auth/canvas/callback  → troca o `code` por token servidor-a-servidor,
                               pergunta "quem é você?" ao Canvas, acha o
                               aluno/coordenador no banco e devolve o JWT
                               do SAS num redirect para o front.
  "já logado entra direto"   → é o próprio redirect: o browser leva a
                               sessão do Canvas e volta sem tela nenhuma.

O que este módulo NÃO faz, de propósito:
  * não cria aluno: identidade que o Canvas atesta mas não existe em
    `aluno` é recusada. O Canvas diz QUEM é; o SAS decide quem ENTRA
    (e é o painel de administrador que gerencia isso — docs/18 §4.6).
  * não guarda o access_token do Canvas: é usado uma vez e descartado. O
    SAS continua agindo no Canvas com o token de Admin, como sempre.
  * não substitui matrícula + senha: é o fallback quando o Canvas está
    fora do ar, senão ninguém entra — nem a coordenação.

⚠️ Escrito ANTES de existir a Developer Key. Está completo, mas só pode ser
   verificado de ponta a ponta quando `CANVAS_CLIENT_ID`/`SECRET` existirem
   (docs/18 §0.3). A única parte provada sem ela é o `state` assinado.
"""

from __future__ import annotations

import contextlib
import logging
import secrets
import time
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt

from ..auditoria import registrar as auditar
from ..auth import ALGORITHM, criar_token
from ..config import get_settings
from ..supabase_client import get_supabase

log = logging.getLogger("sas.auth.canvas")

router = APIRouter(prefix="/auth/canvas", tags=["auth"])

# O `state` vive só o tempo de ir ao Canvas e voltar.
_STATE_VALIDADE_SEGUNDOS = 10 * 60


def _configurado() -> bool:
    s = get_settings()
    return bool(s.canvas_base_url and s.canvas_client_id and s.canvas_client_secret)


@router.get("/disponivel")
async def sso_disponivel() -> dict:
    """A tela de login pergunta antes de mostrar o botão."""
    return {"disponivel": _configurado()}


def _assinar_state(proximo: str) -> str:
    """CSRF: o `state` é um JWT curto com um nonce e o destino pós-login.
    Assinado com o mesmo segredo da sessão — se ele vazar, o SSO é o menor
    dos problemas."""
    s = get_settings()
    return jwt.encode(
        {"n": secrets.token_urlsafe(16), "p": proximo, "exp": int(time.time()) + _STATE_VALIDADE_SEGUNDOS},
        s.jwt_secret_key, algorithm=ALGORITHM,
    )


def _verificar_state(state: str) -> str:
    """Devolve o destino pós-login; levanta se o state for inválido/vencido."""
    s = get_settings()
    try:
        payload = jwt.decode(state, s.jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=400, detail="state inválido ou expirado") from None
    proximo = str(payload.get("p") or "/")
    # Só caminho relativo: um `state` com URL absoluta viraria open redirect.
    return proximo if proximo.startswith("/") and not proximo.startswith("//") else "/"


@router.get("/iniciar")
async def iniciar(proximo: str = Query("/", description="para onde voltar depois do login")) -> RedirectResponse:
    if not _configurado():
        raise HTTPException(status_code=503, detail="Login pelo Canvas não está configurado.")
    s = get_settings()
    params = {
        "client_id": s.canvas_client_id,
        "response_type": "code",
        "redirect_uri": s.canvas_oauth_redirect_uri,
        "state": _assinar_state(proximo),
        # Só identidade. Sem escopo, o Canvas entrega o que o usuário já vê —
        # e o SAS não precisa de mais nada dele nesta credencial.
        "scope": "url:GET|/api/v1/users/:id",
    }
    return RedirectResponse(f"{s.canvas_base_url.rstrip('/')}/login/oauth2/auth?{urlencode(params)}")


@router.get("/callback")
async def callback(
    request: Request,
    code: str | None = Query(None),
    state: str | None = Query(None),
    error: str | None = Query(None),
) -> RedirectResponse:
    if not _configurado():
        raise HTTPException(status_code=503, detail="Login pelo Canvas não está configurado.")
    if error or not code or not state:
        # O usuário cancelou na tela do Canvas. Volta ao login sem drama.
        return RedirectResponse("/login?canvas=cancelado")
    proximo = _verificar_state(state)
    s = get_settings()
    ip = request.client.host if request.client else None

    # 1. code → token, servidor a servidor. O secret nunca vai ao browser.
    async with httpx.AsyncClient(timeout=15) as http:
        try:
            r = await http.post(
                f"{s.canvas_base_url.rstrip('/')}/login/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": s.canvas_client_id,
                    "client_secret": s.canvas_client_secret,
                    "redirect_uri": s.canvas_oauth_redirect_uri,
                    "code": code,
                },
            )
            r.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            log.warning("canvas recusou o code: %s", exc)
            return RedirectResponse("/login?canvas=falhou")
        dados = r.json()
        access_token = dados.get("access_token")
        usuario = dados.get("user") or {}
        canvas_user_id = str(usuario.get("id") or "")

        # 2. Quem é? A resposta do /token já traz {id, name}; confirma no
        #    /users/self para não depender desse campo opcional.
        if not canvas_user_id and access_token:
            try:
                me = await http.get(
                    f"{s.canvas_base_url.rstrip('/')}/api/v1/users/self",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                me.raise_for_status()
                canvas_user_id = str(me.json().get("id") or "")
            except (httpx.HTTPError, httpx.TimeoutException):
                return RedirectResponse("/login?canvas=falhou")

        # 3. O token do usuário não serve para mais nada: revoga.
        if access_token:
            # Melhor-esforço: o token expira sozinho em 1 h de qualquer jeito.
            with contextlib.suppress(httpx.HTTPError, httpx.TimeoutException):
                await http.delete(
                    f"{s.canvas_base_url.rstrip('/')}/login/oauth2/token",
                    headers={"Authorization": f"Bearer {access_token}"},
                )

    if not canvas_user_id:
        return RedirectResponse("/login?canvas=falhou")

    # 4. Quem entra? O Canvas disse quem é; o banco diz se entra e como.
    cliente = get_supabase()
    token, tipo = _sessao_para(cliente, canvas_user_id)
    if token is None:
        auditar(cliente, "login_falhou", canal="acesso", ator_tipo="canvas",
                ator_id=canvas_user_id, ip=ip, detalhe={"motivo": "sem_conta_no_sas"})
        return RedirectResponse("/login?canvas=sem-conta")

    auditar(cliente, "login_ok", canal="acesso", ator_tipo=tipo, ator_id=canvas_user_id,
            ip=ip, detalhe={"via": "canvas"})
    # O front lê o token do fragmento (#), que não vai ao servidor nem fica
    # em log de acesso, grava na sessão e limpa a URL.
    return RedirectResponse(f"/login/canvas#token={token}&tipo={tipo}&proximo={proximo}")


def _sessao_para(cliente, canvas_user_id: str) -> tuple[str | None, str | None]:
    """JWT do SAS para o dono desse canvas_user_id: coordenador antes de
    aluno, porque um coordenador pode também estar matriculado em curso."""
    coord = (
        cliente.table("usuario_coordenacao")
        .select("id, nome, ativo")
        .eq("canvas_user_id", canvas_user_id)
        .limit(1)
        .execute()
        .data
    )
    if coord and coord[0].get("ativo"):
        u = coord[0]
        return criar_token({"sub": u["id"], "tipo": "coordenador", "nome": u["nome"]}), "coordenador"

    aluno = (
        cliente.table("aluno")
        .select("id, nome, ativo")
        .eq("canvas_user_id", canvas_user_id)
        .limit(1)
        .execute()
        .data
    )
    if aluno and aluno[0].get("ativo"):
        a = aluno[0]
        return criar_token(
            {"sub": a["id"], "tipo": "aluno", "nome": a["nome"], "aluno_id": a["id"]}
        ), "aluno"
    return None, None
