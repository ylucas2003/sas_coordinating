# 29 — A área do aluno · o que falta além do front

> Levantado em **29/08/2026**, fechando a rodada de desenho que produziu os
> documentos [24](24-jornada-do-aluno.md) (jornada), [26](26-mecanicas-do-jogo.md)
> (mecânicas), [27](27-tio-leo.md) (Tio Léo) e [28](28-banco-do-aluno.md) (banco).
>
> Aqueles dizem **o que construir**. Este diz **o que ainda falta para o aluno
> conseguir usar** — e quase nada aqui é tela.

---

## A · O dado existe e não chega ao aluno

Cinco casos, e em todos o servidor já sabe a resposta.

### A.1 O aluno não vê simulado futuro

`simulados_do_aluno` parte da tabela `nota`, e **só existe linha em `nota` depois
que sai nota**. Um simulado agendado para daqui a doze dias não existe na área do
aluno.

Mas `evento_agenda` é criado quando o coordenador agenda (Sprint 1 · P1) e **já é
usado para mandar e-mail ao aluno na véspera** (Sprint 1 · P3, no ar). **O e-mail
sabe do simulado; a tela não.**

Falta `/me/agenda`. É pequeno, e sem ele a contagem regressiva da aba Hoje não
tem fonte.

### A.2 O filtro `presente = True` esconde a falta

O mesmo `simulados_do_aluno` filtra por presença e descarta quem faltou. **Do
lado do aluno, hoje, a falta é invisível.**

⚠️ Isso quebra a sequência que a [26 §4](26-mecanicas-do-jogo.md) definiu: a
corrente precisa mostrar o quadrado vazio da falta, que é justamente o que dá
peso a ela. O endpoint tem de mudar junto da mecânica.

### A.3 "Meus erros" só existe por simulado

`/me/simulado/{id}/questoes` devolve as questões de **um** simulado. Falta
`/me/erros`, agregando todos — que é o material de estudo mais óbvio que temos e
está enterrado atrás de uma navegação.

### A.4 A zona não tem rota

`classificacao_aluno.zona` e o avaliador de critérios existem. Falta o endpoint
devolvendo zona, distância por matéria **e a régua que produziu o veredito** — o
rótulo nunca pode aparecer sem ela ([24 §2](24-jornada-do-aluno.md)).

### A.5 Três rotas prontas que nenhuma tela desenha

`/me/trajetoria`, `/me/heatmap` e `/me/simulado/{id}/arquivo`. Construídas,
testadas, invisíveis.

---

## B · As regras que ninguém escreveu — e que mordem no terceiro mês

### B.1 Simulado anulado e nota corrigida

`simulado.anulado` existe, e nota é revisada de verdade — a Sprint 2 inteira
tratou de `pontuacao_canvas` versus `pontuacao_sas`.

**O que acontece com o XP já pago, com a sequência e com a liga que já fechou?**
Estorna, recalcula, ou congela? Não há resposta, e o caso vai acontecer.

Recomendação: **XP é derivado, nunca gravado como saldo.** Se for sempre
recalculado a partir de `nota`, uma correção se propaga sozinha e o problema
deixa de existir. Só o **extrato de uma liga já encerrada** precisa ser
congelado — senão o pódio muda depois de anunciado.

### B.2 A virada de ano letivo

Em janeiro, o que acontece com XP, sequência, esquadrilha e conquistas? Zera,
arquiva ou carrega? Um aluno que faz dois anos de ITM tem duas temporadas ou uma.

Recomendação: **temporada por ano letivo.** XP e liga zeram; conquistas e recorde
de sequência ficam. É o que preserva a história sem tornar o veterano
inalcançável.

### B.3 Quem entra no meio do ano

Chega com o ano na metade, XP zero e a liga madura. Nasce perdendo, e a
gamificação vira desestímulo exatamente para quem mais precisa acolher.

### B.4 Quem sai do colégio

A conta, o dado, e a esquadrilha que fica com um membro a menos.

### B.5 O vestibular-alvo não é usado

`vestibular_alvo_aluno` existe desde a `0001` e **nenhuma tela do aluno o lê**.
Todo aluno é avaliado contra ITA **e** IME — mas o alvo declarado podia ordenar
o que aparece primeiro.

---

## C · O que chama o aluno de volta — o buraco maior

Estamos construindo um produto de hábito que **não tem como chamar ninguém**.

- **Não existe `web/public` e não existe manifest.** O PWA da Sprint Mobile · P4
  está como "não começou" desde 22/08: sem manifest, sem ícone, sem
  `theme-color`, não instalável.
