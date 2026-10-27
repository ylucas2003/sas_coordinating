"""Tools do banco de questões — provas PASSADAS de ITA e IME (docs/43 §4.3).

O banco (`questao_vestibular`, docs/22) é o acervo de provas antigas, não os
simulados do colégio: a questão de simulado é `questao` (migration 0010) e
mora em `questoes_do_simulado`. É o erro de leitura mais provável do schema
(api/CLAUDE.md), e por isso as descrições daqui o dizem com todas as letras.

Três portas, na ordem em que o modelo costuma usá-las:

  topicos_do_edital         o assunto dito → o código do edital ('7.2')
  buscar_questoes_do_banco  as questões de um recorte, ou uma questão aberta
  recorrencia_no_banco      o que mais cai: recorrência e índice de importância

Nada aqui é regra nova. A guarda "tópico exige matéria" é
`consultas.validar_filtros`; as contagens e o índice saem prontos de
`consultas` e `estatisticas`; a fatia de cada ano é `importancia.fatia_do_ano`.
A tool escolhe campos e corta a SAÍDA — nunca a leitura, que é agregada:
truncá-la devolveria recorrência errada sem erro nenhum (docstring de
`banco/estatisticas.py`, armadilha 2 do CLAUDE.md).

⚠️ A matéria do banco tem ACENTO ('Física', `schemas/banco.py`); a da régua e
dos simulados é código ('fisica'). Os enums daqui saem do Literal do schema
para o modelo não ter como mandar o código.

As três vão ao MCP (`METADADOS`): é prova pública, sem dado de pessoa
(docs/43 §5.4; mapa de LGPD de 24/10).
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from datetime import date
from typing import Any, get_args

from supabase import Client

from ...banco import consultas, estatisticas, importancia
from ...schemas.banco import ColecaoBanco, MateriaBanco, QuestaoVestibular, VestibularBanco

MATERIAS_DO_BANCO: tuple[str, ...] = get_args(MateriaBanco)
VESTIBULARES_DO_BANCO: tuple[str, ...] = get_args(VestibularBanco)
COLECOES_DO_BANCO: tuple[str, ...] = get_args(ColecaoBanco)

#: A fase no vocabulário que o assistente da coordenação já usa para simulado
#: (`simulado.tipo`, `insights_do_ciclo`). O banco guarda 1 e 2; a tradução é
#: de vocabulário, não regra. E é texto, e não inteiro, também porque o MCP
#: põe teto em todo inteiro de tool exposta que não esteja declarado como
#: "não é limite" (app/mcp/catalogo.py): fase não é limite de linhas.
FASES = {"fase_1": 1, "fase_2": 2}

#: Tetos da SAÍDA. O despacho não confere `maximum` (ferramentas.py): quem
#: limita é o handler. Página do banco é navegação (docs/22 §2.2); 20 questões
#: com enunciado já é mais texto do que o modelo consegue usar numa resposta.
TETO_DE_TOPICOS = 80
TETO_DE_QUESTOES = 20
TETO_DA_RECORRENCIA = 30

LIMITE_DO_RESUMO = 240
LIMITE_DO_ENUNCIADO = 4000

#: Ano plausível de prova. Não é regra do acervo: é só a guarda contra lixo
#: (`[20, 3000]`) virar `in.()` na query string.
ANO_MINIMO = 1900


# ─── A questão como o modelo a lê ────────────────────────────────────────


def resumir_questao(q: QuestaoVestibular, *, completa: bool = False) -> dict[str, Any]:
    """A questão sem endereço nenhum, no formato das tools.

    Pública e pura de propósito: a tool do banco do ALUNO (docs/43 §4.3) usa
    a mesma, com outro nome de tool — o nome é único entre os escopos
    (ferramentas.py).

    Nunca sai `imagemUrl` nem `resolucaoUrl`. São endereços: o Markdown do
    chat recusa link (docs/31 §2.4) e o modelo não viu a figura. O que ele
    precisa saber é que ela existe — `dependeDeImagem`.

    `completa` é a questão aberta pelo id: enunciado inteiro (até
    `LIMITE_DO_ENUNCIADO`) e alternativas. Sem ela, um resumo de uma linha.
    """
    saida: dict[str, Any] = {
        "id": q.id,
        "vestibular": q.vestibular,
        "ano": q.ano,
        "fase": q.fase,
        "numero": q.numero,
        "materia": q.materia,
        "dissertativa": q.dissertativa,
        "topicos": [{"codigo": t.codigo, "nome": t.nome} for t in q.topicos],
        "gabarito": q.gabarito,
        "gabaritoOrigem": q.gabaritoOrigem,
        "dependeDeImagem": q.usaImagemNoRender,
        "resolucao": _origem_da_resolucao(q),
        "colecao": _colecao(q.extraidoPor),
    }
    if completa:
        saida["enunciado"] = _cortar((q.enunciadoMd or "").strip(), LIMITE_DO_ENUNCIADO)
        saida["alternativas"] = q.alternativas
    else:
        saida["enunciadoResumo"] = _cortar(" ".join((q.enunciadoMd or "").split()), LIMITE_DO_RESUMO)
    return saida


def _origem_da_resolucao(q: QuestaoVestibular) -> str | None:
    """'professor' = a resolução do Ari (o link); senão a origem da escrita no
    cartão; senão nenhuma. Os dois nunca coexistem (CHECK da 0031)."""
    if q.resolucaoUrl:
        return "professor"
    if q.resolucaoMd:
        return q.resolucaoOrigem or "escrita"
    return None


def _colecao(extraido_por: str | None) -> str | None:
    """'recentes' ou 'arquivo', lido da tradução que o domínio já faz."""
    return next(
        (nome for nome, modos in consultas.MODOS_DA_COLECAO.items() if extraido_por in modos),
        None,
    )


def _cortar(texto: str, limite: int) -> str:
    return texto if len(texto) <= limite else f"{texto[: limite - 1].rstrip()}…"


def _sem_acento(texto: str) -> str:
    """Para localizar 'optica' em 'Óptica'. É busca, não regra de negócio."""
    decomposto = unicodedata.normalize("NFKD", texto)
    return " ".join("".join(c for c in decomposto if not unicodedata.combining(c)).casefold().split())


def _fase(fase: str | None) -> tuple[int | None, str | None]:
    if fase is None:
        return None, None
    if fase not in FASES:
        return None, f"fase deve ser uma de: {', '.join(FASES)}"
    return FASES[fase], None


def _anos(anos: list[Any] | None) -> tuple[list[int] | None, str | None]:
    """A lista de anos do filtro, ou o erro que o modelo consegue corrigir.

    O despacho só confere que é lista (ferramentas.py); o item é daqui.
    Fora de [ANO_MINIMO, ano corrente] sai em silêncio — pedir "2020 a 2027"
    é pedir "até agora". Sem nenhum ano válido, é erro: lista vazia significa
    "todos os anos" no domínio, e devolver o acervo inteiro para quem pediu
    2030 seria responder outra pergunta.
    """
    if not anos:
        return None, None
    convertidos: set[int] = set()
    for item in anos:
        if isinstance(item, bool):
            return None, "anos deve ser uma lista de anos, ex.: [2023, 2024]"
        if isinstance(item, float) and item.is_integer():
            item = int(item)
        elif isinstance(item, str) and item.strip().isdigit():
            item = int(item.strip())
        if not isinstance(item, int):
            return None, "anos deve ser uma lista de anos, ex.: [2023, 2024]"
        convertidos.add(item)
    hoje = date.today().year
    validos = sorted(a for a in convertidos if ANO_MINIMO <= a <= hoje)
    if not validos:
        return None, f"nenhum ano válido em {sorted(convertidos)}: o banco tem provas até {hoje}"
    return validos, None


# ─── topicos_do_edital ───────────────────────────────────────────────────


def topicos_do_edital(
    cliente: Client,
    *,
    materia: str | None = None,
    busca: str | None = None,
    incluir_assuntos: bool = False,
    limite: int = 30,
) -> dict:
    """Os tópicos do edital com a contagem de questões, e o resumo de cada matéria."""
    limite = min(max(1, limite), TETO_DE_TOPICOS)
    termo = _sem_acento(busca) if busca and busca.strip() else None

    materias: list[dict[str, Any]] = []
    topicos: list[dict[str, Any]] = []
    for arvore in consultas.listar_taxonomia(cliente, materia):
        m = arvore.model_dump()
        anos = m["anos"]
        materias.append({
            "materia": m["materia"],
            "totalQuestoes": m["totalQuestoes"],
            "semClassificacao": m["semClassificacao"],
            "anos": [min(anos), max(anos)] if anos else [],
            "fases": m["fases"],
            "vestibulares": m["vestibulares"],
        })
        for bloco in m["blocos"]:
            for t in bloco["topicos"]:
                if termo and not any(
                    termo in _sem_acento(texto) for texto in (t["nome"], bloco["nome"], *t["assuntos"])
                ):
                    continue
                item = {
                    "materia": m["materia"],
                    "codigo": t["codigo"],
                    "nome": t["nome"],
                    "bloco": bloco["nome"],
                    "totalQuestoes": t["totalQuestoes"],
                }
                if incluir_assuntos:
                    item["assuntos"] = t["assuntos"]
                topicos.append(item)

    return {
        "materias": materias,
        "total": len(topicos),
        "truncado": len(topicos) > limite,
        "topicos": topicos[:limite],
    }


_SCHEMA_TOPICOS = {
    "name": "topicos_do_edital",
    "description": (
        "Quando usar: para traduzir o assunto citado ('eletrostática', 'estequiometria') no "
        "código de tópico do edital que buscar_questoes_do_banco e recorrencia_no_banco "
        "esperam, e para 'quantas questões o banco tem de X'. É a porta de entrada do banco.\n"
        "Antes de chamar, confirme: a matéria, se foi dita. O banco só tem Física, Química e "
        "Matemática; sem matéria, a busca roda nas três e você mostra os candidatos.\n"
        "Definições: o banco são provas PASSADAS de ITA e IME, não os simulados do colégio "
        "(esses estão em questoes_do_simulado). Tópico = subárea do edital, código 'N.M'. O "
        "mesmo código muda de sentido entre matérias ('1.1' é uma coisa em Física e outra em "
        "Química): nunca use código sem a matéria. totalQuestoes do tópico conta a questão "
        "mista nos dois tópicos, então a soma passa do total da matéria. semClassificacao = "
        "questões sem tópico: existem, mas não aparecem em tópico nenhum.\n"
        "Exemplo: 'quantas questões de óptica temos?' → "
        "topicos_do_edital(materia='Física', busca='óptica')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "materia": {
                "type": "string",
                "enum": list(MATERIAS_DO_BANCO),
                "description": "Com acento. Omitida, traz as três. O banco não tem Português, Inglês nem Redação.",
            },
            "busca": {
                "type": "string",
                "description": "Trecho do nome do tópico ou de um assunto do edital, ex.: 'eletrost'. Acento não importa.",
            },
            "incluir_assuntos": {
                "type": "boolean",
                "default": False,
                "description": "Traz os assuntos que o edital enumera em cada tópico (aumenta muito a resposta).",
            },
            "limite": {"type": "integer", "default": 30, "description": f"Máximo de tópicos, até {TETO_DE_TOPICOS}."},
        },
        "required": [],
    },
}


# ─── buscar_questoes_do_banco ────────────────────────────────────────────


def buscar_questoes_do_banco(
    cliente: Client,
    *,
    questao_id: str | None = None,
    materia: str | None = None,
    vestibular: str | None = None,
    anos: list[Any] | None = None,
    fase: str | None = None,
    topico: str | None = None,
    colecao: str | None = None,
    busca: str | None = None,
    limite: int = 10,
) -> dict:
    """Uma página do banco no recorte pedido, ou uma questão aberta pelo id."""
    if questao_id and questao_id.strip():
        questao = consultas.obter_questao(cliente, questao_id.strip())
        if questao is None:
            return {
                "erro": (
                    f"não existe a questão '{questao_id}' no banco. O id vem de uma busca "
                    "anterior, no formato 'ita_2019_fase1_q01'."
                )
            }
        return {"questao": resumir_questao(questao, completa=True)}

    lista_de_anos, erro_dos_anos = _anos(anos)
    numero_da_fase, erro_da_fase = _fase(fase)
    if erro_dos_anos or erro_da_fase:
        return {"erro": erro_dos_anos or erro_da_fase}

    filtros = consultas.FiltrosQuestoes(
        materia=materia,
        vestibular=vestibular,
        anos=lista_de_anos,
        fase=numero_da_fase,
        topico=topico.strip() if topico and topico.strip() else None,
        colecao=colecao,
        busca=busca,
        pagina=1,
        por_pagina=min(max(1, limite), TETO_DE_QUESTOES),
    )
    # A guarda é do domínio — a mesma que vira 400 na rota. Sem ela, '1.1'
    # juntaria as três matérias em silêncio (consultas.validar_filtros).
    try:
        consultas.validar_filtros(filtros)
    except consultas.FiltroInvalido as exc:
        return {"erro": str(exc)}

    pagina = consultas.listar_questoes(cliente, filtros)
    return {
        "total": pagina.total,
        "mostradas": len(pagina.questoes),
        "questoes": [resumir_questao(q) for q in pagina.questoes],
    }


_SCHEMA_BUSCAR_QUESTOES = {
    "name": "buscar_questoes_do_banco",
    "description": (
        "Quando usar: para listar ou abrir questões de prova passada de ITA/IME por matéria, "
        "vestibular, ano, fase, tópico ou texto ('questões de óptica do ITA desde 2020', 'o "
        "que pedia a questão 7 do ITA 2023'). Para contar o que mais cai, use "
        "recorrencia_no_banco; para questão de simulado do colégio, questoes_do_simulado.\n"
        "Antes de chamar, confirme: tópico só junto com a matéria, e o código vem de "
        "topicos_do_edital, nunca de memória. Para abrir uma questão, o questao_id vem de uma "
        "busca anterior.\n"
        "Definições: a resposta é UMA AMOSTRA — `total` é quantas existem no recorte; nunca "
        "diga que só existem as mostradas, e para ver outras estreite o recorte. Coleção "
        "'recentes' = recorte fino da questão (ITA 2019+, IME 2018+); 'arquivo' = página "
        "inteira do caderno, acervo antigo. dissertativa = sem alternativas nem letra. "
        "gabaritoOrigem 'sugerido' = deduzido resolvendo, não oficial: diga isso. "
        "dependeDeImagem = o texto sozinho não basta. resolucao: 'professor' (do Ari), outra "
        "origem escrita, ou null. O enunciado vem do PDF e pode ter sujeira de OCR: cite, não "
        "conserte.\n"
        "Exemplo: buscar_questoes_do_banco(materia='Física', vestibular='ITA', topico='7.2', "
        "anos=[2020, 2021, 2022, 2023, 2024, 2025]); depois "
        "buscar_questoes_do_banco(questao_id='ita_2023_fase1_q07')."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "questao_id": {
                "type": "string",
                "description": "Id legível, ex.: 'ita_2019_fase1_q01'. Com ele, os outros filtros são ignorados e a questão vem completa.",
            },
            "materia": {"type": "string", "enum": list(MATERIAS_DO_BANCO), "description": "Com acento."},
            "vestibular": {"type": "string", "enum": list(VESTIBULARES_DO_BANCO)},
            "anos": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Os anos, um por item: 'desde 2020' = [2020, 2021, …, ano atual]. Omitido, todos.",
            },
            "fase": {"type": "string", "enum": list(FASES), "description": "1ª ou 2ª fase. Omitida, as duas."},
            "topico": {
                "type": "string",
                "description": (
                    "Código do edital vindo de topicos_do_edital, ex.: '7.2'. Exige materia. "
                    f"'{consultas.TOPICO_SEM_CLASSIFICACAO}' traz as não classificadas."
                ),
            },
            "colecao": {"type": "string", "enum": list(COLECOES_DO_BANCO)},
            "busca": {"type": "string", "description": "Texto no enunciado."},
            "limite": {"type": "integer", "default": 10, "description": f"Quantas questões mostrar, até {TETO_DE_QUESTOES}."},
        },
        "required": [],
    },
}


# ─── recorrencia_no_banco ────────────────────────────────────────────────

_ORDENACOES: dict[str, Callable[[dict[str, Any]], float]] = {
    "importancia": lambda t: -t["importancia"],
    "total": lambda t: -t["total"],
}


def recorrencia_no_banco(
    cliente: Client,
    *,
    materia: str,
    vestibular: str | None = None,
    fase: str | None = None,
    topico: str | None = None,
    ordenar_por: str = "importancia",
    limite: int = 10,
) -> dict:
    """Recorrência e índice de importância por tópico; com `topico`, a série ano a ano."""
    numero_da_fase, erro = _fase(fase)
    if erro is not None:
        return {"erro": erro}
    if ordenar_por not in _ORDENACOES:
        return {"erro": f"ordenar_por deve ser um de: {', '.join(_ORDENACOES)}"}

    # A leitura é a da rota, inteira: o corte em `limite` é só na saída.
    est = estatisticas.recorrencia(cliente, materia, vestibular, numero_da_fase).model_dump()
    anos = est["anos"]
    envelope: dict[str, Any] = {
        "materia": est["materia"],
        "vestibular": vestibular,
        "fase": fase,
        "totalQuestoes": est["totalQuestoes"],
        "semClassificacao": est["semClassificacao"],
        "anos": [anos[0], anos[-1]] if anos else [],
        "meiaVidaAnos": est["meiaVidaAnos"],
        "versaoParametro": est["versaoParametro"],
    }

    if topico and topico.strip():
        codigo = topico.strip()
        linha = next((t for t in est["topicos"] if t["codigo"] == codigo), None)
        if linha is None:
            return {
                "erro": (
                    f"o tópico '{codigo}' não existe em {materia}. O código vem de "
                    "topicos_do_edital, na mesma matéria."
                )
            }
        # O domínio da série é `anos`, não as chaves de `porAno`: ano sem
        # ocorrência é zero e tem de aparecer (docstring de `recorrencia`).
        serie = []
        for ano in anos:
            ocorrencias = linha["porAno"].get(ano, 0)
            questoes = est["questoesPorAno"].get(ano, 0)
            serie.append({
                "ano": ano,
                "ocorrencias": ocorrencias,
                "questoes": questoes,
                "pctDaProva": round(importancia.fatia_do_ano(ocorrencias, questoes), 1),
            })
        return {**envelope, "topico": _linha_do_topico(linha), "serie": serie}

    ordenados = sorted(est["topicos"], key=_ORDENACOES[ordenar_por])
    limite = min(max(1, limite), TETO_DA_RECORRENCIA)
    return {
        **envelope,
        "nTopicos": len(ordenados),
        "nTopicosSemOcorrencia": sum(1 for t in ordenados if t["total"] == 0),
        "ordenadoPor": ordenar_por,
        "topicos": [_linha_do_topico(t) for t in ordenados[:limite]],
    }


def _linha_do_topico(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "codigo": t["codigo"],
        "nome": t["nome"],
        "bloco": t["blocoNome"],
        "total": t["total"],
        "porVestibular": t["porVestibular"],
        "porFase": t["porFase"],
        "importancia": round(t["importancia"], 1),
        "importanciaRanking": round(t["importanciaRanking"]),
    }


_SCHEMA_RECORRENCIA = {
    "name": "recorrencia_no_banco",
    "description": (
        "Quando usar: 'o que mais cai em Química no IME?', 'quanto pesa óptica na prova do "
        "ITA?', 'em que anos caiu termodinâmica?'. Devolve a recorrência de cada tópico do "
        "edital no acervo e o índice de importância.\n"
        "Antes de chamar, confirme: a matéria, que é obrigatória. Vestibular e fase quando a "
        "pergunta for de um só: eles estreitam numerador e denominador juntos e mudam o "
        "número. Para a série ano a ano, o código do tópico vem de topicos_do_edital.\n"
        "Definições: importancia = % da prova que o tópico vale hoje, média dos anos pesada "
        "por recência (meia-vida de meiaVidaAnos anos) — é o número a citar. "
        "importanciaRanking = o mesmo índice reescalado de 0 a 100 pelo maior do recorte: só "
        "ordena, e um 100 de Química não equivale a um 100 de Física. total = ocorrências "
        "brutas, que não comparam bancas nem anos. semClassificacao > 0 = o recorte está "
        "incompleto: diga sempre. versaoParametro null = calibração de fábrica. A tool NÃO "
        "diz se um tópico está subindo ou caindo: descreva a série e não invente tendência.\n"
        "Exemplo: recorrencia_no_banco(materia='Química', vestibular='IME') → 'o tópico X "
        "vale ~6% da prova (pesado por recência); 40 questões sem tópico ficaram de fora'."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "materia": {"type": "string", "enum": list(MATERIAS_DO_BANCO), "description": "Com acento."},
            "vestibular": {
                "type": "string",
                "enum": list(VESTIBULARES_DO_BANCO),
                "description": "Omitido, soma ITA e IME.",
            },
            "fase": {"type": "string", "enum": list(FASES), "description": "Omitida, soma as duas."},
            "topico": {
                "type": "string",
                "description": "Código do edital (topicos_do_edital). Com ele vem a série ano a ano desse tópico.",
            },
            "ordenar_por": {"type": "string", "enum": list(_ORDENACOES), "default": "importancia"},
            "limite": {
                "type": "integer",
                "default": 10,
                "description": f"Quantos tópicos listar, até {TETO_DA_RECORRENCIA}.",
            },
        },
        "required": ["materia"],
    },
}


# ─── Registry ─────────────────────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_TOPICOS, topicos_do_edital),
    (_SCHEMA_BUSCAR_QUESTOES, buscar_questoes_do_banco),
    (_SCHEMA_RECORRENCIA, recorrencia_no_banco),
]

#: Prova pública, sem dado de pessoa: as três vão ao MCP (docs/43 §5.4).
METADADOS: dict[str, dict[str, Any]] = {
    "topicos_do_edital": {"expor_no_mcp": True},
    "buscar_questoes_do_banco": {"expor_no_mcp": True},
    "recorrencia_no_banco": {"expor_no_mcp": True},
}
