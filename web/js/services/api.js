// Contrato com o backend. As telas consomem esses métodos; a implementação
// concreta (HTTP no momento) é selecionada em `getApiClient()`.
//
// Documentação dos campos: ../../../docs/05-data-and-stats.md

import { httpClient } from './http-client.js';

/**
 * @typedef {object} ApiClient
 * @property {() => Promise<Array>} listarAlertas
 * @property {(id: string) => Promise<object>} resolverAlerta
 * @property {(filtros?: object) => Promise<Array>} listarAlunos
 * @property {(id: string) => Promise<object | null>} obterAluno
 * @property {(id: string) => Promise<Array>} trajetoriaAluno
 * @property {(id: string) => Promise<object>} heatmapAluno
 * @property {(id: string, k?: number) => Promise<Array>} alunosSimilares
 * @property {() => Promise<Array>} listarSimulados
 * @property {(id: string) => Promise<object | null>} obterSimulado
 * @property {(id: string) => Promise<object>} histogramaSimulado
 * @property {(id: string) => Promise<Array>} notasSimulado
 * @property {(id: string) => Promise<Array>} simuladoPorMateria
 * @property {(id: string) => Promise<Array>} simuladoPorSede
 * @property {() => Promise<Array>} listarCiclos
 * @property {(id: string) => Promise<object | null>} obterCiclo
 * @property {() => Promise<Array>} listarSedes
 * @property {() => Promise<Array>} listarTurmas
 * @property {(arquivo: File, opts?: object) => Promise<object>} enviarPlanilha
 * @property {() => Promise<Array>} listarUploads
 * @property {(id: string) => Promise<object>} obterUpload
 * @property {(opts?: {incluirArquivadas?: boolean}) => Promise<Array>} listarChatThreads
 * @property {(titulo?: string) => Promise<object>} criarChatThread
 * @property {(id: string) => Promise<object>} obterChatThread
 * @property {(id: string, patch: object) => Promise<object>} atualizarChatThread
 * @property {(id: string) => Promise<object>} apagarChatThread
 * @property {(id: string, conteudo: string, onEvento: Function) => Promise<void>} enviarChatMensagem
 * @property {() => void} limparCacheDados
 */

/** @returns {ApiClient} */
export function getApiClient() {
  return httpClient;
}
