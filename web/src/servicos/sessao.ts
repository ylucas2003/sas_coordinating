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
  cantina: 'sas_cantina',
} as const;

export function token(): string | null {
  return sessionStorage.getItem(CHAVES.token);
}

export function autenticado(): boolean {
  return sessionStorage.getItem(CHAVES.auth) === '1';
}

// ⚠️ Um tipo que não está nesta lista faz `tipo()` devolver `null`, e uma
// sessão com tipo nulo nasce morta: `RotaProtegida` a manda para o login em
// loop, com o token gravado e válido. Foi o terceiro dos três lugares que o
// tipo `cantina` obrigou a mexer (docs/38 §1.1).
const TIPOS: readonly TipoSessao[] = ['aluno', 'coordenador', 'administrador', 'cantina'];

export function tipo(): TipoSessao | null {
  const valor = sessionStorage.getItem(CHAVES.tipo);
  return TIPOS.includes(valor as TipoSessao) ? (valor as TipoSessao) : null;
}

/** Atalho para as telas que escondem o que só o administrador pode fazer. */
export function ehAdministrador(): boolean {
  return tipo() === 'administrador';
}

/** O nome do estabelecimento, para o casco da cantina. Vazio nas outras sessões. */
export function nomeDaCantina(): string {
  return sessionStorage.getItem(CHAVES.cantina) ?? '';
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
  /**
   * Só vem do login da coordenação: 'coordenador' ou 'administrador'
   * (migration 0045). O SSO do Canvas não manda — de lá só entra aluno, e o
   * login da cantina manda `null`.
   */
  papel?: string | null;
  /** Só vem do login da cantina: o nome do estabelecimento (docs/38 §2.1). */
  cantina?: string | null;
  nome: string;
  aluno_id?: string | null;
  temFoto: boolean;
}

/**
 * Grava a sessão. `/auth/login` e o callback do Canvas devolvem o mesmo shape.
 *
 * ⚠️ `sas_tipo` guarda o PAPEL quando ele vem, e não o `tipo` cru do token.
 * A divergência é de propósito e mora só aqui: no servidor o administrador
 * precisa ter `tipo: "coordenador"` para passar por todo guard de coordenação
 * (docs/35 §11.3), enquanto no front a única pergunta é "o que esta pessoa
 * vê" — e aí administrador e coordenador não são a mesma resposta. Juntar os
 * dois em UM valor evita que cada tela tenha que lembrar de olhar dois campos.
 *
 * A cantina passa reto por essa tradução: ela manda `papel: null`, então o
 * `||` cai no `tipo`, que já é 'cantina'. É o que `RotaProtegida` lê para
 * montar o casco certo.
 */
export function iniciar(dados: RespostaAutenticacao): void {
  sessionStorage.setItem(CHAVES.token, dados.access_token);
  sessionStorage.setItem(CHAVES.tipo, dados.papel || dados.tipo);
  sessionStorage.setItem(CHAVES.nome, dados.nome);
  sessionStorage.setItem(CHAVES.auth, '1');
  if (dados.aluno_id) sessionStorage.setItem(CHAVES.alunoId, dados.aluno_id);
  sessionStorage.setItem(CHAVES.temFoto, dados.temFoto ? '1' : '0');
  if (dados.cantina) sessionStorage.setItem(CHAVES.cantina, dados.cantina);
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
