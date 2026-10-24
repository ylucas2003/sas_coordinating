// Horário de estudos — a regra pura (docs/42).
//
// Tudo aqui é função de (blocos, agora): nenhuma lê relógio nem rede. O
// `agora` entra por argumento porque "o próximo bloco" é a única coisa desta
// tela que depende da hora, e uma função que lê `new Date()` por dentro não se
// testa na virada da meia-noite nem no domingo.
//
// ⚠️ Os limites de duração, de sobreposição e de meia-noite repetem o que o
// servidor (`api/app/horario_estudos.py`) faz. A repetição é de propósito e é só
// de ADIANTAMENTO: a tela avisa antes de enviar, para o aluno não esperar uma
// ida e volta por um erro que já se via. Quem decide é o servidor, e é a frase
// dele que aparece quando as duas divergem.

import type { BlocoDeEstudo } from '../tipos/horarioEstudos';

// ─── Os dias ──────────────────────────────────────────────────────────────

export interface DiaDaSemana {
  /** ISO: 1 = segunda … 7 = domingo. */
  numero: number;
  /** Para as pílulas: "SEG". */
  curto: string;
  /** Para o título da seção: "SEGUNDA". */
  secao: string;
  /** Para frase corrida: "Segunda-feira". */
  nome: string;
}

export const DIAS_DA_SEMANA: readonly DiaDaSemana[] = [
  { numero: 1, curto: 'SEG', secao: 'SEGUNDA', nome: 'Segunda-feira' },
  { numero: 2, curto: 'TER', secao: 'TERÇA', nome: 'Terça-feira' },
  { numero: 3, curto: 'QUA', secao: 'QUARTA', nome: 'Quarta-feira' },
  { numero: 4, curto: 'QUI', secao: 'QUINTA', nome: 'Quinta-feira' },
  { numero: 5, curto: 'SEX', secao: 'SEXTA', nome: 'Sexta-feira' },
  { numero: 6, curto: 'SÁB', secao: 'SÁBADO', nome: 'Sábado' },
  { numero: 7, curto: 'DOM', secao: 'DOMINGO', nome: 'Domingo' },
];

/**
 * O dia ISO de uma data local. ⚠️ É O ÚNICO LUGAR da conversão.
 *
 * `Date#getDay()` é 0 = domingo … 6 = sábado; o banco e a API são ISO,
 * 1 = segunda … 7 = domingo. Errar isto desloca UM dia, e só nos extremos: segunda
 * vira domingo e domingo vira segunda, enquanto terça a sábado continuam certos
 * — o tipo de defeito que passa na revisão e aparece numa tela de domingo.
 */
export function diaIso(data: Date): number {
  const js = data.getDay();
  return js === 0 ? 7 : js;
}

export function nomeDoDia(numero: number): string {
  return DIAS_DA_SEMANA.find((d) => d.numero === numero)?.nome ?? '';
}

// ─── Hora e duração ───────────────────────────────────────────────────────

const MINUTOS_NO_DIA = 24 * 60;

function dois(n: number): string {
  return String(n).padStart(2, '0');
}

/** "19:00" → 1140. `null` para o que não é hora — o `<input type="time">` vazio. */
export function minutosDe(hora: string): number | null {
  const achou = /^(\d{1,2}):(\d{2})$/.exec(hora.trim());
  if (!achou) return null;
  const horas = Number(achou[1]);
  const minutos = Number(achou[2]);
  if (horas > 23 || minutos > 59) return null;
  return horas * 60 + minutos;
}

/** 1140 → "19:00". O fim de um bloco que termina à meia-noite sai "00:00". */
export function horaDe(minutos: number): string {
  const dia = ((minutos % MINUTOS_NO_DIA) + MINUTOS_NO_DIA) % MINUTOS_NO_DIA;
  return `${dois(Math.floor(dia / 60))}:${dois(dia % 60)}`;
}

/** Em que hora o bloco termina. */
export function fimDe(bloco: Pick<BlocoDeEstudo, 'horaInicio' | 'duracaoMinutos'>): string {
  return horaDe((minutosDe(bloco.horaInicio) ?? 0) + bloco.duracaoMinutos);
}

/**
 * 90 → "1h30", 60 → "1h", 45 → "45 min", 65 → "1h05".
 *
 * Serve a duração de um bloco e o total de um dia ou da semana — "11h30" e
 * "1h30" são o mesmo formato, e um aluno lê os dois sem pensar.
 */
export function duracaoPorExtenso(minutos: number): string {
  const horas = Math.floor(minutos / 60);
  const resto = minutos % 60;
  if (horas === 0) return `${resto} min`;
  if (resto === 0) return `${horas}h`;
  return `${horas}h${dois(resto)}`;
}

