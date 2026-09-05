-- Quem tem direito a refeição, o que ele pediu, e a contagem para o fogão
-- (docs/38 §2.3, §2.4 e §2.6).
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

-- ─── O direito ───────────────────────────────────────────────────────────
--
-- Uma TABELA e não duas colunas booleanas: "almoço e/ou janta" vira zero, uma
-- ou duas linhas, sem estado impossível. É o desenho de `vestibular_alvo_aluno`
-- (0001) — precedente do projeto para "um conjunto enumerado por aluno", e o
-- schema é para ser lido por quem entende do domínio.
--
-- SEM vigência, de propósito (docs/38 §8.0.4): a linha existe = tem direito;
-- some = não tem. `ativo_desde`/`ativo_ate`, como `matricula_turma` faz, foram
-- recusados — "quem revogou e quando" é pergunta de AUDITORIA, e
-- `evento_auditoria` já responde. Duas datas a mais criariam três leituras
-- possíveis do mesmo aluno ("tem", "tinha", "vai ter") em toda tela.
--
-- A FK para `aluno` basta, e isso também é decisão (docs/38 §8.0.10): o SAS só
-- conhece as turmas ITA/IME — `upsert_alunos_em_lote` é o único escritor de
-- `aluno`, e o sync do Canvas só enxerga o curso `{ano} 3o ITA/IME Simulados`.
-- Não há segundo cadastro de aluno, nem aluno "só da cantina".
CREATE TABLE IF NOT EXISTS direito_refeicao_aluno (
    aluno_id uuid NOT NULL REFERENCES aluno(id),
    refeicao text NOT NULL
        CONSTRAINT direito_refeicao_valida CHECK (refeicao IN ('almoco', 'janta')),
    PRIMARY KEY (aluno_id, refeicao)
);

COMMENT ON TABLE direito_refeicao_aluno IS
    'Flag pura: a linha existe = o aluno tem direito àquela refeição. Conceder e revogar é só do administrador, e os dois vão para evento_auditoria no canal cantina (docs/38 §8.0.3).';


-- ─── A restrição alimentar ───────────────────────────────────────────────
--
-- Coluna em `aluno` e não tabela nova: é um campo por pessoa, sem histórico e
-- sem cardinalidade — e `aluno` já carrega colunas que o ingest do Canvas não
-- toca (`senha_hash`, `foto_perfil_storage`).
--
-- ⚠️ É a PRIMEIRA informação de saúde no SAS. Não muda a arquitetura, mas muda
-- o que um vazamento significaria: por isso quem preenche é a coordenação (não
-- o aluno — autodeclaração de saúde por menor abre um problema de
-- consentimento que este produto não resolve), o campo aparece só na lista de
-- pedidos da cantina, e alterá-lo é auditado (docs/38 §2.6).
ALTER TABLE aluno ADD COLUMN IF NOT EXISTS restricao_alimentar text;

COMMENT ON COLUMN aluno.restricao_alimentar IS
    'Restrição alimentar em texto livre, preenchida pela COORDENAÇÃO. Aparece para a cantina ao lado do pedido, e em lugar nenhum mais — não entra em ficha, painel, dossiê nem chat (docs/38 §2.6).';


-- ─── O pedido ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pedido_refeicao (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cardapio_id   uuid NOT NULL REFERENCES cardapio(id),
    aluno_id      uuid NOT NULL REFERENCES aluno(id),
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cardapio_id, aluno_id)
);

COMMENT ON TABLE pedido_refeicao IS
    'Um pedido por aluno por cardápio. Trocar antes do prazo substitui os itens; depois de cardapio.pedidos_ate nada entra nem sai — nem pela cantina (docs/38 §8.0.5).';

CREATE TABLE IF NOT EXISTS pedido_refeicao_item (
    pedido_id uuid NOT NULL REFERENCES pedido_refeicao(id) ON DELETE CASCADE,
    opcao_id  uuid NOT NULL REFERENCES cardapio_opcao(id),
    PRIMARY KEY (pedido_id, opcao_id)
);

