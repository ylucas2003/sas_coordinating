#!/usr/bin/env python3
"""Cruza `conquista_externa` em `candidato_externo` — o passo de "resolução de
identidade" do funil de captação.

Código que não roda em requisição vive como script (mesma escolha do
`importar_captacao_externa.py`).

Uso:
    ./.venv/bin/python scripts/resolver_candidatos_externos.py

Chave de match usada (ALTA confiança, de propósito): nome normalizado
(maiúsculas, sem acento) + escola informada, exatos. Dá falso NEGATIVO (a
mesma pessoa que trocou de escola entre duas conquistas vira dois candidatos)
em vez de falso POSITIVO (duas pessoas diferentes viradas uma só) — errar pra
esse lado é mais barato: perde um cruzamento, não inventa um. Não tem fila de
revisão ainda porque não tem UI ainda; quando tiver, um segundo passo (nome +
cidade/UF, confiança mais baixa) pode alimentar essa fila em vez de mesclar
direto.

Idempotente: relê TODA `conquista_externa` (resolvida ou não) a cada rodada,
não só o que está com candidato_id nulo — é assim que uma conquista nova de
uma prova nova gruda no candidato_externo que já existe de uma prova antiga,
em vez de criar uma pessoa duplicada.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase

TAMANHO_LOTE = 200

COLUNAS = (
    "id,prova_id,candidato_id,ano,nivel_texto,serie_referencia_min,serie_referencia_max,"
    "resultado,nome_informado,escola_informada,cidade_informada,uf_informada,fonte_url"
)


def normalizar_nome(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


def chave_do_grupo(linha: dict[str, Any]) -> tuple[str, str]:
    escola = (linha.get("escola_informada") or "").strip().upper()
    if not escola:
        # Sem escola não dá pra confiar em match por nome sozinho (homônimo é
        # comum demais no Brasil) — cada linha sem escola vira grupo de 1.
        return (normalizar_nome(linha["nome_informado"]), f"__sem_escola__{linha['id']}")
    return (normalizar_nome(linha["nome_informado"]), escola)


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def main() -> int:
    cliente = criar_cliente_supabase()

    # Sem paginação de propósito (mesma régua da 0022/banco de questões pra
    # outras tabelas grandes): PGRST_DB_MAX_ROWS fica sem valor, então um
    # select sem .range() já devolve tudo.
    todas = cliente.table("conquista_externa").select(COLUNAS).execute().data
    print(f"{len(todas)} conquista_externa no total", file=sys.stderr)

    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for linha in todas:
        grupos[chave_do_grupo(linha)].append(linha)

    print(f"{len(grupos)} pessoas distintas (nome+escola)", file=sys.stderr)

    por_id = {linha["id"]: linha for linha in todas}

    a_criar: list[dict] = []  # grupos sem candidato_id nenhum ainda
    a_atualizar_candidato: list[dict] = []  # candidato_externo existente que pode ter ficado desatualizado
    a_vincular: dict[str, str] = {}  # conquista_id -> candidato_id, só pra quem precisa mudar

    for chave, linhas in grupos.items():
        mais_recente = max(linhas, key=lambda l: l["ano"])
        candidato_id_existente = next((l["candidato_id"] for l in linhas if l["candidato_id"]), None)

        dados_candidato = {
            "nome": mais_recente["nome_informado"],
            "nome_normalizado": chave[0],
            "escola": mais_recente.get("escola_informada"),
            "cidade": mais_recente.get("cidade_informada"),
            "uf": mais_recente.get("uf_informada"),
            "serie_referencia_min": mais_recente.get("serie_referencia_min"),
            "serie_referencia_max": mais_recente.get("serie_referencia_max"),
            "ano_referencia_serie": mais_recente["ano"],
        }

        if candidato_id_existente is None:
            a_criar.append({"_chave": chave, "_linhas": linhas, **dados_candidato})
        else:
            a_atualizar_candidato.append({"id": candidato_id_existente, **dados_candidato})
            for l in linhas:
                if l["candidato_id"] != candidato_id_existente:
                    a_vincular[l["id"]] = candidato_id_existente

    # ── Cria candidato_externo novo pra cada grupo sem match anterior ──
    #
    # ⚠️ O par item↔linha-criada é por POSIÇÃO (`zip`), nunca por (nome, escola)
    # de volta. Foi um dicionário chaveado por (nome, escola) até a OBM expor o
    # bug: SEM escola (toda conquista da OBM), duas pessoas DIFERENTES com o
    # mesmo nome no mesmo lote de 200 colidiam na mesma chave, e as duas
    # ficavam apontando pro MESMO candidato — exatamente o falso POSITIVO que
    # o §4.1 do docs/41 diz ser o erro caro desta feature. `INSERT ... VALUES
    # (...), (...) RETURNING` do Postgres preserva a ordem da lista de valores
    # (sem `ORDER BY`, sem paralelismo dentro do mesmo statement) — é a mesma
    # garantia que bibliotecas de ORM usam pra mapear objeto→linha inserida, e
    # aqui substitui a chave ambígua sem custo nenhum.
    criados = 0
    for lote in _em_lotes(a_criar):
        payload = [
            {k: v for k, v in item.items() if not k.startswith("_")} for item in lote
        ]
        resultado = (
            cliente.table("candidato_externo")
            .insert(payload, returning="representation")
            .execute()
        )
        for item, linha_criada in zip(lote, resultado.data, strict=True):
            for linha in item["_linhas"]:
                a_vincular[linha["id"]] = linha_criada["id"]
        criados += len(lote)
        print(f"  candidatos criados: {criados}/{len(a_criar)}", file=sys.stderr)

    # ── Atualiza o retrato (escola/série/ano de referência) de candidatos já existentes ──
    for lote in _em_lotes(a_atualizar_candidato):
        cliente.table("candidato_externo").upsert(
            lote, on_conflict="id", returning="minimal"
        ).execute()

    # ── Aponta cada conquista_externa pro candidato_id resolvido ──
    # Upsert com a linha INTEIRA (não só id+candidato_id): conquista_externa
    # tem colunas NOT NULL (prova_id, ano, resultado...) que um upsert parcial
    # não preenche — Postgres tenta o INSERT da linha antes de cair no
    # conflito, e falha por NOT NULL mesmo quando o destino é só um UPDATE.
    # Reenviar a linha completa (já em mãos, veio do SELECT lá em cima) deixa
    # isso em poucas dezenas de chamadas em lote, em vez de uma por linha.
    itens_vinculo = [{**por_id[cid_conquista], "candidato_id": cid_candidato} for cid_conquista, cid_candidato in a_vincular.items()]
    for lote in _em_lotes(itens_vinculo):
        cliente.table("conquista_externa").upsert(
            lote, on_conflict="id", returning="minimal"
        ).execute()

    print(
        f"resultado: {criados} candidatos novos, {len(a_atualizar_candidato)} candidatos já existiam, "
        f"{len(a_vincular)} conquista_externa vinculadas",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
