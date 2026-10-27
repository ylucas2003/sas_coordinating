"""Conexões de IA: o token do MCP da coordenação, pela tela (docs/43 §5.3, Fase 2).

A tela `/administracao/conexoes-de-ia` do front lista, emite e revoga. Quem
CONFERE o token é o outro processo — o MCP, pela RPC `mcp_conferir_token` —;
aqui só se emite e se revoga, direto em `token_mcp` (a API, com o
`sas_service`, tem ALL nela pelos DEFAULT PRIVILEGES).

Quatro regras que não são detalhe:

  1. **O token aparece UMA vez**, na resposta da emissão. A linha guarda só o
     sha256 (o CHECK da 0072 recusa qualquer coisa que não seja hex de 64), a
     auditoria guarda só o nome da conexão, e nenhum `response_model` daqui
     tem campo de hash — mesmo que alguém o acrescente ao select, ele não sai.
  2. **Emitir é do administrador E do coordenador**, cada um em nome da
     própria conta — decisão do dono em 26/10 (até ali, só o administrador).
     MCP_EMISSAO_SO_ADMINISTRADOR=true volta ao "só o administrador": conectar
     uma IA de fora é mandar dado de menor a um provedor terceiro (docs/43
     §5.4). Ligada ou não, "administrador" — o que vê e revoga as conexões de
     todos — é reconferido na TABELA, como em `get_current_administrador`: um
     rebaixado não emite nem revoga o de outros com o token de 8 h que tinha.
     A conexão OAuth não nasce aqui: é aprovada pelo código enviado ao e-mail
     da conta de IA (routes/oauth_mcp.py, routes/mcp_emails_ia.py).
  3. **Nunca apagar.** Revogar preenche `revogado_em`; a linha revogada é o
     que responde, meses depois, "quem tinha acesso, e até quando" — e a
     auditoria de cada chamada do MCP aponta para ela (`mcp_token/<id>`).
  4. **O coordenador revoga só as suas; a de outro é 404**, e não 403: dizer
     "existe, mas não é sua" já contaria quem tem conexão aberta.

Todas `def`: só há I/O síncrono (PostgREST), e `async def` rodaria no único
event loop da API (api/CLAUDE.md, convenções).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator

from ..auditoria import registrar as auditar
from ..auth import conta_ainda_e_administradora, get_current_coordenador, papel_da_sessao
from ..mcp import tokens
from ..mcp.auditoria_mcp import ACAO_CONEXAO_EMITIDA, ACAO_CONEXAO_REVOGADA, CANAL, recurso_do_token
from ..mcp.configuracao import get_configuracao_mcp
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/mcp",
    tags=["mcp"],
    dependencies=[Depends(get_current_coordenador)],
)

NOME_MAXIMO = 80  # o CHECK `token_mcp_nome_valido` da 0072

# O que a listagem lê. SEM `hash_acesso`, de propósito — e o response_model
# também não o tem: são duas barreiras para a mesma coisa.
_COLUNAS = (
    "id, usuario_coordenacao_id, nome, origem, oauth_cliente_id, prefixo, "
    "criado_em, expira_em, ultimo_uso_em, revogado_em"
)


# ─── Modelos (o contrato com web/src/tipos/dominio.ts) ───────────────────


class DisponibilidadeDoMcp(BaseModel):
    habilitado: bool
    emissaoSoAdministrador: bool
    urlDoServidor: str | None


class DonoDaConexao(BaseModel):
    id: str
    nome: str


class ConexaoDeIa(BaseModel):
    id: str
    nome: str
    prefixo: str
    origem: Literal["pessoal", "oauth"]
    #: Nome do app quando a origem é `oauth`: o `client_name` que o PRÓPRIO app
    #: declarou no cadastro dinâmico (0073), sem conferência — a tela o limpa
    #: (`conexoesDeIa.ts::nomeDoApp`). None no token pessoal, ou se o app não
    #: declarou nome.
    cliente: str | None = None
    criadaEm: str
    ultimoUsoEm: str | None = None
    #: O fim da CONEXÃO. No token pessoal, a validade dele; na OAuth, o prazo
    #: da concessão — o do refresh, contado da aprovação —, e não o do access
    #: de 60 min (`_apps_e_fins`).
    expiraEm: str | None = None
    revogadaEm: str | None = None
    dono: DonoDaConexao


class ConexaoDeIaCriada(ConexaoDeIa):
    #: A ÚNICA resposta em que o token aparece.
    token: str


class EmitirConexaoBody(BaseModel):
    nome: str

    @field_validator("nome")
    @classmethod
    def _nome_valido(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > NOME_MAXIMO:
            raise ValueError(f"o nome da conexão tem de ter de 1 a {NOME_MAXIMO} caracteres")
        return v


# ─── Auxiliares ──────────────────────────────────────────────────────────


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _agora() -> datetime:
    return datetime.now(UTC)


def _e_administrador(user: dict) -> bool:
    """Administrador no token E na tabela (`conta_ainda_e_administradora`)."""
    return papel_da_sessao(user) == "administrador" and conta_ainda_e_administradora(user.get("sub"))


def _nomes_dos_donos(cliente: Any, ids: set[str]) -> dict[str, str]:
    # Consulta à parte, e não embed: `token_mcp` tem DUAS FKs para
    # `usuario_coordenacao` (dono e quem revogou), e o embed sem dica de FK é
    # ambíguo para o PostgREST.
    if not ids:
        return {}
    linhas = (
        cliente.table("usuario_coordenacao").select("id, nome").in_("id", sorted(ids)).execute().data
        or []
    )
    return {str(linha["id"]): linha.get("nome") or "" for linha in linhas}


#: Ids por `in.(…)`: a lista traz TODAS as conexões que já existiram (regra
#: 3), e uma URL com milhares de uuids passaria do limite do nginx.
_IDS_POR_CONSULTA = 100


def _apps_e_fins(cliente: Any, linhas: list[dict]) -> tuple[dict[str, str | None], dict[str, str]]:
    """O nome do app e o fim da CONEXÃO de cada linha OAuth.

    O fim mora no refresh, não na linha: a linha de `token_mcp` de origem
    `oauth` guarda a validade do ACCESS, 60 min trocados a cada giro
    (routes/oauth_mcp._girar_refresh), e devolvê-la fazia o card dizer
    "expirou" uma hora depois de quem conectou pelo claude.ai ou pelo ChatGPT,
    com a conexão viva. O refresh novo herda o prazo do velho, então o fim é o
    mesmo na família inteira, e basta o ÚLTIMO de cada uma
    (`substituido_por IS NULL`): a família ganha uma linha por giro, e sem
    paginação (CLAUDE.md, armadilha 2) a lista não pode ler o histórico todo.
    App sem `refresh_token` não tem refresh: a conexão acaba com o access, e
    `_conexao` cai na validade da própria linha — que aí é o fim de verdade.
    """
    oauth = [linha for linha in linhas if linha.get("origem") == "oauth"]
    if not oauth:
        return {}, {}
    apps: dict[str, str | None] = {}
    ids_dos_apps = sorted({str(linha["oauth_cliente_id"]) for linha in oauth if linha.get("oauth_cliente_id")})
    for i in range(0, len(ids_dos_apps), _IDS_POR_CONSULTA):
        for app in (
            cliente.table("oauth_cliente_mcp").select("client_id, client_name")
            .in_("client_id", ids_dos_apps[i:i + _IDS_POR_CONSULTA]).execute().data
            or []
        ):
            apps[str(app["client_id"])] = app.get("client_name")
    fins: dict[str, str] = {}
    ids_das_conexoes = sorted({str(linha["id"]) for linha in oauth})
    for i in range(0, len(ids_das_conexoes), _IDS_POR_CONSULTA):
        for refresh in (
            cliente.table("oauth_refresh_mcp").select("token_mcp_id, expira_em")
            .in_("token_mcp_id", ids_das_conexoes[i:i + _IDS_POR_CONSULTA])
            .is_("substituido_por", "null").execute().data
            or []
        ):
            conexao, fim = str(refresh["token_mcp_id"]), str(refresh["expira_em"])
            # Dois "últimos" só num giro interrompido entre gravar o novo e
            # apontar o velho para ele; o prazo herdado é o mesmo.
            if fim > fins.get(conexao, ""):
                fins[conexao] = fim
    return apps, fins


def _conexao(
    linha: dict,
    nomes: dict[str, str],
    apps: dict[str, str | None] | None = None,
    fins: dict[str, str] | None = None,
) -> ConexaoDeIa:
    """A linha no formato do contrato. `apps` e `fins` vêm de `_apps_e_fins`;
    sem eles (o token pessoal), a conexão é a própria linha."""
    dono = str(linha["usuario_coordenacao_id"])
    conexao_id = str(linha["id"])
    oauth = linha["origem"] == "oauth"
    return ConexaoDeIa(
        id=conexao_id,
        nome=linha["nome"],
        prefixo=linha["prefixo"],
        origem=linha["origem"],
        cliente=(apps or {}).get(str(linha.get("oauth_cliente_id"))) if oauth else None,
        criadaEm=str(linha["criado_em"]),
        ultimoUsoEm=_texto_ou_none(linha.get("ultimo_uso_em")),
        expiraEm=((fins or {}).get(conexao_id) if oauth else None) or _texto_ou_none(linha.get("expira_em")),
        revogadaEm=_texto_ou_none(linha.get("revogado_em")),
        dono=DonoDaConexao(id=dono, nome=nomes.get(dono, "")),
    )


def _texto_ou_none(valor: Any) -> str | None:
    return None if valor is None else str(valor)


# ─── Rotas ───────────────────────────────────────────────────────────────


@router.get("/disponibilidade", response_model=DisponibilidadeDoMcp)
def disponibilidade() -> DisponibilidadeDoMcp:
    """O que a tela precisa saber antes de desenhar: se há servidor, quem emite,
    e o endereço que a IA configura."""
    config = get_configuracao_mcp()
    return DisponibilidadeDoMcp(
        habilitado=config.habilitado,
        emissaoSoAdministrador=config.emissao_so_administrador,
        urlDoServidor=config.url_publica or None,
    )


@router.get("/tokens", response_model=list[ConexaoDeIa])
def listar_conexoes(user: dict = Depends(get_current_coordenador)) -> list[ConexaoDeIa]:
    """O administrador vê todas; o coordenador, só as que estão em nome dele.
    As revogadas e vencidas continuam na lista (regra 3)."""
    cliente = get_supabase()
    consulta = cliente.table("token_mcp").select(_COLUNAS).order("criado_em", desc=True)
    if not _e_administrador(user):
        consulta = consulta.eq("usuario_coordenacao_id", user.get("sub"))
    linhas = consulta.execute().data or []
    nomes = _nomes_dos_donos(cliente, {str(linha["usuario_coordenacao_id"]) for linha in linhas})
    apps, fins = _apps_e_fins(cliente, linhas)
    return [_conexao(linha, nomes, apps, fins) for linha in linhas]


@router.post("/tokens", status_code=201, response_model=ConexaoDeIaCriada)
def emitir_conexao(
    body: EmitirConexaoBody,
    request: Request,
    user: dict = Depends(get_current_coordenador),
) -> ConexaoDeIaCriada:
    """Emite um token pessoal em nome de QUEM PEDE. O token volta UMA vez, aqui.

    O Claude Code e o Claude Desktop conectam por ele; o claude.ai e o ChatGPT,
    pelo OAuth. Com MCP_EMISSAO_SO_ADMINISTRADOR ligada (não é o padrão desde
    26/10), só o administrador emite."""
    config = get_configuracao_mcp()
    if config.emissao_so_administrador and not _e_administrador(user):
        raise HTTPException(
            status_code=403,
            detail=(
                "Conectar uma IA ao SAS está, neste ambiente, restrito ao administrador "
                "(MCP_EMISSAO_SO_ADMINISTRADOR, docs/43 §5.4)."
            ),
        )

    sub = str(user.get("sub"))
    cliente = get_supabase()
    token, hash_acesso, prefixo = tokens.gerar()
    criado_em = _agora()
    expira_em = (
        criado_em + timedelta(days=config.validade_do_token_dias)
        if config.validade_do_token_dias
        else None
    )
    linha = (
        cliente.table("token_mcp")
        .insert(
            {
                "usuario_coordenacao_id": sub,
                "nome": body.nome,
                "origem": "pessoal",
                "hash_acesso": hash_acesso,
                "prefixo": prefixo,
                "criado_em": criado_em.isoformat(),
                "expira_em": expira_em.isoformat() if expira_em else None,
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    auditar(
        cliente, ACAO_CONEXAO_EMITIDA, canal=CANAL,
        ator_tipo="coordenador", ator_id=sub,
        recurso=recurso_do_token(str(linha["id"])), ip=_ip(request),
        # Só o nome: nunca o token, nem o hash, nem o prefixo.
        detalhe={"nome": body.nome},
    )
    conexao = _conexao(linha, _nomes_dos_donos(cliente, {sub}))
    return ConexaoDeIaCriada(**conexao.model_dump(), token=token)


@router.post("/tokens/{conexao_id}/revogar", response_model=ConexaoDeIa)
def revogar_conexao(
    conexao_id: str,
    request: Request,
    user: dict = Depends(get_current_coordenador),
) -> ConexaoDeIa:
    """Revoga na hora: a próxima chamada do MCP com este token já é recusada,
    porque o MCP confere pelo banco a cada requisição. Revogar de novo
    devolve a conexão como está, sem segundo evento."""
    # Id torto é 404, não 500: o PostgREST recusaria o texto num uuid.
    try:
        conexao_id = str(uuid.UUID(conexao_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="Conexão não encontrada.") from None

    sub = str(user.get("sub"))
    cliente = get_supabase()
    linhas = cliente.table("token_mcp").select(_COLUNAS).eq("id", conexao_id).limit(1).execute().data or []
    if not linhas or (str(linhas[0]["usuario_coordenacao_id"]) != sub and not _e_administrador(user)):
        raise HTTPException(status_code=404, detail="Conexão não encontrada.")
    linha = linhas[0]

    if linha.get("revogado_em") is None:
        revogada = (
            cliente.table("token_mcp")
            .update({"revogado_em": _agora().isoformat(), "revogado_por": sub}, returning="representation")
            .eq("id", conexao_id)
            # Duas revogações ao mesmo tempo: só a primeira grava.
            .is_("revogado_em", "null")
            .execute()
            .data
            or []
        )
        if revogada:
            linha = {**linha, "revogado_em": revogada[0].get("revogado_em")}
            auditar(
                cliente, ACAO_CONEXAO_REVOGADA, canal=CANAL,
                ator_tipo="coordenador", ator_id=sub,
                recurso=recurso_do_token(conexao_id), ip=_ip(request),
                detalhe={"nome": linha["nome"]},
            )
        else:
            linha = (
                cliente.table("token_mcp").select(_COLUNAS).eq("id", conexao_id).limit(1).execute().data
                or [linha]
            )[0]

    nomes = _nomes_dos_donos(cliente, {str(linha["usuario_coordenacao_id"])})
    return _conexao(linha, nomes, *_apps_e_fins(cliente, [linha]))
