-- Expõe o sinal de conflito de nível de ensino direto em v_fusao_candidata.
--
-- scripts/sinalizar_fusoes_conflito_de_nivel.py já grava "⚠️ Possível engano:
-- nível de ensino conflitante..." em candidato_externo.observacoes quando dois
-- candidatos do mesmo nome têm nível/série incompatível no mesmo ano —
-- fisicamente impossível pra uma pessoa só, sinal bem mais forte que
-- ufs_distintas (que é só "cuidado", não "provavelmente errado"). Até aqui
-- esse aviso só aparecia depois de abrir o grupo em
-- routes/captacao.py::obter_fusao (lendo `observacoes` linha a linha); a fila
-- (listar_fusoes) e a lista geral de candidatos não tinham como filtrar ou
-- destacar por ele sem reparsear texto. Esta migration só soma um bool_or à
-- view que já existe (0059) — mesma tabela, mesmo GROUP BY, sem join novo.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

CREATE OR REPLACE VIEW v_fusao_candidata AS
SELECT
    c.nome_normalizado,
    count(*)::int AS candidatos,
    count(DISTINCT NULLIF(c.uf, '')) FILTER (WHERE c.uf IS NOT NULL)::int AS ufs_distintas,
    COALESCE(bool_or(c.observacoes ILIKE '%Possível engano: nível de ensino conflitante%'), false) AS tem_conflito_nivel
FROM candidato_externo c
WHERE NOT EXISTS (
    SELECT 1 FROM candidato_externo_fusao_decisao d
    WHERE d.nome_normalizado = c.nome_normalizado
)
GROUP BY c.nome_normalizado
HAVING count(*) > 1;

COMMENT ON VIEW v_fusao_candidata IS
    'Grupos de candidato_externo que COMPARTILHAM nome_normalizado e ainda não foram decididos — a fila da fusão de baixa confiança (docs/41 §8 item 1). ufs_distintas é o sinal de confiança rápido: 1 = todo mundo do grupo bate geograficamente, mais que 1 = pode ser gente diferente. tem_conflito_nivel é o sinal FORTE (0061): nível de ensino incompatível no mesmo ano entre candidatos do grupo, escrito por scripts/sinalizar_fusoes_conflito_de_nivel.py — quase certeza de homônimo, não só "cuidado".';

COMMIT;
