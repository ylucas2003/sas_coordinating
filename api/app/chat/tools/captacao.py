"""Tools da captação externa — candidatos de FORA do colégio (docs/41; docs/43 §5).

Entraram em 30/10/2026, quando a coordenação decidiu que a IA lê pelo MCP
tudo o que o coordenador lê na plataforma. Até ali a captação ficava fora de
propósito (docs/43 §6), e não havia tool dela nem no chat do app.

A captação é gente que NUNCA se cadastrou no SAS — muitos são menores —,
achada em resultado público de olimpíada, vestibular e concurso. Não tem nada
a ver com `aluno` (migration 0056), e o erro de leitura mais provável é o
modelo misturar as duas populações: toda descrição daqui o diz com todas as
letras.

Quatro portas, as mesmas das telas de /administracao/captacao:

  buscar_candidatos_externos       nome e filtros do nome → os nomes (a lista)
  buscar_candidatos_por_conquista  conquista → os nomes (o caminho inverso, docs/41 §20)
  perfil_do_candidato_externo      um nome → os perfis e as conquistas (a ficha)
  provas_da_captacao               as provas e os anos carregados (o rodapé da lista)

Nada aqui é regra nova. O vocabulário dos filtros, o público pelo ano de
ingresso, a escolha entre a lista por nome e a busca por conquista e a busca
pelo nome com os curingas escapados são `captacao/consultas`, a mesma que a
rota chama. A tool escolhe campos e corta a SAÍDA; o resumo de cada perfil
sai da leitura inteira.

O que NÃO sai, nem no chat nem no MCP — e por isso nem é pedido ao PostgREST
(o GRANT da 0076 é exatamente o que estas tools pedem):
  * `observacoes`: texto livre do funil, escrito pela coordenação — é onde
    alguém anota o telefone do responsável ou o que ouviu da família. O SAS
    não tem coluna de contato; o texto livre é o único lugar onde ele
    apareceria;
  * o bastidor da raspagem que a tela não mostra: `nome_informado`,
    `raspado_em`, e a trava `retrato_editado_a_mao`.

No MCP, as quatro vão (decisão de 30/10). As três que devolvem nome de
pessoa estão em `app.mcp.catalogo.SO_COM_NOME_DO_ALUNO`: com o pseudônimo
ligado elas saem do catálogo, porque devolver o nome de um adolescente de
fora contrariaria a mesma opção que esconde o de dentro — e o nome é o
próprio objeto delas, não há o que trocar por matrícula.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from typing import Any

from supabase import Client

from scripts._captacao_comum import FAIXAS, FAIXAS_OLIMPIADA, FAIXAS_VESTIBULAR, normalizar_nome

from ...captacao import consultas

#: Tetos da SAÍDA. O despacho não confere `maximum` (ferramentas.py): quem
#: limita é o handler. A lista é navegação sobre mais de 100 mil nomes; o
#: modelo estreita o filtro em vez de paginar — paginar devolveria, chamada a
#: chamada, a base inteira de gente de fora (minimização, LGPD art. 6º, III).
TETO_DE_CANDIDATOS = 50
TETO_DE_CONQUISTAS = 50

#: Escolas e cidades de um nome são um CONJUNTO de todas as conquistas dele
#: (0063): num nome comum, com homônimos ainda num perfil só, passam de vinte.
#: Corte da saída, com quantos ficaram de fora.
LIMITE_DE_LOCAIS = 6

#: O perfil como a IA o lê: o que a ficha mostra, sem o funil escrito à mão.
#: `criado_em` vai só porque `consultas.perfis_do_nome` ordena por ele.
COLUNAS_CANDIDATO = (
    "id, nome, nome_normalizado, escola, cidade, uf, serie_referencia_min, serie_referencia_max, "
    "ano_referencia_serie, status_captacao, criado_em"
)
#: A conquista como a ficha de leitura a mostra (`CaptacaoConquistas.tsx`),
#: mais a `faixa` — a tradução comparável de `resultado` que a busca por
#: conquista usa (0068). `prova_id` é o elo com a prova.
COLUNAS_CONQUISTA = (
    "id, prova_id, ano, nivel_texto, resultado, faixa, escola_informada, cidade_informada, "
    "uf_informada, notas_por_materia, fonte_url"
)

_QUEM_SAO = (
    "⚠️ São candidatos EXTERNOS: gente de FORA do colégio, achada em resultado público de "
    "olimpíada, vestibular e concurso — NÃO são alunos do SAS. Não cruze com as tools de "
    "aluno: um nome igual não é a mesma pessoa. Muitos são menores de idade e nunca se "
    "cadastraram aqui; o SAS não guarda contato deles. Use o que vier só para responder ao "
    "que foi perguntado."
)
_FAIXAS_NO_TEXTO = (
    f"faixa = o que a conquista vale, comparável entre provas: {', '.join(FAIXAS_OLIMPIADA)} "
    f"(olimpíada) ou {', '.join(FAIXAS_VESTIBULAR)} (vestibular); 'classificado_final' é "
    "quem passou em tudo sem vaga confirmada."
)
_STATUS_NO_TEXTO = (
    "status = o funil manual da coordenação (novo → contatado → interessado → matriculado, "
    "ou descartado)."
)


def _sem_acento(texto: str) -> str:
    """Para achar 'obmep' em 'OBMEP' e 'escola naval' em 'Escola Naval'. É
    leitura do pedido, não regra de negócio."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return " ".join("".join(c for c in decomposto if not unicodedata.combining(c)).casefold().split())


