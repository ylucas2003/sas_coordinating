"""Peças compartilhadas entre os scripts de captação externa que criam ou
reagrupam `candidato_externo` a partir de `conquista_externa` — hoje
`resolver_candidatos_externos.py`, `separar_candidatos_externos.py` e
`unificar_candidatos_externos.py` — e também `routes/captacao.py`
(`mover_conquista`), que precisa da mesma fórmula depois de um arraste.

Existe porque todos precisam da MESMA fórmula de "retrato" (nome/escola/
cidade/UF/série) — divergir seria o tipo de bug que só aparece bem depois,
quando alguém notar que um candidato ganhou campo diferente dependendo de
qual caminho escreveu nele.

Ajuste de 28/09/2026 (docs/41 §16): o DEFAULT voltou a ser 1
`candidato_externo` por NOME (não mais 1 por conquista, como na simplificação
de 25/09/2026) — `resolver_candidatos_externos.py` anexa conquista nova ao
perfil já existente do nome, em vez de sempre criar um novo. Isso NÃO
reintroduz o bug de 25/09 (um nome "decidido" que sumia pra sempre): não há
tabela de decisão nenhuma, a lista geral (`v_candidato_externo_por_nome`)
sempre mostra todo nome incondicional, e separar continua manual e reversível
a qualquer momento (`criar_perfil`/`mover_conquista` em `CaptacaoPerfil.tsx`).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def normalizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


# ─── Faixa: o que uma conquista VALE, comparável entre provas (docs/41 §20) ──
#
# `conquista_externa.resultado` continua cru (0056: "cada prova tem seu próprio
# vocabulário — não normalizamos aqui"): a OBF escreve "MEDALHA DE OURO", a
# OBMEP "Ouro — rede pública", a OBI "Ouro". Sem uma tradução comum não dá pra
# perguntar "quem tirou ouro?" atravessando provas — é o que a busca por
# conquista (o caminho inverso, conquista → candidato) precisa. A faixa é essa
# tradução, gravada ao lado do texto cru, nunca no lugar dele.
#
# Duas escadas, porque olimpíada e vestibular não medem a mesma coisa:
#   olimpíada   ouro > prata > bronze > mencao > finalista
#   vestibular  aprovado > classificado_final > passou_de_fase > participou > ausente
#
# `classificado_final` = passou em todas as provas, mas a fonte não confirma
# vaga (excedente do IME, reserva da EFOMM/Escola Naval, a classificação da
# 2ª fase do ITA 2020-2023, que vai além do nº de vagas). É o lead típico de
# pré-vestibular: chegou até o fim e (provavelmente) não entrou.
FAIXAS_OLIMPIADA = ("ouro", "prata", "bronze", "mencao", "finalista")
FAIXAS_VESTIBULAR = ("aprovado", "classificado_final", "passou_de_fase", "participou", "ausente")
FAIXAS = FAIXAS_OLIMPIADA + FAIXAS_VESTIBULAR

# Ter feito (ou faltado) a 1ª fase do ITA não é destaque nenhum — fica no banco
# como dado, mas sai da contagem de conquistas e da ordenação da lista
# (decisão de 07/10/2026, docs/41 §20). Mesma lista no FILTER da migration 0068.
FAIXAS_SO_PARTICIPACAO = ("participou", "ausente")

_MEDALHAS: list[tuple[str, str]] = [
    (r"^(MEDALHA DE )?OURO\b", "ouro"),  # "OURO REDE PUBLICA", "OURO ESPECIAL", "MEDALHA DE OURO"
    (r"^(MEDALHA DE )?PRATA\b", "prata"),
    (r"^(MEDALHA DE )?BRONZE\b", "bronze"),
    (r"^MENCAO HONROSA$", "mencao"),
]

# Por PROVA, e não uma lista global: "RESERVA" é carreira militar no ITA/IME
# (aprovado) e lista de espera na EFOMM/Escola Naval — o mesmo texto vale
# coisas diferentes conforme quem publicou. Regex sobre o texto normalizado
# (`normalizar_nome`: maiúsculo, sem acento, "—" some, "1ª" vira "1A").
_REGRAS_POR_PROVA: dict[str, list[tuple[str, str]]] = {
    "OBMEP": _MEDALHAS,
    "OBM": _MEDALHAS,
    "OBF": _MEDALHAS,
    "OBI": _MEDALHAS,
    "OBQ": [*_MEDALHAS, (r"^DEMAIS CLASSIFICADOS$", "finalista")],
    "OBQ Jr": [*_MEDALHAS, (r"^DEMAIS CLASSIFICADOS$", "finalista")],
    "ITA": [
        (r"^AUSENTE 1A FASE$", "ausente"),
        (r"^REALIZOU A 1A FASE$", "participou"),
        (r"^CONVOCADO 2A FASE$", "passou_de_fase"),
        (r"^NAO CLASSIFICADO 2A FASE$", "passou_de_fase"),
        (r"^CLASSIFICADO 2A FASE \(NO \d+\)$", "classificado_final"),
        # Convocados pra 3ª fase (2024-2025): o título da seção, sem tradução.
        (r"^((ATIVA|RESERVA) \()?(AMPLA CONCORRENCIA|COTA RACIAL)\)?$", "aprovado"),
    ],
    "IME": [
        (r"^HABILITADO 2A FASE \((ATIVA|RESERVA)\)$", "passou_de_fase"),
        (r"^NAO APROVADO 2A FASE\b", "passou_de_fase"),
        (r"^(ATIVA|RESERVA) EXCEDENTE$", "classificado_final"),
        (r"^(ATIVA|RESERVA)( AMPLA CONCORRENCIA| LEI 12\.990 \(COTA RACIAL\))?$", "aprovado"),
    ],
    "EFOMM": [
        (r"^(CIAGA|CIABA) (POS-)?CLASSIFICADO \(.*1A FASE\)$", "passou_de_fase"),
        (r"^(CIAGA|CIABA) TITULAR \(CLASSIFICACAO FINAL\)$", "aprovado"),
        (r"^(CIAGA|CIABA) RESERVA \(CLASSIFICACAO FINAL\)$", "classificado_final"),
    ],
    "Escola Naval (CPAEN)": [
        (r"^NAO ELIMINADO NAS PROVAS ESCRITAS\b", "passou_de_fase"),
        (r"^RESULTADO DA SELECAO INICIAL (TITULAR|RESERVA)$", "passou_de_fase"),
        (r"^RESULTADO FINAL( DA SELECAO)? TITULAR$", "aprovado"),
        (r"^RESULTADO FINAL( DA SELECAO)? RESERVA$", "classificado_final"),
    ],
}


def classificar_faixa(prova_nome: str, resultado: str) -> str:
    """A faixa de uma conquista. **Falha alto** quando não reconhece — prova
    sem régua, ou um texto de resultado que a régua da prova não cobre — em vez
    de devolver um "desconhecido" silencioso: é a lição que cada fonte nova do
    docs/41 ensinou de novo (contagem que não bate vira vazio, sem erro). O
    importador valida o lote inteiro antes de gravar qualquer linha."""
    regras = _REGRAS_POR_PROVA.get(prova_nome)
    if regras is None:
        raise ValueError(f"prova {prova_nome!r} sem régua de faixa em _captacao_comum.py")
    texto = normalizar_nome(resultado)
    for padrao, faixa in regras:
        if re.search(padrao, texto):
            return faixa
    raise ValueError(f"resultado {resultado!r} da prova {prova_nome!r} não casa com nenhuma faixa")


def retrato_da_conquista(conquista: dict[str, Any]) -> dict[str, Any]:
    """O retrato (nome/escola/cidade/UF/série) de UMA conquista — o que um
    `candidato_externo` criado a partir dela deve ter quando ela é a única
    (perfil novo, nome nunca visto). Caso especial de `retrato_dominante`
    com uma lista de um item só."""
    return {
        "nome": conquista["nome_informado"],
        "nome_normalizado": normalizar_nome(conquista["nome_informado"]),
        "escola": conquista.get("escola_informada"),
        "cidade": conquista.get("cidade_informada"),
        "uf": conquista.get("uf_informada"),
        "serie_referencia_min": conquista.get("serie_referencia_min"),
        "serie_referencia_max": conquista.get("serie_referencia_max"),
        "ano_referencia_serie": conquista["ano"],
    }


def retrato_dominante(conquistas: list[dict[str, Any]]) -> dict[str, Any]:
    """O retrato (nome/escola/cidade/UF/série) da conquista mais RECENTE
    entre as de um candidato — usado toda vez que um `candidato_externo`
    passa a ter (ou continua tendo) mais de uma conquista: depois de
    `mover_conquista`, depois do resolver anexar uma conquista nova a um
    perfil existente, ou depois de `unificar_candidatos_externos.py` juntar
    perfis. Sem isso o retrato ficaria preso ao ano em que o perfil nasceu."""
    mais_recente = max(conquistas, key=lambda c: c["ano"])
    return {
        "nome": mais_recente["nome_informado"],
        "escola": mais_recente.get("escola_informada"),
        "cidade": mais_recente.get("cidade_informada"),
        "uf": mais_recente.get("uf_informada"),
        "serie_referencia_min": mais_recente.get("serie_referencia_min"),
        "serie_referencia_max": mais_recente.get("serie_referencia_max"),
        "ano_referencia_serie": mais_recente["ano"],
    }
