"""Guarda o vídeo composto no S3.

Um cliente só, criado sob demanda e reaproveitado — diferente dos scripts de
`banco-questoes/pipeline/`, que instanciam `boto3.client("s3", ...)` do zero
em cada arquivo.

Diferença importante em relação ao banco de questões: lá os PNGs de prova são
públicos; aqui é gravação de sala de aula com aluno menor de idade na câmera
e no chat. O upload NÃO leva ACL pública — quem precisar do objeto lê com
credencial AWS, e a distribuição pra aluno é o link "não listado" do YouTube.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from ..config import get_settings


class S3NaoConfigurado(Exception):
    pass


@lru_cache
def _cliente() -> Any:
    # Import tardio (mesmo padrão de lembretes/email.py): boto3 só é
    # necessário quando há upload de verdade.
    import boto3

    settings = get_settings()
    if not settings.s3_bucket_gravacoes:
        raise S3NaoConfigurado("S3_BUCKET_GRAVACOES não configurado")
    return boto3.client(
        "s3",
        region_name=settings.aws_region or "us-east-1",
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def enviar_video(caminho: Path, *, curso_id: str, conferencia_id: str) -> tuple[str, str]:
    """Sobe o mp4 e devolve (bucket, chave)."""
    settings = get_settings()
    bucket = settings.s3_bucket_gravacoes
    chave = f"aulas/{curso_id}/{conferencia_id}.mp4"
    _cliente().upload_file(
        str(caminho), bucket, chave, ExtraArgs={"ContentType": "video/mp4"}
    )
    return bucket, chave
