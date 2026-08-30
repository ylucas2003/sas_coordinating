BEGIN;

-- Linhas do tipo novo têm de sair antes, senão o CHECK antigo não aplica.
DELETE FROM chat_artefato WHERE tipo = 'navegacao';

ALTER TABLE chat_artefato
    DROP CONSTRAINT IF EXISTS chat_artefato_tipo_check;

ALTER TABLE chat_artefato
    ADD CONSTRAINT chat_artefato_tipo_check
    CHECK (tipo IN ('histograma', 'linha_temporal', 'tabela', 'csv'));

COMMENT ON TABLE chat_artefato IS 'Artefatos visuais ou exportáveis produzidos pelo agente (gráficos inline, CSVs).';

COMMIT;
