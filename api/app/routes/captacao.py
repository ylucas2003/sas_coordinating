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
"decidido" o nome quando só existia 1). Agrupar continua manual (o coordenador
sempre pode separar arrastando em `CaptacaoPerfil.tsx`, `mover_conquista`), e
nunca "concluído" — não há decisão permanente pra registrar. A lista geral
(`GET /captacao/candidatos`) junta por `nome_normalizado` incondicional, via
`v_candidato_externo_por_nome` (migration 0063).

⚠️ Ajuste de 28/09/2026 (docs/41 §16): o DEFAULT voltou a ser 1
`candidato_externo` por NOME, não por conquista —
`resolver_candidatos_externos.py` anexa conquista nova ao perfil já existente
do nome (`scripts/_captacao_comum.py::retrato_dominante`), e só cria perfil
novo pra nome nunca visto. Isso não reabre o bug de 25/09: continua sem
tabela de decisão, a lista geral continua incondicional, e separar continua
manual e reversível a qualquer momento.

Caminho inverso (07/10/2026, docs/41 §20): além de nome → conquistas, a lista
acha nome A PARTIR de conquista — prova, faixa, ano e público (Fundamental 2,
Médio, Pré-vestibular), todos valendo para a MESMA conquista. Quando algum
desses critérios vem, `listar_candidatos` chama a função
`buscar_candidatos_por_conquista` (0068) por RPC em vez de ler a view.

Handlers são `def`, e não `async def`: o cliente PostgREST é síncrono, e um
`async def` rodaria cada `.execute()` no event loop (api/CLAUDE.md,
convenção de 29/09/2026) — a busca, com `count="exact"`, travava o processo
inteiro a cada tecla digitada.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, field_validator

from scripts._captacao_comum import FAIXAS, normalizar_nome, retrato_dominante

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

# Público da captação (decisão de 07/10/2026): Fundamental 2, Médio e
# Pré-vestibular. A tradução pra ano de conclusão mora na função da 0068.
PUBLICOS = ("fundamental", "medio", "pre_vestibular")

# Mesmo fuso de `banco/missao.py` — a "virada do ano" é a do colégio.
_FUSO_DA_ESCOLA = ZoneInfo("America/Fortaleza")


def _ano_ingresso_padrao() -> int:
    """Captação é pra turma do ANO QUE VEM — em outubro ninguém mais entra na
    turma deste ano. O público é calculado pra esse ano (docs/41 §20)."""
    return datetime.now(_FUSO_DA_ESCOLA).year + 1

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
    "conquistas_total, provas_distintas, participacoes, perfis_no_grupo, ano_mais_recente, "
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
    """status_captacao/observacoes são o funil manual (0056 §3). escola/
    cidade/uf também são editáveis (docs/41 §17) — mas editar qualquer um
    dos três TRAVA o retrato inteiro (`retrato_editado_a_mao`): a partir daí,
    `mover_conquista` e o resolver param de recalcular esses campos pra este
    perfil, mesmo ganhando conquista nova depois. serie_referencia_*/
    ano_referencia_serie continuam só derivados — não têm campo aqui."""

    status_captacao: str | None = None
    observacoes: str | None = None
    escola: str | None = None
    cidade: str | None = None
    uf: str | None = None

    @field_validator("status_captacao")
    @classmethod
    def _status_conhecido(cls, v: str | None) -> str | None:
        if v is not None and v not in STATUS_CAPTACAO:
            raise ValueError(f"status_captacao deve ser um de {STATUS_CAPTACAO}")
        return v


def _recusar_fora_do_vocabulario(nome: str, valores: list[str] | None, vocabulario: tuple[str, ...]) -> None:
    """400 em vez de um filtro que não casa com nada em silêncio (ou um 23514
    do Postgres por trás do PostgREST) — mesmo motivo de `STATUS_CAPTACAO`."""
    desconhecidos = [v for v in valores or [] if v not in vocabulario]
    if desconhecidos:
        raise HTTPException(status_code=400, detail=f"{nome} deve ser um de {vocabulario}")


