# Exportação — geradores de documento

Os únicos arquivos do frontend que continuam em JavaScript e montando DOM à
mão, de propósito.

`panorama-aluno.js` monta um nó offscreen com o histórico completo do aluno, e
`exportar-aluno.js` o transforma em PDF (`window.print`), PNG (SVG → canvas) ou
CSV. São **geradores de documento**, não UI reativa: nada aqui re-renderiza,
responde a estado ou entra na árvore do React — o nó é construído, consumido e
descartado.

Converter para JSX só para converter traria risco (o layout de impressão é
sensível a estrutura) sem nenhum ganho. `dom.js` fica junto porque é o helper
`el()` que eles usam.

Quem chama: `src/telas/AlunoFicha/AlunoFicha.tsx`, pelo menu "Exportar".


## Onde mais o projeto gera documento

Não é só aqui. São **três** lugares, com mecânicas diferentes, e a diferença é
deliberada:

| Onde | Como | Word? | Gráfico? |
|---|---|---|---|
| `src/exportacao/` (esta pasta) — ficha do aluno | monta o nó **no documento atual**, marca `body.imprimindo-panorama` e chama `window.print()`; o CSS de print esconde o resto | não | heatmap em HTML, e `exportarPNGGrafico` para SVG→canvas |
| `telas/Banco/exportar.ts` — lista de questões | `window.open('')`, estilo por **CSSOM**, `.doc` por Blob | **sim** | não (as imagens vêm por URL do S3) |
| `telas/CicloFicha/dossie.ts` — dossiê de ciclo | igual ao do Banco, **mais** o gráfico rasterizado (SVG → canvas → `data:` URI) | **sim** | **sim** |

O que os três têm em comum, e que é a única regra que não se pode quebrar:
**estilo nunca por atributo `style` nem por `<style>` com conteúdo** quando o
documento é gerado dentro do navegador. A CSP de produção é `style-src 'self'`,
sem `unsafe-inline`, e a janela aberta por `window.open('')` herda a CSP de quem
a abriu — o estilo inline seria descartado **em silêncio**, e o PDF sairia sem
cor e sem margem sem nenhum erro no console. Aplique por CSSOM (`.style.cssText`,
`insertRule`).

A exceção é o `.doc`: aquele arquivo sai do navegador, a CSP não o alcança, e o
`style` inline é justamente o que o Word entende.

⚠️ **Testar em produção, não só no dev** — a CSP do dev é mais frouxa.
