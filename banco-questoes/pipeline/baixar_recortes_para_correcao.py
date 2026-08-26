"""baixar_recortes_para_correcao.py — Baixa do S3, para disco local, os recortes
das questões marcadas para a segunda passada (correção com imagem).

Agentes leem arquivo local (Read), não URL do S3 — por isso este passo existe
antes de disparar o workflow de correção.

Uso:
    python baixar_recortes_para_correcao.py <lista_de_json.json> <dir_saida>
"""

import json
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

PROJETO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJETO_ROOT / ".env")
_S3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
_BUCKET = os.getenv("S3_BUCKET", "ita-por-assunto")


def main():
    lista = json.loads(Path(sys.argv[1]).read_text())
    saida = Path(sys.argv[2])
    saida.mkdir(parents=True, exist_ok=True)

    baixados = {}
    for caminho_rel in lista:
        dados = json.loads((PROJETO_ROOT / "questoes_json" / caminho_rel).read_text())
        url = dados.get("imagem_questao_url")
        if not url:
            continue
        chave = url.split(f"{_BUCKET}.s3.")[-1].split("/", 1)[-1]  # após a região
        # url é https://{bucket}.s3.{regiao}.amazonaws.com/{chave}
        chave = url.split(".amazonaws.com/", 1)[1]
        destino = saida / f"{dados['id']}.png"
        if not destino.exists():
            _S3.download_file(_BUCKET, chave, str(destino))
        baixados[caminho_rel] = str(destino)
        print(f"  {caminho_rel} → {destino.name}", file=sys.stderr)

    Path(sys.argv[2] + "_indice.json").write_text(json.dumps(baixados, ensure_ascii=False, indent=2))
    print(f"\n{len(baixados)} imagens em {saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
