---
nome: alunos_em_risco
titulo: Alunos em risco
descricao: Quem está em risco agora, por qual motivo, e o que a coordenação pode fazer com cada grupo.
---
1. A lista: `alunos_em_risco` (régua da casa). Para a régua de um edital, `cortados_pela_regua` com o ciclo (`listar_ciclos`) e o slug (`reguas_de_corte`). Diga qual régua cortou.
2. O motivo, até cinco alunos por vez: `relatorio_aluno` ou `tendencia_aluno`. Separe:
   - matéria abaixo do corte, ou eliminatória;
   - média abaixo do corte;
   - queda recente (tendência caindo).
3. Falta ou nota? `historico_aluno` mostra as ausências. Zero que é falta não é desempenho: diga quando o risco vem de ausência.
4. Os sinais que o sistema já deu: `listar_alertas` (queda de desempenho, variância). Cite o alerta em vez de recalcular.
5. Quem parece com quem: `alunos_similares` ajuda a achar o grupo de um caso, e `comparar_alunos` põe até cinco lado a lado.
6. Lista longa: agrupe pela causa ("quatro seguram em Química; dois caíram nas últimas provas") em vez de aluno por aluno.
7. Para cada grupo, uma ação concreta: reforço na matéria, conversa individual, conferir a presença.
8. Mais de quinze nomes: ofereça `exportar_csv` com os alunos da zona de risco.
9. Nos alunos citados, `navegar_para` dá o link da ficha. Fora do app, identifique o aluno como a tool devolveu — `buscar_aluno_por_matricula` acha pela matrícula.

Regras que valem sempre:
- Todo número vem de tool. Não invente critério de risco: ele está codificado nas tools.
- A régua é dado, não constante: diga sempre qual régua está em uso.
- Se uma tool citada não estiver disponível nesta conexão, siga com as que estiverem e diga o que ficou de fora.
