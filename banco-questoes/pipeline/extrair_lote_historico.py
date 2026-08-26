"""extrair_lote_historico.py — Extração mecânica do acervo histórico (ITA/IME oficiais).

Diferença para `extrair_prova.py` do pipeline original: aquele espera um PDF
combinado (todas as matérias juntas, numeração 1-60 com offset por matéria). O
acervo histórico já vem com um PDF por matéria — a numeração recomeça em 1 em
cada arquivo. Forçar a faixa fixa (`FAIXAS_MATERIA`) truncaria silenciosamente
qualquer ano com mais de 12 questões de Física (2015 tem 20, por exemplo) — foi
achado processando o piloto de 1973. Aqui a faixa é sempre "o que o texto trouxer".

Duas fontes, duas geometrias:
  - ITA oficial 2008-2018: 30 questões por matéria — Q1-20 objetivas (gabarito
    publicado pela banca) + Q21-30 dissertativas. Viram DUAS provas (fase 1 e
    fase 2), como já é a convenção em produção.
  - IME oficial (CFG, "Concurso de Admissão"): dissertativa pura, sem alternativa
    nem letra — é a fase 2 do formato que já existe em produção (ime_2019_fase2
    etc.), só que mais velha. Sem gabarito por natureza, não por falta de dado.

Gera os JSONs canônicos em questoes_json/ e sobe os recortes para o mesmo bucket
S3 que a produção já usa (docs/22 §0.2). Classificação por tópico, gabarito
sugerido e resolução ficam vazios — são a etapa seguinte (agente).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import pymupdf
from dotenv import load_dotenv

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_PDFS = PROJETO_ROOT / "pdfs_originais"
DIR_QUESTOES = PROJETO_ROOT / "questoes_json"

load_dotenv(PROJETO_ROOT / ".env")
import boto3  # noqa: E402

_S3_BUCKET = os.getenv("S3_BUCKET", "ita-por-assunto")
_S3_REGION = os.getenv("AWS_REGION", "us-east-1")
# Mesma fonte de credencial que upload_s3.py já usa: AWS_ACCESS_KEY_ID/SECRET do
# .env local, carregadas acima. Sem profile_name — não força um perfil nomeado
# que pode não existir na máquina de quem rodar isto depois.
_S3 = boto3.client("s3", region_name=_S3_REGION)

SUFIXO_MATERIA = {"Física": "", "Química": "_qui", "Matemática": "_mat"}

PADRAO_QUESTAO_ITA = re.compile(r"Quest(?:ão|ao|˜ao)\s*(\d{1,2})\s*\.", re.IGNORECASE)
# `\s*` também ANTES do indicador ordinal: em provas96_97/*.pdf o pymupdf extrai o
# "ª" de "1ª QUESTÃO" como um "a" solto em linha própria ("1\na \nQuestão"), não
# grudado no dígito — sem esse `\s*` o marcador nunca batia e os 3 PDFs (10
# questões cada, texto nativo, conferido por leitura) ficavam de fora por engano
# de regex, não por serem escaneados. Testado contra os biênios já em produção
# (07-08, 12-13, 17-18): mesmos números, nenhuma regressão.
PADRAO_QUESTAO_IME = re.compile(r"(\d{1,2})\s*[ªºao]?\s*QUEST\s*[ÃA]O", re.IGNORECASE)
PADRAO_ALT_ITA = re.compile(r"\b([A-E])\s*\(\s*\)\s*")

VARIANTES_QUESTAO_ITA = ["Questão {n}.", "Questão {n} .", "Quest˜ao {n}.", "Quest˜ao {n} .", "Questao {n}."]
VARIANTES_QUESTAO_IME = ["{n}ª QUESTÃO", "{n}ª Questão", "{n}a QUESTÃO", "{n}ª questão"]


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto)
    for a, b in [("´a", "á"), ("´e", "é"), ("´ı", "í"), ("´i", "í"), ("´o", "ó"), ("´u", "ú"),
                 ("˜a", "ã"), ("˜o", "õ"), ("ˆa", "â"), ("ˆe", "ê"), ("ˆo", "ô"),
                 ("¸c", "ç"), ("ﬁ", "fi"), ("ﬂ", "fl")]:
        texto = texto.replace(a, b)
    return texto


def _texto_pdf(pdf: Path) -> tuple[str, list[str]]:
    """Texto completo e por página. Tenta o encoding cifrado (quimica_2018) como
    fallback quando a extração normal não acha nenhum marcador de questão."""
    doc = pymupdf.open(pdf)
    paginas = [p.get_text() for p in doc]
    doc.close()
    texto = normalizar("\n".join(paginas))
    if PADRAO_QUESTAO_ITA.search(texto) or PADRAO_QUESTAO_IME.search(texto):
        return texto, paginas
    # Fallback: fonte com glifos deslocados +29 no codepoint (achado no quimica_2018).
    deslocado = [
        "".join(chr(ord(c) + 29) if 32 <= ord(c) < 127 else c for c in p) for p in paginas
    ]
    texto2 = normalizar("\n".join(deslocado))
    if PADRAO_QUESTAO_ITA.search(texto2):
        return texto2, deslocado
    return texto, paginas


# ─── Recorte (porta de recortar_questoes.py, generalizado para faixa aberta) ──


def _localizar_pagina_nativa(page, numeros, variantes) -> dict[int, "pymupdf.Rect"]:
    achados = {}
    for n in numeros:
        for v in variantes:
            rects = page.search_for(v.format(n=n))
            if rects:
                achados[n] = rects[0]
                break
    return achados


def _recortar_regiao(page, y0, y1, dpi=200):
    r = page.rect
    # Clamp direto aqui, não em cada chamador: MuPDF recusa clip com altura
    # zero/negativa com um erro de baixo nível (`Invalid bandwriter header`) que
    # derruba o PDF inteiro. Aconteceu em 5 dos 54 do IME oficial — geometria
    # rara (dois marcadores da mesma questão colidindo, ou a última da página
    # perto demais do rodapé), rara demais para valer investigar caso a caso.
    y0 = max(0, min(y0, r.height - 1))
    y1 = max(y0 + 20, min(y1, r.height))
    clip = pymupdf.Rect(15, y0, r.width - 15, y1)
    return page.get_pixmap(dpi=dpi, clip=clip)


def recortar_e_subir(pdf: Path, numeros: list[int], prova_id: str, variantes: list[str]) -> dict[int, str]:
    """Recorta cada questão (nativo) e sobe para o S3. Devolve {numero: url}."""
    doc = pymupdf.open(pdf)
    posicoes: dict[int, tuple[int, "pymupdf.Rect"]] = {}
    for i, page in enumerate(doc, start=1):
        for n, rect in _localizar_pagina_nativa(page, numeros, variantes).items():
            posicoes.setdefault(n, (i, rect))

    urls: dict[int, str] = {}
    ordenados = sorted(posicoes.items(), key=lambda kv: (kv[1][0], kv[1][1].y0))
    for i, (num, (pag, rect)) in enumerate(ordenados):
        y0 = max(0, rect.y0 - 5)
        if i + 1 < len(ordenados) and ordenados[i + 1][1][0] == pag:
            y1 = ordenados[i + 1][1][1].y0 - 2
            pix = _recortar_regiao(doc[pag - 1], y0, y1)
            png = pix.tobytes("png")
        elif i + 1 < len(ordenados):
            prox_pag, prox_rect = ordenados[i + 1][1]
            partes = [_recortar_regiao(doc[pag - 1], y0, doc[pag - 1].rect.height)]
            for m in range(pag + 1, prox_pag):
                partes.append(_recortar_regiao(doc[m - 1], 0, doc[m - 1].rect.height))
            partes.append(_recortar_regiao(doc[prox_pag - 1], 0, prox_rect.y0 - 2))
            from PIL import Image
            imgs = [Image.frombytes("RGB", (p.width, p.height), p.samples) for p in partes]
            largura = max(im.width for im in imgs)
            altura = sum(im.height for im in imgs)
            composta = Image.new("RGB", (largura, altura), "white")
            y = 0
            for im in imgs:
                composta.paste(im, (0, y)); y += im.height
            buf = io.BytesIO(); composta.save(buf, format="PNG"); png = buf.getvalue()
        else:
            pix = _recortar_regiao(doc[pag - 1], y0, doc[pag - 1].rect.height - 40)
            png = pix.tobytes("png")

        chave = f"imagens/{prova_id}/{prova_id}_q{num:02d}.png"
        _S3.put_object(Bucket=_S3_BUCKET, Key=chave, Body=png, ContentType="image/png")
        urls[num] = f"https://{_S3_BUCKET}.s3.{_S3_REGION}.amazonaws.com/{chave}"
    doc.close()
    return urls


# ─── JSON canônico ─────────────────────────────────────────────────────────


def escrever_questao(
    prova_id: str, numero: int, vestibular: str, ano: int, fase: int, materia: str,
    dissertativa: bool, enunciado: str, alternativas: dict[str, str],
    gabarito: str | None, gabarito_origem: str | None, imagem_url: str | None,
    fonte_pdf: str, pagina: int,
) -> None:
    d = DIR_QUESTOES / prova_id
    d.mkdir(parents=True, exist_ok=True)
    dados = {
        "id": f"{prova_id}_q{numero:02d}",
        "prova": {"vestibular": vestibular, "ano": ano, "fase": fase, "materia": materia},
        "numero": numero,
        "dissertativa": dissertativa,
        "enunciado_md": enunciado,
        "alternativas": alternativas,
        "gabarito": gabarito,
        "gabarito_origem": gabarito_origem,
        "imagem_questao_url": imagem_url,
        "usa_imagem_no_render": imagem_url is not None,
        "classificacao": {
            "topicos_ids": [], "topicos_nomes": [], "blocos": [],
            "classificado_por": None, "confianca": None, "observacao": "",
        },
        "resolucao_md": None,
        "resolucao_origem": None,
        "fonte": {"pdf": fonte_pdf, "pagina": pagina, "bbox_questao": None},
        "status": {
            "texto_extraido": bool(enunciado.strip()),
            "alternativas_extraidas": (not dissertativa and len(alternativas) == 5) or dissertativa,
            "figuras_recortadas": imagem_url is not None,
            "classificado": False, "revisado": False,
            "possivelmente_tem_figura": False,
        },
        "extraido_por": "pipeline",
    }
    (d / f"q{numero:02d}.json").write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── ITA oficial ────────────────────────────────────────────────────────────


_NOME_ARQUIVO_MATERIA = {"Física": "fisica", "Química": "quimica", "Matemática": "matematica"}


def processar_ita_oficial(ano: int, materia: str, gabaritos: dict) -> dict:
    pdf = DIR_PDFS / "ita_historico" / "oficial_1fase_2008_2018" / str(ano) / f"{_NOME_ARQUIVO_MATERIA[materia]}_{ano}.pdf"
    if not pdf.exists():
        return {"pdf": str(pdf), "erro": "não encontrado"}

    texto, _ = _texto_pdf(pdf)
    matches = list(PADRAO_QUESTAO_ITA.finditer(texto))
    if not matches:
        return {"pdf": str(pdf), "erro": "nenhum marcador de questão encontrado"}

    questoes = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        corpo = texto[m.end():fim]
        alt_matches = list(PADRAO_ALT_ITA.finditer(corpo))
        dissertativa = len(alt_matches) < 5
        if dissertativa:
            enunciado, alternativas = corpo.strip(), {}
        else:
            enunciado = corpo[:alt_matches[0].start()].strip()
            alternativas = {}
            for j, am in enumerate(alt_matches[:5]):
                letra = am.group(1).upper()
                fim_alt = alt_matches[j + 1].start() if j + 1 < len(alt_matches[:5]) else len(corpo)
                alternativas[letra] = re.sub(r"\s+", " ", corpo[am.end():fim_alt].strip())
        questoes.append({"numero": num, "dissertativa": dissertativa, "enunciado": enunciado,
                         "alternativas": alternativas})

    sufixo = SUFIXO_MATERIA[materia]
    numeros = [q["numero"] for q in questoes]
    # Um PDF só vira DUAS provas (fase 1 objetiva + fase 2 dissertativa), mas o
    # recorte é um por número absoluto no PDF de origem — sobe uma vez com uma
    # chave neutra (por matéria/ano, sem fase) e as duas provas referenciam dali.
    materia_chave = {"Física": "fis", "Química": "qui", "Matemática": "mat"}[materia]
    chave_s3 = f"ita_{ano}_{materia_chave}"
    urls = recortar_e_subir(pdf, numeros, chave_s3, VARIANTES_QUESTAO_ITA)
    doc = pymupdf.open(pdf)
    paginas_por_numero = {}
    for i, page in enumerate(doc, start=1):
        for n, _ in _localizar_pagina_nativa(page, numeros, VARIANTES_QUESTAO_ITA).items():
            paginas_por_numero.setdefault(n, i)
    doc.close()

    gab_obj = gabaritos.get(f"{ano}|{materia}", {})
    contagem = {"fase1": 0, "fase2": 0, "sem_gabarito_oficial": 0}
    for q in questoes:
        fase = 2 if q["dissertativa"] else 1
        prova_id = f"ita_{ano}_fase{fase}{sufixo}"
        gab = None if q["dissertativa"] else gab_obj.get(str(q["numero"]))
        gab_origem = "banca" if gab else None
        if not q["dissertativa"] and not gab:
            contagem["sem_gabarito_oficial"] += 1
        escrever_questao(
            prova_id, q["numero"], "ITA", ano, fase, materia, q["dissertativa"],
            q["enunciado"], q["alternativas"], gab, gab_origem,
            urls.get(q["numero"]), pdf.name, paginas_por_numero.get(q["numero"], 0),
        )
        contagem[f"fase{fase}"] += 1
    return {"pdf": str(pdf), "questoes": len(questoes), **contagem}


# ─── IME oficial (CFG, dissertativa) ───────────────────────────────────────


def processar_ime_oficial(pdf: Path, materia: str, ano: int) -> dict:
    texto, _ = _texto_pdf(pdf)
    matches = list(PADRAO_QUESTAO_IME.finditer(texto))
    if len(matches) < 3:
        return {"pdf": str(pdf), "erro": f"só {len(matches)} marcadores"}

    questoes = []
    vistos = set()
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if num in vistos or not (1 <= num <= 15):
            continue
        vistos.add(num)
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        corpo = texto[m.end():fim].strip()
        # Em provas96_97/*.pdf o marcador aparece como "...Questão:\nValor : 1,0" —
        # o regex casa até "ÃO", então o ":" sobra colado no início do corpo. Não
        # acontece nos biênios já em produção (lá não há ":" logo após o marcador),
        # então isto é sempre um no-op fora deste caso específico.
        corpo = corpo.lstrip(":").strip()
        questoes.append({"numero": num, "enunciado": corpo})

    sufixo = SUFIXO_MATERIA[materia]
    prova_id = f"ime_{ano}_fase2{sufixo}"
    numeros = [q["numero"] for q in questoes]
    urls = recortar_e_subir(pdf, numeros, prova_id, VARIANTES_QUESTAO_IME)

    doc = pymupdf.open(pdf)
    paginas_por_numero = {}
    for i, page in enumerate(doc, start=1):
        for n, _ in _localizar_pagina_nativa(page, numeros, VARIANTES_QUESTAO_IME).items():
            paginas_por_numero.setdefault(n, i)
    doc.close()

    for q in questoes:
        escrever_questao(
            prova_id, q["numero"], "IME", ano, 2, materia, True,
            q["enunciado"], {}, None, None,
            urls.get(q["numero"]), pdf.name, paginas_por_numero.get(q["numero"], 0),
        )
    return {"pdf": str(pdf), "questoes": len(questoes), "prova_id": prova_id}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", choices=["ita_oficial", "ime_oficial"])
    ap.add_argument("--manifesto", type=Path, required=True,
                    help="JSON com a lista de arquivos (relativos a pdfs_originais/) ou de {ano,materia}")
    args = ap.parse_args()

    relatorio = []
    if args.lote == "ita_oficial":
        gabaritos = json.loads((PROJETO_ROOT / "config" / "_gabaritos_oficiais_ita.json").read_text())
        pares = json.loads(args.manifesto.read_text())  # [[ano, materia], ...]
        for ano, materia in pares:
            try:
                r = processar_ita_oficial(ano, materia, gabaritos)
            except Exception as e:
                r = {"pdf": f"{ano}/{materia}", "erro": f"{type(e).__name__}: {e}"}
            relatorio.append(r)
            status = "erro: " + r["erro"] if "erro" in r else f"{r['questoes']}q (obj={r.get('fase1',0)} diss={r.get('fase2',0)} sem_gab={r.get('sem_gabarito_oficial',0)})"
            print(f"  {materia} {ano}: {status}", file=sys.stderr)
    else:
        arquivos = json.loads(args.manifesto.read_text())
        for rel in arquivos:
            pdf = DIR_PDFS / rel
            nome = pdf.name.lower()
            materia = ("Física" if "fisica" in nome or "fís" in nome else
                      "Química" if "quimica" in nome or "quím" in nome else
                      "Matemática" if any(k in nome for k in ("mat", "matematica")) else None)
            ciclo_m = re.search(r"provas(\d{2})_(\d{2})", rel)
            ano = 1900 + int(ciclo_m.group(1)) if int(ciclo_m.group(1)) >= 90 else 2000 + int(ciclo_m.group(1))
            if not materia:
                relatorio.append({"pdf": str(pdf), "erro": "matéria não reconhecida pelo nome"})
                continue
            # Um PDF com geometria estranha não pode derrubar os outros 53 — é
            # exatamente a filosofia do pipeline original (PROMPT_CLAUDE_CODE.md
            # §Regras: "pule a prova, registre o erro, continue com as outras").
            try:
                r = processar_ime_oficial(pdf, materia, ano)
            except Exception as e:
                r = {"pdf": str(pdf), "erro": f"{type(e).__name__}: {e}"}
            relatorio.append(r)
            status = "erro: " + r["erro"] if "erro" in r else f"{r['questoes']}q → {r['prova_id']}"
            print(f"  {rel}: {status}", file=sys.stderr)

    saida = PROJETO_ROOT / f"_relatorio_extracao_{args.lote}.json"
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    erros = [r for r in relatorio if "erro" in r]
    print(f"\n{len(relatorio) - len(erros)} ok · {len(erros)} erro(s) → {saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
