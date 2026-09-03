# 33 — Polimento da coordenação · plano

> **Origem:** o bloco **AVULSO** de [sprints.html](sprints.html) e o
> [25-leitura-da-coordenacao.md](25-leitura-da-coordenacao.md), que por sua vez
> vem dos áudios do Yan de 29/08/2026. **Não é sprint:** são seis PRs avulsos,
> independentes o bastante para entrar entre sprints, e nenhum deles trava o
> Sprint 6.
>
> O documento de estado é [19-roadmap.md](19-roadmap.md). Este aqui diz *como*.

---

## 0 · O levantamento (30/08) — o que o código diz e os documentos não

Antes de planejar, o mesmo exercício que a Sprint 5 fez e que rendeu duas
partes já prontas ([31 §0](31-plano-sprint-5.md)). Aqui rendeu seis achados, e
**três deles mudam o desenho da proposta.**

### 0.1 · A busca global já existe — e ninguém registrou

[`componentes/layout/Topbar.tsx`](../web/src/componentes/layout/Topbar.tsx)
tem uma busca de alunos **em toda tela da coordenação**, com atalho de teclado
`/`, navegação por seta, e que leva direto para `/alunos/:id`. Ela carrega a
lista sob demanda (`useAlunos({ habilitada })`) justamente para não pesar o
boot.

O inventário do [25 §1.1](25-leitura-da-coordenacao.md) não a viu, e por isso a
decisão em aberto *"a busca é da tela ou é global (⌘K)?"* está mal colocada:
**a global já está no ar há tempo.** O que não existe é a busca **de conteúdo
da tela** — filtrar as linhas que estão na frente do coordenador — e é só isso
que o item 2 precisa entregar.

> Consequência: o item 2 encolhe e a decisão 2 do [25 §5](25-leitura-da-coordenacao.md)
> vira quase formalidade. O `⌘K` que sobra é "busca global de **outras coisas**
> além de aluno" — ciclo, simulado, questão — e isso é outro produto, para
> outro dia.

### 0.2 · O cartão de decisão já está escrito, e está desligado

O item 5 é o de maior valor da lista e o mais adiantado sem que ninguém saiba:

| Peça | Onde | Estado |
|---|---|---|
| Motor de 7 regras | [`api/app/stats/alertas.py`](../api/app/stats/alertas.py) | ✅ no ar, roda de hora em hora (`7 * * * *`, `infra/vps/crontab-sas`) |
| `GET /alertas` (severidade ordenada, dedup por hash) | [`api/app/routes/alertas.py`](../api/app/routes/alertas.py) | ✅ |
| `POST /alertas/{id}/resolver` | idem | ✅ |
| `useAlertas()` / `useResolverAlerta()` | `web/src/hooks/consultas.ts` · `mutacoes.ts` | ✅ |
| `AlertCard.tsx` — "componente central do Painel" | `web/src/componentes/ui/` | ✅ escrito e **importado por ninguém** |
| A faixa no Painel | — | ❌ **é isto que falta** |

E há um cabo solto visível: **o sino da topbar aponta para `/painel#alertas`**,
âncora que não existe em tela nenhuma. Hoje o botão de alertas leva ao Painel e
não mostra alerta.

A ironia que fecha o achado: o **assistente** sabe listar alertas — a tool
`listar_alertas` existe em [`chat/tools/contexto.py`](../api/app/chat/tools/contexto.py).
Quem não sabe mostrá-los é a tela.

> Consequência: o item 5 deixa de ser "construir o cartão de decisão" e passa a
> ser **ligar o que existe, curar o recorte e consertar o sino**. Continua M,
> mas por causa da curadoria, não do código.

### 0.3 · São oito superfícies de filtro, não sete

O inventário do [25 §1.1](25-leitura-da-coordenacao.md) tem sete linhas. O
código tem oito — falta `/integracoes/aulas`
(`SincronizacaoAulas.tsx`, grupos *Curso* e *Situação*). E `/provas` é **uma
rota com duas superfícies**: `Ciclos` e `Simulados` montam cada uma a sua
`BarraFiltros`, conforme a aba de `?aba=`.

