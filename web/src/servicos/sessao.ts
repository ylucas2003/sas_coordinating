// Sessão do usuário — o que o login grava no `sessionStorage` e o resto do
// app lê. Centralizado aqui para as chaves cruas (`sas_token`, `sas_tipo`…)
// não se espalharem pelos componentes.

import type { TipoSessao } from '../tipos/dominio';

const CHAVES = {
  token: 'sas_token',
  tipo: 'sas_tipo',
  nome: 'sas_nome',
  auth: 'sas_auth',
  alunoId: 'sas_aluno_id',
} as const;

export function token(): string | null {
  return sessionStorage.getItem(CHAVES.token);
}

export function autenticado(): boolean {
  return sessionStorage.getItem(CHAVES.auth) === '1';
}

export function tipo(): TipoSessao | null {
  const valor = sessionStorage.getItem(CHAVES.tipo);
  return valor === 'aluno' || valor === 'coordenador' ? valor : null;
}

export function nome(): string {
  return sessionStorage.getItem(CHAVES.nome) ?? '';
}

export function alunoId(): string | null {
  return sessionStorage.getItem(CHAVES.alunoId);
}

export interface RespostaAutenticacao {
  access_token: string;
  tipo: string;
  nome: string;
  aluno_id?: string;
}

/** Grava a sessão. Login e primeiro acesso devolvem o mesmo shape. */
export function iniciar(dados: RespostaAutenticacao): void {
  sessionStorage.setItem(CHAVES.token, dados.access_token);
  sessionStorage.setItem(CHAVES.tipo, dados.tipo);
  sessionStorage.setItem(CHAVES.nome, dados.nome);
  sessionStorage.setItem(CHAVES.auth, '1');
  if (dados.aluno_id) sessionStorage.setItem(CHAVES.alunoId, dados.aluno_id);
}

export function encerrar(): void {
  sessionStorage.clear();
}
