"""Avisos neste aparelho — inscrever, listar, revogar e testar (docs/45 §5.3).

A mesma rota para aluno e coordenação, como a foto de perfil: o dono sai do `tipo`
do JWT, e só dele. Nenhum id de dono é aceito no corpo da requisição.

⚠️ **Fail-closed por tipo de sessão.** `_dono_da_sessao` tem um ramo por tipo
conhecido e levanta 403 no resto — é a lição do docs/38 §1.1 e do PR #7: o `else`
genérico vira, no dia em que um terceiro tipo aparece, acesso ao ramo mais
poderoso. A cantina recebe 403 de propósito: a tela dela já tem tempo real por SSE,
e push para ela só entra quando um evento pedir.

Nenhum EVENTO manda push daqui. O único envio é o `POST /push/teste`, que manda
para os aparelhos DA PRÓPRIA pessoa e de mais ninguém.

Os handlers são `def`: o cliente PostgREST é síncrono, e o envio também
(app/push/envio.py) — vão para o threadpool do FastAPI em vez de travar o event
loop do único worker (api/CLAUDE.md, "Convenções").
"""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from typing import Literal

from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..auditoria import registrar as auditar
from ..auth import get_current_user
from ..push import endpoints, envio
from ..push.chaves import chave_do_servidor, de_b64url
from ..supabase_client import get_supabase

router = APIRouter(prefix="/push", tags=["push"])

TABELA = envio.TABELA

#: Teto do botão "Testar", por pessoa. Na memória do processo: com
#: `UVICORN_WORKERS=1` (armadilha 5) ele é exato, e com mais workers só ficaria
#: mais frouxo — nunca mais restrito. É um botão de teste, não uma cota.
TESTES_POR_HORA = 5
_testes: dict[str, deque[float]] = defaultdict(deque)
_trava_testes = threading.Lock()


def _dono_da_sessao(user: dict) -> envio.Dono:
    if user.get("tipo") == "aluno" and user.get("aluno_id"):
        return envio.Dono("aluno_id", str(user["aluno_id"]))
    if user.get("tipo") == "coordenador" and user.get("sub"):
        return envio.Dono("usuario_coordenacao_id", str(user["sub"]))
    raise HTTPException(status_code=403, detail="Este tipo de conta não recebe avisos no aparelho.")


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ─── Configuração ──────────────────────────────────────────────────────────


@router.get("/configuracao")
def configuracao(user: dict = Depends(get_current_user)) -> dict:
    """Se a seção "Avisos neste aparelho" aparece, e com que chave o navegador se inscreve.

    `ativo: false` cobre dois casos que a tela trata igual: o servidor sem chave
    VAPID e a sessão de um tipo que não recebe push.
    """
    chave = chave_do_servidor()
    if chave is None or user.get("tipo") not in ("aluno", "coordenador"):
        return {"ativo": False, "chavePublica": None}
    return {"ativo": True, "chavePublica": chave.publica_b64url}


# ─── Inscrições ────────────────────────────────────────────────────────────


class ChavesDaInscricao(BaseModel):
    p256dh: str = Field(max_length=200)
    auth: str = Field(max_length=100)


class InscricaoBody(BaseModel):
    """O `PushSubscription.toJSON()` do navegador, mais o que a tela sabe do aparelho."""

    endpoint: str = Field(max_length=endpoints.TAMANHO_MAXIMO)
    chaves: ChavesDaInscricao
    plataforma: Literal["ios", "android", "desktop", "outra"]
    descricao_aparelho: str | None = Field(default=None, max_length=80)


def _validar_chaves(chaves: ChavesDaInscricao) -> None:
    try:
        p256dh = de_b64url(chaves.p256dh)
        auth = de_b64url(chaves.auth)
        # Confere que é um ponto DA CURVA, não só 65 bytes: chave torta aqui só
        # apareceria no primeiro envio, longe de quem a mandou.
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), p256dh)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail="As chaves da inscrição do navegador são inválidas.") from erro
    if len(p256dh) != 65 or len(auth) != 16:
        raise HTTPException(status_code=422, detail="As chaves da inscrição do navegador são inválidas.")


