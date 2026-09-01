-- Par obrigatório da 0039 (CLAUDE.md, convenções). É deliberadamente inerte, e
-- a razão vale ser lida antes de alguém "consertar" este arquivo.
--
-- A 0039 troca caractere de controle por barra: TAB vira `\t`, FF vira `\f`. O
-- caminho de volta seria trocar `\t` por TAB — e aí está o problema: `\t` é o
-- começo de `\text`, `\theta`, `\times`, `\tfrac`, que aparecem em MILHARES de
-- fórmulas corretas do acervo. Um down mecânico corromperia as 1.480 resoluções
-- sadias para desfazer o conserto de 20. O prejuízo do inverso é maior, em duas
-- ordens de grandeza, do que qualquer coisa que ele pudesse reparar.
--
-- Se for mesmo preciso voltar, o caminho é restaurar as 20 linhas do backup do
-- banco por id — não uma regra sobre texto. Os ids estão nomeados na 0039.

BEGIN;

COMMIT;
