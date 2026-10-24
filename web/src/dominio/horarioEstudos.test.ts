import { describe, expect, it } from 'vitest';

import type { BlocoDeEstudo } from '../tipos/horarioEstudos';
import {
  agruparPorDia,
  alternarDia,
  blocoQueCruza,
  blocosDoDia,
  diaIso,
  duracaoPorExtenso,
  duracoesDisponiveis,
  fimDe,
  horaDe,
  minutosDe,
  problemaDoRascunho,
  proximoBloco,
  quandoDoProximo,
  rascunhoNovo,
  sobrepoe,
  terminaAs,
  totalDeMinutos,
} from './horarioEstudos';

function bloco(id: string, dia: number, inicio: string, duracao: number, rotulo = id): BlocoDeEstudo {
  return { id, diaSemana: dia, horaInicio: inicio, duracaoMinutos: duracao, rotulo };
}

/** Uma data local numa semana conhecida: 2026-10-19 é segunda-feira. */
function em(diaDoMes: number, hora: number, minuto = 0): Date {
  return new Date(2026, 9, diaDoMes, hora, minuto, 0);
}
const SEGUNDA = 19;
const TERCA = 20;
const DOMINGO = 25;

// A semana de exemplo do docs/prompts-design-horario-de-estudos.md.
const SEMANA = [
  bloco('seg', 1, '19:00', 90, 'Termodinâmica'),
  bloco('ter', 2, '19:00', 90, 'Estequiometria'),
  bloco('qua', 3, '19:00', 90, 'Análise combinatória'),
  bloco('qui2', 4, '19:15', 90, 'Revisar meus erros'),
  bloco('qui1', 4, '18:00', 60, 'Redação'),
  bloco('sex', 5, '19:00', 90, 'Eletrostática'),
  bloco('sab', 6, '14:00', 120, 'Prova do ITA 2019'),
  bloco('dom', 7, '16:00', 60, 'Inglês'),
];

describe('diaIso — a conversão que erra um dia nos extremos', () => {
  it('segunda é 1 e domingo é 7, e não 0', () => {
    expect(diaIso(em(SEGUNDA, 12))).toBe(1);
    expect(diaIso(em(DOMINGO, 12))).toBe(7);
  });

  it('terça a sábado coincidem com o getDay() do JavaScript', () => {
    // Por isso o erro nasce só nos extremos e passa na revisão.
    for (let n = 0; n < 5; n++) {
      const data = em(TERCA + n, 12);
      expect(diaIso(data)).toBe(data.getDay());
    }
  });
});

describe('hora e duração', () => {
  it('minutosDe aceita HH:MM e recusa o resto', () => {
    expect(minutosDe('19:00')).toBe(1140);
    expect(minutosDe('9:05')).toBe(545);
    expect(minutosDe('')).toBeNull();
    expect(minutosDe('24:00')).toBeNull();
    expect(minutosDe('19:60')).toBeNull();
    expect(minutosDe('19h')).toBeNull();
  });

  it('horaDe devolve sempre HH:MM e dá a volta na meia-noite', () => {
    expect(horaDe(1140)).toBe('19:00');
    expect(horaDe(545)).toBe('09:05');
    expect(horaDe(1440)).toBe('00:00');
  });

  it('fimDe soma a duração à hora de início', () => {
    expect(fimDe(bloco('x', 1, '19:00', 90))).toBe('20:30');
    expect(fimDe(bloco('x', 1, '23:00', 60))).toBe('00:00');
  });

  it.each([
    [90, '1h30'],
    [60, '1h'],
    [45, '45 min'],
    [30, '30 min'],
    [120, '2h'],
    [65, '1h05'],
    [690, '11h30'],
  ])('duracaoPorExtenso(%i) = %s', (minutos, esperado) => {
    expect(duracaoPorExtenso(minutos)).toBe(esperado);
  });

  it('o seletor de duração inclui a duração atípica de um bloco editado', () => {
    expect(duracoesDisponiveis()).toEqual([30, 45, 60, 90, 120, 180]);
    // 75 min só entra pela API. Sem ela aqui, editar o rótulo trocaria a duração.
    expect(duracoesDisponiveis(75)).toEqual([30, 45, 60, 75, 90, 120, 180]);
    expect(duracoesDisponiveis(90)).toEqual([30, 45, 60, 90, 120, 180]);
  });
});

