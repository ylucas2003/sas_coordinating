-- ─────────────────────────────────────────────────────────────────────────
-- 0010 · Expansão para sincronização direta com o Canvas
--
-- Contexto completo em docs/08-integracao-canvas.md (§8). Três blocos:
--
--   1. Colunas novas em aluno / matricula_turma / nota / simulado — campos
--      que a API do Canvas expõe e a planilha nunca trouxe (contato, estado
--      bruto de matrícula, distinção fina de ausência, janela de prova).
--   2. Tabelas novas de questão/gabarito e módulo/progresso — criadas agora,
--      populadas na Fase 2 do sync (exigem fan-out N+1 na API do Canvas).
--   3. canvas_sync_execucao — auditoria de cada rodada do sync (análoga à
--      tabela upload do import de planilha, com nomes corretos pro domínio).
--
-- Reversível via 0010_*.down.sql.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

-- ── Aluno ───────────────────────────────────────────────────────────────

ALTER TABLE aluno ADD COLUMN email text;
ALTER TABLE aluno ADD COLUMN avatar_url text;
ALTER TABLE aluno ADD COLUMN canvas_user_id text;
ALTER TABLE aluno ADD COLUMN canvas_criado_em timestamptz;

COMMENT ON COLUMN aluno.email            IS 'E-mail do canal ativo no Canvas (Communication Channels). Populado só no backfill — muda raramente.';
COMMENT ON COLUMN aluno.canvas_user_id   IS 'ID numérico interno do Canvas. Distinto de matricula (= SIS User ID).';
COMMENT ON COLUMN aluno.canvas_criado_em IS 'created_at da conta no Canvas. Distinto de criado_em (entrada no SAS).';

CREATE UNIQUE INDEX idx_aluno_canvas_user_id ON aluno(canvas_user_id) WHERE canvas_user_id IS NOT NULL;


-- ── Matrícula em turma ──────────────────────────────────────────────────

ALTER TABLE matricula_turma ADD COLUMN canvas_enrollment_id text;
ALTER TABLE matricula_turma ADD COLUMN canvas_section_id text;
ALTER TABLE matricula_turma ADD COLUMN enrollment_state text;
ALTER TABLE matricula_turma ADD COLUMN last_activity_at timestamptz;
ALTER TABLE matricula_turma ADD COLUMN last_attended_at timestamptz;

COMMENT ON COLUMN matricula_turma.canvas_section_id IS 'ID bruto da Section no Canvas. Complementa turma.section_original (nome parseado).';
COMMENT ON COLUMN matricula_turma.enrollment_state  IS 'Estado bruto do Canvas (active/completed/inactive/...). ativo_desde/ativo_ate seguem sendo a leitura do SAS.';
COMMENT ON COLUMN matricula_turma.last_activity_at  IS 'Último acesso do aluno ao curso no Canvas — detecta aluno "sumido".';


-- ── Nota ────────────────────────────────────────────────────────────────

ALTER TABLE nota ADD COLUMN late boolean NOT NULL DEFAULT false;
ALTER TABLE nota ADD COLUMN graded_em timestamptz;
ALTER TABLE nota ADD COLUMN grader_canvas_user_id text;
ALTER TABLE nota ADD COLUMN canvas_missing boolean;
ALTER TABLE nota ADD COLUMN canvas_excused boolean;
ALTER TABLE nota ADD COLUMN canvas_workflow_state text;

COMMENT ON COLUMN nota.canvas_missing        IS 'Campo bruto do Submission. presente agora é DERIVADO de missing/excused/workflow_state no sync — não mais heurística.';
COMMENT ON COLUMN nota.canvas_workflow_state IS 'unsubmitted / submitted / graded / pending_review — direto do Canvas.';
COMMENT ON COLUMN nota.grader_canvas_user_id IS 'Quem lançou/corrigiu a nota (id de usuário do Canvas). Auditoria.';


-- ── Simulado ────────────────────────────────────────────────────────────

