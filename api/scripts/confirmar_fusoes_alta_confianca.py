#!/usr/bin/env python3
"""Confirma em lote os grupos de ALTA confiança da fila de fusão (docs/41 §9).

A fila (`v_fusao_candidata`) é candidato_externo com o mesmo nome, sem escola
pra cruzar automático (`resolver_candidatos_externos.py::chave_do_grupo`).
Quando todo mundo do grupo cai na MESMA UF, o risco de homônimo é baixo — foi
essa régua que separou "Aline Lima de Oliveira" (duas alunas reais, UFs
diferentes: Cruzeiro do Sul/AC vs Vertentes/PE, níveis 1 e 3 — corretamente
fora deste lote) do resto da fila, que é candidato genuíno a fusão.

Roda a MESMA lógica de `POST /captacao/fusoes/confirmar`
(`routes/captacao.py::confirmar_fusao`) em lote, pra não exigir 1 clique por
grupo na tela — o volume que a coordenação NÃO precisa decidir à mão. Os
grupos de UF divergente continuam de fora: só a tela
(`/administracao/captacao/fusoes`) resolve esses, com decisão humana.

Idempotente: `v_fusao_candidata` já exclui nome com decisão registrada, então
rodar de novo não refaz nada.

Uso:
    ./.venv/bin/python scripts/confirmar_fusoes_alta_confianca.py --simular  # só mostra o que faria
    ./.venv/bin/python scripts/confirmar_fusoes_alta_confianca.py            # aplica de verdade
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase

TAMANHO_LOTE = 200
ATOR_ID = "script:confirmar_fusoes_alta_confianca"

_COLUNAS_CONQUISTA = (
    "id, candidato_id, prova_id, ano, nivel_texto, serie_referencia_min, "
    "serie_referencia_max, resultado, nome_informado, escola_informada, "
    "cidade_informada, uf_informada, fonte_url, raspado_em"
)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def _serie_dominante(conquistas: list[dict]) -> dict:
    """Mesma regra de `routes/captacao.py::_serie_dominante` — duplicada de
    propósito, como o resto do vocabulário compartilhado entre rota e script
    neste pipeline (docs/41 §4)."""
    mais_recente = max(conquistas, key=lambda c: c["ano"])
    return {
        "nome": mais_recente["nome_informado"],
        "escola": mais_recente.get("escola_informada"),
        "cidade": mais_recente.get("cidade_informada"),
        "uf": mais_recente.get("uf_informada"),
        "serie_referencia_min": mais_recente.get("serie_referencia_min"),
        "serie_referencia_max": mais_recente.get("serie_referencia_max"),
        "ano_referencia_serie": mais_recente["ano"],
    }


def main() -> int:
    simular = "--simular" in sys.argv
    cliente = criar_cliente_supabase()

    grupos = (
        cliente.table("v_fusao_candidata")
        .select("nome_normalizado")
        .lte("ufs_distintas", 1)
        .execute()
        .data
        or []
    )
    nomes = [g["nome_normalizado"] for g in grupos]
    print(f"{len(nomes)} grupos de UF única na fila", file=sys.stderr)
    if not nomes:
        return 0

    candidatos_por_nome: dict[str, list[dict]] = {n: [] for n in nomes}
    for lote in _em_lotes(nomes):
        linhas = (
            cliente.table("candidato_externo")
            .select("id, nome_normalizado, criado_em")
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
            .select(_COLUNAS_CONQUISTA)
            .in_("candidato_id", lote)
            .execute()
            .data
            or []
        )
        for linha in linhas:
            conquistas_por_candidato.setdefault(linha["candidato_id"], []).append(linha)

    itens_vinculo: list[dict] = []  # conquista_externa com o candidato_id do sobrevivente
    retratos: list[dict] = []  # candidato_externo sobrevivente, retrato atualizado
    ids_a_apagar: list[str] = []
    decisoes: list[dict] = []
    eventos_auditoria: list[dict] = []
    processados = 0
    sem_conquista = 0

    for nome, candidatos in candidatos_por_nome.items():
        if len(candidatos) < 2:
            continue  # já resolvido por outra via desde a leitura da view

        ids = [c["id"] for c in candidatos]
        conquistas = [q for i in ids for q in conquistas_por_candidato.get(i, [])]
        if not conquistas:
            sem_conquista += 1
            continue

        contagem: dict[str, int] = {i: 0 for i in ids}
        for q in conquistas:
            contagem[q["candidato_id"]] = contagem.get(q["candidato_id"], 0) + 1
        criado_em_por_id = {c["id"]: c["criado_em"] for c in candidatos}
        maior_contagem = max(contagem.values())
        top = [i for i in ids if contagem[i] == maior_contagem]
        sobrevivente_id = min(top, key=lambda i: criado_em_por_id[i])
        outros_ids = [i for i in ids if i != sobrevivente_id]

        retrato = _serie_dominante(conquistas)
        # `nome_normalizado` é NOT NULL sem default: o upsert tenta um INSERT
        # antes do conflito (mesma armadilha documentada em
        # resolver_candidatos_externos.py), e sem esta chave falha com 23502
        # mesmo o destino sendo sempre um UPDATE (o id já existe).
        retratos.append(
            {"id": sobrevivente_id, "nome_normalizado": nome, **retrato, "atualizado_em": _agora()}
        )

        outros = set(outros_ids)
        for q in conquistas:
            if q["candidato_id"] in outros:
                itens_vinculo.append({**q, "candidato_id": sobrevivente_id})

        ids_a_apagar.extend(outros_ids)
        decisoes.append(
            {
                "nome_normalizado": nome,
                "status": "confirmada",
                "decidido_por": ATOR_ID,
                "decidido_em": _agora(),
            }
        )
        eventos_auditoria.append(
            {
                "acao": "captacao_fusao_confirmada",
                "canal": "captacao",
                "ator_tipo": "sistema",
                "ator_id": ATOR_ID,
                "recurso": f"candidato_externo/{sobrevivente_id}",
                "ip": None,
                "detalhe": {
                    "nome_normalizado": nome,
                    "sobrevivente": sobrevivente_id,
                    "fundidos": outros_ids,
                    "lote": "uf_unica",
                },
                "request_id": None,
            }
        )
        processados += 1

    print(
        f"{processados} grupos a fundir, {len(ids_a_apagar)} candidatos apagados, "
        f"{len(itens_vinculo)} conquistas repassadas, {sem_conquista} pulados (sem conquista)",
        file=sys.stderr,
    )

    if simular:
        print("--simular: nada escrito", file=sys.stderr)
        return 0

    # Ordem importa: repassar conquista ANTES de apagar candidato — senão a
    # FK de conquista_externa.candidato_id fica órfã ou cascata apaga o que
    # devia migrar pro sobrevivente (mesma ordem de routes/captacao.py).
    for lote in _em_lotes(itens_vinculo):
        cliente.table("conquista_externa").upsert(
            lote, on_conflict="id", returning="minimal"
        ).execute()

    for lote in _em_lotes(retratos):
        cliente.table("candidato_externo").upsert(
            lote, on_conflict="id", returning="minimal"
        ).execute()

    for lote in _em_lotes(ids_a_apagar):
        cliente.table("candidato_externo").delete().in_("id", lote).execute()

    for lote in _em_lotes(decisoes):
        cliente.table("candidato_externo_fusao_decisao").upsert(
            lote, on_conflict="nome_normalizado", returning="minimal"
        ).execute()

    for lote in _em_lotes(eventos_auditoria):
        cliente.table("evento_auditoria").insert(lote).execute()

    print(f"concluído: {processados} grupos fundidos", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
