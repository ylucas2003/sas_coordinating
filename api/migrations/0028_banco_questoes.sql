-- Banco de questões ITA · IME por assunto (docs/22 §P1).
--
-- 934 questões de prova de 2018 a 2025, de Física, Química e Matemática,
-- classificadas por tópico do edital. Vinham de um site estático próprio
-- (projeto `ita-por-assunto`) que embutia tudo num HTML de 2,2 MB.
--
-- ⚠️ Estas tabelas são a FONTE DA VERDADE, não uma projeção. Os JSONs que
-- geraram a carga inicial não são versionados (docs/22 §13): quem quiser o
-- arquivo de volta roda `scripts/exportar_banco_questoes.py`. Por isso o schema
-- guarda TUDO que o JSON guardava — proveniência e flags de extração inclusive.
--
-- ⚠️ `questao` JÁ EXISTE e é OUTRA COISA: questão de um simulado-Quiz do Canvas,
-- com simulado_id NOT NULL (0010). A daqui é questão de prova pública, sem
-- simulado nenhum. Os dois nomes convivem de propósito; confundi-los é o risco
-- nº 1 do sprint (docs/22 §8).
--
-- Nada de jsonb: alternativa e assunto do edital são listas com ordem e
-- significado próprios, e viram tabela. Um blob de JSON dentro de uma coluna
-- não se consulta, não se restringe e não se lê — e o schema aqui é para ser
-- lido por quem entende do domínio, não só por quem programa (CLAUDE.md).
--
-- Por que `id` é texto e não uuid: 'ita_2019_fase1_q01' já é único, já é o nome
-- do PNG no S3, e é o que se digita ao investigar. Trocar por uuid exigiria uma
-- tabela de-para para nada.

BEGIN;

CREATE TABLE IF NOT EXISTS questao_vestibular (
    id            text PRIMARY KEY,
    vestibular    text NOT NULL CHECK (vestibular IN ('ITA', 'IME')),
    ano           int  NOT NULL,
    fase          smallint NOT NULL CHECK (fase IN (1, 2)),
    materia       text NOT NULL,
    numero        int  NOT NULL,
    -- 2ª fase é discursiva: sem alternativa e sem letra de gabarito. 420 das
    -- 934 são assim, e é o esperado — não defeito (docs/22 §8, risco 4).
    dissertativa  boolean NOT NULL DEFAULT false,
    enunciado_md  text NOT NULL,
    gabarito      text,
    -- O enunciado é RENDERIZADO como imagem, não como texto: preserva fórmula e
    -- figura da prova original. O texto existe para busca e classificação.
    imagem_url    text,
    usa_imagem_no_render boolean NOT NULL DEFAULT false,
    resolucao_url text,

    -- ── Proveniência: de onde a questão saiu ────────────────────────────
    -- Com o JSON fora do git, é isto que responde "de onde veio este enunciado
    -- errado" e permite conferir o recorte contra a prova original.
    fonte_pdf     text,
    fonte_pagina  int,
    arquivo_origem text,

    -- ── Classificação ───────────────────────────────────────────────────
    classificado_por text,
    revisado      boolean NOT NULL DEFAULT false,

    -- ── Bastidor da extração ────────────────────────────────────────────
    -- Colunas de verdade, não um blob: `alternativas_extraidas` é false em 26
    -- questões e `figuras_recortadas` em 41 — são as que podem estar
    -- incompletas, e é o que se consulta antes de culpar o classificador.
    texto_extraido           boolean NOT NULL DEFAULT false,
    alternativas_extraidas   boolean NOT NULL DEFAULT false,
    figuras_recortadas       boolean NOT NULL DEFAULT false,
    possivelmente_tem_figura boolean NOT NULL DEFAULT false,

    importado_em  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (vestibular, ano, fase, materia, numero)
);

COMMENT ON TABLE  questao_vestibular IS
  'Questão de prova passada de ITA/IME. Fonte da verdade — os JSONs de origem não são versionados. NÃO confundir com `questao`, que é questão de simulado-Quiz do Canvas (0010).';
COMMENT ON COLUMN questao_vestibular.id IS
  'Legível e estável: {vestibular}_{ano}_fase{n}_q{NN}. Mesma chave do PNG no S3.';
COMMENT ON COLUMN questao_vestibular.dissertativa IS
  'true = 2ª fase, discursiva: sem alternativa e sem gabarito por natureza, não por falta de dado.';
COMMENT ON COLUMN questao_vestibular.imagem_url IS
  'PNG do recorte da questão, no bucket S3 próprio. Sem cópia local — dívida consciente (docs/22 §0.2).';
COMMENT ON COLUMN questao_vestibular.fonte_pdf IS
  'PDF da prova de onde a questão foi extraída (55 distintos).';
