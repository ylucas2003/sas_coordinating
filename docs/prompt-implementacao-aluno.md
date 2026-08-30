# Prompt de implementação — a área do aluno nova

Cole o bloco abaixo numa sessão de Claude Code **na raiz do repositório**, junto
do código exportado do Claude Design.

---

```
Você vai implementar a nova área do aluno do SAS no repositório real, a partir
de um código exportado do Claude Design que eu vou te dar.

# COMO COMEÇAR — você não tem nada disto em contexto

Esta é uma sessão nova. Todo o desenho foi decidido em outra conversa e mora em
documentos deste repositório. ANTES de escrever uma linha de código:

1. Leia, nesta ordem: `CLAUDE.md`, `web/CLAUDE.md`, `docs/24-jornada-do-aluno.md`
   (a §7 é a direção visual), `docs/26-mecanicas-do-jogo.md`,
   `docs/27-tio-leo.md`, `docs/28-banco-do-aluno.md` e
   `docs/29-area-do-aluno-o-que-falta.md`.
2. Abra `api/app/routes/me.py` e `api/app/routes/banco.py` e confira com os
   próprios olhos quais rotas existem. A lista que eu dou adiante é de 29/08 e
   pode ter envelhecido — o código vence.
3. Olhe `web/src/telas/Aluno/`, `web/src/telas/Banco/`, `web/src/tipos/aluno.ts`
   e `web/styles/aluno.css` para saber o que já está construído.
4. Só então me apresente um plano, tela a tela, e espere eu aprovar.

Onde está o export do Claude Design: eu vou colar no chat ou apontar o caminho
do arquivo. Se eu não tiver feito isso ainda, pergunte antes de começar.

# O QUE VOCÊ RECEBE, E O QUE FAZER COM ELE

O export do Claude Design é REFERÊNCIA DE MARCAÇÃO E CSS, não código para colar.
Ele pode vir como HTML solto, como React em outro formato, com nomes em inglês,
com CSS Modules, com Tailwind, com dependências novas e com dados inventados.
NADA DISSO ENTRA.

Você REESCREVE o desenho como componentes React deste projeto. Aproveita-se do
export a estrutura visual, o CSS (adaptado às nossas classes e tokens), a
hierarquia dos blocos e as medidas. Descarta-se a componentização dele, os nomes,
o sistema de estilo e qualquer biblioteca.

## A STACK, e ela não muda

    React 19.2 + TypeScript, empacotado por Vite
    react-router-dom 7 — rotas de verdade, nunca navegação por estado interno
    @tanstack/react-query 5 — TODO dado de servidor passa por `useQuery`,
      inclusive os mocks: o mock devolve uma Promise, não um objeto solto, para
      que trocar por fetch depois não mude a assinatura de nada
    Biome — lint e formatação (`npm run lint`)
    Vitest — testes (`npm test`)
    CSS puro em `web/styles/`, um arquivo por tela, SEM CSS Modules e SEM
      qualquer framework de utilitário

⚠️ As dependências de produção do projeto são exatamente estas quatro: `react`,
`react-dom`, `react-router-dom` e `@tanstack/react-query`. **Não instale a
quinta.** Se o export precisar de uma biblioteca para funcionar, o desenho é que
se reescreve, não o `package.json`.

Antes de escrever o primeiro componente, leia como os que já existem são
escritos: `web/src/telas/Aluno/PainelAluno.tsx`, `web/src/hooks/aluno.ts` e
`web/src/componentes/aluno/graficos.tsx` (SVG à mão, que é como todo gráfico do
projeto é feito).

Leia antes de começar, nesta ordem, e siga o que estiver lá:
- CLAUDE.md e web/CLAUDE.md — as convenções e as armadilhas do projeto
- docs/24-jornada-do-aluno.md §7 — a direção visual e os seis papéis de cor
- docs/26-mecanicas-do-jogo.md — as mecânicas e a diretriz do verificável
- docs/27-tio-leo.md — o chat
- docs/28-banco-do-aluno.md — o banco e a sessão de treino
- docs/29-area-do-aluno-o-que-falta.md — o que NÃO existe ainda

# A REGRA CENTRAL DESTE TRABALHO

**Tudo que o SAS já tem hoje precisa sair ligado de verdade.** Nada de mockar
algo cujo endpoint existe — isso é o erro que este trabalho não pode cometer,
porque um mock a mais é uma integração a menos que ninguém percebe que falta.

E tudo que não existe fica mockado atrás de uma COSTURA ÚNICA E DECLARADA, de
modo que tirar o mock depois seja trocar uma linha, nunca caçar dado falso pelo
código.

Existem TRÊS estados, não dois, e a distinção importa:

1. REAL — o endpoint existe e responde. Liga.
2. DADO EXISTE, ROTA NÃO — o servidor já sabe a resposta, só não há rota que a
   devolva. Mocka, mas marca separado: desmockar é escrever uma rota curta, não
   inventar produto.
3. MOCK PURO — não existe nem dado. Mocka e marca.

# A COSTURA DO MOCK

Crie exatamente esta estrutura, e nada de dado falso fora dela:

    web/src/dados/aluno/
      contratos.ts   — os tipos. Os que já existem vêm de src/tipos/aluno.ts
      reais.ts       — hooks que batem na API de verdade
      mocks.ts       — TODO o dado falso do projeto, num arquivo só
      registro.ts    — o inventário legível por máquina (abaixo)
      index.ts       — o ponto único de importação das telas

`registro.ts` declara cada fonte de dado assim, e é dele que sai a documentação
final:

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
    }

REGRAS DA COSTURA:
- Nenhuma tela importa de `mocks.ts`. Todas importam de `index.ts`.
- Nenhum literal de dado falso dentro de componente. Se você escrever "6,4"
  dentro de um `.tsx` que não seja um teste, está errado.
- Em `APP_ENV=dev`, todo bloco alimentado por mock recebe um marcador visual
  discreto — uma tarja em maiúscula pequena no canto do bloco dizendo MOCK. Em
  produção o marcador não existe. Isso é o que impede a superfície mockada de
  virar invisível e ser esquecida.

# O QUE JÁ EXISTE E PRECISA SAIR LIGADO

Confira cada uma no código antes de decidir que não existe.

Do aluno (api/app/routes/me.py):
  GET  /me                          dados do aluno
  GET  /me/simulados                lista com nota, delta e média da turma
  GET  /me/simulado/{id}            posição, percentil, comparação com grupos
  GET  /me/simulado/{id}/questoes   certas, erradas, em branco
  GET  /me/simulado/{id}/arquivo    o PDF da prova — HOJE NENHUMA TELA USA
  GET  /me/evolucao                 por matéria, aluno contra turma
  GET  /me/trajetoria               HOJE NENHUMA TELA USA
  GET  /me/heatmap                  HOJE NENHUMA TELA USA
  GET  /me/insight                  bullets de IA por ciclo
  GET  /me/streak                   existe, mas a semântica é a ANTIGA
  POST /me/senha                    trocar senha

Do banco (api/app/routes/banco.py) — 13 rotas, todas funcionando:
  listagem paginada com filtros, questão por id, estatísticas de recorrência,
  taxonomia, as 5 de listas, e as 2 de estudo (resolvida e anotação).

Mais: foto de perfil, login por senha, primeiro acesso, SSO do Canvas, e o chat
com as 6 tools do aluno.

⚠️ TRÊS ARMADILHAS NESSAS ROTAS, e as três estão documentadas:
- `/me/streak` devolve "ciclos consecutivos acima da média da turma". A mecânica
  nova é "simulados consecutivos sem faltar". Trate como 'mock', não como real,
  e deixe escrito que a rota existe com outra semântica.
- `/me/simulados` filtra `presente = true` e DESCARTA o simulado em que o aluno
  faltou. A corrente de presença precisa dos quadrados vazios. Marque como
  'sem-rota' e não tente contornar no front.
- `/banco/questoes` só aceita filtro por tópico junto de matéria — a API devolve
  400 sem isso, porque '1.1' existe nas três matérias e significa coisa
  diferente em cada uma. A folha de filtros tem de impedir a combinação.

# O QUE É "DADO EXISTE, ROTA NÃO" — estado 'sem-rota'

  Próximo simulado / contagem regressiva  ← `evento_agenda` já dispara e-mail
                                            para o aluno na véspera desde a
                                            Sprint 1. O e-mail sabe; a tela não.
  Zona e distância até o corte            ← `classificacao_aluno.zona` +
                                            o avaliador de critérios (0023)
  "Meus erros" transversal                ← existe por simulado, falta agregar
  Falta em simulado                       ← `nota.presente`, hoje filtrado fora
  Origem da resolução                     ← `resolucao_origem` na questão

# O QUE É MOCK PURO

  Missão do dia · XP e extrato · Sequência de simulados · Meta do ciclo ·
  Liga · Esquadrilha · Conquistas com as regras novas · Importância do assunto ·
  Prioridade pessoal · Acerto por assunto · Artefatos novos do Tio Léo

Use dados falsos PLAUSÍVEIS e coerentes entre si: o aluno do mock tem as mesmas
notas nas telas todas, e o XP do extrato soma exatamente o total mostrado. Um
mock incoerente esconde bug de layout.

# AS ROTAS DO FRONT

    /                      Hoje
    /estudar               Estudar
    /estudar/assuntos      O que mais cai
    /estudar/listas        Minhas listas
    /estudar/listas/:id    Uma lista
    /provas                Provas
    /provas/:id            Ficha de um simulado
    /provas/:id/extrato    Extrato de XP
    /jornada               Jornada
    /liga                  A liga (alcançada pelo cartão da Jornada)
    /treino/:origem        Sessão de treino, tela cheia
    /treino/:origem/resumo Fim da sessão
    /questao/:id           Uma questão, tela cheia
    /login                 A porta

O Tio Léo não é rota: é folha no celular e painel lateral no desktop.

# O QUE NÃO TOCAR

- A área da coordenação inteira. Nenhum arquivo de `web/src/telas/` que não seja
  do aluno, e nenhum componente compartilhado sem verificar quem mais o usa.
- `web/src/telas/Banco/` é COMPARTILHADO — recebe `perfil="aluno"` ou
  `"coordenacao"`. Se o casco do aluno passar a ter o seu próprio, o da
  coordenação continua funcionando exatamente como está. Isso é teste, não
  intenção.
- Qualquer rota da API. Este trabalho é só de front.
- Os 165 testes do backend e os 142 do front. Passavam antes, passam depois.

# CONVENÇÕES QUE NÃO SE NEGOCIAM

- Português em tudo: arquivo, componente, variável, classe CSS, rótulo.
- Sem CSS Modules e sem Tailwind — o projeto usa prefixo por tela como
  namespace. Prefixe `alu-`. Um arquivo CSS por tela em `web/styles/`, tokens num
  arquivo próprio. A decisão de descartar CSS Modules está registrada: as classes
  já são namespace por tela, e converter traria risco visual sem ganho.
- Componente de função com `export function Nome()`, props com `interface Props`,
  hooks de dado em `web/src/dados/aluno/`. Nada de `export default`.
- Comentário explica o PORQUÊ, nunca o quê, e cita a fonte (`docs/26 §3`).
- NENHUMA dependência nova. Sem CDN, sem Google Fonts, sem biblioteca de ícone,
  sem biblioteca de gráfico. Ícones como SVG inline; gráficos como SVG escrito à
  mão, que é como todos os do projeto já são.
- Fórmula matemática: a decisão entre KaTeX e MathML está EM ABERTO
  (docs/27 §12). Não instale nada. Renderize como texto simples e registre a
  fonte como 'mock'.
- Os dois temas por custom property: valores em `:root`, redefinidos sob
  `@media (prefers-color-scheme: dark)` e sob `[data-tema]`, para o seletor
  manual vencer nos dois sentidos. A tabela dos seis papéis está em docs/24 §7.2.

# PISO DE QUALIDADE

- Celular primeiro. Nada transborda a 360px.
- 16px em todo input, senão o iOS dá zoom ao focar.
- Alvo de toque de 44px, foco de teclado visível, `prefers-reduced-motion`
  respeitado, `env(safe-area-inset-bottom)` na barra inferior.
- Contraste AA. É por isso que existe um token de ouro separado para texto.

# AS FERRAMENTAS DESTE REPOSITÓRIO — use, não ignore

Estão configuradas em `.mcp.json` e em `.claude/skills/`, e foram versionadas no
repositório de propósito. Trabalhar sem elas aqui é escolher trabalhar pior.

## MCP `chrome` — é assim que se verifica, não pelo código

Abra a tela de verdade a cada passo. `emulate` para **390x844x3, mobile, touch**
e confira transbordo, alvo de toque e o teclado abrindo. Depois volte para
1440x900 e confira o desktop.

⚠️ Isto não é zelo: o sprint mobile achou **três defeitos que nenhuma contagem de
media query pegaria**, porque só existem em runtime — um `display:flex` do login
vazando para o app inteiro, item de grid sem `min-width:0` escondendo outro, e
dois gráficos com largura fixa apesar do `viewBox`. Ler CSS não encontra nada
disso.

Use também `list_console_messages` e `list_network_requests`: erro de console e
requisição repetida são o que denuncia hook mal escrito.

## Skill `web-design-guidelines` — ao fim de CADA tela

São 103 regras de toque, safe-area, foco e formulário, e as regras vivem em
`regras.md` dentro do diretório da própria skill (a skill foi alterada de
propósito para ler a cópia local, não buscar por HTTP). Rode contra a tela que
você acabou de fazer, antes de passar para a seguinte. Achar tarde custa refazer.

## Skill `frontend-design` — quando o desenho não cobre

O export e os documentos não vão prever tudo. Quando faltar decisão visual — um
estado vazio que ninguém desenhou, um erro, uma densidade — use a skill em vez de
inventar, para o que você acrescentar continuar parecendo o mesmo produto.

## MCP `postgres` — confira antes de decidir que é mock

Está em modo de leitura e aponta para o Postgres do compose. **Antes de marcar
uma fonte como 'mock', olhe se o dado existe.** Foi assim que se descobriu que
`evento_agenda` já alimenta o e-mail do aluno e que `aluno_modulo_progresso`
nunca foi sincronizada. Um mock a mais é uma integração a menos.

## MCP `mobile` — não perca tempo

**Hoje não enxerga aparelho nenhum**: falta o Xcode completo, e o `simctl` não vem
no Command Line Tools (docs/20 §2). Se precisar de Safari real, registre como
não verificado em vez de tentar. E **nunca** use aparelho em nuvem com dado real
de aluno.

## O hook de lint

Um `PostToolUse` roda Biome no `.ts`/`.tsx` que você acabou de editar e devolve o
resultado na hora. Se ele reclamar, conserte antes de seguir — não acumule.

# COMO TRABALHAR

Vá por tela, e verifique cada uma no browser antes de passar para a seguinte —
o MCP `chrome` está configurado neste repositório. A ordem:

  1. tokens e casco (barra inferior, rail do desktop, os dois temas)
  2. Hoje
  3. Estudar + a questão em tela cheia + a folha de filtros
  4. Sessão de treino
  5. Provas + ficha + extrato
  6. Jornada + liga
  7. Tio Léo
  8. Login

Rode a cada passo:
  cd web && npm run lint && npm run typecheck && npm test
  cd api && ./.venv/bin/python -m pytest tests/ -q

# A ENTREGA

Além do código, escreva `docs/30-estado-da-implementacao.md`, gerado a partir de
`registro.ts` e não da sua memória, com três tabelas:

  1. LIGADO — a fonte, a rota que a alimenta, e em que telas aparece.
  2. DADO EXISTE, ROTA NÃO — a fonte, ONDE o dado está no servidor, e qual rota
     a desmockaria. Ordene por esforço crescente: esta tabela é a lista de
     tarefas mais barata do projeto.
  3. MOCK PURO — a fonte, o documento que a especifica, e do que ela depende.

E feche o documento com uma seção "o que fazer a seguir", em ordem, derivada das
tabelas 2 e 3.

⚠️ O documento tem de ser verdadeiro, não otimista. Se você mockou algo que
tinha endpoint, ele diz isso. Se uma tela ficou incompleta, ele diz isso. Um
inventário que esconde buraco é pior que nenhum, porque o próximo a mexer confia
nele.
```
