# 19 — Roadmap · o que foi feito, o que falta, o que vem

> **Este é o documento de estado.** Os outros (`10`, `11`–`13`, `18`, `23`)
> contam *por que* e *como*; este diz só *onde estamos*. Quando divergirem,
> corrija aqui primeiro — é o que se lê antes de qualquer sprint.
>
> Atualizado em **30/08/2026**. O deploy de 24/08 juntou o redesenho do
> casco, a SPRINT FOTO e o acervo histórico do banco de questões — ver §9.8
> de [23-banco-questoes-historico.md](23-banco-questoes-historico.md) pra
> como isso quase saiu errado (checkout desatualizado, importador sem
> acesso aos JSONs dentro do container). Em 29/08 entraram os Sprints 6 e 7
> e o polimento avulso, vindos do brainstorming daquela manhã:
> [24-jornada-do-aluno.md](24-jornada-do-aluno.md) (aluno) e
> [25-leitura-da-coordenacao.md](25-leitura-da-coordenacao.md) (coordenação).
> Em **30/08** a área do aluno saiu do papel: o front inteiro foi escrito.
> ⚠️ **Para o estado dela, leia [30-estado-da-implementacao.md](30-estado-da-implementacao.md)**
> — as tabelas de lá são GERADAS do código (`web/src/dados/aluno/registro.ts`)
> e `npm test` falha se envelhecerem. Este documento resume; aquele não mente.
> Ainda em **30/08**, a publicação automática de aulas saiu de "escrito, não
> em produção" para a §1, depois de conferida no VPS (crontab instalado,
> `AWS_*`/`YOUTUBE_*` preenchidos, migrations `0034`–`0036` aplicadas, 7 aulas
> no canal). Com isso a antiga **§1.5 deixou de existir**: não há mais nada
> escrito fora de produção.

---

## 1 · Em produção hoje (`portalsas.online`)

