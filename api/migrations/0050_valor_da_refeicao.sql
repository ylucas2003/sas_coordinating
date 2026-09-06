-- Quanto custa cada refeição, por cantina (docs/38 §2.1).
--
-- Pedido da coordenação em 06/09: ao cadastrar a cantina, dizer o valor do
-- almoço e o da janta. É preço de TABELA da casa, não cobrança: o SAS não
-- fatura, não concilia e não sabe quem pagou — a decisão 8.1.5 ("benefício
-- binário, sem cobrança") continua de pé. O valor existe para a coordenação
-- somar o custo do que foi pedido, que é a pergunta que ela faz no fim do mês.
--
-- ⚠️ `numeric` e não `float`: dinheiro em ponto flutuante acumula centavo
-- errado, e aqui o número vai ser somado sobre centenas de pedidos.
--
-- Anulável de propósito. As cantinas que já existem não têm valor, e inventar
-- zero para elas seria pior que a ausência: zero é um preço, `NULL` é "ninguém
-- disse ainda" — e a tela precisa saber a diferença para não somar R$ 0,00
-- como se fosse informação.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

ALTER TABLE cantina
    ADD COLUMN IF NOT EXISTS valor_almoco numeric(10, 2)
        CONSTRAINT cantina_valor_almoco_nao_negativo CHECK (valor_almoco >= 0),
    ADD COLUMN IF NOT EXISTS valor_janta numeric(10, 2)
        CONSTRAINT cantina_valor_janta_nao_negativo CHECK (valor_janta >= 0);

COMMENT ON COLUMN cantina.valor_almoco IS
    'Preço de tabela do almoço, em reais. NULL = ainda não informado, que é diferente de 0,00. O SAS não cobra: serve para a coordenação somar o custo do que foi pedido (docs/38 §2.1).';
COMMENT ON COLUMN cantina.valor_janta IS
    'Preço de tabela da janta, em reais. Mesma regra do almoço.';

COMMIT;
