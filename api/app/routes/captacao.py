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

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, field_validator
from supabase import Client

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..supabase_client import criar_cliente_supabase, get_supabase

_log = logging.getLogger("sas.captacao")

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
    "id, nome, nome_normalizado, escola, cidade, uf, serie_referencia_min, serie_referencia_max, "
    "ano_referencia_serie, status_captacao, observacoes, criado_em, atualizado_em, "
    "conquistas_total, provas_distintas, ano_mais_recente"
)

# Só a lista geral lê a view agrupada (0062) — perfis_no_grupo/tem_conflito_nivel
# não existem em v_candidato_externo, só no que agrega por nome_normalizado.
_COLUNAS_CANDIDATO_AGRUPADO = _COLUNAS_CANDIDATO + ", perfis_no_grupo, tem_conflito_nivel"

_COLUNAS_CONQUISTA = (
    "id, prova_id, ano, nivel_texto, serie_referencia_min, serie_referencia_max, "
    "resultado, nome_informado, escola_informada, cidade_informada, uf_informada, "
    "fonte_url, raspado_em, notas_por_materia"
)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _refresh_view_agrupada() -> None:
    """Chamada pelo BackgroundTasks, depois da resposta já ter saído.

    Cliente NOVO (não cacheado), mesmo motivo de
    `gravacoes_aula/rotas.py::_rodada_em_background`: o postgrest-py força
    HTTP/2 numa conexão só por client, e um GOAWAY nesta chamada (o refresh
    sozinho já leva ~1s, medido) não pode abortar as streams de alguma outra
    requisição que esteja usando o client cacheado ao mesmo tempo.

    Erro aqui é engolido (CLAUDE.md: "erro em caminho de auditoria ou
    telemetria é engolido") — é uma view de LEITURA em cache, não o dado em
    si; se falhar, a lista geral só fica desatualizada até o próximo
    refresh (o cron do resolver é o backstop).
    """
    try:
        criar_cliente_supabase().rpc("atualizar_v_candidato_externo_agrupado", {}).execute()
    except Exception:
        _log.warning("Falha ao atualizar v_candidato_externo_agrupado", exc_info=True)


def _agendar_refresh_view_agrupada(tarefas: BackgroundTasks) -> None:
    """Toda rota que escreve em candidato_externo/conquista_externa chama
    isto antes de devolver a resposta — a view agrupada (0062) é
    MATERIALIZADA por custo (~1,3s pra recalcular do zero, medido) e não
    acompanha a escrita sozinha."""
    tarefas.add_task(_refresh_view_agrupada)


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


class FusaoBody(BaseModel):
    nome_normalizado: str


class MoverConquistaBody(BaseModel):
    conquista_id: str
    candidato_id: str


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
    # v_candidato_externo_agrupado (0062), não v_candidato_externo: um nome
    # ainda pendente na fila de fusão (docs/41 §8 item 1) vira UMA linha aqui,
    # com perfis_no_grupo dizendo quantos existem de verdade — quem está
    # caçando lead não deveria ver a fragmentação interna do resolver.
    consulta = cliente.table("v_candidato_externo_agrupado").select(
        _COLUNAS_CANDIDATO_AGRUPADO, count="exact"
    )
    if uf:
        consulta = consulta.eq("uf", uf.upper())
    if status_captacao:
        consulta = consulta.eq("status_captacao", status_captacao)
    if conquistas_min is not None:
        consulta = consulta.gte("conquistas_total", conquistas_min)
    if busca and busca.strip():
        consulta = consulta.ilike("nome", f"%{busca.strip()}%")
    if prova_id:
        # Limitação conhecida (não usada pela UI hoje — Captacao.tsx não expõe
        # filtro de prova): contra a view agrupada, `id` é sempre o do PERFIL
        # REPRESENTANTE do grupo — se a conquista daquela prova estiver num
        # candidato_externo que não é o representante, o filtro não acha.
        # Corrigir exigiria traduzir os ids pra nome_normalizado → id
        # representante antes do `.in_()`, o que não vale o custo enquanto o
        # filtro não é visível em lugar nenhum.
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

    # Duplicata pendente na fila de fusão (docs/41 §8 item 1) — é a base do
    # alerta na ficha (a coordenação descobre a partir do PERFIL da pessoa,
    # não só varrendo a fila separada). v_fusao_candidata (0061) já grupo por
    # nome_normalizado e já traz tem_conflito_nivel calculado.
    fusao = (
        cliente.table("v_fusao_candidata")
        .select("candidatos, tem_conflito_nivel")
        .eq("nome_normalizado", candidato["nome_normalizado"])
        .limit(1)
        .execute()
        .data
    )
    candidato["duplicatas_pendentes"] = (fusao[0]["candidatos"] - 1) if fusao else 0
    candidato["tem_conflito_nivel"] = fusao[0]["tem_conflito_nivel"] if fusao else False

    return candidato