/** As durações oferecidas como atalho. As mesmas do desenho, mais as 3h de uma prova. */
export const DURACOES_RAPIDAS: readonly number[] = [30, 45, 60, 90, 120, 180];

/**
 * As durações que o seletor mostra: os atalhos e, se o bloco editado tem uma
 * duração fora deles (a API aceita qualquer uma de 15 min a 8h), ela também.
 * Sem isso, editar o rótulo de um bloco de 75 min o deixaria sem nenhuma duração
 * marcada, e salvar mudaria a duração sem o aluno ter tocado nela.
 */
export function duracoesDisponiveis(atual?: number): number[] {
  const todas = new Set(DURACOES_RAPIDAS);
  if (atual != null) todas.add(atual);
  return [...todas].sort((a, b) => a - b);
}

// ─── A semana ─────────────────────────────────────────────────────────────

function ordemDoDia(a: BlocoDeEstudo, b: BlocoDeEstudo): number {
  return (minutosDe(a.horaInicio) ?? 0) - (minutosDe(b.horaInicio) ?? 0) || a.id.localeCompare(b.id);
}

export function blocosDoDia(blocos: BlocoDeEstudo[], dia: number): BlocoDeEstudo[] {
  return blocos.filter((b) => b.diaSemana === dia).sort(ordemDoDia);
}

export function totalDeMinutos(blocos: BlocoDeEstudo[]): number {
  return blocos.reduce((soma, b) => soma + b.duracaoMinutos, 0);
}

export interface SecaoDoDia {
  dia: DiaDaSemana;
  blocos: BlocoDeEstudo[];
  totalMinutos: number;
}

/** Os sete dias, sempre os sete: dia sem bloco também é uma seção. */
export function agruparPorDia(blocos: BlocoDeEstudo[]): SecaoDoDia[] {
  return DIAS_DA_SEMANA.map((dia) => {
    const doDia = blocosDoDia(blocos, dia.numero);
    return { dia, blocos: doDia, totalMinutos: totalDeMinutos(doDia) };
  });
}

// ─── O próximo bloco ──────────────────────────────────────────────────────

export interface ProximoBloco {
  bloco: BlocoDeEstudo;
  /** 0 = hoje, 1 = amanhã … 7 = o mesmo dia da semana que vem. */
  diasAte: number;
  /** O bloco de hoje que já começou e ainda não terminou. */
  emAndamento: boolean;
  /** Minutos até começar, só para um bloco de HOJE que ainda não começou. */
  minutosAte: number | null;
}

/**
 * O que vem a seguir, ou `null` se a semana está vazia.
 *
 * Um bloco de hoje que já terminou NÃO é o próximo: a busca segue para amanhã e,
 * dando a volta na semana, pode cair no mesmo dia da semana que vem
 * (`diasAte === 7`). Sem essa volta, quem só estuda às terças ficaria sem
 * "próximo" de terça à noite até quarta de manhã.
 *
 * Um bloco em andamento é devolvido como `emAndamento`: dizer "próximo: amanhã"
 * às 19:30 de um bloco das 19:00 às 20:30 seria mentira de quem está estudando.
 */
export function proximoBloco(blocos: BlocoDeEstudo[], agora: Date): ProximoBloco | null {
  if (blocos.length === 0) return null;
  const hoje = diaIso(agora);
  const agoraEmMinutos = agora.getHours() * 60 + agora.getMinutes();

  for (let deslocamento = 0; deslocamento <= 7; deslocamento++) {
    const dia = ((hoje - 1 + deslocamento) % 7) + 1;
    const doDia = blocosDoDia(blocos, dia);

    if (deslocamento === 0) {
      const achado = doDia.find(
        (b) => (minutosDe(b.horaInicio) ?? 0) + b.duracaoMinutos > agoraEmMinutos,
      );
      if (achado) {
        const inicio = minutosDe(achado.horaInicio) ?? 0;
        const emAndamento = inicio <= agoraEmMinutos;
        return {
          bloco: achado,
          diasAte: 0,
          emAndamento,
          minutosAte: emAndamento ? null : inicio - agoraEmMinutos,
        };
      }
      continue;
    }

    if (doDia.length > 0) {
      return { bloco: doDia[0], diasAte: deslocamento, emAndamento: false, minutosAte: null };
    }
  }
  return null;
}

/**
 * "hoje, 19:00" · "amanhã, 19:00" · "quinta-feira, 19:00" · "agora, até 20:30".
 *
 * Em minúsculas porque entra no meio de frases ("Próximo: hoje, 19:00 · …"); quem
 * abre frase usa `primeiraMaiuscula`.
 */
