-- Listas de questões e estado de estudo do aluno (docs/22 §P5 e §P6).
--
-- O site de origem guardava tudo em localStorage, o que funciona num site sem
-- login. Aqui não: o aluno entra no celular e no computador, e uma lista que
-- existe só num aparelho é uma lista que ele perde sem saber por quê. O SAS tem
-- conta desde a Sprint 2 — usar é o mínimo (docs/22 §5.1).

BEGIN;

CREATE TABLE IF NOT EXISTS lista_questoes (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo        text NOT NULL,
    -- Um par (tipo, id) em vez de duas tabelas ou de duas FKs anuláveis: a
    -- lista é a mesma coisa dos dois lados, e separar duplicaria as rotas de
    -- reordenar e exportar. `dono_id` é o uuid de `aluno` ou de
    -- `usuario_coordenacao`, conforme o tipo — sem FK, porque não há FK
    -- polimórfica em Postgres sem gatilho.
    dono_tipo     text NOT NULL CHECK (dono_tipo IN ('aluno', 'coordenacao')),
    dono_id       uuid NOT NULL,
    criada_em     timestamptz NOT NULL DEFAULT now(),
    atualizada_em timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  lista_questoes IS
  'Lista de questões montada por um aluno ou pela coordenação. Toda rota filtra pelo dono da sessão.';
COMMENT ON COLUMN lista_questoes.dono_id IS
  'uuid de aluno ou de usuario_coordenacao, conforme dono_tipo. Sem FK: seria polimórfica.';

CREATE TABLE IF NOT EXISTS lista_questoes_item (
    lista_id   uuid NOT NULL REFERENCES lista_questoes(id) ON DELETE CASCADE,
    questao_id text NOT NULL REFERENCES questao_vestibular(id) ON DELETE CASCADE,
    posicao    int  NOT NULL,
    PRIMARY KEY (lista_id, questao_id)
);

COMMENT ON TABLE lista_questoes_item IS
  'Questão dentro de uma lista. `posicao` é a ordem escolhida por quem montou, não a ordem natural da prova.';

CREATE INDEX IF NOT EXISTS idx_lista_questoes_dono
    ON lista_questoes (dono_tipo, dono_id, atualizada_em DESC);
CREATE INDEX IF NOT EXISTS idx_lista_questoes_item_ordem
    ON lista_questoes_item (lista_id, posicao);

-- ─── Estado de estudo, por aluno e por questão ──────────────────────────

CREATE TABLE IF NOT EXISTS questao_estudo_aluno (
    aluno_id      uuid NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
    questao_id    text NOT NULL REFERENCES questao_vestibular(id) ON DELETE CASCADE,
    resolvida     boolean NOT NULL DEFAULT false,
    anotacao      text,
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (aluno_id, questao_id)
);

-- É o que faz o banco virar ferramenta de estudo em vez de catálogo: o aluno
-- marca no celular e encontra marcado no computador.
COMMENT ON TABLE questao_estudo_aluno IS
  'O que o aluno já resolveu e o que anotou. Uma linha só existe depois de ele mexer — ausência = não tocado.';

COMMIT;
