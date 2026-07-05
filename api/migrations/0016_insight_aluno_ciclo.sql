-- Cache de insights individuais do aluno por ciclo (card "IA · Insight do
-- ciclo" do painel do aluno). Espelha o padrão de insight_ciclo (0006/0007):
-- hash do payload de estatísticas — números mudam → hash muda → regenera.
BEGIN;

CREATE TABLE insight_aluno_ciclo (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id     uuid NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
    ciclo_id     uuid NOT NULL REFERENCES ciclo(id) ON DELETE CASCADE,
    hash_payload text NOT NULL,
    bullets      jsonb NOT NULL,
    modelo       text,
    gerado_em    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (aluno_id, ciclo_id, hash_payload)
);

COMMENT ON TABLE insight_aluno_ciclo IS
  'Bullets de IA gerados para o aluno sobre o próprio ciclo. Cache por hash das estatísticas individuais.';
COMMENT ON COLUMN insight_aluno_ciclo.hash_payload IS
  'sha256 truncado do payload de stats do aluno — invalida o cache quando os números mudam.';

CREATE INDEX idx_insight_aluno_ciclo_busca ON insight_aluno_ciclo (aluno_id, ciclo_id);

COMMIT;
