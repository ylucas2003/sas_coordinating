#!/usr/bin/env python3
"""Aplica retroativamente a regra "zero em 2+ provas no mesmo dia = ausência".

A regra vive no ingest (api/app/ingest/pipeline.py) e barra esses zeros já
na entrada. Mas dados que entraram ANTES dessa regra existir continuam com
`presente=true, pontuacao=0` no banco. Este script encontra esses casos e
flipa pra `presente=false, pontuacao=null`.

Critério (mesmo do ingest):
  - Para cada (aluno_id, data_aplicacao), conta quantos zeros há.
  - Se forem 2 ou mais → reclassifica TODOS como ausência.

Uso (rode em api/, com .venv ativo):
    python -m scripts.limpar_zeros_provaveis_ausencias            # DRY-RUN
    python -m scripts.limpar_zeros_provaveis_ausencias --aplicar  # aplica

Depois de aplicar, rode `python -m scripts.recalcular_metricas`.

Implementação: usa o Supabase REST (mesma credencial do resto do backend).
Separa em duas queries simples — primeiro carrega o mapa de simulados, depois
busca notas zero sem join. Versão anterior tentava embedded resource + filtro
e o PostgREST travava.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path


def _carregar_dotenv(caminho_env: Path) -> None:
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
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--aplicar", action="store_true", help="Aplica UPDATEs (sem essa flag, só preview).")
    args = parser.parse_args()

    dir_api = Path(__file__).resolve().parent.parent
    _carregar_dotenv(dir_api / ".env")

    try:
        from app.supabase_client import criar_cliente_supabase
    except ImportError as exc:
        sys.exit(f"erro importando app: {exc}")

    try:
        cliente = criar_cliente_supabase()
    except RuntimeError as exc:
        sys.exit(f"erro conectando ao Supabase: {exc}")

    # ── (1) Carrega mapa {simulado_id: data_aplicacao} ──
    print("Carregando simulados...")
    resp = cliente.table("simulado").select("id, data_aplicacao").execute()
    data_por_simulado: dict[str, str] = {
        s["id"]: s["data_aplicacao"] for s in (resp.data or []) if s.get("data_aplicacao")
    }
    print(f"  → {len(data_por_simulado)} simulados em cache.")

    # ── (2) Busca notas zero, paginando ──
    # Sem join, sem range explícito — só os 3 campos necessários, paginando manualmente.
    print("Buscando notas com pontuacao=0 e presente=true...")
    zeros: list[tuple[str, str]] = []  # (aluno_id, simulado_id)
    pagina = 0
    tamanho = 1000
    while True:
        resp = (
            cliente.table("nota")
            .select("aluno_id, simulado_id")
            .eq("presente", True)
            .eq("pontuacao", 0)
            .range(pagina * tamanho, (pagina + 1) * tamanho - 1)
            .execute()
        )
        linhas = resp.data or []
        if not linhas:
            break
        zeros.extend((linha["aluno_id"], linha["simulado_id"]) for linha in linhas)
        if len(linhas) < tamanho:
            break
        pagina += 1
        print(f"  → {len(zeros)} até agora...")

    print(f"  → {len(zeros)} notas zero encontradas.")

    if not zeros:
        print("✓ Nada a fazer.")
        return 0

    # ── (3) Agrupa por (aluno_id, data_aplicacao) ──
    por_aluno_e_data: dict[tuple[str, str], list[str]] = defaultdict(list)
    sem_data = 0
    for aluno_id, simulado_id in zeros:
        data = data_por_simulado.get(simulado_id)
        if not data:
            sem_data += 1
            continue
        por_aluno_e_data[(aluno_id, data)].append(simulado_id)

    if sem_data:
        print(f"  ⚠ {sem_data} notas têm simulado_id sem data_aplicacao no mapa (ignoradas).")

    # ── (4) Filtra grupos com 2+ ──
    grupos = {chave: sims for chave, sims in por_aluno_e_data.items() if len(sims) >= 2}
    total_notas = sum(len(v) for v in grupos.values())

    print(f"  → {len(grupos)} (aluno × dia) com 2+ zeros")
    print(f"  → {total_notas} notas seriam reclassificadas como ausência")

    if grupos:
        print("\nExemplos (5 primeiros):")
        for i, ((aluno_id, data), sims) in enumerate(grupos.items()):
            if i >= 5:
                break
            print(f"  aluno {aluno_id[:8]}…  data {data}  → {len(sims)} zeros")

    if not args.aplicar:
        print("\n— DRY-RUN. Pra aplicar, rode com --aplicar.")
        return 0

    # ── (5) Aplica: UPDATE em lote por aluno ──
    print(f"\nAplicando UPDATEs em {len(grupos)} alunos...")
    n_aplicados = 0
    for i, ((aluno_id, _data), simulado_ids) in enumerate(grupos.items(), 1):
        (
            cliente.table("nota")
            .update({"pontuacao": None, "presente": False})
            .eq("aluno_id", aluno_id)
            .in_("simulado_id", simulado_ids)
            .execute()
        )
        n_aplicados += len(simulado_ids)
        if i % 50 == 0:
            print(f"  → {i}/{len(grupos)} processados ({n_aplicados} notas)...")

    print(f"\n✓ {n_aplicados} notas reclassificadas como ausência.")
    print("\nPróximo passo: `python -m scripts.recalcular_metricas` pra atualizar as estatísticas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
