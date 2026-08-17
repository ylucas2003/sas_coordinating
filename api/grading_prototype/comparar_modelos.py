"""CLI — harness de comparação de modelos AVALIADORES.

A rubrica é obtida UMA vez (persistida em rubrica.json, ou gerada com
--modelo-rubrica e salva) e os modelos comparados avaliam a MESMA rubrica —
assim a tabela compara vereditos sobre critérios idênticos, e a diferença
medida é só do avaliador. Para comparar a GERAÇÃO de rubrica entre modelos,
use `testar_rubrica.py`.

Uso (a partir de api/):
    python -m grading_prototype.comparar_modelos \\
        --questao grading_prototype/dados_exemplo/<questao_id> \\
        --aluno <aluno_id>

Use --dry-run para validar carregamento de arquivos, encoding de imagem e
formatação do relatório sem chamar a API (zero custo).
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from . import config, dados, pipeline, pontuacao, relatorio
from .avaliador import avaliar_resposta
from .cliente_llm import ErroLLM
from .imagem import carregar_imagem_base64

log = logging.getLogger(__name__)

PASTA_PROTOTIPO = Path(__file__).resolve().parent


def _fixture_rubrica() -> dict:
    return {
        "rubrica_final": {
            "criterios": [
                {"id": "criterio_1", "pontuacao": 4.0},
                {"id": "criterio_2", "pontuacao": 3.0},
                {"id": "criterio_3", "pontuacao": 3.0},
            ]
        },
        "origem": "fixture",
        "revisada_por_humano": False,
        "uso": {},
    }


def _fixture_avaliacao(modelo: str) -> dict:
    """Avaliação fake usada só em --dry-run — valida o resto da plumbing
    (carregamento de arquivos, encoding de imagem, tabela/JSON de saída)
    sem gastar tokens de API."""
    # Varia levemente por modelo só pra tabela do dry-run não ficar idêntica.
    veredito_c3 = "parcial" if modelo == config.MODELOS_PADRAO[0] else "atendido"
    return {
        "avaliacoes_por_criterio": [
            {
                "criterio_id": "criterio_1",
                "veredito": "atendido",
                "justificativa": "[dry-run] fixture, sem chamada real à API.",
                "evidencias_encontradas": [],
            },
            {
                "criterio_id": "criterio_2",
                "veredito": "atendido",
                "justificativa": "[dry-run] fixture, sem chamada real à API.",
                "evidencias_encontradas": [],
            },
            {
                "criterio_id": "criterio_3",
                "veredito": veredito_c3,
                "justificativa": "[dry-run] fixture, sem chamada real à API.",
                "evidencias_encontradas": [],
            },
        ],
        "observacoes_gerais": "[dry-run] fixture, sem chamada real à API.",
    }


def _rodar_modelo(
    *,
    modelo: str,
    dry_run: bool,
    api_key: str,
    questao: dados.Questao,
    figura_data_url: str | None,
    rubrica_final: dict,
    paginas_data_urls: list[str],
    resposta_texto: str | None,
    nota_humana: float | None,
) -> dict:
    print(f"\n=== Rodando avaliador: {modelo} ===")
    try:
        if dry_run:
            avaliacao = _fixture_avaliacao(modelo)
            uso = {}
        else:
            print(f"[{modelo}] avaliando resposta do aluno...")
            avaliacao, uso = avaliar_resposta(
                api_key=api_key,
                modelo=modelo,
                questao=questao,
                figura_data_url=figura_data_url,
                rubrica_final=rubrica_final,
                paginas_data_urls=paginas_data_urls,
                resposta_texto=resposta_texto,
            )

        nota = pontuacao.calcular_nota(rubrica_final, avaliacao)
        comparacao = (
            pontuacao.comparar_com_nota_humana(nota["nota_final"], nota_humana)
            if nota_humana is not None
            else None
        )
        return {
            "erro": None,
            "avaliacao": avaliacao,
            "nota": nota,
            "comparacao": comparacao,
            "uso": {"avaliacao": uso},
        }
    except ErroLLM as exc:
        log.exception("modelo %s falhou", modelo)
        return {"erro": str(exc)}
    except Exception as exc:  # noqa: BLE001 — captura qualquer falha do pipeline de UM modelo, sem abortar os outros
        log.exception("modelo %s falhou de forma inesperada", modelo)
        return {"erro": f"Erro inesperado: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compara modelos avaliadores sobre a MESMA rubrica (protótipo)."
    )
    parser.add_argument(
        "--questao", required=True, help="Pasta da questão (ver README.md)."
    )
    parser.add_argument(
        "--aluno", default=None, help="Id do aluno (auto-detecta se só houver um)."
    )
    parser.add_argument(
        "--modelos",
        default=",".join(config.MODELOS_PADRAO),
        help=f"Modelos avaliadores, separados por vírgula (padrão: {','.join(config.MODELOS_PADRAO)}).",
    )
    parser.add_argument(
        "--modelo-rubrica",
        default="gpt-4o",
        help="Modelo usado para GERAR a rubrica quando não há rubrica.json (padrão: gpt-4o).",
    )
    parser.add_argument(
        "--regerar-rubrica",
        action="store_true",
        help="Ignora rubrica.json existente e regenera (sobrescrevendo).",
    )
    parser.add_argument(
        "--saida",
        default=str(PASTA_PROTOTIPO / "resultados"),
        help="Pasta onde salvar o relatório JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Roda a plumbing inteira com fixtures, sem chamar a API (zero custo).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pasta_questao = Path(args.questao)
    modelos = [m.strip() for m in args.modelos.split(",") if m.strip()]

    print(f"Carregando questão de {pasta_questao}...")
    questao = dados.carregar_questao(pasta_questao)
    if questao.anulada:
        raise SystemExit(f"Questão '{questao.id}' está anulada — nada a comparar.")

    aluno_id = args.aluno
    if aluno_id is None:
        disponiveis = dados.listar_alunos_disponiveis(pasta_questao)
        if len(disponiveis) != 1:
            raise SystemExit(
                f"--aluno não informado e há {len(disponiveis)} alunos disponíveis "
                f"({disponiveis}) — especifique um com --aluno."
            )
        aluno_id = disponiveis[0]
    print(f"Carregando resposta do aluno '{aluno_id}'...")
    resposta_aluno = dados.carregar_resposta_aluno(pasta_questao, aluno_id)

    api_key = "" if args.dry_run else config.get_openai_api_key()
    if not args.dry_run and not api_key:
        raise SystemExit(
            "OPENAI_API_KEY não configurada (.env) — use --dry-run para testar sem API."
        )

    print("Codificando imagens (figura do enunciado, se houver, + páginas da resposta)...")
    figura_data_url = (
        carregar_imagem_base64(questao.caminho_figura)
        if questao.caminho_figura is not None
        else None
    )
    if figura_data_url is None:
        print(f"Questão '{questao.id}' não tem figura — seguindo em modo texto-only.")
    paginas_data_urls = [carregar_imagem_base64(p) for p in resposta_aluno.caminhos_paginas]

    if args.dry_run:
        rubrica = _fixture_rubrica()
    else:
        rubrica = pipeline.obter_rubrica(
            pasta_questao,
            questao,
            figura_data_url,
            api_key=api_key,
            modelo=args.modelo_rubrica,
            regerar=args.regerar_rubrica,
        )
    print(
        f"Rubrica: origem={rubrica['origem']}, "
        f"revisada_por_humano={rubrica['revisada_por_humano']}"
    )

    resultados_por_modelo = {}
    for modelo in modelos:
        resultados_por_modelo[modelo] = _rodar_modelo(
            modelo=modelo,
            dry_run=args.dry_run,
            api_key=api_key,
            questao=questao,
            figura_data_url=figura_data_url,
            rubrica_final=rubrica["rubrica_final"],
            paginas_data_urls=paginas_data_urls,
            resposta_texto=resposta_aluno.resposta_texto,
            nota_humana=resposta_aluno.nota_humana,
        )

    print(
        "\n"
        + relatorio.montar_tabela_comparativa(resultados_por_modelo, resposta_aluno.nota_humana)
    )

    caminho_relatorio = relatorio.salvar_relatorio_json(
        resultados_por_modelo,
        questao_id=questao.id,
        aluno_id=aluno_id,
        nota_humana=resposta_aluno.nota_humana,
        pasta_saida=Path(args.saida),
        extras={
            "rubrica_compartilhada": rubrica["rubrica_final"],
            "rubrica_origem": rubrica["origem"],
            "rubrica_revisada_por_humano": rubrica["revisada_por_humano"],
            "metadados_execucao": pipeline.metadados_execucao(
                f"rubrica={args.modelo_rubrica}; avaliadores={','.join(modelos)}"
            ),
        },
    )
    print(f"\nRelatório completo salvo em: {caminho_relatorio}")


if __name__ == "__main__":
    main()
