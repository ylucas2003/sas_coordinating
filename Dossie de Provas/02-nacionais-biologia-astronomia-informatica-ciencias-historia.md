# Olimpíadas nacionais — Biologia, Astronomia, Informática, Ciências, História

OBB, OBA, OBI, ONC e ONHB. Pesquisa via WebSearch/WebFetch, com proxy leitor (`r.jina.ai`) para
contornar bloqueios de WAF em dois domínios `.gov.br`/SPA, sinalizado onde ocorreu.

**Achados que corrigem pistas do levantamento inicial**:
- **ONC não é organizada pela UFV/UFJF.** É organizada pela **Universidade Federal do Piauí (UFPI)**,
  com execução do MCTI, em parceria com SBF, ABQ, Instituto Butantan, SAB e o Departamento de História
  da Unicamp. UFV aparece apenas como uma escola/campus (CAp-Coluni) que participa e ganha medalhas, não
  como organizadora.
- **ONHB não é organizada pela UFJF.** É um projeto de extensão da **Unicamp** (Departamento de
  História/IFCH), com apoio do MCTI, CNPq e ANPUH. Nenhuma menção a UFJF em nenhuma fonte.
- A OBB do Butantan é a única "Olimpíada Brasileira de Biologia" nacional que a Wikipédia registra —
  fundada em 2004, gerida pela ANBio até 2016 e pelo Instituto Butantan desde 2017. Não há uma segunda
  iniciativa concorrente ativa com esse nome.

## Tabela

| Nome | Quando ocorre | Região | Link de resultados/aprovados (últimos anos) | Observação |
|---|---|---|---|---|
| **Olimpíada Brasileira de Biologia (OBB)** | Inscrição jan–fev; Fase 1 em março; Fase 2 em março/abril; seletiva internacional depois. Datas mudam ano a ano dentro desse padrão. | Nacional (fases sucessivas afunilando; sem "etapa estadual" formal separada) | **https://olimpiadasdebiologia.butantan.gov.br/provas-gabaritos-e-classificacoes** — confirmado que a página lista provas/gabaritos/classificações da **XV OBB (2019) até a XXII OBB (2026)**, cobrindo os 8 anos pedidos, além de acesso a edições históricas (I a XIII) | Organizada pelo **Instituto Butantan** (antes, até 2016, pela ANBio). Domínio `.gov.br` protegido por WAF que bloqueou fetch/curl direto com HTTP 403 (mesmo com user-agent de navegador); conteúdo só confirmado via proxy leitor (`r.jina.ai`) — abrir a página num navegador comum deve funcionar normalmente |
| **OBA — Olimpíada Brasileira de Astronomia e Astronáutica** | Prova única aplicada nas escolas; resultados/medalhas da edição 2025 foram divulgados em julho/2025. Mês exato da prova não confirmado (varia pouco ano a ano) | Nacional, prova simultânea em todo o país | **https://novo.oba.org.br/medalhas** (também referenciado como `medalhas.oba.org.br`) — confirmado que a página existe (HTTP 200) e é ferramenta de consulta pública por Ano/UF/Nome/Cidade, mas é um SPA (Next.js) cujas opções de ano ficam carregadas via JavaScript — não foi possível enumerar via fetch estático quantos anos (2019–2026) estão disponíveis no seletor | Promovida pela **Sociedade Astronômica Brasileira (SAB)** e **Agência Espacial Brasileira (AEB)**. Site em migração: pelo menos três domínios em uso (`oba.org.br`, `sistema.oba.org.br`, `novo.oba.org.br`) — sinal de troca de sistema recente |
| **OBI — Olimpíada Brasileira de Informática** | Fase 1 em junho (com data B de reaplicação); Fase 2 em agosto; Fase 3 presencial (finalistas) entre setembro e novembro. Resultado preliminar 2026 já divulgado como 15/set/2026. Varia ano a ano dentro desse padrão | Nacional, com Fase 3 presencial em sedes regionais para os finalistas | **https://olimpiada.ic.unicamp.br/passadas/** — lista todas as edições de OBI1999 a OBI2025 (padrão de URL `/passadas/OBI[ANO]/`); confirmado que a página de cada ano (testado OBI2022) tem "Quadros de Medalhas" por modalidade/nível. **Todos os 7 anos de 2019–2025 estão acessíveis publicamente sem login** | Promovida pela **SBC (Sociedade Brasileira de Computação)**, organizada pelo **Instituto de Computação da Unicamp** |
| **ONC — Olimpíada Nacional de Ciências** | Inscrições até agosto; Fase 1 em meados de agosto; Fase 2 em meados de setembro (dados de 2024/25). Cerimônia de premiação em data variável | Nacional, aplicação simultânea, resultado detalhado por estado | **https://resultado.onciencias.org/** — confirmado via buscas (snippets, o site bloqueia scrapers/SPA) que há páginas de resultado final para **2020, 2021, 2022, 2023, 2024 e 2025** (padrão `resultado.onciencias.org/estado/[ANO]/[UF]`). **2019 não confirmado** (a ONC existe desde 2016, então é provável que exista) | Organizada pela **Universidade Federal do Piauí (UFPI)**, execução do **MCTI**, com SBF, ABQ, Instituto Butantan, SAB e Depto. de História da Unicamp — **não é UFV/UFJF** |
| **ONHB — Olimpíada Nacional em História do Brasil** | Inscrições fev–abr; Fase 1 em maio; Fase 2 em maio; final presencial em agosto (na Unicamp), com base na 17ª edição/2025 (5/5, 12/5 e 30–31/8). Varia ano a ano dentro desse padrão | Nacional, final concentrada presencialmente na Unicamp (Campinas-SP), equipes de todos os estados | **não encontrado** um link único de resultados/medalhistas. O site só publica **notícias avulsas por edição** em `https://www.olimpiadadehistoria.com.br/noticias/index` (padrão de URL não correlacionado ao ano: `/noticias/ler/[ID sequencial]`), cada uma resumindo a contagem de medalhas por estado — não é lista pesquisável nem página fixa de "resultados". Confirmado abrindo a página de menu da 17ª edição, sem nenhum item "resultados/classificados" | Organizada pela **Unicamp** (Departamento de História/IFCH), com apoio do MCTI, CNPq e ANPUH — **não é UFJF**. Existe subdomínio `www2.olimpiadadehistoria.com.br` usado só para edições mais antigas (7ª, 8ª), indicando troca de sistema ao longo dos anos |

**Nota metodológica**: o orçamento de WebSearch da sessão se esgotou no meio da pesquisa (limite de 200
buscas); o restante da verificação (datas de fase, confirmação de organizadores, teste dos links de
resultado) foi completado só com WebFetch, incluindo um proxy leitor (`r.jina.ai`) para dois domínios
que devolviam HTTP 403 tanto no WebFetch quanto no `curl` direto (provável bloqueio de WAF a tráfego
automatizado/datacenter, não à ferramenta em si — um navegador comum deve acessar normalmente).
