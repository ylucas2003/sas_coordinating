-- A zona do aluno passa a dizer sob QUAL régua foi decidida (docs/31 §1.3).
--
-- `classificacao_aluno.zona` é calculada em lote, sem leitor na frente para
-- escolher critério — e até aqui usava uma cópia própria da regra de corte em
-- `thresholds.py`: matérias core fixas, mínimo 4,0, margem 1,0. O Painel, desde
-- a 0023, usa `criterios.py`. As duas discordavam sobre o mesmo aluno, e a
-- coluna não tinha como denunciar isso: 'risco' é veredito sem juiz.
--
-- Agora a zona sai do mesmo avaliador, sob `criterios.CRITERIO_DA_CASA`, e
-- estas duas colunas registram qual régua respondeu. São informativas de
-- propósito — sem FK para `criterio_classificacao`, porque as réguas embutidas
-- são a fonte da verdade no ARQUIVO (a tabela é espelho e semente, ver 0023) e
-- uma FK obrigaria a linha do banco a existir para a classificação rodar.
--
-- Por que `versao` junto: critério é imutável e editar cria versão (0023). Sem
-- a versão, saber "foi o tio-leo" ainda não diz sob que números.

BEGIN;

ALTER TABLE classificacao_aluno
    ADD COLUMN IF NOT EXISTS criterio_slug   text NOT NULL DEFAULT 'tio-leo',
    ADD COLUMN IF NOT EXISTS criterio_versao int  NOT NULL DEFAULT 1;

COMMENT ON COLUMN classificacao_aluno.zona            IS 'top | cinzenta | risco, decidida pelo avaliador de app/stats/criterios.py sob a régua nomeada em criterio_slug.';
COMMENT ON COLUMN classificacao_aluno.criterio_slug   IS 'Qual régua produziu a zona. Default tio-leo = criterios.CRITERIO_DA_CASA.';
COMMENT ON COLUMN classificacao_aluno.criterio_versao IS 'Versão da régua. Critério é imutável: editar cria versão nova (0023).';

COMMIT;