Tudo abaixo está no `main` e no ar. Migrations aplicadas: **0001 → 0036**
(a `0037` e a `0038` existem, aplicadas só no banco local — ver a Sprint 5 em
[§3](#3--próximos-ciclos--proposta)).
Testes: **279** no backend, **233** no front. Banco de questões: **2.693**.

### Sprint 1 · Bloco A — o simulado nasce no SAS *(17–20/08)*

| Parte | O quê | Estado |
|---|---|---|
| P1 | Agendamento: simulado criado no SAS, Assignment no Canvas, `evento_agenda` | ✅ |
| P2 | Motor de lembretes + e-mail (SES), coordenador como 1º destinatário | ✅ |
| P3 | Lembrete de aluno — um e-mail por dia, na véspera | ✅ (etapas 1–12; ver [13](13-plano-p3-lembrete-aluno.md)) |
| P4 | Professores, requerimentos e cobrança por e-mail | ⏳ **não começou** |
| P5 | WhatsApp (Z-API) | ⏳ **não começou** — decisão em aberto, ver [§4](#4--decisões-em-aberto) |

### Sprint 2 · Critérios, Canvas sob controle, auditoria, identidade *(21–22/08)*

Origem: conversa com a coordenação em 21/08. Plano e decisões em [18](18-plano-sprint-2.md).

| Parte | O quê | Estado |
|---|---|---|
| P1 | Regra de corte vira dado, avaliada no servidor; Tio Leo · ITA F1/F2 · IME F1/F2 com artigo do edital; dois blocos + desempate | ✅ |
| P2 | Nada sobe ao Canvas sem o coordenador escolher; `divergente`; nota com `pontuacao_canvas` + `pontuacao_sas` | ✅ verificado contra o Canvas real |
| P3 | Auditoria por canal, só criações e alterações; tela `/auditoria` | ✅ |
| P4 | Login pelo Canvas (OAuth2), painel de administrador, logo do Ari, botão Sair; id do Canvas resolvido pelo e-mail | ✅ (SSO verificado como aluno; como coordenador fecha quando o Leo entrar) |

### Sprint Banco de questões · o acervo ITA·IME vira aba *(22–23/08)*

Furou a fila junto do mobile, por decisão direta. Plano e achados em
[22](22-plano-banco-questoes.md). PR #16, deploy em 23/08.

| Parte | O quê | Estado |
|---|---|---|
| P1 | O dado entra no SAS — `questao_vestibular` e a taxonomia dos editais (`0028`) | ✅ 934 questões, 65 tópicos, 351 assuntos |
| P2 | API: listagem filtrada e paginada, recorrência agregada no servidor | ✅ 13 rotas |
| P3 | A aba `/banco`, nos dois cascos | ✅ verificada a 390 e 360px |
| P4 | Estatísticas sem Chart.js | ✅ |
| P5 | Listas: montar, reordenar, exportar PDF e Word (`0029`) | ✅ |
| P6 | Estudo do aluno: resolvida, anotação, mensagem | ✅ |

**O Postgres é a fonte da verdade** ([22 §13](22-plano-banco-questoes.md)): os
934 JSONs não são versionados, e `scripts/exportar_banco_questoes.py` é a saída
— conferida em produção com zero divergência.

### Sprint Acervo histórico do banco de questões *(23–24/08)*

ITA 2008–2018 + IME 1996–2019 (lotes A+B; C+D — pré-2008/1996, majoritariamente
escaneados — ficaram de fora por decisão de escopo). Plano, achados e a
novela do deploy em [23-banco-questoes-historico.md](23-banco-questoes-historico.md).

| Parte | O quê | Estado |
|---|---|---|
| Extração + classificação + resolução (1ª passada) | 1444 questões, todas | ✅ |
| Correção com imagem (2ª passada) | 482 questões citando figura — 263 via OpenAI, 204 via Claude | ✅ 467/482 (15 pendentes, sem recorte baixado ainda) |
| Import em produção | `questao_vestibular`, migration `0031` | ✅ 24/08 — 2378 questões no total |

**O Postgres de produção passa a ter 2378 questões** (934 + 1444). Lotes C/D
(257 PDFs escaneados) seguem fora — [23-banco-questoes-historico.md §6](23-banco-questoes-historico.md#6--coisas-descobertas-que-mudam-a-forma-de-abordar-cd-no-futuro).

### Sprint Fase 1 do IME · 2007–2016 — o banco cresce 360 *(29/08)*

A prova objetiva do IME estava no repositório desde 22/08 e nunca foi
processada: [23 §3.1](23-banco-questoes-historico.md) a registrou como
"trabalho não começado, não uma lacuna medida". São doze cadernos, um por
biênio, **dez com texto nativo e gabarito oficial ao lado**. Plano, achados e
o que mudou no pipeline em [23 §23](23-banco-questoes-historico.md).

| Etapa | Estado |
|---|---|
| Recorte de imagem do IME (quebrado desde [23 §21.4](23-banco-questoes-historico.md)) | ✅ localiza por palavra; 1996 vai de 0 para 10/10, zero regressão nos biênios em produção |
| `processar_ime_objetiva` — 40 questões, três matérias num PDF, alternativas | ✅ conferida contra `ime_2018_fase1`: **40/40** em matéria, gabarito e letras |
| Gabarito do IME (quatro geometrias, uma delas rotacionada 90°) | ✅ duas leituras por coordenada que precisam concordar; zero divergência contra as 25 respostas já em produção |
| Extração e classificação por tópico do edital | ✅ 280 questões, 384 ligações, sem custo de API |
| **Conferência das 280 letras contra os PDFs renderizados** | ✅ achou 2 erros reais (2016 q25 e q27) — [23 §23.7](23-banco-questoes-historico.md) |
| Gabarito conferido vira trava versionada | ✅ `config/_gabaritos_ime_objetiva.json`; o extrator recusa o ano que divergir |
| Import em produção (1ª rodada) | ✅ 29/08 — 2.383 → **2.693**, 280/280 batendo com o gabarito conferido |
| 2009 e 2011: gabarito oficial achado em `Resultados/` | ✅ [23 §24](23-banco-questoes-historico.md) — conferido por parser, leitura à vista e pelas resoluções do Farias Brito |
| `_texto_poppler` — a prova de 2011 partia o próprio marcador | ✅ recurso opcional; sem o binário o ano é pulado, não quebra |
| Import local (2ª rodada) | ✅ **2.773**, 360/360 batendo com o gabarito oficial |
| Recorte de 2009 saía picado (folha A3 girada, 2-up) | ✅ [23 §25](23-banco-questoes-historico.md) — 24 recortes de <200px; agora 360/360 saudáveis, com guarda no extrator |

**Nove anos entraram** (2007–2009, 2011–2016), todos com gabarito definitivo da
banca. 2009 e 2011 quase ficaram de fora: o gabarito da objetiva não está em
`Provas_Anteriores/`, e sim em `Resultados/`, outra árvore do mesmo site do IME —
achado só depois de uma varredura em seis frentes ([23 §24](23-banco-questoes-historico.md)).
Ficam de fora 2010 e 2017, cadernos escaneados. Onze questões anuladas pela banca
entram sem letra.

**Deploy em 29/08.** Produção foi de 2.383 para **2.693 questões** — as 280 da
primeira rodada mais as 30 do IME 1996 do [§22](23-banco-questoes-historico.md),
que estavam represadas. **As 80 de 2009 e 2011 ainda não subiram**: o local está
em 2.773. Conferido por `psql` direto contra o gabarito versionado:
**280/280**. A `ESPERADO` do importador, parada nos 934 desde 22/08, foi
atualizada — toda importação desde 23/08 terminava com um alarme que ninguém
podia levar a sério ([23 §23.9](23-banco-questoes-historico.md)).

### Sprint Resolução legível · fórmula deixa de sair em código *(01/09)*

As 1.500 resoluções escritas do acervo iam para a tela como string: o cartão
fazia `<p>{md}</p>` e o aluno lia `$q=N\dfrac{\Delta\Phi}{R}$`. Estava
registrado como dívida em [22 §8, risco 5](22-plano-banco-questoes.md) — não era
esquecimento, era decisão adiada.

| Etapa | Estado |
|---|---|
| Medição antes de escrever: KaTeX contra as 13.881 fórmulas do acervo | ✅ 58 falhas em 33 questões — 0,4% |
| `dominio/markdown.ts` — analisador leve, fórmula extraída ANTES do Markdown | ✅ 9 testes; sem `react-markdown` (~40 pacotes para uma gramática que o corpus não usa) |
| `componentes/ui/Markdown.tsx` — KaTeX com macros de notação brasileira | ✅ `\sen`, `\tg`, `\arcsen`, `\Arg`, `\Ω`: sozinhas derrubam 24 das 58 falhas |
| Aplicado nos três cartões, no enunciado sem imagem e no chat do Tio Léo | ✅ o `Markdown` do chat virou o compartilhado; 4 avisos de lint a menos |
| **Bug de dados achado no caminho**: escape de JSON comeu a barra do LaTeX | ✅ migration `0039` — 20 questões, ITA 2008 F1 e IME 2013 F2 Mat |
| Guarda no importador para não voltar na próxima importação | ✅ `_resolucao_saneada`, 10 testes; a ordem (repor a barra ANTES de limpar C0) é o que o teste trava |
| Erro de LaTeX do próprio gerador, que só o renderizador revelou | ✅ migration `0040` — 16 fórmulas em 11 questões, todas trocas tipográficas |
| **Painel de fórmula deixa de depender de quem digitou** | ✅ `\dfrac`, somatório, integral e matriz viram bloco; `\tfrac` não |
| CSP de produção: KaTeX escreve 43 `style=""` por fórmula | ✅ `style-src-attr 'unsafe-inline'` — `<style>` e `<link>` seguem só de `'self'` |
| KaTeX em chunk próprio, para não rebaixar junto com o app a cada deploy | ✅ +77 kB gzip isolados; o app seguiu em 197 kB |

**As 13.882 fórmulas do acervo renderizam. Zero falhas, zero questões
afetadas** — eram 58 em 33. A rede de segurança (`throwOnError: false`, fórmula
inválida em vermelho legível em vez de cartão derrubado) continua lá, e agora
não tem o que pegar.

A última parte é a que muda mais a leitura e não estava no plano: **metade do
acervo escrevia a conta em `$$` e ganhava painel destacado; a outra metade
escrevia a MESMA conta entre `$` e ela sumia no meio da prosa.** Não é diferença
de conteúdo, é de quem digitou — e o aluno pagava, porque o passo da conta
ficava indistinguível da frase que o explica. A regra agora lê a intenção no
comando: `\dfrac` pede tamanho de display e promove; `\tfrac` pede tamanho de
linha e nunca promove; operador grande e matriz não cabem em linha nenhuma.
Promove 844 de 12.690 fórmulas de linha (6,7%) e dá painel a 402 resoluções sem
que ninguém reescreva nada.

A corrupção merece registro porque o modo de falha se repete: `resolucao_md`
volta do LLM dentro de string JSON, e `\text` sem barra escapada vira TAB
porque **é isso que a especificação do JSON manda**. Ficou meses invisível
justamente porque o texto ia cru para a tela — ninguém lê LaTeX cru, então
ninguém distinguia uma barra a menos do resto da notação. Só apareceu ao
renderizar.

### Sprint Aba Estudar · três campos, em dado real *(02/09)*

Implementação do desenho entregue pelo Claude Design (`sas-rea-do-aluno/`).
⚠️ **Estado: ESCRITA, fora de produção** — verificada no browser local a
390x844 nos dois temas, migrations `0041`/`0042` com `up`/`down`/`up` limpos.
Falta o deploy.

A aba Estudar deixa de ser duas metades e passa a ser **três campos**: Banco,
Estatísticas e Meu progresso. A decisão que destravou o sprint foi de desenho:
**Estatísticas passou a falar só do mundo** — recorrência por tópico do edital,
sem nenhuma métrica de acerto do aluno. Com isso a tela deixou de depender do
Sprint 6 (classificar as 1.031 questões de simulado) para existir.

| Parte | O quê | Estado |
|---|---|---|
| B1 | `questoesPorAno` em `/banco/estatisticas` — o denominador de "% da prova" | ✅ 10 testes |
| B2 | `fase` como parâmetro da mesma rota, ao lado de `vestibular` | ✅ |
| B3 | `colecao=recentes\|arquivo` em `/banco/questoes`, traduzida para `extraido_por` | ✅ 8 testes |
| B4 | `GET /banco/progresso` — agregado, com `get_current_aluno` | ✅ 12 testes |
| M1 | `0041` — `extraido_por` NOT NULL DEFAULT 'pipeline' | ✅ |
| M2 | `0042` — `alternativa_escolhida` + `acertou` em `questao_estudo_aluno` | ✅ 12 testes |
| F1 | Cartão em modo página: tarja fixa, "Ampliar" e a folha que explica | ✅ |
| F2 | Estudar → três campos | ✅ |
| F3 | Estatísticas: ranking, decompor, mapa do edital, ficha do assunto | ✅ |
| F4 | Meu progresso: vazio primeiro, depois matéria / assunto / ano | ✅ |
| — | "O que mais cai" (`EstudarAssuntos.tsx`) **apagada** | ✅ rodava em mock |

**Quatro fontes saíram do mock**: `estatisticasDoBanco` (era "ligada no papel,
sem tela"), `progressoDoBanco` (nova), `respostaNoTreino` (a resposta do treino
morria no `useState`) e a matéria de um código de tópico no Treino, que passou
a sair da taxonomia real em vez de um catálogo de cinco assuntos. O inventário
gerado ([30](30-estado-da-implementacao.md)) foi de 20 para 22 fontes ligadas.

**O que o dado real ensinou, e que o protótipo não podia saber:**

- O acervo do IME **pula 1997, 2000, 2001 e 2003**. A linha do gráfico se parte
  nesses anos em vez de interpolar, e a média móvel é de ANOS e não de posições
  no array — uma janela de três posições sobre [1996, 1998, 1999] mediria
  quatro anos e chamaria isso de "média de três".
- Em Matemática e Física a **maioria dos blocos do edital tem um tópico só**,
  com o mesmo nome. O mapa do edital suprime o cabeçalho redundante e funde os
  blocos de um item numa grade única — com a grade de três colunas fixas do
  desenho, o mapa ficava com duas colunas vazias por linha.
- `--alu-topo-altura` virou token: a tarja do modo página gruda abaixo da barra
  de topo, e com um `62px` cravado ela sumiria atrás dela num aparelho com
  notch, onde `safe-area-inset-top` chega a 47px.

**Fora do escopo, declarado:** a ponderação por recência de
[24 §4](24-jornada-do-aluno.md) (decisão de 02/09 — o ranking usa incidência
bruta), e `acertoPorAssunto`, que segue dependendo do Sprint 6.

### Sprint Redesenho do casco *(23/08)*

Rail de ícones no lugar da topbar de 7 abas, migalhas, faixa de filtros
horizontal, Ciclos+Simulados fundidos em `/provas`. Plano em
[23-plano-redesenho-casco.md](23-plano-redesenho-casco.md).

| Parte | O quê | Estado |
|---|---|---|
| P1 | Tokens — paleta do canvas, cinza azulado, âmbar separado em traço e texto | ✅ |
| P2 | Casco — rail, topbar com migalhas, barra inferior no celular | ✅ |
| P3 | Telas — `BarraFiltros`, `/provas`, abas de Administração | ✅ |
| P4 | Polimento tela a tela, com o browser aberto | ⏳ **não feito** — foi pro ar sem essa checagem |

> ⚠️ **Foi pro ar com um blocker conhecido não resolvido**: o sino da topbar
> aponta para `/painel#alertas`, e esse id não existe em `Painel.tsx` —
> confirmado ainda ausente em 24/08, na hora do deploy. Clicar no sino não dá
> erro, só não rola pra lugar nenhum. Documentado aqui antes desse deploy
> como "bloqueia o deploy" ([23-plano-redesenho-casco.md §8](23-plano-redesenho-casco.md#8--o-que-falta--p4)
> · item 3) e foi pro ar assim mesmo — decisão de escopo do usuário
> ("tudo que está na árvore hoje"), não descuido. Conserto pequeno: um
> `id="alertas"` em algum bloco de `Painel.tsx`.

### Sprint Foto de perfil *(23–24/08)*

"O rosto no cadastro" — pedir a foto no primeiro acesso, guardar no banco
(`foto_perfil`, migration `0032`), servir por rota autenticada da própria
API. Documentado em `docs/sprints.html · SPRINT FOTO` (sem doc próprio em
`docs/` ainda).

| Parte | O quê | Estado |
|---|---|---|
| P1 | Onde a foto mora — coluna `foto_perfil` em `aluno` e `usuario_coordenacao` | ✅ |
| P2 | Pedido no primeiro acesso, recorte por `<canvas>` | ✅ |
| P3 | Pedido reaparece pra quem já tinha conta e não tem foto | ✅ |
| P4 | Onde o rosto aparece — casco do aluno, topbar, `/alunos`, ficha, `/auditoria` | ✅ |
| P5 | Consentimento (andaime técnico), troca, remoção auditada | ✅ |

### Sprint Aulas · publicação automática no YouTube *(27–29/08)*

Substitui o processo manual em que um auxiliar de coordenação gravava a
própria tela durante a aula e subia o vídeo depois. Roda em
`api/app/gravacoes_aula/`, disparado pelo cron do VPS como o resto
(`/gravacoes-aula/verificar` e `/gravacoes-aula/processar`, de hora em hora).

| Etapa | Estado |
|---|---|
| Detectar aula nova com gravação no Canvas | ✅ testado contra o Canvas real |
| Baixar do BigBlueButton | ✅ aula real de 97 min, ~480 MB |
| Compor com o template da marca | ✅ ffmpeg, câmera + tela sobre o PNG |
| Guardar no S3 | ✅ bucket privado dedicado |
| Publicar no YouTube como *não listado* | ✅ 7 aulas no canal |
| Publicar a página da aula no Canvas, dentro do módulo da matéria | ✅ 7 páginas, `0035` e `0036` |
| Acompanhamento em `/integracoes/aulas` | ✅ |

**O achado que viabilizou tudo:** a documentação oficial e as ferramentas de
terceiros (`bbb-dl`) dizem que o plano de BigBlueButton do colégio não permite
baixar arquivo de vídeo. É meia-verdade — a página de replay é mesmo só um
player HTML5, mas **existem os arquivos brutos** por trás dela:
`{replay}/video/webcams.mp4` (câmera + áudio) e
`{replay}/deskshare/deskshare.mp4` (tela compartilhada, só se a aula usou).
A busca anterior falhava por procurar `.webm`, a convenção antiga do BBB.

**Retenção de ~7 dias**, medida cruzando idade da aula com presença de
gravação em três matérias: aula com ≤7 dias tem gravação, com ≥8 não tem.
É a janela em que o pipeline precisa rodar — daí o cron de hora em hora e
não diário.

**Decisões de LGPD** (são menores de idade na câmera e no chat):
- Vídeo publicado como **não listado**: o aluno abre pelo link sem precisar de
  conta Google, e a aula não aparece em busca, no canal nem em recomendações.
  *Privado* não serviria — o link não funciona para quem não foi convidado
  individualmente por e-mail, nem quando o vídeo é incorporado no Canvas.
- **Bucket S3 dedicado e privado** (`sas-gravacoes-aula`), com as quatro
  proteções de Block Public Access ligadas e criptografia padrão. Os buckets
  que já existiam na conta são todos públicos — reaproveitar um deles deixaria
  vídeo de aluno a uma edição de política de exposição.
- O token do YouTube tem só `youtube.upload` + `youtube.readonly`: **não pode
  apagar vídeo**. Pedido de eliminação por um responsável exige um humano no
  YouTube Studio. É o padrão mais seguro, mas a coordenação precisa saber.

**No ar desde 29/08, rodando sozinho.** As chaves `AWS_*`,
`S3_BUCKET_GRAVACOES` e `YOUTUBE_*` estão no `infra/vps/.env` do VPS e o
`crontab-sas` foi instalado com os dois jobs (`verificar` aos 20 de cada hora,
`processar` aos 25). Migrations `0034`–`0036` aplicadas em produção. Estado do
banco em 30/08: **4 cursos monitorados** (`581` Preparatório, `691` Matemática,
`692` Física, `693` Química), **7 aulas publicadas** no YouTube — todas as 7
com página criada no Canvas — e 7 em `aguardando_gravacao`, esperando o BBB
disponibilizar o arquivo. A imagem da API passou a incluir `ffmpeg` (~250 MB) —
o build de produção ficou maior.

**Sobrou uma pontinha:** Matemática (`691`) é o único curso sem
`canvas_modulo_id` de fallback. Quando o assunto da aula não casa com módulo
nenhum, a página é criada *fora de módulo* em vez de falhar — conserto é um
`UPDATE` em `curso_monitorado_gravacao` quando o módulo padrão da matéria for
escolhido.

### Blocos B, C, D do [docs/10](10-problemas-e-visao.md) — o que já caiu no caminho

| Item | Estado | Onde |
|---|---|---|
| B.2 Write-back de notas no Canvas | ✅ refeito na Sprint 2 (com escolha do coordenador) | [18 §2.4](18-plano-sprint-2.md#24-nota-sempre-o-canvas--alterações-do-sas) |
| C.1 Componente único de filtro | ✅ | `BarraFiltros.tsx` — era `PainelFiltros.tsx` (lateral) até o redesenho de [23](23-plano-redesenho-casco.md) |
| C.4 Ordenação por cabeçalho | ✅ | `TabelaOrdenavel.tsx` |

---

## 2 · Pendências da Sprint 2 — *o que sobrou, sem código*

| | O quê | Quem |
|---|---|---|
| 1 | **Régua com o Leo** — ele olhar o Ciclo 4 · ITA · 2026 sob "Tio Leo" (316 de 407 cortados; os ~50 que passam na média com uma matéria < 4 **não** são cortados, por decisão dele) e confirmar | Yan → Leo |
| 2 | **SSO como coordenador** — fecha sozinho no primeiro "Entrar com o Canvas" do Leo; a conta dele em produção já está ligada ao Canvas `289`. Conferir em `/auditoria` (filtro "Entradas no sistema") | automático |
| 3 | **Limpar os escopos da Developer Key** — ficou com 582; o SAS usa um (`Usuários → Mostrar detalhes do usuário`). Funciona como está; é poder demais | Yan, 2 min |

---

## 3 · Próximos ciclos — proposta

Três sprints, **uma frente por sprint**. "Escolher, não empilhar" ([10 §2.10](10-problemas-e-visao.md#210-sprint-1--escopo-e-divisão-17082026)).

> ⚠️ **Furou a fila em 22/08:** mobile virou prioridade por decisão direta,
> antes de qualquer uma das frentes abaixo. Plano em
> [20-mobile.md](20-mobile.md) (decisão de rota e auditoria) e
> [21-plano-mobile.md](21-plano-mobile.md) (execução — fundação de CSS e
> login já implementados e verificados no browser; área do aluno em
> andamento). Não renumerei o Sprint 3 abaixo porque a ordem dele entre si
> não mudou, só a posição na fila — quando mobile for pro ar, esta nota sai
> e o trabalho entra na [§1](#1--em-produção-hoje-portalsasonline).

### Sprint 3 · Fechar o Bloco A — *4 partes*

O que a coordenação mais pediu (cobrar professor sem ser na mão) e que já tem infra pronta (motor, agenda, e-mail).

| Parte | O quê | Tamanho | Depende de |
|---|---|---|---|
| P1 | **Requerimento de questões** — tabela `requerimento` + máquina de estados ([10 §2.4](10-problemas-e-visao.md#24-aplicação-1--requerimento-de-questões-aos-professores)); professor entra na fila ao criar o simulado, sai ao entregar | G | decisão do WhatsApp |
| P2 | **Cobrança por e-mail** — o motor existente dispara pros professores (era a P4 da Sprint 1) | M | P1 |
| P3 | **Ausência ≠ zero (B.1)** — o 🔴 confirmado do docs/10: falta contando como zero deturpa toda média, e o corte da Sprint 2 depende de média certa | M | — |
| P4 | **WhatsApp (Z-API)** — era a P5 da Sprint 1 | G | decisão do WhatsApp |

**Pré-voo:** a decisão do WhatsApp ([§4](#4--decisões-em-aberto)). Sem ela, P1 se desenha errado.

### Sprint 4 · Dado e leitura — *4 partes*

> **Estado: EM PRODUÇÃO** *(03/09)*. Plano, medição contra produção e decisões
> em [32-plano-sprint-4.md](32-plano-sprint-4.md); o estado parte a parte está
> no §5.1 de lá. Subiu com a `0043`, o backfill (**123 notas** marcadas
> `todas_em_branco`) e `recalcular_metricas` sobre 255 simulados. Verificado:
> 2.756 zeros − 123 = 2.633 ainda na conta, e **zero** provas marcadas — o
> Problema B segue desligado, esperando o aval prova a prova.
>
> ⚠️ **O mecanismo do Problema B mudou em 04/09, depois do deploy.** A `0043`
> criou `simulado.nota_confiavel`, que tirava a prova inteira do agregado. Medir
> mostrou que excluir era **pior**: aquelas provas eram genuinamente difíceis
> (média de 2,7 a 4,4 entre quem as fez), e removê-las *inflava* a média do
> ciclo — 6,18 contra os 5,51 corretos no Ciclo 4 · ITA. A regra em vigor é
> `simulado.zero_e_ausencia` (migration **`0046`**): a prova **fica** no
> agregado e só as notas zeradas saem, uma a uma, por `nota.computavel`. O que
> autoriza é a contagem da prova irmã do mesmo dia — em seis das oito, o número
> de alunos acima de zero bate com quantos a irmã avaliou, dentro de 1% a 7%.
> `nota_confiavel` fica sem uso, para o caso de uma prova de fato inutilizável.

| Parte | O quê | Estado |
|---|---|---|
| P1 | B.3 Zero × ausência — `nota.computavel` derivada de evidência direta | ✅ escrita (Problema A). ⬜ Problema B — as oito provas de 2023 — espera o aval da coordenação |
| P2 | B.4 Precedência planilha × Canvas | ✅ escrita — virou **aposentar a planilha**: zero uploads em produção, em toda a vida do sistema |
| P3 | C.2 Split ano / vestibular / ciclo no Painel | ✅ escrita |
| ~~P4~~ | ~~C.3 Range de período em Ciclos~~ | ✅ **já estava feito** — `RangeDatas` + `intersectaPeriodo`. Saiu do sprint |
| P6 | Envio em lote ao Canvas (C5) | ✅ escrita — e fechou um buraco maior: `enviarCicloAoCanvas` existia na API e **nenhuma linha do front o chamava** |

> A antiga **P5** (unificar `thresholds.py` com `criterios.py`) **saiu daqui**:
> foi puxada para a Sprint 5 em 30/08, porque os gráficos em camadas dependem
> dela para não desenhar três leituras do mesmo corte errado. A numeração das
> outras não mudou, para não invalidar referência de fora.

> ⚠️ **Duas coisas mudam de número quando isto for para produção**, e valem
> aviso antes: o Problema A tira 122 células da conta (efeito pequeno, e
> individual), e o Problema B — se aprovado — move a média de oito provas de
> 2023 de ~1,1 para ~3,8, o que é grande e visível em qualquer comparação
> histórica. Segunda mudança seguida na mesma tela, depois da régua da Sprint 5.

### Sprint 5 · Assistente com contexto, régua do coordenador e gráficos — *5 partes*

⚠️ **Reescopada em 30/08** depois de um levantamento no código: duas das cinco
partes propostas já estavam feitas, no todo ou em parte, sem registro em
documento nenhum. Plano completo em
[31-plano-sprint-5.md](31-plano-sprint-5.md).

> **Estado: EM PRODUÇÃO.** *(Escrita em 30/08; conferido em 04/09 que as
> migrations `0037` e `0038` estão aplicadas em produção — o texto abaixo, que
> dizia "falta o deploy", ficou para trás.)* As cinco partes estão
> implementadas e testadas localmente — 279 testes na API, 233 no front,
> migrations `0037` e `0038` com `up`/`down`/`up` limpos, e o fluxo da P4
> exercitado contra os 319 alunos do Ciclo 1 · IME. Uma revisão adversarial de
> 13 agentes achou **23 defeitos**, todos consertados antes do PR — inclusive
> uma frase que dizia "subiu" para um aluno que caiu, e um preâmbulo de chat
> que deixava um aluno ler o nome de outro. **Falta o deploy** e a verificação
> visual a 360/390px. Com isto, a §1.5 deste documento — "não há mais nada
> escrito fora de produção" — deixa de valer até o próximo deploy.

| Parte | O quê | No levantamento de 30/08 (antes de escrever) | Hoje |
|---|---|---|---|
| — | ~~D.1 Painel não-modal~~ | ✅ **já estava feito** na migração React (`c1e0a5f`) | saiu do sprint |
| **P1** | Régua única: unificar `thresholds.py` com `criterios.py` (+ `0037`) | era Sprint 4 · P5, puxada para cá | ✅ escrita |
| **P2** | D.4 Consciência de rota (chat ↔ página, + `0038`) | ⏳ intocado | ✅ escrita |
| **P3** | D.3 As três lacunas de tool que sobraram | 🟡 5 das 6 já fechadas por `chat/tools/contexto.py`; D.2 (abertura) ✅ | ✅ escrita — 30 tools |
| **P4** | O coordenador cria a própria régua (A7) | ⚠️ faltava a tela **e** o leitor DB→`Criterio` **e** o CRUD versionado | ✅ escrita |
| **P5** | Gráficos em camadas: leigo → insight → estatística | ⏳ intocado | ✅ escrita |

### Sprint 6 · O assunto entra no simulado — *4 partes*

Origem: brainstorming do Yan em 29/08 ([24](24-jornada-do-aluno.md)). É a
**fundação** de tudo que o aluno passa a poder fazer depois — e a maior alavanca
de esforço/retorno do projeto: classificar **1.031 questões** faz **237.081
respostas já gravadas** passarem a dizer *em que assunto* cada aluno erra.

| Parte | O quê | Tamanho | Depende de |
|---|---|---|---|
| P1 | **`questao_topico`** — ligação N:N das questões de simulado com `topico_taxonomia`, espelhando `questao_vestibular_topico`. A coluna `questao.assunto` da `0015` **não** serve (texto livre, um assunto só) e vira dívida a remover ([24 §3.2](24-jornada-do-aluno.md)) | M | — |
| P2 | **Classificar as 1.031** — lote, fora de `api/`, com o `classificar.py` do banco apontado para o HTML do Quiz Statistics | G | P1 |
| P3 | **Índice de importância** — incidência normalizada por ano × **meia-vida de 5 anos, fixa para todos** (decidido 29/08), com a **tendência exposta separada** do índice ([24 §4](24-jornada-do-aluno.md)) | M | — (só o que já está no Postgres) |
| P4 | **Acerto por assunto** — o aluno e a coordenação passam a ver acerto por tópico do edital | M | P2 |

**Pré-voo: ~~nenhum~~ três decisões**, achadas ao medir o banco em 04/09 e
**todas fechadas no mesmo dia** ([34 §5](34-plano-sprint-6.md)): as 115
questões só-imagem vão de **OCR local** (a amostra mostrou que são a prova
impressa capturada, não diagrama — o `tesseract` já classifica); o índice é
calculado no **servidor**; e a meia-vida mora **no banco**, versionada e
editável pela coordenação, o que sobe a P3 de P para M. As duas decisões *da
proposta* seguem tomadas desde 29/08 — a
meia-vida (5 anos, fixa) e a cobertura (só Matemática, Física e Química; a tela
diz quais matérias cobre). Português, Inglês e Redação ficam de fora, e o
Inglês eliminatório segue acompanhado só pela nota — é o próximo candidato a
ganhar taxonomia, num sprint futuro.

> 📄 **Plano escrito em 04/09: [34-plano-sprint-6.md](34-plano-sprint-6.md).**
> O levantamento mudou três coisas da proposta acima — o alvo é **1.030**
> questões e não 1.031/1.624 (Inglês e Português não têm taxonomia: 594 itens e
> 34% das respostas ficam fora, medido pela primeira vez); a **P3 está metade
> pronta** e cai de M para P; e **11% das questões não têm enunciado em texto**,
> só imagem. Três decisões nasceram daí — o "pré-voo: nenhum" abaixo valia
> antes de medir.

> ✅ **É o próximo sprint** (decidido em 29/08). Furou a fila na frente do
> Sprint 3 e do polimento avulso por ser caminho crítico de tudo que vem
> depois — e porque a **P3 pode começar no mesmo dia**, sem esperar a
> classificação: ela só depende do que já está no Postgres.

### Sprint 7 · A jornada do aluno — *5 partes*

O pedido central do áudio: *"como a gente cria uma jornada para o aluno sair de
um D e ir para um A?"* Desenho em [24](24-jornada-do-aluno.md).

| Parte | O quê | Tamanho | Depende de |
|---|---|---|---|
| P1 | **Prioridade pessoal** — `importância × (1 − meu acerto)`, e o gráfico de quadrantes que é a P5 da Sprint 5 aplicada | M | Sprint 6 · P3 + P4 |
| P2 | **Onde estou / para onde vou** — zona atual, distância até o corte, meta do ciclo (`meta_aluno`), linha do tempo de zona | G | destravada: o aluno **vê** a zona, com a distância (29/08) |
| P3 | **Um próximo passo por vez** — o elemento maior da tela, acima do desempenho | M | P1 |
| P4 | **Tio Léo** — o nome, e 5 tools novas (importância, assuntos fracos, plano de revisão, questões do banco por tópico, minha zona) | M | P1. A colisão de nome com a régua foi **assumida de propósito** (29/08) |
| P5 | ~~**Consertar o streak**~~ ✅ **FEITO em 05/09** — `/me/streak` saiu e `/me/jogo` conta simulados sem faltar ([36 §2.3](36-plano-faixa-1-e-2.md)) | P | ✅ |

**Fora de escopo, de propósito:** o RAG dos livros de método de estudo. Exige
`pgvector`, decisão de direito de uso e infra que o projeto não tem — e as
tools da P4 entregam a maior parte do valor conversacional sem nada disso
([24 §5.2](24-jornada-do-aluno.md)).

### O que falta para o aluno usar — *fora do front*

Levantamento de 29/08 em [29-area-do-aluno-o-que-falta.md](29-area-do-aluno-o-que-falta.md).
Nada aqui é tela; tudo é o que impede as telas desenhadas de funcionarem.

| Bloco | O quê | Tamanho |
|---|---|---|
| **A** | ✅ **FEITO em 05/09** ([36](36-plano-faixa-1-e-2.md)), menos `/me/erros`: ela ficou para o Sprint 6 porque `questao.assunto` está 100% vazio e a rota nasceria prometendo "estude por assunto" sem saber o assunto | **M** |
| **B** | As regras que ninguém escreveu: simulado anulado e nota corrigida, virada de ano letivo, quem entra no meio, quem sai, e o `vestibular_alvo_aluno` que nunca foi lido | **M** |
| **C** | **Notificação** — não existe `web/public` nem manifest; o PWA nunca foi feito. Sem isso, sequência, liga e contagem regressiva perdem o gatilho | **G** |
| **D** | Confiança: a **origem da resolução** (o acervo histórico tem resolução gerada por LLM e o aluno vai achar que é do professor) e um canal de suporte | **M** |
| **E** | Onboarding do jogo e estados vazios de verdade | **M** |
| **F** | Trava de 360px, Safari real, testes de DOM | **M** |
| **G** | Backup do Postgres, caminho de eliminação da LGPD, teto de custo do chat | **M** |
| **H** | **Portão:** backtest do XP contra os 5 ciclos de 2026 antes de fixar número | **P** |

### Polimento da coordenação — *PR avulso, não é sprint*

Do mesmo brainstorming, lado coordenação ([25](25-leitura-da-coordenacao.md)).
Quase tudo que o áudio pediu **já estava planejado** (C.2, C.3, D.1, D.2–D.4);
o que é novo é pequeno e não depende de nada:

> **Estado: EM PRODUÇÃO** *(03/09)*. Plano, levantamento e estado
> item a item em [33-plano-polimento-coordenacao.md](33-plano-polimento-coordenacao.md).
> A verificação a 360px no browser achou quatro defeitos de layout na faixa de
> filtros e no dossiê, consertados antes e depois do merge (PRs #34 e #36).
> O levantamento achou **três coisas que mudaram o desenho da proposta**: a
> busca global já existia na topbar, o cartão de decisão estava escrito e
> desligado (`AlertCard` importado por ninguém, e o sino apontando para uma
> âncora inexistente), e o `/banco` só podia adotar a faixa **depois** de ela
> aprender a colapsar.

| O quê | Tamanho | Estado |
|---|---|---|
| Faixa de filtros colapsando quando passa de uma linha, com resumo do ativo, memorizado por superfície | P | ✅ escrito |
| Busca padronizada como grupo da `BarraFiltros` — são **oito** superfícies, não sete, e faltava em **cinco** | P | ✅ escrito |
| `/banco` adotar a `BarraFiltros` — nasceu com sidebar própria e reabriu a dívida que C.1 fechou | M | ✅ escrito |
| Explicar na tela o que é "criar acesso de coordenação" ([25 §3](25-leitura-da-coordenacao.md)) | P | ✅ escrito. O convite por e-mail segue travado na decisão de e-mail transacional |
| Cartão de decisão acima da tabela do Painel — "o que merece atenção hoje" | M | ✅ escrito — era ligar o que já existia |
| Dossiê de ciclo como artefato (texto + gráfico + tabela) | M | ✅ escrito, **com os gráficos** — nenhum dos dois exportadores sabia levar SVG |

### ✅ Sprint Cantina · o cardápio, o pedido e um terceiro tipo de sessão *(05/09)*

> **ESCRITA, fora de produção.** As quatro fases estão no código e verificadas
> fora do browser: 530 testes no backend (+27), 392 no front (+23), portões
> limpos, as três migrations aplicadas no compose e um smoke de 37 passos
> exercitando as três sessões contra a API de verdade. **Falta o deploy e a
> verificação no browser** — a lista do que não foi olhado está em
> [38 §10.2](38-plano-cantina.md), no molde do §6 do docs/37.

Frente **nova**, fora da fila do brainstorming de 29/08: alunos com direito a
alimentação escolhem o prato no painel; a cantina entra por porta própria
(`/login-cantina`), lança o cardápio num calendário e lê os pedidos do dia; a
coordenação administra os dois lados. Plano em
[38-plano-cantina.md](38-plano-cantina.md).

⚠️ **Não é um CRUD a mais.** É o primeiro TIPO de sessão novo desde que o
projeto existe, e [38 §1.1](38-plano-cantina.md) lista os **três** lugares
verificados onde "aluno ou todo o resto" deixa de ser verdade — um deles
(`routes/foto_perfil.py`) daria a uma sessão de cantina acesso de escrita a
`usuario_coordenacao`. Por isso a Fase 0 vai sozinha e com `/security-review`.

| Fase | O quê | Estado |
|---|---|---|
| **0** | O terceiro tipo de sessão: migration 0047, `get_current_cantina`, os três consertos fail-closed, `/login-cantina`, casco próprio | ✅ escrita |
| **1** | O cardápio: migration 0048, calendário de cinco estados, editor de blocos/opções/limites, publicar, copiar-de | ✅ escrita |
| **2** | O direito e o pedido: migration 0049, flag e concessão em lote, card em Hoje e tela `/cantina` do aluno | ✅ escrita |
| **3** | A leitura: duas views agregadas, contagem de produção, lista do balcão, campo no hub, leitura da coordenação | ✅ escrita |

O conserto de `routes/foto_perfil.py` é o item que mais vale ler no diff: até
05/09 ele devolvia a entidade de COORDENAÇÃO para todo tipo que não fosse
aluno, e a premissa ("só existem dois tipos") era verdadeira até deixar de
ser. `test_cantina.py` tranca os cinco guards para que nenhum deles volte a ser
um `else`.

> **Dez decisões fechadas em 05/09** ([38 §8.0](38-plano-cantina.md)): o
> **prazo do pedido é definido pela cantina**, não pelo sistema (regra padrão da
> casa + prazo por dia, absoluto); **quem não pediu não come**; **conceder o
> direito é só do administrador**, o que trouxe a concessão em lote para dentro
> do escopo; o direito é **flag pura**, sem vigência; **nada entra depois do
> prazo, nem pela cantina**; o aluno vê **todos os dias já publicados** (teto de
> 30); **não há lembrete**; almoço e janta são **cardápios diferentes**; a
> **restrição alimentar é registrada** (`aluno.restricao_alimentar`, preenchida
> pela coordenação, visível só à cantina); e o escopo é **só as turmas
> ITA/IME** — verificado no código, e não por suposição: `aluno` tem um único
> escritor, o sync só enxerga o curso `{ano} 3o ITA/IME Simulados`, e o SSO do
> Canvas não cria aluno nenhum. **Nada mais trava código.**
>
> ⚠️ As três últimas se somam a um preço registrado em [38 §7](38-plano-cantina.md):
> sem prato padrão, sem exceção no balcão e sem lembrete, **o aluno que esquecer
> fica sem almoço e o sistema não terá avisado**. Escolha de simplicidade
> consciente — e a primeira a revisitar se aparecer reclamação.
>
> [38 §9](38-plano-cantina.md) responde ao tempo real (cardápio aparecendo sem
> refresh): o caminho de SSE já está aberto de ponta a ponta neste projeto — o
> nginx e o parser do cliente existem por causa do chat, e `UVICORN_WORKERS=1`
> dispensa `LISTEN/NOTIFY` —, mas a recomendação é `refetchOnWindowFocus` +
> polling autodesligável no v1, porque o cardápio é publicado horas antes.

⚠️ `pedido_refeicao_item` é a primeira tabela que cresce por *dia × aluno ×
item* — 160 mil a 1,4 milhão de linhas no primeiro ano, num sistema **sem
paginação em lugar nenhum** (CLAUDE.md, armadilha 2). A contagem de produção
nasce como view agregada, não como soma em Python ([38 §2.4](38-plano-cantina.md)).

**Total à frente: 7 sprints, 34 partes + as 4 fases da cantina**, mais o polimento avulso de 6 itens.

---

## 3.9 · A área do aluno · front escrito, backend pendente *(30/08)*

**Escrito, fora de produção.** Treze rotas novas no front, dois temas, sub-marca
própria. **Nenhuma rota da API mudou** — e essa é a característica do sprint.

O estado real, fonte por fonte, está em
[30-estado-da-implementacao.md](30-estado-da-implementacao.md), **gerado de
`web/src/dados/aluno/registro.ts`**. Resumo:

| | |
|---|---|
| **LIGADO** | 28 fontes — o endpoint existe e a tela consome |
| **DADO EXISTE, ROTA NÃO** | 1 — `meusErros`, segurada até o Sprint 6 |
| **MOCK PURO** | 11 — não existe nem dado |

Três rotas prontas e sem tela desde sempre ganharam uma ([29 §A.5](29-area-do-aluno-o-que-falta.md)):
`/me/trajetoria`, `/me/heatmap` e `/me/simulado/{id}/arquivo`.

### ✅ Faixa 1 e Faixa 2 entregues *(05/09)* — [36](36-plano-faixa-1-e-2.md)

Entraram `/me/agenda`, `/me/jogo`, `/me/zona`, `/me/meta`,
`/me/simulados?incluirFaltas` e o onboarding (`GET/PUT /me/vestibulares` +
tela + portão), que a decisão da régua obrigou: `vestibular_alvo_aluno` existe
desde a 0001 e nunca teve quem escrevesse nela. **`/me/streak` SAIU**, e o tool
`meu_streak` do Tio Léo foi repontado para `/me/jogo`. A fórmula do Tio Léo saiu
do mock sem dependência nova — o KaTeX já estava no projeto.

⚠️ **A medição do banco derrubou três premissas do docs/30** (§0 do 36):
`nota.presente` tem 58,7% de falta e mistura ausência com "esta prova nunca foi
minha"; `evento_agenda` tem 1 evento futuro no ano inteiro; e `questao.assunto`
está 100% vazio — por isso `/me/erros` **ficou de fora** e volta no Sprint 6.

**O que falta, em ordem de esforço:** o backtest do XP, que é portão → o
Sprint 6 → notificação → Liga e Esquadrilha.

**Buracos conhecidos** (lista inteira na última seção do docs/30): quatro telas
não foram vistas rodando; o mapa de calor nasce 98,3% vazio porque o eixo real é
simulado e não ciclo; o extrato ignora o `:id`; e em produção não existe marca
de placeholder — a tarja MOCK só aparece em desenvolvimento.


### ✅ Refatoração visual da coordenação *(05/09)* — [37](37-plano-refatoracao-visual-coordenacao.md)

O sistema de design que só a área do aluno tinha foi estendido à coordenação,
em dez PRs, e o **padrão de campo** chegou às telas que empilhavam perguntas
diferentes numa rolagem só.

O que mudou de propósito: o semáforo verde/âmbar/vermelho saiu da tela inteira
(preenchido é acima do corte, vazado é abaixo, a intensidade carrega a
distância, o vermelho fica só na etiqueta e na falha); toda tabela de aluno
abre por **distância do corte**, com o ordenador nomeado; Administração virou
quatro campos e a ficha de ciclo, três; o Painel ganhou a faixa de entrada e
perdeu dois estratos por fusão; a ficha do aluno ganhou coluna lateral de
320px com a barra de corte do aluno reusada; e **passou a existir tema
escuro**.

Duas URLs novas, com as antigas ainda válidas: `/administracao/contas` e
`/ciclos/:id/{calibracao,regua,comparacao}`.

⚠️ **Nada foi visto rodando no browser** — a verificação exigia login de
coordenação e não houve sessão. Contraste no tema escuro, layout a 390px e o
dossiê antes/depois **não foram verificados**. A lista inteira está no §6 do
[37](37-plano-refatoracao-visual-coordenacao.md), e ela é o que precisa
acontecer antes do deploy.

⚠️ **Três coisas ficaram pela metade, de propósito** (§7 do 37): a comparação
de ciclo por sede e por turma (falta recorte no endpoint), a tarja de
procedência unificada (um PR próprio, quatro componentes em dois produtos), e
o Banco, que continua construído duas vezes — só que agora **sem a razão que
justificava**, porque os dois cascos passaram a ler os mesmos papéis.

De brinde, o PR 0 zerou 96 erros de ruff e 8 do Biome que estavam na `main`, e
que faziam "portão verde" não significar nada.


## 4 · Decisões em aberto

| Decisão | Trava | Quem decide |
|---|---|---|
| **WhatsApp é só lembrete, ou canal completo** (professor anexa o arquivo no WhatsApp e o sistema relaciona ao simulado)? | Sprint 3 inteira: P1 e P4 se desenham diferente | Yan + coordenação |
| Frequência da cobrança de professores (diária? a cada 3 dias?) | Sprint 3 · P2 | coordenação |
| Regra de "zero = provável ausência" — **metade fechada em 03/09**: o Problema A (não marcou nada) está em produção, derivado de evidência direta. Falta só o aval das **8 provas de 2023** do Problema B, prova a prova ([32 §1](32-plano-sprint-4.md)) | Sprint 3 · P3 | coordenação |
| **Busca é da tela ou global (`⌘K`)?** | Polimento | Yan + coordenação |
| **Papéis dentro da coordenação** — hoje todo mundo pode tudo, inclusive criar acesso e ler auditoria | Polimento | coordenação |
| **Servidor MCP do SAS para uso fora da plataforma?** Expõe dado de menor a cliente fora da nossa infra | — | Yan + LGPD |
| **Parecer de LGPD sobre a Esquadrilha** — um menor compartilhando desempenho com outro, por escolha própria | Esquadrilha | Yan + LGPD |
| **Temporada:** o que zera na virada do ano letivo (XP, liga, esquadrilha) | Sprint 7 | Yan + coordenação |
| **Simulado anulado e nota corrigida:** estorna XP? A liga já fechada muda? | arquitetura do XP | Yan |

### 4.1 · Fechadas em 29/08

| Decisão | Resposta | Destravou |
|---|---|---|
| Qual é o próximo sprint | **Sprint 6 — o assunto entra no simulado** | a fila inteira |
| O aluno vê a própria zona? | **Sim, e com a distância até a próxima** — o rótulo nunca aparece sem a distância e sem a régua que o produziu | Sprint 7 · P2 |
| "Tio Léo" vs. a régua "Tio Leo" | **Assumir a colisão** — é a mesma pessoa. Convenção interna: *"a régua do Tio Leo"* para o critério, *"o Tio Léo"* para o bot | Sprint 7 · P4 |
| Meia-vida do índice de importância | **5 anos, fixa para todos.** Parâmetro num lugar só, não constante espalhada | Sprint 6 · P3 |
| Português, Inglês e Redação na análise por assunto | **Fora.** Cobre só Mat/Fís/Quím, e **a tela é obrigada a dizer quais matérias cobre** — um plano de revisão que ignora Inglês em silêncio é pior que nenhum | Sprint 6 · P2 |
| O que a gamificação pode premiar | **Só o verificável** — sequência de simulados sem faltar, XP a partir da nota e da régua de corte, progresso contra si mesmo na tabela. Especificação em [26](26-mecanicas-do-jogo.md) | Sprint 7 |

---

## 5 · Dívida técnica — *PR avulso, qualquer hora*

| O quê | Por quê | Tamanho |
|---|---|---|
| **Backup do Postgres** | [14 §7](14-plano-producao.md) dispensou backup contínuo porque "o Canvas é o arquivo". O banco de questões é o primeiro dado que ele **não** restaura — e as imagens só existem no S3. Duas cópias únicas | M |
| Renomear `get_supabase()` → `get_postgrest()`, `supabase_client.py` e as 33 anotações `Client` → `ClienteDados` | o nome mente desde 13/08; e é o que destrava o mypy como gate (72 dos 109 erros são isso) | M, mecânico |
| `ShellAluno` redireciona o logout para `/login.html` (rota não existe; é `/login`) | resquício da migração React | P |
| `web/dist/` versionado? conferir `.gitignore` | — | P |
| README.md ainda descreve Vercel/Supabase/8 migrations | mente desde 13/08 | P — corrigido parcialmente em 22/08 |

---

## 6 · Como manter este documento

- Terminou uma parte: marca ✅ na tabela e a data.
- Abriu sprint: move a proposta de [§3](#3--próximos-ciclos--proposta) para [§1](#1--em-produção-hoje-portalsasonline) quando for pro ar, não antes.
- Decisão tomada: sai de [§4](#4--decisões-em-aberto) e entra como nota na parte que destravou.
- Não duplicar o *porquê*: isso mora nos planos (`11`–`13`, `18`). Aqui é só estado.
