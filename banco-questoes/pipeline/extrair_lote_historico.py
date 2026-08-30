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
import shutil
import struct
import subprocess
import sys
import unicodedata
from pathlib import Path

import gabarito_ime_objetiva
import pymupdf
from dotenv import load_dotenv

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_PDFS = PROJETO_ROOT / "pdfs_originais"
DIR_QUESTOES = PROJETO_ROOT / "questoes_json"

load_dotenv(PROJETO_ROOT / ".env")
import boto3

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
# VARIANTES_QUESTAO_IME saiu: era a lista de buscas literais do recorte do IME, e
# não havia variante que cobrisse o ordinal quebrado sem cair em falso positivo de
# substring. Quem localiza agora é `_localizar_marcador_ime`, por palavra.


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFC", texto)
    for a, b in [("´a", "á"), ("´e", "é"), ("´ı", "í"), ("´i", "í"), ("´o", "ó"), ("´u", "ú"),
                 ("˜a", "ã"), ("˜o", "õ"), ("ˆa", "â"), ("ˆe", "ê"), ("ˆo", "ô"),
                 ("¸c", "ç"), ("ﬁ", "fi"), ("ﬂ", "fl")]:
        texto = texto.replace(a, b)
    return texto


def _sem_acento(texto: str) -> str:
    """Minúsculo e sem diacrítico — só para COMPARAR palavra, nunca para gravar.
    "Questão", "QUESTÃO" e "Questao" são o mesmo marcador em PDFs de anos
    diferentes, e `normalizar()` acima resolve outro problema (glifo composto)."""
    sem = "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))
    return sem.lower()


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


def _localizar_pagina_nativa(page, numeros, variantes) -> dict[int, pymupdf.Rect]:
    achados = {}
    for n in numeros:
        for v in variantes:
            rects = page.search_for(v.format(n=n))
            if rects:
                achados[n] = rects[0]
                break
    return achados


_ORDINAL_SOLTO = {"a", "ª", "º", "o", "°"}


def _localizar_marcador_ime(page, numeros) -> dict[int, pymupdf.Rect]:
    """Onde começa cada questão do IME na página — por PALAVRA, não por busca literal.

    `page.search_for()` é busca de substring, e as duas coisas que ela não faz
    quebraram o recorte do IME por duas rodadas inteiras (docs/23 §21.4, §22.1):

    1. **O ordinal quebrado.** Em vários PDFs o pymupdf extrai o "ª" de
       "1ª QUESTÃO" como um "a" solto em linha própria ("1\na \nQuestão:").
       Nenhuma das `VARIANTES_QUESTAO_IME` casa com isso — a prova parecia
       escaneada quando o texto estava perfeito. É o mesmo defeito que o §21.3
       consertou no regex do TEXTO; aqui é o código do RECORTE, que ficou.
    2. **Substring não tem fronteira.** Procurar "1ª QUESTÃO" acha "21ª QUESTÃO"
       também, e o recorte da questão 1 sairia na posição da 21. Passava
       despercebido no lote discursivo (10 questões por PDF, raramente na mesma
       página); no caderno objetivo, com 1–40 e várias por página, seria erro
       garantido.

    Comparando com o comportamento anterior nos biênios já em produção
    (07-08, 12-13, 16-17, 17-18) e no caderno objetivo de 18-19: os mesmos
    números, na mesma página, com y0 no máximo 1,9pt acima — a diferença é o
    sobrescrito, e o recorte já folga 5pt. Nos três PDFs de 1996, que antes
    davam zero, agora dá 10/10.
    """
    palavras = sorted(page.get_text("words"), key=lambda w: (w[5], w[6], w[7]))
    procurados = {str(n): n for n in numeros}
    achados: dict[int, pymupdf.Rect] = {}
    for i, palavra in enumerate(palavras):
        casa = re.fullmatch(r"(\d{1,2})([aªºo°]?)", palavra[4])
        if not casa or casa.group(1) not in procurados:
            continue
        j = i + 1
        if not casa.group(2):
            # O ordinal veio como palavra própria; sem ele, um número solto no
            # meio do enunciado viraria marcador de questão.
            if j < len(palavras) and palavras[j][4] in _ORDINAL_SOLTO:
                j += 1
            else:
                continue
        # "ques" e não "quest": em ProvaObjetiva_CA_CFG_2011_2012.pdf a palavra
        # chega cortada ("16a" + "QUES"), pelo mesmo defeito de blocos
        # sobrepostos que obrigou o `_texto_poppler`. Três questões ficavam sem
        # recorte — e num banco em que a imagem é o que o aluno lê, isso é a
        # questão sem enunciado. Quatro letras depois de um número com ordinal
        # não casam com mais nada num caderno de prova.
        if j >= len(palavras) or not _sem_acento(palavras[j][4]).startswith("ques"):
            continue
        # `get_text` devolve coordenada no espaço NÃO girado; `get_pixmap(clip=...)`
        # espera o espaço exibido. Numa página com /Rotate 90 os dois divergem — em
        # `Objetiva_Final_Formato_A3_02-10.pdf` o y do marcador chegava a 1121 numa
        # página de 842 de altura, e o recorte saía com 3 pixels (docs/23 §25).
        # `rotation_matrix` é identidade quando não há rotação, então isto é no-op
        # em todo o resto do acervo.
        achados.setdefault(
            procurados[casa.group(1)],
            pymupdf.Rect(palavra[0], palavra[1], palavra[2], palavra[3]) * page.rotation_matrix,
        )
    return achados


