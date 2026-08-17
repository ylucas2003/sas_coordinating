"""Camada de apresentação: monta a tabela comparativa em texto e salva o
relatório JSON completo. Sem chamadas de rede/LLM aqui.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from textwrap import shorten


def _truncar(texto: str, largura: int = 60) -> str:
    return shorten(texto or "", width=largura, placeholder="...")


def montar_tabela_comparativa(
    resultados_por_modelo: dict[str, dict], nota_humana: float | None
) -> str:
    """Monta uma tabela em texto puro comparando os modelos, critério a critério."""
    modelos = list(resultados_por_modelo.keys())
    largura_celula = 50

    criterios_ref = None
    for modelo in modelos:
        resultado = resultados_por_modelo[modelo]
        if resultado.get("erro") is None:
            criterios_ref = resultado["nota"]["detalhe_por_criterio"]
            break

    linhas = []

    if criterios_ref is None:
        linhas.append("Nenhum modelo completou o pipeline com sucesso.")
        for modelo in modelos:
            linhas.append(f"  {modelo}: {resultados_por_modelo[modelo].get('erro')}")
        return "\n".join(linhas)

    cabecalho = f"{'Critério':<12}" + "".join(
        f"| {modelo:<{largura_celula}} " for modelo in modelos
    )
    linhas.append(cabecalho)
    linhas.append("-" * len(cabecalho))

    for item_ref in criterios_ref:
        criterio_id = item_ref["criterio_id"]
        linha = f"{criterio_id:<12}"
        for modelo in modelos:
            resultado = resultados_por_modelo[modelo]
            if resultado.get("erro") is not None:
                celula = "(modelo falhou)"
            else:
                detalhe = next(
                    (
                        d
                        for d in resultado["nota"]["detalhe_por_criterio"]
                        if d["criterio_id"] == criterio_id
                    ),
                    None,
                )
                if detalhe is None:
                    celula = "(sem veredito)"
                else:
                    celula = _truncar(
                        f"{detalhe['veredito']}: {detalhe['justificativa']}",
                        largura_celula,
                    )
            linha += f"| {celula:<{largura_celula}} "
        linhas.append(linha)

    linhas.append("-" * len(cabecalho))

    resumo = f"Nota humana: {nota_humana:.2f}" if nota_humana is not None else "Nota humana: (nenhuma ainda)"
    for modelo in modelos:
        resultado = resultados_por_modelo[modelo]
        if resultado.get("erro") is not None:
            resumo += f" | {modelo}: FALHOU"
            continue
        nota_calculada = resultado["nota"]["nota_final"]
        if resultado.get("comparacao") is not None:
            delta = resultado["comparacao"]["delta"]
            sinal = "+" if delta >= 0 else ""
            resumo += f" | {modelo}: {nota_calculada:.2f} (Δ{sinal}{delta:.2f})"
        else:
            resumo += f" | {modelo}: {nota_calculada:.2f}"
    linhas.append(resumo)

    return "\n".join(linhas)


def salvar_relatorio_json(
    resultados_por_modelo: dict,
    *,
    questao_id: str,
    aluno_id: str,
    nota_humana: float | None,
    pasta_saida: Path,
    extras: dict | None = None,
) -> Path:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho = pasta_saida / f"{questao_id}_{aluno_id}_{timestamp}.json"

    relatorio = {
        "questao_id": questao_id,
        "aluno_id": aluno_id,
        "nota_humana": nota_humana,
        "gerado_em": timestamp,
        **(extras or {}),
        "resultados_por_modelo": resultados_por_modelo,
    }
    caminho.write_text(
        json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return caminho
