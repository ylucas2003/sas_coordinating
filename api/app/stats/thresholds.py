"""Constantes calibráveis do stats engine.

Ficam num arquivo só pra coordenação editar à mão depois de calibrar com
dados reais (ver questão #5 em docs/06-open-questions.md).
"""

# ─── Classificação ────────────────────────────────────────────────────────

# Janela de simulados considerados em média recente / tendência / perfil.
JANELA_CLASSIFICACAO = 5

# Tendência: slope mínimo (em pontos por simulado) para considerar movimento
# real, antes ainda do teste-t. Valores menores que isso = "estável".
SLOPE_MINIMO = 0.15

# Perfil âncora: aluno está acima do percentil X da turma E com desvio baixo.
PERCENTIL_ANCORA = 85
FATOR_DESVIO_ANCORA = 0.25  # desvio do aluno < FATOR * desvio_padrao_turma

# Perfil mistério: desvio do aluno > FATOR * mediana_desvios_turma.
FATOR_DESVIO_MISTERIO = 2.0

# ─── Zona (regra ITA/IME) — MUDOU DE ARQUIVO ─────────────────────────────
#
# `NOTA_CORTE_FASE_2`, `CORTE_INGLES_ITA_F1`, `MATERIAS_PARA_CORTE` e
# `MARGEM_TOP_SOBRE_CORTE` moravam aqui e saíram em 30/08/2026.
#
# O critério da separação: **se o número tem artigo de edital, é regra; se ele
# foi escolhido por nós olhando dados, é calibração.** Regra é dado, mora em
# `criterios.py` e tem versão; calibração é constante, mora aqui e se edita à
# mão. Enquanto os dois estavam no mesmo arquivo, um corte de edital era
# editável como se fosse um parâmetro nosso — e a Fase 2 acabou com 4,0 aqui e
# 5,0 no front (docs/18 §1.1).
#
# Onde procurar agora:
#   corte por matéria .......... criterios.corte_da_materia(criterio, materia)
#   corte da média ............. criterios.corte_da_media(criterio)
#   margem da zona "top" ....... criterios.MARGEM_CONFORTAVEL
#   régua quando ninguém escolheu   criterios.CRITERIO_DA_CASA
#
# `MARGEM_TOP` e `MARGEM_RISCO` também saíram: eram código morto desde que
# `nota_corte_vestibular` deixou de ser lido.


# ─── Alertas ──────────────────────────────────────────────────────────────

# QUEDA_RENDIMENTO / SUBIDA_ATIPICA — média(últimos 3) − média(3 anteriores).
DELTA_QUEDA_SUBIDA = 1.5
JANELA_QUEDA_SUBIDA = 3

# PROVA_MAL_CALIBRADA — desvio do simulado vs. histórico do mesmo ciclo/fase.
MULTIPLO_VARIANCIA = 2.0

# MATERIA_EM_RISCO — N simulados consecutivos abaixo do histórico − 1σ.
N_SIMULADOS_MATERIA_RISCO = 3
DELTA_DESVIO_MATERIA = 1.0

# DIFERENCA_ENTRE_SEDES — Welch t-test entre sedes.
P_VALOR_MAX_SEDES = 0.05
DELTA_MIN_SEDES = 0.5

# Auto-arquivar alertas antigos não resolvidos (rodar via cron — fora do MVP).
DIAS_AUTO_ARQUIVAR = 30
