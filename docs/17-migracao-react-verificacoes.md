## 17 — Migração para React: verificações e pendências

Companheiro de [16-plano-migracao-react.md](16-plano-migracao-react.md), que está
**concluído**. Aqui fica o que foi verificado, o que **não** foi, e o que sobrou.

## Verificações automatizadas

Da raiz de `web/`:

```sh
npm run typecheck     # tsc --noEmit
npm test              # Vitest — 94 testes sobre src/dominio/
npm run build         # typecheck + build do Vite
```

Os testes cobrem a lógica de domínio, não markup. O que eles protegem, por arquivo:

| Arquivo | O que garante |
|---|---|
| `dominio/painel.test.ts` | Esquemas de coluna ITA/IME por fase; fórmulas de média (ITA soma linguagens como bloco, IME pesa exatas 3/2,5/2,5); ausência é `null` e nunca zero; aluno sem nota é "neutro", não "cortado"; ranking, KPIs e estatísticas da ficha de nota |
| `dominio/simulados.test.ts` | Filtros AND entre categorias e OR dentro; contagem por chip ignorando o próprio eixo; calendário que não anula o próprio filtro de data |
| `dominio/ciclos.test.ts` | Período que **encosta** no intervalo entra no recorte (não exige contenção) |
| `dominio/evolucaoAluno.test.ts` | Corte 5 só no recorte exato Inglês + ITA + F1; séries por matéria vs. agregada por ciclo; nota 0 marcada como provável abandono |
| `dominio/importacao.test.ts` | Faixas da barra (0-30% upload, 30-95% processamento); dedup de eventos; etapa mais avançada, não a última |
| `dominio/chatStream.test.ts` | Reducer do SSE: tokens em ordem, traces fechando fora de ordem, `end` substituindo o texto cru, extração de artefatos |
| `componentes/ui/ordenacao.test.ts` | Nulos afundam nos dois sentidos; coluna ordinal usa ordem semântica, não alfabética |

## Verificação em browser

Feita com Playwright + Chrome instalado, contra o dev server, com sessão
simulada e API stubada. O harness vive fora do repositório (scratchpad da
sessão), então **não roda em CI** — o que ele cobriu:

| Tela | Verificado |
|---|---|
| Login | Guard redireciona ao `/login`; troca de modo aluno/coordenação; olho da senha; 401 mostra "Credenciais inválidas" **sem recarregar**; primeiro acesso com suas validações; login bem-sucedido entra no app |
| Painel | Colunas por vestibular e fase; ordenação ranking ↔ A–Z; separadores Top 10/50/100; busca; filtro de sede; troca de ciclo; ficha de nota com KPIs de comparação; tooltip de ajuda |
| Alunos | 24 linhas; filtro por chip com contagem cross-filtered; ordenação com nulos ao fim nos dois sentidos; clique na linha navega |
| Simulados | Filtros nas 4 seções; calendário de 12 meses com dias clicáveis; diálogo de agendamento com preview do nome e validação |
| Ciclos | Filtro de período que aceita ciclo apenas encostando no intervalo; diálogo de novo ciclo |
| Ficha de simulado | KPIs, histograma, quebras, notas individuais; edição de nota em dois passos (form → diff → confirmar) com validação |
| Ficha de ciclo | Hero com deltas, linha temporal, insights, blocos por matéria com selo de eliminatória, dados avançados |
| Ficha do aluno | Gráfico com tooltip; séries por matéria; heatmap; similares; menu de exportação; edição de nota |
| Área do aluno | Hero com anel de posição; evolução por matéria; conquistas com progresso; lista e detalhe de simulado; recarregar mantém a rota; troca de senha com validações |
| Importar | Upload → polling → sucesso; barra e etapas; log de eventos; resumo; **polling para no fim** |
| Chat | Cmd+K abre; histórico com markdown; lista de conversas; streaming com trace de tool, título, texto final e artefatos (gráfico + CSV); Esc fecha só com foco dentro |
| Geral | Todas as rotas renderizam com topbar e FAB; navegação pela topbar; busca global; aluno não alcança rota de coordenação |

## Verificação estática da config de produção

Feita sem Docker e sem nginx instalados, lendo a config contra o build real.
Não substitui subir a stack, mas cobre o que é decidível no papel:

| O que | Resultado |
|---|---|
| Premissa do `^~ /assets/` | O build emite **um** arquivo na raiz (`index.html`) e todo o resto sob `assets/`, com hash. As 4 URLs que o app pede resolvem, nenhuma escapa de `/assets/`. |
| `/assets/inexistente.js` | `try_files $uri =404` → 404 honesto, sem cair no fallback |
| `/painel` | prefixo `/` → fallback `/index.html` → regex `.html` → `expires -1` |
| `/api/alunos` vs `/api/docs` | a regex de `/docs` vence o prefixo; `/api/alunos` segue para o proxy |
| `add_header` dentro de `location` | **nenhum** — os headers de segurança valem em todos os caminhos, e o cache dos assets usa `expires`, que não os anula |
| CSP vs. o que o app pede | `script-src`/`style-src 'self'` bastam (nada inline no HTML servido); `font-src` cobre os woff2; `img-src` cobre o data-URI do checkbox e o `blob:` da exportação PNG |

Um achado veio daí: **`/login.html` retornava 404**. O bloco `location ~* \.html$`
não tem `try_files`, então um `.html` inexistente não cai no fallback. Resolvido
com um `location = /login.html { return 301 /login; }` — match exato, e não
fallback no bloco `.html`, porque com fallback qualquer `.html` inexistente
devolveria o app com status 200, que é o que as demais regras existem para evitar.

## Não verificado — precisa de máquina com Docker e login real

1. **Dados reais.** Toda a verificação usou fixtures. Cada tela precisa ser
   aberta com login de coordenação contra o banco de verdade e comparada com o
   comportamento anterior.
2. **Os dois `nginx.conf`.** Nem `nginx -t` nem `docker` estavam disponíveis no
   ambiente da migração. Conferir antes do primeiro deploy:
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build`
   - rota profunda colada na barra (`https://…/alunos/A023`) — valida o `try_files`
   - `/assets/inexistente.js` deve dar **404**, não HTML com status 200
   - console sem violação de CSP — `script-src` e `style-src` perderam o
     `'unsafe-inline'`, então uma violação apareceria como estilo faltando
     (a análise estática acima não achou nada que precise das diretivas
     removidas, mas só o browser confirma)
3. **Exportação PDF/PNG do aluno.** Depende de `window.print` e de canvas; o
   harness não cobre. Testar os cinco itens do menu "Exportar" com dados reais —
   em especial as **cores do heatmap no PDF**, que dependem do `style` por CSSOM.
4. **Streaming do chat em produção.** Regressão aqui é silenciosa: com
   `proxy_buffering` ligado a resposta chega inteira no fim. Enviar uma
   mensagem e ver a bolha crescer.
5. **Upload de planilha real** atrás do nginx (`client_max_body_size 25m`).
6. **Primeira subida do `docker compose` de dev**: o serviço `web` roda `npm ci`
   dentro do container antes de subir o Vite; as seguintes usam o volume.

## Pendências

| # | O que | Onde |
|---|---|---|
| 1 | `vercel.json` e o serviço `sas-web` do `render.yaml` apontam para `web/` como site estático — hoje serviriam código-fonte, não o build | [vercel.json](../vercel.json), [render.yaml](../render.yaml) |
| 2 | `selo-108anos.png` tem 1,7 MB, maior que todo o JS do app | [web/assets/](../web/assets/) |
| 3 | O harness de browser vive no scratchpad e não roda em CI | — |
| 5 | `!reset` no `docker-compose.prod.yml` exige Docker Compose ≥ 2.24; em versão anterior o override falha ao subir | [docker-compose.prod.yml](../docker-compose.prod.yml) |
| 6 | O primeiro deploy passou a rodar `npm ci` + `vite build` dentro do container, na VPS — a primeira subida demora bem mais que antes | [infra/vps/](../infra/vps/) |
| 4 | Sem testes de componente (só de lógica pura) | escolha consciente: o valor está no domínio, não em asserção de markup |

## Diferenças de comportamento assumidas

Mudanças conscientes em relação ao app anterior, para não serem lidas como bug:

- **Rotas por caminho real.** `/alunos/A023`, não `#/alunos/A023`. Links antigos
  com hash continuam abrindo (o fallback do nginx leva ao app).
- **Login é rota, não página.** `/login.html` sumiu; quem tinha o link antigo
  cai no `/login` pelo fallback.
- **A área do aluno tem rotas.** Recarregar em `/simulados/S12` continua ali, em
  vez de voltar ao painel.
- **Cache.** O bootstrap antigo guardava o DOM montado de cada rota; agora quem
  cacheia é o TanStack Query, em nível de dados — a tela remonta, mas não rebusca.
- **`/api` sempre.** O cliente não detecta mais `localhost` para falar com o
  uvicorn direto; em dev quem faz a ponte é o proxy do Vite.
- **Filtros de Sede/Turma no Painel funcionam.** Antes não apareciam (ver o
  registro de bugs em [16](16-plano-migracao-react.md)).
