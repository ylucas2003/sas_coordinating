-- Conserta as 20 resoluções em que a barra do LaTeX foi comida por um escape
-- de JSON.
--
-- Causa: `resolucao_md` é gerado por LLM e volta dentro de um campo de string
-- JSON. Quando o modelo escreve `\text{...}` sem escapar a barra, quem lê o
-- JSON faz exatamente o que a especificação manda — `\t` é TAB, `\b` é
-- backspace, `\f` é formfeed, `\r` é carriage return. O que chegou ao banco foi
-- `<TAB>ext{...}`, `<FF>rac{...}`, `<BS>oldsymbol`. São só esses quatro porque
-- são os únicos escapes de JSON que colidem com comando de LaTeX comum
-- (\text \theta \times \tfrac, \begin \boldsymbol, \frac, \right \rho).
--
-- Medido em 01/09/2026 sobre as 1.500 resoluções: 20 questões, concentradas em
-- dois lotes de extração — ITA 2008 1ª fase (Física) e IME 2013 2ª fase
-- (Matemática). Enunciado e alternativa não foram atingidos: não passam por
-- esse caminho.
--
-- ⚠️ O texto corrompido NÃO aparece literalmente neste arquivo, e é de
-- propósito: escrever um CR dentro do `.sql` não sobrevive à leitura (a
-- primeira versão desta migration fez isso e os 6 UPDATEs com CR casaram com
-- nada, falhando em silêncio). Aqui a corrupção é descrita por `chr()` e
-- desfeita por `replace()`, o que também torna o arquivo idempotente: rodar
-- duas vezes não muda nada, porque a segunda não acha mais controle nenhum.

BEGIN;

-- ── 1. A regra mecânica: repor a barra que o parser de JSON engoliu ──────
UPDATE questao_vestibular
   -- `'\t'` aqui é barra-t de dois caracteres, não uma tabulação: o Postgres
   -- roda com standard_conforming_strings ligado, então string simples não
   -- interpreta escape. É justamente o que se quer devolver ao texto.
   SET resolucao_md = replace(replace(replace(replace(
         resolucao_md,
         chr(9),  '\t'),
         chr(8),  '\b'),
         chr(12), '\f'),
         chr(13), '\r')
 WHERE resolucao_md IS NOT NULL
   AND (strpos(resolucao_md, chr(9))  > 0 OR strpos(resolucao_md, chr(8))  > 0
     OR strpos(resolucao_md, chr(12)) > 0 OR strpos(resolucao_md, chr(13)) > 0);

-- ── 2. O ETX (chr 3), que é lixo do texto do PDF da ITA 2008 ─────────────
-- Aparece solto dentro e fora de fórmula e não substitui comando nenhum. A
-- ÚNICA exceção é ime_2013_fase2_mat_q01, excluída aqui e tratada no passo 4:
-- lá o caractere era o traço do conjugado, e apagá-lo perderia informação.
UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, chr(3), '')
 WHERE id <> 'ime_2013_fase2_mat_q01'
   AND resolucao_md IS NOT NULL
   AND strpos(resolucao_md, chr(3)) > 0;

-- ── 3. Erro de LaTeX genuíno por baixo da corrupção, conferido à mão ────
-- `\root2\bigl2gH\bigr` não é LaTeX de nada (é a raiz de 2gH); `\\Delta`
-- dentro de display é quebra de linha seguida da palavra "Delta"; e duas
-- resoluções escritas em prosa com Unicode tinham comando solto fora de `$`.
-- Cada `replace` é inerte se o texto já estiver certo.
UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$v=\root2\bigl2gH\bigr$resolucao$, $resolucao$v=\sqrt{2gH}$resolucao$)
 WHERE id = 'ita_2008_fase1_q17';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$x_P=\bigl(\textstyle2\root2\bigl2^2+2^2\bigr)^{1/2}-1=2√2-1\rm\text{m}$resolucao$, $resolucao$x_P=\left(2^2+2^2\right)^{1/2}-1=2\sqrt2-1\,\text{m}$resolucao$)
 WHERE id = 'ita_2008_fase1_q14';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$x_T=2-1=1\rm\text{m}$resolucao$, $resolucao$x_T=2-1=1\,\text{m}$resolucao$)
 WHERE id = 'ita_2008_fase1_q14';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$v=√{23{,}4}\rm\text{m/s}$resolucao$, $resolucao$v=\sqrt{23{,}4}\,\text{m/s}$resolucao$)
 WHERE id = 'ita_2008_fase1_q14';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$26r^2\\\rightar-15a_1r$resolucao$, $resolucao$26r^2 \Rightarrow -15a_1r$resolucao$)
 WHERE id = 'ime_2011_fase2_mat_q01';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$$$\\Delta=2$resolucao$, $resolucao$$$\Delta=2$resolucao$)
 WHERE id = 'ime_2014_fase2_mat_q09';

UPDATE questao_vestibular
   SET resolucao_md = replace(resolucao_md, $resolucao$(2n\tanα)$resolucao$, $resolucao$(2n·tan α)$resolucao$)
 WHERE id = 'ita_2015_fase1_q09';

-- ── 4. A que precisou de reescrita ──────────────────────────────────────
-- Aqui o ETX não era lixo: era o traço do conjugado. Apagá-lo trocaria `α, ᾱ`
-- por `α, α` — corrupção que muda a matemática, não a aparência. Junto vinham
-- `\frac`, `\bigl` e a raiz picados pelos mesmos escapes. Reposto o conjugado
-- e desfeitos os comandos, mantendo o registro em que a resolução foi escrita
-- (prosa com Unicode, sem `$`) e SEM tocar no conteúdo da conta.
UPDATE questao_vestibular
   SET resolucao_md = $resolucao$Considere as raízes α, ᾱ, ρ e σ, onde σ=|α|. Pelas relações de Vieta:
- α+ᾱ+ρ+σ=3
- αᾱ+(α+ᾱ)(ρ+σ)+ρσ=10
- αᾱ(ρ+σ)+(α+ᾱ)ρσ=−30
- αᾱρσ=−243
Como αᾱ=|α|²=σ², substitua e resolva o sistema para σ e ρ.
Obtêm-se σ=3, ρ=−3 e α=3e^(±i·2π/3).
Logo as raízes são 3, −3, 3·(−1 ± i√3)/2 e seu conjugado.$resolucao$
 WHERE id = 'ime_2013_fase2_mat_q01'
   AND strpos(resolucao_md, chr(3)) > 0;

COMMIT;
