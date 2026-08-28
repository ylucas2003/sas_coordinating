-- Rastreia o pipeline de publicação de aulas gravadas do Canvas/BigBlueButton
-- no YouTube: quais cursos monitorar, e o estado de cada aula detectada
-- (pendente → baixando → ... → publicado). Ver docs de decisão na conversa
-- que originou esta feature — resumo: não existe download nativo de arquivo
-- único no plano de hospedagem do BBB do colégio, então o SAS baixa os
-- componentes (webcam + tela compartilhada), compõe um vídeo com o template
-- da marca, sobe pro S3 e publica como "não listado" no YouTube.

BEGIN;

CREATE TABLE curso_monitorado_gravacao (
  curso_id text PRIMARY KEY,
  nome text NOT NULL,
  ativo boolean NOT NULL DEFAULT true,
  professor_padrao text,
  criado_em timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE curso_monitorado_gravacao IS
  'Cursos do Canvas que o poller de gravações (app/gravacoes_aula/) verifica. Editar aqui liga/desliga um curso sem redeploy.';
COMMENT ON COLUMN curso_monitorado_gravacao.curso_id IS
  'course_id do Canvas (texto, não uuid — é identificador externo, como em todo o resto do domínio Canvas neste projeto).';
COMMENT ON COLUMN curso_monitorado_gravacao.professor_padrao IS
  'Usado no título do vídeo SÓ quando a conferência do Canvas não traz o nome. Não é o dono do curso: Física já teve Renan e Ryan em semanas diferentes, e nesses casos quem vale é o nome escrito no título da conferência.';

CREATE TABLE aula_gravacao (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  curso_id text NOT NULL,
  conferencia_id text NOT NULL,
  titulo text NOT NULL,
  iniciada_em timestamptz NOT NULL,
  duracao_minutos integer,
  status text NOT NULL DEFAULT 'pendente'
    CHECK (status IN ('pendente', 'baixando', 'baixado', 'compondo', 'composto',
                       'publicando', 'publicado', 'publicado_sem_confirmacao',
                       'erro')),
  tentativas integer NOT NULL DEFAULT 0,
  s3_bucket text,
  s3_chave_composto text,
  youtube_video_id text,
  erro_detalhe text,
  criado_em timestamptz NOT NULL DEFAULT now(),
  atualizado_em timestamptz NOT NULL DEFAULT now(),
  UNIQUE (curso_id, conferencia_id)
);

CREATE INDEX idx_aula_gravacao_status ON aula_gravacao (status);

COMMENT ON TABLE aula_gravacao IS
  'Estado de cada aula gravada detectada pelo poller, do pendente até publicado no YouTube.';
COMMENT ON COLUMN aula_gravacao.conferencia_id IS
  'id da conferência (BigBlueButton) no Canvas. UNIQUE com curso_id é a idempotência: nunca processa a mesma aula duas vezes.';
COMMENT ON COLUMN aula_gravacao.tentativas IS
  'Incrementada a cada falha; o processador para de tentar depois de 3 (ver rotas.py) sem travar as demais linhas pendentes.';
COMMENT ON COLUMN aula_gravacao.status IS
  'publicado e publicado_sem_confirmacao são TERMINAIS: o vídeo já está no canal e reprocessar geraria uma segunda cópia de menores (LGPD). publicado_sem_confirmacao = subiu ao YouTube mas o id não persistiu na primeira escrita.';

-- Cursos monitorados. Sem estas linhas a rotina roda sem verificar nada —
-- a tabela é a ÚNICA fonte do que o poller olha (ele nunca varre a conta do
-- Canvas inteira). Para ligar/desligar um curso depois, basta UPDATE do
-- campo `ativo`, sem deploy.
--
-- Só Matemática tem professor_padrao: é o único cujas conferências não
-- trazem o nome no título.
INSERT INTO curso_monitorado_gravacao (curso_id, nome, professor_padrao) VALUES
  ('691', '2026 SAS ITA/IME Matemática (2º SEMESTRE)', 'Alexandre César'),
  ('692', '2026 SAS ITA/IME Física (2º SEMESTRE)', NULL),
  ('693', '2026 SAS ITA/IME Química (2º SEMESTRE)', NULL)
ON CONFLICT (curso_id) DO NOTHING;

COMMIT;
