"""gerar_imagem_pagina.py — Modo página para o acervo histórico (docs/24).

Troca a imagem de uma questão do acervo histórico de um RECORTE FINO
(heurística de bbox, frágil — "Bug D", docs/23 §12.1) para a PÁGINA INTEIRA
do PDF onde a questão está (1 ou 2, compostas verticalmente quando a questão
atravessa a virada de página). Não recorta, não transcreve — só renderiza a
página como ela é.

Diferente de `extrair_lote_historico.py::escrever_questao()`, que recria o
JSON do zero, este script faz merge cirúrgico (load → muta só os campos
dele → save): `enunciado_md`, `alternativas`, `gabarito*`, `resolucao_md`,
`classificacao` nunca são lidos nem escritos aqui — ficam intactos por
construção. É a garantia de que nada do que já foi transcrito/corrigido
(docs/23 §10-20) é apagado.

Uso:
    python pipeline/gerar_imagem_pagina.py --prova-id ime_1998_fase2_qui
    python pipeline/gerar_imagem_pagina.py --ano 2015 --materia Física   # ITA, as duas fases
    python pipeline/gerar_imagem_pagina.py --todas-historicas
    python pipeline/gerar_imagem_pagina.py --dry-run --prova-id ita_2015_fase1

Roda de dentro de `banco-questoes/` (mesma convenção dos outros scripts do
pipeline).
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from pathlib import Path

import pymupdf
from dotenv import load_dotenv

from _comum import eh_historico

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_PDFS = PROJETO_ROOT / "pdfs_originais"
DIR_QUESTOES = PROJETO_ROOT / "questoes_json"
ARQUIVO_OVERRIDES = PROJETO_ROOT / "config" / "overrides_pagina.json"

load_dotenv(PROJETO_ROOT / ".env")
import boto3  # noqa: E402

_S3_BUCKET = os.getenv("S3_BUCKET", "ita-por-assunto")
_S3_REGION = os.getenv("AWS_REGION", "us-east-1")
_S3 = boto3.client("s3", region_name=_S3_REGION)

_NOME_ARQUIVO_MATERIA = {"Física": "fisica", "Química": "quimica", "Matemática": "matematica"}
_SUFIXO_MATERIA = {"Física": "", "Química": "_qui", "Matemática": "_mat"}

# Mesmas variantes de grafia de extrair_lote_historico.py — precisam ficar
# em sincronia se aquele arquivo ganhar uma variante nova (nenhuma automação
# hoje pra isso, é o mesmo tipo de duplicação que _comum.py já eliminou pra
# eh_historico(); aceito aqui porque mover pra _comum.py também exigiria
# alterar extrair_lote_historico.py, fora do escopo desta mudança).
VARIANTES_QUESTAO_ITA = ["Questão {n}.", "Questão {n} .", "Quest˜ao {n}.", "Quest˜ao {n} .", "Questao {n}."]
# "{n}a Questã" (sem o "o" final, de propósito) é o que resolve as 3 provas
# que tinham fonte.pagina sempre 0 (ime_1998_fase2*, achado processando este
# script): o PDF foi salvo a partir de uma página HTML impressa no navegador
# em 2005 e usa "1a Questão" (ordinal comum, não "ª") em vez de "1ª QUESTÃO";
# em ~40% das ocorrências (quimica9899.pdf) ainda carrega o mesmo bug de
# espaço espúrio pós-vogal-nasal do docs/23 §10 dentro do PRÓPRIO marcador
# ("3a Questã o", não "3a Questão") — cortar o "o" final evita depender do
# espaço estar lá ou não. As 3 provas ficaram 30/30 localizadas sem
# intervenção manual (config/overrides_pagina.json existe só como rede de
# segurança para o próximo caso parecido, não porque este precisou dele).
VARIANTES_QUESTAO_IME = ["{n}ª QUESTÃO", "{n}ª Questão", "{n}a QUESTÃO", "{n}ª questão", "{n}a Questã"]


class ErroResolucaoPdf(Exception):
    pass


class ErroFormatoInesperado(Exception):
    pass


# ─── Localização de página (idêntica em espírito a extrair_lote_historico.py,
#     mas devolve só {numero: página}, nunca um Rect — não recortamos) ──────


def _localizar_pagina_nativa(page, numeros, variantes) -> dict[int, "pymupdf.Rect"]:
    achados = {}
    for n in numeros:
        for v in variantes:
            rects = page.search_for(v.format(n=n))
            if rects:
                achados[n] = rects[0]
                break
    return achados


# Fallback por regex sobre get_text() corrido — search_for() exige que os
# glifos do marcador sejam geometricamente contíguos, e pelo menos duas
# provas (ita_2011/2013_fase1_mat, "Questão 01." com zero à esquerda que as
# VARIANTES não previam) e uma terceira (ita_2016_fase1_mat: "Questão" e o
# número renderizados como runs de glifo separados por um espaço que não é
# um espaço de verdade — search_for("Questão 1.") falha mesmo com
# search_for("Questão") e search_for("1.") achando cada pedaço isolado)
# quebram esse pressuposto. get_text() concatena os runs corretamente onde
# search_for não consegue casar a string inteira. \s* entre cada peça cobre
# tanto isso quanto o bug de espaço espúrio pós-vogal-nasal do §10 quando ele
# cai dentro do próprio marcador ("QUESTÃ O", achado em quimica9899.pdf e
# mat0203.pdf) — union com o resultado de search_for, nunca substituição,
# para não arriscar as ~1400 questões que search_for já localiza bem.
PADRAO_QUESTAO_ITA_TEXTO = re.compile(r"Quest(?:ão|ao|˜ao)\s*0?(\d{1,2})\s*\.", re.IGNORECASE)
PADRAO_QUESTAO_IME_TEXTO = re.compile(r"(\d{1,2})\s*[ªºao]?\s*QUEST\s*[ÃA]\s*O", re.IGNORECASE)


def _localizar_pagina_por_texto(page, numeros: set[int], vestibular: str) -> dict[int, int]:
    padrao = PADRAO_QUESTAO_ITA_TEXTO if vestibular == "ITA" else PADRAO_QUESTAO_IME_TEXTO
    achados = {}
    for m in padrao.finditer(page.get_text()):
        n = int(m.group(1))
        if n in numeros:
            achados.setdefault(n, True)
    return achados


def localizar_todas_paginas(doc, numeros: list[int], variantes: list[str], vestibular: str = "ITA") -> dict[int, int]:
    """{numero: primeira página 1-based onde o marcador apareceu}."""
    achadas: dict[int, int] = {}
    for i, page in enumerate(doc, start=1):
        for n, _ in _localizar_pagina_nativa(page, numeros, variantes).items():
            achadas.setdefault(n, i)
    faltam = {n for n in numeros if n not in achadas}
    if faltam:
        for i, page in enumerate(doc, start=1):
            for n in _localizar_pagina_por_texto(page, faltam, vestibular):
                achadas.setdefault(n, i)
    return achadas


def paginas_da_questao(numero: int, paginas_por_numero: dict[int, int]) -> list[int]:
    """[pág] se cabe numa página; [pág, pág+1] se a próxima questão (mesmo
    PDF, pode estar em outra prova_id quando é a virada fase1→fase2 do ITA)
    está na seguinte — nunca mais que 2 (invariante do domínio: uma questão
    de vestibular nunca atravessa mais que a virada de uma página)."""
    pag = paginas_por_numero[numero]
    seguintes = sorted(p for n, p in paginas_por_numero.items() if n > numero)
    prox_pag = seguintes[0] if seguintes else pag
    return [pag] if prox_pag <= pag else [pag, pag + 1]


# ─── Resolução do PDF fonte ─────────────────────────────────────────────────


def caminho_pdf_ita(ano: int, materia: str) -> Path:
    nome = _NOME_ARQUIVO_MATERIA[materia]
    return DIR_PDFS / "ita_historico" / "oficial_1fase_2008_2018" / str(ano) / f"{nome}_{ano}.pdf"


def resolver_pdf_ime(ano: int, basename: str) -> Path:
    """`fonte.pdf` é só o basename (`quimica.pdf`), e o mesmo basename se
    repete em 7 anos diferentes do acervo IME — resolver por basename sozinho
    abriria o PDF errado em silêncio. Restringe pela pasta `provasAA_BB`
    derivada do ano ANTES de comparar nome."""
    raiz = DIR_PDFS / "ime_historico" / "oficial_1996_2019"
    aa, bb = ano % 100, (ano + 1) % 100
    pasta = raiz / f"provas{aa:02d}_{bb:02d}"
    if pasta.is_dir():
        for p in pasta.iterdir():
            if p.is_file() and p.name.lower() == basename.lower():
                return p
    # Fallback: nomenclatura fora do padrão provasAA_BB (ex. "CFG-MAT-2006-2007.pdf").
    # Ambíguo é erro, não palpite.
    candidatos = [p for p in raiz.rglob("*") if p.is_file() and p.name.lower() == basename.lower()]
    if len(candidatos) == 1:
        return candidatos[0]
    raise ErroResolucaoPdf(
        f"ano={ano} basename={basename}: {len(candidatos)} candidato(s) fora da pasta provas{aa:02d}_{bb:02d}, esperava 1"
    )


# ─── Renderização (sem clip — página inteira) ──────────────────────────────


def renderizar_paginas(doc, paginas: list[int], dpi: int = 200) -> bytes:
    pixmaps = [doc[p - 1].get_pixmap(dpi=dpi) for p in paginas]
    if len(pixmaps) == 1:
        return pixmaps[0].tobytes("png")
    from PIL import Image

    imgs = [Image.frombytes("RGB", (p.width, p.height), p.samples) for p in pixmaps]
    largura = max(im.width for im in imgs)
    altura = sum(im.height for im in imgs)
    composta = Image.new("RGB", (largura, altura), "white")
    y = 0
    for im in imgs:
        composta.paste(im, (0, y))
        y += im.height
    buf = io.BytesIO()
    composta.save(buf, format="PNG")
    return buf.getvalue()


# ─── Merge cirúrgico no JSON — nunca recria o dict ─────────────────────────


def atualizar_json_com_pagina(caminho: Path, url: str, paginas: list[int], dry_run: bool) -> None:
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    if "status" not in dados or "fonte" not in dados:
        raise ErroFormatoInesperado(f"{caminho}: schema sem 'status'/'fonte' — não sobrescrevo às cegas")
    dados["imagem_questao_url"] = url
    dados["usa_imagem_no_render"] = True
    dados["extraido_por"] = "pagina"
    dados["fonte"]["pagina"] = paginas[0]
    dados["fonte"]["pagina_fim"] = paginas[-1] if len(paginas) > 1 else None
    dados["status"]["figuras_recortadas"] = True
    # enunciado_md, alternativas, gabarito*, resolucao_md, classificacao:
    # nunca lidos nem escritos aqui — ficam intactos.
    if not dry_run:
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Processamento por grupo (um PDF, uma ou duas prova_id) ────────────────


def _carregar_overrides() -> dict[str, list[int]]:
    if ARQUIVO_OVERRIDES.exists():
        return json.loads(ARQUIVO_OVERRIDES.read_text())
    return {}


def _questoes_do_grupo(prova_ids: list[str]) -> list[tuple[str, Path, dict]]:
    """[(prova_id, caminho_json, dados)] de todo q*.json nas pastas dadas."""
    saida = []
    for prova_id in prova_ids:
        pasta = DIR_QUESTOES / prova_id
        if not pasta.is_dir():
            continue
        for f in sorted(pasta.glob("q*.json")):
            saida.append((prova_id, f, json.loads(f.read_text(encoding="utf-8"))))
    return saida


def processar_grupo_ita(ano: int, materia: str, dpi: int, dry_run: bool, overrides: dict) -> dict:
    sufixo = _SUFIXO_MATERIA[materia]
    prova_ids = [f"ita_{ano}_fase1{sufixo}", f"ita_{ano}_fase2{sufixo}"]
    itens = _questoes_do_grupo(prova_ids)
    if not itens:
        return {"grupo": f"ita {ano} {materia}", "erro": "nenhuma questão encontrada em questoes_json/"}

    pdf = caminho_pdf_ita(ano, materia)
    if not pdf.exists():
        return {"grupo": f"ita {ano} {materia}", "erro": f"PDF não encontrado: {pdf}"}

    return _processar_itens(f"ita_{ano}_{materia}", pdf, itens, VARIANTES_QUESTAO_ITA, dpi, dry_run, overrides, "ITA")


def processar_grupo_ime(prova_id: str, dpi: int, dry_run: bool, overrides: dict) -> dict:
    itens = _questoes_do_grupo([prova_id])
    if not itens:
        return {"grupo": prova_id, "erro": "nenhuma questão encontrada em questoes_json/"}

    basename = itens[0][2].get("fonte", {}).get("pdf")
    ano = itens[0][2].get("prova", {}).get("ano")
    if not basename or not ano:
        return {"grupo": prova_id, "erro": "fonte.pdf ou prova.ano ausente no JSON"}
    try:
        pdf = resolver_pdf_ime(ano, basename)
    except ErroResolucaoPdf as e:
        return {"grupo": prova_id, "erro": str(e)}

    return _processar_itens(prova_id, pdf, itens, VARIANTES_QUESTAO_IME, dpi, dry_run, overrides, "IME")


def _processar_itens(chave_grupo, pdf, itens, variantes, dpi, dry_run, overrides, vestibular="ITA") -> dict:
    doc = pymupdf.open(pdf)
    numeros = [dados["numero"] for _, _, dados in itens]

    # Override tem prioridade — usado nas provas onde a localização automática
    # já se provou incapaz de achar marcador nenhum (config/overrides_pagina.json).
    tem_override = {dados["id"]: overrides[dados["id"]] for _, _, dados in itens if dados["id"] in overrides}
    faltam = [n for n, (_, _, dados) in zip(numeros, itens) if dados["id"] not in tem_override]

    paginas_por_numero: dict[int, int] = {}
    if faltam:
        paginas_por_numero = localizar_todas_paginas(doc, faltam, variantes, vestibular)

    resultado = {"grupo": chave_grupo, "pdf": str(pdf), "ok": 0, "sem_localizacao": [], "erros": []}
    # Várias questões da mesma prova costumam compartilhar página (ou par de
    # páginas) — cachear por essa chave evita rerenderizar/reenviar o mesmo
    # PNG várias vezes num PDF com N questões por página.
    cache_png: dict[tuple[int, ...], bytes] = {}
    for prova_id, caminho, dados in itens:
        numero, id_q = dados["numero"], dados["id"]
        if id_q in tem_override:
            paginas = tem_override[id_q]
        elif numero in paginas_por_numero:
            paginas = paginas_da_questao(numero, paginas_por_numero)
        else:
            resultado["sem_localizacao"].append(id_q)
            continue

        try:
            chave_cache = tuple(paginas)
            if chave_cache not in cache_png:
                cache_png[chave_cache] = renderizar_paginas(doc, paginas, dpi=dpi)
            png = cache_png[chave_cache]
            chave_s3 = f"imagens/{prova_id}/{prova_id}_q{numero:02d}_pagina.png"
            if not dry_run:
                _S3.put_object(Bucket=_S3_BUCKET, Key=chave_s3, Body=png, ContentType="image/png")
            url = f"https://{_S3_BUCKET}.s3.{_S3_REGION}.amazonaws.com/{chave_s3}"
            atualizar_json_com_pagina(caminho, url, paginas, dry_run)
            resultado["ok"] += 1
        except Exception as e:  # nunca derruba o lote inteiro por uma questão
            resultado["erros"].append(f"{id_q}: {type(e).__name__}: {e}")

    doc.close()
    return resultado


# ─── Descoberta de "todas as históricas" ───────────────────────────────────


def _grupos_historicos() -> tuple[list[tuple[int, str]], list[str]]:
    """(pares ano/matéria do ITA, prova_ids do IME) cobrindo todo prova_id
    de questoes_json/ que eh_historico() aceita."""
    ita_pares: set[tuple[int, str]] = set()
    ime_ids: list[str] = []
    for pasta in sorted(DIR_QUESTOES.iterdir()):
        if not pasta.is_dir() or not eh_historico(pasta.name):
            continue
        m = re.match(r"ita_(\d{4})_fase[12](_qui|_mat)?$", pasta.name)
        if m:
            ano = int(m.group(1))
            sufixo = m.group(2) or ""
            materia = {v: k for k, v in _SUFIXO_MATERIA.items()}[sufixo]
            ita_pares.add((ano, materia))
        elif pasta.name.startswith("ime_"):
            ime_ids.append(pasta.name)
    return sorted(ita_pares), ime_ids


def main():
    ap = argparse.ArgumentParser()
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--prova-id", help="prova_id do IME (ex. ime_1998_fase2_qui)")
    grupo.add_argument("--ita", nargs=2, metavar=("ANO", "MATERIA"), help="ex. --ita 2015 Física")
    grupo.add_argument("--todas-historicas", action="store_true")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true", help="não sobe no S3 nem grava o JSON, só relata")
    args = ap.parse_args()

    overrides = _carregar_overrides()
    relatorios = []

    if args.prova_id:
        relatorios.append(processar_grupo_ime(args.prova_id, args.dpi, args.dry_run, overrides))
    elif args.ita:
        ano, materia = int(args.ita[0]), args.ita[1]
        relatorios.append(processar_grupo_ita(ano, materia, args.dpi, args.dry_run, overrides))
    else:
        ita_pares, ime_ids = _grupos_historicos()
        for ano, materia in ita_pares:
            relatorios.append(processar_grupo_ita(ano, materia, args.dpi, args.dry_run, overrides))
        for prova_id in ime_ids:
            relatorios.append(processar_grupo_ime(prova_id, args.dpi, args.dry_run, overrides))

    for r in relatorios:
        if "erro" in r:
            print(f"  {r['grupo']}: ERRO {r['erro']}", file=sys.stderr)
        else:
            status = f"{r['ok']} ok"
            if r["sem_localizacao"]:
                status += f", {len(r['sem_localizacao'])} sem localização: {r['sem_localizacao']}"
            if r["erros"]:
                status += f", {len(r['erros'])} erro(s): {r['erros']}"
            print(f"  {r['grupo']}: {status}", file=sys.stderr)

    ok_total = sum(r.get("ok", 0) for r in relatorios)
    print(f"\n{ok_total} questão(ões) processada(s){' (dry-run, nada gravado)' if args.dry_run else ''}", file=sys.stderr)


if __name__ == "__main__":
    main()
