"""Motor de lembretes (P2) — regras, disparos e despacho.

O motor não conhece o domínio: ele lê disparo → regra_lembrete → evento_agenda
e para aí (requisito de docs/10 §2.2.2). Quem sabe que o evento é um simulado
é a aplicação (rota de agendamento), que cria a regra.

Nunca chamar isto de "alerta" — alerta já é sinal pedagógico do SAS
(routes/alertas.py). Ver docs/12-plano-p2-motor-lembretes.md.
"""
