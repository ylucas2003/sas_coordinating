-- Reverte a 0029. DESTRUTIVO e sem volta: as listas montadas e o que cada
-- aluno marcou como resolvido só existem aqui — não há JSON de origem que os
-- regenere, ao contrário da 0028.
BEGIN;
DROP TABLE IF EXISTS questao_estudo_aluno;
DROP TABLE IF EXISTS lista_questoes_item;
DROP TABLE IF EXISTS lista_questoes;
COMMIT;
