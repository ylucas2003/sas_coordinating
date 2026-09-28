#!/usr/bin/env python3
"""Cria `candidato_externo` pra cada `conquista_externa` órfã — o passo de
"nasce sozinha" do funil de captação.

Código que não roda em requisição vive como script (mesma escolha do
`importar_captacao_externa.py`).

Uso:
    ./.venv/bin/python scripts/resolver_candidatos_externos.py

⚠️ Não agrupa mais por nome+escola. Até 25/09/2026 este script juntava
conquistas da mesma pessoa (nome+escola exatos) num `candidato_externo` só —
e essa "inteligência" automática, somada a `confirmar_fusoes_alta_confianca.py`
e a `candidato_externo_fusao_decisao` (que marcava um nome como "decidido"
pra sempre), causou um bug sério: 4.395 dos 17.427 nomes "decididos" — TODOS
por script, NENHUM por um humano — ganharam conquista nova depois da decisão
e ficaram escondidos de qualquer tela (achado em produção, 25/09/2026:
"Yan Lucas Freitas de Araújo" tinha 12 `candidato_externo`, nenhum visível
em lugar nenhum). A correção foi tirar a inteligência inteira: toda
conquista nasce com o PRÓPRIO `candidato_externo`, e só um humano junta
duas, arrastando em `CaptacaoPerfil.tsx`
(`routes/captacao.py::mover_conquista`). A lista geral
(`GET /captacao/candidatos`, `v_candidato_externo_por_nome`) já junta por
nome sozinha, incondicional, sem depender de `candidato_id` nenhum — não
precisa mais que ESTE script adivinhe quem é quem.

Idempotente por construção: só processa `conquista_externa` com
`candidato_id IS NULL` — uma vez resolvida, nunca mais aparece na consulta.
Bem mais barato que a versão antiga (que relia a tabela inteira a cada
rodada, de propósito, pra grudar conquista nova em candidato já existente —
não precisa mais, porque não existe mais "grudar", só "nascer sozinho").
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase
from scripts._captacao_comum import retrato_da_conquista

TAMANHO_LOTE = 200

# Linha INTEIRA, não só id+candidato_id: conquista_externa tem colunas NOT
# NULL (prova_id, ano, resultado...) que um upsert parcial não preenche — o
# Postgres tenta o INSERT da linha antes de cair no conflito, e falha por
# NOT NULL mesmo quando o destino real é só um UPDATE. Reenviar a linha
# completa (já em mãos, veio do SELECT abaixo) resolve isso em poucas
# dezenas de chamadas em lote — mesmo motivo da versão antiga deste script.
COLUNAS = (
    "id, prova_id, ano, nivel_texto, serie_referencia_min, serie_referencia_max, "
    "resultado, nome_informado, escola_informada, cidade_informada, uf_informada, "
    "fonte_url, raspado_em, notas_por_materia"
)


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def main() -> int:
    cliente = criar_cliente_supabase()

    orfas = (
        cliente.table("conquista_externa")
        .select(COLUNAS)
        .is_("candidato_id", "null")
        .execute()
        .data
        or []
    )
    print(f"{len(orfas)} conquista_externa sem candidato_externo", file=sys.stderr)
    if not orfas:
        return 0

    criados = 0
    for lote in _em_lotes(orfas):
        payload = [retrato_da_conquista(c) for c in lote]
        resultado = (
            cliente.table("candidato_externo")
            .insert(payload, returning="representation")
            .execute()
        )
        # Pareia por POSIÇÃO (`zip`), nunca por nome_normalizado de volta:
        # `INSERT ... VALUES (...), (...) RETURNING` do Postgres preserva a
        # ordem da lista (sem ORDER BY, sem paralelismo no mesmo statement) —
        # e dois órfãos com o MESMO nome (homônimos raspados no mesmo lote)
        # não são a mesma pessoa só por coincidência de string.
        vinculos = [
            {**c, "candidato_id": novo["id"]}
            for c, novo in zip(lote, resultado.data, strict=True)
        ]
        cliente.table("conquista_externa").upsert(
            vinculos, on_conflict="id", returning="minimal"
        ).execute()
        criados += len(lote)
        print(f"  candidatos criados: {criados}/{len(orfas)}", file=sys.stderr)

    print(f"resultado: {criados} candidato_externo criados, 1 por conquista", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
