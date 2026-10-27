"""Tools do Tio Léo sobre o banco de questões de ITA e IME: o que mais cai, a
missão do dia, questões por assunto, a resolução oficial e o progresso do aluno
no acervo (docs/43 §4.3).

Registradas por `tools_aluno.py`, com as convenções de lá: `aluno_id` do token
(injetado pelo registro, nunca declarado no schema), só leitura, dict de volta
— os tipos do banco são pydantic, daí o `.model_dump()` —, erro de domínio
como `{"erro": ...}`.

⚠️ `questao_vestibular` é questão de PROVA PASSADA do ITA e do IME. A do
simulado do colégio é `questao` (0010), e quem fala dela é
`minhas_questoes_erradas` (api/CLAUDE.md).

⚠️ A defesa contra a fórmula bonita e errada (docs/27 §10) é
`resolucao_oficial`: o prompt manda chamá-la antes de qualquer conta, e ela diz
de onde veio a resolução pelo CAMPO `resolucao_origem`, nunca deduzindo de qual
texto veio preenchido (CartaoQuestaoAluno.tsx). URL nenhuma vai ao modelo
(docs/27 §9, regra 2): quem mostra o link da resolução é o cartão, a partir do
banco. E o id de questão vem SEMPRE do banco — o modelo nunca o monta: a 2ª
fase leva sufixo de matéria (`ita_2017_fase2_qui_q29`).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable
from typing import Any, get_args

from supabase import Client

from ..banco.consultas import (
    POR_PAGINA_MAXIMO,
    TOPICO_SEM_CLASSIFICACAO,
    FiltroInvalido,
    FiltrosQuestoes,
    anexar_estudo_do_aluno,
    listar_questoes,
    listar_taxonomia,
    obter_questao,
    validar_filtros,
)
from ..banco.estatisticas import recorrencia
from ..banco.listas import listar_estudo
from ..banco.missao import hoje_na_escola, missao_do_dia
from ..banco.progresso import progresso_do_aluno
from ..schemas.banco import MateriaBanco, QuestaoVestibular, VestibularBanco

#: As matérias e os vestibulares do acervo, do próprio Literal da fronteira —
#: uma lista à parte aqui envelheceria calada (consultas._materias_pedidas).
MATERIAS_DO_BANCO: tuple[str, ...] = get_args(MateriaBanco)
VESTIBULARES_DO_BANCO: tuple[str, ...] = get_args(VestibularBanco)

#: O cartão `lista_questoes` mostra três linhas (ArtefatoAluno.tsx): mandar mais
#: é payload que ninguém desenha.
_ITENS_DO_CARTAO = 3

#: Só código do edital vira botão "Treinar" no cartão — o mesmo padrão de
#: `CODIGO_DE_TOPICO` em ArtefatoAluno.tsx. "sem-assunto" vira "Ver em Estudar".
_CODIGO_DO_EDITAL = re.compile(r"\d+(\.\d+)*")

_LIMITE_DO_RESUMO = 200


def _normalizar(texto: str) -> str:
    """Sem acento, sem caixa, espaço único — para casar 'termodinamica' com
    'Termodinâmica'."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return " ".join(sem_acento.casefold().split())


_IMAGEM_MD = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK_MD = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.IGNORECASE)


def _sem_endereco(texto: str) -> str:
    """O texto sem imagem, link nem URL: endereço nenhum chega ao modelo, que o
    repetiria para um menor (docs/27 §9, regra 2). A figura vira "[figura]",
    para o modelo saber que ela existe e que ele não a vê."""
    texto = _IMAGEM_MD.sub("[figura]", texto)
    texto = _LINK_MD.sub(r"\1", texto)
    return _URL.sub("[endereço]", texto)


def _resumo(enunciado: str) -> str:
    """Até `_LIMITE_DO_RESUMO` caracteres, cortado em palavra.

    ⚠️ Não é `aluno_dados.texto_resumo_questao`: aquela tira `<...>` do HTML do
    Canvas e comeria as desigualdades do LaTeX daqui.
    """
    texto = " ".join(_sem_endereco(enunciado or "").split())
    if len(texto) <= _LIMITE_DO_RESUMO:
        return texto
    corte = texto[: _LIMITE_DO_RESUMO - 1]
    if " " in corte:
        corte = corte[: corte.rfind(" ")]
    return corte.rstrip() + "…"


