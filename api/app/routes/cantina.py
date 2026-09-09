"""Cantina — cardápio, pedido do aluno e a leitura da coordenação (docs/38).

Três públicos e três routers, e a separação NÃO é organização de arquivo: é o
contorno de segurança. Cada router tem o seu guard no piso, então nenhuma rota
nova nasce sem dono:

  * `router` (`/cantina`)          — a cantina lança e lê o que é dela;
  * `router_aluno` (`/me/cantina`) — o aluno vê o que pode e pede;
  * `router_admin` (`/administracao`) — quem tem direito, e as contas.

São **dois jeitos de comer**, e os dois vivem na mesma linha de
`pedido_refeicao` (docs/40 §1): `modo = "pedido"` escolhe itens dentro do prazo,
e `modo = "presencial"` só declara presença e conclui na leitura do QR
(`retirado_em`). A transição entre eles é ASSIMÉTRICA de propósito — ver
`_cardapio_para_retirada` e o §2 do plano.

⚠️ **Toda consulta da cantina filtra pelo `cantina_id` DO TOKEN, nunca por
parâmetro.** Sem isso, uma cantina lê o cardápio da outra trocando um id na URL
(docs/38 §3.3). A coordenação é a única que pode pedir uma cantina específica,
porque ela enxerga todas por desenho.

⚠️ **O backend nunca escreve SQL** (CLAUDE.md): tudo aqui é `.table(...)` do
PostgREST. Por isso as regras que um banco resolveria com CHECK ou trigger —
teto de escolhas por bloco, prazo, direito à refeição — são Python, e por isso
precisam de teste. As duas agregações que seriam caras em Python viraram VIEW
na 0049 (`v_contagem_pedidos_por_opcao`, `v_pedidos_por_cardapio`), porque não
existe paginação em lugar nenhum e `pedido_refeicao_item` é a primeira tabela
do projeto que cresce por dia × aluno × item. A 0052 quebrou
`v_pedidos_por_cardapio` por modo, porque desde a retirada presencial o número
do calendário e a contagem por opção respondem a perguntas diferentes e
pareciam responder à mesma (docs/40 §10.1).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .. import cantina_relatorio, senha_definida
from ..auditoria import registrar as auditar
from ..auth import (
    get_current_administrador,
    get_current_aluno,
    get_current_cantina,
    get_current_coordenador,
    hash_senha,
)
from ..banco.missao import FUSO_DA_ESCOLA
from ..cantina_eventos import (
    Evento,
    barramento,
    cabecalhos_sse,
    fluxo_sse,
    para_a_cantina,
    para_a_coordenacao,
    para_o_aluno,
    publicar_cardapio_mudou,
)
from ..cantina_token import (
    SEGUNDOS_DA_JANELA,
    RetiradaIlegivel,
    assinar_retirada,
    janela_de,
    ler_qr_rotativo,
    ler_retirada,
    semente_da_retirada,
)
from ..supabase_client import ClienteDados, get_supabase

REFEICOES = ("almoco", "janta")

#: Os dois jeitos de comer (docs/40 §1). `pedido` escolhe itens com
#: antecedência e compromete a cozinha; `presencial` é declaração de presença,
#: sem prato, e só vira compromisso quando o QR é lido.
MODO_PEDIDO = "pedido"
MODO_PRESENCIAL = "presencial"

#: A regra da casa, coluna a coluna (0051). Uma lista só porque os quatro nomes
#: aparecem em três lugares — corpo, insert e patch —, e um esquecido ali é uma
#: coluna que a tela mostra e ninguém consegue mudar.
CAMPOS_DE_MODO_DA_CASA = (
    "aceita_pedido_almoco",
    "aceita_pedido_janta",
    "aceita_presencial_almoco",
    "aceita_presencial_janta",
)

# `FUSO_DA_ESCOLA` vem de `banco/missao.py`, e o import atravessa módulos de
# propósito: é o MESMO fuso que decide qual é "hoje" na missão do dia. A escola
# é uma só, e duas definições de "hoje" no mesmo produto divergem no primeiro
# caso de borda — aqui seria um cardápio aparecendo um dia antes para quem abre
# o app às 22h.

#: Quanto o aluno enxerga à frente (docs/38 §8.0.6). "Todos os dias já
#: publicados" sem janela vira uma resposta que cresce em silêncio no dia em
#: que alguém lançar o semestre inteiro — e não existe paginação em lugar
#: nenhum (CLAUDE.md, armadilha 2). Trinta dias cobrem qualquer antecedência
#: real de cardápio.
DIAS_VISIVEIS_PARA_O_ALUNO = 30

router = APIRouter(prefix="/cantina", tags=["cantina"])
router_aluno = APIRouter(
    prefix="/me/cantina", tags=["cantina"], dependencies=[Depends(get_current_aluno)]
)
router_admin = APIRouter(
    prefix="/administracao", tags=["cantina"], dependencies=[Depends(get_current_coordenador)]
)


# ─── Peças comuns ─────────────────────────────────────────────────────────


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _agora() -> datetime:
    return datetime.now(UTC)


def _instante(bruto: str | None) -> datetime | None:
    """timestamptz do PostgREST → datetime com fuso.

    O PostgREST devolve ISO-8601 já com offset; o `replace` cobre o `Z` que
    algumas versões emitem e que o `fromisoformat` do Python só aceita a
    partir do 3.11.
    """
    if not bruto:
        return None
    return datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))


def _prazo_pela_regra(cantina: dict, dia: date) -> datetime:
    """O `pedidos_ate` que a REGRA da casa produz para essa data (docs/38 §8.0.1).

    A regra é da cantina e o prazo é do dia: isto só pré-preenche. O resultado
    é absoluto (UTC) porque "ainda aceita pedido?" tem de ser uma comparação, e
    não uma conta refeita a cada leitura.
    """
    # Os fallbacks espelham os DEFAULT da 0047 de propósito: uma linha que
    # chegue sem os campos (base antiga, select parcial) tem de produzir o
    # mesmo prazo que o banco produziria, senão o prazo passa a depender da
    # origem da linha.
    bruto_dias = cantina.get("prazo_padrao_dias_antes")
    dias_antes = int(bruto_dias) if bruto_dias is not None else 1
    hora_bruta = str(cantina.get("prazo_padrao_hora") or "20:00")
    local = datetime.combine(
        dia - timedelta(days=dias_antes),
        time.fromisoformat(hora_bruta),
        tzinfo=FUSO_DA_ESCOLA,
    )
    return local.astimezone(UTC)


def _modos_pela_regra(cantina: dict, refeicao: str) -> tuple[bool, bool]:
    """Que modos a REGRA da casa liga num cardápio novo daquela refeição (docs/40 §1).

    Mesmo papel de `_prazo_pela_regra`: isto só pré-preenche, e o valor do dia é
    do cardápio. Os fallbacks espelham os DEFAULT da 0051 — pedido ligado,
    presencial desligado —, senão o modo passaria a depender da origem da linha.
    """
    aceita_pedido = cantina.get(f"aceita_pedido_{refeicao}")
    aceita_presencial = cantina.get(f"aceita_presencial_{refeicao}")
    return (
        True if aceita_pedido is None else bool(aceita_pedido),
        False if aceita_presencial is None else bool(aceita_presencial),
    )


def _modos_do_cardapio(cardapio: dict) -> tuple[bool, bool]:
    """O que ESTE dia aceita. Os mesmos fallbacks da 0051, pelo mesmo motivo."""
    aceita_pedido = cardapio.get("aceita_pedido")
    aceita_presencial = cardapio.get("aceita_presencial")
    return (
        True if aceita_pedido is None else bool(aceita_pedido),
        False if aceita_presencial is None else bool(aceita_presencial),
    )


def _estado(cardapio: dict, agora: datetime) -> str:
    """Os CINCO estados do calendário (docs/38 §3.3).

    `aberto` e `fechado` são o mesmo cardápio publicado antes e depois do
    prazo, e a diferença é a que a cantina mais precisa ler: em `fechado` a
    contagem é final, e é ela que vai para o fogão.
    """
    if cardapio.get("sem_refeicao"):
        return "sem-refeicao"
    if not cardapio.get("publicado_em"):
        return "rascunho"
    prazo = _instante(cardapio.get("pedidos_ate"))
    if prazo is None or agora >= prazo:
        return "fechado"
    return "aberto"


def _cantina_por_id(cliente: ClienteDados, cantina_id: str) -> dict:
    linha = (
        cliente.table("cantina").select("*").eq("id", cantina_id).limit(1).execute().data
    )
    if not linha:
        raise HTTPException(status_code=404, detail="cantina não encontrada")
    return linha[0]


def _cardapio_da_cantina(cliente: ClienteDados, cardapio_id: str, cantina_id: str) -> dict:
    """O cardápio, confirmando que ele é DESTA cantina.

    O `eq("cantina_id", ...)` não é redundante com o 404: sem ele a rota
    responderia sobre o cardápio de outra cantina para quem soubesse o uuid.
    Devolver 404 (e não 403) para o de outra é deliberado — a existência do
    recurso alheio também é informação.
    """
    linha = (
        cliente.table("cardapio")
        .select("*")
        .eq("id", cardapio_id)
        .eq("cantina_id", cantina_id)
        .limit(1)
        .execute()
        .data
    )
    if not linha:
        raise HTTPException(status_code=404, detail="cardápio não encontrado")
    return linha[0]


def _blocos_por_cardapio(
    cliente: ClienteDados, cardapio_ids: list[str]
) -> dict[str, list[dict]]:
    """Blocos e opções de VÁRIOS cardápios, numa ida só.

    ⚠️ Existe por causa de um N+1 medido, não por elegância: `cantina_do_aluno`
    chamava `_montar_cardapio` dentro do `for`, e uma semana lançada com almoço
    e janta são ~10 idas ao PostgREST **em série** — cada uma bloqueando o event
    loop, porque o cliente é síncrono (docs/40 §12.1.3). E essa rota tem
    `refetchInterval` de 60 s por aluno com direito.

    A ordenação continua em Python: o `order` do PostgREST não alcança relação
    aninhada em dois níveis, e as listas são de dezenas de itens.
    """
    if not cardapio_ids:
        return {}
    blocos = (
        cliente.table("cardapio_bloco")
        .select("*, cardapio_opcao(*)")
        .in_("cardapio_id", cardapio_ids)
        .execute()
        .data
        or []
    )
    por_cardapio: dict[str, list[dict]] = {}
    for bloco in blocos:
        opcoes = bloco.pop("cardapio_opcao", None) or []
        opcoes.sort(key=lambda o: o.get("ordem") or 0)
        bloco["opcoes"] = opcoes
        por_cardapio.setdefault(bloco["cardapio_id"], []).append(bloco)
    for lista in por_cardapio.values():
        lista.sort(key=lambda b: b.get("ordem") or 0)
    return por_cardapio


def _montar_cardapio(
    cliente: ClienteDados,
    cardapio: dict,
    agora: datetime,
    *,
    blocos: list[dict] | None = None,
) -> dict:
    """Cardápio + blocos + opções, ordenados, prontos para a tela.

    `blocos` já resolvidos evitam a consulta — é como o laço de
    `cantina_do_aluno` deixou de ser N+1. Quem monta UM cardápio só continua
    chamando sem o parâmetro, e a consulta acontece aqui.
    """
    if blocos is None:
        blocos = _blocos_por_cardapio(cliente, [cardapio["id"]]).get(cardapio["id"], [])
    aceita_pedido, aceita_presencial = _modos_do_cardapio(cardapio)
    return {
        **cardapio,
        "estado": _estado(cardapio, agora),
        # Em camelCase e derivados por `_modos_do_cardapio` mesmo já viajando em
        # snake_case dentro do `**cardapio`: é o contrato da tela, e é o único
        # lugar onde o default de uma base sem a 0051 é aplicado.
        "aceitaPedido": aceita_pedido,
        "aceitaPresencial": aceita_presencial,
        "blocos": blocos,
    }


def _opcoes_com_pedido(cliente: ClienteDados, opcao_ids: list[str]) -> set[str]:
    """Quais dessas opções já foram escolhidas por alguém.

    É o que autoriza (ou recusa) a edição do cardápio publicado — docs/38 §2.5.
    """
    if not opcao_ids:
        return set()
    linhas = (
        cliente.table("pedido_refeicao_item")
        .select("opcao_id")
        .in_("opcao_id", opcao_ids)
        .execute()
        .data
        or []
    )
    return {linha["opcao_id"] for linha in linhas}


# ─── Schemas ──────────────────────────────────────────────────────────────


class OpcaoBody(BaseModel):
    #: Ausente = opção nova. Presente = opção que já existe e vai ser atualizada.
    #: É o `id` que permite renomear com segurança: sem ele, toda edição seria
    #: apagar e recriar, e o pedido de quem já escolheu apontaria para o vazio.
    id: str | None = None
    nome: str
    disponivel: bool = True


class BlocoBody(BaseModel):
    #: A regra que o número não expressa — "a escolha da opção 4 anula a 1 e a
    #: 2" (migration 0053). ⚠️ É ESCRITA, não vigiada: o servidor não recusa a
    #: combinação que ela proíbe (docs/40 §12.5.4).
    observacao: str | None = None
    id: str | None = None
    nome: str
    escolhas_minimas: int = Field(default=0, ge=0)
    escolhas_maximas: int = Field(default=1, ge=0)
    opcoes: list[OpcaoBody] = Field(default_factory=list)


class CardapioBody(BaseModel):
    """O corpo do editor. A ORDEM dos blocos e das opções é a da lista — o
    índice vira a coluna `ordem`, e não há campo separado para ela: dois lugares
    dizendo a mesma ordem divergem no primeiro arrastar-e-soltar."""

    pedidos_ate: datetime | None = None
    sem_refeicao: bool = False
    # `None` = "não mexi neste campo", como os valores de `EditarCantinaBody`.
    # Não é `bool = True`: um editor antigo, que ainda não conhece os dois
    # toggles, desligaria o presencial da cantina a cada salvamento — e a perda
    # seria silenciosa, descoberta só no balcão (docs/40 §1).
    aceita_pedido: bool | None = None
    aceita_presencial: bool | None = None
    blocos: list[BlocoBody] = Field(default_factory=list)


class NovoCardapioBody(BaseModel):
    data: date
    refeicao: str


class CopiarBody(BaseModel):
    origem_id: str


class PedidoBody(BaseModel):
    opcao_ids: list[str] = Field(default_factory=list)


class ConfirmarRetiradaBody(BaseModel):
    """O que a câmera leu do QR. Só o código assinado — nada de `aluno_id`.

    Aceitar o aluno por parâmetro faria da tela da cantina um crachá universal:
    quem tivesse a sessão do balcão marcaria qualquer um como servido. O que
    autoriza a marcação é a assinatura (docs/40 §4).
    """

    token: str


# ─── Os três streams ──────────────────────────────────────────────────────
#
# Um por público, e o recorte é do SERVIDOR: a alternativa seria um stream só
# com o cliente filtrando, e aí o aluno receberia — e poderia ler — o pedido dos
# outros 900. Autorização que depende do cliente descartar o que não é dele não
# é autorização.


@router.get("/eventos")
async def eventos_da_cantina(usuario: dict = Depends(get_current_cantina)) -> StreamingResponse:
    """O que muda no que é desta cantina, mais concessões de direito.

    O direito entra porque muda o PÚBLICO dos cardápios dela — é o aviso "agora
    alguém pode pedir" ao lado do botão de publicar.
    """
    async def fluxo():
        async with barramento.assinar(para_a_cantina(usuario["cantina_id"])) as fila:
            async for pedaco in fluxo_sse(fila):
                yield pedaco

    return StreamingResponse(fluxo(), media_type="text/event-stream", headers=cabecalhos_sse())


@router_aluno.get("/eventos")
async def eventos_do_aluno(aluno: dict = Depends(get_current_aluno)) -> StreamingResponse:
    """Mudança de cardápio, e o que for do próprio aluno."""
    async def fluxo():
        async with barramento.assinar(para_o_aluno(aluno["aluno_id"])) as fila:
            async for pedaco in fluxo_sse(fila):
                yield pedaco

    return StreamingResponse(fluxo(), media_type="text/event-stream", headers=cabecalhos_sse())


@router_admin.get("/cantina/eventos")
async def eventos_da_coordenacao() -> StreamingResponse:
    """A coordenação vê tudo — é o papel dela, e são poucas sessões abertas."""
    async def fluxo():
        async with barramento.assinar(para_a_coordenacao()) as fila:
            async for pedaco in fluxo_sse(fila):
                yield pedaco

    return StreamingResponse(fluxo(), media_type="text/event-stream", headers=cabecalhos_sse())


# ─── A cantina: calendário ────────────────────────────────────────────────


def _calendario(
    cliente: ClienteDados, cantina_id: str | list[str], de: date, ate: date
) -> list[dict]:
    """Um objeto por cardápio existente na janela, com estado e quem vai comer.

    Dia sem cardápio não vem: quem sabe quais dias existem no mês é o
    calendário da tela, e mandar 30 objetos vazios só para ele descobrir isso
    seria o servidor desenhando a grade.

    São TRÊS números de gente e não um (docs/40 §10.1). `pedidos` responde
    "quantos vão comer" — as duas portas somadas —, e é ele que pinta o dia. A
    quebra em `comPedido` e `presenciais` existe porque a contagem por opção,
    que a cantina lê para cozinhar, só soma quem escolheu prato: presencial não
    escolhe nada. Sem a quebra, os dois números parecem que deviam bater, não
    batem, e viram chamado de bug.
    """
    agora = _agora()
    # Uma cantina ou várias na MESMA consulta. A versão que aceitava só uma
    # levava quem quisesse o total a chamar isto num `for` — e duas idas por
    # cantina é o N+1 que a §12.1.3 tirou da rota do aluno; reintroduzi-lo aqui
    # no mesmo trabalho seria trocar de lugar, não consertar.
    ids = [cantina_id] if isinstance(cantina_id, str) else list(cantina_id)
    if not ids:
        return []
    consulta = (
        cliente.table("cardapio")
        .select(
            "id, cantina_id, data, refeicao, pedidos_ate, publicado_em, sem_refeicao, "
            "aceita_pedido, aceita_presencial"
        )
    )
    consulta = consulta.eq("cantina_id", ids[0]) if len(ids) == 1 else consulta.in_("cantina_id", ids)
    cardapios = (
        consulta
        .gte("data", de.isoformat())
        .lte("data", ate.isoformat())
        .execute()
        .data
        or []
    )
    if not cardapios:
        return []

    # A contagem vem da view (0049, quebrada por modo na 0052), e não de um
    # count por cardápio: o calendário mostra um mês inteiro, e contar em Python
    # exigiria trazer todos os pedidos do mês só para saber o tamanho de cada
    # dia.
    ids = [c["id"] for c in cardapios]
    contagens = (
        cliente.table("v_pedidos_por_cardapio")
        .select("cardapio_id, quantos, com_pedido, presenciais")
        .in_("cardapio_id", ids)
        .execute()
        .data
        or []
    )
    por_cardapio = {c["cardapio_id"]: c for c in contagens}

    saida = []
    for c in cardapios:
        aceita_pedido, aceita_presencial = _modos_do_cardapio(c)
        contagem = por_cardapio.get(c["id"], {})
        saida.append(
            {
                "id": c["id"],
                # O id da cantina viaja junto desde que o calendário pode somar
                # mais de uma: sem ele, dois cardápios de almoço no mesmo dia
                # são indistinguíveis na resposta.
                "cantinaId": c.get("cantina_id"),
                "data": c["data"],
                "refeicao": c["refeicao"],
                "estado": _estado(c, agora),
                "pedidosAte": c.get("pedidos_ate"),
                "pedidos": contagem.get("quantos", 0),
                "comPedido": contagem.get("com_pedido", 0),
                "presenciais": contagem.get("presenciais", 0),
                "aceitaPedido": aceita_pedido,
                "aceitaPresencial": aceita_presencial,
            }
        )
    saida.sort(key=lambda c: (c["data"], c["refeicao"]))
    return saida


@router.get("/calendario")
async def calendario_da_cantina(
    de: date,
    ate: date,
    usuario: dict = Depends(get_current_cantina),
) -> list[dict]:
    """O mês da cantina: que dias têm cardápio, em que estado, e quantos vão comer."""
    return _calendario(get_supabase(), usuario["cantina_id"], de, ate)


# ─── A cantina: o cardápio de um dia ──────────────────────────────────────


@router.post("/cardapios")
async def criar_cardapio(
    body: NovoCardapioBody,
    request: Request,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """Abre o cardápio de um dia, em RASCUNHO.

    Já nasce com o `pedidos_ate` da regra da casa. É pré-preenchimento, não
    decisão: a cantina troca no editor quando quiser, e publicar sem prazo é
    recusado (docs/38 §8.0.1).
    """
    if body.refeicao not in REFEICOES:
        raise HTTPException(status_code=422, detail=f"refeicao deve ser uma de {REFEICOES}")

    # ⚠️ Cardápio para data no PASSADO não é caso de borda — foi o primeiro
    # defeito real em produção. A cantina navegou o calendário para trás e
    # lançou três dias já vencidos: eles publicaram sem reclamar, a tela dela
    # mostrou "Contagem final", e o aluno não viu nada, porque
    # `cantina_do_aluno` só devolve `data >= hoje` (e está certa em fazer isso).
    #
    # Dia passado NUNCA aceita pedido, então criar um cardápio ali é sempre
    # engano de navegação. Recusar aqui é a barreira que faltava — a de
    # `publicar` pega o prazo vencido, mas só depois de a pessoa ter montado o
    # cardápio inteiro.
    hoje = _agora().astimezone(FUSO_DA_ESCOLA).date()
    if body.data < hoje:
        raise HTTPException(
            status_code=422,
            detail=(
                "Esse dia já passou, e um cardápio no passado não recebe pedido. "
                "Escolha hoje ou um dia à frente."
            ),
        )

    cliente = get_supabase()
    cantina = _cantina_por_id(cliente, usuario["cantina_id"])

    existente = (
        cliente.table("cardapio")
        .select("id")
        .eq("cantina_id", cantina["id"])
        .eq("data", body.data.isoformat())
        .eq("refeicao", body.refeicao)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        raise HTTPException(
            status_code=409,
            detail="Já existe cardápio para esse dia e refeição.",
        )

    aceita_pedido, aceita_presencial = _modos_pela_regra(cantina, body.refeicao)
    linha = (
        cliente.table("cardapio")
        .insert(
            {
                "cantina_id": cantina["id"],
                "data": body.data.isoformat(),
                "refeicao": body.refeicao,
                "pedidos_ate": _prazo_pela_regra(cantina, body.data).isoformat(),
                # Os modos vêm da regra da casa pelo mesmo motivo do prazo: é
                # pré-preenchimento, não decisão — a cantina troca no editor
                # (docs/40 §1).
                "aceita_pedido": aceita_pedido,
                "aceita_presencial": aceita_presencial,
                "criado_por": usuario.get("sub"),
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    auditar(
        cliente, "cardapio_criado", canal="cantina", ator_tipo="cantina",
        ator_id=usuario.get("sub"), recurso=f"cardapio/{linha['id']}", ip=_ip(request),
        detalhe={"data": body.data.isoformat(), "refeicao": body.refeicao},
    )
    # Rascunho também avisa: a coordenação e as outras abas da cantina veem o
    # dia aparecer no calendário sem recarregar.
    publicar_cardapio_mudou(linha)
    return _montar_cardapio(cliente, linha, _agora())


@router.get("/cardapios/{cardapio_id}")
async def obter_cardapio(
    cardapio_id: str,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    cliente = get_supabase()
    cardapio = _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    return _montar_cardapio(cliente, cardapio, _agora())


@router.put("/cardapios/{cardapio_id}")
async def salvar_cardapio(
    cardapio_id: str,
    body: CardapioBody,
    request: Request,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """Salva blocos e opções inteiros, e é aqui que mora a regra do §2.5.

    O corpo é o estado FINAL do cardápio: o que tem `id` é atualizado, o que
    não tem é criado, e o que sumiu é apagado. Antes de apagar ou renomear,
    conferimos quem já foi pedido — renomear "Frango Grelhado" para "Peixe"
    depois de 40 pedidos faria 40 alunos terem pedido peixe sem saber.

    A alternativa seria gravar o nome dentro do item como snapshot. Foi
    recusada: desnormaliza para proteger contra um caso que a recusa já
    resolve, e a recusa ainda ensina a cantina a publicar direito.
    """
    cliente = get_supabase()
    cardapio = _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])

    atuais = (
        cliente.table("cardapio_bloco")
        .select("id, cardapio_opcao(id, nome)")
        .eq("cardapio_id", cardapio_id)
        .execute()
        .data
        or []
    )
    nome_por_opcao = {
        o["id"]: o["nome"] for b in atuais for o in (b.get("cardapio_opcao") or [])
    }
    travadas = _opcoes_com_pedido(cliente, list(nome_por_opcao))

    blocos_enviados = {b.id for b in body.blocos if b.id}
    opcoes_enviadas = {o.id: o for b in body.blocos for o in b.opcoes if o.id}

    for opcao_id in travadas:
        if opcao_id not in opcoes_enviadas:
            raise HTTPException(
                status_code=409,
                detail=(
                    f'"{nome_por_opcao.get(opcao_id, "essa opção")}" já foi pedida por '
                    "alguém e não pode ser removida. Marque como indisponível se acabou."
                ),
            )
        if opcoes_enviadas[opcao_id].nome.strip() != nome_por_opcao.get(opcao_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    f'"{nome_por_opcao.get(opcao_id)}" já foi pedida por alguém e não pode '
                    "ser renomeada. Crie uma opção nova e marque esta como indisponível."
                ),
            )

    # Apagar o que saiu. `ON DELETE CASCADE` cuida das opções do bloco apagado
    # — e as travadas já foram barradas acima, então nenhum pedido fica órfão.
    for bloco in atuais:
        if bloco["id"] not in blocos_enviados:
            cliente.table("cardapio_bloco").delete().eq("id", bloco["id"]).execute()
    if opcoes_enviadas or nome_por_opcao:
        sobreviventes = set(opcoes_enviadas)
        for opcao_id in nome_por_opcao:
            if opcao_id not in sobreviventes:
                cliente.table("cardapio_opcao").delete().eq("id", opcao_id).execute()

    # A ORDEM é o índice da lista, nos dois níveis.
    for indice, bloco in enumerate(body.blocos):
        campos = {
            "cardapio_id": cardapio_id,
            "nome": bloco.nome.strip(),
            "ordem": indice,
            "escolhas_minimas": bloco.escolhas_minimas,
            "escolhas_maximas": max(bloco.escolhas_maximas, bloco.escolhas_minimas),
            # Vazio vira NULL, e não string vazia: são a mesma coisa para quem
            # lê, e duas representações do mesmo nada é o tipo de coisa que
            # depois vira `if obs and obs.strip()` espalhado por três telas.
            "observacao": (bloco.observacao or '').strip() or None,
        }
        if bloco.id:
            cliente.table("cardapio_bloco").update(campos).eq("id", bloco.id).execute()
            bloco_id = bloco.id
        else:
            bloco_id = (
                cliente.table("cardapio_bloco")
                .insert(campos, returning="representation")
                .execute()
            ).data[0]["id"]

        for posicao, opcao in enumerate(bloco.opcoes):
            valores = {
                "bloco_id": bloco_id,
                "nome": opcao.nome.strip(),
                "ordem": posicao,
                "disponivel": opcao.disponivel,
            }
            if opcao.id:
                cliente.table("cardapio_opcao").update(valores).eq("id", opcao.id).execute()
            else:
                cliente.table("cardapio_opcao").insert(valores).execute()

    patch = {
        "sem_refeicao": body.sem_refeicao,
        "atualizado_em": _agora().isoformat(),
        "pedidos_ate": body.pedidos_ate.isoformat() if body.pedidos_ate else None,
    }
    # Só entram se vieram: `None` aqui é "não mexi", e não "desligue" — ver o
    # comentário em `CardapioBody`. Publicar com os dois desligados é recusado,
    # mas a recusa mora em `publicar`, não aqui: no rascunho a cantina pode
    # deixar o dia em qualquer estado enquanto monta (docs/40 §1).
    if body.aceita_pedido is not None:
        patch["aceita_pedido"] = body.aceita_pedido
    if body.aceita_presencial is not None:
        patch["aceita_presencial"] = body.aceita_presencial
    atualizado = (
        cliente.table("cardapio")
        .update(patch, returning="representation")
        .eq("id", cardapio_id)
        .execute()
    ).data[0]

    auditar(
        cliente, "cardapio_editado", canal="cantina", ator_tipo="cantina",
        ator_id=usuario.get("sub"), recurso=f"cardapio/{cardapio_id}", ip=_ip(request),
        detalhe={"blocos": len(body.blocos), "data": cardapio["data"]},
    )
    publicar_cardapio_mudou(atualizado)
    return _montar_cardapio(cliente, atualizado, _agora())


@router.post("/cardapios/{cardapio_id}/publicar")
async def publicar_cardapio(
    cardapio_id: str,
    request: Request,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """Rascunho → publicado. É o instante em que o cardápio passa a existir
    para o aluno.

    As recusas são o produto, não validação de formulário: publicar sem prazo
    entregaria um cardápio que ninguém sabe até quando pode pedir; publicar sem
    opção entregaria uma tela vazia com ar de erro; e publicar sem nenhum dos
    dois modos entregaria um dia em que o aluno vê comida e não tem botão
    (docs/40 §1).
    """
    cliente = get_supabase()
    cardapio = _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    montado = _montar_cardapio(cliente, cardapio, _agora())

    if not cardapio.get("sem_refeicao"):
        aceita_pedido, aceita_presencial = _modos_do_cardapio(cardapio)
        # Primeira das recusas, e a mais fundamental: um cardápio que não aceita
        # nenhum dos dois modos não é "publicado", é `sem_refeicao` disfarçado —
        # aparece para o aluno sem nenhuma ação possível (docs/40 §1).
        if not aceita_pedido and not aceita_presencial:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Ligue pelo menos um jeito de o aluno comer: pedido com "
                    "antecedência ou retirada presencial."
                ),
            )
        # ⚠️ As duas recusas de prazo valem só para quem aceita PEDIDO. A
        # retirada presencial não olha `pedidos_ate` (docs/40 §3), e exigir
        # prazo futuro de um cardápio presencial mataria justamente o caso que
        # a feature existe para resolver: o almoço de HOJE, cujo prazo padrão
        # ("véspera às 20h") já nasce vencido.
        prazo = _instante(cardapio.get("pedidos_ate"))
        if aceita_pedido and prazo is None:
            raise HTTPException(
                status_code=422,
                detail="Defina até quando o aluno pode pedir antes de publicar.",
            )
        # ⚠️ Publicar com o prazo JÁ VENCIDO era aceito, e o resultado era um
        # cardápio invisível: `cantina_do_aluno` o devolve, mas o card não tem o
        # que mostrar e o `PUT` do pedido responde 409. Ninguém pedia, ninguém
        # via, e a cantina só descobria no balcão.
        #
        # E não é caso raro — é o CAMINHO PADRÃO de um erro fácil: a regra da
        # casa é "véspera às 20h", então um cardápio criado para HOJE nasce com
        # prazo de ontem. Publicar sem reclamar transformava a regra numa
        # armadilha.
        #
        # ⚠️ Mas a recusa só vale quando o pedido é o ÚNICO jeito de comer. Com
        # a retirada presencial ligada, prazo vencido não deixa o cardápio
        # invisível: fecha a encomenda e mantém o balcão — que é exatamente o
        # dia em que a feature serve. Recusar aqui bloquearia "o pedido de hoje
        # já fechou, mas eu ainda quero abrir a retirada". O editor usa a mesma
        # régua (`invisivel` em CardapioDoDia.tsx): as duas barreiras do
        # docs/38 §3.3.1 continuam de pé, e agora concordam uma com a outra.
        if aceita_pedido and not aceita_presencial and prazo is not None and _agora() >= prazo:
            raise HTTPException(
                status_code=422,
                detail=(
                    "O prazo deste cardápio já passou, então nenhum aluno "
                    "conseguiria pedir. Ajuste o prazo antes de publicar."
                ),
            )
        if not any(bloco["opcoes"] for bloco in montado["blocos"]):
            raise HTTPException(
                status_code=422,
                detail="O cardápio precisa de pelo menos uma opção para ser publicado.",
            )

    atualizado = (
        cliente.table("cardapio")
        .update({"publicado_em": _agora().isoformat()}, returning="representation")
        .eq("id", cardapio_id)
        .execute()
    ).data[0]

    auditar(
        cliente, "cardapio_publicado", canal="cantina", ator_tipo="cantina",
        ator_id=usuario.get("sub"), recurso=f"cardapio/{cardapio_id}", ip=_ip(request),
        detalhe={"data": cardapio["data"], "refeicao": cardapio["refeicao"]},
    )
    # O evento mais importante do barramento: é o instante em que o cardápio
    # passa a existir para o aluno, e a tela dele muda sozinha por causa disto.
    publicar_cardapio_mudou(atualizado)
    return _montar_cardapio(cliente, atualizado, _agora())


@router.post("/cardapios/{cardapio_id}/copiar-de")
async def copiar_cardapio(
    cardapio_id: str,
    body: CopiarBody,
    request: Request,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """Traz blocos e opções de outro dia.

    ⚠️ **Não copia `pedidos_ate`.** O prazo é absoluto: copiar a segunda para a
    terça carregando o timestamp da segunda entregaria um cardápio publicado
    com prazo já vencido — ninguém pede, e a cantina só descobre no balcão. O
    prazo é RECALCULADO pela regra da casa para a data nova (docs/38 §2.2).

    Só copia para rascunho, e só para rascunho vazio: sobrescrever um cardápio
    que já tem pedido é a mesma classe de problema do §2.5, sem o ganho.
    """
    cliente = get_supabase()
    destino = _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    origem = _cardapio_da_cantina(cliente, body.origem_id, usuario["cantina_id"])

    ja_tem = (
        cliente.table("cardapio_bloco").select("id").eq("cardapio_id", cardapio_id).execute().data
    )
    if ja_tem:
        raise HTTPException(
            status_code=409,
            detail="Este cardápio já tem conteúdo. Copiar só para um dia ainda vazio.",
        )

    montada = _montar_cardapio(cliente, origem, _agora())
    for bloco in montada["blocos"]:
        novo = (
            cliente.table("cardapio_bloco")
            .insert(
                {
                    "cardapio_id": cardapio_id,
                    "nome": bloco["nome"],
                    "ordem": bloco["ordem"],
                    "escolhas_minimas": bloco["escolhas_minimas"],
                    "escolhas_maximas": bloco["escolhas_maximas"],
                },
                returning="representation",
            )
            .execute()
        ).data[0]
        for opcao in bloco["opcoes"]:
            cliente.table("cardapio_opcao").insert(
                {
                    "bloco_id": novo["id"],
                    "nome": opcao["nome"],
                    # `disponivel` volta a true: "acabou o frango" era verdade
                    # naquele dia, não uma propriedade do prato.
                    "disponivel": True,
                    "ordem": opcao["ordem"],
                }
            ).execute()

    cantina = _cantina_por_id(cliente, usuario["cantina_id"])
    dia = date.fromisoformat(str(destino["data"]))
    atualizado = (
        cliente.table("cardapio")
        .update(
            {
                "pedidos_ate": _prazo_pela_regra(cantina, dia).isoformat(),
                "atualizado_em": _agora().isoformat(),
            },
            returning="representation",
        )
        .eq("id", cardapio_id)
        .execute()
    ).data[0]

    auditar(
        cliente, "cardapio_copiado", canal="cantina", ator_tipo="cantina",
        ator_id=usuario.get("sub"), recurso=f"cardapio/{cardapio_id}", ip=_ip(request),
        detalhe={"origem": body.origem_id},
    )
    publicar_cardapio_mudou(atualizado)
    return _montar_cardapio(cliente, atualizado, _agora())


# ─── A cantina: o que cozinhar, e o que servir ────────────────────────────


def _contagem(cliente: ClienteDados, cardapio_id: str) -> list[dict]:
    linhas = (
        cliente.table("v_contagem_pedidos_por_opcao")
        .select("*")
        .eq("cardapio_id", cardapio_id)
        .execute()
        .data
        or []
    )
    linhas.sort(key=lambda linha: (linha["bloco_ordem"], linha["opcao_ordem"]))
    return linhas


def _contagem_presencial(cliente: ClienteDados, cardapio_id: str) -> dict:
    """Quantos declararam presença, e quantos já passaram pelo balcão.

    Linha à parte na tela, e não misturada na contagem por opção, porque
    presencial NÃO escolhe prato (docs/40 §10.1): somá-lo às opções inventaria
    pedidos de comida que ninguém pediu, e omiti-lo esconderia gente que vai
    comer.

    Conta em Python e não em view, ao contrário da contagem por opção: aqui são
    no máximo os alunos com direito àquela refeição (~900 no teto do colégio, em
    UMA coluna), e não `pedido_refeicao_item`, que é a tabela da armadilha 2. Se
    um dia isto pesar, vira view como a 0049 fez.
    """
    linhas = (
        cliente.table("pedido_refeicao")
        .select("retirado_em")
        .eq("cardapio_id", cardapio_id)
        .eq("modo", MODO_PRESENCIAL)
        .execute()
        .data
        or []
    )
    retirados = sum(1 for linha in linhas if linha.get("retirado_em"))
    return {"pendentes": len(linhas) - retirados, "retirados": retirados}


def _pedidos_do_cardapio(
    cliente: ClienteDados, cardapio_id: str, *, contagem: list[dict] | None = None
) -> list[dict]:
    """Linha por aluno: nome, turma, restrição e o que ele marcou.

    ⚠️ **É tudo que a cantina vê do aluno** (docs/38 §8.2.2). Nenhuma consulta
    daqui toca `nota`, `simulado` ou ficha: são dados de menores, e a lista de
    pedidos já é informação sensível por tabela interposta — a escolha
    vegetariana insinua religião ou saúde.
    """
    pedidos = (
        cliente.table("pedido_refeicao")
        .select(
            "id, aluno_id, criado_em, modo, retirado_em, "
            "aluno(nome, restricao_alimentar)"
        )
        .eq("cardapio_id", cardapio_id)
        .execute()
        .data
        or []
    )
    if not pedidos:
        return []

    itens = (
        cliente.table("pedido_refeicao_item")
        .select("pedido_id, opcao_id")
        .in_("pedido_id", [p["id"] for p in pedidos])
        .execute()
        .data
        or []
    )
    # A contagem entra por parâmetro quando quem chama já a tem: em
    # `cardapio_para_a_coordenacao` ela era calculada DUAS vezes na mesma
    # requisição — uma para a tela, outra aqui só para descobrir o nome das
    # opções (docs/40 §12.1.3).
    if contagem is None:
        contagem = _contagem(cliente, cardapio_id)
    nomes = {linha["opcao_id"]: linha["opcao"] for linha in contagem}
    escolhas: dict[str, list[str]] = {}
    for item in itens:
        escolhas.setdefault(item["pedido_id"], []).append(
            nomes.get(item["opcao_id"], "—")
        )

    # A turma sai de `matricula_turma` com `ativo_ate IS NULL`, que é como o
    # resto do backend define "a turma do aluno hoje" (stats/classificacao_ciclo).
    matriculas = (
        cliente.table("matricula_turma")
        .select("aluno_id, turma(section_original)")
        .in_("aluno_id", [p["aluno_id"] for p in pedidos])
        .is_("ativo_ate", "null")
        .execute()
        .data
        or []
    )
    turma_por_aluno = {
        m["aluno_id"]: (m.get("turma") or {}).get("section_original") for m in matriculas
    }

    saida = [
        {
            "alunoId": p["aluno_id"],
            "nome": (p.get("aluno") or {}).get("nome"),
            "turma": turma_por_aluno.get(p["aluno_id"]),
            "restricaoAlimentar": (p.get("aluno") or {}).get("restricao_alimentar"),
            "escolhas": sorted(escolhas.get(p["id"], [])),
            "pedidoEm": p.get("criado_em"),
            # O modo é rótulo de FLUXO, não dado sensível: quem só declarou
            # presença aparece sem escolhas, e sem esta marca a linha pareceria
            # um pedido em branco (docs/40 §8).
            "modo": p.get("modo") or MODO_PEDIDO,
            "retiradoEm": p.get("retirado_em"),
        }
        for p in pedidos
    ]
    saida.sort(key=lambda linha: (linha["nome"] or "").casefold())
    return saida


@router.get("/eu")
async def cantina_da_sessao(usuario: dict = Depends(get_current_cantina)) -> dict:
    """O estabelecimento desta sessão: nome, regras da casa e preço de tabela.

    O nome já vem no token, mas o resto não — e o preço e os modos mudam na tela
    da coordenação, sem a cantina relogar. Ler do banco (`select("*")`, então as
    colunas novas da 0051 vêm de graça) é o que faz a soma do dia e a regra de
    modos acompanharem uma alteração sem exigir logout.
    """
    return _cantina_por_id(get_supabase(), usuario["cantina_id"])


@router.get("/publico")
async def publico_da_cantina(usuario: dict = Depends(get_current_cantina)) -> dict:
    """Quantos alunos podem pedir cada refeição.

    Existe por causa de um incidente: "publiquei e ninguém vê" tinha quatro
    causas e nenhuma se anunciava. Duas viraram impossíveis (cardápio no
    passado, prazo vencido); esta é a terceira — o cardápio está perfeito e
    simplesmente **não tem público**, porque a coordenação ainda não concedeu o
    direito àquela refeição.

    ⚠️ Isto é AVISO, nunca recusa. Publicar antes de a coordenação conceder é
    ordem de trabalho legítima — a cantina monta a semana, a coordenação libera
    os alunos. Transformar em bloqueio inverteria a dependência entre duas
    equipes que não se falam no mesmo minuto.

    Conta em Python e não em view: a tabela é limitada por aluno (no máximo dois
    por pessoa, ~1.800 linhas no teto do colégio), então não é a `pedido_refeicao_item`
    da armadilha 2 — ali sim a agregação teve de descer para o banco.
    """
    cliente = get_supabase()
    linhas = (
        cliente.table("direito_refeicao_aluno").select("aluno_id, refeicao").execute().data or []
    )
    por_refeicao = {refeicao: 0 for refeicao in REFEICOES}
    for linha in linhas:
        if linha["refeicao"] in por_refeicao:
            por_refeicao[linha["refeicao"]] += 1
    return por_refeicao


@router.get("/cardapios/{cardapio_id}/contagem")
async def contagem_do_cardapio(
    cardapio_id: str,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """O que cozinhar: uma linha por opção, mais o placar do presencial.

    ⚠️ **Devolvia uma lista e agora devolve um objeto** (`opcoes` + `presencial`,
    docs/40 §7). O presencial não cabia como mais uma linha da lista: ele não
    tem opção nem bloco, e entrar ali obrigaria a tela a tratar uma linha
    impossível no meio da contagem por prato.
    """
    cliente = get_supabase()
    _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    return {
        "opcoes": _contagem(cliente, cardapio_id),
        "presencial": _contagem_presencial(cliente, cardapio_id),
    }


@router.get("/cardapios/{cardapio_id}/pedidos")
async def pedidos_do_cardapio(
    cardapio_id: str,
    usuario: dict = Depends(get_current_cantina),
) -> list[dict]:
    """O que servir: uma linha por aluno, para o balcão."""
    cliente = get_supabase()
    _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    return _pedidos_do_cardapio(cliente, cardapio_id)


# ─── A cantina: a leitura do QR ───────────────────────────────────────────


def _ficha_do_aluno(cliente: ClienteDados, aluno_id: str) -> dict:
    """Nome, turma e restrição alimentar — e nada além disso.

    É a MESMA régua de dado da lista de pedidos (docs/38 §8.1.2): a cantina
    precisa saber quem está na frente dela e se há restrição a respeitar, e o
    resto da vida escolar do aluno não é assunto do balcão.
    """
    alunos = (
        cliente.table("aluno")
        .select("nome, restricao_alimentar")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
        .data
        or [{}]
    )
    matriculas = (
        cliente.table("matricula_turma")
        .select("turma(section_original)")
        .eq("aluno_id", aluno_id)
        .is_("ativo_ate", "null")
        .limit(1)
        .execute()
        .data
        or []
    )
    turma = (matriculas[0].get("turma") or {}).get("section_original") if matriculas else None
    return {
        "alunoId": aluno_id,
        "nome": alunos[0].get("nome"),
        "turma": turma,
        "restricaoAlimentar": alunos[0].get("restricao_alimentar"),
    }


def _ler_o_que_veio_do_qr(conteudo: str) -> dict[str, str]:
    """Aceita os DOIS formatos de QR, e a ordem do `if` é a decisão.

    O formato rotativo (`pedido.janela.codigo`, docs/40 §12.9.2) é o novo; o
    JWT de 120 s é o que as telas já abertas ainda estão mostrando.

    ⚠️ **Os dois convivem por uma janela de transição, não para sempre.** Um
    aluno com a tela aberta desde antes do deploy continua com o QR antigo, e
    recusá-lo seria trocar um problema de segurança por uma fila parada. Quando
    o produto estiver há mais de dois minutos no ar, o ramo do JWT deixa de ser
    alcançado por qualquer cliente atual — e aí ele sai daqui.
    """
    if conteudo.count(".") == 2 and " " not in conteudo.strip():
        # Um JWT também tem dois pontos. O que os separa é o formato do meio:
        # aqui a janela é um inteiro, e no JWT é base64 de um JSON.
        partes = conteudo.strip().split(".")
        if partes[1].isdigit():
            pedido_id = ler_qr_rotativo(conteudo)
            return _pedido_para_confirmar(pedido_id)
    return ler_retirada(conteudo)


def _pedido_para_confirmar(pedido_id: str) -> dict[str, str]:
    """Os campos que o resto da rota espera, buscados pelo id do pedido.

    O QR rotativo carrega só o `pedido_id` — cardápio e aluno vêm do banco.
    ⚠️ Uma consulta a mais no caminho mais apressado do produto, e ela é o preço
    de o QR não carregar mais do que precisa: quanto menos viaja no código,
    menos um print entrega.
    """
    linha = (
        get_supabase()
        .table("pedido_refeicao")
        .select("id, cardapio_id, aluno_id")
        .eq("id", pedido_id)
        .limit(1)
        .execute()
        .data
    )
    if not linha:
        raise RetiradaIlegivel("pedido inexistente")
    return {
        "pedido_id": str(linha[0]["id"]),
        "cardapio_id": str(linha[0]["cardapio_id"]),
        "aluno_id": str(linha[0]["aluno_id"]),
    }


def _porque_a_leitura_nao_pegou(cliente: ClienteDados, pedido_id: str) -> str:
    """A frase do 409, depois de o UPDATE condicional não ter achado a linha.

    Esta leitura acontece DEPOIS da tentativa de escrita, e só para explicar —
    nunca antes, para decidir. Ler antes de escrever é justamente a corrida que
    o §4 evita: duas câmeras lendo o mesmo QR no mesmo segundo veriam as duas
    `retirado_em IS NULL` e as duas serviriam.
    """
    linha = (
        cliente.table("pedido_refeicao")
        .select("modo, retirado_em")
        .eq("id", pedido_id)
        .limit(1)
        .execute()
        .data
    )
    if not linha:
        return "Não encontrei este pedido. Peça para o aluno atualizar a tela."
    if linha[0].get("retirado_em"):
        quando = _instante(linha[0].get("retirado_em"))
        if quando:
            hora = quando.astimezone(FUSO_DA_ESCOLA).strftime("%H:%M")
            return f"Esta refeição já foi retirada às {hora}."
        return "Esta refeição já foi retirada."
    if linha[0].get("modo") == MODO_PEDIDO:
        # De graça, pela mesma condição: o aluno desistiu do presencial e fez o
        # pedido no meio do caminho, então `modo = "presencial"` também não bate.
        return "Este aluno trocou a retirada presencial por um pedido. Confira na lista do dia."
    return "Não consegui confirmar esta retirada. Peça para o aluno atualizar a tela."


@router.post("/retiradas/confirmar")
async def confirmar_retirada(
    body: ConfirmarRetiradaBody,
    request: Request,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """A leitura do QR no balcão (docs/40 §4).

    ⚠️ **O UPDATE é CONDICIONAL, e é ele que impede a segunda leitura.** Não há
    "buscar o pedido, ver se já foi retirado, então gravar": entre a leitura e a
    escrita cabe outra câmera do mesmo balcão, e as duas serviriam o mesmo aluno.
    O `WHERE` é a trava — zero linhas afetadas quer dizer "alguém chegou antes",
    e cobre de graça o caso de o aluno ter virado `pedido` nesse meio-tempo.
    """
    try:
        codigo = _ler_o_que_veio_do_qr(body.token)
    except RetiradaIlegivel:
        # `from None`: qual das portas fechou é informação para quem tenta
        # forjar, não para quem está na fila (ver `cantina_token`).
        raise HTTPException(
            status_code=422,
            detail="Código inválido ou vencido. Peça para o aluno atualizar a tela.",
        ) from None

    cliente = get_supabase()
    cardapio = (
        cliente.table("cardapio")
        .select("*")
        .eq("id", codigo["cardapio_id"])
        .limit(1)
        .execute()
        .data
    )
    if not cardapio:
        raise HTTPException(status_code=404, detail="cardápio não encontrado")
    # O mesmo cross-check de toda rota da cantina: o recorte vem do TOKEN DE
    # SESSÃO, e o QR só diz de que cardápio ele é. 403 e não 404 porque aqui o
    # recurso existe e o operador precisa entender o que aconteceu — o código é
    # de outra casa, não é um código quebrado.
    if str(cardapio[0].get("cantina_id")) != str(usuario["cantina_id"]):
        raise HTTPException(
            status_code=403, detail="Este código é de um cardápio de outra cantina."
        )

    atualizados = (
        cliente.table("pedido_refeicao")
        .update({"retirado_em": _agora().isoformat()}, returning="representation")
        .eq("id", codigo["pedido_id"])
        # Os dois `eq` seguintes não são redundantes com o `id`: eles amarram a
        # linha ao que o token diz, e é o que faz a conferência de cantina lá de
        # cima valer para a linha que está sendo escrita.
        .eq("cardapio_id", codigo["cardapio_id"])
        .eq("aluno_id", codigo["aluno_id"])
        .eq("modo", MODO_PRESENCIAL)
        .is_("retirado_em", "null")
        .execute()
    ).data or []
    if not atualizados:
        raise HTTPException(
            status_code=409,
            detail=_porque_a_leitura_nao_pegou(cliente, codigo["pedido_id"]),
        )

    auditar(
        cliente, "retirada_confirmada", canal="cantina", ator_tipo="cantina",
        ator_id=usuario.get("sub"), recurso=f"pedido_refeicao/{codigo['pedido_id']}",
        ip=_ip(request),
        # ⚠️ O token NUNCA entra na trilha — ele é credencial, e a regra da casa
        # é que auditoria responde "quem" e "quando", não reproduz o segredo.
        detalhe={
            "aluno_id": codigo["aluno_id"],
            "cardapio_id": codigo["cardapio_id"],
            "refeicao": cardapio[0].get("refeicao"),
        },
    )
    _avisar_retirada(cardapio[0], codigo["aluno_id"])

    return {
        **_ficha_do_aluno(cliente, codigo["aluno_id"]),
        "refeicao": cardapio[0].get("refeicao"),
        "data": str(cardapio[0].get("data")) if cardapio[0].get("data") else None,
        "retiradoEm": atualizados[0].get("retirado_em"),
    }


# ─── O aluno ──────────────────────────────────────────────────────────────


def _direitos_do_aluno(cliente: ClienteDados, aluno_id: str) -> list[str]:
    linhas = (
        cliente.table("direito_refeicao_aluno")
        .select("refeicao")
        .eq("aluno_id", aluno_id)
        .execute()
        .data
        or []
    )
    return sorted({linha["refeicao"] for linha in linhas})


@router_aluno.get("")
async def cantina_do_aluno(aluno: dict = Depends(get_current_aluno)) -> dict:
    """Meus direitos, os cardápios publicados que me servem, e o que já pedi.

    **Todos os dias já publicados**, e não só o próximo (docs/38 §8.0.6): se a
    cantina lança a semana na sexta, o aluno resolve a semana na sexta. Cada dia
    tem o SEU prazo, e é o prazo que governa — não a posição na lista.

    Sem direito nenhum, a resposta é vazia e o card nem monta. Não é 403: "esta
    tela não é para você" é estado normal para 800 dos 900 alunos, e um erro
    aqui viraria ruído no console de quem não fez nada de errado.
    """
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    direitos = _direitos_do_aluno(cliente, aluno_id)
    if not direitos:
        return {"direitos": [], "dias": []}

    agora = _agora()
    hoje = agora.astimezone(FUSO_DA_ESCOLA).date()
    limite = hoje + timedelta(days=DIAS_VISIVEIS_PARA_O_ALUNO)

    cardapios = (
        cliente.table("cardapio")
        .select("*")
        .in_("refeicao", direitos)
        .gte("data", hoje.isoformat())
        .lte("data", limite.isoformat())
        .not_.is_("publicado_em", "null")
        .eq("sem_refeicao", False)
        .execute()
        .data
        or []
    )
    if not cardapios:
        return {"direitos": direitos, "dias": []}

    ids = [c["id"] for c in cardapios]
    # ⚠️ O NOME da cantina viaja com cada dia desde que pode haver duas
    # (docs/40 §12.12.3). Sem ele, dois almoços da mesma terça chegam à tela do
    # aluno indistinguíveis — e escolher entre dois cartões idênticos é escolher
    # no escuro. Uma consulta para todas, não uma por cardápio.
    cantina_ids = sorted({c["cantina_id"] for c in cardapios})
    nomes_de_cantina = {
        linha["id"]: linha["nome"]
        for linha in (
            cliente.table("cantina")
            .select("id, nome")
            .in_("id", cantina_ids)
            .execute()
            .data
            or []
        )
    }
    meus = (
        cliente.table("pedido_refeicao")
        .select("id, cardapio_id, modo, retirado_em, pedido_refeicao_item(opcao_id)")
        .eq("aluno_id", aluno_id)
        .in_("cardapio_id", ids)
        .execute()
        .data
        or []
    )
    linha_por_cardapio = {p["cardapio_id"]: p for p in meus}
    # ⚠️ FORA do laço, e é o ponto. Aqui dentro, `_montar_cardapio` fazia uma
    # ida ao PostgREST por cardápio: a semana inteira lançada eram ~10 idas em
    # série, num loop que já está bloqueado pelo cliente síncrono
    # (docs/40 §12.1.3).
    blocos_por_cardapio = _blocos_por_cardapio(cliente, ids)

    dias = []
    for c in cardapios:
        minha = linha_por_cardapio.get(c["id"])
        modo = (minha or {}).get("modo") or (MODO_PEDIDO if minha else None)
        dias.append(
            {
                **_montar_cardapio(
                    cliente, c, agora, blocos=blocos_por_cardapio.get(c["id"], [])
                ),
                # ⚠️ `meuPedido` continua sendo O PEDIDO, e por isso é nulo no
                # modo presencial: uma linha presencial não tem prato, e
                # devolvê-la como lista vazia faria a tela mostrar "você pediu
                # nada" onde a verdade é "você vai buscar no balcão". Quem conta
                # a história do presencial são `modo` e `retiradoEm`.
                "meuPedido": (
                    sorted(i["opcao_id"] for i in (minha.get("pedido_refeicao_item") or []))
                    if minha and modo == MODO_PEDIDO
                    else None
                ),
                "modo": modo,
                "retiradoEm": (minha or {}).get("retirado_em"),
                "cantina": nomes_de_cantina.get(c["cantina_id"]),
            }
        )
    dias.sort(key=lambda d: (d["data"], d["refeicao"]))
    return {"direitos": direitos, "dias": dias}


def _avisar_pedido(cardapio: dict, aluno_id: str) -> None:
    """Avisa a cantina e a coordenação de que a contagem daquele dia mudou.

    O `aluno_id` viaja para o stream do próprio aluno reconhecer o evento como
    dele — é o que mantém duas abas do mesmo aluno em dia. Os streams da cantina
    e da coordenação não olham esse campo.
    """
    barramento.publicar(
        Evento(
            tipo="pedido",
            cantina_id=str(cardapio.get("cantina_id") or "") or None,
            refeicao=cardapio.get("refeicao"),
            data=str(cardapio.get("data")) if cardapio.get("data") else None,
            aluno_id=aluno_id,
        )
    )


def _avisar_retirada(cardapio: dict, aluno_id: str) -> None:
    """O aviso de que aquele aluno passou pelo balcão (docs/40 §5).

    Tipo próprio, e não mais um `pedido`: quem recebe precisa distinguir "a
    contagem mudou" de "alguém acabou de retirar" — a tela do aluno vira "Bom
    almoço" e a da cantina soma uma retirada. Os dois recortes que já existem
    cobrem o caso sem alteração: `para_o_aluno` casa por `aluno_id`, e
    `para_a_cantina` por `cantina_id`.

    Como todo evento daqui, ele não carrega o texto pronto — carrega o aviso de
    refazer `GET /me/cantina`, e quem decide o que mostrar é a rota normal.
    """
    barramento.publicar(
        Evento(
            tipo="retirada",
            cantina_id=str(cardapio.get("cantina_id") or "") or None,
            refeicao=cardapio.get("refeicao"),
            data=str(cardapio.get("data")) if cardapio.get("data") else None,
            aluno_id=aluno_id,
        )
    )


def _validar_escolhas(montado: dict, opcao_ids: list[str]) -> None:
    """As escolhas cabem no que o cardápio permite?

    É Python e não CHECK porque o backend nunca escreve SQL (CLAUDE.md) — e é
    justamente por isso que precisa de teste. As três recusas dizem QUAL bloco
    está errado: "escolha inválida" obrigaria o aluno a adivinhar em qual das
    quatro listas ele errou.
    """
    escolhidas = set(opcao_ids)
    if len(escolhidas) != len(opcao_ids):
        raise HTTPException(status_code=422, detail="A mesma opção foi escolhida duas vezes.")

    validas = {
        opcao["id"]
        for bloco in montado["blocos"]
        for opcao in bloco["opcoes"]
        if opcao["disponivel"]
    }
    fora = escolhidas - validas
    if fora:
        raise HTTPException(
            status_code=422,
            detail="Alguma opção escolhida não está mais disponível. Recarregue o cardápio.",
        )

    for bloco in montado["blocos"]:
        do_bloco = escolhidas & {o["id"] for o in bloco["opcoes"]}
        if len(do_bloco) < bloco["escolhas_minimas"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Escolha ao menos {bloco['escolhas_minimas']} em {bloco['nome']}."
                ),
            )
        if len(do_bloco) > bloco["escolhas_maximas"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Em {bloco['nome']} dá para escolher no máximo "
                    f"{bloco['escolhas_maximas']}."
                ),
            )


def _cardapio_aberto_para(cliente: ClienteDados, cardapio_id: str, aluno_id: str) -> dict:
    """O cardápio, se este aluno pode mexer nele AGORA.

    ⚠️ **As três recusas são do servidor, e não da tela** (docs/38 §3.2). A tela
    pode estar aberta desde antes do prazo, e um botão desabilitado no cliente
    não é uma regra — sobretudo aqui, onde a regra tem consequência: quem não
    pediu não come, e nada entra depois do prazo, nem pela cantina.
    """
    linha = (
        cliente.table("cardapio").select("*").eq("id", cardapio_id).limit(1).execute().data
    )
    if not linha or not linha[0].get("publicado_em") or linha[0].get("sem_refeicao"):
        raise HTTPException(status_code=404, detail="cardápio não encontrado")
    cardapio = linha[0]

    if cardapio["refeicao"] not in _direitos_do_aluno(cliente, aluno_id):
        raise HTTPException(
            status_code=403, detail="Você não tem direito a esta refeição."
        )

    # A quarta recusa, e ela é do servidor pelo mesmo motivo das outras três: o
    # cardápio pode aceitar SÓ retirada presencial, e nesse dia não existe
    # pedido para fazer (docs/40 §1). Sem isto, `aceita_pedido` seria um enfeite
    # de tela — e o front está sendo escrito em paralelo a este arquivo.
    if not _modos_do_cardapio(cardapio)[0]:
        raise HTTPException(
            status_code=422,
            detail="Neste dia a cantina só aceita retirada presencial, sem pedido antecipado.",
        )

    prazo = _instante(cardapio.get("pedidos_ate"))
    if prazo is None or _agora() >= prazo:
        raise HTTPException(
            status_code=409,
            detail="O prazo para pedir deste dia já passou.",
        )
    return cardapio


@router_aluno.put("/pedidos/{cardapio_id}")
async def salvar_pedido(
    cardapio_id: str,
    body: PedidoBody,
    aluno: dict = Depends(get_current_aluno),
) -> dict:
    """Grava ou substitui o pedido inteiro. Idempotente de propósito: o aluno
    pode trocar quantas vezes quiser até o prazo, e com um instante em que a
    contagem congela, mudar de ideia antes dele não custa nada a ninguém.

    É também a porta de ENTRADA sem volta da máquina de estados (docs/40 §2):
    uma linha presencial ainda não lida vira pedido aqui — modo e itens são
    sobrescritos —, e o caminho contrário não existe.
    """
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    cardapio = _cardapio_aberto_para(cliente, cardapio_id, aluno_id)
    montado = _montar_cardapio(cliente, cardapio, _agora())
    _validar_escolhas(montado, body.opcao_ids)

    existente = (
        cliente.table("pedido_refeicao")
        .select("id, modo, retirado_em")
        .eq("cardapio_id", cardapio_id)
        .eq("aluno_id", aluno_id)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        # ⚠️ `retirado_em` preenchido é FINAL dos dois lados (docs/40 §2): o
        # aluno já comeu, e deixar o pedido ser reescrito depois disso mudaria a
        # contagem de um prato que já saiu do balcão.
        if existente[0].get("retirado_em"):
            raise HTTPException(
                status_code=409,
                detail="Esta refeição já foi retirada — não dá mais para mudar o pedido.",
            )
        pedido_id = existente[0]["id"]
        cliente.table("pedido_refeicao").update(
            # `modo` entra no patch sempre, e não só quando a linha era
            # presencial: o `PUT` é a definição de "isto é um pedido", e um
            # UPDATE que só às vezes corrige o modo é um estado a mais para
            # alguém errar depois.
            {"atualizado_em": _agora().isoformat(), "modo": MODO_PEDIDO}
        ).eq("id", pedido_id).execute()
        # Substituir em vez de casar item a item: a lista tem quatro elementos,
        # e um diff aqui seria código para manter sem ganho nenhum.
        cliente.table("pedido_refeicao_item").delete().eq("pedido_id", pedido_id).execute()
    else:
        pedido_id = _inserir_pedido(
            cliente,
            cardapio=cardapio,
            aluno_id=aluno_id,
            modo=MODO_PEDIDO,
        )

    if body.opcao_ids:
        cliente.table("pedido_refeicao_item").insert(
            [{"pedido_id": pedido_id, "opcao_id": oid} for oid in body.opcao_ids]
        ).execute()

    _avisar_pedido(cardapio, aluno_id)
    return {"cardapioId": cardapio_id, "opcaoIds": sorted(body.opcao_ids)}


@router_aluno.delete("/pedidos/{cardapio_id}")
async def cancelar_pedido(
    cardapio_id: str,
    aluno: dict = Depends(get_current_aluno),
) -> dict:
    """Desisti. Passa pelas mesmas recusas do `PUT`: depois do prazo o
    pedido está contado, e a cantina já comprou."""
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    cardapio = _cardapio_aberto_para(cliente, cardapio_id, aluno_id)
    # O `is_` não é zelo: sem ele, um cancelamento apagaria a linha de uma
    # refeição JÁ RETIRADA, e a retirada não tem outra prova no produto
    # (docs/40 §2). O `.data` vazio com linha existente vira o 409 abaixo.
    apagados = (
        cliente.table("pedido_refeicao")
        .delete(returning="representation")
        .eq("cardapio_id", cardapio_id)
        .eq("aluno_id", aluno_id)
        .is_("retirado_em", "null")
        .execute()
    ).data or []
    if not apagados and _pedido_do_aluno(cliente, cardapio_id, aluno_id):
        raise HTTPException(
            status_code=409, detail="Esta refeição já foi retirada."
        )
    _avisar_pedido(cardapio, aluno_id)
    return {"cardapioId": cardapio_id, "opcaoIds": None}


# ─── O aluno: a retirada presencial ───────────────────────────────────────
#
# O segundo jeito de comer (docs/40): sem prazo, sem prato escolhido e sem
# antecedência — o aluno chega, mostra o QR, e a cantina lê. A máquina de
# estados por (cardápio, aluno) é ASSIMÉTRICA de propósito: `pedido` compromete
# a cozinha com um prato específico e por isso é final; `presencial` não
# compromete nada até o QR ser lido, e por isso é reversível (docs/40 §2).


#: O que o Postgres devolve quando o índice de um-por-dia recusa a linha.
_TRAVA_DO_DIA = "pedido_refeicao_um_por_dia"


def _inserir_pedido(
    cliente: ClienteDados, *, cardapio: dict, aluno_id: str, modo: str
) -> str:
    """A ÚNICA porta de entrada de uma linha em `pedido_refeicao`.

    Existe por dois motivos que só juntos justificam a função:

    1. **`data` e `refeicao` têm de ser copiados do cardápio** (migration 0055).
       São a cópia que sustenta o índice de um-por-dia, porque unicidade não
       atravessa tabela no Postgres. Dois lugares inserindo — o pedido e a
       retirada presencial — são dois lugares para alguém esquecer a cópia, e o
       esquecimento só apareceria como `NOT NULL violation` em produção;
    2. **a recusa do índice precisa virar frase.** O erro cru do Postgres diz
       "duplicate key value violates unique constraint", que é verdade e não
       ajuda ninguém na fila do balcão.

    ⚠️ A trava vale para os DOIS modos e para as DUAS cantinas: pedir na do Ari
    e declarar presença na Food no mesmo almoço é a mesma linha lógica, e é
    exatamente o que o índice existe para impedir (docs/40 §12.12.2).
    """
    try:
        return (
            cliente.table("pedido_refeicao")
            .insert(
                {
                    "cardapio_id": cardapio["id"],
                    "aluno_id": aluno_id,
                    "modo": modo,
                    # Cópia do cardápio, e não do relógio: o dia é o do
                    # cardápio, não o de quem está pedindo.
                    "data": cardapio["data"],
                    "refeicao": cardapio["refeicao"],
                    # O preço de HOJE, congelado no fato (migration 0054). Lido
                    # da cantina do cardápio, que com duas cantinas já não é "a"
                    # cantina.
                    "valor_cobrado": _valor_da_refeicao(cliente, cardapio),
                },
                returning="representation",
            )
            .execute()
        ).data[0]["id"]
    except Exception as erro:
        if _TRAVA_DO_DIA not in str(erro):
            raise
        raise HTTPException(
            status_code=409,
            detail=(
                "Você já tem uma refeição marcada para este dia. "
                "Cancele a outra antes de escolher esta."
            ),
        ) from erro


def _valor_da_refeicao(cliente: ClienteDados, cardapio: dict) -> float | None:
    """Quanto vale esta refeição NESTA cantina, agora.

    `None` quando ninguém cadastrou o preço — que é diferente de zero, e a
    coluna é anulável exatamente por isso (migration 0050).
    """
    cantina = _cantina_por_id(cliente, cardapio["cantina_id"])
    coluna = "valor_almoco" if cardapio["refeicao"] == "almoco" else "valor_janta"
    return cantina.get(coluna)


def _pedido_do_aluno(cliente: ClienteDados, cardapio_id: str, aluno_id: str) -> dict | None:
    """A linha daquele aluno naquele cardápio, se existir."""
    linhas = (
        cliente.table("pedido_refeicao")
        .select("id, modo, retirado_em")
        .eq("cardapio_id", cardapio_id)
        .eq("aluno_id", aluno_id)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0] if linhas else None


def _cardapio_para_retirada(cliente: ClienteDados, cardapio_id: str, aluno_id: str) -> dict:
    """O cardápio, se este aluno pode gerar o QR dele AGORA.

    As mesmas verificações de `_cardapio_aberto_para` — publicado, com refeição,
    e o aluno com direito —, **exceto a do prazo**: presencial não olha
    `pedidos_ate`, é justamente o caminho de quem não se planejou (docs/40 §3).
    E duas recusas próprias no lugar dela.
    """
    linha = (
        cliente.table("cardapio").select("*").eq("id", cardapio_id).limit(1).execute().data
    )
    if not linha or not linha[0].get("publicado_em") or linha[0].get("sem_refeicao"):
        raise HTTPException(status_code=404, detail="cardápio não encontrado")
    cardapio = linha[0]

    if cardapio["refeicao"] not in _direitos_do_aluno(cliente, aluno_id):
        raise HTTPException(status_code=403, detail="Você não tem direito a esta refeição.")

    if not _modos_do_cardapio(cardapio)[1]:
        raise HTTPException(
            status_code=422,
            detail="Neste dia a cantina não aceita retirada presencial — é preciso pedir antes.",
        )

    # ⚠️ Só o cardápio de HOJE (docs/40 §11.1). O QR é para ser lido na hora:
    # gerar um para daqui a três dias não avisa a cozinha de nada real — o aluno
    # pode simplesmente não vir — e enche a lista de pendentes do balcão de
    # gente que não está ali. `[:10]` porque a coluna é `date` e o PostgREST a
    # devolve como texto.
    hoje = _agora().astimezone(FUSO_DA_ESCOLA).date()
    if str(cardapio.get("data"))[:10] != hoje.isoformat():
        raise HTTPException(
            status_code=422,
            detail="A retirada presencial vale só para a refeição de hoje.",
        )
    return cardapio


@router_aluno.post("/retiradas/{cardapio_id}")
async def gerar_retirada(
    cardapio_id: str,
    aluno: dict = Depends(get_current_aluno),
) -> dict:
    """Declara presença e devolve o código do QR (docs/40 §4).

    Chamada de novo sobre a mesma linha, só emite um código novo — é assim que
    a tela do aluno renova o QR antes de ele vencer, sem criar nada e sem mexer
    na contagem da cantina.
    """
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    cardapio = _cardapio_para_retirada(cliente, cardapio_id, aluno_id)

    existente = _pedido_do_aluno(cliente, cardapio_id, aluno_id)
    if existente:
        # ⚠️ `pedido` é porta sem volta. Quem já pediu comprometeu a cozinha com
        # um prato, e virar presencial deixaria esse prato feito para ninguém.
        if (existente.get("modo") or MODO_PEDIDO) == MODO_PEDIDO:
            raise HTTPException(
                status_code=409,
                detail="Você já fez o pedido — não dá para trocar para retirada presencial.",
            )
        if existente.get("retirado_em"):
            raise HTTPException(status_code=409, detail="Esta refeição já foi retirada.")
        pedido_id = existente["id"]
    else:
        pedido_id = _inserir_pedido(
            cliente,
            cardapio=cardapio,
            aluno_id=aluno_id,
            modo=MODO_PRESENCIAL,
        )
        # O aviso só sai quando a linha NASCE. A renovação do QR acontece a cada
        # dois minutos enquanto a tela estiver aberta, e publicar nela encheria
        # o barramento de eventos que não mudam contagem nenhuma.
        _avisar_pedido(cardapio, aluno_id)

    # Sem auditoria aqui, e é decisão: gerar o QR se repete a cada dois minutos e
    # não concede nada — o ato auditável é a CONFIRMAÇÃO no balcão, que é onde a
    # refeição sai.
    token, expira_em = assinar_retirada(
        pedido_id=str(pedido_id), cardapio_id=cardapio_id, aluno_id=aluno_id
    )
    # ⚠️ A SEMENTE viaja na resposta e **nunca no QR** (docs/40 §12.9.2). É ela
    # que o aparelho usa para derivar um código novo a cada 10 s sem pedir nada
    # à rede — e é por ela não estar no QR que a rotação vale alguma coisa: um
    # print carrega o código de UMA janela, que morre em dez segundos.
    #
    # `janela` é o número da janela AGORA, no relógio do servidor. O cliente
    # conta o tempo decorrido a partir dela, e não a hora do mundo: assim um
    # celular com o relógio adiantado continua gerando o código certo.
    return {
        "token": token,
        "expiraEm": expira_em.isoformat(),
        "semente": semente_da_retirada(str(pedido_id)),
        "pedidoId": str(pedido_id),
        "janela": janela_de(),
        "segundosDaJanela": SEGUNDOS_DA_JANELA,
    }


@router_aluno.delete("/retiradas/{cardapio_id}")
async def desistir_da_retirada(
    cardapio_id: str,
    aluno: dict = Depends(get_current_aluno),
) -> dict:
    """Desisti de buscar. Apaga a linha presencial enquanto ela não foi lida.

    ⚠️ **NÃO passa por `_cardapio_para_retirada`.** Desistir tem de continuar
    funcionando depois de a cantina desligar o presencial daquele dia — recusar
    aqui deixaria o aluno preso a uma pendência que ele não pediu para manter.
    """
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    linha = (
        cliente.table("cardapio").select("*").eq("id", cardapio_id).limit(1).execute().data
    )
    if not linha:
        raise HTTPException(status_code=404, detail="cardápio não encontrado")

    apagados = (
        cliente.table("pedido_refeicao")
        .delete(returning="representation")
        .eq("cardapio_id", cardapio_id)
        .eq("aluno_id", aluno_id)
        .eq("modo", MODO_PRESENCIAL)
        .is_("retirado_em", "null")
        .execute()
    ).data or []

    if not apagados:
        # Nada apagado tem três causas, e duas delas precisam de resposta
        # diferente: a terceira — não havia linha nenhuma — é no-op idempotente,
        # porque desistir do que não existe é o estado que o aluno queria.
        atual = _pedido_do_aluno(cliente, cardapio_id, aluno_id)
        if atual and atual.get("retirado_em"):
            raise HTTPException(status_code=409, detail="Esta refeição já foi retirada.")
        if atual:
            raise HTTPException(
                status_code=409,
                detail="Você fez um pedido para este dia. Cancele pelo próprio pedido.",
            )
        return {"ok": True}

    _avisar_pedido(linha[0], aluno_id)
    return {"ok": True}


# ─── A coordenação: leitura ───────────────────────────────────────────────
#
# Vive sob `/administracao` e não sob `/cantina` porque o guard é o divisor:
# `/cantina/*` é da cantina, inteiro, e uma rota de coordenação no meio dele
# seria a exceção que alguém replica sem perceber. Aqui o piso do router já é
# `get_current_coordenador`, e o que exige administrador diz isso na rota.


def _cantina_padrao(cliente: ClienteDados, cantina_id: str | None) -> dict:
    """A cantina que a coordenação está olhando.

    Sem parâmetro, a primeira ativa — que hoje é a única. O parâmetro existe
    para o dia em que houver duas, e para a tela não precisar mudar quando
    houver (docs/38 §8.2.1).
    """
    if cantina_id:
        return _cantina_por_id(cliente, cantina_id)
    linhas = (
        cliente.table("cantina").select("*").eq("ativo", True).limit(1).execute().data
    )
    if not linhas:
        raise HTTPException(status_code=404, detail="Nenhuma cantina cadastrada.")
    return linhas[0]


@router_admin.get("/cantina/calendario")
async def calendario_da_coordenacao(
    de: date, ate: date, cantina: str | None = None, todas: bool = False
) -> list[dict]:
    """O mês da coordenação — de UMA cantina, ou de todas somadas.

    `todas=true` existe para o card do hub, que é visão de topo e não pode
    dizer "5 dias publicados" quando a segunda cantina publicou outros três
    (docs/40 §12.6). As telas de calendário continuam pedindo UMA: um mês com
    dois cardápios de almoço na mesma terça, misturados, não é calendário —
    é lista.

    ⚠️ `cantina` vence `todas` quando os dois vêm. Um recorte explícito na URL
    é escolha de quem está olhando, e uma flag não pode desfazê-la em silêncio.
    """
    cliente = get_supabase()
    if cantina:
        return _calendario(cliente, _cantina_por_id(cliente, cantina)["id"], de, ate)
    if not todas:
        return _calendario(cliente, _cantina_padrao(cliente, None)["id"], de, ate)

    ativas = cliente.table("cantina").select("id").eq("ativo", True).execute().data or []
    return _calendario(cliente, [linha["id"] for linha in ativas], de, ate)


@router_admin.get("/cantina/cardapios/{cardapio_id}")
async def cardapio_para_a_coordenacao(cardapio_id: str) -> dict:
    """O cardápio como a cantina o vê, sem poder mexer.

    Não filtra por cantina: a coordenação enxerga todas por desenho, e o id do
    cardápio já é específico o bastante.

    ⚠️ `presencial` vem pelas MESMAS duas funções da rota da cantina
    (`/cantina/cardapios/{id}/contagem`), e é por isso que ele existe aqui: sem
    o bloco, a coordenação tinha só a contagem por opção — que ignora o
    presencial de propósito (docs/40 §10.1) — e dizia "nenhum pedido ainda" ao
    lado de uma lista com doze nomes. Uma segunda contagem escrita aqui
    resolveria a tela e criaria o problema seguinte: dois números do mesmo dia,
    livres para divergir.
    """
    cliente = get_supabase()
    linha = cliente.table("cardapio").select("*").eq("id", cardapio_id).limit(1).execute().data
    if not linha:
        raise HTTPException(status_code=404, detail="cardápio não encontrado")
    montado = _montar_cardapio(cliente, linha[0], _agora())
    contagem = _contagem(cliente, cardapio_id)
    montado["contagem"] = contagem
    montado["presencial"] = _contagem_presencial(cliente, cardapio_id)
    montado["pedidos"] = _pedidos_do_cardapio(cliente, cardapio_id, contagem=contagem)
    return montado


# ─── A coordenação: quem tem direito ──────────────────────────────────────


class DireitoBody(BaseModel):
    """Um alvo ou oitenta, pela mesma rota.

    A concessão em lote existe POR CAUSA da decisão de que só o administrador
    concede (docs/38 §3.4): com uma única pessoa autorizada, ligar o direito de
    80 alunos um a um é a tarefa que não acontece — e o que não acontece na
    véspera do primeiro dia letivo derruba a feature inteira.
    """

    aluno_ids: list[str] = Field(min_length=1)
    refeicao: str
    conceder: bool


class RestricaoBody(BaseModel):
    #: `None` ou vazio apaga o campo. Não existe "sem informação" separado de
    #: "não tem restrição": os dois são a mesma coisa para quem serve o prato.
    restricao: str | None = None


@router_admin.get("/cantina/custos")
async def custos_da_cantina(de: date, ate: date, cantina: str | None = None) -> dict:
    """Os números do relatório, para a TELA (docs/40 §12.11.4).

    Mesmo agregador do XLSX: dois caminhos para a mesma soma divergem no
    primeiro caso de borda, e a divergência aparece como "a planilha não bate
    com a tela".
    """
    if ate < de:
        raise HTTPException(status_code=422, detail="O fim do período vem antes do começo.")
    return await asyncio.to_thread(
        cantina_relatorio.agregados, get_supabase(), de=de, ate=ate, cantina_id=cantina
    )


@router_admin.get("/cantina/relatorio.xlsx")
async def relatorio_de_custos(
    de: date, ate: date, cantina: str | None = None
) -> Response:
    """O relatório de custos, em XLSX com gráfico (docs/40 §12.11.3).

    ⚠️ **A primeira rota de exportação da API**, e a exceção tem motivo: gráfico
    em XLSX não se faz no navegador. O CSV e o PDF continuam do lado do cliente.

    ⚠️ **`to_thread` desde a primeira linha.** Montar a planilha é trabalho de
    CPU, síncrono, e o processo tem um event loop só: sem isto, um mês inteiro
    congelaria a API para todo mundo — o mesmo defeito que a §12.1.1 acabou de
    consertar no chat, voltando pela porta que esta rota abriu.

    Leitura de qualquer coordenador: ver quanto custou não é o mesmo que
    decidir quanto custa, e cadastrar o valor continua sendo do administrador
    (docs/40 §12.11.4).
    """
    if ate < de:
        raise HTTPException(status_code=422, detail="O fim do período vem antes do começo.")

    conteudo = await asyncio.to_thread(
        cantina_relatorio.montar, get_supabase(), de=de, ate=ate, cantina_id=cantina
    )
    nome = f"cantina-{de.isoformat()}-a-{ate.isoformat()}.xlsx"
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # `filename*` além de `filename`: o nome não tem acento hoje, e a forma
        # RFC 5987 é o que impede o dia em que tiver de virar mojibake no
        # Windows.
        headers={"Content-Disposition": f'attachment; filename="{nome}"; filename*=UTF-8\'\'{nome}'},
    )


@router_admin.get("/cantina/resumo")
async def resumo_da_cantina() -> dict:
    """Os três números do card do hub, e **só** eles.

    ⚠️ Existe por causa de uma medição, não de um pedido de tela: para escrever
    "3 de 2050 alunos · 3 almoço · 3 janta", o hub chamava `GET /alunos` — a
    leitura mais cara do produto, que monta turmas, sedes, classificações,
    vestibulares, sparklines, simulados e **todas as notas**. Medido no compose
    em 09/09: só a consulta de `nota` são **78.107 linhas e 9,31 MB**, e o
    cliente PostgREST é síncrono, então esse tempo todo é event loop parado
    (docs/40 §12.1.2).

    `ativos` sai por `count="exact"`, que é um `HEAD` no PostgREST: o número
    volta no header e nenhuma linha viaja. Os direitos vêm inteiros porque a
    tabela é limitada por aluno — no máximo dois por pessoa, ~1.800 linhas no
    teto do colégio —, o mesmo raciocínio de `publico_da_cantina`.

    ⚠️ **Devolve contagem, nunca lista.** O irmão desta rota
    (`/direito-refeicao`) traz a restrição alimentar de cada aluno junto, e é
    dado de saúde de menor (docs/38 §2.6) — um card de resumo não pode ser o
    caminho mais fácil para ele sair da tela onde a revelação é deliberada.
    """
    cliente = get_supabase()
    ativos = (
        cliente.table("aluno").select("id", count="exact").eq("ativo", True).limit(1).execute()
    ).count or 0

    linhas = (
        cliente.table("direito_refeicao_aluno").select("aluno_id, refeicao").execute().data or []
    )
    por_refeicao = {refeicao: 0 for refeicao in REFEICOES}
    for linha in linhas:
        if linha["refeicao"] in por_refeicao:
            por_refeicao[linha["refeicao"]] += 1

    return {
        "ativos": ativos,
        # Alunos DISTINTOS com algum direito — não a soma das duas refeições,
        # que contaria duas vezes quem come nas duas.
        "comDireito": len({linha["aluno_id"] for linha in linhas}),
        **por_refeicao,
    }


@router_admin.get("/direito-refeicao")
async def listar_direitos() -> dict:
    """Todos os alunos ativos, com o que cada um tem hoje.

    Leitura é de qualquer coordenador; escrever é do administrador. É a mesma
    divisão de `Contas.tsx` — ver quem tem acesso não é o mesmo que dar acesso.
    """
    cliente = get_supabase()
    alunos = (
        cliente.table("aluno")
        .select("id, nome, matricula, restricao_alimentar")
        .eq("ativo", True)
        .execute()
        .data
        or []
    )
    direitos = (
        cliente.table("direito_refeicao_aluno").select("aluno_id, refeicao").execute().data or []
    )
    por_aluno: dict[str, list[str]] = {}
    for linha in direitos:
        por_aluno.setdefault(linha["aluno_id"], []).append(linha["refeicao"])

    matriculas = (
        cliente.table("matricula_turma")
        .select("aluno_id, turma(section_original)")
        .is_("ativo_ate", "null")
        .execute()
        .data
        or []
    )
    turma_por_aluno = {
        m["aluno_id"]: (m.get("turma") or {}).get("section_original") for m in matriculas
    }

    saida = [
        {
            "id": a["id"],
            "nome": a["nome"],
            "matricula": a.get("matricula"),
            "turma": turma_por_aluno.get(a["id"]),
            "direitos": sorted(por_aluno.get(a["id"], [])),
            "restricaoAlimentar": a.get("restricao_alimentar"),
        }
        for a in alunos
    ]
    saida.sort(key=lambda linha: (linha["nome"] or "").casefold())
    return {"total": len(saida), "comDireito": sum(1 for a in saida if a["direitos"]), "alunos": saida}


@router_admin.post("/direito-refeicao", dependencies=[Depends(get_current_administrador)])
async def conceder_direito(
    body: DireitoBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Liga ou desliga o direito, para um aluno ou para oitenta.

    ⚠️ Auditado sempre, e não por zelo: é benefício com consequência
    financeira, e "quem liberou este aluno?" precisa ter resposta (docs/38
    §3.4). A linha vai para `evento_auditoria` no canal `cantina`.
    """
    if body.refeicao not in REFEICOES:
        raise HTTPException(status_code=422, detail=f"refeicao deve ser uma de {REFEICOES}")

    cliente = get_supabase()
    if body.conceder:
        # `upsert` e não `insert`: conceder o que já está concedido é um
        # não-evento, não um 409 na cara de quem selecionou 80 alunos e acertou
        # 79 deles.
        cliente.table("direito_refeicao_aluno").upsert(
            [{"aluno_id": a, "refeicao": body.refeicao} for a in body.aluno_ids],
            on_conflict="aluno_id,refeicao",
        ).execute()
    else:
        cliente.table("direito_refeicao_aluno").delete().eq("refeicao", body.refeicao).in_(
            "aluno_id", body.aluno_ids
        ).execute()

    auditar(
        cliente,
        "direito_refeicao_concedido" if body.conceder else "direito_refeicao_revogado",
        canal="cantina", ator_tipo="coordenador", ator_id=administrador.get("sub"),
        ip=_ip(request),
        # Os ids vão para o detalhe: sem eles a trilha diria "alguém mexeu em
        # 80 alunos" e não "em quais".
        detalhe={"refeicao": body.refeicao, "alunos": body.aluno_ids},
    )
    # Um evento por aluno, e não um só para o lote: é o `aluno_id` que faz o
    # filtro do stream dele acertar. Oitenta eventos cabem — a fila descarta o
    # mais velho e todos levam ao mesmo refetch.
    for alvo in body.aluno_ids:
        barramento.publicar(Evento(tipo="direito", refeicao=body.refeicao, aluno_id=alvo))
    return {"alterados": len(body.aluno_ids), "refeicao": body.refeicao, "conceder": body.conceder}


