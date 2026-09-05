"""Painel de administrador — gerenciar quem entra (docs/18 §4.6, docs/35 §11.7).

Pedido pela coordenação em 21/08 ("vai ter um acesso para administrador?
para poder gerenciar os logins?") e confirmado como prioridade em 22/08.

A tabela `usuario_coordenacao` existe desde a 0021, mas até aqui uma conta
só nascia por `scripts/criar_coordenador.py`. Estas rotas são o mesmo
provisionamento, pela tela:

  * contas de coordenação: criar, renomear, desativar, redefinir senha e
    trocar o papel (promover a administrador, rebaixar a coordenador);
  * alunos: quem já fez primeiro acesso, quem nunca entrou.

⚠️ **O arquivo é DIVIDIDO, não promovido inteiro.** O router exige coordenação
(o piso); só as rotas de CONTA exigem administrador, uma a uma. A listagem de
acesso dos alunos é trabalho diário de coordenação — promovê-la junto tiraria
da coordenação uma tela que ela usa e ninguém pediu que saísse (docs/35 §11.7).
A listagem das contas também fica no piso: sem ela a tela não teria o que
desenhar, e ler quem tem login não é o mesmo que criar login.

Três regras que não são detalhe:

  1. **Nunca apagar.** Desativar preserva a autoria na trilha de auditoria
     (evento_auditoria.ator_id aponta para cá). Uma conta apagada viraria um
     uuid sem nome na linha do tempo.
  2. **A senha nova nunca volta no corpo da resposta gravada em log.** Volta
     UMA vez, na resposta desta chamada, para a coordenação entregar ao
     titular — o mesmo cuidado que o script tem com stdout. O hash é
     PBKDF2-SHA256 de mão única: depois disto ninguém, nem o sistema, lê a
     senha de volta. Por isso "ver a senha do aluno" (pedido de 21/08,
     19h15) não existe — existe redefinir.
  3. **Conta de coordenação não se liga mais ao Canvas por aqui.** O botão
     "Ligar ao Canvas" e o campo `canvas_user_id` saíram em 04/09 junto com o
     SSO da coordenação (docs/35 §11.6): eles existiam só para habilitar aquele
     login. A COLUNA fica — apagar perde dado —, mas deixou de ter efeito.
"""

from __future__ import annotations

import base64
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from .. import storage
from ..auditoria import registrar as auditar
from ..auth import (
    PAPEIS_DE_COORDENACAO,
    get_current_administrador,
    get_current_coordenador,
    hash_senha,
)
from ..supabase_client import get_supabase

