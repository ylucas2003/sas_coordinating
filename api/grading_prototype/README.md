# Protótipo — Correção Automatizada de Questões Discursivas (ITA/IME)

Protótipo isolado de correção automatizada por IA para questões discursivas
de Matemática, Física e Química nível ITA/IME. **Não importa nada de
`app/*`** — não toca rotas, banco ou config de produção. Roda como script
standalone, pensado pra validar a ideia antes de decidir acoplar (ou não) na
arquitetura real do SAS.

## Filosofia

- A IA **nunca atribui a nota final** — só reporta, por critério de uma
  rubrica, se a resposta do aluno demonstrou o conhecimento esperado
  (`atendido` / `parcial` / `nao_atendido` / `nao_avaliavel`), com
  justificativa e evidências citadas da resposta.
- Um motor determinístico em Python puro (`pontuacao.py`, zero import de
  `openai`) calcula a nota 0-10 a partir desses vereditos + os pesos da
  rubrica. Casos degenerados (critério sem veredito, id duplicado,
  `nao_avaliavel`, pontuação <= 0 na rubrica) nunca passam silenciosamente —
  viram avisos no relatório.
- A rubrica é gerada a partir do gabarito oficial em **duas etapas**
  (gerar → criticar/reescrever) pra capturar a intenção pedagógica de cada
  critério, não o método específico do gabarito — permitindo que o aluno use
  métodos alternativos válidos sem perder pontos injustamente. A crítica
  testa cada critério contra métodos alternativos simulados e proíbe
  critérios de apresentação/verificação, redundantes ou com peso invertido.
- Cada critério carrega **`resultados_esperados`**: valores/conclusões
  extraídos do gabarito (ex: `n = 15`, `área = 30`) que qualquer método
  válido produz. É a âncora que permite ao avaliador conferir as contas do
  aluno **sem nunca ver o gabarito**.
- **Gabarito oficial é obrigatório — o protótipo NÃO gera solução por IA.**
  Chegamos a testar geração automática de solução quando `gabarito.txt`
  estava ausente, mas o próprio teste (nas 10 questões da prova ITA
  Matemática 2026 — 2ª Fase) expôs erros matemáticos reais mesmo no `gpt-4o`
  (ex: contagem de pontos inteiros e potência de matriz erradas). Uma rubrica
  construída sobre uma solução errada corrige o aluno pelo critério errado —
  risco alto demais pra manter. Decisão: `gabarito.txt` é obrigatório; se
  ausente, `carregar_questao` levanta `FileNotFoundError`.
- O avaliador (`avaliador.py`) recebe enunciado + figura (se houver) + rubrica
  + resposta do aluno (fotos e/ou texto já transcrito), e **nunca recebe o
  gabarito** — isso é reforçado no código, não só no prompt.
- **A LLM avaliadora não escolhe veredito.** Ela responde perguntas FACTUAIS
  por critério (evidências citadas, método usado, resultado declarado,
  comparação com o esperado) e o veredito é derivado em código
  (`pontuacao.derivar_veredito`) — a política de correção (método certo +
  conta errada ⇒ `parcial`; erro punido uma única vez; follow-through
  julgado pelo método) é determinística, não interpretação do modelo.
- **Fluxo de dois níveis (avaliador barato + árbitro forte).** Por padrão o
  `gpt-4o-mini` avalia tudo e critérios com gatilho determinístico —
  qualquer desconto, equivalência algébrica alegada, evidência copiada da
  rubrica, `confere` não verificável textualmente, contradição com a
  rubrica — são re-avaliados individualmente pelo `gpt-4o`
  (`--modelo-escalonamento`; string vazia desliga). Assimetria deliberada:
  **nota de aluno não desce sem confirmação do modelo forte.**
- A figura do enunciado é **opcional**: questões puramente analíticas (comum
  em Matemática) rodam em modo texto-only; Física/Química com diagrama usam
  o caminho multimodal. O resto do pipeline não muda.

## Instalação

```bash
cd api
pip install -r grading_prototype/requirements.txt   # instala Pillow no venv já existente
```