def _locais(nome: str, valores: list[str] | None) -> dict[str, Any]:
    valores = list(valores or [])
    saida: dict[str, Any] = {nome: valores[:LIMITE_DE_LOCAIS]}
    if len(valores) > LIMITE_DE_LOCAIS:
        saida[f"{nome}AMais"] = len(valores) - LIMITE_DE_LOCAIS
    return saida


def _linha_do_nome(linha: dict[str, Any]) -> dict[str, Any]:
    """Uma linha da lista: um NOME, com o conjunto do que as conquistas dele
    dizem. `perfis` > 1 = homônimos já separados à mão na ficha."""
    saida: dict[str, Any] = {
        "nome": linha.get("nome"),
        "nomeNormalizado": linha.get("nome_normalizado"),
        **_locais("escolas", linha.get("escolas")),
        **_locais("cidades", linha.get("cidades")),
        "ufs": linha.get("ufs") or [],
        "status": linha.get("status_captacao") or [],
        "conquistasTotal": linha.get("conquistas_total"),
        "provasDistintas": linha.get("provas_distintas"),
        "participacoes": linha.get("participacoes"),
        "perfis": linha.get("perfis_no_grupo"),
        "anoMaisRecente": linha.get("ano_mais_recente"),
        "atualizadoEm": str(linha.get("atualizado_em") or "")[:10] or None,
    }
    if "evidencias" in linha:
        saida["conquistasCasadas"] = linha.get("conquistas_casadas")
        saida["evidencias"] = linha.get("evidencias") or []
    return saida


def _lista(pagina: dict[str, Any]) -> dict[str, Any]:
    linhas = [_linha_do_nome(linha) for linha in pagina["candidatos"]]
    return {
        "total": pagina["total"],
        "mostrados": len(linhas),
        "truncado": pagina["total"] > len(linhas),
        "candidatos": linhas,
    }


def _limite(limite: int, teto: int) -> int:
    return min(max(1, limite), teto)


# ─── buscar_candidatos_externos ──────────────────────────────────────────


def buscar_candidatos_externos(
    cliente: Client,
    *,
    nome: str | None = None,
    uf: str | None = None,
    status_captacao: str | None = None,
    conquistas_min: int | None = None,
    limite: int = 20,
) -> dict:
    """A lista de /administracao/captacao: um nome por linha, de quem mais
    cruzou conquista para quem menos (`consultas.listar_candidatos`, sem
    critério de conquista)."""
    limite = _limite(limite, TETO_DE_CANDIDATOS)
    try:
        pagina = consultas.listar_candidatos(
            cliente, busca=nome, uf=uf, status_captacao=status_captacao,
            conquistas_min=conquistas_min, limite=limite,
        )
    except consultas.FiltroInvalido as exc:
        return {"erro": str(exc)}
    return _lista(pagina)


