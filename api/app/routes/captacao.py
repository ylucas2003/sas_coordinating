"""Captação externa — candidatos achados fora do colégio, cruzando resultado
público de olimpíada/vestibular/concurso (docs/41).

Só leitura + o funil manual (`status_captacao`, `observacoes`). Quem escreve
`prova_externa`/`conquista_externa` de verdade é
`api/scripts/importar_captacao_externa.py`; `candidato_externo` nasce
1:1 por conquista via `api/scripts/resolver_candidatos_externos.py` — esta
rota nunca cria conquista, e só cria/edita `candidato_externo` pelas rotas
explícitas do modo avançado (`criar_perfil`/`mover_conquista`/
`remover_candidato_vazio`), nunca reescrevendo os campos que o resolver
derivou na criação original.

`get_current_coordenador`, e não administrador: é leitura/triagem de lead
sobre gente de FORA do colégio, não acesso a conta ou nota de quem já estuda
aqui — mesma régua de `banco.py`.

⚠️ `candidato_externo` não tem nada a ver com `aluno`. É gente que nunca
colocou os pés no colégio; a migration 0056 explica o porquê das três tabelas.

⚠️ Simplificação de 25/09/2026: não existe mais "fila de fusão" nem decisão
permanente. `candidato_externo_fusao_decisao`/`v_fusao_candidata` marcavam um
nome como "já decidido" e o escondiam PRA SEMPRE — mesmo ganhando conquista
nova depois (achado em produção: "Yan Lucas Freitas de Araújo" tinha 12
`candidato_externo`, nenhum visível em lugar nenhum, porque um script tinha
"decidido" o nome quando só existia 1). Agrupar agora é só manual, sempre
disponível, nunca "concluído": toda conquista nasce com o próprio
`candidato_externo`, e um humano junta duas arrastando em
`CaptacaoPerfil.tsx` (`mover_conquista`). A lista geral
(`GET /captacao/candidatos`) junta por `nome_normalizado` incondicional, via
`v_candidato_externo_por_nome` (migration 0063).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, field_validator

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

# Um candidato_externo por linha — usada pela ficha de um nome (vários por
# vez) e pelas rotas do modo avançado.
_COLUNAS_CANDIDATO = (
    "id, nome, nome_normalizado, escola, cidade, uf, serie_referencia_min, serie_referencia_max, "
    "ano_referencia_serie, status_captacao, observacoes, criado_em, atualizado_em, "
    "conquistas_total, provas_distintas, ano_mais_recente"
)

# Um nome_normalizado por linha — a lista geral (v_candidato_externo_por_nome,
# 0063). Sem `id`: a linha não representa mais um candidato_externo
# específico, é o nome inteiro. escolas/cidades/ufs/status_captacao são
# CONJUNTOS (arrays independentes, não pareados entre si — ver comentário da
# migration).
_COLUNAS_CANDIDATO_POR_NOME = (
    "nome_normalizado, nome, escolas, cidades, ufs, status_captacao, "
    "conquistas_total, provas_distintas, perfis_no_grupo, ano_mais_recente, "
    "criado_em, atualizado_em"
)

_COLUNAS_CONQUISTA = (
    "id, prova_id, ano, nivel_texto, serie_referencia_min, serie_referencia_max, "
    "resultado, nome_informado, escola_informada, cidade_informada, uf_informada, "
    "fonte_url, raspado_em, notas_por_materia"
)


def _agora() -> str:
    return datetime.now(UTC).isoformat()


def _refresh_view_por_nome() -> None:
    """Chamada pelo BackgroundTasks, depois da resposta já ter saído.

    Cliente NOVO (não cacheado), mesmo motivo de
    `gravacoes_aula/rotas.py::_rodada_em_background`: o postgrest-py força
    HTTP/2 numa conexão só por client, e um GOAWAY nesta chamada (o refresh
    sozinho já leva ~1s, medido) não pode abortar as streams de alguma outra
    requisição que esteja usando o client cacheado ao mesmo tempo.

    Erro aqui é engolido (CLAUDE.md: "erro em caminho de auditoria ou
    telemetria é engolido") — é uma view de LEITURA em cache, não o dado em
    si; se falhar, a lista geral só fica desatualizada até o próximo refresh.
    """
    try:
        criar_cliente_supabase().rpc("atualizar_v_candidato_externo_por_nome", {}).execute()
    except Exception:
        _log.warning("Falha ao atualizar v_candidato_externo_por_nome", exc_info=True)


def _agendar_refresh_view_por_nome(tarefas: BackgroundTasks) -> None:
    """Toda rota que escreve em candidato_externo/conquista_externa chama
    isto antes de devolver a resposta — a view por nome (0063) é
    MATERIALIZADA por custo (~1,3s pra recalcular do zero, medido) e não
    acompanha a escrita sozinha."""
    tarefas.add_task(_refresh_view_por_nome)


class NomeNormalizadoBody(BaseModel):
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
    uf: str | None = Query(None, description="sigla, ex.: 'CE' — bate se QUALQUER conquista do nome tiver essa UF"),
    status_captacao: str | None = Query(None, description="bate se QUALQUER perfil do nome tiver esse status"),
    conquistas_min: int | None = Query(
        None, ge=1, description="nº mínimo de conquistas cruzadas — o sinal mais forte de lead"
    ),
    busca: str | None = Query(None, description="texto no nome"),
    pagina: int = Query(1, ge=1, description="1-based, como a URL mostra"),
    por_pagina: int = Query(POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> dict:
    """Página de NOMES (não de candidato_externo), de quem mais cruzou
    conquista pra quem menos — é a ordem que separa lead forte de aparição
    única. Cada nome vira UMA linha sempre, incondicional, mesmo quando por
    baixo tem vários `candidato_externo` ainda não arrumados à mão
    (`perfis_no_grupo` diz quantos) — quem está caçando lead não devia ver a
    fragmentação interna do resolver.

    **Paginação de verdade**, ao contrário do resto do sistema (CLAUDE.md,
    armadilha 2). Lá o teto é proibido porque truncaria leitura ESTATÍSTICA em
    silêncio; aqui a resposta é navegação sobre gente de fora, sem o teto
    natural dos ~900 alunos — mais de 100 mil nomes e crescendo a cada fonte
    nova.
    """
    if status_captacao is not None and status_captacao not in STATUS_CAPTACAO:
        raise HTTPException(
            status_code=400, detail=f"status_captacao deve ser um de {STATUS_CAPTACAO}"
        )

    cliente = get_supabase()
    consulta = cliente.table("v_candidato_externo_por_nome").select(
        _COLUNAS_CANDIDATO_POR_NOME, count="exact"
    )
    if uf:
        # .contains() -> `ufs=cs.{CE}` -> operador @> do Postgres (índice
        # GIN, migration 0063) — bate se a UF estiver em QUALQUER conquista
        # do nome, não só numa escolhida por heurística.
        consulta = consulta.contains("ufs", [uf.upper()])
    if status_captacao:
        consulta = consulta.contains("status_captacao", [status_captacao])
    if conquistas_min is not None:
        consulta = consulta.gte("conquistas_total", conquistas_min)
    if busca and busca.strip():
        consulta = consulta.ilike("nome", f"%{busca.strip()}%")

    # nome_normalizado no fim do `order`: é a chave única da linha (a view
    # agrupa por ele), então basta como critério de desempate total — ao
    # contrário da view antiga, não precisa mais de um `id` de representante.
    inicio = (pagina - 1) * por_pagina
    resposta = (
        consulta.order("conquistas_total", desc=True)
        .order("nome_normalizado")
        .range(inicio, inicio + por_pagina - 1)
        .execute()
    )
    linhas = resposta.data or []
    total = int(resposta.count) if resposta.count is not None else len(linhas)
    return {"candidatos": linhas, "total": total, "pagina": pagina, "por_pagina": por_pagina}


@router.get("/provas")
async def listar_provas() -> dict:
    """Uma linha por prova (ITA, IME, OBMEP...) com o intervalo de anos
    carregado — o rodapé "quais fontes alimentam esta lista" de
    `Captacao.tsx`. 10 linhas hoje, sem paginação."""
    cliente = get_supabase()
    provas = (
        cliente.table("v_prova_externa_resumo")
        .select("nome, categoria, ano_min, ano_max, conquistas_total")
        .order("categoria")
        .order("nome")
        .execute()
        .data
        or []
    )
    return {"provas": provas}


@router.get("/perfis/{nome_normalizado}")
async def obter_perfis_do_nome(nome_normalizado: str = Path(...)) -> dict:
    """Todo `candidato_externo` com este nome, cada um com as próprias
    conquistas — a ficha de QUALQUER nome (não só "casos em disputa": com
    tudo nascendo 1:1, a maioria dos nomes tem exatamente 1 perfil, e
    `CaptacaoPerfil.tsx` precisa abrir pra ele do mesmo jeito)."""
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
    if not candidatos:
        raise HTTPException(status_code=404, detail="Nenhum candidato com este nome")

    conquistas = (
        cliente.table("conquista_externa")
        .select(f"candidato_id, {_COLUNAS_CONQUISTA}")
        .in_("candidato_id", [c["id"] for c in candidatos])
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


@router.patch("/candidatos/{candidato_id}")
async def atualizar_candidato(
    body: AtualizarCandidatoBody,
    request: Request,
    tarefas: BackgroundTasks,
    candidato_id: str = Path(...),
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Só `status_captacao` e `observacoes` — o funil manual da coordenação
    (0056 §3), editado direto em cada cartão de `CaptacaoPerfil.tsx`. Os
    outros campos são derivados: só
    `api/scripts/resolver_candidatos_externos.py` e as rotas do modo
    avançado escrevem neles."""
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

    _agendar_refresh_view_por_nome(tarefas)
    return atualizado[0]


# ─── Modo avançado: agrupar é sempre manual (simplificação de 25/09/2026) ──
#
# Nenhum agrupamento automático mais — resolver_candidatos_externos.py cria
# 1 candidato_externo por conquista, sempre. As três rotas abaixo são a
# ÚNICA forma de duas conquistas virarem "a mesma pessoa": mover uma pro
# perfil da outra. Não existe "decisão" nem "concluir" — cada arraste já
# persiste na hora, sozinho; a lista geral (v_candidato_externo_por_nome)
# só reflete o estado atual, sem nada permanente pra desfazer.


def _serie_dominante(conquistas: list[dict]) -> dict:
    """O retrato (nome/escola/cidade/uf/série) da conquista mais RECENTE
    entre as de um candidato — mesma regra de
    `scripts/_captacao_comum.py::retrato_da_conquista`, aplicada aqui pra um
    GRUPO (depois de `mover_conquista`, um candidato pode ter mais de uma),
    pro candidato não ficar com um retrato de anos atrás."""
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


@router.post("/perfis/criar")
async def criar_perfil(
    body: NomeNormalizadoBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Perfil novo, vazio, com o mesmo nome — pra arrastar pra dentro dele um
    resultado que na verdade é de outra pessoa (homônimo). O retrato
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
    _agendar_refresh_view_por_nome(tarefas)
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
    _agendar_refresh_view_por_nome(tarefas)
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
    _agendar_refresh_view_por_nome(tarefas)
    return {"ok": True}
