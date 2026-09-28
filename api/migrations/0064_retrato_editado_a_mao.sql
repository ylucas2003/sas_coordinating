-- Escola/cidade/UF de candidato_externo passam a ser editáveis à mão
-- (docs/41 §17, 28/09/2026) — pedido do coordenador testando em produção: o
-- perfil vazio criado por "Novo perfil" (pra separar homônimo) nascia com
-- escola/cidade/UF em branco e ficava mostrando "— sem escola —" até alguém
-- arrastar uma conquista pra dentro; não dava pra rotular o cartão antes
-- disso.
--
-- Mas escola/cidade/UF continuam sendo recalculados sozinhos sempre que uma
-- conquista entra ou sai de um perfil (mover_conquista, e agora também o
-- resolver, que pode anexar conquista nova a um perfil já existente — docs/41
-- §16). Sem uma trava, editar à mão e depois arrastar uma conquista pra
-- dentro apagaria a edição em silêncio — a mesma classe de bug (edição que
-- "some sozinha") que o projeto já evita em outros lugares.
--
-- retrato_editado_a_mao: true assim que um humano edita escola/cidade/UF via
-- PATCH /captacao/candidatos/{id}. A partir daí, mover_conquista e o
-- resolver PULAM o recálculo desses campos pra este candidato — a edição
-- vale até outro humano mudar de novo (ou arrastar pra um perfil diferente).

BEGIN;

ALTER TABLE candidato_externo
    ADD COLUMN retrato_editado_a_mao boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN candidato_externo.retrato_editado_a_mao IS
    'true depois que um humano edita escola/cidade/uf à mão (PATCH /captacao/candidatos/{id}). Trava o retrato: mover_conquista e resolver_candidatos_externos.py param de recalcular esses campos pra este perfil, mesmo ganhando ou perdendo conquista depois. docs/41 §17.';

-- v_candidato_externo (0058) precisa expor a coluna nova: é ela que o
-- resolver e mover_conquista consultam pra saber se um alvo está travado.
-- CREATE OR REPLACE só aceita ACRESCENTAR coluna no fim, nunca reordenar —
-- por isso entra depois de ano_mais_recente, não junto de escola/cidade/uf.
CREATE OR REPLACE VIEW v_candidato_externo AS
SELECT
    c.id, c.nome, c.nome_normalizado, c.escola, c.cidade, c.uf,
    c.serie_referencia_min, c.serie_referencia_max, c.ano_referencia_serie,
    c.status_captacao, c.observacoes, c.criado_em, c.atualizado_em,
    count(ce.id)::int             AS conquistas_total,
    count(DISTINCT ce.prova_id)::int AS provas_distintas,
    max(ce.ano)                   AS ano_mais_recente,
    c.retrato_editado_a_mao
FROM candidato_externo c
LEFT JOIN conquista_externa ce ON ce.candidato_id = c.id
GROUP BY c.id;

COMMIT;