`openai` e `python-dotenv` já estão pinados em `api/requirements.txt` — o
protótipo reaproveita o mesmo venv, sem tocar no manifesto de produção.

Configure `OPENAI_API_KEY` no `.env` de `api/` (mesmo arquivo já usado pela
aplicação).

## Fluxo recomendado

```bash
cd api

# 1. Gerar as rubricas persistidas (uma vez por questão) e REVISAR à mão:
python -m grading_prototype.gerar_rubrica --todas
#    -> salva rubrica.json na pasta de cada questão. Abra, ajuste critérios/
#       pesos se necessário e marque "revisada_por_humano": true.

# 2. Corrigir a prova de um aluno (usa as rubricas persistidas; questões em paralelo):
python -m grading_prototype.corrigir_prova --aluno <aluno_id>

# 3. Quando houver notas humanas, medir a concordância:
python -m grading_prototype.validar
```

A rubrica persistida garante que **todos os alunos da mesma questão são
corrigidos pela mesma rubrica** (justiça) e evita pagar as 2 chamadas de
geração por aluno. Se `rubrica.json` não existir na hora da correção, ela é
gerada e salva automaticamente (o próximo aluno reusa). `--regerar-rubrica`
força regeneração. Se o `gabarito.txt` mudar depois da geração, o pipeline
avisa (hash divergente).

### Outros comandos

```bash
# Validar a plumbing sem gastar tokens (carregamento, encoding, relatório):
python -m grading_prototype.comparar_modelos \
    --questao grading_prototype/dados_exemplo/<questao_id> --dry-run

# Comparar modelos AVALIADORES sobre a MESMA rubrica (persistida ou gerada
# com --modelo-rubrica), contra a nota humana se houver:
python -m grading_prototype.comparar_modelos \
    --questao grading_prototype/dados_exemplo/<questao_id> --aluno <aluno_id>

# Comparar a GERAÇÃO de rubrica entre modelos (não salva rubrica.json):
python -m grading_prototype.testar_rubrica \
    --questao grading_prototype/dados_exemplo/<questao_id>

# Checagem do motor de nota (sem API key):
python -m grading_prototype.pontuacao
```

### O que esperar de uma execução bem-sucedida

- Nota por questão + média (parcial, se alguma questão falhou — falhas são
  listadas explicitamente, nunca somem do relatório em silêncio).
- Avisos do motor de nota por questão (critério sem veredito, `nao_avaliavel`
  pedindo revisão humana, etc).
- Total de tokens de entrada/saída da execução (custo visível).
- JSON completo em `resultados/` com todos os artefatos (rubrica usada e sua
  origem, avaliação com evidências citadas e resultado declarado pelo aluno,
  nota detalhada por critério, uso de tokens, metadados de reprodutibilidade
  — modelo, temperatura, hash dos prompts, timestamp).

Sucesso nesta fase ainda é **qualitativo** — é você olhando os vereditos e
julgando se fazem sentido. `validar.py` agrega MAE/viés/% dentro da margem
quando houver notas humanas em escala.

## Convenção dos dados de exemplo

Dados de aluno (fotos de letra, notas) são sensíveis — as pastas abaixo
estão no `.gitignore`, só a estrutura e este README ficam versionados.

```
grading_prototype/dados_exemplo/
  <questao_id>/                    # slug livre, ex: fisica_02_plano_inclinado
    enunciado.txt                  # obrigatório — texto do enunciado
    enunciado_figura.jpg           # opcional — figura do enunciado (.jpg/.jpeg/.png), se houver
    gabarito.txt                   # obrigatório — solução oficial completa, em texto (ver Filosofia)
    rubrica.json                   # gerado por gerar_rubrica.py — editável; marque revisada_por_humano
    metadata.json                  # opcional — {"materia": "fisica", "nota_maxima": 10.0, "anulada": false}
    respostas/                     # obrigatório só pra corrigir/comparar (não pra rubrica)
      <aluno_id>/                  # use pseudônimo, não nome real
        pagina_01.jpg              # foto/scan da resposta manuscrita — OU use resposta.txt
        pagina_02.jpg               # opcional — páginas adicionais (ordenação natural: 2 < 10)
        resposta.txt               # alternativa a pagina_*.jpg — resposta já transcrita em texto
        nota_humana.json           # opcional — {"nota": 7.5, "nota_maxima": 10.0, "observacoes": "..."}
                                    # ausente = ainda não há nota humana (uso real de correção)
```

