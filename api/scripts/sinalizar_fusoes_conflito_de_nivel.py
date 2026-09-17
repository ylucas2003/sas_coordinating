#!/usr/bin/env python3
"""Sinaliza, na fila de fusão (docs/41 §9), grupo com nível de ensino
CONFLITANTE no mesmo ano — o sinal que desqualificou "Aline Lima de
Oliveira" como fusão: nível de ensino diferente no mesmo ano é fisicamente
impossível pra uma pessoa só, e é o indício mais forte de que o grupo é
homônimo (pessoas diferentes com o mesmo nome), não fusão de verdade.

Cuidado com falso positivo: a OBF relata série/ano (6º ano ... 3ª série);
OBMEP/OBM relatam "Nível N". É a MESMA faixa em vocabulário diferente — Nível
1 = 6º-7º ano, Nível 2 = 8º-9º ano, Nível 3 = ensino médio (1ª-3ª série) — e
"9º ano" + "Nível 2" no MESMO ano não é conflito nenhum, é a mesma pessoa
vista por duas provas. Só conta como conflito duas leituras que caem em
faixas DIFERENTES depois de traduzidas pra este número (ver
`_NIVEL_NUMERICO`).

Não funde nem rejeita nada — só escreve um aviso em `observacoes`, pra
aparecer na ficha de fusão (CaptacaoFusaoDetalhe.tsx) antes de alguém
confirmar por engano o que na verdade é homônimo. Idempotente: não duplica
o aviso se já estiver lá, e nunca apaga observação que já existia.

Uso:
    ./.venv/bin/python scripts/sinalizar_fusoes_conflito_de_nivel.py --simular
    ./.venv/bin/python scripts/sinalizar_fusoes_conflito_de_nivel.py
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase

TAMANHO_LOTE = 200

# Equivalência OBF (série/ano) -> faixa do "Nível N" da OBMEP/OBM.
_NIVEL_POR_SERIE_OU_ANO = {
    "6º ano": 1,
    "7º ano": 1,
    "8º ano": 2,
    "9º ano": 2,
    "1ª série": 3,
    "2ª série": 3,
    "3ª série": 3,
}
_PADRAO_NIVEL_N = re.compile(r"^Nível\s+(\d)$")

FLAG = (
    "⚠️ Possível engano: nível de ensino conflitante no mesmo ano com outro "
    "candidato deste nome — revisar com cuidado antes de fundir (docs/41 §9)."
)


def _nivel_numerico(nivel_texto: str | None) -> int | None:
    if not nivel_texto:
        return None
    casado = _PADRAO_NIVEL_N.match(nivel_texto)
    if casado:
        return int(casado.group(1))
    return _NIVEL_POR_SERIE_OU_ANO.get(nivel_texto)


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def main() -> int:
    simular = "--simular" in sys.argv
    cliente = criar_cliente_supabase()

    nomes = [
        g["nome_normalizado"]
        for g in (
            cliente.table("v_fusao_candidata").select("nome_normalizado").execute().data or []
        )
    ]
    print(f"{len(nomes)} grupos não decididos na fila", file=sys.stderr)
    if not nomes:
        return 0

    candidatos_por_nome: dict[str, list[dict]] = {n: [] for n in nomes}
    for lote in _em_lotes(nomes):
        linhas = (
            cliente.table("candidato_externo")
            .select("id, nome_normalizado, observacoes")
            .in_("nome_normalizado", lote)
            .execute()
            .data
            or []
        )
        for linha in linhas:
            candidatos_por_nome.setdefault(linha["nome_normalizado"], []).append(linha)

    todos_ids = [c["id"] for candidatos in candidatos_por_nome.values() for c in candidatos]
    conquistas_por_candidato: dict[str, list[dict]] = {i: [] for i in todos_ids}
    for lote in _em_lotes(todos_ids):
        linhas = (
            cliente.table("conquista_externa")
            .select("candidato_id, ano, nivel_texto")
            .in_("candidato_id", lote)
            .execute()
            .data
            or []
        )
        for linha in linhas:
            conquistas_por_candidato.setdefault(linha["candidato_id"], []).append(linha)

    nomes_com_conflito: list[str] = []
    detalhe_conflito: dict[str, dict[int, set[int]]] = {}

    for nome, candidatos in candidatos_por_nome.items():
        if len(candidatos) < 2:
            continue
        por_ano: dict[int, set[int]] = defaultdict(set)
        for c in candidatos:
            for q in conquistas_por_candidato.get(c["id"], []):
                nivel = _nivel_numerico(q.get("nivel_texto"))
                if nivel is not None:
                    por_ano[q["ano"]].add(nivel)
        conflito_anos = {ano: niveis for ano, niveis in por_ano.items() if len(niveis) > 1}
        if conflito_anos:
            nomes_com_conflito.append(nome)
            detalhe_conflito[nome] = conflito_anos

    print(f"{len(nomes_com_conflito)} grupos com conflito de nível no mesmo ano:", file=sys.stderr)
    for nome in nomes_com_conflito:
        anos = ", ".join(
            f"{ano} ({'/'.join(str(n) for n in sorted(niveis))})"
            for ano, niveis in sorted(detalhe_conflito[nome].items())
        )
        print(f"  {nome}: {anos}", file=sys.stderr)

    if simular:
        print("--simular: nada escrito", file=sys.stderr)
        return 0

    atualizados = 0
    for nome in nomes_com_conflito:
        for c in candidatos_por_nome[nome]:
            atual = (c.get("observacoes") or "").strip()
            if FLAG in atual:
                continue
            novo = f"{atual}\n{FLAG}" if atual else FLAG
            cliente.table("candidato_externo").update({"observacoes": novo}).eq(
                "id", c["id"]
            ).execute()
            atualizados += 1

    print(f"concluído: {atualizados} candidato_externo sinalizados", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
