"""A leitura da cantina — o que as telas da coordenação mostram, num lugar só.

Até 30/10/2026 isto morava em `routes/cantina.py`, como funções privadas da
rota. A decisão da coordenação de 30/10 — tudo o que ela lê na plataforma a IA
dela lê também, pelo MCP (docs/43 §5) — trouxe um segundo leitor: as tools de
`chat/tools/cantina.py`. Duas cópias da mesma regra divergem no primeiro caso
de borda (o estado do cardápio, o default dos modos, a turma de hoje, quem
conta como "vai comer"), e a divergência aparece como "a IA disse outra coisa
que a tela". Por isso a regra saiu da rota, e a rota e a tool a chamam daqui
(docs/43 §4.4). `cantina_relatorio.py` continua sendo o domínio dos custos e
das planilhas; este é o da leitura de tela.

Três coisas que o segundo leitor muda, e que moram aqui:

  * COLUNAS EXPLÍCITAS em todo select que a tool alcança. O papel do MCP
    (`sas_mcp`) só tem SELECT coluna por coluna (migrations 0071 e 0075), e
    `select=*` numa tabela com GRANT por coluna dá 42501. As listas abaixo são
    as colunas que as telas usam — coluna nova não aparece sozinha nem na tela
    nem no MCP, e é de propósito: é a falha fechada da 0071.
  * A CONTAGEM tem duas fontes, lado a lado. As rotas leem as views da 0049 e
    da 0052 (`v_pedidos_por_cardapio`, `v_contagem_pedidos_por_opcao`), porque
    o calendário da cantina mostra um mês, e somar em Python traria todos os
    pedidos do mês pelo PostgREST (CLAUDE.md, armadilha 2). O MCP não lê view
    nenhuma: nenhuma view do schema usa security_invoker, elas rodam com o
    privilégio do DONO, e um GRANT nelas exporia tudo o que leem (0071). Para
    ele, a MESMA conta sai das tabelas de base, numa janela que a tool limita
    — `contar_pelos_pedidos` e `contagem_por_opcao_pelos_itens`, escritas ao
    lado das que leem a view para que quem mudar uma veja a outra. Que as duas
    dão o mesmo número é teste (tests/test_chat_tools_cantina.py), contra a
    agregação da 0052 reconstruída do jeito que test_cantina_retirada.py já
    fazia.
  * O PADRÃO É O SEGURO. Toda função que pode ler a restrição alimentar só a
    lê com `com_restricao=True`, dito por quem chama: a rota da cantina e a da
    coordenação dizem; as tools da cantina não dizem, salvo
    `restricoes_alimentares`. O que não é lido não tem como vazar por um campo
    novo escrito às pressas — a regra de `cantina_relatorio._ler`.

⚠️ O backend nunca escreve SQL (CLAUDE.md): tudo é `.table(...)` do PostgREST,
e nada aqui escreve.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from .supabase_client import ClienteDados

REFEICOES = ("almoco", "janta")

#: Os dois jeitos de comer (docs/40 §1). `pedido` escolhe itens com
#: antecedência e compromete a cozinha; `presencial` é declaração de presença,
#: sem prato, e só vira compromisso quando o QR é lido.
MODO_PEDIDO = "pedido"
MODO_PRESENCIAL = "presencial"

#: A cantina e a regra da casa (0047, 0050, 0051) — o que `/cantina/acesso`
#: mostra de cada uma. Sem `criado_em`, que tela nenhuma lê. As CONTAS
#: (`usuario_cantina`) não moram aqui: são credencial, e o MCP não as lê
#: (0071, 0075).
COLUNAS_DA_CANTINA = (
    "id, nome, ativo, prazo_padrao_dias_antes, prazo_padrao_hora, valor_almoco, valor_janta, "
    "aceita_pedido_almoco, aceita_pedido_janta, aceita_presencial_almoco, aceita_presencial_janta"
)

#: O cardápio como o calendário o lê. Sem `criado_por` (o uuid da CONTA da
#: cantina que lançou), `criado_em` e `atualizado_em`.
COLUNAS_DO_CARDAPIO = (
    "id, cantina_id, data, refeicao, pedidos_ate, publicado_em, sem_refeicao, "
    "aceita_pedido, aceita_presencial"
)

#: Blocos e opções, numa ida só (o embed é o que tirou o N+1 da rota do aluno,
#: docs/40 §12.1.3). As colunas são TODAS as das duas tabelas hoje (0048, 0053):
#: era o `*, cardapio_opcao(*)` de antes, escrito por extenso.
COLUNAS_DOS_BLOCOS = (
    "id, cardapio_id, nome, ordem, escolhas_minimas, escolhas_maximas, observacao, "
    "cardapio_opcao(id, bloco_id, nome, ordem, disponivel)"
)


# ─── Tempo e estado ──────────────────────────────────────────────────────


def agora() -> datetime:
    return datetime.now(UTC)


def instante(bruto: str | None) -> datetime | None:
    """timestamptz do PostgREST → datetime com fuso.

    O PostgREST devolve ISO-8601 já com offset; o `replace` cobre o `Z` que
    algumas versões emitem e que o `fromisoformat` do Python só aceita a
    partir do 3.11.
    """
    if not bruto:
        return None
    return datetime.fromisoformat(str(bruto).replace("Z", "+00:00"))


def estado(cardapio: Mapping[str, Any], momento: datetime) -> str:
    """Os CINCO estados do calendário (docs/38 §3.3).

    `aberto` e `fechado` são o mesmo cardápio publicado antes e depois do
    prazo, e a diferença é a que a cantina mais precisa ler: em `fechado` a
    contagem é final, e é ela que vai para o fogão.
    """
    if cardapio.get("sem_refeicao"):
        return "sem-refeicao"
    if not cardapio.get("publicado_em"):
        return "rascunho"
    prazo = instante(cardapio.get("pedidos_ate"))
    if prazo is None or momento >= prazo:
        return "fechado"
    return "aberto"


def modos_pela_regra(cantina: Mapping[str, Any], refeicao: str) -> tuple[bool, bool]:
    """Que modos a REGRA da casa liga num cardápio novo daquela refeição (docs/40 §1).

    Só pré-preenche: o valor do dia é do cardápio (`modos_do_cardapio`). Os
    fallbacks espelham os DEFAULT da 0051 — pedido ligado, presencial
    desligado —, senão o modo passaria a depender da origem da linha.
    """
    aceita_pedido = cantina.get(f"aceita_pedido_{refeicao}")
    aceita_presencial = cantina.get(f"aceita_presencial_{refeicao}")
    return (
        True if aceita_pedido is None else bool(aceita_pedido),
        False if aceita_presencial is None else bool(aceita_presencial),
    )


def modos_do_cardapio(cardapio: Mapping[str, Any]) -> tuple[bool, bool]:
    """O que ESTE dia aceita. Os fallbacks espelham os DEFAULT da 0051 —
    pedido ligado, presencial desligado —, senão o modo passaria a depender da
    origem da linha."""
    aceita_pedido = cardapio.get("aceita_pedido")
    aceita_presencial = cardapio.get("aceita_presencial")
    return (
        True if aceita_pedido is None else bool(aceita_pedido),
        False if aceita_presencial is None else bool(aceita_presencial),
    )


# ─── O cardápio ──────────────────────────────────────────────────────────


def blocos_por_cardapio(cliente: ClienteDados, cardapio_ids: list[str]) -> dict[str, list[dict]]:
    """Blocos e opções de VÁRIOS cardápios, numa ida só.

    ⚠️ Existe por causa de um N+1 medido, não por elegância: `cantina_do_aluno`
    chamava a montagem dentro do `for`, e uma semana lançada com almoço e janta
    são ~10 idas ao PostgREST **em série** — cada uma bloqueando o event loop,
    porque o cliente é síncrono (docs/40 §12.1.3). E essa rota tem
    `refetchInterval` de 60 s por aluno com direito.

    A ordenação continua em Python: o `order` do PostgREST não alcança relação
    aninhada em dois níveis, e as listas são de dezenas de itens.
    """
    if not cardapio_ids:
        return {}
    blocos = (
        cliente.table("cardapio_bloco")
        .select(COLUNAS_DOS_BLOCOS)
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


def montar_cardapio(
    cliente: ClienteDados,
    cardapio: dict,
    momento: datetime,
    *,
    blocos: list[dict] | None = None,
) -> dict:
    """Cardápio + blocos + opções, ordenados, prontos para a tela.

    `blocos` já resolvidos evitam a consulta — é como o laço de
    `cantina_do_aluno` deixou de ser N+1. Quem monta UM cardápio só continua
    chamando sem o parâmetro, e a consulta acontece aqui.
    """
    if blocos is None:
        blocos = blocos_por_cardapio(cliente, [cardapio["id"]]).get(cardapio["id"], [])
    aceita_pedido, aceita_presencial = modos_do_cardapio(cardapio)
    return {
        **cardapio,
        "estado": estado(cardapio, momento),
        # Em camelCase e derivados por `modos_do_cardapio` mesmo já viajando em
        # snake_case dentro do `**cardapio`: é o contrato da tela, e é o único
        # lugar onde o default de uma base sem a 0051 é aplicado.
        "aceitaPedido": aceita_pedido,
        "aceitaPresencial": aceita_presencial,
        "blocos": blocos,
    }


def cardapios_da_janela(
    cliente: ClienteDados, cantina_ids: list[str], de: date, ate: date
) -> list[dict]:
    """Os cardápios das cantinas na janela, com as colunas do calendário.

    Uma cantina ou várias na MESMA consulta. A versão que aceitava só uma levava
    quem quisesse o total a chamar isto num `for` — e duas idas por cantina é o
    N+1 que a §12.1.3 tirou da rota do aluno.
    """
    if not cantina_ids:
        return []
    consulta = cliente.table("cardapio").select(COLUNAS_DO_CARDAPIO)
    consulta = (
        consulta.eq("cantina_id", cantina_ids[0])
        if len(cantina_ids) == 1
        else consulta.in_("cantina_id", cantina_ids)
    )
    return (
        consulta.gte("data", de.isoformat()).lte("data", ate.isoformat()).execute().data or []
    )


# ─── Quem vai comer: a contagem por cardápio ─────────────────────────────

#: `{cardapio_id: {quantos, com_pedido, presenciais}}` — o formato da linha de
#: `v_pedidos_por_cardapio` (0052), venha ela da view ou das tabelas de base.
Contador = Callable[[ClienteDados, list[str]], dict[str, dict]]


def contar_modos(modos: Iterable[str | None]) -> dict[str, int]:
    """A conta da 0052, em Python: quantos vão comer, e por qual porta.

    `quantos` = as duas portas somadas (é o número do calendário); `com_pedido`
    = escolheu prato; `presenciais` = declarou presença pelo QR, pendentes e
    já retiradas juntas. `modo` ausente é `pedido`, como no banco: o DEFAULT da
    0051. `quantos == com_pedido + presenciais` sempre, porque modo é NOT NULL
    com CHECK de dois valores.
    """
    lista = [m or MODO_PEDIDO for m in modos]
    return {
        "quantos": len(lista),
        "com_pedido": lista.count(MODO_PEDIDO),
        "presenciais": lista.count(MODO_PRESENCIAL),
    }


def contar_pela_view(cliente: ClienteDados, cardapio_ids: list[str]) -> dict[str, dict]:
    """A contagem das ROTAS: a view da 0049/0052, uma linha por cardápio.

    View, e não count em Python: o calendário mostra um mês inteiro, e contar
    aqui exigiria trazer todos os pedidos do mês só para saber o tamanho de
    cada dia. O MCP não chega aqui — ver `contar_pelos_pedidos`.
    """
    if not cardapio_ids:
        return {}
    linhas = (
        cliente.table("v_pedidos_por_cardapio")
        .select("cardapio_id, quantos, com_pedido, presenciais")
        .in_("cardapio_id", cardapio_ids)
        .execute()
        .data
        or []
    )
    return {linha["cardapio_id"]: linha for linha in linhas}


def contar_pelos_pedidos(cliente: ClienteDados, cardapio_ids: list[str]) -> dict[str, dict]:
    """A MESMA contagem de `contar_pela_view`, das tabelas de base — a do MCP.

    Traz uma linha de `pedido_refeicao` por pessoa e cardápio, só com
    (cardapio_id, modo): é por isso que quem chama limita a janela (as tools
    da cantina vão até 31 dias). Cardápio sem pedido vem com os três zeros, como
    o LEFT JOIN da 0052 o devolve.
    """
    if not cardapio_ids:
        return {}
    linhas = (
        cliente.table("pedido_refeicao")
        .select("cardapio_id, modo")
        .in_("cardapio_id", cardapio_ids)
        .execute()
        .data
        or []
    )
    modos: dict[str, list[str | None]] = {cid: [] for cid in cardapio_ids}
    for linha in linhas:
        modos.setdefault(linha["cardapio_id"], []).append(linha.get("modo"))
    return {cid: {"cardapio_id": cid, **contar_modos(lista)} for cid, lista in modos.items()}


def calendario(
    cliente: ClienteDados,
    cantina_id: str | list[str],
    de: date,
    ate: date,
    *,
    momento: datetime | None = None,
    contar: Contador = contar_pela_view,
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

    `contar` diz de onde vem a contagem: a view, nas rotas; as tabelas de base,
    no MCP (o cabeçalho deste módulo).
    """
    momento = momento or agora()
    ids = [cantina_id] if isinstance(cantina_id, str) else list(cantina_id)
    cardapios = cardapios_da_janela(cliente, ids, de, ate)
    if not cardapios:
        return []

    por_cardapio = contar(cliente, [c["id"] for c in cardapios])

    saida = []
    for c in cardapios:
        aceita_pedido, aceita_presencial = modos_do_cardapio(c)
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
                "estado": estado(c, momento),
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