_SCHEMA_BUSCAR = {
    "name": "buscar_candidatos_externos",
    "description": (
        "Quando usar: 'tem algum candidato externo chamado Fulano?', 'quem são os candidatos de "
        "fora com mais conquistas no CE?', 'quais leads estão como interessado?'. A lista da "
        "captação externa: um NOME por linha, de quem mais cruzou conquista para quem menos.\n"
        f"{_QUEM_SAO}\n"
        "Para 'quem tirou ouro na OBF?' ou 'quem vai estar no Médio no ano que vem?', use "
        "buscar_candidatos_por_conquista. Para as conquistas de um nome, "
        "perfil_do_candidato_externo com o nomeNormalizado da linha.\n"
        "Definições: conquistasTotal = conquistas cruzadas do nome — o sinal mais forte de lead; "
        "participação (ter feito ou faltado a 1ª fase do ITA) não conta e vem em participacoes. "
        "escolas/cidades/ufs = tudo o que as conquistas do nome informaram, listas soltas (não "
        "pareadas). perfis > 1 = homônimos já separados à mão na ficha. "
        f"{_STATUS_NO_TEXTO} A resposta diz o total e se a lista foi cortada (truncado): "
        "estreite o filtro em vez de pedir mais.\n"
        "Exemplo: buscar_candidatos_externos(uf='CE', conquistas_min=3) → 'são 412 nomes no CE "
        "com 3 ou mais conquistas; os 20 primeiros…'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "nome": {
                "type": "string",
                "description": "Trecho do nome, sem diferença de acento nem de maiúscula. Omitido, lista todos.",
            },
            "uf": {"type": "string", "description": "Sigla, ex.: 'CE'. Bate se QUALQUER conquista do nome tiver essa UF."},
            "status_captacao": {
                "type": "string",
                "enum": list(consultas.STATUS_CAPTACAO),
                "description": "Bate se QUALQUER perfil do nome estiver nele.",
            },
            "conquistas_min": {"type": "integer", "description": "Nº mínimo de conquistas cruzadas (1 ou mais)."},
            "limite": {
                "type": "integer",
                "default": 20,
                "description": f"Quantos nomes listar, até {TETO_DE_CANDIDATOS}.",
            },
        },
    },
}


# ─── buscar_candidatos_por_conquista ─────────────────────────────────────


def _resolver_provas(cliente: Client, provas: list[Any] | None) -> tuple[list[str] | None, str | None]:
    """Os nomes de prova como o banco os grava ('OBMEP', 'Escola Naval'), ou o
    erro com os que existem. A função da 0068 compara o nome exato: 'obmep'
    não casaria com nada, e a resposta vazia pareceria "ninguém ganhou"."""
    if not provas:
        return None, None
    if any(not isinstance(p, str) or not p.strip() for p in provas):
        return None, "provas deve ser uma lista de nomes de prova, ex.: ['OBMEP', 'OBF']"
    existentes = [p["nome"] for p in cliente.table("prova_externa").select("nome").execute().data or []]
    por_chave = {_sem_acento(n): n for n in existentes}
    resolvidas, desconhecidas = [], []
    for pedida in provas:
        achada = por_chave.get(_sem_acento(pedida))
        (resolvidas if achada else desconhecidas).append(achada or pedida)
    if desconhecidas:
        return None, (
            f"prova desconhecida: {', '.join(desconhecidas)}. As que alimentam a captação: "
            f"{', '.join(sorted(existentes)) or 'nenhuma'}"
        )
    return resolvidas, None


