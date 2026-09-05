// O inventário da área do aluno, legível por máquina.
//
// Este arquivo é a fonte da verdade de três coisas ao mesmo tempo, e é por isso
// que ele existe em vez de uma tabela num `.md`:
//
//   1. `docs/30-estado-da-implementacao.md` é GERADO daqui
//      (`npm run inventario`), e um teste falha se os dois divergirem. Um
//      inventário escrito à mão envelhece em silêncio.
//   2. A tarja MOCK lê o estado daqui (`pecas/TarjaFonte.tsx`) — e desde
//      04/09 ela aparece TAMBÉM em produção, para o aluno (docs/35 §10). A
//      tarja não pode mentir sobre o inventário porque é a mesma linha; o que
//      mudou é que agora a linha errada mente para 900 pessoas, não para quem
//      está com o `npm run dev` aberto.
//   3. `costura.test.ts` exige que todo hook exportado pelo `index.ts` tenha
//      entrada aqui — fonte nova sem registro não compila o teste.
//
// ⚠️ São TRÊS estados, não dois, e a distinção é o ponto do arquivo:
// desmockar um `'sem-rota'` é escrever uma rota curta sobre dado que o servidor
// já tem; desmockar um `'mock'` é inventar produto. Misturar os dois esconde a
// lista de tarefas mais barata do projeto.

export type EstadoFonte = 'real' | 'sem-rota' | 'mock';

export interface Fonte {
  chave: string;
  estado: EstadoFonte;
  /** Onde o desenho dela está documentado. */
  doc: string;
  /** A rota que a desmockaria. Vazio quando é 'real'. */
  rotaFutura?: string;
  /** Só para 'sem-rota': onde o dado já está no servidor. */
  origemDoDado?: string;

  // ── Campos do inventário, além do mínimo ───────────────────────────────

  /** Uma linha dizendo o que a fonte é. Vira a primeira coluna do doc. */
  descricao: string;
  /** Em que telas ela aparece. Coluna obrigatória da tabela 1. */
  telas: string[];
  /**
   * Esforço para desmockar, e é o que ordena a tabela 2 — de propósito, porque
   * essa tabela é uma lista de tarefas, não um relatório.
   */
  esforco?: 'P' | 'M' | 'G';
  /** Do que a fonte depende para existir. Coluna obrigatória da tabela 3. */
  depende?: string;
  /** O que o próximo a mexer precisa saber e não deduz do resto. */
  observacao?: string;
}

