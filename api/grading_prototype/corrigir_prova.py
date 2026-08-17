"""CLI — corrige a prova completa de um aluno: roda rubrica + avaliação +
nota em todas as questões (dentro de --pasta-exemplos) que tiverem uma
resposta desse aluno. Questões rodam em paralelo (ThreadPoolExecutor).

Diferença pra `comparar_modelos.py`: este script NÃO exige `nota_humana.json`
— é o caminho de correção real (produzir uma nota), não de validação contra
uma nota humana já conhecida. Se `nota_humana.json` existir, a comparação
aparece no relatório; se não existir, só a nota calculada é reportada.

Usa a rubrica persistida (`rubrica.json` na pasta da questão) quando existe
— gere e revise antes com `python -m grading_prototype.gerar_rubrica --todas`.
Se não existir, gera e salva na primeira correção (os próximos alunos reusam).

Questões marcadas `"anulada": true` no `metadata.json` são puladas.

Uso (a partir de api/):
    python -m grading_prototype.corrigir_prova --aluno <aluno_id>
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from . import config, dados, pipeline
from .cliente_llm import ErroLLM

log = logging.getLogger(__name__)

PASTA_PROTOTIPO = Path(__file__).resolve().parent


def _corrigir_uma(pasta_questao: Path, *, aluno_id: str, modelo: str,
                  modelo_escalonamento: str | None, api_key: str,
                  regerar_rubrica: bool) -> tuple[str, dict]:
    try:
        resultado = pipeline.corrigir_questao(
            pasta_questao,
            aluno_id,
            api_key=api_key,
            modelo_avaliador=modelo,
            modelo_escalonamento=modelo_escalonamento,
            regerar_rubrica=regerar_rubrica,
        )
        n_escalonados = len(resultado.get("escalonamentos", []))
        sufixo = f", {n_escalonados} critério(s) escalonado(s)" if n_escalonados else ""
        print(
            f"[{pasta_questao.name}] nota: {resultado['nota']['nota_final']:.2f} "
            f"(rubrica {resultado['rubrica_origem']}{sufixo})"
        )
        return pasta_questao.name, resultado
    except ErroLLM as exc:
        log.exception("questão %s falhou", pasta_questao.name)
        return pasta_questao.name, {"erro": str(exc)}
    except Exception as exc:  # noqa: BLE001 — uma questão falhar não deve abortar as outras
        log.exception("questão %s falhou de forma inesperada", pasta_questao.name)
        return pasta_questao.name, {"erro": f"Erro inesperado: {exc}"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Corrige a prova completa de um aluno (todas as questões disponíveis)."
    )
    parser.add_argument("--aluno", required=True, help="Id do aluno (pasta em respostas/).")
    parser.add_argument(
        "--pasta-exemplos",
        default=str(PASTA_PROTOTIPO / "dados_exemplo"),
        help="Pasta contendo as subpastas de questão (padrão: dados_exemplo/).",
    )
    parser.add_argument(
        "--modelo",
        default=config.MODELO_AVALIADOR_BARATO,
        help=f"Modelo avaliador (padrão: {config.MODELO_AVALIADOR_BARATO}).",
    )
    parser.add_argument(
        "--modelo-escalonamento",
        default=config.MODELO_ESCALONAMENTO,
        help=(
            f"Modelo forte que confirma descontos/casos suspeitos, critério a "
            f"critério (padrão: {config.MODELO_ESCALONAMENTO}). Passe string "
            f"vazia para desligar o escalonamento."
        ),
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
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    pasta_exemplos = Path(args.pasta_exemplos)
    api_key = config.get_openai_api_key()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY não configurada (.env).")

    candidatas = sorted(
        p
        for p in pasta_exemplos.iterdir()
        if p.is_dir() and (p / "respostas" / args.aluno).is_dir()
    )
    if not candidatas:
        raise SystemExit(
            f"Nenhuma questão em {pasta_exemplos} tem resposta do aluno '{args.aluno}'."
        )

    anuladas = [p.name for p in candidatas if dados.questao_esta_anulada(p)]
    pastas_questoes = [p for p in candidatas if p.name not in anuladas]
    for nome in anuladas:
        print(f"=== {nome}: ANULADA — pulando ===")

    modelo_escalonamento = args.modelo_escalonamento.strip() or None

    resultados_por_questao: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS_CORRECAO) as executor:
        futuros = [
            executor.submit(
                _corrigir_uma,
                pasta_questao,
                aluno_id=args.aluno,
                modelo=args.modelo,
                modelo_escalonamento=modelo_escalonamento,
                api_key=api_key,
                regerar_rubrica=args.regerar_rubrica,
            )
            for pasta_questao in pastas_questoes
        ]
        for futuro in as_completed(futuros):
            nome, resultado = futuro.result()
            resultados_por_questao[nome] = resultado
    # dict ordenado por nome da questão no relatório
    resultados_por_questao = dict(sorted(resultados_por_questao.items()))

    questoes_com_erro = [n for n, r in resultados_por_questao.items() if "erro" in r]
    notas_validas = [
        r["nota"]["nota_final"] for r in resultados_por_questao.values() if "erro" not in r
    ]
    media = sum(notas_validas) / len(notas_validas) if notas_validas else 0.0

    total_tokens = {"entrada": 0, "saida": 0}
    for r in resultados_por_questao.values():
        for uso in r.get("uso", {}).values():
            total_tokens["entrada"] += uso.get("tokens_entrada", 0)
            total_tokens["saida"] += uso.get("tokens_saida", 0)

    total_escalonados = sum(
        len(r.get("escalonamentos", []))
        for r in resultados_por_questao.values()
        if "erro" not in r
    )

    print("\n" + "=" * 60)
    rotulo_modelos = args.modelo + (
        f" + escalonamento {modelo_escalonamento}" if modelo_escalonamento else ""
    )
    print(f"RESUMO — aluno: {args.aluno} (modelo: {rotulo_modelos})")
    for nome_questao, resultado in resultados_por_questao.items():
        if "erro" in resultado:
            print(f"  {nome_questao}: ERRO — {resultado['erro']}")
            continue
        linha = f"  {nome_questao}: {resultado['nota']['nota_final']:.2f}"
        if "nota_humana" in resultado:
            linha += f" (nota humana: {resultado['nota_humana']:.2f})"
        if resultado.get("escalonamentos"):
            linha += f"  [{len(resultado['escalonamentos'])} escalonado(s)]"
        if resultado["nota"]["avisos"]:
            linha += f"  [{len(resultado['nota']['avisos'])} aviso(s)]"
        print(linha)
    if modelo_escalonamento:
        print(f"Critérios escalonados para {modelo_escalonamento}: {total_escalonados}")
    if questoes_com_erro:
        print(
            f"ATENÇÃO: {len(questoes_com_erro)} questão(ões) FALHARAM e estão fora "
            f"da média: {', '.join(questoes_com_erro)}"
        )
    rotulo_media = "Média parcial" if questoes_com_erro else "Média"
    print(
        f"{rotulo_media} ({len(notas_validas)} de "
        f"{len(pastas_questoes)} questões avaliadas): {media:.2f}"
    )
    print(f"Tokens: {total_tokens['entrada']} entrada / {total_tokens['saida']} saída")

    pasta_saida = Path(args.saida)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta_saida / f"correcao_{args.aluno}_{timestamp}.json"
    caminho.write_text(
        json.dumps(
            {
                "aluno_id": args.aluno,
                "metadados_execucao": pipeline.metadados_execucao(rotulo_modelos),
                "media": media,
                "media_parcial": bool(questoes_com_erro),
                "questoes_anuladas_puladas": anuladas,
                "questoes_com_erro": questoes_com_erro,
                "total_tokens": total_tokens,
                "resultados_por_questao": resultados_por_questao,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nRelatório completo salvo em: {caminho}")


if __name__ == "__main__":
    main()
