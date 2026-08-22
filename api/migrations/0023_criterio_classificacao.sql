-- Critérios de classificação como dado (docs/18 §1.7).
--
-- A regra do corte existia em três lugares e já tinha divergido (5,0 no front,
-- 4,0 no backend, nenhum igual ao edital). A partir daqui a régua é uma LINHA
-- nesta tabela, avaliada por um único lugar — app/stats/criterios.py — e os
-- três critérios embutidos (colégio, ITA, IME) são a carga inicial.
--
-- Por que tabela filha e não jsonb: para a coordenação conseguir ler um
-- critério com SELECT e entender o que ele exige. Legibilidade do schema é
-- regra da casa (CLAUDE.md §Convenções).
--
-- Por que `versao`: critério é IMUTÁVEL. Editar cria uma versão nova; a antiga
-- continua respondendo por quem já a usou. Sem isso, editar um critério
-- mudaria retroativamente os números de ciclos já fechados, em silêncio.
--
-- Por que não se chama `metrica`: metrica_simulado já existe e é outra coisa
-- (média, mediana, desvio, quartis de um simulado).

BEGIN;

CREATE TABLE IF NOT EXISTS criterio_classificacao (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text NOT NULL,
    versao      int  NOT NULL DEFAULT 1,
    nome        text NOT NULL,
    descricao   text,
    -- 'todos' = corta só se TODOS os requisitos falharem (régua do colégio).
    -- 'algum' = basta UM falhar (é o que os dois editais mandam).
    combinador  text NOT NULL CHECK (combinador IN ('todos', 'algum')),
    -- 1 ou 2; NULL = vale para qualquer fase (a régua do colégio).
    fase        smallint CHECK (fase IN (1, 2)),
    -- Ordem de precedência do desempate, por código de matéria.
    -- 'media' é a média geral do próprio critério.
    desempate   text[] NOT NULL DEFAULT '{}',
    -- Os embutidos vêm de criterios.py e não podem ser apagados pela tela;
    -- os que a coordenação criar têm embutido = false.
    embutido    boolean NOT NULL DEFAULT false,
    ativo       boolean NOT NULL DEFAULT true,
    criado_em   timestamptz NOT NULL DEFAULT now(),
    criado_por  text,
    UNIQUE (slug, versao)
);

CREATE TABLE IF NOT EXISTS predicado_criterio (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    criterio_id     uuid NOT NULL REFERENCES criterio_classificacao(id) ON DELETE CASCADE,
    posicao         smallint NOT NULL,
    -- Código da matéria ('matematica', ...), '*' para "qualquer disciplina",
    -- 'fase_1' para a média da 1ª fase entrando como componente da 2ª,
    -- ou NULL para a média geral do critério.
    materia         text,
    operador        text NOT NULL DEFAULT '>=' CHECK (operador IN ('>=', '>', '<=', '<')),
    -- Ou um ou outro: nota em 0–10, OU "acertos de total" (como os editais
    -- escrevem os mínimos da 1ª fase — ITA §4.6.2.1, IME Art. 40).
    valor_nota      numeric(4, 2),
    valor_acertos   smallint,
    valor_de        smallint,
    -- Reprova sozinho, ignorando o combinador (inglês do ITA na F1, redação).
    eliminatorio    boolean NOT NULL DEFAULT false,
    -- Cobrado mas fora da média (ITA §4.6.5: inglês "não é classificatório").
    entra_na_media  boolean NOT NULL DEFAULT true,
    -- Média ponderada do IME (Art. 37, III): 3 / 2,5 / 2,5 / 1 / 1.
    peso            numeric(5, 2) NOT NULL DEFAULT 1,
    -- Artigo do edital ou origem da regra. Aparece no motivo do corte.
    fonte           text,
    CHECK (
        (valor_nota IS NOT NULL AND valor_acertos IS NULL AND valor_de IS NULL)
        OR (valor_nota IS NULL AND valor_acertos IS NOT NULL AND valor_de IS NOT NULL)
    ),
    UNIQUE (criterio_id, posicao)
);

CREATE INDEX IF NOT EXISTS idx_criterio_classificacao_slug_ativo
    ON criterio_classificacao (slug, ativo, versao DESC);

