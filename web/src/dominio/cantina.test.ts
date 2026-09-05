import { describe, expect, it } from 'vitest';

import type { BlocoCardapio, Cardapio, DiaDoAluno } from '../tipos/cantina';
import {
  cardDaCantina, dataLocal, deInputLocal, gradeDoMes, instrucaoDoBloco, isoDoDia, marcadasNoBloco,
  paraInputLocal, pendenciaDoPedido, podeMarcarMais, prazoAberto, prazoLegivel, resumoDoPedido,
  rotuloDoDia,
} from './cantina';

const bloco = (parcial: Partial<BlocoCardapio>): BlocoCardapio => ({
  id: 'b', nome: 'Guarnição', ordem: 0, escolhas_minimas: 0, escolhas_maximas: 2,
  opcoes: [
    { id: 'arroz', nome: 'Arroz', ordem: 0, disponivel: true },
    { id: 'feijao', nome: 'Feijão', ordem: 1, disponivel: true },
    { id: 'macarrao', nome: 'Macarrão', ordem: 2, disponivel: true },
  ],
  ...parcial,
});

const cardapio = (blocos: BlocoCardapio[]): Cardapio => ({
  id: 'c', cantina_id: 'x', data: '2026-09-08', refeicao: 'almoco',
  pedidos_ate: null, publicado_em: null, sem_refeicao: false, estado: 'aberto', blocos,
});

describe('data local', () => {
  it('não escorrega um dia para trás', () => {
    // `new Date('2026-09-08')` é UTC e volta como dia 7 à noite em todo fuso
    // negativo — o Brasil inteiro. É o bug clássico de calendário, e aqui ele
    // apareceria como "o cardápio de terça aparece na segunda".
    expect(dataLocal('2026-09-08').getDate()).toBe(8);
    expect(dataLocal('2026-01-01').getMonth()).toBe(0);
  });

  it('vai e volta sem perder o dia', () => {
    expect(isoDoDia(dataLocal('2026-09-08'))).toBe('2026-09-08');
  });

  it('nomeia o dia da semana em português', () => {
    // 8 de setembro de 2026 é uma terça.
    expect(rotuloDoDia('2026-09-08')).toContain('terça');
  });
});

describe('prazo', () => {
  const agora = new Date('2026-09-07T12:00:00-03:00');

  it('conta minutos quando falta menos de uma hora', () => {
    // A escala muda com a urgência: faltando 40 min, é o número em minutos que
    // faz alguém parar e escolher.
    expect(prazoLegivel('2026-09-07T12:40:00-03:00', agora)).toBe('faltam 40 min');
  });

  it('conta horas dentro do mesmo dia', () => {
    expect(prazoLegivel('2026-09-07T20:00:00-03:00', agora)).toBe('faltam 8h');
  });

  it('nomeia o dia quando falta mais de um dia', () => {
    expect(prazoLegivel('2026-09-09T20:00:00-03:00', agora)).toContain('quarta');
  });

  it('diz que encerrou em vez de contar para trás', () => {
    expect(prazoLegivel('2026-09-07T11:00:00-03:00', agora)).toBe('prazo encerrado');
  });

  it('sem prazo não é prazo aberto', () => {
    // Cardápio publicado sem prazo não deveria existir (a rota de publicar
    // recusa), mas se existir vale como FECHADO — o mesmo lado seguro do
    // `_estado` do servidor.
    expect(prazoAberto(null, agora)).toBe(false);
    expect(prazoAberto('2026-09-07T11:00:00-03:00', agora)).toBe(false);
    expect(prazoAberto('2026-09-07T20:00:00-03:00', agora)).toBe(true);
  });
});

