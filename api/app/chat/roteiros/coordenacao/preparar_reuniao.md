---
nome: preparar_reuniao
titulo: Preparar uma reunião
descricao: Montar a pauta de uma reunião sobre um aluno (com a família ou com professores) ou sobre a turma de um ciclo.
---
1. Pergunte, se não estiver claro: é sobre um aluno ou sobre a turma? Com quem é a reunião?

Sobre um aluno:
2. Ache o aluno: `buscar_aluno_por_nome` (ou `buscar_aluno_por_matricula`). Mais de um com o mesmo nome? Pergunte qual.
3. O retrato: `relatorio_aluno`; por ciclo, `historico_aluno`; a direção, `tendencia_aluno`.
4. Para a família, a evolução desenhada ajuda: `gerar_grafico` com a linha temporal do aluno.
5. Nota alterada é assunto delicado: se houver dúvida sobre uma nota, `historico_de_alteracoes` diz quem mudou, quando e de quanto para quanto.

Sobre a turma de um ciclo:
6. `relatorio_ciclo`, `comparar_ciclos` com o anterior e `materias_problematicas`.
7. Os dois lados: `alunos_destaque` e `alunos_em_risco` — com professores, agrupe por matéria e não exponha nomes sem necessidade.
8. O que vem pela frente: `lembretes_agendados` mostra os próximos simulados com aviso marcado.

A pauta:
9. Três a cinco pontos, cada um com o número, a tool de onde veio e uma pergunta para a reunião discutir.
10. Feche com um ou dois encaminhamentos possíveis, como opção — quem decide é a coordenação.

Regras que valem sempre:
- Todo número vem de tool. Sem o dado, diga que não tem.
- A régua é dado, não constante: diga sempre qual régua está em uso.
- Se uma tool citada não estiver disponível nesta conexão, siga com as que estiverem e diga o que ficou de fora.
