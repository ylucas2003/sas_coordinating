"""CLI — gera e salva `rubrica.json` na pasta da questão (rubrica persistida).

Este é o ponto de REVISÃO HUMANA do fluxo: gere as rubricas antes de
corrigir os alunos, abra os `rubrica.json`, ajuste critérios/pesos à mão se
necessário e marque `"revisada_por_humano": true`. Depois disso, todos os
alunos daquela questão serão corrigidos pela MESMA rubrica.

Uso (a partir de api/):
    # uma questão
    python -m grading_prototype.gerar_rubrica --questao grading_prototype/dados_exemplo/<questao_id>

    # todas as questões de uma pasta (pula anuladas e as que já têm rubrica.json)
    python -m grading_prototype.gerar_rubrica --todas

    # regenerar por cima de uma rubrica existente
    python -m grading_prototype.gerar_rubrica --questao ... --forcar
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import config, dados, pipeline
from .cliente_llm import ErroLLM

log = logging.getLogger(__name__)

PASTA_PROTOTIPO = Path(__file__).resolve().parent


def _gerar_para_questao(pasta_questao: Path, *, api_key: str, modelo: str, forcar: bool) -> bool:
    """Gera (ou pula) a rubrica de uma questão. Devolve True se gerou."""
    if dados.questao_esta_anulada(pasta_questao):
        print(f"{pasta_questao.name}: ANULADA — pulando.")
        return False

    caminho_rubrica = pasta_questao / pipeline.ARQUIVO_RUBRICA
    if caminho_rubrica.is_file() and not forcar:
        print(f"{pasta_questao.name}: rubrica.json já existe — pulando (use --forcar).")
        return False

    print(f"{pasta_questao.name}: gerando rubrica com {modelo}...")
    questao, figura_data_url = pipeline.preparar_questao(pasta_questao)
    rubrica = pipeline.obter_rubrica(
        pasta_questao,
        questao,
        figura_data_url,
        api_key=api_key,
        modelo=modelo,
        regerar=forcar,
    )
    for criterio in rubrica["rubrica_final"]["criterios"]:
        resultados = criterio.get("resultados_esperados") or []
        sufixo = f" | resultados esperados: {'; '.join(resultados)}" if resultados else ""
        print(
            f"  - {criterio['id']} ({criterio['pontuacao']} pts): "
            f"{criterio['objetivo_pedagogico']}{sufixo}"
        )
    print(f"  salva em {caminho_rubrica} — revise à mão e marque revisada_por_humano.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera e salva rubrica.json na pasta da questão (rubrica persistida)."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--questao", help="Pasta de UMA questão.")
    grupo.add_argument(
        "--todas",
        action="store_true",
        help="Todas as questões de --pasta-exemplos (pula anuladas e já geradas).",
    )
    parser.add_argument(
        "--pasta-exemplos",
        default=str(PASTA_PROTOTIPO / "dados_exemplo"),
        help="Pasta com as subpastas de questão (usada com --todas).",
    )
    parser.add_argument(
        "--modelo", default="gpt-4o", help="Modelo gerador (padrão: gpt-4o)."
    )
    parser.add_argument(
        "--forcar", action="store_true", help="Regenera por cima de rubrica.json existente."
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    api_key = config.get_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY não configurada (.env).")

    if args.questao:
        pastas = [Path(args.questao)]
    else:
        pasta_exemplos = Path(args.pasta_exemplos)
        pastas = sorted(
            p for p in pasta_exemplos.iterdir() if p.is_dir() and (p / "enunciado.txt").is_file()
        )
        if not pastas:
            raise SystemExit(f"Nenhuma questão encontrada em {pasta_exemplos}.")

    geradas = 0
    for pasta_questao in pastas:
        try:
            if _gerar_para_questao(
                pasta_questao, api_key=api_key, modelo=args.modelo, forcar=args.forcar
            ):
                geradas += 1
        except ErroLLM as exc:
            log.exception("questão %s falhou", pasta_questao.name)
            print(f"{pasta_questao.name}: ERRO — {exc}")
        except Exception as exc:  # noqa: BLE001 — uma questão falhar não deve abortar as outras
            log.exception("questão %s falhou de forma inesperada", pasta_questao.name)
            print(f"{pasta_questao.name}: ERRO inesperado — {exc}")

    print(f"\n{geradas} rubrica(s) gerada(s).")


if __name__ == "__main__":
    main()
