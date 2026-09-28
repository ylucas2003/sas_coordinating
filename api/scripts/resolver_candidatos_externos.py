#!/usr/bin/env python3
"""Dá `candidato_externo` pra cada `conquista_externa` órfã — o passo de
"achar quem já é conhecido, criar quem não é" do funil de captação.

Código que não roda em requisição vive como script (mesma escolha do
`importar_captacao_externa.py`).

Uso:
    ./.venv/bin/python scripts/resolver_candidatos_externos.py

Ajuste de 28/09/2026 (docs/41 §16): o DEFAULT voltou a ser 1
`candidato_externo` por NOME, não por conquista. Entre 25/09 e 28/09 este
script criava um perfil novo pra toda conquista órfã, sempre — e o resultado
visível foi um nome como "Ryan Nojosa Barros" abrir com 14 cartões idênticos
(uma conquista cada) na tela de perfis, mesmo sem nenhum humano ter pedido
pra separar ninguém. Voltou a ser: conquista nova de um nome JÁ CONHECIDO
anexa no perfil existente (o com mais conquistas, se o nome já foi separado à
mão em mais de um — ver `_perfil_alvo`); só nome NUNCA VISTO ganha perfil
novo.

Isso NÃO reabre o bug de antes de 25/09/2026 ("Yan Lucas Freitas de Araújo"
tinha 12 `candidato_externo`, nenhum visível em lugar nenhum): aquele bug era
`candidato_externo_fusao_decisao` marcando um nome como "decidido" e
escondendo ele PRA SEMPRE, mesmo ganhando conquista nova depois. Não existe
mais tabela de decisão nenhuma — a lista geral (`v_candidato_externo_por_nome`)
sempre mostra todo nome, incondicional — e separar continua manual e
reversível a qualquer momento, arrastando em `CaptacaoPerfil.tsx`
(`routes/captacao.py::mover_conquista`).

Idempotente por construção: só processa `conquista_externa` com
`candidato_id IS NULL` — uma vez resolvida, nunca mais aparece na consulta.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase
from scripts._captacao_comum import normalizar_nome, retrato_dominante

TAMANHO_LOTE = 200

# Linha INTEIRA, não só id+candidato_id: conquista_externa tem colunas NOT
# NULL (prova_id, ano, resultado...) que um upsert parcial não preenche — o
# Postgres tenta o INSERT da linha antes de cair no conflito, e falha por
# NOT NULL mesmo quando o destino real é só um UPDATE.
COLUNAS = (
    "id, prova_id, ano, nivel_texto, serie_referencia_min, serie_referencia_max, "
    "resultado, nome_informado, escola_informada, cidade_informada, uf_informada, "
    "fonte_url, raspado_em, notas_por_materia"
)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def _perfil_alvo(perfis: list[dict]) -> dict:
    """Qual `candidato_externo` já existente recebe a conquista nova, quando
    o nome já tem 1 ou mais perfis. O caso comum é 1 perfil só (óbvio). Quando
    o nome já foi separado à mão em vários (homônimo de verdade), não há como
    adivinhar QUAL é o dono certo sem virar a heurística de confiança que a
    simplificação de 25/09/2026 baniu — o default é o perfil com mais
    conquistas (o mais "estabelecido"); se vier errado, é um arrasto pra
    corrigir, não uma perda de dado. Empate desfeito pelo mais ANTIGO — mesma
    regra de `unificar_candidatos_externos.py::_keeper`."""
    return min(perfis, key=lambda p: (-p["conquistas_total"], p["criado_em"]))


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

    por_nome: dict[str, list[dict]] = {}
    for conquista in orfas:
        chave = normalizar_nome(conquista["nome_informado"])
        por_nome.setdefault(chave, []).append(conquista)
    nomes = list(por_nome.keys())
    print(f"{len(nomes)} nomes distintos entre elas", file=sys.stderr)

    # Perfis JÁ existentes pra esses nomes — só o suficiente pra escolher o
    # alvo (`_perfil_alvo`); o retrato de quem ganha conquista é recalculado
    # depois, com a lista de conquistas completa do candidato.
    perfis_por_nome: dict[str, list[dict]] = {n: [] for n in nomes}
    for lote_nomes in _em_lotes(nomes):
        linhas = (
            cliente.table("v_candidato_externo")
            .select("id, nome_normalizado, conquistas_total, criado_em")
            .in_("nome_normalizado", lote_nomes)
            .execute()
            .data
            or []
        )
        for linha in linhas:
            perfis_por_nome[linha["nome_normalizado"]].append(linha)

    criados = 0
    anexados = 0
    alvos_tocados: dict[str, str] = {}  # candidato_id -> nome_normalizado

    for lote_nomes in _em_lotes(nomes):
        payload_novos: list[dict] = []
        nomes_dos_novos: list[str] = []  # mesma posição de payload_novos
        vinculos: list[dict] = []

        for nome in lote_nomes:
            conquistas_do_nome = por_nome[nome]
            perfis = perfis_por_nome.get(nome) or []
            if perfis:
                alvo = _perfil_alvo(perfis)
                vinculos.extend({**c, "candidato_id": alvo["id"]} for c in conquistas_do_nome)
                anexados += len(conquistas_do_nome)
                alvos_tocados[alvo["id"]] = nome
            else:
                # Nome nunca visto: nasce com o retrato dominante do PRÓPRIO
                # lote de órfãs (pode ser mais de uma, se a mesma pessoa nova
                # cruzou duas provas na mesma rodada de import).
                payload_novos.append(
                    {**retrato_dominante(conquistas_do_nome), "nome_normalizado": nome}
                )
                nomes_dos_novos.append(nome)

        if payload_novos:
            resultado = (
                cliente.table("candidato_externo")
                .insert(payload_novos, returning="representation")
                .execute()
            )
            # Ordem preservada pelo Postgres (INSERT...VALUES sem ORDER BY,
            # sem paralelismo no mesmo statement).
            for nome, novo in zip(nomes_dos_novos, resultado.data, strict=True):
                vinculos.extend({**c, "candidato_id": novo["id"]} for c in por_nome[nome])
                criados += 1

        if vinculos:
            cliente.table("conquista_externa").upsert(
                vinculos, on_conflict="id", returning="minimal"
            ).execute()

        print(
            f"  processado: {criados} perfis novos, {anexados} conquistas anexadas até aqui",
            file=sys.stderr,
        )

    # Retrato de quem recebeu conquista NOVA num perfil que já existia: busca
    # o conjunto final (velhas + novas) e recalcula com a mais recente, pro
    # cartão não ficar mostrando escola/cidade de anos atrás. Upsert (não
    # update simples) porque cada candidato leva um valor diferente no mesmo
    # lote — e por isso a linha inteira, com nome/nome_normalizado: a fase de
    # INSERT do upsert exige as colunas NOT NULL mesmo quando o destino real
    # é só um UPDATE (mesmo achado de `separar_candidatos_externos.py`).
    ids_tocados = list(alvos_tocados)
    for lote_ids in _em_lotes(ids_tocados):
        conquistas = (
            cliente.table("conquista_externa")
            .select(f"candidato_id, {COLUNAS}")
            .in_("candidato_id", lote_ids)
            .execute()
            .data
            or []
        )
        por_candidato: dict[str, list[dict]] = {i: [] for i in lote_ids}
        for c in conquistas:
            por_candidato.setdefault(c["candidato_id"], []).append(c)

        retratos = [
            {
                "id": cid,
                "nome_normalizado": alvos_tocados[cid],
                **retrato_dominante(cs),
                "atualizado_em": _agora(),
            }
            for cid, cs in por_candidato.items()
            if cs
        ]
        for sub in _em_lotes(retratos):
            cliente.table("candidato_externo").upsert(
                sub, on_conflict="id", returning="minimal"
            ).execute()

    print(
        f"resultado: {criados} candidato_externo criados (nome novo), "
        f"{anexados} conquistas anexadas a perfil já existente",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
