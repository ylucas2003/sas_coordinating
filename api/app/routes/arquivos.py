"""Download de arquivos do Storage local.

Existe só quando `STORAGE_DIR` está configurado (stack do docker compose). No
modo Supabase o download vai direto para a signed URL do bucket e esta rota
nunca é chamada — por isso ela não usa `Depends(get_current_*)`: a autorização
está no próprio token assinado, exatamente como na signed URL que ela
substitui. Ver `app/storage.py`.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from jose import JWTError

from ..storage import ler_token_download, resolver_caminho_local

router = APIRouter(prefix="/arquivos", tags=["arquivos"])


@router.get("/download")
async def baixar_arquivo(token: str = Query(..., description="JWT emitido por gerar_url_download_arquivo")):
    try:
        caminho_storage, nome_download = ler_token_download(token)
    except (JWTError, ValueError, KeyError):
        raise HTTPException(status_code=403, detail="Link inválido ou expirado.")

    try:
        destino = resolver_caminho_local(caminho_storage)
    except (RuntimeError, ValueError):
        raise HTTPException(status_code=403, detail="Link inválido ou expirado.")

    if not destino.is_file():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado no Storage.")

    return FileResponse(destino, filename=nome_download)
