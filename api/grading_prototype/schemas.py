"""JSON schemas para as chamadas de LLM (modo strict da OpenAI).

Modo strict exige `additionalProperties: false` e todo campo em `required`
— não existe "opcional de verdade"; usamos lista/string vazia como valor de
"nada aqui" quando necessário. Mesmo formato de `SCHEMA_SAIDA` em
`api/app/stats/insights.py`.

Nota sobre ORDEM dos campos: em geração autoregressiva a LLM produz os
campos na ordem em que aparecem no schema. No schema de avaliação, o
veredito vem POR ÚLTIMO de propósito — o modelo primeiro cita evidências,
declara o resultado do aluno e justifica, e só então decide (evita
decidir-primeiro-racionalizar-depois).
"""

import copy

_CRITERIO_RUBRICA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "pontuacao": {"type": "number"},
        "objetivo_pedagogico": {"type": "string"},
        "evidencias_esperadas": {"type": "array", "items": {"type": "string"}},
        "resultados_esperados": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Valores/conclusões extraídos do gabarito que qualquer método "
                "válido deve produzir (ex: 'n = 15', 'área = 30'). Lista vazia "
                "para critérios de método puro sem resultado âncora."
            ),
        },
        "metodos_alternativos_aceitos": {"type": "array", "items": {"type": "string"}},
        "erros_comuns": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "id",
        "pontuacao",
        "objetivo_pedagogico",
        "evidencias_esperadas",
        "resultados_esperados",
        "metodos_alternativos_aceitos",
        "erros_comuns",
    ],
    "additionalProperties": False,
}

SCHEMA_RUBRICA = {
    "type": "object",
    "properties": {
        "criterios": {"type": "array", "items": _CRITERIO_RUBRICA},
    },
    "required": ["criterios"],
    "additionalProperties": False,
}

_CRITERIO_RUBRICA_CRITICADA = {
    "type": "object",
    "properties": {
        **_CRITERIO_RUBRICA["properties"],
        "foi_reescrito": {"type": "boolean"},
        "motivo_alteracao": {"type": "string"},
    },
    "required": [*_CRITERIO_RUBRICA["required"], "foi_reescrito", "motivo_alteracao"],
    "additionalProperties": False,
}

# `metodos_alternativos_considerados` vem ANTES de `criterios` de propósito:
# obriga o crítico a enumerar os métodos-teste antes de revisar cada critério
# (geração autoregressiva segue a ordem do schema).
SCHEMA_RUBRICA_CRITICADA = {
    "type": "object",
    "properties": {
        "metodos_alternativos_considerados": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "2-3 métodos alternativos válidos de resolver esta questão, "
                "usados como teste contra cada critério."
            ),
        },
        "criterios": {"type": "array", "items": _CRITERIO_RUBRICA_CRITICADA},
        "resumo_geral": {"type": "string"},
    },
    "required": ["metodos_alternativos_considerados", "criterios", "resumo_geral"],
    "additionalProperties": False,
}

VEREDITOS_VALIDOS = ["atendido", "nao_atendido", "parcial", "nao_avaliavel"]

# A LLM NÃO escolhe veredito: ela responde às perguntas FACTUAIS abaixo e o
# veredito é derivado deterministicamente pela política em pontuacao.py
# (derivar_veredito). Isso tira da LLM a parte que modelos baratos mais
# erram — aplicar política de correção — e deixa com ela só a leitura.
DEMONSTROU_VALORES = ["sim", "parcialmente", "nao", "nao_encontrei_ou_ilegivel"]
COMPARACAO_VALORES = [
    "confere",
    "equivalente_em_outra_forma",
    "diverge",
    "aluno_nao_declarou",
    "sem_resultado_esperado",
]

# Ordem dos campos deliberada (geração autoregressiva segue o schema):
# evidências -> método -> resultado declarado -> comparação -> demonstrou ->
# justificativa. Os fatos vêm antes dos julgamentos.
_AVALIACAO_CRITERIO = {
    "type": "object",
    "properties": {
        "criterio_id": {"type": "string"},
        "evidencias_encontradas": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Citações/paráfrases fiéis DA RESPOSTA DO ALUNO, com "
                "localização (ex: 'no item ii'). Nunca copie a rubrica."
            ),
        },
        "metodo_do_aluno": {
            "type": "string",
            "description": "Em uma frase: que método o aluno usou nesta parte.",
        },
        "resultado_declarado_pelo_aluno": {
            "type": "string",
            "description": (
                "O valor/conclusão que o ALUNO declarou para este critério, "
                "transcrito da resposta dele. String vazia se não se aplica."
            ),
        },
        "comparacao_resultado": {
            "type": "string",
            "enum": COMPARACAO_VALORES,
            "description": (
                "Compare o resultado declarado com os resultados_esperados do "
                "critério, POR VALOR (use a aproximação decimal quando houver)."
            ),
        },
        "aluno_demonstrou_o_objetivo": {
            "type": "string",
            "enum": DEMONSTROU_VALORES,
            "description": (
                "O aluno demonstrou o objetivo pedagógico do critério, por "
                "QUALQUER método válido? (independente de erros de conta, que "
                "já foram capturados em comparacao_resultado)"
            ),
        },
        "justificativa": {"type": "string"},
    },
    "required": [
        "criterio_id",
        "evidencias_encontradas",
        "metodo_do_aluno",
        "resultado_declarado_pelo_aluno",
        "comparacao_resultado",
        "aluno_demonstrou_o_objetivo",
        "justificativa",
    ],
    "additionalProperties": False,
}

SCHEMA_AVALIACAO = {
    "type": "object",
    "properties": {
        "avaliacoes_por_criterio": {"type": "array", "items": _AVALIACAO_CRITERIO},
        "observacoes_gerais": {"type": "string"},
    },
    "required": ["avaliacoes_por_criterio", "observacoes_gerais"],
    "additionalProperties": False,
}


def schema_avaliacao_para(criterio_ids: list[str]) -> dict:
    """SCHEMA_AVALIACAO com `criterio_id` restrito por enum aos ids reais da
    rubrica — garantia estrutural contra a LLM inventar um id inexistente.
    (Omissão/duplicação de critério não são evitáveis por schema; o motor de
    nota trata esses casos com avisos — ver pontuacao.py.)"""
    schema = copy.deepcopy(SCHEMA_AVALIACAO)
    item = schema["properties"]["avaliacoes_por_criterio"]["items"]
    item["properties"]["criterio_id"] = {"type": "string", "enum": list(criterio_ids)}
    return schema
