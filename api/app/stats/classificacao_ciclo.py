"""Classificação de um ciclo por um critério — a ponte entre o banco e o avaliador.

`criterios.py` é puro e não sabe de banco. Este módulo é quem carrega as notas
do ciclo, monta o `dict[codigo_materia, NotaDaMateria]` de cada aluno e chama
`avaliar`. A regra continua morando só lá; aqui é I/O e montagem.

Uma decisão de modelagem que não é óbvia: quando o aluno fez a mesma matéria
mais de uma vez no ciclo (dois simulados de Matemática na Fase 2), entra a
**média** das notas dessa matéria — é o que o painel já fazia nas colunas
virtuais, e o que a coordenação espera ver. Os acertos somam junto, para os
mínimos em acertos continuarem comparáveis.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date

from supabase import Client

from .criterios import FASE_1, Criterio, NotaDaMateria, Veredito, avaliar, tom_da_nota
from .utils import como_float, nota_real

log = logging.getLogger("sas.stats.classificacao_ciclo")

# O PostgREST corta a resposta em 1000 linhas; sem paginar, um ciclo com 1500
# alunos e 6 simulados classificaria sobre uma fatia arbitrária (risco nº 2 do
# docs/18 §7). Mesmo tamanho de página de classificacao.py.
_TAMANHO_PAGINA = 1000


def classificar(
    cliente: Client,
    *,
    ciclo_id: str,
    criterio: Criterio,
    fase: int | None = None,
) -> list[dict]:
    """Lista ordenada de alunos do ciclo segundo o critério.

    `fase` restringe às notas de uma fase; None usa a fase do critério, e se o
    critério também não tiver, usa o ciclo inteiro. Para critérios de Fase 2 a
    média da Fase 1 entra como a pseudo-matéria `fase_1` quando o critério a
    pede (ITA §4.7).
    """
    fase_alvo = fase if fase is not None else criterio.fase
    simulados = _carregar_simulados(cliente, ciclo_id=ciclo_id)
    materias = _mapa_materias(cliente)
    notas_brutas = _carregar_notas(cliente, simulado_ids=[s["id"] for s in simulados])
    alunos = _mapa_alunos(cliente, {linha["aluno_id"] for linha in notas_brutas})

    por_aluno = _montar_notas_por_aluno(
        simulados, notas_brutas, materias, fase_alvo=fase_alvo,
        precisa_fase_1=any(p.materia == FASE_1 for p in criterio.predicados),
    )

    linhas: list[dict] = []
    for aluno_id, notas in por_aluno.items():
        veredito = avaliar(criterio, notas)
        aluno = alunos.get(aluno_id) or {}
        linhas.append(_linha(aluno_id, aluno, notas, veredito, criterio))

    # Maior chave é melhor; desempate final por nome para a ordem ser estável
    # entre duas chamadas (o edital desempata por idade, que não temos).
    linhas.sort(key=lambda l: (tuple(-x for x in l["_ordenacao"]), l["nome"]))
    for posicao, linha in enumerate(linhas, start=1):
        linha["posicao"] = posicao
        del linha["_ordenacao"]
    return linhas


# ─── Montagem ────────────────────────────────────────────────────────────


def _montar_notas_por_aluno(
    simulados: list[dict],
    notas_brutas: list[dict],
    materias: dict[str, dict],
    *,
    fase_alvo: int | None,
    precisa_fase_1: bool,
) -> dict[str, dict[str, NotaDaMateria]]:
    sim_por_id = {s["id"]: s for s in simulados}
    tipo_alvo = f"fase_{fase_alvo}" if fase_alvo else None

    # {aluno: {codigo: [(nota, acertos, total), ...]}}
    acum: dict[str, dict[str, list[tuple[float, float | None, float | None]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    # Para a pseudo-matéria fase_1: {aluno: [notas de qualquer matéria da F1]}
    f1: dict[str, list[float]] = defaultdict(list)

    for linha in notas_brutas:
        sim = sim_por_id.get(linha["simulado_id"])
        if not sim:
            continue
        total = como_float(sim.get("nota_maxima"))
        acertos = como_float(linha.get("pontuacao"))
        nota = nota_real(acertos, total)
        if nota is None:
            continue
        codigo = (materias.get(sim.get("materia_id")) or {}).get("codigo")
        aluno_id = linha["aluno_id"]

        if precisa_fase_1 and sim.get("tipo") == "fase_1":
            f1[aluno_id].append(nota)
        if tipo_alvo and sim.get("tipo") != tipo_alvo:
            continue
        if not codigo:
            continue
        acum[aluno_id][codigo].append((nota, acertos, total))

    saida: dict[str, dict[str, NotaDaMateria]] = {}
    for aluno_id in set(acum) | set(f1):
        notas: dict[str, NotaDaMateria] = {}
        for codigo, lista in acum.get(aluno_id, {}).items():
            media = sum(n for n, _, _ in lista) / len(lista)
            # Acertos só fazem sentido somados se todos os totais são conhecidos.
            if all(a is not None and t is not None for _, a, t in lista):
                soma_a = sum(a for _, a, _ in lista)
                soma_t = sum(t for _, _, t in lista)
                notas[codigo] = NotaDaMateria(nota=media, acertos=soma_a, total=soma_t)
            else:
                notas[codigo] = NotaDaMateria(nota=media)
        if precisa_fase_1 and f1.get(aluno_id):
            notas[FASE_1] = NotaDaMateria(nota=sum(f1[aluno_id]) / len(f1[aluno_id]))
        if notas:
            saida[aluno_id] = notas
    return saida


def _linha(
    aluno_id: str,
    aluno: dict,
    notas: dict[str, NotaDaMateria],
    veredito: Veredito,
    criterio: Criterio,
) -> dict:
    return {
        "alunoId": aluno_id,
        "nome": aluno.get("nome") or "",
        "turmaId": aluno.get("turma_id"),
        "aprovado": veredito.aprovado,
        "motivo": veredito.motivo,
        "media": round(veredito.media, 2) if veredito.media is not None else None,
        "notas": {
            codigo: {
                "nota": round(n.nota, 2),
                "tom": tom_da_nota(criterio, codigo, n.nota),
            }
            for codigo, n in notas.items()
            if codigo != FASE_1
        },
        "_ordenacao": veredito.ordenacao,
    }


# ─── Carregadores ────────────────────────────────────────────────────────


def _carregar_simulados(cliente: Client, *, ciclo_id: str) -> list[dict]:
    resp = (
        cliente.table("simulado")
        .select("id, tipo, materia_id, nota_maxima")
        .eq("ciclo_id", ciclo_id)
        .eq("anulado", False)
        .eq("e_agregado", False)
        .lte("data_aplicacao", date.today().isoformat())
        .execute()
    )
    return resp.data or []


def _mapa_materias(cliente: Client) -> dict[str, dict]:
    resp = cliente.table("materia").select("id, codigo").execute()
    return {m["id"]: m for m in (resp.data or [])}


def _carregar_notas(cliente: Client, *, simulado_ids: list[str]) -> list[dict]:
    """Todas as notas presentes dos simulados dados, PAGINANDO."""
    if not simulado_ids:
        return []
    linhas: list[dict] = []
    offset = 0
    while True:
        lote = (
            cliente.table("nota")
            .select("aluno_id, simulado_id, pontuacao")
            .in_("simulado_id", simulado_ids)
            .eq("presente", True)
            .range(offset, offset + _TAMANHO_PAGINA - 1)
            .execute()
            .data
            or []
        )
        linhas.extend(lote)
        if len(lote) < _TAMANHO_PAGINA:
            return linhas
        offset += _TAMANHO_PAGINA


def _mapa_alunos(cliente: Client, aluno_ids: set[str]) -> dict[str, dict]:
    """{aluno_id: {nome, turma_id}} — turma ativa via matricula_turma."""
    if not aluno_ids:
        return {}
    ids = list(aluno_ids)
    saida: dict[str, dict] = {}
    for inicio in range(0, len(ids), _TAMANHO_PAGINA):
        fatia = ids[inicio : inicio + _TAMANHO_PAGINA]
        alunos = cliente.table("aluno").select("id, nome").in_("id", fatia).execute().data or []
        for a in alunos:
            saida[a["id"]] = {"nome": a.get("nome"), "turma_id": None}
        matriculas = (
            cliente.table("matricula_turma")
            .select("aluno_id, turma_id")
            .in_("aluno_id", fatia)
            .is_("ativo_ate", "null")
            .execute()
            .data
            or []
        )
        for m in matriculas:
            if m["aluno_id"] in saida:
                saida[m["aluno_id"]]["turma_id"] = m["turma_id"]
    return saida