COMMENT ON TABLE pedido_refeicao_item IS
    'O que o aluno marcou. A PK composta já impede escolher a mesma opção duas vezes; o teto por bloco é validado na API, que é onde a regra pode ser explicada.';

-- ⚠️ Estas duas tabelas são as primeiras do SAS que crescem por
-- *dia útil × aluno × item* — 160 mil a 1,4 milhão de linhas no primeiro ano,
-- num sistema SEM PAGINAÇÃO em lugar nenhum (CLAUDE.md, armadilha 2). Nenhuma
-- rota devolve "os pedidos": toda leitura é filtrada por cardapio_id (um dia)
-- ou por aluno_id com janela de data. Os índices abaixo são o que torna esse
-- filtro barato, e entram junto com as tabelas — não depois.
CREATE INDEX IF NOT EXISTS idx_pedido_refeicao_cardapio ON pedido_refeicao (cardapio_id);
CREATE INDEX IF NOT EXISTS idx_pedido_refeicao_aluno    ON pedido_refeicao (aluno_id);
CREATE INDEX IF NOT EXISTS idx_pedido_item_opcao        ON pedido_refeicao_item (opcao_id);


-- ─── A contagem para o fogão ─────────────────────────────────────────────
--
-- View e não soma em Python: somar no cliente traria as linhas cruas pelo
-- PostgREST, que é exatamente o que a armadilha 2 proíbe nesta escala. Aqui o
-- Postgres agrega e devolve uma linha por opção.
--
-- `LEFT JOIN` de propósito: opção com zero pedido tem de aparecer com 0. Uma
-- contagem que omite o que ninguém pediu obriga a cantina a cruzar com o
-- cardápio de cabeça para descobrir o que sobrou.
CREATE OR REPLACE VIEW v_contagem_pedidos_por_opcao AS
SELECT
    c.id                        AS cardapio_id,
    b.id                        AS bloco_id,
    b.nome                      AS bloco,
    b.ordem                     AS bloco_ordem,
    o.id                        AS opcao_id,
    o.nome                      AS opcao,
    o.ordem                     AS opcao_ordem,
    o.disponivel                AS disponivel,
    count(i.pedido_id)::int     AS quantos
FROM cardapio c
JOIN cardapio_bloco b ON b.cardapio_id = c.id
JOIN cardapio_opcao o ON o.bloco_id = b.id
LEFT JOIN pedido_refeicao_item i ON i.opcao_id = o.id
GROUP BY c.id, b.id, b.nome, b.ordem, o.id, o.nome, o.ordem, o.disponivel;

COMMENT ON VIEW v_contagem_pedidos_por_opcao IS
    'Quantos pediram cada opção de cada cardápio. É o que a cantina lê de manhã para cozinhar — e é view porque somar no cliente traria a tabela inteira (docs/38 §2.4).';

-- Quantos pedidos cada cardápio tem. É o que pinta o calendário da cantina, e
-- é view pelo mesmo motivo da de cima: o calendário mostra um MÊS, e contar em
-- Python exigiria trazer todos os pedidos do mês só para saber o tamanho de
-- cada dia.
CREATE OR REPLACE VIEW v_pedidos_por_cardapio AS
SELECT
    c.id                    AS cardapio_id,
    count(p.id)::int        AS quantos
FROM cardapio c
LEFT JOIN pedido_refeicao p ON p.cardapio_id = c.id
GROUP BY c.id;

COMMENT ON VIEW v_pedidos_por_cardapio IS
    'Quantos alunos pediram em cada cardápio. LEFT JOIN para o dia sem pedido aparecer com 0 em vez de sumir do calendário.';


-- O canal novo da trilha. `evento_auditoria.canal` é texto livre (0025), então
-- isto é documentação, não restrição — mas sem atualizar o comentário o
-- próximo a ler a tabela não descobre que 'cantina' existe.
COMMENT ON COLUMN evento_auditoria.canal IS
    'acesso | nota | simulado | ciclo | canvas | cantina. Filtro da linha do tempo; permite retenção por canal.';

COMMIT;