ALTER TABLE simulado ADD COLUMN quiz_id text;
ALTER TABLE simulado ADD COLUMN unlock_at timestamptz;
ALTER TABLE simulado ADD COLUMN lock_at timestamptz;
ALTER TABLE simulado ADD COLUMN duracao_media_segundos numeric(8, 2);

COMMENT ON COLUMN simulado.quiz_id                IS 'ID do Quiz no Canvas quando o simulado é online. NULL = nota lançada manualmente (sem detalhe por questão).';
COMMENT ON COLUMN simulado.duracao_media_segundos IS 'duration_average do Quiz Statistics — tempo médio de prova. O SAS não tem como calcular isso sozinho.';


-- ── Questão + gabarito + resposta (populadas na Fase 2 do sync) ─────────

CREATE TABLE questao (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    simulado_id         uuid NOT NULL REFERENCES simulado(id),
    canvas_question_id  text NOT NULL,
    posicao             int  NOT NULL,
    texto               text NOT NULL,
    pontos              numeric(5, 2),
    UNIQUE (simulado_id, canvas_question_id)
);

COMMENT ON TABLE  questao       IS 'Questão de um simulado-Quiz do Canvas. Só existe para simulados com quiz_id.';
COMMENT ON COLUMN questao.texto IS 'HTML completo da questão (com LaTeX/imagens embutidos), vindo do Quiz Statistics.';

CREATE TABLE questao_alternativa (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    questao_id        uuid NOT NULL REFERENCES questao(id),
    canvas_answer_id  text NOT NULL,
    texto             text NOT NULL,
    correta           boolean NOT NULL,
    UNIQUE (questao_id, canvas_answer_id)
);

CREATE TABLE questao_resposta_aluno (
    aluno_id        uuid NOT NULL REFERENCES aluno(id),
    questao_id      uuid NOT NULL REFERENCES questao(id),
    alternativa_id  uuid REFERENCES questao_alternativa(id),
    correta         boolean NOT NULL,
    PRIMARY KEY (aluno_id, questao_id)
);

COMMENT ON TABLE questao_resposta_aluno IS 'Qual alternativa cada aluno marcou. Substitui o dot-grid mocado do painel do aluno.';


-- ── Módulo de estudo + progresso por aluno (populadas na Fase 2) ────────

CREATE TABLE modulo (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    materia_id        uuid REFERENCES materia(id),
    canvas_module_id  text NOT NULL UNIQUE,
    nome              text NOT NULL,
    posicao           int  NOT NULL
);

COMMENT ON TABLE modulo IS 'Módulo de aulas por assunto nos cursos por matéria do Canvas (ex.: "Combinatória" em Matemática 1).';

CREATE TABLE aluno_modulo_progresso (
    aluno_id       uuid NOT NULL REFERENCES aluno(id),
    modulo_id      uuid NOT NULL REFERENCES modulo(id),
    estado         text NOT NULL CHECK (estado IN ('locked', 'unlocked', 'started', 'completed')),
    completado_em  timestamptz,
    PRIMARY KEY (aluno_id, modulo_id)
);

COMMENT ON TABLE aluno_modulo_progresso IS 'Engajamento do aluno com o conteúdo, por assunto — "estudou Combinatória antes da prova?".';


-- ── Auditoria das rodadas de sincronização ──────────────────────────────

CREATE TABLE canvas_sync_execucao (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo           text NOT NULL CHECK (tipo IN ('backfill', 'incremental')),
    status         text NOT NULL CHECK (status IN ('processando', 'sucesso', 'erro')),
    resumo         jsonb,
    erro_mensagem  text,
    iniciado_em    timestamptz NOT NULL DEFAULT now(),
    finalizado_em  timestamptz
);

COMMENT ON TABLE  canvas_sync_execucao        IS 'Uma linha por rodada do sync com o Canvas (incremental de 5 min ou backfill manual). Análoga à tabela upload do import de planilha.';
COMMENT ON COLUMN canvas_sync_execucao.resumo IS 'Contagens por entidade (alunos_processados, notas_gravadas, avisos, ...).';

CREATE INDEX idx_canvas_sync_execucao_recente ON canvas_sync_execucao (iniciado_em DESC);


COMMIT;
