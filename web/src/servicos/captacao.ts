// Captação externa (docs/41), prefixo `/captacao`. Arquivo próprio, como
// `servicos/banco.ts`: é um recurso fechado — candidato + conquistas —, sem
// nada em comum com o resto de `servicos/api.ts`.

import { del, get, patch, post, qs } from './http';
import type {
  CandidatoFicha, DetalheDaFusao, FiltrosCaptacao, MembroDaFusao, PaginaCandidatos,
  PaginaFusoes, RemendoCandidato, ResultadoDaConclusao, ResultadoDaFusao,
} from '../tipos/captacao';

const enc = encodeURIComponent;

export const listarCandidatos = (filtros: FiltrosCaptacao = {}) =>
  get<PaginaCandidatos>(`/captacao/candidatos${qs({ ...filtros })}`);

export const obterCandidato = (id: string) =>
  get<CandidatoFicha>(`/captacao/candidatos/${enc(id)}`);

/** Só `status_captacao` e/ou `observacoes` — o backend recusa corpo vazio. */
export const atualizarCandidato = (id: string, remendo: RemendoCandidato) =>
  patch<CandidatoFicha>(`/captacao/candidatos/${enc(id)}`, remendo);

// ─── Fila de fusão de baixa confiança (docs/41 §8, item 1) ────────────────

export const listarFusoes = (
  opcoes: { ufIncerta?: boolean; soConflitoNivel?: boolean; pagina?: number; porPagina?: number } = {},
) =>
  get<PaginaFusoes>(
    `/captacao/fusoes${qs({
      uf_incerta: opcoes.ufIncerta,
      so_conflito_nivel: opcoes.soConflitoNivel,
      pagina: opcoes.pagina,
      por_pagina: opcoes.porPagina,
    })}`,
  );

export const obterFusao = (nomeNormalizado: string) =>
  get<DetalheDaFusao>(`/captacao/fusoes/${enc(nomeNormalizado)}`);

export const confirmarFusao = (nomeNormalizado: string) =>
  post<ResultadoDaFusao>('/captacao/fusoes/confirmar', { nome_normalizado: nomeNormalizado });

export const rejeitarFusao = (nomeNormalizado: string) =>
  post<{ ok: boolean }>('/captacao/fusoes/rejeitar', { nome_normalizado: nomeNormalizado });

// ─── Modo avançado: dividir um grupo à mão (docs/41, 24/09/2026) ──────────

export const criarPerfilNoGrupo = (nomeNormalizado: string) =>
  post<MembroDaFusao>('/captacao/fusoes/criar-perfil', { nome_normalizado: nomeNormalizado });

export const moverConquista = (conquistaId: string, candidatoId: string) =>
  post<{ ok: boolean }>('/captacao/conquistas/mover', {
    conquista_id: conquistaId,
    candidato_id: candidatoId,
  });

/** Só aceita perfil SEM conquista nenhuma — o backend recusa (409) o resto. */
export const removerCandidatoVazio = (candidatoId: string) =>
  del<{ ok: boolean }>(`/captacao/candidatos/${enc(candidatoId)}`);

export const concluirRevisao = (nomeNormalizado: string) =>
  post<ResultadoDaConclusao>('/captacao/fusoes/concluir', { nome_normalizado: nomeNormalizado });