def _item_do_cartao(
    assunto: str, materia: str, codigo: str, quantidade: int | None
) -> dict[str, Any]:
    item: dict[str, Any] = {"assunto": assunto, "materia": materia, "topicoCodigo": codigo}
    if quantidade is not None:
        item["quantidade"] = quantidade
    return item


def _lista_questoes(titulo: str, itens: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not itens:
        return None
    return {"tipo": "lista_questoes", "titulo": titulo, "payload": {"itens": itens}}


# ─── o_que_mais_cai ──────────────────────────────────────────────────────


def o_que_mais_cai(
    cliente: Client,
    *,
    aluno_id: str,
    materia: str | None = None,
    vestibular: str | None = None,
    fase: int | None = None,
    quantos: int = 8,
) -> dict:
    """Os assuntos pela fatia da prova que ocupam — o índice de `recorrencia`.

    O índice é o de GET /banco/estatisticas, calculado no servidor para todo
    mundo ver o mesmo número (estatisticas.py); aqui só se reordena por ele — a
    resposta de lá vem por contagem bruta. Juntar matérias pelo índice é
    legítimo porque ele é percentual da prova (schemas/banco.py);
    `importanciaRanking` não compara matérias e não vai ao modelo. `aluno_id`
    chega porque o registro o injeta, e não é usado: fala das provas, não do
    aluno.
    """
    quantos = min(20, max(1, quantos))
    materias = [materia] if materia else list(MATERIAS_DO_BANCO)

    por_materia: list[dict[str, Any]] = []
    candidatos: list[tuple[float, dict[str, Any]]] = []
    for nome in materias:
        estatisticas = recorrencia(cliente, nome, vestibular, fase)  # type: ignore[arg-type]
        por_materia.append(
            {
                "materia": nome,
                "totalQuestoes": estatisticas.totalQuestoes,
                "semClassificacao": estatisticas.semClassificacao,
                "meiaVidaAnos": estatisticas.meiaVidaAnos,
                "versaoParametro": estatisticas.versaoParametro,
            }
        )
        for topico in estatisticas.topicos:
            # O que nunca caiu no recorte não é "o que mais cai".
            if topico.total <= 0:
                continue
            candidatos.append(
                (
                    topico.importancia,
                    {
                        "materia": nome,
                        "codigo": topico.codigo,
                        "nome": topico.nome,
                        "blocoNome": topico.blocoNome,
                        "importancia": round(topico.importancia, 1),
                        "total": topico.total,
                        "porVestibular": topico.porVestibular,
                    },
                )
            )
    # `sort` é estável: no empate fica a ordem de `recorrencia` (contagem, edital).
    candidatos.sort(key=lambda par: -par[0])
    topicos = [t for _, t in candidatos[:quantos]]

    recorte = [materia or "as três matérias"]
    if vestibular:
        recorte.append(vestibular)
    if fase:
        recorte.append(f"Fase {fase}")
    resultado: dict[str, Any] = {
        "recorte": {"materia": materia, "vestibular": vestibular, "fase": fase},
        "topicos": topicos,
        "porMateria": por_materia,
    }
    if not topicos:
        resultado["observacao"] = "Nenhuma questão classificada neste recorte do acervo."

    # Com recorte de vestibular ou fase, a contagem do cartão mentiria: o botão
    # "Treinar" abre o assunto INTEIRO (ArtefatoAluno.tsx), não o recorte.
    sem_recorte = vestibular is None and fase is None
    cartao = _lista_questoes(
        f"O que mais cai — {' · '.join(recorte)}",
        [
            _item_do_cartao(t["nome"], t["materia"], t["codigo"], t["total"] if sem_recorte else None)
            for t in topicos[:_ITENS_DO_CARTAO]
        ],
    )
    if cartao is not None:
        resultado["artefato"] = cartao
    return resultado


_SCHEMA_O_QUE_MAIS_CAI = {
    "name": "o_que_mais_cai",
    "description": (
        "Quando usar: 'o que mais cai no ITA?', 'qual assunto de química é mais "
        "importante?', 'o que eu priorizo pra prova?'. Devolve os assuntos do edital "
        "pela fatia da prova que ocupam, com mais peso nas provas recentes, e anexa "
        "os três primeiros para treinar. Antes de chamar, confirme o recorte que o "
        "aluno disse: matéria, vestibular e fase. Definições: importancia = % médio "
        "da prova que o assunto ocupa (meia-vida de meiaVidaAnos anos) — diga 'vale "
        "cerca de X% da prova'. total = quantas vezes caiu no recorte. "
        "semClassificacao = questões sem assunto, fora da conta. Não existe "
        "tendência ('está caindo mais'): não afirme. Fala das provas, não do aluno. "
        "Só Física, Química e Matemática. Exemplo: 'o que mais cai de física no "
        "ITA?' → o_que_mais_cai(materia='Física', vestibular='ITA') → '[assunto] "
        "vale cerca de [x]% da prova do ITA; depois vem [assunto 2].'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "materia": {
                "type": "string",
                "enum": list(MATERIAS_DO_BANCO),
                "description": "Matéria do banco. Omitida, junta as três pela fatia da prova.",
            },
            "vestibular": {
                "type": "string",
                "enum": list(VESTIBULARES_DO_BANCO),
                "description": "Omitido, soma ITA e IME.",
            },
            "fase": {
                "type": "integer",
                "enum": [1, 2],
                "description": "Omitida, soma as duas fases.",
            },
            "quantos": {
                "type": "integer",
                "description": "Quantos assuntos devolver, de 1 a 20. Padrão 8.",
            },
        },
        "required": [],
    },
}


