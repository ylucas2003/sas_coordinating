#!/usr/bin/env python3
"""Exporta o banco de questões de volta para JSON: Postgres → arquivos.

O caminho inverso do `importar_banco_questoes.py`, e a razão de ele existir:
desde docs/22 §13 as tabelas são a FONTE DA VERDADE e os JSONs não são
versionados. Sem uma saída, o acervo ficaria preso num volume de Postgres.

Serve a três coisas:

1. **Reprocessar uma prova.** O pipeline de `banco-questoes/` trabalha sobre
   arquivos. Para corrigir um enunciado ou reclassificar, exporte, edite, e
   reimporte.
2. **Backup fora do banco.** É o único dado do SAS que o Canvas não restaura
   (docs/15 §7 assumia que "o Canvas é o arquivo" — deixou de valer aqui).
3. **Provar que nada se perdeu.** `--conferir` compara o que sai com o que
   entrou, campo a campo.

Uso (a partir de api/):
    python -m scripts.exportar_banco_questoes
    python -m scripts.exportar_banco_questoes --destino /tmp/backup-banco
    python -m scripts.exportar_banco_questoes --conferir ~/algum/questoes_json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.banco.taxonomia import raiz_repositorio  # noqa: E402
from app.supabase_client import criar_cliente_supabase  # noqa: E402

# O PostgREST responde no máximo mil e poucas linhas por ida sem paginar; as
# tabelas aqui passam disso (1.399 ligações, 2.459 alternativas).
TAMANHO_PAGINA = 1000

_ORDEM_STATUS = (
    "texto_extraido",
    "alternativas_extraidas",
    "figuras_recortadas",
    "classificado",
    "revisado",
    "possivelmente_tem_figura",
)


def _todas_as_linhas(cliente: Any, tabela: str, colunas: str) -> list[dict[str, Any]]:
    """Lê a tabela inteira, em páginas. Aqui paginar é meio, não contrato.

    Diferente da listagem da API (docs/22 §2.2), onde a página é a resposta:
    este script só termina quando leu tudo, e para na primeira página curta.
    """
    linhas: list[dict[str, Any]] = []
    inicio = 0
    while True:
        pagina = (
            cliente.table(tabela)
            .select(colunas)
            .order("id" if tabela == "questao_vestibular" else "questao_id")
            .range(inicio, inicio + TAMANHO_PAGINA - 1)
            .execute()
            .data
            or []
        )
        linhas.extend(pagina)
        if len(pagina) < TAMANHO_PAGINA:
            return linhas
        inicio += TAMANHO_PAGINA


def _montar_json(
    questao: dict[str, Any],
    alternativas: list[dict[str, Any]],
    topicos: list[dict[str, Any]],
    nome_por_topico: dict[tuple[str, str], tuple[str, str]],
) -> dict[str, Any]:
    """Refaz o arquivo no formato que o pipeline escreve e lê.

    `topicos_nomes` e `blocos` são derivados da taxonomia em vez de guardados:
    são o mesmo dado que `topico_taxonomia` já tem, e duplicá-los na questão
    deixaria os dois divergirem no dia em que um tópico for renomeado.
    """
    materia = questao["materia"]
    codigos = sorted(t["topico_codigo"] for t in topicos)
    nomes = [nome_por_topico[(materia, c)][0] for c in codigos]
    # `dict.fromkeys` e não `set`: preserva a ordem dos tópicos, e bloco
    # repetido em questão mista aparece uma vez só.
    blocos = list(dict.fromkeys(nome_por_topico[(materia, c)][1] for c in codigos))

    # A confiança e a observação são por tópico no banco e por questão no
    # arquivo — o importador as replica em cada linha, então qualquer uma serve.
    primeiro = topicos[0] if topicos else {}

    saida: dict[str, Any] = {
        "id": questao["id"],
        "prova": {
            "vestibular": questao["vestibular"],
            "ano": questao["ano"],
            "fase": questao["fase"],
            "materia": materia,
        },
        "numero": questao["numero"],
        "dissertativa": questao["dissertativa"],
        "enunciado_md": questao["enunciado_md"],
        "alternativas": {a["letra"]: a["texto"] for a in sorted(alternativas, key=lambda x: x["letra"])},
        "gabarito": questao["gabarito"],
        # Vazio nas 934 desde sempre: a figura vai dentro do recorte único da
        # questão. A chave fica para o pipeline não precisar de `.get`.
        "imagens": [],
        "classificacao": {
            "topicos_ids": codigos,
            "topicos_nomes": nomes,
            "blocos": blocos,
            "classificado_por": questao.get("classificado_por") or "",
            "confianca": primeiro.get("confianca") or "",
            "observacao": primeiro.get("observacao") or "",
        },
        "fonte": {
            "pdf": questao.get("fonte_pdf"),
            "pagina": questao.get("fonte_pagina"),
            # Nunca foi preenchido nas 934 (docs/22 §13) — a chave fica pela
            # mesma razão de `imagens`.
            "bbox_questao": None,
        },
        "status": {
            "texto_extraido": questao["texto_extraido"],
            "alternativas_extraidas": questao["alternativas_extraidas"],
            "figuras_recortadas": questao["figuras_recortadas"],
            "classificado": bool(codigos),
            "revisado": questao["revisado"],
            "possivelmente_tem_figura": questao["possivelmente_tem_figura"],
        },
        "usa_imagem_no_render": questao["usa_imagem_no_render"],
    }
    if questao.get("imagem_url"):
        saida["imagem_questao_url"] = questao["imagem_url"]
    if questao.get("resolucao_url"):
        saida["resolucao_url"] = questao["resolucao_url"]
    return saida


def _pasta_da_questao(questao: dict[str, Any]) -> str:
    """A pasta é a prova, e o id já a carrega: 'ita_2019_fase1_q01' → 'ita_2019_fase1'.

    Derivar do id em vez de recompor de vestibular/ano/fase/matéria porque o
    sufixo de matéria (`_mat`, `_qui`) não sai de nenhuma coluna — é convenção
    de nome de pasta do pipeline, e o id é onde ela sobreviveu.
    """
    return questao["id"].rsplit("_q", 1)[0]


def exportar(cliente: Any, destino: Path) -> tuple[int, int]:
    questoes = _todas_as_linhas(cliente, "questao_vestibular", "*")
    alternativas = _todas_as_linhas(cliente, "questao_vestibular_alternativa", "*")
    ligacoes = _todas_as_linhas(cliente, "questao_vestibular_topico", "*")
    taxonomia = cliente.table("topico_taxonomia").select("materia, codigo, nome, bloco_nome").execute().data or []

    nome_por_topico = {(t["materia"], t["codigo"]): (t["nome"], t["bloco_nome"]) for t in taxonomia}
    alt_por_questao: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for linha in alternativas:
        alt_por_questao[linha["questao_id"]].append(linha)
    top_por_questao: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for linha in ligacoes:
        top_por_questao[linha["questao_id"]].append(linha)

    pastas: set[str] = set()
    for questao in questoes:
        pasta = destino / _pasta_da_questao(questao)
        pasta.mkdir(parents=True, exist_ok=True)
        pastas.add(pasta.name)
        numero = questao["id"].rsplit("_q", 1)[1]
        conteudo = _montar_json(
            questao,
            alt_por_questao[questao["id"]],
            top_por_questao[questao["id"]],
            nome_por_topico,
        )
        (pasta / f"q{numero}.json").write_text(
            json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return len(questoes), len(pastas)


def conferir(cliente: Any, original: Path) -> int:
    """Compara o que sai com um diretório de referência. Devolve nº de divergências.

    Não é diff de arquivo: o importador normaliza (tira controles C0) e o
    exportador reordena chave. O que se compara é o SIGNIFICADO — os campos que
    o SAS promete conservar.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        exportar(cliente, Path(tmp))
        divergencias = 0
        arquivos = sorted(p for p in original.glob("*/*.json") if not p.name.startswith("_"))
        for caminho in arquivos:
            gerado = Path(tmp) / caminho.parent.name / caminho.name
            if not gerado.exists():
                print(f"  ! não exportado: {caminho.parent.name}/{caminho.name}")
                divergencias += 1
                continue
            antes = json.loads(caminho.read_text(encoding="utf-8"))
            depois = json.loads(gerado.read_text(encoding="utf-8"))
            for campo in ("id", "numero", "gabarito", "prova", "alternativas"):
                if antes.get(campo) != depois.get(campo):
                    # Controle C0 removido na importação é diferença esperada.
                    if campo == "alternativas" and _iguais_sem_controles(
                        antes.get(campo), depois.get(campo)
                    ):
                        continue
                    print(f"  ! {caminho.parent.name}/{caminho.name}: {campo} divergiu")
                    divergencias += 1
            if sorted((antes.get("classificacao") or {}).get("topicos_ids") or []) != (
                depois["classificacao"]["topicos_ids"]
            ):
                print(f"  ! {caminho.parent.name}/{caminho.name}: topicos_ids divergiu")
                divergencias += 1
            if (antes.get("fonte") or {}).get("pagina") != depois["fonte"]["pagina"]:
                print(f"  ! {caminho.parent.name}/{caminho.name}: fonte.pagina divergiu")
                divergencias += 1
        return divergencias


def _iguais_sem_controles(a: Any, b: Any) -> bool:
    import re

    controles = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
    normalizar = lambda v: {k: controles.sub("", t) for k, t in (v or {}).items()}  # noqa: E731
    return normalizar(a) == normalizar(b)


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta o banco de questões para JSON.")
    parser.add_argument(
        "--destino",
        type=Path,
        default=None,
        help="onde escrever (padrão: banco-questoes/questoes_json/ do repositório)",
    )
    parser.add_argument(
        "--conferir",
        type=Path,
        default=None,
        help="compara a exportação com este diretório em vez de escrever",
    )
    args = parser.parse_args()

    cliente = criar_cliente_supabase()

    if args.conferir:
        print(f"conferindo contra {args.conferir} …")
        divergencias = conferir(cliente, args.conferir)
        if divergencias:
            print(f"\n  ✗ {divergencias} divergência(s).")
            return 1
        print("\n  ✓ nenhuma divergência: o que entrou é o que sai.")
        return 0

    destino = args.destino or (raiz_repositorio() / "banco-questoes" / "questoes_json")
    destino.mkdir(parents=True, exist_ok=True)
    total, pastas = exportar(cliente, destino)
    print(f"  ✓ {total} questões em {pastas} pastas → {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