| Superfície | Grupos | Busca? |
|---|---|---|
| `/painel` | Ciclo · Sede · Turmas | sim, **fora** da faixa |
| `/alunos` | Turma · Sede | **não** |
| `/provas` → Ciclos | Vestibular · Ano letivo · Período | **não** |
| `/provas` → Simulados | Vestibular · Fase · Ciclo · Disciplina | **não** |
| `/auditoria` | Canal · Incluir também | **não** |
| `/administracao` | Primeiro acesso · Buscar | sim, **dentro** da faixa |
| `/integracoes/aulas` | Curso · Situação | **não** |
| `/banco` | Matéria · Vestibular · Fase · Ano · Assunto | sim, `<aside>` próprio |

Ou seja: a busca de tela falta em **cinco**, não em quatro. E a memória do
item 1 tem de ser por **superfície** (`provas.ciclos` ≠ `provas.simulados`), não
por rota — senão as duas abas de Provas dividem um estado e uma delas abre
errada.

### 0.4 · O item 3 contradiz uma decisão registrada — e só o item 1 a desfaz

O cabeçalho de [`telas/Banco/Banco.tsx`](../web/src/telas/Banco/Banco.tsx) diz,
com fonte:

> *"O resto da coordenação usa a `.barra-filtros` horizontal; aqui não, porque
> são muitos assuntos por edital e eles não caberiam numa linha (docs/22 §3.5)."*

Não é esquecimento: é decisão escrita, e ela está **certa enquanto a faixa não
colapsar**. Some-se a isso o que o CSS mostra:

- `.banco-filtros` é **mobile-first** (`@media (min-width: …)`), gruda a partir
  de 880px, rola sozinha e limita a altura em `100dvh` — ou seja, uma árvore
  longa de assuntos cabe.
- `.barra-filtros` **não tem uma única regra de celular.** Nenhuma media query
  a menciona em `styles/`.

Trocar uma pela outra hoje **regride** a aba que foi verificada a 390 e 360px
([19 §1](19-roadmap.md), Sprint Banco · P3).

> Consequência: **o item 3 depende do item 1**, e essa dependência não é de
> conforto — é de não quebrar o que está no ar. O item 3 vai por último.

### 0.5 · O dossiê tem casa melhor que o chat

O item 6 pede "texto, gráfico e tabela num documento que se salva". A
[`CicloFicha`](../web/src/telas/CicloFicha/CicloFicha.tsx) já desenha
exatamente isso: hero de KPIs, evolução temporal, **leitura do LLM em
linguagem acessível** (`InsightsPainel`, cache por hash em `insight_ciclo`),
histogramas por matéria, tabela de simulados e o bloco estatístico avançado.

O que falta não é reunir conteúdo — é **tirá-lo da tela em papel**. E o projeto
tem dois motores de exportação, com mecânicas diferentes:

| Motor | Como | Word? | Gráfico? |
|---|---|---|---|
| `src/exportacao/` (ficha do aluno) | monta o nó **no documento atual**, marca `body.imprimindo-panorama`, `window.print()` | não | heatmap em HTML; e há `exportarPNGGrafico` (SVG→canvas) |
| `telas/Banco/exportar.ts` (lista de questões) | `window.open('')`, estilo por **CSSOM** (a CSP é `style-src 'self'`), `.doc` por Blob | **sim** | não |

O sprints.html diz que "o exportador de PDF/Word do banco é o mesmo motor" —
verdade quanto ao Word, mas **nenhum dos dois sabe levar um SVG junto**. É aí
que mora o trabalho do item 6. A boa notícia é que a CSP de produção permite
`img-src 'self' data: blob:` (`infra/vps/nginx.conf`), então rasterizar o
gráfico e embutir como `data:` **funciona** — o caminho já existe em
`exportarPNGGrafico`.

### 0.6 · A recusa que "não ensina" já é uma frase — falta reescrevê-la

