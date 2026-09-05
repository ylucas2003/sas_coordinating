"""Cantina — cardápio, pedido do aluno e a leitura da coordenação (docs/38).

Três públicos e três routers, e a separação NÃO é organização de arquivo: é o
contorno de segurança. Cada router tem o seu guard no piso, então nenhuma rota
nova nasce sem dono:

  * `router` (`/cantina`)          — a cantina lança e lê o que é dela;
  * `router_aluno` (`/me/cantina`) — o aluno vê o que pode e pede;
  * `router_admin` (`/administracao`) — quem tem direito, e as contas.

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
do projeto que cresce por dia × aluno × item.
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..auditoria import registrar as auditar
from ..auth import (
    get_current_administrador,
    get_current_aluno,
    get_current_cantina,
    get_current_coordenador,
    hash_senha,
)
from ..banco.missao import FUSO_DA_ESCOLA
from ..supabase_client import ClienteDados, get_supabase

REFEICOES = ("almoco", "janta")

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


def _montar_cardapio(cliente: ClienteDados, cardapio: dict, agora: datetime) -> dict:
    """Cardápio + blocos + opções, ordenados, prontos para a tela.

    A ordenação é feita aqui e não no PostgREST porque o `order` dele não
    alcança relação aninhada em dois níveis — e as listas são de dezenas de
    itens, não de milhares.
    """
    blocos = (
        cliente.table("cardapio_bloco")
        .select("*, cardapio_opcao(*)")
        .eq("cardapio_id", cardapio["id"])
        .execute()
        .data
        or []
    )
    blocos.sort(key=lambda b: b.get("ordem") or 0)
    for bloco in blocos:
        opcoes = bloco.pop("cardapio_opcao", None) or []
        opcoes.sort(key=lambda o: o.get("ordem") or 0)
        bloco["opcoes"] = opcoes
    return {**cardapio, "estado": _estado(cardapio, agora), "blocos": blocos}


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
    blocos: list[BlocoBody] = Field(default_factory=list)


class NovoCardapioBody(BaseModel):
    data: date
    refeicao: str


class CopiarBody(BaseModel):
    origem_id: str


class PedidoBody(BaseModel):
    opcao_ids: list[str] = Field(default_factory=list)


# ─── A cantina: calendário ────────────────────────────────────────────────


def _calendario(cliente: ClienteDados, cantina_id: str, de: date, ate: date) -> list[dict]:
    """Um objeto por cardápio existente na janela, com estado e nº de pedidos.

    Dia sem cardápio não vem: quem sabe quais dias existem no mês é o
    calendário da tela, e mandar 30 objetos vazios só para ele descobrir isso
    seria o servidor desenhando a grade.
    """
    agora = _agora()
    cardapios = (
        cliente.table("cardapio")
        .select("id, data, refeicao, pedidos_ate, publicado_em, sem_refeicao")
        .eq("cantina_id", cantina_id)
        .gte("data", de.isoformat())
        .lte("data", ate.isoformat())
        .execute()
        .data
        or []
    )
    if not cardapios:
        return []

    # A contagem vem da view (0049), e não de um count por cardápio: o
    # calendário mostra um mês inteiro, e contar em Python exigiria trazer
    # todos os pedidos do mês só para saber o tamanho de cada dia.
    ids = [c["id"] for c in cardapios]
    contagens = (
        cliente.table("v_pedidos_por_cardapio")
        .select("cardapio_id, quantos")
        .in_("cardapio_id", ids)
        .execute()
        .data
        or []
    )
    por_cardapio = {c["cardapio_id"]: c["quantos"] for c in contagens}

    saida = [
        {
            "id": c["id"],
            "data": c["data"],
            "refeicao": c["refeicao"],
            "estado": _estado(c, agora),
            "pedidosAte": c.get("pedidos_ate"),
            "pedidos": por_cardapio.get(c["id"], 0),
        }
        for c in cardapios
    ]
    saida.sort(key=lambda c: (c["data"], c["refeicao"]))
    return saida


@router.get("/calendario")
async def calendario_da_cantina(
    de: date,
    ate: date,
    usuario: dict = Depends(get_current_cantina),
) -> list[dict]:
    """O mês da cantina: que dias têm cardápio, em que estado, com quantos pedidos."""
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

    linha = (
        cliente.table("cardapio")
        .insert(
            {
                "cantina_id": cantina["id"],
                "data": body.data.isoformat(),
                "refeicao": body.refeicao,
                "pedidos_ate": _prazo_pela_regra(cantina, body.data).isoformat(),
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
    return _montar_cardapio(cliente, atualizado, _agora())


@router.post("/cardapios/{cardapio_id}/publicar")
async def publicar_cardapio(
    cardapio_id: str,
    request: Request,
    usuario: dict = Depends(get_current_cantina),
) -> dict:
    """Rascunho → publicado. É o instante em que o cardápio passa a existir
    para o aluno.

    Duas recusas, e as duas são o produto, não validação de formulário:
    publicar sem prazo entregaria um cardápio que ninguém sabe até quando pode
    pedir; publicar sem opção entregaria uma tela vazia com ar de erro.
    """
    cliente = get_supabase()
    cardapio = _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    montado = _montar_cardapio(cliente, cardapio, _agora())

    if not cardapio.get("sem_refeicao"):
        if not cardapio.get("pedidos_ate"):
            raise HTTPException(
                status_code=422,
                detail="Defina até quando o aluno pode pedir antes de publicar.",
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


def _pedidos_do_cardapio(cliente: ClienteDados, cardapio_id: str) -> list[dict]:
    """Linha por aluno: nome, turma, restrição e o que ele marcou.

    ⚠️ **É tudo que a cantina vê do aluno** (docs/38 §8.2.2). Nenhuma consulta
    daqui toca `nota`, `simulado` ou ficha: são dados de menores, e a lista de
    pedidos já é informação sensível por tabela interposta — a escolha
    vegetariana insinua religião ou saúde.
    """
    pedidos = (
        cliente.table("pedido_refeicao")
        .select("id, aluno_id, criado_em, aluno(nome, restricao_alimentar)")
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
    nomes = {
        linha["opcao_id"]: linha["opcao"] for linha in _contagem(cliente, cardapio_id)
    }
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
        }
        for p in pedidos
    ]
    saida.sort(key=lambda linha: (linha["nome"] or "").casefold())
    return saida


@router.get("/cardapios/{cardapio_id}/contagem")
async def contagem_do_cardapio(
    cardapio_id: str,
    usuario: dict = Depends(get_current_cantina),
) -> list[dict]:
    """O que cozinhar: uma linha por opção, com quantos pediram."""
    cliente = get_supabase()
    _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    return _contagem(cliente, cardapio_id)


@router.get("/cardapios/{cardapio_id}/pedidos")
async def pedidos_do_cardapio(
    cardapio_id: str,
    usuario: dict = Depends(get_current_cantina),
) -> list[dict]:
    """O que servir: uma linha por aluno, para o balcão."""
    cliente = get_supabase()
    _cardapio_da_cantina(cliente, cardapio_id, usuario["cantina_id"])
    return _pedidos_do_cardapio(cliente, cardapio_id)


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
    meus = (
        cliente.table("pedido_refeicao")
        .select("id, cardapio_id, pedido_refeicao_item(opcao_id)")
        .eq("aluno_id", aluno_id)
        .in_("cardapio_id", ids)
        .execute()
        .data
        or []
    )
    pedido_por_cardapio = {
        p["cardapio_id"]: sorted(i["opcao_id"] for i in (p.get("pedido_refeicao_item") or []))
        for p in meus
    }

    dias = [
        {
            **_montar_cardapio(cliente, c, agora),
            "meuPedido": pedido_por_cardapio.get(c["id"]),
        }
        for c in cardapios
    ]
    dias.sort(key=lambda d: (d["data"], d["refeicao"]))
    return {"direitos": direitos, "dias": dias}


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
    """
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    cardapio = _cardapio_aberto_para(cliente, cardapio_id, aluno_id)
    montado = _montar_cardapio(cliente, cardapio, _agora())
    _validar_escolhas(montado, body.opcao_ids)

    existente = (
        cliente.table("pedido_refeicao")
        .select("id")
        .eq("cardapio_id", cardapio_id)
        .eq("aluno_id", aluno_id)
        .limit(1)
        .execute()
        .data
    )
    if existente:
        pedido_id = existente[0]["id"]
        cliente.table("pedido_refeicao").update(
            {"atualizado_em": _agora().isoformat()}
        ).eq("id", pedido_id).execute()
        # Substituir em vez de casar item a item: a lista tem quatro elementos,
        # e um diff aqui seria código para manter sem ganho nenhum.
        cliente.table("pedido_refeicao_item").delete().eq("pedido_id", pedido_id).execute()
    else:
        pedido_id = (
            cliente.table("pedido_refeicao")
            .insert(
                {"cardapio_id": cardapio_id, "aluno_id": aluno_id},
                returning="representation",
            )
            .execute()
        ).data[0]["id"]

    if body.opcao_ids:
        cliente.table("pedido_refeicao_item").insert(
            [{"pedido_id": pedido_id, "opcao_id": oid} for oid in body.opcao_ids]
        ).execute()

    return {"cardapioId": cardapio_id, "opcaoIds": sorted(body.opcao_ids)}


