## SAS · web

Frontend da interface de coordenação ITM. **HTML + CSS + JavaScript puro**, sem bundler, sem framework, sem dependências de build.

## Rodar localmente

Qualquer servidor estático serve. Exemplos:

```sh
# Python (já instalado no macOS)
python3 -m http.server 5173

# ou Node, se você tiver
npx serve .
```

Abre em `http://localhost:5173`.

> **Não abra `index.html` direto com `file://`.** Os módulos JS usam `import` e o navegador bloqueia ESM via `file://`.

## Estrutura

```
web/
├── index.html              entry point
├── styles/
│   ├── tokens.css          variáveis (cores, tipografia, sombras)
│   ├── base.css            reset e tipografia
│   └── layout.css          shell, topbar, sidebar, cards, etc.
└── js/
    ├── main.js             bootstrap (router + render)
    ├── router.js           hash router
    ├── dom.js              helpers (`el()`, `clear()`, `fmtNota()`)
    ├── services/
    │   ├── api.js          contrato (escolhe entre mock e HTTP)
    │   ├── mock-client.js  implementação mock
    │   ├── mock-data.js    dados sintéticos
    │   └── http-client.js  placeholder do client real (FastAPI)
    ├── components/
    │   ├── topbar.js
    │   ├── filter-strip.js
    │   ├── sidebar.js
    │   └── ui/
    │       ├── alert-card.js
    │       └── sparkline.js
    └── screens/
        ├── painel.js
        ├── alunos.js
        ├── aluno-ficha.js
        ├── simulados.js
        ├── simulado-ficha.js
        ├── ciclos.js
        └── ciclo-ficha.js
```

## Trocar mock por backend real

Quando o backend FastAPI estiver de pé, abrir [js/services/api.js](js/services/api.js) e alterar a função `getApiClient()`:

```js
import { httpClient } from './http-client.js';

export function getApiClient() {
  return httpClient; // antes era mockClient
}
```

A `BASE_URL` da API fica em [js/services/http-client.js](js/services/http-client.js).

## Deploy (Vercel)

O `vercel.json` na raiz do repositório aponta `outputDirectory` para `web/`. Conectar o repo ao Vercel e o build sai grátis — não há build de fato, é só copiar os arquivos estáticos.
