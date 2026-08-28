"""Monta o template do vídeo a partir dos assets soltos — gera template_aula.png.

    cd api && python scripts/montar_template_gravacao.py

Requer Pillow (não é dependência da API; instale num venv avulso se precisar).

Composição, não geração: cada logo entra como o arquivo exato, sem redesenho.
Mudar posição/tamanho é mexer nos números abaixo e rodar de novo.
"""
from pathlib import Path

from PIL import Image, ImageDraw

W, H = 1920, 1080
COLUNA = 480                      # faixa esquerda
MARGEM = 40

# Área da tela compartilhada: 16:9 para o deskshare encaixar sem tarja preta.
TELA_W, TELA_H = 1440, 810
TELA_X, TELA_Y = COLUNA, (H - TELA_H) // 2

# Área da câmera: 4:3, centralizada verticalmente na coluna.
CAM_W, CAM_H = 392, 294
CAM_X, CAM_Y = (COLUNA - CAM_W) // 2, (H - CAM_H) // 2

# Largura-alvo de cada logo (altura sai por proporção).
LARG_ARI, LARG_SAS = 300, 190
ALT_ITA, ALT_IME = 62, 92         # brasões: altura casada, não largura

BORDA = (255, 255, 255, 90)       # borda discreta nas áreas de vídeo
PRETO = (0, 16, 46)               # preenchimento das áreas de vídeo

# Os assets de origem vivem ao lado do módulo, não aqui: são a matéria-prima
# do template_aula.png que o compositor usa em produção.
MODULO = Path(__file__).resolve().parent.parent / "app" / "gravacoes_aula"
d = str(MODULO / "assets")


def por_largura(im, larg):
    return im.resize((larg, round(im.height * larg / im.width)), Image.LANCZOS)


def por_altura(im, alt):
    return im.resize((round(im.width * alt / im.height), alt), Image.LANCZOS)


fundo = Image.open(f"{d}/fundo.png").convert("RGBA").resize((W, H), Image.LANCZOS)
tela = Image.new("RGBA", (W, H), (0, 0, 0, 0))

# --- áreas de vídeo: preenchidas e com borda fina ---
p = ImageDraw.Draw(tela)
for x, y, w, h in ((TELA_X, TELA_Y, TELA_W, TELA_H), (CAM_X, CAM_Y, CAM_W, CAM_H)):
    p.rectangle([x, y, x + w - 1, y + h - 1], fill=PRETO, outline=BORDA, width=2)

# --- topo da coluna: Ari e SAS ---
ari = por_largura(Image.open(f"{d}/ari.png").convert("RGBA"), LARG_ARI)
sas = por_largura(Image.open(f"{d}/sas.png").convert("RGBA"), LARG_SAS)
y = MARGEM + 10
tela.alpha_composite(ari, ((COLUNA - ari.width) // 2, y))
y += ari.height + 24
tela.alpha_composite(sas, ((COLUNA - sas.width) // 2, y))

# --- base da coluna: ITA e IME lado a lado ---
ita = por_altura(Image.open(f"{d}/ita.png").convert("RGBA"), ALT_ITA)
ime = por_altura(Image.open(f"{d}/ime.png").convert("RGBA"), ALT_IME)
gap = 34
larg_total = ita.width + gap + ime.width
x = (COLUNA - larg_total) // 2
base = H - MARGEM - 20
tela.alpha_composite(ita, (x, base - ita.height - (ime.height - ita.height) // 2))
tela.alpha_composite(ime, (x + ita.width + gap, base - ime.height))

fundo.alpha_composite(tela)
saida = str(MODULO / "template_aula.png")
fundo.convert("RGB").save(saida, quality=95)
print(f"gerado: {saida}")
print(f"  tela compartilhada: x={TELA_X} y={TELA_Y} {TELA_W}x{TELA_H}")
print(f"  câmera            : x={CAM_X} y={CAM_Y} {CAM_W}x{CAM_H}")
print(f"  ari {ari.width}x{ari.height} | sas {sas.width}x{sas.height} | "
      f"ita {ita.width}x{ita.height} | ime {ime.width}x{ime.height}")
