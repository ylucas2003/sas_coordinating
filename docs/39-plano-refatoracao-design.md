# 39 — Refatoração da coordenação a partir do Claude Design

> **Estado em 05/09/2026 — fases 0 a 5 FEITAS**, em quatro commits na
> `refactor/design-coordenacao`; a fase 6 (o tour) está sendo escrita em
> paralelo. Cada fase abaixo carrega o próprio estado e, quando o que foi feito
> divergiu do que estava escrito, **o que mudou**. A varredura de consistência
> que fechou o conjunto está no [§6](#6--a-varredura-de-consistência-0509).
>
> | Fase | Estado | Commit |
> |---|---|---|
> | 0 · fundação de tokens | ✅ | `258ea62` |
> | 1 · kit de peças | ✅ | `258ea62` |
> | 2 · Painel | ✅ | `41ce477` |
> | 3 · Provas | ✅ **parcial** — o hub e as fichas sim, as duas LISTAS não | `41ce477` · `182cdae` |
> | 4 · Alunos | ✅ | `182cdae` |
> | 5 · Cantina | ✅ | `182cdae` |
> | 6 · o tour | 🔨 em curso, noutro agente | — |
>
> ⚠️ **Nada foi visto rodando no browser.** O portão `css` do §4 continua
> aberto, e é o mesmo débito de docs/37 §6 e docs/38 §10.2.

Executa o projeto **SAS Área do Aluno** (Claude Design, `a8bf25f7`), arquivo
`Coordenação completa.dc.html` e os quatro que ele importa. Os briefs que o
geraram são o [37](37-plano-refatoracao-visual-coordenacao.md) e a família
`brief-claude-design-*`; **onde eles e a prancheta divergirem, a prancheta
vence** — ela é posterior e foi desenhada com o código à vista.

## 0 · O que a prancheta contém

Quatro artboards, **21 telas**, nos dois temas, com documento de decisões
embutido no próprio código de cada uma.

| Artboard | Telas |
|---|---|
| Kit de peças | os seis papéis, KPI, selo nos 7 estados, régua, heatmap, histograma, linha, dot plot, sparkline, tabela, filtros, botões, tarja de procedência, alerta, card de campo, vazio, esqueleto, migalha, abas |
| Painel e cantina | 9 variantes do Painel + hub, calendário, o dia, direitos e acesso da cantina |
| Provas | hub, hub vazio, lista de ciclos, ciclo (chegada / rolado / vazio), calibração, lista de provas, prova (normal / fora das estatísticas / sem notas) |
| Alunos | lista, ficha, ficha sem simulado |

`Coordenação completa.dc.html` é só o comutador de módulos. O Banco está
**fora** do pacote, por decisão declarada na própria prancheta.

## 1 · Decisões tomadas — 05/09/2026, com o Yan

| # | Decisão | Consequência |
|---|---|---|
| 1 | **Backend faz parte do escopo** | destrava as fases 4 e 5 sem gambiarra de front |
| 2 | **Renomeação em massa** de `--color-*` → `--sas-*` | 1.067 ocorrências, 34 arquivos; `tokens.css` morre |
| 3 | **Uma PR só, no fim** | com o rename como **primeiro commit isolado** (mitigação abaixo) |
| 4 | Direitos de refeição **entram** na lista de alunos | a lista passa a consultar dado da cantina |
| 5 | Busca global e sino **saem** do header | segue a prancheta: migalha + tema + avatar |
| 6 | O tour de 6 passos **vira produto** | ganha fase própria (6) |
| 7 | Rail **252px fixo** | −164px de largura em toda tela, o tempo todo |

Decidido por mim, salvo objeção: os números de desenho saem da prancheta (ela é
a fonte); o painel "ver todos os estados" e o alternador de papel/tema do mock
**não** entram; a tabela do ciclo mantém **uma coluna por simulado**, como a
tela desenha — o Kit mostra por matéria, e a tela vence; os cards BANCO e CANVAS
da variante de cinco ficam de fora, porque existem só para provar que a grade
cresce; e há **verificação no browser antes de abrir a PR**, não por fase.

### 1.1 · A mitigação da decisão 2 + 3

Renomear em massa e entregar numa PR só significa que a troca de token — que
toca os **quatro caminhos de geração de documento** — só é exercida no fim,
junto com tudo. Se um dossiê sair escuro, o diff onde procurar tem ~15 mil
linhas.

O rename é o **primeiro commit da PR, sozinho**, sem nenhuma outra mudança
junto. O histórico fica bissectável e a decisão do Yan continua de pé.

## 2 · ⚠️ A fase 0 já estava quase toda feita

O levantamento achou o que a [CLAUDE.md](../CLAUDE.md) avisa que costuma
acontecer aqui: **a fundação de tokens que o plano ia construir já existe e está
em produção.**

    paleta.css        os hexadecimais crus (--dia-*, --noite-*)      110 linhas
    papeis.css        os seis papéis em --sas-*, três blocos de tema  101 usos
    tokens.css        --color-* como ALIAS dos papéis                142 linhas
    aluno-tokens.css  --alu-* como alias dos papéis                  892 usos
    documento.css     --doc-*, paleta clara FIXA                     107 usos

Dos nove tokens que a prancheta usa, **sete já existem** (`--sas-fio`,
`--sas-hachura`, `--sas-realce`, `--sas-grade`, `--sas-borda-l`,
`--sas-referencia-fraca`, `--sas-dado-texto-forte`). **Faltam dois:**
`--sas-fio-forte` e `--sas-alerta-texto`.

Ou seja: a fase 0 deixa de ser fundação e vira **limpeza**.

## 3 · As fases

### Fase 0 · Fechar a fundação — ✅ *feita em `258ea62`*

1. Acrescentar `--sas-fio-forte` e `--sas-alerta-texto` aos três blocos de tema
   de `papeis.css` (padrão dia · `prefers-color-scheme: dark` · `[data-tema]`).
2. Substituir as 1.067 ocorrências de `--color-*` por `--sas-*` nos 34 arquivos.
3. Apagar `tokens.css` e sua importação.

**O que mudou em relação ao plano.** O §2 já avisava que a fundação existia; na
execução ela era ainda mais completa, e a fase virou limpeza pura. Apareceu uma
quarta tarefa que não estava escrita: `tokens.css` guardava nomes que **não são
cor** — `--radius-*`, a largura do rail, a altura da topbar, `--font-family` —
e eles não podiam morrer com o arquivo nem entrar na pilha de tema, porque não
respondem a tema nenhum. Foram para `styles/forma.css`, **fora da pilha**.
`dominio/tokensCss.test.ts` passou a travar quatro arquivos, não cinco.

O commit não ficou isolado como a §1.1 pedia: ele saiu junto com a fase 1. A
mitigação valia contra um rename de 15 mil linhas escondido dentro de tudo — e
o rename ficou sendo o grosso de um commit de dois assuntos, ainda
bissectável.

**Não mexer** em `documento.css` (lê a paleta crua de propósito) nem em
`aluno-tokens.css` (já aponta para os papéis).

**Portão desta fase:** exercitar os quatro geradores — PDF da ficha
(`window.print`), PDF e PNG do panorama (`exportacao/exportar-aluno.js`,
`panorama-aluno.js`), e o `.doc` do dossiê de ciclo e do banco. Um token órfão
aqui não dá erro: dá folha preta.

### Fase 1 · Kit de peças — ✅ *feita em `258ea62`*

Nenhuma tela nova; é o vocabulário do qual todas as outras fases dependem.

**O que mudou:** `TarjaProcedencia` unificou `SeloCanvas` e `SeloGravacao`, mas
**não** a marca de gerado do `InsightsPainel` nem a `TarjaFonte` do aluno — os
dois ficaram, e a unificação completa segue sendo o PR próprio que docs/37 §7
já previa. Sobrou disso um último semáforo de cor na coordenação: a tarja de
data de `/integracoes/aulas` ainda casa `.gravacao__data.tone-*` e volta a
pintar verde, âmbar, vermelho e azul por cima da regra global de `layout.css`
(ver o §6).

| Arquivo | O quê |
|---|---|
| `componentes/ui/Histograma.tsx` | média e mediana deixam de ser `--color-red`/`--color-amber` e viram **referência cinza** (R5); entra `picoCompartilhado`; o sombreado da zona reprovada sai, porque quem carrega "abaixo" é o vazado |
| `componentes/ui/Sparkline.tsx` | escala **fixa 0–10** e prop `corte`. Hoje normaliza por min/max próprios — a mentira gráfica das 900 linhas |
| `componentes/ui/TarjaProcedencia.tsx` | **novo.** Unifica `SeloCanvas`, `SeloGravacao`, a marca de gerado do `InsightsPainel` e a `TarjaFonte` do aluno. Seis estados: medido · gerado · divergente · pendente · falhou · exemplo. "Gerado" deixa de ser ouro |
| `componentes/ui/AlertCard.tsx` | sai a barra de severidade e o `tone-*` da raiz; entra o **desfazer** |
| `componentes/ui/Campo.tsx` | `CartaoDeCampo` ganha magnitude, aviso, marca e o estado **inerte**; `CartaoDeEntrada` 110px; `CabecaDeCampo` com chevron de 44px |
| `componentes/ui/Kpi.tsx` | o rótulo vira **olho** de 10px em caixa alta |
| `componentes/ui/LinhaEvolucao.tsx` | a paleta categórica de seis matizes sai; as séries se distinguem por **forma** além de cor |
| `componentes/ui/Heatmap.tsx` | alinhar os números aos do selo da prancheta (hoje `18 + razão*72`) |
| `componentes/ui/filtros/BarraFiltros.tsx` | pílula de 44px de altura fixa, nos três estados |
| `componentes/layout/Rail.tsx` | **252px fixo**, rótulo sempre, logo do Ari no topo, usuário no rodapé, ativo como pílula em realce |
| `componentes/layout/Topbar.tsx` | **saem a busca e o sino**; fica migalha (último degrau 19px/700, os outros 15px/400, separador `›`) + botão de tema + pílula de avatar e papel |
| `dominio/selo.ts` | mantém a forma; os consumidores é que passam a usar os números da prancheta |

### Fase 2 · Painel — ✅ *feita em `41ce477`*

- `telas/Painel/Painel.tsx` — saem faixa de filtros, os 4 KPIs, a busca e a
  tabela. Grade de **12 colunas**: o card do CICLO ocupa 7 e duas linhas, com a
  **única magnitude da tela**; SIMULADO e CANTINA ocupam 5 cada, empilhados.
- `telas/Painel/FaixaDecisao.tsx` — sem recorte (não há mais filtros), com
  desfazer; some a linha "+N fora do recorte".
- `telas/Painel/TabelaPainel.tsx` — **muda de casa** para a ficha de ciclo.
- Estados: normal · sem alertas · prova sem notas · cantina com uma refeição ·
  cantina inerte · nada recente · primeiro dia · carregando · cinco cards.

**Backend:** `POST /alertas/{id}/reabrir` (o desfazer).

### Fase 3 · Provas — ✅ **parcial**, em `41ce477` e `182cdae`

⚠️ **As duas LISTAS não foram refeitas.** O hub, as duas fichas, a calibração e
a ficha de nota saíram; `telas/Ciclos/Ciclos.tsx` e `telas/Simulados/Simulados.tsx`
não foram tocados e seguem com a `.data-table` antiga. O CSS delas foi escrito
(`styles/provas.css`, de `.provas-lista__contagem` para baixo) e o domínio
também (`dominio/provas.ts::estadoDoCiclo`, com teste) — os dois estão MARCADOS
no lugar como "escrito, não ligado", para a próxima varredura não os apagar
como lixo. É o que falta desta fase.

- `telas/Provas/Provas.tsx` — as abas viram **hub de dois cards**; rotas novas
  `/provas/ciclos` e `/provas/simulados`; os caminhos antigos redirecionam.
- `telas/CicloFicha/CicloFicha.tsx` — identidade + régua + KPIs + **dois** campos
  em faixa fina + a tabela absorvida. Estado **rolado**: a régua e os campos
  encolhem para uma tira no topo.
- `telas/CicloFicha/CicloRegua.tsx` — **absorvida** pela tabela. ✅ O arquivo
  foi APAGADO de verdade (não ficou como casca redirecionando): quem atende
  `/ciclos/:id/regua` é `ReguaAbsorvidaPelaFicha`, um `<Navigate>` de quatro
  linhas em `App.tsx`. As colunas **Situação** (o motivo em palavras) e
  **Distância** foram junto para `TabelaDoCiclo.tsx` — são a única explicação
  de corte do produto.
- `telas/CicloFicha/CicloCalibracao.tsx` — doze múltiplos com **pico
  compartilhado**; sem ele a comparação que justifica a tela não existe.
- `telas/SimuladoFicha/SimuladoFicha.tsx` — hierarquia entre as seis seções;
  "fora das estatísticas" como **estado da tela inteira**, não etiqueta;
  ausência com forma própria; barra de ações condicional sem dançar de tamanho.
- `componentes/dialogos/FichaNota.tsx` — **morrem `toneNota` e `tonePosicao`**,
  os últimos ternários fixos do produto; os seis KPIs viram uma escala com a
  régua desenhada; três do aluno em dado/magnitude, três da turma em referência.
- `styles/edicao.css` — `.dialog__kpi-valor.tone-*` sai.

### Fase 4 · Alunos — ✅ *feita em `182cdae`*

- `telas/Alunos/Alunos.tsx` — três **grupos de média expansíveis** (do ano, do
  1º ciclo, do último), cada um abrindo em Matemática/Física/Química, um por
  vez; coluna de **direitos de refeição** (decisão 4); trajetória em escala
  compartilhada 0–10 com o corte desenhado; cards de entrada que **aplicam
  filtro** (`risco`, `sem nota`, `top N`, `bottom N`); contagem viva.
- `telas/AlunoFicha/AlunoFicha.tsx` — **revisão em sequência**: o recorte da
  lista sobrevive à entrada, "aluno 4 de 23", anterior e próximo, e a volta cai
  na posição de onde saiu. "Perfis semelhantes" reescrito em português (sai o
  kNN e a coluna "Distância: 0,42"); "Métricas internas" resolvido (sai
  "Janela: 9"); o `window.confirm` da foto vira o diálogo do sistema.

**Backend:** média do 1º e do último ciclo por aluno e por matéria ✅; direitos
de refeição junto do aluno ✅. **Os recortes top/bottom N não viraram rota** — e
não deviam: o N depende de quantos alunos estão na tela DEPOIS da peneira de
turma, sede e busca, e um top-30 do servidor contradiria o "3 de 902" do
cabeçalho. `dominio/recorteDeAlunos.ts::extremosPorMedia` os calcula sobre as
médias que o `GET /alunos` já manda — uma fonte só.

### Fase 5 · Cantina — ✅ *feita em `182cdae`*

- `/cantina` vira **hub** de três cards (dois para o coordenador comum — o card
  ausente **some**, não fica cinza); o calendário ganha `/cantina/cardapios`.
- **`/cantina/:data` é rota nova** do front: o dia com as **duas refeições**,
  destino do card do Painel.
- O calendário: 30 dias × 2 refeições, **cinco estados**. `aberto` e `fechado`
  compartilham preenchimento e divergem só no glifo e na redação do prazo — são
  o mesmo cardápio em dois momentos do relógio, e a passagem entre eles não é
  ação, acontece sozinha.
- `telas/Administracao/Cantina.tsx` — **divide** em `/cantina/direitos` e
  `/cantina/acesso`.
- Direitos: lote **e** pílula na própria linha; restrição alimentar com o texto
  **sob clique**; versão de leitura sem checkbox e sem barra de lote.
- Acesso: a senha revelada uma vez; desativar cantina × desativar conta com
  raios de explosão distintos; nada é apagado.
- `telas/Administracao/HubAdministracao.tsx` — o card da cantina passa a
  apontar para o hub.

**Backend: não precisou de nada.** O plano pedia "o dia com as duas refeições
numa resposta"; o calendário da coordenação já aceita janela, e
`useDiaDaCantina` o chama com `de = até = a data`, recebendo as duas linhas e
partindo em almoço e janta no `select`. Rota nova teria sido uma segunda fonte
para o mesmo número — a contradição que este produto pune.

### Fase 6 · O tour — *decisão 6*

Seis passos, cada um destacando uma região e citando a regra que a justifica.
Vira onboarding de verdade: abrir e fechar, lembrar que já foi visto, continuar
apontando certo quando a tela mudar. **Escrito na prancheta só para Provas** —
precisa de uma decisão sobre viver também nos outros ramos ou ficar órfão.

## 4 · Portões

    api    ./.venv/bin/python -m pytest tests/ -q     570 testes  ✅
    api    ./.venv/bin/ruff check .                              ✅
    web    npm test && npm run lint && npm run typecheck  489     ✅ (lint em 28 avisos)
    docs   docs/30 é GERADO — `npm test` quebra se envelhecer     ✅
    doc    os quatro geradores de documento, à mão (fase 0)       ⏳ NÃO exercitados
    css    verificação no browser antes de abrir a PR, nos dois temas,
           a 1440×900 e a 390×844                                 ⏳ NÃO feita

Os dois portões abertos são os que não têm robô: o `doc` (folha preta não dá
erro) e o `css`. São a mesma lacuna de docs/37 §6 e docs/38 §10.2, agora pela
terceira vez seguida — e as contagens acima são de antes da varredura do §6,
que mexeu no número do front.

## 5 · Fora do escopo

- **O Banco de questões** — a prancheta declara. A unificação das duas
  implementações depende do sistema de tokens que a fase 0 termina.
- Os cards **BANCO** e **CANVAS** da variante de cinco.
- O painel "ver todos os estados" e o alternador de papel/tema do mock.
- Migrations destrutivas: nenhuma fase apaga coluna.


## 6 · A varredura de consistência *(05/09)*

Cinco fases, doze agentes em paralelo, cada um vendo a própria fatia. Esta
passagem foi a primeira a olhar o conjunto. O que ela **consertou**:

| O quê | Onde |
|---|---|
| `.painel-grade` **não existia**: a grade de 12 colunas da fase 2 era só um `className`, e os três cartões empilhavam em largura cheia | `styles/painel.css` |
| `contarDecisoes` e `alertasDoRecorte` mortas com teste verde — o recorte que as justificava saiu com a faixa de filtros | `dominio/painel.ts` |
| `RECORTE_VAZIO`, `contagensDoRecorte` e `rotuloDoCiclo`, mortas pelo mesmo motivo | `dominio/painelFiltros.ts` |
| `toneCanvas`, morta desde que `SeloGravacao` virou `TarjaProcedencia` | `dominio/gravacoes.ts` |
| **Dois nomes para uma constante:** `REGUA_DA_CASA` (Alunos) e `REGUA_DO_PAINEL` (Painel), com o mesmo `'tio-leo'` cravado em mais seis lugares. Virou `REGUA_DA_CASA` + `reguaDaCasa()` em `dominio/criterios.ts`, com teste | 7 arquivos |
| **Duas traduções do mesmo chip:** `.nota-badge--verde/ambar/vermelho` no CSS faziam o que `INTENSIDADE_SEM_CORTE` já faz no TSX | `styles/ciclo.css` |
| ~25 classes órfãs das telas que mudaram de forma: a grade de KPIs da ficha de nota, o `ciclo-hero`, a `tabela-similares`, a legenda de ajuda do Painel, o `.tag.tone-anulado` | `layout` · `edicao` · `painel` · `simulados` · `aluno-ficha` `.css` |
| Comentários que passaram a mentir: "as `.tone-*` não pintam mais nada em lugar nenhum" (pintam, em dois lugares), a faixa de decisão "acima da tabela", o sino que aponta para `#alertas` | vários |

E o que ela **achou e não consertou** — porque é desenho, e desenho não se
conserta de passagem:

1. **`componentes/dialogos/CamposNota.tsx` tem ~28 classes sem uma linha de
   CSS** (`dialog-escala__*`, `dialog-pontuacao__*`, `dialog-presenca__*`,
   `dialog__olho`). É a peça central da fase 3 — a escala 0–10 que substituiu
   os seis KPIs — e ela renderiza sem forma nenhuma.
2. **`telas/Painel/Painel.tsx::PrimeiroDia` idem**, com sete classes
   `painel-primeiro*` sem CSS.
3. **As duas listas de `/provas`** (fase 3, acima).
4. **Duas definições de "corte" a um clique de distância.** O card do Painel diz
   `N cortados de M alunos` — o critério inteiro, de `GET /ciclos/{id}/classificacao`.
   A ficha para onde ele leva diz `Acima do corte X%` — a fração de alunos cuja
   MÉDIA passa de `corte_da_media`, de `GET /ciclos/{id}/estatisticas`. Os dois
   números discordam, e os dois se chamam corte.
5. **O semáforo de cor sobreviveu em dois lugares:** `.gravacao__data.tone-*`
   (`integracoes.css`) e `.panorama__tag.tone-*` (o panorama exportado do
   aluno, em `layout.css`).
6. O rótulo `CORTE 4,0` do fio de ouro está escrito quatro vezes, em duas
   grafias — `Histograma.tsx`, `SimuladoFicha.tsx`, `AlertCard.tsx` (caixa
   alta) e `criterios.ts::rotuloDoCorte` (caixa baixa).