O item 4 pede "uma recusa que ensine o que fazer". Ela existe:
`auth_canvas.py` redireciona para `/login?canvas=sem-conta` e
[`Login.tsx`](../web/src/telas/Login/Login.tsx) responde *"Sua conta do Canvas
não está cadastrada no SAS. Procure a coordenação."*

Não é ausência, é redação. E o resto do item 4 (o parágrafo antes do botão de
criar) também está pela metade: o `NovaConta` já traz *"Use o mesmo e-mail do
Canvas…"* como legenda de campo.

> Consequência: o item 4 se parte em **4a — redação, sem decisão nenhuma
> travando** e **4b — o convite por e-mail, travado**.

---

## 0.7 · Estado da execução *(03/09/2026)*

**Os seis escritos**, depois da Sprint 4. Localmente verdes: **322 testes** no
front (eram 294) e **358** na API; `tsc`, Biome e `npm run build` limpos, e o
Biome saiu de 9 erros de baseline para 8.

| PR | Item | Estado | O que ficou de pé |
|---|---|---|---|
| 1 | Faixa colapsa | ✅ | `dominio/filtros.ts` + teste, `memoria.ts`, medição por quebra de linha, e a **primeira regra de celular** que `.barra-filtros` teve |
| 2 | Cartão de decisão | ✅ | `FaixaDecisao.tsx`, `contarDecisoes` + `alertasDoRecorte` testados, `AlertCard` finalmente montado, âncora `#alertas`, e o alerta passou a dizer `entidadeTipo`/`entidadeId` |
| 3 | Busca num lugar só | ✅ | `<Busca>` na `BarraFiltros`, nas **oito** superfícies; a do Painel saiu do cabeçalho, a da Administração trocou de dono |
| 4 | Dossiê de ciclo | ✅ | `CicloFicha/dossie.ts` — PDF e Word, **com os gráficos** (SVG → canvas → `data:`) |
| 5 | Explicar o acesso (4a) | ✅ | Parágrafo antes de "Nova conta", a recusa que ensina, e o que a senha sorteada é e não é |
| — | Convite por e-mail (4b) | ⬜ **travado** | Espera a decisão "coordenação recebe e-mail transacional?" |
| 6 | `/banco` na `BarraFiltros` | ✅ | Árvore de assuntos em painel; `<aside>` e o grid de duas colunas removidos; docs/22 §3.5 corrigido |

**Um bug encontrado e consertado no caminho:** `_href_para_entidade` manda o
alerta de turma/sede para `/alunos?turmaId=X`, e `Alunos.tsx` **nunca leu essa
query** — o link caía numa lista sem filtro. Resíduo do hash router anterior à
migração React.

⬜ **Falta a verificação visual** — Painel a 1440 e a 390/360, faixa colapsada,
painel de assuntos, dossiê impresso **em produção** (a CSP do dev é mais
frouxa). O perfil do MCP `chrome` esteve tomado por outra sessão o tempo todo.

⬜ **Falta decidir** se a busca de `/auditoria` deve ir ao servidor: hoje ela
peneira as páginas já carregadas, e o rótulo do grupo diz isso em voz alta.

---

## 1 · A ordem

| PR | Item | O quê | Tam. | Depende de | Decisão que trava |
|---|---|---|---|---|---|
| **1** | 1 | A faixa de filtros colapsa quando passa de uma linha | **P** | — | nenhuma (o texto da proposta já decide) |
| **2** | 5 | Cartão de decisão no Painel + o sino que aponta para lugar nenhum | **M** | — | nenhuma |
| **3** | 2 | A busca de tela num lugar só, nas oito superfícies | **P** | PR 1 (usa a API de grupo) | nenhuma, depois do §0.1 |
| **4** | 6 | Dossiê de ciclo como artefato | **M** | — | nenhuma |
| **5** | 4a | Explicar o acesso de coordenação | **P** | — | nenhuma |
| — | 4b | Convite por e-mail em vez de senha sorteada | M | PR 5 | **sim** — coordenação recebe e-mail transacional? |
| **6** | 3 | O `/banco` adota a `BarraFiltros` | **M** | **PR 1 + PR 3** | nenhuma |

