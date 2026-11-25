# 46 — Cadastro de aluno no Canvas pela tela

> **Estado em 25/11/2026:** escrito no branch `feat/cadastro-canvas`, **fora de
> produção** e **sem nenhuma escrita real no Canvas ainda**. Testes verdes
> (backend e front), tela conferida no navegador contra o Canvas real só com
> leitura. O que falta para ligar está no §5 — e o primeiro passo dele depende
> de autorização.

O SAS só **lia** quem é aluno: o sync traz do Canvas quem está matriculado nos
cursos de provas. Criar a conta e matricular era trabalho do administrador do
Canvas, à mão. Este documento é a tela que faz isso pelo SAS: **um aluno por
vez** ou **em lote, por planilha**.

---

## 1 · As decisões (25/11/2026)

| Pergunta | Decisão | Por quê |
|---|---|---|
| Quem usa | **Só administrador** do SAS | O token do SAS é administrador pleno da conta do colégio; criar login já é poder de administrador (docs/35 §11.7) |
| Onde matricula | **Pacote da série**: escolhe-se série (e sede, no 3º); o SAS acha os cursos do ano no Canvas pelo nome | No 3º são 19 cursos; marcar à mão é esquecer um |
| A senha | **O Canvas manda o e-mail** e o aluno a cria | Nenhuma senha de menor passa pelo SAS |
| Quem é cadastrado | **Só aluno** nesta versão | Professor e responsável usam o mesmo encanamento depois |

Os dois caminhos são os que a API do Canvas oferece:

- **um por vez** → REST (`POST /accounts/1/users` + uma matrícula por curso);
- **em lote** → **SIS Import** de CSV, o mesmo que o administrador do Canvas já
  sobe à mão.

## 2 · O que o Canvas mostrou (25/11/2026, só GETs)

Nada disto se deduz do código, e tudo isto decidiu o desenho:

- **O token pode tudo.** `GET /accounts/self/permissions` deu `true` em
  `manage_user_logins`, `manage_sis`, `import_sis`, `add_student_to_course`,
  `manage_sections_add` e o resto. Um bug aqui cria conta de verdade.
- **O login é a matrícula.** 1.048 dos 1.104 alunos do curso 577 entram com o
  `sis_user_id` como login; o `sis_user_id` é a matrícula de **8 dígitos** (1.097
  de 1.104; os outros são contas de teste). Os e-mails são quase todos pessoais
  (gmail).
- **Um aluno do 3º está em 19 cursos** — Física 1–5, Matemática 1–5, Química
  1–4, Português 1–2, Inglês, Redação e Simulados —, todos com ~1.110 alunos. A
  **sede** só existe como section no curso de **Simulados** (`3o ITA AD`,
  `3o ITA MF`, `AD Online`, `MF Online`, `PB`, `Escolas Parceiras SAS`,
  `Proposito (Objetivo)`); os outros têm só a section padrão. O 1º e o 2º ano
  têm **um** curso cada (Avaliações).
- **A section padrão do Simulados é a sede fantasma**: quem cai nela vira "Sem
  section no Canvas" no SAS (os 46 alertas falsos de 06/11). Ela fica fora da
  lista de sedes.
- **As SIS IDs são os próprios ids numéricos** (curso 577 → `"577"`), com uma
  exceção que importa: a section do 1º ano é `"858a"`. O CSV só entende SIS ID;
  por isso o lote nunca usa o id do Canvas no lugar dela.
- **Só há um provedor de login**, o nativo (`canvas`, id 105). Sem SSO.
- **Isso já é feito à mão.** A conta pessoal do Leo (289) fez SIS Imports em
  04/08, 25/08, 08/09, 28/09 e 06/11 (em 06/11: 108 usuários num envio, 108
  matrículas em outro). Nenhum em batch mode.
- **Ainda há cursos "disponíveis" de 2021 a 2025.** A tela só oferece o ano
  corrente em diante.

## 3 · Como funciona

Código: `api/app/canvas_sync/cadastro.py` (domínio e conversa com o Canvas),
`api/app/routes/cadastro_canvas.py` (rotas), `web/src/telas/Administracao/CadastroCanvas.tsx`
(tela, em `/administracao/cadastro-canvas`, com cartão só de administrador no hub).

### 3.1 · O pacote da série

Lido do Canvas **a cada chamada**, nunca guardado: todo curso
`{ano} {série}o ITA/IME …` do ano entra; o curso de provas da série
(Simulados no 3º, Avaliações no 1º e 2º) dá as sedes. Curso novo que a escola
criar entra sozinho. Busca cursos publicados **e não publicados**: na virada do
ano a escola matricula antes de abrir o curso.

### 3.2 · Um por vez — `POST /administracao/cadastro-canvas/aluno`

1. Procura a conta pela SIS ID (`GET /users/sis_user_id:{matrícula}`).
2. **Existe** → não é tocada (nem nome, nem e-mail, nem senha). Se o nome
   digitado não bate com o do Canvas (primeiro e último nome, sem acento), a
   rota devolve **409 sem escrever nada** e a tela pergunta "é a mesma
   pessoa?". É a trava contra o erro mais caro: uma matrícula digitada errado
   que é de OUTRO aluno, que seria matriculado em 19 cursos.
3. **Não existe** → cria com login = SIS ID = matrícula,
   `force_self_registration` e o e-mail (obrigatório só aqui).
4. Matricula em cada curso do pacote, `active` e **sem notificação** (19 avisos
   de "você foi matriculado" seriam só ruído). A sede só no curso de provas.
5. **Repetível**: o que já existe é reconhecido (`GET /users/:id/enrollments`) e
   não é POSTado de novo. Falhou no meio → "Tentar de novo" faz só o que falta.
