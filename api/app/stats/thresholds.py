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

# ─── Zona (regra ITA/IME) ─────────────────────────────────────────────────
#
# ITA e IME cortam por MATÉRIA, não por média geral: basta uma disciplina
# abaixo do mínimo para o candidato ser eliminado. O valor abaixo é o piso
# absoluto que vale tanto pra ITA quanto pra IME na Fase 2.

NOTA_CORTE_FASE_2 = 4.0

# Matérias core que entram no cálculo de "cortado" (Fase 2, escala 0-10).
# Mat / Fis / Quim / Port aparecem em ITA E IME. Inglês aparece só no IME.
# Redação tem tratamento especial (IME é binária); fica fora da regra de
# corte numérica mas continua sendo exibida na ficha.
MATERIAS_PARA_CORTE: tuple[str, ...] = ("matematica", "fisica", "quimica", "portugues")

# Acima do corte por uma margem confortável → zona "top".
MARGEM_TOP_SOBRE_CORTE = 1.0    # ex.: 4.0 + 1.0 = todas as matérias ≥ 5.0
# Atalho de risco: aluno passou no corte mas perigosamente perto.
MARGEM_RISCO_ABAIXO_CORTE = 0.0  # já é "cortado" se < corte exato

# Mantidos por compatibilidade — usados em comparações antigas com nota_corte
# genérica. Podem ser removidos quando nota_corte_vestibular sair do schema.
MARGEM_TOP = 0.5
MARGEM_RISCO = 0.5


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