COMMENT ON TABLE  criterio_classificacao IS 'Réguas de corte/classificação. Imutáveis: editar cria versão nova. Avaliadas em app/stats/criterios.py.';
COMMENT ON COLUMN criterio_classificacao.combinador IS 'todos = corta só se todos os requisitos falharem; algum = basta um.';
COMMENT ON COLUMN criterio_classificacao.embutido   IS 'true = vem de criterios.py (colégio, ITA, IME); não pode ser apagado pela tela.';
COMMENT ON TABLE  predicado_criterio IS 'Um requisito de um critério. Ou valor_nota, ou valor_acertos/valor_de — nunca os dois.';
COMMENT ON COLUMN predicado_criterio.materia        IS 'código da matéria | ''*'' (qualquer) | ''fase_1'' (média da F1 como componente) | NULL (média geral).';
COMMENT ON COLUMN predicado_criterio.eliminatorio   IS 'Reprova sozinho, sem consultar o combinador.';
COMMENT ON COLUMN predicado_criterio.entra_na_media IS 'false = cobrado mas fora da média (inglês do ITA, redação).';

-- ─── Carga inicial: os três critérios embutidos ─────────────────────────
-- Espelho literal de app/stats/criterios.py. Se os dois divergirem, o
-- arquivo vence — e este bloco deve ser corrigido.

INSERT INTO criterio_classificacao (slug, nome, descricao, combinador, fase, desempate, embutido) VALUES
  ('tio-leo', 'Tio Leo',
   'A régua pedagógica do Ari, ditada pela coordenação em 21/08/2026. Diverge dos editais de propósito: corta com E, não com OU.',
   'todos', NULL, '{media,matematica,fisica,quimica,ingles}', true),
  ('ita-f1', 'ITA — Fase 1',
   '48 questões: 12 de Matemática, Física, Química e Inglês (§4.1.2).',
   'algum', 1, '{media,matematica,fisica,quimica}', true),
  ('ita-f2', 'ITA — Fase 2',
   'Média final: 20% da 1ª fase + 20% de cada uma das quatro provas da 2ª (§4.7). Habilitado exige média ≥ 5,0 E ≥ 4,0 em cada (§4.9.1.1).',
   'algum', 2, '{media,matematica,fisica,quimica,portugues}', true),
  ('ime-f1', 'IME — Fase 1',
   '40 questões: 15 de Matemática, 15 de Física, 10 de Química (Art. 38). Sem Português e sem Inglês.',
   'algum', 1, '{media,matematica,fisica,quimica}', true),
  ('ime-f2', 'IME — Fase 2',
   'Cinco provas com pesos 3 / 2,5 / 2,5 / 1 / 1 (Art. 37, III). Nota final é a média ponderada (Art. 63). Inglês ENTRA na média.',
   'algum', 2, '{media,matematica,fisica,quimica,portugues,ingles}', true)
ON CONFLICT (slug, versao) DO NOTHING;

-- Tio Leo
INSERT INTO predicado_criterio (criterio_id, posicao, materia, valor_nota, eliminatorio, entra_na_media, fonte)
SELECT c.id, p.posicao, p.materia, p.valor_nota, p.eliminatorio, p.entra_na_media, p.fonte
FROM criterio_classificacao c
CROSS JOIN (VALUES
  (1, '*',      4.0, false, true,  'régua do colégio: 40% da prova'),
  (2, NULL,     5.0, false, true,  'régua do colégio: 50% da média'),
  (3, 'ingles', 4.0, true,  false, 'eliminatório, fora da média')
) AS p(posicao, materia, valor_nota, eliminatorio, entra_na_media, fonte)
WHERE c.slug = 'tio-leo' AND c.versao = 1
ON CONFLICT (criterio_id, posicao) DO NOTHING;

