"""Adapter fino sobre o Storage de arquivos.

Dois backends, escolhidos por env — os chamadores não sabem qual está ativo:

  - **Supabase Storage** (default): bucket `STORAGE_BUCKET`.
  - **Filesystem local** (docker compose): diretório `STORAGE_DIR`.

O `caminho_storage` gravado no banco é o mesmo nos dois casos (é uma chave
relativa, não um caminho absoluto), então trocar de backend não invalida as
linhas já existentes de `upload.caminho_storage` e `simulado.arquivo_storage` —
só muda de onde os bytes são lidos.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from jose import jwt

from .config import get_settings
from .supabase_client import get_supabase

_PADRAO_CARACTERE_INVALIDO_STORAGE = re.compile(r"[^A-Za-z0-9._-]+")

# Algoritmo do token de download local. Mesmo segredo do login (JWT_SECRET_KEY),
# namespace separado pelo claim "tipo" para um token de sessão não virar
# permissão de download nem vice-versa.
_ALGORITMO_TOKEN = "HS256"
_TIPO_TOKEN_DOWNLOAD = "download_arquivo"


def _segredo_download() -> str:
    """Chave dedicada ao token de download, derivada da JWT_SECRET_KEY.

    Antes este token era assinado com a `jwt_secret_key` crua — a mesma da
    sessão. Como o aluno recebe o token em claro (a URL vem no corpo de
    `GET /me/simulado/{id}/arquivo`), ele tinha na mão um JWT que o verificador
    de sessão aceitava. O `tipo` no payload era a única separação, e só o lado
    do download a conferia.

    Derivar em vez de criar uma env nova é deliberado: não exige coordenar
    variável no deploy da VPS, e um token assinado com esta chave é
    matematicamente incapaz de validar contra a `jwt_secret_key`. O prefixo é a
    separação de domínio; o `v1` existe para permitir rotacionar só este token
    no futuro sem tocar na sessão.
    """
    return hashlib.sha256(
        b"sas:download-arquivo:v1|" + get_settings().jwt_secret_key.encode()
    ).hexdigest()


def _slugificar_nome_arquivo(nome: str) -> str:
    """Nomes de Course File do Canvas trazem espaço/acento/vírgula/parênteses
    — inválidos como key do Supabase Storage (erro 'InvalidKey')."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", nome) if not unicodedata.combining(c)
    )
    return _PADRAO_CARACTERE_INVALIDO_STORAGE.sub("-", sem_acento).strip("-")


def _raiz_local() -> Path | None:
    """Diretório do Storage local, ou None se o backend for o Supabase."""
    diretorio = get_settings().storage_dir
    return Path(diretorio) if diretorio else None


def resolver_caminho_local(caminho_storage: str) -> Path:
    """Traduz uma key do Storage para um path absoluto dentro de STORAGE_DIR.

    Recusa qualquer key que escape da raiz (`../`, path absoluto). As keys são
    geradas aqui, mas isto é a última linha de defesa antes de um `open()`.
    """
    raiz = _raiz_local()
    if raiz is None:
        raise RuntimeError("Storage local não configurado (STORAGE_DIR vazio).")
    destino = (raiz / caminho_storage).resolve()
    if not destino.is_relative_to(raiz.resolve()):
        raise ValueError(f"Caminho fora da raiz do Storage: {caminho_storage!r}")
    return destino


def _salvar(caminho: str, conteudo: bytes, *, content_type: str, upsert: bool = False) -> str:
    """Grava no backend ativo e devolve a key.

    `upsert` só muda o backend Supabase (sem ele, subir em cima de um path
    existente é erro). O filesystem sempre sobrescreve — os dois chamadores ou
    têm path único por timestamp, ou querem idempotência de propósito.
    """
    raiz = _raiz_local()
    if raiz is not None:
        destino = resolver_caminho_local(caminho)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        return caminho

    settings = get_settings()
    opcoes = {"content-type": content_type}
    if upsert:
        opcoes["upsert"] = "true"
    get_supabase().storage.from_(settings.storage_bucket).upload(
        path=caminho, file=conteudo, file_options=opcoes
    )
    return caminho


def salvar_planilha(*, arquivo_origem: str, conteudo: bytes) -> str:
    """Sobe o arquivo bruto pro Storage. Retorna o path armazenado.

    Path determinístico: `uploads/AAAA/MM/DD/HHMMSS-<arquivo>`.
    Sufixo no nome evita colisão; histórico fica organizado por data.
    """
    agora = datetime.now(timezone.utc)
    caminho = f"uploads/{agora:%Y/%m/%d}/{agora:%H%M%S}-{arquivo_origem}"
    return _salvar(caminho, conteudo, content_type="application/octet-stream")


def salvar_arquivo_simulado(*, canvas_file_id: str, nome_arquivo: str, conteudo: bytes) -> str:
    """Sobe o PDF da prova pro Storage. Retorna o path armazenado.

    Path determinístico por Canvas File id (não por simulado — o mesmo PDF
    pode cobrir várias matérias/ciclos). A escrita é idempotente: reprocessar
    o mesmo arquivo sobrescreve em vez de falhar em cima de um path existente.
    """
    caminho = f"simulados/{canvas_file_id}-{_slugificar_nome_arquivo(nome_arquivo)}"
    return _salvar(caminho, conteudo, content_type="application/pdf", upsert=True)


def gerar_url_download_arquivo(
    caminho_storage: str, *, nome_download: str, expira_em_segundos: int = 3600
) -> str:
    """URL de curta duração pro aluno baixar o PDF.

    No Supabase é uma signed URL do próprio Storage. No modo local é uma URL da
    própria API com um JWT assinado no lugar da assinatura do Supabase — mesma
    propriedade: quem tem o link baixa, o link expira, e o path do arquivo não
    trafega em claro para o browser adivinhar outro.
    """
    settings = get_settings()

    if _raiz_local() is not None:
        token = jwt.encode(
            {
                "tipo": _TIPO_TOKEN_DOWNLOAD,
                "caminho": caminho_storage,
                "nome": nome_download,
                "exp": datetime.now(timezone.utc) + timedelta(seconds=expira_em_segundos),
            },
            _segredo_download(),
            algorithm=_ALGORITMO_TOKEN,
        )
        base = settings.api_base_url.rstrip("/")
        return f"{base}/arquivos/download?token={quote(token)}"

    resposta = get_supabase().storage.from_(settings.storage_bucket).create_signed_url(
        caminho_storage, expira_em_segundos, options={"download": nome_download}
    )
    return resposta["signedURL"]


def ler_token_download(token: str) -> tuple[str, str]:
    """Valida o token do modo local e devolve (caminho_storage, nome_download).

    Levanta `jose.JWTError` se o token for inválido/expirado.
    """
    payload = jwt.decode(token, _segredo_download(), algorithms=[_ALGORITMO_TOKEN])
    if payload.get("tipo") != _TIPO_TOKEN_DOWNLOAD:
        raise ValueError("Token não é de download de arquivo.")
    return payload["caminho"], payload["nome"]
