-- Reverte a 0028. DESTRUTIVO e SEM VOLTA desde que os JSONs saíram do git
-- (docs/22 §13): estas tabelas são a fonte da verdade, não uma projeção.
--
-- Antes de rodar isto, rode `python -m scripts.exportar_banco_questoes` — é o
-- que devolve as 934 questões a arquivo. Sem esse passo, o que se apaga aqui só
-- existe em backup do Postgres, se houver.
BEGIN;
DROP TABLE IF EXISTS questao_vestibular_topico;
DROP TABLE IF EXISTS topico_taxonomia_assunto;
DROP TABLE IF EXISTS topico_taxonomia;
DROP TABLE IF EXISTS questao_vestibular_alternativa;
DROP TABLE IF EXISTS questao_vestibular;
COMMIT;
