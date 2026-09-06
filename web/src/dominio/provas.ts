// O hub de Provas — o que cada uma das duas portas confessa na chegada.
//
// Por que isto é domínio e não um `useMemo` dentro da tela: os subtítulos do
// hub são DADO VIVO (C2, `componentes/ui/Campo.tsx`), e dado vivo derivado
// dentro do componente envelhece calado — foi exatamente assim que o Painel
// antigo mostrou o número de julho como se fosse o de hoje. Aqui as regras têm
// teste ao lado (`provas.test.ts`) e o componente só formata.
//
// ⚠️ Nada aqui inventa número. Onde o servidor não diz, a função devolve
// `null` e o card cai no estado vazio — "0" no lugar de "não sei" é a mentira
// mais cara desta interface (docs/39, regras desta rodada).

import type { Ciclo, Simulado } from '../tipos/dominio';

/** Dias inteiros de `hoje` até `iso`. Negativo quando `iso` já passou. */
export function diasAte(iso: string, hoje: string): number {
  // `Date.UTC` e não `new Date(iso)`: a diferença é contada em dias de
  // calendário, e horário de verão faria um dos dias ter 23 horas — o que
  // arredondaria "fecha em 6 dias" para 5 uma vez por ano, em silêncio.
  const [aA, mA, dA] = iso.split('-').map(Number);
  const [aH, mH, dH] = hoje.split('-').map(Number);
  const ms = Date.UTC(aA, mA - 1, dA) - Date.UTC(aH, mH - 1, dH);
  return Math.round(ms / 86_400_000);
}

/** "6 dias" · "1 dia" — o numeral com a unidade concordando. */
function dias(n: number): string {
  return n === 1 ? '1 dia' : `${n} dias`;
}

/**
 * O estado do ciclo em palavras, na linha de baixo do nome.
 *
 * ⚠️ AINDA NÃO LIGADA. Ela foi escrita para a lista de ciclos redesenhada da
 * fase 3 do docs/39 — junto com `.provas-linha__estado` em `provas.css` —, e
 * a lista não chegou a ser refeita: `telas/Ciclos/Ciclos.tsx` segue com a
 * `.data-table` antiga. A varredura de consistência a MARCOU em vez de
 * apagá-la com os testes, porque o que falta é ligar, não decidir. Enquanto
 * isso, o teste verde aqui não prova tela nenhuma.
 *
 * Devolve `''` quando o ciclo não tem período: um ciclo criado sem simulado
 * nenhum não tem data (o período vem do min/max das provas, ver
 * `dominio/ciclos.ts::intersectaPeriodo`), e escrever "encerrado" para ele
 * seria afirmar o que ninguém mediu.
 */
export function estadoDoCiclo(ciclo: Ciclo, hoje: string): string {
  if ((ciclo.simuladoIds ?? []).length === 0) return 'sem prova';
  if (!ciclo.periodoInicio || !ciclo.periodoFim) return '';

  if (hoje < ciclo.periodoInicio) {
    const d = diasAte(ciclo.periodoInicio, hoje);
    return d === 1 ? 'começa amanhã' : `começa em ${dias(d)}`;
  }
  if (hoje > ciclo.periodoFim) return 'encerrado';

  const d = diasAte(ciclo.periodoFim, hoje);
  if (d === 0) return 'em andamento · fecha hoje';
  if (d === 1) return 'em andamento · fecha amanhã';
  return `em andamento · fecha em ${dias(d)}`;
}

export interface ResumoDeCiclos {
  total: number;
  /**
   * O ciclo aberto AGORA. Havendo mais de um (ITA e IME correm em paralelo), é
   * o que fecha primeiro: entre dois abertos, quem decide se vale abrir o card
   * hoje é o prazo mais curto.
   */
  emAndamento: Ciclo | null;
  /** Dias até o `emAndamento` fechar. `null` quando não há ciclo aberto. */
  diasParaFechar: number | null;
}

