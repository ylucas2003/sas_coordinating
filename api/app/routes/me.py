"""Endpoints do aluno autenticado — proxy seguro para os dados do próprio aluno.

O aluno só consegue ver os próprios dados: o JWT carrega o aluno_id e os
handlers repassam para as extrações de stats/aluno_dados.py (compartilhadas
com as tools do chat do aluno) sem expor o ID na URL nem permitir acesso a
outros alunos.

⚠️ `GET /simulado/{id}/arquivo` SAIU em 04/09 (docs/35 §8b), junto com o botão
"Abrir a prova" da ficha do aluno. Não foi só o botão: a rota devolvia uma URL
assinada de vida curta, e uma porta que ninguém mais abre continua sendo uma
porta — este projeto já teve uma vulnerabilidade nascida de token de download
(PR #7). Se a prova em PDF voltar a ser entregue ao aluno, ela volta com a
decisão inteira refeita, não descomentando uma rota.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_aluno
from ..stats.aluno_dados import (
    detalhe_simulado_do_aluno,
    evolucao_do_aluno,
    payload_insight_ciclo,
    questoes_do_aluno_no_simulado,
    simulados_do_aluno,
)
from ..stats.aluno_jornada import (
    meta_do_ciclo_do_aluno,
    proximo_simulado_do_aluno,
    sequencia_do_aluno,
)
from ..stats.aluno_zona import vestibulares_alvo, zona_do_aluno
from ..stats.insight_aluno import gerar_para_aluno_ciclo
from ..supabase_client import get_supabase
from .alunos import heatmap_aluno, obter_aluno, trajetoria_aluno

#: Os dois únicos alvos que o SAS conhece. Fechado por Literal e não por texto
#: livre porque o valor vira slug de régua em `aluno_zona._REGUA_POR_VESTIBULAR`
#: — um terceiro valor entraria no banco e sairia sem critério do outro lado.
VESTIBULARES = ("ITA", "IME")

router = APIRouter(prefix="/me", tags=["me"])


def _ou_404(resultado: dict) -> dict:
    """{"erro": ...} das extrações compartilhadas vira 404 na camada HTTP."""
    if isinstance(resultado, dict) and "erro" in resultado:
        raise HTTPException(status_code=404, detail=resultado["erro"])
    return resultado


# ── Conta ─────────────────────────────────────────────────────────────────
# A rota POST /me/senha SAIU em 04/09 (docs/35 §11.5), junto com a folha
# "Trocar senha" da área do aluno (`telas/Aluno/CascoAluno.tsx`).
#
# Ela não estava só obsoleta, estava quebrada dos dois lados: para quem nunca
# teve hash — a maioria — `verificar_senha(atual, None)` é False, então ela
# respondia "Senha atual incorreta" sempre; e para os poucos com hash antigo
# funcionava, dizia "Senha alterada." e gravava uma credencial que não
# autentica em lugar nenhum, porque o aluno entra só pelo Canvas.
#
# Com ela fora, nenhuma ROTA escreve mais em `aluno.senha_hash` — a outra que
# escrevia era `/alunos/{id}/resetar-acesso`, extinta no mesmo dia. Sobrou só
# `scripts/criar_acesso.py --matricula`, que grava um hash que hoje não
# autentica ninguém (ver o docstring de `app/auth.py`). A coluna fica com o que
# já tinha: apagar perde dado e não devolve nada.


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


# ⚠️ `GET /me/streak` SAIU em 05/09 (docs/36 §4), junto com `/me/jogo` entrando.
# Ela devolvia "ciclos consecutivos acima da média da turma" — métrica
# RELATIVA, que premia posição e não progresso (docs/24 §1.1): um aluno que
# melhorou podia perder a sequência porque a turma melhorou mais. A mecânica
# do produto é "simulados consecutivos sem faltar" (docs/26 §4), e enquanto as
# duas rotas existissem haveria duas verdades sobre o mesmo número na tela.


@router.get("/jogo")
async def me_jogo(user: dict = Depends(get_current_aluno)):
    """Sequência de simulados sem faltar: a corrente, a atual e o recorde."""
    return sequencia_do_aluno(get_supabase(), user["aluno_id"])


@router.get("/agenda")
async def me_agenda(user: dict = Depends(get_current_aluno)):
    """O próximo simulado do aluno, ou `null` quando não há nada marcado."""
    return proximo_simulado_do_aluno(get_supabase(), user["aluno_id"])


@router.get("/meta")
async def me_meta(user: dict = Depends(get_current_aluno)):
    """A meta do ciclo — presença nos simulados marcados (docs/36 §1.5)."""
    return meta_do_ciclo_do_aluno(get_supabase(), user["aluno_id"])


@router.get("/zona")
async def me_zona(user: dict = Depends(get_current_aluno)):
    """Zona, distância até a próxima e as matérias contra o corte.

    ⚠️ `regua` vem junto e não é enfeite: docs/24 §2 proíbe o rótulo sem a
    distância e sem o nome do critério que o produziu — "risco" sem dizer
    contra qual corte é só a má notícia.
    """
    return zona_do_aluno(get_supabase(), user["aluno_id"])


class DefinirVestibulares(BaseModel):
    """O alvo declarado no onboarding. Lista porque mirar ITA e IME é comum."""

    vestibulares: list[str] = Field(min_length=1, max_length=len(VESTIBULARES))


@router.get("/vestibulares")
async def me_vestibulares(user: dict = Depends(get_current_aluno)):
    """Os vestibulares alvo do aluno. `completo` é o portão do onboarding."""
    alvos = vestibulares_alvo(get_supabase(), user["aluno_id"])
    return {"vestibulares": alvos, "completo": bool(alvos)}


@router.put("/vestibulares")
async def me_definir_vestibulares(
    corpo: DefinirVestibulares, user: dict = Depends(get_current_aluno)
):
    """Grava o alvo do aluno — a escrita que faltava para a régua existir.

    ⚠️ Apaga e reinsere em vez de fazer upsert: `vestibular_alvo_aluno` não
    declara chave primária (migration 0001), e `on_conflict` sem constraint
    falha no PostgREST. Apagar as linhas do próprio aluno é seguro porque a
    tabela é a declaração inteira dele, não um histórico.
    """
    escolhidos = sorted({v.strip().upper() for v in corpo.vestibulares})
    invalidos = [v for v in escolhidos if v not in VESTIBULARES]
    if invalidos:
        raise HTTPException(
            status_code=422,
            detail=f"vestibular inválido: {', '.join(invalidos)}. Use {' ou '.join(VESTIBULARES)}.",
        )

    cliente = get_supabase()
    aluno_id = user["aluno_id"]
    cliente.table("vestibular_alvo_aluno").delete().eq("aluno_id", aluno_id).execute()
    cliente.table("vestibular_alvo_aluno").insert(
        [{"aluno_id": aluno_id, "vestibular": v} for v in escolhidos]
    ).execute()
    return {"vestibulares": escolhidos, "completo": True}


@router.get("/simulados")
async def me_simulados(
    incluirFaltas: bool = False,  # camelCase: é nome de query param, não de variável
    user: dict = Depends(get_current_aluno),
):
    """Lista de simulados do aluno com nota, delta vs próprio padrão e média da turma.

    `incluirFaltas=true` traz junto os simulados em que o aluno não compareceu
    (`nota: null`, `presente: false`). Default `false` porque as telas que já
    consomem esta rota calculam média sobre a lista — ver o docstring de
    `simulados_do_aluno`.
    """
    return simulados_do_aluno(
        get_supabase(), user["aluno_id"], incluir_faltas=incluirFaltas
    )


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
