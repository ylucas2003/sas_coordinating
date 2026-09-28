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