export const FONTES: Fonte[] = [
  // ─── REAL · conta e perfil ─────────────────────────────────────────────
  {
    chave: 'aluno',
    estado: 'real',
    descricao: 'Nome, turma, e-mail e foto do aluno logado',
    doc: 'api/app/routes/me.py',
    rotaFutura: 'GET /me',
    telas: ['casco', 'Jornada'],
  },
  {
    chave: 'fotoDePerfil',
    estado: 'real',
    descricao: 'Foto de perfil do aluno, por rota autenticada',
    doc: 'api/app/routes/foto_perfil.py',
    rotaFutura: 'GET/PUT/DELETE /me/foto',
    telas: ['casco'],
  },

  {
    chave: 'cantina',
    estado: 'real',
    descricao: 'Cardápios publicados que servem o aluno, o pedido dele e o prazo de cada dia',
    doc: 'docs/38-plano-cantina.md',
    rotaFutura: 'GET/PUT/DELETE /me/cantina',
    telas: ['Hoje', 'Cantina'],
    observacao:
      'Só existe para quem tem `direito_refeicao_aluno` — o card em Hoje se apaga sozinho para '
      + 'os outros ~800 alunos. Traz TODOS os dias publicados de hoje em diante, com teto de 30 '
      + 'dias (docs/38 §8.0.6). É a única fonte da área do aluno que revalida sozinha: '
      + '`refetchOnWindowFocus` ligado contra o default do app, mais polling de 60 s que se '
      + 'autodesliga — o dado muda porque OUTRA pessoa publicou (docs/38 §9).',
  },

  // ─── REAL · provas ─────────────────────────────────────────────────────
  {
    chave: 'simulados',
    estado: 'real',
    descricao: 'Simulados do aluno com nota, delta contra o próprio padrão e média da turma',
    doc: 'api/app/routes/me.py',
    rotaFutura: 'GET /me/simulados',
    telas: ['Hoje', 'Provas', 'Jornada'],
    observacao:
      'Filtra `presente = true` POR DEFAULT e descarta a falta; `?incluirFaltas=true` traz a ausência junto, e é o que alimenta `presencaNosSimulados`. O default não mudou de propósito: Hoje, Provas e Jornada calculam média e delta sobre esta lista, e ligar a falta para todo mundo mudaria número em tela sem ninguém ter pedido.',
  },
  {
    chave: 'simulado',
    estado: 'real',
    descricao: 'Ficha de um simulado: posição, percentil e comparação com grupos',
    doc: 'api/app/routes/me.py',
    rotaFutura: 'GET /me/simulado/{id}',
    telas: ['Hoje', 'Provas', 'Ficha do simulado'],
  },
  {
    chave: 'questoesDoSimulado',
    estado: 'real',
    descricao: 'Resultado questão a questão: certas, erradas e em branco',
    doc: 'api/app/routes/me.py',
    rotaFutura: 'GET /me/simulado/{id}/questoes',
    telas: ['Ficha do simulado'],
  },
  {
    chave: 'evolucao',
    estado: 'real',
    descricao: 'Evolução por matéria ao longo dos ciclos, aluno contra turma',
    doc: 'api/app/routes/me.py',
    rotaFutura: 'GET /me/evolucao',
    telas: ['Hoje', 'Provas', 'Jornada'],
  },
  {
    chave: 'trajetoria',
    estado: 'real',
    descricao: 'Todas as notas do aluno em ordem cronológica, já em escala 0–10',
    doc: 'docs/29 §A.5',
    rotaFutura: 'GET /me/trajetoria',
    telas: ['Jornada'],
    observacao: 'Rota pronta e sem tela até agora — docs/29 §A.5.',
  },
  {
    chave: 'heatmap',
    estado: 'real',
    descricao: 'Matriz matéria × simulado para o mapa de calor',
    doc: 'docs/29 §A.5',
    rotaFutura: 'GET /me/heatmap',
    telas: ['Provas'],
    observacao: 'Rota pronta e sem tela até agora — docs/29 §A.5.',
  },
  {
    chave: 'insight',
    estado: 'real',
    descricao: 'Bullets de IA sobre o ciclo mais recente',
    doc: 'api/app/routes/me.py',
    rotaFutura: 'GET /me/insight',
    telas: ['Hoje'],
  },

  // ─── REAL · banco de questões ──────────────────────────────────────────
  {
    chave: 'questoesDoBanco',
    estado: 'real',
    descricao: 'Página filtrada do acervo ITA·IME — a única rota paginada do projeto',
    doc: 'docs/28 §1',
    rotaFutura: 'GET /banco/questoes?…&colecao',
    telas: ['Banco', 'Questão em tela cheia', 'Sessão de treino'],
    observacao:
      'Filtrar por tópico exige matéria: a rota devolve 400 sem ela, e a folha de filtros impede a combinação. Em 02/09 ganhou `colecao=recentes|arquivo`, traduzida para `extraido_por` na camada de consulta — o aluno e a URL não precisam do nome da coluna. O Arquivo é a página INTEIRA do caderno (0033) e o cartão de lá leva tarja dizendo qual número procurar.',
  },
  {
    chave: 'questaoDoBanco',
    estado: 'real',
    descricao: 'Uma questão por id legível (`ita_2019_fase1_q01`)',
    doc: 'docs/28 §1',
    rotaFutura: 'GET /banco/questoes/{id}',
    telas: ['Questão em tela cheia'],
  },
  {
    chave: 'taxonomia',
    estado: 'real',
    descricao: 'Árvore bloco → tópico do edital, com contagem em cada nível',
    doc: 'docs/28 §1',
    rotaFutura: 'GET /banco/taxonomia',
    telas: ['Estudar (folha de filtros)'],
  },
  {
    chave: 'estatisticasDoBanco',
    estado: 'real',
    descricao: 'Recorrência bruta de cada tópico, por ano, fase e vestibular',
    doc: 'docs/28 §5',
    rotaFutura: 'GET /banco/estatisticas?materia&vestibular&fase',
    telas: ['Estatísticas (ranking, mapa do edital, ficha do assunto)'],
    observacao:
      'Ganhou tela em 02/09 e virou a espinha da aba Estatísticas. `questoesPorAno` (denominador de "% da prova") e o filtro `fase` entraram junto: os dois estreitam a resposta INTEIRA, e é isso que mantém numerador e denominador no mesmo recorte. A ficha faz DUAS chamadas, uma por vestibular — `porVestibular` é agregado e não tem quebra por ano —, e as duas falham independentemente: série ausente é declarada na tela, nunca desenhada como zero. Nunca pagina, de propósito.',
  },
  {
    chave: 'listas',
    estado: 'real',
    descricao: 'Listas de questões montadas pelo aluno — as 5 rotas',
    doc: 'docs/28 §1',
    rotaFutura: 'GET/POST/PATCH/DELETE /banco/listas…',
    telas: ['Minhas listas', 'Uma lista', 'Questão em tela cheia'],
  },
  {
    chave: 'estudo',
    estado: 'real',
    descricao: 'Resolvida, anotação e a resposta do treino, por aluno e questão',
    doc: 'docs/28 §1',
    rotaFutura: 'GET/PUT /banco/estudo',
    telas: ['Banco', 'Questão em tela cheia', 'Sessão de treino', 'Meu progresso'],
    observacao:
      '⚠️ `resolvida` e `acertou` NÃO são a mesma coisa e não se somam: a primeira é auto-declarada e pode existir sem resposta nenhuma; a segunda é conferida contra o gabarito, no servidor (0042). Ausência de linha = questão não tocada, que é a maioria.',
  },
  {
    chave: 'progressoDoBanco',
    estado: 'real',
    descricao: 'Quanto do acervo o aluno marcou como feito — por matéria, por assunto e por ano',
    doc: 'este handoff · api/app/banco/progresso.py',
    rotaFutura: 'GET /banco/progresso',
    telas: ['Meu progresso', 'Estudar (o subtítulo dos três campos)'],
    observacao:
      'Agrega no servidor de propósito: `GET /banco/estudo` devolve as linhas cruas, sem atributo de questão, e montar a tela com ela obrigaria o celular a baixar as ~2.700 questões para cruzar no navegador. Devolve SEMPRE o par (feitas, total) — contagem sem denominador é bug de produto. Usa `get_current_aluno`: é dado pessoal de menor, e o id sai do token.',
  },
  {
    chave: 'origemDaResolucao',
    estado: 'real',
    descricao: 'Se a resolução é do professor do Ari ou foi gerada por LLM no pipeline',
    doc: 'docs/29 §D.1',
    rotaFutura: 'resolucaoOrigem em GET /banco/questoes',
    telas: ['Questão em tela cheia', 'Sessão de treino'],
    observacao:
      'O prompt de implementação a listava como sem-rota; o campo JÁ vem no schema (`schemas/banco.py`), então está ligada. O aluno lendo resolução de IA achando que é do professor é o achado mais desconfortável de docs/29 — a tela é obrigada a marcar.',
  },
  {
    chave: 'missaoDoDia',
    estado: 'real',
    descricao: 'O assunto do dia com 10 questões — o herói da aba Hoje, igual para toda a turma',
    doc: 'docs/35 §9 · api/app/banco/missao.py',
    rotaFutura: 'GET /missao/hoje',
    telas: ['Hoje', 'Sessão de treino'],
    observacao:
      'Deixou de ser mock em 04/09. O fixture pareava o código `7.2` com o nome "Termodinâmica", e na taxonomia de Física 7.2 é "Ondas e Acústica": o cartão lia a etiqueta e o treino lia o endereço, e como o endereço existia nada quebrava — só mentia. Agora nome e código saem da mesma linha de `topico_taxonomia`. O sorteio é determinístico pela data em America/Fortaleza (em UTC viraria às 21h, para todo mundo junto) e só entra tópico com 10+ questões OBJETIVAS: o `totalQuestoes` da taxonomia conta dissertativa, que a fila de treino descarta. Saiu do Sprint 6 porque "o mesmo desafio para todos" derruba a personalização que dependia de `acertoPorAssunto`.',
  },
  {
    chave: 'conversaTioLeo',
    estado: 'real',
    descricao: 'Threads, streaming SSE e as 6 tools do aluno',
    doc: 'docs/27 §2',
    rotaFutura: 'GET/POST /chat/threads…',
    telas: ['Tio Léo'],
  },
  // A entrada do ALUNO é só o SSO do Canvas desde 04/09 (docs/35 §11.5): a
  // matrícula + senha e o `/auth/primeiro-acesso` saíram, e `POST /auth/login`
  // recusa `tipo == "aluno"` (routes/auth.py). Fica na linha porque a tela de
  // Login continua sendo uma só — o outro lado dela é a coordenação.
  {
    chave: 'autenticacao',
    estado: 'real',
    descricao: 'SSO do Canvas para o aluno — a coordenação entra por senha, na mesma tela',
    doc: 'api/app/routes/auth_canvas.py',
    rotaFutura: 'GET /auth/canvas/iniciar · /auth/canvas/callback · POST /auth/login (coordenação)',
    telas: ['Login'],
  },

  // ─── SEM-ROTA · o servidor já sabe a resposta ──────────────────────────
  {
    chave: 'presencaNosSimulados',
    estado: 'real',
    descricao: 'Os simulados em que o aluno faltou — os quadrados vazados da corrente',
    doc: 'docs/36 §2.1',
    rotaFutura: 'GET /me/simulados?incluirFaltas=true',
    telas: ['Hoje', 'Jornada'],
    observacao:
      '⚠️ A regra de QUEM pode ser chamado de falta é o produto desta fonte, não o filtro. Medindo em 05/09: 58,7% das notas são `presente = false` e 440 alunos de 1.229 têm 100% de falta — o número bruto mistura ausência com "esta prova nunca foi minha". Vale falta só com matrícula ativa e só a partir de `matricula_turma.ativo_desde` (docs/36 §1.1). A trilha NÃO entra: `INDEFINIDA` são 664 alunos reais cuja section o parser não entendeu (commit 59cc7ce), e excluí-los seria punir o aluno por defeito de ingest. O default da rota continua sem faltas — as telas que já a consomem calculam média sobre a lista.',
  },
  {
    chave: 'sequencia',
    estado: 'real',
    descricao: 'Simulados consecutivos sem faltar, corrente e recorde',
    doc: 'docs/26 §4',
    rotaFutura: 'GET /me/jogo',
    telas: ['Hoje', 'casco (coluna direita)', 'Login'],
    observacao:
      'As duas janelas são diferentes de propósito (docs/36 §1.3): a FITA cobre o ciclo corrente, porque é o que cabe no cartão da Hoje; os dois NÚMEROS cobrem o ano inteiro, porque recorde que zera na virada de ciclo não é recorde. ⚠️ `/me/streak` SAIU no mesmo commit — ela media "ciclos acima da média da turma", relativa, que premia posição e não progresso (docs/24 §1.1). O tool `meu_streak` do Tio Léo foi repontado para cá: o nome ficou, a resposta mudou.',
  },
  {
    chave: 'proximoSimulado',
    estado: 'real',
    descricao: 'Data do próximo simulado, para a contagem regressiva',
    doc: 'docs/36 §2.2',
    rotaFutura: 'GET /me/agenda',
    telas: ['Hoje', 'casco (coluna direita)'],
    observacao:
      '⚠️ `null` é resposta legítima e COMUM, não erro: em 05/09 havia 1 evento futuro no banco inteiro e 1 simulado com `evento_agenda_id`. A tela ESCONDE o bloco nesse caso (docs/36 §1.2) — vazio permanente ensina o aluno a ignorar aquele espaço. `vestibular` e `fase` saem do simulado ligado ao evento, porque `evento_agenda` não tem nenhum dos dois; `fase` vem de `simulado.tipo`, já que a coluna `simulado.fase` saiu na migration 0003. Evento sem simulado não alcança ninguém — é a mesma regra de audiência do motor de lembretes.',
  },
  {
    chave: 'zonaEDistancia',
    estado: 'real',
    descricao: 'Zona do aluno, distância até a próxima e o nome da régua que produziu o veredito',
    doc: 'docs/36 §2.5',
    rotaFutura: 'GET /me/zona',
    telas: ['Hoje', 'Jornada'],
    observacao:
      'A régua é obrigatória junto do rótulo (docs/24 §2): "risco" sem contra qual corte é só a má notícia. A régua é a do vestibular alvo do aluno, e quem mira ITA e IME é avaliado contra os dois valendo o PIOR veredito. NÃO lê `classificacao_aluno`: a tabela é cache de lote e cobre 568 dos 1.229 alunos com nota — devolver 404 aos outros 661 seria transformar "o job ainda não passou por você" em "você não existe". Calcula com o mesmo avaliador de `criterios.py`, nunca uma cópia da regra: foi a segunda cópia que a migration 0037 matou.',
  },
  {
    chave: 'cortePorMateria',
    estado: 'real',
    descricao: 'A nota de corte de cada matéria — 4,0, e 5,0 no Inglês eliminatório do ITA F1',
    doc: 'docs/24 §2',
    rotaFutura: 'GET /me/zona (mesma rota da zona)',
    telas: ['Hoje', 'Provas', 'Jornada', 'Extrato de XP'],
    observacao:
      'Vem na MESMA resposta de `zonaEDistancia`, e `useMateriasContraCorte` a recorta da mesma `queryKey`. Separar as duas em chaves diferentes faria duas chamadas e — pior — abriria a porta para a tela mostrar a barra de uma régua e o rótulo de outra.',
  },
  {
    chave: 'meusErros',
    estado: 'sem-rota',
    descricao: 'Todas as questões erradas e em branco, agregadas por todos os simulados',
    doc: 'docs/29 §A.3',
    origemDoDado: '`/me/simulado/{id}/questoes` já devolve isso por simulado — falta somar',
    rotaFutura: 'GET /me/erros',
    telas: ['Estudar (o elo quieto)', 'Sessão de treino (origem `erros`)'],
    esforco: 'P',
    observacao:
      '⚠️ FICOU DE FORA da leva de 05/09 de propósito (docs/36 §4), e não por esforço: `questao.assunto` está 100% VAZIO no banco (0 de 1.079), então a rota nasceria devolvendo `assunto: null` em toda linha e a tela prometeria "estude por assunto" sem saber o assunto. São ~200 questões erradas por aluno, pior caso 676 — o que também pede uma decisão de teto, já que não há paginação. Volta no Sprint 6 com `questao_topico`, e aí nasce já útil.',
  },

  // ─── MOCK PURO ─────────────────────────────────────────────────────────
  {
    chave: 'importanciaDoAssunto',
    estado: 'mock',
    descricao: 'Fatia da prova ponderada por recência (meia-vida 5 anos) e a tendência ao lado',
    doc: 'docs/24 §4',
    depende: '`/banco/estatisticas`, que já dá a incidência bruta — falta a ponderação',
    telas: ['— nenhuma'],
    esforco: 'M',
    observacao:
      '⚠️ ADIADA POR DECISÃO DE 02/09: a tela de Estatísticas ranqueia por INCIDÊNCIA BRUTA, sem ponderação por recência, e a tendência sai de código puro sobre a mesma série que o gráfico desenha (`dominio/serieDoAssunto.ts`). Sobrevive só como heurística interna da fila de treino (o fixture `ASSUNTOS` em `mocks.ts`, dentro de `ordenarFilaDeTreino`). Independe do Sprint 6 e continua sendo "B pode começar hoje" de docs/24 §8 — mas deixou de ser pré-requisito da missão do dia, que foi construída em 04/09 sem ela: um desafio igual para toda a turma não pondera nada por aluno (docs/35 §9).',
  },
  {
    chave: 'acertoPorAssunto',
    estado: 'mock',
    descricao: 'Quanto o aluno acerta em cada tópico do edital',
    doc: 'docs/24 §3',
    depende: 'classificar as 1.031 questões de simulado (`questao_topico`, Sprint 6)',
    telas: ['Resumo do treino'],
    esforco: 'G',
    observacao:
      'O caminho crítico de tudo. Classificar 1.031 questões faz 237.081 respostas passarem a dizer em que assunto o aluno erra.',
  },
  {
    chave: 'escolhaDaFilaDeTreino',
    estado: 'mock',
    descricao: 'Quais questões entram na sessão, e em que ordem',
    doc: 'docs/28 §3',
    depende: 'acertoPorAssunto + importanciaDoAssunto',
    telas: ['Sessão de treino'],
    esforco: 'M',
    observacao:
      'As QUESTÕES são reais (`/banco/questoes`); o que é mock é o critério de escolha. Antes do Sprint 6 a sessão cai para matéria, escolhida pela mais distante do corte.',
  },
  {
    chave: 'respostaNoTreino',
    estado: 'real',
    descricao: 'A alternativa que o aluno escolheu no treino e se ela bate com o gabarito',
    doc: 'api/migrations/0042_resposta_no_treino.sql',
    rotaFutura: 'PUT /banco/estudo/{id} · alternativaEscolhida',
    telas: ['Sessão de treino', 'Resumo do treino'],
    observacao:
      'Ligada em 02/09 (migration 0042). É a única fonte de acerto por assunto que NÃO depende do Sprint 6 — as questões do banco já são classificadas por tópico do edital. ⚠️ `acertou` é calculado no SERVIDOR contra o gabarito, nunca aceito do cliente; `null` é "não dá para dizer" (dissertativa ou sem gabarito), jamais "errou". E não muda a diretriz: alimenta o plano de estudo, NUNCA o XP — treino não é supervisionado.',
  },
  {
    chave: 'xp',
    estado: 'mock',
    descricao: 'XP total e do ciclo',
    doc: 'docs/26 §3',
    depende: 'o cálculo de XP reusando o avaliador de critérios, e o backtest de docs/29 §H',
    telas: ['casco (topo e coluna direita)', 'Extrato de XP', 'Liga'],
    esforco: 'M',
    observacao:
      '⚠️ Os números da tabela são primeira calibração e o backtest contra os 5 ciclos de 2026 é PORTÃO, não desejável (docs/26 §7). XP é derivado, nunca saldo gravado.',
  },
  {
    chave: 'extratoXp',
    estado: 'mock',
    descricao: 'De onde vieram os pontos, linha por linha, com as que não pontuaram vazadas',
    doc: 'docs/26 §3',
    depende: 'xp + cortePorMateria',
    telas: ['Extrato de XP', 'Tio Léo (artefato)'],
    esforco: 'M',
    observacao:
      'A única tela que explica a régua de corte sem parecer boletim. As linhas com +0 nunca somem.',
  },
  {
    chave: 'metaDoCiclo',
    estado: 'real',
    descricao: 'O alvo do ciclo — substituiu a meta semanal, que o dado não sustentava',
    doc: 'docs/36 §1.5',
    rotaFutura: 'GET /me/meta',
    telas: ['Hoje'],
    observacao:
      'Quem define é o SISTEMA e a meta é PRESENÇA (docs/36 §1.5) — foi assim que a decisão aberta de docs/24 §9.1 caiu sem inventar produto: dá para verificar com `nota.presente`, não depende do XP (travado no backtest de docs/29 §H) e não pede tela de coordenação. ⚠️ `alvo` sai do CALENDÁRIO do ciclo, não do que o aluno fez: contar só o que ele já viu faria a meta andar junto com ele e parecer sempre cumprida.',
  },
  {
    chave: 'liga',
    estado: 'mock',
    descricao: 'Liga anônima do ciclo, com sobe-5 / desce-5',
    doc: 'docs/26 §5.1',
    depende: 'xp + a decisão de coordenação "gamificação pode ser competitiva?"',
    telas: ['Liga', 'Jornada', 'casco (coluna direita)'],
    esforco: 'G',
    observacao:
      'Os grupos TÊM de cruzar turma e sede: com ~900 alunos são 30 grupos, e um grupo que coincida com uma turma derruba o anonimato por dedução.',
  },
  {
    chave: 'esquadrilha',
    estado: 'mock',
    descricao: 'Time de 3 a 6 amigos cujo XP soma; ninguém é ranqueado por dentro',
    doc: 'docs/26 §5.2',
    depende: 'xp + parecer de LGPD (docs/26 §5.3)',
    telas: ['Jornada'],
    esforco: 'G',
    observacao:
      'É dado de desempenho de um menor compartilhado com outro menor, por escolha do titular. Entrada só por código de convite, nunca por busca de aluno. Entregue como afordância, não como funcionalidade.',
  },
  {
    chave: 'conquistas',
    estado: 'mock',
    descricao: 'As medalhas sob as regras novas — só o que se verifica',
    doc: 'docs/26 §6',
    depende: 'xp, sequencia e `conquista_aluno(aluno_id, chave, em)`',
    telas: ['Jornada'],
    esforco: 'P',
    observacao:
      'Sai "Top 15%", que premia posição. Sem a tabela de registro a celebração de tela cheia repete a cada abertura.',
  },
  {
    chave: 'depoimentos',
    estado: 'mock',
    descricao: '"De quem já passou" — o cartão de aprovados',
    doc: 'docs/24 §7 (brief)',
    depende: 'conteúdo editorial de verdade',
    telas: ['Jornada'],
    esforco: 'P',
    observacao: 'Entregue como afordância com um botão. Citação de aprovado não se inventa.',
  },
  {
    chave: 'ganchoDeRetorno',
    estado: 'mock',
    descricao: 'O gancho personalizado da tela de login — "sua sequência está esperando"',
    doc: 'docs/29 §C',
    depende: 'notificação (e-mail, push ou PWA), que não existe',
    telas: ['Login'],
    esforco: 'G',
    observacao:
      '⚠️ NÃO foi implementado, e a ausência é deliberada: antes do login o servidor não sabe quem está do outro lado, e mostrar a sequência de alguém a quem quer que abra a página é vazamento, não retenção. O gancho de verdade é notificação — e docs/29 §C registra que não existe PWA, manifest nem push. A porta mostra a metáfora, não um número de ninguém.',
  },
  {
    chave: 'artefatosDoTioLeo',
    estado: 'mock',
    descricao: 'Os artefatos novos do catálogo: barras_corte, extrato_xp, questao, plano, prova',
    doc: 'docs/27 §7',
    depende: 'as tools novas em `tools_aluno.py` e as fontes que cada artefato mostra',
    telas: ['Tio Léo'],
    esforco: 'M',
    observacao:
      '`histograma` e `linha_temporal` já são reais e continuam. `fonte_id` é injetado do JWT, nunca aceito como argumento.',
  },
  {
    chave: 'formulaMatematica',
    estado: 'real',
    descricao: 'Renderização de fórmula na resposta do Tio Léo',
    doc: 'docs/36 §3.1',
    rotaFutura: 'componentes/ui/Markdown.tsx (KaTeX) — renderização no cliente, sem rota',
    telas: ['Tio Léo'],
    observacao:
      '⚠️ A decisão de docs/27 §12 ("KaTeX ou Temml?") JÁ ESTAVA FECHADA no código — o documento é que não sabia. `componentes/ui/Markdown.tsx` usa KaTeX desde 01/09, com macros pt-BR (`\\sen`, `\\tg`, `\\cotg`) e fontes servidas do nosso domínio, e já desenha as resoluções do banco e as questões do treino. Não entrou dependência nova: o artefato do Tio Léo passou a usar o mesmo componente. Um segundo motor de fórmula seria a dívida que este projeto vive consertando. ⚠️ O risco de docs/27 §10 NÃO é resolvido por renderizar e segue de pé: fórmula bonita e errada aumenta a confiança do aluno numa resposta falsa.',
  },
];

const PORCHAVE = new Map(FONTES.map((f) => [f.chave, f]));

/** A fonte, ou `undefined` — quem chama decide se isso é erro. */
export function fonte(chave: string): Fonte | undefined {
  return PORCHAVE.get(chave);
}

/** O estado de uma fonte. Chave desconhecida vira `'mock'`: falhar para o lado
 *  de marcar demais é melhor que esconder superfície mockada. */
export function estadoDaFonte(chave: string): EstadoFonte {
  return PORCHAVE.get(chave)?.estado ?? 'mock';
}

export function fontesPorEstado(estado: EstadoFonte): Fonte[] {
  return FONTES.filter((f) => f.estado === estado);
}
