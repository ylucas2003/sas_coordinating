-- Caminho inverso da captação (docs/41 §20, 07/10/2026): achar candidato A
-- PARTIR de conquista ("quem tirou ouro na OBF 2025 e está no 9º ano?"), e não
-- só o caminho que já existia (nome → conquistas).
--
-- Três peças:
--
-- 1. `conquista_externa.faixa` — o que a conquista VALE, comparável entre
--    provas. `resultado` continua cru (0056); a faixa é a tradução, derivada
--    em Python (`scripts/_captacao_comum.py::classificar_faixa`, a ÚNICA régua)
--    e gravada pelo importador. Nasce NULL aqui: quem preenche as linhas que
--    já existem é `scripts/classificar_conquistas_externas.py`, rodado logo
--    depois desta migration. Enquanto estiver NULL, a linha conta como
--    conquista (o comportamento de antes), nunca some.
--
-- 2. `ano_conclusao_min/max` — o ano em que a pessoa termina (ou terminou) o
--    3º médio, pela série da conquista. GERADA, e não "série estimada hoje":
--    a série envelhece a cada 1º de janeiro, o ano de conclusão não. É ele que
--    deixa filtrar o PÚBLICO (Fundamental 2, Médio, Pré-vestibular) no banco.
--    NULL quando a fonte não diz a série (todo vestibular).
--
-- 3. `buscar_candidatos_por_conquista()` — a busca, chamada por RPC. Todo
--    critério de conquista (prova, faixa, ano, público) vale para a MESMA
--    linha de `conquista_externa`: com 1 perfil por nome (docs/41 §16), juntar
--    "ouro" de uma linha com "OBMEP" de outra e "2024" de uma terceira casaria
--    três conquistas de homônimos diferentes. Função, e não o padrão
--    "pré-consulta + .in_()" de `banco/consultas.py`, porque a pré-consulta
--    aqui devolveria dezenas de milhares de ids (só bronze da OBMEP são 48 mil).
--
-- E a lista geral (`v_candidato_externo_por_nome`) passa a NÃO contar
-- participação (`participou`/`ausente` — ter feito ou faltado a 1ª fase do
-- ITA) como conquista: eram 31.908 linhas, e 3.367 nomes apareciam em
-- "2+ conquistas" só por isso. O número continua visível em `participacoes`.
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1)
-- e `./.venv/bin/python scripts/classificar_conquistas_externas.py` (ele já
-- atualiza a lista geral no fim).

BEGIN;

-- ── 1 e 2. Colunas novas em conquista_externa ─────────────────────────────
ALTER TABLE conquista_externa
    ADD COLUMN faixa text
        CONSTRAINT conquista_externa_faixa_valida
        CHECK (faixa IN (
            'ouro', 'prata', 'bronze', 'mencao', 'finalista',
            'aprovado', 'classificado_final', 'passou_de_fase', 'participou', 'ausente'
        )),
    -- 12 = 3º médio (mesma escala de serie_referencia_*, 0056). A série MAIOR
    -- da faixa termina primeiro — por isso o min usa o max e vice-versa.
    ADD COLUMN ano_conclusao_min smallint
        GENERATED ALWAYS AS ((ano + 12 - serie_referencia_max)::smallint) STORED,
    ADD COLUMN ano_conclusao_max smallint
        GENERATED ALWAYS AS ((ano + 12 - serie_referencia_min)::smallint) STORED;

COMMENT ON COLUMN conquista_externa.faixa IS
    'O que a conquista vale, comparável entre provas: ouro/prata/bronze/mencao/finalista (olimpíada) ou aprovado/classificado_final/passou_de_fase/participou/ausente (vestibular). Derivada de `resultado` por scripts/_captacao_comum.py::classificar_faixa — a única régua; nunca editar à mão. docs/41 §20.';
COMMENT ON COLUMN conquista_externa.ano_conclusao_min IS
    'Ano em que a pessoa termina o 3º médio, pela série da conquista (faixa: min/max, como serie_referencia_*). Gerada — não envelhece, ao contrário de "série hoje". NULL quando a fonte não publica série (vestibulares). docs/41 §20.';
COMMENT ON COLUMN conquista_externa.ano_conclusao_max IS
    'Ver ano_conclusao_min.';

CREATE INDEX idx_conquista_externa_faixa ON conquista_externa (faixa);


-- ── A lista geral deixa de contar participação como conquista ────────────
--
-- DROP + CREATE (e não ALTER): view materializada não aceita coluna nova.
-- Mesma forma da 0065, com conquistas_total/provas_distintas filtrados e
-- `participacoes` à parte.
DROP MATERIALIZED VIEW v_candidato_externo_por_nome;

