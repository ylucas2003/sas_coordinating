-- Fila de revisão pra fusão de candidato_externo por confiança média — o
-- item 1 do §8 do docs/41, pedido explícito em 16/09/2026.
--
-- O resolver (scripts/resolver_candidatos_externos.py) só funde por nome +
-- escola EXATOS (§4.1) — de propósito, pra nunca juntar duas pessoas
-- diferentes por engano. Fontes sem escola (OBM, ITA, IME) nunca cruzam
-- automaticamente com o que a OBMEP/OBF já resolveram pra mesma pessoa,
-- mesmo quando é a mesma pessoa de verdade — cada conquista delas vira
-- candidato PRÓPRIO. Esta tabela é o segundo nível, de confiança MAIS
-- BAIXA (nome batendo sozinho, cidade/UF como pista extra) — nunca funde
-- sozinho, só REGISTRA A DECISÃO de quem olhou.
--
-- ⚠️ Não guarda os candidatos do grupo (não precisa): o grupo é sempre
-- "todo candidato_externo com este nome_normalizado", recalculado na
-- leitura (routes/captacao.py::_grupos_de_fusao) — igual o resolver relê
-- tudo a cada rodada em vez de guardar estado. O que esta tabela fixa é só
-- a DECISÃO humana, pra não perguntar de novo pro mesmo nome depois que
-- alguém já disse "não são a mesma pessoa".
--
-- Depois de aplicar: `docker compose restart postgrest` (CLAUDE.md, armadilha 1).

BEGIN;

CREATE TABLE IF NOT EXISTS candidato_externo_fusao_decisao (
    nome_normalizado text PRIMARY KEY,
    status           text NOT NULL
        CONSTRAINT fusao_decisao_status_valido
        CHECK (status IN ('confirmada', 'rejeitada')),
    decidido_por     text,
    decidido_em      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE candidato_externo_fusao_decisao IS
    'Uma linha por NOME já revisado na fila de fusão de baixa confiança (docs/41 §8 item 1). status=rejeitada tira o nome da fila pra sempre (a coordenação já disse que não é a mesma pessoa); status=confirmada é o registro de que a fusão aconteceu — o candidato_externo já foi combinado de verdade em routes/captacao.py::confirmar_fusao, esta linha é só a trilha de que já foi decidido, pra não sugerir de novo.';
COMMENT ON COLUMN candidato_externo_fusao_decisao.decidido_por IS
    'Nome de quem decidiu, pra mostrar na tela sem precisar resolver uuid — a auditoria (evento_auditoria) já guarda o id estável de quem confirmou ou rejeitou.';

-- A fila em si: todo NOME com mais de um candidato_externo — 6.560 grupos
-- (15/09/2026), grande o bastante pra precisar da MESMA paginação de
-- verdade que /captacao/candidatos já tem (0058), pelo mesmo motivo:
-- volume de gente de fora, sem teto natural. `ufs_distintas` é o sinal de
-- confiança que dá pra calcular sem abrir cada grupo — 1 UF só entre todos
-- os candidatos do nome é "todo mundo bate geograficamente", mais de uma é
-- "cuidado, pode ser gente diferente" (o caso real do Antonio Eduardo
-- Rossano, achado em 16/09/2026 — Fortaleza/CE numa conquista, Santa Fé do
-- Sul/SP noutra).
-- O `NOT EXISTS` já tira quem foi decidido (rejeitado — não sugere de novo;
-- confirmado — os candidatos já viraram um só, então o grupo nem bate mais
-- `count(*) > 1`, mas o filtro fica explícito mesmo assim, pra sobreviver
-- ao caso raro de uma conquista nova recriar o mesmo nome_normalizado
-- depois de rejeitado). Fazer isso AQUI, na view, e não filtrando uma lista
-- de nomes já decididos na rota: 6.560 grupos crescendo é gente demais pra
-- caber numa query string de `.not_.in_(...)`.
CREATE OR REPLACE VIEW v_fusao_candidata AS
SELECT
    c.nome_normalizado,
    count(*)::int AS candidatos,
    count(DISTINCT NULLIF(c.uf, '')) FILTER (WHERE c.uf IS NOT NULL)::int AS ufs_distintas
FROM candidato_externo c
WHERE NOT EXISTS (
    SELECT 1 FROM candidato_externo_fusao_decisao d
    WHERE d.nome_normalizado = c.nome_normalizado
)
GROUP BY c.nome_normalizado
HAVING count(*) > 1;

COMMENT ON VIEW v_fusao_candidata IS
    'Grupos de candidato_externo que COMPARTILHAM nome_normalizado e ainda não foram decididos — a fila da fusão de baixa confiança (docs/41 §8 item 1). ufs_distintas é o sinal de confiança rápido: 1 = todo mundo do grupo bate geograficamente, mais que 1 = pode ser gente diferente.';

COMMIT;
