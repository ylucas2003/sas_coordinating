// Cadastro de aluno no Canvas (docs/46) — o que a tela diz, em função pura.
//
// A régua de validação de verdade mora no servidor (`canvas_sync/cadastro.py`):
// aqui só o mínimo para o botão não acender com uma matrícula que ele vai
// recusar, e as frases do resultado.

import type {
  EstadoDoCurso, EstadoDoLote, LinhaDaPrevia, LoteNoCanvas, PacoteDaSerie, PreviaDoLote,
  ResultadoDoCadastro, ResumoDoLote,
} from '../tipos/cadastroCanvas';

/** O servidor recusa qualquer coisa que não sejam 8 dígitos (docs/46 §2). */
export const DIGITOS_DA_MATRICULA = 8;

/** O que a pessoa digitou, só com os dígitos — e no máximo oito. */
export function soDigitos(texto: string): string {
  return texto.replace(/\D/g, '').slice(0, DIGITOS_DA_MATRICULA);
}

export function matriculaCompleta(matricula: string): boolean {
  return new RegExp(`^\\d{${DIGITOS_DA_MATRICULA}}$`).test(matricula);
}

/**
 * Os domínios do botão do e-mail, na ordem em que aparecem nos alunos do 3º de
 * 2026 (curso 577, levantamento de 25/11/2026): gmail.com é ~86% dos e-mails,
 * depois hotmail, aridesa.edu.br e outlook. icloud e yahoo entram por pedido —
 * são os outros que um aluno costuma ter.
 */
export const DOMINIOS_DE_EMAIL = [
  'gmail.com', 'hotmail.com', 'outlook.com', 'icloud.com', 'yahoo.com.br', 'aridesa.edu.br',
] as const;

/** A opção "outro domínio" do botão: o endereço inteiro vai no campo. */
export const OUTRO_DOMINIO = '';

/**
 * O endereço que vai ao servidor. Com "@" no campo, vale o que foi digitado —
 * quem colou o endereço inteiro não pode ganhar um segundo domínio no fim.
 */
export function montarEmail(usuario: string, dominio: string): string {
  const texto = usuario.trim();
  if (!texto) return '';
  if (texto.includes('@') || dominio === OUTRO_DOMINIO) return texto;
  return `${texto}@${dominio}`;
}

const ROTULO_DO_CURSO: Record<EstadoDoCurso, string> = {
  matriculado: 'matriculado agora',
  ja_estava: 'já estava',
  outra_sede: 'em outra sede',
  falhou: 'falhou',
};

export function rotuloDoEstadoDoCurso(estado: EstadoDoCurso): string {
  return ROTULO_DO_CURSO[estado];
}

/** "1 conta nova" / "3 contas novas", com o número no formato do Brasil. */
export function plural(n: number, um: string, varios: string): string {
  return `${n.toLocaleString('pt-BR')} ${n === 1 ? um : varios}`;
}

/**
 * "Conta criada · matriculado nos 19 cursos" — a frase de cima do resultado.
 *
 * A falha vem antes de tudo quando existe: é a única parte sobre a qual a
 * pessoa precisa agir, e ela age repetindo o mesmo cadastro.
 */
export function resumoDoCadastro(r: ResultadoDoCadastro): string {
  const conta = r.conta === 'criada' ? 'Conta criada' : 'A conta já existia';
  const novos = r.cursos.filter((c) => c.estado === 'matriculado').length;
  const jaEstavam = r.cursos.filter((c) => c.estado === 'ja_estava').length;
  const falharam = r.cursos.filter((c) => c.estado === 'falhou').length;
  const outraSede = r.cursos.filter((c) => c.estado === 'outra_sede').length;
  const partes = [conta];
  if (falharam) partes.push(`${plural(falharam, 'curso falhou', 'cursos falharam')}`);
  if (outraSede) partes.push('já está em outra sede');
  if (novos === r.cursos.length) {
    partes.push(`matriculado ${r.cursos.length === 1 ? 'no curso' : `nos ${r.cursos.length} cursos`}`);
  } else {
    if (novos) partes.push(`${plural(novos, 'matrícula nova', 'matrículas novas')}`);
    if (jaEstavam) partes.push(`${jaEstavam} já ${jaEstavam === 1 ? 'estava' : 'estavam'}`);
  }
  return partes.join(' · ');
}

