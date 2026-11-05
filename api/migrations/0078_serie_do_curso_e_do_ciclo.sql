-- 0078 · Curso, ciclo e turma passam a dizer de que série são (docs/44 §3)
--
-- A coordenação separa a plataforma em três blocos: "3º e cursinho", "1º ano" e
-- "2º ano" (docs/44 §1). Um bloco é uma série, e o banco não sabia dizer isso:
--
--   * `ano_letivo.canvas_course_id` guarda UM curso por ano, e cada série tem o
--     seu: 577, 578 e 579 em 2026.
--   * `ciclo` era único por (ano, ordem): a 1ª AP do 1º ano, a do 2º e o Ciclo 1
--     do 3º seriam a mesma linha, e o upsert de uma sobrescreveria a outra.
--   * `turma.serie` não resolve. Ela é o que o NOME da section declara e vale 0
--     em "AD Online", "PB", "Escolas Parceiras SAS"... Filtrar por ela esconderia
--     centenas de alunos do 3º. Por isso a turma ganha outra coluna, em vez de
--     reinterpretar esta.
--
-- Nada muda para o que já existe: tudo nasce 3, porque tudo o que está na
-- plataforma veio do curso de simulados do 3º, cursinho incluído. Esta migration
-- não traz aluno nem prova nova. Quem usa as colunas são as etapas seguintes.
--
-- `ano_letivo.canvas_course_id` FICA: agendamento, escrita no Canvas e notas ainda
-- o leem. A troca é da etapa 3, junto com a importação (docs/44 §4).
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`. Sem o
-- PostgREST reler o schema, o sync falha ao gravar `curso_canvas` (404) e o
-- `upsert_ciclo` recusa o novo `on_conflict`.

BEGIN;

CREATE TABLE curso_canvas (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ano_letivo_id     uuid NOT NULL REFERENCES ano_letivo(id),
    serie             int  NOT NULL CHECK (serie IN (1, 2, 3)),
    canvas_course_id  text NOT NULL UNIQUE,
    criado_em         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (ano_letivo_id, serie)
);

COMMENT ON TABLE  curso_canvas                  IS 'O curso de provas do Canvas de cada série em cada ano: "{ano} 3o ITA/IME Simulados" no 3º e "{ano} {1|2}o ITA/IME Avaliações" no 1º e no 2º (docs/44 §2).';
COMMENT ON COLUMN curso_canvas.serie            IS 'O bloco da coordenação: 3 = "3º e cursinho", 1 = "1º ano", 2 = "2º ano".';
COMMENT ON COLUMN curso_canvas.canvas_course_id IS 'Id do curso no Canvas. Sucede ano_letivo.canvas_course_id, que só comporta um curso por ano.';

INSERT INTO curso_canvas (ano_letivo_id, serie, canvas_course_id)
SELECT id, 3, canvas_course_id
  FROM ano_letivo
 WHERE canvas_course_id IS NOT NULL;

ALTER TABLE ciclo
    ADD COLUMN serie int NOT NULL DEFAULT 3 CHECK (serie IN (1, 2, 3));

COMMENT ON COLUMN ciclo.serie IS 'De que série é o ciclo. 1º e 2º ano fazem provas diferentes e nunca dividem ciclo (docs/44 §1).';

ALTER TABLE ciclo DROP CONSTRAINT ciclo_ano_letivo_id_ordem_key;
ALTER TABLE ciclo ADD CONSTRAINT ciclo_ano_letivo_serie_ordem_key UNIQUE (ano_letivo_id, serie, ordem);

ALTER TABLE turma
    ADD COLUMN serie_do_curso int NOT NULL DEFAULT 3 CHECK (serie_do_curso IN (1, 2, 3));

COMMENT ON COLUMN turma.serie_do_curso IS 'A série do curso de onde a turma veio, e é ela que diz o bloco. Diferente de turma.serie, que vale 0 quando o nome da section não declara a série.';

-- `stats/ciclo_estatisticas.py` roda também sob o papel do MCP (0071) e passa a
-- ler `serie` para achar o ciclo anterior. A lista desse papel é coluna a coluna.
GRANT SELECT (serie) ON ciclo TO sas_leitura;

COMMIT;
