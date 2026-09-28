// Captação externa (docs/41), prefixo `/captacao`. Arquivo próprio, como
// `servicos/banco.ts`: é um recurso fechado — candidato + conquistas —, sem
// nada em comum com o resto de `servicos/api.ts`.
//
// Simplificação de 25/09/2026: sem fila de fusão nem decisão permanente —
// agrupar é sempre manual, via as três funções do "modo avançado" abaixo.

import { del, get, patch, post, qs } from './http';
import type {
  FiltrosCaptacao, PaginaCandidatos, PaginaProvas, PerfilDoNome,
  PerfisDoNome, RemendoCandidato,
} from '../tipos/captacao';

const enc = encodeURIComponent;

export const listarCandidatos = (filtros: FiltrosCaptacao = {}) =>
  get<PaginaCandidatos>(`/captacao/candidatos${qs({ ...filtros })}`);

export const listarProvas = () => get<PaginaProvas>('/captacao/provas');

export const obterPerfisDoNome = (nomeNormalizado: string) =>
  get<PerfisDoNome>(`/captacao/perfis/${enc(nomeNormalizado)}`);

/** Só `status_captacao` e/ou `observacoes` — o backend recusa corpo vazio. */
export const atualizarCandidato = (id: string, remendo: RemendoCandidato) =>
  patch<PerfilDoNome>(`/captacao/candidatos/${enc(id)}`, remendo);

// ─── Modo avançado: agrupar é sempre manual (docs/41, 25/09/2026) ─────────

export const criarPerfil = (nomeNormalizado: string) =>
  post<PerfilDoNome>('/captacao/perfis/criar', { nome_normalizado: nomeNormalizado });

export const moverConquista = (conquistaId: string, candidatoId: string) =>
  post<{ ok: boolean }>('/captacao/conquistas/mover', {
    conquista_id: conquistaId,
    candidato_id: candidatoId,
  });

/** Só aceita perfil SEM conquista nenhuma — o backend recusa (409) o resto. */
export const removerCandidatoVazio = (candidatoId: string) =>
  del<{ ok: boolean }>(`/captacao/candidatos/${enc(candidatoId)}`);
