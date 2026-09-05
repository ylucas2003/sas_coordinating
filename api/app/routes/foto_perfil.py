"""Foto de perfil, autosserviço — aluno e coordenação usam a MESMA rota.

`/me/foto` não é `Depends(get_current_aluno)`: a foto é simétrica entre os
dois perfis (docs/sprints.html · SPRINT FOTO), então em vez de duplicar
GET/PUT/DELETE em dois módulos, esta rota lê `user["tipo"]` do JWT e resolve
a tabela e a coluna de id certas. `routes/me.py` continua só-aluno de
propósito — é o proxy dos dados de estudo — então a foto ganhou módulo
próprio em vez de entrar lá.

Nunca devolve URL: a foto volta embutida como data URL no corpo JSON (base64).
Sem isso have um link que expira, precisaria refresh periódico no front para
uma sessão de coordenação que fica o dia inteiro aberta — e a CSP de produção
(`img-src 'self' data: blob:`) já aceita `data:` sem precisar de origem nova.
"""

from __future__ import annotations

import base64
import binascii
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from .. import storage
from ..auditoria import registrar as auditar
from ..auth import get_current_user
from ..supabase_client import get_supabase

router = APIRouter(prefix="/me", tags=["perfil"])

_TIPOS_ACEITOS = ("image/jpeg", "image/png", "image/webp")


class FotoPerfilBody(BaseModel):
    conteudo_base64: str
    content_type: str
    # Não é consentimento legal (isso é decisão de coordenação + jurídico,
    # docs/sprints.html · SPRINT FOTO · apêndice) — é o registro técnico de
    # que a própria pessoa (ou quem está com a sessão dela) confirmou que
    # pode enviar esta imagem, guardado em claro na auditoria.
    declaracao_autorizacao: bool

    @field_validator("content_type")
    @classmethod
    def _content_type_aceito(cls, v: str) -> str:
        if v not in _TIPOS_ACEITOS:
            raise ValueError(f"content_type precisa ser um de {_TIPOS_ACEITOS}")
        return v

    @field_validator("declaracao_autorizacao")
    @classmethod
    def _autorizacao_confirmada(cls, v: bool) -> bool:
        if not v:
            raise ValueError("é necessário confirmar a autorização para enviar a foto")
        return v


def _entidade_do_usuario(user: dict) -> tuple[str, str, str]:
    """(nome da entidade, tabela, id) a partir do JWT.

    ⚠️ **Fail-closed, e o `else` genérico que estava aqui era um bug esperando
    um terceiro tipo de sessão.** Até 05/09 esta função dizia, por escrito, que
    "só 'aluno' ou 'coordenador' chegam aqui" e devolvia a entidade de
    COORDENAÇÃO para tudo que não fosse aluno. A premissa era verdadeira e
    deixou de ser quando a cantina entrou em `TIPOS_DE_SESSAO` (0047): uma
    sessão de cantina passaria a LER E ESCREVER `usuario_coordenacao` pelo
    próprio `sub` — foto de perfil é `UPDATE` (docs/38 §1.1).

    É a mesma forma da vulnerabilidade do token de download (PR #7), e o
    conserto é o mesmo de `chat/rotas.py`: cada tipo conhecido tem o seu ramo,
    e o desconhecido levanta em vez de cair no ramo mais poderoso.

    A cantina não tem foto de propósito — não há tela dela que mostre avatar, e
    inventar uma coluna para isso seria produto que ninguém pediu.
    """
    if user["tipo"] == "aluno":
        return "aluno", "aluno", user["aluno_id"]
    if user["tipo"] == "coordenador":
        return "coordenador", "usuario_coordenacao", user["sub"]
    raise HTTPException(
        status_code=403, detail="Este tipo de conta não tem foto de perfil."
    )


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/foto")
async def obter_minha_foto(user: dict = Depends(get_current_user)) -> dict:
    _, tabela, entidade_id = _entidade_do_usuario(user)
    cliente = get_supabase()
    linha = (
        cliente.table(tabela).select("foto_perfil_storage").eq("id", entidade_id).limit(1).execute().data
    )
    caminho = linha[0].get("foto_perfil_storage") if linha else None
    if not caminho:
        return {"fotoDataUrl": None}

    lido = storage.ler_foto_perfil(caminho)
    if lido is None:
        return {"fotoDataUrl": None}
    conteudo, content_type = lido
    return {"fotoDataUrl": f"data:{content_type};base64,{base64.b64encode(conteudo).decode()}"}


@router.put("/foto")
async def salvar_minha_foto(
    body: FotoPerfilBody, request: Request, user: dict = Depends(get_current_user)
) -> dict:
    entidade, tabela, entidade_id = _entidade_do_usuario(user)
    try:
        conteudo = base64.b64decode(body.conteudo_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="conteudo_base64 inválido") from exc

    try:
        caminho = storage.salvar_foto_perfil(
            entidade=entidade, entidade_id=entidade_id, conteudo=conteudo, content_type=body.content_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cliente = get_supabase()
    cliente.table(tabela).update(
        {"foto_perfil_storage": caminho, "foto_perfil_atualizada_em": datetime.now(UTC).isoformat()}
    ).eq("id", entidade_id).execute()

    auditar(
        cliente, "foto_perfil_definida", canal="acesso",
        ator_tipo=user["tipo"], ator_id=entidade_id, recurso=f"{tabela}/{entidade_id}",
        ip=_ip(request), detalhe={"tamanho_bytes": len(conteudo), "declaracao_autorizacao": True},
    )
    return {"ok": True}


@router.delete("/foto")
async def remover_minha_foto(request: Request, user: dict = Depends(get_current_user)) -> dict:
    _, tabela, entidade_id = _entidade_do_usuario(user)
    cliente = get_supabase()
    linha = (
        cliente.table(tabela).select("foto_perfil_storage").eq("id", entidade_id).limit(1).execute().data
    )
    caminho = linha[0].get("foto_perfil_storage") if linha else None
    if not caminho:
        return {"ok": True}

    cliente.table(tabela).update(
        {"foto_perfil_storage": None, "foto_perfil_atualizada_em": None}
    ).eq("id", entidade_id).execute()
    storage.remover_foto_perfil(caminho)

    auditar(
        cliente, "foto_perfil_removida", canal="acesso",
        ator_tipo=user["tipo"], ator_id=entidade_id, recurso=f"{tabela}/{entidade_id}",
        ip=_ip(request), detalhe={"por_titular": True},
    )
    return {"ok": True}