# Altura mínima plausível de um recorte, em pixels a 200dpi (~2,5cm de página).
# O menor recorte legítimo do acervo tem 263px; um de 57px é o sintoma de que a
# geometria foi lida errado — foi assim que o recorte de 2009 saiu picado
# (docs/23 §25). O extrator reclama na hora porque tem o PNG na mão: esperar
# alguém rodar auditoria depois é esperar que alguém se lembre.
ALTURA_MINIMA_RECORTE = 200


def _metades_da_folha(page) -> list[tuple[float, float]]:
    """As páginas impressas na folha, no espaço exibido.

    `Objetiva_Final_Formato_A3_02-10.pdf` é uma folha A3 em paisagem com DUAS
    páginas A4 lado a lado — imposição 2-up. Recortar a largura inteira trazia o
    RASCUNHO da página vizinha grudado na questão (docs/23 §25).

    O critério é a geometria da folha, não aglomerado de texto: folha em paisagem
    são duas páginas retrato, e o corte é no meio. Tentar inferir das posições do
    texto dá falso positivo — em 2014 um trecho de 56pt encostado na margem
    direita virava "coluna" e cortava a questão ao meio.
    """
    r = page.rect
    if r.width <= r.height:
        return []                                   # folha retrato: uma página só
    meio = r.width / 2
    return [(0.0, meio), (meio, r.width)]


def _localizar_ita(page, numeros) -> dict[int, pymupdf.Rect]:
    return _localizar_pagina_nativa(page, numeros, VARIANTES_QUESTAO_ITA)


def _recortar_regiao(page, y0, y1, faixa_x=None, dpi=200):
    """Recorta uma faixa da página. `faixa_x` limita à coluna; None = largura toda."""
    r = page.rect
    # Clamp direto aqui, não em cada chamador: MuPDF recusa clip com altura
    # zero/negativa com um erro de baixo nível (`Invalid bandwriter header`) que
    # derruba o PDF inteiro. Aconteceu em 5 dos 54 do IME oficial — geometria
    # rara (dois marcadores da mesma questão colidindo, ou a última da página
    # perto demais do rodapé), rara demais para valer investigar caso a caso.
    y0 = max(0, min(y0, r.height - 1))
    y1 = max(y0 + 20, min(y1, r.height))
    x0, x1 = (15, r.width - 15) if faixa_x is None else faixa_x
    clip = pymupdf.Rect(max(0, x0), y0, min(r.width, x1), y1)
    return page.get_pixmap(dpi=dpi, clip=clip)


