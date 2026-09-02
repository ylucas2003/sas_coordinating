-- `extraido_por` deixa de aceitar NULL — o invariante que as coleções assumem.
--
-- A área do aluno passa a partir o acervo em duas COLEÇÕES de produto,
-- "Recentes" e "Arquivo", e quem as separa é esta coluna
-- (`app/banco/consultas.py::MODOS_DA_COLECAO`):
--
--     recentes → 'pipeline'            recorte fino da questão, PDF nativo
--     arquivo  → 'pagina', 'visao'     a página inteira do caderno
--
-- O CHECK da 0033 lista os três valores, mas **CHECK não recusa NULL**: em SQL
-- a expressão sobre NULL vale UNKNOWN, e UNKNOWN passa. Ou seja, hoje é
-- possível gravar uma questão sem método de extração — e essa questão não
-- apareceria em NENHUMA das duas coleções. Não daria erro, não apareceria em
-- log nenhum: ela simplesmente não estaria na tela, e ninguém descobre o que
-- não está na tela.
--
-- É o mesmo defeito que `TOPICO_SEM_CLASSIFICACAO` existe para evitar do outro
-- lado (docs/22 §8, risco 3): dar ao aluno um recorte incompleto sem avisar que
-- é incompleto.
--
-- Nenhuma linha é NULL hoje — a 0031 preencheu o acervo inteiro com 'pipeline'
-- e `importador.py` tem o mesmo default —, então o `SET NOT NULL` não move
-- dado. O UPDATE abaixo é cinto de segurança para banco que tenha divergido, e
-- é no-op no nosso.
--
-- O DEFAULT existe para o mesmo motivo pelo outro lado: importação que esqueça
-- a coluna cai no acervo recente em vez de ser recusada. 'pipeline' é o valor
-- certo para isso — é o modo do pipeline padrão, e o histórico sempre declara
-- o seu explicitamente.

BEGIN;

UPDATE questao_vestibular
   SET extraido_por = 'pipeline'
 WHERE extraido_por IS NULL;

ALTER TABLE questao_vestibular
    ALTER COLUMN extraido_por SET DEFAULT 'pipeline',
    ALTER COLUMN extraido_por SET NOT NULL;

COMMIT;
