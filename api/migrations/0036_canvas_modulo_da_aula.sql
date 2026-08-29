-- Onde a página da aula fica pendurada no Canvas.
--
-- Criar a página NÃO a coloca em módulo nenhum: são dois objetos distintos na
-- API, e o aluno navega por módulo. As quatro primeiras páginas criadas pela
-- automação (29/08/2026) nasceram publicadas e fora de módulo — existiam, mas
-- ninguém as achava. Foram penduradas à mão; daqui em diante o código pendura.

ALTER TABLE curso_monitorado_gravacao
  ADD COLUMN canvas_modulo_id text;

COMMENT ON COLUMN curso_monitorado_gravacao.canvas_modulo_id IS
  'Módulo que recebe a página quando o ASSUNTO não decidir sozinho. Fica NULO '
  'no 691 de propósito: aquele curso tem duas trilhas paralelas (Trigonometria '
  'e Números Complexos) com aulas alternadas, e um módulo fixo penduraria '
  'metade das aulas na trilha errada — lá quem decide é o assunto.';

ALTER TABLE aula_gravacao
  ADD COLUMN canvas_modulo_nome text;

COMMENT ON COLUMN aula_gravacao.canvas_modulo_nome IS
  'Módulo em que a página foi pendurada. NULO com canvas_estado=publicado '
  'significa página criada e fora de módulo: existe, mas o aluno não acha. '
  'A tela de Integrações mostra isso para alguém arrastar.';

-- Os módulos escolhidos com a coordenação em 29/08/2026, conferidos na API.
UPDATE curso_monitorado_gravacao SET canvas_modulo_id = '2738' WHERE curso_id = '692';
UPDATE curso_monitorado_gravacao SET canvas_modulo_id = '2744' WHERE curso_id = '693';
UPDATE curso_monitorado_gravacao SET canvas_modulo_id = '2609' WHERE curso_id = '581';
