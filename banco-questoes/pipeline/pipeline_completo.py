"""
pipeline_completo.py — Orquestrador que roda as etapas automáticas em sequência.

Roda na ordem:
  1. extrair_prova.py   (texto + renderização de páginas)
  2. recortar_questoes.py (imagens das questões)
  3. extrair_gabarito.py  (se --gabarito foi passado)

Depois disso, o que falta é SÓ a classificação (feita via Claude Code) e a
renderização do HTML (que você invoca quando quiser, eventualmente juntando
várias provas).

Uso:
    python pipeline_completo.py pdfs_originais/2019_fase1.pdf \
        --ano 2019 --fase 1 --materia Física \
        --gabarito pdfs_originais/gabarito_2019.pdf
"""

import argparse
import subprocess
import sys
from pathlib import Path


PROJETO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = Path(__file__).resolve().parent


def rodar(cmd: list[str], descricao: str) -> int:
    print(f"\n{'='*70}")
    print(f"▶ {descricao}")
    print(f"{'='*70}")
    return subprocess.call([sys.executable] + cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--ano", type=int, required=True)
    parser.add_argument("--fase", type=int, default=1)
    parser.add_argument("--materia", default="Física")
    parser.add_argument("--vestibular", default="ITA")
    parser.add_argument("--gabarito", type=Path, default=None,
                        help="PDF do gabarito (opcional)")
    args = parser.parse_args()

    SUFIXO_MATERIA = {
        "Física":     "",
        "Química":    "_qui",
        "Matemática": "_mat",
        "Português":  "_por",
        "Inglês":     "_ing",
    }
    prova_id = f"{args.vestibular.lower()}_{args.ano}"
    if args.fase:
        prova_id += f"_fase{args.fase}"
    prova_id += SUFIXO_MATERIA.get(args.materia, f"_{args.materia.lower()[:3]}")

    # Etapa 1: extrair
    rc = rodar(
        [str(PIPELINE_DIR / "extrair_prova.py"), str(args.pdf),
         "--ano", str(args.ano), "--fase", str(args.fase),
         "--materia", args.materia, "--vestibular", args.vestibular],
        f"Etapa 1: Extraindo texto e renderizando páginas de {args.pdf.name}",
    )
    if rc != 0:
        print("Erro na etapa 1.")
        return 1

    # Etapa 2: recortar
    rc = rodar(
        [str(PIPELINE_DIR / "recortar_questoes.py"), prova_id],
        f"Etapa 2: Recortando questões como imagens",
    )
    if rc != 0:
        print("Erro na etapa 2.")
        return 1

    # Etapa 3: gabarito (opcional)
    if args.gabarito:
        rc = rodar(
            [str(PIPELINE_DIR / "extrair_gabarito.py"),
             str(args.gabarito), prova_id],
            f"Etapa 3: Aplicando gabarito de {args.gabarito.name}",
        )
        if rc != 0:
            print("Erro na etapa 3.")
            return 1

    print(f"\n{'='*70}")
    print(f"✓ Pipeline automático concluído: {prova_id}")
    print(f"{'='*70}")
    print()
    print("PRÓXIMOS PASSOS:")
    print()
    print(f"  4. Classificar as questões (abra no Claude Code):")
    print(f"     python pipeline/classificar.py listar {prova_id} > pendentes.txt")
    print(f"     # Peça ao Claude para gerar _classificacao_patch.json")
    print(f"     python pipeline/classificar.py aplicar {prova_id} "
          f"questoes_json/{prova_id}/_classificacao_patch.json")
    print()
    # Antes este passo gerava um HTML estático. Desde docs/22 quem serve o banco
    # é a API do SAS, e o JSON entra no Postgres pelo importador.
    print(f"  5. Importar para o SAS (a partir de api/):")
    print(f"     python -m scripts.importar_banco_questoes")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
