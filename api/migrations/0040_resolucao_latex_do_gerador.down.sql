-- Desfaz a 0040, devolvendo o LaTeX inválido que o gerador escreveu.
--
-- Diferente da 0039, este down É seguro e simétrico: cada troca aqui é uma
-- substring longa e específica de UMA questão nomeada, não uma regra sobre
-- texto que possa pegar resolução sadia por engano.
--
-- Só não há motivo para rodá-lo: o resultado é fórmula em vermelho na tela do
-- aluno. Existe porque toda migration tem par (CLAUDE.md, convenções).

BEGIN;

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\approx2{,}0$ reais.$resolucao$, $resolucao$\approx2{,}0\,$R$\$$.$resolucao$)
 WHERE id = 'ime_2009_fase2_q05';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$pmatrix$resolucao$, $resolucao$psmallmatrix$resolucao$)
 WHERE id = 'ime_2010_fase2_mat_q02';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$[\text{H}_2\text{O}]$resolucao$, $resolucao$[\text{H$_2$O}]$resolucao$)
 WHERE id = 'ime_2013_fase2_qui_q01';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$+\tfrac12mv^2\,.$resolucao$, $resolucao$+\tfrac12mv^2\. $resolucao$)
 WHERE id = 'ime_2014_fase2_q01';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$=35p\Rightarrow q=$resolucao$, $resolucao$=35p\Rightarrowq=$resolucao$)
 WHERE id = 'ime_2017_fase2_mat_q07';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$-2xy\Rightarrow y^2$resolucao$, $resolucao$-2xy\Rightarrowy^2$resolucao$)
 WHERE id = 'ime_2018_fase2_mat_q04';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$=m\omega^2d\,.$$ Dividindo, $$$resolucao$, $resolucao$=m\omega^2d\,.\" Dividindo, $$$resolucao$)
 WHERE id = 'ita_2012_fase1_q06';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao${d}}$$ e $$T=$resolucao$, $resolucao${d}}$$\ e $$T=$resolucao$)
 WHERE id = 'ita_2012_fase1_q06';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$$$ $resolucao$, $resolucao$\newline $resolucao$)
 WHERE id = 'ime_2012_fase2_qui_q02';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$$\log_{\sqrt3}x=363$resolucao$, $resolucao$$\log_\sqrt3x=363$resolucao$)
 WHERE id = 'ime_2016_fase2_mat_q03';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\tfrac12m_1{v'_{1y}}^2+\tfrac12m_2{v'_{2y}}^2$resolucao$, $resolucao$\tfrac12m_1v'_{1y}^2+\tfrac12m_2v'_{2y}^2$resolucao$)
 WHERE id = 'ita_2017_fase2_q23';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$\,\text{kJ/mol}$$$resolucao$, $resolucao$\,$kJ/mol$$$resolucao$)
 WHERE id = 'ita_2012_fase2_qui_q21';

COMMIT;
