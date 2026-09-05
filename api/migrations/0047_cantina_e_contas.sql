-- A cantina e suas contas de acesso (docs/38 §2.1).
--
-- É o TERCEIRO tipo de sessão do SAS, e o primeiro desde que o projeto existe.
-- Não é um `papel` dentro de `usuario_coordenacao`: um papel novo ali passaria
-- por `get_current_coordenador` — que aceita todo papel de propósito — e
-- abriria as 39 rotas de coordenação para quem trabalha na copa (docs/38 §1).
--
-- ⚠️ Esta migration sozinha não é segura: ela é o par do conserto fail-closed
-- em `app/routes/foto_perfil.py`. Antes de 05/09 aquele arquivo assumia, por
-- escrito, que "só 'aluno' ou 'coordenador' chegam aqui" e caía num `return`
-- de coordenação para todo o resto — com a cantina existindo, isso viraria
-- acesso de ESCRITA a `usuario_coordenacao`. Ver docs/38 §1.1.
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest`. O schema cache é
-- lido na inicialização, e sem o restart as tabelas novas voltam 404 — que
-- parece bug de código (CLAUDE.md, armadilha 1).

BEGIN;

-- Por que a cantina é uma ENTIDADE separada da conta, mesmo sendo uma só hoje:
-- o cardápio precisa pertencer a algo que sobreviva à rotatividade de quem
-- trabalha lá. Desativar a conta de quem saiu não pode orfanar os cardápios de
-- março. Custa uma tabela de seis colunas.
CREATE TABLE IF NOT EXISTS cantina (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nome                    text NOT NULL,
    ativo                   boolean NOT NULL DEFAULT true,
    prazo_padrao_dias_antes int  NOT NULL DEFAULT 1
        CONSTRAINT cantina_prazo_dias_valido CHECK (prazo_padrao_dias_antes >= 0),
    prazo_padrao_hora       time NOT NULL DEFAULT '20:00',
    criado_em               timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE  cantina IS
    'O estabelecimento, não a conta. O cardápio pertence a ele para sobreviver à troca de quem trabalha lá (docs/38 §2.1).';
COMMENT ON COLUMN cantina.prazo_padrao_dias_antes IS
    'A REGRA de prazo da casa, que pré-preenche cada cardápio novo — não é o prazo. O prazo é cardapio.pedidos_ate, absoluto, e a cantina pode sobrescrever dia a dia (docs/38 §8.0.1).';
COMMENT ON COLUMN cantina.prazo_padrao_hora IS
    'Hora do dia em que o pedido fecha, contada prazo_padrao_dias_antes antes da data da refeição.';


CREATE TABLE IF NOT EXISTS usuario_cantina (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cantina_id      uuid NOT NULL REFERENCES cantina(id),
    email           text NOT NULL,
    nome            text NOT NULL,
    senha_hash      text NOT NULL,
    ativo           boolean NOT NULL DEFAULT true,
    criado_em       timestamptz NOT NULL DEFAULT now(),
    ultimo_login_em timestamptz
);

-- Case-insensitive, mesmo motivo da 0021: ninguém deve conseguir criar
-- `Copa@` e `copa@` como contas diferentes, e o login normaliza para
-- minúsculas antes de consultar.
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuario_cantina_email
    ON usuario_cantina (lower(email));

COMMENT ON TABLE  usuario_cantina IS
    'Logins da cantina. Espelho de usuario_coordenacao (0021), inclusive o formato do hash.';
COMMENT ON COLUMN usuario_cantina.senha_hash IS
    'pbkdf2_sha256$<iteracoes>$<salt>$<hash> — mesmo formato de usuario_coordenacao.senha_hash.';

COMMIT;