# ─── missao_de_hoje ──────────────────────────────────────────────────────


def missao_de_hoje(cliente: Client, *, aluno_id: str) -> dict:
    """A missão de GET /missao/hoje — a mesma para todos, sorteada pela data.

    O dia é passado ao sorteio para o `hoje` da resposta ser o mesmo que
    escolheu o assunto, mesmo perto da meia-noite. Nenhuma escolha por aluno
    aqui: é decisão de produto (banco/missao.py). `aluno_id` não é usado.
    """
    hoje = hoje_na_escola()
    missao = missao_do_dia(cliente, hoje)
    resultado: dict[str, Any] = {
        "hoje": hoje.isoformat(),
        "missao": missao.model_dump() if missao else None,
    }
    if missao is None:
        resultado["observacao"] = (
            "Nenhum assunto tem questões suficientes para o desafio hoje. Ofereça "
            "o_que_mais_cai ou questoes_do_banco."
        )
        return resultado
    resultado["artefato"] = _lista_questoes(
        "Missão de hoje",
        [_item_do_cartao(missao.nome, missao.materia, missao.topicoCodigo, missao.quantidade)],
    )
    return resultado


_SCHEMA_MISSAO = {
    "name": "missao_de_hoje",
    "description": (
        "Quando usar: 'o que eu treino hoje?', 'qual é a missão do dia?', 'me dá um "
        "desafio'. Devolve o assunto do dia — o MESMO para a turma inteira, sorteado "
        "pela data — e anexa o cartão para começar. Antes de chamar, confirme que o "
        "aluno quer o desafio comum; para o ponto fraco dele, use "
        "meu_progresso_no_banco ou o_que_mais_cai. Definições: não é personalizada — "
        "nunca diga 'escolhida para você'; razao fala só de quanto o assunto aparece "
        "no acervo; missao null = nenhum assunto com questões suficientes hoje. "
        "Exemplo: 'qual a missão de hoje?' → missao_de_hoje → 'Hoje é [assunto], de "
        "[matéria]: [razão].'"
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── questoes_do_banco ───────────────────────────────────────────────────


def _resolver_assunto(
    cliente: Client, materia: str, assunto: str
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """O tópico do edital que o texto livre nomeia: `(tópico, [])`, ou
    `(None, candidatos)` quando não há um só.

    A fonte é a taxonomia (`listar_taxonomia`), a mesma da tela: o nome do
    tópico primeiro, depois os assuntos que o edital enumera dentro dele.
    """
    alvo = _normalizar(assunto)
    topicos = [
        {"codigo": t.codigo, "nome": t.nome, "assuntos": t.assuntos, "totalQuestoes": t.totalQuestoes}
        for arvore in listar_taxonomia(cliente, materia)
        for bloco in arvore.blocos
        for t in bloco.topicos
    ]
    if not alvo or not topicos:
        return None, []
    exatos = [t for t in topicos if _normalizar(t["nome"]) == alvo]
    no_nome = exatos or [t for t in topicos if alvo in _normalizar(t["nome"])]
    if len(no_nome) == 1:
        return no_nome[0], []
    if no_nome:
        return None, no_nome
    nos_assuntos = [t for t in topicos if any(alvo in _normalizar(a) for a in t["assuntos"])]
    if len(nos_assuntos) == 1:
        return nos_assuntos[0], []
    return None, nos_assuntos


def _questao_resumida(q: QuestaoVestibular) -> dict[str, Any]:
    """O que o modelo precisa para apresentar a questão — sem gabarito, sem
    anotação (texto livre do aluno, pode ter nome de terceiro) e sem URL."""
    return {
        "id": q.id,
        "vestibular": q.vestibular,
        "ano": q.ano,
        "fase": q.fase,
        "numero": q.numero,
        "dissertativa": q.dissertativa,
        "topicos": [t.nome for t in q.topicos],
        "enunciadoResumo": _resumo(q.enunciadoMd),
        "temGabarito": bool((q.gabarito or "").strip()),
        "gabaritoOrigem": q.gabaritoOrigem,
        # O CAMPO, nunca deduzido de qual texto veio (CartaoQuestaoAluno.tsx).
        "origemDaResolucao": q.resolucaoOrigem,
        "resolvida": q.resolvida,
    }


def questoes_do_banco(
    cliente: Client,
    *,
    aluno_id: str,
    materia: str,
    topico_codigo: str | None = None,
    assunto: str | None = None,
    vestibular: str | None = None,
    ano: int | None = None,
    fase: int | None = None,
    busca: str | None = None,
    quantidade: int = 5,
    pagina: int = 1,
) -> dict:
    """Uma página de GET /banco/questoes, com o estudo do aluno anexado."""
    quantidade = min(10, max(1, quantidade))
    pagina = max(1, pagina)

    topico: dict[str, Any] | None = None
    if not topico_codigo and assunto:
        topico, candidatos = _resolver_assunto(cliente, materia, assunto)
        if topico is None:
            if candidatos:
                return {
                    "erro": (
                        f"'{assunto}' casa com mais de um assunto de {materia}. Escolha "
                        "um código e chame de novo com topico_codigo (ou pergunte ao aluno)."
                    ),
                    "candidatos": [{"codigo": c["codigo"], "nome": c["nome"]} for c in candidatos[:8]],
                }
            return {
                "erro": (
                    f"Não achei '{assunto}' entre os assuntos de {materia} no edital. Tente "
                    "outro nome, ou peça os assuntos com o_que_mais_cai."
                )
            }
        topico_codigo = topico["codigo"]

    filtros = FiltrosQuestoes(
        materia=materia,
        vestibular=vestibular,
        anos=[ano] if ano else None,
        fase=fase,
        topico=topico_codigo,
        busca=busca,
        pagina=pagina,
        por_pagina=quantidade,
    )
    try:
        # A guarda do domínio, a mesma do 400 de GET /banco/questoes.
        validar_filtros(filtros)
    except FiltroInvalido as exc:
        return {"erro": str(exc)}

    pagina_lida = listar_questoes(cliente, filtros)
    questoes = anexar_estudo_do_aluno(cliente, pagina_lida.questoes, aluno_id)

    if topico is None and topico_codigo:
        # O nome sai da própria questão, que já traz os tópicos resolvidos pela
        # taxonomia — sem uma segunda leitura dela.
        nome = next(
            (t.nome for q in questoes for t in q.topicos if t.codigo == topico_codigo), None
        )
        if nome is not None:
            topico = {"codigo": topico_codigo, "nome": nome}

    resultado: dict[str, Any] = {
        "materia": materia,
        "topico": {"codigo": topico["codigo"], "nome": topico["nome"]} if topico else None,
        "total": pagina_lida.total,
        "pagina": pagina_lida.pagina,
        "porPagina": pagina_lida.porPagina,
        "questoes": [_questao_resumida(q) for q in questoes],
    }
    if not questoes:
        resultado["observacao"] = "Nenhuma questão do acervo neste recorte."
        return resultado

    if quantidade == 1 and len(questoes) == 1:
        resultado["artefato"] = {
            "tipo": "questao",
            "titulo": f"Questão {questoes[0].numero}",
            # O id EXATO do banco: o cartão busca o resto em GET /banco/questoes/{id}.
            "payload": {"id": questoes[0].id},
        }
    elif topico is not None:
        sem_recorte = not (vestibular or ano or fase or busca)
        cartao = _lista_questoes(
            f"{topico['nome']} · {materia}",
            [
                _item_do_cartao(
                    topico["nome"],
                    materia,
                    topico["codigo"],
                    pagina_lida.total if sem_recorte else None,
                )
            ],
        )
        if cartao is not None:
            resultado["artefato"] = cartao
    return resultado


_SCHEMA_QUESTOES_DO_BANCO = {
    "name": "questoes_do_banco",
    "description": (
        "Quando usar: 'me dá questões de termodinâmica do ITA', 'tem questão do IME "
        "2023 de cinemática?', 'quero treinar óptica'. Devolve questões de PROVA "
        "PASSADA do ITA e do IME, com o assunto, se tem gabarito e de quem é a "
        "resolução, e anexa o cartão para treinar (ou a própria questão, se for uma "
        "só). Antes de chamar, confirme a matéria — o mesmo código de assunto existe "
        "nas três com sentidos diferentes — e use topico_codigo vindo de outra tool; "
        "sem código, mande o nome em assunto. Definições: resolvida = o aluno marcou "
        "como feita, não é acerto. origemDaResolucao 'ari' = professor do Ari; "
        "'sugerida' = gerada por IA, sem revisão. Não traz gabarito: para resolver "
        "ou corrigir, use resolucao_oficial. Não são as questões dos simulados do "
        "colégio (essas: minhas_questoes_erradas). Exemplo: 'me passa 3 de "
        "termodinâmica do ITA' → questoes_do_banco(materia='Física', "
        "assunto='termodinâmica', vestibular='ITA', quantidade=3)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "materia": {
                "type": "string",
                "enum": list(MATERIAS_DO_BANCO),
                "description": "Obrigatória: o mesmo código de assunto existe nas três matérias.",
            },
            "topico_codigo": {
                "type": "string",
                "description": (
                    "Código do assunto no edital (ex.: 9.1), vindo de o_que_mais_cai, "
                    "meu_progresso_no_banco ou missao_de_hoje. Nunca de memória."
                ),
            },
            "assunto": {
                "type": "string",
                "description": "Nome do assunto em texto livre (ex.: termodinâmica), sem o código.",
            },
            "vestibular": {"type": "string", "enum": list(VESTIBULARES_DO_BANCO)},
            "ano": {"type": "integer", "description": "Ano da prova."},
            "fase": {"type": "integer", "enum": [1, 2]},
            "busca": {"type": "string", "description": "Palavra que aparece no enunciado."},
            "quantidade": {
                "type": "integer",
                "description": "Quantas questões, de 1 a 10. Padrão 5.",
            },
            "pagina": {
                "type": "integer",
                "description": "Página seguinte do mesmo recorte, a partir de 1. Padrão 1.",
            },
        },
        "required": ["materia"],
    },
}


# ─── resolucao_oficial ───────────────────────────────────────────────────


def _resolucao(q: QuestaoVestibular) -> dict[str, Any]:
    """De onde veio a resolução, e o que o modelo pode fazer com ela.

    A origem é o CAMPO `resolucaoOrigem`; o que existe é `resolucaoUrl` (a
    página do Ari) ou `resolucaoMd` (texto escrito no banco) — nunca os dois
    (CHECK da 0031). O link nunca vai ao modelo: o cartão o mostra.
    """
    origem = q.resolucaoOrigem
    existe = bool(q.resolucaoUrl or q.resolucaoMd)
    do_professor = origem == "ari" and existe
    texto = q.resolucaoMd if (q.resolucaoMd and not do_professor) else None

    if do_professor:
        aviso = (
            "A resolução é do professor do Ari e está no cartão abaixo. Não a "
            "reescreva nem derive outra: explique no máximo a ideia em palavras e "
            "mande o aluno ao cartão."
        )
    elif texto is not None and origem == "sugerida":
        aviso = (
            "Esta resolução foi gerada por IA e nenhum professor a revisou. Diga isso "
            "com essas palavras antes de usá-la e peça para o aluno conferir as contas."
        )
    elif texto is not None:
        aviso = (
            "Esta resolução não tem origem registrada: não se sabe se um professor a "
            "revisou. Diga isso antes de usá-la e peça para o aluno conferir as contas."
        )
    elif existe:
        aviso = (
            "A resolução está no cartão abaixo, mas não foi revisada por professor. "
            "Diga isso e mande o aluno conferir."
        )
    else:
        aviso = (
            "O banco não tem resolução desta questão. Diga isso. Se explicar, avise "
            "que a explicação é sua e pode ter erro."
        )
    return {
        "origem": origem,
        "doProfessor": do_professor,
        "noCartao": existe,
        "textoSugerido": _sem_endereco(texto) if texto else None,
        "aviso": aviso,
    }


def _achar_questao(
    cliente: Client,
    *,
    vestibular: str,
    ano: int,
    fase: int,
    numero: int,
    materia: str | None,
) -> QuestaoVestibular | dict:
    """A questão pelo endereço que o aluno cita, ou o `{"erro": ...}` que diz por
    que não deu. Uma prova cabe em uma página de `POR_PAGINA_MAXIMO`; o laço é
    para o acervo que um dia não couber."""
    casam: list[QuestaoVestibular] = []
    pagina = 1
    while True:
        filtros = FiltrosQuestoes(
            materia=materia,
            vestibular=vestibular,
            anos=[ano],
            fase=fase,
            pagina=pagina,
            por_pagina=POR_PAGINA_MAXIMO,
        )
        validar_filtros(filtros)
        lida = listar_questoes(cliente, filtros)
        casam.extend(q for q in lida.questoes if q.numero == numero)
        if pagina * lida.porPagina >= lida.total or not lida.questoes:
            break
        pagina += 1

    endereco = f"{vestibular} {ano}, fase {fase}, questão {numero}" + (
        f", de {materia}" if materia else ""
    )
    if not casam:
        return {"erro": f"Não achei no banco a {endereco}. Confirme o endereço com o aluno."}
    if len(casam) > 1:
        return {
            "erro": (
                f"Há mais de uma {endereco} no banco (uma por matéria). Pergunte a "
                "matéria, ou chame de novo com o questao_id certo."
            ),
            "candidatos": [{"id": q.id, "materia": q.materia} for q in casam],
        }
    return casam[0]


def resolucao_oficial(
    cliente: Client,
    *,
    aluno_id: str,
    questao_id: str | None = None,
    vestibular: str | None = None,
    ano: int | None = None,
    fase: int | None = None,
    materia: str | None = None,
    numero: int | None = None,
) -> dict:
    """A questão com a resolução que o banco tem e a origem dela (docs/27 §10)."""
    if questao_id:
        questao = obter_questao(cliente, questao_id)
        if questao is None:
            return {
                "erro": (
                    f"Não há questão com o id '{questao_id}' no banco. Use o id "
                    "exatamente como veio de outra tool, ou o endereço da prova."
                )
            }
    else:
        faltando = [
            nome
            for nome, valor in (("vestibular", vestibular), ("ano", ano), ("fase", fase), ("numero", numero))
            if valor is None
        ]
        if faltando:
            return {
                "erro": (
                    "argumentos inválidos para 'resolucao_oficial': mande questao_id, ou "
                    f"vestibular, ano, fase e numero — falta {', '.join(faltando)}"
                )
            }
        achada = _achar_questao(
            cliente,
            vestibular=vestibular,  # type: ignore[arg-type]
            ano=ano,  # type: ignore[arg-type]
            fase=fase,  # type: ignore[arg-type]
            numero=numero,  # type: ignore[arg-type]
            materia=materia,
        )
        if isinstance(achada, dict):
            return achada
        questao = achada

    # O que o PRÓPRIO aluno fez nesta questão — nunca a anotação, que é texto
    # livre e pode ter nome de terceiro.
    estudo = next((e for e in listar_estudo(cliente, aluno_id) if e.questaoId == questao.id), None)

    return {
        "id": questao.id,
        "vestibular": questao.vestibular,
        "ano": questao.ano,
        "fase": questao.fase,
        "materia": questao.materia,
        "numero": questao.numero,
        "dissertativa": questao.dissertativa,
        "enunciadoMd": _sem_endereco(questao.enunciadoMd),
        # O enunciado de verdade está numa figura que o modelo não vê: sem isto,
        # ele resolveria o texto do OCR achando que é a questão inteira.
        "dependeDeFigura": questao.usaImagemNoRender,
        # Alternativa também pode ser figura, e a figura traz o endereço junto.
        "alternativas": (
            {letra: _sem_endereco(texto) for letra, texto in questao.alternativas.items()}
            if questao.alternativas
            else None
        ),
        "gabarito": questao.gabarito,
        "gabaritoOrigem": questao.gabaritoOrigem,
        "gabaritoConfianca": questao.gabaritoConfianca,
        "topicos": [{"codigo": t.codigo, "nome": t.nome} for t in questao.topicos],
        "resolucao": _resolucao(questao),
        "meuTreino": (
            {
                "resolvida": estudo.resolvida,
                "alternativaEscolhida": estudo.alternativaEscolhida,
                "acertou": estudo.acertou,
            }
            if estudo
            else None
        ),
        "artefato": {
            "tipo": "questao",
            "titulo": f"Questão {questao.numero}",
            "payload": {"id": questao.id},
        },
    }


_SCHEMA_RESOLUCAO = {
    "name": "resolucao_oficial",
    "description": (
        "Quando usar: SEMPRE antes de explicar, resolver ou conferir uma questão de "
        "prova do ITA ou do IME — antes de escrever qualquer conta. Devolve o "
        "enunciado, o gabarito e a resolução que o banco tem, com a origem dela, e "
        "anexa o cartão da questão. Antes de chamar, confirme a questão: questao_id "
        "exatamente como veio de outra tool, ou vestibular + ano + fase + número (e "
        "a matéria, se o aluno disse); nunca monte o id. Definições: "
        "resolucao.doProfessor=true → é do professor do Ari e está no cartão: não a "
        "reescreva nem derive outra; explique no máximo a ideia. textoSugerido = "
        "gerada por IA, sem revisão: diga isso antes de usar e peça para conferir as "
        "contas. Sem resolução: diga que o banco não tem; se explicar, avise que a "
        "conta é sua e pode ter erro. gabaritoOrigem 'banca' = oficial; 'sugerido' "
        "= deduzido. dependeDeFigura=true: o enunciado depende de figura que você "
        "não vê. Pediu só dica? Não entregue o gabarito. Nunca escreva link. "
        "Exemplo: 'como resolve a 12 do ITA 2019, fase 1?' → "
        "resolucao_oficial(vestibular='ITA', ano=2019, fase=1, numero=12)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "questao_id": {
                "type": "string",
                "description": (
                    "id do banco exatamente como veio de outra tool (ex.: "
                    "ita_2019_fase1_q12). Nunca monte o id à mão."
                ),
            },
            "vestibular": {"type": "string", "enum": list(VESTIBULARES_DO_BANCO)},
            "ano": {"type": "integer", "description": "Ano da prova."},
            "fase": {"type": "integer", "enum": [1, 2]},
            "materia": {
                "type": "string",
                "enum": list(MATERIAS_DO_BANCO),
                "description": "Só se o aluno disse: desempata a 2ª fase, numerada por matéria.",
            },
            "numero": {"type": "integer", "description": "Número da questão na prova."},
        },
        "required": [],
    },
}


