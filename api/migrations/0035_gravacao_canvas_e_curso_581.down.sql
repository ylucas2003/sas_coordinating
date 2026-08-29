BEGIN;

DELETE FROM curso_monitorado_gravacao WHERE curso_id = '581';

ALTER TABLE curso_monitorado_gravacao DROP COLUMN IF EXISTS publicar_no_canvas;

DROP INDEX IF EXISTS idx_aula_gravacao_canvas_estado;

ALTER TABLE aula_gravacao
  DROP COLUMN IF EXISTS canvas_estado,
  DROP COLUMN IF EXISTS canvas_pagina_url,
  DROP COLUMN IF EXISTS canvas_pagina_slug,
  DROP COLUMN IF EXISTS canvas_pagina_criada,
  DROP COLUMN IF EXISTS canvas_erro,
  DROP COLUMN IF EXISTS canvas_tentativas,
  DROP COLUMN IF EXISTS youtube_titulo;

-- Volta o CHECK e o NOT NULL anteriores. Se houver linha em
-- 'aguardando_gravacao' (ou com iniciada_em nulo), este down FALHA de
-- propósito: apagá-las às cegas perderia aula detectada.
DELETE FROM aula_gravacao WHERE status = 'aguardando_gravacao';

ALTER TABLE aula_gravacao DROP CONSTRAINT aula_gravacao_status_check;
ALTER TABLE aula_gravacao ADD CONSTRAINT aula_gravacao_status_check
  CHECK (status IN ('pendente', 'baixando', 'baixado', 'compondo', 'composto',
                    'publicando', 'publicado', 'publicado_sem_confirmacao', 'erro'));

ALTER TABLE aula_gravacao ALTER COLUMN iniciada_em SET NOT NULL;

COMMIT;
