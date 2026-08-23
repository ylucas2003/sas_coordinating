"""
recortar_questoes.py — Etapa 2 do pipeline.

Objetivo: para cada questão já identificada no JSON, gerar uma IMAGEM PNG
contendo o enunciado + alternativas + figuras (tudo junto, como aparece no PDF).

Estratégia:
  1. Em cada página, localizar as ocorrências de "Questão N." (onde N está
     na faixa da matéria) e suas coordenadas (bounding boxes) na página.
  2. Para cada questão N:
       - Determinar a página e o Y inicial (topo do "Questão N.").
       - Determinar o Y final:
           * se a próxima questão está na MESMA página: topo de "Questão N+1"
           * se a próxima questão está em OUTRA página: fim da página atual
             + recortar também o topo da próxima página até "Questão N+1".
       - Renderizar o(s) recorte(s) em alta resolução e salvar como PNG.
  3. Atualizar o JSON da questão com o caminho da imagem.

Para páginas escaneadas, usamos OCR para localizar as marcas "Questão N".

Uso:
    python recortar_questoes.py <prova_id>
    ex: python recortar_questoes.py ita_2019_fase1
"""

import argparse
import io
import json
import os
import re
from pathlib import Path
from typing import Optional
import fitz  # PyMuPDF

try:
    import pytesseract
    from PIL import Image
    OCR_DISPONIVEL = True
except ImportError:
    OCR_DISPONIVEL = False

try:
    import boto3
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    _S3_KEY    = os.getenv("AWS_ACCESS_KEY_ID")
    _S3_SECRET = os.getenv("AWS_SECRET_ACCESS_KEY")
    _S3_REGION = os.getenv("AWS_REGION", "us-east-1")
    _S3_BUCKET = os.getenv("S3_BUCKET")
    S3_DISPONIVEL = bool(_S3_KEY and _S3_SECRET and _S3_BUCKET)
except ImportError:
    S3_DISPONIVEL = False


# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_PDFS = PROJETO_ROOT / "pdfs_originais"
DIR_QUESTOES_JSON = PROJETO_ROOT / "questoes_json"
DIR_IMAGENS = PROJETO_ROOT / "imagens"

# DPI alto para que a imagem final renderize com nitidez em qualquer tela.
# 200 dpi é bom para tela; 300 dpi se você quer imprimir.
DPI_RECORTE = 200

# Margem (em pontos PDF) acima do "Questão N" para não cortar letra.
# 1 ponto ≈ 0.35mm; 5 pontos é quase imperceptível mas evita cortes feios.
MARGEM_TOPO = 5
MARGEM_LATERAL = 15  # corta cabeçalhos/rodapés laterais


# ============================================================================
# LOCALIZAÇÃO DE "QUESTÃO N." EM PÁGINAS NATIVAS
# ============================================================================

# Para páginas nativas, usamos page.search_for() — busca exata de strings.
# O ITA compõe em LaTeX, então "Quest˜ao" ou "Questão" podem aparecer.
# Tentamos várias variantes e pegamos a que funcionar.

VARIANTES_QUESTAO_ITA = [
    "Questão {n}.",
    "Questão {n} .",
    "Quest˜ao {n}.",   # com til combinante
    "Quest˜ao {n} .",
    "Questao {n}.",    # sem acento
]

VARIANTES_QUESTAO_IME = [
    "{n}ª QUESTÃO",
    "{n}ª Questão",
    "{n}a QUESTÃO",    # ª pode ser encodado como 'a' em alguns PDFs
    "{n}ª questão",
    "{n}ª QUEST \u02dcAO",  # IME 2020: til separado (U+02DC) após espaço
    "{n}ª QUEST ˜AO",       # literal (mesma variante acima)
]

# retrocompatibilidade
VARIANTES_QUESTAO = VARIANTES_QUESTAO_ITA


