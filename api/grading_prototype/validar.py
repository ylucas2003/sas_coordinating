"""CLI — agrega a concordância IA × corretor humano a partir dos relatórios
salvos em resultados/ (correcao_*.json e relatórios do comparar_modelos).

Só considera pares (nota calculada, nota humana) — execuções sem
`nota_humana` são ignoradas. Métricas: MAE, viés médio (IA − humano),
% dentro da margem (config.MARGEM_ACEITAVEL_NOTA) e detalhe por questão.
É isso que transforma a decisão "acoplar ou não o protótipo" em número.

Sem chamadas de LLM — puro Python sobre os JSONs já salvos.

Uso (a partir de api/):
    python -m grading_prototype.validar
    python -m grading_prototype.validar --resultados <pasta>
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

PASTA_PROTOTIPO = Path(__file__).resolve().parent


def _extrair_pares(caminho: Path) -> list[dict]:
    """Extrai pares {questao, fonte, modelo, nota_ia, nota_humana} de um
    relatório salvo — cobre os formatos de corrigir_prova e comparar_modelos."""
    try:
        dados_relatorio = json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        log.warning("Ignorando %s (JSON inválido).", caminho.name)
        return []

    pares = []

    # Formato de corrigir_prova: resultados_por_questao
    for questao, r in (dados_relatorio.get("resultados_por_questao") or {}).items():
        if not isinstance(r, dict) or "erro" in r or "nota_humana" not in r:
            continue
        pares.append(
            {
                "questao": questao,
                "fonte": caminho.name,
                "modelo": (dados_relatorio.get("metadados_execucao") or {}).get("modelo", "?"),
                "nota_ia": r["nota"]["nota_final"],
                "nota_humana": r["nota_humana"],
            }
        )

    # Formato de comparar_modelos: resultados_por_modelo + nota_humana no topo
    nota_humana = dados_relatorio.get("nota_humana")
    if nota_humana is not None:
        for modelo, r in (dados_relatorio.get("resultados_por_modelo") or {}).items():
            if not isinstance(r, dict) or r.get("erro") is not None or "nota" not in r:
                continue
            pares.append(
                {
                    "questao": dados_relatorio.get("questao_id", "?"),
                    "fonte": caminho.name,
                    "modelo": modelo,
                    "nota_ia": r["nota"]["nota_final"],
                    "nota_humana": nota_humana,
                }
            )

    return pares


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agrega concordância IA × humano a partir dos relatórios salvos."
    )
    parser.add_argument(
        "--resultados",
        default=str(PASTA_PROTOTIPO / "resultados"),
        help="Pasta com os relatórios JSON (padrão: resultados/).",
    )
    parser.add_argument(
        "--margem",
        type=float,
        default=config.MARGEM_ACEITAVEL_NOTA,
        help=f"Margem de concordância em pontos (padrão: {config.MARGEM_ACEITAVEL_NOTA}).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pasta = Path(args.resultados)
    if not pasta.is_dir():
        raise SystemExit(f"Pasta de resultados não encontrada: {pasta}")

    pares: list[dict] = []
    for caminho in sorted(pasta.glob("*.json")):
        pares.extend(_extrair_pares(caminho))

    if not pares:
        raise SystemExit(
            "Nenhum par (nota IA, nota humana) encontrado — as execuções salvas "
            "não têm nota_humana.json. Adicione notas humanas e rode as correções."
        )

    deltas = [p["nota_ia"] - p["nota_humana"] for p in pares]
    mae = sum(abs(d) for d in deltas) / len(deltas)
    vies = sum(deltas) / len(deltas)
    dentro = sum(1 for d in deltas if abs(d) <= args.margem)

    print(f"{len(pares)} pares (nota IA, nota humana) encontrados\n")
    print(f"{'Questão':<28} {'Modelo':<14} {'IA':>6} {'Humano':>7} {'Δ':>7}")
    print("-" * 66)
    for p in sorted(pares, key=lambda x: (x["questao"], x["modelo"])):
        delta = p["nota_ia"] - p["nota_humana"]
        print(
            f"{p['questao']:<28} {p['modelo']:<14} {p['nota_ia']:>6.2f} "
            f"{p['nota_humana']:>7.2f} {delta:>+7.2f}"
        )
    print("-" * 66)
    print(f"MAE (erro absoluto médio):        {mae:.2f}")
    print(f"Viés médio (IA − humano):         {vies:+.2f}")
    print(
        f"Dentro da margem (±{args.margem:.1f}):        "
        f"{dentro}/{len(pares)} ({100 * dentro / len(pares):.0f}%)"
    )


if __name__ == "__main__":
    main()