def recortar_e_subir(pdf: Path, numeros: list[int], prova_id: str, localizador) -> dict[int, str]:
    """Recorta cada questão (nativo) e sobe para o S3. Devolve {numero: url}.

    `localizador` é `(page, numeros) -> {numero: Rect}` em vez da lista de
    variantes de antes: ITA e IME acham o marcador de jeitos diferentes desde
    que o do IME passou a ler por palavra (`_localizar_marcador_ime`).

    O recorte respeita a METADE da folha em que a questão está, e não a largura
    inteira: numa folha em paisagem são duas páginas impressas lado a lado, e
    recortar tudo trazia o RASCUNHO da página vizinha junto (docs/23 §25). Em
    folha retrato — o resto do acervo inteiro — nada muda.
    """
    doc = pymupdf.open(pdf)
    colunas_por_pagina: dict[int, list[tuple[float, float]]] = {}
    posicoes: dict[int, tuple[int, int, pymupdf.Rect]] = {}
    for i, page in enumerate(doc, start=1):
        achados = localizador(page, numeros)
        if not achados:
            continue
        metades = colunas_por_pagina.setdefault(i, _metades_da_folha(page))
        for n, rect in achados.items():
            centro = (rect.x0 + rect.x1) / 2
            idx = next((j for j, (a, b) in enumerate(metades) if a <= centro < b), 0)
            posicoes.setdefault(n, (i, idx, rect))

    def faixa(pagina: int, indice: int):
        metades = colunas_por_pagina.get(pagina) or []
        if len(metades) < 2 or indice >= len(metades):
            return None                      # folha retrato: margem de sempre
        a, b = metades[indice]
        return (a + 15, b - 15)              # a mesma margem, dentro da metade

    urls: dict[int, str] = {}
    suspeitos: list[str] = []
    ordenados = sorted(posicoes.items(), key=lambda kv: (kv[1][0], kv[1][1], kv[1][2].y0))
    for i, (num, (pag, col, rect)) in enumerate(ordenados):
        y0 = max(0, rect.y0 - 5)
        seguinte = ordenados[i + 1][1] if i + 1 < len(ordenados) else None
        mesma_coluna = seguinte is not None and seguinte[0] == pag and seguinte[1] == col
        if mesma_coluna:
            pix = _recortar_regiao(doc[pag - 1], y0, seguinte[2].y0 - 2, faixa(pag, col))
            png = pix.tobytes("png")
        elif seguinte is not None:
            prox_pag, prox_col, prox_rect = seguinte
            partes = [_recortar_regiao(doc[pag - 1], y0, doc[pag - 1].rect.height, faixa(pag, col))]
            for m in range(pag + 1, prox_pag):
                partes.append(_recortar_regiao(doc[m - 1], 0, doc[m - 1].rect.height))
            partes.append(
                _recortar_regiao(doc[prox_pag - 1], 0, prox_rect.y0 - 2, faixa(prox_pag, prox_col))
            )
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
            pix = _recortar_regiao(doc[pag - 1], y0, doc[pag - 1].rect.height - 40, faixa(pag, col))
            png = pix.tobytes("png")

        # O caderno objetivo do IME é um PDF só com as três matérias, e cada
        # questão pertence a uma prova diferente (`ime_2012_fase1_mat` × `_qui`).
        # Por isso `prova_id` pode ser uma função do número — os limites do
        # recorte continuam vindo dos 40 marcadores juntos, senão a última
        # questão de cada matéria se estenderia até o fim da página.
        chave_prova = prova_id(num) if callable(prova_id) else prova_id
        chave = f"imagens/{chave_prova}/{chave_prova}_q{num:02d}.png"
        altura = struct.unpack(">I", png[20:24])[0]      # IHDR do PNG
        if altura < ALTURA_MINIMA_RECORTE:
            suspeitos.append(f"q{num} com {altura}px de altura")
        _S3.put_object(Bucket=_S3_BUCKET, Key=chave, Body=png, ContentType="image/png")
        urls[num] = f"https://{_S3_BUCKET}.s3.{_S3_REGION}.amazonaws.com/{chave}"
    doc.close()
    if suspeitos:
        print(f"      ⚠ recorte curto demais — {', '.join(suspeitos)}", file=sys.stderr)
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
    caminho = d / f"q{numero:02d}.json"

    # Classificação, resolução e revisão são trabalho de DEPOIS da extração —
    # de agente ou de gente —, e reextrair não pode apagá-las. Sem isto, rodar o
    # extrator de novo zera tudo em silêncio: aconteceu em 29/08 com as 280
    # questões recém-classificadas, e apagaria também as resoluções dos §16–§22
    # se alguém reextraísse o acervo histórico (docs/23 §23.7).
    anterior = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
    classificacao_anterior = anterior.get("classificacao")
    tinha_classificacao = bool((classificacao_anterior or {}).get("topicos_ids"))

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
    if tinha_classificacao:
        dados["classificacao"] = classificacao_anterior
        dados["status"]["classificado"] = True
    for campo in ("resolucao_md", "resolucao_origem"):
        if anterior.get(campo) is not None:
            dados[campo] = anterior[campo]
    if anterior.get("status", {}).get("revisado"):
        dados["status"]["revisado"] = True

    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


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
    urls = recortar_e_subir(pdf, numeros, chave_s3, _localizar_ita)
    doc = pymupdf.open(pdf)
    paginas_por_numero = {}
    for i, page in enumerate(doc, start=1):
        for n in _localizar_ita(page, numeros):
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
    urls = recortar_e_subir(pdf, numeros, prova_id, _localizar_marcador_ime)

    doc = pymupdf.open(pdf)
    paginas_por_numero = {}
    for i, page in enumerate(doc, start=1):
        for n in _localizar_marcador_ime(page, numeros):
            paginas_por_numero.setdefault(n, i)
    doc.close()

    for q in questoes:
        escrever_questao(
            prova_id, q["numero"], "IME", ano, 2, materia, True,
            q["enunciado"], {}, None, None,
            urls.get(q["numero"]), pdf.name, paginas_por_numero.get(q["numero"], 0),
        )
    return {"pdf": str(pdf), "questoes": len(questoes), "prova_id": prova_id}


