"""
upload_s3.py — Faz upload das imagens das questões para o S3 e atualiza os JSONs.

Para cada prova processada, sobe os PNGs de imagens/{prova_id}/ para
s3://{bucket}/imagens/{prova_id}/ e escreve o campo `imagem_questao_url`
em cada questão JSON.

Uso:
    python pipeline/upload_s3.py                    # todas as provas
    python pipeline/upload_s3.py ita_2024_fase1     # prova específica
    python pipeline/upload_s3.py --dry-run          # só lista o que faria
"""

import argparse
import json
import os
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_IMAGENS = PROJETO_ROOT / "imagens"
DIR_QUESTOES = PROJETO_ROOT / "questoes_json"


def carregar_config() -> dict:
    load_dotenv(PROJETO_ROOT / ".env")
    cfg = {
        "key": os.getenv("AWS_ACCESS_KEY_ID"),
        "secret": os.getenv("AWS_SECRET_ACCESS_KEY"),
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "bucket": os.getenv("S3_BUCKET"),
    }
    faltando = [k for k, v in cfg.items() if not v]
    if faltando:
        print(f"Erro: variáveis não definidas no .env: {faltando}")
        sys.exit(1)
    return cfg


def url_publica(bucket: str, region: str, key: str) -> str:
    return f"https://{bucket}.s3.{region}.amazonaws.com/{key}"


def upload_prova(prova_id: str, s3, cfg: dict, dry_run: bool) -> int:
    dir_img = DIR_IMAGENS / prova_id
    dir_json = DIR_QUESTOES / prova_id

    if not dir_img.exists():
        print(f"  ⚠ Sem imagens para {prova_id} — pulando")
        return 0

    pngs = sorted(dir_img.glob("*.png"))
    if not pngs:
        print(f"  ⚠ Nenhum PNG em {dir_img} — pulando")
        return 0

    enviados = 0
    for png in pngs:
        s3_key = f"imagens/{prova_id}/{png.name}"
        if dry_run:
            print(f"  [dry-run] s3://{cfg['bucket']}/{s3_key}")
            enviados += 1
            continue
        try:
            s3.upload_file(
                str(png),
                cfg["bucket"],
                s3_key,
                ExtraArgs={"ContentType": "image/png"},
            )
            enviados += 1
        except ClientError as e:
            print(f"  ✗ Erro ao enviar {png.name}: {e}")

    # Atualiza JSONs com a URL S3
    if not dry_run:
        for json_path in sorted(dir_json.glob("q*.json")):
            with open(json_path, encoding="utf-8") as f:
                dados = json.load(f)

            img_local = dados.get("imagem_questao", "")
            if not img_local:
                continue

            nome_png = Path(img_local).name
            s3_key = f"imagens/{prova_id}/{nome_png}"
            dados["imagem_questao_url"] = url_publica(
                cfg["bucket"], cfg["region"], s3_key
            )

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)

    return enviados


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "provas", nargs="*",
        help="IDs das provas (ex: ita_2024_fase1). Omita para todas."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Mostra o que seria enviado sem enviar nada")
    args = parser.parse_args()

    cfg = carregar_config()

    s3 = boto3.client(
        "s3",
        aws_access_key_id=cfg["key"],
        aws_secret_access_key=cfg["secret"],
        region_name=cfg["region"],
    )

    # Descobre provas
    if args.provas:
        provas = args.provas
    else:
        provas = sorted(p.name for p in DIR_IMAGENS.iterdir() if p.is_dir())

    if not provas:
        print("Nenhuma prova encontrada em imagens/")
        return

    total = 0
    for prova_id in provas:
        print(f"\n→ {prova_id}")
        n = upload_prova(prova_id, s3, cfg, dry_run=args.dry_run)
        print(f"  ✓ {n} arquivo(s) {'listados' if args.dry_run else 'enviados'}")
        total += n

    print(f"\nTotal: {total} imagens {'(dry-run)' if args.dry_run else 'enviadas para s3://' + cfg['bucket']}")


if __name__ == "__main__":
    try:
        main()
    except NoCredentialsError:
        print("Credenciais AWS não encontradas. Verifique o arquivo .env")
        sys.exit(1)
