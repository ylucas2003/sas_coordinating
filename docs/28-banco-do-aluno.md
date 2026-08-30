# 28 — O banco de questões do lado do aluno

> Desenho de 29/08/2026. O banco existe e está em produção desde 23/08
> ([22](22-plano-banco-questoes.md), [23](23-banco-questoes-historico.md)):
> 2.693 questões de prova do ITA e do IME, classificadas por tópico do edital.
> O que este documento define é o que ele vira **dentro da aba Estudar** do casco
> novo do aluno ([24 §7](24-jornada-do-aluno.md)).

---

## 1 · O que já existe — e é muito

### API — 13 rotas

| Rota | O que faz |
|---|---|
| `GET /banco/questoes` | página filtrada por matéria, vestibular, ano, fase, tópico e busca textual. **A única rota paginada do projeto** |
| `GET /banco/questoes/{id}` | uma questão, por id legível (`ita_2019_fase1_q01`) |
| `GET /banco/estatisticas` | recorrência por tópico. **Nunca paginada**, de propósito |
| `GET /banco/taxonomia` | os tópicos do edital |
| `/banco/listas` (5 rotas) | montar, renomear, remover, adicionar e tirar questão |
| `GET/PUT /banco/estudo` | resolvida e anotação, por aluno |

### Front

`FiltrosBanco` (coluna lateral própria), `ListaQuestoes` (paginada),
`CartaoQuestao`, `MinhaLista`, `Estatisticas`, `exportar.ts` (PDF e Word) e
`Mensagem`.

### O que o cartão de questão já sabe fazer

Enunciado como **PNG** (preserva fórmula e figura da prova original), gabarito
escondido atrás de um toque, anotação com rascunho local gravado no `blur`,
marcar como resolvida, tópicos do edital com aviso quando a classificação é de
confiança média ou baixa.

⚠️ **`resolucao_url` existe na tabela** e é o que permite o Tio Léo mostrar a
resolução oficial em vez de derivar do zero ([27 §10](27-tio-leo.md)).

---

## 2 · A mudança estrutural: o banco tem duas faces

O que está no ar é um **catálogo** — navegar, filtrar, montar lista, exportar.
Foi desenhado para o coordenador montando prova, e o aluno herdou a mesma tela.

O aluno precisa de uma segunda face, que **não existe**: a **sessão de treino**.

| | Navegar | Treinar |
|---|---|---|
| A pergunta | "que questões existem sobre Termodinâmica?" | "me dá 12 de Termodinâmica agora" |
| A forma | lista paginada, filtro visível, tudo à mão | fila, uma questão por vez, sem filtro na tela |
| Quem escolhe | o aluno | o sistema, por prioridade |
| Existe hoje? | **sim, inteiro** | **não** |

A sessão de treino é o destino do botão **COMEÇAR** da aba Hoje. É a peça que
transforma o banco de catálogo em ferramenta.

---

## 3 · A sessão de treino

### As regras

1. **N questões, escolhidas por prioridade** — `importância × (1 − meu acerto)`.
   Antes do Sprint 6 não existe acerto por assunto: a sessão cai para **matéria**,
   escolhida pela que está mais longe do corte.
2. **Uma por vez, tela cheia.** Progresso no topo, sem navegação por baixo.
3. **Só objetivas, por padrão.** Das 934 da carga original, **420 são de 2ª fase
   — dissertativas, sem alternativa e sem gabarito por natureza** (`0028`). Não
   dá para "responder" uma dessas. Elas entram como *estudar a resolução*, nunca
   como *responder*, e nunca no meio de uma fila de objetivas.
4. **Não repete questão já resolvida**, a menos que o aluno peça revisão.
5. **A sessão NÃO paga XP.** Diretriz do verificável ([26](26-mecanicas-do-jogo.md)):
   treino não é supervisionado, e nada impede clicar em alternativa aleatória.
   A sessão registra e informa; quem paga é o simulado.

### O que ela deve gravar — e aqui há um ganho que a tabela de hoje não captura

Hoje `questao_estudo_aluno` guarda um booleano `resolvida` e uma anotação. Numa
sessão de treino o aluno **escolhe uma alternativa**, e o gabarito oficial está
na mesma tabela da questão. Comparar as duas coisas dá **acerto por tópico no
treino** — sinal muito melhor que "marquei como resolvida".

