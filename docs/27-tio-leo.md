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

| | |
|---|---|
| Casca | `ChatLauncher.tsx` (FAB + gaveta), `Conversa.tsx`, `ListaThreads.tsx` |
| Renderização | `Markdown.tsx`, `Artefato.tsx`, `ToolTrace.tsx`, `Mensagem.tsx` |
| Motor | `api/app/chat/agente.py`, parametrizado por `perfis.py` |
| Tools do aluno | 6, em `tools_aluno.py`, todas com `aluno_id` injetado do JWT |
| Modelo | `gpt-4o-mini` |

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

| tipo | o que mostra | estado |
|---|---|---|
| `linha_temporal` | minha trajetória pelos ciclos | **existe** |
| `histograma` | distribuição do simulado, **com a minha marca** | existe; falta a marca |
| `barras_corte` | minhas matérias contra o corte | novo, dado no ar |
| `extrato_xp` | de onde vieram meus pontos no último simulado | novo ([26 §3](26-mecanicas-do-jogo.md)) |
| `questao` | imagem, enunciado, gabarito e **resolução oficial** | dado no ar |
| `lista_questoes` | N questões para treinar agora | existe |
| `prova` | metadados + abrir o PDF | existe |
| `plano` | ranking de assuntos prioritários | depende do Sprint 6 |

⚠️ **`fonte_id` é injetado do JWT, nunca aceito como argumento.** Senão o aluno
pede o gráfico de um colega. É o padrão que `executar_para_aluno` já aplica às
seis tools de hoje, e precisa valer para os artefatos.

`ArtefatoNaoRenderizavel` já existe em `Artefato.tsx` e continua sendo a saída
quando o payload não bate — falhar visível, nunca em silêncio.

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
   turma e a marca do próprio aluno, nunca a nota nominal de um colega.

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
| **KaTeX empacotado ou MathML via Temml?** Peso contra qualidade tipográfica | §4 |
| **Link externo entra na gramática?** Hoje proibido | §9, regra 2 |
| **Estruturas químicas, num sprint futuro?** Fora por ora | §5 |
| O modelo do aluno continua `gpt-4o-mini` com respostas mais ricas? | custo do chat, [14 §6.4](14-plano-producao.md) |