-- ITA — Fase 1
INSERT INTO predicado_criterio (criterio_id, posicao, materia, valor_nota, valor_acertos, valor_de, entra_na_media, fonte)
SELECT c.id, p.posicao, p.materia, p.valor_nota, p.valor_acertos, p.valor_de, p.entra_na_media, p.fonte
FROM criterio_classificacao c
CROSS JOIN (VALUES
  (1, 'matematica', NULL::numeric, 5, 12, true,  'ITA §4.6.2.1'),
  (2, 'fisica',     NULL,          5, 12, true,  'ITA §4.6.2.1'),
  (3, 'quimica',    NULL,          5, 12, true,  'ITA §4.6.2.1'),
  (4, 'ingles',     NULL,          5, 12, false, 'ITA §4.6.2.1 e §4.6.5'),
  (5, NULL,         5.0,  NULL, NULL, true, 'ITA §4.6.2.2')
) AS p(posicao, materia, valor_nota, valor_acertos, valor_de, entra_na_media, fonte)
WHERE c.slug = 'ita-f1' AND c.versao = 1
ON CONFLICT (criterio_id, posicao) DO NOTHING;

-- ITA — Fase 2
INSERT INTO predicado_criterio (criterio_id, posicao, materia, valor_nota, eliminatorio, entra_na_media, fonte)
SELECT c.id, p.posicao, p.materia, p.valor_nota, p.eliminatorio, p.entra_na_media, p.fonte
FROM criterio_classificacao c
CROSS JOIN (VALUES
  (1, 'matematica', 4.0, false, true,  'ITA §4.6.6.5'),
  (2, 'fisica',     4.0, false, true,  'ITA §4.6.6.5'),
  (3, 'quimica',    4.0, false, true,  'ITA §4.6.6.5'),
  (4, 'portugues',  4.0, false, true,  'ITA §4.6.6.5'),
  (5, 'fase_1',     0.0, false, true,  'ITA §4.7'),
  (6, 'redacao',    4.0, true,  false, 'ITA §4.6.6.3.1'),
  (7, NULL,         5.0, false, true,  'ITA §4.9.1.1')
) AS p(posicao, materia, valor_nota, eliminatorio, entra_na_media, fonte)
WHERE c.slug = 'ita-f2' AND c.versao = 1
ON CONFLICT (criterio_id, posicao) DO NOTHING;

-- IME — Fase 1 (pesos = nº de questões, para a média ser "acertos ÷ 40 × 10")
INSERT INTO predicado_criterio (criterio_id, posicao, materia, valor_nota, valor_acertos, valor_de, peso, fonte)
SELECT c.id, p.posicao, p.materia, p.valor_nota, p.valor_acertos, p.valor_de, p.peso, p.fonte
FROM criterio_classificacao c
CROSS JOIN (VALUES
  (1, 'matematica', NULL::numeric, 6, 15, 15, 'IME Art. 40, II'),
  (2, 'fisica',     NULL,          6, 15, 15, 'IME Art. 40, III'),
  (3, 'quimica',    NULL,          4, 10, 10, 'IME Art. 40, IV'),
  (4, NULL,         5.0,  NULL, NULL, 1,  'IME Art. 40, I')
) AS p(posicao, materia, valor_nota, valor_acertos, valor_de, peso, fonte)
WHERE c.slug = 'ime-f1' AND c.versao = 1
ON CONFLICT (criterio_id, posicao) DO NOTHING;

-- IME — Fase 2
INSERT INTO predicado_criterio (criterio_id, posicao, materia, valor_nota, eliminatorio, entra_na_media, peso, fonte)
SELECT c.id, p.posicao, p.materia, p.valor_nota, p.eliminatorio, p.entra_na_media, p.peso, p.fonte
FROM criterio_classificacao c
CROSS JOIN (VALUES
  (1, 'matematica', 4.0, false, true,  3.0, 'IME Art. 37 III-a; Art. 52'),
  (2, 'fisica',     4.0, false, true,  2.5, 'IME Art. 37 III-b; Art. 52'),
  (3, 'quimica',    4.0, false, true,  2.5, 'IME Art. 37 III-c; Art. 52'),
  (4, 'portugues',  4.0, false, true,  1.0, 'IME Art. 37 III-d; Art. 52'),
  (5, 'ingles',     4.0, false, true,  1.0, 'IME Art. 37 III-e; Art. 52'),
  (6, 'redacao',    4.0, true,  false, 1.0, 'IME Art. 50 §2º; Art. 65')
) AS p(posicao, materia, valor_nota, eliminatorio, entra_na_media, peso, fonte)
WHERE c.slug = 'ime-f2' AND c.versao = 1
ON CONFLICT (criterio_id, posicao) DO NOTHING;

COMMIT;
