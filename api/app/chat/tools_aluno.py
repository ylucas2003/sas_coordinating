"""Tools do chat do aluno — restritas aos dados do próprio aluno.

Espelham os endpoints /me: cada handler recebe o `aluno_id` injetado a partir
do JWT pelo registro de ferramentas (`chat/ferramentas.py`, escopo `aluno`).
NENHUM schema declara `aluno_id` — mesmo que o LLM alucine um nos argumentos, o
registro o descarta e injeta o do token.

Mesmas convenções do registry do coordenador (tools/__init__.py):
read-only, retornos JSON-serializáveis, erros como {"erro": "..."}.

Este módulo é a PORTA do escopo `aluno` no registro: `TOOLS` daqui é o que
`ferramentas._montar_registro` recolhe. As tools de 24/10 (docs/43 §4.3) moram
em dois irmãos, por assunto, e entram pela lista lá embaixo:

  tools_aluno_situacao.py   panorama, régua, agenda, trajetória, distribuição
  tools_aluno_banco.py      o que mais cai, missão, questões, resolução, progresso

Um cartão para a tela vai no campo ANINHADO `artefato: {tipo, titulo, payload}`
(docs/27 §7; ferramentas.artefatos_do_resultado), nunca com `tipo` no topo.
"""

from __future__ import annotations

from collections.abc import Callable

from supabase import Client

from ..stats.aluno_dados import (
    conta_como_desempenho,
    detalhe_simulado_do_aluno,
    evolucao_do_aluno,
    payload_insight_ciclo,
    questoes_do_aluno_no_simulado,
    simulados_do_aluno,
)
from ..stats.aluno_jornada import sequencia_do_aluno
from ..stats.insight_aluno import gerar_para_aluno_ciclo
from . import tools_aluno_banco, tools_aluno_situacao

# ─── minhas_notas ─────────────────────────────────────────────────────────

#: As marcas do domínio que já fizeram o seu trabalho na partição: na lista
#: das que contam, são todas verdadeiras, e só ocupariam o contexto do modelo.
_MARCAS_DO_DOMINIO = ("computavel", "motivoNaoComputavel", "notaConfiavel", "anoLetivoId")


def minhas_notas(cliente: Client, *, aluno_id: str) -> dict:
    """Todos os simulados do aluno com nota, delta e média da turma.

    Nenhuma regra aqui: `mediaGeral` já vem pelo piso de anonimato e
    `deltaSelf` já ignora a nota que não conta (`aluno_dados.simulados_do_aluno`,
    a mesma de GET /me/simulados). O que a tool faz é partir a lista com
    `conta_como_desempenho`: a prova cuja nota é provável ausência vai para
    `naoContam`, sem o número — no meio das outras, o zero era lido como "você
    zerou Química".
    """
    itens = simulados_do_aluno(cliente, aluno_id)
    contam = [
        {k: v for k, v in s.items() if k not in _MARCAS_DO_DOMINIO}
        for s in itens
        if conta_como_desempenho(s)
    ]
    resultado: dict = {"total": len(contam), "simulados": contam}
    nao_contam = [s for s in itens if not conta_como_desempenho(s)]
    if nao_contam:
        resultado["naoContam"] = tools_aluno_situacao.provas_que_nao_contam(nao_contam)
        resultado["observacao"] = tools_aluno_situacao.NAO_CONTAM
    return resultado


