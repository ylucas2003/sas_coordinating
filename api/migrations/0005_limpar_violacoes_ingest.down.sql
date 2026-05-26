-- ─────────────────────────────────────────────────────────────────────────
-- 0005 · DOWNGRADE — no-op (irreversível por design)
--
-- A migration 0005 apaga simulados/notas/alunos que violam as regras novas
-- de ingestão. Não temos como restaurá-los a partir do banco — a fonte
-- canônica desses dados é a planilha original.
--
-- Estratégia de rollback: rodar `limpar_dados_importados.sql` e re-importar
-- a planilha. O migration runner ainda destaqueta esta migration da tabela
-- `_migracoes_aplicadas` pra permitir reaplicar caso necessário.
-- ─────────────────────────────────────────────────────────────────────────

SELECT 'noop — recupere via re-import da planilha original' AS aviso;
