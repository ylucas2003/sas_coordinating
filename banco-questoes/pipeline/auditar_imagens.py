"""auditar_imagens.py — QA em lote das imagens de página (docs/24), sem
baixar imagem nenhuma inteira.

Reaproveita a técnica usada para achar o "Bug D" do recorte fino (docs/23
§12.1): um `Range: bytes=0-32` no S3 lê só a assinatura PNG + o chunk IHDR
(onde `width`/`height` moram, bytes 16-23), suficiente para flagar outlier
sem baixar 200KB por imagem. Sinaliza — não decide sozinho; humano confirma
antes do reimport, mesma filosofia do Bug D.

Uso:
    python pipeline/auditar_imagens.py ime_1998_fase2_qui ime_1998_fase2_mat ...
    python pipeline/auditar_imagens.py --todas-pagina   # varre questoes_json/ inteiro
"""

from __future__ import annotations

import argparse
import glob
import json
import struct
import sys
from pathlib import Path

import requests

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_QUESTOES = PROJETO_ROOT / "questoes_json"

# Referência: A4 retrato em 200dpi dá ~2339px de altura; A4 PAISAGEM (usado em
# pelo menos 5 provas do IME 2002-2006, ex. fisica0203.pdf: 842x595pt) dá só
# ~1653px — descoberto nesta auditoria como falso-positivo em massa (50
# outliers, todos legítimos ao abrir a imagem). O piso desce para cobrir os
# dois formatos; fora daqui ainda sinaliza render truncado de verdade.
ALTURA_MIN_1PAG = 1500
ALTURA_MAX_1PAG = 3400
TAMANHO_MAX_BYTES = 2_000_000  # ~2MB: candidato a revisão de DPI antes de escalar


def dimensao_png(url: str) -> tuple[int, int]:
    r = requests.get(url, headers={"Range": "bytes=0-32"}, timeout=15)
    r.raise_for_status()
    return struct.unpack(">II", r.content[16:24])


def tamanho_arquivo(url: str) -> int:
    r = requests.head(url, timeout=15)
    return int(r.headers.get("Content-Length", 0))


def auditar_prova(prova_id: str) -> dict:
    pasta = DIR_QUESTOES / prova_id
    arquivos = sorted(pasta.glob("q*.json")) if pasta.is_dir() else []
    total = len(arquivos)
    em_modo_pagina, outliers, sem_imagem = 0, [], []

    for f in arquivos:
        dados = json.loads(f.read_text(encoding="utf-8"))
        if dados.get("extraido_por") != "pagina":
            continue
        em_modo_pagina += 1
        url = dados.get("imagem_questao_url")
        id_q = dados["id"]
        if not url:
            sem_imagem.append(id_q)
            continue
        try:
            largura, altura = dimensao_png(url)
            tamanho = tamanho_arquivo(url)
        except Exception as e:
            outliers.append(f"{id_q}: falha ao consultar S3 ({type(e).__name__}: {e})")
            continue

        n_paginas = 2 if dados["fonte"].get("pagina_fim") else 1
        altura_esperada_min = ALTURA_MIN_1PAG * n_paginas
        altura_esperada_max = ALTURA_MAX_1PAG * n_paginas
        if not (altura_esperada_min <= altura <= altura_esperada_max):
            outliers.append(
                f"{id_q}: altura {altura}px fora da faixa esperada para {n_paginas} página(s) "
                f"({altura_esperada_min}-{altura_esperada_max}px) — composição pode ter falhado"
            )
        if tamanho > TAMANHO_MAX_BYTES * n_paginas:
            outliers.append(f"{id_q}: {tamanho / 1e6:.1f}MB — candidato a revisão de DPI")

    return {
        "prova_id": prova_id,
        "total_questoes": total,
        "em_modo_pagina": em_modo_pagina,
        "cobertura_incompleta": em_modo_pagina < total,
        "sem_imagem": sem_imagem,
        "outliers": outliers,
    }


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("provas", nargs="*", default=[])
    g.add_argument("--todas-pagina", action="store_true", help="varre toda prova com pelo menos 1 questão extraido_por=pagina")
    args = ap.parse_args()

    if args.todas_pagina:
        provas = []
        for pasta in sorted(DIR_QUESTOES.iterdir()):
            if not pasta.is_dir():
                continue
            algum_q = next(iter(sorted(glob.glob(str(pasta / "q*.json")))), None)
            if algum_q and json.loads(Path(algum_q).read_text()).get("extraido_por") == "pagina":
                provas.append(pasta.name)
    else:
        provas = args.provas

    total_outliers = 0
    for prova_id in provas:
        r = auditar_prova(prova_id)
        linha = f"{prova_id}: {r['em_modo_pagina']}/{r['total_questoes']} em modo página"
        if r["cobertura_incompleta"]:
            linha += " ⚠ cobertura incompleta"
        print(linha, file=sys.stderr)
        for s in r["sem_imagem"]:
            print(f"    sem imagem: {s}", file=sys.stderr)
        for o in r["outliers"]:
            print(f"    outlier: {o}", file=sys.stderr)
            total_outliers += 1

    print(f"\n{len(provas)} prova(s) auditada(s), {total_outliers} outlier(s)", file=sys.stderr)


if __name__ == "__main__":
    main()
