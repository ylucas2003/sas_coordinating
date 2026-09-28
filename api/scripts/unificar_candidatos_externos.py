#!/usr/bin/env python3
"""Reagrupa `candidato_externo` fragmentado de volta pra 1 por NOME — passo
ÚNICO de transição pro ajuste de 28/09/2026 (docs/41 §16): o default deixou
de ser 1 `candidato_externo` por conquista (simplificação de 25/09/2026) e
voltou a ser 1 por nome. `resolver_candidatos_externos.py` já foi ajustado
pra daqui pra frente anexar conquista nova ao perfil existente — este script
é só pra desfazer, de uma vez, a fragmentação que os ~3 dias de "1:1 por
conquista" já causaram em produção (ex.: um nome com 14 perfis, um por
resultado, nenhum separado por um humano).

Por que unificar em vez de deixar quieto: a lista geral
(`v_candidato_externo_por_nome`) já junta por nome pra EXIBIÇÃO, mas por
baixo os `candidato_externo` continuavam fragmentados — e é `CaptacaoPerfil.tsx`
(a ficha de um nome) que mostra a fragmentação crua, card por card. Um
coordenador abrindo qualquer nome com 2+ conquistas via `CaptacaoPerfil.tsx`
depois de 25/09/2026 encontrava vários perfis com uma conquista cada, todos
criados pelo resolver — nada disso foi separação humana de homônimo de
verdade, então juntar de volta não perde nenhuma decisão real de ninguém.

Qual perfil FICA (o `id` que sobrevive, pros outros que apontam pra ele em
qualquer lugar futuro continuarem válidos): o com MAIS conquistas hoje —
mesmo critério de `resolver_candidatos_externos.py::_perfil_alvo`; empate
por `criado_em` mais antigo (o perfil "original"). O retrato final é o
`retrato_dominante` (conquista mais recente) do GRUPO JUNTO, não só do
perfil que ficou.

Quando mais de um perfil do grupo já tinha funil preenchido
(`status_captacao != 'novo'` ou `observacoes` não vazia) — sinal de que um
humano pode ter mexido em mais de um perfil do mesmo nome —, o script
PRESERVA o funil do perfil escolhido como keeper e AVISA no stderr sobre os
descartados, pra revisão. Não há como fundir dois textos de observação
diferentes automaticamente sem inventar conteúdo.

Idempotente por construção, sem tabela de checkpoint: a entrada é sempre
`v_candidato_externo_por_nome` com `perfis_no_grupo > 1` — depois de
unificado, um nome tem 1 perfil e some da própria consulta. Rodar de novo
depois de uma queda nunca reprocessa um nome já unificado.

⚠️ A view `v_candidato_externo_por_nome` é MATERIALIZADA (migration 0063) —
este script escreve direto no banco via `criar_cliente_supabase()`, fora de
qualquer rota, então ela NÃO acompanha sozinha. No fim do modo real, chama o
RPC `atualizar_v_candidato_externo_por_nome` — sem isso a lista geral ficaria
mostrando `perfis_no_grupo` velho até a próxima escrita por rota.

Uso:
    ./.venv/bin/python scripts/unificar_candidatos_externos.py --simular
    ./.venv/bin/python scripts/unificar_candidatos_externos.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase
from scripts._captacao_comum import retrato_dominante

TAMANHO_LOTE = 200
ATOR_ID = "script:unificar_candidatos_externos"

_COLUNAS_CANDIDATO = "id, nome_normalizado, status_captacao, observacoes, criado_em, conquistas_total"
_COLUNAS_CONQUISTA = (
    "id, candidato_id, prova_id, ano, nivel_texto, serie_referencia_min, "
    "serie_referencia_max, resultado, nome_informado, escola_informada, "
    "cidade_informada, uf_informada, fonte_url, raspado_em, notas_por_materia"
)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _em_lotes(itens: list, tamanho: int = TAMANHO_LOTE):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


def _funil_preenchido(perfil: dict) -> bool:
    return bool(perfil["status_captacao"] not in (None, "novo") or perfil["observacoes"])


def _keeper(perfis: list[dict]) -> dict:
    # Mais conquistas primeiro; empate desfeito pelo mais ANTIGO (`min` com
    # `conquistas_total` negado — `criado_em` sozinho já ordena crescente).
    return min(perfis, key=lambda p: (-p["conquistas_total"], p["criado_em"]))


def main() -> int:
    simular = "--simular" in sys.argv
    cliente = criar_cliente_supabase()

    nomes_fragmentados = (
        cliente.table("v_candidato_externo_por_nome")
        .select("nome_normalizado, perfis_no_grupo")
        .gt("perfis_no_grupo", 1)
        .execute()
        .data
        or []
    )
    print(f"{len(nomes_fragmentados)} nomes com 2+ perfis pra unificar", file=sys.stderr)
    if not nomes_fragmentados:
        return 0

    processados = 0
    total_removidos = 0
    total_funil_perdido = 0

    for lote_nomes in _em_lotes([g["nome_normalizado"] for g in nomes_fragmentados]):
        perfis = (
            cliente.table("v_candidato_externo")
            .select(_COLUNAS_CANDIDATO)
            .in_("nome_normalizado", lote_nomes)
            .execute()
            .data
            or []
        )
        perfis_por_nome: dict[str, list[dict]] = {}
        for p in perfis:
            perfis_por_nome.setdefault(p["nome_normalizado"], []).append(p)

        keepers_payload: list[dict] = []  # id + retrato final, upsert no fim
        removidos_ids: list[str] = []
        vinculos: list[dict] = []  # conquista_externa que muda de dono
        eventos: list[dict] = []

        for nome, grupo in perfis_por_nome.items():
            if len(grupo) < 2:
                continue  # já foi unificado numa rodada anterior interrompida

            keeper = _keeper(grupo)
            descartados = [p for p in grupo if p["id"] != keeper["id"]]

            funis_perdidos = [p for p in descartados if _funil_preenchido(p)]
            if funis_perdidos:
                total_funil_perdido += len(funis_perdidos)
                print(
                    f"  funil descartado em {nome}: perfil {keeper['id']} venceu "
                    f"({keeper['conquistas_total']} conquistas); "
                    f"{len(funis_perdidos)} outro(s) tinham status/observação e foram perdidos "
                    f"(ids: {[p['id'] for p in funis_perdidos]})",
                    file=sys.stderr,
                )

            ids_do_grupo = [p["id"] for p in grupo]
            conquistas_do_grupo = (
                cliente.table("conquista_externa")
                .select(_COLUNAS_CONQUISTA)
                .in_("candidato_id", ids_do_grupo)
                .execute()
                .data
                or []
            )
            vinculos.extend(
                {**c, "candidato_id": keeper["id"]}
                for c in conquistas_do_grupo
                if c["candidato_id"] != keeper["id"]
            )
            keepers_payload.append(
                {
                    "id": keeper["id"],
                    "nome_normalizado": nome,
                    **retrato_dominante(conquistas_do_grupo),
                    "atualizado_em": _agora(),
                }
            )
            removidos_ids.extend(p["id"] for p in descartados)

            eventos.append(
                {
                    "acao": "captacao_perfil_unificado",
                    "canal": "captacao",
                    "ator_tipo": "sistema",
                    "ator_id": ATOR_ID,
                    "recurso": f"candidato_externo/{keeper['id']}",
                    "ip": None,
                    "detalhe": {
                        "nome_normalizado": nome,
                        "candidato_mantido": keeper["id"],
                        "candidatos_removidos": [p["id"] for p in descartados],
                        "funil_perdido": [p["id"] for p in funis_perdidos],
                    },
                }
            )
            processados += 1

        total_removidos += len(removidos_ids)
        if simular:
            continue

        # UPDATE das conquistas pro keeper, DEPOIS o keeper com o retrato
        # final, DEPOIS apaga quem ficou vazio — nessa ordem, uma queda no
        # meio nunca deixa conquista apontando pra um candidato já apagado.
        for sub in _em_lotes(vinculos):
            cliente.table("conquista_externa").upsert(
                sub, on_conflict="id", returning="minimal"
            ).execute()
        for sub in _em_lotes(keepers_payload):
            cliente.table("candidato_externo").upsert(
                sub, on_conflict="id", returning="minimal"
            ).execute()
        for sub in _em_lotes(removidos_ids):
            cliente.table("candidato_externo").delete().in_("id", sub).execute()
        for sub in _em_lotes(eventos):
            cliente.table("evento_auditoria").insert(sub).execute()

        print(
            f"  processado: {processados}/{len(nomes_fragmentados)} nomes, "
            f"{total_removidos} perfis removidos até aqui",
            file=sys.stderr,
        )

    if simular:
        print(
            f"--simular: {processados} nomes seriam unificados, {total_removidos} perfis "
            f"removidos, {total_funil_perdido} com funil descartado (lista acima) — nada escrito",
            file=sys.stderr,
        )
        return 0

    cliente.rpc("atualizar_v_candidato_externo_por_nome", {}).execute()
    print(
        f"concluído: {processados} nomes unificados, {total_removidos} perfis removidos, "
        f"{total_funil_perdido} com funil descartado, view por nome atualizada",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