export function quandoDoProximo(proximo: ProximoBloco): string {
  if (proximo.emAndamento) return `agora, até ${fimDe(proximo.bloco)}`;
  const hora = proximo.bloco.horaInicio;
  if (proximo.diasAte === 0) return `hoje, ${hora}`;
  if (proximo.diasAte === 1) return `amanhã, ${hora}`;
  return `${nomeDoDia(proximo.bloco.diaSemana).toLowerCase()}, ${hora}`;
}

export function primeiraMaiuscula(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

// ─── Montar e validar um bloco ────────────────────────────────────────────

export interface Rascunho {
  dias: number[];
  hora: string;
  duracao: number;
  rotulo: string;
}

export const TAMANHO_MAXIMO_DO_ROTULO = 80;

/** Um rascunho novo, já com o dia em que o aluno tocou no "+". */
export function rascunhoNovo(dia: number): Rascunho {
  return { dias: [dia], hora: '19:00', duracao: 90, rotulo: '' };
}

export function rascunhoDe(bloco: BlocoDeEstudo): Rascunho {
  return {
    dias: [bloco.diaSemana],
    hora: bloco.horaInicio,
    duracao: bloco.duracaoMinutos,
    rotulo: bloco.rotulo,
  };
}

/** Dois intervalos se cruzam? Encostar não é cruzar (18–19 e 19–20:30 convivem). */
export function sobrepoe(
  inicioA: number,
  duracaoA: number,
  inicioB: number,
  duracaoB: number,
): boolean {
  return inicioA < inicioB + duracaoB && inicioB < inicioA + duracaoA;
}

/** O bloco do aluno que o intervalo cruza, no dia dado — o primeiro, por hora. */
export function blocoQueCruza(
  blocos: BlocoDeEstudo[],
  dia: number,
  inicio: number,
  duracao: number,
  ignorarId?: string,
): BlocoDeEstudo | null {
  return (
    blocosDoDia(blocos, dia).find(
      (b) =>
        b.id !== ignorarId &&
        sobrepoe(inicio, duracao, minutosDe(b.horaInicio) ?? 0, b.duracaoMinutos),
    ) ?? null
  );
}

/** "Termina às 20:30", ou `null` quando o rascunho ainda não tem hora válida. */
export function terminaAs(hora: string, duracao: number): string | null {
  const inicio = minutosDe(hora);
  if (inicio == null || inicio + duracao > MINUTOS_NO_DIA) return null;
  return horaDe(inicio + duracao);
}

/**
 * Por que o rascunho não pode ser salvo, em frase para o aluno — ou `null` se pode.
 *
 * `ignorarId` é o bloco em edição: sem ele, mudar só o rótulo faria o bloco
 * cruzar consigo mesmo.
 */
export function problemaDoRascunho(
  rascunho: Rascunho,
  existentes: BlocoDeEstudo[],
  ignorarId?: string,
): string | null {
  if (rascunho.dias.length === 0) return 'Escolha ao menos um dia da semana.';
  const inicio = minutosDe(rascunho.hora);
  if (inicio == null) return 'Escolha a hora em que o bloco começa.';
  if (!rascunho.rotulo.trim()) return 'Diga o que você vai estudar neste bloco.';
  if (rascunho.rotulo.trim().length > TAMANHO_MAXIMO_DO_ROTULO) {
    return `O nome do bloco pode ter até ${TAMANHO_MAXIMO_DO_ROTULO} caracteres.`;
  }
  if (inicio + rascunho.duracao > MINUTOS_NO_DIA) {
    return 'O bloco não pode passar da meia-noite. Para estudar até mais tarde, faça dois blocos.';
  }
  for (const dia of [...rascunho.dias].sort((a, b) => a - b)) {
    const outro = blocoQueCruza(existentes, dia, inicio, rascunho.duracao, ignorarId);
    if (outro) {
      const ini = outro.horaInicio;
      return `${nomeDoDia(dia)} já tem “${outro.rotulo}” das ${ini} às ${fimDe(outro)}. Escolha outro horário.`;
    }
  }
  return null;
}

/** Marca ou desmarca um dia, mantendo a lista em ordem — a ordem de seleção não
 *  é informação, e uma lista sem ordem faria dois rascunhos iguais parecerem diferentes. */
export function alternarDia(dias: number[], dia: number): number[] {
  return dias.includes(dia)
    ? dias.filter((d) => d !== dia)
    : [...dias, dia].sort((a, b) => a - b);
}