Pelo menos um de `pagina_01.jpg` ou `resposta.txt` é obrigatório — pode ter
os dois. `metadata.json.anulada: true` faz todos os CLIs pularem a questão
(não faz sentido montar rubrica pra questão sem solução oficial válida).

Se a questão não tiver figura, simplesmente não crie `enunciado_figura.*` —
`dados.py` detecta a ausência e o pipeline segue em modo texto-only. Fotos
com EXIF de rotação (celular em pé) são corrigidas automaticamente antes do
envio.

## Placeholders tuneáveis (`config.py`)

- `PESO_CREDITO_PARCIAL = 0.5`: crédito dado a um critério `parcial`, como
  fração do critério `atendido`.
- `MARGEM_ACEITAVEL_NOTA = 1.0`: diferença (pontos, base 10) considerada
  "dentro da margem" da nota humana — usada no relatório e no `validar.py`.
- `MAX_DIMENSAO_IMAGEM_PX = 2000` / `DETALHE_IMAGEM = "high"`: custo de
  tokens de visão vs. legibilidade das fotos.
- `MAX_WORKERS_CORRECAO = 4`: questões corrigidas em paralelo por
  `corrigir_prova.py`.
- `TEMPERATURA = 0.0`: usada em todas as chamadas de LLM (reprodutibilidade
  melhor-esforço; a API não garante determinismo).

## Questões já extraídas

`dados_exemplo/ita_mat_2026_2f_q01` a `q10`: as 10 questões da prova de
Matemática — 2ª Fase — ITA 2026, com `enunciado.txt` (transcrito de
`matematica_2026_2f.pdf`) e `gabarito.txt` (transcrito de
`ITA_2026_Solucoes.pdf`, o gabarito oficial). **`q06` foi anulada pela
banca** (`metadata.json` tem `"anulada": true`) — pulada por todos os CLIs.

Há também uma resposta real de aluno em
`respostas/aluno_13_22/resposta.txt` em cada questão, transcrita de uma
prova manuscrita real — usada pra validar o pipeline de ponta a ponta. Não
tem `nota_humana.json` (ainda não há correção humana desse aluno pra
comparar) — a nota reportada é só a calculada pelo pipeline.

## Custo em escala

Medições reais de custo (baseline de 1,58¢/questão/aluno) e o plano de
otimização para volume estão em [`CUSTO_EM_ESCALA.md`](CUSTO_EM_ESCALA.md).
A implementação futura principal é a **Batch API em duas ondas** (−50% em
tudo, correção não é tempo-real; $7,92 por 1000 alunos/questão, chegando
a ~$0,37 com rubricas maduras). Nada de lá é necessário na fase de
validação.

## Suposições / limitações desta fase

- Resposta do aluno aceita fotos individuais (JPG/PNG) e/ou texto já
  transcrito (`resposta.txt`) — não um PDF único com várias páginas. Se
  precisar processar PDF diretamente, adicionar extração de páginas (ex:
  PyMuPDF) em `imagem.py`/`dados.py` é a única mudança necessária.
- Sem persistência em banco — tudo roda a partir de arquivos locais e salva
  JSON em `resultados/`. Migração pra rotas/DB fica pra depois de validado.
- Sem retries automáticos nas chamadas de LLM (mesmo padrão do resto do
  repo) — uma falha de uma questão/modelo não aborta as demais.
- Vereditos `nao_avaliavel` e critérios sem veredito valem 0 pontos
  provisoriamente e geram aviso de revisão humana — o protótipo não decide
  sozinho o que fazer com resposta ilegível.
