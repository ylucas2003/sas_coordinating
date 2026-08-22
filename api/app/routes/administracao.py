"""Painel de administrador — gerenciar quem entra (docs/18 §4.6).

Pedido pela coordenação em 21/08 ("vai ter um acesso para administrador?
para poder gerenciar os logins?") e confirmado como prioridade em 22/08.

A tabela `usuario_coordenacao` existe desde a 0021, mas até aqui uma conta
só nascia por `scripts/criar_coordenador.py`. Estas rotas são o mesmo
provisionamento, pela tela:

  * contas de coordenação: criar, renomear, desativar, redefinir senha;
  * alunos: quem já fez primeiro acesso, quem nunca entrou.

Duas regras que não são detalhe:

  1. **Nunca apagar.** Desativar preserva a autoria na trilha de auditoria
     (evento_auditoria.ator_id aponta para cá). Uma conta apagada viraria um
     uuid sem nome na linha do tempo.
  2. **A senha nova nunca volta no corpo da resposta gravada em log.** Volta
     UMA vez, na resposta desta chamada, para a coordenação entregar ao
     titular — o mesmo cuidado que o script tem com stdout. O hash é
     PBKDF2-SHA256 de mão única: depois disto ninguém, nem o sistema, lê a
     senha de volta. Por isso "ver a senha do aluno" (pedido de 21/08,
     19h15) não existe — existe redefinir.
"""

from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador, hash_senha
from ..canvas_sync import identidade
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/administracao",
    tags=["administracao"],
    dependencies=[Depends(get_current_coordenador)],
)

_TAMANHO_PAGINA = 1000


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ─── Contas de coordenação ────────────────────────────────────────────────


class CriarCoordenadorBody(BaseModel):
    email: str
    nome: str
    # id do usuário no Canvas — é o que liga a conta ao SSO (0026). Opcional:
    # sem ele a conta entra só por e-mail + senha.
    canvas_user_id: str | None = None

    # Sem `EmailStr` de propósito: puxaria email-validator (e dnspython) para
    # a imagem por causa de um campo. O que importa aqui é "tem @ e domínio"
    # — o e-mail é identificador de login, não destinatário de envio.
    @field_validator("email")
    @classmethod
    def _email_plausivel(cls, v: str) -> str:
        v = v.strip().lower()
        usuario, _, dominio = v.partition("@")
        if not usuario or "." not in dominio:
            raise ValueError("e-mail inválido")
        return v

    @field_validator("nome")
    @classmethod
    def _nome_nao_vazio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("nome é obrigatório")
        return v.strip()


class EditarCoordenadorBody(BaseModel):
    nome: str | None = None
    ativo: bool | None = None
    canvas_user_id: str | None = None


@router.get("/coordenadores")
async def listar_coordenadores() -> list[dict]:
    """Todas as contas, ativas e inativas — inativa continua listada porque
    continua sendo autora de eventos."""
    cliente = get_supabase()
    linhas = (
        cliente.table("usuario_coordenacao")
        .select("id, email, nome, ativo, criado_em, ultimo_login_em, canvas_user_id")
        .order("nome")
        .execute()
        .data
        or []
    )
    return linhas


