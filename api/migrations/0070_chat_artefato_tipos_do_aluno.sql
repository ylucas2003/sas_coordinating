-- 0070 · Os cartões do Tio Léo passam a ser gravados (docs/43 §4.1, defeito 6).
--
-- O catálogo fechado de artefatos do aluno (`ferramentas.TIPOS_DE_ARTEFATO`,
-- espelhado no front em `chatStream.ts::CATALOGO_DE_ARTEFATOS`) tem quatro
-- tipos que o CHECK da 0038 não conhece: barras_corte, questao,
-- lista_questoes e prova. Sem esta migration o INSERT do primeiro cartão do
-- aluno é recusado DEPOIS de ele já ter visto o cartão ao vivo, e o cartão
-- some ao reabrir a conversa. Até 24/10 a recusa ia além: levantava dentro do
-- gerador SSE e levava junto a resposta final e o resto do turno — desde então
-- `rotas._talvez_salvar_artefato` isola cada INSERT, mas o cartão continuaria
-- se perdendo.
--
-- A lista vigente fica sendo a união dos dois escopos do catálogo, mais
-- `tabela`, que o CHECK aceita desde a 0008 sem que tool nenhuma a produza:
-- tirá-la faria esta migration falhar em banco que tenha linha antiga dela.
-- `tests/test_chat_persistencia_de_artefatos.py` lê as migrations e confere
-- que o ÚLTIMO CHECK aceita todo tipo do catálogo — tipo novo no catálogo sem
-- migration nova quebra o teste, e não o chat.
--
-- Só troca uma CHECK constraint: nenhuma tabela ou coluna nasce ou muda, e o
-- schema cache do PostgREST não guarda constraint. (O `migrate up` manda o
-- NOTIFY de recarga mesmo assim.)

BEGIN;

ALTER TABLE chat_artefato
    DROP CONSTRAINT IF EXISTS chat_artefato_tipo_check;

ALTER TABLE chat_artefato
    ADD CONSTRAINT chat_artefato_tipo_check
    CHECK (tipo IN (
        'histograma', 'linha_temporal', 'tabela', 'csv', 'navegacao',
        'barras_corte', 'questao', 'lista_questoes', 'prova'
    ));

COMMENT ON TABLE chat_artefato IS 'Artefatos produzidos pelo agente: gráficos inline, CSVs, links de navegação e os cartões do aluno (matérias contra o corte, questão, lista de questões, prova).';

COMMIT;