@router.patch("/candidatos/{candidato_id}")
async def atualizar_candidato(
    body: AtualizarCandidatoBody,
    request: Request,
    tarefas: BackgroundTasks,
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

    _agendar_refresh_view_agrupada(tarefas)
    return atualizado[0]


# ─── Fila de fusão de baixa confiança (docs/41 §8, item 1) ──────────────
#
# O resolver só funde por nome+escola EXATOS (§4.1) — de propósito, pra
# nunca juntar duas pessoas diferentes por engano. Isso deixa cada conquista
# de fonte sem escola (OBM, ITA, IME) como candidato PRÓPRIO, mesmo quando é
# a mesma pessoa que a OBMEP/OBF já resolveram. Aqui é o segundo nível,
# nome sozinho — mais barato de achar, mais arriscado de confiar — por isso
# NUNCA funde sozinho: só sugere, e um humano confirma ou rejeita.


def _serie_dominante(conquistas: list[dict]) -> dict:
    """O retrato (nome/escola/cidade/uf/série) da conquista mais RECENTE
    entre todas as do grupo fundido — mesma regra do resolver
    (`resolver_candidatos_externos.py::dados_candidato`), aplicada aqui pro
    candidato sobrevivente não ficar com um retrato de anos atrás só porque
    foi o primeiro a ser criado."""
    mais_recente = max(conquistas, key=lambda c: c["ano"])
    return {
        "nome": mais_recente["nome_informado"],
        "escola": mais_recente.get("escola_informada"),
        "cidade": mais_recente.get("cidade_informada"),
        "uf": mais_recente.get("uf_informada"),
        "serie_referencia_min": mais_recente.get("serie_referencia_min"),
        "serie_referencia_max": mais_recente.get("serie_referencia_max"),
        "ano_referencia_serie": mais_recente["ano"],
    }


@router.get("/fusoes")
async def listar_fusoes(
    uf_incerta: bool = Query(False, description="só grupos com mais de uma UF entre os candidatos — mais arriscado"),
    so_conflito_nivel: bool = Query(
        False,
        description=(
            "só grupos com nível de ensino conflitante entre candidatos — sinal FORTE "
            "de gente diferente (quase certeza), não só 'cuidado' como ufs_distintas"
        ),
    ),
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> dict:
    """A fila: nomes com mais de um `candidato_externo`, ainda não
    decididos. Ordenada do mais confiável (uma UF só entre os candidatos)
    pro menos, e dentro disso do grupo com mais candidatos pro com menos —
    é o que faz o trabalho de revisão render mais rápido primeiro.
    """
    cliente = get_supabase()
    consulta = cliente.table("v_fusao_candidata").select(
        "nome_normalizado, candidatos, ufs_distintas, tem_conflito_nivel", count="exact"
    )
    if uf_incerta:
        consulta = consulta.gt("ufs_distintas", 1)
    if so_conflito_nivel:
        consulta = consulta.eq("tem_conflito_nivel", True)

    inicio = (pagina - 1) * por_pagina
    resposta = (
        consulta.order("ufs_distintas")
        .order("candidatos", desc=True)
        .order("nome_normalizado")
        .range(inicio, inicio + por_pagina - 1)
        .execute()
    )
    linhas = resposta.data or []
    total = int(resposta.count) if resposta.count is not None else len(linhas)
    return {"grupos": linhas, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/fusoes/{nome_normalizado}")
async def obter_fusao(nome_normalizado: str = Path(...)) -> dict:
    """O grupo inteiro: todo `candidato_externo` com este nome, cada um com
    as próprias conquistas — pra comparar escola/cidade/UF lado a lado
    antes de decidir."""
    cliente = get_supabase()
    candidatos = (
        cliente.table("v_candidato_externo")
        .select(_COLUNAS_CANDIDATO)
        .eq("nome_normalizado", nome_normalizado)
        .order("criado_em")
        .execute()
        .data
        or []
    )
    if len(candidatos) < 2:
        raise HTTPException(status_code=404, detail="Nada pra fundir com este nome")

    conquistas = (
        cliente.table("conquista_externa")
        .select(f"candidato_id, {_COLUNAS_CONQUISTA}")
        .in_("candidato_id", [c["id"] for c in candidatos])
        .order("ano", desc=True)
        .execute()
        .data
        or []
    )
    ids_das_provas = list({c["prova_id"] for c in conquistas})
    provas = (
        cliente.table("prova_externa").select("id, nome").in_("id", ids_das_provas).execute().data
        if ids_das_provas
        else []
    )
    nome_da_prova = {p["id"]: p["nome"] for p in provas}
    por_candidato: dict[str, list[dict]] = {c["id"]: [] for c in candidatos}
    for c in conquistas:
        c["prova_nome"] = nome_da_prova.get(c["prova_id"])
        por_candidato.setdefault(c["candidato_id"], []).append(c)

    for candidato in candidatos:
        candidato["conquistas"] = por_candidato.get(candidato["id"], [])
    return {"nome_normalizado": nome_normalizado, "candidatos": candidatos}


@router.post("/fusoes/confirmar")
async def confirmar_fusao(
    body: FusaoBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """São a mesma pessoa: combina todo `candidato_externo` deste nome num
    só. O sobrevivente é o que já tem MAIS conquistas (empate: o mais
    antigo) — os outros são apagados depois de repassar as conquistas
    deles pro sobrevivente. Nunca desfeito automaticamente; a trilha de
    auditoria guarda quem eram os candidatos fundidos, pra investigar se um
    dia alguém discordar da decisão."""
    cliente = get_supabase()
    candidatos = (
        cliente.table("candidato_externo")
        .select("id, criado_em")
        .eq("nome_normalizado", body.nome_normalizado)
        .execute()
        .data
        or []
    )
    if len(candidatos) < 2:
        raise HTTPException(status_code=404, detail="Nada pra fundir com este nome")

    ids = [c["id"] for c in candidatos]
    conquistas = (
        cliente.table("conquista_externa")
        .select(f"id, candidato_id, {_COLUNAS_CONQUISTA}")
        .in_("candidato_id", ids)
        .execute()
        .data
        or []
    )

    contagem: dict[str, int] = {i: 0 for i in ids}
    for c in conquistas:
        contagem[c["candidato_id"]] = contagem.get(c["candidato_id"], 0) + 1
    criado_em_por_id = {c["id"]: c["criado_em"] for c in candidatos}
    # Mais conquistas primeiro; empate resolvido pelo mais antigo — o
    # sobrevivente natural é quem já tinha mais história, não um sorteio.
    # `criado_em` é ISO 8601: comparar como string já ordena por data,
    # sem precisar converter pra `datetime`.
    maior_contagem = max(contagem.values())
    top = [i for i in ids if contagem[i] == maior_contagem]
    sobrevivente_id = min(top, key=lambda i: criado_em_por_id[i])

    outros_ids = [i for i in ids if i != sobrevivente_id]
    retrato = _serie_dominante(conquistas)

    cliente.table("conquista_externa").update(
        {"candidato_id": sobrevivente_id}
    ).in_("candidato_id", outros_ids).execute()

    cliente.table("candidato_externo").update(
        {**retrato, "atualizado_em": _agora()}
    ).eq("id", sobrevivente_id).execute()

    for outro_id in outros_ids:
        cliente.table("candidato_externo").delete().eq("id", outro_id).execute()

    cliente.table("candidato_externo_fusao_decisao").upsert(
        {
            "nome_normalizado": body.nome_normalizado,
            "status": "confirmada",
            "decidido_por": coordenador.get("nome"),
            "decidido_em": _agora(),
        },
        on_conflict="nome_normalizado",
    ).execute()

    auditar(
        cliente,
        "captacao_fusao_confirmada",
        canal="captacao",
        ator_tipo="coordenador",
        ator_id=coordenador.get("sub"),
        recurso=f"candidato_externo/{sobrevivente_id}",
        ip=request.client.host if request.client else None,
        detalhe={
            "nome_normalizado": body.nome_normalizado,
            "sobrevivente": sobrevivente_id,
            "fundidos": outros_ids,
        },
    )
    _agendar_refresh_view_agrupada(tarefas)
    return {"sobrevivente_id": sobrevivente_id, "candidatos_fundidos": len(outros_ids)}


@router.post("/fusoes/rejeitar")
async def rejeitar_fusao(
    body: FusaoBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Não são a mesma pessoa: tira este nome da fila pra sempre (nenhum
    candidato_externo é tocado — só a decisão fica registrada)."""
    cliente = get_supabase()
    cliente.table("candidato_externo_fusao_decisao").upsert(
        {
            "nome_normalizado": body.nome_normalizado,
            "status": "rejeitada",
            "decidido_por": coordenador.get("nome"),
            "decidido_em": _agora(),
        },
        on_conflict="nome_normalizado",
    ).execute()

    auditar(
        cliente,
        "captacao_fusao_rejeitada",
        canal="captacao",
        ator_tipo="coordenador",
        ator_id=coordenador.get("sub"),
        recurso=f"candidato_externo_fusao/{body.nome_normalizado}",
        ip=request.client.host if request.client else None,
        detalhe={"nome_normalizado": body.nome_normalizado},
    )
    _agendar_refresh_view_agrupada(tarefas)
    return {"ok": True}


# ─── Modo avançado: dividir um grupo à mão (pedido de 24/09/2026) ──────────
#
# O binário confirmar/rejeitar acima resolve o caso simples (todo mundo é a
# mesma pessoa, ou ninguém é) — mas o caso mais comum na prática é misto: 2
# destes 3 candidatos são a mesma pessoa, o terceiro é homônimo. As quatro
# rotas abaixo dão o controle fino — mover CADA resultado pro perfil certo,
# criar um perfil vazio pra separar um homônimo, remover o que sobrar vazio —
# e `concluir` fecha o nome com o que restou, reaproveitando os DOIS status já
# existentes em `candidato_externo_fusao_decisao` (sem migration no CHECK):
# 1 perfil sobrevivente = mesma semântica de "confirmada"; 2+ = mesma
# semântica de "rejeitada" (pessoas diferentes), só que agora com os
# resultados no perfil certo em vez de intocados.


@router.post("/fusoes/criar-perfil")
async def criar_perfil_no_grupo(
    body: FusaoBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Perfil novo, vazio, com o mesmo nome do grupo — pra arrastar pra
    dentro dele um resultado que na verdade é de outra pessoa (homônimo
    misturado num candidato_externo que hoje junta os dois). O retrato
    (escola/cidade/UF) fica em branco: assim que uma conquista for movida
    pra cá, `mover_conquista` recalcula com `_serie_dominante`."""
    cliente = get_supabase()
    candidatos = (
        cliente.table("candidato_externo")
        .select("nome")
        .eq("nome_normalizado", body.nome_normalizado)
        .order("criado_em")
        .limit(1)
        .execute()
        .data
    )
    if not candidatos:
        raise HTTPException(status_code=404, detail="Nenhum candidato com este nome")

    novo = (
        cliente.table("candidato_externo")
        .insert(
            {
                "nome": candidatos[0]["nome"],
                "nome_normalizado": body.nome_normalizado,
                "status_captacao": "novo",
                "criado_em": _agora(),
                "atualizado_em": _agora(),
            },
            returning="representation",
        )
        .execute()
    ).data
    if not novo:
        raise HTTPException(status_code=500, detail="Não foi possível criar o perfil")
    novo_candidato = novo[0]

    auditar(
        cliente,
        "captacao_perfil_criado",
        canal="captacao",
        ator_tipo="coordenador",
        ator_id=coordenador.get("sub"),
        recurso=f"candidato_externo/{novo_candidato['id']}",
        ip=request.client.host if request.client else None,
        detalhe={"nome_normalizado": body.nome_normalizado},
    )

    novo_candidato["conquistas"] = []
    novo_candidato["conquistas_total"] = 0
    novo_candidato["provas_distintas"] = 0
    novo_candidato["ano_mais_recente"] = None
    _agendar_refresh_view_agrupada(tarefas)
    return novo_candidato


@router.post("/conquistas/mover")
async def mover_conquista(
    body: MoverConquistaBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Reatribui UM resultado pra outro perfil do mesmo nome — o coração do
    modo avançado. Recalcula o retrato de quem ganhou e de quem perdeu a
    conquista (se ainda sobrar alguma), pra nenhum dos dois ficar com um
    retrato de anos atrás depois do reagrupamento."""
    cliente = get_supabase()

    conquista = (
        cliente.table("conquista_externa")
        .select("id, candidato_id")
        .eq("id", body.conquista_id)
        .limit(1)
        .execute()
        .data
    )
    if not conquista:
        raise HTTPException(status_code=404, detail="Conquista não encontrada")
    origem_id = conquista[0]["candidato_id"]

    if origem_id == body.candidato_id:
        return {"ok": True}

    pares = (
        cliente.table("candidato_externo")
        .select("id, nome_normalizado")
        .in_("id", [i for i in (origem_id, body.candidato_id) if i])
        .execute()
        .data
        or []
    )
    por_id = {c["id"]: c for c in pares}
    destino = por_id.get(body.candidato_id)
    if not destino:
        raise HTTPException(status_code=404, detail="Perfil de destino não encontrado")
    origem = por_id.get(origem_id)
    if origem and origem["nome_normalizado"] != destino["nome_normalizado"]:
        raise HTTPException(
            status_code=400, detail="O perfil de destino não tem o mesmo nome do de origem"
        )

    cliente.table("conquista_externa").update(
        {"candidato_id": body.candidato_id}
    ).eq("id", body.conquista_id).execute()

    for candidato_id in {origem_id, body.candidato_id} & set(por_id):
        conquistas_restantes = (
            cliente.table("conquista_externa")
            .select(_COLUNAS_CONQUISTA)
            .eq("candidato_id", candidato_id)
            .execute()
            .data
            or []
        )
        # Sem conquista sobrando (origem esvaziada pelo movimento):
        # `_serie_dominante` quebra em lista vazia, e o retrato deixa de
        # importar — o cartão vira candidato a "Remover perfil vazio".
        if conquistas_restantes:
            retrato = _serie_dominante(conquistas_restantes)
            cliente.table("candidato_externo").update(
                {**retrato, "atualizado_em": _agora()}
            ).eq("id", candidato_id).execute()

    auditar(
        cliente,
        "captacao_conquista_movida",
        canal="captacao",
        ator_tipo="coordenador",
        ator_id=coordenador.get("sub"),
        recurso=f"conquista_externa/{body.conquista_id}",
        ip=request.client.host if request.client else None,
        detalhe={
            "conquista_id": body.conquista_id,
            "de": origem_id,
            "para": body.candidato_id,
            "nome_normalizado": destino["nome_normalizado"],
        },
    )
    _agendar_refresh_view_agrupada(tarefas)
    return {"ok": True}


@router.delete("/candidatos/{candidato_id}")
async def remover_candidato_vazio(
    request: Request,
    tarefas: BackgroundTasks,
    candidato_id: str = Path(...),
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Só remove perfil SEM NENHUMA conquista — o que sobra de um "+ Novo
    perfil" nunca usado, ou de um cartão esvaziado por `mover_conquista`.
    Nunca apaga quem tem resultado de verdade; essa guarda é o que torna a
    rota segura de expor num botão de um clique."""
    cliente = get_supabase()
    linhas = (
        cliente.table("v_candidato_externo")
        .select("id, nome_normalizado, conquistas_total")
        .eq("id", candidato_id)
        .limit(1)
        .execute()
        .data
    )
    if not linhas:
        raise HTTPException(status_code=404, detail="Candidato não encontrado")
    candidato = linhas[0]
    if candidato["conquistas_total"] > 0:
        raise HTTPException(
            status_code=409, detail="Este perfil tem conquista — não pode ser removido"
        )

    cliente.table("candidato_externo").delete().eq("id", candidato_id).execute()

    auditar(
        cliente,
        "captacao_perfil_removido",
        canal="captacao",
        ator_tipo="coordenador",
        ator_id=coordenador.get("sub"),
        recurso=f"candidato_externo/{candidato_id}",
        ip=request.client.host if request.client else None,
        detalhe={"nome_normalizado": candidato["nome_normalizado"]},
    )
    _agendar_refresh_view_agrupada(tarefas)
    return {"ok": True}


@router.post("/fusoes/concluir")
async def concluir_fusao(
    body: FusaoBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Fecha um nome depois de mexer nele à mão (mover/criar/remover), em vez
    de confirmar/rejeitar tudo de uma vez. Limpa quem ficou vazio no meio do
    caminho e grava a decisão com o vocabulário que já existe: 1 perfil
    sobrevivente = `confirmada`, 2+ = `rejeitada` — o `detalhe` da auditoria
    guarda a história real (quantos perfis, quais ids), já que o status
    sozinho não distingue "sempre foram 2" de "eram 3, viraram 2 na mão"."""
    cliente = get_supabase()
    candidatos = (
        cliente.table("v_candidato_externo")
        .select("id, conquistas_total")
        .eq("nome_normalizado", body.nome_normalizado)
        .execute()
        .data
        or []
    )
    if not candidatos:
        raise HTTPException(status_code=404, detail="Nenhum candidato com este nome")

    vazios = [c["id"] for c in candidatos if c["conquistas_total"] == 0]
    for candidato_id in vazios:
        cliente.table("candidato_externo").delete().eq("id", candidato_id).execute()

    restantes = [c["id"] for c in candidatos if c["conquistas_total"] > 0]
    status = "confirmada" if len(restantes) <= 1 else "rejeitada"

    cliente.table("candidato_externo_fusao_decisao").upsert(
        {
            "nome_normalizado": body.nome_normalizado,
            "status": status,
            "decidido_por": coordenador.get("nome"),
            "decidido_em": _agora(),
        },
        on_conflict="nome_normalizado",
    ).execute()

    auditar(
        cliente,
        "captacao_fusao_revisada",
        canal="captacao",
        ator_tipo="coordenador",
        ator_id=coordenador.get("sub"),
        recurso=f"candidato_externo_fusao/{body.nome_normalizado}",
        ip=request.client.host if request.client else None,
        detalhe={
            "nome_normalizado": body.nome_normalizado,
            "status": status,
            "perfis_finais": restantes,
            "removidos_vazios": vazios,
        },
    )
    _agendar_refresh_view_agrupada(tarefas)
    return {"status": status, "perfis_finais": len(restantes)}
