"""
processar_ime_2fase.py — Processa todas as provas dissertativas (2ª fase) do IME.

Cada matéria tem um PDF separado com 10 questões dissertativas (1 a 10).

Espera arquivos com o padrão:
    {fis|mat|quim}{ano}.pdf
ex: fis2019.pdf, mat2020.pdf, quim2025.pdf

Uso:
    python pipeline/processar_ime_2fase.py
    python pipeline/processar_ime_2fase.py --dir pdfs_originais/ime_fase2
    python pipeline/processar_ime_2fase.py --force
    python pipeline/processar_ime_2fase.py --materias Física Matemática
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_JSON = PROJETO_ROOT / "questoes_json"
PIPELINE_COMPLETO = PROJETO_ROOT / "pipeline" / "pipeline_completo.py"

DIR_2FASE_DEFAULT = (PROJETO_ROOT / "pdfs_originais" / "ime_fase2").resolve()

SLUG_PARA_MATERIA = {
    "fis":  "Física",
    "mat":  "Matemática",
    "quim": "Química",
}

SUFIXO_MATERIA = {
    "Física":     "",
    "Química":    "_qui",
    "Matemática": "_mat",
}


def descobrir_pdfs(dir_2fase: Path) -> list[tuple[Path, int, str]]:
    encontrados = []
    for pdf in dir_2fase.glob("*.pdf"):
        m = re.match(r"(fis|mat|quim)(20\d{2})\.pdf$", pdf.name, re.IGNORECASE)
        if not m:
            print(f"[AVISO] Nome fora do padrão, pulando: {pdf.name}")
            continue
        slug = m.group(1).lower()
        ano = int(m.group(2))
        materia = SLUG_PARA_MATERIA[slug]
        encontrados.append((pdf, ano, materia))
    encontrados.sort(key=lambda t: (t[1], t[2]))
    return encontrados


def prova_id_for(ano: int, materia: str) -> str:
    return f"ime_{ano}_fase2{SUFIXO_MATERIA[materia]}"


def ja_processado(ano: int, materia: str) -> bool:
    return (DIR_JSON / prova_id_for(ano, materia) / "_relatorio.json").exists()


def rodar(pdf: Path, ano: int, materia: str) -> bool:
    cmd = [
        sys.executable, str(PIPELINE_COMPLETO),
        str(pdf),
        "--ano", str(ano),
        "--fase", "2",
        "--materia", materia,
        "--vestibular", "IME",
    ]
    result = subprocess.run(cmd, cwd=PROJETO_ROOT)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=Path, default=DIR_2FASE_DEFAULT,
                        help=f"Diretório com os PDFs da 2ª fase (padrão: {DIR_2FASE_DEFAULT})")
    parser.add_argument("--materias", nargs="+",
                        default=list(SLUG_PARA_MATERIA.values()),
                        choices=list(SLUG_PARA_MATERIA.values()),
                        metavar="MATERIA",
                        help="Matérias a processar")
    parser.add_argument("--force", action="store_true",
                        help="Reprocessa mesmo provas já processadas")
    args = parser.parse_args()

    dir_2fase = args.dir.resolve()
    if not dir_2fase.exists():
        print(f"Diretório não encontrado: {dir_2fase}")
        sys.exit(1)

    pdfs = descobrir_pdfs(dir_2fase)
    pdfs = [t for t in pdfs if t[2] in args.materias]
    if not pdfs:
        print(f"Nenhum PDF válido encontrado em {dir_2fase}")
        sys.exit(1)

    total = len(pdfs)
    ok = pulados = falhos = 0

    for pdf, ano, materia in pdfs:
        pid = prova_id_for(ano, materia)
        if not args.force and ja_processado(ano, materia):
            print(f"[SKIP] {pid} já processado")
            pulados += 1
            continue

        print(f"\n{'='*60}")
        print(f"  {pid}  ({materia} {ano} — IME 2ª fase)")
        print(f"{'='*60}")
        sucesso = rodar(pdf, ano, materia)
        if sucesso:
            ok += 1
        else:
            falhos += 1
            log_dir = PROJETO_ROOT / "logs"
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "processamento_ime_2fase.log", "a") as f:
                f.write(f"[ERRO] {pid}: pipeline retornou código != 0\n")
            print(f"[ERRO] {pid} falhou — registrado em logs/processamento_ime_2fase.log")

    print(f"\n{'='*60}")
    print(f"  Concluído: {ok} processados, {pulados} pulados, {falhos} falhos / {total} total")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
