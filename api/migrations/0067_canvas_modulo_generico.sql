-- O módulo "Outras aulas gravadas": último recurso para pendurar a página.
--
-- Até aqui, quando nem o assunto nem o módulo padrão (0036) decidiam, a página
-- ficava publicada e fora de módulo. O aluno navega por módulo, então não a
-- achava, e 'publicado' é terminal: ninguém tentava de novo. Com a coordenação,
-- em 30/09/2026, ficou decidido que cada curso tem um módulo publicado com esse
-- nome. A ordem passa a ser assunto → módulo padrão → genérico, e a coordenação
-- arrasta dali para a trilha certa.
--
-- Não há id para semear: o código cria o módulo na primeira vez que ele faz
-- falta (ou adota um que alguém criou à mão com o mesmo nome) e grava aqui.

ALTER TABLE curso_monitorado_gravacao
  ADD COLUMN canvas_modulo_generico_id text;

COMMENT ON COLUMN curso_monitorado_gravacao.canvas_modulo_generico_id IS
  'Módulo "Outras aulas gravadas" do curso: recebe a página quando nem o '
  'assunto nem canvas_modulo_id decidem. Nulo até a primeira vez que faz '
  'falta; aí app/gravacoes_aula/canvas_publicacao.py cria (ou acha pelo nome) '
  'e grava. É pelo id, e não pelo nome, para que renomear o módulo no Canvas '
  'não faça nascer um segundo.';