**Proposta:** estender `questao_estudo_aluno` com `alternativa_escolhida` e
`acertou`. Migration pequena, e o retorno é grande: é a única fonte de acerto por
assunto que **não depende do Sprint 6**, porque as questões do banco já são
classificadas.

⚠️ **E não muda a diretriz do verificável.** Esse acerto **alimenta o plano de
estudo**, nunca o XP nem a liga. Treino informa; prova paga. Se um dia alguém
propuser pagar por acerto no treino, a resposta está aqui: não é supervisionado.

### O fim da sessão

Resumo com quantas foram, quais assuntos, quantas o aluno acertou, e o que isso
mudou no plano dele. Nunca um número de XP.

---

## 4 · O modo Navegar, no casco do aluno

Mesma capacidade, casca diferente:

- **O filtro sai da coluna lateral e vira folha.** `FiltrosBanco` é um `<aside>`
  próprio — a dívida registrada em [25 §1.1](25-leitura-da-coordenacao.md): C.1
  fechou "dois sistemas de filtro" para seis telas, e o banco nasceu depois e
  reabriu. No celular, coluna lateral não existe; o filtro é uma folha que sobe.
- **A busca sobe para o topo**, junto do controle segmentado da aba Estudar.
- **Minha lista** continua, e ganha sentido novo: é a fila de treino que o aluno
  monta à mão.
- **Exportar PDF e Word** continua existindo. É do coordenador por natureza, mas
  um aluno que quer imprimir para resolver no papel é caso real.

---

## 5 · As estatísticas viram outra coisa

`GET /banco/estatisticas` devolve recorrência por tópico — quantas vezes cada
assunto caiu, por ano, fase e vestibular. Hoje é uma tela de consulta.

Com o **índice de importância** ([24 §4](24-jornada-do-aluno.md), Sprint 6 · P3),
ela deixa de responder *"o que já caiu"* e passa a responder *"o que estudar"* —
incidência ponderada por recência, com a tendência exposta ao lado.

⚠️ **Ela nunca pagina, e isso é regra.** O docstring de
`api/app/banco/estatisticas.py` explica: truncar leitura estatística devolve
número errado **sem parecer errado**. A paginação da listagem não contradiz isso
— lá a resposta é navegação.

---

## 6 · Cuidados de execução

**A imagem é o conteúdo.** O enunciado é PNG de largura variável; sem
`max-width: 100%` ele estoura a viewport a 360px. O comentário de
`CartaoQuestao.tsx` já avisa. Numa sessão de 12 questões são 12 PNGs — **vale
pré-carregar a imagem da próxima** enquanto o aluno resolve a atual.

**A CSP já permite o bucket** do banco (`img-src 'self' data: blob:` mais o
bucket). Nenhuma origem nova entra.

**Filtrar por tópico exige matéria.** A rota devolve 400 sem ela, e o motivo está
no código: `1.1` existe nas três matérias e significa coisa diferente em cada uma.
A interface tem de impedir a combinação, não deixar o erro chegar.

**Classificação incerta se declara.** O cartão já marca confiança média e baixa.
Numa sessão de treino isso importa mais: uma questão classificada errado põe o
aluno treinando o assunto errado.

---

## 7 · Decisões em aberto — as três seguem abertas desde 23/08

| Decisão | Hoje, de fato |
|---|---|
| **O aluno vê o banco inteiro, ou só o do vestibular-alvo dele?** | vê inteiro. E todo aluno é avaliado contra ITA **e** IME, o que joga a favor de manter |
| **As questões sem classificação aparecem?** | aparecem — sumir daria ao aluno um recorte incompleto sem aviso |
| **A lista montada pelo coordenador é visível para o aluno?** | não. `(dono_tipo, dono_id)` entra em toda consulta, e isso é teste, não intenção |

Nenhuma das três impede o desenho seguir; todas mudam o que a tela mostra.

---

## 8 · O que criar

| | Depende de | Tamanho |
|---|---|---|
| `alternativa_escolhida` + `acertou` em `questao_estudo_aluno` | — | **P** |
| Sessão de treino — fila, uma por vez, resumo final | a migration acima | **M** |
| Escolha da fila por prioridade | Sprint 6 · P3 e P4 | **M** |
| Filtro em folha no casco do aluno | — | **P** |
| Estatísticas com o índice de importância | Sprint 6 · P3 | **M** |
| Pré-carga da imagem seguinte | — | **P** |