export function resumirCiclos(ciclos: readonly Ciclo[], hoje: string): ResumoDeCiclos {
  const abertos = ciclos
    .filter((c) => c.periodoInicio && c.periodoFim && c.periodoInicio <= hoje && hoje <= c.periodoFim)
    .sort((a, b) => a.periodoFim.localeCompare(b.periodoFim));
  const emAndamento = abertos[0] ?? null;
  return {
    total: ciclos.length,
    emAndamento,
    diasParaFechar: emAndamento ? diasAte(emAndamento.periodoFim, hoje) : null,
  };
}

/**
 * O subtítulo do card "Ciclos completos" (C2).
 *
 * `null` significa VAZIO — o card mostra a frase que convida a criar o
 * primeiro, e não um "0 ciclos" que parece defeito de carregamento.
 */
export function subtituloDeCiclos(r: ResumoDeCiclos): string | null {
  if (r.total === 0) return null;

  const contagem = r.total === 1 ? '1 ciclo' : `${r.total} ciclos`;
  if (!r.emAndamento) return `${contagem} · nenhum em andamento`;

  const d = r.diasParaFechar ?? 0;
  const prazo = d <= 0 ? 'fecha hoje' : d === 1 ? 'fecha amanhã' : `fecha em ${dias(d)}`;
  return `${contagem} · ${r.emAndamento.nome} em andamento, ${prazo}`;
}

export interface ResumoDeProvas {
  /** Provas já aplicadas — as agendadas ainda não são medida de nada. */
  total: number;
  /** Aplicadas sem nenhuma nota: aconteceram e o dado não chegou. */
  semNotaLancada: number;
  /** O Assignment do Canvas não reflete o SAS por FALHA (não por escolha). */
  falhouNoCanvas: number;
  /** Marcadas para uma data futura. */
  agendadas: number;
}

export function resumirProvas(simulados: readonly Simulado[], hoje: string): ResumoDeProvas {
  const aplicadas = simulados.filter((s) => s.dataAplicacao <= hoje);
  return {
    total: aplicadas.length,
    // `media` nula é o sinal de que NENHUMA nota entrou: ela é calculada sobre
    // as notas da prova, e sem nota não há como haver média. `nPresentes` não
    // serve — ele vem da presença, que o Canvas devolve antes das notas.
    semNotaLancada: aplicadas.filter((s) => s.media == null).length,
    // 'divergente' fica de fora de propósito: ali o coordenador ESCOLHEU não
    // criar o grupo no Canvas (docs/18 §2.5). Escolha não é pendência, e
    // contá-la aqui encheria o hub de um número que ninguém vai resolver.
    falhouNoCanvas: simulados.filter((s) => s.canvasEstado === 'falhou').length,
    agendadas: simulados.length - aplicadas.length,
  };
}

/**
 * O subtítulo do card "Provas específicas" (C2).
 *
 * As pendências operacionais moram AQUI, e não no card do ciclo: falha de
 * prova é problema de instrumento, e é este card que responde "a medida
 * funcionou?" (a prancheta de Provas, `hubCards`).
 */
export function subtituloDeProvas(r: ResumoDeProvas): string | null {
  if (r.total === 0 && r.agendadas === 0) return null;

  const partes: string[] = [];
  if (r.total > 0) partes.push(r.total === 1 ? '1 prova' : `${r.total} provas`);
  if (r.agendadas > 0) {
    partes.push(r.agendadas === 1 ? '1 agendada' : `${r.agendadas} agendadas`);
  }
  if (r.semNotaLancada > 0) partes.push(`${r.semNotaLancada} sem nota lançada`);
  if (r.falhouNoCanvas > 0) {
    partes.push(
      r.falhouNoCanvas === 1 ? '1 falhou no Canvas' : `${r.falhouNoCanvas} falharam no Canvas`,
    );
  }
  return partes.join(' · ');
}
