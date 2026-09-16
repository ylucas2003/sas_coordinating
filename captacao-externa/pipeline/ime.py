"""Raspa o Resultado Preliminar do Exame de Escolaridade do concurso de
admissão do IME (CACFG — Curso de Formação e Graduação, o vestibular civil
de ensino médio, não confundir com o "CP/IME" de pós-graduação de oficiais
já formados) e grava um JSON em dados/.

Uso:
    ./.venv/bin/python pipeline/ime.py

## Sem `--anos`, de propósito — isto é um retrato, não um arquivo histórico

As outras três fontes (OBMEP, OBM, ITA) têm URL por ANO — dá pra escolher
qual ano raspar. O IME não: `inscricoes.ime.eb.br/documentos/ATIVA.pdf` e
`.../RESERVA.pdf` são os nomes FIXOS que o site usa pro ciclo CORRENTE, e são
sobrescritos a cada concurso novo — não existe (achado procurando: Dossiê de
Provas já registrava "não há padrão de URL único e estável confirmado" pro
IME) um arquivo por ano pra voltar atrás. Rodar este script daqui a um ano
traz o resultado de OUTRO concurso, não deste — por isso o `ano` do registro
vem de DENTRO do PDF ("CACFG 2025/2026" no cabeçalho), nunca de um argumento
de linha de comando, e o nome do JSON de saída (`dados/ime_{ano}.json`) seria
sobrescrito numa rodada futura se o ano não mudar de verdade.

## Ativa e Reserva são dois arquivos, dois PDFs, uma tabela cada

"CACFG ATIVA" é a carreira de oficial da ativa; "CACFG RESERVA" é reserva —
a distinção entra em `resultado`, igual ATIVA/RESERVA já entrava pra OBM
(pipeline/obm.py). Cada PDF também publica uma segunda relação — "Não
Aprovados" — SEM coluna de nome (só inscrição, pra não expor quem não
passou); esta função ignora essa parte inteira: o padrão de linha que ela
casa (rank + inscrição + sigilo + NOME + notas + local + situação) não
existe nela, então ela nunca é capturada — não precisa filtrar à mão.

## Texto de PDF de verdade, não imagem escaneada — mas fora de ordem

`pymupdf` extrai o texto perfeitamente (nenhuma tabela é imagem), mas a
ordem do CABEÇALHO na extração não é a ordem visual das colunas — só a
ordem das LINHAS DE DADO é estável: classif, inscrição, sigilo, nome, média,
mat, fis, qui, port, ing, local do exame, situação, sempre nessa sequência,
uma por linha. O regex de `_padrao_linha` casa por essa sequência, não pelo
cabeçalho.

## Sem escola, sem série de referência — mesma ausência da ITA (docs/41 §6.1)

O relatório não diz escola nem se o candidato é treineiro ou formando (não
tem "nível" por série, é vestibular de verdade). `escola_informada` sai `""`
e `nivel_texto` sai `""` — nunca `None`: o índice único de dedup (migration
0057) trata NULL como sempre-diferente-de-NULL, e a OBM e a ITA já
descobriram isso rodando de verdade (docs/41 §5.1, §6.1) antes deste arquivo
existir.

## "Local de Exame" é a cidade da PROVA, não do candidato

Mesmíssima ressalva da ITA: quem mora longe faz a prova no local mais perto,
não na própria cidade. `_CIDADE_DA_BANCA` é a mesma lista de cidades
(municípios onde as Forças Armadas costumam abrir banca de concurso
nacional) — coincide quase inteira com a da ITA por serem os mesmos tipos de
cidade-sede, com "Vila Velha" (ES) a mais, conferida contra todo valor visto
nos dois PDFs.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf
import requests
import urllib3

# O certificado de inscricoes.ime.eb.br não manda a cadeia intermediária —
# achado rodando de verdade, e já registrado pelo Dossiê de Provas antes
# deste script existir ("as duas tentativas de acesso automático falharam
# por erro de certificado SSL"). `curl` tolera porque completa a cadeia com
# certificados que já tem por perto; o verificador do Python não. Não é
# downgrade de segurança escolhido à toa: é o único jeito de falar com este
# servidor específico, e o aviso correspondente é silenciado de propósito
# (senão sai um por requisição).
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = "https://inscricoes.ime.eb.br/documentos"
DIR_DADOS = Path(__file__).resolve().parent.parent / "dados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# Mesma lista de cidades-sede de concurso nacional da ITA (pipeline/ita.py),
# mais "Vila Velha" — as duas Forças usam basicamente o mesmo conjunto de
# capitais/cidades grandes como banca. Conferida contra todo "Local de
# Exame" visto nos PDFs de ATIVA e RESERVA do CACFG 2025/2026.
_CIDADE_DA_BANCA: dict[str, tuple[str, str]] = {
    "BELEM": ("Belém", "PA"),
    "BELO HORIZONTE": ("Belo Horizonte", "MG"),
    "BRASILIA": ("Brasília", "DF"),
    "CAMPINAS": ("Campinas", "SP"),
    "CAMPO GRANDE": ("Campo Grande", "MS"),
    "CUIABA": ("Cuiabá", "MT"),
    "CURITIBA": ("Curitiba", "PR"),
    "FLORIANOPOLIS": ("Florianópolis", "SC"),
    "FORTALEZA": ("Fortaleza", "CE"),
    "GOIANIA": ("Goiânia", "GO"),
    "JUIZ DE FORA": ("Juiz de Fora", "MG"),
    "LONDRINA": ("Londrina", "PR"),
    "MANAUS": ("Manaus", "AM"),
    "NATAL": ("Natal", "RN"),
    "PORTO ALEGRE": ("Porto Alegre", "RS"),
    "RECIFE": ("Recife", "PE"),
    "RIBEIRAO PRETO": ("Ribeirão Preto", "SP"),
    "RIO DE JANEIRO": ("Rio de Janeiro", "RJ"),
    "SALVADOR": ("Salvador", "BA"),
    "SAO JOSE DO RIO PRETO": ("São José do Rio Preto", "SP"),
    "SAO JOSE DOS CAMPOS": ("São José dos Campos", "SP"),
    "SAO LUIS": ("São Luís", "MA"),
    "SAO PAULO": ("São Paulo", "SP"),
    "TERESINA": ("Teresina", "PI"),
    "VITORIA": ("Vitória", "ES"),
    "VILA VELHA": ("Vila Velha", "ES"),
}

def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


_SITUACAO = {
    "1": "ampla concorrência",
    "2": "Lei 12.990 (cota racial)",
    "3": "excedente",
}

# rank, inscrição, sigilo, NOME, média, mat, fis, qui, port, ing, local, situação
# — sempre nessa ordem numa linha de candidato APROVADO (docstring do módulo).
# A relação de NÃO aprovados não tem NOME nenhum, então nunca casa aqui.
_PADRAO_LINHA = re.compile(
    r"(\d+)°\n(\d+)\n(\d+)\n(.+?)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([\d,]+)\n([^\n]+)\n\((\d)\)"
)


@dataclass
class Registro:
    prova_nome: str
    ano: int
    nivel_texto: str
    serie_referencia_min: int | None
    serie_referencia_max: int | None
    resultado: str
    nome_informado: str
    escola_informada: str
    cidade_informada: str
    uf_informada: str
    fonte_url: str


def parsear_pdf(caminho_pdf: str, conteudo: bytes, modalidade: str, fonte_url: str) -> tuple[int, list[Registro]]:
    doc = pymupdf.open(stream=conteudo, filetype="pdf")
    texto = "".join(pagina.get_text() for pagina in doc)

    m_ano = re.search(r"CACFG (\d{4})/\d{4}", texto)
    if not m_ano:
        raise ValueError(f"não achei 'CACFG AAAA/AAAA' no cabeçalho de {caminho_pdf} — layout mudou?")
    ano = int(m_ano.group(1))

    registros: list[Registro] = []
    for _classif, _inscricao, _sigilo, nome, _media, _mat, _fis, _qui, _port, _ing, local, situacao in _PADRAO_LINHA.findall(texto):
        nome = nome.strip()
        if not nome:
            continue
        local_normalizado = _sem_acento(local.strip()).upper()
        cidade, uf = _CIDADE_DA_BANCA.get(local_normalizado, (local.strip(), ""))
        if local_normalizado not in _CIDADE_DA_BANCA:
            print(f"  aviso: local de exame desconhecido {local!r} — sem UF", file=sys.stderr)

        registros.append(
            Registro(
                prova_nome="IME",
                ano=ano,
                nivel_texto="",
                serie_referencia_min=None,
                serie_referencia_max=None,
                resultado=f"{modalidade} — {_SITUACAO.get(situacao, f'situação {situacao}')}",
                nome_informado=nome,
                escola_informada="",
                cidade_informada=cidade,
                uf_informada=uf,
                fonte_url=fonte_url,
            )
        )
    return ano, registros


def raspar() -> tuple[int, list[Registro]]:
    todos: list[Registro] = []
    ano_visto: int | None = None
    for modalidade, arquivo in (("ATIVA", "ATIVA.pdf"), ("RESERVA", "RESERVA.pdf")):
        url = f"{BASE}/{arquivo}"
        resp = requests.get(url, headers=HEADERS, timeout=30, verify=False)
        resp.raise_for_status()
        ano, registros = parsear_pdf(arquivo, resp.content, modalidade, url)
        if ano_visto is not None and ano != ano_visto:
            raise ValueError(f"ATIVA diz {ano_visto}, {arquivo} diz {ano} — os dois PDFs deviam ser do mesmo ciclo")
        ano_visto = ano
        todos.extend(registros)
        print(f"  {modalidade}: {len(registros)} aprovados ({ano})", file=sys.stderr)

    assert ano_visto is not None
    return ano_visto, todos


def main() -> None:
    DIR_DADOS.mkdir(exist_ok=True)
    print("IME (CACFG) — raspando ATIVA e RESERVA...", file=sys.stderr)
    try:
        ano, registros = raspar()
    except requests.HTTPError as e:
        print(f"  falhou: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    if not registros:
        print("  0 registros — algo mudou no site, confira antes de importar", file=sys.stderr)
        raise SystemExit(1)

    destino = DIR_DADOS / f"ime_{ano}.json"
    destino.write_text(
        json.dumps([r.__dict__ for r in registros], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  IME {ano} → {len(registros)} registros → {destino}", file=sys.stderr)


if __name__ == "__main__":
    main()
