"""Adapter fino sobre o Supabase Storage.

Mantemos isto isolado pra que trocar por S3 (ou armazenamento local em dev)
seja só substituir esse arquivo.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .config import get_settings
from .supabase_client import get_supabase


def salvar_planilha(*, arquivo_origem: str, conteudo: bytes) -> str:
    """Sobe o arquivo bruto pro bucket configurado. Retorna o path armazenado.

    Path determinístico: `uploads/AAAA/MM/DD/HHMMSS-<arquivo>`.
    Sufixo no nome evita colisão; histórico fica organizado por data.
    """
    settings = get_settings()
    cliente = get_supabase()

    agora = datetime.now(timezone.utc)
    caminho = (
        f"uploads/{agora:%Y/%m/%d}/{agora:%H%M%S}-{arquivo_origem}"
    )

    cliente.storage.from_(settings.storage_bucket).upload(
        path=caminho,
        file=conteudo,
        file_options={"content-type": "application/octet-stream"},
    )
    return caminho
