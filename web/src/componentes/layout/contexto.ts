import { createContext, useContext } from 'react';

/**
 * O casco expõe só um contador de versão dos dados: ele muda quando entra
 * planilha nova (evento `sas:dados-atualizados` do código legado) e força as
 * telas ainda não migradas a remontar. As telas em React não precisam dele —
 * quem as atualiza é a invalidação do TanStack Query.
 */
export const ContextoShell = createContext({ versaoDados: 0 });

export const usarShell = () => useContext(ContextoShell);
