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
