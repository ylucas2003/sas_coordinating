"""Endpoints do aluno autenticado — proxy seguro para /alunos/{id}.

O aluno só consegue ver os próprios dados: o JWT carrega o aluno_id e
os handlers repassam direto para as funções de /alunos sem expor o ID
na URL ou permitir acesso a outros alunos.
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException

from ..auth import get_current_aluno
from ..stats.metricas import mapa_metrica_geral_por_simulado
from ..stats.utils import como_float, nota_real
from .alunos import heatmap_aluno, obter_aluno, trajetoria_aluno

router = APIRouter(prefix="/me", tags=["me"])


# ── Endpoints existentes ──────────────────────────────────────────────────


@router.get("")
async def me(user: dict = Depends(get_current_aluno)):
    return await obter_aluno(user["aluno_id"])


@router.get("/trajetoria")
async def me_trajetoria(user: dict = Depends(get_current_aluno)):
    return await trajetoria_aluno(user["aluno_id"])


@router.get("/heatmap")
async def me_heatmap(user: dict = Depends(get_current_aluno)):
    return await heatmap_aluno(user["aluno_id"])


# ── Novos endpoints da área do aluno ─────────────────────────────────────


@router.get("/streak")
async def me_streak(user: dict = Depends(get_current_aluno)):
    """Ciclos consecutivos recentes onde o aluno ficou acima da média da turma."""
    aluno_id = user["aluno_id"]
    from ..supabase_client import get_supabase

    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nota_maxima, anulado, e_agregado, "
            "ciclo:ciclo_id(id, ordem)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .execute()
    )

    metricas = mapa_metrica_geral_por_simulado(cliente)

    por_ciclo: dict[int, dict] = defaultdict(lambda: {"minhas": [], "turma": []})
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        ciclo = sim.get("ciclo") or {}
        ordem = ciclo.get("ordem")
        if ordem is None:
            continue
        por_ciclo[ordem]["minhas"].append(nota)
        media_turma = (metricas.get(sim["id"]) or {}).get("media")
        if media_turma is not None:
            por_ciclo[ordem]["turma"].append(media_turma)

    if not por_ciclo:
        return {"count": 0, "label": "ciclos acima da média da turma"}

    streak = 0
    for ordem in sorted(por_ciclo.keys(), reverse=True):
        d = por_ciclo[ordem]
        if not d["minhas"] or not d["turma"]:
            break
        if st.mean(d["minhas"]) > st.mean(d["turma"]):
            streak += 1
        else:
            break

    return {"count": streak, "label": "ciclos acima da média da turma"}


@router.get("/simulados")
async def me_simulados(user: dict = Depends(get_current_aluno)):
    """Lista de simulados do aluno com nota, delta vs próprio padrão e média da turma."""
    aluno_id = user["aluno_id"]
    from ..supabase_client import get_supabase

    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, nota_maxima, materia_id, tipo, anulado, e_agregado, "
            "ciclo:ciclo_id(id, ordem, vestibular_alvo)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .execute()
    )

    metricas = mapa_metrica_geral_por_simulado(cliente)
    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    itens: list[dict] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        ciclo = sim.get("ciclo") or {}
        met = metricas.get(sim["id"]) or {}
        itens.append(
            {
                "id": sim["id"],
                "nome": sim.get("nome"),
                "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "tipo": sim.get("tipo"),
                "materia": nome_mat.get(sim.get("materia_id")),
                "nota": round(nota, 2),
                "deltaSelf": None,
                "mediaGeral": round(met["media"], 2) if met.get("media") is not None else None,
                "nPresentes": met.get("n_presentes", 0),
                "cicloOrdem": ciclo.get("ordem"),
                "vestibularAlvo": ciclo.get("vestibular_alvo"),
                "novo": False,
            }
        )

    # Ordena ASC para calcular delta acumulativo
    itens.sort(key=lambda s: s.get("dataAplicacao") or "")
    notas_ant: list[float] = []
    for item in itens:
        if notas_ant:
            item["deltaSelf"] = round(item["nota"] - sum(notas_ant) / len(notas_ant), 2)
        notas_ant.append(item["nota"])

    # Ordena DESC para a resposta; marca o mais recente
    itens.sort(key=lambda s: s.get("dataAplicacao") or "", reverse=True)
    if itens:
        itens[0]["novo"] = True

    return itens


@router.get("/simulado/{simulado_id}")
async def me_simulado(simulado_id: str, user: dict = Depends(get_current_aluno)):
    """Detalhe de um simulado: nota do aluno, ranking e comparação com grupos."""
    aluno_id = user["aluno_id"]
    from ..supabase_client import get_supabase

    cliente = get_supabase()

    sim_resp = (
        cliente.table("simulado")
        .select("id, nome, rotulo_curto, data_aplicacao, nota_maxima, materia_id, tipo")
        .eq("id", simulado_id)
        .limit(1)
        .execute()
    )
    if not sim_resp.data:
        raise HTTPException(status_code=404, detail="Simulado não encontrado")

    sim = sim_resp.data[0]
    nota_maxima = como_float(sim.get("nota_maxima")) or 10.0

    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    notas_resp = (
        cliente.table("nota")
        .select("aluno_id, pontuacao")
        .eq("simulado_id", simulado_id)
        .eq("presente", True)
        .execute()
    )

    todas_notas: list[float] = []
    minha_nota: float | None = None
    for linha in notas_resp.data or []:
        n = nota_real(como_float(linha.get("pontuacao")), nota_maxima)
        if n is None:
            continue
        todas_notas.append(n)
        if linha["aluno_id"] == aluno_id:
            minha_nota = n

    if minha_nota is None:
        raise HTTPException(status_code=404, detail="Nota não encontrada para este simulado")

    total = len(todas_notas)
    desc = sorted(todas_notas, reverse=True)
    # Posição = posição do aluno entre os melhores (1 = melhor)
    posicao = next((i + 1 for i, v in enumerate(desc) if v <= minha_nota + 0.001), total)
    percentil = round((total - posicao) / total * 100) if total > 1 else 50

    n15 = max(1, int(total * 0.15))
    geral = st.mean(todas_notas)
    top15 = st.mean(sorted(todas_notas)[-n15:])
    bottom15 = st.mean(sorted(todas_notas)[:n15])

    # Delta vs média de todos os outros simulados do aluno
    outras_resp = (
        cliente.table("nota")
        .select("pontuacao, presente, simulado(nota_maxima, anulado, e_agregado)")
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .neq("simulado_id", simulado_id)
        .execute()
    )
    outras: list[float] = []
    for linha in outras_resp.data or []:
        s = linha.get("simulado") or {}
        if s.get("anulado") or s.get("e_agregado"):
            continue
        n = nota_real(como_float(linha.get("pontuacao")), como_float(s.get("nota_maxima")))
        if n is not None:
            outras.append(n)
    delta_self = round(minha_nota - st.mean(outras), 2) if outras else None

    return {
        "id": sim["id"],
        "nome": sim.get("nome"),
        "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
        "dataAplicacao": sim.get("data_aplicacao"),
        "tipo": sim.get("tipo"),
        "materia": nome_mat.get(sim.get("materia_id")),
        "nota": round(minha_nota, 2),
        "deltaSelf": delta_self,
        "posicao": posicao,
        "total": total,
        "percentil": percentil,
        "grupos": {
            "voce": round(minha_nota, 2),
            "geral": round(geral, 2),
            "top15": round(top15, 2),
            "bottom15": round(bottom15, 2),
        },
    }


@router.get("/evolucao")
async def me_evolucao(user: dict = Depends(get_current_aluno)):
    """Dados para o gráfico de evolução por matéria ao longo dos ciclos."""
    aluno_id = user["aluno_id"]
    from ..supabase_client import get_supabase

    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nota_maxima, materia_id, anulado, e_agregado, "
            "ciclo:ciclo_id(id, ordem)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .execute()
    )

    metricas = mapa_metrica_geral_por_simulado(cliente)
    mats_resp = cliente.table("materia").select("id, nome").execute()
    nome_mat = {m["id"]: m["nome"] for m in (mats_resp.data or [])}

    # {ciclo_ordem: {materia_nome: {aluno: [...], turma: [...]}}}
    dados: dict[int, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"aluno": [], "turma": []}))

    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        ciclo = sim.get("ciclo") or {}
        ordem = ciclo.get("ordem")
        if ordem is None:
            continue
        materia = nome_mat.get(sim.get("materia_id"))
        if not materia:
            continue
        nota = nota_real(como_float(linha.get("pontuacao")), como_float(sim.get("nota_maxima")))
        if nota is None:
            continue
        dados[ordem][materia]["aluno"].append(nota)
        media_turma = (metricas.get(sim["id"]) or {}).get("media")
        if media_turma is not None:
            dados[ordem][materia]["turma"].append(media_turma)

    if not dados:
        return {"ciclos": [], "materias": {}}

    ordens = sorted(dados.keys())
    ciclos = [{"ordem": o, "label": f"C{o}"} for o in ordens]
    todas_mats = sorted({m for cd in dados.values() for m in cd.keys()})

    materias_out: dict[str, dict] = {}
    for mat in todas_mats:
        aluno_vals = []
        turma_vals = []
        for ordem in ordens:
            vals = dados[ordem].get(mat, {})
            al = vals.get("aluno", [])
            tu = vals.get("turma", [])
            aluno_vals.append(round(st.mean(al), 2) if al else None)
            turma_vals.append(round(st.mean(tu), 2) if tu else None)
        materias_out[mat] = {"aluno": aluno_vals, "turma": turma_vals}

    return {"ciclos": ciclos, "materias": materias_out}