describe('teto por bloco', () => {
  it('conta o que está marcado', () => {
    expect(marcadasNoBloco(bloco({}), new Set(['arroz', 'feijao']))).toBe(2);
  });

  it('fecha a porta ao chegar no teto', () => {
    expect(podeMarcarMais(bloco({}), new Set(['arroz']))).toBe(true);
    expect(podeMarcarMais(bloco({}), new Set(['arroz', 'feijao']))).toBe(false);
  });

  it('teto zero é bloco só de leitura', () => {
    expect(podeMarcarMais(bloco({ escolhas_maximas: 0 }), new Set())).toBe(false);
  });
});

describe('pendência do pedido', () => {
  it('pedido completo não tem pendência', () => {
    const c = cardapio([bloco({ escolhas_minimas: 1 })]);
    expect(pendenciaDoPedido(c, new Set(['arroz']))).toBeNull();
  });

  it('diz QUAL bloco falta, e não "escolha inválida"', () => {
    const c = cardapio([bloco({ nome: 'Proteínas', escolhas_minimas: 1, escolhas_maximas: 1 })]);
    expect(pendenciaDoPedido(c, new Set())).toContain('Proteínas');
  });

  it('concorda em número com o que falta', () => {
    const c = cardapio([bloco({ escolhas_minimas: 2 })]);
    expect(pendenciaDoPedido(c, new Set())).toContain('2 opções');
    expect(pendenciaDoPedido(c, new Set(['arroz']))).toContain('uma opção');
  });

  it('devolve só a PRIMEIRA pendência', () => {
    // Quem está escolhendo almoço resolve uma coisa de cada vez; quatro avisos
    // simultâneos não dizem por onde começar.
    const c = cardapio([
      bloco({ id: 'b1', nome: 'Guarnição', escolhas_minimas: 1 }),
      bloco({ id: 'b2', nome: 'Proteínas', escolhas_minimas: 1 }),
    ]);
    const pendencia = pendenciaDoPedido(c, new Set());
    expect(pendencia).toContain('Guarnição');
    expect(pendencia).not.toContain('Proteínas');
  });

  it('bloco opcional vazio não é pendência', () => {
    expect(pendenciaDoPedido(cardapio([bloco({})]), new Set())).toBeNull();
  });
});

describe('leitura do pedido', () => {
  it('resume na ordem do cardápio, não na da seleção', () => {
    const c = cardapio([bloco({})]);
    expect(resumoDoPedido(c, ['feijao', 'arroz'])).toBe('Arroz · Feijão');
  });

  it('pedido vazio resume em nada', () => {
    expect(resumoDoPedido(cardapio([bloco({})]), [])).toBe('');
  });
});

describe('instrução do bloco', () => {
  it('distingue obrigatório de opcional', () => {
    // "escolha até 2" e "escolha 2" são coisas diferentes para quem monta o
    // prato; um rótulo genérico ("máx. 2") obrigaria a deduzir.
    expect(instrucaoDoBloco(bloco({ escolhas_minimas: 1, escolhas_maximas: 1 }))).toBe('Escolha 1');
    expect(instrucaoDoBloco(bloco({ escolhas_minimas: 0, escolhas_maximas: 2 }))).toBe('Escolha até 2');
    expect(instrucaoDoBloco(bloco({ escolhas_minimas: 1, escolhas_maximas: 3 }))).toBe('Escolha de 1 a 3');
    expect(instrucaoDoBloco(bloco({ escolhas_maximas: 0 }))).toBe('Só para conferir');
  });
});

describe('grade do mês', () => {
  it('alinha o dia 1 na coluna certa e fecha a última semana', () => {
    // Setembro de 2026 começa numa terça: duas casas vazias antes.
    const casas = gradeDoMes(2026, 8);
    expect(casas.slice(0, 2)).toEqual([null, null]);
    expect(casas[2]).toBe('2026-09-01');
    expect(casas.length % 7).toBe(0);
    expect(casas.filter(Boolean)).toHaveLength(30);
  });

  it('mês que começa no domingo não ganha casa vazia', () => {
    // Fevereiro de 2026 começa num domingo.
    expect(gradeDoMes(2026, 1)[0]).toBe('2026-02-01');
  });
});

