-- Captação: potenciais alunos identificados fora do colégio, a partir de
-- resultados públicos de olimpíadas/vestibulares/concursos (a pasta "Dossiê de
-- Provas" na raiz do repo é o levantamento que originou este catálogo).
--
-- ⚠️ Isto NÃO tem nada a ver com `aluno`. `candidato_externo` é gente que
-- nunca colocou os pés no colégio — o objetivo é achar quem, e cruzar as
-- conquistas da MESMA pessoa em provas/anos diferentes, pra virar lead.
--
-- O fluxo é em 3 tabelas porque a resolução de identidade (decidir que duas
-- linhas raspadas são a mesma pessoa) é um passo à parte, revisável por
-- gente — não um efeito colateral do INSERT:
--
--   prova_externa       catálogo (OBMEP, OBM, ITA...), alimentado aos poucos
--   conquista_externa   1 linha por registro raspado, CRU — nome/escola/
--                       cidade/UF exatamente como a fonte informou
--   candidato_externo   identidade resolvida; agrupa N conquista_externa
--
-- `conquista_externa.candidato_id` nasce NULL e só é preenchido pelo script
-- de resolução — nunca no INSERT do scraper.

BEGIN;

CREATE TABLE IF NOT EXISTS prova_externa (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome            text NOT NULL UNIQUE,
    categoria       text NOT NULL
        CONSTRAINT prova_externa_categoria_valida
        CHECK (categoria IN ('olimpiada', 'vestibular', 'colegio_militar', 'concurso_nivel_medio')),
    abrangencia     text,
    fonte_resultado text,
    criado_em       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  prova_externa IS
    'Catálogo de provas externas usadas na captação. Uma linha aqui não implica que já exista scraper ou dado — ela pode existir só pra registrar que a prova foi pesquisada (ver pasta "Dossiê de Provas").';
COMMENT ON COLUMN prova_externa.categoria IS
    'Mesmo agrupamento do Dossiê de Provas: olimpiada, vestibular, colégio militar (admissão de adolescente) ou concurso de nível médio.';
COMMENT ON COLUMN prova_externa.abrangencia IS
    'Texto livre e descritivo (ex. "nacional", "estadual — CE", "ibero-americana") — não é enum porque o Dossiê já mostrou que a abrangência real varia demais pra caber em 3 valores fixos.';
COMMENT ON COLUMN prova_externa.fonte_resultado IS
    'URL de referência de onde os resultados são (ou seriam) raspados. Fica NULL quando o Dossiê de Provas não achou fonte confiável — a linha existe mesmo assim, documentando que já foi pesquisada.';


CREATE TABLE IF NOT EXISTS candidato_externo (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome                 text NOT NULL,
    nome_normalizado     text NOT NULL,
    escola               text,
    cidade               text,
    uf                   text,
    serie_referencia_min smallint,
    serie_referencia_max smallint,
    ano_referencia_serie smallint,
    status_captacao      text NOT NULL DEFAULT 'novo'
        CONSTRAINT candidato_externo_status_valido
        CHECK (status_captacao IN ('novo', 'contatado', 'interessado', 'matriculado', 'descartado')),
    observacoes          text,
    criado_em            timestamptz NOT NULL DEFAULT now(),
    atualizado_em        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_candidato_externo_nome_normalizado
    ON candidato_externo (nome_normalizado);

COMMENT ON TABLE  candidato_externo IS
    'Uma PESSOA de fora, resolvida a partir de uma ou mais conquista_externa — não é aluno.aluno. Existe pra agrupar as conquistas da mesma pessoa e sustentar o funil de captação (status_captacao).';
COMMENT ON COLUMN candidato_externo.nome_normalizado IS
    'Maiúsculas, sem acento, espaços colapsados — chave que o script de resolução usa pra comparar/agrupar conquista_externa. Derivado, nunca editado à mão.';
COMMENT ON COLUMN candidato_externo.escola IS
    'Escola da conquista mais recente já resolvida pra este candidato. Pode estar desatualizada se a pessoa trocou de escola depois da última conquista raspada — é retrato, não fato corrente.';
COMMENT ON COLUMN candidato_externo.serie_referencia_min IS
    'Estimativa de série (6 = 6º EF ... 12 = 3º médio) na conquista mais recente. min/max porque prova costuma anunciar por NÍVEL — uma faixa de séries, não uma série só (ex. Nível 2 da OBMEP = 8º-9º).';
COMMENT ON COLUMN candidato_externo.serie_referencia_max IS
    'Ver serie_referencia_min.';
COMMENT ON COLUMN candidato_externo.ano_referencia_serie IS
    'Ano em que serie_referencia_min/max valiam (o ano da conquista de referência). serie_estimada_hoje = serie_referencia + (ano_corrente - ano_referencia_serie) é calculado na leitura, não guardado — pra nunca ficar desatualizado sozinho.';
COMMENT ON COLUMN candidato_externo.status_captacao IS
    'Funil manual da coordenação: novo (ainda não olhado) → contatado → interessado → matriculado; ou descartado a qualquer momento. Nunca movido por código, só por quem está olhando a ficha.';


CREATE TABLE IF NOT EXISTS conquista_externa (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    prova_id              uuid NOT NULL REFERENCES prova_externa(id),
    candidato_id          uuid REFERENCES candidato_externo(id),
    ano                   smallint NOT NULL,
    nivel_texto           text,
    serie_referencia_min  smallint,
    serie_referencia_max  smallint,
    resultado             text NOT NULL,
    nome_informado        text NOT NULL,
    escola_informada      text,
    cidade_informada      text,
    uf_informada          text,
    fonte_url             text NOT NULL,
    raspado_em            timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conquista_externa_candidato   ON conquista_externa (candidato_id);
CREATE INDEX IF NOT EXISTS idx_conquista_externa_prova_ano   ON conquista_externa (prova_id, ano);

COMMENT ON TABLE  conquista_externa IS
    'Uma linha por registro raspado de uma lista de resultado externa — CRU, antes de qualquer resolução de identidade. As colunas "_informado(a)" são cópia exata do que a fonte disse; não normalizamos, não corrigimos.';
COMMENT ON COLUMN conquista_externa.nivel_texto IS
    'Rótulo de nível exatamente como a fonte publicou (ex. "Nível 2"). serie_referencia_min/max é a nossa tradução desse rótulo pra série (6-12); nivel_texto fica guardado pra auditar essa tradução depois.';
COMMENT ON COLUMN conquista_externa.resultado IS
    'Texto livre do que a fonte informou: "Ouro", "Prata", "Menção Honrosa", "Aprovado — 12º lugar"... Cada prova tem seu próprio vocabulário — não normalizamos aqui, cada consumidor interpreta.';
COMMENT ON COLUMN conquista_externa.candidato_id IS
    'NULL até o script de resolução de identidade rodar. Uma vez preenchido, não é sobrescrito automaticamente por um novo run — reatribuir pra outro candidato é decisão de gente, não da rotina de resolução.';
COMMENT ON COLUMN conquista_externa.fonte_url IS
    'URL exata de onde esta linha foi lida — não a URL genérica da prova (essa é prova_externa.fonte_resultado). Permite reabrir e conferir uma linha específica.';

COMMIT;