@router.post("/inscricoes")
def inscrever(body: InscricaoBody, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Upsert pelo endpoint — SÓ do clique em "Ativar avisos". A reconciliação é `confirmar`.

    Endpoint que já é de outro dono MUDA de dono: num computador compartilhado, o
    aparelho é de quem ativou por último, e o aviso de quem saiu não aparece mais
    na tela de quem entrou (docs/45 §5.3).
    """
    dono = _dono_da_sessao(user)
    if chave_do_servidor() is None:
        raise HTTPException(status_code=503, detail="Os avisos no aparelho não estão ligados neste servidor.")
    try:
        endpoints.validar(body.endpoint)
    except endpoints.EndpointRecusado as erro:
        raise HTTPException(status_code=422, detail=f"Este navegador não pode receber avisos: {erro}.") from erro
    _validar_chaves(body.chaves)

    cliente = get_supabase()
    anterior = (
        cliente.table(TABELA)
        .select("id, aluno_id, usuario_coordenacao_id")
        .eq("endpoint", body.endpoint)
        .limit(1)
        .execute()
    ).data or []

    linha = {
        "endpoint": body.endpoint,
        "chave_p256dh": body.chaves.p256dh,
        "chave_auth": body.chaves.auth,
        "plataforma": body.plataforma,
        "descricao_aparelho": (body.descricao_aparelho or "").strip() or None,
        # As duas colunas sempre, uma delas nula: é o que faz a troca de dono
        # apagar o dono anterior em vez de somar a ele (e violar o CHECK).
        "aluno_id": dono.id if dono.coluna == "aluno_id" else None,
        "usuario_coordenacao_id": dono.id if dono.coluna == "usuario_coordenacao_id" else None,
        "vista_em": datetime.now(UTC).isoformat(),
        "falhas_seguidas": 0,
    }
    salvo = cliente.table(TABELA).upsert(linha, on_conflict="endpoint").execute().data or []
    if not salvo:
        raise HTTPException(status_code=500, detail="Não foi possível guardar a inscrição.")

    novo_para_esta_pessoa = not anterior or str(anterior[0].get(dono.coluna) or "") != dono.id
    if novo_para_esta_pessoa:
        auditar(
            cliente, "push_aparelho_ativado", canal="acesso",
            ator_tipo=user.get("tipo"), ator_id=dono.id, recurso=f"{TABELA}/{salvo[0]['id']}",
            ip=_ip(request),
            # Nunca o endpoint nem as chaves: identificam o aparelho.
            detalhe={"plataforma": body.plataforma, "trocou_de_dono": bool(anterior)},
        )
    return {"id": salvo[0]["id"]}


@router.post("/inscricoes/confirmar")
def confirmar(body: InscricaoBody, user: dict = Depends(get_current_user)) -> dict:
    """A reconciliação de cada abertura: CONFIRMA uma inscrição que já é da pessoa.

    ⚠️ **Nunca cria e nunca transfere** (docs/45 §6.1). Se a abertura do casco
    fizesse upsert, três coisas que a pessoa decidiu seriam desfeitas sem ela
    saber: o aparelho revogado na lista de outro aparelho voltaria sozinho; quem
    entrasse depois num computador compartilhado herdaria os avisos de quem saiu
    sem ter pedido; e um "Desativar" mal sincronizado voltaria no dia seguinte.
    Toda inscrição nasce de um clique (`inscrever`) — é também o consentimento.

    `registrada: false` faz a tela mostrar "Ativar" de novo, que é a verdade: este
    navegador tem a inscrição, mas o SAS não a tem em nome desta pessoa.
    """
    dono = _dono_da_sessao(user)
    if chave_do_servidor() is None:
        return {"registrada": False, "id": None}
    _validar_chaves(body.chaves)
    atualizadas = (
        get_supabase()
        .table(TABELA)
        .update({
            "vista_em": datetime.now(UTC).isoformat(),
            "chave_p256dh": body.chaves.p256dh,
            "chave_auth": body.chaves.auth,
            "descricao_aparelho": (body.descricao_aparelho or "").strip() or None,
        })
        .eq("endpoint", body.endpoint)
        .eq(dono.coluna, dono.id)
        .execute()
    ).data or []
    if not atualizadas:
        return {"registrada": False, "id": None}
    return {"registrada": True, "id": atualizadas[0]["id"]}


@router.get("/inscricoes")
def listar(user: dict = Depends(get_current_user)) -> dict:
    """"Seus aparelhos". Sem endpoint e sem chaves na resposta."""
    dono = _dono_da_sessao(user)
    linhas = (
        get_supabase()
        .table(TABELA)
        .select("id, plataforma, descricao_aparelho, criada_em, vista_em, ultimo_envio_ok_em, ultimo_status_http")
        .eq(dono.coluna, dono.id)
        .order("criada_em")
        .execute()
    ).data or []
    return {
        "aparelhos": [
            {
                "id": l["id"],
                "plataforma": l["plataforma"],
                "descricao": l.get("descricao_aparelho"),
                "criadaEm": l.get("criada_em"),
                "vistaEm": l.get("vista_em"),
                "ultimoEnvioOkEm": l.get("ultimo_envio_ok_em"),
                "ultimoStatusHttp": l.get("ultimo_status_http"),
            }
            for l in linhas
        ]
    }


def _remover(user: dict, request: Request, campo: str, valor: str, motivo: str) -> bool:
    dono = _dono_da_sessao(user)
    cliente = get_supabase()
    removidas = (
        cliente.table(TABELA).delete().eq(campo, valor).eq(dono.coluna, dono.id).execute()
    ).data or []
    if removidas:
        auditar(
            cliente, "push_aparelho_removido", canal="acesso",
            ator_tipo=user.get("tipo"), ator_id=dono.id, recurso=f"{TABELA}/{removidas[0]['id']}",
            ip=_ip(request), detalhe={"motivo": motivo},
        )
    return bool(removidas)


@router.delete("/inscricoes/{inscricao_id}")
def revogar(inscricao_id: str, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """Revoga um aparelho da lista — inclusive outro que não este."""
    try:
        uuid.UUID(inscricao_id)
    except ValueError as erro:
        # Sem isto o PostgREST devolve 22P02 e a pessoa vê 500.
        raise HTTPException(status_code=404, detail="Aparelho não encontrado.") from erro
    if not _remover(user, request, "id", inscricao_id, "revogado_na_lista"):
        raise HTTPException(status_code=404, detail="Aparelho não encontrado.")
    return {"ok": True}


class RemocaoBody(BaseModel):
    endpoint: str = Field(max_length=endpoints.TAMANHO_MAXIMO)


@router.post("/inscricoes/remover")
def desativar_neste_aparelho(body: RemocaoBody, request: Request, user: dict = Depends(get_current_user)) -> dict:
    """"Desativar neste aparelho" e o Sair.

    POST com o endpoint no CORPO, e não DELETE com ele na query: a URL vai para o
    log do nginx, e o endpoint identifica o aparelho.
    """
    return {"removida": _remover(user, request, "endpoint", body.endpoint, "desativado_no_aparelho")}


# ─── Teste ─────────────────────────────────────────────────────────────────


def _cabe_mais_um_teste(chave: str, agora: float) -> bool:
    with _trava_testes:
        janela = _testes[chave]
        while janela and agora - janela[0] > 3600:
            janela.popleft()
        if len(janela) >= TESTES_POR_HORA:
            return False
        janela.append(agora)
        return True


@router.post("/teste")
def testar(user: dict = Depends(get_current_user)) -> dict:
    """Manda um aviso de teste para TODOS os aparelhos da própria pessoa.

    É a prova de ponta a ponta que a tela oferece: chave VAPID, cifra, serviço do
    fabricante, service worker e o toque que abre o SAS.
    """
    dono = _dono_da_sessao(user)
    if chave_do_servidor() is None:
        raise HTTPException(status_code=503, detail="Os avisos no aparelho não estão ligados neste servidor.")
    if not _cabe_mais_um_teste(f"{dono.coluna}:{dono.id}", time.monotonic()):
        raise HTTPException(status_code=429, detail="Você já testou várias vezes nesta hora. Tente mais tarde.")

    notificacao = envio.Notificacao(
        tipo="teste",
        titulo="Avisos do SAS ligados",
        corpo="É assim que os avisos vão chegar neste aparelho. Toque para abrir o SAS.",
        url="/",
        tag="teste",
        # Teste que chega uma hora depois não testa nada.
        ttl_segundos=600,
        urgencia="high",
    )
    resultado = envio.enviar_para_dono(get_supabase(), dono, notificacao)
    return resultado.como_dict()
