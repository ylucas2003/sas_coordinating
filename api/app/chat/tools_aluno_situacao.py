"""Tools do Tio Léo sobre a situação do aluno: panorama, régua, agenda,
trajetória e a distribuição de uma prova (docs/43 §4.3).

Registradas por `tools_aluno.py`, que continua sendo a porta do escopo `aluno`
no registro (`ferramentas._montar_registro`). As convenções são as de lá: o
`aluno_id` vem do token, injetado pelo registro, e NENHUM schema o declara; só
leitura; dict de volta; erro de domínio como `{"erro": ...}`.

⚠️ Nenhuma regra mora aqui. A régua é de `stats/criterios.py` (via
`zona_do_aluno`), a falta é de `aluno_jornada`, o piso de anonimato é de
`aluno_dados` — o que as tools fazem é escolher o pedaço, recortar, dizer ao
modelo o que um `null` significa e anexar o cartão (docs/27 §7).

O cartão vai no campo ANINHADO `artefato: {tipo, titulo, payload}`, nunca com
`tipo` no topo — `meu_desempenho_em_simulado` usa o topo para o tipo do
simulado (`ferramentas.artefatos_do_resultado`). O payload é o que
`web/src/telas/Aluno/TioLeo/ArtefatoAluno.tsx` lê.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from supabase import Client

from ..banco.missao import hoje_na_escola
from ..stats import computavel, criterios
from ..stats.aluno_dados import (
    PISO_DE_ANONIMATO,
    detalhe_simulado_do_aluno,
    trajetoria_do_aluno,
    turma_acima_do_piso,
)
from ..stats.aluno_jornada import (
    dias_ate,
    historico_com_presenca,
    meta_do_ciclo_do_aluno,
    proximo_simulado_do_aluno,
)
from ..stats.aluno_panorama import panorama_do_aluno
from ..stats.aluno_zona import onboarding_completo, zona_do_aluno
from ..stats.metricas import carregar_metrica_geral
from ..stats.utils import como_float

#: Os nomes da tabela `materia` — o conjunto fechado semeado na migration 0001.
#: É o que a trajetória devolve em `materia`, e o filtro é igualdade sobre ele.
MATERIAS_DO_SAS = ("Matemática", "Física", "Química", "Português", "Inglês", "Redação")

# O que o modelo lê quando um pedaço vem vazio. Texto para o modelo, não regra:
# a regra que produziu o `null` está na função de domínio.
_SEM_ZONA = (
    "Ainda não há nota que conte para a régua: sem zona, sem distância e sem "
    "corte por matéria. Não estime nenhum deles."
)
_SO_FASE_1 = (
    "Sem nota de Fase 2 por matéria: a zona sai só da média, e não há corte por "
    "matéria para citar."
)
_REGUA_DO_COLEGIO = (
    "'Tio Leo' é a régua do colégio, que vale enquanto não há vestibular "
    "declarado. Diga isso: não é um vestibular."
)
_SEM_PROXIMO = (
    "Nenhum simulado com data marcada no sistema. É o normal: diga isso e não "
    "invente data."
)
_SEM_META = "Sem meta de ciclo: ainda não há simulado do aluno num ciclo com calendário."
_SEM_NOTAS = "O aluno ainda não tem prova feita com nota."
NAO_CONTAM = (
    "As provas em naoContam têm nota lançada que NÃO é desempenho (porQueNaoConta "
    "diz o motivo): não cite essa nota, não a compare nem a some com as outras. Se "
    "o aluno perguntar por ela, explique o motivo."
)

#: O motivo de `stats/computavel.py` em palavras, para o modelo. Motivo novo cai
#: no texto genérico, sem quebrar — o mesmo trato de `TEXTO_IGNORADA` na tabela
#: do ciclo (web/src/telas/CicloFicha/TabelaDoCiclo.tsx).
_POR_QUE_NAO_CONTA = {
    computavel.TODAS_EM_BRANCO: (
        "abriu a prova e não marcou nenhuma alternativa: provável ausência, não desempenho"
    ),
    computavel.ZERO_POR_FALTA_LANCADA: (
        "nesta prova o zero foi lançado para quem faltou: é falta, não desempenho"
    ),
}
_NAO_COMPUTAVEL = "o sistema tem evidência de que esta nota não é desempenho"
_PROVA_NAO_CONFIAVEL = "a coordenação marcou a prova inteira como não confiável"


def provas_que_nao_contam(itens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """As provas que `aluno_dados.conta_como_desempenho` deixou de fora, como o
    modelo as lê: o que é a prova e por que a nota não conta — sem o número.

    Quem decide que não conta é o domínio; aqui só se escolhe a frase.
    """
    saida = []
    for item in itens:
        if item.get("computavel") is False:
            motivo = _POR_QUE_NAO_CONTA.get(item.get("motivoNaoComputavel") or "", _NAO_COMPUTAVEL)
        else:
            motivo = _PROVA_NAO_CONFIAVEL
        saida.append(
            {
                "id": item.get("id"),
                "rotulo": item.get("rotulo"),
                "dataAplicacao": item.get("dataAplicacao"),
                "materia": item.get("materia"),
                "porQueNaoConta": motivo,
            }
        )
    return saida


def _virgula(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


# ─── O cartão das matérias contra o corte ────────────────────────────────


def _cartao_barras_corte(zona: dict[str, Any] | None) -> dict[str, Any] | None:
    """`barras_corte`, ou None quando não há barra para desenhar.

    A régua vai no título E no payload: o olho do cartão é fixo ("Suas notas
    contra o corte"), e um veredito sem o nome da régua é só a má notícia
    (docs/24 §2). Aluno só com Fase 1 tem `materias` vazia — sem cartão.
    """
    if not zona or not zona.get("materias"):
        return None
    regua = zona.get("regua") or ""
    return {
        "tipo": "barras_corte",
        "titulo": f"Régua {regua}".strip(),
        "payload": {"regua": regua, "materias": zona["materias"]},
    }


def _regua_sem_media(zona: dict[str, Any]) -> str:
    """O que dizer na régua que só tem mínimo por matéria (`reguaCobraMedia`
    falso, ex.: IME — Fase 2). Ali `distancia` e `corteProximaZona` vêm sempre
    `None`, e sem esta frase o modelo fica entre desobedecer a descrição
    ("nunca a zona sem a distância") e inventar uma — ele não conhece a margem.

    A margem é a do domínio (`criterios.MARGEM_CONFORTAVEL`), lida, não copiada:
    o "top" é a régua endurecida por ela em cada requisito.
    """
    margem = _virgula(criterios.MARGEM_CONFORTAVEL, 1)
    texto = (
        f"A régua {zona.get('regua') or ''} não cobra média, só o mínimo de cada "
        "matéria: distancia e corteProximaZona vêm null de propósito — não existe "
        "distância na média para dizer, e não invente uma. A folga é por matéria: o "
        f"top pede cada matéria pelo menos {margem} acima do corte dela."
    )
    menor = zona.get("materiaComMenosFolga")
    if menor and zona.get("zona") != "risco":
        texto += (
            f" A matéria com menos folga é {menor['materia']}, "
            f"{_virgula(menor['folga'])} acima do corte."
        )
    return texto


def _observacoes_da_zona(zona: dict[str, Any] | None) -> list[str]:
    if zona is None:
        return [_SEM_ZONA]
    saida = []
    # `reguaDoColegio` e `reguaCobraMedia` vêm de `zona_do_aluno`: quem
    # identifica a régua é o domínio, num lugar só, e o preâmbulo lê o mesmo.
    if zona.get("reguaDoColegio"):
        saida.append(_REGUA_DO_COLEGIO)
    if not zona.get("materias"):
        saida.append(_SO_FASE_1)
    if zona.get("reguaCobraMedia") is False:
        saida.append(_regua_sem_media(zona))
    return saida


# ─── meu_panorama ────────────────────────────────────────────────────────


def meu_panorama(cliente: Client, *, aluno_id: str, ultimas_notas: int = 5) -> dict:
    """A situação do aluno numa chamada (`stats/aluno_panorama.py`)."""
    panorama = panorama_do_aluno(
        cliente, aluno_id, ultimas_notas=min(10, max(1, ultimas_notas))
    )
    zona = panorama["zona"]
    nao_contam = panorama.pop("naoContam")
    observacoes = _observacoes_da_zona(zona)
    if not panorama["ultimasNotas"] and not nao_contam:
        observacoes.append(_SEM_NOTAS)
    if nao_contam:
        observacoes.append(NAO_CONTAM)
    if panorama["proximoSimulado"] is None:
        observacoes.append(_SEM_PROXIMO)
    if panorama["metaDoCiclo"] is None:
        observacoes.append(_SEM_META)

    resultado: dict[str, Any] = dict(panorama)
    # Só quando há: lista vazia é ruído para o modelo, e a observação acima já
    # diz quando há prova que não conta.
    if nao_contam:
        resultado["naoContam"] = provas_que_nao_contam(nao_contam)
    if observacoes:
        resultado["observacoes"] = observacoes
    cartao = _cartao_barras_corte(zona)
    if cartao is not None:
        resultado["artefato"] = cartao
    return resultado


_SCHEMA_MEU_PANORAMA = {
    "name": "meu_panorama",
    "description": (
        "Quando usar: PRIMEIRA chamada para pergunta aberta — 'como estou?', 'tô "
        "passando?', 'no que eu foco?'. Traz as últimas notas, a zona com régua e "
        "distância, a sequência, a meta do ciclo, o próximo simulado e os "
        "vestibulares-alvo, e anexa o cartão das matérias contra o corte. Antes de "
        "chamar, confirme: pergunta sobre UMA prova vai para "
        "meu_desempenho_em_simulado; se o panorama já veio nesta conversa, reuse. "
        "Definições: zona 'risco' = a régua corta hoje; 'cinzenta' = passa sem "
        "folga; 'top' = passa com folga. zona.media é a média que vale. distancia = "
        "quanto falta na média para a próxima zona; null no top, quando quem segura "
        "é uma matéria (materiaMaisCurta) e sempre na régua sem média "
        "(reguaCobraMedia=false), onde a folga é por matéria (materiaComMenosFolga). "
        "Diga a zona sempre com a régua e com a distância ou a matéria. naoContam = "
        "provas cuja nota não é desempenho: nunca as cite como nota. "
        "proximoSimulado null é normal: não invente data. Exemplo: 'como estou?' → "
        "meu_panorama → 'Zona cinzenta pela régua do colégio: média [m], faltam [d] "
        "para o top; [matéria] está abaixo do corte.'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ultimas_notas": {
                "type": "integer",
                "description": "Quantas provas recentes trazer, de 1 a 10. Padrão 5.",
            },
        },
        "required": [],
    },
}


# ─── minha_zona ──────────────────────────────────────────────────────────


def minha_zona(cliente: Client, *, aluno_id: str) -> dict:
    """GET /me/zona, com os alvos que decidiram a régua e o cartão."""
    zona = zona_do_aluno(cliente, aluno_id)
    if zona is None:
        return {"erro": _SEM_ZONA}
    resultado: dict[str, Any] = {
        **zona,
        # O mesmo `completo` de GET /me/vestibulares, pela mesma função.
        "onboardingCompleto": onboarding_completo(zona.get("vestibularesAlvo") or []),
    }
    observacoes = _observacoes_da_zona(zona)
    if observacoes:
        resultado["observacoes"] = observacoes
    cartao = _cartao_barras_corte(zona)
    if cartao is not None:
        resultado["artefato"] = cartao
    return resultado


_SCHEMA_MINHA_ZONA = {
    "name": "minha_zona",
    "description": (
        "Quando usar: pergunta só sobre corte, régua, zona ou vestibular-alvo — 'tô "
        "cortado em física?', 'quanto falta pra passar?', 'qual régua vale pra "
        "mim?'. Anexa o cartão das matérias contra o corte. Antes de chamar, "
        "confirme: se meu_panorama já veio nesta conversa, a zona já está lá. "
        "Definições: zonas como em meu_panorama. corteProximaZona = a linha de média "
        "que falta cruzar; corteAtual = a maior já cruzada. materias = notas de "
        "Fase 2 contra o corte DAQUELA matéria; eliminatoria=true reprova sozinha. "
        "reguaCobraMedia=false (ex.: IME — Fase 2): régua só de mínimo por "
        "matéria — distancia e corteProximaZona vêm null de propósito; diga a "
        "matéria com menos folga (materiaComMenosFolga), nunca uma distância na "
        "média. reguaDoColegio=true: é a régua do colégio ('Tio Leo'), que vale sem "
        "vestibular declarado — diga isso. Quem mira ITA e IME é avaliado pelas "
        "duas, e vale o pior veredito. Exemplo: 'quanto falta pra sair do risco?' → "
        "minha_zona → 'Pela régua [régua] você está em risco: média [m], faltam [d] "
        "para [corte].'"
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── minha_agenda_do_ciclo ───────────────────────────────────────────────


def minha_agenda_do_ciclo(cliente: Client, *, aluno_id: str) -> dict:
    """GET /me/agenda e GET /me/meta numa chamada, contadas no dia da escola."""
    hoje = hoje_na_escola()
    # Lido uma vez para as duas: sem isto, agenda e meta releriam as notas.
    historico = historico_com_presenca(cliente, aluno_id)
    proximo = proximo_simulado_do_aluno(cliente, aluno_id, historico=historico, hoje=hoje)
    meta = meta_do_ciclo_do_aluno(cliente, aluno_id, historico=historico)

    resultado: dict[str, Any] = {
        "hoje": hoje.isoformat(),
        "proximoSimulado": proximo,
        "diasAteOProximo": dias_ate(proximo.get("data"), hoje) if proximo else None,
        "metaDoCiclo": meta,
    }
    observacoes = []
    if proximo is None:
        observacoes.append(_SEM_PROXIMO)
    if meta is None:
        observacoes.append(_SEM_META)
    if observacoes:
        resultado["observacoes"] = observacoes
    return resultado


_SCHEMA_MINHA_AGENDA = {
    "name": "minha_agenda_do_ciclo",
    "description": (
        "Quando usar: 'quando é o próximo simulado?', 'quantos dias faltam pra "
        "prova?', 'qual é a minha meta do ciclo?'. Devolve o próximo simulado "
        "marcado, os dias até ele e a meta de presença do ciclo. Antes de chamar, "
        "confirme: se meu_panorama já veio nesta conversa, os dois dados já estão "
        "lá. Definições: proximoSimulado null é comum e não é erro — nada marcado no "
        "sistema; diga isso e não invente data. diasAteOProximo é contado no dia da "
        "escola. metaDoCiclo é PRESENÇA (feitos de alvo simulados do ciclo) — não "
        "existe meta de nota nem de XP. Exemplo: 'quando é a próxima prova?' → "
        "minha_agenda_do_ciclo → 'O próximo é o [rótulo], em [data] — daqui a [n] "
        "dias.'"
    ),
    "parameters": {"type": "object", "properties": {}, "required": []},
}


# ─── minha_trajetoria ────────────────────────────────────────────────────

LIMITE_DA_TRAJETORIA = 60


def minha_trajetoria(
    cliente: Client, *, aluno_id: str, materia: str | None = None, limite: int = 40
) -> dict:
    """As notas do aluno em ordem de data (`aluno_dados.trajetoria_do_aluno`).

    O filtro de matéria vem ANTES do corte: `trajetoria_do_aluno` guarda as mais
    recentes de todas as matérias, e cortar primeiro deixaria a matéria pedida
    com menos pontos do que tem.
    """
    limite = min(LIMITE_DA_TRAJETORIA, max(1, limite))
    pontos = trajetoria_do_aluno(cliente, aluno_id)
    disponiveis = sorted({p["materia"] for p in pontos if p.get("materia")})
    if materia:
        pontos = [p for p in pontos if p.get("materia") == materia]
    pontos = pontos[-limite:]

    resultado: dict[str, Any] = {
        "materia": materia,
        "total": len(pontos),
        "trajetoria": [
            {
                "simuladoId": p["simuladoId"],
                "rotulo": p.get("rotuloCurto") or p.get("simulado"),
                "dataAplicacao": p.get("dataAplicacao"),
                "materia": p.get("materia"),
                "tipo": p.get("tipo"),
                "nota": p["nota"],
            }
            for p in pontos
        ],
        "materiasDisponiveis": disponiveis,
    }
    # Uma linha precisa de dois pontos; com um só, o gráfico seria um ponto
    # solto que não mostra evolução nenhuma.
    if len(pontos) >= 2:
        resultado["artefato"] = {
            "tipo": "linha_temporal",
            "titulo": f"Sua trajetória — {materia or 'todas as matérias'}",
            "payload": {
                "pontos": [
                    {
                        "simuladoId": p["simuladoId"],
                        "rotulo": p.get("rotuloCurto") or p.get("simulado") or "",
                        "data": p.get("dataAplicacao"),
                        "nota": p["nota"],
                        "materia": p.get("materia"),
                    }
                    for p in pontos
                ]
            },
        }
    elif not pontos:
        resultado["observacao"] = (
            f"Nenhuma prova de {materia} que conte." if materia else _SEM_NOTAS
        )
    return resultado


_SCHEMA_MINHA_TRAJETORIA = {
    "name": "minha_trajetoria",
    "description": (
        "Quando usar: 'me mostra minha evolução em física', 'como foram minhas notas "
        "desde março?'. Devolve as notas do aluno em ordem de data (0–10), com a "
        "matéria, e anexa o gráfico de linha. Antes de chamar, confirme a matéria: "
        "sem ela o gráfico mistura matérias e sobe e desce sem significar nada — use "
        "a da conversa ou pergunte. Para a média por ciclo comparada à turma, use "
        "minha_evolucao. Definições: só provas que o aluno fez e que contam como "
        "desempenho; não há média da turma aqui. Exemplo: 'como evoluí em química?' "
        "→ minha_trajetoria(materia='Química') → 'Suas [n] provas de Química foram "
        "de [mín] a [máx]; a última foi [nota].'"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "materia": {
                "type": "string",
                "enum": list(MATERIAS_DO_SAS),
                "description": "Só as notas desta matéria. Omitida, traz todas.",
            },
            "limite": {
                "type": "integer",
                "description": "Quantas notas, as mais recentes, de 1 a 60. Padrão 40.",
            },
        },
        "required": [],
    },
}


# ─── distribuicao_do_simulado ────────────────────────────────────────────


def _inteiro(valor: Any) -> int | None:
    numero = como_float(valor)
    return int(numero) if numero is not None else None


def _duas_casas(valor: Any) -> float | None:
    numero = como_float(valor)
    return round(numero, 2) if numero is not None else None


def distribuicao_do_simulado(cliente: Client, *, aluno_id: str, simulado_id: str) -> dict:
    """O histograma da turma numa prova que o aluno fez, com a nota dele.

    `detalhe_simulado_do_aluno` é a GUARDA — prova sem nota válida do aluno
    volta erro, a mesma de GET /me/simulado/{id} — e dá a nota e o percentil
    dele; a distribuição é a linha geral de `metrica_simulado`, a mesma do
    histograma da coordenação. Abaixo do piso de anonimato, nada sai.
    """
    detalhe = detalhe_simulado_do_aluno(cliente, aluno_id, simulado_id)
    if "erro" in detalhe:
        return detalhe
    metrica = carregar_metrica_geral(cliente, simulado_id)
    if not metrica or not metrica.get("histograma"):
        return {"erro": "A distribuição da turma nesta prova ainda não foi calculada."}
    presentes = _inteiro(metrica.get("n_presentes"))
    # Duas contagens, e as duas passam pelo piso: a da métrica, de onde sai o
    # histograma, e a da ficha (`detalhe["total"]`, as notas de agora), de onde
    # sai o percentil. Métrica calculada antes de uma nota sair deixaria o
    # histograma passar com o percentil já `None` pelo piso da ficha — e o
    # modelo leria um percentil nulo sem frase nenhuma que o explique.
    if not (turma_acima_do_piso(presentes) and turma_acima_do_piso(detalhe.get("total"))):
        return {
            "erro": (
                f"Menos de {PISO_DE_ANONIMATO} alunos têm nota nesta prova: a "
                "distribuição mostraria a nota de colegas, e por isso não sai. Diga "
                "isso ao aluno — a nota dele está em meu_desempenho_em_simulado."
            )
        }

    rotulo = detalhe.get("rotulo") or "simulado"
    media = _duas_casas(metrica.get("media"))
    mediana = _duas_casas(metrica.get("mediana"))
    return {
        "simuladoId": detalhe["id"],
        "rotulo": rotulo,
        "minhaNota": detalhe["nota"],
        "percentil": detalhe["percentil"],
        "media": media,
        "mediana": mediana,
        "nPresentes": presentes,
        "artefato": {
            "tipo": "histograma",
            "titulo": f"Distribuição da turma — {rotulo}",
            "payload": {
                "histograma": metrica["histograma"],
                "media": media,
                "mediana": mediana,
                "nPresentes": presentes,
                # A marca do PRÓPRIO aluno (docs/27 §7), tirada do aluno_id do
                # token pelo detalhe — nunca de argumento.
                "minhaNota": detalhe["nota"],
            },
        },
    }


_SCHEMA_DISTRIBUICAO = {
    "name": "distribuicao_do_simulado",
    "description": (
        "Quando usar: 'como a turma foi nessa prova?', 'fui melhor que a maioria?', "
        "'me mostra o gráfico da prova'. Devolve a distribuição de notas da turma "
        "num simulado que o aluno FEZ, com a nota dele, e anexa o histograma. Antes "
        "de chamar, confirme o simulado_id (de minhas_notas ou meu_panorama). "
        "Definições: só agregados — média, mediana, presentes e quantos caíram em "
        "cada faixa de 0,5; nunca a nota nem o nome de um colega. percentil = parte "
        f"da turma que ficou abaixo do aluno. Prova com menos de {PISO_DE_ANONIMATO} "
        "notas não tem distribuição: diga isso. Exemplo: 'fui bem no ITA P2?' → "
        "distribuicao_do_simulado → 'Você tirou [nota]; a mediana foi [mediana] entre "
        "[n] presentes.'"
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


# ─── As tools deste módulo ───────────────────────────────────────────────

TOOLS: list[tuple[dict, Callable]] = [
    (_SCHEMA_MEU_PANORAMA, meu_panorama),
    (_SCHEMA_MINHA_ZONA, minha_zona),
    (_SCHEMA_MINHA_AGENDA, minha_agenda_do_ciclo),
    (_SCHEMA_MINHA_TRAJETORIA, minha_trajetoria),
    (_SCHEMA_DISTRIBUICAO, distribuicao_do_simulado),
]