# O PISO: nada aqui é público, e nada aqui é de aluno. O que exige
# administrador diz isso na própria rota — ver o ⚠️ do docstring.
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
    # Default "coordenador" porque é o caso de quase toda conta: administrador
    # é uma só (docs/35 §11.2). Quem esquecer o campo cria a conta MENOS
    # poderosa, que é o lado seguro do esquecimento.
    papel: str = "coordenador"

    @field_validator("papel")
    @classmethod
    def _papel_conhecido(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in PAPEIS_DE_COORDENACAO:
            raise ValueError("papel deve ser 'coordenador' ou 'administrador'")
        return v

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
    # `papel` continua FORA daqui, mesmo agora que a promoção existe pela
    # tela: ela tem rota própria (`PATCH .../papel`). Promover é a ação mais
    # cara deste arquivo — dá a uma conta o poder de criar login e alterar
    # nota —, e misturá-la com "Renomear" faria um corpo `{nome, papel}` mal
    # montado promover alguém de lado. Rota separada torna isso impossível:
    # um `papel` perdido aqui é campo desconhecido, não promoção.


class PapelDoCoordenadorBody(BaseModel):
    papel: str

    @field_validator("papel")
    @classmethod
    def _papel_conhecido(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in PAPEIS_DE_COORDENACAO:
            raise ValueError("papel deve ser 'coordenador' ou 'administrador'")
        return v


@router.get("/coordenadores")
async def listar_coordenadores() -> list[dict]:
    """Todas as contas, ativas e inativas — inativa continua listada porque
    continua sendo autora de eventos."""
    cliente = get_supabase()
    linhas = (
        cliente.table("usuario_coordenacao")
        .select(
            "id, email, nome, ativo, papel, criado_em, ultimo_login_em, "
            "foto_perfil_storage"
        )
        .order("nome")
        .execute()
        .data
        or []
    )
    for linha in linhas:
        linha["temFoto"] = linha.pop("foto_perfil_storage") is not None
    return linhas


@router.post(
    "/coordenadores",
    status_code=201,
    dependencies=[Depends(get_current_administrador)],
)
async def criar_coordenador(
    body: CriarCoordenadorBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Cria a conta com senha sorteada. A senha volta UMA vez, aqui.

    Admin-only: criar login é o poder de dar acesso à base inteira de menores
    de idade a quem a pessoa quiser (docs/35 §11.7).
    """
    cliente = get_supabase()
    email = body.email.lower()
    existente = (
        cliente.table("usuario_coordenacao").select("id").eq("email", email).limit(1).execute()
    )
    if existente.data:
        raise HTTPException(status_code=409, detail=f"Já existe conta para {email}.")

    # O `canvas_user_id` NÃO é mais procurado nem gravado aqui: ele só servia
    # para habilitar o login pelo Canvas da coordenação, que saiu (docs/35
    # §11.6). A conta nasce entrando por e-mail + senha, e é o único jeito.
    senha = secrets.token_urlsafe(12)
    linha = (
        cliente.table("usuario_coordenacao")
        .insert(
            {
                "email": email, "nome": body.nome, "senha_hash": hash_senha(senha),
                "ativo": True, "papel": body.papel,
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    auditar(
        cliente, "coordenador_criado", canal="acesso",
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"coordenador/{linha['id']}", ip=_ip(request),
        detalhe={"email": email, "nome": body.nome, "papel": body.papel},
    )
    return {
        "id": linha["id"], "email": email, "nome": body.nome, "ativo": True,
        "papel": body.papel,
        # Única vez que a senha aparece. Não vai para a auditoria.
        "senha_inicial": senha,
    }


@router.patch(
    "/coordenadores/{usuario_id}",
    dependencies=[Depends(get_current_administrador)],
)
async def editar_coordenador(
    usuario_id: str,
    body: EditarCoordenadorBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Renomear ou (des)ativar. Ninguém desativa a si mesmo — senão a última
    conta da casa se tranca do lado de fora."""
    cliente = get_supabase()
    patch: dict = {}
    if body.nome is not None and body.nome.strip():
        patch["nome"] = body.nome.strip()
    if body.ativo is not None:
        if body.ativo is False and usuario_id == administrador.get("sub"):
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
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"coordenador/{usuario_id}", ip=_ip(request), detalhe=patch,
    )
    linha = atualizado[0]
    return {
        k: linha[k]
        for k in ("id", "email", "nome", "ativo", "papel", "ultimo_login_em")
        if k in linha
    }


@router.patch(
    "/coordenadores/{usuario_id}/papel",
    dependencies=[Depends(get_current_administrador)],
)
async def alterar_papel_do_coordenador(
    usuario_id: str,
    body: PapelDoCoordenadorBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Promove um coordenador a administrador, ou rebaixa um administrador a
    coordenador.

    Até 05/09 isto só existia por `scripts/criar_coordenador.py --papel`, na
    linha de comando do VPS — o que na prática queria dizer que **rebaixar não
    acontecia**: quem precisa tirar o acesso de alguém precisa fazer isso na
    hora, não abrindo um ssh. A decisão anterior está preservada de outro
    jeito: o poder continua sendo só do administrador, a ação tem rota e
    evento de auditoria próprios, e a tela pergunta antes.

    **Ninguém muda o próprio papel.** É o que garante que sempre reste um
    administrador: quem chama já é um, e sai desta rota continuando um. Sem
    essa regra, o último administrador se rebaixaria e a casa ficaria sem
    quem cria login — e sem quem conserte, porque criar login é dele. É a
    mesma trava do `ativo` em `editar_coordenador`, pelo mesmo motivo.

    Rebaixar vale na hora, e não quando o token do rebaixado vencer: quem lê
    o papel de volta na tabela é `auth.conta_ainda_e_administradora`.
    """
    cliente = get_supabase()
    if usuario_id == administrador.get("sub"):
        raise HTTPException(
            status_code=422,
            detail="Você não pode alterar o próprio papel. Peça a outro administrador.",
        )

    atual = (
        cliente.table("usuario_coordenacao")
        .select("papel, nome")
        .eq("id", usuario_id)
        .limit(1)
        .execute()
    ).data
    if not atual:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    papel_anterior = atual[0].get("papel") or "coordenador"
    if papel_anterior == body.papel:
        raise HTTPException(
            status_code=422, detail=f"A conta já é {body.papel}."
        )

    atualizado = (
        cliente.table("usuario_coordenacao")
        .update({"papel": body.papel}, returning="representation")
        .eq("id", usuario_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="conta não encontrada")

    # Evento PRÓPRIO, e não um `coordenador_editado` com o papel no detalhe:
    # mudança de poder é o que mais se procura numa trilha de auditoria, e
    # procurar é filtrar por ação.
    #
    # `valor_antes`/`valor_depois` é o par que `PATCH /notas` já usa e que a
    # tela de auditoria já sabe desenhar como "antes → depois". Sem ele, as
    # duas direções — promover e rebaixar — ficariam DUAS LINHAS IDÊNTICAS na
    # trilha, dizendo que o papel mudou sem dizer para onde.
    auditar(
        cliente, "papel_alterado", canal="acesso",
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"coordenador/{usuario_id}", ip=_ip(request),
        detalhe={
            "valor_antes": papel_anterior,
            "valor_depois": body.papel,
            "nome": atual[0].get("nome"),
        },
    )
    linha = atualizado[0]
    return {k: linha[k] for k in ("id", "email", "nome", "ativo", "papel") if k in linha}


# A rota POST /coordenadores/{id}/ligar-canvas ("Ligar ao Canvas") SAIU em
# 04/09. Ela procurava o id do Canvas pelo e-mail e gravava em
# `canvas_user_id`, e o único efeito disso era habilitar o login pelo Canvas
# para a conta — que é exatamente o que a coordenação deixou de ter (docs/35
# §11.6). Sem o SSO, o botão gravava um número que ninguém lê. A coluna
# permanece na tabela com o que já estava lá; só não se escreve mais nela
# por aqui.


@router.post(
    "/coordenadores/{usuario_id}/redefinir-senha",
    dependencies=[Depends(get_current_administrador)],
)
async def redefinir_senha_coordenador(
    usuario_id: str,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
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
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"coordenador/{usuario_id}", ip=_ip(request),
    )
    return {"id": usuario_id, "senha_nova": senha}


# ─── Acessos de alunos ────────────────────────────────────────────────────


@router.get("/alunos-acesso")
async def acessos_de_alunos() -> dict:
    """Quem consegue entrar e quem não consegue (docs/18 §4.6, docs/35 §11.5).

    "Quando o aluno faz isso, aparece na tela de gerenciamento do
    coordenador" (21/08, 19h15). Continua sendo trabalho diário de
    coordenação, e por isso NÃO exige administrador.

    ⚠️ A pergunta que esta tela responde MUDOU em 04/09. Antes era "quem já
    criou senha" (`senha_hash IS NOT NULL`); com a senha de aluno extinta,
    ninguém vai criar mais nenhuma, e esse número virou fóssil: ele congela no
    valor de 04/09 para sempre. A pergunta viva agora é **quem tem
    `canvas_user_id`** — é o único caminho de entrada que existe, então aluno
    sem ele é aluno que não entra, e é a lista que a coordenação precisa ver.

    `primeiroAcessoFeito` continua no corpo por ser histórico verdadeiro (quem
    tinha senha antes da virada), mas quem decide é `temCanvas`.
    """
    cliente = get_supabase()
    alunos: list[dict] = []
    offset = 0
    while True:
        lote = (
            cliente.table("aluno")
            .select(
                "id, nome, matricula, email, ativo, senha_hash, canvas_user_id, "
                "foto_perfil_storage"
            )
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
            "temFoto": a.get("foto_perfil_storage") is not None,
            "ultimoLoginEm": ultimo_login.get(a["id"]),
        }
        for a in alunos
    ]
    return {
        "total": len(linhas),
        "comCanvas": sum(1 for l in linhas if l["temCanvas"]),
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


# ─── Foto de perfil (visão de outra coordenação) ─────────────────────────
# Cada conta gerencia a própria foto por PUT/DELETE /me/foto
# (routes/foto_perfil.py). Isto aqui é só leitura, para a auditoria e a
# administração conseguirem mostrar a foto de outro coordenador na lista.


@router.get("/coordenadores/{usuario_id}/foto")
async def foto_do_coordenador(usuario_id: str) -> dict:
    cliente = get_supabase()
    resp = (
        cliente.table("usuario_coordenacao")
        .select("foto_perfil_storage")
        .eq("id", usuario_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    caminho = resp.data[0].get("foto_perfil_storage")
    if not caminho:
        return {"fotoDataUrl": None}

    lido = storage.ler_foto_perfil(caminho)
    if lido is None:
        return {"fotoDataUrl": None}
    conteudo, content_type = lido
    return {"fotoDataUrl": f"data:{content_type};base64,{base64.b64encode(conteudo).decode()}"}

