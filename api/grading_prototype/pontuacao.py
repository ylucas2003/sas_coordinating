"""Motor determinístico de nota — puro Python, ZERO import de `openai`.

A IA nunca decide a nota (ver `avaliador.py`) — este é o único lugar onde os
vereditos por critério viram uma nota 0-10. Roda como `python -m
grading_prototype.pontuacao` para o self-test, sem precisar de API key —
não há pytest no repo, então isto é a checagem mínima do único componente
que precisa estar 100% correto.

Casos degenerados vindos da LLM são tratados com avisos explícitos, nunca
silenciosamente: critério da rubrica sem veredito (vira 0 com aviso),
criterio_id duplicado (ocorrência extra ignorada com aviso), veredito
`nao_avaliavel` (0 pontos + aviso destacado — sinal de revisão humana),
critério com pontuação <= 0 na rubrica (aviso forte).
"""

from __future__ import annotations

from . import config

MULTIPLICADOR_POR_VEREDITO = {
    "atendido": 1.0,
    "parcial": config.PESO_CREDITO_PARCIAL,
    "nao_atendido": 0.0,
    # Ilegível/em branco/não encontrado: 0 pontos, mas sinalizado com aviso
    # destacado — é um pedido de revisão humana, não um julgamento de mérito.
    "nao_avaliavel": 0.0,
}


def derivar_veredito(item: dict) -> str:
    """Política de correção em CÓDIGO: converte as respostas factuais do
    avaliador (aluno_demonstrou_o_objetivo × comparacao_resultado) no
    veredito. A LLM nunca escolhe 'parcial'/'atendido' diretamente — modelos
    baratos erram justamente na aplicação da política, não na leitura.

    Regras (decisão do dono do projeto):
    - demonstrou + resultado confere/equivalente/sem resultado âncora -> atendido
    - demonstrou + resultado diverge -> parcial (método certo, conta errada:
      o erro custa parte do crédito no critério de conclusão, não tudo)
    - demonstrou parcialmente -> parcial
    - não demonstrou -> nao_atendido
    - ilegível/não encontrado -> nao_avaliavel (revisão humana)
    """
    demonstrou = item.get("aluno_demonstrou_o_objetivo")
    comparacao = item.get("comparacao_resultado")

    if demonstrou == "nao_encontrei_ou_ilegivel":
        return "nao_avaliavel"
    if demonstrou == "nao":
        return "nao_atendido"
    if demonstrou == "parcialmente":
        return "parcial"
    if demonstrou == "sim":
        if comparacao == "diverge":
            return "parcial"
        if comparacao == "aluno_nao_declarou":
            # Demonstrou o objetivo mas não fechou o valor pedido.
            return "parcial"
        return "atendido"
    # Campo ausente/inesperado — trata como não avaliável pra forçar revisão.
    return "nao_avaliavel"


