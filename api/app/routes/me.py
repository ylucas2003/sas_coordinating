"""Endpoints do aluno autenticado — proxy seguro para os dados do próprio aluno.

O aluno só consegue ver os próprios dados: o JWT carrega o aluno_id e os
handlers repassam para as extrações de stats/aluno_dados.py (compartilhadas
com as tools do chat do aluno) sem expor o ID na URL nem permitir acesso a
outros alunos.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from ..auth import get_current_aluno, hash_senha, verificar_senha
from ..stats.aluno_dados import (
    detalhe_simulado_do_aluno,
    evolucao_do_aluno,
    payload_insight_ciclo,
    questoes_do_aluno_no_simulado,
    simulados_do_aluno,
    streak_do_aluno,
)
from ..stats.insight_aluno import gerar_para_aluno_ciclo
from ..supabase_client import get_supabase
from .alunos import heatmap_aluno, obter_aluno, trajetoria_aluno

router = APIRouter(prefix="/me", tags=["me"])


def _ou_404(resultado: dict) -> dict:
    """{"erro": ...} das extrações compartilhadas vira 404 na camada HTTP."""
    if isinstance(resultado, dict) and "erro" in resultado:
        raise HTTPException(status_code=404, detail=resultado["erro"])
    return resultado


# ── Conta ─────────────────────────────────────────────────────────────────


class TrocarSenhaBody(BaseModel):
    senha_atual: str
    senha_nova: str

    @field_validator("senha_nova")
    @classmethod
    def _senha_minima(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("a senha precisa ter pelo menos 8 caracteres")
        return v


@router.post("/senha")
async def me_trocar_senha(body: TrocarSenhaBody, user: dict = Depends(get_current_aluno)) -> dict:
    cliente = get_supabase()
    resp = (
        cliente.table("aluno")
        .select("id, senha_hash")
        .eq("id", user["aluno_id"])
        .limit(1)
        .execute()
    )
    # 400 (não 401): o http-client do front desloga a sessão em qualquer 401,
    # e errar a senha atual não pode derrubar o aluno logado.
    if not resp.data or not verificar_senha(body.senha_atual, resp.data[0].get("senha_hash")):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    cliente.table("aluno").update(
        {"senha_hash": hash_senha(body.senha_nova)}
    ).eq("id", user["aluno_id"]).execute()
    return {"ok": True}


# ── Perfil e dados (proxies das funções de /alunos) ───────────────────────


@router.get("")
async def me(user: dict = Depends(get_current_aluno)):
    return await obter_aluno(user["aluno_id"])


@router.get("/trajetoria")
async def me_trajetoria(user: dict = Depends(get_current_aluno)):
    return await trajetoria_aluno(user["aluno_id"])


@router.get("/heatmap")
async def me_heatmap(user: dict = Depends(get_current_aluno)):
    return await heatmap_aluno(user["aluno_id"])


# ── Área do aluno (extrações compartilhadas em stats/aluno_dados.py) ──────


@router.get("/streak")
async def me_streak(user: dict = Depends(get_current_aluno)):
    """Ciclos consecutivos recentes onde o aluno ficou acima da média da turma."""
    return streak_do_aluno(get_supabase(), user["aluno_id"])


@router.get("/simulados")
async def me_simulados(user: dict = Depends(get_current_aluno)):
    """Lista de simulados do aluno com nota, delta vs próprio padrão e média da turma."""
    return simulados_do_aluno(get_supabase(), user["aluno_id"])


@router.get("/simulado/{simulado_id}")
async def me_simulado(simulado_id: str, user: dict = Depends(get_current_aluno)):
    """Detalhe de um simulado: nota do aluno, ranking e comparação com grupos."""
    return _ou_404(detalhe_simulado_do_aluno(get_supabase(), user["aluno_id"], simulado_id))


@router.get("/simulado/{simulado_id}/questoes")
async def me_simulado_questoes(simulado_id: str, user: dict = Depends(get_current_aluno)):
    """Resultado questão a questão do aluno num simulado (dados do Canvas)."""
    return _ou_404(questoes_do_aluno_no_simulado(get_supabase(), user["aluno_id"], simulado_id))


@router.get("/evolucao")
async def me_evolucao(user: dict = Depends(get_current_aluno)):
    """Dados para o gráfico de evolução por matéria ao longo dos ciclos."""
    return evolucao_do_aluno(get_supabase(), user["aluno_id"])


@router.get("/insight")
def me_insight(user: dict = Depends(get_current_aluno)) -> dict:
    """Insight de IA do ciclo mais recente do aluno (card do painel).

    On-demand com cache em insight_aluno_ciclo — primeira chamada por
    aluno×ciclo×dados chama o LLM; as seguintes voltam do banco. Handler
    síncrono de propósito: a chamada LLM roda no threadpool, não no event loop.
    """
    cliente = get_supabase()
    resultado = payload_insight_ciclo(cliente, user["aluno_id"])
    if resultado is None:
        return {"disponivel": False, "cicloOrdem": None, "cicloNome": None, "bullets": []}

    ciclo, stats_payload = resultado
    bullets = gerar_para_aluno_ciclo(
        cliente,
        aluno_id=user["aluno_id"],
        ciclo_id=ciclo["id"],
        stats_payload=stats_payload,
        contexto={"nomeAluno": user.get("nome") or ""},
    )
    return {
        "disponivel": bool(bullets),
        "cicloOrdem": ciclo["ordem"],
        "cicloNome": ciclo["nome"],
        "bullets": bullets,
    }