CREATE MATERIALIZED VIEW v_candidato_externo_por_nome AS
SELECT
    c.nome_normalizado,
    (array_agg(c.nome ORDER BY c.atualizado_em DESC))[1]     AS nome,
    COALESCE(
        array_agg(DISTINCT NULLIF(ce.escola_informada, ''))
            FILTER (WHERE NULLIF(ce.escola_informada, '') IS NOT NULL),
        ARRAY[]::text[]
    )                                                         AS escolas,
    COALESCE(
        array_agg(DISTINCT NULLIF(ce.cidade_informada, ''))
            FILTER (WHERE NULLIF(ce.cidade_informada, '') IS NOT NULL),
        ARRAY[]::text[]
    )                                                         AS cidades,
    COALESCE(
        array_agg(DISTINCT NULLIF(ce.uf_informada, ''))
            FILTER (WHERE NULLIF(ce.uf_informada, '') IS NOT NULL),
        ARRAY[]::text[]
    )                                                         AS ufs,
    array_agg(DISTINCT c.status_captacao)                    AS status_captacao,
    -- `faixa IS NULL` conta: linha ainda não classificada é tratada como
    -- antes desta migration, nunca escondida.
    count(ce.id) FILTER (WHERE ce.faixa IS NULL OR ce.faixa NOT IN ('participou', 'ausente'))::int
                                                              AS conquistas_total,
    count(DISTINCT ce.prova_id)
        FILTER (WHERE ce.faixa IS NULL OR ce.faixa NOT IN ('participou', 'ausente'))::int
                                                              AS provas_distintas,
    count(ce.id) FILTER (WHERE ce.faixa IN ('participou', 'ausente'))::int
                                                              AS participacoes,
    count(DISTINCT c.id)::int                                AS perfis_no_grupo,
    max(ce.ano)                                              AS ano_mais_recente,
    min(c.criado_em)                                         AS criado_em,
    max(c.atualizado_em)                                     AS atualizado_em
FROM candidato_externo c
LEFT JOIN conquista_externa ce ON ce.candidato_id = c.id
GROUP BY c.nome_normalizado
WITH DATA;

CREATE UNIQUE INDEX v_candext_por_nome_nome_idx
    ON v_candidato_externo_por_nome (nome_normalizado);
CREATE INDEX v_candext_por_nome_ordem_idx
    ON v_candidato_externo_por_nome (conquistas_total DESC, nome_normalizado);
CREATE INDEX v_candext_por_nome_ufs_gin_idx
    ON v_candidato_externo_por_nome USING GIN (ufs);
CREATE INDEX v_candext_por_nome_status_gin_idx
    ON v_candidato_externo_por_nome USING GIN (status_captacao);

COMMENT ON MATERIALIZED VIEW v_candidato_externo_por_nome IS
    'Uma linha por nome_normalizado, SEMPRE (simplificação de 25/09/2026). escolas/cidades/ufs são o CONJUNTO de conquista_externa.*_informada do nome (arrays independentes, não pareados), nunca null (0065). conquistas_total/provas_distintas NÃO contam participação (faixa participou/ausente — 0068, docs/41 §20); essas ficam em participacoes. Fonte de GET /captacao/candidatos e da busca por conquista. MATERIALIZADA por custo — atualizar_v_candidato_externo_por_nome() roda a cada escrita das rotas e no fim dos scripts de import/resolução.';


