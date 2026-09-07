-- Reverte a 0051.
--
-- ⚠️ NÃO DESÇA SÓ ESTA MIGRATION com a API de 07/09 em diante no ar. As rotas
-- de retirada (`POST /me/cantina/retiradas/{id}`, `POST
-- /cantina/retiradas/confirmar`) leem e escrevem `pedido_refeicao.modo`, e
-- coluna ausente não é valor nulo: o PostgREST devolve 400 e o postgrest-py
-- levanta APIError, que vira 500 no balcão. Ordem obrigatória: a API volta para
-- a versão anterior à 0051, e só então este `down`.
--
-- DESTRUTIVO em um ponto: `retirado_em` é a única prova de que aquele aluno
-- passou pelo balcão, e ela não existe em nenhuma outra fonte — a trilha de
-- `evento_auditoria` guarda que a cantina confirmou, mas não é de onde o
-- produto lê. As linhas presenciais SOBREVIVEM ao down como se fossem pedidos
-- normais (sem itens), porque `modo` some e o resto da linha fica: uma retirada
-- vira um pedido vazio na contagem da cantina.

BEGIN;

ALTER TABLE cardapio
    DROP COLUMN IF EXISTS aceita_pedido,
    DROP COLUMN IF EXISTS aceita_presencial;

ALTER TABLE cantina
    DROP COLUMN IF EXISTS aceita_pedido_almoco,
    DROP COLUMN IF EXISTS aceita_pedido_janta,
    DROP COLUMN IF EXISTS aceita_presencial_almoco,
    DROP COLUMN IF EXISTS aceita_presencial_janta;

ALTER TABLE pedido_refeicao
    DROP COLUMN IF EXISTS modo,
    DROP COLUMN IF EXISTS retirado_em;

COMMIT;
