#!/usr/bin/env python3
"""Desfaz TODO agrupamento automático de `candidato_externo` — passo ÚNICO de
transição pra simplificação radical da captação externa (docs/41, 25/09/2026):
daqui pra frente, agrupar é só manual (arrastar em `CaptacaoPerfil.tsx`);
antes de ligar a view nova (migration 0063), todo `candidato_externo` com 2+
conquistas precisa voltar a ser 1 candidato por conquista.

Por que separar em vez de só desligar o agrupamento futuro: 4.395 dos 17.427
nomes "decididos" por `confirmar_fusoes_alta_confianca.py` (script
automático, nunca revisado por humano) já tinham ganhado conquista nova
DEPOIS da decisão e ficavam escondidos pra sempre atrás de
`candidato_externo_fusao_decisao`. Separar tudo de volta é a única forma de
zerar esse buraco sem tentar adivinhar quais dos candidato_externo de hoje
foram agrupados corretamente e quais não.

Qual conquista FICA com o `candidato_id` original (e com o funil já
preenchido — `status_captacao`/`observacoes`): a de ANO mais recente, mesma
convenção de `_serie_dominante` em `routes/captacao.py` — quem decidiu
"contatado" num perfil que hoje é 3 conquistas fundidas provavelmente falou
com a pessoa depois da conquista mais nova. As outras N-1 conquistas ganham
`candidato_externo` NOVO, status 'novo', observações vazias — o script
avisa no stderr toda vez que isso descarta funil preenchido, pra revisão
humana.

Também limpa o aviso morto de `scripts/sinalizar_fusoes_conflito_de_nivel.py`
(apagado nesta mesma simplificação) de `candidato_externo.observacoes` — ele
cita "fundir" e uma seção do doc que não existe mais, e ficaria como lixo
confuso no ÚNICO lugar onde a coordenação escreve anotação de verdade daqui
pra frente.

Idempotente por CONSTRUÇÃO, sem tabela de checkpoint: a entrada é sempre
`candidato_externo` com `conquistas_total > 1` — depois de separado, um
grupo tem 1 conquista e some da própria consulta. Rodar de novo depois de
uma queda nunca reprocessa um grupo já separado; na pior hipótese deixa um
`candidato_externo` órfão (0 conquistas) do lote interrompido, inofensivo
(mesma guarda de `DELETE /captacao/candidatos/{id}`).

Uso:
    ./.venv/bin/python scripts/separar_candidatos_externos.py --simular
    ./.venv/bin/python scripts/separar_candidatos_externos.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.supabase_client import criar_cliente_supabase
from scripts._captacao_comum import retrato_da_conquista

TAMANHO_LOTE = 200
ATOR_ID = "script:separar_candidatos_externos"

# Texto EXATO de scripts/sinalizar_fusoes_conflito_de_nivel.py::FLAG —
# copiado aqui antes de apagar o arquivo, porque a limpeza precisa da string
# literal.
FLAG_CONFLITO_NIVEL = (
    "⚠️ Possível engano: nível de ensino conflitante no mesmo ano com outro "
    "candidato deste nome — revisar com cuidado antes de fundir (docs/41 §9)."
)

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


def _observacoes_sem_flag(observacoes: str | None) -> str | None:
    limpo = (
        (observacoes or "")
        .replace(f"\n{FLAG_CONFLITO_NIVEL}", "")
        .replace(FLAG_CONFLITO_NIVEL, "")
        .strip()
    )
    return limpo or None


def _limpar_flag_de_conflito(cliente, simular: bool) -> dict[str, str | None]:
    """Devolve {id: observacoes_depois_de_limpar} de todo candidato afetado —
    usado tanto pra escrever de verdade quanto pra `--simular` calcular
    `funil_preenchido` corretamente (sem isso, o texto do alerta antigo,
    ainda não limpo em modo simulação, conta como "anotação de verdade" por
    engano — achado rodando `--simular` localmente antes de ir pra produção)."""
    # `nome`/`nome_normalizado` vêm junto mesmo não mudando: o upsert do
    # PostgREST é um INSERT ... ON CONFLICT — a fase de INSERT exige as
    # colunas NOT NULL sem default (nome/nome_normalizado) mesmo quando o
    # destino real é só um UPDATE. Mesmo motivo do comentário de
    # `resolver_candidatos_externos.py::COLUNAS` — achado rodando de
    # verdade (28/09/2026): `upsert({"id", "observacoes"})` sozinho quebra
    # com "null value in column nome violates not-null constraint".
    afetados = (
        cliente.table("candidato_externo")
        .select("id, nome, nome_normalizado, observacoes")
        .ilike("observacoes", f"%{FLAG_CONFLITO_NIVEL}%")
        .execute()
        .data
        or []
    )
    print(f"{len(afetados)} candidato_externo com o alerta antigo em observacoes", file=sys.stderr)
    limpos = {c["id"]: _observacoes_sem_flag(c["observacoes"]) for c in afetados}
    if simular or not afetados:
        return limpos

    patches = [
        {
            "id": c["id"],
            "nome": c["nome"],
            "nome_normalizado": c["nome_normalizado"],
            "observacoes": limpos[c["id"]],
            "atualizado_em": _agora(),
        }
        for c in afetados
    ]
    for lote in _em_lotes(patches):
        cliente.table("candidato_externo").upsert(lote, on_conflict="id", returning="minimal").execute()
    return limpos


def main() -> int:
    simular = "--simular" in sys.argv
    cliente = criar_cliente_supabase()

    limpos = _limpar_flag_de_conflito(cliente, simular)

    grupos = (
        cliente.table("v_candidato_externo")
        .select("id, nome_normalizado, status_captacao, observacoes, criado_em, conquistas_total")
        .gt("conquistas_total", 1)
        .execute()
        .data
        or []
    )
    print(f"{len(grupos)} candidato_externo com 2+ conquistas pra separar", file=sys.stderr)
    if not grupos:
        print(f"nada a fazer (observacoes limpas: {len(limpos)})", file=sys.stderr)
        return 0

    total_novos = 0
    total_funil_preservado = 0
    processados = 0

    for lote_grupos in _em_lotes(grupos):
        ids_lote = [g["id"] for g in lote_grupos]

        conquistas = (
            cliente.table("conquista_externa")
            .select(_COLUNAS_CONQUISTA)
            .in_("candidato_id", ids_lote)
            .execute()
            .data
            or []
        )
        conquistas_por_candidato: dict[str, list[dict]] = {i: [] for i in ids_lote}
        for c in conquistas:
            conquistas_por_candidato.setdefault(c["candidato_id"], []).append(c)

        novos_payload: list[dict] = []
        novas_conquistas: list[dict] = []  # linha inteira da conquista, na MESMA posição do payload correspondente
        retratos_originais: list[dict] = []
        eventos: list[dict] = []

        for g in lote_grupos:
            cid = g["id"]
            qs = conquistas_por_candidato.get(cid, [])
            if len(qs) < 2:
                continue  # já foi separado numa rodada anterior interrompida

            keeper = max(qs, key=lambda q: (q["ano"], q.get("raspado_em") or "", q["id"]))
            outras = [q for q in qs if q["id"] != keeper["id"]]

            # `limpos` já reflete o texto SEM o alerta morto de conflito de
            # nível — sem isso, `--simular` (que não escreve) contaria esse
            # aviso automático como "anotação de verdade" da coordenação.
            observacoes_efetivas = limpos.get(cid, g["observacoes"])
            funil_preenchido = bool(g["status_captacao"] not in (None, "novo") or observacoes_efetivas)
            if funil_preenchido:
                total_funil_preservado += 1
                print(
                    f"  funil preservado em {cid} ({g['nome_normalizado']}): "
                    f"status={g['status_captacao']!r} — ficou com a conquista {keeper['id']} "
                    f"(ano {keeper['ano']}); as outras {len(outras)} viram perfil novo, status 'novo'",
                    file=sys.stderr,
                )

            retratos_originais.append(
                {"id": cid, **retrato_da_conquista(keeper), "atualizado_em": _agora()}
            )
            for q in outras:
                novos_payload.append(
                    {
                        **retrato_da_conquista(q),
                        "status_captacao": "novo",
                        "criado_em": _agora(),
                        "atualizado_em": _agora(),
                    }
                )
                novas_conquistas.append(q)

            eventos.append(
                {
                    "acao": "captacao_perfil_separado",
                    "canal": "captacao",
                    "ator_tipo": "sistema",
                    "ator_id": ATOR_ID,
                    "recurso": f"candidato_externo/{cid}",
                    "ip": None,
                    "detalhe": {
                        "nome_normalizado": g["nome_normalizado"],
                        "conquista_mantida": keeper["id"],
                        "conquistas_separadas": [q["id"] for q in outras],
                        "funil_preservado": funil_preenchido,
                    },
                }
            )
            processados += 1

        total_novos += len(novos_payload)
        if simular:
            continue

        # INSERT dos candidato_externo novos + UPDATE das conquistas
        # correspondentes, um logo depois do outro — encolhe a janela de
        # queda que deixaria conquista_externa apontando pra um candidato
        # que ainda não existe.
        novos_ids: list[str] = []
        for sub in _em_lotes(novos_payload):
            resultado = cliente.table("candidato_externo").insert(sub, returning="representation").execute()
            # Ordem preservada pelo Postgres (INSERT...VALUES sem ORDER BY,
            # sem paralelismo no mesmo statement) — mesma garantia que
            # resolver_candidatos_externos.py já usa pra este pareamento.
            novos_ids.extend(row["id"] for row in resultado.data)

        vinculos = [
            {**conquista, "candidato_id": novo_id}
            for conquista, novo_id in zip(novas_conquistas, novos_ids, strict=True)
        ]
        for sub in _em_lotes(vinculos):
            cliente.table("conquista_externa").upsert(sub, on_conflict="id", returning="minimal").execute()
        for sub in _em_lotes(retratos_originais):
            cliente.table("candidato_externo").upsert(sub, on_conflict="id", returning="minimal").execute()
        for sub in _em_lotes(eventos):
            cliente.table("evento_auditoria").insert(sub).execute()

        print(
            f"  processado: {processados}/{len(grupos)} grupos, {total_novos} perfis novos até aqui",
            file=sys.stderr,
        )

    if simular:
        print(
            f"--simular: {processados} grupos seriam separados, {total_novos} candidato_externo novos, "
            f"{total_funil_preservado} com funil preenchido (lista acima) — nada escrito",
            file=sys.stderr,
        )
        return 0

    orfaos = (
        cliente.table("v_candidato_externo").select("id", count="exact").eq("conquistas_total", 0).execute()
    )
    print(
        f"concluído: {processados} grupos separados, {total_novos} candidato_externo novos, "
        f"{total_funil_preservado} com funil preservado, {orfaos.count or 0} perfis com 0 conquista "
        f"(revisar antes de apagar — DELETE /captacao/candidatos/{{id}} recusa quem tem conquista)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
