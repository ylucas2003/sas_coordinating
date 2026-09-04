-- Volta a calibração do índice para os valores de fábrica do código.
--
-- Seguro por construção: pela regra 2 da migration de subida, a leitura já
-- funciona sem esta tabela — `banco/importancia.py` tem os mesmos números como
-- padrão. Derrubá-la faz o índice voltar a H = 5 fixo, não faz o índice sumir.
--
-- O que se perde é o HISTÓRICO de versões: se a coordenação já girou o botão,
-- o registro de quem girou e para quanto vai junto. Por isso, num banco onde a
-- tela de edição já foi usada, exportar `parametro_importancia` antes.

BEGIN;

DROP TABLE IF EXISTS parametro_importancia;

COMMIT;
