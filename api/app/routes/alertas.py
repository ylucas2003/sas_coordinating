"""Endpoints de alertas.

Lê de `alerta` filtrando não-resolvidos, ordenado por severidade desc,
disparado_em desc. Monta o payload no formato esperado pelo frontend
(documentado em docs/05-data-and-stats.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from ..schemas.domain import Alerta
from ..supabase_client import get_supabase

router = APIRouter(prefix="/alertas", tags=["alertas"])


# Ordem semântica do design system (vermelho > âmbar > verde > cinza).
_PESO_SEVERIDADE = {"vermelho": 0, "ambar": 1, "verde": 2, "cinza": 3}

_TAG_LABEL = {
    "QUEDA_RENDIMENTO": "Queda de rendimento",
    "SUBIDA_ATIPICA": "Subida atípica",
    "PROVA_MAL_CALIBRADA": "Prova mal calibrada",
    "MATERIA_EM_RISCO": "Matéria em risco",
    "DIFERENCA_ENTRE_SEDES": "Diferença entre sedes",
    "ZONA_TRANSICAO": "Mudança de zona",
    "PANORAMA_CICLO": "Panorama de ciclo",
}


def _href_para_entidade(entidade_tipo: str, entidade_id: str) -> str:
    if entidade_tipo == "aluno":
        return f"#/alunos/{entidade_id}"
    if entidade_tipo == "simulado":
        return f"#/simulados/{entidade_id}"
    if entidade_tipo == "turma":
        return f"#/alunos?turmaId={entidade_id}"
    if entidade_tipo == "sede":
        return f"#/alunos?sedeId={entidade_id}"
    return "#/painel"


def _tempo_relativo(disparado_em: str | None) -> str:
    if not disparado_em:
        return ""
    try:
        d = datetime.fromisoformat(disparado_em.replace("Z", "+00:00"))
        agora = datetime.now(timezone.utc)
        delta = agora - d
        if delta.total_seconds() < 60:
            return "agora há pouco"
        minutos = int(delta.total_seconds() / 60)
        if minutos < 60:
            return f"há {minutos} min"
        horas = int(minutos / 60)
        if horas < 24:
            return f"há {horas} h"
        dias = int(horas / 24)
        if dias < 7:
            return f"há {dias} d"
        return d.strftime("%d/%m")
    except Exception:
        return disparado_em


def _linha_para_alerta(linha: dict) -> Alerta:
    dados = linha.get("dados_brutos") or {}
    categoria = linha["categoria"]
    return Alerta(
        id=linha["id"],
        categoria=categoria,
        severidade=linha["severidade"],
        tagLabel=_TAG_LABEL.get(categoria, categoria),
        titulo=linha.get("titulo") or "",
        subtitulo=linha.get("subtitulo") or "",
        tempoRelativo=_tempo_relativo(linha.get("disparado_em")),
        href=_href_para_entidade(linha["entidade_tipo"], linha["entidade_id"]),
        sparkline=dados.get("sparkline") or [],
    )


@router.get("", response_model=list[Alerta])
async def listar_alertas() -> list[Alerta]:
    cliente = get_supabase()
    resp = (
        cliente.table("alerta")
        .select("id, categoria, severidade, entidade_tipo, entidade_id, titulo, subtitulo, dados_brutos, disparado_em, resolvido")
        .eq("resolvido", False)
        .order("disparado_em", desc=True)
        .limit(100)
        .execute()
    )
    linhas = resp.data or []
    linhas.sort(key=lambda r: (_PESO_SEVERIDADE.get(r["severidade"], 99), r.get("disparado_em") or ""))
    return [_linha_para_alerta(linha) for linha in linhas]


@router.post("/{alerta_id}/resolver")
async def resolver_alerta(alerta_id: str) -> dict:
    """Marca o alerta como resolvido. Tela do painel remove o card."""
    cliente = get_supabase()
    resp = (
        cliente.table("alerta")
        .update({"resolvido": True, "resolvido_em": "now()"})
        .eq("id", alerta_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail=f"alerta {alerta_id} não encontrado")
    return {"id": alerta_id, "resolvido": True}
