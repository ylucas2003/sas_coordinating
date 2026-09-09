-- Um aluno come UMA vez por refeição por dia, mesmo com duas cantinas
-- (docs/40 §12.12.2).
--
-- Até aqui a trava era `UNIQUE (cardapio_id, aluno_id)`: um pedido por
-- CARDÁPIO. Isso bastava porque existia uma cantina só — e "o almoço de
-- terça" e "o cardápio de almoço de terça" eram a mesma coisa.
--
-- Deixam de ser no dia em que a segunda cantina for cadastrada. Duas cantinas
-- publicando almoço na mesma terça são DOIS cardápios, e a trava atual permite
-- o aluno pedir nos dois — as duas cozinham para ele, e nada no sistema acusa.
-- Não é caso de borda: é o que o formulário do Google já registra hoje, na
-- coluna "LOCAL DA REFEIÇÃO", com os valores "Cantina" e "Food".
--
-- ⚠️ É o mesmo padrão que o docs/38 §1.1 registrou no `foto_perfil.py`:
-- premissa verdadeira até deixar de ser, e o dia em que deixa não vem com
-- aviso — vem com comida a mais na conta.
--
-- ⚠️ **A trava cobre os DOIS modos.** Pedido e retirada presencial são linhas
-- da mesma tabela, então declarar presença na Food e pedir na do Ari no mesmo
-- almoço passa a ser recusado. Hoje é aceito.
--
-- A trava ANTIGA fica de pé. Ela é subsumida por esta, mas continua sendo a
-- afirmação mais direta de "um pedido por cardápio" — e derrubá-la seria mexer
-- em duas coisas numa migration que já mexe em bastante.

BEGIN;

-- ── 1. As colunas ──
-- ⚠️ Isto é DESNORMALIZAÇÃO, e ela só é segura por causa de um fato
-- verificado: `data` e `refeicao` são IMUTÁVEIS depois de criado o cardápio.
-- O corpo do editor (`CardapioBody`, routes/cantina.py) não tem esses campos —
-- eles só existem em `NovoCardapioBody`, na criação. No dia em que alguém
-- acrescentar "mover cardápio de dia", esta cópia passa a divergir em
-- silêncio, e o conserto não é aqui: é não deixar mover.
--
-- Por que não uma trigger em vez da cópia: restrição de unicidade que
-- atravessa tabela NÃO EXISTE no Postgres, e uma trigger teria de resolver
-- concorrência à mão — dois pedidos simultâneos passariam pela checagem antes
-- de qualquer um gravar. O índice único é a única forma que o banco garante
-- sozinho.
ALTER TABLE pedido_refeicao
    ADD COLUMN IF NOT EXISTS data     date,
    ADD COLUMN IF NOT EXISTS refeicao text;

COMMENT ON COLUMN pedido_refeicao.data IS
    'Cópia de cardapio.data, escrita pelo servidor no INSERT. Existe só para o índice único de um-por-dia poder existir: unicidade não atravessa tabela no Postgres. Válida porque cardapio.data é imutável depois de criado (docs/40 §12.12.2).';
COMMENT ON COLUMN pedido_refeicao.refeicao IS
    'Cópia de cardapio.refeicao, pelo mesmo motivo de pedido_refeicao.data.';

-- ── 2. O backfill, ANTES do índice ──
UPDATE pedido_refeicao p
   SET data = c.data, refeicao = c.refeicao
  FROM cardapio c
 WHERE c.id = p.cardapio_id
   AND (p.data IS NULL OR p.refeicao IS NULL);

-- ── 3. A conferência, ANTES do índice ──
-- Sem isto, uma duplicata já gravada faria a criação do índice falhar com a
-- mensagem do Postgres ("could not create unique index") e a migration pararia
-- no meio, deixando as colunas criadas e o índice não — um estado que o runner
-- não sabe desfazer sozinho. Com duas cantinas ainda não cadastradas isso é
-- improvável; improvável não é o mesmo que impossível, e a diferença de custo
-- entre as duas mensagens é grande.
--
-- Para LISTAR as duplicatas antes de resolver:
--
--   SELECT c.data, c.refeicao, p.aluno_id, a.nome,
--          count(*) AS pedidos,
--          array_agg(p.id::text)          AS pedidos_ids,
--          array_agg(p.modo)              AS modos,
--          array_agg(ca.nome)             AS cantinas,
--          array_agg(p.criado_em::text)   AS quando
--     FROM pedido_refeicao p
--     JOIN cardapio c  ON c.id  = p.cardapio_id
--     JOIN cantina  ca ON ca.id = c.cantina_id
--     JOIN aluno    a  ON a.id  = p.aluno_id
--    GROUP BY c.data, c.refeicao, p.aluno_id, a.nome
--   HAVING count(*) > 1;
--
-- ⚠️ **Resolver é decisão de gente, não desta migration.** Apagar o pedido
-- "errado" automaticamente seria escolher, em nome da coordenação, qual
-- refeição um aluno não vai comer — e escolher errado não deixaria rastro.
-- Quem sabe qual das duas vale é quem serve.
DO $$
DECLARE
    duplicados int;
BEGIN
    SELECT count(*) INTO duplicados FROM (
        SELECT aluno_id, data, refeicao
          FROM pedido_refeicao
         WHERE data IS NOT NULL
         GROUP BY aluno_id, data, refeicao
        HAVING count(*) > 1
    ) d;

    IF duplicados > 0 THEN
        RAISE EXCEPTION
            'A 0055 não pode subir: % combinações (aluno, dia, refeição) têm mais de um pedido. A consulta que as lista está no comentário desta migration, logo acima do bloco DO. Resolver é decisão da coordenação: apagar o pedido errado por conta própria seria escolher qual refeição um aluno não vai comer.',
            duplicados;
    END IF;
END $$;

-- ── 4. As colunas passam a ser obrigatórias ──
-- Depois do backfill, e não antes: um NOT NULL declarado na criação recusaria
-- as linhas existentes.
ALTER TABLE pedido_refeicao
    ALTER COLUMN data     SET NOT NULL,
    ALTER COLUMN refeicao SET NOT NULL;

-- ── 5. A trava ──
CREATE UNIQUE INDEX IF NOT EXISTS pedido_refeicao_um_por_dia
    ON pedido_refeicao (aluno_id, data, refeicao);

COMMENT ON INDEX pedido_refeicao_um_por_dia IS
    'Um aluno come uma vez por refeição por dia, ainda que haja duas cantinas publicando o mesmo dia. Cobre os dois modos — pedido e retirada presencial são linhas da mesma tabela (docs/40 §12.12.2).';

COMMIT;
