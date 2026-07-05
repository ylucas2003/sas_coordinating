"""Endpoints de upload e auditoria de planilhas."""

from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel

from ..auth import get_current_coordenador
from ..ingest.pipeline import processar_planilha
from ..ingest.upsert import criar_upload
from ..storage import salvar_planilha
from ..supabase_client import criar_cliente_supabase, get_supabase

router = APIRouter(
    prefix="/uploads",
    tags=["uploads"],
    dependencies=[Depends(get_current_coordenador)],
)


# ─── Schemas de resposta ──────────────────────────────────────────────────


class RespostaUpload(BaseModel):
    """Resposta do POST /uploads."""
    upload_id: str
    status: str
    resumo: dict[str, Any]


class RegistroUpload(BaseModel):
    id: str
    arquivo_origem: str
    status: str
    linhas_total: int | None = None
    linhas_aceitas: int | None = None
    linhas_rejeitadas: int | None = None
    resumo: dict[str, Any] | None = None
    criado_em: str
    finalizado_em: str | None = None


class EventoUpload(BaseModel):
    nivel: str
    mensagem: str
    linha_planilha: int | None = None
    coluna_planilha: str | None = None
    criado_em: str


class DetalheUpload(BaseModel):
    upload: RegistroUpload
    eventos: list[EventoUpload]


# ─── POST /uploads ────────────────────────────────────────────────────────


@router.post("", response_model=RespostaUpload)
async def receber_upload(
    background_tasks: BackgroundTasks,
    arquivo: UploadFile = File(..., description="Planilha CSV ou XLSX exportada do Canvas."),
    autor: str | None = Form(default=None, description="Identificador de quem enviou."),
    salvar_no_storage: bool = Form(default=True),
) -> RespostaUpload:
    """Recebe a planilha e dispara a ingestão em background.

    A rota retorna imediatamente após salvar a linha em `upload` (status =
    'processando'). O cliente acompanha o progresso fazendo polling em
    `GET /uploads/{id}` — os eventos `ETAPA N/7: ...` alimentam a barra
    do frontend, e o status muda para `sucesso` ou `erro` no fim.
    """
    if not arquivo.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome.")

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(status_code=400, detail="Arquivo vazio.")

    # Validar config do Supabase ANTES de devolver o upload_id — assim, se as
    # credenciais estiverem erradas, o cliente recebe um 500 de cara em vez de
    # ficar polling um upload que nunca vai sair de 'processando'.
    cliente = get_supabase()

    caminho_storage: str | None = None
    if salvar_no_storage:
        try:
            caminho_storage = salvar_planilha(
                arquivo_origem=arquivo.filename,
                conteudo=conteudo,
            )
        except Exception:
            # Falha ao subir pro storage não impede a ingestão.
            caminho_storage = None

    # Cria a linha de upload AGORA pra devolver o ID. O processamento
    # propriamente dito (parsing + upserts) roda em background.
    upload_id = criar_upload(
        cliente,
        arquivo_origem=arquivo.filename,
        caminho_storage=caminho_storage,
        autor=autor,
    )

    background_tasks.add_task(
        _processar_em_background,
        upload_id=upload_id,
        arquivo_origem=arquivo.filename,
        conteudo=conteudo,
        caminho_storage=caminho_storage,
        autor=autor,
    )

    return RespostaUpload(
        upload_id=upload_id,
        status="processando",
        resumo={},
    )


def _processar_em_background(
    *,
    upload_id: str,
    arquivo_origem: str,
    conteudo: bytes,
    caminho_storage: str | None,
    autor: str | None,
) -> None:
    """Wrapper síncrono — FastAPI BackgroundTasks chama isto após enviar a resposta.

    Usa cliente Supabase NOVO (não cacheado) para ter conexão TCP isolada do
    cliente que serve o polling do frontend. Sem isso, o GOAWAY de uma stream
    HTTP/2 da pipeline derruba também as streams do polling.
    """
    cliente = criar_cliente_supabase()
    try:
        processar_planilha(
            cliente=cliente,
            arquivo_origem=arquivo_origem,
            conteudo=conteudo,
            caminho_storage=caminho_storage,
            autor=autor,
            upload_id_existente=upload_id,
        )
    except Exception:
        # `processar_planilha` já registra o erro no `upload` e em `upload_evento`.
        # Aqui só evitamos que a exceção escale e quebre o worker do FastAPI.
        pass


# ─── GET /uploads ─────────────────────────────────────────────────────────


@router.get("", response_model=list[RegistroUpload])
async def listar_uploads(limite: int = 50) -> list[RegistroUpload]:
    """Histórico de uploads, mais recentes primeiro."""
    cliente = get_supabase()
    resposta = (
        cliente.table("upload")
        .select("*")
        .order("criado_em", desc=True)
        .limit(limite)
        .execute()
    )
    return [RegistroUpload(**linha) for linha in (resposta.data or [])]


# ─── GET /uploads/{id} ────────────────────────────────────────────────────


@router.get("/{upload_id}", response_model=DetalheUpload)
async def obter_upload(upload_id: str) -> DetalheUpload:
    """Detalhe de um upload + log de eventos (avisos, erros)."""
    cliente = get_supabase()

    upload_resp = (
        cliente.table("upload").select("*").eq("id", upload_id).limit(1).execute()
    )
    if not upload_resp.data:
        raise HTTPException(status_code=404, detail=f"upload {upload_id} não encontrado")

    eventos_resp = (
        cliente.table("upload_evento")
        .select("nivel,mensagem,linha_planilha,coluna_planilha,criado_em")
        .eq("upload_id", upload_id)
        .order("criado_em", desc=False)
        .execute()
    )

    return DetalheUpload(
        upload=RegistroUpload(**upload_resp.data[0]),
        eventos=[EventoUpload(**ev) for ev in (eventos_resp.data or [])],
    )
