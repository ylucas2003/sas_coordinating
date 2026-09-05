-- O cardápio da cantina: dia, blocos e opções (docs/38 §2.2).
--
-- O modelo sai da planilha que a cantina já usa: uma coluna por dia, e dentro
-- do dia blocos ("Guarnição", "Vegetariano", "Proteínas", "Salada") com N
-- opções cada. O que a planilha NÃO diz, e o produto precisa, é quantas opções
-- de cada bloco o aluno pode escolher — daí `escolhas_minimas`/`maximas`.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

CREATE TABLE IF NOT EXISTS cardapio (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cantina_id    uuid NOT NULL REFERENCES cantina(id),
    data          date NOT NULL,
    refeicao      text NOT NULL
        CONSTRAINT cardapio_refeicao_valida CHECK (refeicao IN ('almoco', 'janta')),
    pedidos_ate   timestamptz,
    publicado_em  timestamptz,
    sem_refeicao  boolean NOT NULL DEFAULT false,
    criado_por    uuid REFERENCES usuario_cantina(id),
    criado_em     timestamptz NOT NULL DEFAULT now(),
    atualizado_em timestamptz NOT NULL DEFAULT now(),
    UNIQUE (cantina_id, data, refeicao)
);

COMMENT ON TABLE cardapio IS
    'Um cardápio por (cantina, data, refeição). Almoço e janta são cardápios DIFERENTES — a comida não é a mesma, e o direito do aluno distingue os dois (docs/38 §8.0.8).';
COMMENT ON COLUMN cardapio.pedidos_ate IS
    'Instante em que o pedido fecha. NULO enquanto rascunho; publicar sem prazo é recusado pela API. Absoluto de propósito: "ainda aceita pedido?" tem de ser comparação, não conta (docs/38 §8.0.1).';
COMMENT ON COLUMN cardapio.publicado_em IS
    'NULO = rascunho, invisível para o aluno. A cantina monta a semana na sexta; sem rascunho ela publicaria pela metade.';
COMMENT ON COLUMN cardapio.sem_refeicao IS
    'true = "não haverá refeição neste dia" (feriado, recesso). Diferente de "ainda não lancei": sem isso o alarme da coordenação mentiria todo fim de semana.';

CREATE INDEX IF NOT EXISTS idx_cardapio_data ON cardapio (data);


CREATE TABLE IF NOT EXISTS cardapio_bloco (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cardapio_id      uuid NOT NULL REFERENCES cardapio(id) ON DELETE CASCADE,
    nome             text NOT NULL,
    ordem            int  NOT NULL,
    escolhas_minimas int  NOT NULL DEFAULT 0
        CONSTRAINT cardapio_bloco_minimo_valido CHECK (escolhas_minimas >= 0),
    escolhas_maximas int  NOT NULL DEFAULT 1
        CONSTRAINT cardapio_bloco_maximo_valido CHECK (escolhas_maximas >= escolhas_minimas),
    UNIQUE (cardapio_id, ordem)
);

COMMENT ON TABLE cardapio_bloco IS
    'Bloco do cardápio ("Guarnição", "Proteínas"). Texto livre e não taxonomia fixa: os quatro nomes de hoje são o cardápio de hoje, não uma lei, e uma tabela canônica exigiria migration toda vez que a cantina inventasse "Sobremesa".';
COMMENT ON COLUMN cardapio_bloco.escolhas_maximas IS
    'Quantas opções deste bloco o aluno pode marcar. Vive no BLOCO porque é assim que a cantina pensa: "Guarnição: escolha 2, Proteína: escolha 1".';
COMMENT ON COLUMN cardapio_bloco.escolhas_minimas IS
    'Zero = bloco opcional. Um = "escolher uma proteína é obrigatório", que é regra real e sem esta coluna viraria validação escondida no front.';

CREATE INDEX IF NOT EXISTS idx_cardapio_bloco_cardapio ON cardapio_bloco (cardapio_id);


CREATE TABLE IF NOT EXISTS cardapio_opcao (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    bloco_id   uuid NOT NULL REFERENCES cardapio_bloco(id) ON DELETE CASCADE,
    nome       text NOT NULL,
    ordem      int  NOT NULL,
    disponivel boolean NOT NULL DEFAULT true,
    UNIQUE (bloco_id, ordem)
);

COMMENT ON COLUMN cardapio_opcao.disponivel IS
    'false = acabou. É a ÚNICA alteração permitida numa opção que já tem pedido: renomear ou apagar faria 40 alunos terem pedido outra coisa sem saber (docs/38 §2.5).';

CREATE INDEX IF NOT EXISTS idx_cardapio_opcao_bloco ON cardapio_opcao (bloco_id);

COMMIT;