# ─── IME oficial (CFG, prova objetiva = fase 1) ────────────────────────────

# Alternativa do IME em duas grafias, porque a banca trocou por volta de 2010:
# "(A) 23" de 2011 em diante, e "A)" no começo da linha em 2007–2009. O ITA usa
# "A ( )", outro padrão ainda. Sem o segundo caso, 2007–2009 saem com as 40
# questões e ZERO alternativas — foi o que o ensaio mostrou.
# A forma sem parêntese exige início de linha OU dois espaços antes: em 2009 as
# cinco alternativas vêm na mesma linha ("A)  0     B)  1     C) ..."), e exigir
# início de linha acharia só a primeira. Dois espaços é o que separa "A)" de
# alternativa de um "a)" citado no meio de uma frase.
PADRAO_ALT_IME = re.compile(r"(?:\(\s*([A-E])\s*\)|(?:^|\s{2,})([A-E])\s*\))\s*", re.MULTILINE)

# Cabeçalho que abre cada matéria: "QUESTÕES DE 1 A 15" seguido de "MATEMÁTICA".
PADRAO_FAIXA_IME = re.compile(r"QUEST[ÕO]ES\s+DE\s+(\d{1,2})\s+A\s+(\d{1,2})", re.IGNORECASE)

# Todos os cadernos de 2007 a 2018 conferidos usam esta divisão. Serve de
# conferência do que se leu do cabeçalho, não de suposição: se um ano divergir,
# o relatório avisa em vez de gravar a matéria errada em 40 questões.
FAIXAS_IME_OBJETIVA = {"Matemática": (1, 15), "Física": (16, 30), "Química": (31, 40)}