/** Quantas matrículas o lote vai pedir: uma por curso do pacote, por aluno. */
export function totalDeMatriculas(linhas: LinhaDaPrevia[], pacotes: PacoteDaSerie[]): number {
  const cursosDaSerie = new Map(pacotes.map((p) => [p.serie, p.cursos.length]));
  return linhas
    .filter((l) => l.situacao !== 'erro' && l.serie != null)
    .reduce((soma, l) => soma + (cursosDaSerie.get(l.serie as number) ?? 0), 0);
}

/**
 * A linha de cima da prévia, em três pedaços: o erro e o aviso saem separados
 * porque a tela pinta só o erro — é a única falha da frase.
 */
export function frasesDaPrevia(
  resumo: ResumoDoLote,
  matriculas: number,
): { base: string; erro: string | null; aviso: string | null } {
  const base = [
    plural(resumo.total, 'linha', 'linhas'),
    plural(resumo.novas, 'conta nova', 'contas novas'),
    `${resumo.existentes.toLocaleString('pt-BR')} já ${resumo.existentes === 1 ? 'existe' : 'existem'}`,
    plural(matriculas, 'matrícula', 'matrículas'),
  ].join(' · ');
  return {
    base,
    erro: resumo.com_erro ? `${resumo.com_erro.toLocaleString('pt-BR')} com erro` : null,
    aviso: resumo.com_aviso ? `${resumo.com_aviso.toLocaleString('pt-BR')} com aviso` : null,
  };
}

/** O envio só acende sem erro nenhum — o servidor recusa o lote inteiro. */
export function podeEnviar(previa: PreviaDoLote | null | undefined): boolean {
  if (!previa) return false;
  const { com_erro, novas, existentes } = previa.resumo;
  return com_erro === 0 && novas + existentes > 0;
}

/**
 * Erro primeiro, depois aviso, depois o resto — cada grupo na ordem do
 * arquivo. Num lote de 100 linhas, o que precisa de olho não pode estar na
 * linha 87.
 */
export function ordenarParaRevisao(linhas: LinhaDaPrevia[]): LinhaDaPrevia[] {
  const peso = (l: LinhaDaPrevia) => (l.situacao === 'erro' ? 0 : l.avisos.length ? 1 : 2);
  return [...linhas].sort((a, b) => peso(a) - peso(b) || a.linha - b.linha);
}

const ROTULO_DO_LOTE: Record<EstadoDoLote, string> = {
  processando: 'processando',
  concluido: 'concluído',
  concluido_com_avisos: 'concluído com avisos',
  falhou: 'falhou',
};

export function rotuloDoLote(lote: Pick<LoteNoCanvas, 'estado' | 'progresso'>): string {
  if (lote.estado === 'processando' && lote.progresso != null) {
    return `processando · ${Math.round(lote.progresso)}%`;
  }
  return ROTULO_DO_LOTE[lote.estado];
}

/** "108 contas · 2.052 matrículas · 3 erros" — o que o Canvas contou. */
export function contagemDoLote(lote: LoteNoCanvas): string {
  const partes: string[] = [];
  if (lote.contas != null) partes.push(plural(lote.contas, 'conta', 'contas'));
  if (lote.matriculas != null) {
    partes.push(`${lote.matriculas.toLocaleString('pt-BR')} ${lote.matriculas === 1 ? 'matrícula' : 'matrículas'}`);
  }
  if (lote.total_erros) partes.push(plural(lote.total_erros, 'erro', 'erros'));
  if (lote.total_avisos) partes.push(plural(lote.total_avisos, 'aviso', 'avisos'));
  return partes.join(' · ');
}

/**
 * A planilha-modelo do lote. `;` porque é o separador que o Excel em
 * português lê sem perguntar; o servidor aceita `,` e `;`.
 */
export const MODELO_DA_PLANILHA = [
  'matricula;nome;email;serie;sede',
  '12345678;Nome Completo do Aluno;aluno@exemplo.com;3;3o ITA AD',
  '12345679;Outro Aluno;outro@exemplo.com;1;',
].join('\r\n');
