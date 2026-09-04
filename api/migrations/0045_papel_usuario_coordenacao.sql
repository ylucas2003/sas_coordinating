-- Papel da conta de coordenação (docs/35 §11.4).
--
-- Até aqui `usuario_coordenacao` tinha um único nível: quem entrava podia
-- tudo o que o painel oferece — inclusive criar login para outra pessoa e
-- alterar nota de aluno. A coordenação pediu em 04/09 que essas duas coisas
-- ficassem com UMA conta, e o resto continuasse com todas.
--
-- Por que `DEFAULT 'coordenador'` e não uma coluna anulável: o default É o
-- pedido. As oito contas que existem em produção viram coordenador sozinhas,
-- sem UPDATE nenhum, e a promoção do administrador é uma linha explícita
-- depois (passo operacional, com a coordenação junto — docs/35 §11.2).
--
-- O CHECK existe porque o backend nunca escreve SQL: quem grava é o PostgREST,
-- a partir de um corpo JSON. Sem a restrição no banco, um `papel: "admin"`
-- (ou "Administrador", com maiúscula) entraria calado e a conta ficaria SEM
-- poder nenhum — o guard compara string exata (app/auth.py). Falha barulhenta
-- aqui é melhor que conta morta lá.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest`. O schema cache é
-- carregado na inicialização, e sem o restart a coluna nova volta 404 — que
-- parece bug de código (CLAUDE.md, armadilha 1).
--
-- O NOME DA TABELA fica torto a partir daqui: `usuario_coordenacao` passa a
-- guardar também o administrador. Renomear é caro (`.table("usuario_coordenacao")`
-- espalhado pelo backend) e fica registrado, não feito (docs/35 §11.4).

BEGIN;

ALTER TABLE usuario_coordenacao
    ADD COLUMN IF NOT EXISTS papel text NOT NULL DEFAULT 'coordenador'
        CONSTRAINT usuario_coordenacao_papel_valido
        CHECK (papel IN ('coordenador', 'administrador'));

COMMENT ON COLUMN usuario_coordenacao.papel IS
    'coordenador (padrão) ou administrador. Administrador é coordenador COM MAIS PODERES, não outro cargo: ele passa por todo guard de coordenação e mais os de conta e edição de nota (docs/35 §11).';

COMMIT;