Os PRs 1, 2, 4 e 5 são independentes entre si: podem sair em qualquer ordem, ou
em paralelo. O 3 só precisa que o 1 tenha desenhado a API de grupo, e o 6 é o
último de propósito (§0.4).

**Recomendação de ordem de valor:** PR 2 primeiro se o objetivo for o que o
coordenador nota; PR 1 primeiro se for o que ele reclama. Os dois são baratos.

---

## 2 · PR 1 — a faixa que cabe *(item 1, P)*

### O que muda

`BarraFiltros` ganha três coisas: saber se transbordou, um resumo do que está
ativo, e memória por superfície.

- **Aberta por padrão.** A regra do comentário de cabeçalho continua valendo —
  "o custo de esconder um filtro é o usuário não saber que ele existe".
- **Colapsa quando o conteúdo passa de uma linha**, e não antes. Colapsar tudo
  por padrão é voltar ao `PainelFiltros` lateral que o redesenho do casco tirou
  ([23-plano-redesenho-casco.md](23-plano-redesenho-casco.md)).
- **Colapsada, mostra o resumo do ativo**: `Ciclo 4 · ITA · 2026 · 2 turmas`.
  É o resumo que impede o pior resultado possível deste PR — um filtro em vigor
  que o usuário não enxerga e não sabe desmarcar.
- **Memória por superfície**, em `localStorage` (precedente:
  `telas/Aluno/pecas/tema.ts`). Preferência de UI, sem dado pessoal — a regra 6
  do `CLAUDE.md` não é tocada.

### Desenho

```
interface GrupoFiltro {
  chave: string;
  rotulo: string;
  corpo: ReactNode;
  resumo?: string | null;   // NOVO — null/ausente = nada ativo neste grupo
}

<BarraFiltros tela="painel" grupos={…} onLimpar={…} algumAtivo={…} />
```

O **resumo é declarado pela tela**, não deduzido do `corpo`: só a tela sabe que
`turmaIds.size === 2` se escreve `2 turmas` e que o ciclo se abrevia para `4`.
A junção, a pluralização e a ordem viram função pura em
`web/src/dominio/filtros.ts`, com teste ao lado — é a régua do
[web/CLAUDE.md](../web/CLAUDE.md) ("regra de negócio vai para `src/dominio/`").

### ⚠️ A armadilha: o laço de medição

Detectar "passou de uma linha" com `ResizeObserver` sobre o container **oscila**:
mede aberto → transbordou → colapsa → agora cabe → expande → transbordou. Laço
infinito que o React não acusa.

Duas defesas, ambas necessárias:

1. **A medição é da quebra de linha, não da altura.** Com `flex-wrap`, o teste
   exato é `grupo.offsetTop > primeiroGrupo.offsetTop` para algum grupo — sem
   número mágico e sem depender de `padding`.
2. **Só se mede no estado aberto.** Colapsado, o valor medido é congelado; a
   remedição acontece no `resize` do container e ao expandir.

### Arquivos

| Arquivo | O quê |
|---|---|
| `web/src/componentes/ui/filtros/BarraFiltros.tsx` | `resumo`, `tela`, botão de expandir, hook de medição |
| `web/src/dominio/filtros.ts` + `.test.ts` | **novo** — `resumirFiltros(grupos)` |
| `web/styles/layout.css` | estado colapsado; **e a primeira regra de celular que `.barra-filtros` terá** |
| 8 chamadas | passar `tela` e `resumo` por grupo |

### Pronto quando

- A 1440px o Painel abre com a faixa **colapsada** (Sede + Turmas não cabem numa
  linha) e as outras sete abrem **abertas**.
- A 390 e 360px praticamente todas colapsam — e é o ganho maior do PR.
- Recarregar a página preserva o estado da superfície; `/provas?aba=simulados`
  não herda o de `/provas`.