describe('prazo no campo do editor', () => {
  it('vai e volta sem deslocar a hora', () => {
    // O `<input type="datetime-local">` é LOCAL e sem fuso. Passar o ISO cru
    // faz o campo aparecer VAZIO, sem erro nenhum — e a cantina conclui que o
    // prazo se perdeu.
    const local = paraInputLocal('2026-09-07T20:00:00-03:00');
    expect(local).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    expect(deInputLocal(local)).toBe(new Date('2026-09-07T20:00:00-03:00').toISOString());
  });

  it('campo vazio é prazo ausente, não data inválida', () => {
    expect(paraInputLocal(null)).toBe('');
    expect(deInputLocal('')).toBeNull();
    expect(deInputLocal('não é data')).toBeNull();
  });
});

describe('o card em Hoje', () => {
  const AGORA = new Date('2026-09-07T12:00:00-03:00');
  const ABERTO = '2026-09-07T20:00:00-03:00';
  const FECHADO = '2026-09-06T20:00:00-03:00';

  const dia = (p: Partial<DiaDoAluno>): DiaDoAluno => ({
    id: 'c', cantina_id: 'x', data: '2026-09-07', refeicao: 'almoco',
    pedidos_ate: ABERTO, publicado_em: '2026-09-01', sem_refeicao: false,
    estado: 'aberto', blocos: [], meuPedido: null, ...p,
  });

  it('sem dia nenhum, o card some', () => {
    expect(cardDaCantina([], AGORA)).toBeNull();
  });

  it('prazo aberto e sem pedido é o estado urgente', () => {
    expect(cardDaCantina([dia({})], AGORA)?.tipo).toBe('escolher');
  });

  it('o que falta pedir vence o que já foi pedido', () => {
    // Um cardápio de quarta ainda por pedir é mais urgente que o de terça já
    // resolvido, mesmo vindo depois na lista.
    const r = cardDaCantina([
      dia({ id: 'ter', meuPedido: ['x'] }),
      dia({ id: 'qua', data: '2026-09-09', meuPedido: null }),
    ], AGORA);
    expect(r).toEqual({ tipo: 'escolher', dia: expect.objectContaining({ id: 'qua' }) });
  });

  it('tudo pedido e prazo aberto vira linha quieta com troca', () => {
    expect(cardDaCantina([dia({ meuPedido: ['x'] })], AGORA)?.tipo).toBe('pedido-aberto');
  });

  it('prazo fechado com pedido ainda responde "o que eu vou comer"', () => {
    // ⚠️ O caso que faltava. Sem ele o card sumia, e como `/cantina` não está
    // na barra de quatro destinos, a tela ficava SEM PORTA: quem pediu na
    // véspera não tinha como conferir o próprio pedido.
    const r = cardDaCantina([dia({ pedidos_ate: FECHADO, meuPedido: ['x'] })], AGORA);
    expect(r?.tipo).toBe('pedido-fechado');
  });

  it('prazo fechado com pedido de dia que já passou não volta', () => {
    const r = cardDaCantina(
      [dia({ data: '2026-09-01', pedidos_ate: FECHADO, meuPedido: ['x'] })],
      AGORA,
    );
    expect(r).toBeNull();
  });

  it('prazo de hoje fechado e sem pedido avisa que não há reserva', () => {
    const r = cardDaCantina([dia({ pedidos_ate: FECHADO })], AGORA);
    expect(r?.tipo).toBe('sem-reserva');
  });

  it('prazo fechado de um dia futuro sem pedido não vira aviso de hoje', () => {
    // "Sem almoço reservado hoje" só vale para HOJE — dizer isso de quinta-feira
    // seria cobrança sobre algo que ainda nem chegou.
    const r = cardDaCantina([dia({ data: '2026-09-10', pedidos_ate: FECHADO })], AGORA);
    expect(r).toBeNull();
  });
});
