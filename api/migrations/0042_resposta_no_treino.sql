-- A resposta do treino passa a sobreviver à sessão.
--
-- Até aqui o aluno escolhia uma alternativa em `Treino.tsx`, via se acertou, e
-- a informação morria no `useState` quando ele fechava a tela. Era a fonte
-- `respostaNoTreino` do inventário (`web/src/dados/aluno/registro.ts`), a única
-- superfície do treino que continuava mock.
--
-- POR QUE VALE A PENA, e não é só completude: **é a única fonte de acerto por
-- assunto que não depende do Sprint 6.** As questões do banco JÁ estão
-- classificadas por tópico do edital (`questao_vestibular_topico`, 0028), então
-- a resposta gravada aqui já nasce dizendo em que assunto o aluno errou. As
-- 1.031 questões de simulado continuam sem classificar — esse é o caminho
-- crítico de docs/24 §3.2 — mas ele deixa de ser o único caminho.
--
-- ⚠️ ISTO ALIMENTA O PLANO DE ESTUDO, NUNCA O XP. Treino não é supervisionado:
-- ninguém garante que foi o aluno quem resolveu, quanto tempo levou nem se
-- consultou a resolução antes de responder. XP só sai de simulado, porque só
-- simulado é verificável (docs/26 §1 e §2, docs/28 §3 regra 5). Uma tela que
-- pague ponto por isto contradiz a regra central do produto.
--
-- ⚠️ E NÃO É `resolvida`. As duas colunas convivem e dizem coisas diferentes:
-- `resolvida` é auto-declarado ("eu fiz esta"), e o aluno pode marcá-la sem
-- nunca ter respondido; `acertou` é conferido contra o gabarito. Somar as duas,
-- ou tirar média entre elas, produz um número que não significa nada.
--
-- ONDE MORA: em `questao_estudo_aluno` e não em tabela nova, porque a PK
-- (aluno_id, questao_id) já é exatamente "o que este aluno fez com esta
-- questão". A consequência precisa ficar escrita: **só a última resposta
-- sobrevive** — refazer a questão sobrescreve a tentativa anterior. É o que se
-- quer para "em que assunto ele erra hoje"; um histórico de tentativas seria
-- outra tabela, e nenhuma tela pede isso.
--
-- OS DOIS NULOS, que significam coisas diferentes:
--   alternativa_escolhida IS NULL  o aluno pulou a questão
--   acertou IS NULL                não dá para dizer — questão sem gabarito.
--                                  São as dissertativas (420 e 469 das 934
--                                  originais, docs/22 §8 risco 4) e as
--                                  objetivas cujo gabarito não foi importado.
--                                  NULL aqui é "não sabemos", nunca "errou", e
--                                  a tela é obrigada a distinguir.
--
-- A CONFIANÇA NÃO SE DUPLICA AQUI. Parte do acervo histórico tem gabarito
-- deduzido em vez de publicado (`gabarito_origem = 'sugerido'`, 0031). O
-- `acertou` calculado contra ele herda essa incerteza, e quem quiser filtrar
-- junta com `questao_vestibular` — copiar a confiança para cá criaria duas
-- verdades sobre a mesma letra, que foi o defeito que a 0031 existe para
-- evitar.

BEGIN;

ALTER TABLE questao_estudo_aluno
    ADD COLUMN IF NOT EXISTS alternativa_escolhida text,
    ADD COLUMN IF NOT EXISTS acertou               boolean;

-- Acertar sem ter respondido é o estado que não pode existir: seria um acerto
-- que ninguém sabe de onde veio.
ALTER TABLE questao_estudo_aluno
    ADD CONSTRAINT questao_estudo_aluno_acertou_exige_resposta
        CHECK (acertou IS NULL OR alternativa_escolhida IS NOT NULL);

COMMENT ON COLUMN questao_estudo_aluno.alternativa_escolhida IS
  'A letra que o aluno marcou no treino. NULL = pulou. Só a última tentativa sobrevive: refazer a questão sobrescreve.';
COMMENT ON COLUMN questao_estudo_aluno.acertou IS
  'Conferido contra questao_vestibular.gabarito no servidor. NULL = questão sem gabarito (dissertativa ou não importado) — "não dá para dizer", nunca "errou". Alimenta o plano de estudo; NUNCA o XP, que só sai de simulado (docs/26 §1).';

COMMIT;