@router_admin.put(
    "/alunos/{aluno_id}/restricao-alimentar",
    dependencies=[Depends(get_current_administrador)],
)
async def salvar_restricao(
    aluno_id: str,
    body: RestricaoBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """A restrição alimentar do aluno (docs/38 §2.6).

    ⚠️ **É a primeira informação de saúde no SAS.** Quem preenche é a
    coordenação, e não o aluno: autodeclaração de saúde por menor abre um
    problema de consentimento que este produto não tem estrutura para resolver.
    Auditado como a concessão do direito — e o CONTEÚDO não vai para a trilha,
    pela regra da casa de que auditoria responde "quem" e "quando", não
    reproduz o dado.
    """
    texto = (body.restricao or "").strip() or None
    cliente = get_supabase()
    atualizado = (
        cliente.table("aluno")
        .update({"restricao_alimentar": texto}, returning="representation")
        .eq("id", aluno_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="aluno não encontrado")

    auditar(
        cliente, "restricao_alimentar_editada", canal="cantina",
        ator_tipo="coordenador", ator_id=administrador.get("sub"),
        recurso=f"aluno/{aluno_id}", ip=_ip(request),
        detalhe={"preenchida": texto is not None},
    )
    return {"id": aluno_id, "restricaoAlimentar": texto}


# ─── A coordenação: as contas da cantina ──────────────────────────────────
#
# Tudo aqui é do administrador, pela regra da 0045: criar login para outra
# pessoa fica com UMA conta, e não há motivo para a cantina ser exceção.


class NovaCantinaBody(BaseModel):
    nome: str
    prazo_padrao_dias_antes: int = Field(default=1, ge=0)
    prazo_padrao_hora: str = "20:00"
    # Preço de TABELA, não cobrança: o SAS não fatura nem sabe quem pagou. O
    # valor existe para a coordenação somar o custo do que foi pedido, que é a
    # pergunta do fim do mês. `None` = ainda não informado, e é diferente de
    # 0,00 — a tela precisa distinguir para não somar zero como se fosse dado.
    valor_almoco: float | None = Field(default=None, ge=0)
    valor_janta: float | None = Field(default=None, ge=0)
    # A regra de modos da casa (docs/40 §1), com a MESMA semântica dos valores:
    # `None` é "não disse", nunca "desligue" — e aqui o ausente cai no DEFAULT
    # da 0051 (pedido ligado, presencial desligado) em vez de virar NULL, que a
    # coluna nem aceita.
    aceita_pedido_almoco: bool | None = None
    aceita_pedido_janta: bool | None = None
    aceita_presencial_almoco: bool | None = None
    aceita_presencial_janta: bool | None = None


class EditarCantinaBody(BaseModel):
    nome: str | None = None
    ativo: bool | None = None
    prazo_padrao_dias_antes: int | None = Field(default=None, ge=0)
    prazo_padrao_hora: str | None = None
    valor_almoco: float | None = Field(default=None, ge=0)
    valor_janta: float | None = Field(default=None, ge=0)
    aceita_pedido_almoco: bool | None = None
    aceita_pedido_janta: bool | None = None
    aceita_presencial_almoco: bool | None = None
    aceita_presencial_janta: bool | None = None


class NovaContaCantinaBody(BaseModel):
    cantina_id: str
    email: str
    nome: str
    #: A senha escolhida pelo administrador. `None` = sorteie uma, que é o
    #: comportamento de sempre — nenhum cliente antigo precisa mudar
    #: (docs/40 §12.7).
    senha: str | None = None


class RedefinirSenhaBody(BaseModel):
    #: Mesmo contrato do cadastro: `None` sorteia.
    senha: str | None = None


class EditarContaCantinaBody(BaseModel):
    nome: str | None = None
    ativo: bool | None = None


@router_admin.get("/cantinas")
async def listar_cantinas() -> list[dict]:
    """As cantinas e as contas de cada uma. Leitura é de qualquer coordenador —
    saber quem tem acesso é diferente de dar acesso."""
    cliente = get_supabase()
    cantinas = cliente.table("cantina").select("*").execute().data or []
    contas = (
        cliente.table("usuario_cantina")
        .select("id, cantina_id, email, nome, ativo, ultimo_login_em")
        .execute()
        .data
        or []
    )
    por_cantina: dict[str, list[dict]] = {}
    for conta in contas:
        por_cantina.setdefault(conta["cantina_id"], []).append(conta)
    for lista in por_cantina.values():
        lista.sort(key=lambda c: (c["nome"] or "").casefold())

    saida = [{**c, "contas": por_cantina.get(c["id"], [])} for c in cantinas]
    saida.sort(key=lambda c: (c["nome"] or "").casefold())
    return saida


@router_admin.post("/cantinas", dependencies=[Depends(get_current_administrador)])
async def criar_cantina(
    body: NovaCantinaBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    cliente = get_supabase()
    campos = {
        "nome": body.nome.strip(),
        "prazo_padrao_dias_antes": body.prazo_padrao_dias_antes,
        "prazo_padrao_hora": body.prazo_padrao_hora,
        "valor_almoco": body.valor_almoco,
        "valor_janta": body.valor_janta,
    }
    # Os modos entram só se vieram — ao contrário dos valores, que são anuláveis
    # e podem ir como `None`. Estas quatro colunas são NOT NULL: mandar `None`
    # seria erro do banco, e o certo para "não disse" é deixar o DEFAULT da 0051
    # responder (docs/40 §1).
    for campo in CAMPOS_DE_MODO_DA_CASA:
        escolhido = getattr(body, campo)
        if escolhido is not None:
            campos[campo] = escolhido

    linha = (
        cliente.table("cantina").insert(campos, returning="representation").execute()
    ).data[0]
    auditar(
        cliente, "cantina_criada", canal="cantina", ator_tipo="coordenador",
        ator_id=administrador.get("sub"), recurso=f"cantina/{linha['id']}",
        ip=_ip(request), detalhe={"nome": body.nome},
    )
    return {**linha, "contas": []}


@router_admin.patch("/cantinas/{cantina_id}", dependencies=[Depends(get_current_administrador)])
async def editar_cantina(
    cantina_id: str,
    body: EditarCantinaBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Renomear, (des)ativar, ou mudar as regras da casa — prazo e modos.

    Desativar a cantina tranca as contas dela sem precisar mexer em cada uma —
    é o que `_login_da_cantina` confere.
    """
    patch: dict = {}
    if body.nome is not None and body.nome.strip():
        patch["nome"] = body.nome.strip()
    if body.ativo is not None:
        patch["ativo"] = body.ativo
    if body.prazo_padrao_dias_antes is not None:
        patch["prazo_padrao_dias_antes"] = body.prazo_padrao_dias_antes
    if body.prazo_padrao_hora:
        patch["prazo_padrao_hora"] = body.prazo_padrao_hora
    # Os valores entram mesmo quando são `None`? NÃO: `None` no corpo significa
    # "não mexi neste campo", e apagar um preço por omissão seria o pior tipo
    # de perda silenciosa. Zerar um valor é mandar 0.
    if body.valor_almoco is not None:
        patch["valor_almoco"] = body.valor_almoco
    if body.valor_janta is not None:
        patch["valor_janta"] = body.valor_janta
    # A regra de modos, pela mesma porta: ligar o presencial do almoço não pode
    # desligar o da janta só porque o corpo não falou dela (docs/40 §1).
    for campo in CAMPOS_DE_MODO_DA_CASA:
        escolhido = getattr(body, campo)
        if escolhido is not None:
            patch[campo] = escolhido
    if not patch:
        raise HTTPException(status_code=422, detail="Nada para alterar.")

    cliente = get_supabase()
    atualizado = (
        cliente.table("cantina")
        .update(patch, returning="representation")
        .eq("id", cantina_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="cantina não encontrada")
    auditar(
        cliente, "cantina_editada", canal="cantina", ator_tipo="coordenador",
        ator_id=administrador.get("sub"), recurso=f"cantina/{cantina_id}",
        ip=_ip(request), detalhe=patch,
    )
    return atualizado[0]


@router_admin.post("/usuarios-cantina", dependencies=[Depends(get_current_administrador)])
async def criar_conta_de_cantina(
    body: NovaContaCantinaBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Cria o login. A senha volta UMA vez, para o administrador entregar.

    O mesmo contrato de `POST /administracao/coordenadores`: o hash é PBKDF2 de
    mão única, então depois disto ninguém — nem o sistema — lê a senha de
    volta. "Ver a senha" não existe; existe redefinir.
    """
    cliente = get_supabase()
    email = body.email.strip().lower()
    _cantina_por_id(cliente, body.cantina_id)

    existente = (
        cliente.table("usuario_cantina").select("id").eq("email", email).limit(1).execute().data
    )
    if existente:
        raise HTTPException(status_code=409, detail=f"Já existe conta para {email}.")

    senha = senha_definida.resolver(body.senha, email=email)
    linha = (
        cliente.table("usuario_cantina")
        .insert(
            {
                "cantina_id": body.cantina_id,
                "email": email,
                "nome": body.nome.strip(),
                "senha_hash": hash_senha(senha),
                "ativo": True,
            },
            returning="representation",
        )
        .execute()
    ).data[0]

    auditar(
        cliente, "conta_cantina_criada", canal="cantina", ator_tipo="coordenador",
        ator_id=administrador.get("sub"), recurso=f"usuario_cantina/{linha['id']}",
        ip=_ip(request), detalhe={"email": email, "nome": body.nome},
    )
    return {
        "id": linha["id"], "cantina_id": body.cantina_id, "email": email,
        "nome": linha["nome"], "ativo": True, "ultimo_login_em": None,
        # Única vez que a senha aparece. Não vai para a auditoria.
        "senha_inicial": senha,
    }


@router_admin.patch(
    "/usuarios-cantina/{usuario_id}", dependencies=[Depends(get_current_administrador)]
)
async def editar_conta_de_cantina(
    usuario_id: str,
    body: EditarContaCantinaBody,
    request: Request,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Renomear ou (des)ativar. Nunca apagar: a conta apagada viraria um uuid
    sem nome em `cardapio.criado_por` e na trilha de auditoria."""
    patch: dict = {}
    if body.nome is not None and body.nome.strip():
        patch["nome"] = body.nome.strip()
    if body.ativo is not None:
        patch["ativo"] = body.ativo
    if not patch:
        raise HTTPException(status_code=422, detail="Nada para alterar.")

    cliente = get_supabase()
    atualizado = (
        cliente.table("usuario_cantina")
        .update(patch, returning="representation")
        .eq("id", usuario_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    auditar(
        cliente, "conta_cantina_editada", canal="cantina", ator_tipo="coordenador",
        ator_id=administrador.get("sub"), recurso=f"usuario_cantina/{usuario_id}",
        ip=_ip(request), detalhe=patch,
    )
    linha = atualizado[0]
    return {
        k: linha[k]
        for k in ("id", "cantina_id", "email", "nome", "ativo", "ultimo_login_em")
        if k in linha
    }


@router_admin.post(
    "/usuarios-cantina/{usuario_id}/redefinir-senha",
    dependencies=[Depends(get_current_administrador)],
)
async def redefinir_senha_de_cantina(
    usuario_id: str,
    request: Request,
    body: RedefinirSenhaBody | None = None,
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    """Troca a senha: por uma sorteada, ou pela que o administrador digitou.

    ⚠️ Continua não existindo "ver a senha" — o hash é de mão única. O que
    existe é DEFINIR: quem define, sabe, e era isso que "ver" queria resolver
    (docs/40 §12.7).
    """
    cliente = get_supabase()
    conta = (
        cliente.table("usuario_cantina")
        .select("email")
        .eq("id", usuario_id)
        .limit(1)
        .execute()
        .data
    )
    if not conta:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    # A validação lê o e-mail DA CONTA, não o do corpo: é o e-mail com que a
    # pessoa vai entrar, e é dele que a senha não pode ser derivada.
    senha = senha_definida.resolver(
        body.senha if body else None, email=conta[0]["email"]
    )
    atualizado = (
        cliente.table("usuario_cantina")
        .update({"senha_hash": hash_senha(senha)}, returning="representation")
        .eq("id", usuario_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="conta não encontrada")
    auditar(
        cliente, "senha_cantina_redefinida", canal="cantina", ator_tipo="coordenador",
        ator_id=administrador.get("sub"), recurso=f"usuario_cantina/{usuario_id}",
        ip=_ip(request),
    )
    return {"id": usuario_id, "senha_nova": senha}