- `aria-expanded` no botão, região com `id` e o "Limpar filtros" alcançável nos
  dois estados.

---

## 3 · PR 2 — o cartão de decisão no Painel *(item 5, M)*

### O que muda

Uma faixa **acima** da tabela do Painel, com `id="alertas"` — o destino que o
sino da topbar já promete e não cumpre (§0.2). A tabela **fica**: é a tela de
varrer 900 pessoas, e cartão não compara 900 linhas ([25 §2](25-leitura-da-coordenacao.md)).

Duas camadas, e a primeira não custa requisição nenhuma:

1. **Contagens do recorte em vigor** — quantos abaixo do corte, quantos mudaram
   de zona, quantos sem nota no ciclo. Tudo isso já chega em
   `useClassificacaoCiclo` e já está na memória do `Painel.tsx`.
2. **Os alertas**, do `useAlertas()` que ninguém chama, desenhados pelo
   `AlertCard` que ninguém importa. Ordenados por severidade (o servidor já
   ordena), três visíveis, "ver todos" abre o resto, "Resolver" liga no
   `useResolverAlerta()`.

### A pergunta de desenho que precisa de resposta na hora de escrever

Os alertas são **globais**; a tabela abaixo deles está **filtrada** por ciclo,
sede e turma. Uma faixa que diz "3 alunos em queda" sobre uma tabela de uma
turma só é uma mentira de contexto.

**Decisão proposta:** a faixa respeita o recorte do Painel — alerta de aluno
some se o aluno não está no recorte — e, quando algo foi escondido, a faixa
**diz**: `+4 fora do recorte atual`. Esconder em silêncio é a armadilha 2 do
`CLAUDE.md` em outra roupa (número errado sem parecer errado).

### 🐛 Um bug que este PR encontra de graça

`_href_para_entidade` ([`routes/alertas.py`](../api/app/routes/alertas.py))
devolve `#/alunos?turmaId={id}` para alerta de turma e `#/alunos?sedeId={id}`
para sede. **`Alunos.tsx` não lê nenhum dos dois** — os filtros moram em
`useState`, e o link cai numa lista sem filtro. É resíduo do hash router
anterior à migração React.

Conserto barato, e é pré-requisito de "Ver detalhes" significar alguma coisa:
`Alunos.tsx` lê `turmaId`/`sedeId` da query no primeiro render. (O `AlertCard`
já tira o `#`.)

### Arquivos

| Arquivo | O quê |
|---|---|
| `web/src/telas/Painel/FaixaDecisao.tsx` | **novo** — as duas camadas |
| `web/src/telas/Painel/Painel.tsx` | monta a faixa acima do `kpi-grid` |
| `web/src/dominio/painel.ts` + teste | contagens derivadas da classificação |
| `web/src/telas/Alunos/Alunos.tsx` | lê `turmaId`/`sedeId` da query |
| `web/styles/painel.css` | a faixa |

### Pronto quando

- O sino leva a `/painel#alertas` e **para em cima de alertas**.
- Resolver um alerta o remove sem recarregar (o `invalidateQueries` já existe).
- Nenhum alerta some sem a faixa dizer quantos sumiram.
- A faixa não empurra a tabela para fora da dobra a 390px — no celular ela nasce
  com um cartão e um "ver todos".

---

## 4 · PR 3 — a busca num lugar só *(item 2, P)*

### O que muda

Depois do §0.1, o item é só isto: **a busca de conteúdo da tela vira um grupo da
`BarraFiltros`, nas oito superfícies.** A busca global da topbar não se mexe —
mas passa a estar **escrita** em `web/CLAUDE.md`, que é o motivo de ela ter
sumido do inventário.

- Novo corpo de grupo `Busca` em `BarraFiltros.tsx`, ao lado de `Pills`,
  `PillsUnica` e `RangeDatas` — `<input type="search">` sobre `.pill-campo`,
  com `aria-label` e ícone.
- **Painel:** sai de `painel-header__controles` e entra na faixa. `.painel-busca*`
  morre com ele.
