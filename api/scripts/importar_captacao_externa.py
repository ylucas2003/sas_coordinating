#!/usr/bin/env python3
"""Importa conquistas raspadas (captacao-externa/pipeline/*.py) para
`conquista_externa`, criando a linha em `prova_externa` se ainda não existir.

Código que não roda em requisição vive como script — mesma escolha do
`importar_planilha.py` e do `banco-questoes/`.

Uso:
    ./.venv/bin/python scripts/importar_captacao_externa.py \\
        ../captacao-externa/dados/obmep_2025.json \\
        --prova-categoria olimpiada --prova-abrangencia nacional \\
        --prova-fonte https://www.obmep.org.br/premiados.htm

    ./.venv/bin/python scripts/importar_captacao_externa.py \\
        ../captacao-externa/dados/obmep_*.json

Depois de importar, rode `scripts/resolver_candidatos_externos.py` pra
cruzar as conquistas em candidatos.

Formato esperado de cada item do JSON (ver captacao-externa/pipeline/obmep.py):
    prova_nome, ano, nivel_texto, serie_referencia_min, serie_referencia_max,
    resultado, nome_informado, escola_informada, cidade_informada,
    uf_informada, fonte_url
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase

TAMANHO_LOTE = 200


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def obter_ou_criar_prova(cliente: Any, nome: str, categoria: str | None, abrangencia: str | None, fonte: str | None) -> str:
    existente = cliente.table("prova_externa").select("id").eq("nome", nome).execute()
    if existente.data:
        return existente.data[0]["id"]

    if not categoria:
        raise SystemExit(
            f"prova '{nome}' não existe em prova_externa ainda — passe --prova-categoria "
            f"(e opcionalmente --prova-abrangencia/--prova-fonte) na primeira importação."
        )

    criado = (
        cliente.table("prova_externa")
        .insert(
            {
                "nome": nome,
                "categoria": categoria,
                "abrangencia": abrangencia,
                "fonte_resultado": fonte,
            },
            returning="representation",
        )
        .execute()
    )
    return criado.data[0]["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("arquivos", type=Path, nargs="+", help="JSON(s) produzido(s) pelo scraper.")
    ap.add_argument("--prova-categoria", choices=["olimpiada", "vestibular", "colegio_militar", "concurso_nivel_medio"])
    ap.add_argument("--prova-abrangencia", default=None)
    ap.add_argument("--prova-fonte", default=None)
    args = ap.parse_args()

    cliente = criar_cliente_supabase()
    provas_cache: dict[str, str] = {}
    total_lidos = 0
    total_gravados = 0

    for arquivo in args.arquivos:
        registros: list[dict] = json.loads(arquivo.read_text(encoding="utf-8"))
        total_lidos += len(registros)
        if not registros:
            continue

        linhas: list[dict] = []
        for r in registros:
            nome_prova = r["prova_nome"]
            if nome_prova not in provas_cache:
                provas_cache[nome_prova] = obter_ou_criar_prova(
                    cliente, nome_prova, args.prova_categoria, args.prova_abrangencia, args.prova_fonte
                )
            linhas.append(
                {
                    "prova_id": provas_cache[nome_prova],
                    "ano": r["ano"],
                    "nivel_texto": r.get("nivel_texto"),
                    "serie_referencia_min": r.get("serie_referencia_min"),
                    "serie_referencia_max": r.get("serie_referencia_max"),
                    "resultado": r["resultado"],
                    "nome_informado": r["nome_informado"],
                    "escola_informada": r.get("escola_informada"),
                    "cidade_informada": r.get("cidade_informada"),
                    "uf_informada": r.get("uf_informada"),
                    "fonte_url": r["fonte_url"],
                }
            )

        for lote in _em_lotes(linhas):
            cliente.table("conquista_externa").upsert(
                lote,
                on_conflict="prova_id,ano,nivel_texto,nome_informado,escola_informada,resultado",
                returning="minimal",
            ).execute()
            total_gravados += len(lote)

        print(f"{arquivo.name}: {len(registros)} registros", file=sys.stderr)

    print(f"total: {total_lidos} lidos, {total_gravados} gravados (upsert)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