# ─── meu_progresso_no_banco ──────────────────────────────────────────────


def meu_progresso_no_banco(
    cliente: Client,
    *,
    aluno_id: str,
    materia: str | None = None,
    assuntos: int = 8,
    por_ano: bool = False,
) -> dict:
    """GET /banco/progresso, recortado para o modelo.

    "Feitas" é `resolvida`, AUTO-DECLARADA — não é acerto (banco/progresso.py).
    Os assuntos vão pelo maior buraco (total − feitas), e a linha das questões
    sem classificação vai SEMPRE: escondê-la daria ao aluno um recorte
    incompleto sem aviso (docs/22 §8).
    """
    assuntos = min(20, max(1, assuntos))
    progresso = progresso_do_aluno(cliente, aluno_id)

    da_materia = [a for a in progresso.porAssunto if materia is None or a.materia == materia]
    sem_classificacao = [a for a in da_materia if a.codigo == TOPICO_SEM_CLASSIFICACAO]
    do_edital = sorted(
        (a for a in da_materia if a.codigo != TOPICO_SEM_CLASSIFICACAO),
        key=lambda a: (-(a.total - a.feitas), a.materia, a.nome),
    )
    escolhidos = do_edital[:assuntos]

    resultado: dict[str, Any] = {
        "feitas": progresso.feitas,
        "total": progresso.total,
        "porMateria": [m.model_dump() for m in progresso.porMateria],
        "porAssunto": [a.model_dump() for a in [*escolhidos, *sem_classificacao]],
    }
    if por_ano:
        resultado["porAno"] = [
            linha.model_dump()
            for linha in progresso.porAno
            if materia is None or linha.materia == materia
        ]

    cartao = _lista_questoes(
        "Onde você ainda não marcou questões",
        [
            _item_do_cartao(a.nome, a.materia, a.codigo, a.total - a.feitas)
            for a in escolhidos
            if a.total > a.feitas and _CODIGO_DO_EDITAL.fullmatch(a.codigo)
        ][:_ITENS_DO_CARTAO],
    )
    if cartao is not None:
        resultado["artefato"] = cartao
    return resultado


