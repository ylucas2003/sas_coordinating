-- Fecha o ciclo da publicação de aulas: leva o vídeo até o aluno (que vive no
-- Canvas, não no YouTube), dá ao coordenador uma tela para acompanhar, e
-- acrescenta o curso "SAS Preparatório ITA/IME 2026".
--
-- DECISÃO CENTRAL: o Canvas é um eixo SEPARADO do status do YouTube, mesmo
-- desenho de simulado.canvas_estado (0018). Se virasse mais um degrau de
-- `status`, os estados retentáveis passariam a incluir linhas que JÁ têm
-- vídeo no canal, e o guard antiduplicata de _processar_uma brigaria com o
-- pool de elegíveis — custando a invariante que impede segunda cópia de
-- menor de idade no canal (LGPD art. 18, VI) sem ganho nenhum.

BEGIN;

ALTER TABLE aula_gravacao
  ADD COLUMN canvas_estado text NOT NULL DEFAULT 'pendente'
    CHECK (canvas_estado IN ('pendente', 'publicado', 'falhou', 'ambiguo', 'conflito', 'ignorado')),
  ADD COLUMN canvas_pagina_url text,
  ADD COLUMN canvas_pagina_slug text,
  ADD COLUMN canvas_pagina_criada boolean NOT NULL DEFAULT false,
  ADD COLUMN canvas_erro text,
  ADD COLUMN canvas_tentativas integer NOT NULL DEFAULT 0,
  ADD COLUMN youtube_titulo text;

CREATE INDEX idx_aula_gravacao_canvas_estado ON aula_gravacao (canvas_estado);

COMMENT ON COLUMN aula_gravacao.canvas_estado IS
  'Eixo INDEPENDENTE do status do YouTube. ambiguo = mais de uma página candidata (não escreve); conflito = a página achada já tem outro vídeo (não escreve); ignorado = curso com publicar_no_canvas=false.';
COMMENT ON COLUMN aula_gravacao.canvas_pagina_slug IS
  'O campo `url` que a listagem do Canvas devolveu. NUNCA montar este slug: PUT /pages/{slug} num slug inexistente CRIA a página.';
COMMENT ON COLUMN aula_gravacao.youtube_titulo IS
  'Título REALMENTE publicado no YouTube; vira o title= do iframe. Guardado em vez de recomputado porque compor_titulo pode mudar, e aí o iframe divergiria do vídeo.';

-- 'aguardando_gravacao': conferência já agendada/ocorrida cuja gravação ainda
-- não ficou pronta no BigBlueButton. É o que permite mostrar aula FUTURA na
-- tela do coordenador. Fica FORA dos status retentáveis (ver rotas.py), então
-- o processar nunca a pega e ela não queima tentativa.
ALTER TABLE aula_gravacao DROP CONSTRAINT aula_gravacao_status_check;
ALTER TABLE aula_gravacao ADD CONSTRAINT aula_gravacao_status_check
  CHECK (status IN ('aguardando_gravacao', 'pendente', 'baixando', 'baixado', 'compondo',
                    'composto', 'publicando', 'publicado', 'publicado_sem_confirmacao', 'erro'));

-- Aula ainda não ocorrida não tem início de verdade.
ALTER TABLE aula_gravacao ALTER COLUMN iniciada_em DROP NOT NULL;

-- Interruptor da escrita no Canvas, por curso. Nasce DESLIGADO de propósito:
-- escrever na página errada de um curso com ~900 alunos é o pior desfecho
-- desta feature, e é silencioso. Liga-se um curso por vez, com UPDATE, depois
-- de conferir a saída de POST /gravacoes-aula/publicar-no-canvas?simular=true.
ALTER TABLE curso_monitorado_gravacao
  ADD COLUMN publicar_no_canvas boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN curso_monitorado_gravacao.publicar_no_canvas IS
  'false = só publica no YouTube. O 581 fica false: não tem páginas de aula, só "Prova - ...".';

-- Curso novo. professor_padrao fica NULL porque as conferências dele já
-- trazem o nome do professor no próprio título.
INSERT INTO curso_monitorado_gravacao (curso_id, nome, professor_padrao) VALUES
  ('581', 'SAS Preparatório ITA/IME 2026', NULL)
ON CONFLICT (curso_id) DO NOTHING;

COMMIT;