def localizar_questoes_pagina_nativa(
    page: fitz.Page, numeros: list[int], vestibular: str = "ITA"
) -> dict[int, fitz.Rect]:
    """
    Dada uma página nativa e uma lista de números de questão esperados,
    retorna um dict {numero: Rect} com o bounding box do texto "Questão N."
    na página. Ignora números que não estão na página.
    """
    variantes = VARIANTES_QUESTAO_IME if vestibular.upper() == "IME" else VARIANTES_QUESTAO_ITA
    achados = {}
    for n in numeros:
        for variante in variantes:
            termo = variante.format(n=n)
            rects = page.search_for(termo)
            if rects:
                achados[n] = rects[0]
                break
    return achados


# ============================================================================
# LOCALIZAÇÃO EM PÁGINAS ESCANEADAS (via OCR com coordenadas)
# ============================================================================

def _ocr_procurar_marcadores(data, fator, numeros, is_ime, achados):
    """Percorre tokens OCR e adiciona posições de marcadores ainda não achados."""
    tokens = data["text"]
    for i, tok in enumerate(tokens):
        tok_limpo = tok.strip().lower().replace("ã", "a").replace("˜a", "a")
        if is_ime:
            tok_sem_suffix = tok_limpo.rstrip("aº°ª")
            if tok_sem_suffix.isdigit():
                num = int(tok_sem_suffix)
                for j in range(i + 1, min(i + 3, len(tokens))):
                    prox = tokens[j].strip().lower().replace("ã", "a")
                    if prox in ("questao", "questão", "quest"):
                        if num in numeros and num not in achados:
                            x = data["left"][i] * fator
                            y = data["top"][i] * fator
                            w = data["width"][i] * fator
                            h = data["height"][i] * fator
                            achados[num] = fitz.Rect(x, y, x + w, y + h)
                        break
        else:
            if tok_limpo in ("questão", "questao", "quest"):
                for j in range(i + 1, min(i + 4, len(tokens))):
                    prox = tokens[j].strip().rstrip(".")
                    if prox.isdigit():
                        num = int(prox)
                        if num in numeros and num not in achados:
                            x = data["left"][i] * fator
                            y = data["top"][i] * fator
                            w = data["width"][i] * fator
                            h = data["height"][i] * fator
                            achados[num] = fitz.Rect(x, y, x + w, y + h)
                        break


