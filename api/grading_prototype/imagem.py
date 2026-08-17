"""Abrir, redimensionar e codificar em base64 as fotos usadas nas chamadas
multimodais (figura do enunciado, páginas da resposta do aluno).

Única dependência nova do protótipo (Pillow) — fica toda contida aqui.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageOps

from . import config


def carregar_imagem_base64(
    caminho: Path, *, max_dimensao: int = config.MAX_DIMENSAO_IMAGEM_PX
) -> str:
    """Abre a imagem, redimensiona se necessário e devolve um data URL base64.

    Fotos de celular costumam vir com 12MP+; redimensionar antes de mandar
    pra API limita o custo de tokens de visão sem perder legibilidade útil.
    """
    imagem = Image.open(caminho)
    # Fotos de celular em retrato guardam os pixels deitados + tag EXIF
    # Orientation; sem isto a página chegaria rotacionada ao modelo de visão
    # (o re-encode JPEG abaixo descarta o EXIF).
    imagem = ImageOps.exif_transpose(imagem)
    imagem = imagem.convert("RGB")  # descarta alfa/paleta, garante JPEG válido

    lado_maior = max(imagem.size)
    if lado_maior > max_dimensao:
        fator = max_dimensao / lado_maior
        novo_tamanho = (
            max(1, round(imagem.width * fator)),
            max(1, round(imagem.height * fator)),
        )
        imagem = imagem.resize(novo_tamanho, Image.LANCZOS)

    buffer = io.BytesIO()
    imagem.save(buffer, format="JPEG", quality=85)
    codificado = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{codificado}"


def montar_bloco_imagem(data_url: str, *, detalhe: str = config.DETALHE_IMAGEM) -> dict:
    """Monta o bloco `image_url` no formato esperado pela Chat Completions API."""
    return {
        "type": "image_url",
        "image_url": {"url": data_url, "detail": detalhe},
    }