def buscar_candidatos_por_conquista(
    cliente: Client,
    *,
    provas: list[str] | None = None,
    faixas: list[str] | None = None,
    ano_min: int | None = None,
    ano_max: int | None = None,
    publicos: list[str] | None = None,
    ano_ingresso: int | None = None,
    uf: str | None = None,
    status_captacao: str | None = None,
    nome: str | None = None,
    conquistas_min: int | None = None,
    limite: int = 20,
) -> dict:
    """O caminho inverso (docs/41 §20): os nomes que têm UMA conquista casando
    todos os critérios de conquista, pela função da 0068
    (`consultas.listar_candidatos` com critério de conquista)."""
    if not consultas.tem_criterio_de_conquista(
        prova=provas, faixa=faixas, ano_min=ano_min, ano_max=ano_max, publico=publicos
    ):
        return {
            "erro": (
                "informe pelo menos um critério de conquista (provas, faixas, ano_min, ano_max ou "
                "publicos). Para buscar pelo nome, use buscar_candidatos_externos."
            )
        }
    provas_resolvidas, erro = _resolver_provas(cliente, provas)
    if erro is not None:
        return {"erro": erro}
    limite = _limite(limite, TETO_DE_CANDIDATOS)
    try:
        pagina = consultas.listar_candidatos(
            cliente, prova=provas_resolvidas, faixa=faixas, ano_min=ano_min, ano_max=ano_max,
            publico=publicos, ano_ingresso=ano_ingresso, uf=uf, status_captacao=status_captacao,
            busca=nome, conquistas_min=conquistas_min, limite=limite,
        )
    except consultas.FiltroInvalido as exc:
        return {"erro": str(exc)}
    return {"anoIngresso": pagina["ano_ingresso"], **_lista(pagina)}


_SCHEMA_POR_CONQUISTA = {
    "name": "buscar_candidatos_por_conquista",
    "description": (
        "Quando usar: 'quem tirou ouro na OBF 2025 e vai estar no Médio no ano que vem?', 'quem "
        "chegou à 2ª fase do ITA ou do IME e não entrou?', 'medalhistas da OBMEP no CE desde "
        "2023'. O caminho inverso da captação externa: da conquista para os nomes.\n"
        f"{_QUEM_SAO}\n"
        "Todo critério de conquista (provas, faixas, anos, públicos) vale para a MESMA conquista "
        "— 'ouro' e 'OBMEP' e '2024' juntos são um ouro na OBMEP de 2024, nunca três conquistas "
        "de homônimos. uf, status, nome e conquistas_min filtram o nome depois. Os nomes de "
        "prova vêm de provas_da_captacao. Para as conquistas de um nome, "
        "perfil_do_candidato_externo com o nomeNormalizado.\n"
        f"Definições: {_FAIXAS_NO_TEXTO} Público, no ano de ingresso (anoIngresso; padrão: o ano "
        "que vem): fundamental = 6º ao 9º ano, medio = 1ª à 3ª série, pre_vestibular = formado "
        "há 1 ou 2 anos (e quem fez vestibular nos dois anos anteriores). A série vem do nível "
        "que a fonte publica, então uma conquista pode tocar dois públicos; vestibular não "
        "publica série. evidencias = as até 3 conquistas mais fortes que fizeram o nome entrar; "
        "a ordem é de lead: classificado_final e passou_de_fase vêm antes de aprovado, porque "
        "quem foi aprovado provavelmente já entrou. A resposta diz o total e se foi cortada "
        "(truncado): estreite o filtro em vez de pedir mais.\n"
        "Exemplo: buscar_candidatos_por_conquista(provas=['OBF'], faixas=['ouro'], "
        "publicos=['medio']) → '108 nomes com ouro na OBF que estarão no Médio em 2027'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "provas": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Nomes de prova (OBMEP, OBF, ITA…), de provas_da_captacao.",
            },
            "faixas": {"type": "array", "items": {"type": "string", "enum": list(FAIXAS)}},
            "ano_min": {"type": "integer", "description": "Ano da conquista, desde."},
            "ano_max": {"type": "integer", "description": "Ano da conquista, até."},
            "publicos": {"type": "array", "items": {"type": "string", "enum": list(consultas.PUBLICOS)}},
            "ano_ingresso": {
                "type": "integer",
                "description": "Ano letivo de referência do público. Omitido, o ano que vem.",
            },
            "uf": {"type": "string", "description": "Sigla, ex.: 'CE'. Bate se QUALQUER conquista do nome tiver essa UF."},
            "status_captacao": {"type": "string", "enum": list(consultas.STATUS_CAPTACAO)},
            "nome": {"type": "string", "description": "Trecho do nome, sem diferença de acento nem de maiúscula."},
            "conquistas_min": {"type": "integer", "description": "Nº mínimo de conquistas cruzadas do nome."},
            "limite": {
                "type": "integer",
                "default": 20,
                "description": f"Quantos nomes listar, até {TETO_DE_CANDIDATOS}.",
            },
        },
    },
}