def localizar_questoes_pagina_escaneada(
    page: fitz.Page, numeros: list[int], dpi: int = DPI_RECORTE, vestibular: str = "ITA"
) -> dict[int, fitz.Rect]:
    """
    Para páginas escaneadas, renderiza a página e usa Tesseract com
    `image_to_data` (que retorna posições dos tokens) para encontrar onde
    está cada "Questão N" e converter de volta para coordenadas PDF.

    Tenta múltiplos PSM (6 → 11 → 3) para cobrir layouts onde o cabeçalho
    da questão está isolado no topo da página e o modo 6 não segmenta bem.
    """
    if not OCR_DISPONIVEL:
        return {}

    pix = page.get_pixmap(dpi=dpi)
    img_path = "/tmp/_ocr_page.png"
    pix.save(img_path)
    img = Image.open(img_path)

    fator = 72.0 / dpi
    is_ime = vestibular.upper() == "IME"
    achados: dict[int, fitz.Rect] = {}

    for psm in (6, 11, 3):
        if set(numeros).issubset(achados.keys()):
            break
        data = pytesseract.image_to_data(
            img, lang="por", output_type=pytesseract.Output.DICT,
            config=f"--psm {psm}",
        )
        _ocr_procurar_marcadores(data, fator, numeros, is_ime, achados)

    # Fallback IME: para cada "QUESTÃO" isolado que não foi pareado com um
    # número, re-OCR da região imediatamente à esquerda usando whitelist
    # numérica (casos em que o tesseract lê "4º" como "dE").
    if is_ime and not set(numeros).issubset(achados.keys()):
        for psm in (6, 11, 3):
            if set(numeros).issubset(achados.keys()):
                break
            data = pytesseract.image_to_data(
                img, lang="por", output_type=pytesseract.Output.DICT,
                config=f"--psm {psm}",
            )
            tokens = data["text"]
            for i, tok in enumerate(tokens):
                tok_up = tok.strip().upper().replace("Ã", "A")
                if tok_up not in ("QUESTAO", "QUESTÃO"):
                    continue
                prev = tokens[i - 1].strip().lower().replace("ã", "a") if i > 0 else ""
                if prev.rstrip("aº°ª").isdigit():
                    continue
                left = data["left"][i]
                top = data["top"][i]
                height = data["height"][i]
                crop_box = (max(0, left - 140), max(0, top - 5),
                            left, top + height + 5)
                crop = img.crop(crop_box)
                # Coleta candidatos de vários PSMs e escolhe um que bata com
                # os números esperados da prova.
                candidatos = []
                for psm_fb in (8, 7, 10, 13):
                    txt_fb = pytesseract.image_to_string(
                        crop, lang="por",
                        config=f"--psm {psm_fb} -c tessedit_char_whitelist=0123456789ºª°",
                    ).strip()
                    for grupo in re.findall(r"\d+", txt_fb):
                        candidatos.append(int(grupo))
                num = next((c for c in candidatos if c in numeros), None)
                if num is None:
                    continue
                if num in numeros and num not in achados:
                    x = left * fator
                    y = top * fator
                    w = data["width"][i] * fator
                    h = height * fator
                    achados[num] = fitz.Rect(x, y, x + w, y + h)

    return achados


# ============================================================================
# RECORTE E COMPOSIÇÃO DAS IMAGENS
# ============================================================================

def recortar_regiao_pagina(
    page: fitz.Page, y_top: float, y_bot: float, dpi: int = DPI_RECORTE
):
    """
    Renderiza a região [y_top, y_bot] da página (mantendo largura quase
    total) e retorna um objeto Pixmap.

    y_top e y_bot são em coordenadas PDF (pontos).
    """
    page_rect = page.rect
    # Clip: margens laterais pequenas para remover cabeçalho/rodapé se
    # eles forem visuais de margem. Mas na prova do ITA o texto ocupa
    # quase toda a largura, então cortamos só um pouquinho.
    x0 = MARGEM_LATERAL
    x1 = page_rect.width - MARGEM_LATERAL
    clip = fitz.Rect(x0, y_top, x1, y_bot)
    pix = page.get_pixmap(dpi=dpi, clip=clip)
    return pix


def compor_verticalmente(pixmaps: list) -> fitz.Pixmap:
    """
    Quando uma questão atravessa páginas, temos vários Pixmaps e precisamos
    empilhá-los verticalmente em uma única imagem. PyMuPDF não faz isso
    nativamente; usamos PIL.
    """
    if len(pixmaps) == 1:
        return pixmaps[0]

    imagens_pil = []
    for pix in pixmaps:
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        imagens_pil.append(img)

    largura = max(img.width for img in imagens_pil)
    altura_total = sum(img.height for img in imagens_pil)

    nova = Image.new("RGB", (largura, altura_total), "white")
    y = 0
    for img in imagens_pil:
        nova.paste(img, (0, y))
        y += img.height

    return nova  # retorna PIL Image (será salvo com .save)


# ============================================================================
# PIPELINE PRINCIPAL DE RECORTE
# ============================================================================

