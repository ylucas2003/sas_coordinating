"""Captação externa — candidatos achados fora do colégio, cruzando resultado
público de olimpíada/vestibular/concurso (docs/41).

Só leitura + o funil manual (`status_captacao`, `observacoes`). Quem escreve
`prova_externa`/`conquista_externa`/`candidato_externo` de verdade são os
scripts de `api/scripts/importar_captacao_externa.py` e
`api/scripts/resolver_candidatos_externos.py` (docs/41 §4) — esta rota nunca
cria candidato nem conquista, e nunca reescreve os campos que o resolver
deriva (nome, escola, série de referência...).

`get_current_coordenador`, e não administrador: é leitura/triagem de lead
sobre gente de FORA do colégio, não acesso a conta ou nota de quem já estuda
aqui — mesma régua de `banco.py` (docs/41 §7.1).

⚠️ `candidato_externo` não tem nada a ver com `aluno`. É gente que nunca
colocou os pés no colégio; a migration 0056 explica o porquê das três tabelas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, field_validator
from supabase import Client

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/captacao",
    tags=["captacao"],
    dependencies=[Depends(get_current_coordenador)],
)

# Mesmo vocabulário do CHECK de `candidato_externo.status_captacao` (0056) —
# duplicado aqui de propósito, como `PAPEIS_DE_COORDENACAO` em auth.py: é o que
# permite a rota recusar um valor errado com 400 em vez de estourar 23514 do
# Postgres por trás do PostgREST.
STATUS_CAPTACAO = ("novo", "contatado", "interessado", "matriculado", "descartado")

POR_PAGINA_PADRAO = 20
POR_PAGINA_MAXIMO = 100

_COLUNAS_CANDIDATO = (
    "id, nome, escola, cidade, uf, serie_referencia_min, serie_referencia_max, "
    "ano_referencia_serie, status_captacao, observacoes, criado_em, atualizado_em, "
    "conquistas_total, provas_distintas, ano_mais_recente"
)

_COLUNAS_CONQUISTA = (
    "id, prova_id, ano, nivel_texto, serie_referencia_min, serie_referencia_max, "
    "resultado, nome_informado, escola_informada, cidade_informada, uf_informada, "
    "fonte_url, raspado_em"
)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _ids_por_prova(cliente: Client, prova_id: str) -> list[str]:
    """Candidatos com ao menos uma conquista da prova pedida.

    `v_candidato_externo` não tem `prova_id` — um candidato cruza N provas —,
    então filtrar "por prova" exige pré-consultar `conquista_externa` e aplicar
    o resultado como `.in_("id", ...)` na view. Mesmo desenho de
    `banco/consultas.py::_ids_por_topico`, pelo mesmo motivo: o filtro não é
    coluna da tabela principal.
    """
    linhas = (
        cliente.table("conquista_externa")
        .select("candidato_id")
        .eq("prova_id", prova_id)
        .not_.is_("candidato_id", "null")
        .execute()
        .data
        or []
    )
    return list({linha["candidato_id"] for linha in linhas})


class AtualizarCandidatoBody(BaseModel):
    """Só os dois campos do funil manual — os outros são derivados (0056 §3)."""

    status_captacao: str | None = None
    observacoes: str | None = None

    @field_validator("status_captacao")
    @classmethod
    def _status_conhecido(cls, v: str | None) -> str | None:
        if v is not None and v not in STATUS_CAPTACAO:
            raise ValueError(f"status_captacao deve ser um de {STATUS_CAPTACAO}")
        return v


@router.get("/candidatos")
async def listar_candidatos(
    uf: str | None = Query(None, description="sigla, ex.: 'CE'"),
    status_captacao: str | None = Query(None),
    conquistas_min: int | None = Query(
        None, ge=1, description="nº mínimo de conquistas cruzadas — o sinal mais forte de lead"
    ),
    prova_id: str | None = Query(None, description="só candidatos com conquista desta prova"),
    busca: str | None = Query(None, description="texto no nome"),
    pagina: int = Query(1, ge=1, description="1-based, como a URL mostra"),
    por_pagina: int = Query(POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> dict:
    """Página de candidatos, de quem mais cruzou conquista pra quem menos —
    é a ordem que separa lead forte de aparição única (docs/41 §5).

    **Paginação de verdade**, ao contrário do resto do sistema (CLAUDE.md,
    armadilha 2). Lá o teto é proibido porque truncaria leitura ESTATÍSTICA em
    silêncio; aqui a resposta é navegação sobre gente de fora, sem o teto
    natural dos ~900 alunos — 26 mil candidatos e crescendo a cada fonte nova
    (docs/41 §7.1).
    """
    if status_captacao is not None and status_captacao not in STATUS_CAPTACAO:
        raise HTTPException(
            status_code=400, detail=f"status_captacao deve ser um de {STATUS_CAPTACAO}"
        )

    cliente = get_supabase()
    consulta = cliente.table("v_candidato_externo").select(_COLUNAS_CANDIDATO, count="exact")
    if uf:
        consulta = consulta.eq("uf", uf.upper())
    if status_captacao:
        consulta = consulta.eq("status_captacao", status_captacao)
    if conquistas_min is not None:
        consulta = consulta.gte("conquistas_total", conquistas_min)
    if busca and busca.strip():
        consulta = consulta.ilike("nome", f"%{busca.strip()}%")
    if prova_id:
        ids_da_prova = _ids_por_prova(cliente, prova_id)
        if not ids_da_prova:
            return {"candidatos": [], "total": 0, "pagina": pagina, "por_pagina": por_pagina}
        consulta = consulta.in_("id", ids_da_prova)

    # `id` no fim do `order`, como em `banco/consultas.py::listar_questoes`:
    # `conquistas_total` empata para milhares de candidatos com uma conquista
    # só, e sem um critério total o Postgres é livre para reordenar os empates
    # a cada página — a virada repete um candidato e perde outro.
    inicio = (pagina - 1) * por_pagina
    resposta = (
        consulta.order("conquistas_total", desc=True)
        .order("nome")
        .order("id")
        .range(inicio, inicio + por_pagina - 1)
        .execute()
    )
    linhas = resposta.data or []
    total = int(resposta.count) if resposta.count is not None else len(linhas)
    return {"candidatos": linhas, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/candidatos/{candidato_id}")
async def obter_candidato(candidato_id: str = Path(...)) -> dict:
    """A ficha: o candidato resolvido e TODAS as conquistas cruzadas dele,
    da mais recente para a mais antiga — é o cruzamento que a captação existe
    pra mostrar (docs/41 §0)."""
    cliente = get_supabase()
    linhas = (
        cliente.table("v_candidato_externo")
        .select(_COLUNAS_CANDIDATO)
        .eq("id", candidato_id)
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    candidato = linhas[0]

    conquistas = (
        cliente.table("conquista_externa")
        .select(_COLUNAS_CONQUISTA)
        .eq("candidato_id", candidato_id)
        .order("ano", desc=True)
        .execute()
        .data
        or []
    )

    # Nome e categoria da prova, resolvidos em Python — a mesma junção manual
    # de `banco/consultas.py::montar_questoes`, e pelo mesmo motivo: o projeto
    # não usa embedding do PostgREST, só `.table()` + merge (api/CLAUDE.md).
    ids_das_provas = list({c["prova_id"] for c in conquistas})
    provas = (
        cliente.table("prova_externa")
        .select("id, nome, categoria")
        .in_("id", ids_das_provas)
        .execute()
        .data
        if ids_das_provas
        else []
    )
    nome_da_prova = {p["id"]: p["nome"] for p in provas}
    categoria_da_prova = {p["id"]: p["categoria"] for p in provas}
    for c in conquistas:
        c["prova_nome"] = nome_da_prova.get(c["prova_id"])
        c["prova_categoria"] = categoria_da_prova.get(c["prova_id"])

    candidato["conquistas"] = conquistas
    return candidato


@router.patch("/candidatos/{candidato_id}")
async def atualizar_candidato(
    body: AtualizarCandidatoBody,
    request: Request,
    candidato_id: str = Path(...),
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Só `status_captacao` e `observacoes` — o funil manual da coordenação
    (0056 §3). Os outros campos são derivados: só
    `api/scripts/resolver_candidatos_externos.py` escreve neles, e reescrevê-los
    aqui os deixaria divergentes na próxima resolução."""
    if body.status_captacao is None and body.observacoes is None:
        raise HTTPException(status_code=400, detail="Nada a atualizar")

    cliente = get_supabase()
    atual = (
        cliente.table("candidato_externo")
        .select("status_captacao")
        .eq("id", candidato_id)
        .limit(1)
        .execute()
        .data
    )
    if not atual:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")

    patch: dict[str, Any] = {"atualizado_em": _agora()}
    if body.status_captacao is not None:
        patch["status_captacao"] = body.status_captacao
    if body.observacoes is not None:
        patch["observacoes"] = body.observacoes

    atualizado = (
        cliente.table("candidato_externo")
        .update(patch, returning="representation")
        .eq("id", candidato_id)
        .execute()
    ).data
    if not atualizado:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")

    # Evento próprio, e só quando o STATUS muda: é a decisão que interessa
    # auditar (quem moveu este lead no funil), não a edição de um comentário
    # livre — mesmo recorte de `papel_alterado` em administracao.py.
    status_anterior = atual[0].get("status_captacao")
    if body.status_captacao is not None and body.status_captacao != status_anterior:
        auditar(
            cliente,
            "captacao_status_alterado",
            canal="captacao",
            ator_tipo="coordenador",
            ator_id=coordenador.get("sub"),
            recurso=f"candidato_externo/{candidato_id}",
            ip=request.client.host if request.client else None,
            detalhe={"valor_antes": status_anterior, "valor_depois": body.status_captacao},
        )

    return atualizado[0]