_SCHEMA_MINHAS_NOTAS = {
    "name": "minhas_notas",
    "description": (
        "Quando usar: achar o simulado_id de uma prova que o aluno citou pelo nome "
        "('o ITA P1 de março') ou listar todas as provas com nota. Devolve cada "
        "simulado com nota (0–10), deltaSelf, média da turma, matéria, ciclo e "
        "vestibular. Antes de chamar, confirme: para 'como estou?' use meu_panorama, "
        "que já traz as últimas notas. Definições: deltaSelf = nota menos a média das "
        "provas anteriores do próprio aluno. mediaGeral null = turma pequena demais "
        "para comparar: diga isso, sem estimar. naoContam = provas com nota lançada "
        "que não é desempenho (provável ausência): nunca as cite como nota. Não tire "
        "média desta lista — a média que vale para a régua está em minha_zona. "
        "Exemplo: 'como fui no ITA P1?' → minhas_notas → "
        "meu_desempenho_em_simulado(simulado_id=[id])."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── meu_desempenho_em_simulado ───────────────────────────────────────────

def meu_desempenho_em_simulado(cliente: Client, *, aluno_id: str, simulado_id: str) -> dict:
    """Nota, posição, percentil e comparação com grupos num simulado, com o
    cartão da prova.

    A guarda de "só simulado do próprio aluno" é da função de domínio — sem
    nota dele ali, volta erro —, a mesma de GET /me/simulado/{id}, que o cartão
    consulta e que devolve 404 para prova alheia. O payload é só o id: nome e
    data o cartão busca por conta própria (ArtefatoAluno.tsx). O nome da tool
    não muda — renomeá-la quebraria as conversas em andamento.
    """
    detalhe = detalhe_simulado_do_aluno(cliente, aluno_id, simulado_id)
    if "erro" in detalhe:
        return detalhe
    resultado = {
        **detalhe,
        "artefato": {"tipo": "prova", "titulo": None, "payload": {"simuladoId": detalhe["id"]}},
    }
    grupos = detalhe.get("grupos") or {}
    # O `null` é o piso de anonimato de `aluno_dados` (docs/27 §9), e são dois
    # pisos: o da turma tira média, posição e percentil; o do grupo de 15% tira
    # só os dois grupos. Frases diferentes, porque o que dizer é diferente.
    if grupos.get("geral") is None:
        resultado["observacao"] = (
            "Turma pequena demais nesta prova: média da turma, top 15%, inferior 15%, "
            "posição e percentil vêm null para não expor a nota de colegas. Diga a "
            "nota e o deltaSelf, e que a turma ainda é pequena para comparar — sem "
            "estimar nenhum desses números."
        )
    elif grupos.get("top15") is None or grupos.get("bottom15") is None:
        resultado["observacao"] = (
            "O top 15% e o inferior 15% vêm null: com esta turma, cada grupo teria uma "
            "ou duas pessoas, e a média dele seria a nota de alguém. A média da turma, "
            "a posição e o percentil valem. Não estime os grupos."
        )
    return resultado


_SCHEMA_MEU_DESEMPENHO = {
    "name": "meu_desempenho_em_simulado",
    "description": (
        "Quando usar: o detalhe do aluno em UMA prova — nota, posição, percentil e a "
        "comparação com a média da turma, o top 15% e o inferior 15%; anexa o cartão "
        "da prova, que abre a ficha dela no app. Antes de chamar, confirme o "
        "simulado_id (de minhas_notas ou meu_panorama). Definições: geral, top15 e "
        "bottom15 são médias de grupo, nunca notas de colegas; deltaSelf é a nota "
        "menos a média das OUTRAS provas do próprio aluno — não é comparação com a "
        "turma. Com a turma pequena, geral, posicao e percentil vêm null (e os "
        "grupos também): diga que a turma é pequena demais para comparar, sem "
        "estimar. O cartão abre a ficha da prova, nunca um PDF. Exemplo: 'como fui "
        "no ITA P2?' → meu_desempenho_em_simulado → 'Você tirou [nota]; a média da "
        "turma foi [geral], e você ficou acima de [percentil]% dela. Contra a sua "
        "média nas outras provas: [deltaSelf].'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "simulado_id": {
                "type": "string",
                "description": "id (UUID) do simulado, vindo de minhas_notas ou meu_panorama.",
            },
        },
        "required": ["simulado_id"],
    },
}


# ─── minha_evolucao ───────────────────────────────────────────────────────

