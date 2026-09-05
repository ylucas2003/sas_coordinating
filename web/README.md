## SAS · web

Frontend da coordenação ITA/IME e da área do aluno. **React + TypeScript, build com Vite.**

## Rodar localmente

Pela stack completa (recomendado — sobe API, banco e front juntos):

```sh
docker compose up          # front em :8080, API em :8000
```

Só o front, contra uma API já rodando em `:8000`:

```sh
npm install
npm run dev                # http://localhost:8080
```

O dev server faz proxy de `/api` para a API, então o browser vê tudo na mesma
origem — igual a produção, e sem CORS. Para apontar para outro endereço:
`VITE_API_ALVO=http://outro-host:8000 npm run dev`.

## Scripts

| Comando | O que faz |
|---------|-----------|
| `npm run dev` | Dev server com HMR em `:8080` |
| `npm run build` | `tsc --noEmit` e depois o build do Vite em `dist/` |
| `npm run typecheck` | Só a checagem de tipos |
| `npm run preview` | Serve o `dist/` (smoke test do build de produção) |
| `npm test` | Vitest sobre a lógica de domínio (`src/dominio/`) |

## Estrutura

```
web/
├── index.html              entrada única — o login é a rota /login
├── assets/                 fontes (Plus Jakarta Sans) e logos
├── styles/                 CSS global (tokens, base, layout e por tela)
└── src/
    ├── main.tsx            bootstrap: QueryClient + Router + CSS global
    ├── App.tsx             rotas e guard de sessão
    ├── rotas.ts            que sidebar cada rota mostra
    ├── tipos/              dominio.ts · aluno.ts · chat.ts
    ├── dominio/            regras puras e testadas (painel, filtros, chat…)
    ├── servicos/           http.ts · api.ts · sessao.ts
    ├── hooks/              consultas.ts · mutacoes.ts · aluno.ts
    ├── componentes/        layout/ · ui/ · dialogos/ · simulados/ · chat/ · aluno/
    ├── telas/              uma pasta por tela
    └── exportacao/         PDF/PNG/CSV do aluno — DOM cru, de propósito
```

## Convenções

- Nomes em português, como no resto do projeto.
- Nenhum `fetch` dentro de componente: leitura passa por um hook de `hooks/consultas.ts`,
  escrita por um de `hooks/mutacoes.ts`.
- Regra de negócio não mora em componente: vai para `src/dominio/`, com teste.
- Classes compartilhadas (`.card`, `.tone-*`, `.nota-badge`, `.btn`) ficam globais.

## Deploy

O front é construído pelo [Dockerfile](Dockerfile) (Vite → nginx) e servido em
produção pelo nginx de borda em [infra/vps/nginx.conf](../infra/vps/nginx.conf),
que também faz TLS e o proxy da API. Ver [docs/15-plano-hospedagem-vps.md](../docs/15-plano-hospedagem-vps.md).
