"""As leituras da captação externa que a tela e o assistente dividem (docs/41).

Nasceram em `routes/captacao.py` e desceram para cá em 30/10/2026, quando a
coordenação decidiu que a IA lê pelo MCP tudo o que o coordenador lê na
plataforma — a captação inclusive, que o docs/43 §6 deixava fora. A rota
deixou de ser a única porta: `chat/tools/captacao.py` monta os mesmos filtros e
não pode ter uma cópia da régua (docs/43 §4.4, o padrão de
`banco/consultas.validar_filtros`). O que vale para as duas, por isso, mora
aqui: o vocabulário dos filtros, o público relativo ao ano de ingresso, a
escolha entre a lista por nome e a busca por conquista, e a busca pelo nome
com os curingas do LIKE lidos como letras.

As COLUNAS são de quem chama. A rota pede o perfil inteiro, como antes; as
tools pedem menos — sem `observacoes`, o texto livre do funil, que é onde
alguém anota o telefone do responsável, e sem o bastidor da raspagem
(`raspado_em`, `nome_informado`) —, e o GRANT do `sas_mcp` (migration 0076) é
exatamente o que elas pedem. Com GRANT por coluna, pedir uma coluna a mais
pelo PostgREST do MCP é 42501, e não vazamento (falha fechada, 0071).

Funções síncronas: o cliente PostgREST é síncrono, e a rota as chama de um
handler `def` (api/CLAUDE.md, convenção de 29/09/2026).

⚠️ `candidato_externo` não é `aluno` — ver o `__init__` deste pacote.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from supabase import Client

from scripts._captacao_comum import FAIXAS, normalizar_nome

# Mesmo vocabulário do CHECK de `candidato_externo.status_captacao` (0056) —
# duplicado aqui de propósito, como `PAPEIS_DE_COORDENACAO` em auth.py: é o que
# permite recusar um valor errado com uma frase em vez de estourar 23514 do
# Postgres por trás do PostgREST.
STATUS_CAPTACAO = ("novo", "contatado", "interessado", "matriculado", "descartado")

# Público da captação (decisão de 07/10/2026): Fundamental 2, Médio e
# Pré-vestibular. A tradução pra ano de conclusão mora na função da 0068.
PUBLICOS = ("fundamental", "medio", "pre_vestibular")

#: Os mesmos limites que a rota declarava no `Query(ge=…, le=…)`: ano da
#: conquista e ano letivo de referência. Guarda contra lixo, não regra de
#: acervo — a OBMEP vai a 2016, a fonte mais antiga.
ANO_DA_CONQUISTA = (1990, 2100)
ANO_DE_INGRESSO = (2000, 2100)

# Mesmo fuso de `banco/missao.py` — a "virada do ano" é a do colégio.
_FUSO_DA_ESCOLA = ZoneInfo("America/Fortaleza")

#: Um nome_normalizado por linha — a lista geral (v_candidato_externo_por_nome,
#: 0063/0068). Sem `id`: a linha não representa um candidato_externo, é o nome
#: inteiro. escolas/cidades/ufs/status_captacao são CONJUNTOS (arrays
#: independentes, não pareados entre si — ver comentário da 0063). É também o
#: que a função da busca por conquista devolve, então serve aos dois caminhos.
COLUNAS_POR_NOME = (
    "nome_normalizado, nome, escolas, cidades, ufs, status_captacao, "
    "conquistas_total, provas_distintas, participacoes, perfis_no_grupo, ano_mais_recente, "
    "criado_em, atualizado_em"
)

#: O perfil como a TELA o lê (`CaptacaoPerfil.tsx`): um candidato_externo por
#: linha, com o funil manual inteiro.
COLUNAS_CANDIDATO = (
    "id, nome, nome_normalizado, escola, cidade, uf, serie_referencia_min, serie_referencia_max, "
    "ano_referencia_serie, status_captacao, observacoes, criado_em, atualizado_em"
)

#: A conquista como a TELA a lê. `prova_id` é obrigatório em qualquer seleção
#: passada a `perfis_do_nome`: é por ele que a prova ganha nome e categoria.
COLUNAS_CONQUISTA = (
    "id, prova_id, ano, nivel_texto, serie_referencia_min, serie_referencia_max, "
    "resultado, nome_informado, escola_informada, cidade_informada, uf_informada, "
    "fonte_url, raspado_em, notas_por_materia"
)


class FiltroInvalido(ValueError):
    """O filtro pedido não existe no vocabulário. A mensagem sai pronta para
    quem pediu: o 400 da rota, o `{"erro": ...}` da tool."""


def ano_ingresso_padrao() -> int:
    """Captação é pra turma do ANO QUE VEM — em outubro ninguém mais entra na
    turma deste ano. O público é calculado pra esse ano (docs/41 §20)."""
    return datetime.now(_FUSO_DA_ESCOLA).year + 1


def literal_no_like(termo: str) -> str:
    """`chat.tools.lookup.literal_no_like` — a mesma, e não uma cópia.

    Import tardio de propósito: `app.chat.tools` importa todas as tools no
    `__init__`, inclusive a da captação, que importa este módulo — no topo, a
    rota que chegasse aqui primeiro acharia o pacote pela metade."""
    from ..chat.tools.lookup import literal_no_like as _literal

    return _literal(termo)


def termo_de_busca(busca: str | None) -> str:
    """O trecho de nome como padrão de LIKE: normalizado e com os curingas
    lidos como letras.

    Normalizado do mesmo jeito que `nome_normalizado` (0056): quem digita
    "Goncalves" acha "Gonçalves" (docs/41 §20). E escapado com
    `literal_no_like`: até 30/10 a rota TIRAVA `%` e `_` mas deixava a barra
    invertida, que é o ESCAPE do LIKE, e o `*`, que o PostgREST troca por `%`
    — `busca='a*o'` casava com qualquer nome que tivesse um A antes de um O (a
    mesma classe de buraco que o docs/43 anotou em `buscar_aluno_por_nome`). O
    `*` sai antes, como lá: nome não tem `*`, e escapado ele continuaria
    curinga para o PostgREST. Vale para os dois caminhos — o `ilike` da lista e
    o `LIKE` da função da 0068, cujo ESCAPE padrão é a mesma barra invertida."""
    if not busca:
        return ""
    termo = normalizar_nome(busca.replace("*", ""))
    return literal_no_like(termo) if termo else ""


def _no_intervalo(nome: str, valor: int | None, intervalo: tuple[int, int]) -> None:
    if valor is not None and not intervalo[0] <= valor <= intervalo[1]:
        raise FiltroInvalido(f"{nome} deve estar entre {intervalo[0]} e {intervalo[1]}")


def _no_vocabulario(nome: str, valores: list[str] | None, vocabulario: tuple[str, ...]) -> None:
    desconhecidos = [v for v in valores or [] if v not in vocabulario]
    if desconhecidos:
        raise FiltroInvalido(f"{nome} deve ser um de {vocabulario}")


def validar_filtros(
    *,
    status_captacao: str | None = None,
    faixa: list[str] | None = None,
    publico: list[str] | None = None,
    conquistas_min: int | None = None,
    ano_min: int | None = None,
    ano_max: int | None = None,
    ano_ingresso: int | None = None,
) -> None:
    """Recusa o filtro que não casaria com nada em silêncio (ou um 23514 do
    Postgres por trás do PostgREST). `listar_candidatos` a chama antes de ler."""
    if status_captacao is not None and status_captacao not in STATUS_CAPTACAO:
        raise FiltroInvalido(f"status_captacao deve ser um de {STATUS_CAPTACAO}")
    _no_vocabulario("faixa", faixa, FAIXAS)
    _no_vocabulario("publico", publico, PUBLICOS)
    if conquistas_min is not None and conquistas_min < 1:
        raise FiltroInvalido("conquistas_min deve ser 1 ou mais")
    _no_intervalo("ano_min", ano_min, ANO_DA_CONQUISTA)
    _no_intervalo("ano_max", ano_max, ANO_DA_CONQUISTA)
    _no_intervalo("ano_ingresso", ano_ingresso, ANO_DE_INGRESSO)


def tem_criterio_de_conquista(
    *,
    prova: list[str] | None = None,
    faixa: list[str] | None = None,
    ano_min: int | None = None,
    ano_max: int | None = None,
    publico: list[str] | None = None,
) -> bool:
    """Algum critério que vale para UMA conquista (docs/41 §20) — é ele que
    troca a lista por nome pela função da 0068."""
    return bool(prova or faixa or ano_min is not None or ano_max is not None or publico)


def listar_candidatos(
    cliente: Client,
    *,
    uf: str | None = None,
    status_captacao: str | None = None,
    conquistas_min: int | None = None,
    busca: str | None = None,
    prova: list[str] | None = None,
    faixa: list[str] | None = None,
    ano_min: int | None = None,
    ano_max: int | None = None,
    publico: list[str] | None = None,
    ano_ingresso: int | None = None,
    limite: int = 20,
    deslocamento: int = 0,
) -> dict[str, Any]:
    """Uma página de NOMES (não de candidato_externo): `{candidatos, total,
    ano_ingresso}`. Cada nome vira UMA linha sempre, mesmo quando por baixo tem
    vários `candidato_externo` ainda não arrumados à mão (`perfis_no_grupo`
    diz quantos) — quem está caçando lead não devia ver a fragmentação interna
    do resolver.

    Dois caminhos, a mesma resposta:
    - **sem critério de conquista**: a view por nome, de quem mais cruzou
      conquista pra quem menos — participação (1ª fase do ITA) não conta
      (0068);
    - **com prova/faixa/ano/público**: a função `buscar_candidatos_por_conquista`
      (0068), que exige que UMA MESMA conquista case todos esses critérios e
      devolve, em `evidencias`, as que fizeram o nome entrar.

    Levanta `FiltroInvalido` com o vocabulário errado.
    """
    validar_filtros(
        status_captacao=status_captacao, faixa=faixa, publico=publico,
        conquistas_min=conquistas_min, ano_min=ano_min, ano_max=ano_max, ano_ingresso=ano_ingresso,
    )
    termo = termo_de_busca(busca)
    ingresso = ano_ingresso or ano_ingresso_padrao()
    uf_normalizada = uf.strip().upper() if uf and uf.strip() else None

    if tem_criterio_de_conquista(prova=prova, faixa=faixa, ano_min=ano_min, ano_max=ano_max, publico=publico):
        linhas = (
            cliente.rpc(
                "buscar_candidatos_por_conquista",
                {
                    "p_provas": prova or None,
                    "p_faixas": faixa or None,
                    "p_ano_min": ano_min,
                    "p_ano_max": ano_max,
                    "p_publicos": publico or None,
                    "p_ano_ingresso": ingresso,
                    "p_uf": uf_normalizada,
                    "p_status": status_captacao,
                    "p_conquistas_min": conquistas_min,
                    "p_busca": termo or None,
                    "p_limite": limite,
                    "p_deslocamento": deslocamento,
                },
            )
            .execute()
            .data
            or []
        )
        # O total vem repetido em toda linha (window antes do LIMIT, 0068) —
        # sai daqui pra não viajar 20 vezes pro front.
        total = int(linhas[0]["total_filtrado"]) if linhas else 0
        for linha in linhas:
            linha.pop("total_filtrado", None)
        return {"candidatos": linhas, "total": total, "ano_ingresso": ingresso}

    consulta = cliente.table("v_candidato_externo_por_nome").select(COLUNAS_POR_NOME, count="exact")
    if uf_normalizada:
        # .contains() -> `ufs=cs.{CE}` -> operador @> do Postgres (índice
        # GIN, migration 0063) — bate se a UF estiver em QUALQUER conquista
        # do nome, não só numa escolhida por heurística.
        consulta = consulta.contains("ufs", [uf_normalizada])
    if status_captacao:
        consulta = consulta.contains("status_captacao", [status_captacao])
    if conquistas_min is not None:
        consulta = consulta.gte("conquistas_total", conquistas_min)
    if termo:
        consulta = consulta.ilike("nome_normalizado", f"%{termo}%")

    # nome_normalizado no fim do `order`: é a chave única da linha (a view
    # agrupa por ele), então basta como critério de desempate total.
    resposta = (
        consulta.order("conquistas_total", desc=True)
        .order("nome_normalizado")
        .range(deslocamento, deslocamento + limite - 1)
        .execute()
    )
    linhas = resposta.data or []
    total = int(resposta.count) if resposta.count is not None else len(linhas)
    return {"candidatos": linhas, "total": total, "ano_ingresso": ingresso}


def listar_provas(cliente: Client) -> list[dict[str, Any]]:
    """Uma linha por prova (ITA, IME, OBMEP...) com o intervalo de anos
    carregado — o rodapé "quais fontes alimentam esta lista" de
    `Captacao.tsx`. 10 linhas hoje, sem paginação.

    `v_prova_externa_resumo` é SECURITY INVOKER desde a 0076: lê com o
    privilégio de quem chama, então o sas_mcp a lê só porque lê as colunas de
    `prova_externa` e `conquista_externa` que ela agrega."""
    return (
        cliente.table("v_prova_externa_resumo")
        .select("nome, categoria, ano_min, ano_max, conquistas_total")
        .order("categoria")
        .order("nome")
        .execute()
        .data
        or []
    )


def perfis_do_nome(
    cliente: Client,
    nome_normalizado: str,
    *,
    colunas_candidato: str = COLUNAS_CANDIDATO,
    colunas_conquista: str = COLUNAS_CONQUISTA,
) -> list[dict[str, Any]]:
    """Todo `candidato_externo` com este nome, cada um com as próprias
    conquistas (da mais recente pra mais antiga) e o resumo delas — a ficha de
    QUALQUER nome (docs/41 §16: a maioria tem exatamente 1 perfil). Lista
    vazia quando o nome não existe.

    Lê `candidato_externo`, e não a view `v_candidato_externo` (0058/0064),
    desde 30/10: a view roda com o privilégio do dono e pede `observacoes`, e
    nenhum GRANT por coluna nela deixaria o MCP de fora do texto livre. O
    resumo que a view somava — `conquistas_total`, `provas_distintas`,
    `ano_mais_recente` — sai das MESMAS conquistas que esta função já lê, com
    a mesma conta (todas as linhas, participação inclusive: é a régua de um
    perfil, ao contrário da lista por nome, docs/41 §20.2).

    `colunas_conquista` precisa de `prova_id`; `candidato_id` entra sempre.
    """
    candidatos = (
        cliente.table("candidato_externo")
        .select(colunas_candidato)
        .eq("nome_normalizado", nome_normalizado)
        .order("criado_em")
        .execute()
        .data
        or []
    )
    if not candidatos:
        return []

    conquistas = (
        cliente.table("conquista_externa")
        .select(f"candidato_id, {colunas_conquista}")
        .in_("candidato_id", [c["id"] for c in candidatos])
        .order("ano", desc=True)
        .execute()
        .data
        or []
    )
    # Nome e categoria da prova, resolvidos em Python — a mesma junção manual
    # de `banco/consultas.py::montar_questoes`, e pelo mesmo motivo: o projeto
    # não usa embedding do PostgREST, só `.table()` + merge (api/CLAUDE.md).
    ids_das_provas = list({c["prova_id"] for c in conquistas})
    provas = (
        cliente.table("prova_externa").select("id, nome, categoria").in_("id", ids_das_provas).execute().data
        if ids_das_provas
        else []
    )
    prova_por_id = {p["id"]: p for p in provas or []}
    por_candidato: dict[str, list[dict[str, Any]]] = {c["id"]: [] for c in candidatos}
    for c in conquistas:
        prova = prova_por_id.get(c["prova_id"]) or {}
        c["prova_nome"] = prova.get("nome")
        c["prova_categoria"] = prova.get("categoria")
        por_candidato.setdefault(c["candidato_id"], []).append(c)

    for candidato in candidatos:
        proprias = por_candidato.get(candidato["id"], [])
        candidato["conquistas"] = proprias
        candidato["conquistas_total"] = len(proprias)
        candidato["provas_distintas"] = len({c["prova_id"] for c in proprias})
        candidato["ano_mais_recente"] = max((c["ano"] for c in proprias), default=None)
    return candidatos
