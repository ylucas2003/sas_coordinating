"""Endpoints de alunos.

Cada aluno tem matrícula ativa em uma turma (matricula_turma.ativo_ate IS NULL).
Perfil/tendência/zona/media_recente vêm de `classificacao_aluno`, populada
pelo stats engine ao fim de cada upload. Sparkline vem das últimas N notas
em ordem cronológica.
"""

from __future__ import annotations

import math
import statistics as st
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..auth import get_current_coordenador
from ..schemas.domain import Aluno
from ..stats import classificacao as _classif
from ..stats.utils import como_float, nota_real
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/alunos",
    tags=["alunos"],
    dependencies=[Depends(get_current_coordenador)],
)


# ─── Helpers de mapeamento ────────────────────────────────────────────────


def _mapa_turma_para_sede(cliente) -> dict[str, str]:
    resp = cliente.table("turma").select("id, sede_id").execute()
    return {linha["id"]: linha["sede_id"] for linha in (resp.data or [])}


def _mapa_aluno_para_turma_ativa(cliente) -> dict[str, str]:
    resp = (
        cliente.table("matricula_turma")
        .select("aluno_id, turma_id, ativo_desde, ativo_ate")
        .is_("ativo_ate", "null")
        .execute()
    )
    mapa: dict[str, tuple[str, str]] = {}
    for linha in resp.data or []:
        aluno_id = linha["aluno_id"]
        ativo_desde = linha.get("ativo_desde") or ""
        previo = mapa.get(aluno_id)
        if previo is None or ativo_desde > previo[1]:
            mapa[aluno_id] = (linha["turma_id"], ativo_desde)
    return {aluno_id: t[0] for aluno_id, t in mapa.items()}


def _vestibulares_por_aluno(cliente) -> dict[str, list[str]]:
    resp = cliente.table("vestibular_alvo_aluno").select("aluno_id, vestibular").execute()
    mapa: dict[str, list[str]] = defaultdict(list)
    for linha in resp.data or []:
        mapa[linha["aluno_id"]].append(linha["vestibular"])
    return mapa


def _passar_recorte(aluno: Aluno, recorte: str | None) -> bool:
    if not recorte:
        return True
    if recorte == "em-risco":
        return aluno.zona == "risco"
    if recorte == "em-ascensao":
        return aluno.tendencia == "subindo"
    if recorte == "perfil-irregular":
        return aluno.perfil == "misterio"
    if recorte == "zona-corte":
        return aluno.zona == "cinzenta"
    return True


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.get("", response_model=list[Aluno])
async def listar_alunos(
    recorte: str | None = Query(None, description="em-risco | em-ascensao | perfil-irregular | zona-corte"),
    sede_id: str | None = Query(None, alias="sedeId"),
    turma_id: str | None = Query(None, alias="turmaId"),
) -> list[Aluno]:
    cliente = get_supabase()

    aluno_para_turma = _mapa_aluno_para_turma_ativa(cliente)
    turma_para_sede = _mapa_turma_para_sede(cliente)
    classificacoes = _classif.mapa_classificacao(cliente)
    vestibulares = _vestibulares_por_aluno(cliente)
    sparklines = _classif.sparkline_por_aluno(cliente)

    resp = cliente.table("aluno").select("id, nome, ativo").order("nome").execute()

    alunos: list[Aluno] = []
    for linha in resp.data or []:
        id_aluno = linha["id"]
        id_turma = aluno_para_turma.get(id_aluno)
        if not id_turma:
            continue
        id_sede = turma_para_sede.get(id_turma, "")

        if turma_id and id_turma != turma_id:
            continue
        if sede_id and id_sede != sede_id:
            continue

        classif = classificacoes.get(id_aluno) or {}
        aluno = Aluno(
            id=id_aluno,
            nome=linha["nome"],
            turmaId=id_turma,
            sedeId=id_sede,
            vestibularesAlvo=vestibulares.get(id_aluno, []),
            ativo=bool(linha.get("ativo", True)),
            perfil=classif.get("perfil", "regular"),
            tendencia=classif.get("tendencia", "estavel"),
            zona=classif.get("zona", "cinzenta"),
            media=como_float(classif.get("media_recente")),
            sparkline=sparklines.get(id_aluno, []),
        )
        if not _passar_recorte(aluno, recorte):
            continue
        alunos.append(aluno)

    return alunos


