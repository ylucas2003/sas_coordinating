"""montar_manifesto_correcao.py — Lista as questões do acervo histórico já
classificadas que citam figura/gráfico no enunciado, baixa os recortes e monta
o manifesto (args) para o workflow `wf_corrigir_com_imagem.js`.

Uso:
    python montar_manifesto_correcao.py <dir_imagens_saida>
Escreve manifesto_correcao.json (agrupado por prova_id) no diretório atual.
"""

import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

from _comum import eh_historico

PALAVRAS = ["figura", "mostra", "conforme", "ilustrad", "esquema",
           "gráfico", "grafico", "diagrama", "abaixo", "ao lado"]


def main():
    dir_imagens = Path(sys.argv[1])
    flagueadas = []
    for f in sorted(glob.glob("questoes_json/*/q*.json")):
        pasta = f.split("/")[1]
        if not eh_historico(pasta):
            continue
        dados = json.loads(Path(f).read_text())
        if dados["classificacao"].get("classificado_por") != "claude":
            continue
        if dados.get("_corrigido_com_imagem"):  # já passou pela correção
            continue
        if any(p in dados["enunciado_md"].lower() for p in PALAVRAS):
            flagueadas.append(f.replace("questoes_json/", ""))

    print(f"{len(flagueadas)} questões flagueadas", file=sys.stderr)
    Path("/tmp/questoes_com_figura.json").write_text(json.dumps(flagueadas, ensure_ascii=False))

    grupos = defaultdict(list)
    indice_imagens = json.loads(Path(str(dir_imagens) + "_indice.json").read_text()) if (
        Path(str(dir_imagens) + "_indice.json").exists()
    ) else {}

    for rel in flagueadas:
        prova_id, arq = rel.split("/")
        dados = json.loads((Path("questoes_json") / rel).read_text())
        local = indice_imagens.get(rel)
        if not local:
            continue
        grupos[prova_id].append({"numero": dados["numero"], "arquivo_local": local})

    manifesto = [{"prova_id": p, "imagens": sorted(qs, key=lambda x: x["numero"])} for p, qs in grupos.items()]
    Path("manifesto_correcao.json").write_text(json.dumps(manifesto, ensure_ascii=False))
    print(f"{len(manifesto)} provas no manifesto → manifesto_correcao.json", file=sys.stderr)


if __name__ == "__main__":
    main()
