-- 0076 · A captação externa entra no MCP da coordenação (docs/43 §5.2; docs/41)
--
-- Decisão da coordenação em 30/10/2026: TUDO o que o coordenador lê na
-- plataforma passa a ser lido também pela IA no MCP. A captação ficava fora
-- de propósito (0071 e docs/43 §6: "dado de gente de fora") e não tinha tool
-- nem no chat. Agora tem quatro, em `app/chat/tools/captacao.py`, que leem
-- pelo domínio `app/captacao/consultas.py` — o mesmo da rota
-- `routes/captacao.py`:
--
--   buscar_candidatos_externos       a lista de /administracao/captacao
--   buscar_candidatos_por_conquista  a busca por conquista (0068, docs/41 §20)
--   perfil_do_candidato_externo      a ficha de um nome e a de um perfil
--   provas_da_captacao               o rodapé "quais fontes alimentam a lista"
--
-- A LISTA BRANCA cresce aqui com exatamente o que essas quatro pedem, seguindo
-- cada uma até o PostgREST — select, filtro e ordem — e, na busca por
-- conquista, até o corpo da função da 0068, que é SECURITY INVOKER: roda com o
-- privilégio de quem chama, e o Postgres exige SELECT em toda coluna que ela
-- cita. Por coluna, como na 0071: coluna nova nasce invisível ao MCP.
--
-- São pessoas que nunca se cadastraram no SAS, muitas menores. Entra só o que
-- as telas da captação mostram, e o que fica de fora fica pelo nome:
--   * `candidato_externo.observacoes` — o texto livre do funil, escrito pela
--     coordenação. O SAS não tem coluna de contato; se um telefone ou o que a
--     família disse aparecer em algum lugar, é ali;
--   * o bastidor da raspagem e do resolver que a tela não mostra:
--     `conquista_externa.nome_informado`, `raspado_em`,
--     `serie_referencia_min/max` (a tela mostra o nível, `nivel_texto`) e
--     `candidato_externo.retrato_editado_a_mao` e `atualizado_em`;
--   * `prova_externa.abrangencia` e `fonte_resultado` — catálogo, não pessoa,
--     mas nenhuma tool os lê.
--
-- DUAS VIEWS entram, e nenhuma das duas roda com o privilégio do dono — a
-- razão de a 0071 deixar toda view de fora:
--   * `v_candidato_externo_por_nome` é MATERIALIZADA (0063/0068): ler não roda
--     a consulta de baixo, e o GRANT por coluna vale como numa tabela. ⚠️ Ela
--     PERDE o GRANT quando é derrubada e recriada (foi o que a 0065 e a 0068
--     fizeram): quem a recriar repete o GRANT abaixo na mesma migration — o
--     leitor da lista branca (scripts/verificar_papeis_do_mcp.py) segue o DROP
--     e o teste das migrations reprova a que esquecer;
--   * `v_prova_externa_resumo` (0063) passa a SECURITY INVOKER aqui: lê com o
--     privilégio de quem chama, então o sas_mcp a lê só porque lê as colunas
--     de `prova_externa` e `conquista_externa` que ela agrega. A API não muda:
--     o sas_service tem ALL nas duas. ⚠️ `CREATE OR REPLACE VIEW` sem
--     `WITH (security_invoker = true)` DESLIGA a opção (provado num Postgres
--     16 descartável em 30/10) — a auditoria das migrations reprova o GRANT
--     numa view assim.
-- `v_candidato_externo` (0058/0064), a do perfil, NÃO entra: roda como o dono
-- e cita `observacoes`. A ficha passou a ler `candidato_externo` direto e a
-- somar as conquistas que já lê (`consultas.perfis_do_nome`).
--
-- Nenhuma escrita: só SELECT. As rotas do funil e do modo avançado continuam
-- só na API. E a função de refresh da view por nome continua fora do MCP
-- (REVOKE de PUBLIC na 0071).
--
-- ⚠️ Depois de aplicar: `docker compose restart postgrest postgrest_mcp`
-- (CLAUDE.md, armadilha 1) e `python -m scripts.verificar_papeis_do_mcp
-- --ferramentas`, que roda as quatro contra o PostgREST do MCP. O GRANT vale na
-- hora: o Postgres confere privilégio a cada consulta.

BEGIN;

-- ─── A view do rodapé passa a ler com o privilégio de quem chama ──────────
ALTER VIEW v_prova_externa_resumo SET (security_invoker = true);


-- ─── A lista branca da captação ───────────────────────────────────────────

-- prova_externa · perfil_do_candidato_externo (nome e categoria da prova, por
-- id: consultas.perfis_do_nome), buscar_candidatos_por_conquista (o nome
-- pedido, conferido contra o catálogo; e p.id, p.nome e p.categoria na
-- função da 0068) e provas_da_captacao (pela view do rodapé: p.nome e
-- p.categoria).
GRANT SELECT (id, nome, categoria)
    ON prova_externa TO sas_leitura;

-- candidato_externo · perfil_do_candidato_externo (o retrato e o funil do
-- perfil; nome_normalizado é filtro e criado_em é ordem) e a função da 0068
-- (c.id e c.nome_normalizado, a junção com a conquista). FORA: observacoes,
-- retrato_editado_a_mao e atualizado_em.
GRANT SELECT (id, nome, nome_normalizado, escola, cidade, uf, serie_referencia_min,
              serie_referencia_max, ano_referencia_serie, status_captacao, criado_em)
    ON candidato_externo TO sas_leitura;

-- conquista_externa · perfil_do_candidato_externo (o que a ficha de leitura
-- mostra, mais a faixa; candidato_id é filtro e ano, ordem), a função da 0068
-- (candidato_id, prova_id, ano, faixa, resultado, nivel_texto e as duas
-- colunas geradas do público, ano_conclusao_min/max) e a view do rodapé (id,
-- prova_id e ano). FORA: nome_informado, raspado_em e
-- serie_referencia_min/max.
GRANT SELECT (id, candidato_id, prova_id, ano, nivel_texto, resultado, faixa,
              escola_informada, cidade_informada, uf_informada, notas_por_materia,
              fonte_url, ano_conclusao_min, ano_conclusao_max)
    ON conquista_externa TO sas_leitura;

-- v_candidato_externo_por_nome · buscar_candidatos_externos (as 13 colunas de
-- consultas.COLUNAS_POR_NOME; ufs e status_captacao são filtro @>,
-- conquistas_total é filtro e ordem, nome_normalizado é busca e ordem) e
-- buscar_candidatos_por_conquista (a função da 0068 devolve as mesmas 13 e
-- filtra por ufs, status_captacao, conquistas_total e nome_normalizado). São
-- os conjuntos que a lista mostra; nenhuma coluna aqui é texto livre.
GRANT SELECT (nome_normalizado, nome, escolas, cidades, ufs, status_captacao,
              conquistas_total, provas_distintas, participacoes, perfis_no_grupo,
              ano_mais_recente, criado_em, atualizado_em)
    ON v_candidato_externo_por_nome TO sas_leitura;

-- v_prova_externa_resumo · provas_da_captacao (as cinco colunas, agregadas
-- das linhas de cima — SECURITY INVOKER desde o começo deste arquivo).
GRANT SELECT (nome, categoria, ano_min, ano_max, conquistas_total)
    ON v_prova_externa_resumo TO sas_leitura;

COMMIT;