describe('a semana', () => {
  it('agruparPorDia devolve sempre os sete dias, com os blocos em ordem de hora', () => {
    const secoes = agruparPorDia(SEMANA);
    expect(secoes.map((s) => s.dia.curto)).toEqual(['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM']);
    expect(secoes[3].blocos.map((b) => b.id)).toEqual(['qui1', 'qui2']);
    expect(secoes[3].totalMinutos).toBe(150);
  });

  it('um dia sem bloco continua sendo uma seção', () => {
    const secoes = agruparPorDia([bloco('seg', 1, '19:00', 60)]);
    expect(secoes).toHaveLength(7);
    expect(secoes[1].blocos).toEqual([]);
    expect(secoes[1].totalMinutos).toBe(0);
  });

  it('a semana de exemplo soma 11h30', () => {
    expect(duracaoPorExtenso(totalDeMinutos(SEMANA))).toBe('11h30');
  });
});

describe('proximoBloco', () => {
  it('semana vazia não tem próximo', () => {
    expect(proximoBloco([], em(TERCA, 17, 40))).toBeNull();
  });

  it('terça às 17:40, com bloco hoje às 19:00 → hoje, daqui a 80 min', () => {
    const p = proximoBloco(SEMANA, em(TERCA, 17, 40));
    expect(p?.bloco.id).toBe('ter');
    expect(p?.diasAte).toBe(0);
    expect(p?.minutosAte).toBe(80);
    expect(p?.emAndamento).toBe(false);
    expect(p && quandoDoProximo(p)).toBe('hoje, 19:00');
  });

  it('bloco em andamento é "agora", e não "amanhã"', () => {
    const p = proximoBloco(SEMANA, em(TERCA, 19, 30));
    expect(p?.bloco.id).toBe('ter');
    expect(p?.emAndamento).toBe(true);
    expect(p?.minutosAte).toBeNull();
    expect(p && quandoDoProximo(p)).toBe('agora, até 20:30');
  });

  it('o bloco de hoje que já terminou fica para trás: o próximo é amanhã', () => {
    const p = proximoBloco(SEMANA, em(TERCA, 21, 0));
    expect(p?.bloco.id).toBe('qua');
    expect(p?.diasAte).toBe(1);
    expect(p && quandoDoProximo(p)).toBe('amanhã, 19:00');
  });

  it('o limite é exclusivo: às 20:30 em ponto o bloco das 19:00–20:30 já acabou', () => {
    expect(proximoBloco(SEMANA, em(TERCA, 20, 30))?.bloco.id).toBe('qua');
  });

  it('pula os dias sem bloco e diz o nome do dia', () => {
    const so = [bloco('qui', 4, '18:00', 60, 'Redação')];
    const p = proximoBloco(so, em(TERCA, 12));
    expect(p?.diasAte).toBe(2);
    expect(p && quandoDoProximo(p)).toBe('quinta-feira, 18:00');
  });

  it('dá a volta na semana: só estuda às terças e já é terça à noite', () => {
    const so = [bloco('ter', 2, '19:00', 90, 'Estequiometria')];
    const p = proximoBloco(so, em(TERCA, 21, 0));
    expect(p?.bloco.id).toBe('ter');
    expect(p?.diasAte).toBe(7);
    expect(p && quandoDoProximo(p)).toBe('terça-feira, 19:00');
  });

  it('domingo à noite o próximo é a segunda: a volta atravessa o 7 → 1', () => {
    const p = proximoBloco(SEMANA, em(DOMINGO, 20, 0));
    expect(p?.bloco.id).toBe('seg');
    expect(p?.diasAte).toBe(1);
  });

  it('um bloco que termina exatamente à meia-noite ainda conta como em andamento às 23:59', () => {
    const so = [bloco('ter', 2, '23:00', 60)];
    expect(proximoBloco(so, em(TERCA, 23, 59))?.emAndamento).toBe(true);
  });
});

