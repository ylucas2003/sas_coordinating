# Colégios militares e concursos de nível médio

Dez itens pesquisados: 3 colégios militares (admissão de adolescentes) + 7 concursos que pedem ensino
médio completo.

**Resumo dos bloqueios encontrados**: os sites do Exército (`eb.mil.br`) são acessíveis e publicam pouco
histórico — normalmente só o edital do ciclo vigente e, no máximo, uma página de "provas anteriores" com
PDFs de provas antigas, **não** de listas de aprovados. Os sites da Marinha (`marinha.mil.br` e
`inscricao.marinha.mil.br`) e da Aeronáutica (`fab.mil.br`, `afa.aer.mil.br`, `eear.aer.mil.br`) ficam
atrás de proteção anti-bot (Cloudflare) ou, no caso de dois domínios da FAB, simplesmente não aceitaram
conexão a partir da pesquisa — não foi possível navegar neles diretamente, só via resultados de busca já
indexados. Nenhuma dessas instituições parece manter uma página única e estável com os aprovados dos
últimos 7 anos: os resultados saem como PDFs avulsos, por edição, com nomes de arquivo que mudam a cada
ano, e frequentemente saem do ar quando o ciclo seguinte é publicado.

## Colégios militares (admissão de adolescentes)

| Nome | Quando ocorre | Região | Link de resultados/aprovados (últimos anos) | Observação |
|---|---|---|---|---|
| **Colégio Militar** (Exército Brasileiro) — Concurso de Admissão ao CM (6º ano EF / 1º ano EM) | Edital ~jul; inscrições ago–set; prova (Exame Intelectual) meados de out; resultado final dez a mar do ano seguinte. Varia por unidade/ano | Nacional — 15 unidades: Belém, Belo Horizonte, Brasília, Campo Grande, Curitiba, Fortaleza, Juiz de Fora, Manaus, Porto Alegre, Recife, Rio de Janeiro, Salvador, Santa Maria, São Paulo e Vila Militar (RJ) | **Não encontrado** um índice único. Cada unidade publica no próprio site (ex. `cmr.eb.mil.br`, `cmb.eb.mil.br`, `cmcg.eb.mil.br`...), geralmente só o ciclo vigente. Ponto de partida real: [www.depa.eb.mil.br](https://www.depa.eb.mil.br/) (Diretoria de Educação Preparatória e Assistencial), que lista as 15 unidades e seus sites | Não existe portal central "Sistema Colégio Militar do Brasil" — é nome informal do conjunto, sem domínio próprio (`sistemacolegiomilitar.eb.mil.br` não existe). Testados CMR e CMB: cada um guarda no máximo o edital do ciclo atual e às vezes o do ciclo anterior, não 7 anos |
| **Colégio Naval** (Marinha, Angra dos Reis-RJ) — CPACN | Inscrições tipicamente mar–mai; prova escrita ~ago; resultado final ~dez | Sede em Angra dos Reis-RJ; provas aplicadas em vários polos pelo país (abrangência nacional na aplicação) | PDFs avulsos por ano em `inscricao.marinha.mil.br/marinha/`, ex.: [ResFinal-CPACN2024.pdf](https://www.inscricao.marinha.mil.br/marinha/ResFinal-CPACN2024.pdf?id_file=8524), [ResFinal-CPACN-2025.pdf](https://www.inscricao.marinha.mil.br/marinha/ResFinal-CPACN-2025.pdf?id_file=9225). Página do concurso (muda de `id_concurso` a cada edição): [index_concursos.jsp?id_concurso=483](https://www.inscricao.marinha.mil.br/marinha/index_concursos.jsp?id_concurso=483) | Domínio protegido por Cloudflare — não foi possível abrir por automação, só via cache de busca. Não há página-índice listando os 7 anos; cada edição tem uma URL de resultado com nome de arquivo diferente |
| **EPCAR** — Escola Preparatória de Cadetes do Ar (Aeronáutica, Barbacena-MG) | Edital ~jan–mar; inscrições abrem em mar (ex. 2026: inscrições a partir de 06/03); prova no 1º semestre — varia | Sede em Barbacena-MG; provas aplicadas nacionalmente | **Não encontrado** arquivo histórico. Páginas oficiais localizadas via busca: [fab.mil.br/admissao/militares-de-carreira/epcar/](https://www.fab.mil.br/admissao/militares-de-carreira/epcar/) e [fab.mil.br/ingresso/cpcar/cpcar2026.html](https://www.fab.mil.br/ingresso/cpcar/cpcar2026.html) (nome do arquivo muda a cada ano: `cpcar2026.html`) | O antigo domínio `epcar.aer.mil.br` não existe mais (404/NXDOMAIN) — a FAB migrou tudo para `fab.mil.br`. Esse domínio bloqueia acesso automatizado (403 mesmo com ferramentas de fetch), então não foi possível confirmar se há seção de anos anteriores |

## Concursos de nível médio (pedem ensino médio completo)

| Nome | Quando ocorre | Região | Link de resultados/aprovados (últimos anos) | Observação |
|---|---|---|---|---|
| **EsPCEx** — Escola Preparatória de Cadetes do Exército | Edital ~fev–mar; inscrições abr–mai; prova objetiva+redação ~set; resultado da fase escrita ~dez | Nacional (escola fica em Campinas-SP; provas aplicadas em todo o país) | **Não há arquivo consolidado.** A única página histórica oficial, [espcex.eb.mil.br/.../provas-anteriores](https://espcex.eb.mil.br/index.php/concurso/provas-anteriores), só tem PDFs de **provas** antigas (1996–2026), não listas de aprovados. Resultados de anos específicos existem como PDFs soltos e não indexados centralmente, ex.: [LISTA_APROVADOS_2024.pdf](https://espcex.eb.mil.br/images/concurso/2024_publConcurso/classificacao/LISTA_APROVADOS_2024.pdf) (2024) e [RESULTADO CONCURSO 2021 PUBLICADO SITE.pdf](https://espcex.eb.mil.br/downloads/RESULTADO%20CONCURSO%202021%20PUBLICADO%20SITE.pdf) (2021) | Confirmado diretamente (curl) que o menu do site só tem "Edital do Concurso [ano atual]" e "Provas Anteriores" — nenhuma seção "Resultados anteriores" |
| **AFA** — Academia da Força Aérea (Pirassununga-SP) | Edital ~fev; inscrições mar–abr; prova geralmente no 1º semestre — não confirmado com precisão nesta pesquisa | Nacional (sede em Pirassununga-SP; provas em todo o país) | **Não encontrado.** Domínio oficial é `www.afa.aer.mil.br`, mas não foi possível carregar nenhuma página dele nesta sessão (conexão recusada) para localizar uma seção de resultados | O domínio resolve no DNS mas recusou conexão em todas as tentativas (curl e fetch) — pode ser bloqueio geográfico/anti-bot do servidor. `fab.mil.br` também bloqueou (403) todas as tentativas de acesso automatizado |
| **Escola Naval** (Marinha, Rio de Janeiro) — CPAEN | Inscrições ~mar–mai; prova escrita ~ago; resultado final ~dez | Sede no Rio de Janeiro (Urca); provas aplicadas nacionalmente | Mesmo padrão do Colégio Naval: PDFs avulsos em `inscricao.marinha.mil.br/marinha/`, ex.: resultado definitivo CPAEN-2025 (`ResFinal-CPAEN2025.pdf`), CPAEN-2021, CPAEN-2020 — todos encontrados via busca, não navegáveis diretamente. Página do concurso: [index_concursos.jsp?id_concurso=436](https://www.inscricao.marinha.mil.br/marinha/index_concursos.jsp?id_concurso=436) | Mesmo bloqueio Cloudflare do Colégio Naval; sem índice único dos 7 anos |
| **EFOMM** — Escola de Formação de Oficiais da Marinha Mercante | Inscrições ~mai–jun; provas ~ago; 1ª classificação ~set | Formação dividida entre CIAGA (Rio de Janeiro) e CIABA (Belém-PA); provas aplicadas nacionalmente | Páginas oficiais (encontradas via busca, conteúdo não aberto): [marinha.mil.br/ciaga/efommadmissao](https://www.marinha.mil.br/ciaga/efommadmissao) e [marinha.mil.br/ciaga/node/2516](https://www.marinha.mil.br/ciaga/node/2516) (Processo Seletivo EFOMM 2027); lado Belém: [marinha.mil.br/ciaba/node/206](https://www.marinha.mil.br/ciaba/node/206) | Não encontrada lista de aprovados histórica — essas páginas parecem tratar do ciclo vigente. `marinha.mil.br` bloqueou acesso automatizado direto |
| **ESA** — Escola de Sargentos das Armas (Três Corações-MG) | Edital ~abr; inscrições mai–jun; prova ~ago; resultado ~dez | Sede em Três Corações-MG; provas aplicadas nacionalmente | **Não encontrado.** O "Portal do Candidato" oficial, [concursocfgs.esa.eb.mil.br](https://concursocfgs.esa.eb.mil.br/), é um app que não foi possível inspecionar por automação (carrega via JavaScript). O site institucional [esa.eb.mil.br/.../concurso.html](https://esa.eb.mil.br/index.php/pt/concurso.html) só lista edital vigente, etapas e "provas anteriores" (sem resultados) | Confirmado via curl que o menu do site institucional não tem seção de resultados/aprovados de anos anteriores |
| **EEAR** — Escola de Especialistas de Aeronáutica (Guaratinguetá-SP) | Ocorre **duas vezes por ano** (concursos "1º/ano" e "2º/ano"); janelas de inscrição variam a cada edição | Sede em Guaratinguetá-SP; provas aplicadas nacionalmente | **Não encontrado.** Nenhuma URL oficial confiável (`.aer.mil.br` ou `fab.mil.br`) com lista de aprovados localizada — só páginas de terceiros (cursinhos) | Vale destacar: como o concurso roda duas vezes ao ano, "os últimos 7 anos" significam até ~14 editais — reforça a chance de não haver arquivo histórico consolidado |
| **Fuzileiro Naval** (Marinha, praças) — C-FSD-FN | Parece rodar em "turmas" (I e II) por ano; janelas de inscrição variam | Formação no Rio de Janeiro (CIAMPA) e Brasília (CIAB); provas aplicadas nacionalmente | Portal específico (subdomínio próprio, diferente do usado para Colégio/Escola Naval): [inscricao.marinha.mil.br/marinhafn/](https://www.inscricao.marinha.mil.br/marinhafn/index_concursos.jsp?id_concurso=84) — encontradas páginas de concurso para 2022, 2023, 2024, 2026 e 2027, cada uma com seu `id_concurso`, mas não uma lista de aprovados consolidada | Mesmo bloqueio Cloudflare; resultados devem existir como PDF por turma/edição, padrão de nome não confirmado |

**Nota geral sobre confiabilidade dos links**: toda URL acima veio de um resultado de busca real ou de
uma página aberta diretamente (via `curl`) — nenhuma foi inventada. Onde nada confiável foi encontrado,
está escrito "não encontrado" em vez de chutar. Para os itens da Aeronáutica (AFA, EPCAR, EEAR) a
pesquisa ficou mais fraca porque `fab.mil.br` bloqueou todo acesso automatizado (403) e os domínios
`afa.aer.mil.br`/`eear.aer.mil.br` recusaram conexão nesta sessão — vale repetir a busca manualmente num
navegador comum, que não sofre esse bloqueio.

## Fontes

- [Colégio Militar 2026: edital do processo seletivo divulgado](https://portal.estrategia.com/militares/escolas/exercito/colegios-militares/colegio-militar-2026-edital-do-processo-seletivo-divulgado/)
- [DEPA — Diretoria de Educação Preparatória e Assistencial](https://www.depa.eb.mil.br/)
- [Concurso Público de Admissão ao Colégio Naval (CPACN)](https://www.inscricao.marinha.mil.br/marinha/index_concursos.jsp?id_concurso=483)
- [Marinha do Brasil - Colégio Naval (hotsite)](https://concursos.marinha.mil.br/colegio-naval.html)
- [ResFinal-CPACN2024.pdf](https://www.inscricao.marinha.mil.br/marinha/ResFinal-CPACN2024.pdf?id_file=8524)
- [Resultado Final CPACN-2025](https://www.inscricao.marinha.mil.br/marinha/ResFinal-CPACN-2025.pdf?id_file=9225)
- [Epcar – Força Aérea Brasileira](https://www.fab.mil.br/admissao/militares-de-carreira/epcar/)
- [Ingresso EPCAR 2026](https://www.fab.mil.br/ingresso/cpcar/cpcar2026.html)
- [EsPCEx — Provas Anteriores](https://espcex.eb.mil.br/index.php/concurso/provas-anteriores)
- [Lista de aprovados EsPCEx 2024](https://espcex.eb.mil.br/images/concurso/2024_publConcurso/classificacao/LISTA_APROVADOS_2024.pdf)
- [Resultado Concurso EsPCEx 2021](https://espcex.eb.mil.br/downloads/RESULTADO%20CONCURSO%202021%20PUBLICADO%20SITE.pdf)
- [AFA - Academia da Força Aérea](http://www.afa.aer.mil.br/)
- [Concurso Público de Admissão à Escola Naval (CPAEN)](https://www.inscricao.marinha.mil.br/marinha/index_concursos.jsp?id_concurso=436)
- [EFOMM - Admissão | CIAGA](https://www.marinha.mil.br/ciaga/efommadmissao)
- [PROCESSO SELETIVO EFOMM 2027 | CIAGA](https://www.marinha.mil.br/ciaga/node/2516)
- [EFOMM Admissão | CIABA](https://www.marinha.mil.br/ciaba/node/206)
- [ESA - Portal do Candidato CFGS](https://concursocfgs.esa.eb.mil.br/)
- [ESA - Concurso (institucional)](https://esa.eb.mil.br/index.php/pt/concurso.html)
- [Concurso EEAR: calendário, vagas e etapas](https://militares.estrategia.com/portal/escolas-militares/fab/eear/concurso-eear/)
- [Marinha prorroga inscrições — Fuzileiros Navais](https://www.agencia.marinha.mil.br/vem-pra-marinha/marinha-prorroga-o-periodo-de-inscricoes-para-o-concurso-de-fuzileiros-navais)
- [Concurso C-FSG-MU-CFN](https://www.inscricao.marinha.mil.br/marinhafn/index_concursos.jsp?id_concurso=84)
