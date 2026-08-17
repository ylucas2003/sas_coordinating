"""CLI leve — compara a GERAÇÃO de rubrica entre modelos (gerar + criticar),
sem precisar de resposta de aluno nem nota humana.

Não salva rubrica.json (é ferramenta de exploração) — para gerar a rubrica
persistida que as correções vão usar, rode `gerar_rubrica.py`.

Precisa de `enunciado.txt` + `gabarito.txt` (solução oficial real — este
protótipo não gera solução por IA, ver decisão em README.md).

Uso (a partir de api/):
    python -m grading_prototype.testar_rubrica \\
        --questao grading_prototype/dados_exemplo/<questao_id>
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from . import config, dados, pipeline
from .cliente_llm import ErroLLM
from .imagem import carregar_imagem_base64
from .rubrica import gerar_rubrica_final

log = logging.getLogger(__name__)

PASTA_PROTOTIPO = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara a geração de rubrica entre modelos — sem avaliador, sem salvar rubrica.json."
    )
    parser.add_argument(
        "--questao", required=True, help="Pasta da questão (ver README.md)."
    )
    parser.add_argument(
        "--modelos",
        default=",".join(config.MODELOS_PADRAO),
        help=f"Modelos a testar, separados por vírgula (padrão: {','.join(config.MODELOS_PADRAO)}).",
    )
    parser.add_argument(
        "--saida",
        default=str(PASTA_PROTOTIPO / "resultados"),
        help="Pasta onde salvar o JSON com as rubricas geradas.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pasta_questao = Path(args.questao)
    modelos = [m.strip() for m in args.modelos.split(",") if m.strip()]

    if dados.questao_esta_anulada(pasta_questao):
        raise SystemExit(
            f"Questão '{pasta_questao.name}' está anulada — sem gabarito válido "
            f"para gerar rubrica."
        )

    print(f"Carregando questão de {pasta_questao}...")
    questao = dados.carregar_questao(pasta_questao)

    api_key = config.get_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY não configurada (.env).")

    figura_data_url = (
        carregar_imagem_base64(questao.caminho_figura)
        if questao.caminho_figura is not None
        else None
    )
    if figura_data_url is None:
        print(f"Questão '{questao.id}' não tem figura — seguindo em modo texto-only.")

    resultados: dict = {"metadados_execucao": pipeline.metadados_execucao(",".join(modelos))}
    for modelo in modelos:
        print(f"\n=== Gerando rubrica com {modelo} ===")
        try:
            pacote = gerar_rubrica_final(
                api_key=api_key,
                modelo=modelo,
                questao=questao,
                figura_data_url=figura_data_url,
            )
            resultados[modelo] = {"erro": None, **pacote}

            print(f"[{modelo}] Resumo da crítica: {pacote['alteracoes']['resumo_geral']}\n")
            for criterio in pacote["rubrica_final"]["criterios"]:
                resultados_esp = criterio.get("resultados_esperados") or []
                sufixo = (
                    f" | resultados esperados: {'; '.join(resultados_esp)}"
                    if resultados_esp
                    else ""
                )
                print(
                    f"  - {criterio['id']} ({criterio['pontuacao']} pts): "
                    f"{criterio['objetivo_pedagogico']}{sufixo}"
                )
        except ErroLLM as exc:
            log.exception("modelo %s falhou", modelo)
            resultados[modelo] = {"erro": str(exc)}

    pasta_saida = Path(args.saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta_saida / f"rubrica_{questao.id}_{timestamp}.json"
    caminho.write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nRubricas completas salvas em: {caminho}")


if __name__ == "__main__":
    main()
