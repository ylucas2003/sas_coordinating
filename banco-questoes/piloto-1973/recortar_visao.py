"""Recorta cada questão de uma prova escaneada, cruzando visão + coordenadas OCR.

Mesma ideia do `recortar_questoes.py` do pipeline original: a questão vai do seu
marcador até o marcador da próxima, compondo verticalmente quando atravessa página.
A diferença é de onde vem a posição do marcador — aqui, do cruzamento entre a
leitura por visão (que diz QUAIS questões estão em cada página, e em que ordem) e o
tesseract (que dá o Y de cada número na margem). Sozinho, nenhum dos dois basta: o
OCR de texto é ilegível nessas provas, e a visão não devolve coordenada confiável.
"""

import json
import sys
from pathlib import Path

from PIL import Image

MARGEM_TOPO = 12      # px a mais acima do marcador, para não cortar o número
# O tesseract devolve o topo do GLIFO do número, que fica alguns pixels abaixo do
# topo real da linha (maiúsculas e acentos sobem mais). Cortar em prox_y-4 deixava
# a primeira linha da questão seguinte aparecendo no pé do recorte.
FOLGA_PROXIMA = 26
MARGEM_RODAPE = 90    # "Scanned by CamScanner" e o número da página
# Duas coisas diferentes que antes dividiam uma constante só:
TOPO_CONTEUDO = 120   # onde o conteúdo começa — usado ao INFERIR posição
CORTE_EMENDA = 178    # onde cortar a página emendada, abaixo do "- N -" do cabeçalho


def carregar_transcricao(dir_prova: Path) -> list[dict]:
    questoes = []
    for arq in sorted(dir_prova.glob("transcricao_*.json")):
        dados = json.loads(arq.read_text())
        questoes.extend(dados.get("questoes", []))
    # A questão que atravessa lote aparece duas vezes: fica a versão mais completa.
    por_numero: dict[int, dict] = {}
    for q in questoes:
        n = q["numero"]
        if n not in por_numero or len(q.get("enunciado_md", "")) > len(por_numero[n].get("enunciado_md", "")):
            por_numero[n] = q
    return [por_numero[n] for n in sorted(por_numero)]


def main():
    dir_prova = Path(sys.argv[1])
    prova_id = sys.argv[2]
    saida = dir_prova / "recortes"
    saida.mkdir(exist_ok=True)

    coords = json.loads((dir_prova / "coordenadas.json").read_text())
    questoes = carregar_transcricao(dir_prova)

    # Posição de cada questão: só aceita o candidato OCR se a visão colocou a
    # questão naquela página. É esse cruzamento que descarta o falso positivo.
    posicao: dict[int, tuple[int, int]] = {}   # numero -> (pagina, y)
    sem_coordenada: list[int] = []
    inferidas: list[int] = []
    for q in questoes:
        num, pag = q["numero"], q["pagina"]
        cands = coords[str(pag)]["candidatos"]
        if str(num) in cands:
            posicao[num] = (pag, cands[str(num)])
        else:
            sem_coordenada.append(num)

    # Fallback para o marcador que o tesseract não leu (número apagado no scan).
    # A visão já disse em que página a questão está e a numeração dá a ordem, então
    # a posição é dedutível: primeira da página começa no topo do conteúdo, as
    # demais ficam entre a anterior e a seguinte DA MESMA página.
    por_pagina: dict[int, list[int]] = {}
    for q in questoes:
        por_pagina.setdefault(q["pagina"], []).append(q["numero"])
    for num in list(sem_coordenada):
        pag = next(q["pagina"] for q in questoes if q["numero"] == num)
        irmas = sorted(por_pagina[pag])
        if num == irmas[0]:
            posicao[num] = (pag, TOPO_CONTEUDO)
        else:
            anterior = max((n for n in irmas if n < num and n in posicao), default=None)
            seguinte = min((n for n in irmas if n > num and n in posicao), default=None)
            y_ant = posicao[anterior][1] if anterior else TOPO_CONTEUDO
            y_seg = posicao[seguinte][1] if seguinte else coords[str(pag)]["altura"] - MARGEM_RODAPE
            posicao[num] = (pag, (y_ant + y_seg) // 2)
        sem_coordenada.remove(num)
        inferidas.append(num)

    ordenadas = sorted(posicao.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    relatorio = []

    for i, (num, (pag, y)) in enumerate(ordenadas):
        y_ini = max(0, y - MARGEM_TOPO)
        if i + 1 < len(ordenadas):
            prox_pag, prox_y = ordenadas[i + 1][1]
        else:
            prox_pag, prox_y = pag, coords[str(pag)]["altura"] - MARGEM_RODAPE

        partes = []
        if prox_pag == pag:
            img = Image.open(dir_prova / f"pg{pag:02d}.png")
            partes.append(img.crop((0, y_ini, img.width, max(y_ini + 40, prox_y - FOLGA_PROXIMA))))
        else:
            img = Image.open(dir_prova / f"pg{pag:02d}.png")
            partes.append(img.crop((0, y_ini, img.width, img.height - MARGEM_RODAPE)))
            for meio in range(pag + 1, prox_pag):
                im = Image.open(dir_prova / f"pg{meio:02d}.png")
                partes.append(im.crop((0, CORTE_EMENDA, im.width, im.height - MARGEM_RODAPE)))
            im = Image.open(dir_prova / f"pg{prox_pag:02d}.png")
            fim = max(CORTE_EMENDA + 40, prox_y - FOLGA_PROXIMA)
            partes.append(im.crop((0, CORTE_EMENDA, im.width, fim)))

        largura = max(p.width for p in partes)
        altura = sum(p.height for p in partes)
        composta = Image.new("RGB", (largura, altura), "white")
        yy = 0
        for p in partes:
            composta.paste(p, (0, yy))
            yy += p.height

        nome = f"{prova_id}_q{num:02d}.png"
        composta.save(saida / nome)
        relatorio.append({"numero": num, "pagina": pag, "arquivo": nome,
                          "altura": altura, "paginas_compostas": len(partes)})
        print(f"  Q{num:02d} pg{pag} → {nome} ({largura}x{altura}, {len(partes)} parte(s))", file=sys.stderr)

    (dir_prova / "recorte_relatorio.json").write_text(
        json.dumps({"recortadas": relatorio, "sem_coordenada": sem_coordenada,
                    "posicao_inferida": inferidas}, indent=1)
    )
    if inferidas:
        print(f"\n  ~ posição inferida (marcador ilegível, conferir): {sorted(inferidas)}", file=sys.stderr)
    if sem_coordenada:
        print(f"\n  ! sem coordenada (não recortadas): {sem_coordenada}", file=sys.stderr)
    print(f"\n  {len(relatorio)} recortadas → {saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