-- ── 3. A busca por conquista ─────────────────────────────────────────────
--
-- Público é relativo ao ANO DE INGRESSO (p_ano_ingresso), não ao ano
-- corrente: captação em outubro é pra turma do ano que vem. Faixas de ano de
-- conclusão, sobrepostas à faixa [ano_conclusao_min, ano_conclusao_max] da
-- conquista (fonte que publica por nível dá uma faixa, e ela pode tocar dois
-- públicos — é o que a fonte permite afirmar, nada mais):
--   fundamental     série 6-9 no ingresso  → conclui entre I+3 e I+6
--   medio           série 10-12            → conclui entre I e I+2
--   pre_vestibular  concluiu há 1-2 anos   → conclui entre I-2 e I-1
-- Vestibular não publica série: a conquista de vestibular dos dois anos
-- anteriores ao ingresso entra em pre_vestibular (quem fez ITA/IME/EFOMM/EN
-- ontem é vestibulando hoje — treineiro ou formado, a fonte não diz).
--
-- Força da faixa, só pra ORDENAR (nunca filtra) — e é força de LEAD, não de
-- resultado: `aprovado` fica ABAIXO de `classificado_final`/`passou_de_fase`
-- porque quem foi aprovado no ITA/IME/EFOMM/EN provavelmente já entrou, e
-- quem chegou até o fim sem vaga é o candidato típico de pré-vestibular
-- (decisão de 07/10/2026, docs/41 §20). Lista explícita aqui, ao lado de
-- quem usa.
CREATE FUNCTION buscar_candidatos_por_conquista(
    p_provas          text[]  DEFAULT NULL,
    p_faixas          text[]  DEFAULT NULL,
    p_ano_min         int     DEFAULT NULL,
    p_ano_max         int     DEFAULT NULL,
    p_publicos        text[]  DEFAULT NULL,
    p_ano_ingresso    int     DEFAULT NULL,
    p_uf              text    DEFAULT NULL,
    p_status          text    DEFAULT NULL,
    p_conquistas_min  int     DEFAULT NULL,
    p_busca           text    DEFAULT NULL,
    p_limite          int     DEFAULT 20,
    p_deslocamento    int     DEFAULT 0
)
RETURNS TABLE (
    nome_normalizado    text,
    nome                text,
    escolas             text[],
    cidades             text[],
    ufs                 text[],
    status_captacao     text[],
    conquistas_total    int,
    provas_distintas    int,
    participacoes       int,
    perfis_no_grupo     int,
    ano_mais_recente    smallint,
    criado_em           timestamptz,
    atualizado_em       timestamptz,
    conquistas_casadas  int,
    evidencias          jsonb,
    total_filtrado      bigint
)
LANGUAGE sql
STABLE
AS $$
    WITH parametros AS (
        SELECT COALESCE(p_ano_ingresso, extract(year FROM now())::int + 1) AS ingresso
    ),
    casadas AS (
        SELECT
            c.nome_normalizado,
            ce.ano,
            ce.faixa,
            ce.resultado,
            ce.nivel_texto,
            p.nome AS prova_nome,
            CASE ce.faixa
                WHEN 'ouro'      THEN 5 WHEN 'classificado_final' THEN 5
                WHEN 'prata'     THEN 4 WHEN 'passou_de_fase'     THEN 4
                WHEN 'bronze'    THEN 3 WHEN 'aprovado'           THEN 3
                WHEN 'mencao'    THEN 2
                WHEN 'finalista' THEN 1 WHEN 'participou'         THEN 1
                ELSE 0
            END AS forca
        FROM conquista_externa ce
        JOIN candidato_externo c ON c.id = ce.candidato_id
        JOIN prova_externa p ON p.id = ce.prova_id
        CROSS JOIN parametros
        WHERE (p_provas IS NULL OR p.nome = ANY (p_provas))
          AND (p_faixas IS NULL OR ce.faixa = ANY (p_faixas))
          AND (p_ano_min IS NULL OR ce.ano >= p_ano_min)
          AND (p_ano_max IS NULL OR ce.ano <= p_ano_max)
          AND (
              p_publicos IS NULL
              OR ('fundamental' = ANY (p_publicos)
                  AND ce.ano_conclusao_min <= ingresso + 6 AND ce.ano_conclusao_max >= ingresso + 3)
              OR ('medio' = ANY (p_publicos)
                  AND ce.ano_conclusao_min <= ingresso + 2 AND ce.ano_conclusao_max >= ingresso)
              OR ('pre_vestibular' = ANY (p_publicos)
                  AND (
                      (ce.ano_conclusao_min <= ingresso - 1 AND ce.ano_conclusao_max >= ingresso - 2)
                      OR (ce.ano_conclusao_min IS NULL AND p.categoria = 'vestibular'
                          AND ce.ano BETWEEN ingresso - 2 AND ingresso - 1)
                  ))
          )
    ),
    por_nome AS (
        SELECT
            casadas.nome_normalizado,
            max(forca) AS melhor_forca,
            (array_agg(ano ORDER BY forca DESC, ano DESC))[1] AS ano_da_melhor,
            count(*)::int AS conquistas_casadas,
            -- As 3 melhores que casaram — o "por que está aqui" da linha.
            to_jsonb((array_agg(
                jsonb_build_object(
                    'prova', prova_nome, 'ano', ano, 'faixa', faixa,
                    'resultado', resultado, 'nivel', NULLIF(nivel_texto, '')
                )
                ORDER BY forca DESC, ano DESC
            ))[1:3]) AS evidencias
        FROM casadas
        GROUP BY casadas.nome_normalizado
    )
    SELECT
        v.nome_normalizado, v.nome, v.escolas, v.cidades, v.ufs, v.status_captacao,
        v.conquistas_total, v.provas_distintas, v.participacoes, v.perfis_no_grupo,
        v.ano_mais_recente, v.criado_em, v.atualizado_em,
        pn.conquistas_casadas, pn.evidencias,
        count(*) OVER () AS total_filtrado
    FROM por_nome pn
    JOIN v_candidato_externo_por_nome v ON v.nome_normalizado = pn.nome_normalizado
    WHERE (p_uf IS NULL OR v.ufs @> ARRAY[p_uf])
      AND (p_status IS NULL OR v.status_captacao @> ARRAY[p_status])
      AND (p_conquistas_min IS NULL OR v.conquistas_total >= p_conquistas_min)
      AND (p_busca IS NULL OR v.nome_normalizado LIKE '%' || p_busca || '%')
    ORDER BY pn.melhor_forca DESC, pn.ano_da_melhor DESC, pn.conquistas_casadas DESC,
             v.provas_distintas DESC, v.nome_normalizado
    LIMIT p_limite OFFSET p_deslocamento
$$;

COMMENT ON FUNCTION buscar_candidatos_por_conquista IS
    'Caminho inverso da captação (docs/41 §20): nomes que têm PELO MENOS UMA conquista casando TODOS os critérios de conquista (prova, faixa, ano, público — na mesma linha), filtrados depois pelos critérios do nome (UF, status, nº de conquistas, busca já normalizada). Devolve as 3 melhores conquistas que casaram em `evidencias` e o total em `total_filtrado` (window, antes do LIMIT). Chamada por GET /captacao/candidatos quando há critério de conquista.';

COMMIT;
