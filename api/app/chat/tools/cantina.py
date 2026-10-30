"""Tools da cantina — o que a coordenação lê nas telas da cantina (docs/38, docs/40).

Nasceram em 30/10/2026, com a decisão da coordenação de que TUDO o que ela lê na
plataforma a IA dela lê também, pelo MCP (docs/43 §5). Até ali a cantina não
tinha tool nenhuma, nem no chat. São sete, uma por pergunta que as telas
respondem:

  cantinas_e_regras       /cantina/acesso — as cantinas e a regra da casa (prazo,
                          preço, que modos aceita). Sem as CONTAS: credencial.
  calendario_da_cantina   /cantina/cardapios e /cantina/:data — que dias têm
                          cardápio, em que estado, e quantos vão comer.
  cardapio_da_cantina     /cantina/:data/:refeicao — o que tem no prato, bloco a
                          bloco, com a regra de escolha de cada bloco.
  pedidos_da_refeicao     /cantina/:data/:refeicao — o que cozinhar (contagem
                          por opção, placar do presencial) e quem vai comer.
  custos_da_cantina       /cantina/custos — o mesmo agregador da tela e do XLSX.
  direitos_a_refeicao     /cantina/direitos e o card do hub — quem pode pedir.
  restricoes_alimentares  ⚠️ dado de SAÚDE de menor: tool própria (abaixo).

Quatro regras valem para tudo aqui:

  * SÓ LEITURA, e a regra é do domínio — `cantina_leitura.py` e
    `cantina_relatorio.py`, que as rotas também chamam. Nenhuma conta é
    escrita aqui (docs/43 §4.4): o que a tool faz é escolher, recortar e dar
    nome em camelCase ao que o domínio devolve;
  * A CONTAGEM vem das tabelas de base, não das views da 0049/0052: o MCP não
    lê view (0071). É a mesma conta, e o domínio explica por que há duas
    fontes (`cantina_leitura`, cabeçalho). Por isso toda janela tem teto em
    dias — a contagem traz uma linha por pedido;
  * TODA LISTA tem `limite`, diz o `total` e se foi cortada (`truncado`). O MCP
    põe por cima um teto de 50 (app/mcp/catalogo.py);
  * NOME DE ALUNO só sai num dict com `alunoId` e `matricula` da mesma pessoa
    — é o que deixa `pedidos_da_refeicao` e `direitos_a_refeicao` passarem pelo
    portão do pseudônimo (app/mcp/pseudonimo.py). `custos_da_cantina` traz o
    nome como rótulo da soma por aluno, e `restricoes_alimentares` é dado de
    saúde: as duas só existem no MCP com o nome real
    (`catalogo.SO_COM_NOME_DO_ALUNO`).

⚠️ A RESTRIÇÃO ALIMENTAR. É a primeira informação de saúde no SAS (0049), de
adolescentes, e a LGPD a trata como dado SENSÍVEL (art. 11; art. 14 para
menores). Até 30/10 ela aparecia só para a cantina, ao lado do pedido, e na
tela de direitos sob clique — "em lugar nenhum mais", dizia o COMMENT da coluna.
A decisão da coordenação de 30/10 é que ela entra também na IA, mas numa tool
SEPARADA, `restricoes_alimentares`: assim ela pode ser desligada sozinha, pelo
METADADOS abaixo, sem tirar a cantina inteira do ar. As outras seis NUNCA a
devolvem — nem o "tem restrição" —, e o domínio nem lê a coluna para elas
(`com_restricao=False`). ⚠️ O registro é um só para o chat do app e o MCP
(chat/ferramentas.py): a tool vale nos dois.

Ficam de fora, de propósito: as contas da cantina (`usuario_cantina` — e-mail,
último acesso, hash), o token do QR de retirada (`cantina_token.py`) e qualquer
escrita (publicar, conceder direito, editar restrição). Dado de pagamento não
existe no SAS: `valor_cobrado` é o preço de tabela carimbado no pedido, para o
relatório não mudar quando o preço mudar (0054), e não cobrança.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from ... import cantina_leitura as leitura
from ... import cantina_relatorio
from ...banco.missao import FUSO_DA_ESCOLA
from ...supabase_client import ClienteDados

#: Tetos de janela, em dias. A contagem sai das tabelas de base (uma linha por
#: pedido), e é a janela que a mantém pequena.
TETO_DE_DIAS_DO_CALENDARIO = 31
TETO_DE_DIAS_DO_CARDAPIO = 7
#: O mesmo teto das exportações da cantina (routes/cantina.py,
#: `_TETO_DE_DIAS_DA_EXPORTACAO`; web/src/dominio/periodo.ts): três meses.
TETO_DE_DIAS_DE_CUSTO = 93

#: Tetos de linhas, ditos ao modelo como "até N".
TETO_DE_CANTINAS = 20
TETO_DE_CARDAPIOS_NO_CALENDARIO = 62
TETO_DE_CARDAPIOS = 28
TETO_DE_ALUNOS = 100
TETO_DE_LINHAS_DE_CUSTO = 100

_ROTULO_DA_REFEICAO = {"almoco": "almoço", "janta": "janta"}


# ─── Argumentos ──────────────────────────────────────────────────────────


def _hoje() -> date:
    """O "hoje" da escola — o mesmo fuso que decide o hoje da cantina e da
    missão do dia (routes/cantina.py, banco/missao.py)."""
    return datetime.now(FUSO_DA_ESCOLA).date()


def _data(valor: Any, campo: str) -> tuple[date | None, dict | None]:
    try:
        return date.fromisoformat(str(valor).strip()), None
    except ValueError:
        return None, {"erro": f"{campo} deve ser uma data AAAA-MM-DD (ex.: {_hoje().isoformat()})"}


def _janela(
    de: Any, ate: Any, *, padrao: Callable[[date], date], teto: int, campo_de: str = "de"
) -> tuple[date | None, date | None, dict | None]:
    """(de, ate) validados. Sem `de`, hoje; sem `ate`, `padrao(de)`. `campo_de`
    é o nome do parâmetro na tool: o erro cita o que o modelo mandou."""
    inicio, erro = _data(de, campo_de) if de else (_hoje(), None)
    if erro:
        return None, None, erro
    fim, erro = _data(ate, "ate") if ate else (padrao(inicio), None)
    if erro:
        return None, None, erro
    if fim < inicio:
        return None, None, {"erro": f"ate vem antes de {campo_de}: o fim do período é anterior ao começo"}
    if (fim - inicio).days + 1 > teto:
        return None, None, {
            "erro": f"o período vai até {teto} dias; peça um mais curto (de {inicio.isoformat()} "
            f"a {(inicio + timedelta(days=teto - 1)).isoformat()}, por exemplo)"
        }
    return inicio, fim, None


def _uuid(valor: Any, campo: str, onde_achar: str) -> tuple[str | None, dict | None]:
    """O id normalizado, ou o erro que o modelo lê. Torto, ele viraria 22P02 no
    PostgREST, e o despacho responderia "falhou do nosso lado" quando quem
    errou foi o id (o mesmo `_uuid` de tools/rotinas.py)."""
    try:
        return str(uuid.UUID(str(valor).strip())), None
    except ValueError:
        return None, {"erro": f"{campo} deve ser um UUID; {onde_achar}"}


def _teto(limite: int, teto: int) -> int:
    return min(max(1, int(limite)), teto)


def _recorte_de_cantinas(
    cliente: ClienteDados, cantina_id: str | None
) -> tuple[list[str], dict[str, str], dict | None]:
    """(ids do recorte, nome por id, erro). Sem `cantina_id`, as ATIVAS — o
    `todas=true` do card do hub (docs/40 §12.6), que é visão de topo e não pode
    esconder a segunda cantina."""
    nomes = {c["id"]: c.get("nome") for c in leitura.cantinas(cliente)}
    if cantina_id is None:
        return leitura.ids_das_cantinas_ativas(cliente), nomes, None
    cid, erro = _uuid(cantina_id, "cantina_id", "use o id que cantinas_e_regras devolve")
    if erro:
        return [], nomes, erro
    if cid not in nomes:
        return [], nomes, {"erro": "essa cantina não existe; use o id que cantinas_e_regras devolve"}
    return [cid], nomes, None


def _cortar(lista: list, limite: int) -> tuple[list, int, bool]:
    return lista[:limite], len(lista), len(lista) > limite


# ─── cantinas_e_regras ───────────────────────────────────────────────────


def cantinas_e_regras(cliente: ClienteDados, *, limite: int = TETO_DE_CANTINAS) -> dict:
    """As cantinas e a regra da casa de cada uma — sem as contas."""
    limite = _teto(limite, TETO_DE_CANTINAS)
    linhas, total, truncado = _cortar(leitura.cantinas(cliente), limite)
    cantinas = []
    for c in linhas:
        regra = {}
        for refeicao in leitura.REFEICOES:
            # A MESMA regra que pré-preenche o cardápio novo (routes/cantina.py,
            # criar_cardapio), com os defaults da 0051.
            pedido, presencial = leitura.modos_pela_regra(c, refeicao)
            regra[refeicao] = {"aceitaPedido": pedido, "aceitaPresencial": presencial}
        cantinas.append(
            {
                "id": c["id"],
                "nome": c.get("nome"),
                "ativa": bool(c.get("ativo")),
                "prazoPadrao": {
                    "diasAntes": c.get("prazo_padrao_dias_antes"),
                    "hora": str(c.get("prazo_padrao_hora") or "")[:5] or None,
                },
                "valorAlmoco": c.get("valor_almoco"),
                "valorJanta": c.get("valor_janta"),
                "modosDaCasa": regra,
            }
        )
    return {"total": total, "truncado": truncado, "cantinas": cantinas}


_SCHEMA_CANTINAS = {
    "name": "cantinas_e_regras",
    "description": (
        "Quando usar: 'quais cantinas existem?', 'até que horas dá para pedir o almoço?', "
        "'quanto custa a janta?', 'a cantina aceita retirada na hora?'. É também onde se acha "
        "o id de uma cantina para as outras tools da cantina.\n"
        "Antes de chamar, confirme: nada — sem argumento, lista todas.\n"
        "Definições: prazoPadrao = a REGRA da casa que pré-preenche cada cardápio novo "
        "(diasAntes dias antes da refeição, às hora); o prazo que vale num dia é o pedidosAte "
        "daquele cardápio, que a cantina pode mudar. valorAlmoco/valorJanta = preço de tabela "
        "em reais; null = ninguém informou, que é diferente de 0,00. O SAS não cobra nem sabe "
        "quem pagou. modosDaCasa = o que um cardápio NOVO já nasce aceitando: aceitaPedido = "
        "escolher o prato com antecedência; aceitaPresencial = retirar no balcão com QR, sem ter "
        "pedido. A resposta nunca traz as contas de acesso da cantina.\n"
        "Exemplo: cantinas_e_regras() → 'uma cantina ativa, a do Ari: pedido até 20:00 da "
        "véspera; almoço R$ 18,00; janta sem preço informado; só aceita pedido'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "limite": {
                "type": "integer",
                "default": TETO_DE_CANTINAS,
                "description": f"Quantas cantinas, até {TETO_DE_CANTINAS}.",
            },
        },
        "required": [],
    },
}


# ─── calendario_da_cantina ───────────────────────────────────────────────


def calendario_da_cantina(
    cliente: ClienteDados,
    *,
    de: str | None = None,
    ate: str | None = None,
    cantina_id: str | None = None,
    limite: int = TETO_DE_CARDAPIOS_NO_CALENDARIO,
) -> dict:
    """Que dias têm cardápio, em que estado e quantos vão comer."""
    limite = _teto(limite, TETO_DE_CARDAPIOS_NO_CALENDARIO)
    inicio, fim, erro = _janela(
        de, ate, padrao=lambda d: d + timedelta(days=6), teto=TETO_DE_DIAS_DO_CALENDARIO
    )
    if erro:
        return erro
    ids, nomes, erro = _recorte_de_cantinas(cliente, cantina_id)
    if erro:
        return erro

    linhas = leitura.calendario(
        cliente, ids, inicio, fim, contar=leitura.contar_pelos_pedidos
    )
    linhas, total, truncado = _cortar(linhas, limite)
    return {
        "de": inicio.isoformat(),
        "ate": fim.isoformat(),
        "total": total,
        "truncado": truncado,
        "cardapios": [
            {
                "cardapioId": c["id"],
                "cantinaId": c["cantinaId"],
                "cantina": nomes.get(c["cantinaId"]),
                "data": c["data"],
                "refeicao": c["refeicao"],
                "estado": c["estado"],
                "pedidosAte": c["pedidosAte"],
                "pedidos": c["pedidos"],
                "comPedido": c["comPedido"],
                "presenciais": c["presenciais"],
                "aceitaPedido": c["aceitaPedido"],
                "aceitaPresencial": c["aceitaPresencial"],
            }
            for c in linhas
        ],
    }


_DEFINICAO_DE_ESTADO = (
    "estado: rascunho = a cantina ainda não publicou, o aluno não vê; aberto = publicado e "
    "aceitando pedido até pedidosAte; fechado = o prazo passou e a contagem é final (é a que "
    "vai para o fogão); sem-refeicao = a cantina avisou que não haverá refeição (feriado, "
    "recesso). Dia sem cardápio não aparece — não é dia sem pedido."
)
_DEFINICAO_DAS_PORTAS = (
    "pedidos = quantos vão comer, as duas portas somadas; comPedido = escolheram o prato "
    "com antecedência; presenciais = declararam presença para retirar no balcão com QR, já "
    "retirados ou não. pedidos = comPedido + presenciais sempre."
)

_SCHEMA_CALENDARIO = {
    "name": "calendario_da_cantina",
    "description": (
        "Quando usar: 'a cantina já lançou o cardápio da semana?', 'quantos vão almoçar "
        "amanhã?', 'o pedido de sexta ainda está aberto?', 'quais dias do mês não terão "
        "refeição?'. É o calendário da tela da coordenação, sem o prato nem os nomes.\n"
        "Antes de chamar, confirme: o período (de/ate em AAAA-MM-DD; sem eles, de hoje até "
        f"daqui a 6 dias; até {TETO_DE_DIAS_DO_CALENDARIO} dias). Sem cantina_id, soma todas as "
        "cantinas ativas, cada cardápio com a sua.\n"
        f"Definições: {_DEFINICAO_DE_ESTADO} {_DEFINICAO_DAS_PORTAS} Para o prato, use "
        "cardapio_da_cantina; para o que cozinhar e quem vai comer, pedidos_da_refeicao.\n"
        "Exemplo: calendario_da_cantina(de='2026-11-02', ate='2026-11-06') → 'almoço lançado "
        "nos cinco dias; segunda já fechou com 41 (38 com pedido, 3 na hora); quarta é "
        "feriado'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "de": {"type": "string", "description": "Primeiro dia, AAAA-MM-DD. Sem ele, hoje."},
            "ate": {
                "type": "string",
                "description": (
                    f"Último dia, AAAA-MM-DD. Sem ele, de + 6 dias. Até "
                    f"{TETO_DE_DIAS_DO_CALENDARIO} dias de janela."
                ),
            },
            "cantina_id": {
                "type": "string",
                "description": "UUID de uma cantina (cantinas_e_regras). Sem ele, todas as ativas.",
            },
            "limite": {
                "type": "integer",
                "default": TETO_DE_CARDAPIOS_NO_CALENDARIO,
                "description": f"Quantos cardápios, até {TETO_DE_CARDAPIOS_NO_CALENDARIO}.",
            },
        },
        "required": [],
    },
}


# ─── cardapio_da_cantina ─────────────────────────────────────────────────


def cardapio_da_cantina(
    cliente: ClienteDados,
    *,
    data: str | None = None,
    ate: str | None = None,
    refeicao: str | None = None,
    cantina_id: str | None = None,
    limite: int = 14,
) -> dict:
    """O que tem no prato de um dia — ou de uma semana —, bloco a bloco."""
    limite = _teto(limite, TETO_DE_CARDAPIOS)
    inicio, fim, erro = _janela(
        data, ate, padrao=lambda d: d, teto=TETO_DE_DIAS_DO_CARDAPIO, campo_de="data"
    )
    if erro:
        return erro
    ids, nomes, erro = _recorte_de_cantinas(cliente, cantina_id)
    if erro:
        return erro

    cardapios = [
        c
        for c in leitura.cardapios_da_janela(cliente, ids, inicio, fim)
        if refeicao is None or c["refeicao"] == refeicao
    ]
    cardapios.sort(key=lambda c: (c["data"], c["refeicao"], nomes.get(c["cantina_id"]) or ""))
    cardapios, total, truncado = _cortar(cardapios, limite)
    blocos = leitura.blocos_por_cardapio(cliente, [c["id"] for c in cardapios])
    momento = leitura.agora()

    saida = []
    for c in cardapios:
        montado = leitura.montar_cardapio(cliente, c, momento, blocos=blocos.get(c["id"], []))
        saida.append(
            {
                "cardapioId": c["id"],
                "cantinaId": c["cantina_id"],
                "cantina": nomes.get(c["cantina_id"]),
                "data": c["data"],
                "refeicao": c["refeicao"],
                "estado": montado["estado"],
                "pedidosAte": c.get("pedidos_ate"),
                "aceitaPedido": montado["aceitaPedido"],
                "aceitaPresencial": montado["aceitaPresencial"],
                "blocos": [
                    {
                        "bloco": b.get("nome"),
                        "escolhasMinimas": b.get("escolhas_minimas"),
                        "escolhasMaximas": b.get("escolhas_maximas"),
                        "observacao": (b.get("observacao") or "").strip() or None,
                        "opcoes": [
                            {"opcao": o.get("nome"), "disponivel": o.get("disponivel") is not False}
                            for o in b.get("opcoes") or []
                        ],
                    }
                    for b in montado["blocos"]
                ],
            }
        )
    return {
        "de": inicio.isoformat(),
        "ate": fim.isoformat(),
        "total": total,
        "truncado": truncado,
        "cardapios": saida,
    }


_SCHEMA_CARDAPIO = {
    "name": "cardapio_da_cantina",
    "description": (
        "Quando usar: 'o que tem no almoço de hoje?', 'qual o cardápio da semana?', 'tem opção "
        "vegetariana na janta de quinta?', 'quantas guarnições o aluno pode escolher?'.\n"
        "Antes de chamar, confirme: o dia (data em AAAA-MM-DD; sem ela, hoje). Para uma semana, "
        f"data e ate (até {TETO_DE_DIAS_DO_CARDAPIO} dias). A refeição, se a pergunta for de uma "
        "só.\n"
        f"Definições: {_DEFINICAO_DE_ESTADO} bloco = um grupo do prato ('Guarnição', "
        "'Proteínas'), na ordem em que é servido. escolhasMinimas/escolhasMaximas = quantas "
        "opções do bloco o aluno marca (mínimo 0 = opcional). observacao = a regra que o número "
        "não diz ('a opção 4 anula a 1'), escrita pela cantina e NÃO vigiada pelo sistema. "
        "disponivel=false = a opção acabou. Sem contagem: quantos pediram cada opção vem de "
        "pedidos_da_refeicao.\n"
        "Exemplo: cardapio_da_cantina(data='2026-11-03', refeicao='almoco') → 'Proteínas "
        "(escolha 1): frango grelhado, omelete; Guarnição (até 2): arroz, feijão, purê'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "data": {"type": "string", "description": "O dia, AAAA-MM-DD. Sem ele, hoje."},
            "ate": {
                "type": "string",
                "description": (
                    f"Último dia, para ver mais de um (AAAA-MM-DD). Até {TETO_DE_DIAS_DO_CARDAPIO} "
                    "dias contando o primeiro."
                ),
            },
            "refeicao": {"type": "string", "enum": list(leitura.REFEICOES)},
            "cantina_id": {
                "type": "string",
                "description": "UUID de uma cantina (cantinas_e_regras). Sem ele, todas as ativas.",
            },
            "limite": {
                "type": "integer",
                "default": 14,
                "description": f"Quantos cardápios, até {TETO_DE_CARDAPIOS}.",
            },
        },
        "required": [],
    },
}


# ─── pedidos_da_refeicao ─────────────────────────────────────────────────


def pedidos_da_refeicao(
    cliente: ClienteDados,
    *,
    refeicao: str,
    data: str | None = None,
    cantina_id: str | None = None,
    limite: int = 50,
) -> dict:
    """O que cozinhar e quem vai comer numa refeição — sem a restrição alimentar."""
    limite = _teto(limite, TETO_DE_ALUNOS)
    if refeicao not in leitura.REFEICOES:
        return {"erro": f"refeicao deve ser uma de: {', '.join(leitura.REFEICOES)}"}
    dia, erro = _data(data, "data") if data else (_hoje(), None)
    if erro:
        return erro
    ids, nomes, erro = _recorte_de_cantinas(cliente, cantina_id)
    if erro:
        return erro

    cardapios = [
        c for c in leitura.cardapios_da_janela(cliente, ids, dia, dia) if c["refeicao"] == refeicao
    ]
    cardapios.sort(key=lambda c: nomes.get(c["cantina_id"]) or "")
    blocos = leitura.blocos_por_cardapio(cliente, [c["id"] for c in cardapios])
    momento = leitura.agora()

    saida = []
    for c in cardapios:
        dos_blocos = blocos.get(c["id"], [])
        montado = leitura.montar_cardapio(cliente, c, momento, blocos=dos_blocos)
        opcoes = {o["id"]: o.get("nome") for b in dos_blocos for o in b.get("opcoes") or []}
        # Sem a restrição (`com_restricao` fica no padrão, False): ela tem tool
        # própria, por decisão de 30/10. Com a matrícula, para o pseudônimo.
        alunos = leitura.pedidos_do_cardapio(
            cliente, c["id"], nomes_das_opcoes=lambda opcoes=opcoes: opcoes, com_matricula=True
        )
        portas = leitura.contar_modos(a["modo"] for a in alunos)
        alunos, total, truncado = _cortar(alunos, limite)
        saida.append(
            {
                "cardapioId": c["id"],
                "cantinaId": c["cantina_id"],
                "cantina": nomes.get(c["cantina_id"]),
                "estado": montado["estado"],
                "pedidosAte": c.get("pedidos_ate"),
                "aceitaPedido": montado["aceitaPedido"],
                "aceitaPresencial": montado["aceitaPresencial"],
                "pedidos": portas["quantos"],
                "comPedido": portas["com_pedido"],
                "presenciais": portas["presenciais"],
                "presencial": leitura.contagem_presencial(cliente, c["id"]),
                "contagem": [
                    {
                        "bloco": linha["bloco"],
                        "opcao": linha["opcao"],
                        "disponivel": linha["disponivel"] is not False,
                        "quantos": linha["quantos"],
                    }
                    for linha in leitura.contagem_por_opcao_pelos_itens(cliente, c["id"], dos_blocos)
                ],
                "totalDeAlunos": total,
                "truncado": truncado,
                "alunos": alunos,
            }
        )
    resposta: dict[str, Any] = {"data": dia.isoformat(), "refeicao": refeicao, "cardapios": saida}
    if not saida:
        resposta["aviso"] = (
            f"Nenhuma cantina lançou cardápio de {_ROTULO_DA_REFEICAO[refeicao]} para "
            f"{dia.isoformat()}."
        )
    return resposta


_SCHEMA_PEDIDOS = {
    "name": "pedidos_da_refeicao",
    "description": (
        "Quando usar: 'quantos pediram frango no almoço de hoje?', 'o que a cozinha tem de "
        "preparar amanhã?', 'quem vai jantar hoje?', 'a Ana pediu almoço?', 'quantos já "
        "retiraram na hora?'. É a tela de uma refeição da coordenação: o que cozinhar e quem vai "
        "comer.\n"
        "Antes de chamar, confirme: a refeição e o dia (data em AAAA-MM-DD; sem ela, hoje). Sem "
        "cantina_id, vem cada cantina ativa que lançou aquela refeição.\n"
        f"Definições: {_DEFINICAO_DAS_PORTAS} presencial.pendentes = declararam presença e "
        "ainda não passaram no balcão; presencial.retirados = já retiraram. contagem = quantos "
        "marcaram cada opção — só quem pediu com antecedência; quem retira na hora não escolhe "
        "prato, por isso a soma da contagem não bate com pedidos. alunos = um por pessoa, em "
        "ordem de nome: modo 'pedido' (com as escolhas) ou 'presencial' (escolhas vazias), "
        "pedidoEm e retiradoEm. A restrição alimentar NÃO vem aqui: ela tem tool própria, para "
        "quando a pergunta for sobre ela.\n"
        "Exemplo: pedidos_da_refeicao(refeicao='almoco') → 'hoje 41 vão almoçar (38 com "
        "pedido, 3 na hora, 1 já retirou); frango 25, omelete 13'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "refeicao": {"type": "string", "enum": list(leitura.REFEICOES)},
            "data": {"type": "string", "description": "O dia, AAAA-MM-DD. Sem ele, hoje."},
            "cantina_id": {
                "type": "string",
                "description": "UUID de uma cantina (cantinas_e_regras). Sem ele, todas as ativas.",
            },
            "limite": {
                "type": "integer",
                "default": 50,
                "description": (
                    f"Quantos alunos por cardápio, até {TETO_DE_ALUNOS}. A contagem e os totais "
                    "valem sempre para todos."
                ),
            },
        },
        "required": ["refeicao"],
    },
}


# ─── custos_da_cantina ───────────────────────────────────────────────────


def _fim_do_mes(dia: date) -> date:
    proximo = (dia.replace(day=28) + timedelta(days=4)).replace(day=1)
    return proximo - timedelta(days=1)


def custos_da_cantina(
    cliente: ClienteDados,
    *,
    de: str | None = None,
    ate: str | None = None,
    cantina_id: str | None = None,
    limite: int = 31,
) -> dict:
    """Quanto custou o que foi pedido no período — o agregador da tela e do XLSX."""
    limite = _teto(limite, TETO_DE_LINHAS_DE_CUSTO)
    # Sem `de`, o primeiro dia do mês — do `ate`, ou do mês corrente: a tela de
    # custos abre no mês inteiro, e só o `ate` não pode virar "hoje" como
    # começo, senão outubro perguntado em novembro daria "fim antes do começo".
    if not de:
        referencia, erro = _data(ate, "ate") if ate else (_hoje(), None)
        if erro:
            return erro
        de = referencia.replace(day=1).isoformat()
    inicio, fim, erro = _janela(de, ate, padrao=_fim_do_mes, teto=TETO_DE_DIAS_DE_CUSTO)
    if erro:
        return erro
    cid = None
    if cantina_id is not None:
        # O recorte, e não só o formato: um uuid que não é de cantina nenhuma
        # somava zero, e a IA diria que a cantina não custou nada.
        ids, _, erro = _recorte_de_cantinas(cliente, cantina_id)
        if erro:
            return erro
        cid = ids[0]

    # O MESMO agregador da tela e da planilha (docs/40 §12.11.4): a soma é de
    # `valor_cobrado`, o preço carimbado no pedido (0054), não o de hoje.
    agregado = cantina_relatorio.agregados(cliente, de=inicio, ate=fim, cantina_id=cid)

    saida: dict[str, Any] = {
        "de": agregado["de"],
        "ate": agregado["ate"],
        "refeicoes": agregado["refeicoes"],
        "total": agregado["total"],
        "semValor": agregado["semValor"],
    }
    totais, truncados = {}, {}
    for recorte in ("porDia", "porTurma", "porAluno", "porCantina"):
        linhas = list(agregado[recorte])
        if recorte != "porDia":
            # Os maiores primeiro, para o corte guardar o que mais pesa. O dia
            # fica em ordem de calendário, como o domínio o devolve.
            linhas.sort(key=lambda linha: (-linha["total"], -linha["refeicoes"], linha["rotulo"]))
        saida[recorte], totais[recorte], truncados[recorte] = _cortar(linhas, limite)
    saida["linhas"] = totais
    saida["truncado"] = truncados
    return saida


_SCHEMA_CUSTOS = {
    "name": "custos_da_cantina",
    "description": (
        "Quando usar: 'quanto a cantina custou em outubro?', 'qual turma gastou mais?', 'qual o "
        "custo da semana?', 'quantos pedidos ficaram sem preço?'. É a tela de custos: os mesmos "
        "números da tela e da planilha.\n"
        "Antes de chamar, confirme: o período (de/ate em AAAA-MM-DD; sem os dois, o mês corrente "
        f"inteiro; só um deles, o mês daquele dia; até {TETO_DE_DIAS_DE_CUSTO} dias).\n"
        "Definições: refeicoes = quantos pedidos no período, as duas portas (pedido e retirada "
        "na hora). total = soma, em reais, do preço CARIMBADO em cada pedido no momento em que "
        "foi feito — não o preço de hoje. semValor = pedidos sem preço registrado, que entram "
        "como zero no total: diga quantos são. porDia (em ordem de data), porTurma, porAluno e "
        "porCantina (os maiores primeiro) trazem rotulo, refeicoes e total; linhas = quantas "
        "linhas cada recorte tem, e truncado diz qual foi cortado. Isto não é cobrança: o SAS "
        "não fatura nem sabe quem pagou.\n"
        "Exemplo: custos_da_cantina(de='2026-10-01', ate='2026-10-31') → 'outubro: 812 "
        "refeições, R$ 14.616,00; 3o ITA AD foi a turma de maior custo; 12 pedidos sem valor'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "de": {"type": "string", "description": "Primeiro dia, AAAA-MM-DD."},
            "ate": {"type": "string", "description": "Último dia, AAAA-MM-DD."},
            "cantina_id": {
                "type": "string",
                "description": "UUID de uma cantina (cantinas_e_regras). Sem ele, todas.",
            },
            "limite": {
                "type": "integer",
                "default": 31,
                "description": f"Quantas linhas em cada recorte, até {TETO_DE_LINHAS_DE_CUSTO}.",
            },
        },
        "required": [],
    },
}


# ─── direitos_a_refeicao ─────────────────────────────────────────────────

SITUACOES = ("com_direito", "sem_direito", "todos")


def direitos_a_refeicao(
    cliente: ClienteDados,
    *,
    situacao: str = "com_direito",
    refeicao: str | None = None,
    limite: int = 50,
) -> dict:
    """Quem pode pedir almoço e janta — sem a restrição alimentar."""
    limite = _teto(limite, TETO_DE_ALUNOS)
    if situacao not in SITUACOES:
        return {"erro": f"situacao deve ser uma de: {', '.join(SITUACOES)}"}
    if refeicao is not None and refeicao not in leitura.REFEICOES:
        return {"erro": f"refeicao deve ser uma de: {', '.join(leitura.REFEICOES)}"}

    # Sem `com_restricao`: a coluna nem é lida (decisão de 30/10).
    lista = leitura.alunos_e_direitos(cliente)["alunos"]

    def tem(aluno: dict) -> bool:
        return refeicao in aluno["direitos"] if refeicao else bool(aluno["direitos"])

    if situacao == "com_direito":
        lista = [a for a in lista if tem(a)]
    elif situacao == "sem_direito":
        lista = [a for a in lista if not tem(a)]
    alunos, total, truncado = _cortar(lista, limite)
    return {
        "resumo": leitura.resumo_dos_direitos(cliente),
        "situacao": situacao,
        "refeicao": refeicao,
        "total": total,
        "truncado": truncado,
        "alunos": [
            {
                "alunoId": a["id"],
                "matricula": a.get("matricula"),
                "nome": a.get("nome"),
                "turma": a.get("turma"),
                "direitos": a["direitos"],
            }
            for a in alunos
        ],
    }


_SCHEMA_DIREITOS = {
    "name": "direitos_a_refeicao",
    "description": (
        "Quando usar: 'quantos alunos têm direito a almoço?', 'quem pode jantar na escola?', "
        "'a Ana tem direito à janta?', 'quem ainda não tem direito nenhum?'. É a tela de "
        "direitos da coordenação e o card do hub.\n"
        "Antes de chamar, confirme: situacao (com_direito, o padrão; sem_direito; todos) e, se a "
        "pergunta for de uma refeição só, refeicao — aí com/sem direito vale para ela.\n"
        "Definições: direito = o aluno pode pedir aquela refeição; quem concede é o "
        "administrador. resumo = o card do hub: ativos (alunos ativos), comDireito (alunos "
        "distintos com algum direito), almoco e janta (quantos direitos de cada). alunos = só os "
        "ativos, em ordem de nome, com a turma de hoje. A restrição alimentar NÃO vem aqui: ela "
        "tem tool própria, para quando a pergunta for sobre ela.\n"
        "Exemplo: direitos_a_refeicao(refeicao='janta') → '87 dos 905 alunos ativos podem "
        "jantar; 12 deles são do 3o ITA ON'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "situacao": {"type": "string", "enum": list(SITUACOES), "default": "com_direito"},
            "refeicao": {"type": "string", "enum": list(leitura.REFEICOES)},
            "limite": {
                "type": "integer",
                "default": 50,
                "description": f"Quantos alunos, até {TETO_DE_ALUNOS}. O resumo vale para todos.",
            },
        },
        "required": [],
    },
}


# ─── restricoes_alimentares ──────────────────────────────────────────────
#
# ⚠️ DADO DE SAÚDE DE MENOR (LGPD art. 11, e art. 14 para criança e
# adolescente). Entrou na IA por decisão da coordenação de 30/10/2026, e SÓ
# por esta tool — separada das outras para poder ser desligada sozinha, pelo
# METADADOS no fim do arquivo, sem tirar a cantina do ar. Nenhuma outra tool
# devolve a restrição, nem o "tem restrição". No MCP ela só existe com o nome
# real (`catalogo.SO_COM_NOME_DO_ALUNO`): com o pseudônimo ligado, "Aluno
# <matrícula>" ao lado de um dado de saúde continuaria sendo dado pessoal
# sensível (art. 5º, I e II), e o modo conservador não o manda.


def restricoes_alimentares(
    cliente: ClienteDados,
    *,
    aluno_id: str | None = None,
    data: str | None = None,
    refeicao: str | None = None,
    limite: int = 50,
) -> dict:
    """Quem tem restrição alimentar registrada, e qual — só quando perguntado."""
    limite = _teto(limite, TETO_DE_ALUNOS)
    if (data is None) != (refeicao is None):
        return {"erro": "data e refeicao vêm juntas: as duas dizem de que refeição se fala"}
    if refeicao is not None and refeicao not in leitura.REFEICOES:
        return {"erro": f"refeicao deve ser uma de: {', '.join(leitura.REFEICOES)}"}
    aid = None
    if aluno_id is not None:
        aid, erro = _uuid(aluno_id, "aluno_id", "ache o aluno por buscar_aluno_por_nome ou buscar_aluno_por_matricula")
        if erro:
            return erro
    dia = None
    if data is not None:
        dia, erro = _data(data, "data")
        if erro:
            return erro

    # A lista da tela de direitos, COM a restrição (é ela que a tela revela
    # sob clique), e o mesmo "tem restrição" da planilha de direitos.
    lista = [
        a
        for a in leitura.alunos_e_direitos(cliente, com_restricao=True)["alunos"]
        if leitura.tem_restricao(a.get("restricaoAlimentar"))
    ]
    if aid is not None:
        lista = [a for a in lista if a["id"] == aid]
    if dia is not None:
        vao_comer = leitura.alunos_que_vao_comer(cliente, dia, refeicao)
        lista = [a for a in lista if a["id"] in vao_comer]
    alunos, total, truncado = _cortar(lista, limite)
    return {
        "cuidado": (
            "Restrição alimentar é dado de saúde de adolescente (LGPD art. 11): responda só ao "
            "que foi perguntado e não a repita fora do assunto."
        ),
        "data": dia.isoformat() if dia else None,
        "refeicao": refeicao,
        "total": total,
        "truncado": truncado,
        "alunos": [
            {
                "alunoId": a["id"],
                "matricula": a.get("matricula"),
                "nome": a.get("nome"),
                "turma": a.get("turma"),
                "direitos": a["direitos"],
                "restricaoAlimentar": a["restricaoAlimentar"].strip(),
            }
            for a in alunos
        ],
    }


_SCHEMA_RESTRICOES = {
    "name": "restricoes_alimentares",
    "description": (
        "⚠️ Dado SENSÍVEL: restrição alimentar é informação de saúde de aluno menor de idade "
        "(LGPD art. 11). Use SÓ quando a pergunta for sobre restrição, alergia ou intolerância "
        "alimentar — nunca para enriquecer outra resposta.\n"
        "Quando usar: 'quem tem restrição alimentar?', 'quem do almoço de hoje tem alergia?', "
        "'a Ana tem alguma restrição registrada?'.\n"
        "Antes de chamar, confirme: o recorte — um aluno (aluno_id), uma refeição (data e "
        "refeicao, juntas: só quem vai comer nela) ou todos os ativos.\n"
        "Definições: restricaoAlimentar = o texto que a coordenação registrou, cite como está; "
        "quem não tem texto não aparece (não ter registro não prova que não tenha restrição). "
        "direitos = as refeições a que o aluno tem direito.\n"
        "Exemplo: restricoes_alimentares(data='2026-11-03', refeicao='almoco') → '2 dos que "
        "almoçam amanhã têm restrição registrada: Ana Souza (sem lactose) e Pedro Lima (alergia "
        "a amendoim)'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "aluno_id": {
                "type": "string",
                "description": "UUID de um aluno (buscar_aluno_por_nome ou buscar_aluno_por_matricula).",
            },
            "data": {
                "type": "string",
                "description": "Dia da refeição, AAAA-MM-DD — junto com refeicao.",
            },
            "refeicao": {"type": "string", "enum": list(leitura.REFEICOES)},
            "limite": {
                "type": "integer",
                "default": 50,
                "description": f"Quantos alunos, até {TETO_DE_ALUNOS}.",
            },
        },
        "required": [],
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_CANTINAS, cantinas_e_regras),
    (_SCHEMA_CALENDARIO, calendario_da_cantina),
    (_SCHEMA_CARDAPIO, cardapio_da_cantina),
    (_SCHEMA_PEDIDOS, pedidos_da_refeicao),
    (_SCHEMA_CUSTOS, custos_da_cantina),
    (_SCHEMA_DIREITOS, direitos_a_refeicao),
    (_SCHEMA_RESTRICOES, restricoes_alimentares),
]

#: As sete no MCP, pela decisão da coordenação de 30/10 (docs/43 §5). A
#: restrição alimentar é dado de saúde de menor (LGPD art. 11) e tem linha
#: própria de propósito: `False` aqui a tira do MCP sem mexer nas outras.
METADADOS: dict[str, dict] = {
    "cantinas_e_regras": {"expor_no_mcp": True},
    "calendario_da_cantina": {"expor_no_mcp": True},
    "cardapio_da_cantina": {"expor_no_mcp": True},
    "pedidos_da_refeicao": {"expor_no_mcp": True},
    "custos_da_cantina": {"expor_no_mcp": True},
    "direitos_a_refeicao": {"expor_no_mcp": True},
    "restricoes_alimentares": {"expor_no_mcp": True},
}
