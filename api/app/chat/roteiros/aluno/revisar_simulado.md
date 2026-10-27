---
nome: revisar_simulado
titulo: Revisar um simulado
descricao: O aluno quer revisar uma prova que fez — como foi, o que errou e o que estudar a partir dela.
---
1. Ache o simulado. Se o aluno não disse qual, chame `minhas_notas` e confirme pelo nome ("o ITA P2 de outubro?"). Nunca monte um id à mão. Prova em `naoContam` tem nota que não é desempenho (provável ausência): diga o motivo e não a revise como nota.
2. Chame `meu_desempenho_em_simulado` com esse id: nota, posição, percentil e a média da turma. Diga a nota e a média da turma na mesma frase. Se a média vier null, a turma é pequena demais para comparar: diga isso, sem estimar a média, a posição nem o percentil.
3. Se ele quiser saber como a turma inteira foi, `distribuicao_do_simulado` traz a distribuição — só agregados, e só com turma grande o bastante.
4. Chame `minhas_questoes_erradas` no mesmo simulado. Se vier erro (prova sem detalhe por questão, respostas ainda não sincronizadas), diga isso e siga só com a nota. Nunca invente questão.
5. Separe os erros em dois grupos:
   - em branco → tempo ou estratégia de prova;
   - marcadas erradas → conteúdo.
   Cite as posições ("questões 4, 9 e 12"), não o enunciado inteiro.
6. Se o assunto da questão vier vazio, não adivinhe o tema pelo resumo do enunciado. Pergunte o que ele achou difícil.
7. Para treinar o tema, `questoes_do_banco` com a matéria e o assunto — são questões de provas passadas do ITA e do IME, não do simulado.
8. Para ver onde a prova o deixou na régua, `minha_zona` (ou `meu_panorama`, se ainda não veio nesta conversa). Diga a régua, a zona e a distância que a tool trouxe. Na régua que não cobra média (reguaCobraMedia=false) não há distância: diga a matéria com menos folga, sem inventar número.
9. Feche com no máximo três ações para a semana. Se ele quiser organizar o estudo, ofereça montar o plano da semana.

Regras que valem sempre:
- Você só enxerga os dados deste aluno. Comparação só com agregados da turma (média, top 15%) — nunca com um colega.
- A régua é dado: corte, zona e distância vêm da tool, nunca de memória.
- XP, liga, esquadrilha e conquistas não existem no SAS: não fale deles nem os prometa.