@router.get("/{aluno_id}", response_model=Aluno)
async def obter_aluno(aluno_id: str) -> Aluno:
    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("id, nome, ativo, email")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")

    aluno_para_turma = _mapa_aluno_para_turma_ativa(cliente)
    turma_para_sede = _mapa_turma_para_sede(cliente)
    classificacoes = _classif.mapa_classificacao(cliente)
    vestibulares = _vestibulares_por_aluno(cliente)
    sparklines = _classif.sparkline_por_aluno(cliente)

    id_turma = aluno_para_turma.get(aluno_id, "")
    id_sede = turma_para_sede.get(id_turma, "") if id_turma else ""
    classif = classificacoes.get(aluno_id) or {}

    linha = resp.data[0]
    return Aluno(
        id=linha["id"],
        nome=linha["nome"],
        turmaId=id_turma,
        sedeId=id_sede,
        vestibularesAlvo=vestibulares.get(aluno_id, []),
        ativo=bool(linha.get("ativo", True)),
        email=linha.get("email"),
        perfil=classif.get("perfil", "regular"),
        tendencia=classif.get("tendencia", "estavel"),
        zona=classif.get("zona", "cinzenta"),
        media=como_float(classif.get("media_recente")),
        sparkline=sparklines.get(aluno_id, []),
    )


@router.get("/{aluno_id}/trajetoria")
async def trajetoria_aluno(aluno_id: str) -> list[dict]:
    """Lista cronológica das notas do aluno (já em escala 0–10).

    Retorna `pontuacao` normalizada (`acertos / total * 10`). O cliente recebe
    direto o número que faz sentido pra interpretar — nunca acertos brutos.
    """
    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, data_aplicacao, anulado, e_agregado, materia_id, nota_maxima, tipo"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .execute()
    )
    linhas: list[dict] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        if not linha.get("presente"):
            continue
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None:
            continue
        linhas.append(
            {
                "simuladoId": sim.get("id"),
                "simulado": sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "materiaId": sim.get("materia_id"),
                "tipo": sim.get("tipo"),
                "pontuacao": round(nota, 2),
            }
        )
    linhas.sort(key=lambda r: r["dataAplicacao"] or "")
    return linhas


@router.get("/{aluno_id}/heatmap")
async def heatmap_aluno(aluno_id: str) -> dict:
    """Matriz matérias × simulados pra heatmap.

    Saída:
        {
          "materias": ["Matemática", "Física", ...],
          "simulados": [{
              "id", "nome", "rotulo", "dataAplicacao",
              "cicloId", "cicloOrdem", "cicloNome", "vestibularAlvo",
              "fase"  // "fase_1" | "fase_2" | None
          }, ...],
          "celulas": [{"materia", "simuladoId", "pontuacao"}, ...]
        }
    """
    cliente = get_supabase()
    resp = (
        cliente.table("nota")
        .select(
            "pontuacao, presente, simulado("
            "id, nome, rotulo_curto, data_aplicacao, materia_id, tipo, "
            "anulado, e_agregado, nota_maxima, "
            "ciclo:ciclo_id(id, ordem, nome, vestibular_alvo)"
            ")"
        )
        .eq("aluno_id", aluno_id)
        .eq("presente", True)
        .execute()
    )

    materias_resp = cliente.table("materia").select("id, nome").execute()
    nome_materia = {m["id"]: m["nome"] for m in (materias_resp.data or [])}

    simulados_vistos: dict[str, dict] = {}
    celulas: list[dict] = []
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        materia = nome_materia.get(sim.get("materia_id"))
        if not materia:
            continue
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None:
            continue
        sid = sim["id"]
        if sid not in simulados_vistos:
            ciclo = sim.get("ciclo") or {}
            simulados_vistos[sid] = {
                "id": sid,
                "nome": sim.get("nome"),
                "rotulo": sim.get("rotulo_curto") or sim.get("nome"),
                "dataAplicacao": sim.get("data_aplicacao"),
                "cicloId": ciclo.get("id"),
                "cicloOrdem": ciclo.get("ordem"),
                "cicloNome": ciclo.get("nome"),
                "vestibularAlvo": ciclo.get("vestibular_alvo"),
                "fase": sim.get("tipo"),
            }
        celulas.append(
            {
                "materia": materia,
                "simuladoId": sid,
                "pontuacao": round(nota, 2),
            }
        )

    # Ordena primeiro por (ciclo_ordem, fase, data) — coloca tudo do ciclo 1
    # junto, depois ciclo 2, etc. Simulados sem ciclo ordem ficam por último.
    simulados_ordenados = sorted(
        simulados_vistos.values(),
        key=lambda s: (
            s.get("cicloOrdem") if s.get("cicloOrdem") is not None else 999,
            0 if s.get("fase") == "fase_1" else (1 if s.get("fase") == "fase_2" else 2),
            s.get("dataAplicacao") or "",
        ),
    )
    materias_distintas = sorted({c["materia"] for c in celulas})
    return {
        "materias": materias_distintas,
        "simulados": simulados_ordenados,
        "celulas": celulas,
    }


