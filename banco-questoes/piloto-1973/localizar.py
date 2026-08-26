"""Localiza a coordenada Y de cada marcador de questão numa página escaneada.

O OCR de texto corrido é ilegível nessas provas datilografadas, mas o marcador de
questão é só um número na margem esquerda — 2-3 caracteres, que o tesseract acerta.
Quem diz QUAIS questões estão em cada página é a leitura por visão; aqui só se
procura a coordenada das que ela apontou, o que elimina o falso positivo (número de
página, número solto no meio do texto).
"""

import json
import re
import sys
from pathlib import Path

import pytesseract
from PIL import Image

# Margem esquerda: o marcador de questão nunca passa daqui. Números além disso são
# do corpo do texto (valores, índices) ou do cabeçalho.
FRACAO_MARGEM = 0.18
ALTURA_MINIMA = 15  # descarta ruído de scan


def candidatos_na_pagina(caminho: Path) -> dict[int, int]:
    """Todos os números plausíveis na margem esquerda: {numero: y}."""
    img = Image.open(caminho)
    largura = img.size[0]
    melhor: dict[int, int] = {}
    for psm in (6, 11, 3):
        data = pytesseract.image_to_data(
            img, lang="por", output_type=pytesseract.Output.DICT, config=f"--psm {psm}"
        )
        for i, token in enumerate(data["text"]):
            m = re.fullmatch(r"(\d{1,2})[.)]?", token.strip())
            if not m:
                continue
            if data["left"][i] > largura * FRACAO_MARGEM or data["height"][i] < ALTURA_MINIMA:
                continue
            num, y = int(m.group(1)), data["top"][i]
            if num not in melhor or y < melhor[num]:
                melhor[num] = y
    return melhor


def main():
    dir_paginas = Path(sys.argv[1])
    saida = {}
    for png in sorted(dir_paginas.glob("pg*.png")):
        pagina = int(png.stem.replace("pg", ""))
        img = Image.open(png)
        saida[pagina] = {
            "altura": img.size[1],
            "largura": img.size[0],
            "candidatos": candidatos_na_pagina(png),
        }
        print(f"  pg{pagina:02d}: {sorted(saida[pagina]['candidatos'])}", file=sys.stderr)
    (dir_paginas / "coordenadas.json").write_text(json.dumps(saida, indent=1))
    print(f"→ {dir_paginas / 'coordenadas.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