# ─── O que cozinhar: a contagem por opção ────────────────────────────────


def contagem_por_opcao_pela_view(cliente: ClienteDados, cardapio_id: str) -> list[dict]:
    """A contagem das ROTAS: uma linha por opção do cardápio, da view da 0049."""
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


def contagem_por_opcao_pelos_itens(
    cliente: ClienteDados, cardapio_id: str, blocos: list[dict]
) -> list[dict]:
    """A MESMA contagem de `contagem_por_opcao_pela_view`, das tabelas de base.

    É o que a view faz, passo a passo: cada opção dos blocos do cardápio, com
    quantos itens de pedido a escolheram — e o LEFT JOIN, que põe a opção que
    ninguém pediu com 0 em vez de sumir com ela. Os itens vêm por `opcao_id`,
    como no JOIN da view (e como `routes/cantina._opcoes_com_pedido` já lia):
    um cardápio são no máximo os alunos com direito vezes as escolhas de cada
    um, e não a tabela inteira da armadilha 2.
    """
    opcoes = [(b, o) for b in blocos for o in (b.get("opcoes") or [])]
    if not opcoes:
        return []
    itens = (
        cliente.table("pedido_refeicao_item")
        .select("opcao_id")
        .in_("opcao_id", [o["id"] for _, o in opcoes])
        .execute()
        .data
        or []
    )
    quantos: dict[str, int] = {}
    for item in itens:
        quantos[item["opcao_id"]] = quantos.get(item["opcao_id"], 0) + 1
    linhas = [
        {
            "cardapio_id": cardapio_id,
            "bloco_id": b["id"],
            "bloco": b.get("nome"),
            "bloco_ordem": b.get("ordem"),
            "opcao_id": o["id"],
            "opcao": o.get("nome"),
            "opcao_ordem": o.get("ordem"),
            "disponivel": o.get("disponivel"),
            "quantos": quantos.get(o["id"], 0),
        }
        for b, o in opcoes
    ]
    linhas.sort(key=lambda linha: (linha["bloco_ordem"] or 0, linha["opcao_ordem"] or 0))
    return linhas