def _faixas_por_materia(texto: str) -> tuple[dict[str, tuple[int, int]], list[str]]:
    """Lê "QUESTÕES DE X A Y / MATEMÁTICA" do próprio caderno e compara com o padrão."""
    achadas: dict[str, tuple[int, int]] = {}
    for m in PADRAO_FAIXA_IME.finditer(texto):
        # O nome da matéria vem logo depois — na mesma linha em 2007, na
        # seguinte de 2008 em diante. Em 2016 e 2018 sai "FíSICA", com i
        # minúsculo: comparação sem acento e sem caixa.
        adiante = _sem_acento(texto[m.end():m.end() + 60])
        for materia, chave in (("Matemática", "matematica"), ("Física", "fisica"), ("Química", "quimica")):
            if chave in adiante and materia not in achadas:
                achadas[materia] = (int(m.group(1)), int(m.group(2)))
                break
    avisos = []
    for materia, faixa in FAIXAS_IME_OBJETIVA.items():
        if materia in achadas and achadas[materia] != faixa:
            avisos.append(f"{materia}: caderno diz {achadas[materia]}, o padrão é {faixa}")
    return (achadas or FAIXAS_IME_OBJETIVA), avisos


def _separar_alternativas(corpo: str) -> tuple[str, dict[str, str]]:
    """Enunciado e A–E. Sem cinco alternativas em sequência, devolve o corpo inteiro.

    Procura a ÚLTIMA janela de cinco marcas com as cinco letras, não as cinco
    primeiras ocorrências: "(A)" aparece no meio de enunciado do IME para nomear
    ponto, vértice e alternativa de circuito, e cortar na primeira levaria metade
    da pergunta para dentro da alternativa A.

    As cinco letras em QUALQUER ordem, não A→E: quando as alternativas vêm em
    duas colunas (2015), a leitura sai A, C, E, B, D — e o texto entre uma marca
    e a seguinte continua sendo o valor da primeira, que é o que importa.
    """
    marcas = list(PADRAO_ALT_IME.finditer(corpo))
    letra_de = lambda m: (m.group(1) or m.group(2)).upper()
    inicio = None
    for i in range(len(marcas) - 4):
        if len({letra_de(m) for m in marcas[i:i + 5]}) == 5:
            inicio = i
    if inicio is None:
        return corpo.strip(), {}
    escolhidas = marcas[inicio:inicio + 5]
    alternativas = {}
    for j, marca in enumerate(escolhidas):
        fim = escolhidas[j + 1].start() if j + 1 < len(escolhidas) else len(corpo)
        # `lstrip(")")`: quando a linha da alternativa está partida em dois blocos
        # de texto sobrepostos, a leitura ordenada repete o caractere da emenda e
        # "(C) a = 2b" chega como "(C)) a = 2b". Nenhuma alternativa do IME começa
        # com fecha-parêntese, então tirar é seguro; o resto da emenda duplicada
        # fica no enunciado e está listado em docs/23 §23.
        texto_alt = corpo[marca.end():fim].strip().lstrip(")").strip()
        alternativas[letra_de(marca)] = re.sub(r"\s+", " ", texto_alt)
    return corpo[:escolhidas[0].start()].strip(), alternativas


