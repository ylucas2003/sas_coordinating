-- O botão "quanto o passado ainda conta" vira dado (docs/34 §5 · D2).
--
-- `meia_vida_anos` é o H de `w(a) = 0,5^((ref−a)/H)`: com H = 5, a prova de
-- 2021 vale metade da de 2026 e a de 2016 vale um quarto. Mexer nele REORDENA
-- o ranking de assuntos — e portanto muda o que o sistema diz para o aluno
-- estudar primeiro.
--
-- ⚠️ É o PRIMEIRO parâmetro de calibração que a coordenação edita. Os treze de
-- `stats/thresholds.py` são código. Por isso o desenho daqui vira precedente, e
-- as três regras abaixo vêm de `criterios_repo.py`, que já resolveu o mesmo
-- problema na Sprint 2 (migration 0023):
--
--   1. VERSIONADO, NUNCA EDITADO NO LUGAR. É a regra do critério: "editar
--      insere versao + 1 e desativa a anterior; sem isso, mexer numa régua
--      mudaria retroativamente os números de quem já a usou — em silêncio, e
--      sem ninguém conseguir explicar a diferença depois". Aqui vale mais: um H
--      alterado muda TODO o ranking de uma vez, e sem versão o print que a
--      coordenação tirou mês passado deixa de ser reproduzível.
--
--   2. DEFAULT NO CÓDIGO, BANCO COMO OVERRIDE. Mesma razão de o arquivo vencer
--      para as réguas embutidas: banco fora do ar não impede o Painel de
--      classificar. Se esta tabela sumir ou não responder, o H de fábrica
--      assume e o índice continua saindo — um índice que some porque uma linha
--      de configuração falhou é pior que um índice com o valor de fábrica.
--
--   3. A MUDANÇA É AUDITADA (`criado_por`, e o registro em auditoria.py). Um
--      número que reordena o que ~900 alunos veem não muda anônimo.
--
-- ⚠️ Tabela TIPADA, e não `config(chave text, valor text)`. Chave/valor
-- genérico não valida nada e adia o problema: `meia_vida_anos = 'cinco'` entra
-- sem reclamar e explode na leitura. Nasce com duas colunas porque são as duas
-- que existem hoje — não se inventa mecanismo geral para uma linha.

BEGIN;

CREATE TABLE IF NOT EXISTS parametro_importancia (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    versao                integer NOT NULL,
    meia_vida_anos        numeric(4,2) NOT NULL CHECK (meia_vida_anos > 0),
    janela_tendencia_anos integer NOT NULL CHECK (janela_tendencia_anos > 0),
    ativo                 boolean NOT NULL DEFAULT true,
    criado_em             timestamptz NOT NULL DEFAULT now(),
    criado_por            text,
    CONSTRAINT parametro_importancia_versao_unica UNIQUE (versao)
);

COMMENT ON TABLE parametro_importancia IS
    'Calibração do índice de importância do assunto (docs/34 §3). Uma linha ativa por vez; editar cria versão nova. O código tem os mesmos valores de fábrica e assume se esta tabela não responder.';
COMMENT ON COLUMN parametro_importancia.meia_vida_anos IS
    'O H de w(a) = 0,5^((ref−a)/H). Quantos anos até uma prova valer metade. Padrão 5, decidido em 29/08/2026 (docs/24 §4.2).';
COMMENT ON COLUMN parametro_importancia.janela_tendencia_anos IS
    'A janela de T(t) = média dos últimos N anos − média dos N anteriores. Vive AQUI, e não solta no front, porque era um segundo "5" independente do H — dois números iguais por coincidência divergem no primeiro que alguém mexer (docs/34 §0.3).';

-- ⚠️ Índice PARCIAL: garante no máximo uma linha ativa, sem impedir o
-- histórico de versões desativadas. Um UNIQUE(ativo) comum permitiria uma
-- ativa e uma inativa só.
CREATE UNIQUE INDEX IF NOT EXISTS parametro_importancia_uma_ativa
    ON parametro_importancia (ativo) WHERE ativo;

-- A semente é a decisão de 29/08. Ela existe para a tela de edição ter o que
-- mostrar desde o primeiro dia — a LEITURA não depende dela (regra 2 acima).
INSERT INTO parametro_importancia (versao, meia_vida_anos, janela_tendencia_anos, criado_por)
SELECT 1, 5, 5, 'migration 0044'
WHERE NOT EXISTS (SELECT 1 FROM parametro_importancia);

COMMIT;
