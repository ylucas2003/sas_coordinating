import { cabecalhosAuth, seNaoAutorizado } from './http';

/**
 * Baixa um arquivo gerado pela API — COM o token da sessão.
 *
 * ⚠️ **Existe por causa de um defeito que estava em produção.** A tela de custos
 * baixava o XLSX com `<a href="/api/…" download>`, e isso nunca funcionou fora
 * do dev: o token mora em `sessionStorage` e viaja só no cabeçalho
 * `Authorization` (`cabecalhosAuth`), que um link comum não manda. O servidor
 * respondia 401 e o navegador salvava a página de erro — ou nada. Medido em
 * 14/09: a mesma URL sem token → 401.
 *
 * Nenhum arquivo da API se baixa por link. Todo download passa por aqui.
 */
export async function baixarDaApi(caminho: string, nomeReserva: string): Promise<void> {
  const resposta = await fetch(`/api${caminho}`, { headers: cabecalhosAuth() });
  if (resposta.status === 401) {
    seNaoAutorizado(401, caminho);
    throw new Error('A sessão expirou. Entre de novo para exportar.');
  }
  if (!resposta.ok) {
    let detalhe = '';
    try {
      detalhe = (await resposta.json())?.detail ?? '';
    } catch {
      // Corpo que não é JSON: fica a mensagem genérica.
    }
    throw new Error(detalhe || `Não deu para gerar o arquivo (${resposta.status}).`);
  }

  const blob = await resposta.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nomeDoArquivo(resposta.headers.get('Content-Disposition')) ?? nomeReserva;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** O nome que o servidor mandou — `filename*` (RFC 5987) antes de `filename`. */
function nomeDoArquivo(disposicao: string | null): string | null {
  if (!disposicao) return null;
  const estendido = /filename\*=UTF-8''([^;]+)/i.exec(disposicao);
  if (estendido) return decodeURIComponent(estendido[1]);
  const simples = /filename="([^"]+)"/i.exec(disposicao);
  return simples ? simples[1] : null;
}
