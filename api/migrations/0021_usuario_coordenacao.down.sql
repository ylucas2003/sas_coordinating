-- Reverte a 0021. DESTRUTIVO: apaga os usuários da coordenação criados desde
-- então. Depois disto o login volta a depender de COORDENADOR_EMAIL/SENHA no
-- ambiente — que precisam continuar preenchidas para o sistema não ficar sem
-- nenhuma forma de entrar.
BEGIN;
DROP TABLE IF EXISTS usuario_coordenacao;
COMMIT;
