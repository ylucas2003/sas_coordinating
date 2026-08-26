"""aplicar_patch_historico.py — Aplica o resultado do workflow de classificação
sobre os JSONs do acervo histórico (extrair_lote_historico.py já os criou,
vazios de classificação/resolução).

Lê o journal.jsonl de um workflow do Claude Code (cada linha um evento; as do
tipo "result" trazem o retorno de cada agente: {prova_id, questoes: [...]}) e
escreve em cada questoes_json/{prova_id}/qNN.json:

  - classificacao.topicos_ids/topicos_nomes/blocos/observacao/classificado_por
  - gabarito + gabarito_origem='sugerido' + gabarito_confianca — SÓ quando a
    questão não tinha gabarito de banca E o agente respondeu confiança alta.
    Confiança média/baixa não vira letra na tela — fica só a resolução
    (calibrado em 220 questões de gabarito conhecido: 99,5% de acerto na faixa
    alta, ver relatório do piloto).
  - resolucao_md + resolucao_origem='sugerida'

Uso:
    python aplicar_patch_historico.py <journal.jsonl> [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJETO_ROOT = Path(__file__).resolve().parent.parent
DIR_QUESTOES = PROJETO_ROOT / "questoes_json"
DIR_CONFIG = PROJETO_ROOT / "config"

ARQUIVO_TAXONOMIA = {
    "Física": "taxonomia-fisica.json",
    "Química": "taxonomia-quimica.json",
    "Matemática": "taxonomia-matematica.json",
}

# Não colhida nesta rodada (o schema do workflow só pediu confiança do
# GABARITO, não da classificação por tópico) — "alta" é o piso seguro: no banco
# já em produção, 890 das 894 questões classificadas por IA são "alta" (docs/22
# §7.5), e aqui a mesma tarefa (ler enunciado, apontar assunto do edital) não
# fica mais incerta só por a prova ser mais antiga.
CONFIANCA_CLASSIFICACAO_PADRAO = "alta"


def carregar_indices_taxonomia() -> dict[str, dict[str, dict]]:
    indices = {}
    for materia, arquivo in ARQUIVO_TAXONOMIA.items():
        dados = json.loads((DIR_CONFIG / arquivo).read_text(encoding="utf-8"))
        indice = {}
        for bloco in dados["blocos"]:
            for sub in bloco["subareas"]:
                indice[sub["id"]] = {"nome": sub["nome"], "bloco": bloco["nome"]}
        indices[materia] = indice
    return indices


def ler_resultados(journal: Path) -> dict[str, list[dict]]:
    """{prova_id: [questoes]}.

    Uma prova grande demais para um agente só (estourou o teto de tokens de
    saída — aconteceu com `ita_2014_fase1`, 20 objetivas com resolução longa)
    é dividida em duas chamadas com o mesmo prova_id e faixas de número
    diferentes. Por isso aqui é MERGE por número de questão, não substituição:
    a última resposta de cada NÚMERO vence (cobre também o caso normal de um
    workflow retomado reexecutar algum item)."""
    resultados: dict[str, dict[int, dict]] = {}
    for linha in journal.read_text(encoding="utf-8").splitlines():
        evento = json.loads(linha)
        if evento.get("type") != "result":
            continue
        r = evento.get("result")
        if not (isinstance(r, dict) and "prova_id" in r and "questoes" in r):
            continue
        por_numero = resultados.setdefault(r["prova_id"], {})
        for q in r["questoes"]:
            por_numero[q["numero"]] = q
    return {prova_id: list(qs.values()) for prova_id, qs in resultados.items()}


def aplicar(
    resultados: dict[str, list[dict]], indices: dict, dry_run: bool, marcar_corrigido: bool = False
) -> dict:
    relatorio = {
        "provas_aplicadas": 0, "questoes_aplicadas": 0,
        "gabaritos_sugeridos_alta": 0, "gabaritos_descartados_baixa_media": 0,
        "avisos": [],
    }

    for prova_id, questoes in resultados.items():
        dir_prova = DIR_QUESTOES / prova_id
        if not dir_prova.is_dir():
            relatorio["avisos"].append(f"{prova_id}: pasta não existe, pulando")
            continue

        for q in questoes:
            num = q["numero"]
            caminho = dir_prova / f"q{num:02d}.json"
            if not caminho.exists():
                relatorio["avisos"].append(f"{prova_id} q{num:02d}: arquivo não existe")
                continue

            dados = json.loads(caminho.read_text(encoding="utf-8"))
            # Defesa contra vazamento de prova de PRODUÇÃO para dentro de um lote
            # histórico (aconteceu com `ime_2018_fase1_qui`: mesma faixa de ano do
            # filtro, schema mais velho — sem "status"/"dissertativa"/"gabarito").
            # Pular com aviso é sempre melhor que travar o lote inteiro no meio.
            if "status" not in dados or "dissertativa" not in dados:
                relatorio["avisos"].append(
                    f"{prova_id} q{num:02d}: schema sem 'status'/'dissertativa' — "
                    f"provável prova de produção vazada para o lote; PULADA sem gravar nada."
                )
                continue
            materia = dados["prova"]["materia"]
            indice = indices.get(materia, {})

            ids = [c for c in q.get("topicos_ids", []) if c in indice]
            invalidos = [c for c in q.get("topicos_ids", []) if c not in indice]
            if invalidos:
                relatorio["avisos"].append(f"{prova_id} q{num:02d}: tópico inválido {invalidos}")

            dados["classificacao"] = {
                "topicos_ids": ids,
                "topicos_nomes": [indice[c]["nome"] for c in ids],
                "blocos": sorted({indice[c]["bloco"] for c in ids}),
                "classificado_por": "claude",
                "confianca": CONFIANCA_CLASSIFICACAO_PADRAO,
                "observacao": q.get("observacao", ""),
            }
            dados["status"]["classificado"] = bool(ids)

            # Gabarito sugerido: só entra se a questão não tinha letra de banca
            # E a confiança do agente foi "alta". Média/baixa fica sem letra —
            # a resolução ainda aparece, só que sem afirmar uma resposta.
            if not dados["dissertativa"] and not dados.get("gabarito"):
                letra = q.get("gabarito_sugerido")
                conf = q.get("confianca_gabarito")
                if letra and conf == "alta":
                    dados["gabarito"] = letra
                    dados["gabarito_origem"] = "sugerido"
                    dados["gabarito_confianca"] = "alta"
                    relatorio["gabaritos_sugeridos_alta"] += 1
                elif letra:
                    relatorio["gabaritos_descartados_baixa_media"] += 1

            resolucao = q.get("resolucao_md")
            if resolucao:
                dados["resolucao_md"] = resolucao
                dados["resolucao_origem"] = "sugerida"

            if marcar_corrigido:
                # Evita que uma segunda rodada do workflow de correção
                # reprocesse (e gaste agente com) o que já viu a imagem.
                dados["_corrigido_com_imagem"] = True

            if not dry_run:
                caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
            relatorio["questoes_aplicadas"] += 1

        relatorio["provas_aplicadas"] += 1

    return relatorio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("journal", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--marcar-corrigido", action="store_true",
                    help="Marca _corrigido_com_imagem=true (uso: aplicar o resultado do workflow de correção)")
    args = ap.parse_args()

    indices = carregar_indices_taxonomia()
    resultados = ler_resultados(args.journal)
    print(f"{len(resultados)} provas no journal", file=sys.stderr)

    relatorio = aplicar(resultados, indices, args.dry_run, args.marcar_corrigido)
    print(json.dumps(relatorio, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