def contagem_presencial(cliente: ClienteDados, cardapio_id: str) -> dict:
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


# ─── Quem vai comer: a lista ─────────────────────────────────────────────


def turma_atual_por_aluno(
    cliente: ClienteDados, aluno_ids: list[str] | None = None
) -> dict[str, str | None]:
    """A turma de HOJE de cada aluno: `matricula_turma` com `ativo_ate IS NULL`,
    que é como o resto do backend define "a turma do aluno hoje"
    (stats/classificacao_ciclo). Sem `aluno_ids`, a de todos."""
    if aluno_ids is not None and not aluno_ids:
        return {}
    consulta = cliente.table("matricula_turma").select("aluno_id, turma(section_original)")
    if aluno_ids is not None:
        consulta = consulta.in_("aluno_id", aluno_ids)
    matriculas = consulta.is_("ativo_ate", "null").execute().data or []
    return {m["aluno_id"]: (m.get("turma") or {}).get("section_original") for m in matriculas}


def pedidos_do_cardapio(
    cliente: ClienteDados,
    cardapio_id: str,
    *,
    nomes_das_opcoes: Callable[[], Mapping[str, str]],
    com_restricao: bool = False,
    com_matricula: bool = False,
) -> list[dict]:
    """Linha por aluno: nome, turma, o que ele marcou e por qual porta veio.

    ⚠️ **É tudo que a cantina vê do aluno** (docs/38 §8.2.2). Nenhuma consulta
    daqui toca `nota`, `simulado` ou ficha: são dados de menores, e a lista de
    pedidos já é informação sensível por tabela interposta — a escolha
    vegetariana insinua religião ou saúde.

    Os dois acréscimos são de quem chama, e o padrão é sem eles:

      * `com_restricao` lê e devolve a restrição alimentar — dado de SAÚDE
        (docs/38 §2.6). A cantina monta o prato com ela; as tools da cantina
        nunca a pedem (decisão de 30/10: ela tem tool própria);
      * `com_matricula` devolve a matrícula — o que o MCP precisa para trocar
        o nome por "Aluno <matrícula>" com o pseudônimo ligado
        (app/mcp/pseudonimo.py). A cantina NÃO a recebe: não é dado do balcão.

    `nomes_das_opcoes` só é chamada se houver pedido: é como a rota pede o nome
    das opções à view de contagem sem ir a ela num dia vazio, e como a tool os
    tira dos blocos que já leu.
    """
    campos_do_aluno = ["nome"]
    if com_matricula:
        campos_do_aluno.append("matricula")
    if com_restricao:
        campos_do_aluno.append("restricao_alimentar")
    pedidos = (
        cliente.table("pedido_refeicao")
        .select(f"id, aluno_id, criado_em, modo, retirado_em, aluno({', '.join(campos_do_aluno)})")
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
    nomes = nomes_das_opcoes()
    escolhas: dict[str, list[str]] = {}
    for item in itens:
        escolhas.setdefault(item["pedido_id"], []).append(nomes.get(item["opcao_id"], "—"))

    turma_por_aluno = turma_atual_por_aluno(cliente, [p["aluno_id"] for p in pedidos])

    saida = []
    for p in pedidos:
        aluno = p.get("aluno") or {}
        linha: dict[str, Any] = {"alunoId": p["aluno_id"]}
        if com_matricula:
            linha["matricula"] = aluno.get("matricula")
        linha.update(
            {
                "nome": aluno.get("nome"),
                "turma": turma_por_aluno.get(p["aluno_id"]),
            }
        )
        if com_restricao:
            linha["restricaoAlimentar"] = aluno.get("restricao_alimentar")
        linha.update(
            {
                "escolhas": sorted(escolhas.get(p["id"], [])),
                "pedidoEm": p.get("criado_em"),
                # O modo é rótulo de FLUXO, não dado sensível: quem só declarou
                # presença aparece sem escolhas, e sem esta marca a linha
                # pareceria um pedido em branco (docs/40 §8).
                "modo": p.get("modo") or MODO_PEDIDO,
                "retiradoEm": p.get("retirado_em"),
            }
        )
        saida.append(linha)
    saida.sort(key=lambda linha: (linha["nome"] or "").casefold())
    return saida


def alunos_que_vao_comer(cliente: ClienteDados, dia: date, refeicao: str) -> set[str]:
    """Quem tem linha em `pedido_refeicao` para aquele dia e refeição, nas
    duas portas e em qualquer cantina. Um por aluno, pela trava da 0055
    (`pedido_refeicao_um_por_dia`) — e é por ela que `data` e `refeicao` estão
    na linha do pedido, sem precisar do cardápio."""
    linhas = (
        cliente.table("pedido_refeicao")
        .select("aluno_id")
        .eq("data", dia.isoformat())
        .eq("refeicao", refeicao)
        .execute()
        .data
        or []
    )
    return {linha["aluno_id"] for linha in linhas}


# ─── Quem tem direito ────────────────────────────────────────────────────


def tem_restricao(texto: str | None) -> bool:
    """"Tem restrição" é texto que sobra depois do `strip`. Vazio e nulo são a
    mesma coisa para quem serve o prato (routes/cantina.RestricaoBody)."""
    return bool((texto or "").strip())


def contar_direitos_por_refeicao(linhas: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    """Quantas linhas de direito há por refeição — o "3 almoço · 3 janta" do hub
    e o público de `/cantina/publico`."""
    por_refeicao = {refeicao: 0 for refeicao in REFEICOES}
    for linha in linhas:
        if linha["refeicao"] in por_refeicao:
            por_refeicao[linha["refeicao"]] += 1
    return por_refeicao


def _linhas_de_direito(cliente: ClienteDados) -> list[dict]:
    # A tabela inteira, sem filtro: é limitada por aluno — no máximo duas linhas
    # por pessoa, ~1.800 no teto do colégio —, então não é a
    # `pedido_refeicao_item` da armadilha 2.
    return cliente.table("direito_refeicao_aluno").select("aluno_id, refeicao").execute().data or []


def alunos_e_direitos(cliente: ClienteDados, *, com_restricao: bool = False) -> dict:
    """Todos os alunos ativos, com o que cada um tem hoje — `/cantina/direitos`.

    `com_restricao` é da TELA da coordenação, que revela o texto sob clique
    (docs/38 §2.6); a tool `direitos_a_refeicao` não o pede, e a coluna nem é
    lida.
    """
    colunas = "id, nome, matricula, restricao_alimentar" if com_restricao else "id, nome, matricula"
    alunos = cliente.table("aluno").select(colunas).eq("ativo", True).execute().data or []
    por_aluno: dict[str, list[str]] = {}
    for linha in _linhas_de_direito(cliente):
        por_aluno.setdefault(linha["aluno_id"], []).append(linha["refeicao"])
    turma_por_aluno = turma_atual_por_aluno(cliente)

    saida = []
    for a in alunos:
        linha: dict[str, Any] = {
            "id": a["id"],
            "nome": a["nome"],
            "matricula": a.get("matricula"),
            "turma": turma_por_aluno.get(a["id"]),
            "direitos": sorted(por_aluno.get(a["id"], [])),
        }
        if com_restricao:
            linha["restricaoAlimentar"] = a.get("restricao_alimentar")
        saida.append(linha)
    saida.sort(key=lambda linha: (linha["nome"] or "").casefold())
    return {"total": len(saida), "comDireito": sum(1 for a in saida if a["direitos"]), "alunos": saida}


def resumo_dos_direitos(cliente: ClienteDados) -> dict:
    """Os três números do card do hub, e **só** eles (`/administracao/cantina/resumo`).

    `ativos` sai por `count="exact"`, que é um `HEAD` no PostgREST: o número
    volta no header e nenhuma linha viaja. ⚠️ Devolve contagem, nunca lista:
    a lista irmã traz a restrição alimentar, e um card de resumo não pode ser o
    caminho mais fácil para ela sair da tela onde a revelação é deliberada.
    """
    ativos = (
        cliente.table("aluno").select("id", count="exact").eq("ativo", True).limit(1).execute()
    ).count or 0
    linhas = _linhas_de_direito(cliente)
    return {
        "ativos": ativos,
        # Alunos DISTINTOS com algum direito — não a soma das duas refeições,
        # que contaria duas vezes quem come nas duas.
        "comDireito": len({linha["aluno_id"] for linha in linhas}),
        **contar_direitos_por_refeicao(linhas),
    }


# ─── As cantinas ─────────────────────────────────────────────────────────


def cantinas(cliente: ClienteDados) -> list[dict]:
    """As cantinas e a regra da casa de cada uma, em ordem de nome."""
    linhas = cliente.table("cantina").select(COLUNAS_DA_CANTINA).execute().data or []
    linhas.sort(key=lambda c: (c.get("nome") or "").casefold())
    return linhas


def ids_das_cantinas_ativas(cliente: ClienteDados) -> list[str]:
    """As cantinas que o card do hub soma (`todas=true`, docs/40 §12.6)."""
    return [
        linha["id"]
        for linha in cliente.table("cantina").select("id").eq("ativo", True).execute().data or []
    ]
