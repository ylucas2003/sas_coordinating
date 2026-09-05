-- Reverte a 0047.
--
-- ⚠️ NÃO DESÇA SÓ ESTA MIGRATION enquanto a API de 05/09 em diante estiver no
-- ar. `app/routes/auth.py` consulta `usuario_cantina` no ramo
-- `tipo == "cantina"`, e tabela ausente não é lista vazia: o PostgREST devolve
-- 404 e o postgrest-py levanta APIError, que vira 500 na porta da cantina.
-- Ordem obrigatória: a API volta para a versão anterior à 0047, e só então
-- este `down`.
--
-- DESTRUTIVO: apaga as contas da cantina. Refazê-las é trabalho de
-- administrador, uma a uma — não há de onde restaurar.
--
-- A ordem dos DROPs é a das dependências: `usuario_cantina` referencia
-- `cantina`.

BEGIN;

DROP TABLE IF EXISTS usuario_cantina;
DROP TABLE IF EXISTS cantina;

COMMIT;
