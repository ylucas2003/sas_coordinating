#!/usr/bin/env python3
"""Reaplica `app/banco/resolucao.py` sobre `questao_vestibular.resolucao_url`.

**Por que este script existe.** A URL da resolução é gravada pelo importador,
uma vez, e não calculada por requisição (é o que `app/banco/resolucao.py`
explica: a URL de uma prova de 2019 não muda mais). O efeito colateral é que
consertar o mapa **não conserta o banco** — as linhas já gravadas continuam com
o valor de quando entraram. Foi o que aconteceu com o deep-link da plataforma
nova: 146 questões apontando para `#gallery-1-…`, uma galeria que a página do
Ari não declara (docs/35 §2).

**Por que recalcular em vez de dar um replace de string.** Um
`UPDATE … replace('#gallery-1-', '#gallery-stage-1-')` acertaria as 146 de hoje
e erraria a 2ª fase do ITA (que vira `-stage-2-`, não `-stage-1-`) e a
plataforma antiga (onde `gallery-1` está CERTO). A fonte da verdade é
`url_da_resolucao()`: chamando ela, este script vale para qualquer correção
futura do mapa, e não só para esta.

**Idempotente.** Rodar de novo depois de aplicar não muda nada — a segunda
passada encontra zero linhas divergentes. Rodar depois de uma correção nova no
mapa reaplica só o que mudou.

**O que ele NÃO faz.** Não apaga link. Onde o mapa devolve `None` mas o banco
tem URL, ele relata e não toca: seria o caso de uma prova que saiu do mapa por
engano, e apagar em silêncio destruiria o link de uma turma inteira. Também não
encosta em resolução própria (`resolucao_origem = 'sugerida'`, o acervo
histórico da 0031), cujo texto mora em `resolucao_md` e não veio do Ari.

Uso (a partir de api/, com a stack local no ar):
    POSTGREST_URL=http://127.0.0.1:3000 ./.venv/bin/python -m scripts.recalcular_resolucao_url
    POSTGREST_URL=http://127.0.0.1:3000 ./.venv/bin/python -m scripts.recalcular_resolucao_url --aplicar

Sem `--aplicar` ele só conta — mesmo padrão de `scripts/backfill_computavel.py`:
backfill começa contando, e a flag é o consentimento de escrever.

Conexão: usa POSTGREST_URL (ou SUPABASE_*) do ambiente / .env.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.banco.resolucao import url_da_resolucao  # noqa: E402
from app.supabase_client import ClienteDados, criar_cliente_supabase  # noqa: E402

_COLUNAS = "id, vestibular, ano, fase, materia, numero, resolucao_url, resolucao_origem"

# Os quatro destinos possíveis de uma linha, na ordem em que importam ao operador.
_A_CORRIGIR = "a_corrigir"
_JA_CERTA = "ja_certa"
_SEM_MAPA = "sem_mapa"
_RESOLUCAO_PROPRIA = "resolucao_propria"


def _classificar(linha: dict[str, Any]) -> tuple[str, str | None]:
    """Diz o que fazer com uma questão, e qual URL o mapa calcula para ela."""
    calculada = url_da_resolucao(
        linha["vestibular"], linha["ano"], linha["fase"], linha["materia"], linha["numero"]
    )
    atual = linha.get("resolucao_url")
    if calculada == atual:
        return _JA_CERTA, calculada
    # Resolução escrita por nós: a coluna que vale é `resolucao_md`, e o CHECK da
    # 0031 amarra as duas. Não é lugar de link do colégio.
    if linha.get("resolucao_origem") == "sugerida":
        return _RESOLUCAO_PROPRIA, calculada
    if calculada is None:
        return _SEM_MAPA, None
    return _A_CORRIGIR, calculada


def _prova(linha: dict[str, Any]) -> str:
    return f"{linha['vestibular']} {linha['ano']} · fase {linha['fase']}"


def _relatar_por_prova(rotulo: str, linhas: list[dict[str, Any]]) -> None:
    if not linhas:
        return
    print(f"\n  {rotulo}: {len(linhas)}")
    contagem: dict[str, int] = {}
    for linha in linhas:
        contagem[_prova(linha)] = contagem.get(_prova(linha), 0) + 1
    for prova in sorted(contagem):
        print(f"    {prova:.<24} {contagem[prova]:>4}")


def _aplicar(cliente: ClienteDados, alvos: list[tuple[dict[str, Any], str]]) -> int:
    """Grava uma linha por vez. São ~150, e o PostgREST não faz UPDATE em lote
    com valor diferente por linha sem virar upsert — que exigiria repetir todas
    as colunas NOT NULL e arriscaria sobrescrever o que não é assunto daqui."""
    gravadas = 0
    for linha, nova_url in alvos:
        cliente.table("questao_vestibular").update({"resolucao_url": nova_url}).eq(
            "id", linha["id"]
        ).execute()
        gravadas += 1
    return gravadas


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument(
        "--aplicar", action="store_true", help="Grava as correções. Sem isto, só relata."
    )
    grupo.add_argument(
        "--dry-run",
        action="store_true",
        help="Só relata (é o padrão; a flag existe para deixar a intenção explícita).",
    )
    args = parser.parse_args()

    try:
        cliente = criar_cliente_supabase()
    except RuntimeError as erro:
        print(f"✗ {erro}", file=sys.stderr)
        return 1

    resposta = cliente.table("questao_vestibular").select(_COLUNAS).execute()
    linhas: list[dict[str, Any]] = resposta.data or []
    print(f"{len(linhas)} questão(ões) de vestibular no banco.")

    baldes: dict[str, list[dict[str, Any]]] = {
        _A_CORRIGIR: [], _JA_CERTA: [], _SEM_MAPA: [], _RESOLUCAO_PROPRIA: []
    }
    a_gravar: list[tuple[dict[str, Any], str]] = []
    for linha in linhas:
        destino, calculada = _classificar(linha)
        baldes[destino].append(linha)
        if destino == _A_CORRIGIR and calculada is not None:
            a_gravar.append((linha, calculada))

    print(f"  {len(baldes[_JA_CERTA])} já batem com o mapa.")
    _relatar_por_prova("divergentes (o mapa manda outra URL)", baldes[_A_CORRIGIR])
    _relatar_por_prova(
        "o banco tem link e o mapa não conhece a prova — NÃO tocadas", baldes[_SEM_MAPA]
    )
    _relatar_por_prova(
        "resolução própria (resolucao_md) — NÃO tocadas", baldes[_RESOLUCAO_PROPRIA]
    )

    if baldes[_A_CORRIGIR]:
        exemplo, nova = a_gravar[0]
        print(f"\n  exemplo — {exemplo['id']}")
        print(f"    de:    {exemplo.get('resolucao_url')}")
        print(f"    para:  {nova}")

    if not args.aplicar:
        print(f"\n  → {len(a_gravar)} linha(s) mudariam. Rode com --aplicar para gravar.")
        return 0

    gravadas = _aplicar(cliente, a_gravar)
    print(f"\n✓ {gravadas} linha(s) atualizadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
