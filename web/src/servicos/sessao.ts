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
  temFoto: 'sas_tem_foto',
  fotoDispensadaNestaSessao: 'sas_foto_dispensada',
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
  temFoto: boolean;
}

/** Grava a sessão. Login e primeiro acesso devolvem o mesmo shape. */
export function iniciar(dados: RespostaAutenticacao): void {
  sessionStorage.setItem(CHAVES.token, dados.access_token);
  sessionStorage.setItem(CHAVES.tipo, dados.tipo);
  sessionStorage.setItem(CHAVES.nome, dados.nome);
  sessionStorage.setItem(CHAVES.auth, '1');
  if (dados.aluno_id) sessionStorage.setItem(CHAVES.alunoId, dados.aluno_id);
  sessionStorage.setItem(CHAVES.temFoto, dados.temFoto ? '1' : '0');
}

export function encerrar(): void {
  sessionStorage.clear();
}

// ─── Foto de perfil ─────────────────────────────────────────────────────
// O lembrete de foto (componentes/perfil/LembreteFotoPerfil) só olha isto:
// nasce de `iniciar()` no login e é a mesma resposta pra quem acabou de criar
// conta (P2 do sprint) e pra quem já tinha uma sem foto (P3) — sem os dois
// mecanismos separados que o plano original desenhava.

export function temFoto(): boolean {
  return sessionStorage.getItem(CHAVES.temFoto) === '1';
}

/** Chamar depois de um upload bem-sucedido, sem precisar de outro login. */
export function marcarFotoDefinida(): void {
  sessionStorage.setItem(CHAVES.temFoto, '1');
}

/** "Agora não": o lembrete some pro resto desta sessão, mas volta na próxima
 * (novo login) enquanto a conta não tiver foto — é o que cobre P3. */
export function dispensarFotoNestaSessao(): void {
  sessionStorage.setItem(CHAVES.fotoDispensadaNestaSessao, '1');
}

export function fotoFoiDispensadaNestaSessao(): boolean {
  return sessionStorage.getItem(CHAVES.fotoDispensadaNestaSessao) === '1';
}