@router_aluno.delete("/pedidos/{cardapio_id}")
async def cancelar_pedido(
    cardapio_id: str,
    aluno: dict = Depends(get_current_aluno),
) -> dict:
    """Desisti. Passa pelas mesmas três recusas do `PUT`: depois do prazo o
    pedido está contado, e a cantina já comprou."""
    cliente = get_supabase()
    aluno_id = aluno["aluno_id"]
    _cardapio_aberto_para(cliente, cardapio_id, aluno_id)
    cliente.table("pedido_refeicao").delete().eq("cardapio_id", cardapio_id).eq(
        "aluno_id", aluno_id
    ).execute()
    return {"cardapioId": cardapio_id, "opcaoIds": None}


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
async def calendario_da_coordenacao(de: date, ate: date, cantina: str | None = None) -> list[dict]:
    cliente = get_supabase()
    return _calendario(cliente, _cantina_padrao(cliente, cantina)["id"], de, ate)


@router_admin.get("/cantina/cardapios/{cardapio_id}")
async def cardapio_para_a_coordenacao(cardapio_id: str) -> dict:
    """O cardápio como a cantina o vê, sem poder mexer.

    Não filtra por cantina: a coordenação enxerga todas por desenho, e o id do
    cardápio já é específico o bastante.
    """
    cliente = get_supabase()
    linha = cliente.table("cardapio").select("*").eq("id", cardapio_id).limit(1).execute().data
    if not linha:
        raise HTTPException(status_code=404, detail="cardápio não encontrado")
    montado = _montar_cardapio(cliente, linha[0], _agora())
    montado["contagem"] = _contagem(cliente, cardapio_id)
    montado["pedidos"] = _pedidos_do_cardapio(cliente, cardapio_id)
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


class EditarCantinaBody(BaseModel):
    nome: str | None = None
    ativo: bool | None = None
    prazo_padrao_dias_antes: int | None = Field(default=None, ge=0)
    prazo_padrao_hora: str | None = None


class NovaContaCantinaBody(BaseModel):
    cantina_id: str
    email: str
    nome: str


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
    linha = (
        cliente.table("cantina")
        .insert(
            {
                "nome": body.nome.strip(),
                "prazo_padrao_dias_antes": body.prazo_padrao_dias_antes,
                "prazo_padrao_hora": body.prazo_padrao_hora,
            },
            returning="representation",
        )
        .execute()
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
    """Renomear, (des)ativar, ou mudar a regra de prazo da casa.

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

    senha = secrets.token_urlsafe(12)
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
    administrador: dict = Depends(get_current_administrador),
) -> dict:
    cliente = get_supabase()
    senha = secrets.token_urlsafe(12)
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