- **Administração:** já é grupo — troca a mão pelo componente.
- **Entram** em `/alunos`, `/provas` (as duas abas), `/auditoria` e
  `/integracoes/aulas`.
- **Banco:** fica como está neste PR; muda no PR 6.

O que cada tela procura precisa ser dito no `placeholder`, não adivinhado. O
caso menos óbvio é `/auditoria` — proposta: **ator e recurso**, e o placeholder
diz isso.

### Detalhe que separa este PR do Banco

As sete da coordenação filtram **no cliente**, sobre listas já carregadas
(`normalizar()` de `util/formato.ts`, que já existe): sem debounce, sem
requisição. O Banco filtra **no servidor**, com 350ms de espera, porque a
listagem é paginada. O componente aceita `espera?: number` para servir aos dois
sem que a coordenação pague latência que não tem.

---

## 5 · PR 4 — o dossiê de ciclo *(item 6, M)*

### O que muda

Um botão **Exportar dossiê** na `CicloFicha`, PDF e Word, com o que a tela já
mostra (§0.5): identificação e período, os KPIs do hero, a leitura do LLM, a
evolução, o recorte por matéria e a tabela de simulados.

**Não começa pelo chat**, e por dois motivos: o coordenador já está na ficha
quando quer o documento, e o dossiê não precisa de LLM nenhum para existir — os
insights já vêm cacheados de `GET /ciclos/{id}/estatisticas?com_insights=true`.
O chat entra depois, e barato: a tool `navegar_para` (Sprint 5 · P2) já sabe
levar a pessoa até a ficha.

### O trabalho de verdade: o gráfico dentro do documento

O motor do Banco (`window.open` + CSSOM + `.doc`) é o certo — é o único que faz
Word. O que ele não faz é levar SVG. Caminho:

1. Serializar o `<svg>` que já está na árvore (`refGrafico.current.querySelector('svg')`),
   como `exportarPNGGrafico` faz hoje.
2. Rasterizar num `canvas` e embutir como `data:` URI. **A CSP de produção
   permite** (`img-src 'self' data: blob:`), o que torna esse caminho viável no
   PDF *e* no `.doc` — no Word, um `data:` URI dispensa rede na primeira
   abertura, ao contrário das imagens do S3 da lista de questões.
3. O estilo continua por CSSOM. `style-src` é `'self'`, sem `unsafe-inline`, e
   atributo inline é descartado **em silêncio**.

> ⚠️ **Testar em produção, não só no dev** — a CSP do dev é mais frouxa. Foi a
> armadilha do gerador da lista ([22 §8, risco 7](22-plano-banco-questoes.md)) e
> do gerador da ficha do aluno antes dela.

### Arquivos

| Arquivo | O quê |
|---|---|
| `web/src/telas/CicloFicha/dossie.ts` | **novo** — o gerador, na linhagem de `telas/Banco/exportar.ts` |
| `web/src/telas/CicloFicha/CicloFicha.tsx` | o botão, e `ref` nos gráficos |
| `web/src/exportacao/LEIA-ME.md` | passam a ser **três** lugares que geram documento; dizer qual serve para quê |

---

## 6 · PR 5 — explicar o acesso de coordenação *(item 4a, P)*

O modelo está certo — quatro perguntas do áudio têm resposta no código
([25 §3.1](25-leitura-da-coordenacao.md)). O produto é que não conta. Três
textos, e nenhum precisa de decisão:

1. **Antes do botão "Nova conta"**, na Administração — não como legenda de
   campo, e sim antes: *"Isto cria um acesso ao SAS. Não cria nada no Canvas.
   Use o mesmo e-mail do Canvas e a pessoa poderá entrar pelo botão do Canvas."*
2. **A recusa que ensina.** `/login?canvas=sem-conta` passa de "Procure a
   coordenação" para *"Peça a um coordenador para criar seu acesso no SAS com o
   mesmo e-mail da sua conta do Canvas. O Canvas diz quem você é; o acesso ao
   SAS é criado aqui dentro."*
   ⚠️ **Sem ecoar o e-mail na URL.** Seria o texto mais útil possível e é
   exatamente o que não se faz: query string entra em histórico de navegador e
   em log de acesso do nginx.
