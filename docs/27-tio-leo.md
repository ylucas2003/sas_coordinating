# 27 — Tio Léo · o mentor do aluno

> Desenho de 29/08/2026. O chat do aluno existe e está no ar desde a migração
> React; o que este documento define é o que ele passa a **saber mostrar** —
> fórmula, gráfico, questão, prova — e sob que regras.
>
> A direção visual está em [24 §7](24-jornada-do-aluno.md); as mecânicas do jogo
> em [26](26-mecanicas-do-jogo.md).

---

## 1 · O nome

**"Tio Léo" é o nome do bot do aluno**, e colide de propósito com "Tio Leo", uma
das cinco réguas de corte da migration `0023` que aparece no seletor do Painel da
coordenação. A colisão foi assumida em 29/08: é a mesma pessoa — o bot é a
pedagogia do Leo falando com o aluno ([24 §5.1](24-jornada-do-aluno.md)).

**A convenção que desfaz a ambiguidade internamente:** *"a régua do Tio Leo"*
para o critério, *"o Tio Léo"* para o bot.

---

## 2 · O que já existe

> Atualizado em 26/10. A coluna do meio é o que está no ar (o `main`, que
> desde 26/10 inclui o piso de anonimato do PR #114). A da direita é o branch
> `feat/ferramentas-registro-unico`, escrito e testado mas **fora de
> produção** — o que ele entregou está no
> [42 §4.4](43-plano-ferramentas-e-mcp.md), e as decisões do dono de 26/10 no
> [42 §0.1](43-plano-ferramentas-e-mcp.md).

| | No ar (`main`) | No branch, fora de produção |
|---|---|---|
| Casca | `FolhaTioLeo.tsx` (bottom sheet no celular, cartão flutuante de 400×620 no desktop) e `FabTioLeo.tsx`, com a MESMA `Conversa.tsx` da coordenação | a mesma, e o `CascoAluno` a põe num `LimiteDeErro`: se quebrar, sobra o botão, que reinicia o Tio Léo sem recarregar a página |
| Renderização | `Markdown.tsx` (com KaTeX), `Mensagem.tsx`, `ToolTrace.tsx` | e os cartões de `ArtefatoAluno.tsx`, passados pela prop `renderArtefato`, cada um no próprio `LimiteDeErro` e com tela cheia; o trace dá nome legível a cada tool e, no aluno, não mostra UUID nem `aluno_id` |
| Cartões | **nenhum**: `ArtefatoAluno.tsx` existia e ninguém o importava, e nenhuma tool do aluno produzia artefato | os seis tipos do catálogo (§7), gravados em `chat_artefato` (migration 0070) e relidos ao reabrir a conversa. O de `barras_corte` diz de que nota se trata — "Notas que contam na régua" —, e as barras da Hoje dizem "Notas no último simulado" (decisão do dono de 26/10, §12) |
| Motor | `api/app/chat/agente.py`, parametrizado por `perfis.py`; tools em série e a resposta inteira picada em pedaços de 40 caracteres | streaming de verdade e tools em paralelo, pelo registro único `chat/ferramentas.py` (42 §3) |
| Tools do aluno | 6, em `tools_aluno.py` | **17**: as 6, mais 5 em `tools_aluno_situacao.py`, 5 em `tools_aluno_banco.py` e `roteiro_do_mentor`. Nenhum schema declara `aluno_id`: ele sai do JWT, e o do argumento é descartado |
| Contexto do turno | nenhum: o prompt não sabia que dia era | `chat/contexto_do_turno.py`: data, alvos, régua com zona e distância, próximo simulado e sequência, montados do JWT antes de cada pergunta |
| Roteiros | — | 4, em `api/app/chat/roteiros/aluno/`: `antes_da_prova`, `explicar_questao`, `plano_da_semana` e `revisar_simulado` |
| Comparação com a turma | a regra do prompt e, **desde 26/10, o piso de anonimato no domínio** (PR #114, `aluno_dados.PISO_DE_ANONIMATO = 10`): com menos de 10 notas na prova, nenhum número da turma sai, nem pelas rotas `/me` nem pelas 6 tools, que leem as mesmas funções | o mesmo piso, valendo também nas tools novas, que o leem do domínio sem cópia (`test_as_tools_nao_reaplicam_o_piso`); e a nota que não conta como desempenho (o zero não computável) fica fora das contas |
| Modelo | `gpt-4o-mini`, constante em `perfis.py` | `OPENAI_MODELO_ALUNO`, com padrão `gpt-4o-mini` |

⚠️ **Visto no browser em 26/10** só contra uma stack descartável, com a conversa
semeada pelas tools reais e **sem nenhuma mensagem ao modelo**: a escolha de
tool pelo `gpt-4o-mini` nunca foi vista (42 §4.5, §8). Os três achados daquela
verificação foram resolvidos na mesma tarde — a migalha no celular, o nome das
duas notas (§12) e o nome acessível dos dois controles do cartão da questão,
que agora são "Ampliar este cartão — " seguido do olho do cartão, e "Abrir a
questão N (…) numa tela só dela" —, e essas mudanças não foram vistas contra
o backend real.

### 2.1 Duas coisas do código que decidem este documento

**O `Markdown.tsx` é pobre de propósito.** O comentário no topo dele:

> *"Sem links, imagens nem HTML — o texto vem do LLM, e ampliar a gramática
> ampliaria a superfície de injeção sem ganho para o caso de uso."*

Tudo que este documento acrescenta amplia essa gramática. Fazer isso tipo a
tipo, com allowlist, é o único jeito — trocar por um markdown genérico com
`innerHTML` é como isso costuma dar errado.

**O modelo de artefato já está certo.** `gerar_grafico` **não devolve desenho**:
devolve `{tipo, titulo, payload}` com payload sendo dado, e o front tem um
componente por tipo. O LLM escolhe *qual* gráfico e *de qual fonte*; quem desenha
é o nosso código. É à prova de injeção por construção, e é o padrão que tudo
aqui deve seguir.

---

## 3 · As duas famílias, e elas têm regras opostas

| | Como chega | Risco | Regra |
|---|---|---|---|
| **Artefato** — gráfico, questão, prova, extrato | dado estruturado, **catálogo fechado** de tipos | zero | o modelo escolhe de uma lista; nunca produz markup |
| **Inline** — fórmula, negrito, lista, tabela | dentro do texto do modelo | real | parser próprio, allowlist, **nunca `innerHTML`** |

Toda decisão abaixo é sobre em qual família cada coisa cai.

---

## 4 · Fórmula matemática

É inline, e é a única coisa do pedido que exige biblioteca.

| Caminho | Peso | Observação |
|---|---|---|
| **KaTeX empacotado** | ~270 KB JS + ~200 KB de fontes | padrão de fato, MIT. Respeita a regra 6 do CLAUDE.md **desde que as fontes venham do nosso servidor** — mesmo procedimento que tirou a Plus Jakarta Sans do Google |
| Temml → MathML nativo | ~50 KB, sem fontes | o browser renderiza; qualidade tipográfica varia com a fonte do sistema |
| Renderizar no servidor | 0 KB no cliente | vira artefato SVG e cai na família segura; custa latência e dependência Python |

**Proposta: KaTeX com `import()` dinâmico**, carregado só quando a primeira
fórmula aparece na conversa. O aluno que nunca vê fórmula nunca baixa nada, e o
peso deixa de ser argumento.

⚠️ **Configurar explicitamente `trust: false` e `throwOnError: false`.** KaTeX é
seguro por padrão, mas quem herdar o código precisa ver a escolha escrita, não
deduzida.

---

## 5 · Química — dois problemas, não um

**Equações** (`H₂SO₄ + 2NaOH → Na₂SO₄ + 2H₂O`): `mhchem` é extensão do KaTeX,
+30 KB. Resolve junto com a matemática.

**Estruturas** (esqueleto de orgânica): outro problema — SMILES para desenho 2D,
biblioteca de ~200 KB. E orgânica é assunto grande no ITA e no IME, então não é
hipotético.

**Proposta: fora da primeira versão**, e resolvido por artefato — quando a
resposta precisar de estrutura, o Tio Léo mostra a **imagem da questão do
banco**, que já existe em PNG (`questao_vestibular.imagem_url`).

---

## 6 · PDF — o atalho que o projeto já pagou

O aluno tem a prova em PDF (`/me/simulado/{id}/arquivo`) e o banco tem **PNG de
cada questão**, mais o `gerar_imagem_pagina.py` no pipeline.

- *"me mostra a questão 12"* → **não precisa de PDF**; precisa do PNG que existe.
- *"me mostra a prova inteira"* → **abrir, não renderizar**. `pdf.js` é ~1 MB e
  num celular entrega experiência pior que o visualizador nativo.

**Proposta: nada de `pdf.js`.** Artefato `prova` = metadados e um botão "Abrir a
prova". Artefato `questao` = imagem, enunciado, gabarito e resolução.

---

## 7 · O catálogo de artefatos

> Estado de 26/10. **No ar (`main`), nenhuma tool do aluno produz cartão.** A
> coluna "no branch" é o `feat/ferramentas-registro-unico`, fora de produção
> ([42 §4.4](43-plano-ferramentas-e-mcp.md), "Cartões").

| tipo | o que mostra | no branch: quem produz | estado |
|---|---|---|---|
| `linha_temporal` | minha trajetória pelos ciclos | `minha_trajetoria` (`api/app/chat/tools_aluno_situacao.py`) | ✅ no catálogo, gravado e visto no browser |
| `histograma` | distribuição do simulado, **com a minha marca** | `distribuicao_do_simulado` (`tools_aluno_situacao.py`), com `minhaNota` tirada do `aluno_id` do token — a marca que faltava | ✅ idem; abaixo do piso de anonimato a distribuição não sai |
| `barras_corte` | minhas matérias contra o corte, **na nota que conta na régua** | `minha_zona` e `meu_panorama` (`tools_aluno_situacao.py`), sobre `/me/zona` | ✅ idem; o cartão diz "Notas que contam na régua" (§12) |
| `extrato_xp` | de onde vieram meus pontos no último simulado | — | ❌ **fora do catálogo**: o XP ainda é mock ([26 §3](26-mecanicas-do-jogo.md)), e `chatStream.ts` o deixa de fora de propósito |
| `questao` | imagem, enunciado, gabarito e **resolução oficial** | `resolucao_oficial` e `questoes_do_banco` (com uma questão só), em `api/app/chat/tools_aluno_banco.py`. O payload leva só o id; o cartão busca o resto em `GET /banco/questoes/{id}` | ✅ idem |
| `lista_questoes` | N questões para treinar agora | `o_que_mais_cai`, `missao_de_hoje`, `questoes_do_banco` e `meu_progresso_no_banco` (`tools_aluno_banco.py`) | ✅ idem |
| `prova` | metadados + abrir o PDF | `meu_desempenho_em_simulado` (`api/app/chat/tools_aluno.py`). O payload leva só o `simuladoId`; o cartão relê `GET /me/simulado/{id}` | ✅ idem |
| `plano` | ranking de assuntos prioritários | — | depende do Sprint 6 |

O catálogo é FECHADO e tem duas pontas que precisam bater:
`TIPOS_DE_ARTEFATO` em `api/app/chat/ferramentas.py` (o escopo `aluno` tem os
seis tipos acima marcados ✅) e `CATALOGO_DE_ARTEFATOS` em
`web/src/dominio/chatStream.ts`; `api/tests/test_chat_ferramentas.py` lê a
constante do front e reprova se as duas divergirem. A
tool devolve o cartão no campo aninhado `artefato: {tipo, titulo?, payload}`; o
servidor o grava em `chat_artefato` (o CHECK da migration 0070 aceita os quatro
tipos novos) e o modelo recebe só `{tipo, anexado}`, para não redesenhar o
cartão em texto. Na folha, `ArtefatoAluno.tsx` desenha cada um num
`LimiteDeErro` próprio, com tela cheia. "Visto no browser" quer dizer: numa
stack descartável, com a conversa semeada pelas tools reais, sem modelo (§2).

⚠️ **`fonte_id` é injetado do JWT, nunca aceito como argumento.** Senão o aluno
pede o gráfico de um colega. No branch, o registro de ferramentas
(`chat/ferramentas.py`, escopo `aluno` — docs/43 §3) aplica isso às 17 tools do
aluno e, com elas, aos cartões: nenhum schema declara `aluno_id`, o do
argumento é descartado, e o payload de `questao` e `prova` carrega só o id. A
questão é do acervo do banco, igual para todos; a prova é relida por `GET
/me/simulado/{id}`, que só devolve o resultado do próprio aluno (o do token).

`ArtefatoNaoRenderizavel` já existe em `Artefato.tsx` e continua sendo a saída
da coordenação quando o payload não bate — falhar visível, nunca em silêncio.
No aluno, a mesma regra mora em `ArtefatoAluno.tsx`: "Cartão não desenhado"
para o payload que não bate, e "Cartão não abriu" para o cartão que quebra
dentro do `LimiteDeErro` dele.

---

## 8 · A forma: sheet de três alturas

**Celular:** bottom sheet com três alturas — espiada, meio e cheio. Um artefato
grande empurra para cheio sozinho, e **qualquer artefato pode ser expandido para
tela inteira**: gráfico e questão precisam disso num aparelho de 390px.

**Desktop:** painel lateral à direita, não-modal.

⚠️ **A tensão com a D.1.** O [docs/10](10-problemas-e-visao.md) pede o chat
**não-modal** porque o modal bloqueia a navegação — é a reclamação do
coordenador. Para o aluno no celular o cálculo é outro: sheet é o único padrão
sensato, e ele não precisa navegar enquanto conversa.

**O split é defensável e é o que se implementa: aluno com sheet modal,
coordenador com painel lateral não-modal.** Mesma máquina de conversa
(`agente.py`), cascas diferentes — exatamente o que `perfis.py` já faz com prompt,
tools e modelo.

---

## 9 · As regras duras

1. **O modelo nunca emite markup.** Nem HTML, nem SVG, nem link externo. Ele
   escolhe tipos de um catálogo e escreve texto numa gramática restrita.
2. **Sem link externo.** Link vindo de LLM é vetor de phishing para um público de
   16 a 18 anos. Se um dia entrar, **só rota interna do próprio app**, validada
   contra uma lista fechada.
3. **`aluno_id` do JWT em toda tool e todo artefato.** Nunca argumento.
4. **Comparações só com agregados** — regra que o `prompt_aluno.py` já impõe e
   que vale igual para artefato: um histograma pode mostrar a distribuição da
   turma e a marca do próprio aluno, nunca a nota nominal de um colega. Desde
   26/10 ela é também regra do domínio, e não só do prompt: com menos de 10
   notas na prova, o agregado não sai (o piso de anonimato, §2), porque com
   duas notas "a média da turma" é a nota do colega a uma conta de distância.

---

## 10 · O risco que ninguém vê chegando

**Fórmula bonita e errada.** O modelo pode escrever LaTeX impecavelmente
renderizado e matematicamente falso, e não há como validar. Um aluno de 17 anos
não tem repertório para desconfiar de uma derivação bem diagramada — e
renderizar bem **aumenta** a confiança dele na resposta.

Mitigação, barata porque o dado existe: **`questao_vestibular.resolucao_url`**.
Quando a conversa for sobre conteúdo, o Tio Léo mostra a **resolução oficial da
questão** em vez de derivar do zero. O `prompt_aluno.py` precisa mandar isso com
a mesma dureza com que hoje manda *"nunca invente notas"*.

---

## 11 · Custo e ordem

| | Tamanho |
|---|---|
| Ampliar o Markdown — cabeçalho, código inline, tabela simples | **P** |
| Catálogo de artefatos do aluno + a marca no histograma | **M** |
| Sheet de três alturas + expandir artefato para tela cheia | **M** |
| KaTeX sob demanda + mhchem | **M** |
| Regra da resolução oficial no prompt | **P** |
| Estruturas químicas | **fora** |
| `pdf.js` | **fora** |

---

## 12 · Decisões em aberto

| Decisão | Trava |
|---|---|
| ~~**KaTeX empacotado ou MathML via Temml?**~~ **FECHADA — e já estava.** Venceu o KaTeX, empacotado, com as fontes servidas do nosso domínio. Não foi decidido em reunião: `componentes/ui/Markdown.tsx` já o usava desde 01/09, com macros pt-BR (`\sen`, `\tg`, `\cotg`) e uma medição de 58 fórmulas que falhavam, e este documento é que não sabia. O artefato de fórmula do Tio Léo passou a usar o mesmo componente em 05/09, sem dependência nova (docs/36 §3.1 e §6.1) | — |
| **Link externo entra na gramática?** Hoje proibido | §9, regra 2 |
| **Estruturas químicas, num sprint futuro?** Fora por ora | §5 |
| O modelo do aluno continua `gpt-4o-mini` com respostas mais ricas? *Em parte:* no branch das fases o modelo deixou de ser constante e virou `OPENAI_MODELO_ALUNO`, com padrão `gpt-4o-mini`; trocar segue sendo decisão de custo. A escolha de tool pelo `gpt-4o-mini` com o catálogo novo não foi medida ([42 §8](43-plano-ferramentas-e-mcp.md)) | custo do chat, [14 §6.4](14-plano-producao.md) |
| ~~**A Hoje e o Tio Léo mostram a mesma nota contra o corte?**~~ **FECHADA em 26/10 pelo dono.** Não, e cada uma diz qual é: as barras da Hoje são as "Notas no último simulado" (a nota do ciclo mais recente, de `/me/evolucao`); o cartão `barras_corte` e a zona mostram as "Notas que contam na régua" (`/me/zona`). Nada mudou no cálculo — a regra e os nomes estão em `web/src/dominio/notaContraCorte.ts`. Na verificação do browser de 26/10 a aluna via Física 4,3 na Hoje e 4,6 no Tio Léo, sem nome nenhum, e um dos dois parecia errado. A Jornada, que também mostra a média, passar a dizer que ela é "a que conta na régua" é a ponta (f) da [42 §5.6](43-plano-ferramentas-e-mcp.md) | — |
| **Quando uma prova fecha para a comparação com a turma?** O piso de 10 notas protege uma leitura, não a diferença entre duas: quem lê a mesma prova com 10 e depois com 11 notas tira a 11ª ([42 §6](43-plano-ferramentas-e-mcp.md)) | privacidade do aluno, §9 regra 4 |
