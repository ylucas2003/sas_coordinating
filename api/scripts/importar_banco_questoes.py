#!/usr/bin/env python3
"""Importa o banco de questões ITA · IME para o Postgres (docs/22 §P1).

Lê os 934 JSONs de `banco-questoes/questoes_json/` e as três taxonomias de
`banco-questoes/config/`, e faz upsert em `topico_taxonomia`,
`questao_vestibular` e `questao_vestibular_topico`.

Idempotente: rodar duas vezes não duplica nada. Corrigir um JSON e rodar de novo
é o ciclo de trabalho normal — inclusive quando a correção *tira* um tópico da
classificação, que o importador então apaga da ligação.

Falha alto: tópico que não existe na taxonomia da matéria para tudo, antes de
escrever qualquer linha, dizendo qual arquivo e qual código.

Uso (a partir de api/):
    python -m scripts.importar_banco_questoes
    python -m scripts.importar_banco_questoes --raiz /caminho/de/uma/amostra

Depois de rodar pela primeira vez (as tabelas são novas), o PostgREST precisa de
`docker compose restart postgrest` — ele cacheia o schema na inicialização e sem
isso as rotas do banco devolvem 404 (CLAUDE.md, armadilha 1).

Conexão: usa POSTGREST_URL (ou SUPABASE_*) do .env.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.banco.importador import ErroImportacao, RelatorioImportacao, importar  # noqa: E402
from app.supabase_client import criar_cliente_supabase  # noqa: E402

# Fotografia do acervo, não meta. Divergir não é erro por si — prova nova
# processada muda todos estes números de uma vez —, mas divergir SEM ninguém ter
# mexido no pipeline quer dizer que algo entrou torto, e é a única chance de
# perceber isso antes de a tela mostrar um recorte incompleto.
#
# ⚠️ **Atualize junto com o acervo.** Ficaram nos 934 de 22/08 enquanto o banco
# crescia para 2.693, então TODA importação terminava com "8 números fora do
# esperado" — e um alarme que dispara sempre é um alarme que ninguém lê. Foi
# assim durante os lotes de 23/08 a 29/08 (docs/23 §23.9).
#
# Conferidos em 29/08/2026, depois da fase 1 do IME 2007–2016 e da entrada de
# 2009 e 2011, cujos gabaritos oficiais estavam noutra árvore do site do IME
# (docs/23 §23 e §24).
ESPERADO: dict[str, int] = {
    "total": 2773,
    "Física": 957,
    "Química": 848,
    "Matemática": 968,
    "sem_classificacao": 44,
    "dissertativas": 1271,
    "sem_gabarito": 1340,
    "com_imagem": 2710,
    # 18 subáreas em Física + 26 em Química + 21 em Matemática.
    "topicos_importados": 65,
}


def _linha(rotulo: str, obtido: int, chave: str) -> bool:
    """Imprime uma linha do relatório. Devolve True se bateu com o esperado."""
    esperado = ESPERADO[chave]
    bateu = obtido == esperado
    marca = "✓" if bateu else "!"
    sufixo = "" if bateu else f"   ← esperado {esperado}"
    print(f"  {marca} {rotulo:.<28} {obtido:>5}{sufixo}")
    return bateu


def _imprimir(relatorio: RelatorioImportacao) -> None:
    print("\n═══ Banco de questões importado ═══")
    divergencias = 0
    divergencias += not _linha("questões", relatorio.total, "total")
    for materia in ("Física", "Química", "Matemática"):
        divergencias += not _linha(materia, relatorio.por_materia.get(materia, 0), materia)
    divergencias += not _linha("sem classificação", relatorio.sem_classificacao, "sem_classificacao")
    divergencias += not _linha("dissertativas", relatorio.dissertativas, "dissertativas")
    divergencias += not _linha("sem gabarito", relatorio.sem_gabarito, "sem_gabarito")
    divergencias += not _linha("com imagem no S3", relatorio.com_imagem, "com_imagem")
    divergencias += not _linha("tópicos da taxonomia", relatorio.topicos_importados,
                               "topicos_importados")

    if divergencias:
        print(f"\n  !! {divergencias} número(s) fora do esperado em docs/22 §1.4.")
        print("     Se uma prova nova entrou no pipeline, é isso — atualize a §1.4.")
        print("     Se ninguém mexeu, algum JSON mudou sem querer: confira o git diff")
        print("     de banco-questoes/ antes de seguir para a API.")
    else:
        print("\n  Todos os números batem com docs/22 §1.4.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Importa o banco de questões ITA · IME (docs/22 §P1)."
    )
    parser.add_argument(
        "--raiz",
        type=Path,
        default=None,
        help="Raiz do repositório (a que contém banco-questoes/). Default: deduzida do módulo.",
    )
    args = parser.parse_args()

    inicio = time.monotonic()
    cliente = criar_cliente_supabase()
    try:
        relatorio = importar(cliente, args.raiz)
    except ErroImportacao as erro:
        print(f"\n✗ {erro}", file=sys.stderr)
        sys.exit(1)

    _imprimir(relatorio)
    print(f"  ({time.monotonic() - inicio:.0f}s)")


if __name__ == "__main__":
    main()
