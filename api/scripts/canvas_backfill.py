#!/usr/bin/env python3
"""Backfill histórico do Canvas — popula o banco com todos os anos existentes.

Roda UMA vez (ou sob demanda, é idempotente — tudo upsert por chave natural).
Depois dele, o sync incremental de 5 min (POST /canvas-sync/run) mantém o
ano vigente atualizado.

Uso (a partir de api/):
    python -m scripts.canvas_backfill              → todos os anos encontrados
    python -m scripts.canvas_backfill --ano 2026   → restringe a um ano (teste)

Conexão: usa CANVAS_BASE_URL / CANVAS_API_TOKEN / SUPABASE_* do .env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.canvas_sync.cliente import ClienteCanvas          # noqa: E402
from app.canvas_sync.sincronizar import (                  # noqa: E402
    ResumoSincronizacao,
    sincronizar_ano_atual,
    sincronizar_historico_completo,
)
from app.config import get_settings                        # noqa: E402
from app.ingest.upsert import (                            # noqa: E402
    criar_execucao_sync,
    finalizar_execucao_sync,
)
from app.supabase_client import criar_cliente_supabase     # noqa: E402


async def _rodar(ano: str | None) -> ResumoSincronizacao:
    settings = get_settings()
    cliente = criar_cliente_supabase()
    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        if ano:
            # Um ano só: reusa a rotina do ano vigente com override do ano e
            # lookback de 10 anos (graded_since tão antigo que traz tudo).
            return await sincronizar_ano_atual(
                cliente=cliente,
                canvas=canvas,
                account_id=settings.canvas_account_id,
                override_ano=ano,
                lookback_minutos=60 * 24 * 365 * 10,
            )
        return await sincronizar_historico_completo(
            cliente=cliente,
            canvas=canvas,
            account_id=settings.canvas_account_id,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill histórico do Canvas.")
    parser.add_argument("--ano", help="Restringe a um ano específico (ex.: 2026).")
    args = parser.parse_args()

    cliente = criar_cliente_supabase()
    execucao_id = criar_execucao_sync(cliente, tipo="backfill")
    print(f"→ backfill iniciado (execucao {execucao_id})")
    t0 = time.monotonic()

    try:
        resumo = asyncio.run(_rodar(args.ano))
    except Exception as exc:
        finalizar_execucao_sync(
            cliente, execucao_id=execucao_id, status="erro", erro_mensagem=str(exc)
        )
        print(f"✗ backfill falhou após {time.monotonic() - t0:.0f}s: {exc}")
        sys.exit(1)

    finalizar_execucao_sync(
        cliente, execucao_id=execucao_id, status="sucesso", resumo=resumo.como_dict()
    )
    print(f"✓ backfill concluído em {time.monotonic() - t0:.0f}s")
    for chave, valor in resumo.como_dict().items():
        if chave == "avisos":
            continue
        print(f"    {chave}: {valor}")
    if resumo.avisos:
        print(f"    avisos ({len(resumo.avisos)}):")
        for aviso in resumo.avisos[:20]:
            print(f"      - {aviso}")
        if len(resumo.avisos) > 20:
            print(f"      ... e mais {len(resumo.avisos) - 20}")


if __name__ == "__main__":
    main()