def calcular_nota(rubrica_final: dict, avaliacao: dict) -> dict:
    """Combina os pesos da rubrica com os vereditos da avaliação numa nota 0-10."""
    pontuacao_max_por_id = {c["id"]: c["pontuacao"] for c in rubrica_final["criterios"]}
    soma_maxima = sum(pontuacao_max_por_id.values())

    avisos: list[str] = []

    # Evidência "encontrada" que é cópia literal das evidências ESPERADAS da
    # rubrica não é evidência da resposta do aluno — o veredito pode até
    # estar certo, mas fica inauditável. Flag determinística pra revisão.
    esperadas_por_id = {
        c["id"]: set(c.get("evidencias_esperadas", []))
        for c in rubrica_final["criterios"]
    }
    for item in avaliacao["avaliacoes_por_criterio"]:
        esperadas = esperadas_por_id.get(item["criterio_id"], set())
        copiadas = [
            ev for ev in item.get("evidencias_encontradas", []) if ev in esperadas
        ]
        if copiadas:
            avisos.append(
                f"REVISÃO HUMANA: evidências do critério '{item['criterio_id']}' "
                f"são cópia literal da rubrica ({len(copiadas)} item(ns)) — o "
                f"veredito não está ancorado na resposta do aluno."
            )

    criterios_rubrica = rubrica_final["criterios"]
    if len(pontuacao_max_por_id) < len(criterios_rubrica):
        avisos.append(
            "Rubrica tem criterio_id duplicado — ocorrências repetidas foram "
            "colapsadas; revise a rubrica."
        )
    for c in criterios_rubrica:
        if c["pontuacao"] <= 0:
            avisos.append(
                f"Rubrica inválida: critério '{c['id']}' tem pontuação "
                f"{c['pontuacao']} (<= 0) — o passo correspondente não vale "
                f"nada; revise a rubrica."
            )

    if soma_maxima <= 0:
        avisos.append("Soma de pontuação da rubrica é zero ou negativa.")
    elif abs(soma_maxima - 10.0) > 0.5:
        avisos.append(
            f"Soma de pontuação da rubrica ({soma_maxima}) difere de 10.0 — "
            f"nota final normalizada para base 10."
        )

    detalhe_por_criterio = []
    soma_obtida = 0.0
    ids_processados: set[str] = set()
    for item in avaliacao["avaliacoes_por_criterio"]:
        criterio_id = item["criterio_id"]
        veredito = item["veredito"]

        pontuacao_max = pontuacao_max_por_id.get(criterio_id)
        if pontuacao_max is None:
            avisos.append(
                f"Critério '{criterio_id}' da avaliação não existe na rubrica — ignorado."
            )
            continue

        if criterio_id in ids_processados:
            avisos.append(
                f"Critério '{criterio_id}' apareceu mais de uma vez na avaliação — "
                f"ocorrência extra ignorada (vale a primeira)."
            )
            continue
        ids_processados.add(criterio_id)

        multiplicador = MULTIPLICADOR_POR_VEREDITO.get(veredito)
        if multiplicador is None:
            avisos.append(
                f"Veredito desconhecido '{veredito}' para '{criterio_id}' — "
                f"tratado como não atendido."
            )
            multiplicador = 0.0

        if veredito == "nao_avaliavel":
            avisos.append(
                f"REVISÃO HUMANA: critério '{criterio_id}' marcado como "
                f"nao_avaliavel (ilegível/ausente) — 0 pontos atribuídos "
                f"provisoriamente."
            )

        pontuacao_obtida = pontuacao_max * multiplicador
        soma_obtida += pontuacao_obtida
        detalhe_por_criterio.append(
            {
                "criterio_id": criterio_id,
                "pontuacao_max": pontuacao_max,
                "veredito": veredito,
                "multiplicador": multiplicador,
                "pontuacao_obtida": round(pontuacao_obtida, 3),
                "justificativa": item.get("justificativa", ""),
            }
        )

    # Critérios da rubrica que o avaliador NÃO cobriu: 0 pontos, mas nunca
    # silenciosamente — entrada sintética visível no relatório + aviso.
    for criterio_id, pontuacao_max in pontuacao_max_por_id.items():
        if criterio_id in ids_processados:
            continue
        avisos.append(
            f"Critério '{criterio_id}' da rubrica ficou SEM veredito do "
            f"avaliador — tratado como 0 pontos; revise."
        )
        detalhe_por_criterio.append(
            {
                "criterio_id": criterio_id,
                "pontuacao_max": pontuacao_max,
                "veredito": "sem_veredito",
                "multiplicador": 0.0,
                "pontuacao_obtida": 0.0,
                "justificativa": "(o avaliador não emitiu veredito para este critério)",
            }
        )

    nota_final = round(10 * soma_obtida / soma_maxima, 2) if soma_maxima > 0 else 0.0

    return {
        "nota_final": nota_final,
        "soma_pontuacao_maxima": soma_maxima,
        "detalhe_por_criterio": detalhe_por_criterio,
        "avisos": avisos,
    }


def comparar_com_nota_humana(
    nota_calculada: float,
    nota_humana: float,
    *,
    margem_aceitavel: float = config.MARGEM_ACEITAVEL_NOTA,
) -> dict:
    delta = round(nota_calculada - nota_humana, 2)
    return {
        "delta": delta,
        "delta_absoluto": abs(delta),
        "dentro_da_margem": abs(delta) <= margem_aceitavel,
    }


