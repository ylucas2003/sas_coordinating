# Olimpíadas internacionais — Física, Química e Biologia (mundiais e ibero-americanas)

IPhO, IChO, IBO e suas correspondentes ibero-americanas (OIbF, OIAQ, OIAB). Tentativa de abrir
(WebFetch/curl) as páginas de cada olimpíada nacional brasileira e suas correspondentes
internacionais/ibero-americanas.

Dois domínios se recusaram a abrir para ferramentas automatizadas: `sbfisica.org.br/v1` (certificado
TLS quebrado) e `butantan.gov.br` / `olimpiadasdebiologia.butantan.gov.br` (bloqueio Cloudflare 403 —
tentativas via WebFetch, curl com user-agent de navegador, proxy leitor jina.ai, e Chrome MCP, que
estava com uma instância travada por outra sessão e não pôde ser usado). Onde isso aconteceu, está
marcado explicitamente como não verificado por abertura direta, com a fonte alternativa que funcionou.

## Tabela

| Nome | Quando ocorre | Região | Link de resultados/aprovados (últimos anos) | Observação |
|---|---|---|---|---|
| **IPhO** — International Physics Olympiad | Tradicionalmente julho (varia com a sede; IPhO 2025 foi em Paris, França — mês exato não confirmado nas páginas abertas) | Internacional | [www1.fisica.org.br/olimpiada/2025 — "Quatro pratas e um Bronze em Paris na IPhO 2025"](https://www1.fisica.org.br/olimpiada/2025/index.php/15-soif/375-quatro-pratas-e-um-bronze-em-paris-na-ipho-2025) — **aberto e confirmado**: 5 alunos nomeados, 4 pratas + 1 bronze. O site usa uma pasta por ano (`www1.fisica.org.br/olimpiada/{ano}/`); confirmado via HTTP 200 que 2019–2025 existem, mas só o conteúdo completo de 2025 foi aberto | Seleção nacional: **OBF** (Olimpíada Brasileira de Física), organizada pela SBF; os 5 selecionados saem do **TBF** (Torneio Brasileiro de Física), etapa final do programa SOIF. **Não confundir com a OBFEP** (Olimpíada Brasileira de Física das Escolas Públicas) — é olimpíada distinta, só para rede pública, e não alimenta a equipe da IPhO. O domínio antigo `sbfisica.org.br/v1` tem certificado TLS quebrado e não abre em nenhuma ferramenta |
| **IChO** — International Chemistry Olympiad | Tradicionalmente julho (mês exato de edições recentes não confirmado nas páginas abertas) | Internacional | [obquimica.org/olimpiada/olimpiada-internacional-de-quimica](https://obquimica.org/olimpiada/olimpiada-internacional-de-quimica) — **aberto e confirmado**: existem PDFs de resultado só até 2013 e 2015–2021 (com lacuna em 2014); a "Galeria de Honra" da página está **vazia**, e nada de 2022 em diante aparece publicado | Seleção nacional: **OBQ** (Olimpíada Brasileira de Química), do Programa Nacional Olimpíadas de Química, hoje sob as Pró-Reitorias de Extensão da UFC/UFPI (antes ligado à USP/SBQ). A fase final elege 4 alunos que vão **simultaneamente** para IChO e OIAQ. Os posts anuais de resultado existem e abrem (ex.: [resultado-final-obq-2024](https://obquimica.org/noticias/resultado-final-obq-2024), [-2025](https://obquimica.org/noticias/resultado-final-obq-2025)), mas não trazem nomes/medalhas na própria página — só remetem a um PDF ou ao site oficial da IChO |
| **IBO** — International Biology Olympiad | Julho (IBO 2025: 20–27/jul, Quezon City, Filipinas — confirmado por busca, não por abertura direta) | Internacional | **Bloqueado (403 Cloudflare) em toda tentativa de abertura direta.** Portal oficial, existência confirmada só via índice de busca (não aberto): `olimpiadasdebiologia.butantan.gov.br`. Posts anuais de resultado ficam em `butantan.gov.br/butantan-educa/…` — inclusive um sobre a lista de classificados IBO+OIAB 2026 — mas nenhum pôde ser aberto para confirmar o conteúdo linha a linha | Seleção nacional: **OBB** (Olimpíada Brasileira de Biologia), organizada pelo **Instituto Butantan** desde 2017 (antes era a ANBio). Os 4 primeiros colocados da fase final vão para a IBO; os 4 seguintes, para a OIAB |
| **Olimpíada Ibero-americana de Física (OIbF)** | Setembro/outubro, varia por sede (ex.: 23–30/set/2023 na Costa Rica — confirmado; 20–28/out em Porto Rico, ano não confirmado) | Regional — ibero-americana | [www1.fisica.org.br/~oibf/home/resultados](https://www1.fisica.org.br/~oibf/home/resultados/index.html) — **aberto e confirmado**: hub com PDF de resultado de 26 edições, 1991 a 2021 (inclui a edição virtual de 2020). Para 2022–2025 os resultados saem como post individual em `www1.fisica.org.br/olimpiada/{ano}/…`; confirmado o [post da OIbF 2023](https://www1.fisica.org.br/olimpiada/2024/index.php/15-soif/333-brasil-conquista-3-ouros-e-1-prata-na-oibf-2023) (3 ouros + 1 prata, 4 alunos nomeados) | Mesma seleção da OBF/TBF: outros 4 alunos (distintos dos 5 da IPhO) representam o Brasil. Histórico forte — vários 1º lugares gerais |
| **Olimpíada Ibero-americana de Química (OIAQ)** | Outubro, varia por sede (ex.: 2–5/out/2021 em Teresina-PI — confirmado) | Regional — ibero-americana | [obquimica.org/olimpiada/olimpiada-ibero-americana-de-quimica](https://obquimica.org/olimpiada/olimpiada-ibero-americana-de-quimica) — **aberto e confirmado**: a "Galeria de Honra" e a seção de resultados desta olimpíada estão **literalmente vazias** ("ainda não possui registros" / "ainda não foram publicados"). Fonte alternativa aberta e confirmada: [cfq.org.br — XXV OIAQ](https://cfq.org.br/noticia/brasil-tem-quatro-medalhistas-na-xxv-olimpiada-ibero-americana-de-quimica/) (edição 2021, Teresina, 4 alunos nomeados) | Mesma seleção da OBQ: os mesmos 4 alunos do IChO. A página oficial brasileira existe mas está vazia — hoje a fonte prática é notícia avulsa (CFQ, agências) por edição, não um hub consolidado |
| **Olimpíada Ibero-americana de Biologia (OIAB)** | Agosto/setembro, varia por sede (2025: 13/set, Colômbia — confirmado; 2026: 30/ago–5/set, sediada no Brasil — confirmado) | Regional — ibero-americana | Mesmo bloqueio Cloudflare de `butantan.gov.br`. Fonte alternativa aberta e confirmada: [cfbio.gov.br — 18ª OIAB 2025](https://cfbio.gov.br/2025/09/18/estudantes-brasileiros-alcancam-resultado-historico-na-18a-olimpiada-iberoamericana-de-biologia-com-primeiro-lugar-e-quatro-medalhas/) (4 alunos nomeados, 2 ouros + 1 prata + Top Gold) | Mesma seleção da OBB: os 4 classificados em 5º–8º lugar da fase final (depois dos 4 da IBO). 2026 é a 3ª vez que o Brasil sedia a OIAB, no próprio Instituto Butantan |

## Notas gerais

- O hub `olimpiadascientificas.org/equipes-brasileiras/` existe e cobre IPhO, IChO, IBO e as três
  ibero-americanas, mas os links por ano visíveis iam só até ~2010–2012 — não é fonte atual confiável
  para 2019–2026.
- Em física e biologia, os 4 alunos ibero-americanos **não são os mesmos** que vão à olimpíada
  internacional (mundial) — são grupos diferentes saídos da mesma seleção nacional. Em química, os
  **mesmos** 4 alunos vão para IChO e OIAQ.
- Dois domínios oficiais recusaram acesso automatizado consistentemente: `sbfisica.org.br/v1` (TLS
  quebrado) e `butantan.gov.br`/`olimpiadasdebiologia.butantan.gov.br` (Cloudflare 403). Para IBO e
  OIAB, o conteúdo dessas páginas vem de trechos indexados por busca, não de abertura direta —
  recomenda-se conferir manualmente no navegador antes de usar como fonte definitiva.

## Fontes

- [OBF/2025 (graxaim.org)](https://app.graxaim.org/obf/2025/open_page/about_tbf)
- [Quatro pratas e um Bronze em Paris na IPhO 2025](https://www1.fisica.org.br/olimpiada/2025/index.php/15-soif/375-quatro-pratas-e-um-bronze-em-paris-na-ipho-2025)
- [Olimpíada Internacional de Física | SBF](https://www.sbfisica.org.br/v1/sbf/olimpiada-internacional-de-fisica/)
- [Olimpíada Brasileira de Física seleciona representantes — Agência FAPESP](https://agencia.fapesp.br/olimpiada-brasileira-de-fisica-seleciona-representantes-para-eventos-internacionais/275)
- [Olimpíada Brasileira de Química – Wikipédia](https://pt.wikipedia.org/wiki/Olimp%C3%ADada_Brasileira_de_Qu%C3%ADmica)
- [obquimica.org — Olimpíada Brasileira de Química](https://obquimica.org/olimpiada/olimpiada-brasileira-de-quimica)
- [obquimica.org — Olimpíada Internacional de Química](https://obquimica.org/olimpiada/olimpiada-internacional-de-quimica)
- [obquimica.org — Olimpíada Ibero-americana de Química](https://obquimica.org/olimpiada/olimpiada-ibero-americana-de-quimica)
- [Resultado Final OBQ 2024](https://obquimica.org/noticias/resultado-final-obq-2024)
- [Resultado Final OBQ 2025](https://obquimica.org/noticias/resultado-final-obq-2025)
- [CFQ — Brasil tem quatro medalhistas na XXV OIAQ](https://cfq.org.br/noticia/brasil-tem-quatro-medalhistas-na-xxv-olimpiada-ibero-americana-de-quimica/)
- [XXI Olimpíada Brasileira de Biologia 2025 | CEFET-MG](https://www.dcb.cefetmg.br/2025/02/14/xxi-olimpiada-brasileira-de-biologia-2025/)
- [CFBio — 18ª OIAB 2025, primeiro lugar e quatro medalhas](https://cfbio.gov.br/2025/09/18/estudantes-brasileiros-alcancam-resultado-historico-na-18a-olimpiada-iberoamericana-de-biologia-com-primeiro-lugar-e-quatro-medalhas/)
- [Olimpíada Brasileira de Biologia – Wikipédia](https://pt.wikipedia.org/wiki/Olimp%C3%ADada_Brasileira_de_Biologia)
- [Instituto Butantan divulga lista de classificados IBO/OIAB 2026](https://butantan.gov.br/butantan-educa/instituto-butantan-divulga-lista-de-estudantes-classificados-para-olimpiada-internacional-e-iberoamericana-de-biologia-de-2026)
- [Resultados | Olimpíada Iberoamericana de Física](https://www1.fisica.org.br/~oibf/home/resultados/index.html)
- [Brasil Conquista 3 Ouros e 1 Prata na OIbF 2023](https://www1.fisica.org.br/olimpiada/2024/index.php/15-soif/333-brasil-conquista-3-ouros-e-1-prata-na-oibf-2023)
- [Resultado da Olimpíada Ibero Americana de Física 2018 | SBF](https://www.sbfisica.org.br/v1/olimpiada/2018/index.php/2-uncategorised/180-resultado-da-olimpiada-ibero-americana-de-fisica-2018.html)