# ─── perfil_do_candidato_externo ─────────────────────────────────────────


def _conquista(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c.get("id"),
        "prova": c.get("prova_nome"),
        "categoria": c.get("prova_categoria"),
        "ano": c.get("ano"),
        "resultado": c.get("resultado"),
        "faixa": c.get("faixa"),
        "nivel": c.get("nivel_texto") or None,
        "escolaInformada": c.get("escola_informada") or None,
        "cidadeInformada": c.get("cidade_informada") or None,
        "ufInformada": c.get("uf_informada") or None,
        "notasPorMateria": c.get("notas_por_materia"),
        "fonte": c.get("fonte_url"),
    }


def _perfil(candidato: dict[str, Any], *, prova: str | None, ano: int | None, limite: int) -> dict[str, Any]:
    conquistas = [
        c for c in candidato["conquistas"]
        if (prova is None or _sem_acento(c.get("prova_nome") or "") == _sem_acento(prova))
        and (ano is None or c.get("ano") == ano)
    ]
    serie = None
    if candidato.get("serie_referencia_min") is not None and candidato.get("ano_referencia_serie") is not None:
        serie = {
            "min": candidato["serie_referencia_min"],
            "max": candidato.get("serie_referencia_max"),
            "ano": candidato["ano_referencia_serie"],
        }
    return {
        "id": candidato["id"],
        "nome": candidato.get("nome"),
        "escola": candidato.get("escola"),
        "cidade": candidato.get("cidade"),
        "uf": candidato.get("uf"),
        "serieDeReferencia": serie,
        "status": candidato.get("status_captacao"),
        "conquistasTotal": candidato["conquistas_total"],
        "provasDistintas": candidato["provas_distintas"],
        "anoMaisRecente": candidato["ano_mais_recente"],
        "conquistasNoFiltro": len(conquistas),
        "truncado": len(conquistas) > limite,
        "conquistas": [_conquista(c) for c in conquistas[:limite]],
    }


def perfil_do_candidato_externo(
    cliente: Client,
    *,
    nome_normalizado: str,
    candidato_id: str | None = None,
    prova: str | None = None,
    ano: int | None = None,
    limite: int = 30,
) -> dict:
    """A ficha de um nome (`consultas.perfis_do_nome`): os perfis dele — quase
    sempre um — e as conquistas de cada um, da mais recente para a mais antiga.

    O nome passa por `normalizar_nome` de novo porque o modelo costuma mandar o
    nome de exibição ('Ana Gonçalves'); no que já vem normalizado, nada muda."""
    chave = normalizar_nome(nome_normalizado or "")
    if not chave:
        return {"erro": "informe o nome_normalizado que as buscas devolvem"}
    candidatos = consultas.perfis_do_nome(
        cliente, chave, colunas_candidato=COLUNAS_CANDIDATO, colunas_conquista=COLUNAS_CONQUISTA
    )
    if not candidatos:
        return {
            "erro": (
                f"nenhum candidato externo com o nome exato '{chave}'. Para achar o nome por um "
                "trecho, use buscar_candidatos_externos."
            )
        }
    if candidato_id:
        candidatos = [c for c in candidatos if c["id"] == candidato_id]
        if not candidatos:
            return {"erro": f"o nome '{chave}' não tem o perfil {candidato_id}"}
    limite = _limite(limite, TETO_DE_CONQUISTAS)
    return {
        "nomeNormalizado": chave,
        "perfis": len(candidatos),
        "candidatos": [_perfil(c, prova=prova, ano=ano, limite=limite) for c in candidatos],
    }


