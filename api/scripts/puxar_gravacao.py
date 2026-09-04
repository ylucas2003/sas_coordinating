#!/usr/bin/env python3
"""Baixa a gravação de uma conferência do Canvas, à mão, agora.

A publicação normal é automática: o cron roda de hora em hora e o
`gravacoes_aula/` baixa, compõe e publica. Esta escotilha existe porque a
gravação **some do Canvas em ~7 dias** — quando o pipeline falhou, ou quando
alguém só quer o arquivo bruto, esperar o próximo ciclo pode custar a aula.

Uso (a partir de api/):
    python -m scripts.puxar_gravacao 693 "AULA 19 - 26/08"
    python -m scripts.puxar_gravacao 693 --listar
    python -m scripts.puxar_gravacao 693 "AULA 19" --destino /tmp/aula19

⚠️ Este script NÃO reimplementa o download. Ele chama
`gravacoes_aula.downloader`, que é onde mora o que custou caro descobrir: que
o vídeo bruto é `.mp4` e não `.webm`, que o `resourceToken` da URL de replay é
de USO ÚNICO, e que 403/404 no deskshare significa "esta aula não compartilhou
tela" enquanto qualquer outro código é erro de verdade. Existiu uma cópia
disso solta na raiz do repositório, fora do git; ela foi apagada em 03/09/2026
justamente para o conhecimento não ter duas versões para divergir.

Conexão: CANVAS_BASE_URL / CANVAS_API_TOKEN do .env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.canvas_sync.cliente import ClienteCanvas  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.gravacoes_aula.downloader import (  # noqa: E402
    FalhaNoDownload,
    GravacaoIndisponivel,
    baixar_video,
)


def _casa(conferencia: dict, trecho: str) -> bool:
    """Casamento por trecho do título, sem diferenciar maiúscula.

    O identificador que o `downloader` quer é o `id` numérico, mas ninguém
    tem esse número em mãos — o que se sabe é "a aula 19, do dia 26/08". Daí
    a busca por trecho: é o dado que a pessoa tem quando precisa da escotilha.
    """
    return trecho.casefold() in str(conferencia.get("title") or "").casefold()


def _descrever(conferencia: dict) -> str:
    gravacoes = conferencia.get("recordings") or []
    marca = "com gravação" if gravacoes else "SEM gravação (processando ou expirada)"
    return f"  {conferencia.get('id'):>8}  {conferencia.get('title')}  —  {marca}"


async def _rodar(course_id: str, trecho: str | None, destino: Path, listar: bool) -> int:
    settings = get_settings()
    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        conferencias = await canvas.listar_conferencias(course_id)
        if not conferencias:
            print(f"curso {course_id} não tem conferência nenhuma.")
            return 1

        if listar:
            print(f"{len(conferencias)} conferência(s) no curso {course_id}:")
            for conf in conferencias:
                print(_descrever(conf))
            return 0

        achadas = [c for c in conferencias if _casa(c, trecho or "")]
        if not achadas:
            print(f"nenhuma conferência casa com {trecho!r}. As que existem:")
            for conf in conferencias:
                print(_descrever(conf))
            return 1
        # Ambiguidade não vira escolha silenciosa: baixar a aula errada só se
        # descobre depois de assistir, e o token de replay já teria queimado.
        if len(achadas) > 1:
            print(f"{trecho!r} casa com {len(achadas)} conferências — seja mais específico:")
            for conf in achadas:
                print(_descrever(conf))
            return 1

        conferencia = achadas[0]
        print(f"→ {conferencia.get('title')} (id {conferencia.get('id')})")
        video = await baixar_video(canvas, course_id, str(conferencia["id"]), destino)

    print(f"✓ webcam            {video.webcam}")
    if video.tela_compartilhada:
        print(f"✓ tela compartilhada {video.tela_compartilhada}")
    else:
        print("  (esta aula não compartilhou tela — só a webcam)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("course_id", help="id do curso no Canvas (ex.: 693)")
    p.add_argument("trecho", nargs="?", help="trecho do título da conferência")
    p.add_argument("--listar", action="store_true", help="só lista as conferências do curso")
    p.add_argument(
        "--destino",
        type=Path,
        default=Path("gravacao"),
        help="diretório de saída (padrão: ./gravacao)",
    )
    args = p.parse_args()

    if not args.listar and not args.trecho:
        p.error("informe o trecho do título, ou use --listar para ver as opções")

    try:
        return asyncio.run(_rodar(args.course_id, args.trecho, args.destino, args.listar))
    except GravacaoIndisponivel as e:
        # Situação normal, não defeito: a retenção do Canvas é de ~7 dias.
        print(f"gravação indisponível — {e}")
        return 1
    except FalhaNoDownload as e:
        print(f"falha no download — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
