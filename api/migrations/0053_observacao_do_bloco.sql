-- A regra do bloco que o número não expressa (docs/40 §12.5.4).
--
-- A cantina já diz "escolha no máximo 2" por `escolhas_maximas`, e isso cobre a
-- maior parte da coluna "Obs!" da planilha que ela usa hoje. O que não cabe em
-- número é a outra metade: "a escolha da opção 4 anula a opção 1 e a 2",
-- "opção 6 OU 7". São regras de combinação entre opções, e elas existem no
-- papel desde antes do SAS.
--
-- ⚠️ **É texto ESCRITO, não vigiado.** O servidor não recusa a combinação que
-- a observação proíbe, e o aluno pode marcá-la. Foi decisão de 09/09
-- (docs/40 §12.12.12): vigiar de verdade exige um par de opções incompatíveis
-- no schema e validação nos dois lados, o que é uma feature e não um ajuste.
-- Deixar a regra visível para quem escolhe já é melhor do que ela viver só na
-- cabeça de quem cozinha — e é reversível.
--
-- Por que no BLOCO e não no cardápio: a regra é do bloco. "Máximo 2 opções"
-- pertence à Guarnição, não ao almoço de terça — e uma observação no cardápio
-- inteiro obrigaria a repetir de qual bloco ela fala.

BEGIN;

ALTER TABLE cardapio_bloco ADD COLUMN IF NOT EXISTS observacao text;

COMMENT ON COLUMN cardapio_bloco.observacao IS
    'Texto livre da cantina sobre a regra do bloco ("a escolha da opção 4 anula a 1 e a 2"). O que é NÚMERO já mora em escolhas_minimas/escolhas_maximas; aqui fica o que o número não diz. ⚠️ É escrito, não vigiado: o servidor não recusa a combinação (docs/40 §12.5.4).';

COMMIT;