def _texto_poppler(pdf: Path) -> str | None:
    """O mesmo PDF lido pelo `pdftotext` (poppler), quando ele existir na máquina.

    Último recurso, e só para o caderno objetivo: em
    `ProvaObjetiva_CA_CFG_2011_2012.pdf` os blocos de texto se sobrepõem de um
    jeito que o pymupdf não desfaz — o marcador sai partido ("1a QUEST" + "TÃO"),
    e a leitura ordenada, que reúne, duplica o caractere da emenda
    ("1a QUESTTÃO", "vvalem a, b ee c"). Nenhum dos dois casa com
    `PADRAO_QUESTAO_IME`, e a prova inteira ficava de fora — 40 questões com
    gabarito oficial (docs/23 §24).

    O poppler lê a mesma página limpa. Não vira dependência do projeto: se o
    binário não estiver lá, devolve None e o ano é pulado com o aviso de sempre.
    As POSIÇÕES continuam vindo do pymupdf — `_localizar_marcador_ime` acha o
    marcador mesmo partido, porque procura por palavra.
    """
    caminho = shutil.which("pdftotext")
    if not caminho:
        return None
    try:
        saida = subprocess.run(
            [caminho, "-q", "-enc", "UTF-8", str(pdf), "-"],
            capture_output=True, timeout=120, check=True,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    return normalizar(saida.stdout.decode("utf-8", errors="replace"))


def _texto_ordenado(pdf: Path) -> str:
    """O mesmo PDF lido por posição na página (`sort=True`), não por ordem do fluxo."""
    documento = pymupdf.open(pdf)
    texto = normalizar("\n".join(p.get_text("text", sort=True) for p in documento))
    documento.close()
    return texto


def _corpos_por_numero(texto: str, materia_de: dict[int, str]) -> dict[int, str]:
    """Texto de cada questão, do marcador até o próximo.

    A questão que não cabe na página aparece de novo na seguinte, como
    "17ª QUESTÃO (CONTINUAÇÃO)" — e é lá que estão as alternativas. Tratar a
    segunda aparição como repetição a descartar deixava a questão sem alternativa
    nenhuma (3 casos em 2008). Por isso o corpo se acumula por número; repetição
    que NÃO é continuação continua sendo descartada, porque aí é marcador citado
    dentro de outra questão.
    """
    corpos: dict[int, str] = {}
    marcadores = list(PADRAO_QUESTAO_IME.finditer(texto))
    for i, marcador in enumerate(marcadores):
        numero = int(marcador.group(1))
        if numero not in materia_de:
            continue
        fim = marcadores[i + 1].start() if i + 1 < len(marcadores) else len(texto)
        corpo = texto[marcador.end():fim].strip().lstrip(":").strip()
        continuacao = re.match(r"\(?\s*CONTINUA[ÇC][ÃA]O", corpo, re.IGNORECASE)
        if numero in corpos and not continuacao:
            continue
        corpos[numero] = (corpos[numero] + "\n" + corpo).strip() if numero in corpos else corpo
    return corpos


def processar_ime_objetiva(pdf: Path, ano: int, gabarito: dict[int, str] | None) -> dict:
    """A prova objetiva do IME (fase 1) — um PDF, três matérias, numeração 1–40.

    Por que não dá para reusar `processar_ime_oficial`: aquele é a prova
    discursiva. Ele descarta tudo acima de 15, grava `fase2`, marca
    `dissertativa=True` e não lê alternativa nem gabarito — rodá-lo aqui
    perderia 25 das 40 questões sem erro nenhum na tela (docs/23 §23).

    A numeração fica ABSOLUTA (Física é q16–q30), que é a convenção que
    `ime_2018_fase1_q16` já usa em produção — renumerar por matéria criaria
    dois esquemas para a mesma prova.
    """
    texto, _ = _texto_pdf(pdf)
    marcadores = list(PADRAO_QUESTAO_IME.finditer(texto))
    origem_texto = "pymupdf"
    # Menos de 40 marcadores num caderno de 40 é sinal de leitura ruim, não de
    # prova curta. Antes de desistir, tenta o poppler (ver `_texto_poppler`).
    if len({int(x.group(1)) for x in marcadores}) < 40:
        alternativo = _texto_poppler(pdf)
        if alternativo:
            outros = list(PADRAO_QUESTAO_IME.finditer(alternativo))
            if len({int(x.group(1)) for x in outros}) > len({int(x.group(1)) for x in marcadores}):
                texto, marcadores, origem_texto = alternativo, outros, "pdftotext"
    if len(marcadores) < 10:
        return {"pdf": str(pdf), "erro": f"só {len(marcadores)} marcadores"}

    faixas, avisos = _faixas_por_materia(texto)
    if origem_texto != "pymupdf":
        avisos.append(f"texto lido pelo {origem_texto}: o pymupdf achou marcadores demais de menos")
    materia_de = {}
    for materia, (primeiro, ultimo) in faixas.items():
        for n in range(primeiro, ultimo + 1):
            materia_de[n] = materia

    # A questão que não cabe na página aparece de novo na seguinte, como
    # "17ª QUESTÃO (CONTINUAÇÃO)" — e é lá que estão as alternativas. Tratar a
    # segunda aparição como repetição a descartar deixava a questão sem nenhuma
    # alternativa (3 casos em 2008). Por isso o corpo se acumula por número, e a
    # separação de alternativas roda no texto inteiro, depois de juntar.
    corpos = _corpos_por_numero(texto, materia_de)

    questoes = []
    for numero in sorted(corpos):
        enunciado, alternativas = _separar_alternativas(corpos[numero])
        questoes.append({"numero": numero, "materia": materia_de[numero],
                         "enunciado": enunciado, "alternativas": alternativas})

    # Segunda tentativa, só para quem não fechou cinco alternativas: o mesmo PDF
    # relido com `sort=True`, que reordena por posição em vez de por ordem do
    # fluxo. Em 2012 as três primeiras questões saem TRUNCADAS na leitura normal
    # ("...pode-se af" e a alternativa (C) pela metade) e saem inteiras na
    # ordenada. Como fallback e não como padrão de propósito: a leitura normal é
    # a que foi conferida questão a questão contra o `ime_2018_fase1` que já está
    # em produção, e trocá-la para todo mundo jogaria fora essa conferência.
    incompletas = [q for q in questoes if len(q["alternativas"]) != 5]
    if incompletas:
        ordenado = _texto_ordenado(pdf)
        corpos_ord = _corpos_por_numero(ordenado, materia_de)
        for q in incompletas:
            if q["numero"] not in corpos_ord:
                continue
            enunciado, alternativas = _separar_alternativas(corpos_ord[q["numero"]])
            if len(alternativas) == 5:
                q["enunciado"], q["alternativas"] = enunciado, alternativas

    numeros = [q["numero"] for q in questoes]
    def prova_de(numero: int) -> str:
        return f"ime_{ano}_fase1{SUFIXO_MATERIA[materia_de[numero]]}"

    urls = recortar_e_subir(pdf, numeros, prova_de, _localizar_marcador_ime)
    doc = pymupdf.open(pdf)
    paginas = {}
    for i, page in enumerate(doc, start=1):
        for n in _localizar_marcador_ime(page, numeros):
            paginas.setdefault(n, i)
    doc.close()

    contagem = {"Matemática": 0, "Física": 0, "Química": 0}
    anuladas, sem_gabarito, sem_alternativas = [], [], []
    for q in questoes:
        letra = (gabarito or {}).get(q["numero"])
        if letra == "ANULADA":
            # A banca disse que não há resposta única. Entra sem letra: sugerir
            # uma seria inventar (mesma regra do ITA em docs/23 §2.2).
            anuladas.append(q["numero"]); letra = None
        elif letra is None:
            sem_gabarito.append(q["numero"])
        if len(q["alternativas"]) != 5:
            sem_alternativas.append(q["numero"])
        escrever_questao(
            prova_de(q["numero"]), q["numero"], "IME", ano, 1, q["materia"], False,
            q["enunciado"], q["alternativas"], letra, "banca" if letra else None,
            urls.get(q["numero"]), pdf.name, paginas.get(q["numero"], 0),
        )
        contagem[q["materia"]] += 1
    return {"pdf": str(pdf), "ano": ano, "questoes": len(questoes), **contagem,
            "anuladas": anuladas, "sem_gabarito": sem_gabarito,
            "sem_alternativas": sem_alternativas, "origem_texto": origem_texto,
            "avisos": avisos}


def _aplicar_emendas_de_texto() -> tuple[int, list[str]]:
    """Reaplica as correções de enunciado de `config/emendas_texto.json`.

    Roda depois da extração, e não antes, porque é ela que reescreve o arquivo.
    Emenda cujo `de` sumiu do texto é reportada, nunca aplicada às cegas: quer
    dizer que a extração mudou e alguém precisa reconferir contra o PDF.
    """
    arquivo = PROJETO_ROOT / "config" / "emendas_texto.json"
    if not arquivo.exists():
        return 0, []
    aplicadas, ausentes = 0, []
    for emenda in json.loads(arquivo.read_text())["emendas"]:
        prova_id, _, numero = emenda["questao"].rpartition("_q")
        caminho = DIR_QUESTOES / prova_id / f"q{int(numero):02d}.json"
        if not caminho.exists():
            continue
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        texto = dados["enunciado_md"] or ""
        if emenda["de"] not in texto:
            if emenda["para"] not in texto:
                ausentes.append(f"{emenda['questao']}: {emenda['de']!r}")
            continue
        dados["enunciado_md"] = texto.replace(emenda["de"], emenda["para"])
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
        aplicadas += 1
    return aplicadas, ausentes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lote", choices=["ita_oficial", "ime_oficial", "ime_objetiva"])
    ap.add_argument("--manifesto", type=Path, required=True,
                    help="JSON com a lista de arquivos (relativos a pdfs_originais/) ou de {ano,materia}")
    ap.add_argument("--sem-gabarito", action="store_true",
                    help="ime_objetiva: importa o ano mesmo quando o gabarito não converge "
                         "(as questões entram sem letra). Sem isto, o ano é pulado.")
    args = ap.parse_args()

    relatorio = []
    if args.lote == "ime_objetiva":
        # Gabarito conferido a olho contra a página renderizada, versionado em
        # config/. Não é a saída do parser: é a régua contra a qual ele responde.
        conferidos = json.loads(
            (PROJETO_ROOT / "config" / "_gabaritos_ime_objetiva.json").read_text()
        )["gabaritos"]
        for item in json.loads(args.manifesto.read_text()):
            ano, prova = item["ano"], DIR_PDFS / item["prova"]
            gabarito, avisos_gab = None, ["sem PDF de gabarito no acervo"]
            if item.get("gabarito"):
                gabarito, avisos_gab = gabarito_ime_objetiva.ler(DIR_PDFS / item["gabarito"])
            # A trava: o que o parser leu tem de bater com a conferência humana.
            # Sem isto, 2016 q25 e q27 entraram com a resposta que o IME
            # SUBSTITUIU, e nada na tela denunciaria (docs/23 §23.7).
            esperado = conferidos.get(str(ano))
            if gabarito and esperado:
                fora = sorted(int(n) for n, letra in esperado.items()
                              if gabarito.get(int(n)) != letra)
                if fora:
                    detalhe = ", ".join(
                        f"q{n}: conferido={esperado[str(n)]} lido={gabarito.get(n)}" for n in fora)
                    gabarito = None
                    avisos_gab = [f"NÃO bate com o gabarito conferido — {detalhe}"]
            if gabarito is None and not args.sem_gabarito:
                # Prova sem gabarito conferível é pior do que prova ausente: o
                # aluno resolve e não tem como conferir, e é a lacuna que o banco
                # já tem em 189 questões do IME. Só entra se alguém pedir.
                r = {"pdf": str(prova), "ano": ano,
                     "erro": "gabarito não convergiu: " + " ; ".join(avisos_gab)}
            else:
                try:
                    r = processar_ime_objetiva(prova, ano, gabarito)
                    r["avisos"] = r.get("avisos", []) + avisos_gab
                except Exception as e:
                    r = {"pdf": str(prova), "ano": ano, "erro": f"{type(e).__name__}: {e}"}
            relatorio.append(r)
            estado = ("erro: " + r["erro"] if "erro" in r else
                      f"{r['questoes']}q (mat={r['Matemática']} fis={r['Física']} qui={r['Química']})"
                      f" anuladas={r['anuladas']} sem_gab={r['sem_gabarito']}")
            print(f"  IME {ano}: {estado}", file=sys.stderr)
            for aviso in r.get("avisos", []):
                print(f"      ⚠ {aviso}", file=sys.stderr)
    elif args.lote == "ita_oficial":
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

    if args.lote == "ime_objetiva":
        aplicadas, ausentes = _aplicar_emendas_de_texto()
        print(f"\n  emendas de texto: {aplicadas} aplicada(s)", file=sys.stderr)
        for falta in ausentes:
            print(f"      ⚠ emenda não encontrada no texto — {falta}", file=sys.stderr)

    saida = PROJETO_ROOT / f"_relatorio_extracao_{args.lote}.json"
    saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2))
    erros = [r for r in relatorio if "erro" in r]
    print(f"\n{len(relatorio) - len(erros)} ok · {len(erros)} erro(s) → {saida}", file=sys.stderr)


if __name__ == "__main__":
    main()