- **Não existe push.**
- O motor de lembretes e o e-mail existem desde a Sprint 1 e são a ponte barata:
  dá para começar por e-mail e adiar push.

**O que precisa notificar:** saiu nota, o simulado é amanhã, a liga fechou, sua
esquadrilha subiu. Sem isso, sequência, liga e contagem regressiva perdem o
gatilho e o aluno só descobre tudo se lembrar de abrir.

---

## D · Confiança

### D.1 A origem da resolução

⚠️ **O achado mais desconfortável da rodada.** `resolucao_url` cobre **2019 em
diante** e aponta para fora do app — os sites do próprio Ari
(`comentarios.aridesa.com.br` e antecessores, ver `api/app/banco/resolucao.py`).
O acervo histórico usa `resolucao_md`, que foi **gerado pelo pipeline com LLM**.

**O aluno vai ler uma resolução de IA achando que é do professor.** A coluna
`resolucao_origem` existe exatamente para distinguir, e a tela é obrigada a
mostrá-la.

E isso resolve a contradição com a regra "sem link externo" da
[27 §9](27-tio-leo.md): o **artefato** carrega a URL vinda do banco — dado nosso —
mas **o Tio Léo nunca escreve link**. `*.aridesa.com.br` entra numa allowlist,
porque é o colégio.

### D.2 Não existe canal de suporte

O aluno não tem onde dizer "essa nota está errada" ou "essa questão está
classificada errado". `/banco/mensagem` é uma página estática de motivação.

---

## E · Primeira vez e casos vazios

**Onboarding do jogo.** O aluno entra e não sabe o que é XP, sequência,
esquadrilha nem corte. O primeiro acesso hoje pede senha e foto, e mais nada.

**Estado zero de verdade.** Aluno sem simulado, sem XP, sem sequência — e as
telas precisam convidar a agir, não avisar que está vazio.

---

## F · Qualidade que ficou pendente

| | Onde parou |
|---|---|
| **Trava de 360px** — script que abre cada rota e falha se transbordar | Sprint Mobile, "ainda em aberto". Sem ela, cada tela nova reintroduz o defeito |
| **Safari real** | o MCP `mobile` não enxerga aparelho: falta o Xcode completo ([20 §2](20-mobile.md)). Três itens seguem não verificáveis |
| **Testes que toquem DOM** | os 7 arquivos de teste do front são de lógica pura |

---

## G · Dívidas que a camada nova torna urgentes

**Backup do Postgres.** O [14 §7](14-plano-producao.md) dispensou backup contínuo
porque *"o Canvas é o arquivo"*. Esse argumento morre aqui: anotação, lista, XP,
sequência, esquadrilha e histórico de treino **só existem no nosso banco**.

**LGPD.** O [14 §5.4](14-plano-producao.md) registra que **não existe caminho
para atender pedido de eliminação** (art. 18, V). A camada de jogo aumenta o dado
pessoal de menor, e a esquadrilha faz um menor compartilhar desempenho com outro.

**Teto de custo do chat.** O Tio Léo com artefatos e cinco tools novas puxa
conversas mais longas. O teto existe; o número precisa ser reaferido.

---

## H · Calibração — o portão

**Rodar a tabela de XP contra os 5 ciclos reais de 2026 antes de fixar qualquer
número.** Quantos alunos ficam abaixo de 200 XP, se o topo se descola, se as
linhas de progresso pessoal de fato mudam a liga.

É barato, e **nenhum jogo consegue testar o próprio balanceamento contra dado
real antes do primeiro jogador entrar** ([26 §7](26-mecanicas-do-jogo.md)).
Fazer isso é obrigatório, não desejável.

Mesma coisa para o **índice de importância**: conferir contra o acervo antes de
mostrar ao aluno.

---

## I · A ordem que eu faria

1. **Começa hoje, não toca nada no ar:** o backtest do XP e a classificação das
   1.031 questões de simulado (Sprint 6 · P2).
2. **Depois:** as cinco rotas do bloco A. São pequenas e destravam metade das
   telas desenhadas.
3. **Depois:** as regras do bloco B — em especial B.1, porque "XP é derivado,
   nunca saldo" é decisão de arquitetura e fica cara de mudar depois.
4. **Depois:** notificação. Sem ela o resto não é usado.
5. **Por último:** a Liga e a Esquadrilha. São as maiores e a Liga é a única
   travada numa decisão que não é do Yan.