3. **No diálogo da senha sorteada**, dizer o que ela é e o que ela não é —
   ela não vale no Canvas, e redefinir invalida a anterior na hora.

### 4b — o convite por e-mail *(M, travado)*

Trava na decisão *"coordenação recebe e-mail transacional?"*
([25 §5](25-leitura-da-coordenacao.md), item 3). Duas notas para quando
destravar:

- **Não mande a senha.** Mande **convite com token que expira**. Senha sorteada
  por e-mail troca um canal informal (WhatsApp) por um canal permanente (caixa
  de entrada) — é pior, não melhor.
- **O motor de lembretes não é o caminho óbvio.** Ele é máquina de estados para
  disparo *agendado* (`regra_lembrete` → `disparo`); um convite é envio
  imediato. Ou vira uma `aplicacao/` nova, ou chama `enviar_email` direto — e aí
  **fica de fora da lista de supressão** (`email_invalido`), o que precisa ser
  decisão consciente, não descuido.

---

## 7 · PR 6 — o `/banco` adota a `BarraFiltros` *(item 3, M — por último)*

Fecha a dívida que a C.1 abriu de novo: o Banco nasceu depois das outras seis
telas, com sidebar própria, e são dois sistemas de filtro outra vez.

**Só entra depois do PR 1 e do PR 3**, pelo §0.4 — e o desenho tem de preservar
três coisas que a sidebar entrega hoje e a faixa não:

| O que a sidebar faz | Como a faixa preserva |
|---|---|
| Cabe 65 tópicos em 3 níveis | O grupo **Assunto** é um botão que abre a árvore existente (`ArvoreTopicos`) em popover, e mostra o tópico ativo no rótulo |
| É mobile-first e verificada a 360px | Herda o colapso do PR 1 — que é o que torna isto possível |
| Gruda e rola sozinha acima de 880px | **Perde-se.** É o custo do PR, e vale dizer em voz alta antes de escrever |

Preservar também, porque cada um custou um bug: o debounce de 350ms, a limpeza
do tópico ao trocar de matéria (o código `1.1` existe nas três matérias e
significa coisa diferente em cada uma), o "campo vazio é campo ausente" de
`semVazios` (senão `{materia: undefined}` e `{}` viram duas chaves de cache), e
o **Sem assunto** filtrando no servidor.

⚠️ **A aba serve os dois cascos.** `Banco.tsx` recebe `perfil` e a mesma tela
roda dentro do casco do aluno. `banco.css` já lê `--color-*` nos dois (os
tokens `--alu-*` não alcançam a aba), então o tema não é o risco — **o layout
é**: no aluno, `.tela` é um bloco da coluna de `.alu-body__inner`, não filha de
um `<main>`. Verificar nos dois cascos, nos dois tamanhos.

Na passagem, **corrigir [22 §3.5](22-plano-banco-questoes.md)** e o cabeçalho de
`Banco.tsx`: a decisão de não usar a faixa deixou de valer, e a razão pela qual
deixou é o PR 1. Documento que descreve estado que não existe mais é o que o
`CLAUDE.md` chama de mentira na tabela.

---

## 8 · Riscos

| # | Risco | Onde | Mitigação |
|---|---|---|---|
| 1 | Laço colapsa/expande no `ResizeObserver` | PR 1 | medir quebra de linha por `offsetTop`, e só no estado aberto (§2) |
| 2 | Filtro ativo escondido pelo colapso | PR 1 | o resumo é obrigatório; sem resumo, o grupo não colapsa |
| 3 | Faixa de decisão mentindo sobre o recorte | PR 2 | respeitar o recorte **e** dizer quantos ficaram fora |
| 4 | Regressão de celular no `/banco` | PR 6 | ordem (1 → 3 → 6) e verificação a 390/360 nos dois cascos |
| 5 | PDF sem estilo em produção e ninguém vê | PR 4 | CSSOM, nunca `style` inline; **testar em `portalsas.online`** |
| 6 | E-mail de convite fora da supressão | 4b | decidir explicitamente antes de escrever |
| 7 | Sem teste que toque DOM | PR 1, 2, 6 | é dívida conhecida ([19](19-roadmap.md), bloco F): o que der para extrair em função pura vai para `dominio/` com teste; o resto é verificação por MCP `chrome`, declarada |

