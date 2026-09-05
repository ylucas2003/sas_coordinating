#!/usr/bin/env python3
"""Backfill do arquivo (PDF) da prova de cada simulado (Fase 3 do Canvas sync).

Varre todos os simulados já aplicados sem `arquivo_storage_path` e casa cada
um contra os Course Files do curso "Simulados" (pasta por ciclo, nome
`P{n} - {MATÉRIA(S)} (...)`) — mesma lógica de app/canvas_sync/arquivos.py.
O sync incremental de 5 min só baixa um punhado por rodada
(MAX_ARQUIVOS_PENDENTES_POR_RODADA); este script zera o backlog de uma vez.

Uso (a partir de api/):
    python -m scripts.canvas_backfill_arquivos                → todos os anos
    python -m scripts.canvas_backfill_arquivos --ano 2026     → um ano
    python -m scripts.canvas_backfill_arquivos --forcar       → refaz até os já sincronizados

Conexão: usa CANVAS_BASE_URL / CANVAS_API_TOKEN / SUPABASE_* do .env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from datetime import date
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.canvas_sync.arquivos import sincronizar_arquivos_do_curso  # noqa: E402
from app.canvas_sync.cliente import ClienteCanvas  # noqa: E402
from app.canvas_sync.sincronizar import _descobrir_cursos_simulados  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.supabase_client import criar_cliente_supabase  # noqa: E402


def _em_lotes(itens: list, tamanho: int):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


async def _simulados_pendentes_do_curso(
    canvas: ClienteCanvas, cliente, course_id: str, *, forcar: bool
) -> list[dict[str, Any]]:
    """Simulados do banco (deste curso, já aplicados) sem arquivo — ou todos,
    com --forcar."""
    assignments = await canvas.listar_assignments(course_id)
    external_ids = [str(a["id"]) for a in assignments]
    hoje = date.today().isoformat()

    brutos: list[dict[str, Any]] = []
    for lote in _em_lotes(external_ids, 100):
        q = (
            cliente.table("simulado")
            .select("id, rotulo_curto, data_aplicacao, arquivo_storage_path, ciclo(ordem), materia(codigo)")
            .in_("external_id", lote)
            .not_.is_("rotulo_curto", "null")
            .not_.is_("materia_id", "null")
            .lte("data_aplicacao", hoje)
        )
        resp = q.execute()
        brutos.extend(resp.data or [])

    if not forcar:
        brutos = [s for s in brutos if not s.get("arquivo_storage_path")]

    pendentes = [
        {
            "id": s["id"],
            "ciclo_ordem": (s.get("ciclo") or {}).get("ordem"),
            "rotulo_curto": s["rotulo_curto"],
            "materia_codigo": (s.get("materia") or {}).get("codigo"),
        }
        for s in brutos
    ]
    return [p for p in pendentes if p["ciclo_ordem"] is not None and p["materia_codigo"]]


async def _rodar(ano: str | None, forcar: bool) -> None:
    settings = get_settings()
    cliente = criar_cliente_supabase()

    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        cursos = await _descobrir_cursos_simulados(canvas, settings.canvas_account_id)
        if ano:
            cursos = [(a, c) for a, c in cursos if a == int(ano)]
        if not cursos:
            print("Nenhum curso de simulados encontrado para o filtro dado.")
            sys.exit(1)

        total_arquivos = 0
        total_simulados = 0

        for ano_curso, curso in cursos:
            course_id = str(curso["id"])
            print(f"\n═══ {ano_curso} — {curso.get('name')} (curso {course_id}) ═══")

            pendentes = await _simulados_pendentes_do_curso(
                canvas, cliente, course_id, forcar=forcar
            )
            if not pendentes:
                print("  nada a sincronizar (use --forcar para refazer).")
                continue
            print(f"  {len(pendentes)} simulados pendentes de arquivo")

            resultado = await sincronizar_arquivos_do_curso(
                cliente, canvas, course_id=course_id,
                simulados_pendentes=pendentes, limite_arquivos=None,
            )
            print(
                f"  ✓ {resultado['arquivos_baixados']} arquivos baixados, "
                f"{resultado['simulados_atualizados']} simulados atualizados"
            )
            for aviso in resultado["avisos"]:
                print(f"  ! {aviso}")

            total_arquivos += resultado["arquivos_baixados"]
            total_simulados += resultado["simulados_atualizados"]

        print(
            f"\n✓ backfill de arquivos: {total_arquivos} arquivos, "
            f"{total_simulados} simulados atualizados"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill dos arquivos (PDF) dos simulados do Canvas.")
    parser.add_argument("--ano", help="Restringe a um ano específico (ex.: 2026).")
    parser.add_argument("--forcar", action="store_true",
                        help="Refaz também simulados já com arquivo sincronizado.")
    args = parser.parse_args()

    t0 = time.monotonic()
    asyncio.run(_rodar(args.ano, args.forcar))
    print(f"  ({time.monotonic() - t0:.0f}s)")


if __name__ == "__main__":
    main()
