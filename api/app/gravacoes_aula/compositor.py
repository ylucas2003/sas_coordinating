"""Compõe o vídeo final: template da marca + tela compartilhada + câmera.

O BigBlueButton entrega os dois componentes separados (ver downloader.py);
quem junta é o ffmpeg, sobrepondo cada um no seu lugar dentro do template
`template_aula.png` (faixa lateral com logo do Ari, SAS ITA/IME e escudos
ITA/IME; o resto do quadro é vazio de propósito, pra receber os vídeos).

As coordenadas abaixo foram MEDIDAS na imagem original (1672x941, por
análise de pixel dos retângulos vazios) e escaladas para 1920x1080 — o
fator é praticamente igual nos dois eixos (~1.148), então não distorce.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

TEMPLATE = Path(__file__).parent / "template_aula.png"

LARGURA_SAIDA, ALTURA_SAIDA = 1920, 1080
# Área grande (tela compartilhada) e área pequena (câmera, canto inferior direito).
#
# Todas as dimensões são PARES de propósito: o h264 em yuv420p exige lado par,
# e o `scale` arredonda pra cima pra conseguir isso — com um lado ímpar aqui,
# o vídeo escalado fica 1px maior que o `pad` de destino e o ffmpeg aborta com
# "Padded dimensions cannot be smaller than input dimensions".
TELA_X, TELA_Y, TELA_W, TELA_H = 482, 0, 1438, 1080
CAM_X, CAM_Y, CAM_W, CAM_H = 1479, 736, 392, 278

# Teto de núcleos do ffmpeg. A composição divide CPU com a API que serve o
# site — melhor a aula demorar mais do que o site engasgar no horário de aula.
THREADS_FFMPEG = 2

# Teto de duração. Com 2 threads, 93 min de 1080p levam de 30 a 60 min; 4 h dá
# folga larga para a aula mais longa e ainda assim garante que um ffmpeg travado
# não segure a trava de processamento indefinidamente.
TIMEOUT_FFMPEG_SEGUNDOS = 4 * 3600

# FPS de saída, fixado de propósito. A webcam do BBB vem a 15 fps e a tela
# compartilhada a 5 fps; sem declarar nada, o ffmpeg adota 25 fps (o default do
# `-loop 1` da imagem) e passa a duplicar os frames de 15 em 25 de forma
# irregular — vídeo picotado E, pior, a linha de tempo do vídeo estica em
# relação ao áudio (medido: 1s de dessincronia em 20s de teste, o que numa aula
# de 93 min vira minutos). Casar com a taxa da webcam elimina os dois.
FPS_SAIDA = 15


class FalhaNaComposicao(Exception):
    pass


def _caminho_seguro(caminho: Path) -> str:
    """Absolutiza antes de virar argumento do ffmpeg.

    Não é sobre shell injection (a chamada é lista, sem `shell=True`): é que
    um caminho relativo começando com "-" seria lido pelo ffmpeg como FLAG,
    não como arquivo. Absoluto sempre começa com "/", então nunca colide."""
    return str(caminho.resolve())


def compor(
    *, webcam: Path, tela_compartilhada: Path | None, destino: Path
) -> Path:
    """Gera o mp4 final. Sem tela compartilhada (aula que não usou), a câmera
    ocupa a área grande em vez do cantinho — senão sobraria um quadro quase
    todo vazio."""
    if tela_compartilhada is not None:
        filtro = (
            f"[0:v]scale={LARGURA_SAIDA}:{ALTURA_SAIDA},fps={FPS_SAIDA}[bg];"
            f"[1:v]scale={TELA_W}:{TELA_H}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={TELA_W}:{TELA_H}:(ow-iw)/2:(oh-ih)/2:color=black@0,fps={FPS_SAIDA}[tela];"
            f"[2:v]scale={CAM_W}:{CAM_H}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={CAM_W}:{CAM_H}:(ow-iw)/2:(oh-ih)/2:color=black@0,fps={FPS_SAIDA}[cam];"
            f"[bg][tela]overlay={TELA_X}:{TELA_Y}[tmp];"
            f"[tmp][cam]overlay={CAM_X}:{CAM_Y}:shortest=1[out]"
        )
        entradas = [
            "-i", _caminho_seguro(TEMPLATE),
            "-i", _caminho_seguro(tela_compartilhada),
            "-i", _caminho_seguro(webcam),
        ]
        audio = "2:a"
    else:
        filtro = (
            f"[0:v]scale={LARGURA_SAIDA}:{ALTURA_SAIDA},fps={FPS_SAIDA}[bg];"
            f"[1:v]scale={TELA_W}:{TELA_H}:force_original_aspect_ratio=decrease:force_divisible_by=2,"
            f"pad={TELA_W}:{TELA_H}:(ow-iw)/2:(oh-ih)/2:color=black@0,fps={FPS_SAIDA}[cam];"
            f"[bg][cam]overlay={TELA_X}:{TELA_Y}:shortest=1[out]"
        )
        entradas = ["-i", _caminho_seguro(TEMPLATE), "-i", _caminho_seguro(webcam)]
        audio = "1:a"

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FalhaNaComposicao("ffmpeg não encontrado no PATH do container")

    comando = [
        ffmpeg, "-y",
        # `-framerate` ANTES do -loop: declara a taxa da imagem em vez de deixar
        # o ffmpeg adotar 25 fps e reamostrar todo o resto em cima disso.
        "-framerate", str(FPS_SAIDA), "-loop", "1", *entradas,
        "-filter_complex", filtro,
        # Os dois tetos de CPU precisam vir DEPOIS das entradas: `-threads`
        # antes do primeiro `-i` é opção de ENTRADA e limitaria só o decoder do
        # PNG, deixando o x264 (que é quem realmente queima CPU) livre para
        # tomar todos os núcleos. Isto roda no MESMO container que serve o site
        # para ~900 alunos: melhor a aula demorar do que o site engasgar.
        "-filter_complex_threads", str(THREADS_FFMPEG),
        "-map", "[out]", "-map", audio,
        "-c:v", "libx264", "-threads", str(THREADS_FFMPEG),
        "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        # CFR explícito: sem isto o mux ainda pode gravar timestamps
        # irregulares (frames faltando no meio), que é o que se vê como
        # "picotado" mesmo com a taxa certa declarada.
        "-r", str(FPS_SAIDA), "-fps_mode", "cfr",
        # Corrige deriva do áudio inserindo/removendo amostras em vez de
        # deixar a dessincronia acumular ao longo dos 93 min.
        "-af", "aresample=async=1",
        "-shortest",
        _caminho_seguro(destino),
    ]
    # S603: a chamada é lista (sem shell=True), o binário vem resolvido do
    # PATH por shutil.which e todo caminho passa por _caminho_seguro() — não
    # há shell nem argumento capaz de virar flag. O filtro é montado só de
    # constantes deste módulo.
    #
    # O `timeout` não é decoração: sem ele, um ffmpeg que trave (arquivo
    # corrompido, filtro que nunca converge) segura a trava de processamento
    # para sempre e nenhuma aula volta a ser publicada — com o processo vivo,
    # nem a varredura de órfãos resolve.
    try:
        resultado = subprocess.run(  # noqa: S603
            comando, capture_output=True, text=True, timeout=TIMEOUT_FFMPEG_SEGUNDOS
        )
    except subprocess.TimeoutExpired as exc:
        raise FalhaNaComposicao(
            f"ffmpeg passou de {TIMEOUT_FFMPEG_SEGUNDOS}s e foi abortado"
        ) from exc
    if resultado.returncode != 0:
        # stderr do ffmpeg é longo; as últimas linhas é que dizem o que falhou.
        raise FalhaNaComposicao(
            f"ffmpeg falhou ({resultado.returncode}): {resultado.stderr[-1500:]}"
        )
    return destino
