#!/usr/bin/env python3
"""Ingestão de planilha do Canvas — fora da requisição, de propósito.

Era `POST /uploads`. A rota foi aposentada em 03/09/2026 porque a medição em
produção mostrou zero uploads em toda a vida do sistema, e porque ela era um
segundo escritor sem arbitragem para `nota.presente` (docs/32 §2.4). O pipeline
em si não tem defeito nenhum — é como o projeto nasceu — e continua aqui como
plano B (Canvas fora do ar) e como caminho de carga histórica.

Mesma escolha de `banco-questoes/`: código que não roda em requisição vive como
script.

Uso:
    ./.venv/bin/python scripts/importar_planilha.py notas.xlsx
    ./.venv/bin/python scripts/importar_planilha.py notas.xlsx --autor "leo"

⚠️ Escreve em `nota` e `simulado`. O sync do Canvas é a fonte da verdade: o que
esta carga escrever em `pontuacao` entra como valor do Canvas e a próxima
rodada do sync pode sobrescrever. A edição do coordenador (`pontuacao_sas`)
sobrevive às duas — é o que a `0024` garante.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingest.pipeline import processar_planilha
from app.supabase_client import criar_cliente_supabase


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("planilha", type=Path, help="CSV ou XLSX exportado do Canvas.")
    ap.add_argument("--autor", default="script", help="Quem está rodando (vai para a auditoria).")
    args = ap.parse_args()

    if not args.planilha.is_file():
        print(f"não achei o arquivo: {args.planilha}", file=sys.stderr)
        return 1

    conteudo = args.planilha.read_bytes()
    if not conteudo:
        print("arquivo vazio", file=sys.stderr)
        return 1

    # Cliente novo, não o cacheado: é processo próprio, sem nada mais na conexão.
    cliente = criar_cliente_supabase()
    resultado = processar_planilha(
        cliente=cliente,
        arquivo_origem=args.planilha.name,
        conteudo=conteudo,
        caminho_storage=None,
        autor=args.autor,
    )
    print(resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
