BEGIN;

-- Restaura a view pro formato da 0058, antes de tirar a coluna que ela usa.
-- DROP + CREATE, não CREATE OR REPLACE: replace só aceita ACRESCENTAR coluna
-- no fim, nunca remover — e aqui a coluna nova está saindo.
DROP VIEW v_candidato_externo;

CREATE VIEW v_candidato_externo AS
SELECT
    c.id, c.nome, c.nome_normalizado, c.escola, c.cidade, c.uf,
    c.serie_referencia_min, c.serie_referencia_max, c.ano_referencia_serie,
    c.status_captacao, c.observacoes, c.criado_em, c.atualizado_em,
    count(ce.id)::int             AS conquistas_total,
    count(DISTINCT ce.prova_id)::int AS provas_distintas,
    max(ce.ano)                   AS ano_mais_recente
FROM candidato_externo c
LEFT JOIN conquista_externa ce ON ce.candidato_id = c.id
GROUP BY c.id;

COMMENT ON VIEW v_candidato_externo IS
    'Um candidato por linha, com o resumo que a lista de captação precisa pra filtrar e ordenar: conquistas_total (pra "nº mínimo de conquistas"), provas_distintas e ano_mais_recente. Só leitura — status_captacao e observacoes continuam escritos em candidato_externo direto (PATCH /captacao/candidatos/{id}), nunca por aqui.';

ALTER TABLE candidato_externo DROP COLUMN retrato_editado_a_mao;

COMMIT;