def minha_evolucao(cliente: Client, *, aluno_id: str) -> dict:
    """Séries por matéria ao longo dos ciclos (aluno × média da turma).

    O lado da turma já vem pelo piso de anonimato (`evolucao_do_aluno`); aqui
    só se diz ao modelo o que significa o `null` dele quando o aluno tem nota
    no mesmo ponto — sem a frase, "a turma não tem média" vira um número
    estimado.
    """
    evolucao = evolucao_do_aluno(cliente, aluno_id)
    materias = evolucao.get("materias") or {}
    evolucao["materias_disponiveis"] = sorted(materias.keys())
    sem_turma = any(
        a is not None and t is None
        for serie in materias.values()
        for a, t in zip(serie.get("aluno") or [], serie.get("turma") or [], strict=False)
    )
    if sem_turma:
        evolucao["observacao"] = (
            "turma null onde o aluno tem nota = não há média da turma para comparar "
            "ali (turma pequena demais, para não expor colegas). Diga isso, sem estimar."
        )
    return evolucao


_SCHEMA_MINHA_EVOLUCAO = {
    "name": "minha_evolucao",
    "description": (
        "Quando usar: tendência por matéria ao longo dos ciclos, comparada à média "
        "da turma — 'estou melhorando em física?'. Devolve, por matéria, a média do "
        "aluno e a da turma em cada ciclo. Antes de chamar, confirme: para as notas "
        "prova a prova, com gráfico, use minha_trajetoria. Definições: null num ciclo "
        "= o aluno não fez prova daquela matéria naquele ciclo; turma null com a nota "
        "do aluno no mesmo ciclo = turma pequena demais para comparar — diga isso, "
        "sem estimar. Exemplo: 'tô "
        "melhorando em química?' → minha_evolucao → 'Em Química você foi de [a] para "
        "[b] nos últimos ciclos; a turma, de [c] para [d].'"
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── meu_streak ───────────────────────────────────────────────────────────

def meu_streak(cliente: Client, *, aluno_id: str) -> dict:
    """Simulados consecutivos sem faltar — a sequência de GET /me/jogo.

    ⚠️ Mudou de significado em 05/09 (docs/36 §4). Antes eram "ciclos acima da
    média da turma", métrica relativa que premia posição e não progresso
    (docs/24 §1.1). O nome da tool ficou: renomeá-la quebraria as conversas em
    andamento, e o que o aluno pergunta ("qual minha sequência?") não mudou —
    mudou a resposta certa. A descrição abaixo é o que o LLM lê, e ela conta a
    métrica nova.
    """
    return sequencia_do_aluno(cliente, aluno_id)


_SCHEMA_MEU_STREAK = {
    "name": "meu_streak",
    "description": (
        "Quando usar: 'qual é a minha sequência?', 'quantos simulados seguidos eu "
        "fiz?'. Devolve quantos simulados seguidos o aluno fez sem faltar "
        "(`simulados`), o recorde dele no ano letivo (`melhor`) e a corrente do ciclo atual "
        "(`corrente`, um elo por simulado — presente=false é falta, presente=null é "
        "simulado que ainda vai acontecer). Antes de chamar, confirme: se "
        "meu_panorama já veio nesta conversa, a sequência está lá. Definições: é "
        "presença, não nota nem posição na turma. Exemplo: 'qual minha sequência?' → "
        "meu_streak → 'Você está em [n] simulados seguidos; seu recorde no ano é [m].'"
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── minhas_questoes_erradas ──────────────────────────────────────────────

def minhas_questoes_erradas(cliente: Client, *, aluno_id: str, simulado_id: str) -> dict:
    """Questões erradas/em branco reais do aluno num simulado (dados do Canvas)."""
    resultado = questoes_do_aluno_no_simulado(cliente, aluno_id, simulado_id)
    if "erro" in resultado:
        return resultado
    if not resultado.get("temGabarito"):
        return {"erro": "Este simulado não tem detalhe por questão (não é um quiz sincronizado)."}
    if not resultado.get("temMinhasRespostas"):
        return {"erro": "As respostas do aluno neste simulado ainda não foram sincronizadas."}

    para_revisar = [
        {
            "posicao": q["posicao"],
            "resultado": q["resultado"],
            "assunto": q["assunto"],
            "enunciadoResumo": q["textoResumo"],
            "alternativaMarcada": q["alternativaMarcada"],
            "alternativaCorreta": q["alternativaCorreta"],
        }
        for q in resultado["questoes"]
        if q["resultado"] in ("errada", "em_branco")
    ]
    return {
        "totalQuestoes": resultado["totalQuestoes"],
        "acertos": resultado["acertos"],
        "erros": resultado["erros"],
        "emBranco": resultado["emBranco"],
        "paraRevisar": para_revisar,
    }


_SCHEMA_MINHAS_QUESTOES = {
    "name": "minhas_questoes_erradas",
    "description": (
        "Quando usar: 'o que eu errei na prova?', 'o que devo revisar?'. Devolve as "
        "questões que o aluno errou ou deixou em branco num simulado, com o resumo do "
        "enunciado, a alternativa marcada e a correta. Antes de chamar, confirme o "
        "simulado_id (de minhas_notas ou meu_panorama). Definições: são questões do "
        "simulado do colégio, não do banco de provas passadas; assunto vazio é normal "
        "— não adivinhe o tema. Exemplo: 'o que eu errei no ITA P2?' → "
        "minhas_questoes_erradas → 'Você errou as questões [4, 9 e 12]…'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "simulado_id": {
                "type": "string",
                "description": "id (UUID) do simulado, vindo de minhas_notas ou meu_panorama.",
            },
        },
        "required": ["simulado_id"],
    },
}


# ─── meu_insight_do_ciclo ─────────────────────────────────────────────────

def meu_insight_do_ciclo(cliente: Client, *, aluno_id: str) -> dict:
    """Bullets de insight do ciclo mais recente (cacheados em insight_aluno_ciclo)."""
    resultado = payload_insight_ciclo(cliente, aluno_id)
    if resultado is None:
        return {"erro": "O aluno ainda não tem notas em nenhum ciclo."}
    ciclo, stats_payload = resultado

    nome_resp = cliente.table("aluno").select("nome").eq("id", aluno_id).limit(1).execute()
    nome = (nome_resp.data or [{}])[0].get("nome") or ""

    bullets = gerar_para_aluno_ciclo(
        cliente,
        aluno_id=aluno_id,
        ciclo_id=ciclo["id"],
        stats_payload=stats_payload,
        contexto={"nomeAluno": nome},
    )
    return {"ciclo": ciclo["nome"], "bullets": bullets, "estatisticas": stats_payload}


_SCHEMA_MEU_INSIGHT = {
    "name": "meu_insight_do_ciclo",
    "description": (
        "Quando usar: 'como foi meu ciclo?', 'me dá um resumo do ciclo'. Devolve um "
        "resumo do ciclo mais recente escrito por IA (bullets) e as estatísticas do "
        "aluno no ciclo — média própria e da turma, por matéria, contra o ciclo "
        "anterior. Antes de chamar, confirme: para 'como estou?' use meu_panorama. "
        "Definições: os bullets são texto de IA — confira com os números antes de "
        "repetir; ciclosAcimaDaMediaDaTurma NÃO é a sequência (essa é de meu_streak); "
        "mediaTurma null = turma pequena demais para comparar, sem estimar. "
        "Exemplo: 'como foi meu ciclo?' → meu_insight_do_ciclo."
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── Registry ─────────────────────────────────────────────────────────────

#: O catálogo do Tio Léo, na ordem em que o modelo o lê: a situação do aluno
#: primeiro — `meu_panorama` abre a lista, porque é a primeira chamada de
#: pergunta aberta (prompt_aluno.py) —, as provas no meio e o banco de questões
#: no fim.
TOOLS: list[tuple[dict, Callable]] = [
    *tools_aluno_situacao.TOOLS,
    (_SCHEMA_MINHAS_NOTAS, minhas_notas),
    (_SCHEMA_MEU_DESEMPENHO, meu_desempenho_em_simulado),
    (_SCHEMA_MINHAS_QUESTOES, minhas_questoes_erradas),
    (_SCHEMA_MINHA_EVOLUCAO, minha_evolucao),
    (_SCHEMA_MEU_STREAK, meu_streak),
    (_SCHEMA_MEU_INSIGHT, meu_insight_do_ciclo),
    *tools_aluno_banco.TOOLS,
]