@router.get("/{aluno_id}/similares")
async def alunos_similares(aluno_id: str, k: int = 5) -> list[dict]:
    """kNN por vetor de features (média por matéria + desvio + slope).

    Distância euclidiana. Retorna os `k` alunos mais próximos (excluindo o
    próprio). Vetor com NaN em uma feature pula essa coordenada na soma.
    """
    cliente = get_supabase()
    vetores = _vetores_de_features(cliente)
    if aluno_id not in vetores:
        return []

    alvo = vetores[aluno_id]
    distancias: list[tuple[str, float]] = []
    for outro_id, vec in vetores.items():
        if outro_id == aluno_id:
            continue
        dist = _distancia(alvo, vec)
        if dist is None:
            continue
        distancias.append((outro_id, dist))

    distancias.sort(key=lambda x: x[1])
    top = distancias[:k]

    # Anexa nome e classificação.
    nomes_resp = cliente.table("aluno").select("id, nome").execute()
    nomes = {a["id"]: a["nome"] for a in (nomes_resp.data or [])}
    classif = _classif.mapa_classificacao(cliente)

    saida: list[dict] = []
    for outro_id, dist in top:
        c = classif.get(outro_id) or {}
        saida.append(
            {
                "alunoId": outro_id,
                "nome": nomes.get(outro_id, outro_id),
                "distancia": round(dist, 3),
                "perfil": c.get("perfil"),
                "tendencia": c.get("tendencia"),
                "zona": c.get("zona"),
                "media": como_float(c.get("media_recente")),
            }
        )
    return saida


# ─── Vetor de features por aluno ─────────────────────────────────────────


def _vetores_de_features(cliente) -> dict[str, list[float | None]]:
    """{aluno_id: [media_mat1, media_mat2, ..., desvio, slope]}.

    Materias ordenadas alfabeticamente por nome → ordem estável. None onde
    o aluno não tem nota da matéria.
    """
    materias_resp = cliente.table("materia").select("id, nome").execute()
    materias = sorted(materias_resp.data or [], key=lambda m: m["nome"])
    materia_ids = [m["id"] for m in materias]

    # Notas com materia_id e pontuação — normalizadas em 0–10 antes de
    # virar feature. Sem isso, vetores de alunos comparam apples to oranges.
    resp = (
        cliente.table("nota")
        .select(
            "aluno_id, pontuacao, simulado("
            "materia_id, data_aplicacao, anulado, e_agregado, nota_maxima"
            ")"
        )
        .eq("presente", True)
        .execute()
    )

    notas_por_aluno: dict[str, list[dict]] = defaultdict(list)
    for linha in resp.data or []:
        sim = linha.get("simulado") or {}
        if sim.get("anulado") or sim.get("e_agregado"):
            continue
        mid = sim.get("materia_id")
        nota = nota_real(
            como_float(linha.get("pontuacao")),
            como_float(sim.get("nota_maxima")),
        )
        if nota is None or not mid:
            continue
        notas_por_aluno[linha["aluno_id"]].append(
            {"materia_id": mid, "pontuacao": nota, "data": sim.get("data_aplicacao") or ""}
        )

    classif = _classif.mapa_classificacao(cliente)

    vetores: dict[str, list[float | None]] = {}
    for aluno_id, notas in notas_por_aluno.items():
        por_materia: dict[str, list[float]] = defaultdict(list)
        for n in notas:
            por_materia[n["materia_id"]].append(n["pontuacao"])
        # 6 médias por matéria
        v: list[float | None] = []
        for mid in materia_ids:
            valores = por_materia.get(mid, [])
            v.append(st.mean(valores) if valores else None)
        # Desvio geral
        todas = [n["pontuacao"] for n in notas]
        v.append(st.stdev(todas) if len(todas) > 1 else None)
        # Slope (vem da classificação)
        c = classif.get(aluno_id) or {}
        v.append(como_float(c.get("coef_tendencia")))
        vetores[aluno_id] = v
    return vetores


def _distancia(a: list[float | None], b: list[float | None]) -> float | None:
    if len(a) != len(b):
        return None
    soma = 0.0
    dimensoes_validas = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        soma += (x - y) ** 2
        dimensoes_validas += 1
    if dimensoes_validas == 0:
        return None
    # Normaliza pela dimensão pra não penalizar alunos com matérias faltando.
    return math.sqrt(soma / dimensoes_validas)


# ─── Acesso do aluno (área do aluno) ─────────────────────────────────────


class ResetarAcessoBody(BaseModel):
    email: str | None = None  # corrige o e-mail do Canvas quando divergente/ausente


@router.post("/{aluno_id}/resetar-acesso")
async def resetar_acesso_aluno(aluno_id: str, body: ResetarAcessoBody) -> dict:
    """Zera a senha do aluno, liberando um novo "primeiro acesso".

    Fallback da coordenação para alunos sem e-mail no Canvas (ou com e-mail
    divergente): opcionalmente grava o e-mail correto junto.
    """
    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("id, email")
        .eq("id", aluno_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"aluno {aluno_id} não encontrado")

    patch: dict = {"senha_hash": None}
    if body.email and body.email.strip():
        patch["email"] = body.email.strip().lower()
    cliente.table("aluno").update(patch).eq("id", aluno_id).execute()

    return {"ok": True, "email": patch.get("email") or resp.data[0].get("email")}