describe('sobreposição', () => {
  it('encostar não é cruzar', () => {
    expect(sobrepoe(1080, 60, 1140, 90)).toBe(false);
    expect(sobrepoe(1140, 90, 1080, 60)).toBe(false);
  });

  it('cruzar, conter e igualar são sobreposição', () => {
    expect(sobrepoe(1140, 90, 1170, 60)).toBe(true);
    expect(sobrepoe(1140, 120, 1170, 30)).toBe(true);
    expect(sobrepoe(1140, 90, 1140, 90)).toBe(true);
  });

  it('blocoQueCruza só olha o dia pedido e ignora o bloco em edição', () => {
    expect(blocoQueCruza(SEMANA, 2, 1170, 60)?.id).toBe('ter');
    expect(blocoQueCruza(SEMANA, 3, 600, 60)).toBeNull();
    expect(blocoQueCruza(SEMANA, 2, 1170, 60, 'ter')).toBeNull();
  });
});

describe('o rascunho', () => {
  const pronto = { dias: [2], hora: '19:00', duracao: 90, rotulo: 'Estudo' };

  it('um rascunho novo traz o dia em que o aluno tocou no "+"', () => {
    expect(rascunhoNovo(4).dias).toEqual([4]);
  });

  it('terminaAs mostra o fim, e some quando passa da meia-noite ou falta a hora', () => {
    expect(terminaAs('19:00', 90)).toBe('20:30');
    expect(terminaAs('23:30', 60)).toBeNull();
    expect(terminaAs('', 60)).toBeNull();
  });

  it('um rascunho válido não tem problema', () => {
    expect(problemaDoRascunho({ ...pronto, dias: [1, 3], hora: '21:00' }, SEMANA)).toBeNull();
  });

  it.each([
    [{ dias: [] }, 'dia'],
    [{ hora: '' }, 'hora'],
    [{ rotulo: '   ' }, 'estudar'],
    [{ rotulo: 'x'.repeat(81) }, '80'],
    [{ hora: '23:30', duracao: 60 }, 'meia-noite'],
  ])('recusa %j com uma frase que cita "%s"', (mudanca, citacao) => {
    expect(problemaDoRascunho({ ...pronto, ...mudanca }, [])).toContain(citacao);
  });

  it('diz qual dia e qual bloco atrapalham', () => {
    const frase = problemaDoRascunho({ ...pronto, hora: '20:00' }, SEMANA);
    expect(frase).toContain('Terça-feira');
    expect(frase).toContain('Estequiometria');
    expect(frase).toContain('19:00');
    expect(frase).toContain('20:30');
  });

  it('em vários dias, basta um cruzar para recusar o rascunho inteiro', () => {
    expect(problemaDoRascunho({ ...pronto, dias: [1, 2, 3], hora: '19:30' }, SEMANA)).not.toBeNull();
  });

  it('editar o próprio bloco não cruza consigo mesmo', () => {
    expect(problemaDoRascunho(pronto, SEMANA, 'ter')).toBeNull();
    expect(problemaDoRascunho(pronto, SEMANA)).not.toBeNull();
  });

  it('alternarDia liga e desliga, sempre em ordem', () => {
    expect(alternarDia([1, 3], 2)).toEqual([1, 2, 3]);
    expect(alternarDia([1, 2, 3], 2)).toEqual([1, 3]);
    expect(alternarDia([], 5)).toEqual([5]);
  });
});

describe('blocosDoDia', () => {
  it('ordena por hora, e não pela ordem em que chegaram', () => {
    expect(blocosDoDia(SEMANA, 4).map((b) => b.id)).toEqual(['qui1', 'qui2']);
  });
});
