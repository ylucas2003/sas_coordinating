-- Retirada presencial: comer sem ter pedido antes (docs/40 §1).
--
-- Até aqui só existia um jeito de comer: pedir com antecedência, dentro do
-- prazo (docs/38). Esta migration abre o segundo — chegar, mostrar um QR Code
-- gerado na hora, e a cantina ler — e deixa a critério de cada cantina quais
-- dos dois jeitos valem para cada refeição.
--
-- ⚠️ **Nenhuma tabela nova, e isso é decisão.** `pedido_refeicao` já é o
-- registro de "este aluno vai comer este cardápio", com o `UNIQUE(cardapio_id,
-- aluno_id)` que impede contar a mesma pessoa duas vezes (docs/38 §2.3). Uma
-- tabela paralela para o presencial teria de reimplementar essa mesma trava —
-- e a primeira vez que as duas divergissem, um aluno apareceria nas duas
-- listas.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md,
-- armadilha 1). Sem o restart as colunas novas voltam 404, e o 404 parece bug
-- de código.

BEGIN;

-- ─── O modo e a conclusão do pedido presencial ───────────────────────────

ALTER TABLE pedido_refeicao
    ADD COLUMN IF NOT EXISTS modo text NOT NULL DEFAULT 'pedido'
        CONSTRAINT pedido_refeicao_modo_valido CHECK (modo IN ('pedido', 'presencial')),
    ADD COLUMN IF NOT EXISTS retirado_em timestamptz;

-- O DEFAULT 'pedido' é o que faz as linhas que já existem continuarem
-- significando exatamente o que significavam: toda refeição pedida até hoje foi
-- pedida com antecedência.
COMMENT ON COLUMN pedido_refeicao.modo IS
    'pedido = escolheu itens com antecedência; presencial = declarou presença e vai mostrar o QR no balcão, sem prato escolhido (docs/40 §10.1). A transição é ASSIMÉTRICA: pedido é final, presencial vira pedido enquanto retirado_em for nulo (docs/40 §2).';

-- É o campo que docs/38 §8.1.3 já previa ("cabe depois sem migration
-- destrutiva"), só que generalizado: não é só "confirmar que retirou o que
-- pediu", é a PRÓPRIA conclusão do pedido presencial. E é ele que serve de
-- trava de corrida: a confirmação é um UPDATE condicional em
-- `retirado_em IS NULL`, nunca um ler-depois-escrever (docs/40 §4).
COMMENT ON COLUMN pedido_refeicao.retirado_em IS
    'Instante em que a cantina leu o QR. NULO = ainda não passou pelo balcão. Preenchido é estado FINAL dos dois lados — o aluno já comeu, não há desfazer. Modo pedido nunca tem este campo preenchido no v1: confirmar a retirada de quem PEDIU continua fora de escopo (docs/40 §14).';


-- ─── A regra da casa: que modos cada cantina aceita ──────────────────────
--
-- Mesmo papel que `prazo_padrao_*` já tem (0047): pré-preenche o cardápio novo,
-- e a cantina pode divergir dia a dia. Os DEFAULTs mantêm o comportamento de
-- hoje — só pedido — para toda cantina que já existe, senão a migration ligaria
-- sozinha uma feature que ninguém combinou de ligar.
--
-- Quatro colunas e não uma tabela porque são duas refeições × dois modos. Se um
-- terceiro modo aparecer um dia, isto vira tabela — o mesmo raciocínio que os
-- blocos de cardápio já usam (docs/38 §2.2).
ALTER TABLE cantina
    ADD COLUMN IF NOT EXISTS aceita_pedido_almoco     boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS aceita_pedido_janta      boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS aceita_presencial_almoco boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS aceita_presencial_janta  boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN cantina.aceita_pedido_almoco IS
    'REGRA da casa, não o valor do dia: pré-preenche cardapio.aceita_pedido de todo almoço novo. Quem manda no dia é o cardápio (docs/40 §1).';
COMMENT ON COLUMN cantina.aceita_pedido_janta IS
    'Mesma regra do almoço, para a janta.';
COMMENT ON COLUMN cantina.aceita_presencial_almoco IS
    'REGRA da casa para a retirada presencial no almoço. Nasce false: ligar o presencial é decisão de quem serve, não efeito colateral de uma migration.';
COMMENT ON COLUMN cantina.aceita_presencial_janta IS
    'Mesma regra do almoço, para a janta.';


-- ─── O valor do dia ──────────────────────────────────────────────────────
--
-- Absoluto, como `pedidos_ate` já é: a regra da cantina só pré-preenche, e
-- depois disso o cardápio responde sozinho por si. Sem isto, mudar a regra da
-- casa em outubro reescreveria o que valia em março.
ALTER TABLE cardapio
    ADD COLUMN IF NOT EXISTS aceita_pedido     boolean NOT NULL DEFAULT true,
    ADD COLUMN IF NOT EXISTS aceita_presencial boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN cardapio.aceita_pedido IS
    'true = o aluno pode escolher itens com antecedência neste dia. Publicar com este e aceita_presencial os dois em false é recusado (422): um cardápio que não aceita nada não é publicado, é sem_refeicao disfarçado (docs/40 §1).';
COMMENT ON COLUMN cardapio.aceita_presencial IS
    'true = o aluno pode gerar o QR e retirar no balcão sem ter pedido. NÃO olha pedidos_ate — presencial é justamente o caminho de quem não se planejou (docs/40 §3).';

COMMIT;
