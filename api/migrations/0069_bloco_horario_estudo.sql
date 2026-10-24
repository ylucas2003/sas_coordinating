-- Horário de estudos (docs/42): a semana de estudo que o aluno monta sozinho.
--
-- Uma linha é um BLOCO: "toda terça, às 19:00, por 1h30, Estequiometria". A
-- semana inteira é o conjunto de linhas do aluno — não existe tabela de
-- "horário", porque não há nada para guardar no horário que não esteja nos
-- blocos.
--
-- ⚠️ É AUTODECLARADO e PRIVADO. Tempo de estudo não é verificável (docs/26 §1),
-- então nada aqui alimenta XP, sequência ou liga; e nenhuma rota da coordenação
-- lê esta tabela, por decisão de produto (docs/42 §0): é dado de menor, e usá-lo
-- como sinal de alerta seria vigilância. Quem for ligar isto a outra coisa deve
-- reabrir a decisão, não só escrever a consulta.

BEGIN;

CREATE TABLE bloco_horario_estudo (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    aluno_id         uuid NOT NULL REFERENCES aluno(id) ON DELETE CASCADE,
    -- ISO: 1 = segunda … 7 = domingo. O `getDay()` do JavaScript é 0 = domingo,
    -- e a conversão mora num lugar só no front (`dominio/horarioEstudos.ts`).
    dia_semana       smallint NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),
    -- `time` e não `timestamptz`: uma rotina semanal não tem instante absoluto.
    -- "Toda terça às 19h" é hora de parede, e guardar fuso inventaria um
    -- problema de horário de verão que o dado não tem.
    hora_inicio      time NOT NULL,
    duracao_minutos  integer NOT NULL CHECK (duracao_minutos BETWEEN 15 AND 480),
    -- Texto livre: o aluno põe "Termodinâmica", "Revisão" ou "Aula de Física".
    -- O SAS não tem a grade de aulas, então o bloco não aponta para a taxonomia
    -- (docs/42 §0, decisão 3).
    rotulo           text NOT NULL CHECK (char_length(btrim(rotulo)) BETWEEN 1 AND 80),
    criado_em        timestamptz NOT NULL DEFAULT now(),
    atualizado_em    timestamptz NOT NULL DEFAULT now(),

    -- Resolução de minuto. A API só aceita "HH:MM"; o CHECK é o cinto de quem
    -- escrever direto no banco.
    CONSTRAINT bloco_horario_estudo_minuto_cheio
        CHECK (date_part('second', hora_inicio) = 0),
    -- O bloco não atravessa a meia-noite: quem estuda das 23h à 1h faz dois
    -- blocos. Um bloco que pertencesse a dois dias não caberia na seção de nenhum.
    CONSTRAINT bloco_horario_estudo_dentro_do_dia
        CHECK (
            date_part('hour', hora_inicio) * 60
            + date_part('minute', hora_inicio)
            + duracao_minutos <= 1440
        )
);

COMMENT ON TABLE  bloco_horario_estudo IS
  'Bloco de estudo que o aluno marcou na própria semana. Autodeclarado e privado: nenhuma rota da coordenação lê isto (docs/42 §0).';
COMMENT ON COLUMN bloco_horario_estudo.dia_semana IS
  'ISO: 1 = segunda … 7 = domingo.';
COMMENT ON COLUMN bloco_horario_estudo.hora_inicio IS
  'Hora de parede, sem fuso: a rotina é semanal e não tem instante absoluto.';
COMMENT ON COLUMN bloco_horario_estudo.rotulo IS
  'Texto livre do aluno, até 80 caracteres.';

-- A leitura é sempre "a semana inteira deste aluno, por dia e hora".
--
-- ⚠️ SEM trava de sobreposição no banco: um EXCLUDE por intervalo pediria a
-- extensão btree_gist, que o runner de migrations não instala. Quem recusa o
-- cruzamento é a API (`app/horario_estudos.py`), e o pior caso de uma corrida
-- entre duas abas do MESMO aluno é ele ver dois blocos no mesmo horário — dado
-- dele, sem efeito sobre mais ninguém.
CREATE INDEX idx_bloco_horario_estudo_aluno
    ON bloco_horario_estudo (aluno_id, dia_semana, hora_inicio);

COMMIT;
