#!/usr/bin/env python3
"""Verificação ao vivo do Quiz Statistics — passo 0 da Fase 2 do sync.

READ-ONLY: não grava nada no banco. Decide o plano A vs B da sincronização
de questões:

  - Plano A (assumido): `question_statistics[].answers[]` traz `user_ids`
    (quem marcou cada alternativa) — campo observado ao vivo, não documentado.
  - Plano B (se user_ids não vier): Quiz Submissions + Quiz Submission
    Questions (N+1 por submission).

Uso (a partir de api/):
    python -m scripts.canvas_verificar_quiz_statistics              → 2 quizzes mais recentes
    python -m scripts.canvas_verificar_quiz_statistics --quiz 123   → um quiz específico
"""

from __future__ import annotations

import argparse
import asyncio
import json

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.canvas_sync.cliente import ClienteCanvas                      # noqa: E402
from app.canvas_sync.sincronizar import _curso_do_ano_vigente          # noqa: E402
from app.config import get_settings                                    # noqa: E402
from app.supabase_client import criar_cliente_supabase                 # noqa: E402


def _resumo_chaves(objeto: dict, rotulo: str) -> None:
    print(f"\n  chaves de {rotulo}:")
    for chave, valor in objeto.items():
        tipo = type(valor).__name__
        extra = f" (len={len(valor)})" if isinstance(valor, (list, dict, str)) else f" = {valor!r}"
        print(f"    - {chave}: {tipo}{extra}")


async def _verificar(quiz_id_cli: str | None) -> None:
    settings = get_settings()
    cliente = criar_cliente_supabase()

    # Quizzes alvo: da CLI, ou os 2 simulados com quiz_id mais recentes do banco.
    if quiz_id_cli:
        alvos = [{"quiz_id": quiz_id_cli, "nome": "(via --quiz)", "id": None}]
    else:
        resp = (
            cliente.table("simulado")
            .select("id, nome, quiz_id, data_aplicacao")
            .not_.is_("quiz_id", "null")
            .order("data_aplicacao", desc=True)
            .limit(2)
            .execute()
        )
        alvos = resp.data or []
        if not alvos:
            print("Nenhum simulado com quiz_id no banco — rode o backfill do Canvas antes.")
            return

    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        _, curso = await _curso_do_ano_vigente(
            canvas, account_id=settings.canvas_account_id,
            override_ano=settings.canvas_ano_vigente or None,
        )
        course_id = str(curso["id"])
        print(f"curso: {curso.get('name')} (id {course_id})")

        for alvo in alvos:
            quiz_id = str(alvo["quiz_id"])
            print(f"\n═══ quiz {quiz_id} — {alvo.get('nome')} ═══")
            try:
                bruto = await canvas.obter_estatisticas_quiz(course_id, quiz_id)
            except Exception as exc:
                # Quiz de outro ano não pertence ao curso vigente (404) —
                # segue para o próximo em vez de derrubar a verificação.
                print(f"  !! falha ao buscar statistics ({exc}) — pulando.")
                continue

            lista = bruto.get("quiz_statistics") or []
            if not lista:
                print("  !! resposta sem quiz_statistics — corpo bruto:")
                print(json.dumps(bruto, ensure_ascii=False)[:2000])
                continue
            stats = lista[0]
            _resumo_chaves(stats, "quiz_statistics[0]")

            submission_stats = stats.get("submission_statistics") or {}
            print(f"\n  submission_statistics.duration_average = "
                  f"{submission_stats.get('duration_average')!r}")
            print(f"  submission_statistics.unique_count = "
                  f"{submission_stats.get('unique_count')!r}")

            questoes = stats.get("question_statistics") or []
            print(f"\n  question_statistics: {len(questoes)} questões")
            if not questoes:
                continue
            _resumo_chaves(questoes[0], "question_statistics[0]")

            answers = questoes[0].get("answers") or []
            if not answers:
                print("  !! primeira questão sem answers[]")
                continue
            _resumo_chaves(answers[0], "answers[0]")

            # ── O veredito: user_ids existe? ──
            com_user_ids = sum(
                1 for q in questoes for a in (q.get("answers") or []) if a.get("user_ids")
            )
            total_answers = sum(len(q.get("answers") or []) for q in questoes)
            print(f"\n  >>> answers com user_ids: {com_user_ids}/{total_answers}")
            if com_user_ids:
                exemplo = next(
                    a for q in questoes for a in (q.get("answers") or []) if a.get("user_ids")
                )
                print(f"  >>> PLANO A CONFIRMADO — exemplo: answer {exemplo.get('id')} "
                      f"({'correta' if exemplo.get('correct') else 'errada'}) com "
                      f"{len(exemplo['user_ids'])} user_ids")
            else:
                print("  >>> user_ids AUSENTE — usar plano B (Quiz Submissions + "
                      "Quiz Submission Questions).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verifica o shape do Quiz Statistics ao vivo.")
    parser.add_argument("--quiz", help="quiz_id específico (default: 2 simulados mais recentes).")
    args = parser.parse_args()
    asyncio.run(_verificar(args.quiz))


if __name__ == "__main__":
    main()
