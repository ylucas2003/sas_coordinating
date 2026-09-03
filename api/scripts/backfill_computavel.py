#!/usr/bin/env python3
"""Avalia `nota.computavel` retroativamente, sobre o que já está no banco.

Substitui `limpar_zeros_provaveis_ausencias.py`, que fazia o oposto do que se
espera de um backfill: **apagava dado**. Aquele script inferia ausência de
"2+ zeros no mesmo dia" e gravava `presente = false, pontuacao = null` por cima
do que o Canvas afirmava. A medição contra produção (docs/32 §1.4) mostrou que
a regra pega 414 células; onde há dado de questão para conferir, 73 confirmam e
**12 contradizem** — 14% de erro, apagando a pontuação de quem respondeu — e em
329 delas não há como conferir.

Este aqui não escreve em `presente` nem em `pontuacao`. Só deriva
`computavel`/`motivo_nao_computavel` a partir de evidência direta (o aluno não
marcou nenhuma alternativa), e é reversível: rodar de novo depois de a
evidência mudar reavalia nos dois sentidos.

⚠️ Se o script ANTIGO já rodou em algum banco, o que ele apagou é recuperável:
o Canvas ainda tem o valor, e um `POST /canvas-sync/reconciliar` completo o traz
de volta. Faça isso ANTES deste backfill, senão as notas que ele zerou estão
como `presente = false` e não há o que avaliar.

Uso (em api/, com o .venv):
    ./.venv/bin/python scripts/backfill_computavel.py              # DRY-RUN
    ./.venv/bin/python scripts/backfill_computavel.py --aplicar
    ./.venv/bin/python scripts/backfill_computavel.py --simulado <uuid> --aplicar

Depois de aplicar, rode `scripts/recalcular_metricas.py`: métrica e
classificação leem `computavel`, e o cache fica um passo atrás até recalcular.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _carregar_dotenv(caminho_env: Path) -> None:
    if not caminho_env.exists():
        return
    for linha in caminho_env.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(
            chave.strip(), valor.split("#", 1)[0].strip().strip('"').strip("'")
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--aplicar", action="store_true", help="Grava. Sem a flag, só relata."
    )
    parser.add_argument(
        "--simulado", action="append", dest="simulados",
        help="Restringe a um simulado (repetível). Sem isto, avalia todos os que são quiz.",
    )
    args = parser.parse_args()

    dir_api = Path(__file__).resolve().parent.parent
    _carregar_dotenv(dir_api / ".env")
    sys.path.insert(0, str(dir_api))

    try:
        from app.stats.computavel import avaliar_computavel, decidir
        from app.supabase_client import criar_cliente_supabase
    except ImportError as exc:
        sys.exit(f"erro importando app: {exc}")

    try:
        cliente = criar_cliente_supabase()
    except RuntimeError as exc:
        sys.exit(f"erro conectando ao banco: {exc}")

    # Só simulados que são quiz têm evidência. Avaliar os outros é varrer o
    # banco inteiro para concluir "não sei" em cada linha.
    if args.simulados:
        simulado_ids = list(args.simulados)
    else:
        resp = cliente.table("simulado").select("id, quiz_id").execute()
        simulado_ids = [s["id"] for s in (resp.data or []) if s.get("quiz_id")]
    print(f"{len(simulado_ids)} simulado(s) com quiz a avaliar.")
    if not simulado_ids:
        print("✓ Nada a fazer.")
        return 0

    if args.aplicar:
        mudancas = avaliar_computavel(cliente, simulado_ids=simulado_ids)
        print(f"✓ {mudancas} nota(s) mudaram de estado.")
        print("  Agora rode: ./.venv/bin/python scripts/recalcular_metricas.py")
        return 0

    # ── Dry-run: mesma decisão, sem escrever ──
    from app.stats.computavel import _carregar_respostas, _em_lotes, _mapear_questoes

    questao_para_simulado = _mapear_questoes(cliente, simulado_ids)
    respostas = _carregar_respostas(cliente, list(questao_para_simulado))
    por_chave: dict[tuple[str, str], list[dict]] = {}
    for r in respostas:
        simulado_id = questao_para_simulado.get(r["questao_id"])
        if simulado_id is None:
            continue
        por_chave.setdefault((r["aluno_id"], simulado_id), []).append(r)

    nao_computaveis = {
        chave for chave, linhas in por_chave.items() if not decidir(linhas)[0]
    }
    print(f"  {len(por_chave)} par(es) aluno×simulado com evidência.")
    print(f"  {len(nao_computaveis)} cairiam em 'todas em branco'.")

    # Quantas dessas são de fato zero-com-presença — as que a regra move.
    afetadas = 0
    for lote in _em_lotes(simulado_ids):
        resp = (
            cliente.table("nota")
            .select("aluno_id, simulado_id, pontuacao, presente, computavel")
            .in_("simulado_id", lote)
            .execute()
        )
        for linha in resp.data or []:
            chave = (linha["aluno_id"], linha["simulado_id"])
            if chave not in nao_computaveis:
                continue
            if not linha.get("presente"):
                continue
            if float(linha.get("pontuacao") or 0) != 0.0:
                continue
            if linha.get("computavel") is False:
                continue
            afetadas += 1

    print(f"\n  → {afetadas} nota(s) sairiam da conta. Rode com --aplicar para gravar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