---

## 9 · Decisões

**Já decididas pelo texto da proposta** (`sprints.html` · AVULSO), e registradas
aqui para não voltarem à mesa:

- A faixa **abre por padrão** e colapsa só quando estoura a linha.
- **Ciclos, Alunos, Painel, Simulados, Administração e Auditoria ficam tabela.**
  O que falta é o cartão de decisão, não trocar o formato das listas.

**Em aberto, e o que cada uma trava:**

| # | Decisão | Trava | Quem |
|---|---|---|---|
| 1 | Coordenação recebe e-mail transacional? | **4b inteiro** | Coordenação |
| 2 | `/provas` → Ciclos vira cartão? | nada nestes 6 PRs — o [19](19-roadmap.md) amarrou essa decisão ao item 5, mas o item 5 é a faixa do Painel. É trabalho **adicional**, não parte dele | Yan |
| 3 | Papéis dentro da coordenação | nada aqui — não está entre os 6 itens | Coordenação |
| 4 | Servidor MCP do SAS | nada aqui — é decisão de LGPD antes de protótipo ([25 §4.3](25-leitura-da-coordenacao.md)) | Yan + LGPD |
| 5 | ~~Busca é da tela ou global?~~ | **respondida pelo código** (§0.1): a global existe e é de aluno; estes PRs entregam a de tela | — |

---

## 10 · Verificação

Por PR, antes do merge:

```sh
cd web && npm test && npm run lint && npm run typecheck
cd api && ./.venv/bin/python -m pytest tests/ -q && ./.venv/bin/ruff check .
```

E o que o `tsc` não pega — pelo MCP `chrome`, com `emulate` em
`390x844x3,mobile,touch` e a trava de 360px:

| PR | O que olhar |
|---|---|
| 1 | Painel colapsado a 1440; as oito superfícies a 390 e 360; memória entre as abas de `/provas` |
| 2 | O sino aterrissando nos alertas; resolver sem recarregar; a faixa a 390 |
| 3 | Foco e teclado no campo de busca em cada superfície |
| 4 | **O PDF e o `.doc` em `portalsas.online`** — com gráfico, e com cor |
| 5 | A recusa real, entrando pelo Canvas com uma conta sem acesso |
| 6 | `/banco` nos **dois** cascos, nos dois tamanhos, com a árvore de assuntos |

Nenhum destes seis PRs cria migration. Se o 4b entrar, aí sim vale a armadilha 1
do `CLAUDE.md`: `docker compose restart postgrest` depois de aplicar, senão o
schema cacheado devolve 404 e o 404 parece bug de código.

---

## 11 · Documentos a corrigir na passagem

| Documento | O que passa a estar errado | Em qual PR |
|---|---|---|
| [25 §1.1](25-leitura-da-coordenacao.md) | são oito superfícies, e a busca falta em cinco | PR 3 |
| [25 §1.4](25-leitura-da-coordenacao.md) e §5 item 2 | a busca global já existe na topbar | PR 3 |
| [22 §3.5](22-plano-banco-questoes.md) + cabeçalho de `Banco.tsx` | a exceção da sidebar deixou de valer | PR 6 |
| `web/CLAUDE.md` | idem, e registrar a busca global da topbar | PR 3 e 6 |
| [19 §3](19-roadmap.md) · Polimento | marcar o que entrou; e desamarrar "Ciclos vira cartão" do item 5 | cada PR |
| [sprints.html](sprints.html) | mesmo conteúdo, mesma passagem | cada PR |