@router.get("/candidatos")
def listar_candidatos(
    uf: str | None = Query(None, description="sigla, ex.: 'CE' — bate se QUALQUER conquista do nome tiver essa UF"),
    status_captacao: str | None = Query(None, description="bate se QUALQUER perfil do nome tiver esse status"),
    conquistas_min: int | None = Query(
        None, ge=1, description="nº mínimo de conquistas cruzadas — o sinal mais forte de lead"
    ),
    busca: str | None = Query(None, description="texto no nome — sem diferença de acento nem de maiúscula"),
    prova: list[str] | None = Query(None, description="nome da prova (OBMEP, ITA...) — repetível"),
    faixa: list[str] | None = Query(None, description=f"repetível, um de {FAIXAS}"),
    ano_min: int | None = Query(None, ge=1990, le=2100, description="ano da conquista, desde"),
    ano_max: int | None = Query(None, ge=1990, le=2100, description="ano da conquista, até"),
    publico: list[str] | None = Query(None, description=f"repetível, um de {PUBLICOS}"),
    ano_ingresso: int | None = Query(
        None, ge=2000, le=2100, description="ano letivo de referência do público — padrão: o ano que vem"
    ),
    pagina: int = Query(1, ge=1, description="1-based, como a URL mostra"),
    por_pagina: int = Query(POR_PAGINA_PADRAO, ge=1, le=POR_PAGINA_MAXIMO),
) -> dict:
    """Página de NOMES (não de candidato_externo). Cada nome vira UMA linha
    sempre, incondicional, mesmo quando por baixo tem vários
    `candidato_externo` ainda não arrumados à mão (`perfis_no_grupo` diz
    quantos) — quem está caçando lead não devia ver a fragmentação interna do
    resolver.

    Dois caminhos, a mesma resposta:
    - **sem critério de conquista**: a view por nome, de quem mais cruzou
      conquista pra quem menos — participação (1ª fase do ITA) não conta
      (0068);
    - **com prova/faixa/ano/público**: a função `buscar_candidatos_por_conquista`
      (0068), que exige que UMA MESMA conquista case todos esses critérios e
      devolve, em `evidencias`, as que fizeram o nome entrar.

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
    _recusar_fora_do_vocabulario("faixa", faixa, FAIXAS)
    _recusar_fora_do_vocabulario("publico", publico, PUBLICOS)

    # Busca pelo nome NORMALIZADO, com o termo normalizado do mesmo jeito: quem
    # digita "Goncalves" acha "Gonçalves". `%`/`_` saem porque são curinga do
    # LIKE, não letra de nome.
    termo = normalizar_nome(busca).replace("%", "").replace("_", "") if busca else ""
    ingresso = ano_ingresso or _ano_ingresso_padrao()
    inicio = (pagina - 1) * por_pagina
    cliente = get_supabase()

    if prova or faixa or ano_min is not None or ano_max is not None or publico:
        linhas = (
            cliente.rpc(
                "buscar_candidatos_por_conquista",
                {
                    "p_provas": prova or None,
                    "p_faixas": faixa or None,
                    "p_ano_min": ano_min,
                    "p_ano_max": ano_max,
                    "p_publicos": publico or None,
                    "p_ano_ingresso": ingresso,
                    "p_uf": uf.upper() if uf else None,
                    "p_status": status_captacao,
                    "p_conquistas_min": conquistas_min,
                    "p_busca": termo or None,
                    "p_limite": por_pagina,
                    "p_deslocamento": inicio,
                },
            )
            .execute()
            .data
            or []
        )
        # O total vem repetido em toda linha (window antes do LIMIT, 0068) —
        # sai daqui pra não viajar 20 vezes pro front.
        total = int(linhas[0]["total_filtrado"]) if linhas else 0
        for linha in linhas:
            linha.pop("total_filtrado", None)
        return {
            "candidatos": linhas,
            "total": total,
            "pagina": pagina,
            "por_pagina": por_pagina,
            "ano_ingresso": ingresso,
        }

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
    if termo:
        consulta = consulta.ilike("nome_normalizado", f"%{termo}%")

    # nome_normalizado no fim do `order`: é a chave única da linha (a view
    # agrupa por ele), então basta como critério de desempate total — ao
    # contrário da view antiga, não precisa mais de um `id` de representante.
    resposta = (
        consulta.order("conquistas_total", desc=True)
        .order("nome_normalizado")
        .range(inicio, inicio + por_pagina - 1)
        .execute()
    )
    linhas = resposta.data or []
    total = int(resposta.count) if resposta.count is not None else len(linhas)
    return {
        "candidatos": linhas,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "ano_ingresso": ingresso,
    }


@router.get("/provas")
def listar_provas() -> dict:
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
def obter_perfis_do_nome(nome_normalizado: str = Path(...)) -> dict:
    """Todo `candidato_externo` com este nome, cada um com as próprias
    conquistas — a ficha de QUALQUER nome (não só "casos em disputa": com o
    default sendo 1 perfil por nome (docs/41 §16), a maioria já tem
    exatamente 1, e `CaptacaoPerfil.tsx` precisa abrir pra ele do mesmo
    jeito)."""
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
def atualizar_candidato(
    body: AtualizarCandidatoBody,
    request: Request,
    tarefas: BackgroundTasks,
    candidato_id: str = Path(...),
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """`status_captacao`/`observacoes` são o funil manual (0056 §3).
    escola/cidade/uf também são editáveis (docs/41 §17) — editar qualquer um
    dos três marca `retrato_editado_a_mao=true`, travando o retrato pra
    `mover_conquista`/o resolver não recalcularem mais em cima da edição."""
    if all(
        v is None
        for v in (body.status_captacao, body.observacoes, body.escola, body.cidade, body.uf)
    ):
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
    if body.escola is not None or body.cidade is not None or body.uf is not None:
        if body.escola is not None:
            patch["escola"] = body.escola
        if body.cidade is not None:
            patch["cidade"] = body.cidade
        if body.uf is not None:
            patch["uf"] = body.uf
        patch["retrato_editado_a_mao"] = True

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


# ─── Modo avançado: separar continua sempre manual ─────────────────────────
#
# Desde 28/09/2026 o resolver pode anexar conquista nova a um perfil já
# existente do nome (docs/41 §16) — mas juntar duas conquistas que já
# nasceram em perfis DIFERENTES continua exigindo as três rotas abaixo: mover
# uma pro perfil da outra. Não existe "decisão" nem "concluir" — cada arraste
# já persiste na hora, sozinho; a lista geral (v_candidato_externo_por_nome)
# só reflete o estado atual, sem nada permanente pra desfazer.


@router.post("/perfis/criar")
def criar_perfil(
    body: NomeNormalizadoBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Perfil novo, vazio, com o mesmo nome — pra arrastar pra dentro dele um
    resultado que na verdade é de outra pessoa (homônimo). O retrato
    (escola/cidade/UF) fica em branco: assim que uma conquista for movida
    pra cá, `mover_conquista` recalcula com `retrato_dominante`."""
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
def mover_conquista(
    body: MoverConquistaBody,
    request: Request,
    tarefas: BackgroundTasks,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Reatribui UM resultado pra outro perfil do mesmo nome — o coração do
    modo avançado. Recalcula o retrato de quem ganhou e de quem perdeu a
    conquista (se ainda sobrar alguma), pra nenhum dos dois ficar com um
    retrato de anos atrás depois do reagrupamento — EXCETO quem tem
    `retrato_editado_a_mao` (docs/41 §17): um humano já corrigiu esse
    perfil, então o recálculo automático não pisa em cima da edição."""
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
        .select("id, nome_normalizado, retrato_editado_a_mao")
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
        if por_id[candidato_id].get("retrato_editado_a_mao"):
            continue  # travado — a edição manual vale mais que o recálculo

        conquistas_restantes = (
            cliente.table("conquista_externa")
            .select(_COLUNAS_CONQUISTA)
            .eq("candidato_id", candidato_id)
            .execute()
            .data
            or []
        )
        # Sem conquista sobrando (origem esvaziada pelo movimento):
        # `retrato_dominante` quebra em lista vazia, e o retrato deixa de
        # importar — o cartão vira candidato a "Remover perfil vazio".
        if conquistas_restantes:
            retrato = retrato_dominante(conquistas_restantes)
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
def remover_candidato_vazio(
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
