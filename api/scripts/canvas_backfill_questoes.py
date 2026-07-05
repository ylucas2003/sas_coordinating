#!/usr/bin/env python3
"""Backfill de questões/respostas dos quizzes (Fase 2 do Canvas sync).

Varre todos os simulados com quiz_id e roda o Quiz Statistics de cada um —
idempotente (tudo upsert por chave natural). O sync incremental de 5 min só
cobre quizzes com notas novas + um backlog pequeno por rodada; este script
zera o backlog de uma vez.

Uso (a partir de api/):
    python -m scripts.canvas_backfill_questoes                → todos os anos
    python -m scripts.canvas_backfill_questoes --ano 2026     → um ano
    python -m scripts.canvas_backfill_questoes --forcar       → refaz até os já sincronizados

Conexão: usa CANVAS_BASE_URL / CANVAS_API_TOKEN / SUPABASE_* do .env.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from dotenv import load_dotenv

load_dotenv()  # antes dos imports do app — Settings lê o ambiente na construção

from app.canvas_sync import mapeador                                  # noqa: E402
from app.canvas_sync.cliente import ClienteCanvas                     # noqa: E402
from app.canvas_sync.questoes import sincronizar_questoes_do_quiz     # noqa: E402
from app.canvas_sync.sincronizar import _descobrir_cursos_simulados   # noqa: E402
from app.config import get_settings                                   # noqa: E402
from app.supabase_client import criar_cliente_supabase                # noqa: E402


def _em_lotes(itens: list, tamanho: int):
    for inicio in range(0, len(itens), tamanho):
        yield itens[inicio : inicio + tamanho]


async def _mapa_aluno_do_curso(canvas: ClienteCanvas, cliente, course_id: str) -> dict[str, str]:
    """{canvas_user_id: aluno_id} no escopo do curso (via enrollments + matrícula).

    canvas_user_id não é único na tabela aluno (0011) — a resolução é sempre
    matrícula (chave natural), como no sync.
    """
    enrollments = await canvas.listar_matriculas_de_alunos(course_id)
    matricula_por_canvas_user: dict[str, str] = {}
    for enrollment in enrollments:
        aluno = mapeador.mapear_aluno(enrollment.get("user") or {})
        if aluno:
            matricula_por_canvas_user[aluno["canvas_user_id"]] = aluno["matricula"]

    matriculas = list(set(matricula_por_canvas_user.values()))
    id_por_matricula: dict[str, str] = {}
    for lote in _em_lotes(matriculas, 200):
        resp = cliente.table("aluno").select("id, matricula").in_("matricula", lote).execute()
        for linha in resp.data or []:
            id_por_matricula[linha["matricula"]] = linha["id"]

    return {
        canvas_user: id_por_matricula[matricula]
        for canvas_user, matricula in matricula_por_canvas_user.items()
        if matricula in id_por_matricula
    }


async def _simulados_com_quiz_do_curso(
    canvas: ClienteCanvas, cliente, course_id: str, *, forcar: bool
) -> list[dict]:
    """Simulados do banco (com quiz_id) que pertencem a este curso."""
    assignments = await canvas.listar_assignments(course_id)
    external_ids = [str(a["id"]) for a in assignments]
    simulados: list[dict] = []
    for lote in _em_lotes(external_ids, 100):
        q = (
            cliente.table("simulado")
            .select("id, nome, quiz_id, questoes_sincronizadas_em")
            .in_("external_id", lote)
            .not_.is_("quiz_id", "null")
        )
        resp = q.execute()
        simulados.extend(resp.data or [])
    if not forcar:
        simulados = [s for s in simulados if s.get("questoes_sincronizadas_em") is None]
    return simulados


async def _rodar(ano: str | None, forcar: bool) -> None:
    settings = get_settings()
    cliente = criar_cliente_supabase()

    async with ClienteCanvas(
        base_url=settings.canvas_base_url, token=settings.canvas_api_token
    ) as canvas:
        cursos = await _descobrir_cursos_simulados(canvas, settings.canvas_account_id)
        if ano:
            cursos = [(a, c) for a, c in cursos if a == int(ano)]
        if not cursos:
            print("Nenhum curso de simulados encontrado para o filtro dado.")
            sys.exit(1)

        total_quizzes = 0
        total_respostas = 0
        sem_user_ids: list[str] = []

        for ano_curso, curso in cursos:
            course_id = str(curso["id"])
            print(f"\n═══ {ano_curso} — {curso.get('name')} (curso {course_id}) ═══")

            simulados = await _simulados_com_quiz_do_curso(
                canvas, cliente, course_id, forcar=forcar
            )
            if not simulados:
                print("  nada a sincronizar (use --forcar para refazer).")
                continue

            aluno_por_canvas_user = await _mapa_aluno_do_curso(canvas, cliente, course_id)
            print(f"  {len(simulados)} quizzes · {len(aluno_por_canvas_user)} alunos mapeados")

            for sim in simulados:
                try:
                    resultado = await sincronizar_questoes_do_quiz(
                        cliente,
                        canvas,
                        course_id=course_id,
                        simulado_id=sim["id"],
                        quiz_id=str(sim["quiz_id"]),
                        aluno_por_canvas_user=aluno_por_canvas_user,
                    )
                except Exception as exc:
                    print(f"  ✗ {sim.get('nome')}: {exc}")
                    continue
                total_quizzes += 1
                total_respostas += resultado["respostas"]
                marcador = "" if resultado["tem_user_ids"] else "  [SEM user_ids!]"
                print(
                    f"  ✓ {sim.get('nome')}: {resultado['questoes']} questões, "
                    f"{resultado['respostas']} respostas{marcador}"
                )
                if resultado["questoes"] and not resultado["tem_user_ids"]:
                    sem_user_ids.append(str(sim["quiz_id"]))

        print(f"\n✓ backfill de questões: {total_quizzes} quizzes, {total_respostas} respostas")
        if sem_user_ids:
            print(f"  !! {len(sem_user_ids)} quizzes sem user_ids (plano B necessário): "
                  f"{', '.join(sem_user_ids[:10])}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill de questões dos quizzes do Canvas.")
    parser.add_argument("--ano", help="Restringe a um ano específico (ex.: 2026).")
    parser.add_argument("--forcar", action="store_true",
                        help="Refaz também quizzes já sincronizados.")
    args = parser.parse_args()

    t0 = time.monotonic()
    asyncio.run(_rodar(args.ano, args.forcar))
    print(f"  ({time.monotonic() - t0:.0f}s)")


if __name__ == "__main__":
    main()
