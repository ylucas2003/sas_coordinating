"""Os e-mails das contas de IA: quem aprova a conexão OAuth do MCP (decisão do dono, 26/10).

No card "Conexões de IA" o coordenador cadastra o e-mail da conta de IA dele —
a do claude.ai, a do ChatGPT; pode não ser o do SAS, pode ser mais de um. A
conexão OAuth só é aprovada por um código enviado a esse e-mail
(routes/oauth_mcp.py: `/oauth/pedidos/{id}/codigo` e `/aprovar`), e nasce em
nome do coordenador DONO dele. O claude.ai e o ChatGPT não informam a conta de
quem conecta: a posse do e-mail é a prova (app/mcp/emails_ia.py).

Quatro regras que não são detalhe:

  0. **Posse antes de valer** (revisão de segurança de 26/10). O cadastro
     nasce AGUARDANDO, com um código de 6 dígitos enviado ao e-mail, e só
     passa a aprovar conexão depois que quem o cadastrou — logado, aqui no
     card — digita esse código (`/confirmar`). Sem isso, um domínio digitado
     errado ("gmial.com", que tem dono e caixa catch-all) ou uma caixa
     compartilhada entregava o acesso da conta, com o nome dos alunos menores
     de idade, a quem lesse aquela caixa: o /codigo mandava para lá o código
     de APROVAR. O de confirmar é o mesmo mecanismo do de aprovar
     (app/mcp/emails_ia.py): só o HMAC, 10 minutos, 5 tentativas gastas antes
     de comparar, uso único — preso ao cadastro, e não a um pedido. E, ao
     contrário do consentimento, aqui quem pede está logado e é dono do
     cadastro: a rota diz quando o código não saiu (503), em vez de esconder.
  1. **Um e-mail, um dono.** Já CONFIRMADO e ativo, por qualquer conta, é 409:
     com dois donos, a conexão nasceria em nome de quem? O que só aguarda não
     tranca ninguém — não aprova nada, e quem digitou o e-mail de outra pessoa
     não pode impedir o dono da caixa de cadastrá-lo. Na MESMA conta, o mesmo
     e-mail ativo duas vezes também é 409. Os dois índices parciais da 0073 são
     o que vale quando dois cadastros, ou duas confirmações, chegam juntos.
     O dono que é uma conta DESATIVADA não conta: o e-mail dela não aprova
     mais nada (`oauth_mcp._conta_pode_conectar`), e ninguém o liberava — o
     administrador só remove os próprios (regra 3). Quem cadastra, ou
     confirma, o libera: `removido_em` na linha velha, nunca apagar (regra 2),
     e a trilha com o e-mail mascarado (`_liberar_de_conta_desativada`). O
     cadastro novo segue o caminho de sempre, com a posse provada (regra 0).
  2. **Nunca apagar.** Remover preenche `removido_em`, como revogar em
     `token_mcp` (routes/mcp_tokens.py, regra 3): a linha responde depois
     "quem podia aprovar conexão, e até quando". O removido para de receber
     código na hora (o /codigo só procura ativo e confirmado), e o código que
     já tinha saído para de aprovar (o /aprovar reconfere o cadastro).
  3. **Cada um vê e remove só os seus** — o administrador também. O que ele vê
     de todos são as CONEXÕES (routes/mcp_tokens.py); o e-mail é contato de
     uma pessoa, e o de outra conta é 404, como a conexão alheia lá.

Cadastrar não passa pelo portão do administrador (MCP_EMISSAO_SO_ADMINISTRADOR):
um e-mail cadastrado sozinho não dá acesso a nada. Com a regra ligada, quem a
aplica é o /codigo (não envia código ao e-mail de quem não é administrador) e
o /aprovar (não aprova em nome dele).

Cada código de confirmação é um e-mail que a escola manda a um endereço que
alguém digitou: os tetos, em memória como os do /codigo (a API é um processo
só, UVICORN_WORKERS=1), seguram o card de virar disparador — por conta, por
hora, e por e-mail, por dia, somados o cadastro e o "enviar outro".

Remover um e-mail NÃO derruba as conexões que ele aprovou: elas são da conta, e
se revogam em Conexões de IA, como as outras.

Todas `def`: só há I/O síncrono (PostgREST), e `async def` rodaria no único
event loop da API (api/CLAUDE.md, convenções).
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..config import get_settings
from ..lembretes import email as email_ses
from ..mcp.auditoria_mcp import CANAL
from ..mcp.emails_ia import (
    MAXIMO_DO_EMAIL,
    TENTATIVAS_POR_CODIGO,
    VALIDADE_DO_CODIGO,
    chave_dos_hashes,
    codigo_no_formato,
    email_valido,
    gerar_codigo,
    hash_da_confirmacao,
    mascarar_email,
    mensagem_de_confirmacao,
    normalizar_email,
)
from ..supabase_client import get_supabase
from .oauth_mcp import TetoPorIp

log = logging.getLogger("sas.mcp.emails_ia")

router = APIRouter(
    prefix="/mcp/emails-ia",
    tags=["mcp"],
    dependencies=[Depends(get_current_coordenador)],
)

ACAO_EMAIL_CADASTRADO = "mcp_email_ia_cadastrado"
#: O evento que dá ao e-mail o poder de aprovar (regra 0) — é ele que responde,
#: depois, "desde quando esta caixa aprova conexão em nome desta conta?".
ACAO_EMAIL_CONFIRMADO = "mcp_email_ia_confirmado"
ACAO_EMAIL_REMOVIDO = "mcp_email_ia_removido"

#: E-mails ativos por conta, aguardando ou confirmados. Quem conecta tem um ou
#: dois (o do claude.ai, o do ChatGPT); o teto existe para o card não virar
#: lista de contatos — cada e-mail aqui é uma caixa que aprova conexão em nome
#: da conta.
MAXIMO_DE_EMAILS_POR_CONTA = 10

#: Os tetos dos códigos de confirmação (ver o topo). Por conta: o dobro dos 10
#: e-mails que ela pode ter — cadastrar todos e ainda pedir outro código para
#: cada um numa hora. Por e-mail: o dono da caixa recebe no máximo isto por dia
#: do card, venha de que conta vier — a chave é o sha256 do endereço, como no
#: /codigo, e nunca sai da memória.
CODIGOS_POR_CONTA_POR_HORA = 20
CODIGOS_POR_EMAIL_POR_DIA = 5
TETO_DE_CODIGOS_POR_CONTA = TetoPorIp(3600.0)
TETO_DE_CODIGOS_POR_EMAIL = TetoPorIp(86400.0)

#: Os índices parciais da 0073 (regra 1): o confirmado ativo é único no SAS, e
#: o ativo é único na conta. É pelo NOME que a recusa do banco é reconhecida e
#: vira 409 (o padrão de routes/cantina.py::_inserir_pedido).
_INDICE_DO_EMAIL_CONFIRMADO = "uq_email_conta_ia_mcp_confirmado"
_INDICE_DO_EMAIL_NA_CONTA = "uq_email_conta_ia_mcp_na_conta"

_JA_CADASTRADO = "Este e-mail já está cadastrado no SAS como e-mail de conta de IA."
_JA_CONFIRMADO = "Este e-mail já está confirmado: não há código a pedir."
_NAO_ENCONTRADO = "E-mail não encontrado."
#: Uma frase só para código errado, vencido, trocado por outro e sem
#: tentativas, como no consentimento: a ação que resolve é a mesma.
_CODIGO_RECUSADO = "Código errado, vencido ou sem tentativas. Confira o último código que chegou, ou peça outro."
_CODIGO_NAO_SAIU_NO_CADASTRO = (
    "O e-mail entrou na lista, aguardando confirmação, mas não consegui enviar o código agora. "
    "Peça outro na linha dele daqui a pouco."
)
_CODIGO_NAO_SAIU = "Não consegui enviar o código agora. Tente de novo daqui a pouco."
_DEMAIS_NA_CONTA = "Códigos de confirmação demais nesta hora. Espere um pouco e peça de novo."
_DEMAIS_NO_EMAIL = "Códigos de confirmação demais para este e-mail hoje. Tente de novo amanhã."

#: O que o card mostra. As colunas do código de confirmação são lidas só para
#: conferir (`_COLUNAS_DA_CONFIRMACAO`) e nunca vão para a resposta.
_COLUNAS = "id, usuario_coordenacao_id, email, criado_em, confirmado_em, ultimo_uso_em, removido_em"
_COLUNAS_DA_CONFIRMACAO = (
    f"{_COLUNAS}, hash_codigo_de_confirmacao, confirmacao_expira_em, tentativas_de_confirmacao"
)


# ─── Modelos (o contrato com web/src/tipos/dominio.ts) ───────────────────


class EmailDaIa(BaseModel):
    id: str
    email: str
    criadoEm: str
    #: NULL = aguardando o código (regra 0): o e-mail ainda não aprova nada.
    confirmadoEm: str | None = None
    ultimoUsoEm: str | None = None


class EmailDaIaRemovido(BaseModel):
    id: str
    removidoEm: str


class ConfirmarEmailBody(BaseModel):
    #: Folga para quem cola "123 456" do e-mail; a forma é de codigo_no_formato.
    codigo: str = Field(max_length=32)


class CodigoDeConfirmacao(BaseModel):
    #: Só sai `true`: quando o código não sai, a resposta é 503 (ver o topo).
    enviado: bool


class CadastrarEmailBody(BaseModel):
    #: O teto antes da normalização: o corpo é de quem chama.
    email: str = Field(max_length=MAXIMO_DO_EMAIL + 64)

    @field_validator("email")
    @classmethod
    def _email_valido(cls, v: str) -> str:
        normalizado = normalizar_email(v)
        if not email_valido(normalizado):
            raise ValueError("e-mail inválido: use o endereço da conta de IA, como nome@dominio.com")
        return normalizado


# ─── Auxiliares ──────────────────────────────────────────────────────────


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _instante(momento: datetime) -> str:
    """Com `Z`, o formato de routes/oauth_mcp._instante: as duas rotas gravam e
    comparam os mesmos instantes desta tabela."""
    return momento.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _agora() -> str:
    return _instante(datetime.now(UTC))


def _vencido(valor: Any, agora: datetime) -> bool:
    """Prazo ilegível conta como vencido: falha fechada, como no /aprovar."""
    try:
        fim = datetime.fromisoformat(str(valor).replace("Z", "+00:00")) if valor else None
    except ValueError:
        return True
    if fim is None:
        return True
    return (fim if fim.tzinfo else fim.replace(tzinfo=UTC)) <= agora


def _texto_ou_none(valor: Any) -> str | None:
    return None if valor is None else str(valor)


def _email(linha: dict) -> EmailDaIa:
    return EmailDaIa(
        id=str(linha["id"]),
        email=linha["email"],
        criadoEm=str(linha["criado_em"]),
        confirmadoEm=_texto_ou_none(linha.get("confirmado_em")),
        ultimoUsoEm=_texto_ou_none(linha.get("ultimo_uso_em")),
    )


def _recurso(email_id: str) -> str:
    return f"email_conta_ia/{email_id}"


def _id_ou_404(email_id: str) -> str:
    """Id torto é 404, não 500: o PostgREST recusaria o texto num uuid."""
    try:
        return str(uuid.UUID(email_id))
    except ValueError:
        raise HTTPException(status_code=404, detail=_NAO_ENCONTRADO) from None


def _ativo_da_conta(cliente: Any, email_id: str, sub: str) -> dict:
    """O cadastro ATIVO desta conta, com o código de confirmação — ou 404. O de
    outra conta também é 404, como em `remover_email` (regra 3)."""
    linhas = (
        cliente.table("email_conta_ia_mcp").select(_COLUNAS_DA_CONFIRMACAO).eq("id", email_id)
        .limit(1).execute().data
        or []
    )
    if not linhas or str(linhas[0]["usuario_coordenacao_id"]) != sub or linhas[0].get("removido_em") is not None:
        raise HTTPException(status_code=404, detail=_NAO_ENCONTRADO)
    return linhas[0]


#: O motivo na trilha da linha que o cadastro de outra conta liberou (regra 1).
MOTIVO_CONTA_DESATIVADA = "conta_desativada"


def _donos_do_confirmado(cliente: Any, email: str, *, exceto: str | None = None) -> tuple[bool, list[dict]]:
    """(algum dono é conta ATIVA, os cadastros presos em conta desativada) do
    e-mail confirmado e ativo — fora `exceto`, o que se está confirmando:
    confirmado por outra aba da mesma conta, ele não é "de outro dono". Há no
    máximo um (o índice da 0073), então dois bastam.

    Ativa é `ativo IS TRUE` na tabela, a régua de `oauth_mcp._conta_pode_conectar`:
    a conta que não está lá também não aprova nada."""
    linhas = [
        linha for linha in (
            cliente.table("email_conta_ia_mcp").select("id, usuario_coordenacao_id, email").eq("email", email)
            .is_("removido_em", "null").not_.is_("confirmado_em", "null").limit(2).execute().data
            or []
        )
        if str(linha["id"]) != exceto
    ]
    if not linhas:
        return False, []
    donos = sorted({str(linha["usuario_coordenacao_id"]) for linha in linhas})
    ativas = {
        str(conta["id"])
        for conta in (
            cliente.table("usuario_coordenacao").select("id, ativo").in_("id", donos).execute().data or []
        )
        if conta.get("ativo") is True
    }
    presos = [linha for linha in linhas if str(linha["usuario_coordenacao_id"]) not in ativas]
    return len(presos) < len(linhas), presos


def _liberar_de_conta_desativada(cliente: Any, presos: list[dict], *, sub: str, ip: str | None) -> None:
    """Remove (nunca apaga) o cadastro preso em conta desativada (regra 1) e
    o audita como remoção, com o motivo e o e-mail mascarado. Quem consta como
    ator é quem cadastrou ou confirmou — é a pergunta que a trilha responde
    depois: "quem tirou este e-mail daquela conta?". Duas liberações ao mesmo
    tempo: só a primeira grava e audita."""
    for linha in presos:
        liberadas = (
            cliente.table("email_conta_ia_mcp")
            .update({"removido_em": _agora()}, returning="representation")
            .eq("id", str(linha["id"]))
            .is_("removido_em", "null")
            .execute()
            .data
            or []
        )
        if liberadas:
            auditar(
                cliente, ACAO_EMAIL_REMOVIDO, canal=CANAL,
                ator_tipo="coordenador", ator_id=sub,
                recurso=_recurso(str(linha["id"])), ip=ip,
                detalhe={"email": mascarar_email(linha["email"]), "motivo": MOTIVO_CONTA_DESATIVADA},
            )


def _ativo_na_conta(cliente: Any, sub: str, email: str) -> bool:
    return bool(
        cliente.table("email_conta_ia_mcp").select("id").eq("usuario_coordenacao_id", sub).eq("email", email)
        .is_("removido_em", "null").limit(1).execute().data
    )


def _confirmado_ou_400(cliente: Any, email_id: str, sub: str) -> EmailDaIa:
    """A corrida com outra aba da MESMA conta (`_ativo_da_conta` confere o
    dono): se ela confirmou, o item, como em "confirmar de novo"; se removeu,
    404; senão, a recusa de sempre."""
    atual = _ativo_da_conta(cliente, email_id, sub)
    if atual.get("confirmado_em") is not None:
        return _email(atual)
    raise HTTPException(status_code=400, detail=_CODIGO_RECUSADO)


def _recusa_de_indice(erro: Exception) -> bool:
    """Dois cadastros (ou duas confirmações) ao mesmo tempo: os dois passaram
    pela conferência, e um dos índices da 0073 recusa o segundo."""
    texto = str(erro)
    return _INDICE_DO_EMAIL_CONFIRMADO in texto or _INDICE_DO_EMAIL_NA_CONTA in texto


def _admitir_codigo(sub: str, email: str) -> None:
    """Os dois tetos do código de confirmação (ver o topo), ou 429."""
    if not TETO_DE_CODIGOS_POR_CONTA.admitir(sub, CODIGOS_POR_CONTA_POR_HORA):
        raise HTTPException(status_code=429, detail=_DEMAIS_NA_CONTA, headers={"Retry-After": "3600"})
    chave = hashlib.sha256(email.encode()).hexdigest()
    if not TETO_DE_CODIGOS_POR_EMAIL.admitir(chave, CODIGOS_POR_EMAIL_POR_DIA):
        raise HTTPException(status_code=429, detail=_DEMAIS_NO_EMAIL, headers={"Retry-After": "86400"})


def _novo_codigo(email_id: str, email: str) -> tuple[str, dict]:
    """(código em claro, as colunas que o guardam): o hash preso ao cadastro, o
    prazo de 10 minutos e as tentativas zeradas."""
    codigo = gerar_codigo()
    chave = chave_dos_hashes(get_settings().jwt_secret_key)
    return codigo, {
        "hash_codigo_de_confirmacao": hash_da_confirmacao(chave, email_id, email, codigo),
        "confirmacao_expira_em": _instante(datetime.now(UTC) + VALIDADE_DO_CODIGO),
        "tentativas_de_confirmacao": 0,
    }


def _enviar_codigo_de_confirmacao(email: str, codigo: str) -> bool:
    """Pelo SES do motor de lembretes (lembretes/email.py), como o código de
    aprovar (routes/oauth_mcp._enviar_codigo). Devolve se o código saiu.

    Sem SES, em dev o código vai ao log, que é como se testa na máquina; fora
    de dev, NUNCA — quem lesse o log confirmaria o e-mail de qualquer um. E o
    erro do SES vai ao log sem a mensagem dele: a do sandbox (MessageRejected)
    traz o endereço inteiro, e o log não guarda contato (app/auditoria.py).
    """
    assunto, corpo = mensagem_de_confirmacao(codigo)
    if email_ses.email_configurado():
        try:
            email_ses.enviar_email(destinatario=email, assunto=assunto, corpo=corpo)
        except Exception as erro:  # o SES fora não pode virar 500 de um cadastro que já foi gravado
            log.error(
                "[AÇÃO NECESSÁRIA] o SES não enviou o código de confirmação para %s (%s)",
                mascarar_email(email), type(erro).__name__,
            )
            return False
        return True
    if get_settings().app_env == "dev":
        log.warning("[DEV] SES não configurado — o código de confirmação para %s é %s", mascarar_email(email), codigo)
        return True
    log.error(
        "[AÇÃO NECESSÁRIA] SES não configurado (AWS_SES_* e EMAIL_REMETENTE): o código de "
        "confirmação de um e-mail de conta de IA não foi enviado"
    )
    return False


# ─── Rotas ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[EmailDaIa])
def listar_emails(user: dict = Depends(get_current_coordenador)) -> list[EmailDaIa]:
    """Os e-mails ATIVOS da própria conta, do mais antigo ao mais novo — os
    confirmados e os que aguardam o código (`confirmadoEm` nulo), que o card
    mostra com o campo do código. Os removidos ficam no banco (regra 2), fora
    da lista: não aprovam mais nada."""
    linhas = (
        get_supabase()
        .table("email_conta_ia_mcp")
        .select(_COLUNAS)
        .eq("usuario_coordenacao_id", str(user.get("sub")))
        .is_("removido_em", "null")
        .order("criado_em")
        .execute()
        .data
        or []
    )
    return [_email(linha) for linha in linhas]


@router.post("", status_code=201, response_model=EmailDaIa)
def cadastrar_email(
    body: CadastrarEmailBody,
    request: Request,
    user: dict = Depends(get_current_coordenador),
) -> EmailDaIa:
    """Cadastra um e-mail de conta de IA em nome de QUEM PEDE, AGUARDANDO, e
    manda a ele o código que o confirma (regra 0). 409 se ele já está
    confirmado em qualquer conta ATIVA, ou ativo nesta (regra 1); o de conta
    desativada é liberado aqui, depois das recusas (400, 429) e antes de gravar.

    Grava antes de enviar: o índice da 0073 recusa o cadastro repetido ANTES
    de sair e-mail nenhum. Se o envio falha, o cadastro fica na lista,
    aguardando, e a resposta é 503 — quem pede está logado e é o dono dele, e
    o "enviar outro código" da linha resolve quando o SES voltar.
    """
    sub = str(user.get("sub"))
    cliente = get_supabase()
    tabela = "email_conta_ia_mcp"
    if _ativo_na_conta(cliente, sub, body.email):
        raise HTTPException(status_code=409, detail=_JA_CADASTRADO)
    dono_ativo, presos = _donos_do_confirmado(cliente, body.email)
    if dono_ativo:
        raise HTTPException(status_code=409, detail=_JA_CADASTRADO)
    ativos = (
        cliente.table(tabela).select("id", count="exact").eq("usuario_coordenacao_id", sub)
        .is_("removido_em", "null").limit(1).execute()
    )
    if (ativos.count or 0) >= MAXIMO_DE_EMAILS_POR_CONTA:
        raise HTTPException(
            status_code=400,
            detail=f"Uma conta tem no máximo {MAXIMO_DE_EMAILS_POR_CONTA} e-mails de IA. Remova um antes.",
        )
    _admitir_codigo(sub, body.email)
    _liberar_de_conta_desativada(cliente, presos, sub=sub, ip=_ip(request))
    # O id nasce aqui, e não no banco: o hash do código é preso a ele.
    email_id = str(uuid.uuid4())
    codigo, colunas_do_codigo = _novo_codigo(email_id, body.email)
    try:
        linha = (
            cliente.table(tabela)
            .insert(
                {
                    "id": email_id, "usuario_coordenacao_id": sub, "email": body.email,
                    "criado_em": _agora(), **colunas_do_codigo,
                },
                returning="representation",
            )
            .execute()
        ).data[0]
    except Exception as erro:
        if not _recusa_de_indice(erro):
            raise
        raise HTTPException(status_code=409, detail=_JA_CADASTRADO) from erro

    auditar(
        cliente, ACAO_EMAIL_CADASTRADO, canal=CANAL,
        ator_tipo="coordenador", ator_id=sub,
        recurso=_recurso(email_id), ip=_ip(request),
        # Mascarado: a trilha guarda quem e quando, não contato (app/auditoria.py).
        detalhe={"email": mascarar_email(body.email)},
    )
    if not _enviar_codigo_de_confirmacao(body.email, codigo):
        raise HTTPException(status_code=503, detail=_CODIGO_NAO_SAIU_NO_CADASTRO)
    return _email(linha)


@router.post("/{email_id}/confirmar", response_model=EmailDaIa)
def confirmar_email(
    email_id: str,
    body: ConfirmarEmailBody,
    request: Request,
    user: dict = Depends(get_current_coordenador),
) -> EmailDaIa:
    """Confirma o e-mail com o código que chegou a ele: daqui em diante ele
    recebe o código de aprovar e aprova em nome desta conta (regra 0).

    O mecanismo do /aprovar do consentimento (routes/oauth_mcp._conferir_codigo):
    a tentativa é gasta ANTES de comparar, num UPDATE condicional na contagem
    que se leu — dez chutes ao mesmo tempo não viram dez comparações —, e a
    confirmação é outro UPDATE condicional (`confirmado_em IS NULL`). Já
    confirmado, devolve o mesmo item, sem segundo evento.
    """
    email_id = _id_ou_404(email_id)
    sub = str(user.get("sub"))
    cliente = get_supabase()
    tabela = "email_conta_ia_mcp"
    linha = _ativo_da_conta(cliente, email_id, sub)
    if linha.get("confirmado_em") is not None:
        return _email(linha)

    agora = datetime.now(UTC)
    codigo = codigo_no_formato(body.codigo)
    tentativas = int(linha.get("tentativas_de_confirmacao") or 0)
    if (
        codigo is None
        or not linha.get("hash_codigo_de_confirmacao")
        or _vencido(linha.get("confirmacao_expira_em"), agora)
        or tentativas >= TENTATIVAS_POR_CODIGO
    ):
        raise HTTPException(status_code=400, detail=_CODIGO_RECUSADO)
    gasta = (
        cliente.table(tabela)
        .update({"tentativas_de_confirmacao": tentativas + 1})
        .eq("id", email_id)
        .eq("tentativas_de_confirmacao", tentativas)
        .is_("confirmado_em", "null")
        .is_("removido_em", "null")
        .execute()
        .data
        or []
    )
    if not gasta:
        # Outro chute ganhou a vez de gastar a tentativa — ou outra aba já
        # confirmou: quem perde a vez não compara (o /aprovar faz o mesmo).
        return _confirmado_ou_400(cliente, email_id, sub)
    esperado = hash_da_confirmacao(chave_dos_hashes(get_settings().jwt_secret_key), email_id, linha["email"], codigo)
    if not hmac.compare_digest(esperado, str(linha.get("hash_codigo_de_confirmacao") or "")):
        raise HTTPException(status_code=400, detail=_CODIGO_RECUSADO)
    # Um e-mail, um dono (regra 1): outra conta pode tê-lo confirmado enquanto
    # este aguardava — o dono da caixa é um só, mas digitar é de qualquer um.
    # Se a conta que confirmou foi desativada depois, o cadastro dela é
    # liberado aqui: sem isso, o índice da 0073 recusaria esta confirmação, e
    # cadastrar de novo é 409 na própria conta.
    dono_ativo, presos = _donos_do_confirmado(cliente, linha["email"], exceto=email_id)
    if dono_ativo:
        raise HTTPException(status_code=409, detail=_JA_CADASTRADO)
    _liberar_de_conta_desativada(cliente, presos, sub=sub, ip=_ip(request))
    try:
        confirmadas = (
            cliente.table(tabela)
            .update({
                "confirmado_em": _instante(agora),
                "hash_codigo_de_confirmacao": None,
                "confirmacao_expira_em": None,
            })
            .eq("id", email_id)
            .is_("confirmado_em", "null")
            .is_("removido_em", "null")
            .execute()
            .data
            or []
        )
    except Exception as erro:
        if not _recusa_de_indice(erro):
            raise
        raise HTTPException(status_code=409, detail=_JA_CADASTRADO) from erro
    if not confirmadas:
        # Outra aba confirmou, ou removeu, entre a conferência e aqui.
        return _confirmado_ou_400(cliente, email_id, sub)

    auditar(
        cliente, ACAO_EMAIL_CONFIRMADO, canal=CANAL,
        ator_tipo="coordenador", ator_id=sub,
        recurso=_recurso(email_id), ip=_ip(request),
        detalhe={"email": mascarar_email(linha["email"])},
    )
    return _email({**linha, **confirmadas[0]})


@router.post("/{email_id}/reenviar", status_code=202, response_model=CodigoDeConfirmacao)
def reenviar_codigo(
    email_id: str,
    request: Request,
    user: dict = Depends(get_current_coordenador),
) -> CodigoDeConfirmacao:
    """Manda outro código de confirmação ao e-mail que aguarda: o anterior
    morre na hora, e as tentativas voltam a cinco. Confirmado, é 409 — não há
    o que confirmar. Grava antes de enviar, como o cadastro: se o envio falha,
    é 503, e nenhum código vale até o próximo pedido."""
    email_id = _id_ou_404(email_id)
    sub = str(user.get("sub"))
    cliente = get_supabase()
    linha = _ativo_da_conta(cliente, email_id, sub)
    if linha.get("confirmado_em") is not None:
        raise HTTPException(status_code=409, detail=_JA_CONFIRMADO)
    _admitir_codigo(sub, linha["email"])
    codigo, colunas_do_codigo = _novo_codigo(email_id, linha["email"])
    trocadas = (
        cliente.table("email_conta_ia_mcp")
        .update(colunas_do_codigo)
        .eq("id", email_id)
        .is_("confirmado_em", "null")
        .is_("removido_em", "null")
        .execute()
        .data
        or []
    )
    if not trocadas:
        # Removido (404, na releitura) ou confirmado (409) entre a leitura e aqui.
        if _ativo_da_conta(cliente, email_id, sub).get("confirmado_em") is not None:
            raise HTTPException(status_code=409, detail=_JA_CONFIRMADO)
        raise HTTPException(status_code=503, detail=_CODIGO_NAO_SAIU)
    log.info("código de confirmação reenviado para o e-mail de IA %s", email_id)
    if not _enviar_codigo_de_confirmacao(linha["email"], codigo):
        raise HTTPException(status_code=503, detail=_CODIGO_NAO_SAIU)
    return CodigoDeConfirmacao(enviado=True)


@router.post("/{email_id}/remover", response_model=EmailDaIaRemovido)
def remover_email(
    email_id: str,
    request: Request,
    user: dict = Depends(get_current_coordenador),
) -> EmailDaIaRemovido:
    """Remove na hora: o próximo /codigo para este e-mail não envia nada, e o
    código que já tinha saído não aprova (regra 2). Remover de novo devolve o
    mesmo instante, sem segundo evento."""
    # Id torto é 404, não 500: o PostgREST recusaria o texto num uuid.
    try:
        email_id = str(uuid.UUID(email_id))
    except ValueError:
        raise HTTPException(status_code=404, detail=_NAO_ENCONTRADO) from None

    sub = str(user.get("sub"))
    cliente = get_supabase()
    tabela = "email_conta_ia_mcp"
    linhas = cliente.table(tabela).select(_COLUNAS).eq("id", email_id).limit(1).execute().data or []
    if not linhas or str(linhas[0]["usuario_coordenacao_id"]) != sub:
        raise HTTPException(status_code=404, detail=_NAO_ENCONTRADO)
    linha = linhas[0]

    if linha.get("removido_em") is None:
        removida = (
            cliente.table(tabela)
            .update({"removido_em": _agora()}, returning="representation")
            .eq("id", email_id)
            # Duas remoções ao mesmo tempo: só a primeira grava.
            .is_("removido_em", "null")
            .execute()
            .data
            or []
        )
        if removida:
            linha = {**linha, "removido_em": removida[0].get("removido_em")}
            auditar(
                cliente, ACAO_EMAIL_REMOVIDO, canal=CANAL,
                ator_tipo="coordenador", ator_id=sub,
                recurso=_recurso(email_id), ip=_ip(request),
                detalhe={"email": mascarar_email(linha["email"])},
            )
        else:
            linha = (cliente.table(tabela).select(_COLUNAS).eq("id", email_id).limit(1).execute().data or [linha])[0]

    return EmailDaIaRemovido(id=email_id, removidoEm=str(linha["removido_em"]))
