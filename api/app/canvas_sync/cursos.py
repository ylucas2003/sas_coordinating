"""Em que curso do Canvas mora um ciclo (docs/44 §3).

Cada série tem o próprio curso de provas: 577 no 3º, 578 no 1º e 579 no 2º, em
2026. `ano_letivo.canvas_course_id` só comporta um, e é o do 3º: por isso o 3º
continua lendo exatamente o campo de sempre, e só as outras séries passam por
`curso_canvas` (0078). Escrever uma nota do 1º ano no curso do 3º mandaria a
submission para um Assignment que não existe lá.
"""

from __future__ import annotations

from typing import Any

from ..ingest.upsert import SERIE_DO_CURSO_DE_SIMULADOS


def curso_do_ciclo(cliente: Any, ciclo: dict[str, Any]) -> str | None:
    """O `canvas_course_id` do ciclo, ou None se o sync ainda não o gravou.

    `ciclo` vem do embed de quem chama, com `serie`, `ano_letivo_id` e
    `ano_letivo(canvas_course_id)`. Sem `serie`, é do 3º: é o que todo ciclo era
    antes de a coluna existir.
    """
    serie = ciclo.get("serie") or SERIE_DO_CURSO_DE_SIMULADOS
    if serie == SERIE_DO_CURSO_DE_SIMULADOS:
        return (ciclo.get("ano_letivo") or {}).get("canvas_course_id")
    ano_letivo_id = ciclo.get("ano_letivo_id")
    if not ano_letivo_id:
        return None
    linhas = (
        cliente.table("curso_canvas")
        .select("canvas_course_id")
        .eq("ano_letivo_id", ano_letivo_id)
        .eq("serie", serie)
        .limit(1)
        .execute()
        .data
    )
    return linhas[0]["canvas_course_id"] if linhas else None