6. **Mudar de sede não é feito por aqui**: se o aluno já está no curso de provas
   em outra sede, o curso volta como `outra_sede` — acrescentar a nova o
   deixaria em duas sedes, e o SAS o contaria nas duas.

### 3.3 · Em lote — prévia, envio, acompanhamento

- **Prévia** (`POST …/lote/previa`, multipart): lê `.xlsx` ou `.csv` (o `;` do
  Excel em português, matrícula que virou número, cabeçalho com acento) e diz,
  linha a linha, o que aconteceria. **Não escreve nada.** Quem o sync já trouxe
  é reconhecido pelo banco do SAS, sem chamada ao Canvas; só as matrículas
  desconhecidas são perguntadas a ele.
- **Envio** (`POST …/lote`): confere **tudo de novo** (não confia na prévia) e
  recusa o lote inteiro se uma linha tiver erro. Sobe **um** SIS Import com:
  - `users.csv` **só com as contas novas** — mandar uma conta existente
    reescreveria nome e e-mail dela;
  - `enrollments.csv` com todas as linhas;
  - `canvas_password_notification=true` e provedor `canvas` (o e-mail de criar
    senha);
  - `skip_deletes=true`, e **nunca** batch mode nem diffing: nesses, quem falta
    no arquivo é apagado ou suspenso.
- **Acompanhamento**: a tela consulta o import a cada 3 s enquanto ele processa.
  O histórico ("Lotes enviados pelo SAS") **não tem tabela**: são os SIS
  Imports cujo autor é o dono do token. O que alguém sobe pela tela do Canvas
  sai com a conta pessoal e não aparece.

### 3.4 · Auditoria e LGPD

`aluno_cadastrado_no_canvas` e `lote_enviado_ao_canvas`, canal `acesso` — fora
da trilha que o chat e o MCP leem. O detalhe leva a **matrícula**, nunca nome
nem e-mail de aluno. Nenhum serviço de terceiro novo: a escrita vai ao Canvas,
que já é o sistema da escola.

## 4 · Decisões pequenas que o código tomou

- A matrícula precisa de **exatamente 8 dígitos**, e o erro de 7 explica o zero
  à esquerda que o Excel come. É uma constante (`DIGITOS_DA_MATRICULA`).
- A sede da planilha casa por nome exato, id ou SIS ID; senão por palavra
  inteira, **só se uma sede casar** ("AD" casa com duas e é erro, não chute).
- O 409 da rota de um aluno é **só** o "confirme o nome"; a recusa do Canvas
  (login já em uso, por exemplo) é 422, para a tela não oferecer "confirmar"
  onde confirmar não resolve.
- **O e-mail é campo + botão de domínio** (25/11, pedido do dono): digita-se o
  começo e escolhe-se `@gmail.com` (o padrão, ~86% dos alunos), `@hotmail.com`,
  `@outlook.com`, `@icloud.com`, `@yahoo.com.br`, `@aridesa.edu.br` ou "outro
  domínio". Com "@" no campo vale o digitado e o botão desliga — e o campo
  **não** separa o domínio sozinho enquanto se digita, porque `fulano@gmail.com.br`
  seria cortado no `.com`. O endereço final aparece por extenso embaixo: um
  erro ali é o aluno que nunca recebe o e-mail da senha. O campo é `type="text"`
  com `inputMode="email"`: com `type="email"` o navegador barraria o envio por
  falta de "@".
- O cartão do hub tem subtítulo fixo: o dado vivo dele custaria duas chamadas
  ao Canvas a cada visita ao hub.

## 5 · O que NÃO foi verificado — e como verificar

**Nenhuma escrita real foi feita.** No navegador foram conferidos, contra o
Canvas de verdade e só com leitura: o pacote (19 cursos, 7 sedes), o 409 de uma
matrícula real com nome trocado, a prévia de uma planilha com todos os erros
possíveis, o diálogo de confirmação (cancelado) e a tela no celular e no tema
escuro.

Falta ver escrevendo, e **não dá para ver pela tela**: o pacote aponta para os
cursos reais, e um aluno de teste apareceria na lista de todos os professores
do 3º. Para isso existe o ensaio, que só toca o curso sandbox 694 e desfaz tudo
no fim:

```sh
cd api && python -m scripts.ensaio_cadastro_canvas --email <um e-mail que você lê>
```

O que ele responde:

1. O Canvas aceita o corpo do `criar_usuario_aluno`?
2. **Quantos e-mails chegam por conta, e qual** — `send_confirmation` com
   `force_self_registration` deveria mandar um só, o de terminar o cadastro e
   criar a senha. Se chegarem dois, tira-se o `send_confirmation`.
3. O mesmo POST de matrícula duas vezes duplica? (O código não depende disso —
   ele lista antes —, mas a resposta diz quanto a trava vale.)
4. O SIS Import com `canvas_password_notification` manda o mesmo e-mail?

⚠️ Roda contra o Canvas de **produção** (é o único). Precisa de autorização de
quem o administra — e combinar com o Leo, porque o lote do SAS passa a fazer o
que ele faz à mão (§2).

Depois do ensaio: deploy normal (sem migration — não há tabela nova), e o
primeiro uso real de preferência com um aluno só.

## 6 · Fica para depois

- Professor (`TeacherEnrollment` nos cursos dele) e responsável (observador
  ligado ao aluno, `PUT /users/:id/observees/:id`).
- Mudança de sede e desmatrícula — hoje no Canvas, de propósito.
- Os cursos fora do pacote (Minicurso de Cálculo, Simulado Nacional, SAS
  Preparatório): a escola matricula neles por outro critério, que não está
  escrito em lugar nenhum.
