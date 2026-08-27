"""Baixa os componentes de vídeo de uma conferência do Canvas/BigBlueButton.

Não existe download de arquivo único nesse plano de hospedagem do BBB
(confirmado em 26-27/08/2026 testando direto no servidor de gravações) —
mas existe sim vídeo bruto real por trás da página de replay:
`video/webcams.mp4` (câmera + áudio) e `deskshare/deskshare.mp4` (tela
compartilhada, sem áudio próprio, só existe se a aula usou compartilhamento
de tela). Confirmado com `ffprobe` em duas conferências reais independentes.

O `resourceToken` da URL de replay (`recordings[].playback_formats[0].url`)
é de USO ÚNICO — por isso a chamada que autentica (segue o redirect e ganha
os cookies assinados pela CloudFront) precisa acontecer uma vez só, na
mesma sessão HTTP que baixa os arquivos.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ..canvas_sync.cliente import ClienteCanvas

_ASSETS = [
    ("video/webcams.mp4", "webcam.mp4"),
    ("deskshare/deskshare.mp4", "tela_compartilhada.mp4"),
]


@dataclass
class VideoBaixado:
    webcam: Path
    tela_compartilhada: Path | None


class GravacaoIndisponivel(Exception):
    """A conferência não tem `recordings` (ainda processando, ou já expirou —
    a retenção do Canvas é de ~7 dias)."""


class FalhaNoDownload(Exception):
    """Erro real ao buscar um componente que deveria existir — diferente de
    "esta aula não tem tela compartilhada", que é situação normal."""


# 403/404 no deskshare = a aula não compartilhou tela (o BBB nem gera o
# arquivo). QUALQUER outro código é erro de verdade e precisa virar retentativa
# — tratar 5xx como "sem tela" publicaria a aula mutilada, sem o quadro, e
# marcaria como publicada com sucesso.
_STATUS_ASSET_INEXISTENTE = (403, 404)


async def obter_conferencia(
    canvas: ClienteCanvas, course_id: str, conferencia_id: str
) -> dict[str, Any]:
    conferencias = await canvas.listar_conferencias(course_id)
    for conf in conferencias:
        if str(conf.get("id")) == str(conferencia_id):
            return conf
    raise GravacaoIndisponivel(
        f"conferência {conferencia_id} não encontrada no curso {course_id}"
    )


async def baixar_video(
    canvas: ClienteCanvas, course_id: str, conferencia_id: str, destino_dir: Path
) -> VideoBaixado:
    conf = await obter_conferencia(canvas, course_id, conferencia_id)
    recs = conf.get("recordings") or []
    if not recs:
        raise GravacaoIndisponivel(
            f"'{conf.get('title')}' ainda não tem gravação disponível"
        )
    playback_url = recs[0]["playback_formats"][0]["url"]

    await asyncio.to_thread(destino_dir.mkdir, parents=True, exist_ok=True)
    caminhos: dict[str, Path] = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=60) as sessao:
        r = await sessao.get(playback_url)
        if r.status_code != 200:
            raise GravacaoIndisponivel(
                f"não autenticou na página de replay (status {r.status_code}) — "
                "o resourceToken pode já ter sido usado"
            )
        base_pasta = str(r.url).rsplit("/presentation/", 1)[0] + "/presentation"

        for caminho_remoto, nome_local in _ASSETS:
            destino = destino_dir / nome_local
            async with sessao.stream(
                "GET", f"{base_pasta}/{caminho_remoto}", headers={"Referer": str(r.url)}
            ) as resp:
                if resp.status_code in _STATUS_ASSET_INEXISTENTE:
                    continue
                if resp.status_code != 200:
                    raise FalhaNoDownload(
                        f"{caminho_remoto} devolveu {resp.status_code} — erro de "
                        "transporte, não ausência do componente"
                    )
                arquivo = await asyncio.to_thread(open, destino, "wb")
                try:
                    async for pedaco in resp.aiter_bytes(chunk_size=1024 * 1024):
                        await asyncio.to_thread(arquivo.write, pedaco)
                finally:
                    await asyncio.to_thread(arquivo.close)
            caminhos[nome_local] = destino

    if "webcam.mp4" not in caminhos:
        raise GravacaoIndisponivel("webcam.mp4 não pôde ser baixado")

    return VideoBaixado(
        webcam=caminhos["webcam.mp4"],
        tela_compartilhada=caminhos.get("tela_compartilhada.mp4"),
    )
