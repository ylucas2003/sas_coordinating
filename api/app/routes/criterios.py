"""Réguas de corte criadas pela coordenação (docs/31 §P4).

O pedido é o de [18 §1.10]: *"criar rotas e UI para o coordenador criar filtros
— por exemplo, nota 7 em Mat/Fís/Quím e maior que 4 em Português"*. O formato
nasceu pronto na Sprint 2 (`Criterio`, `Predicado`, o avaliador e as tabelas da
0023); o que faltava era exatamente isto — as rotas — mais o leitor
(`stats/criterios_repo.py`) e a tela.

Três decisões que estas rotas materializam:

  **Critério é imutável.** `PATCH` não altera linha nenhuma: grava a versão
  seguinte e desativa a anterior. Sem isso, editar uma régua mudaria
  retroativamente os números de quem já a usou, em silêncio.

  **Embutida não se edita nem se apaga.** As cinco do arquivo são a régua do
  colégio e as dos dois editais; a tabela guarda uma cópia como semente e o
  arquivo é quem vence.

  **A prévia avalia sem gravar.** Sem ela, ver "quantos seriam cortados" exigia
  criar-e-apagar — sujando a auditoria e o versionamento para responder uma
  pergunta que é de rascunho.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..auditoria import registrar as auditar
from ..auth import get_current_coordenador
from ..stats import classificacao_ciclo, criterios_repo
from ..supabase_client import get_supabase

router = APIRouter(
    prefix="/criterios",
    tags=["criterios"],
    dependencies=[Depends(get_current_coordenador)],
)


class PredicadoEntrada(BaseModel):
    """Um requisito. Ou nota, ou 'N de M acertos' — nunca os dois (0023)."""

    materia: str | None = Field(
        default=None,
        description="Código da matéria, '*' para qualquer disciplina, 'fase_1', ou vazio para a média geral.",
    )
    operador: str = ">="
    valor_nota: float | None = None
    valor_acertos: int | None = None
    valor_de: int | None = None
    eliminatorio: bool = False
    entra_na_media: bool = True
    peso: float = 1.0
    fonte: str | None = Field(default=None, max_length=200)


class CriterioEntrada(BaseModel):
    slug: str = Field(max_length=64)
    nome: str = Field(max_length=120)
    descricao: str | None = Field(default=None, max_length=500)
    combinador: str = Field(description="'todos' = corta só se TODOS falharem; 'algum' = basta um.")
    fase: int | None = None
    desempate: list[str] = Field(default_factory=lambda: ["media"])
    predicados: list[PredicadoEntrada]


class CriterioEdicao(BaseModel):
    """Igual à entrada, sem o slug: renomear o identificador criaria outra régua."""

    nome: str = Field(max_length=120)
    descricao: str | None = Field(default=None, max_length=500)
    combinador: str
    fase: int | None = None
    desempate: list[str] = Field(default_factory=lambda: ["media"])
    predicados: list[PredicadoEntrada]


def _ator(coordenador: dict) -> str | None:
    return coordenador.get("sub")


def _422(exc: criterios_repo.CriterioInvalido) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.get("")
async def listar_criterios() -> list[dict]:
    """As réguas disponíveis, embutidas e criadas, com os cortes resolvidos."""
    from .ciclos import _descrever_criterio

    cliente = get_supabase()
    return [
        {**_descrever_criterio(c), "embutido": c.slug in _slugs_embutidos()}
        for c in criterios_repo.listar(cliente)
    ]


def _slugs_embutidos() -> frozenset[str]:
    from ..stats import criterios as mod

    return frozenset(mod.CRITERIOS)


@router.get("/{slug}")
async def obter_criterio(slug: str) -> dict:
    """Uma régua, com o histórico de versões quando foi criada pela coordenação."""
    from .ciclos import _descrever_criterio

    cliente = get_supabase()
    try:
        regua = criterios_repo.resolver(cliente, slug)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    embutido = slug in _slugs_embutidos()
    historico = [] if embutido else [
        {
            "versao": l.get("versao"),
            "ativo": l.get("ativo"),
            "criadoEm": l.get("criado_em"),
            "criadoPor": l.get("criado_por"),
        }
        for l in criterios_repo.versoes(cliente, slug)
    ]
    return {**_descrever_criterio(regua), "embutido": embutido, "versoes": historico}


@router.post("/previa")
async def previa_do_criterio(
    body: CriterioEntrada,
    ciclo_id: str = Query(..., description="Ciclo contra o qual simular a régua."),
    fase: int | None = Query(None, ge=1, le=2),
) -> dict:
    """Quantos alunos esta régua cortaria — sem gravar nada.

    É o que impede alguém de digitar 7 onde queria 4 e só descobrir depois de
    a régua já estar valendo e versionada.
    """
    payload = body.model_dump()
    try:
        criterios_repo.validar(payload)
    except criterios_repo.CriterioInvalido as exc:
        raise _422(exc) from exc

    cliente = get_supabase()
    if not cliente.table("ciclo").select("id").eq("id", ciclo_id).limit(1).execute().data:
        raise HTTPException(status_code=404, detail=f"ciclo {ciclo_id} não encontrado")

    regua = criterios_repo.de_payload(payload)
    linhas = classificacao_ciclo.classificar(
        cliente, ciclo_id=ciclo_id, criterio=regua, fase=fase
    )
    cortados = [l for l in linhas if not l["aprovado"]]
    return {
        "total": len(linhas),
        "cortados": len(cortados),
        # Alguns nomes de quem seria cortado: um número sozinho não deixa
        # ninguém perceber que a régua está pegando o aluno errado.
        "exemplos": [
            {"nome": l["nome"], "motivo": l["motivo"]} for l in cortados[:5]
        ],
    }


@router.post("", status_code=201)
async def criar_criterio(
    body: CriterioEntrada,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    cliente = get_supabase()
    try:
        linha = criterios_repo.criar(cliente, body.model_dump(), criado_por=_ator(coordenador))
    except criterios_repo.CriterioInvalido as exc:
        raise _422(exc) from exc

    auditar(
        cliente, "criterio_criado", canal="criterio",
        ator_tipo="coordenador", ator_id=_ator(coordenador),
        recurso=f"criterio/{linha['slug']}",
        ip=request.client.host if request.client else None,
        detalhe={"nome": linha["nome"], "versao": linha["versao"],
                 "requisitos": len(body.predicados)},
    )
    return {"slug": linha["slug"], "versao": linha["versao"], "nome": linha["nome"]}


@router.patch("/{slug}")
async def editar_criterio(
    slug: str,
    body: CriterioEdicao,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Edita criando a versão seguinte. A anterior fica, inativa."""
    cliente = get_supabase()
    try:
        linha = criterios_repo.nova_versao(
            cliente, slug, body.model_dump(), criado_por=_ator(coordenador)
        )
    except criterios_repo.CriterioInvalido as exc:
        raise _422(exc) from exc

    auditar(
        cliente, "criterio_versionado", canal="criterio",
        ator_tipo="coordenador", ator_id=_ator(coordenador),
        recurso=f"criterio/{slug}",
        ip=request.client.host if request.client else None,
        detalhe={"versao": linha["versao"], "requisitos": len(body.predicados)},
    )
    return {"slug": linha["slug"], "versao": linha["versao"], "nome": linha["nome"]}


@router.delete("/{slug}")
async def desativar_criterio(
    slug: str,
    request: Request,
    coordenador: dict = Depends(get_current_coordenador),
) -> dict:
    """Tira do seletor. Nunca apaga — a régua nomeia números já lidos."""
    cliente = get_supabase()
    try:
        criterios_repo.desativar(cliente, slug)
    except criterios_repo.CriterioInvalido as exc:
        # Embutida vira 409, e não 422: não é o corpo que está errado, é a
        # operação que não existe para esse recurso.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    auditar(
        cliente, "criterio_desativado", canal="criterio",
        ator_tipo="coordenador", ator_id=_ator(coordenador),
        recurso=f"criterio/{slug}",
        ip=request.client.host if request.client else None,
    )
    return {"slug": slug, "ativo": False}
