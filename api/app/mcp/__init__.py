"""O MCP da coordenação (docs/43 §5): a IA de FORA da escola lendo o SAS.

Processo próprio — `python -m app.mcp` —, com um PostgREST próprio
(`postgrest_mcp`) cujo papel anônimo é o `sas_mcp` das migrations 0071/0072.
Não divide o event loop da API nem as travas dela, e por isso NUNCA importa
`app.main` nem os routers: o guard de boot de lá exigiria segredos que este
processo não deve ter (JWT_SECRET_KEY, SCHEDULER_SECRET...).

⚠️ Este `__init__` fica vazio de propósito. A API importa `configuracao` e
`tokens` daqui (rotas de `/mcp/tokens`), e um import do SDK neste arquivo
puxaria o servidor MCP inteiro para dentro do processo da API.

  configuracao   ConfiguracaoMcp (env MCP_*) e o guard de boot do processo
  tokens         o token opaco: gerar, hash, conferir pela RPC
  emails_ia      o e-mail da conta de IA e o código de 6 dígitos que aprova a
                 conexão OAuth — puro, usado só pela API (decisão de 26/10)
  pseudonimo     nome de aluno → matrícula, fail-closed — OPCIONAL desde 26/10,
                 quando o nome real virou o padrão (LGPD, docs/43 §5.4)
  catalogo       as tools do registro com expor_no_mcp, no formato do SDK
  auditoria_mcp  uma linha em evento_auditoria por chamada de tool
  dados          o cliente PostgREST novo de cada operação e a sonda de
                 privilégio do boot (o PostgREST não pode ler usuario_coordenacao)
  servidor       o Server de baixo nível: tools, prompts, identidade, limite
  app            o Starlette: /mcp (Streamable HTTP, stateless) e /health
  __main__       uvicorn (1 processo) ou --stdio
"""
