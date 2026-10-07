#!/usr/bin/env python3
"""Preenche `conquista_externa.faixa` (migration 0068, docs/41 §20) com a
régua de `scripts/_captacao_comum.py::classificar_faixa` — a única régua.

Uso:
    ./.venv/bin/python scripts/classificar_conquistas_externas.py --simular
    ./.venv/bin/python scripts/classificar_conquistas_externas.py

Roda uma vez depois da 0068 (as linhas antigas nascem com faixa NULL) e de
novo sempre que a régua mudar: reclassifica TODA linha cuja faixa gravada
difere da que a régua dá hoje, não só as NULL. Idempotente — a segunda rodada
não acha nada pra mudar. O importador já grava a faixa de quem chega depois.

A faixa só depende de (prova, resultado), então a escrita é um UPDATE por
par distinto (~400 hoje), não um por linha (166 mil).

Falha alto, antes de escrever qualquer coisa, se algum resultado não casar
com a régua — mesma lição de cada fonte do docs/41: silêncio vira dado
errado, erro vira conserto.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase
from scripts._captacao_comum import classificar_faixa


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--simular", action="store_true", help="Só conta o que mudaria, sem escrever.")
    args = ap.parse_args()

    cliente = criar_cliente_supabase()
    nome_da_prova = {
        p["id"]: p["nome"] for p in cliente.table("prova_externa").select("id, nome").execute().data or []
    }
    linhas = cliente.table("conquista_externa").select("prova_id, resultado, faixa").execute().data or []
    print(f"{len(linhas)} conquista_externa lidas", file=sys.stderr)

    # (prova_id, resultado) -> Counter(faixa gravada hoje)
    gravadas: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for linha in linhas:
        gravadas[(linha["prova_id"], linha["resultado"])][linha["faixa"]] += 1

    alvo: dict[tuple[str, str], str] = {}
    erros: list[str] = []
    for prova_id, resultado in gravadas:
        try:
            alvo[(prova_id, resultado)] = classificar_faixa(nome_da_prova[prova_id], resultado)
        except ValueError as erro:
            erros.append(str(erro))
    if erros:
        print(f"{len(erros)} resultado(s) sem faixa — nada foi escrito:", file=sys.stderr)
        for erro in erros:
            print(f"  {erro}", file=sys.stderr)
        return 1

    por_faixa: Counter = Counter()
    a_mudar = 0
    pares_a_mudar: list[tuple[str, str, str]] = []
    for (prova_id, resultado), contagem in gravadas.items():
        faixa = alvo[(prova_id, resultado)]
        por_faixa[faixa] += sum(contagem.values())
        diferentes = sum(n for atual, n in contagem.items() if atual != faixa)
        if diferentes:
            a_mudar += diferentes
            pares_a_mudar.append((prova_id, resultado, faixa))

    for faixa, n in por_faixa.most_common():
        print(f"  {faixa:20} {n}", file=sys.stderr)
    print(f"{a_mudar} linhas em {len(pares_a_mudar)} pares (prova, resultado) a mudar", file=sys.stderr)
    if args.simular or not pares_a_mudar:
        return 0

    for i, (prova_id, resultado, faixa) in enumerate(pares_a_mudar, 1):
        cliente.table("conquista_externa").update({"faixa": faixa}, returning="minimal").eq(
            "prova_id", prova_id
        ).eq("resultado", resultado).execute()
        if i % 50 == 0:
            print(f"  {i}/{len(pares_a_mudar)} pares", file=sys.stderr)

    # A lista geral é materializada (0063) e conta conquista pela faixa (0068):
    # sem o refresh, ela seguiria contando participação até a próxima escrita
    # pela tela.
    cliente.rpc("atualizar_v_candidato_externo_por_nome", {}).execute()
    print(f"ok: {a_mudar} linhas classificadas, lista geral atualizada", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
