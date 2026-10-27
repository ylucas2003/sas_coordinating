-- Par da 0070: volta o CHECK de chat_artefato.tipo ao da 0038.
--
-- ⚠️ O ROLLBACK PERDE ARTEFATOS. As linhas dos quatro tipos do aluno têm de
-- sair antes, senão o CHECK antigo não se aplica: são os cartões do Tio Léo
-- gravados desde a 0070. As mensagens das conversas ficam; ao reabrir, só os
-- cartões não voltam. E, com o backend novo ainda no ar, cartão novo desses
-- tipos deixa de ser gravado (a conversa segue — `_talvez_salvar_artefato`
-- isola o INSERT recusado).

BEGIN;

DELETE FROM chat_artefato
WHERE tipo IN ('barras_corte', 'questao', 'lista_questoes', 'prova');

ALTER TABLE chat_artefato
    DROP CONSTRAINT IF EXISTS chat_artefato_tipo_check;

ALTER TABLE chat_artefato
    ADD CONSTRAINT chat_artefato_tipo_check
    CHECK (tipo IN ('histograma', 'linha_temporal', 'tabela', 'csv', 'navegacao'));

COMMENT ON TABLE chat_artefato IS 'Artefatos produzidos pelo agente: gráficos inline, CSVs e links de navegação.';

COMMIT;