_SCHEMA_PROGRESSO = {
    "name": "meu_progresso_no_banco",
    "description": (
        "Quando usar: 'quanto do banco eu já fiz?', 'que assunto eu ainda não "
        "treinei?'. Devolve quantas questões do acervo de provas do ITA e do IME o "
        "aluno MARCOU como feitas, por matéria e por assunto, sempre com o total ao "
        "lado, e anexa os assuntos com mais questões por fazer. Antes de chamar, "
        "confirme a matéria, se o aluno falou de uma. Definições: 'feitas' é a marca "
        "que o próprio aluno aperta — não é acerto; diga 'você marcou [f] de [t]', "
        "nunca 'você domina'. A soma dos assuntos passa do total porque uma questão "
        "pode estar em dois. 'Sem classificação de assunto' são questões que ninguém "
        "classificou — não as esconda. Só Física, Química e Matemática. Exemplo: 'o "
        "que eu ainda não estudei em física?' → meu_progresso_no_banco(materia="
        "'Física') → 'Você marcou [f] de [t] questões de Física; [assunto] tem [n] e "
        "você não fez nenhuma.'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "materia": {
                "type": "string",
                "enum": list(MATERIAS_DO_BANCO),
                "description": "Recorta os assuntos a uma matéria do banco. Omitida, as três.",
            },
            "assuntos": {
                "type": "integer",
                "description": "Quantos assuntos com mais questões por fazer, de 1 a 20. Padrão 8.",
            },
            "por_ano": {
                "type": "boolean",
                "description": "true inclui a grade matéria × ano de prova. Padrão false.",
            },
        },
        "required": [],
    },
}


# ─── As tools deste módulo ───────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_O_QUE_MAIS_CAI, o_que_mais_cai),
    (_SCHEMA_MISSAO, missao_de_hoje),
    (_SCHEMA_QUESTOES_DO_BANCO, questoes_do_banco),
    (_SCHEMA_RESOLUCAO, resolucao_oficial),
    (_SCHEMA_PROGRESSO, meu_progresso_no_banco),
]
