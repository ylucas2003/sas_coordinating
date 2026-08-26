-- Acervo histórico do banco de questões: ITA e IME anteriores a 2018/2019.
--
-- Numerada 0031 e não 0030 de propósito: o banco de desenvolvimento tem o slot
-- 0030 registrado em `_migracoes_aplicadas` (slug `banco_questoes_proveniencia`,
-- cujas colunas acabaram consolidadas dentro da 0028 e o arquivo, removido). O
-- runner decide o que aplicar comparando só a VERSÃO, então uma 0030 nova seria
-- silenciosamente pulada em dev — e o teste local passaria sem ter aplicado nada.
--
-- O banco de hoje começa em ITA 2019 e IME 2018 porque era até onde o projeto de
-- origem tinha processado. O acervo que entra agora vem de duas fontes: o site
-- oficial do ITA (1ª fase 2008–2018) e o arquivo oficial do IME (1996–2019).
--
-- Três coisas mudam com essas provas, e as três precisam de coluna:
--
-- 1. NEM TODA PROVA TEM GABARITO PUBLICADO. As objetivas do ITA 2008–2018 têm; as
--    do IME de vários ciclos, não. Onde falta, a resposta é DEDUZIDA resolvendo a
--    questão — e uma letra deduzida não pode ser servida como se a banca a tivesse
--    publicado. `gabarito_origem` é o que separa as duas, e é obrigatório sempre
--    que houver letra: sem isso, a distinção depende de alguém lembrar de qual ano
--    tinha gabarito, que é exatamente o tipo de saber que se perde.
--
-- 2. NENHUMA DELAS TEM RESOLUÇÃO DO ARI. `resolucao_url` (0028) aponta para os
--    sites do colégio, que só comentam de 2019 em diante — todo o acervo histórico
--    cairia com o cartão vazio, que foi o defeito consertado em 23/08 (resolucao.py).
--    `resolucao_md` guarda o texto da resolução para ser exibido no próprio cartão.
--    As duas colunas convivem e são exclusivas na prática: onde há link do Ari não
--    há texto, e vice-versa.
--
-- 3. PARTE DELAS FOI EXTRAÍDA DE SCAN, NÃO DE PDF NATIVO. As provas datilografadas
--    (ITA pré-2008, IME pré-1996) derrotam o OCR: o texto sai ilegível, e a extração
--    é feita lendo a página como imagem. `extraido_por` registra isso, porque é o
--    que explica um enunciado com erro de transcrição — e é por onde se acha o lote
--    inteiro que precisa de reconferência se o método se mostrar ruim.
--
-- ⚠️ `fase` continua 1 ou 2, e as provas antigas do ITA cabem nisso sem forçar: o
-- PDF de cada matéria em 2008–2018 traz 30 questões, sendo Q1-20 objetivas (a 1ª
-- fase, que é o que o gabarito oficial cobre) e Q21-30 dissertativas (a 2ª). São
-- gravadas como fase 1 e fase 2, mantendo o NÚMERO IMPRESSO na prova — a questão
-- 21 continua sendo a 21, e não vira "fase 2 nº 1". O número é o que o aluno lê no
-- recorte; renumerar faria a imagem contradizer o rótulo.

BEGIN;

ALTER TABLE questao_vestibular
    ADD COLUMN IF NOT EXISTS gabarito_origem    text,
    ADD COLUMN IF NOT EXISTS gabarito_confianca text,
    ADD COLUMN IF NOT EXISTS resolucao_md       text,
    ADD COLUMN IF NOT EXISTS resolucao_origem   text,
    ADD COLUMN IF NOT EXISTS extraido_por       text;

-- As 934 que já estão no banco vieram todas de gabarito oficial e de PDF nativo.
-- Preenchido antes do CHECK entrar, senão a restrição recusa as linhas existentes.
UPDATE questao_vestibular
   SET gabarito_origem = 'banca'
 WHERE gabarito IS NOT NULL AND gabarito_origem IS NULL;

UPDATE questao_vestibular
   SET extraido_por = 'pipeline'
 WHERE extraido_por IS NULL;

UPDATE questao_vestibular
   SET resolucao_origem = 'ari'
 WHERE resolucao_url IS NOT NULL AND resolucao_origem IS NULL;

-- Letra sem origem declarada é o estado que não pode existir: é dela que sai a
-- decisão de mostrar "gabarito" ou "sugestão de gabarito" na tela.
ALTER TABLE questao_vestibular
    ADD CONSTRAINT questao_vestibular_gabarito_origem_check
        CHECK (gabarito_origem IN ('banca', 'sugerido')),
    ADD CONSTRAINT questao_vestibular_gabarito_origem_presente
        CHECK (gabarito IS NULL OR gabarito_origem IS NOT NULL),
    ADD CONSTRAINT questao_vestibular_gabarito_confianca_check
        CHECK (gabarito_confianca IN ('alta', 'media', 'baixa')),
    -- Confiança é propriedade de quem deduziu. Numa letra da banca ela não
    -- significa nada, e permitir preenchê-la ali abriria espaço para "gabarito
    -- oficial de confiança média", que é contradição.
    ADD CONSTRAINT questao_vestibular_confianca_so_em_sugerido
        CHECK (gabarito_confianca IS NULL OR gabarito_origem = 'sugerido'),
    ADD CONSTRAINT questao_vestibular_resolucao_origem_check
        CHECK (resolucao_origem IN ('ari', 'sugerida')),
    ADD CONSTRAINT questao_vestibular_resolucao_coerente
        CHECK (
            (resolucao_origem = 'ari'     AND resolucao_url IS NOT NULL) OR
            (resolucao_origem = 'sugerida' AND resolucao_md IS NOT NULL) OR
            resolucao_origem IS NULL
        ),
    ADD CONSTRAINT questao_vestibular_extraido_por_check
        CHECK (extraido_por IN ('pipeline', 'visao'));

COMMENT ON COLUMN questao_vestibular.gabarito_origem IS
  '''banca'' = letra publicada pela banca; ''sugerido'' = deduzida resolvendo a questão. Obrigatória sempre que houver gabarito — é o que decide se a tela diz "gabarito" ou "sugestão de gabarito".';
COMMENT ON COLUMN questao_vestibular.gabarito_confianca IS
  'Só para gabarito sugerido. Medido contra provas de gabarito conhecido: o acerto nas de confiança alta foi muito superior ao das demais, e é por isso que existe corte por esta coluna em vez de publicar tudo.';
COMMENT ON COLUMN questao_vestibular.resolucao_md IS
  'Resolução exibida dentro do cartão, em Markdown. Existe porque o Ari só comenta provas de 2019 em diante e o acervo histórico ficaria sem nada. Convive com resolucao_url, que é o link para o site do colégio.';
COMMENT ON COLUMN questao_vestibular.resolucao_origem IS
  '''ari'' = link para a resolução publicada pelo colégio; ''sugerida'' = texto próprio em resolucao_md.';
COMMENT ON COLUMN questao_vestibular.extraido_por IS
  '''pipeline'' = PDF nativo, texto extraído direto; ''visao'' = página escaneada lida como imagem, porque o OCR não dá conta de prova datilografada. É por onde se acha o lote a reconferir.';

-- Índice parcial: a revisão humana busca justamente o que foi deduzido, que é a
-- minoria das linhas. Índice cheio pagaria pelas 934 que não interessam à consulta.
CREATE INDEX IF NOT EXISTS idx_questao_vestibular_sugerido
    ON questao_vestibular (materia, gabarito_confianca)
 WHERE gabarito_origem = 'sugerido';

COMMIT;
