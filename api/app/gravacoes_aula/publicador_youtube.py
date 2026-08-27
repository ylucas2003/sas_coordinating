"""Publica o vídeo composto no YouTube (Data API v3).

Privacidade é `unlisted` ("não listado") e NÃO é parâmetro: são aulas com
aluno menor de idade aparecendo na câmera e no chat (LGPD — mesma régua do
item 6 do CLAUDE.md raiz). Não listado é o suficiente pro caso de uso (o
aluno recebe o link), sem expor a gravação em busca ou no canal público.

A credencial é OAuth de usuário (não service account: só uma conta com acesso
ao canal pode publicar). O refresh token é gerado uma vez, fora daqui, no
Google Cloud Console + fluxo de consentimento; sem ele configurado a função
falha com mensagem explícita em vez de tentar adivinhar.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from ..config import get_settings

_log = logging.getLogger(__name__)

# Os DOIS são necessários, e por motivos diferentes:
#   youtube.upload   — videos.insert, o envio em si;
#   youtube.readonly — channels.list / playlistItems.list / videos.list, que
#                      `ja_publicado()` usa para não republicar a mesma aula.
# Só com o primeiro, a consulta ao canal falha com 403 insufficientPermissions.
ESCOPOS = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
# Endpoint público do OAuth do Google (onde o refresh token é trocado por um
# access token), não um segredo.
_ENDPOINT_OAUTH_GOOGLE = "https://oauth2.googleapis.com/token"

# Páginas de 50 vídeos varridas por `ja_publicado`. 3 páginas = 150 uploads
# mais recentes: a aula procurada subiu há minutos ou horas, então varrer o
# canal inteiro (anos de vídeo) só gastaria cota da API.
_PAGINAS_BUSCA = 3

# "unlisted" é o que o colégio quer: o aluno abre pelo link, e a aula não
# aparece em busca nem no canal público. Ver a nota em `publicar` sobre por que
# o YouTube pode devolver "private" mesmo assim.
PRIVACIDADE_PRETENDIDA = "unlisted"


class YouTubeNaoConfigurado(Exception):
    pass


def _servico() -> Any:
    # Import tardio: as libs do Google só são necessárias quando há publicação
    # de verdade (mesmo padrão de lembretes/email.py com o boto3).
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    settings = get_settings()
    faltando = [
        nome
        for nome, valor in (
            ("YOUTUBE_CLIENT_ID", settings.youtube_client_id),
            ("YOUTUBE_CLIENT_SECRET", settings.youtube_client_secret),
            ("YOUTUBE_REFRESH_TOKEN", settings.youtube_refresh_token),
        )
        if not valor
    ]
    if faltando:
        raise YouTubeNaoConfigurado(
            f"credencial do YouTube incompleta: {', '.join(faltando)} — "
            "gerar no Google Cloud Console (YouTube Data API v3 + OAuth)"
        )

    credenciais = Credentials(
        token=None,
        refresh_token=settings.youtube_refresh_token,
        client_id=settings.youtube_client_id,
        client_secret=settings.youtube_client_secret,
        token_uri=_ENDPOINT_OAUTH_GOOGLE,
        scopes=ESCOPOS,
    )
    return build("youtube", "v3", credentials=credenciais, cache_discovery=False)


def marcador(curso_id: str, conferencia_id: str) -> str:
    """Etiqueta que amarra o vídeo do canal à linha de aula_gravacao.

    Vai na descrição porque é o único campo que sobrevive à publicação e pode
    ser consultado depois. É o que torna `ja_publicado()` possível — e sem ele
    não há como saber que uma aula já subiu quando o id se perde no caminho."""
    return f"[sas:{curso_id}:{conferencia_id}]"


def ja_publicado(curso_id: str, conferencia_id: str) -> str | None:
    """Procura no canal um vídeo já publicado para esta aula; devolve o id.

    Existe por causa de uma janela que nenhum retry do nosso lado fecha: o
    upload pode ser COMITADO pelo YouTube e a resposta se perder (socket cai,
    503 pós-commit). Aí o vídeo existe no canal e o id nunca chega ao processo
    — e retentar publicaria uma segunda cópia de menores de idade, sem registro
    para atender a um pedido de eliminação (LGPD art. 18, VI).

    O canal é a única fonte de verdade sobre "isto já foi publicado?", então é
    ele que se consulta, não o nosso banco. Varre só as páginas recentes: a
    aula em questão foi publicada há minutos ou horas, nunca no fim da lista.
    """
    servico = _servico()
    alvo = marcador(curso_id, conferencia_id)

    canais = servico.channels().list(part="contentDetails", mine=True).execute()
    itens = canais.get("items") or []
    if not itens:
        raise YouTubeNaoConfigurado("credencial do YouTube não tem canal associado")
    playlist_uploads = itens[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    pagina = None
    for _ in range(_PAGINAS_BUSCA):
        resposta = (
            servico.playlistItems()
            .list(part="snippet", playlistId=playlist_uploads, maxResults=50, pageToken=pagina)
            .execute()
        )
        for item in resposta.get("items", []):
            trecho = item.get("snippet") or {}
            if alvo in (trecho.get("description") or ""):
                return (trecho.get("resourceId") or {}).get("videoId")
        pagina = resposta.get("nextPageToken")
        if not pagina:
            break
    return None


def publicar(
    caminho: Path, *, titulo: str, curso_id: str, conferencia_id: str, descricao: str = ""
) -> str:
    """Sobe o vídeo e devolve o id no YouTube.

    A descrição sempre carrega o `marcador()` — é ele que permite reconhecer
    esta aula no canal depois, caso o id se perca entre o commit do upload e a
    gravação no banco."""
    from googleapiclient.http import MediaFileUpload

    etiqueta = marcador(curso_id, conferencia_id)
    corpo = {
        "snippet": {
            "title": titulo[:100],  # limite duro da API
            "description": f"{descricao}\n\n{etiqueta}".strip(),
            "categoryId": "27",     # Education
        },
        "status": {
            # Pedimos "unlisted", mas o YouTube pode NÃO obedecer: projeto de
            # API criado depois de 28/07/2020 e ainda não auditado tem todo
            # upload por videos.insert forçado a "private" — a API responde 200
            # e o vídeo fica privado. Por isso a privacidade real é conferida
            # depois do upload, e não presumida (ver abaixo).
            # https://developers.google.com/youtube/v3/docs/videos/insert
            "privacyStatus": PRIVACIDADE_PRETENDIDA,
            "selfDeclaredMadeForKids": False,
        },
    }
    midia = MediaFileUpload(str(caminho), chunksize=-1, resumable=True, mimetype="video/mp4")
    requisicao = _servico().videos().insert(part="snippet,status", body=corpo, media_body=midia)
    # num_retries cobre a falha de transporte ANTES do commit; a janela do
    # pós-commit é coberta por ja_publicado(), não aqui.
    resposta = requisicao.execute(num_retries=3)

    # Confere o que o YouTube REALMENTE aplicou. Enquanto o projeto de API não
    # passar pela auditoria de compliance, o vídeo volta como "private" mesmo
    # tendo sido pedido "unlisted" — e aí o aluno com o link não assiste. Sem
    # este aviso, o banco registraria "publicado" e ninguém descobriria até
    # alguém reclamar que o link não abre. Vídeo travado assim NÃO tem
    # apelação: precisa ser reenviado depois da auditoria.
    aplicada = ((resposta.get("status") or {}).get("privacyStatus")) or "desconhecida"
    if aplicada != PRIVACIDADE_PRETENDIDA:
        _log.warning(
            "YouTube devolveu privacidade %r em vez de %r para o vídeo %s — provável "
            "projeto de API ainda não auditado (videos.insert força 'private'). "
            "O link não funcionará para os alunos até a auditoria ser concluída.",
            aplicada,
            PRIVACIDADE_PRETENDIDA,
            resposta["id"],
        )
    return resposta["id"]
