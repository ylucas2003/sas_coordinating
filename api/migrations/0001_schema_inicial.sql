-- ─────────────────────────────────────────────────────────────────────────
-- SAS · schema inicial
--
-- Convenções:
--   - tudo em português, snake_case, tabelas no singular
--   - FK explícitas (aluno_id, simulado_id) sem abreviações
--   - booleans em forma positiva (ativo, presente, anulado, resolvido)
--   - timestamps padrão: criado_em, atualizado_em
--   - COMMENT ON COLUMN quando o nome sozinho não basta
-- ─────────────────────────────────────────────────────────────────────────

-- ─── Dimensões físicas ────────────────────────────────────────────────────

CREATE TABLE sede (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo       text NOT NULL UNIQUE,
    nome         text NOT NULL,
    modalidade   text NOT NULL CHECK (modalidade IN ('presencial', 'online')),
    criado_em    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  sede           IS 'Sedes físicas e online do colégio.';
COMMENT ON COLUMN sede.codigo    IS 'Sigla extraída do campo Section da planilha (ex.: "AD" de "3o ITA AD"). "ONLINE" para a sede virtual.';
COMMENT ON COLUMN sede.nome      IS 'Nome legível para a UI (ex.: "Aldeota").';


CREATE TABLE ano_letivo (
    id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ano   int  NOT NULL UNIQUE
);

COMMENT ON TABLE ano_letivo IS 'Anos letivos cadastrados (2025, 2026, ...).';


CREATE TABLE turma (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sede_id           uuid NOT NULL REFERENCES sede(id),
    ano_letivo_id     uuid NOT NULL REFERENCES ano_letivo(id),
    serie             int  NOT NULL,
    trilha            text NOT NULL,
    section_original  text NOT NULL,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (sede_id, ano_letivo_id, serie, trilha)
);

COMMENT ON TABLE  turma                   IS 'Turmas — uma turma por (sede, ano letivo, série, trilha).';
COMMENT ON COLUMN turma.serie             IS 'Ano escolar (1, 2 ou 3) extraído do prefixo numérico do Section.';
COMMENT ON COLUMN turma.trilha            IS 'Trilha de preparação (ITA, IME, AFA, EsPCEx, EFOMM, ...).';
COMMENT ON COLUMN turma.section_original  IS 'Valor original do Section da planilha (ex.: "3o ITA AD"). Preservado para reconciliação.';


CREATE TABLE materia (
    id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    codigo  text NOT NULL UNIQUE,
    nome    text NOT NULL
);

COMMENT ON COLUMN materia.codigo  IS 'Slug ASCII (matematica, fisica, quimica, portugues, ingles, redacao).';
COMMENT ON COLUMN materia.nome    IS 'Nome canônico exibido (Matemática, Física, ...).';


-- ─── Aluno e matrículas ───────────────────────────────────────────────────

CREATE TABLE aluno (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    matricula      text NOT NULL UNIQUE,
    nome           text NOT NULL,
    ativo          boolean NOT NULL DEFAULT true,
    criado_em      timestamptz NOT NULL DEFAULT now(),
    atualizado_em  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN aluno.matricula  IS 'SIS User ID do Canvas. Confirmado estável entre uploads — chave natural para o upsert.';
COMMENT ON COLUMN aluno.ativo      IS 'Aluno saiu = false. Mantemos a linha para preservar histórico de notas.';


CREATE TABLE matricula_turma (
    aluno_id     uuid NOT NULL REFERENCES aluno(id),
    turma_id     uuid NOT NULL REFERENCES turma(id),
    ativo_desde  date NOT NULL,
    ativo_ate    date,
    PRIMARY KEY (aluno_id, turma_id, ativo_desde)
);

COMMENT ON TABLE  matricula_turma           IS 'Histórico de matrículas. Um aluno pode ter sido de várias turmas ao longo do tempo.';
COMMENT ON COLUMN matricula_turma.ativo_ate IS 'NULL enquanto o aluno está ativo na turma. Preenchido quando ele sai.';


CREATE TABLE vestibular_alvo_aluno (
    aluno_id    uuid NOT NULL REFERENCES aluno(id),
    vestibular  text NOT NULL CHECK (vestibular IN ('ITA', 'IME', 'AFA', 'EsPCEx', 'EFOMM')),
    PRIMARY KEY (aluno_id, vestibular)
);

COMMENT ON TABLE vestibular_alvo_aluno IS 'Vestibulares-alvo de cada aluno. Configurado por fora do upload (UI separada ou aba do XLSX).';


-- ─── Ciclos e simulados ───────────────────────────────────────────────────

CREATE TABLE ciclo (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ano_letivo_id   uuid NOT NULL REFERENCES ano_letivo(id),
    ordem           int  NOT NULL,
    nome            text NOT NULL,
    periodo_inicio  date,
    periodo_fim     date,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ano_letivo_id, ordem)
);

COMMENT ON COLUMN ciclo.ordem          IS 'Ordem do ciclo dentro do ano letivo (1, 2, 3, ...). Extraída do prefixo "N_" do nome de coluna da planilha.';
COMMENT ON COLUMN ciclo.periodo_inicio IS 'Min(data_aplicacao) dos simulados do ciclo. Atualizado a cada upload.';
COMMENT ON COLUMN ciclo.periodo_fim    IS 'Max(data_aplicacao) dos simulados do ciclo. Atualizado a cada upload.';


CREATE TABLE simulado (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id     text NOT NULL UNIQUE,
    ciclo_id        uuid NOT NULL REFERENCES ciclo(id),
    materia_id      uuid REFERENCES materia(id),
    nome            text NOT NULL,
    rotulo_curto    text,
    fase            text CHECK (fase IN ('1a', '2a')),
    data_aplicacao  date NOT NULL,
    nota_maxima     numeric(6, 2) NOT NULL,
    e_agregado      boolean NOT NULL DEFAULT false,
    anulado         boolean NOT NULL DEFAULT false,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    atualizado_em   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN simulado.external_id    IS 'ID numérico do Canvas, capturado dos parênteses no header (ex.: "(4255)").';
COMMENT ON COLUMN simulado.materia_id     IS 'NULL para provas multi-matéria (tipo "1° CICLO - 1º DIA - Humanas"). Ver e_agregado.';
COMMENT ON COLUMN simulado.rotulo_curto   IS 'Rótulo curto pra eixo de gráfico (ex.: "P1", "P22").';
COMMENT ON COLUMN simulado.e_agregado     IS 'true para provas estilo ENEM/macro-ciclo que somam várias matérias. Ficam fora da média individual.';
COMMENT ON COLUMN simulado.anulado        IS 'Marcado pela coordenação após a aplicação. Fica oculto por default na UI.';


CREATE TABLE nota (
    aluno_id       uuid NOT NULL REFERENCES aluno(id),
    simulado_id    uuid NOT NULL REFERENCES simulado(id),
    pontuacao      numeric(6, 2),
    presente       boolean NOT NULL,
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aluno_id, simulado_id)
);

COMMENT ON COLUMN nota.pontuacao IS 'Nota bruta. NULL quando presente = false (aluno faltou).';
COMMENT ON COLUMN nota.presente  IS 'false quando a célula da planilha veio vazia. Falta ≠ zero.';


-- ─── Auditoria de uploads ─────────────────────────────────────────────────

CREATE TABLE upload (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    arquivo_origem     text NOT NULL,
    caminho_storage    text,
    autor              text,
    status             text NOT NULL CHECK (status IN ('processando', 'sucesso', 'erro')),
    linhas_total       int,
    linhas_aceitas     int,
    linhas_rejeitadas  int,
    resumo             jsonb,
    erro_mensagem      text,
    criado_em          timestamptz NOT NULL DEFAULT now(),
    finalizado_em      timestamptz
);

COMMENT ON TABLE  upload                IS 'Histórico de uploads de planilha. Uma linha por arquivo processado.';
COMMENT ON COLUMN upload.caminho_storage IS 'Path no Supabase Storage. NULL se o arquivo não foi salvo (modo dev local).';
COMMENT ON COLUMN upload.resumo         IS 'JSON com contagens por entidade afetada (alunos_novos, simulados_novos, ...).';


CREATE TABLE upload_evento (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    upload_id        uuid NOT NULL REFERENCES upload(id) ON DELETE CASCADE,
    nivel            text NOT NULL CHECK (nivel IN ('info', 'aviso', 'erro')),
    mensagem         text NOT NULL,
    linha_planilha   int,
    coluna_planilha  text,
    criado_em        timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE upload_evento IS 'Log granular do processamento de um upload — avisos, erros, info por linha/coluna.';


-- ─── Cache de cálculos derivados ──────────────────────────────────────────

CREATE TABLE classificacao_aluno (
    aluno_id           uuid PRIMARY KEY REFERENCES aluno(id),
    perfil             text NOT NULL CHECK (perfil IN ('ancora', 'misterio', 'regular')),
    tendencia          text NOT NULL CHECK (tendencia IN ('subindo', 'estavel', 'caindo')),
    zona               text NOT NULL CHECK (zona IN ('top', 'cinzenta', 'risco')),
    media_recente      numeric(6, 2),
    desvio_recente     numeric(6, 2),
    coef_tendencia     numeric(6, 3),
    p_valor_tendencia  numeric(5, 3),
    janela_simulados   int NOT NULL DEFAULT 5,
    calculado_em       timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN classificacao_aluno.coef_tendencia    IS 'Coeficiente angular da regressão linear das últimas N notas. Positivo = subindo.';
COMMENT ON COLUMN classificacao_aluno.p_valor_tendencia IS 'P-valor do coeficiente angular. Usado para distinguir tendência real de ruído.';


CREATE TABLE metrica_simulado (
    simulado_id    uuid NOT NULL REFERENCES simulado(id),
    recorte_tipo   text NOT NULL CHECK (recorte_tipo IN ('geral', 'turma', 'sede')),
    recorte_id     uuid,
    media          numeric(6, 2),
    mediana        numeric(6, 2),
    desvio_padrao  numeric(6, 2),
    variancia      numeric(7, 3),
    minimo         numeric(6, 2),
    maximo         numeric(6, 2),
    quartil_1      numeric(6, 2),
    quartil_3      numeric(6, 2),
    n_presentes    int NOT NULL,
    n_ausentes     int NOT NULL,
    histograma     jsonb,
    calculado_em   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (simulado_id, recorte_tipo, recorte_id)
);

COMMENT ON COLUMN metrica_simulado.recorte_tipo IS 'geral = simulado inteiro; turma = uma turma específica; sede = uma sede específica.';
COMMENT ON COLUMN metrica_simulado.recorte_id   IS 'NULL quando recorte_tipo = geral. ID da turma/sede caso contrário.';


-- ─── Alertas e config ─────────────────────────────────────────────────────

CREATE TABLE alerta (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    categoria      text NOT NULL CHECK (categoria IN (
                       'QUEDA_RENDIMENTO',
                       'SUBIDA_ATIPICA',
                       'PROVA_MAL_CALIBRADA',
                       'MATERIA_EM_RISCO',
                       'DIFERENCA_ENTRE_SEDES',
                       'PANORAMA_CICLO',
                       'ZONA_TRANSICAO'
                   )),
    severidade     text NOT NULL CHECK (severidade IN ('vermelho', 'ambar', 'verde', 'cinza')),
    entidade_tipo  text NOT NULL CHECK (entidade_tipo IN ('aluno', 'simulado', 'turma', 'sede')),
    entidade_id    uuid NOT NULL,
    titulo         text NOT NULL,
    subtitulo      text,
    dados_brutos   jsonb,
    disparado_em   timestamptz NOT NULL DEFAULT now(),
    resolvido      boolean NOT NULL DEFAULT false,
    resolvido_em   timestamptz,
    hash_dedup     text UNIQUE
);

COMMENT ON COLUMN alerta.dados_brutos IS 'Payload mínimo para renderizar sparkline/mini-histograma na UI sem refetch.';
COMMENT ON COLUMN alerta.hash_dedup   IS 'Hash de (categoria, entidade, janela). Previne alertas duplicados no mesmo recálculo.';


CREATE TABLE nota_corte_vestibular (
    vestibular     text NOT NULL CHECK (vestibular IN ('ITA', 'IME', 'AFA', 'EsPCEx', 'EFOMM')),
    ano_letivo_id  uuid NOT NULL REFERENCES ano_letivo(id),
    nota_corte     numeric(6, 2) NOT NULL,
    atualizado_em  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (vestibular, ano_letivo_id)
);


-- ─── Índices que importam para as queries das telas ───────────────────────

CREATE INDEX idx_nota_simulado_presente
    ON nota (simulado_id) WHERE presente = true;

CREATE INDEX idx_nota_aluno_atualizado
    ON nota (aluno_id, atualizado_em DESC);

CREATE INDEX idx_simulado_ciclo_data
    ON simulado (ciclo_id, data_aplicacao);

CREATE INDEX idx_simulado_externo
    ON simulado (external_id);

CREATE INDEX idx_alerta_pendente
    ON alerta (severidade, disparado_em DESC) WHERE resolvido = false;

CREATE INDEX idx_matricula_ativa
    ON matricula_turma (turma_id) WHERE ativo_ate IS NULL;


-- ─── Seed de matérias (conjunto fechado por enquanto) ─────────────────────

INSERT INTO materia (codigo, nome) VALUES
    ('matematica', 'Matemática'),
    ('fisica',     'Física'),
    ('quimica',    'Química'),
    ('portugues',  'Português'),
    ('ingles',     'Inglês'),
    ('redacao',    'Redação');