COMMENT ON COLUMN questao_vestibular.fonte_pagina IS
  'Página do PDF. É como se confere um recorte suspeito contra a prova original.';
COMMENT ON COLUMN questao_vestibular.arquivo_origem IS
  'Onde o pipeline escreveu o JSON localmente. Diretório NÃO versionado — é pista de reprocessamento, não endereço garantido. A proveniência que vale é fonte_pdf + fonte_pagina.';
COMMENT ON COLUMN questao_vestibular.classificado_por IS
  'Quem atribuiu os tópicos: ''claude'' em 894, NULL nas 40 sem classificação. Junto com `revisado`, separa palpite de máquina de conferência humana.';

-- ─── Alternativas ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS questao_vestibular_alternativa (
    questao_id text NOT NULL REFERENCES questao_vestibular(id) ON DELETE CASCADE,
    letra      text NOT NULL CHECK (letra ~ '^[A-E]$'),
    texto      text NOT NULL,
    PRIMARY KEY (questao_id, letra)
);

-- Tabela e não jsonb, espelhando `questao_alternativa` (0010), que faz o mesmo
-- para as questões do Canvas. Duas estruturas diferentes para a mesma ideia
-- seriam duas formas de errar.
COMMENT ON TABLE questao_vestibular_alternativa IS
  'Alternativa A–E de uma questão objetiva. Ausente nas dissertativas — a ordem de exibição é a da letra.';

-- ─── Taxonomia dos editais ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS topico_taxonomia (
    materia      text NOT NULL,
    codigo       text NOT NULL,
    nome         text NOT NULL,
    bloco_codigo text NOT NULL,
    bloco_nome   text NOT NULL,
    ordem        int  NOT NULL,
    PRIMARY KEY (materia, codigo)
);

-- ⚠️ A chave é COMPOSTA, e tem que ser: '1.1' existe nas três matérias e
-- significa coisa diferente — "Fundamentos" em Física, "Conjuntos e Lógica" em
-- Matemática, "Estrutura Atômica" em Química. Chave só por `codigo` misturaria
-- as três em silêncio, e o sintoma apareceria como estatística errada, não
-- como erro.
COMMENT ON TABLE topico_taxonomia IS
  'Tópico do edital, por matéria. Chave composta de propósito: o código se repete entre matérias.';

CREATE TABLE IF NOT EXISTS topico_taxonomia_assunto (
    materia       text NOT NULL,
    topico_codigo text NOT NULL,
    ordem         int  NOT NULL,
    texto         text NOT NULL,
    PRIMARY KEY (materia, topico_codigo, ordem),
    FOREIGN KEY (materia, topico_codigo) REFERENCES topico_taxonomia(materia, codigo) ON DELETE CASCADE
);

-- `ordem` na chave e não o texto: o edital enumera os assuntos numa sequência
-- que é dele, e é essa que o professor reconhece. Ordenar por texto trocaria a
-- ordem do edital pela do dicionário.
COMMENT ON TABLE topico_taxonomia_assunto IS
  'Os assuntos que o edital enumera dentro de um tópico, na ordem do edital. Descritivo: a classificação aponta para o tópico, não para um assunto.';

CREATE TABLE IF NOT EXISTS questao_vestibular_topico (
    questao_id    text NOT NULL REFERENCES questao_vestibular(id) ON DELETE CASCADE,
    materia       text NOT NULL,
    topico_codigo text NOT NULL,
    confianca     text CHECK (confianca IN ('alta', 'media', 'baixa')),
    observacao    text,
    PRIMARY KEY (questao_id, materia, topico_codigo),
    FOREIGN KEY (materia, topico_codigo) REFERENCES topico_taxonomia(materia, codigo)
);

-- Tabela de ligação porque questão mista é a REGRA, não a exceção, e porque a
-- recorrência da P4 é um GROUP BY aqui.
COMMENT ON TABLE  questao_vestibular_topico IS
  'Classificação da questão por tópico. N:N — questão mista tem mais de uma linha.';
COMMENT ON COLUMN questao_vestibular_topico.confianca IS
  'Confiança do classificador. Junto com `observacao`, é o que torna uma classificação errada diagnosticável.';

CREATE INDEX IF NOT EXISTS idx_questao_vestibular_filtros
    ON questao_vestibular (materia, vestibular, ano, fase);
CREATE INDEX IF NOT EXISTS idx_questao_vestibular_fonte
    ON questao_vestibular (fonte_pdf, fonte_pagina);
CREATE INDEX IF NOT EXISTS idx_questao_vestibular_topico_topico
    ON questao_vestibular_topico (materia, topico_codigo);

COMMIT;
