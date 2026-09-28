// Depois de um deploy, uma aba que já estava aberta continua com o
// `index.html` ANTERIOR carregado — que referencia os nomes de arquivo (hash)
// da build anterior. Qualquer `import()` dinâmico que essa aba tente fazer
// depois disso (os três cascos e Banco/ChatLauncher são `lazy()`, App.tsx) dá
// 404: o `docker compose build` já sobrescreveu esses arquivos com hashes
// novos. Sem tratamento, o erro sobe até a raiz — não existe ErrorBoundary lá
// (só o chat tem um, `LimiteDeErro.tsx`, e é escopado só a ele) — e derruba a
// árvore inteira: tela branca, só um F5 resolve (achado em produção,
// 28/09/2026, logo depois de um deploy).
//
// O Vite já avisa esse caso específico com um evento próprio no `window`,
// `vite:preloadError`, antes do `import()` rejeitar de vez. Recarregar a
// página busca o `index.html` novo, que aponta pros hashes certos — o mesmo
// que um F5 manual já resolvia.

const CHAVE_JA_RECARREGOU = 'sas:recarregou-apos-chunk-perdido';

/**
 * `sessionStorage`, não uma flag em memória: precisa sobreviver ao PRÓPRIO
 * reload que este código dispara. Sem ela, um chunk que segue 404 por outro
 * motivo (falha de rede de verdade, não deploy) recarregaria pra sempre.
 */
export function recarregarUmaVezSeChunkSumiu(): void {
  window.addEventListener('vite:preloadError', () => {
    if (sessionStorage.getItem(CHAVE_JA_RECARREGOU)) return;
    sessionStorage.setItem(CHAVE_JA_RECARREGOU, '1');
    window.location.reload();
  });
}
