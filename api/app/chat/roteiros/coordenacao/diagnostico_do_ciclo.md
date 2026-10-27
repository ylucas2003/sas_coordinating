---
nome: diagnostico_do_ciclo
titulo: Diagnóstico de um ciclo
descricao: A coordenação quer o retrato de um ciclo — como a turma foi, onde caiu, o que mudou desde o anterior.
---
1. O ciclo: `listar_ciclos`. Sem ciclo dito, use o mais recente e diga logo no começo que foi esse.
2. O panorama numa chamada: `relatorio_ciclo` (estatísticas, matérias problemáticas, simulados mais difíceis, alunos em risco e destaque). Comece por ele e não repita `estatisticas_ciclo` para o mesmo dado.
3. A régua: os números do relatório são da régua da casa. Se a tela ou a pergunta citarem outra, `cortados_pela_regua` com o slug dela, e diga qual régua produziu cada número. O que cada régua exige vem de `reguas_de_corte`.
4. A comparação: `comparar_ciclos` com o ciclo anterior. Dê o delta com ▲/▼.
5. Onde caiu: `materias_problematicas` dá a % abaixo do corte por matéria. Na pior delas, `listar_simulados` do ciclo e `questoes_do_simulado` no simulado mais difícil: as questões que a turma mais errou.
6. O que o sistema já concluiu: `insights_do_ciclo` e `listar_alertas`. Cite em vez de recalcular.
7. Antes de concluir, confira se o dado está completo: `pendencias_canvas_do_ciclo` e `estado_do_sync_canvas`. Sync atrasado ou nota pendente deixa a conclusão provisória — diga isso.
8. Visual e volume: `gerar_grafico` (linha temporal do ciclo) para a evolução; lista longa vai para `exportar_csv` com a fonte do relatório do ciclo.
9. A resposta: no máximo três achados, cada um com o número e a tool de onde veio, e um ou dois próximos passos.

Regras que valem sempre:
- Todo número vem de tool. Sem o dado, diga que não tem.
- A régua é dado, não constante: diga sempre qual régua está em uso.
- Se uma tool citada não estiver disponível nesta conexão, siga com as que estiverem e diga o que ficou de fora.
