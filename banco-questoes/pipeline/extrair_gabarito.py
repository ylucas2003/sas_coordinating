"""
extrair_gabarito.py — Etapa 3 do pipeline.

Lê o PDF do gabarito oficial do ITA e popula o campo `gabarito` em cada JSON
de questão da prova correspondente.

O gabarito do ITA tem um formato tabular bem previsível:
  1 C 13 B 25 D 37 C 49 A
  2 A 14 E 26 E 38 A 50 D
  ...

A estratégia é: extrair todo o texto do PDF, procurar pares (número, letra)
onde o número está na faixa 1-60 e a letra é A-E.

Uso:
    python extrair_gabarito.py <pdf_gabarito> <prova_id>
    ex: python extrair_gabarito.py gabarito_2019.pdf ita_2019_fase1
"""

import argparse
import json
import re
from pathlib import Path
import fitz


PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_QUESTOES_JSON = PROJETO_ROOT / "questoes_json"


# Procura um dígito (1-60) seguido por espaço e uma letra A-E.
# Ancorado por quebras de linha ou espaços para evitar captar "H2 C" etc.
PADRAO_GABARITO = re.compile(
    r"(?<![A-Za-z\d])(\d{1,2})\s+([A-E])(?![A-Za-z])",
)


def extrair_gabarito_pdf(pdf_path: Path) -> dict[int, str]:
    """
    Retorna dict {numero: letra} com todo o gabarito identificado.
    """
    doc = fitz.open(pdf_path)
    texto = "\n".join(page.get_text() for page in doc)

    gabarito = {}
    for m in PADRAO_GABARITO.finditer(texto):
        num = int(m.group(1))
        letra = m.group(2)
        if 1 <= num <= 60 and num not in gabarito:
            gabarito[num] = letra

    return gabarito


def aplicar_gabarito(prova_id: str, gabarito: dict[int, str]) -> dict:
    """
    Aplica o gabarito aos JSONs da prova.

    Preenche o campo 'gabarito' de cada questão cujo número esteja no dict.
    """
    dir_prova = DIR_QUESTOES_JSON / prova_id
    if not dir_prova.exists():
        raise FileNotFoundError(f"Pasta {dir_prova} não existe.")

    atualizados = 0
    faltantes = []

    for json_path in sorted(dir_prova.glob("q*.json")):
        with open(json_path, encoding="utf-8") as f:
            q = json.load(f)

        num = q["numero"]
        if num in gabarito:
            q["gabarito"] = gabarito[num]
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(q, f, ensure_ascii=False, indent=2)
            atualizados += 1
        else:
            faltantes.append(num)

    return {"atualizados": atualizados, "faltantes": faltantes}


def main():
    parser = argparse.ArgumentParser(description="Extrai gabarito e aplica aos JSONs.")
    parser.add_argument("pdf_gabarito", type=Path)
    parser.add_argument("prova_id")
    args = parser.parse_args()

    print(f"=== Extraindo gabarito de {args.pdf_gabarito.name} ===\n")
    gabarito = extrair_gabarito_pdf(args.pdf_gabarito)
    print(f"Gabaritos identificados: {len(gabarito)}")
    print(f"Amostra: {dict(list(gabarito.items())[:12])}")

    print(f"\n=== Aplicando a {args.prova_id} ===")
    resultado = aplicar_gabarito(args.prova_id, gabarito)
    print(f"Questões atualizadas: {resultado['atualizados']}")
    if resultado["faltantes"]:
        print(f"⚠ Questões sem gabarito encontrado: {resultado['faltantes']}")


if __name__ == "__main__":
    main()
