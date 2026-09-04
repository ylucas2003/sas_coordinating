"""HTTP da missão do dia (docs/35 §9).

Só fronteira, como o resto de `routes/`: quem escolhe o assunto é
`app/banco/missao.py`, e é lá que a regra se testa sem subir a API.

Router próprio, e não mais uma rota em `routes/banco.py`, porque não é a mesma
coisa: `/banco` é NAVEGAÇÃO pelo acervo — filtro, página, lista —, e a missão é
uma ESCOLHA do dia sobre esse acervo. O prefixo separado também deixa claro na
`/docs` que a rota não aceita filtro nenhum: ela não tem o que recortar.

⚠️ Sem dado pessoal e sem `aluno_id`: a missão é a MESMA para todos os alunos
por decisão de produto (docs/35 §9.3), então basta sessão válida — mesma régua
da taxonomia em `routes/banco.py`, que é conteúdo público de prova.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from supabase import Client

from ..auth import get_current_user
from ..banco.missao import MissaoDoDia, missao_do_dia
from ..supabase_client import get_supabase

router = APIRouter(prefix="/missao", tags=["missao"])


@router.get(
    "/hoje",
    response_model=MissaoDoDia | None,
    dependencies=[Depends(get_current_user)],
)
async def obter_missao_de_hoje() -> MissaoDoDia | None:
    """O assunto do dia, igual para toda a turma, com 10 questões.

    Devolve `null` — e não 404 — quando nenhum tópico tem lastro de 10 questões
    objetivas: é estado possível do acervo, não erro, e a aba Hoje já tem a tela
    dele (o convite "escolha um assunto"). Ver `banco/missao.py::missao_do_dia`.
    """
    cliente: Client = get_supabase()
    return missao_do_dia(cliente)
