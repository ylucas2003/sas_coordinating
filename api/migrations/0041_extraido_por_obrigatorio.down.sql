-- Volta `extraido_por` a aceitar NULL e sem default.
--
-- Não repõe NULL em linha nenhuma, e não teria como: a 0041 não guarda quais
-- linhas ela preencheu, porque no nosso banco não preencheu nenhuma. Desfazer
-- é remover a restrição, não inventar dado ausente.

BEGIN;

ALTER TABLE questao_vestibular
    ALTER COLUMN extraido_por DROP NOT NULL,
    ALTER COLUMN extraido_por DROP DEFAULT;

COMMIT;
