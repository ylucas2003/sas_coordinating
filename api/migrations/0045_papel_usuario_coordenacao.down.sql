-- Reverte a 0045.
--
-- DESTRUTIVO no sentido que importa: apaga QUEM é administrador. Voltar a
-- subir a 0045 devolve todo mundo para 'coordenador' (o default), e a
-- promoção precisa ser refeita à mão.
--
-- O código que lê a coluna trata a ausência dela como "todo mundo é
-- coordenador" (app/auth.py: token sem `papel` vale como coordenador), então
-- descer isto NÃO tranca ninguém do lado de fora — só devolve a `PATCH /notas`
-- e as rotas de conta para a coordenação inteira.

BEGIN;

ALTER TABLE usuario_coordenacao DROP COLUMN IF EXISTS papel;

COMMIT;
