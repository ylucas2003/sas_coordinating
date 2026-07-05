"""Fase 2 do Canvas sync: questões, alternativas e respostas por aluno.

Fonte primária: Quiz Statistics (`GET /courses/:cid/quizzes/:qid/statistics`) —
UMA chamada por quiz devolve todas as questões com gabarito e, por alternativa,
os `user_ids` de quem a marcou (campo observado ao vivo, não documentado na
API oficial — ver docs/08-integracao-canvas.md §5.6). Se o Canvas parar de
devolver `user_ids`, o plano B documentado é Quiz Submissions + Quiz
Submission Questions (N+1 por submission).

Populei as tabelas criadas na migration 0010:
  questao(simulado_id, canvas_question_id, posicao, texto, pontos)
  questao_alternativa(questao_id, canvas_answer_id, texto, correta)
  questao_resposta_aluno(aluno_id, questao_id, alternativa_id, correta)
e simulado.duracao_media_segundos + questoes_sincronizadas_em (0015).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from supabase import Client

from ..ingest.upsert import (
    upsert_alternativas_em_lote,
    upsert_questoes_em_lote,
    upsert_respostas_questao_em_lote,
)
from .cliente import ClienteCanvas

# Buckets sintéticos do Quiz Statistics: não são alternativas reais.
# "none" = deixou em branco; "other" = resposta fora das alternativas
# (ex.: questão alterada depois da aplicação).
_BUCKETS_SEM_ALTERNATIVA = {"none", "other"}


def _como_float(valor: Any) -> float | None:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


async def sincronizar_questoes_do_quiz(
    cliente: Client,
    canvas: ClienteCanvas,
    *,
    course_id: str,
    simulado_id: str,
    quiz_id: str,
    aluno_por_canvas_user: dict[str, str],
) -> dict[str, Any]:
    """Sincroniza todas as questões e respostas de UM quiz.

    `aluno_por_canvas_user` deve vir do escopo do curso (enrollments) — o
    canvas_user_id não é único na tabela aluno (migration 0011), então uma
    query global seria ambígua.

    Devolve {"questoes": n, "respostas": n, "tem_user_ids": bool}.
    """
    bruto = await canvas.obter_estatisticas_quiz(course_id, quiz_id)
    lista_stats = bruto.get("quiz_statistics") or []
    if not lista_stats:
        return {"questoes": 0, "respostas": 0, "tem_user_ids": False}
    stats = lista_stats[0]

    # ── Questões ──
    # `pontos` fica de fora do payload: o Quiz Statistics não traz
    # points_possible por questão (verificado ao vivo), e mandar NULL no
    # upsert apagaria um valor preenchido por outra fonte no futuro.
    question_stats = stats.get("question_statistics") or []
    questoes_payload: list[dict[str, Any]] = []
    for indice, questao in enumerate(question_stats):
        questoes_payload.append(
            {
                "simulado_id": simulado_id,
                "canvas_question_id": str(questao["id"]),
                "posicao": int(questao.get("position") or indice + 1),
                "texto": questao.get("question_text") or "",
            }
        )
    canvas_para_questao_id = upsert_questoes_em_lote(cliente, questoes=questoes_payload)

    # ── Alternativas + respostas por aluno ──
    alternativas_payload: list[dict[str, Any]] = []
    # (questao_id, canvas_answer_id | None, correta, user_ids)
    respostas_brutas: list[tuple[str, str | None, bool, list[Any]]] = []
    tem_user_ids = False

    for questao in question_stats:
        questao_id = canvas_para_questao_id.get(str(questao["id"]))
        if questao_id is None:
            continue
        for answer in questao.get("answers") or []:
            canvas_answer_id = str(answer.get("id") or "")
            correta = bool(answer.get("correct"))
            user_ids = answer.get("user_ids") or []
            if user_ids:
                tem_user_ids = True

            if canvas_answer_id.lower() in _BUCKETS_SEM_ALTERNATIVA or not canvas_answer_id:
                # Em branco / fora das alternativas: vira resposta sem alternativa.
                respostas_brutas.append((questao_id, None, False, user_ids))
                continue

            alternativas_payload.append(
                {
                    "questao_id": questao_id,
                    "canvas_answer_id": canvas_answer_id,
                    "texto": answer.get("text") or "",
                    "correta": correta,
                }
            )
            respostas_brutas.append((questao_id, canvas_answer_id, correta, user_ids))

    chave_para_alternativa_id = upsert_alternativas_em_lote(
        cliente, alternativas=alternativas_payload
    )

    # Dedup pela PK (aluno_id, questao_id): o mesmo aluno pode aparecer em
    # mais de um bucket da mesma questão (ex.: alternativa real + 'other' em
    # quizzes com múltiplas tentativas) — duas linhas com a mesma chave no
    # MESMO upsert quebram com "ON CONFLICT cannot affect row a second time".
    # Alternativa real vence bucket em branco.
    resposta_por_chave: dict[tuple[str, str], dict[str, Any]] = {}
    for questao_id, canvas_answer_id, correta, user_ids in respostas_brutas:
        alternativa_id = (
            chave_para_alternativa_id.get((questao_id, canvas_answer_id))
            if canvas_answer_id
            else None
        )
        for user_id in user_ids:
            aluno_id = aluno_por_canvas_user.get(str(user_id))
            if aluno_id is None:
                continue  # aluno fora das sections reconhecidas
            chave = (aluno_id, questao_id)
            existente = resposta_por_chave.get(chave)
            if existente is not None and existente["alternativa_id"] is not None:
                continue
            resposta_por_chave[chave] = {
                "aluno_id": aluno_id,
                "questao_id": questao_id,
                "alternativa_id": alternativa_id,
                "correta": correta,
            }
    n_respostas = upsert_respostas_questao_em_lote(
        cliente, respostas=list(resposta_por_chave.values())
    )

    # ── Duração média + marcador de sync ──
    submission_stats = stats.get("submission_statistics") or {}
    patch: dict[str, Any] = {
        "questoes_sincronizadas_em": datetime.now(timezone.utc).isoformat()
    }
    duracao = _como_float(submission_stats.get("duration_average"))
    if duracao is not None:
        patch["duracao_media_segundos"] = duracao
    cliente.table("simulado").update(patch).eq("id", simulado_id).execute()

    return {
        "questoes": len(canvas_para_questao_id),
        "respostas": n_respostas,
        "tem_user_ids": tem_user_ids,
    }
