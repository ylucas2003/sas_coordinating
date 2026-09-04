# 35 — Plano de correções · 04/09/2026

> **Origem:** sessão de levantamento com a coordenação em 04/09/2026 — doze
> itens relatados de uso real, em produção (`portalsas.online`).
>
> **Escopo:** onze correções mais uma mudança estrutural de autenticação. Não é
> sprint de produto: nada aqui inventa funcionalidade nova, exceto a missão do
> dia (§7), que substitui um mock por dado de verdade.
>
> **Pronto quando:** nenhuma tela do aluno mostra nome de assunto que não bate
> com a questão entregue; o link "ver a resolução" abre no slide certo; o banco
> não tem prova inteira sem classificação; e a coordenação entra por três
> papéis distintos, com o aluno entrando só pelo Canvas.

---

## 0 · O levantamento — o que o código e o banco disseram

Mesma regra das Sprints 4, 5 e 6: **ler o código e medir antes de planejar**
([34 §0](34-plano-sprint-6.md)). Rendeu quatro achados que mudam o trabalho.

### 0.1 · Três dos "bugs" eram convenções deliberadas, não acidentes

O filtro de ano aceso ([§4](#4--filtro-de-ano-vira-aditivo)), o onboarding que
só aparece uma vez ([§6](#6--onboarding-do-banco-por-sessão)) e a tarja MOCK
invisível ([§10](#10--a-tarja-mock-acende-em-produção)) estão todos comentados,
datados e justificados no código. Não são descuido: são decisões que o uso
desmentiu.

Consequência prática: **cada uma exige reescrever o comentário que a defende**,
não apagá-lo. Comentário que sobrevive à decisão que ele explica vira armadilha
para quem ler depois.

### 0.2 · Duas ferramentas estavam quebradas em silêncio

| Ferramenta | Desde | Sintoma |
|---|---|---|
| `banco-questoes/pipeline/classificar.py` | migração de 22/08 | `FileNotFoundError` em qualquer matéria |
| `api/app/banco/resolucao.py` | plataforma nova do Ari | deep-link para galeria que não existe |

As duas falham em lugares que ninguém olha todo dia, e as duas explicam
sintomas que pareciam desconexos. A primeira é a causa de as quatro provas de
Química estarem sem assunto ([§3](#3--classificar-as-44-questões-órfãs)); a
segunda é a causa da "resolução estranha" ([§2](#2--deep-link-da-resolução)).

⚠️ **Um teste protegia o segundo defeito.** `api/tests/test_resolucao_banco.py`
crava as URLs erradas — foi escrito a partir do código, não do site. Passa com
o bug e quebra com o conserto.

### 0.3 · Medições em produção (04/09/2026)

| O quê | Número |
|---|---:|
| Questões sem assunto classificado | **44** (Química 40 · Física 4 · Matemática 0) |
| Deep-links de resolução quebrados | **146** |
| Contas de coordenação | **8** |
| Contas que entram pelo Canvas hoje | **2** (Leonardo 289 · Alanno 902) |
| Fontes não-reais na área do aluno | **20** (14 `mock` + 6 `sem-rota`) |

As 44 não estão espalhadas: são **provas inteiras**, 100% cada uma — IME 2022,
2023 e 2024 (1ª fase, Química) e IME 2025 (2ª fase, Química), mais quatro de
Física. É por isso que parecem muitas: IME Química de 2022 a 2025 é exatamente
o topo da coleção "Recentes", que ordena por ano.

### 0.4 · O banco local **não** é o banco de produção

Descoberto ao conferir as contas: local tem 3, produção tem 8. E o e-mail do
Leonardo diverge — `leonardobruno@aridesa.com` em produção, `.com.br` no local.

⚠️ **Regra que sai daqui:** contagem que vira decisão se mede em produção. As
duas bases divergiram em silêncio e nada avisou.

### 0.5 · O que **não** cabe nesta leva

O rename `materia` → `disciplina` foi pedido e está aceito, mas medido dá
**~5.500 ocorrências**, uma tabela, uma view e 8 colunas em 8 tabelas:

| Onde | Ocorrências |
|---|---:|
| `banco-questoes/` | 3.400 |
| `api/app/` | 870 |
| `web/src/` | 771 |
| `docs/` | 266 |
| `api/tests/` | 162 |
| `web/styles/` · `api/scripts/` | 49 |

No banco: tabela `materia`; view `v_nota_dimensoes`; colunas
`insight_ciclo.materia_codigo`, `modulo.materia_id`, `predicado_criterio.materia`,
`questao_vestibular.materia`, `questao_vestibular_topico.materia`,
`simulado.materia_id`, `topico_taxonomia.materia`,
`topico_taxonomia_assunto.materia`.

E a rota pública recebe `?materia=Física`, que já está em link salvo por aluno
— renomear sem rota de compatibilidade quebra link compartilhado.

**Decisão:** sprint própria ([§12](#12--fora-desta-leva-o-rename-de-materia)).
Enfiado aqui, engole os outros dez.

---

## 1 · Ordem de execução, e por que esta ordem

```
FASE A  desbloquear e consertar o silencioso     §2  §3  §7  §8  §8b
FASE B  banco de questões, a interface           §4  §6  §7
FASE C  a missão do dia deixa de ser mentira     §8
FASE D  honestidade sobre o que é mock           §10
FASE E  os três papéis de login                  §11
```

Três dependências mandam na ordem:

1. **`classificar.py` antes de tudo do banco** — sem a ferramenta, §3 não roda.
2. **As senhas antes do login** — tirar o SSO da coordenação sem redefinir a
   senha de quem entra por lá tranca duas pessoas do lado de fora (§11.1).
3. **A missão antes da tarja** — §8 remove `missaoDoDia` da lista de mocks, o
   que diminui o que §10 vai carimbar.

O login é o último de propósito: é o único item cujo erro derruba o acesso de
~900 pessoas.

---

## 2 · Deep-link da resolução

**Sintoma relatado:** a resolução de ITA 2025 · Química · Q36 "está beeem
estranha". **Alcance real: 146 questões.**

### O que está errado

`api/app/banco/resolucao.py` monta, para a plataforma nova:

```
https://comentarios.aridesa.com.br/ita?reference_id=1#gallery-1-36
```

A página do Ari declara `data-fancybox="gallery-stage-1"`. O hash do Fancybox é
`#<nome-da-galeria>-<índice>`, então o certo é `#gallery-stage-1-36`. Com
`gallery-1` nenhuma galeria casa e o lightbox não abre no slide pedido.

**O índice está certo — só o nome da galeria está errado.** Conferido item a
item contra a página baixada: índice 36 → `QUI-1_Q36.gif`, rótulo `36 - C`, e o
gabarito da q36 no nosso banco é **C**.

A 2ª fase idem: 46 âncoras na ordem Mat 1–10 · Quí 11–20 · Fís 21–30 ·
Port 31–45 · Redação 46 — exatamente o que `_ITA_F2_OFFSET_2025_MAIS`
`{_mat: 0, _qui: 10, "": 20}` assume. Os offsets estão certos.

A plataforma **antiga** (`servicos.aridesa.com.br`) declara `gallery-1` …
`gallery-8` de verdade, e lá o nosso link casa. Por isso ninguém viu antes: o
defeito existe só na plataforma nova, que é a das provas recentes.

### Alcance

| Prova | Questões |
|---|---:|
| IME 2023 · fase 1 | 40 |
| IME 2024 · fase 1 | 40 |
| ITA 2025 · fase 1 | 36 |
| ITA 2025 · fase 2 | 30 |
| **Total** | **146** |

### Passos

1. `resolucao.py`: `#gallery-1-` → `#gallery-stage-1-` (linhas 76 e 93) e
   → `#gallery-stage-2-` (linha 116).
2. Atualizar `api/tests/test_resolucao_banco.py` — ver ⚠️ do [§0.2](#02--duas-ferramentas-estavam-quebradas-em-silêncio).
3. No docstring, registrar que a conferência foi feita **contra a página**, e
   não contra o código. É o que impede o próximo teste de nascer errado igual.
4. ⚠️ A URL é gravada pelo **importador**, não calculada por requisição.
   Consertar a função não muda o banco: precisa de `UPDATE` nas 146 linhas ou
   reimportação.

---

## 3 · Classificar as 44 questões órfãs

### 3.1 · Consertar a ferramenta primeiro

`banco-questoes/pipeline/classificar.py` aponta para nomes de arquivo que
deixaram de existir no rename de 22/08:

| No código | No disco |
|---|---|
| `taxonomia.json` | `taxonomia-fisica.json` |
| `taxonomia_quimica.json` | `taxonomia-quimica.json` |
| `taxonomia_matematica.json` | `taxonomia-matematica.json` |

As **três** matérias. Verificado rodando: `FileNotFoundError`. A classificação
não parou por esquecimento — parou porque a ferramenta emudeceu, e as provas
que faltam são exatamente as que chegaram depois disso.

### 3.2 · Classificar

Fluxo do próprio pipeline: `classificar.py listar <prova>` imprime taxonomia e
enunciados → o Claude devolve um patch JSON → `classificar.py aplicar`. Regra
das tags: 1+ tópicos por questão, no máximo **3 blocos distintos**.

| Prova | Questões | Observação |
|---|---:|---|
| IME 2022 · f1 · Química | 10 | objetivas |
| IME 2023 · f1 · Química | 10 | objetivas |
| IME 2024 · f1 · Química | 10 | objetivas |
| IME 2025 · f2 · Química | 10 | **dissertativas** |
| ITA 2016 · f2 · Física | 3 | **dissertativas** |
| ITA 2008 · f1 · Física | 1 | objetiva |

As 13 dissertativas são as caras: vêm como página inteira e o texto extraído
tem sujeira de OCR. Podem exigir ler a imagem.

Ciclo completo, porque o JSON não é a fonte da verdade:
`scripts/exportar_banco_questoes.py` → classificar → `importar_banco_questoes.py`.

### 3.3 · Tirar o número cravado da interface

`web/src/telas/Banco/CartaoQuestao.tsx:221` e
`web/src/telas/Banco/FiltrosBanco.tsx:368` dizem **"40 sem classificação"**.
Hoje são 44 e depois disto serão 0. Número cravado em texto de tela envelhece
sozinho — trocar por contagem, ou tirar.

---

## 4 · Filtro de ano vira aditivo

**Decisão revertida:** a de 02/09, que abre todas as pílulas acesas.

O resultado já está certo — sem filtro, `filtros.anos === undefined` e a
listagem devolve todos os anos. O que mente é a pintura, e com ela o gesto.

Dois motivos, e o segundo é o que dói:

1. **A mesma ausência de filtro é desenhada de dois jeitos no mesmo painel.**
   Vestibular e Fase abrem apagados e significam "todos"; Ano abre aceso e
   significa a mesma coisa, quarenta pixels abaixo.
2. **O gesto ficou subtrativo, sozinho na tela.** Com tudo aceso, tocar 2025
   *remove* 2025. Para ver só 2025 o aluno apagaria 27 pílulas — não existe
   caminho de um toque para o recorte mais pedido.

**Novo comportamento:** vazio = nada aceso = todos os anos. Tocar 2025 = só
2025. Marcar todos na mão **mantém aceso**, não colapsa (decisão de 04/09).

Toca: `web/src/dominio/banco.ts` (`anosMarcados`, `alternarAno`),
`banco.test.ts:546-596` (~8 casos codificam o comportamento atual),
`telas/Banco/FiltrosBanco.tsx:213-231`,
`telas/Aluno/pecas/FolhaFiltros.tsx:170,176,262,347`, `tipos/banco.ts:137`.

O botão **"Limpar" já existe duas vezes** — no cabeçalho do painel e como chip
"Limpar tudo" no centro. Não construir de novo; garantir que sobrevivam ao §5.

---

## 5 · Disciplina e assunto vão para o centro

**Pedido:** tirar Matemática/Física/Química do painel lateral e levar para o
centro, exatamente onde estão hoje os cartões "Recentes/Arquivo" — que descem
para a lateral.

### Por que isto é um bug e não só gosto

O painel lateral é contêiner de rolagem próprio
(`max-height: calc(100dvh - 48px); overflow-y: auto`, `aluno-estudar.css:1784`).
No print que originou o relato ele estava rolado: sumiram o título "Filtros" e o
grupo MATÉRIA, e o que sobrou à vista foi ASSUNTO dizendo *"Escolha uma matéria
primeiro"*. **A instrução aponta para um controle fora da tela.** O que empurrou
a matéria para fora foram as 28 pílulas de ano do §4 — os dois são o mesmo cacho.

E matéria não é filtro qualquer: é o que **destrava** o assunto. A chave do
tópico é `(matéria, código)` — `1.1` é "Fundamentos" em Física e "Conjuntos e
Lógica" em Matemática. Sem matéria a rota devolve 400.

### O que quebra

Os cinco filtros são **um corpo só** (`CorpoDeFiltros`) vestido por duas cascas:
o `<aside>` de 236px no desktop e a folha que sobe do rodapé no celular. Mover
dois grupos para o centro quebra essa unidade — e no celular **não existe
centro** ([28 §4](28-banco-do-aluno.md) proíbe coluna lateral). A folha do
celular precisa de resposta própria.

⚠️ Os cartões de coleção carregam texto explicativo ("recorte da questão" /
"página inteira do caderno") e uma contagem cada. Em 236px não cabem assim —
viram segmentado, e o "como é" **tem de sobreviver**: é ele que explica a
diferença entre as duas leituras do acervo (migrations 0031/0033).

---

## 6 · Onboarding do banco, por sessão

A folha "Por que a prova vem inteira"
(`telas/Aluno/pecas/FolhaDaPaginaInteira.tsx`) hoje aparece uma vez e nunca
mais, por aparelho.

**Novo comportamento:** aparece **ao entrar no banco**, uma vez por sessão
(decisão de 04/09 — não mais "na primeira questão em modo página").

Conserto: `sessionStorage` no lugar de `localStorage`. A chave morre com a aba,
que é literalmente "nova sessão". O `try/catch` existente continua valendo — o
acessor *lança* em navegação privativa, e cair para "mostrar" é o lado seguro.

Efeitos colaterais:

- **"Ver de novo depois"** perde sentido ao lado de um "Entendi" que agora só
  vale pela sessão — provavelmente vira um botão só.
- A chave antiga fica órfã em ~900 aparelhos: `removeItem` de uma linha.
- Os comentários das linhas 16–33 descrevem a regra antiga; **reescrever**.

⚠️ Ressalva registrada: para quem abre o banco todo dia, folha que volta toda
sessão vira ruído, e o preço do ruído é o aluno aprender a fechar folha sem ler
— o que queima a próxima folha que importar. Decisão tomada de olhos abertos.

---

## 7 · "Turma ITM" → "turma ITA/IME"

O banco dá a régua: a `trilha` das turmas reais é `ITA`, e `section_original`
é `3o ITA AD` / `3o ITA MF`, vindas do Canvas. Zero linhas com "ITM".

**28 ocorrências no código.** As que o usuário vê:

| Arquivo | O quê |
|---|---|
| `web/index.html:6` | `<title>` |
| `web/src/componentes/layout/Rail.tsx:30` | subtítulo da marca |
| `web/src/telas/Alunos/Alunos.tsx:177` | "Alunos da turma ITM" |
| `web/src/telas/Aluno/PortaDoAluno.tsx:75` | "Turma ITM" |
| `web/src/dados/aluno/mocks.ts:237` | "Aprovados do ITM" |
| `api/app/chat/prompt.py:11` | **system prompt** — o LLM repete "ITM" na resposta |

O resto é metadado e documentação: `package.json`, `tokens.css`,
`main.py:126`, os quatro READMEs, `CLAUDE.md` e nove pontos em `docs/`
(incluindo o verbete "Aluno ITM" do [glossário](07-glossary.md)).

⚠️ **Também está no dado.** A conta `leonardobruno@aridesa.com` tem
`nome = "Coordenação ITM"` em produção. Vira `UPDATE`, e convém fazer junto do
§11, que já mexe nessa linha.

---

## 8 · Logo do Ari branco no login

O asset não é o problema: `ari-logo-branca.png` é branco de verdade (RGB médio
dos pixels opacos = 255,255,255) e já é o que a Porta do Aluno usa. **O azul é
pintado por CSS.**

A marca é desenhada por **máscara**: o alfa do PNG recorta a forma e a cor vem
de `background-color: var(--marca-cor)` (`aluno-casco.css:69-76`). Duas regras
disputam a variável no login:

```
.porta .alu-marca                  { --marca-cor: #ffffff }   (0,2,0)
:root[data-tema='dia'] .alu-marca  { --marca-cor: #1b3f8b }   (0,3,0)  ← ganha
```

`:root` + `[data-tema]` + `.alu-marca` são três seletores de peso de classe
contra dois. Ordem de import não resolve: especificidade vem antes. E
`data-tema` está **sempre** cravado no `<html>`, inclusive no login —
`pecas/tema.ts:57` roda no escopo do módulo e `App.tsx:9` importa `CascoAluno`
sem lazy, então o efeito dispara no carregamento do bundle em qualquer rota.

Resultado: todo aluno em tema "dia" (o padrão em aparelho claro) vê a marca
navy sobre o céu escuro do amanhecer. O comentário em `aluno-login.css:139-140`
já descreve a intenção certa — a especificidade é que não entrega.

Conserto: uma linha. O login do coordenador está correto (`<img>` direto no
arquivo branco, sem filtro).

---

## 8b · Sai o botão de abrir a prova

**Pedido:** tirar do aluno o botão de baixar o simulado.

O botão é `BotaoDaProva` em `web/src/telas/Aluno/ProvaFicha.tsx:141`, usado na
linha 110. O rótulo na tela é **"Abrir a prova"** — ele não baixa: pede uma URL
assinada de vida curta e abre em aba nova, no leitor do próprio aparelho
(o PDF nunca é embutido; `pdf.js` está fora por decisão, [27 §6](27-tio-leo.md)).

Cadeia inteira, para não deixar ponta solta:

| Camada | Onde |
|---|---|
| componente | `telas/Aluno/ProvaFicha.tsx:110,141-190` |
| hook | `dados/aluno/reais.ts:80` (`useArquivoDoSimulado`) |
| export | `dados/aluno/index.ts:29` |
| inventário | `dados/aluno/registro.ts:104` (`arquivoDoSimulado`) |
| rota | `api/app/routes/me.py:124` → `stats/aluno_dados.py:430` |

⚠️ `costura.test.ts` exige que todo hook exportado pelo `index.ts` tenha entrada
no `registro.ts`. Tirar o hook **e** a entrada no mesmo commit, senão o teste
quebra — e `docs/30` é gerado do registro, então ele também é regerado.

**Decisão pendente:** a rota do backend sai junto ou fica? Sem o botão ela deixa
de ser chamada, mas continua servindo URL assinada a quem souber o caminho. Dado
o histórico do projeto com token de download (PR #7), a recomendação é
**desligar a rota também** — porta fechada é melhor que porta sem maçaneta.

---

## 9 · A missão do dia deixa de ser mentira

### 9.1 · Por que o nome não bate com as questões

O cartão é mock (`dados/aluno/index.ts:133`), e o fixture pareia um nome com o
código de **outro** tópico:

```
MISSAO = { topicoCodigo: '7.2', nome: 'Termodinâmica', ... }
```

Na taxonomia real, **Física 7.2 = "Ondas e Acústica"**; Termodinâmica é **9.1**.
O cartão imprime o `nome` do mock; o treino consulta o banco real pelo `código`
do mock (`Treino.tsx:166-170`). Um lê a etiqueta, o outro lê o endereço — e
como o endereço existe e devolve questões, nada quebra. Só mente. O
`FÍSICA · 7.2` impresso no cartão é a prova visível.

### 9.2 · O pedido derruba a dependência que travava a missão

`registro.ts:313` registra `missaoDoDia` como mock dependente do **Sprint 6**
(`acertoPorAssunto + importanciaDoAssunto`). Mas essa dependência existia para
uma missão **personalizada**: `importância × (1 − meu acerto)`.

"O mesmo desafio para todos" derruba isso inteiro. Sem personalização, não
precisa saber o que cada aluno erra — e a missão sai do Sprint 6.

### 9.3 · Rota nova no backend (decisão de 04/09)

Sorteio determinístico pela data, igual para todos, **10 questões fixas**.

Pool medido em produção, só objetivas: **58 de 65 tópicos** têm 10+ questões
(Física 18/18 · Matemática 17/21 · Química 23/26) — quase dois meses de rodízio
diário sem repetir.

Três armadilhas:

1. **Fuso.** "Hoje" é America/Fortaleza. Em UTC o desafio vira às 21h — e como
   todos veem o mesmo, vira para todo mundo junto, bem na hora do estudo.
2. **`totalQuestoes` conta dissertativa**, e o treino filtra dissertativa fora.
   Corte de elegibilidade pelo número cru deixa sete tópicos passarem e a
   missão promete 10 entregando menos — a mesma classe de bug que estamos
   consertando.
3. **A razão tem duas metades e só uma sobrevive.** "Cai em 7% da prova do ITA"
   é calculável do acervo; "Você acerta 41%" é pessoal e some por definição.

`quantidade` 12 → 10 acerta os dois lados sozinho: `Treino.tsx:182` já usa
`missao.quantidade ?? QUESTOES_POR_SESSAO`.

⚠️ `registro.ts` sai de `estado: 'mock'`, e `docs/30` é **gerado** dele com
`npm test` quebrando se envelhecer. Entra no mesmo commit.

---

## 10 · A tarja MOCK acende em produção

**Decisão de 04/09: liga tudo.**

A infraestrutura já existe pronta. `telas/Aluno/pecas/TarjaFonte.tsx` desenha a
marca lendo o estado de `registro.ts` — nunca de prop, e o comentário explica
por quê: prop deixaria a tarja e o inventário divergirem. Duas marcas, já
distintas:

- **MOCK** — não existe nem dado. Desmockar é inventar produto.
- **SEM ROTA** — o servidor já sabe a resposta. Desmockar é uma rota curta.

O que impede de aparecer é uma linha:

```ts
if (!import.meta.env.DEV) return null;   // TarjaFonte.tsx:38
```

### Cobertura medida

| | Fontes |
|---|---|
| **Já têm tarja** (10) | `conquistas`, `cortePorMateria`, `depoimentos`, `extratoXp`, `liga`, `missaoDoDia`, `presencaNosSimulados`, `proximoSimulado`, `sequencia`, `zonaEDistancia` |
| **Sem tarja** (10) | `acertoPorAssunto`, `artefatosDoTioLeo`, `escolhaDaFilaDeTreino`, `esquadrilha`, `formulaMatematica`, `ganchoDeRetorno`, `importanciaDoAssunto`, `metaDoCiclo`, `meusErros`, `xp` |

Ligar a chave resolve metade de graça. A outra metade precisa que alguém passe
`fonte=` nos blocos que faltam — e algumas não têm superfície nenhuma
(`importanciaDoAssunto` tem `telas: ['— nenhuma']`), então o número real é
menor que 10.

### Onboarding por aba

Reaproveita o padrão do §6: folha explicando, uma vez por sessão, que aquela
aba mostra número de exemplo. Mesma mecânica, mesmo componente `Folha` — os
dois itens andam juntos de propósito.

⚠️ **Ressalva registrada.** `xp`, `liga`, `sequencia` e `conquistas` são o
coração da área do aluno. Carimbar MOCK neles diz ao aluno "o seu XP é
inventado" — o que é verdade, e é por isso que dói. O §9 tira `missaoDoDia` da
lista antes desta fase começar, o que reduz o estrago em um item.

---

## 11 · Três papéis de login

**O item mais arriscado da leva.** É o único cujo erro derruba o acesso de ~900
pessoas.

### O desenho pedido

| Papel | Como entra | Pode a mais |
|---|---|---|
| aluno | **só** Canvas (SSO) | — |
| coordenador | e-mail + senha | — |
| administrador | e-mail + senha | criar logins · alterar nota no painel |

### 11.1 · Primeiro passo, e é operacional

**Duas** contas entram pelo Canvas hoje: Leonardo (`canvas_user_id` 289) e
Alanno Chaves (902, login em 02/09 — usuário ativo). As duas perdem esse
caminho quando o SSO da coordenação sair.

Redefinir a senha das duas **antes** de virar a chave. A ordem inversa tranca
duas pessoas do lado de fora do próprio sistema.

### 11.2 · A conta de administrador

`leonardobruno@aridesa.com.br` é o admin. Em produção a conta existe como
`leonardobruno@aridesa.com` (sem `.br`), com `nome = "Coordenação ITM"` — então
são **três** mudanças na mesma linha:

1. `email` → `leonardobruno@aridesa.com.br`
2. `nome` → deixa de dizer "ITM" (§7)
3. `papel` → `administrador`

Corrigir a conta existente, e não criar outra: o `id`
`adc08f68-a57e-4081-9155-ca2b489972e7` é o que a trilha de auditoria referencia
(`evento_auditoria.ator_id`), e a regra "nunca apagar" de
`administracao.py:14-17` existe exatamente para isso. Conta nova deixaria o
histórico dele órfão.

`scripts/criar_coordenador.py` já **atualiza** quando o e-mail existe (linhas
116-121), mantendo o `id`, e grava a senha num arquivo em vez do stdout.

⚠️ A senha combinada é fraca para uma conta que altera nota, num sistema com
dado de menor de idade. O que atenua é o limitador de 5 tentativas/15 min em
`/auth/login` — mas ele é **em memória e por worker**, então protege menos do
que parece se a API subir com mais de um processo. Registrado; a decisão é da
coordenação.

### 11.3 · A armadilha do token

`get_current_coordenador` faz `tipo != "coordenador"` → 403, e aparece **39
vezes em 10 arquivos de rota**. Se o token do admin disser
`tipo: "administrador"`, o admin perde acesso a todas as telas de coordenação
de uma vez — o oposto do pedido.

O guard tem de aceitar **os dois** papéis, com um `get_current_administrador`
novo ao lado.

### 11.4 · Migration

Coluna `papel` em `usuario_coordenacao`, `NOT NULL DEFAULT 'coordenador'`. O
default já faz o que foi pedido: as oito contas existentes viram coordenador
sozinhas. Par `.down.sql`, como toda migration do projeto.

⚠️ Depois de migration que altera tabela, `docker compose restart postgrest` —
senão o schema cache devolve 404 e o 404 parece bug de código
([CLAUDE.md](../CLAUDE.md), armadilha 1).

O **nome da tabela** fica torto quando ela passa a guardar admin. Renomear é
caro (`.table("usuario_coordenacao")` espalhado pelo backend); fica registrado
aqui, não feito.

### 11.5 · Aluno só pelo Canvas

Sai o ramo `tipo == "aluno"` de `/auth/login`. Morrem junto:
`/auth/primeiro-acesso`, o "esqueci minha senha", os dois formulários da Porta
do Aluno e o `POST /alunos/{id}/resetar-acesso`.

O SSO **já foi testado em produção e funciona** (confirmado pela coordenação em
04/09) — o que derruba o alerta do docstring de `auth_canvas.py`, escrito antes
da Developer Key existir. Atualizar esse docstring: ele hoje diz que o fluxo
"só pode ser verificado quando `CANVAS_CLIENT_ID`/`SECRET` existirem", e isso
deixou de ser verdade.

⚠️ **Consequência permanente a aceitar:** Canvas fora do ar = nenhum aluno
entra. Para a coordenação não vale, porque eles ficam com e-mail + senha.

### 11.6 · Coordenação não entra pelo Canvas

Sai o ramo do coordenador em `_sessao_para` (`auth_canvas.py`) e o
`canvas_user_id` da tela de criação. A coluna **fica** — apagar perde dado —, só
deixa de valer para login.

### 11.7 · O que vira admin-only

- `PATCH /notas/{aluno_id}/{simulado_id}` — alterar nota pelo painel.
- Só as rotas de **conta** de `/administracao`. A listagem de acesso dos alunos
  ("quem já fez primeiro acesso, quem nunca entrou") é trabalho diário de
  coordenação e fica onde está. O arquivo precisa ser **dividido**, não
  promovido inteiro.

⚠️ `PATCH /notas` não é o único caminho que escreve nota: o ingest de planilha e
o sync do Canvas também escrevem. O pedido foi "alterar notas no painel", então
só o PATCH muda — dito em voz alta para não parecer que fechamos uma porta que
segue aberta por trás.

### 11.8 · Front

`telas/Login/modos.ts` (hoje `type Modo = 'aluno' | 'coordenador'`),
`Login.tsx`, `PortaDoAluno.tsx`, `Administracao.tsx`, `servicos/sessao.ts`
(`sas_tipo`) e `tipos/dominio.ts` (`TipoSessao`).

---

## 12 · Fora desta leva: o rename de `materia`

Aceito, dimensionado em [§0.5](#05--o-que-não-cabe-nesta-leva), adiado. Quando
for feito, três coisas não podem faltar:

1. **Migration com par `.down.sql`** para as 8 colunas, a tabela e a view.
2. **Compatibilidade na rota**: aceitar `?materia=` e `?disciplina=` por um
   tempo, senão link salvo por aluno quebra em silêncio.
3. **`banco-questoes/` é 3.400 das ~5.500 ocorrências** e não roda em
   requisição nenhuma — dá para renomear em fase separada, depois do resto.

---

## 13 · Riscos, em uma tabela

| # | Risco | Onde | Mitigação |
|---|---|---|---|
| 1 | Trancar coordenador fora | §11.1 | redefinir senha das 2 contas com Canvas **antes** |
| 2 | Teste protege o defeito | §2 | atualizar `test_resolucao_banco.py` no mesmo commit |
| 3 | Schema cache devolve 404 | §11.4 | `restart postgrest` depois da migration |
| 4 | Tarja carimbar o placar do aluno | §10 | §9 antes, tirando `missaoDoDia` da lista |
| 5 | Local ≠ produção | §0.4 | contagem que vira decisão se mede em produção |
| 6 | Folha por sessão vira ruído | §6 | medir; se incomodar, voltar a "uma vez" é uma linha |
| 7 | Missão promete 10 e entrega menos | §9.3 | elegibilidade conta **só objetivas** |
