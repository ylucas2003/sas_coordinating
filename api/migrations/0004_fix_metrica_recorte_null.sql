-- ─────────────────────────────────────────────────────────────────────────
-- 0004 · permitir recorte_id NULL em metrica_simulado
--
-- Bug original (0001): a PK (simulado_id, recorte_tipo, recorte_id) faz com
-- que `recorte_id` seja implicitamente NOT NULL no Postgres. Isso impede o
-- caso `recorte_tipo='geral'`, que por design não tem recorte específico
-- (não é de uma turma nem de uma sede em particular).
--
-- Correção: trocar a PK por um UNIQUE NULLS NOT DISTINCT (Postgres 15+).
-- Esse modo trata NULL = NULL para fins de uniqueness, então:
--   - apenas UMA linha 'geral' por simulado é aceita
--   - múltiplas linhas turma/sede continuam permitidas (diferentes recorte_id)
-- ─────────────────────────────────────────────────────────────────────────

ALTER TABLE metrica_simulado
    DROP CONSTRAINT metrica_simulado_pkey;

-- Postgres não tira o NOT NULL automaticamente quando dropa a PK — tem que
-- ser explícito. Sem isso, o INSERT com recorte_id=NULL ainda falha.
ALTER TABLE metrica_simulado
    ALTER COLUMN recorte_id DROP NOT NULL;

ALTER TABLE metrica_simulado
    ADD CONSTRAINT metrica_simulado_chave_natural
    UNIQUE NULLS NOT DISTINCT (simulado_id, recorte_tipo, recorte_id);
