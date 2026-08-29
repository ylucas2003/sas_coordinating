"""Leitura do acompanhamento de gravações — GET /gravacoes-aula.

Router SEPARADO de rotas.py de propósito: lá dentro tudo é do scheduler
(`X-Scheduler-Secret`), aqui tudo é do coordenador (JWT). Misturar os dois num
arquivo só é como se esquece um guard numa rota nova.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..auth import get_current_coordenador
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/gravacoes-aula",
    tags=["gravacoes-aula"],
    dependencies=[Depends(get_current_coordenador)],
)

# Explícito, nunca "*": s3_bucket e s3_chave_composto NÃO saem daqui. São a
# localização do vídeo de aluno menor de idade no bucket privado — não é dado
# de tela, e a tela não precisa deles para nada.
_CAMPOS = (
    "id,curso_id,conferencia_id,titulo,iniciada_em,duracao_minutos,status,"
    "tentativas,youtube_video_id,youtube_titulo,erro_detalhe,"
    "canvas_estado,canvas_pagina_url,canvas_erro,criado_em,atualizado_em"
)


def _para_camel(a: dict[str, Any]) -> dict[str, Any]:
    """O front espelha o backend (web/src/tipos/dominio.ts); a URL do vídeo é
    montada aqui para o front não precisar reinventar o formato."""
    video = a.get("youtube_video_id")
    return {
        "id": a["id"],
        "cursoId": a["curso_id"],
        "conferenciaId": a["conferencia_id"],
        "titulo": a["titulo"],
        "iniciadaEm": a.get("iniciada_em"),
        "duracaoMinutos": a.get("duracao_minutos"),
        "status": a["status"],
        "tentativas": a.get("tentativas") or 0,
        "youtubeVideoId": video,
        "youtubeTitulo": a.get("youtube_titulo"),
        "youtubeUrl": f"https://youtu.be/{video}" if video else None,
        "erroDetalhe": (a.get("erro_detalhe") or None) and a["erro_detalhe"][:300],
        "canvasEstado": a.get("canvas_estado") or "pendente",
        "canvasUrl": a.get("canvas_pagina_url"),
        "canvasErro": (a.get("canvas_erro") or None) and a["canvas_erro"][:300],
        "atualizadoEm": a.get("atualizado_em"),
    }


@router.get("")
async def listar_gravacoes() -> dict:
    """Tudo que o painel precisa numa chamada só.

    Sem paginação de propósito: são dezenas de linhas por semestre (uma por
    aula), não as centenas de milhares de `nota` que motivam a dívida de
    paginação descrita no CLAUDE.md da raiz."""
    cliente = get_supabase()
    cursos = (
        cliente.table("curso_monitorado_gravacao")
        .select("curso_id,nome,ativo,publicar_no_canvas")
        .order("nome")
        .execute()
        .data
    )
    aulas = (
        cliente.table("aula_gravacao")
        .select(_CAMPOS)
        .order("iniciada_em", desc=True)
        .execute()
        .data
    )
    return {
        "cursos": [
            {
                "cursoId": c["curso_id"],
                "nome": c["nome"],
                "ativo": c["ativo"],
                "publicarNoCanvas": c["publicar_no_canvas"],
            }
            for c in cursos
        ],
        "aulas": [_para_camel(a) for a in aulas],
    }