_SCHEMA_PERFIL = {
    "name": "perfil_do_candidato_externo",
    "description": (
        "Quando usar: 'o que a Fulana já ganhou?', 'em que escola ele estava na OBF?', 'quais "
        "as notas dele no IME?'. A ficha de UM nome da captação externa: os perfis do nome — "
        "quase sempre um; mais de um são homônimos que a coordenação separou à mão — e as "
        "conquistas de cada perfil, da mais recente para a mais antiga.\n"
        f"{_QUEM_SAO}\n"
        "Antes de chamar: o nome exato vem do nomeNormalizado de buscar_candidatos_externos ou "
        "de buscar_candidatos_por_conquista; um trecho de nome não basta.\n"
        "Definições: serieDeReferencia = a série no ano da conquista mais recente (6 = 6º ano … "
        "12 = 3ª série do médio); a de hoje é essa mais os anos que passaram desde então, e "
        "acima de 12 a pessoa já deve ter saído da escola. escola/cidade/uf = o retrato do "
        "perfil (a conquista mais recente, ou o que a coordenação corrigiu); "
        "escolaInformada/cidadeInformada/ufInformada = o que cada fonte publicou. "
        f"{_FAIXAS_NO_TEXTO} notasPorMateria só existe quando a fonte publica (IME, EFOMM, 1ª "
        f"fase do ITA), cada uma com as próprias chaves. fonte = a página pública do resultado. "
        f"{_STATUS_NO_TEXTO} conquistasTotal conta participação também.\n"
        "Exemplo: perfil_do_candidato_externo(nome_normalizado='ANA BEATRIZ SOUZA') → '1 perfil, 4 "
        "conquistas: prata na OBMEP 2024, …'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "nome_normalizado": {
                "type": "string",
                "description": "O nomeNormalizado (maiúsculas, sem acento) que as buscas devolvem.",
            },
            "candidato_id": {"type": "string", "description": "Só este perfil do nome (o id de cada perfil)."},
            "prova": {"type": "string", "description": "Só as conquistas desta prova."},
            "ano": {"type": "integer", "description": "Só as conquistas deste ano."},
            "limite": {
                "type": "integer",
                "default": 30,
                "description": f"Quantas conquistas por perfil, até {TETO_DE_CONQUISTAS}.",
            },
        },
        "required": ["nome_normalizado"],
    },
}


# ─── provas_da_captacao ──────────────────────────────────────────────────


def provas_da_captacao(cliente: Client) -> dict:
    """O rodapé da lista: cada prova que alimenta a captação, com os anos
    carregados (`consultas.listar_provas`). Catálogo de 10 linhas, sem pessoa
    — como `listar_ciclos`, não tem limite."""
    provas = consultas.listar_provas(cliente)
    return {
        "provas": [
            {
                "nome": p.get("nome"),
                "categoria": p.get("categoria"),
                "anoMin": p.get("ano_min"),
                "anoMax": p.get("ano_max"),
                "conquistasTotal": p.get("conquistas_total"),
            }
            for p in provas
        ]
    }


_SCHEMA_PROVAS = {
    "name": "provas_da_captacao",
    "description": (
        "Quando usar: 'de onde vêm os candidatos externos?', 'até que ano a OBF está carregada?', "
        "'o IME entra na captação?'. As provas públicas — olimpíadas, vestibulares e concursos "
        "— que alimentam a captação externa, com os anos carregados e quantas conquistas cada "
        "uma tem. A captação é de gente de FORA do colégio, não de alunos do SAS: aqui só vêm as "
        "provas, sem pessoa nenhuma. O nome da prova é o que os filtros de prova aceitam.\n"
        "Definições: categoria = olimpiada, vestibular, colegio_militar ou "
        "concurso_nivel_medio. conquistasTotal conta participação (1ª fase do ITA) também. Prova "
        "sem ano carregado ainda não tem resultado importado."
    ),
    "parameters": {"type": "object", "properties": {}},
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_BUSCAR, buscar_candidatos_externos),
    (_SCHEMA_POR_CONQUISTA, buscar_candidatos_por_conquista),
    (_SCHEMA_PERFIL, perfil_do_candidato_externo),
    (_SCHEMA_PROVAS, provas_da_captacao),
]

#: As quatro vão ao MCP (decisão da coordenação de 30/10: a IA lê o que o
#: coordenador lê). As três de pessoa ficam também em
#: `app.mcp.catalogo.SO_COM_NOME_DO_ALUNO` — fora do catálogo com o pseudônimo.
METADADOS: dict[str, dict[str, Any]] = {
    "buscar_candidatos_externos": {"expor_no_mcp": True},
    "buscar_candidatos_por_conquista": {"expor_no_mcp": True},
    "perfil_do_candidato_externo": {"expor_no_mcp": True},
    "provas_da_captacao": {"expor_no_mcp": True},
}
