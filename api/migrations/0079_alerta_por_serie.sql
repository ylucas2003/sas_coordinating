-- 0079 · O alerta passa a dizer de que série é (docs/44 §4, etapa 2)
--
-- Cada bloco do rail tem o próprio Painel, e o Painel mostra os alertas do bloco.
-- O filtro precisa ficar no servidor: `GET /alertas` devolve os 100 mais recentes,
-- e filtrar depois disso na tela sumiria com alertas de um bloco sem aviso nenhum.
--
-- Coluna, e não um join na leitura: descobrir a série a partir da entidade exigiria
-- ler todas as matrículas a cada abertura do Painel, a tela que deixou de baixar os
-- 900 alunos na fase 2 do docs/39.
--
-- Tudo o que existe é do 3º, então o DEFAULT já acerta as linhas atuais. Quem
-- preenche as novas é `stats/alertas.py::_marcar_serie`.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`.

BEGIN;

ALTER TABLE alerta
    ADD COLUMN serie int NOT NULL DEFAULT 3 CHECK (serie IN (1, 2, 3));

COMMENT ON COLUMN alerta.serie IS 'De que bloco da coordenação é o alerta: 3 = "3º e cursinho", 1 = "1º ano", 2 = "2º ano".';

COMMIT;
