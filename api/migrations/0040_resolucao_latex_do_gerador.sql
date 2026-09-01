-- Conserta as 11 resoluções com erro de LaTeX escrito pelo próprio gerador.
--
-- Causa diferente da 0039, e por isso migration separada: aqui nada corrompeu o
-- dado no caminho. O LLM escreveu LaTeX inválido e ninguém viu, porque até
-- 01/09/2026 a resolução ia CRUA para a tela — `$\log_\sqrt3x$` e
-- `$\log_{\sqrt3}x$` são igualmente ilegíveis quando ninguém renderiza. Foi o
-- renderizador que revelou: 16 fórmulas em 11 questões, de 13.881.
--
-- Todas as trocas abaixo são TIPOGRÁFICAS e foram conferidas contra a conta de
-- cada resolução. Nenhuma muda número, sinal, unidade ou resultado — devolvem
-- ao LaTeX a forma que o gerador errou ao escrever:
--
--   · chave que falta na base do log        \log_\sqrt3x   → \log_{\sqrt3}x
--   · espaço que falta depois do comando    \Rightarrowq   → \Rightarrow q
--   · linha e expoente na mesma variável    v'_{1y}^2      → {v'_{1y}}^2
--   · acento no lugar de espaço e ponto     mv^2\.         → mv^2\,.
--   · ambiente que o KaTeX não tem          psmallmatrix   → pmatrix
--   · `$` solto DENTRO do display, que arrastava a prosa e a unidade para
--     dentro da fórmula                     \newline / \" / $kJ/mol
--
-- Duas linhas merecem nota, porque a troca parece mudar o texto e não muda:
--
--   ime_2009_fase2_q05     "R$" escrito como `$\$$` reabria fórmula. Vira
--                          "reais", FORA da fórmula — mesmo valor, e some o
--                          `$` aninhado que o separador de fórmula não lê.
--   ime_2013_fase2_qui_q01 `\text{H$_2$O}` é LaTeX válido, mas aninha `$`
--                          dentro de `$…$`. `\text{H}_2\text{O}` diz o mesmo
--                          sem aninhar. Ver a ressalva em dominio/markdown.ts.
--
-- Como a 0039, cada `replace` é inerte se o texto já estiver certo: rodar duas
-- vezes não muda nada.

BEGIN;

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\approx2{,}0\,$R$\$$.$resolucao$, $resolucao$\approx2{,}0$ reais.$resolucao$)
 WHERE id = 'ime_2009_fase2_q05';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$psmallmatrix$resolucao$, $resolucao$pmatrix$resolucao$)
 WHERE id = 'ime_2010_fase2_mat_q02';  -- 4 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$[\text{H$_2$O}]$resolucao$, $resolucao$[\text{H}_2\text{O}]$resolucao$)
 WHERE id = 'ime_2013_fase2_qui_q01';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$+\tfrac12mv^2\. $resolucao$, $resolucao$+\tfrac12mv^2\,.$resolucao$)
 WHERE id = 'ime_2014_fase2_q01';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$=35p\Rightarrowq=$resolucao$, $resolucao$=35p\Rightarrow q=$resolucao$)
 WHERE id = 'ime_2017_fase2_mat_q07';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$-2xy\Rightarrowy^2$resolucao$, $resolucao$-2xy\Rightarrow y^2$resolucao$)
 WHERE id = 'ime_2018_fase2_mat_q04';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$=m\omega^2d\,.\" Dividindo, $$$resolucao$, $resolucao$=m\omega^2d\,.$$ Dividindo, $$$resolucao$)
 WHERE id = 'ita_2012_fase1_q06';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao${d}}$$\ e $$T=$resolucao$, $resolucao${d}}$$ e $$T=$resolucao$)
 WHERE id = 'ita_2012_fase1_q06';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\newline $resolucao$, $resolucao$$$ $resolucao$)
 WHERE id = 'ime_2012_fase2_qui_q02';  -- 2 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$$\log_\sqrt3x=363$resolucao$, $resolucao$$\log_{\sqrt3}x=363$resolucao$)
 WHERE id = 'ime_2016_fase2_mat_q03';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\tfrac12m_1v'_{1y}^2+\tfrac12m_2v'_{2y}^2$resolucao$, $resolucao$\tfrac12m_1{v'_{1y}}^2+\tfrac12m_2{v'_{2y}}^2$resolucao$)
 WHERE id = 'ita_2017_fase2_q23';  -- 1 ocorrência(s)

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\,$kJ/mol$$$resolucao$, $resolucao$\,\text{kJ/mol}$$$resolucao$)
 WHERE id = 'ita_2012_fase2_qui_q21';  -- 5 ocorrência(s)

COMMIT;
