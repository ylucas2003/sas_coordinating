# 19 — Roadmap · o que foi feito, o que falta, o que vem

> **Este é o documento de estado.** Os outros (`10`, `11`–`13`, `18`, `23`)
> contam *por que* e *como*; este diz só *onde estamos*. Quando divergirem,
> corrija aqui primeiro — é o que se lê antes de qualquer sprint.
>
> Atualizado em **24/08/2026**, depois do deploy que juntou o redesenho do
> casco, a SPRINT FOTO e o acervo histórico do banco de questões — ver §9.8
> de [23-banco-questoes-historico.md](23-banco-questoes-historico.md) pra
> como isso quase saiu errado (checkout desatualizado, importador sem
> acesso aos JSONs dentro do container).

---

## 1 · Em produção hoje (`portalsas.online`)

Tudo abaixo está no `main` e no ar. Migrations aplicadas: **0001 → 0032**.
Testes: **165** no backend, **142** no front.

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

### Sprint Redesenho do casco *(23/08)*

Rail de ícones no lugar da topbar de 7 abas, migalhas, faixa de filtros
horizontal, Ciclos+Simulados fundidos em `/provas`. Plano em
[23-plano-redesenho-casco.md](23-plano-redesenho-casco.md).

| Parte | O quê | Estado |
|---|---|---|
| P1 | Tokens — paleta do canvas, cinza azulado, âmbar separado em traço e texto | ✅ |
| P2 | Casco — rail, topbar com migalhas, barra inferior no celular | ✅ |
| P3 | Telas — `BarraFiltros`, `/provas`, abas de Administração | ✅ |
| P4 | Polimento tela a tela, com o browser aberto | ⏳ **não feito** — foi pro ar sem essa checagem, ver §1.5 |

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

### Blocos B, C, D do [docs/10](10-problemas-e-visao.md) — o que já caiu no caminho

| Item | Estado | Onde |
|---|---|---|
| B.2 Write-back de notas no Canvas | ✅ refeito na Sprint 2 (com escolha do coordenador) | [18 §2.4](18-plano-sprint-2.md#24-nota-sempre-o-canvas--alterações-do-sas) |
| C.1 Componente único de filtro | ✅ | `BarraFiltros.tsx` — era `PainelFiltros.tsx` (lateral) até o redesenho de [23](23-plano-redesenho-casco.md) |
| C.4 Ordenação por cabeçalho | ✅ | `TabelaOrdenavel.tsx` |

---

## 1.5 · Escrito mas **não em produção**

### Publicação automática de aulas no YouTube *(27/08)*

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
| Publicar no YouTube como *não listado* | ✅ comprovado com vídeo de teste |

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

**Pendente para ir a produção:** preencher `AWS_*`, `S3_BUCKET_GRAVACOES` e
`YOUTUBE_*` no `infra/vps/.env`, e instalar o `crontab-sas` atualizado. A
imagem da API passou a incluir `ffmpeg` (~250 MB) — o build de produção fica
maior.

> ⚠️ **Foi pro ar com um blocker conhecido não resolvido**: o sino da topbar
> aponta para `/painel#alertas`, e esse id não existe em `Painel.tsx` —
> confirmado ainda ausente em 24/08, na hora do deploy. Clicar no sino não dá
> erro, só não rola pra lugar nenhum. Documentado aqui antes desse deploy
> como "bloqueia o deploy" ([23-plano-redesenho-casco.md §8](23-plano-redesenho-casco.md#8--o-que-falta--p4)
> · item 3) e foi pro ar assim mesmo — decisão de escopo do usuário
> ("tudo que está na árvore hoje"), não descuido. Conserto pequeno: um
> `id="alertas"` em algum bloco de `Painel.tsx`.

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

### Sprint 4 · Dado e leitura — *6 partes*

| Parte | O quê | Origem |
|---|---|---|
| P1 | B.3 Zero × ausência nas estatísticas | docs/10 |
| P2 | B.4 Precedência entre ingest de planilha e sync do Canvas | docs/10 |
| P3 | C.2 Split ano / vestibular / ciclo no Painel | docs/10 |
| P4 | C.3 Range de período em Ciclos | docs/10 |
| P5 | Corte na Fase 1 via `classificacao_aluno.zona` — unificar `thresholds.py` com `criterios.py` (A5) | Sprint 2, Onda 3 |
| P6 | Envio em lote ao Canvas — "enviar N pendências do ciclo" (C5) | Sprint 2, Onda 3 |

### Sprint 5 · Assistente e gráficos em camadas — *5 partes*

| Parte | O quê | Origem |
|---|---|---|
| P1 | D.1 Painel não-modal | docs/10 |
| P2 | D.4 Consciência de rota (chat ↔ página) | docs/10 |
| P3 | D.2 + D.3 Apresentação da abertura; lacunas de tools | docs/10 |
| P4 | **UI de critérios do coordenador** — o formato da Sprint 2 já nasceu pronto; falta a tela (A7) | [18 §1.10](18-plano-sprint-2.md#110-futuro-critérios-criados-pelo-coordenador) |
| P5 | Gráficos em camadas: leigo → insight → estatística | visão de produto |

**Total à frente: 3 sprints, 15 partes.**

---

## 4 · Decisões em aberto

| Decisão | Trava | Quem decide |
|---|---|---|
| **WhatsApp é só lembrete, ou canal completo** (professor anexa o arquivo no WhatsApp e o sistema relaciona ao simulado)? | Sprint 3 inteira: P1 e P4 se desenham diferente | Yan + coordenação |
| Frequência da cobrança de professores (diária? a cada 3 dias?) | Sprint 3 · P2 | coordenação |
| Regra de "zero = provável ausência" (limiar) | Sprint 3 · P3 | coordenação |

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
