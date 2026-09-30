"""Séries derivadas das notas, guardadas por aluno (migration 0066).

Duas coisas que a coordenação lia varrendo TODAS as notas a cada clique:

  - a **sparkline** (últimas notas em 0–10) de `GET /alunos` e `GET /alunos/{id}`;
  - o **vetor de features** do kNN de `GET /alunos/{id}/similares`.

Medido em 29/09/2026: abrir UM aluno custava 1,04 s, dos quais 1,01 s eram a
sparkline de todos (78 páginas de 1.000 linhas em sequência). As duas séries só
mudam quando entra nota — o mesmo instante em que `classificacao_aluno` é
recalculada —, então são gravadas ali (`classificacao.recalcular_*`) e lidas
daqui como leitura de tabela.

Este módulo NÃO importa `classificacao` no topo: é `classificacao` que o chama.
Só o backfill (`python -m app.stats.serie_recente`) faz o caminho inverso, e faz
por import tardio.
"""

from __future__ import annotations

import logging
import statistics as st
from collections import defaultdict
from collections.abc import Iterable

from supabase import Client

from .utils import como_float, nota_real

log = logging.getLogger("sas.stats.serie_recente")

#: Quantos ids cabem numa query `in.(...)` sem estourar a URL do PostgREST.
_FATIA_DE_IDS = 200
#: Quantas linhas por upsert.
_FATIA_DE_GRAVACAO = 500


# ─── Leitura (o que as rotas usam) ────────────────────────────────────────


def sparklines(cliente: Client, *, aluno_ids: Iterable[str] | None = None) -> dict[str, list[float]]:
    """{aluno_id: [nota 0–10, da mais antiga à mais recente]}.

    `aluno_ids` restringe a leitura (a ficha de um aluno só). Aluno sem linha
    fica de fora — quem chama usa `.get(id, [])`.
    """
    return {
        linha["aluno_id"]: linha["sparkline"] or []
        for linha in _ler(cliente, "aluno_id, sparkline", aluno_ids)
    }


def vetores(cliente: Client) -> dict[str, list[float | None]]:
    """{aluno_id: vetor de features} de todos os alunos que têm vetor."""
    return {
        linha["aluno_id"]: linha["vetor_similares"]
        for linha in _ler(cliente, "aluno_id, vetor_similares", None)
        if linha["vetor_similares"] is not None
    }


def _ler(cliente: Client, colunas: str, aluno_ids: Iterable[str] | None) -> list[dict]:
    if aluno_ids is None:
        return cliente.table("aluno_serie_recente").select(colunas).execute().data or []
    ids = list(dict.fromkeys(aluno_ids))
    linhas: list[dict] = []
    for inicio in range(0, len(ids), _FATIA_DE_IDS):
        fatia = ids[inicio : inicio + _FATIA_DE_IDS]
        linhas.extend(
            cliente.table("aluno_serie_recente").select(colunas).in_("aluno_id", fatia).execute().data or []
        )
    return linhas


# ─── Escrita (o que o recálculo usa) ──────────────────────────────────────


def gravar(
    cliente: Client,
    *,
    notas_recentes: dict[str, list[dict]],
    aluno_ids: Iterable[str] | None = None,
) -> int:
    """Regrava sparkline e vetor. Devolve quantas linhas foram gravadas.

    `notas_recentes` é o `{aluno_id: [{pontuacao, ...}]}` de
    `classificacao._notas_recentes_por_aluno` — já em 0–10 e já cortado na
    janela —, para o recálculo não reler as notas só para isto.

    `aluno_ids` None = todos os alunos: quem tinha linha e agora não tem nota
    nenhuma (nota apagada, prova anulada) é zerado, senão a sparkline antiga
    ficaria para sempre. Com lista (sync incremental), só esses são regravados.
    """
    escopo = None if aluno_ids is None else list(dict.fromkeys(aluno_ids))
    calculados = calcular_vetores(cliente, aluno_ids=escopo)

    if escopo is None:
        alvo = set(notas_recentes) | set(calculados)
        # Quem tinha linha e saiu do conjunto é zerado, não deixado para trás.
        existentes = {l["aluno_id"] for l in _ler(cliente, "aluno_id", None)}
        alvo |= existentes
    else:
        alvo = set(escopo)

    linhas = [
        {
            "aluno_id": aluno_id,
            "sparkline": [n["pontuacao"] for n in notas_recentes.get(aluno_id, [])],
            "vetor_similares": calculados.get(aluno_id),
        }
        for aluno_id in sorted(alvo)
    ]
    for inicio in range(0, len(linhas), _FATIA_DE_GRAVACAO):
        cliente.table("aluno_serie_recente").upsert(
            linhas[inicio : inicio + _FATIA_DE_GRAVACAO], on_conflict="aluno_id"
        ).execute()
    return len(linhas)


