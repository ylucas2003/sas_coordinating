-- O chat passa a devolver links navegáveis (docs/31 §2.4).
--
-- Por que artefato e não link no texto: o `Markdown.tsx` do front recusa
-- `[texto](url)` de propósito — o texto vem do LLM, e ampliar a gramática
-- ampliaria a superfície de injeção sem ganho. Como artefato, a rota é montada
-- no servidor a partir de (tipo, id) e o rótulo vem do banco: o modelo escolhe
-- para onde ir, nunca o endereço nem o nome que aparece.
--
-- Por que migration: o CHECK da 0008 enumera os tipos, e um INSERT com
-- 'navegacao' falharia em produção depois de a tool já ter respondido — o
-- usuário veria o link na conversa e o perderia ao recarregar.

BEGIN;

ALTER TABLE chat_artefato
    DROP CONSTRAINT IF EXISTS chat_artefato_tipo_check;

ALTER TABLE chat_artefato
    ADD CONSTRAINT chat_artefato_tipo_check
    CHECK (tipo IN ('histograma', 'linha_temporal', 'tabela', 'csv', 'navegacao'));

COMMENT ON TABLE chat_artefato IS 'Artefatos produzidos pelo agente: gráficos inline, CSVs e links de navegação.';

-- O canal 'criterio' passa a existir (docs/31 §4.6). A coluna não tem CHECK
-- (0025), então o custo é só manter o comentário honesto — ele é o que alguém
-- lê no psql para saber que canais existem.
COMMENT ON COLUMN evento_auditoria.canal IS 'acesso | nota | simulado | ciclo | canvas | criterio. Filtro da linha do tempo; permite retenção por canal.';

COMMIT;
