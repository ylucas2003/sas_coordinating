"""Peças compartilhadas entre os scripts de captação externa que criam
`candidato_externo` a partir de `conquista_externa` — hoje
`resolver_candidatos_externos.py` e `separar_candidatos_externos.py`.

Existe porque os dois precisam da MESMA fórmula de "retrato" (nome/escola/
cidade/UF/série a partir de uma conquista) — divergir seria o tipo de bug
que só aparece bem depois, quando alguém notar que um candidato recém-criado
pelo resolver tem campo diferente de um candidato recém-separado.

Desde a simplificação de 25/09/2026 (docs/41), um `candidato_externo` nasce
sempre de UMA conquista só — nunca mais de um grupo (nome, escola) inteiro.
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
    `candidato_externo` criado 1:1 a partir dela deve ter. Mesma fórmula que
    `_serie_dominante` (`routes/captacao.py`) usa pra recalcular o retrato de
    um candidato depois de `mover_conquista` — aqui é sempre uma conquista
    só, porque cada candidato agora nasce de uma."""
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