@router.post("/coordenadores", status_code=201)
async def criar_coordenador(
    body: CriarCoordenadorBody,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Cria a conta com senha sorteada. A senha volta UMA vez, aqui."""
    cliente = get_supabase()
    email = body.email.lower()
    existente = (
        cliente.table("usuario_coordenacao").select("id").eq("email", email).limit(1).execute()
    )
    if existente.data:
        raise HTTPException(status_code=409, detail=f"Já existe conta para {email}.")

    # Ninguém precisa saber o id do Canvas: com o e-mail o SAS pergunta lá.
    # Se o Canvas não souber (ou souber dois), fica em branco e o primeiro
    # login pelo Canvas liga sozinho pelo e-mail (auth_canvas.py).
    canvas_user_id = body.canvas_user_id or await identidade.id_pelo_email(email)

    senha = secrets.token_urlsafe(12)
    linha = (
        cliente.table("usuario_coordenacao")
        .insert(
            {
                "email": email, "nome": body.nome, "senha_hash": hash_senha(senha), "ativo": True,
                "canvas_user_id": canvas_user_id,
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    auditar(
        cliente, "coordenador_criado", canal="acesso",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"coordenador/{linha['id']}", ip=_ip(request),
        detalhe={"email": email, "nome": body.nome, "canvas_user_id": canvas_user_id},
    )
    return {
        "id": linha["id"], "email": email, "nome": body.nome, "ativo": True,
        "canvas_user_id": canvas_user_id,
        # Única vez que a senha aparece. Não vai para a auditoria.
        "senha_inicial": senha,
    }


@router.patch("/coordenadores/{usuario_id}")
async def editar_coordenador(
    usuario_id: str,
    body: EditarCoordenadorBody,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Renomear ou (des)ativar. Ninguém desativa a si mesmo — senão a última
    conta da casa se tranca do lado de fora."""
    cliente = get_supabase()
    patch: dict = {}
    if body.nome is not None and body.nome.strip():
        patch["nome"] = body.nome.strip()
    if body.canvas_user_id is not None:
        patch["canvas_user_id"] = body.canvas_user_id.strip() or None
    if body.ativo is not None:
        if body.ativo is False and usuario_id == coordenador.get("sub"):
            raise HTTPException(status_code=422, detail="Você não pode desativar a própria conta.")
        patch["ativo"] = body.ativo
    if not patch:
        raise HTTPException(status_code=422, detail="Nada para alterar.")

    atualizado = (
        cliente.table("usuario_coordenacao")
        .update(patch, returning="representation")
        .eq("id", usuario_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="conta não encontrada")

    auditar(
        cliente, "coordenador_editado", canal="acesso",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"coordenador/{usuario_id}", ip=_ip(request), detalhe=patch,
    )
    linha = atualizado[0]
    return {k: linha[k] for k in ("id", "email", "nome", "ativo", "ultimo_login_em") if k in linha}


@router.post("/coordenadores/{usuario_id}/ligar-canvas")
async def ligar_canvas(
    usuario_id: str,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Procura o id do Canvas pelo e-mail da conta e grava. É o botão
    "Ligar ao Canvas" — a pessoa não digita número nenhum."""
    cliente = get_supabase()
    linha = (
        cliente.table("usuario_coordenacao").select("id, email").eq("id", usuario_id)
        .limit(1).execute().data
    )
    if not linha:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    canvas_user_id = await identidade.id_pelo_email(linha[0]["email"])
    if not canvas_user_id:
        raise HTTPException(
            status_code=404,
            detail=(
                f"O Canvas não tem exatamente um usuário com o e-mail {linha[0]['email']}. "
                "Confira se o e-mail da conta é o mesmo do Canvas."
            ),
        )
    cliente.table("usuario_coordenacao").update({"canvas_user_id": canvas_user_id}).eq(
        "id", usuario_id
    ).execute()
    auditar(
        cliente, "coordenador_editado", canal="acesso",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"coordenador/{usuario_id}", ip=_ip(request),
        detalhe={"canvas_user_id": canvas_user_id, "via": "busca por e-mail"},
    )
    return {"id": usuario_id, "canvas_user_id": canvas_user_id}


@router.post("/coordenadores/{usuario_id}/redefinir-senha")
async def redefinir_senha_coordenador(
    usuario_id: str,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Sorteia uma senha nova. Volta UMA vez; o titular troca no primeiro uso."""
    cliente = get_supabase()
    senha = secrets.token_urlsafe(12)
    atualizado = (
        cliente.table("usuario_coordenacao")
        .update({"senha_hash": hash_senha(senha)}, returning="representation")
        .eq("id", usuario_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    auditar(
        cliente, "senha_redefinida", canal="acesso",
        ator_tipo="coordenador", ator_id=coordenador.get("sub"),
        recurso=f"coordenador/{usuario_id}", ip=_ip(request),
    )
    return {"id": usuario_id, "senha_nova": senha}


# ─── Acessos de alunos ────────────────────────────────────────────────────


@router.get("/alunos-acesso")
async def acessos_de_alunos() -> dict:
    """Quem já fez o primeiro acesso e quem nunca entrou (docs/18 §4.6).

    "Quando o aluno faz isso, aparece na tela de gerenciamento do
    coordenador" (21/08, 19h15). `senha_hash IS NOT NULL` é o sinal de
    primeiro acesso feito; o último login vem da trilha de auditoria.
    """
    cliente = get_supabase()
    alunos: list[dict] = []
    offset = 0
    while True:
        lote = (
            cliente.table("aluno")
            .select("id, nome, matricula, email, ativo, senha_hash, canvas_user_id")
            .eq("ativo", True)
            .order("nome")
            .range(offset, offset + _TAMANHO_PAGINA - 1)
            .execute()
            .data
            or []
        )
        alunos.extend(lote)
        if len(lote) < _TAMANHO_PAGINA:
            break
        offset += _TAMANHO_PAGINA

    ultimo_login = _ultimo_login_por_aluno(cliente)
    linhas = [
        {
            "id": a["id"], "nome": a["nome"], "matricula": a.get("matricula"),
            "email": a.get("email"),
            "temCanvas": bool(a.get("canvas_user_id")),
            "primeiroAcessoFeito": a.get("senha_hash") is not None,
            "ultimoLoginEm": ultimo_login.get(a["id"]),
        }
        for a in alunos
    ]
    return {
        "total": len(linhas),
        "comAcesso": sum(1 for l in linhas if l["primeiroAcessoFeito"]),
        "alunos": linhas,
    }


def _ultimo_login_por_aluno(cliente) -> dict[str, str]:
    """{aluno_id: ocorrido_em} do login_ok mais recente. Lê a cauda da trilha
    — o suficiente para o painel; a trilha inteira não cabe numa tela."""
    eventos = (
        cliente.table("evento_auditoria")
        .select("ator_id, ocorrido_em")
        .eq("acao", "login_ok")
        .eq("ator_tipo", "aluno")
        .order("ocorrido_em", desc=True)
        .limit(5000)
        .execute()
        .data
        or []
    )
    saida: dict[str, str] = {}
    for e in eventos:
        if e.get("ator_id") and e["ator_id"] not in saida:
            saida[e["ator_id"]] = e["ocorrido_em"]
    return saida