def calcular_vetores(
    cliente: Client, *, aluno_ids: Iterable[str] | None = None
) -> dict[str, list[float | None]]:
    """{aluno_id: [média por matéria (ordem alfabética do nome)..., desvio, slope]}.

    None onde o aluno não tem dado. As notas entram normalizadas em 0–10; sem
    isso vetores de alunos comparariam provas de tamanhos diferentes.

    O slope (última posição) vem de `classificacao_aluno.coef_tendencia`, então
    esta função precisa rodar DEPOIS de a classificação ser gravada.
    """
    materias = sorted(
        cliente.table("materia").select("id, nome").execute().data or [],
        key=lambda m: m["nome"],
    )
    materia_ids = [m["id"] for m in materias]

    escopo = None if aluno_ids is None else list(dict.fromkeys(aluno_ids))
    linhas = _notas_para_vetor(cliente, escopo)

    notas_por_aluno: dict[str, list[dict]] = defaultdict(list)
    for linha in linhas:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        materia_id = sim.get("materia_id")
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None or not materia_id:
            continue
        notas_por_aluno[linha["aluno_id"]].append({"materia_id": materia_id, "pontuacao": nota})

    coeficientes = _coeficientes_de_tendencia(cliente, escopo)

    resultado: dict[str, list[float | None]] = {}
    for aluno_id, notas in notas_por_aluno.items():
        por_materia: dict[str, list[float]] = defaultdict(list)
        for n in notas:
            por_materia[n["materia_id"]].append(n["pontuacao"])
        vetor: list[float | None] = []
        for materia_id in materia_ids:
            valores = por_materia.get(materia_id, [])
            vetor.append(st.mean(valores) if valores else None)
        todas = [n["pontuacao"] for n in notas]
        vetor.append(st.stdev(todas) if len(todas) > 1 else None)
        vetor.append(coeficientes.get(aluno_id))
        resultado[aluno_id] = vetor
    return resultado


def _notas_para_vetor(cliente: Client, escopo: list[str] | None) -> list[dict]:
    def consulta():
        return (
            cliente.table("nota")
            .select(
                "aluno_id, pontuacao, simulado("
                "materia_id, anulado, e_agregado, nota_maxima"
                ")"
            )
            .eq("presente", True)
            .eq("computavel", True)
        )

    if escopo is None:
        return consulta().execute().data or []
    linhas: list[dict] = []
    for inicio in range(0, len(escopo), _FATIA_DE_IDS):
        fatia = escopo[inicio : inicio + _FATIA_DE_IDS]
        linhas.extend(consulta().in_("aluno_id", fatia).execute().data or [])
    return linhas


def _coeficientes_de_tendencia(cliente: Client, escopo: list[str] | None) -> dict[str, float | None]:
    def consulta():
        return cliente.table("classificacao_aluno").select("aluno_id, coef_tendencia")

    if escopo is None:
        linhas = consulta().execute().data or []
    else:
        linhas = []
        for inicio in range(0, len(escopo), _FATIA_DE_IDS):
            fatia = escopo[inicio : inicio + _FATIA_DE_IDS]
            linhas.extend(consulta().in_("aluno_id", fatia).execute().data or [])
    return {l["aluno_id"]: como_float(l.get("coef_tendencia")) for l in linhas}


# ─── Backfill ─────────────────────────────────────────────────────────────


def recalcular_tudo(cliente: Client) -> int:
    """Regrava as séries de todos os alunos sem reclassificar ninguém.

    É o backfill depois da migration 0066, e serve também de reparo se alguém
    suspeitar que as séries envelheceram.
    """
    from . import classificacao  # import tardio: `classificacao` importa este módulo
    from . import thresholds as th

    notas = classificacao._notas_recentes_por_aluno(cliente, janela=th.JANELA_CLASSIFICACAO)
    return gravar(cliente, notas_recentes=notas)


def _tabela_vazia(cliente: Client) -> bool:
    return not (cliente.table("aluno_serie_recente").select("aluno_id").limit(1).execute().data)


if __name__ == "__main__":
    import sys

    from ..supabase_client import criar_cliente_supabase

    logging.basicConfig(level=logging.INFO)
    _cliente = criar_cliente_supabase()
    # `--se-vazia` é o que o deploy usa: idempotente, então pode rodar a cada
    # deploy sem custo, e só trabalha na primeira vez depois da migration 0066.
    if "--se-vazia" in sys.argv and not _tabela_vazia(_cliente):
        log.info("aluno_serie_recente já tem dados — nada a fazer")
    else:
        log.info("%d alunos com série gravada", recalcular_tudo(_cliente))
