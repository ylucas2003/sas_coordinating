"""Banco de questões de prova passada de ITA e IME (docs/22).

934 questões de 2018 a 2025 — Física, Química e Matemática — classificadas por
tópico do edital. Aqui mora o domínio: importação, consulta, agregação e
listas. O HTTP fica em `routes/banco.py`; os tipos da fronteira, em
`schemas/banco.py`.

⚠️ `questao_vestibular` NÃO é `questao`. `questao` (migration 0010) é questão de
um simulado-Quiz do Canvas e tem `simulado_id NOT NULL`; a daqui é questão de
prova pública, sem simulado nenhum. Os dois nomes convivem de propósito —
confundi-los é o risco nº 1 do sprint (docs/22 §8).
"""
