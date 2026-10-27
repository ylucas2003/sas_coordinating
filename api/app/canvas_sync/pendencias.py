"""O que de um ciclo ainda não está refletido no Canvas — só leitura.

Nasceu em `routes/ciclos.py` como `_pendencias_do_ciclo`, para alimentar o
diálogo de confirmação do envio em lote (docs/32 §4.2). Desceu para cá porque
deixou de ter um leitor só: a tool do assistente que responde "o que deste
ciclo ainda não subiu?" (docs/43 §4.3) faz a mesma pergunta, e de dentro de uma
tool um `HTTPException` vira "falhou do nosso lado" em vez de "esse ciclo não
existe". Por isso o ciclo inexistente aqui é `None`, e quem o traduz em 404 é
a rota.

Não escreve nada. A regra de 21/08 — "nada sobe ao Canvas sem alguém clicar" —
aplicada ao lote quer dizer que o coordenador vê esta lista ANTES de mandar;
quem manda é `routes/ciclos.enviar_ciclo_ao_canvas_em_lote`, item a item, pelas
funções de `escrita.py`.

⚠️ O `erro` do grupo e o de cada simulado são o `str(exc)` que a escrita gravou
(`escrita.py`), cru: podem trazer o endereço da API do Canvas. A tela o mostra
a quem vai clicar; quem o leva a um modelo passa por `texto_seguro` antes
(docs/43 §3.2, invariante 6).
"""

from __future__ import annotations

from typing import Any

from supabase import Client

from .escrita import DIVERGENTE

#: Teto de notas por lote. `enviar_nota` é UMA requisição por aluno, e um
#: ciclo pode ter centenas de notas divergentes — sem teto, a rota estoura o
#: timeout do gateway no meio, deixando metade enviada e nenhum relatório.
#:
#: O Canvas tem `POST .../submissions/update_grades`, que faria isso numa
#: chamada assíncrona por assignment, e o `ClienteCanvas` não o tem. Entra como
#: melhoria medida, não como aposta (docs/32 §4.2, item 4).
TETO_NOTAS_POR_LOTE = 80


def pendencias_do_ciclo(cliente: Client, ciclo_id: str) -> dict[str, Any] | None:
    """O que deste ciclo não está refletido no Canvas, por tipo. `None` se o
    ciclo não existe.

    `notas` vem cortada em `TETO_NOTAS_POR_LOTE` — é o que o lote manda —, e
    `notasAlemDoTeto` diz quantas ficaram de fora: truncar em silêncio é o que
    esta leitura existe para evitar.
    """
    ciclo = (
        cliente.table("ciclo")
        .select("id, nome, canvas_estado, canvas_erro")
        .eq("id", ciclo_id)
        .limit(1)
        .execute()
    ).data
    if not ciclo:
        return None
    ciclo = ciclo[0]

    # 1 · o grupo do ciclo
    grupo_pendente = ciclo.get("canvas_estado") in (DIVERGENTE, "falhou")

    # 2 · os simulados nascidos no SAS que ainda não refletem lá
    simulados = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, origem, canvas_estado, canvas_erro")
        .eq("ciclo_id", ciclo_id)
        .eq("origem", "sas")
        .in_("canvas_estado", [DIVERGENTE, "falhou"])
        .execute()
    ).data or []

    # 3 · as notas editadas no SAS que o Canvas ainda não tem.
    #
    # A divergência de nota é DERIVADA (docs/18 §2.4), não um estado guardado:
    # é `pontuacao_sas` diferente de `pontuacao_canvas`. Por isso ela não dá
    # para filtrar no PostgREST — a comparação é entre duas colunas —, e a
    # peneira acontece aqui.
    ids_do_ciclo = [
        linha["id"]
        for linha in (
            cliente.table("simulado").select("id").eq("ciclo_id", ciclo_id).execute().data or []
        )
    ]
    notas_divergentes: list[dict[str, Any]] = []
    if ids_do_ciclo:
        linhas = (
            cliente.table("nota")
            .select(
                "aluno_id, simulado_id, pontuacao_sas, pontuacao_canvas, "
                "aluno:aluno_id(nome), simulado:simulado_id(nome, rotulo_curto)"
            )
            .in_("simulado_id", ids_do_ciclo)
            .not_.is_("pontuacao_sas", "null")
            .execute()
        ).data or []
        for linha in linhas:
            if linha.get("pontuacao_sas") == linha.get("pontuacao_canvas"):
                continue
            notas_divergentes.append(
                {
                    "alunoId": linha["aluno_id"],
                    "simuladoId": linha["simulado_id"],
                    "aluno": (linha.get("aluno") or {}).get("nome", ""),
                    "simulado": (linha.get("simulado") or {}).get("rotulo_curto")
                    or (linha.get("simulado") or {}).get("nome", ""),
                    "noSas": linha.get("pontuacao_sas"),
                    "noCanvas": linha.get("pontuacao_canvas"),
                }
            )

    return {
        "cicloId": ciclo_id,
        "nome": ciclo.get("nome"),
        "grupo": {
            "pendente": grupo_pendente,
            "estado": ciclo.get("canvas_estado"),
            "erro": ciclo.get("canvas_erro"),
        },
        "simulados": [
            {
                "id": s["id"],
                "nome": s.get("rotulo_curto") or s.get("nome", ""),
                "estado": s.get("canvas_estado"),
                "erro": s.get("canvas_erro"),
            }
            for s in simulados
        ],
        "notas": notas_divergentes[:TETO_NOTAS_POR_LOTE],
        # Truncar em silêncio é o que esta leitura existe para evitar.
        "notasAlemDoTeto": max(0, len(notas_divergentes) - TETO_NOTAS_POR_LOTE),
        "total": (1 if grupo_pendente else 0)
        + len(simulados)
        + min(len(notas_divergentes), TETO_NOTAS_POR_LOTE),
    }