if __name__ == "__main__":
    rubrica_teste = {
        "criterios": [
            {"id": "c1", "pontuacao": 4.0},
            {"id": "c2", "pontuacao": 3.0},
            {"id": "c3", "pontuacao": 3.0},
        ]
    }

    # Caso 1: tudo atendido -> nota 10, sem avisos.
    avaliacao_tudo_certo = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c3", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_tudo_certo)
    assert resultado["nota_final"] == 10.0, resultado
    assert resultado["avisos"] == []

    # Caso 2: atendido + parcial + não atendido -> 4 + 1.5 + 0 = 5.5.
    avaliacao_mista = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "parcial", "justificativa": ""},
            {"criterio_id": "c3", "veredito": "nao_atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_mista)
    assert resultado["nota_final"] == 5.5, resultado

    # Caso 3: rubrica que soma 15 (não 10) -> normaliza + avisa.
    rubrica_desbalanceada = {
        "criterios": [
            {"id": "a", "pontuacao": 5.0},
            {"id": "b", "pontuacao": 5.0},
            {"id": "c", "pontuacao": 5.0},
        ]
    }
    avaliacao_parcial = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "a", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "b", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c", "veredito": "nao_atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_desbalanceada, avaliacao_parcial)
    assert resultado["nota_final"] == 6.67, resultado
    assert any("difere de 10.0" in aviso for aviso in resultado["avisos"])

    # Caso 4: criterio_id da avaliação não existe na rubrica -> avisa e ignora.
    avaliacao_com_id_invalido = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c3", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "inexistente", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_com_id_invalido)
    assert resultado["nota_final"] == 10.0
    assert any("não existe na rubrica" in aviso for aviso in resultado["avisos"])

    # Caso 5: avaliador OMITE um critério -> 0 pontos, aviso + entrada sintética.
    avaliacao_com_omissao = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_com_omissao)
    assert resultado["nota_final"] == 7.0, resultado  # 4 + 3 de 10
    assert any("SEM veredito" in aviso for aviso in resultado["avisos"])
    sinteticas = [d for d in resultado["detalhe_por_criterio"] if d["veredito"] == "sem_veredito"]
    assert len(sinteticas) == 1 and sinteticas[0]["criterio_id"] == "c3"

    # Caso 6: criterio_id DUPLICADO na avaliação -> vale a primeira, extra ignorada.
    avaliacao_com_duplicata = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c3", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_com_duplicata)
    assert resultado["nota_final"] == 10.0, resultado  # jamais > 10
    assert any("mais de uma vez" in aviso for aviso in resultado["avisos"])

    # Caso 6b: duplicata com vereditos conflitantes -> vale a primeira.
    avaliacao_duplicata_conflito = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "nao_atendido", "justificativa": ""},
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c3", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_duplicata_conflito)
    assert resultado["nota_final"] == 6.0, resultado  # c1 nao_atendido (primeira)
    assert len(resultado["detalhe_por_criterio"]) == 3

    # Caso 7: veredito nao_avaliavel -> 0 pontos + aviso de revisão humana.
    avaliacao_ilegivel = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "nao_avaliavel", "justificativa": "ilegível"},
            {"criterio_id": "c3", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_teste, avaliacao_ilegivel)
    assert resultado["nota_final"] == 7.0, resultado
    assert any("REVISÃO HUMANA" in aviso for aviso in resultado["avisos"])

    # Caso 8: rubrica com critério de pontuação 0 -> aviso forte.
    rubrica_com_zero = {
        "criterios": [
            {"id": "c1", "pontuacao": 10.0},
            {"id": "c2", "pontuacao": 0.0},
        ]
    }
    avaliacao_zero = {
        "avaliacoes_por_criterio": [
            {"criterio_id": "c1", "veredito": "atendido", "justificativa": ""},
            {"criterio_id": "c2", "veredito": "atendido", "justificativa": ""},
        ]
    }
    resultado = calcular_nota(rubrica_com_zero, avaliacao_zero)
    assert any("<= 0" in aviso for aviso in resultado["avisos"])

    # Casos da política derivar_veredito (fatos -> veredito).
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "sim", "comparacao_resultado": "confere"}) == "atendido"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "sim", "comparacao_resultado": "equivalente_em_outra_forma"}) == "atendido"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "sim", "comparacao_resultado": "sem_resultado_esperado"}) == "atendido"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "sim", "comparacao_resultado": "diverge"}) == "parcial"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "sim", "comparacao_resultado": "aluno_nao_declarou"}) == "parcial"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "parcialmente", "comparacao_resultado": "confere"}) == "parcial"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "nao", "comparacao_resultado": "confere"}) == "nao_atendido"
    assert derivar_veredito({"aluno_demonstrou_o_objetivo": "nao_encontrei_ou_ilegivel", "comparacao_resultado": "sem_resultado_esperado"}) == "nao_avaliavel"
    assert derivar_veredito({}) == "nao_avaliavel"

    # Caso 9: evidência copiada literalmente da rubrica -> aviso de revisão.
    rubrica_com_evidencias = {
        "criterios": [
            {
                "id": "c1",
                "pontuacao": 10.0,
                "evidencias_esperadas": ["Cálculo correto de b²=32."],
            },
        ]
    }
    avaliacao_evidencia_copiada = {
        "avaliacoes_por_criterio": [
            {
                "criterio_id": "c1",
                "veredito": "atendido",
                "justificativa": "",
                "evidencias_encontradas": ["Cálculo correto de b²=32."],
            },
        ]
    }
    resultado = calcular_nota(rubrica_com_evidencias, avaliacao_evidencia_copiada)
    assert any("cópia literal da rubrica" in aviso for aviso in resultado["avisos"])

    # comparar_com_nota_humana
    comparacao = comparar_com_nota_humana(7.5, 7.0)
    assert comparacao["delta"] == 0.5
    assert comparacao["dentro_da_margem"] is True

    comparacao = comparar_com_nota_humana(7.5, 4.0, margem_aceitavel=1.0)
    assert comparacao["dentro_da_margem"] is False

    print("pontuacao.py: todos os self-tests passaram.")
