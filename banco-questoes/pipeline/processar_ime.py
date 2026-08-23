#!/usr/bin/env python3
"""
processar_ime.py — Roda o pipeline para todos os PDFs do IME em fis/ime/,
nas três matérias (Física, Matemática, Química), pulando provas já processadas.

Uso:
    python pipeline/processar_ime.py
    python pipeline/processar_ime.py --force
    python pipeline/processar_ime.py --materias Física
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_IME = PROJETO_ROOT / "pdfs_originais" / "ime_fase1"
DIR_JSON = PROJETO_ROOT / "questoes_json"
PIPELINE = PROJETO_ROOT / "pipeline" / "pipeline_completo.py"

SUFIXO = {
    "Física": "", "Química": "_qui", "Matemática": "_mat",
}
ALL_MATERIAS = ["Física", "Matemática", "Química"]


def descobrir_anos() -> list[tuple[int, Path, Path | None]]:
    """Retorna lista de (ano, pdf_prova, pdf_gabarito | None) ordenada por ano."""
    pares: dict[int, dict] = {}
    for pdf in DIR_IME.glob("*.pdf"):
        m = re.search(r"(20\d{2})", pdf.name)
        if not m:
            continue
        ano = int(m.group(1))
        pares.setdefault(ano, {})
        if re.search(r"gab", pdf.name, re.IGNORECASE):
            pares[ano]["gabarito"] = pdf
        else:
            pares[ano]["prova"] = pdf

    resultado = []
    for ano in sorted(pares):
        p = pares[ano]
        if "prova" not in p:
            print(f"[AVISO] Ano {ano}: gabarito encontrado mas sem prova — pulando.")
            continue
        resultado.append((ano, p["prova"], p.get("gabarito")))
    return resultado


def ja_processado(ano: int, materia: str) -> bool:
    sufixo = SUFIXO.get(materia, "")
    prova_id = f"ime_{ano}_fase1{sufixo}"
    return (DIR_JSON / prova_id / "_relatorio.json").exists()


def rodar(ano: int, prova: Path, gabarito: Path | None, materia: str) -> bool:
    cmd = [
        sys.executable, str(PIPELINE),
        str(prova),
        "--ano", str(ano),
        "--fase", "1",
        "--materia", materia,
        "--vestibular", "IME",
    ]
    if gabarito:
        cmd += ["--gabarito", str(gabarito)]
    result = subprocess.run(cmd, cwd=PROJETO_ROOT)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--materias", nargs="+", default=ALL_MATERIAS,
                        choices=ALL_MATERIAS, metavar="MATERIA")
    parser.add_argument("--force", action="store_true",
                        help="Reprocessa mesmo provas já processadas")
    args = parser.parse_args()

    if not DIR_IME.exists():
        print(f"Pasta IME não encontrada: {DIR_IME}")
        sys.exit(1)

    anos = descobrir_anos()
    if not anos:
        print("Nenhum PDF encontrado em", DIR_IME)
        sys.exit(1)

    total = len(anos) * len(args.materias)
    ok = pulados = falhos = 0

    for ano, prova, gabarito in anos:
        for materia in args.materias:
            sufixo = SUFIXO.get(materia, "")
            prova_id = f"ime_{ano}_fase1{sufixo}"

            if not args.force and ja_processado(ano, materia):
                print(f"[SKIP] {prova_id} já processado")
                pulados += 1
                continue

            print(f"\n{'='*60}")
            print(f"  {prova_id}  ({materia})")
            print(f"{'='*60}")
            sucesso = rodar(ano, prova, gabarito, materia)
            if sucesso:
                ok += 1
            else:
                falhos += 1
                log_dir = PROJETO_ROOT / "logs"
                log_dir.mkdir(exist_ok=True)
                with open(log_dir / "processamento.log", "a") as f:
                    f.write(f"[ERRO] {prova_id}: pipeline retornou código != 0\n")
                print(f"[ERRO] {prova_id} falhou — registrado em logs/processamento.log")

    print(f"\n{'='*60}")
    print(f"  Concluído: {ok} processados, {pulados} pulados, {falhos} falhos / {total} total")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
