"""Monta os templates do vídeo a partir dos assets soltos — gera os dois PNGs.

    cd api && python scripts/montar_template_gravacao.py

Requer Pillow (não é dependência da API; instale num venv avulso se precisar).

Composição, não geração: cada logo entra como o arquivo exato, sem redesenho.
Mudar posição/tamanho é mexer nos números abaixo e rodar de novo.

São DOIS templates porque nem toda aula tem tela compartilhada — quando o
professor não compartilha nada, o BigBlueButton entrega só `webcams.mp4` (ver
downloader.py). Cada um tem sua própria arrumação de logo:

  template_aula.png         duas áreas à direita de uma coluna, e a coluna
                            é que segura os logos empilhados
  template_aula_camera.png  uma área 4:3 CENTRALIZADA (proporção nativa da
                            webcam do BBB, 640x480, pra ela preencher sem
                            tarja), e os logos vão pros cantos, que é o que
                            sobra de moldura

Estes números e os de app/gravacoes_aula/compositor.py são O MESMO sistema de
coordenadas: mudou aqui, mude lá, senão o ffmpeg sobrepõe o vídeo fora do
retângulo desenhado.
"""
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1920, 1080
COLUNA = 480                      # faixa esquerda do template de duas áreas
MARGEM = 40

# Área da tela compartilhada: 16:9 para o deskshare encaixar sem tarja preta.
TELA_W, TELA_H = 1440, 810
TELA_X, TELA_Y = COLUNA, (H - TELA_H) // 2

# Área da câmera no template de duas áreas: 4:3, centralizada na coluna.
CAM_W, CAM_H = 392, 294
CAM_X, CAM_Y = (COLUNA - CAM_W) // 2, (H - CAM_H) // 2

# Aula sem tela compartilhada: uma área só, 4:3, centralizada no quadro. A
# altura é a MESMA da área grande de propósito — os dois templates ficam com o
# mesmo respiro em cima e embaixo, e a série parece uma série só quando o aluno
# abre uma aula depois da outra. Sobram 420px de moldura de cada lado, que é o
# que dá lugar confortável pros logos nos cantos.
SOLO_H = TELA_H
SOLO_W = SOLO_H * 4 // 3
SOLO_X, SOLO_Y = (W - SOLO_W) // 2, (H - SOLO_H) // 2

# Largura-alvo de cada logo (altura sai por proporção).
LARG_ARI, LARG_SAS = 300, 190
ALT_ITA, ALT_IME = 62, 92         # brasões: altura casada, não largura

BORDA = (255, 255, 255, 90)       # borda discreta nas áreas de vídeo
PRETO = (0, 16, 46)               # preenchimento das áreas de vídeo

# Os assets de origem vivem ao lado do módulo, não aqui: são a matéria-prima
# dos template_aula*.png que o compositor usa em produção.
MODULO = Path(__file__).resolve().parent.parent / "app" / "gravacoes_aula"
d = str(MODULO / "assets")


def por_largura(im, larg):
    return im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)


def por_altura(im, alt):
    return im.resize((round(im.width * alt / im.height), alt), Image.LANCZOS)


def abrir(nome):
    return Image.open(f"{d}/{nome}").convert("RGBA")


def brasoes(tela, base, *, x=None, centrado_em=None):
    """ITA e IME lado a lado, apoiados na mesma base. `x` fixa a borda
    esquerda do par; `centrado_em` centra o par numa largura."""
    ita = por_altura(abrir("ita.png"), ALT_ITA)
    ime = por_altura(abrir("ime.png"), ALT_IME)
    gap = 34
    if x is None:
        x = (centrado_em - (ita.width + gap + ime.width)) // 2
    tela.alpha_composite(ita, (x, base - ita.height - (ime.height - ita.height) // 2))
    tela.alpha_composite(ime, (x + ita.width + gap, base - ime.height))


def logos_na_coluna(tela):
    """Template de duas áreas: tudo empilhado na faixa esquerda."""
    ari = por_largura(abrir("ari.png"), LARG_ARI)
    sas = por_largura(abrir("sas.png"), LARG_SAS)
    y = MARGEM + 10
    tela.alpha_composite(ari, ((COLUNA - ari.width) // 2, y))
    y += ari.height + 24
    tela.alpha_composite(sas, ((COLUNA - sas.width) // 2, y))
    brasoes(tela, H - MARGEM - 20, centrado_em=COLUNA)


def logos_nos_cantos(tela):
    """Template centralizado: SAS em cima à esquerda, Ari em cima à direita,
    ITA e IME embaixo à esquerda.

    Os dois de cima ficam com os CENTROS na mesma altura, não com o topo: o
    Ari é quase o dobro da altura do SAS, e alinhar pelo topo deixaria o par
    visivelmente torto."""
    ari = por_largura(abrir("ari.png"), LARG_ARI)
    sas = por_largura(abrir("sas.png"), LARG_SAS)
    eixo = MARGEM + ari.height // 2
    tela.alpha_composite(ari, (W - MARGEM - ari.width, eixo - ari.height // 2))
    tela.alpha_composite(sas, (MARGEM, eixo - sas.height // 2))
    brasoes(tela, H - MARGEM - 20, x=MARGEM)


def montar(areas, logos, nome):
    """Um template: o fundo, as áreas de vídeo vazias e os logos por cima."""
    fundo = abrir("fundo.png").resize((W, H), Image.LANCZOS)
    tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    p = ImageDraw.Draw(tela)
    for x, y, w, h in areas:
        p.rectangle([x, y, x + w - 1, y + h - 1], fill=PRETO, outline=BORDA, width=2)

    logos(tela)

    fundo.alpha_composite(tela)
    saida = str(MODULO / nome)
    fundo.convert("RGB").save(saida, quality=95)
    return saida


duas = montar(
    [(TELA_X, TELA_Y, TELA_W, TELA_H), (CAM_X, CAM_Y, CAM_W, CAM_H)],
    logos_na_coluna,
    "template_aula.png",
)
print(f"gerado: {duas}")
print(f"  tela compartilhada: x={TELA_X} y={TELA_Y} {TELA_W}x{TELA_H}")
print(f"  câmera            : x={CAM_X} y={CAM_Y} {CAM_W}x{CAM_H}")

solo = montar(
    [(SOLO_X, SOLO_Y, SOLO_W, SOLO_H)], logos_nos_cantos, "template_aula_camera.png"
)
print(f"gerado: {solo}")
print(f"  câmera sozinha    : x={SOLO_X} y={SOLO_Y} {SOLO_W}x{SOLO_H}")
