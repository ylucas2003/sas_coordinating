-- O zero de OITO provas de 2023 é falta, não desempenho (docs/32 §1.4).
--
-- A 0043 criou `simulado.nota_confiavel`, que tira a prova inteira dos
-- agregados. Era o desenho do plano naquele dia. Em 04/09 ele foi trocado por
-- um melhor, e a troca tem número em cima:
--
--   Excluir a prova jogava fora as ~130 notas VERDADEIRAS de cada uma — as de
--   quem compareceu — e, pior, INFLAVA a média do ciclo, porque as oito eram
--   provas genuinamente difíceis (média de 2,7 a 4,4 entre quem as fez).
--
--   | Ciclo (2023) | hoje | excluindo a prova | só os zeros viram falta |
--   |--------------|------|-------------------|-------------------------|
--   | Ciclo 4 ITA  | 4,33 |       6,18        |          5,51           |
--   | Ciclo 6 ITA  | 4,41 |       6,47         |          6,08           |
--
--   A terceira coluna é a leitura certa: uma depressão SUAVE entre abril e
--   julho, que é real, no lugar de um desabamento que não foi.
--
-- A conferência que autoriza a regra é a prova irmã. Em cada uma das oito, o
-- número de alunos ACIMA DE ZERO tem de bater com quantos alunos a prova
-- aplicada no MESMO DIA avaliou — os dois descrevem quem compareceu. Seis das
-- oito batem dentro de 1% a 7% (130/128, 118/120, 218/224, 222/231, 200/212,
-- 222/238); as duas de 08/05 são irmãs uma da outra e concordam entre si
-- (234 e 224). São seis confirmações independentes, cada uma vinda de um
-- professor diferente que no mesmo dia lançou a nota do jeito certo.
--
-- Erro assumido, medido: a regra converteria em falta, no máximo, de 2 a 16
-- zeros legítimos por prova — contra 165 a 325 faltas por prova hoje contadas
-- como nota.
--
-- ─── Por que uma coluna NOVA, e não reusar `nota_confiavel` ──────────────
--
-- São dois vereditos diferentes sobre a prova, e confundi-los custaria caro:
--
--   nota_confiavel = false  →  "a coluna INTEIRA não presta". A prova sai dos
--                              agregados. Continua existindo para o caso de
--                              uma prova de fato inutilizável.
--   zero_e_ausencia = true  →  "nesta prova, 0 quer dizer FALTA". A prova FICA
--                              nos agregados, com a média de quem a fez; só as
--                              notas zeradas saem, uma a uma, por
--                              `nota.computavel`.
--
-- Nenhuma prova está marcada com `nota_confiavel = false` hoje — o Problema B
-- nunca foi aplicado, então não há dado a migrar de um para o outro.
--
-- ⚠️ Esta migration NÃO marca prova nenhuma. Marcar as oito depende do aval da
-- coordenação sobre o histórico de 2023 (docs/32 §1.7), e é um UPDATE
-- explícito, com a lista na mão, quando esse aval vier.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest`. O schema cache é
-- carregado na inicialização e a coluna nova volta 404 sem o restart — que
-- parece bug de código (CLAUDE.md, armadilha 1).

BEGIN;

ALTER TABLE simulado
    ADD COLUMN IF NOT EXISTS zero_e_ausencia        boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS motivo_zero_e_ausencia text;

COMMENT ON COLUMN simulado.zero_e_ausencia IS
    'Nesta prova, pontuacao = 0 com presenca significa FALTA, nao desempenho. A prova CONTINUA nos agregados; quem sai sao as notas zeradas, marcadas nota.computavel = false por stats/computavel.py. Ligado a mao, com lista na mao — nao ha detector automatico, de proposito (docs/32 §1.4).';

COMMENT ON COLUMN simulado.motivo_zero_e_ausencia IS
    'Por que esta prova entrou na lista. Texto livre, escrito por quem ligou a marca — a conferencia da prova irma do mesmo dia mora aqui.';

COMMIT;
