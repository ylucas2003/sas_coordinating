-- Quanto valia a refeição no instante em que o pedido foi feito
-- (docs/40 §12.11.2).
--
-- A 0050 deu à cantina `valor_almoco` e `valor_janta` — valor de TABELA, o que
-- vale hoje. Isso serve para a tela de hoje somar `pedidos × valor`, e não
-- serve para relatório nenhum: no dia em que o almoço subir de R$ 18 para
-- R$ 21, todo relatório já emitido passa a dizer outro número.
--
--   preço do almoço: R$ 18,00 até 15/03 · R$ 21,00 a partir de 16/03
--   com carimbo   10 × 18,00 + 12 × 21,00 = R$ 432,00   ✓
--   sem carimbo   22 × 21,00              = R$ 462,00   ✗  30 reais que ninguém gastou
--
-- Por que no PEDIDO e não numa tabela de vigência: o pedido é o fato, e o
-- preço no instante do fato é atributo dele. Vigência depende de alguém
-- cadastrar a data certa, e uma data errada reescreve o mês sem avisar.
--
-- ⚠️ **Isto NÃO é cobrança.** Continua não havendo fatura, "quem pagou" nem
-- conciliação — a fronteira do docs/38 §8.1.5 segue de pé. O carimbo existe
-- para o relatório não mentir, não para cobrar de ninguém.

BEGIN;

ALTER TABLE pedido_refeicao ADD COLUMN IF NOT EXISTS valor_cobrado numeric(10,2);

COMMENT ON COLUMN pedido_refeicao.valor_cobrado IS
    'Quanto valia a refeição quando ESTE pedido foi feito, copiado de cantina.valor_almoco/valor_janta. Anulável: NULL é "não havia valor cadastrado", diferente de 0,00. Não é cobrança — não existe fatura nem pagamento (docs/40 §12.11.2).';

-- ── Backfill ──
-- Os pedidos que já existem nasceram sem carimbo. Preencher com o valor de
-- HOJE é aceitável por um motivo verificável, e não por conveniência: o preço
-- nunca mudou desde que a coluna existe (a 0050 é de 06/09). No dia em que
-- mudar, esta afirmação deixa de valer — e é por isso que ela está escrita
-- aqui, e não presumida.
--
-- Fica `NULL` onde a cantina ainda não disse o preço, que é o estado de
-- "ninguém informou" que a 0050 criou de propósito.
UPDATE pedido_refeicao p
   SET valor_cobrado = CASE c.refeicao
       WHEN 'almoco' THEN ca.valor_almoco
       WHEN 'janta'  THEN ca.valor_janta
   END
  FROM cardapio c
  JOIN cantina ca ON ca.id = c.cantina_id
 WHERE c.id = p.cardapio_id
   AND p.valor_cobrado IS NULL;

COMMIT;