def processar_recortes(prova_id: str):
    """
    Lê todos os JSONs da prova e recorta cada questão como uma imagem PNG.
    Atualiza os JSONs com o caminho da imagem gerada.
    """
    dir_questoes = DIR_QUESTOES_JSON / prova_id
    if not dir_questoes.exists():
        raise FileNotFoundError(
            f"Pasta {dir_questoes} não existe. Rode extrair_prova.py antes."
        )

    dir_img_prova = DIR_IMAGENS / prova_id

    # Carrega relatório para saber qual PDF
    relatorio_path = dir_questoes / "_relatorio.json"
    with open(relatorio_path, encoding="utf-8") as f:
        relatorio = json.load(f)
    pdf_path = Path(relatorio["pdf"])

    # Detecta vestibular a partir do primeiro JSON de questão
    vestibular = "ITA"
    jsons_questao = sorted(dir_questoes.glob("q*.json"))
    if jsons_questao:
        with open(jsons_questao[0], encoding="utf-8") as f:
            vestibular = json.load(f).get("prova", {}).get("vestibular", "ITA")

    # Coleta todos os JSONs de questão (ordenados)
    questoes_por_pagina: dict[int, list[tuple[int, Path]]] = {}
    for jp in jsons_questao:
        with open(jp, encoding="utf-8") as f:
            q = json.load(f)
        pag = q["fonte"]["pagina"]
        questoes_por_pagina.setdefault(pag, []).append((q["numero"], jp))

    # Ordena as listas por número dentro de cada página
    for pag in questoes_por_pagina:
        questoes_por_pagina[pag].sort()

    doc = fitz.open(pdf_path)

    # S3 client (criado uma vez por prova)
    s3_client = None
    if S3_DISPONIVEL:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=_S3_KEY,
            aws_secret_access_key=_S3_SECRET,
            region_name=_S3_REGION,
        )
    else:
        dir_img_prova.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Localiza posição de cada "Questão N" na página onde ela está,
    # e também da próxima questão (para saber onde a anterior termina).
    # ------------------------------------------------------------------
    posicoes: dict[int, tuple[int, fitz.Rect]] = {}  # num -> (pagina_idx, rect)

    # Precisamos localizar TODAS as questões da matéria em todo o doc
    # (não só as que o JSON diz — porque uma questão pode "terminar" na
    # página seguinte, e precisamos saber onde a próxima começa).
    numeros_todos = [q["numero"] for q in relatorio["questoes_extraidas"]]

    for num_pag, page in enumerate(doc, start=1):
        info_pag = relatorio["paginas"][num_pag - 1]
        if info_pag["tipo"] == "nativa":
            achados = localizar_questoes_pagina_nativa(page, numeros_todos, vestibular=vestibular)
        else:
            achados = localizar_questoes_pagina_escaneada(page, numeros_todos, vestibular=vestibular)

        for n, rect in achados.items():
            if n not in posicoes:  # só a primeira ocorrência
                posicoes[n] = (num_pag, rect)

    # ------------------------------------------------------------------
    # Para cada questão, determina janela de recorte e salva PNG.
    # ------------------------------------------------------------------
    numeros_ordenados = sorted(posicoes.keys())
    avisos = []

    for i, num in enumerate(numeros_ordenados):
        pag_inicio, rect_inicio = posicoes[num]
        y_inicio = max(0, rect_inicio.y0 - MARGEM_TOPO)

        # Determina onde a questão termina
        if i + 1 < len(numeros_ordenados):
            proximo = numeros_ordenados[i + 1]
            pag_prox, rect_prox = posicoes[proximo]
        else:
            # Última questão da matéria; termina no fim da sua página
            # (ou onde a próxima matéria começa — mas isso é mais complexo;
            #  por ora, cortamos no fim da página atual).
            pag_prox = pag_inicio
            rect_prox = fitz.Rect(0, doc[pag_inicio - 1].rect.height, 0, 0)

        pixmaps = []

        if pag_prox == pag_inicio:
            # Caso simples: mesma página.
            y_fim = rect_prox.y0 - 2
            # Se não há questão seguinte na mesma página (última da matéria),
            # aplica margem inferior para evitar capturar rodapé/número de página —
            # mas só se isso não colidir com o início da própria questão (caso de
            # provas de 2ª fase em que a última questão está no fim da página).
            altura_pag = doc[pag_inicio - 1].rect.height
            if i + 1 == len(numeros_ordenados):
                candidato = altura_pag - 80
                if candidato > y_inicio + 20:
                    y_fim = min(y_fim, candidato)
                else:
                    y_fim = altura_pag - 2
            pix = recortar_regiao_pagina(doc[pag_inicio - 1], y_inicio, y_fim)
            pixmaps.append(pix)
        else:
            # Caso complexo: questão atravessa páginas.
            # Corte 1: do Y_inicio até o fim da página de início.
            pag = doc[pag_inicio - 1]
            pix1 = recortar_regiao_pagina(pag, y_inicio, pag.rect.height)
            pixmaps.append(pix1)

            # Corte(s) intermediário(s): se questão pula mais de uma página,
            # precisamos incluir páginas inteiras no meio. Raro mas possível.
            for pmid in range(pag_inicio + 1, pag_prox):
                pag_m = doc[pmid - 1]
                pix_m = recortar_regiao_pagina(pag_m, 0, pag_m.rect.height)
                pixmaps.append(pix_m)

            # Corte final: do topo da última página até onde a próxima questão começa
            pag_final = doc[pag_prox - 1]
            y_fim = rect_prox.y0 - 2
            pix_fim = recortar_regiao_pagina(pag_final, 0, y_fim)
            pixmaps.append(pix_fim)

        # Compõe PNG em memória
        nome_arquivo = f"{prova_id}_q{num:02d}.png"
        buf = io.BytesIO()
        if len(pixmaps) == 1:
            buf.write(pixmaps[0].tobytes("png"))
        else:
            img_final = compor_verticalmente(pixmaps)
            img_final.save(buf, format="PNG")
        png_bytes = buf.getvalue()

        # Salva: S3 se disponível, disco caso contrário
        json_path = dir_questoes / f"q{num:02d}.json"
        with open(json_path, encoding="utf-8") as f:
            q = json.load(f)

        if s3_client:
            s3_key = f"imagens/{prova_id}/{nome_arquivo}"
            s3_client.put_object(
                Bucket=_S3_BUCKET,
                Key=s3_key,
                Body=png_bytes,
                ContentType="image/png",
            )
            q["imagem_questao_url"] = (
                f"https://{_S3_BUCKET}.s3.{_S3_REGION}.amazonaws.com/{s3_key}"
            )
            q.pop("imagem_questao", None)
        else:
            destino = dir_img_prova / nome_arquivo
            destino.write_bytes(png_bytes)
            q["imagem_questao"] = str(destino.relative_to(PROJETO_ROOT))

        q["usa_imagem_no_render"] = True
        q["status"]["figuras_recortadas"] = True
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(q, f, ensure_ascii=False, indent=2)

        print(f"  ✓ Q{num:02d} → {'s3://' + _S3_BUCKET + '/' if s3_client else ''}{nome_arquivo}")

    # Questões que não foram localizadas
    nao_localizadas = set(numeros_todos) - set(posicoes.keys())
    if nao_localizadas:
        avisos.append(
            f"Não localizei o marcador de {len(nao_localizadas)} questões: "
            f"{sorted(nao_localizadas)}. Pode ser falha de OCR ou padrão de texto diferente."
        )

    return {"recortadas": len(posicoes), "avisos": avisos}


def main():
    parser = argparse.ArgumentParser(description="Recorta questões como imagens.")
    parser.add_argument("prova_id", help="Ex: ita_2019_fase1")
    args = parser.parse_args()

    print(f"\n=== Recortando questões de {args.prova_id} ===\n")
    resultado = processar_recortes(args.prova_id)
    print(f"\nTotal recortado: {resultado['recortadas']}")
    if resultado["avisos"]:
        print("\n⚠ Avisos:")
        for a in resultado["avisos"]:
            print(f"  - {a}")


if __name__ == "__main__":
    main()
