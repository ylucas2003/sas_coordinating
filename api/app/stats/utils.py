"""Helpers estatísticos sem dependência externa (scipy/numpy).

Todas as fórmulas aqui usam só `math` + `statistics` da stdlib. Suficiente
pra escala atual do SAS (~milhares de alunos, ~dezenas de simulados).
"""

from __future__ import annotations

import hashlib
import json
import math
import statistics as st
from typing import Iterable, Sequence


# ─── Regressão linear simples ─────────────────────────────────────────────


def regressao_linear(valores_y: list[float]) -> tuple[float, float]:
    """Mínimos quadrados sobre x = 0, 1, ..., n-1.

    Retorna (slope, t_statistic). Para n < 3 o t_statistic é 0 (não
    significativo). Usado pra classificar tendência das notas do aluno.
    """
    n = len(valores_y)
    if n < 2:
        return 0.0, 0.0

    x = list(range(n))
    x_med = sum(x) / n
    y_med = sum(valores_y) / n

    numerador = sum((x[i] - x_med) * (valores_y[i] - y_med) for i in range(n))
    denominador = sum((x[i] - x_med) ** 2 for i in range(n))
    if denominador == 0:
        return 0.0, 0.0

    slope = numerador / denominador
    if n < 3:
        return slope, 0.0

    intercept = y_med - slope * x_med
    soma_quadrados_residuos = sum(
        (valores_y[i] - (intercept + slope * x[i])) ** 2 for i in range(n)
    )
    # Erro padrão do slope.
    sigma2 = soma_quadrados_residuos / (n - 2)
    se_slope = math.sqrt(sigma2 / denominador) if denominador > 0 else 0
    if se_slope == 0:
        return slope, 0.0
    t_stat = slope / se_slope
    return slope, t_stat


# Valores críticos de t-Student (bicaudal, α=0.10) por graus de liberdade.
# Fonte: tabela padrão; aceitos pra "tendência detectável" no contexto SAS.
_T_CRITICOS = {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895}


def t_critico(graus_liberdade: int) -> float:
    """t crítico bicaudal a 10%. Acima de 7 df aproxima por 1.86 (assintótico)."""
    return _T_CRITICOS.get(graus_liberdade, 1.86)


# ─── Welch t-test ─────────────────────────────────────────────────────────


def welch_t_test(amostra_a: list[float], amostra_b: list[float]) -> tuple[float, float]:
    """Welch t-statistic e p-valor aproximado (bicaudal).

    Aproximação do p: para df > 30 usa CDF normal (z = t). Suficiente pra
    detectar diferença entre sedes na escala do SAS (centenas de alunos).
    """
    n_a, n_b = len(amostra_a), len(amostra_b)
    if n_a < 2 or n_b < 2:
        return 0.0, 1.0

    media_a = sum(amostra_a) / n_a
    media_b = sum(amostra_b) / n_b
    var_a = st.variance(amostra_a)
    var_b = st.variance(amostra_b)
    if var_a == 0 and var_b == 0:
        return 0.0, 1.0

    se = math.sqrt(var_a / n_a + var_b / n_b)
    if se == 0:
        return 0.0, 1.0

    t = (media_a - media_b) / se
    # Welch-Satterthwaite df:
    num = (var_a / n_a + var_b / n_b) ** 2
    den = ((var_a / n_a) ** 2) / (n_a - 1) + ((var_b / n_b) ** 2) / (n_b - 1)
    df = num / den if den > 0 else (n_a + n_b - 2)

    # p-valor — aproximação por CDF normal (válida para df >= 30).
    z = abs(t)
    p = 2 * (1 - _cdf_normal(z))
    _ = df  # mantido só pra leitura/debug
    return t, p


