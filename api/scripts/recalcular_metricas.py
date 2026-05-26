#!/usr/bin/env python3
"""Recalcula `metrica_simulado` pra todos os simulados válidos.

Use depois de aplicar a migration 0006 (que adicionou skewness, curtose,
p10, p90, moda, taxas, bimodal_flag em metrica_simulado). Sem rodar isto,
as colunas novas ficam NULL nas linhas existentes — o frontend já lida
com NULL (mostra "—"), mas o gráfico de comparação e os insights ficam
sem dados úteis.

Idempotente: pode rodar quantas vezes quiser. Cada execução faz upsert
sobre `(simulado_id, recorte_tipo, recorte_id)`, sobrescrevendo o cache.

Uso:
    cd api
    source .venv/bin/activate
    python -m scripts.recalcular_metricas
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _carregar_dotenv(caminho_env: Path) -> None:
    """Reaproveita a mesma lógica do migrate.py — evita dep extra."""
    if not caminho_env.exists():
        return
    for linha in caminho_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(chave, valor)


def main() -> int:
    # Carrega .env antes de importar qualquer coisa que use get_settings().
    dir_api = Path(__file__).resolve().parent.parent
    _carregar_dotenv(dir_api / ".env")

    # Log enxuto pro terminal — info do stats.metricas + erros.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    # Imports tardios pra .env já estar carregado.
    try:
        from app.stats.metricas import recalcular_tudo
        from app.supabase_client import criar_cliente_supabase
    except ImportError as exc:
        sys.exit(
            f"erro importando módulos da app: {exc}\n"
            "Você está rodando como módulo? `python -m scripts.recalcular_metricas` "
            "a partir de api/."
        )

    try:
        cliente = criar_cliente_supabase()
    except RuntimeError as exc:
        sys.exit(f"erro conectando ao Supabase: {exc}")

    print("Iniciando recálculo de métricas...")
    n = recalcular_tudo(cliente)
    print(f"\n✓ {n} simulados processados.")
    print("  Cada simulado gerou 1 linha 'geral' + 1 por turma + 1 por sede em metrica_simulado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
