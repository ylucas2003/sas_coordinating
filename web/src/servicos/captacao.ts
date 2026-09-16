// Captação externa (docs/41), prefixo `/captacao`. Arquivo próprio, como
// `servicos/banco.ts`: é um recurso fechado — candidato + conquistas —, sem
// nada em comum com o resto de `servicos/api.ts`.

import { get, patch, qs } from './http';
import type {
  CandidatoFicha, FiltrosCaptacao, PaginaCandidatos, RemendoCandidato,
} from '../tipos/captacao';

const enc = encodeURIComponent;

export const listarCandidatos = (filtros: FiltrosCaptacao = {}) =>
  get<PaginaCandidatos>(`/captacao/candidatos${qs({ ...filtros })}`);

export const obterCandidato = (id: string) =>
  get<CandidatoFicha>(`/captacao/candidatos/${enc(id)}`);

/** Só `status_captacao` e/ou `observacoes` — o backend recusa corpo vazio. */
export const atualizarCandidato = (id: string, remendo: RemendoCandidato) =>
  patch<CandidatoFicha>(`/captacao/candidatos/${enc(id)}`, remendo);