def _cdf_normal(z: float) -> float:
    """CDF da normal padrão via fórmula de erf (math.erf)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


# ─── Histograma fixo (bins de largura constante) ──────────────────────────


def histograma_bins(valores: Iterable[float], *, largura_bin: float, maximo: float) -> dict:
    """Conta valores em bins [0, largura), [largura, 2·largura), ..., [maximo-largura, maximo].

    `maximo` deve ser múltiplo (ou aproximadamente) de `largura_bin`. Valores
    fora do range são clipados pro último bin. Retorna o payload que vai pra
    `metrica_simulado.histograma` em JSONB.
    """
    if maximo <= 0:
        maximo = 10.0
    n_bins = max(1, int(round(maximo / largura_bin)))
    contagens = [0] * n_bins

    for v in valores:
        if v is None:
            continue
        idx = int(v / largura_bin)
        if idx < 0:
            idx = 0
        elif idx >= n_bins:
            idx = n_bins - 1
        contagens[idx] += 1

    return {
        "largura_bin": largura_bin,
        "maximo": maximo,
        "contagens": contagens,
    }


# ─── Percentil (interpolação linear) ──────────────────────────────────────


def percentil(valores: list[float], p: float) -> float | None:
    """Percentil p (0 a 100). Para listas vazias retorna None."""
    if not valores:
        return None
    if len(valores) == 1:
        return valores[0]
    ordenados = sorted(valores)
    indice = (p / 100) * (len(ordenados) - 1)
    inf = int(math.floor(indice))
    sup = int(math.ceil(indice))
    if inf == sup:
        return ordenados[inf]
    fracao = indice - inf
    return ordenados[inf] + (ordenados[sup] - ordenados[inf]) * fracao


# ─── Forma da distribuição ────────────────────────────────────────────────


def skewness(valores: list[float]) -> float | None:
    """Coeficiente de assimetria amostral (Fisher-Pearson ajustado).

    Positivo  → cauda à direita (poucas notas altas puxam a média acima da mediana).
    Negativo  → cauda à esquerda.
    Próximo 0 → simétrica.

    Retorna None se n < 3 ou desvio padrão = 0 (todos os valores iguais).
    """
    n = len(valores)
    if n < 3:
        return None
    media = sum(valores) / n
    desvio = st.stdev(valores)
    if desvio == 0:
        return None
    m3 = sum((v - media) ** 3 for v in valores) / n
    g1 = m3 / (desvio ** 3)
    # Ajuste amostral (mesma fórmula que numpy.stats.skew com bias=False).
    return g1 * math.sqrt(n * (n - 1)) / (n - 2)


def kurtosis(valores: list[float]) -> float | None:
    """Excesso de curtose amostral (Fisher: normal ≈ 0).

    Positivo  → caudas mais pesadas que a normal (outliers).
    Negativo  → distribuição mais "achatada" (platicúrtica).

    Retorna None se n < 4 ou desvio padrão = 0.
    """
    n = len(valores)
    if n < 4:
        return None
    media = sum(valores) / n
    desvio = st.stdev(valores)
    if desvio == 0:
        return None
    m4 = sum((v - media) ** 4 for v in valores) / n
    g2 = m4 / (desvio ** 4) - 3
    # Ajuste amostral (alinha com scipy.stats.kurtosis(bias=False)).
    fator = ((n - 1) / ((n - 2) * (n - 3))) * ((n + 1) * g2 + 6)
    return fator


def moda_histograma(contagens: list[int], largura_bin: float) -> float | None:
    """Centro do bin mais alto. Estimativa rápida da moda quando o dado é contínuo.

    Em caso de empate, devolve o centro do primeiro bin máximo (ordem natural).
    """
    if not contagens or max(contagens) == 0:
        return None
    idx = contagens.index(max(contagens))
    return (idx + 0.5) * largura_bin


def detectar_bimodalidade(contagens: list[int], *, min_vale_ratio: float = 0.7) -> bool:
    """Heurística: existem ≥ 2 picos locais separados por um vale "profundo"?

    Um pico é um índice cujo valor é maior que ambos vizinhos. Um par de picos
    conta como bimodalidade se o vale entre eles tem altura ≤ `min_vale_ratio`
    do menor dos dois picos.

    Suficiente pra sinalizar "duas turmas" sem trazer scipy (dip test).
    """
    n = len(contagens)
    if n < 5:
        return False

    picos: list[int] = []
    for i in range(1, n - 1):
        if contagens[i] > contagens[i - 1] and contagens[i] > contagens[i + 1]:
            picos.append(i)
    # Considera extremidades só se houver gradiente claro (evita ruído nas bordas).
    if contagens[0] > contagens[1] > 0:
        picos.insert(0, 0)
    if contagens[-1] > contagens[-2] > 0:
        picos.append(n - 1)

    if len(picos) < 2:
        return False

    # Mantém só picos "altos" (≥ 15% do maior pico) para ignorar ruído.
    altura_max = max(contagens[i] for i in picos)
    significativos = [i for i in picos if contagens[i] >= 0.15 * altura_max]
    if len(significativos) < 2:
        return False

    # Procura pelo menos um par com vale profundo entre eles.
    for a, b in zip(significativos, significativos[1:]):
        vale = min(contagens[a + 1 : b]) if b - a > 1 else min(contagens[a], contagens[b])
        menor_pico = min(contagens[a], contagens[b])
        if menor_pico == 0:
            continue
        if vale <= min_vale_ratio * menor_pico:
            return True
    return False


# ─── Taxas por corte ──────────────────────────────────────────────────────


def taxas_por_corte(
    valores: list[float],
    *,
    corte: float,
    excelencia: float = 7.0,
) -> tuple[float | None, float | None, float | None]:
    """Devolve (pct_aprovados, pct_zona_critica, pct_excelencia).

    - pct_aprovados      : nota ≥ corte
    - pct_zona_critica   : nota em [corte − 1, corte)   (passou, mas perigosamente perto)
    - pct_excelencia     : nota ≥ excelencia

    Todos como percentual 0–100. None se a amostra estiver vazia.
    """
    n = len(valores)
    if n == 0:
        return None, None, None
    aprovados = sum(1 for v in valores if v >= corte)
    criticos = sum(1 for v in valores if corte - 1 <= v < corte)
    excelentes = sum(1 for v in valores if v >= excelencia)
    return (
        round(100 * aprovados / n, 2),
        round(100 * criticos / n, 2),
        round(100 * excelentes / n, 2),
    )


# ─── Hash estável de payload (pra cache de insights) ──────────────────────


def hash_payload_estavel(payload: dict | list) -> str:
    """sha256 truncado (32 chars) de um payload arbitrário.

    Usa JSON com chaves ordenadas pra ser determinístico entre execuções.
    Reusado pelo cache de insight_ciclo: hash igual → dado igual → reusa texto.
    """
    canonico = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:32]


# ─── Hash de dedup pra alertas ────────────────────────────────────────────


def hash_dedup_alerta(
    *,
    categoria: str,
    entidade_tipo: str,
    entidade_id: str,
    janela_chave: str,
) -> str:
    """Hash estável de (categoria, entidade, janela). Idempotente entre reuploads."""
    chave = f"{categoria}|{entidade_tipo}|{entidade_id}|{janela_chave}"
    return hashlib.sha256(chave.encode("utf-8")).hexdigest()[:32]


# ─── Conversão segura pra float ───────────────────────────────────────────


def como_float(valor) -> float | None:
    """Converte um valor (Decimal, str, int, float) para float, ou None se falhar."""
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


# ─── Normalização de pontuação para nota 0-10 ─────────────────────────────


def nota_real(pontuacao: float | None, nota_maxima: float | None) -> float | None:
    """Converte pontuação bruta (acertos) para nota em escala 0–10.

    A planilha do Canvas guarda em `Points Possible` o **número de questões**
    da prova (variando entre simulados — 10, 12, 15, 20...). A coluna
    `nota.pontuacao` é quantas questões o aluno acertou. A "nota" exibida
    é sempre `(acertos / total) * 10`.

    Retorna None se pontuação for None ou nota_maxima for None/0.

    Casos:
      - Mat com 15 questões, aluno acertou 13   → 13/15 * 10 = 8,67
      - Português com 20 questões, aluno fez 12 → 12/20 * 10 = 6,00
      - Redação com escala 10 já direta, fez 7  → 7/10 * 10 = 7,00 ✓
    """
    if pontuacao is None or not nota_maxima:
        return None
    return (pontuacao / nota_maxima) * 10.0
