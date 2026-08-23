"""HTTP do banco de questões ITA · IME (docs/22 §P2).

Só fronteira: valida a entrada, resolve o dono da sessão, chama o domínio em
`app/banco/` e devolve. Nenhuma agregação e nenhum filtro moram aqui
(docs/22 §7.2) — é o que permite testar recorrência, paginação e lista sem
subir a API.

Quem enxerga o quê:

  * **taxonomia, questões e estatísticas** valem para os dois perfis: é
    conteúdo público de prova, sem dado pessoal (docs/22 §2.3). Para o aluno as
    questões voltam com o estado de estudo DELE anexado; para a coordenação
    voltam com `None`, que é diferente de `false` — um diz "este perfil não tem
    estudo", o outro diz "este aluno não resolveu" (`consultas.anexar_estudo`).
  * **lista** e **estudo** têm dono, e o dono é sempre o da sessão. Nunca vem da
    URL nem do corpo.

⚠️ `questao_vestibular` é questão de PROVA PASSADA de ITA/IME. A questão de
simulado-Quiz do Canvas é `questao` (migration 0010) e não tem nada a ver — é o
erro de leitura mais provável do schema hoje (api/CLAUDE.md).
"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from supabase import Client

from ..auth import get_current_aluno, get_current_user
from ..banco import consultas, estatisticas, listas
from ..schemas.banco import (
    AtualizarEstudo,
    AtualizarLista,
    CriarLista,
    DonoLista,
    EstatisticasBanco,
    EstudoQuestao,
    Lista,
    ListaResumo,
    MateriaBanco,
    PaginaQuestoes,
    QuestaoVestibular,
    TaxonomiaMateria,
    VestibularBanco,
)
from ..supabase_client import get_supabase

router = APIRouter(prefix="/banco", tags=["banco"])


# ─── Dono da sessão e erros ──────────────────────────────────────────────


def _dono(user: dict) -> tuple[DonoLista, str]:
    """O par `(dono_tipo, dono_id)` da sessão — a única origem de dono do módulo.

    Sai do token e nunca da URL nem do corpo: é o que garante que ninguém monte
    ou leia lista em nome de outra pessoa (docs/22 §5.2).

    A tradução `'coordenador'` → `'coordenacao'` acontece aqui e só aqui: o token
    nomeia a PESSOA (auth.py) e o CHECK da 0029 nomeia o LADO a que a lista
    pertence. São duas palavras porque são duas coisas.
    """
    dono_tipo: DonoLista = "aluno" if user.get("tipo") == "aluno" else "coordenacao"
    return dono_tipo, str(user["sub"])


def _lista_ou_404(lista: Lista | None) -> Lista:
    """Lista inexistente e lista de outro dono dão o MESMO 404, nunca 403.

    Distinguir os dois seria mais informativo do que se quer ser: o 403
    confirmaria a existência da lista alheia para quem estivesse varrendo uuids
    (docs/22 §5.2). O domínio já devolve `None` para os dois casos de propósito
    — ver `listas._linha_da_lista`.
    """
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista não encontrada")
    return lista


def _titulo_ou_400(titulo: str) -> str:
    """Título só de espaço viraria uma lista sem nome na tela, impossível de
    distinguir das outras. O domínio faz o `strip`; quem recusa o vazio é aqui."""
    limpo = titulo.strip()
    if not limpo:
        raise HTTPException(status_code=400, detail="O título da lista não pode ser vazio")
    return limpo


def _com_estudo_do_aluno(
    cliente: Client, user: dict, questoes: Sequence[QuestaoVestibular]
) -> list[QuestaoVestibular]:
    """Anexa `resolvida`/`anotacao` quando quem pede é aluno (docs/22 §P6).

    Uma leitura do estudo por resposta, não uma por questão: a página inteira é
    resolvida com a mesma consulta.

    Não vale para as rotas de lista, e é decisão do domínio: a lista serve os
    dois perfis e o estudo é de UM aluno, então quem quer o estado pede
    `GET /banco/estudo` (`listas._questoes_por_id`).
    """
    if user.get("tipo") != "aluno" or not questoes:
        return list(questoes)
    estudo = {item.questaoId: item for item in listas.listar_estudo(cliente, user["aluno_id"])}
    return consultas.anexar_estudo(questoes, estudo)


# ─── Leitura: vale para os dois perfis (docs/22 §2.3) ────────────────────


@router.get(
    "/taxonomia",
    response_model=list[TaxonomiaMateria],
    dependencies=[Depends(get_current_user)],
)
async def obter_taxonomia(
    materia: MateriaBanco | None = Query(None, description="omitida, devolve as três"),
) -> list[TaxonomiaMateria]:
    """Árvore bloco → tópico do edital, com a contagem de questões em cada nível."""
    return consultas.listar_taxonomia(get_supabase(), materia)


@router.get("/questoes", response_model=PaginaQuestoes)
async def listar_questoes(
    materia: MateriaBanco | None = Query(None),
    vestibular: VestibularBanco | None = Query(None),
    ano: int | None = Query(None),
    fase: int | None = Query(None),
    topico: str | None = Query(
        None,
        description=(
            "código do edital, ex.: '7.2' — exige `materia`. "
            f"'{consultas.TOPICO_SEM_CLASSIFICACAO}' traz as que ninguém classificou"
        ),
    ),
    busca: str | None = Query(None, description="texto no enunciado"),
    pagina: int = Query(1, ge=1, description="1-based, como a URL mostra"),
    # O teto é o do domínio, não uma cópia: duplicar o número aqui o deixaria
    # envelhecer em dois lugares. `le` e não clamp silencioso — pedir 500 e
    # receber 100 sem aviso é o tipo de coisa que o front descobre tarde.
    por_pagina: int = Query(
        consultas.POR_PAGINA_PADRAO,
        ge=1,
        le=consultas.POR_PAGINA_MAXIMO,
        alias="porPagina",
    ),
    user: dict = Depends(get_current_user),
) -> PaginaQuestoes:
    """Página filtrada de questões. **A única rota paginada do projeto.**

    Isso não contradiz a armadilha 2 do CLAUDE.md: lá o teto é proibido porque
    truncar leitura ESTATÍSTICA devolve número errado sem parecer errado. Aqui a
    resposta é navegação, e uma página é resposta completa da pergunta feita
    (docs/22 §2.2). Quem agrega — `/banco/estatisticas` — nunca pagina. Não
    "conserte" tirando a paginação daqui nem pondo teto lá.
    """
    if topico and topico != consultas.TOPICO_SEM_CLASSIFICACAO and not materia:
        # '1.1' existe nas três matérias e significa coisa diferente em cada uma
        # — "Fundamentos", "Conjuntos e Lógica", "Estrutura Atômica" (0028).
        # Sem `materia` o filtro juntaria as três em silêncio, e o aluno leria
        # um recorte errado sem erro nenhum na tela.
        raise HTTPException(
            status_code=400,
            detail="Filtrar por tópico exige `materia`: o mesmo código existe nas três matérias",
        )

    cliente = get_supabase()
    pagina_de_questoes = consultas.listar_questoes(
        cliente,
        consultas.FiltrosQuestoes(
            materia=materia,
            vestibular=vestibular,
            ano=ano,
            fase=fase,
            topico=topico,
            busca=busca,
            pagina=pagina,
            por_pagina=por_pagina,
        ),
    )
    pagina_de_questoes.questoes = _com_estudo_do_aluno(
        cliente, user, pagina_de_questoes.questoes
    )
    return pagina_de_questoes


@router.get("/questoes/{questao_id}", response_model=QuestaoVestibular)
async def obter_questao(
    questao_id: str = Path(..., description="id legível, ex.: 'ita_2019_fase1_q01'"),
    user: dict = Depends(get_current_user),
) -> QuestaoVestibular:
    cliente = get_supabase()
    questao = consultas.obter_questao(cliente, questao_id)
    if questao is None:
        raise HTTPException(status_code=404, detail="Questão não encontrada")
    return _com_estudo_do_aluno(cliente, user, [questao])[0]


@router.get(
    "/estatisticas",
    response_model=EstatisticasBanco,
    dependencies=[Depends(get_current_user)],
)
async def obter_estatisticas(
    # Obrigatória: a recorrência é de UMA matéria, e os códigos de tópico se
    # repetem entre elas (0028) — uma resposta com as três somaria "1.1" de
    # Física com "1.1" de Química e o número não significaria nada.
    materia: MateriaBanco = Query(...),
    vestibular: VestibularBanco | None = Query(None, description="omitido, soma ITA e IME"),
) -> EstatisticasBanco:
    """Recorrência de cada tópico do edital, por ano, por fase e por vestibular.

    Agrega sobre a tabela inteira e **nunca pagina** — ver o docstring de
    `listar_questoes` e docs/22 §2.2.
    """
    return estatisticas.recorrencia(get_supabase(), materia, vestibular)


# ─── Listas: têm dono, e o dono é o da sessão (docs/22 §P5) ──────────────


@router.get("/listas", response_model=list[ListaResumo])
async def listar_listas(user: dict = Depends(get_current_user)) -> list[ListaResumo]:
    """Só as listas do dono da sessão, da mexida mais recente para a mais antiga."""
    dono_tipo, dono_id = _dono(user)
    return listas.listar(get_supabase(), dono_tipo, dono_id)


@router.post("/listas", response_model=Lista, status_code=201)
async def criar_lista(body: CriarLista, user: dict = Depends(get_current_user)) -> Lista:
    dono_tipo, dono_id = _dono(user)
    return listas.criar(get_supabase(), dono_tipo, dono_id, _titulo_ou_400(body.titulo))


@router.get("/listas/{lista_id}", response_model=Lista)
async def obter_lista(
    lista_id: str = Path(...), user: dict = Depends(get_current_user)
) -> Lista:
    dono_tipo, dono_id = _dono(user)
    return _lista_ou_404(listas.obter(get_supabase(), lista_id, dono_tipo, dono_id))


@router.patch("/listas/{lista_id}", response_model=Lista)
async def atualizar_lista(
    body: AtualizarLista,
    lista_id: str = Path(...),
    user: dict = Depends(get_current_user),
) -> Lista:
    """Renomeia e/ou substitui a ordem inteira (`questaoIds` é a lista completa,
    não um patch — docs/22 §P5). Corpo vazio é engano de quem chamou, não no-op:
    um PATCH que não pede nada só tocaria `atualizada_em` e reordenaria a tela."""
    if body.titulo is None and body.questaoIds is None:
        raise HTTPException(status_code=400, detail="Nada a atualizar")

    titulo = _titulo_ou_400(body.titulo) if body.titulo is not None else None
    dono_tipo, dono_id = _dono(user)
    try:
        lista = listas.atualizar(
            get_supabase(),
            lista_id,
            dono_tipo,
            dono_id,
            titulo=titulo,
            questao_ids=body.questaoIds,
        )
    except ValueError as exc:
        # `ValueError` do domínio é sempre "citou questão que não existe" — e a
        # mensagem nomeia os ids. 400 e não 404: nesta rota o 404 já significa
        # "lista não é sua", e reusá-lo apagaria a diferença entre errar a lista
        # e errar a questão. O domínio valida ANTES do DELETE dos itens, então a
        # lista não fica vazia por causa deste erro.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _lista_ou_404(lista)


# `response_model=None` explícito: sem ele o FastAPI infere o modelo a partir do
# `-> None` do handler, entende `NoneType` como "tem corpo" e recusa o 204.
@router.delete("/listas/{lista_id}", status_code=204, response_model=None)
async def remover_lista(
    lista_id: str = Path(...), user: dict = Depends(get_current_user)
) -> None:
    dono_tipo, dono_id = _dono(user)
    if not listas.remover(get_supabase(), lista_id, dono_tipo, dono_id):
        raise HTTPException(status_code=404, detail="Lista não encontrada")


@router.post("/listas/{lista_id}/questoes/{questao_id}", response_model=Lista)
async def adicionar_questao_na_lista(
    lista_id: str = Path(...),
    questao_id: str = Path(...),
    user: dict = Depends(get_current_user),
) -> Lista:
    """Põe a questão no fim da lista. Adicionar de novo é no-op, não erro."""
    dono_tipo, dono_id = _dono(user)
    try:
        lista = listas.adicionar_questao(
            get_supabase(), lista_id, dono_tipo, dono_id, questao_id
        )
    except ValueError as exc:
        # Mesma separação do PATCH: 404 é da lista, 400 é da questão. O domínio
        # confere o dono ANTES da questão, então este 400 nunca conta a ninguém
        # que a lista alheia existe.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _lista_ou_404(lista)


@router.delete("/listas/{lista_id}/questoes/{questao_id}", response_model=Lista)
async def remover_questao_da_lista(
    lista_id: str = Path(...),
    questao_id: str = Path(...),
    user: dict = Depends(get_current_user),
) -> Lista:
    """Tira a questão da lista. Tirar o que já não está é no-op, não erro."""
    dono_tipo, dono_id = _dono(user)
    return _lista_ou_404(
        listas.remover_questao(get_supabase(), lista_id, dono_tipo, dono_id, questao_id)
    )


# ─── Estudo: só aluno (docs/22 §P6) ──────────────────────────────────────


@router.get("/estudo", response_model=list[EstudoQuestao])
async def listar_estudo(user: dict = Depends(get_current_aluno)) -> list[EstudoQuestao]:
    """O que este aluno marcou ou anotou. Questão sem linha = não tocada."""
    return listas.listar_estudo(get_supabase(), user["aluno_id"])


@router.put("/estudo/{questao_id}", response_model=EstudoQuestao)
async def atualizar_estudo(
    body: AtualizarEstudo,
    questao_id: str = Path(...),
    user: dict = Depends(get_current_aluno),
) -> EstudoQuestao:
    """Marca resolvida e/ou anota. Campo ausente não é mexido; `anotacao: ""`
    limpa a anotação (`listas.atualizar_estudo`)."""
    try:
        return listas.atualizar_estudo(
            get_supabase(),
            user["aluno_id"],
            questao_id,
            resolvida=body.resolvida,
            anotacao=body.anotacao,
        )
    except ValueError as exc:
        # Aqui o 404 é o certo, ao contrário das rotas de lista: a questão é o
        # único recurso citado na URL, então não há o que confundir.
        raise HTTPException(status_code=404, detail=str(exc)) from exc
