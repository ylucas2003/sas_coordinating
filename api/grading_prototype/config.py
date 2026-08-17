"""Constantes e configuração do protótipo — lê o .env sem depender de app.config.

Deliberadamente não importa `app.config.get_settings()`: esta pasta precisa
poder ser deletada ou copiada pra outro lugar sem levar nada de `app/` junto.
`load_dotenv()` sobe a árvore de diretórios a partir do cwd até achar um
`.env` — como o protótipo é rodado a partir de `api/` (mesma convenção de
`scripts/`), ele encontra o mesmo `api/.env` já usado pela aplicação.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

# Modelos comparados por padrão no harness (nessa ordem no relatório).
MODELOS_PADRAO: list[str] = ["gpt-4o-mini", "gpt-4o"]

# Fluxo de dois níveis da correção: o barato avalia tudo; critérios com
# gatilho (desconto, equivalência alegada, evidência copiada, 'confere'
# suspeito) são confirmados individualmente no forte. Nota não desce sem
# confirmação do modelo forte.
MODELO_AVALIADOR_BARATO = "gpt-4o-mini"
MODELO_ESCALONAMENTO = "gpt-4o"
MODELO_RUBRICA = "gpt-4o"  # rubrica é custo único por questão — não economizar aqui

# Temperatura baixa — reprodutibilidade entre execuções importa mais aqui
# do que na feature de chat (que usa 0.2).
TEMPERATURA = 0.0

MAX_TOKENS_RUBRICA = 2500
MAX_TOKENS_CRITICA = 2500
MAX_TOKENS_AVALIACAO = 2500

# Paralelização de corrigir_prova.py (questões independentes).
MAX_WORKERS_CORRECAO = 4

# Parâmetro `detail` da API de visão da OpenAI. "high" é necessário pra ter
# alguma chance de ler notação matemática/física manuscrita — custa mais
# tokens de imagem que "low"/"auto".
DETALHE_IMAGEM = "high"

# Lado maior da imagem, em pixels, após redimensionamento. Fotos de celular
# costumam vir com 12MP+; isso limita o custo de tokens de visão sem perder
# legibilidade útil.
MAX_DIMENSAO_IMAGEM_PX = 2000

# --- Placeholders tuneáveis do motor de nota (ver pontuacao.py) ---
# Crédito dado a um critério "parcial", como fração do critério "atendido".
PESO_CREDITO_PARCIAL = 0.5

# Diferença (em pontos, base 10) considerada aceitável entre a nota calculada
# e a nota do corretor humano, usada só pro relatório indicar "dentro da
# margem" — não afeta o cálculo da nota em si.
MARGEM_ACEITAVEL_NOTA = 1.0


def get_openai_api_key() -> str:
    """Lê OPENAI_API_KEY do .env (mesmo arquivo usado por `app/`)."""
    load_dotenv()
    return os.getenv("OPENAI_API_KEY", "")
