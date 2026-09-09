import { describe, expect, it } from 'vitest';

import type {
  BlocoCardapio, Cardapio, ContagemDeOpcao, DiaDoAluno, PedidoDeAluno, RetiradaConfirmada,
} from '../tipos/cantina';
import {
  blocoDeCadaOpcao, blocosDaContagem, blocosDoPeriodo,
  cardDaCantina, codigoNaTela, contagemPorModo, dataLocal, deInputLocal, escolhasDaLinha,
  escolhasPorBloco, horaDaLinha, recortarPedidos,
  FOLGA_DE_RENOVACAO_MS, fraseDaQuebra, gradeDoMes, horaLegivel, instrucaoDoBloco, isoDoDia,
  lerRespostaDoQr, MARGEM_DE_EXIBICAO_MS, marcaDoModo,
  marcadasNoBloco, msAteRenovar, normalizarContagem, paraInputLocal, pendenciaDoPedido,
  placaDaRetirada, PRAZO_DA_RENOVACAO_MS,
  podeMarcarMais, prazoAberto, prazoLegivel, presencialDoCardapio, quebraDaContagem,
  refeicaoPorHorario, resumoDoPedido, rotuloDaContagem, rotuloDoDia, situacaoDoDia, somarContagens,
} from './cantina';

const bloco = (parcial: Partial<BlocoCardapio>): BlocoCardapio => ({
  id: 'b', nome: 'Guarnição', ordem: 0, escolhas_minimas: 0, escolhas_maximas: 2,
  observacao: null,
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
  aceitaPedido: true, aceitaPresencial: false,
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
    estado: 'aberto', blocos: [], meuPedido: null,
    aceitaPedido: true, aceitaPresencial: false, modo: null, retiradoEm: null,
    cantina: null, ...p,
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

// ─── Retirada presencial (docs/40) ────────────────────────────────────────

describe('a máquina de estados do dia', () => {
  const AGORA = new Date('2026-09-07T12:00:00-03:00');
  const ABERTO = '2026-09-07T20:00:00-03:00';
  const FECHADO = '2026-09-06T20:00:00-03:00';

  const dia = (p: Partial<DiaDoAluno>): DiaDoAluno => ({
    id: 'c', cantina_id: 'x', data: '2026-09-07', refeicao: 'almoco',
    pedidos_ate: ABERTO, publicado_em: '2026-09-01', sem_refeicao: false,
    estado: 'aberto', blocos: [], meuPedido: null,
    aceitaPedido: true, aceitaPresencial: true, modo: null, retiradoEm: null,
    cantina: null, ...p,
  });

  it('dia em aberto oferece os dois caminhos quando o cardápio aceita os dois', () => {
    expect(situacaoDoDia(dia({}), AGORA)).toEqual({
      estado: 'aberto', podePedir: true, podeRetirar: true,
    });
  });

  it('cardápio só de pedido não oferece a retirada', () => {
    const s = situacaoDoDia(dia({ aceitaPresencial: false }), AGORA);
    expect(s.podePedir).toBe(true);
    expect(s.podeRetirar).toBe(false);
  });

  it('cardápio só de presencial não oferece o pedido', () => {
    const s = situacaoDoDia(dia({ aceitaPedido: false }), AGORA);
    expect(s.podePedir).toBe(false);
    expect(s.podeRetirar).toBe(true);
  });

  it('presencial IGNORA o prazo — é o caminho de quem não se planejou', () => {
    // A recusa do prazo é do pedido, não da retirada (docs/40 §3). Este teste é
    // a razão de a feature existir: às 12h05 o pedido já fechou e o aluno ainda
    // come.
    const s = situacaoDoDia(dia({ pedidos_ate: FECHADO }), AGORA);
    expect(s.podePedir).toBe(false);
    expect(s.podeRetirar).toBe(true);
  });

  it('retirada de um dia que não é hoje não é oferecida', () => {
    // Espelha o 422 proposto em docs/40 §11.1. Gerar o QR para daqui a três
    // dias não avisa a cozinha de nada real.
    expect(situacaoDoDia(dia({ data: '2026-09-10' }), AGORA).podeRetirar).toBe(false);
  });

  it('pedido é porta sem volta: trava o modo, não o conteúdo', () => {
    // O aluno troca arroz por batata até o prazo (docs/40 §11.2), mas não vira
    // presencial naquele cardápio.
    const s = situacaoDoDia(dia({ modo: 'pedido', meuPedido: ['arroz'] }), AGORA);
    expect(s.estado).toBe('pedido');
    expect(s.podePedir).toBe(true);
    expect(s.podeRetirar).toBe(false);
  });

  it('presencial ainda não lido é reversível', () => {
    // Gerou às 7h, ninguém leu, mudou de ideia às 11h e pede: o `PUT` de pedido
    // sobrescreve a linha presencial.
    const s = situacaoDoDia(dia({ modo: 'presencial' }), AGORA);
    expect(s.estado).toBe('presencial');
    expect(s.podePedir).toBe(true);
    expect(s.podeRetirar).toBe(true);
  });

  it('retirado é final dos dois lados', () => {
    const s = situacaoDoDia(dia({ modo: 'presencial', retiradoEm: '2026-09-07T12:14:00-03:00' }), AGORA);
    expect(s).toEqual({ estado: 'retirado', podePedir: false, podeRetirar: false });
  });

  it('presencial com pedido vazio não vira "pedi e não marquei nada"', () => {
    // ⚠️ O bug que o campo `modo` existe para evitar: a retirada não escolhe
    // item, então ela chega com `meuPedido` vazio — e `[] != null` é `true`.
    expect(situacaoDoDia(dia({ modo: 'presencial', meuPedido: [] }), AGORA).estado)
      .toBe('presencial');
  });

  it('servidor anterior à 0051 recai no comportamento de hoje: só pedido', () => {
    // Sem `aceitaPedido`/`aceitaPresencial` no corpo, a leitura tolerante devolve
    // exatamente o default do banco (0051): pedido ligado, presencial desligado.
    const antigo = { ...dia({}) } as Record<string, unknown>;
    delete antigo.aceitaPedido;
    delete antigo.aceitaPresencial;
    delete antigo.modo;
    delete antigo.retiradoEm;
    const s = situacaoDoDia(antigo as unknown as DiaDoAluno, AGORA);
    expect(s).toEqual({ estado: 'aberto', podePedir: true, podeRetirar: false });
  });
});

describe('o card em Hoje com retirada', () => {
  const AGORA = new Date('2026-09-07T12:00:00-03:00');
  const ABERTO = '2026-09-07T20:00:00-03:00';
  const FECHADO = '2026-09-06T20:00:00-03:00';

  const dia = (p: Partial<DiaDoAluno>): DiaDoAluno => ({
    id: 'c', cantina_id: 'x', data: '2026-09-07', refeicao: 'almoco',
    pedidos_ate: ABERTO, publicado_em: '2026-09-01', sem_refeicao: false,
    estado: 'aberto', blocos: [], meuPedido: null,
    aceitaPedido: true, aceitaPresencial: true, modo: null, retiradoEm: null,
    cantina: null, ...p,
  });

  it('retirada pendente de hoje vira linha com o caminho para o código', () => {
    expect(cardDaCantina([dia({ modo: 'presencial', pedidos_ate: FECHADO })], AGORA)?.tipo)
      .toBe('retirada');
  });

  it('o que ainda dá para pedir vence a retirada já resolvida', () => {
    // Só o prazo do PEDIDO expira: o QR de hoje não vira abóbora ao meio-dia, o
    // cardápio de amanhã por escolher, sim.
    const r = cardDaCantina([
      dia({ id: 'hoje', modo: 'presencial', pedidos_ate: FECHADO }),
      dia({ id: 'amanha', data: '2026-09-08' }),
    ], AGORA);
    expect(r).toEqual({ tipo: 'escolher', dia: expect.objectContaining({ id: 'amanha' }) });
  });

  it('prazo vencido sem pedido vira "ainda dá" quando o dia aceita presencial', () => {
    // É a diferença entre "você perdeu" e "ainda dá" — e é a razão da feature.
    expect(cardDaCantina([dia({ pedidos_ate: FECHADO })], AGORA)?.tipo).toBe('presencial-aberto');
  });

  it('sem presencial no cardápio, o prazo vencido continua sendo "sem reserva"', () => {
    const r = cardDaCantina([dia({ pedidos_ate: FECHADO, aceitaPresencial: false })], AGORA);
    expect(r?.tipo).toBe('sem-reserva');
  });

  it('quem já comeu lê a hora, não uma cobrança', () => {
    const r = cardDaCantina(
      [dia({ modo: 'presencial', retiradoEm: '2026-09-07T12:14:00-03:00', pedidos_ate: FECHADO })],
      AGORA,
    );
    expect(r?.tipo).toBe('retirado');
  });
});

describe('renovação do token do QR', () => {
  const AGORA = new Date('2026-09-07T12:00:00-03:00');

  it('renova antes de vencer, com a folga da viagem de rede', () => {
    // Dois minutos de validade (docs/40 §4): a renovação sai bem antes, senão o
    // QR na tela do aluno vira leitura falhada com fila atrás.
    const doisMinutos = new Date(AGORA.getTime() + 120_000).toISOString();
    expect(msAteRenovar(doisMinutos, AGORA)).toBe(120_000 - FOLGA_DE_RENOVACAO_MS);
  });

  it('token já vencido pede outro logo, sem entrar em laço', () => {
    const passado = new Date(AGORA.getTime() - 60_000).toISOString();
    expect(msAteRenovar(passado, AGORA)).toBe(5_000);
  });

  it('sem token ainda, espera o piso', () => {
    expect(msAteRenovar(null, AGORA)).toBe(5_000);
    expect(msAteRenovar('não é data', AGORA)).toBe(5_000);
  });
});

describe('o QR que vai para a tela', () => {
  const CHEGOU = new Date('2026-09-07T12:00:00-03:00').getTime();
  /** `expiraEm` de um token que vale `segundos` a partir da chegada. */
  const validoPor = (segundos: number) => new Date(CHEGOU + segundos * 1000).toISOString();

  it('token recém-chegado vai para a placa', () => {
    expect(codigoNaTela(validoPor(120), CHEGOU, CHEGOU).vale).toBe(true);
  });

  it('agenda a própria reavaliação para o instante em que o código morre', () => {
    // Nada na tela muda quando o token vence: sem este prazo, o QR morto ficaria
    // na placa até a próxima resposta do servidor.
    expect(codigoNaTela(validoPor(120), CHEGOU, CHEGOU).msAteVencer)
      .toBe(120_000 - MARGEM_DE_EXIBICAO_MS);
  });

  it('vencido não vai para a tela — um QR morto no balcão é uma leitura recusada', () => {
    const r = codigoNaTela(validoPor(120), CHEGOU, CHEGOU + 121_000);
    expect(r.vale).toBe(false);
    // Nada a agendar: quem devolve o QR é a renovação, não o relógio.
    expect(r.msAteVencer).toBe(null);
  });

  it('sai da placa ANTES do vencimento, pela margem entre o olho e a câmera', () => {
    expect(codigoNaTela(validoPor(120), CHEGOU, CHEGOU + 119_000).vale).toBe(false);
  });

  it('sem token não há código a mostrar', () => {
    expect(codigoNaTela(null, CHEGOU, CHEGOU)).toEqual({ vale: false, msAteVencer: null });
    expect(codigoNaTela(undefined, CHEGOU, CHEGOU).vale).toBe(false);
  });

  it('celular com a hora adiantada continua mostrando o código', () => {
    // O aparelho acha que a validade já passou; o servidor, que é quem julga,
    // acabou de emitir. Esconder aqui deixaria este aluno sem QR nenhum, sempre.
    const dezMinutosAdiantado = CHEGOU + 10 * 60_000;
    const r = codigoNaTela(validoPor(120), dezMinutosAdiantado, dezMinutosAdiantado);
    expect(r.vale).toBe(true);
    expect(r.msAteVencer).toBe(null);
  });

  it('`expiraEm` ilegível não esconde o código', () => {
    expect(codigoNaTela('não é data', CHEGOU, CHEGOU)).toEqual({ vale: true, msAteVencer: null });
  });
});

describe('o prazo da renovação', () => {
  it('é curto o bastante para o erro chegar ANTES de o código sair da placa', () => {
    // A desigualdade é a razão de ser do número: a renovação dispara
    // `FOLGA_DE_RENOVACAO_MS` antes de vencer, e o QR sai da placa
    // `MARGEM_DE_EXIBICAO_MS` antes disso. Um prazo maior que essa diferença faz
    // a tela chegar ao vencimento SEM SABER que a renovação falhou — que é
    // exatamente o "Renovando o código…" para sempre, com a fila na frente.
    expect(PRAZO_DA_RENOVACAO_MS).toBeLessThan(FOLGA_DE_RENOVACAO_MS - MARGEM_DE_EXIBICAO_MS);
  });

  it('não é o teto do gateway disfarçado', () => {
    // 300 s é o `proxy_read_timeout` do nginx, e ele está certo para o lote do
    // Canvas. Cinco minutos de tela sem QR não são o prazo de ninguém na fila.
    expect(PRAZO_DA_RENOVACAO_MS).toBeLessThan(60_000);
  });
});

describe('a placa do QR na tela do aluno', () => {
  const semFalha = { falha: null };

  it('código válido na mão vai para a placa', () => {
    expect(placaDaRetirada({ temCodigo: true, codigoVale: true, ...semFalha }))
      .toEqual({ tipo: 'codigo' });
  });

  it('⚠️ código válido VENCE a falha da última renovação', () => {
    // O defeito que este teste tranca: a tela escondia a placa inteira em
    // `isError`, e o reducer do `query-core` PRESERVA `data` no caso "error" —
    // ou seja, jogava fora um QR que ainda valia 23 segundos, com o aluno na
    // frente da fila. Quem julga o código é o servidor, no balcão.
    const r = placaDaRetirada({
      temCodigo: true,
      codigoVale: true,
      falha: { status: 0, mensagem: 'Sem resposta do servidor.' },
    });
    expect(r).toEqual({ tipo: 'codigo' });
  });

  it('primeira resposta ainda não chegou: gerando', () => {
    expect(placaDaRetirada({ temCodigo: false, codigoVale: false, ...semFalha }))
      .toEqual({ tipo: 'gerando' });
  });

  it('código vencido com a renovação a caminho: renovando', () => {
    expect(placaDaRetirada({ temCodigo: true, codigoVale: false, ...semFalha }))
      .toEqual({ tipo: 'renovando' });
  });

  it('sem resposta e sem código: a falha do transporte, com saída', () => {
    const r = placaDaRetirada({
      temCodigo: true,
      codigoVale: false,
      falha: { status: 0, mensagem: 'O servidor não respondeu a tempo. Tente de novo.' },
    });
    expect(r.tipo).toBe('sem-resposta');
    // ⚠️ A frase do transporte NÃO passa: ela foi escrita para a coordenação, que
    // tem botão, e nesta tela ficava ao lado de "não há nada para atualizar".
    expect(r).toHaveProperty('mensagem', expect.not.stringContaining('Tente de novo'));
    expect(r).toHaveProperty('mensagem', expect.stringContaining('sozinho'));
  });

  it('servidor caído é ausência de resposta, não veredito sobre este aluno', () => {
    expect(placaDaRetirada({
      temCodigo: false,
      codigoVale: false,
      falha: { status: 502, mensagem: 'Bad gateway' },
    }).tipo).toBe('sem-resposta');
  });

  it('a recusa do servidor passa inteira — ela explica a regra', () => {
    expect(placaDaRetirada({
      temCodigo: false,
      codigoVale: false,
      falha: { status: 409, mensagem: 'Você já fez o pedido — não dá para trocar.' },
    })).toEqual({ tipo: 'recusado', mensagem: 'Você já fez o pedido — não dá para trocar.' });
  });

  it('o `POST /x → 422` cru vira frase de gente, e sem prometer tentativa', () => {
    // Nenhuma segunda tentativa muda uma recusa definitiva, e a tela não oferece
    // botão aqui: mandar "tente de novo" seria mandar bater na mesma porta.
    const r = placaDaRetirada({
      temCodigo: false,
      codigoVale: false,
      falha: { status: 422, mensagem: 'POST /me/cantina/retiradas/c1 → 422' },
    });
    expect(r.tipo).toBe('recusado');
    expect(r).toHaveProperty('mensagem', expect.not.stringContaining('→'));
    expect(r).toHaveProperty('mensagem', expect.not.stringContaining('de novo'));
  });
});

describe('contagem com presencial', () => {
  const linha = {
    cardapio_id: 'c', bloco_id: 'b', bloco: 'Guarnição', bloco_ordem: 0,
    opcao_id: 'arroz', opcao: 'Arroz', opcao_ordem: 0, disponivel: true, quantos: 47,
  };

  it('aceita a forma nova', () => {
    expect(normalizarContagem({ opcoes: [linha], presencial: { pendentes: 3, retirados: 12 } }))
      .toEqual({ opcoes: [linha], presencial: { pendentes: 3, retirados: 12 } });
  });

  it('aceita a lista do servidor anterior à 0051 sem derrubar a tela', () => {
    // A janela entre o deploy do backend e o do front não pode virar
    // `contagem.map is not a function` na cara de quem está com a mão na panela.
    expect(normalizarContagem([linha])).toEqual({ opcoes: [linha], presencial: null });
  });

  it('resposta vazia é "não sei", não "ninguém"', () => {
    expect(normalizarContagem(undefined)).toEqual({ opcoes: [], presencial: null });
  });
});

describe('a marca de modo nas listas', () => {
  it('distingue os três estados que a coordenação lê', () => {
    expect(marcaDoModo({ modo: 'pedido', retiradoEm: null })).toBe('pedido');
    expect(marcaDoModo({ modo: 'presencial', retiradoEm: null })).toBe('retirada na hora');
    expect(marcaDoModo({ modo: 'presencial', retiradoEm: '2026-09-07T12:14:00-03:00' }))
      .toBe('retirada na hora · retirado');
  });

  it('a palavra é a MESMA do editor e da quebra — "presencial" é dado, não texto', () => {
    // O nome do modo aparece na mesma dobra que `fraseDaQuebra` em três telas.
    // Dois nomes ali fazem a cantina e a coordenação discutirem duas features
    // onde há uma (docs/40 §7 e §8).
    const marca = marcaDoModo({ modo: 'presencial', retiradoEm: null });
    expect(fraseDaQuebra({ comPedido: 44, presenciais: 3 })).toContain(marca);
    expect(marca).not.toContain('presencial');
  });

  it('linha sem modo é pedido — é o default do banco', () => {
    expect(marcaDoModo({})).toBe('pedido');
  });
});

describe('a coluna de escolhas', () => {
  it('quem pediu leva os pratos, no separador de quem chamou', () => {
    const pedido = { modo: 'pedido' as const, retiradoEm: null, escolhas: ['Arroz', 'Feijão'] };
    expect(escolhasDaLinha(pedido)).toBe('Arroz · Feijão');
    expect(escolhasDaLinha(pedido, ' | ')).toBe('Arroz | Feijão');
  });

  it('retirada na hora não sai vazia — vazio é lido como dado faltando', () => {
    // "João Silva · 3ºA · —" na folha impressa faz quem serve procurar um prato
    // que não existe (docs/40 §10.1).
    expect(escolhasDaLinha({ modo: 'presencial', retiradoEm: null }))
      .toBe('sem prato escolhido — vai mostrar o código no balcão');
  });

  it('a instrução do balcão sai nas TRÊS superfícies, não só na tela', () => {
    // A tela da cantina reimplementava esta frase à mão e por isso o papel saía
    // sem a metade que diz o que FAZER com a linha. Uma cópia sem teste é uma
    // cópia que diverge — este teste é o que impede a próxima.
    const linha = escolhasDaLinha({ modo: 'presencial', retiradoEm: null });
    expect(linha).toContain('código');
  });

  it('depois da leitura do QR, a linha vira a hora em que ele passou', () => {
    expect(escolhasDaLinha({ modo: 'presencial', retiradoEm: '2026-09-07T12:14:00-03:00' }))
      .toMatch(/^retirado às \d{2}:\d{2}$/);
  });

  it('pedido sem nada marcado continua vazio — quem decide o traço é a folha', () => {
    expect(escolhasDaLinha({ modo: 'pedido', escolhas: [] })).toBe('');
  });
});

describe('o placar de retirada na hora de um cardápio', () => {
  const presencial = { modo: 'presencial' as const, retiradoEm: null };
  const retirado = { modo: 'presencial' as const, retiradoEm: '2026-09-07T12:14:00-03:00' };
  const pedido = { modo: 'pedido' as const, retiradoEm: null };

  it('o servidor manda o placar, e ele vence a lista', () => {
    expect(presencialDoCardapio({ pendentes: 2, retirados: 10 }, []))
      .toEqual({ pendentes: 2, retirados: 10 });
  });

  it('servidor que ainda não manda o bloco não deixa a coluna muda', () => {
    // É a janela entre o deploy do backend e o do front: sem isto, "Nenhum
    // pedido ainda" apareceria ao lado de doze nomes.
    expect(presencialDoCardapio(undefined, [pedido, presencial, retirado, presencial]))
      .toEqual({ pendentes: 2, retirados: 1 });
  });

  it('cardápio sem ninguém pegando na hora não ganha placar de zeros', () => {
    expect(presencialDoCardapio({ pendentes: 0, retirados: 0 }, [pedido])).toBeNull();
    expect(presencialDoCardapio(null, [pedido, pedido])).toBeNull();
    expect(presencialDoCardapio(undefined, [])).toBeNull();
  });
});

describe('a leitura do QR no balcão', () => {
  const ficha: RetiradaConfirmada = {
    alunoId: 'a1', nome: 'Ana Beatriz', turma: 'ITA 1', refeicao: 'almoco',
    data: '2026-09-07', restricaoAlimentar: null, retiradoEm: '2026-09-07T12:14:00-03:00',
  };

  it('sucesso entrega a ficha', () => {
    const r = lerRespostaDoQr(ficha, 'almoco');
    expect(r).toEqual({ tipo: 'sucesso', ficha, refeicaoTrocada: false });
  });

  it('QR de janta lido no almoço é sinalizado, não recusado', () => {
    // O token é VÁLIDO (docs/40 §7): quem decide é quem está no balcão.
    const r = lerRespostaDoQr({ ...ficha, refeicao: 'janta' }, 'almoco');
    expect(r).toEqual({ tipo: 'sucesso', ficha: expect.anything(), refeicaoTrocada: true });
  });

  it('409 é segunda passagem, não erro', () => {
    const r = lerRespostaDoQr({ status: 409, mensagem: 'Já retirado às 12h14.' }, 'almoco');
    expect(r).toEqual({ tipo: 'ja-retirado', mensagem: 'Já retirado às 12h14.' });
  });

  it('422 manda a ação para o lado certo: o aluno atualiza a tela', () => {
    const r = lerRespostaDoQr({ status: 422, mensagem: '' }, 'almoco');
    expect(r.tipo).toBe('atualizar');
    expect(r).toHaveProperty('mensagem', expect.stringContaining('atualizar'));
  });

  it('403 de outra cantina não vira "peça para atualizar"', () => {
    // A ação seguinte é outra, e mandar o aluno atualizar a tela não resolveria
    // nada: o cardápio é de outro estabelecimento.
    const r = lerRespostaDoQr({ status: 403, mensagem: 'Cardápio de outra cantina.' }, 'almoco');
    expect(r).toEqual({ tipo: 'recusado', mensagem: 'Cardápio de outra cantina.' });
  });

  it('sem status não é recusa: é ausência de resposta, e a ação é ler de novo', () => {
    // `status: 0` é a convenção de `servicos/http.ts` para "a requisição não
    // voltou" — rede caída, ou o teto de tempo abortando. Cair em `recusado`
    // mandaria embora, com "não dá para servir por aqui", um aluno que tem
    // direito à refeição e só precisa que se leia o código outra vez.
    const r = lerRespostaDoQr({ status: 0, mensagem: '' }, 'almoco');
    expect(r.tipo).toBe('sem-resposta');
    expect(r).toHaveProperty('mensagem', expect.stringContaining('de novo'));
  });

  it('a frase do transporte passa inteira quando existe', () => {
    const r = lerRespostaDoQr(
      { status: 0, mensagem: 'O servidor não respondeu a tempo. Tente de novo.' },
      'almoco',
    );
    expect(r).toEqual({
      tipo: 'sem-resposta',
      mensagem: 'O servidor não respondeu a tempo. Tente de novo.',
    });
  });
});

describe('o serviço em curso', () => {
  it('abre no almoço de manhã e na janta à noite', () => {
    expect(refeicaoPorHorario(new Date('2026-09-07T11:30:00'))).toBe('almoco');
    expect(refeicaoPorHorario(new Date('2026-09-07T19:00:00'))).toBe('janta');
  });

  it('a hora da retirada é só hora e minuto', () => {
    expect(horaLegivel('2026-09-07T12:14:00-03:00')).toMatch(/^\d{2}:\d{2}$/);
    expect(horaLegivel(null)).toBe('');
  });
});

describe('a quebra da contagem do calendário', () => {
  it('dia sem presencial nenhum não ganha quebra — e a tela fica como estava', () => {
    // A regra que impede a feature de virar ruído: 60 células por mês, e na
    // esmagadora maioria delas a quebra não teria o que dizer.
    expect(quebraDaContagem({ pedidos: 47, comPedido: 47, presenciais: 0 })).toBeNull();
  });

  it('servidor anterior à 0052 não vira "nenhum presencial"', () => {
    // "Não sei" virando "ninguém" é a mentira mais barata de escrever e a mais
    // cara de descobrir — e aqui ela apareceria como uma quebra que não bate.
    expect(quebraDaContagem({ pedidos: 47 })).toBeNull();
  });

  it('com presencial, devolve as duas metades do total', () => {
    expect(quebraDaContagem({ pedidos: 47, comPedido: 44, presenciais: 3 }))
      .toEqual({ comPedido: 44, presenciais: 3 });
  });

  it('ninguém pediu e três vão pegar na hora: a quebra é o caso mais importante', () => {
    // É o dia em que "o que cozinhar" fica vazio e o calendário mostra 3 — sem
    // a quebra, é exatamente aqui que nasce o chamado de bug.
    expect(quebraDaContagem({ pedidos: 3, comPedido: 0, presenciais: 3 }))
      .toEqual({ comPedido: 0, presenciais: 3 });
  });

  it('a frase usa as palavras do editor da cantina, não um segundo nome', () => {
    expect(fraseDaQuebra({ comPedido: 44, presenciais: 3 }))
      .toBe('44 com pedido · 3 de retirada na hora');
  });

  it('para o leitor de tela, o separador vira palavra', () => {
    expect(fraseDaQuebra({ comPedido: 44, presenciais: 3 }, ' e '))
      .toBe('44 com pedido e 3 de retirada na hora');
  });

  it('mês inteiro sai com o ponto de milhar', () => {
    expect(fraseDaQuebra({ comPedido: 1790, presenciais: 52 }))
      .toBe('1.790 com pedido · 52 de retirada na hora');
  });
});

describe('o nome do total', () => {
  it('sem presencial, continua sendo "pedidos"', () => {
    expect(rotuloDaContagem({ pedidos: 47, comPedido: 47, presenciais: 0 })).toBe('pedidos');
    expect(rotuloDaContagem({ pedidos: 1, comPedido: 1, presenciais: 0 })).toBe('pedido');
  });

  it('com presencial, o total deixa de ser "pedido" — ele conta quem vai comer', () => {
    expect(rotuloDaContagem({ pedidos: 47, comPedido: 44, presenciais: 3 })).toBe('vão comer');
    expect(rotuloDaContagem({ pedidos: 1, comPedido: 0, presenciais: 1 })).toBe('vai comer');
  });

  it('servidor sem a quebra mantém a palavra de sempre', () => {
    expect(rotuloDaContagem({ pedidos: 47 })).toBe('pedidos');
  });
});

describe('somar contagens', () => {
  it('soma as duas refeições do dia, quebra inclusive', () => {
    expect(somarContagens([
      { pedidos: 47, comPedido: 44, presenciais: 3 },
      { pedidos: 20, comPedido: 20, presenciais: 0 },
    ])).toEqual({ pedidos: 67, comPedido: 64, presenciais: 3 });
  });

  it('refeição que não existe não conta nada', () => {
    expect(somarContagens([null, { pedidos: 20, comPedido: 18, presenciais: 2 }, undefined]))
      .toEqual({ pedidos: 20, comPedido: 18, presenciais: 2 });
  });

  it('uma parcela sem quebra derruba a quebra da soma — não a completa com zero', () => {
    // Somar quem sabe com quem não sabe daria um "com pedido" menor que a
    // verdade, e um número errado é pior que número nenhum.
    expect(somarContagens([{ pedidos: 47, comPedido: 44, presenciais: 3 }, { pedidos: 20 }]))
      .toEqual({ pedidos: 67 });
  });

  it('dia inteiro em branco soma zero, sem quebra', () => {
    expect(somarContagens([null, undefined])).toEqual({ pedidos: 0 });
  });
});

describe('a contagem vinda da lista do balcão', () => {
  it('separa quem pediu de quem vai pegar na hora', () => {
    expect(contagemPorModo([
      { modo: 'pedido' }, { modo: 'presencial' }, { modo: 'pedido' },
    ])).toEqual({ pedidos: 3, comPedido: 2, presenciais: 1 });
  });

  it('lista de servidor antigo, sem `modo`, conta tudo como pedido', () => {
    expect(contagemPorModo([{}, {}])).toEqual({ pedidos: 2, comPedido: 2, presenciais: 0 });
  });

  it('lista vazia não inventa quebra', () => {
    expect(quebraDaContagem(contagemPorModo([]))).toBeNull();
  });
});

// ─── A planilha larga (docs/40 §12.5.2) ──────────────────────────────────

describe('uma coluna por bloco', () => {
  const linha = (bloco: string, ordem: number, opcao: string): ContagemDeOpcao => ({
    cardapio_id: 'c', bloco_id: `b-${bloco}`, bloco, bloco_ordem: ordem,
    opcao_id: `o-${opcao}`, opcao, opcao_ordem: 1, disponivel: true, quantos: 0,
  });

  const CONTAGEM: ContagemDeOpcao[] = [
    linha('Guarnição', 1, 'Arroz'),
    linha('Guarnição', 1, 'Feijão'),
    linha('Proteína', 2, 'Frango'),
    linha('Salada', 3, 'Folhas'),
  ];

  it('lê os blocos na ordem da bandeja, não em ordem alfabética', () => {
    expect(blocosDaContagem(CONTAGEM)).toEqual(['Guarnição', 'Proteína', 'Salada']);
  });

  it('mantém a coluna do bloco em que ninguém pediu nada', () => {
    // A contagem traz a opção com `quantos: 0`, e é por isso que ela sai da
    // contagem e não dos pedidos: um dia sem salada pedida perderia a coluna.
    expect(blocosDaContagem(CONTAGEM)).toContain('Salada');
  });

  it('distribui as escolhas de um aluno pelas colunas certas', () => {
    const blocos = blocosDaContagem(CONTAGEM);
    const mapa = blocoDeCadaOpcao(CONTAGEM);
    const celulas = escolhasPorBloco(
      { modo: 'pedido', escolhas: ['Arroz', 'Feijão', 'Frango'] }, blocos, mapa,
    );
    expect(celulas).toEqual(['Arroz; Feijão', 'Frango', '']);
  });

  it('quem pega na hora sai com traço, e não com célula vazia', () => {
    // Vazio numa planilha lê-se como "faltou o dado". O traço diz que não
    // havia dado a ter (docs/40 §10.1).
    const blocos = blocosDaContagem(CONTAGEM);
    const celulas = escolhasPorBloco(
      { modo: 'presencial', escolhas: [] }, blocos, blocoDeCadaOpcao(CONTAGEM),
    );
    expect(celulas).toEqual(['—', '—', '—']);
  });

  it('a semana usa a UNIÃO dos blocos, na ordem em que apareceram', () => {
    const terca = [linha('Guarnição', 1, 'Arroz'), linha('Proteína', 2, 'Frango')];
    const quarta = [linha('Guarnição', 1, 'Baião'), linha('Sobremesa', 3, 'Pudim')];
    expect(blocosDoPeriodo([terca, quarta]))
      .toEqual(['Guarnição', 'Proteína', 'Sobremesa']);
  });

  it('opção de nome repetido cai no primeiro bloco, sem sumir', () => {
    // Ambiguidade do CARDÁPIO, não do código. Resolver aqui escondendo uma das
    // duas seria pior que repetir o nome na coluna errada.
    const ambiguo = [linha('Vegetariano', 1, 'Ovo'), linha('Guarnição', 2, 'Ovo')];
    expect(blocoDeCadaOpcao(ambiguo).get('Ovo')).toBe('Vegetariano');
  });
});

// ─── A lista de trabalho (docs/40 §12.4) ─────────────────────────────────

describe('recortar a lista de quem vai comer', () => {
  const p = (parcial: Partial<PedidoDeAluno>): PedidoDeAluno => ({
    alunoId: 'a', nome: 'Ana', turma: 'ITA-A', restricaoAlimentar: null,
    escolhas: [], pedidoEm: '2026-09-07T17:00:00Z', modo: 'pedido', retiradoEm: null,
    ...parcial,
  });

  const LISTA: PedidoDeAluno[] = [
    p({ alunoId: '1', nome: 'Caio', turma: 'ITA-B', pedidoEm: '2026-09-07T19:50:00Z' }),
    p({ alunoId: '2', nome: 'Ana', turma: 'ITA-A', pedidoEm: '2026-09-07T17:10:00Z' }),
    p({ alunoId: '3', nome: 'Bruno', turma: 'ITA-A', modo: 'presencial',
        retiradoEm: '2026-09-08T12:07:00Z', pedidoEm: '2026-09-08T12:00:00Z' }),
    p({ alunoId: '4', nome: 'Édis', turma: 'IME-A', restricaoAlimentar: 'sem lactose' }),
  ];

  const recorte = (o: Partial<Parameters<typeof recortarPedidos>[1]> = {}) =>
    recortarPedidos(LISTA, { filtros: new Set(), busca: '', ordem: 'nome', ...o })
      .map((x) => x.nome);

  it('sem filtro nem busca, ordena por nome', () => {
    expect(recorte()).toEqual(['Ana', 'Bruno', 'Caio', 'Édis']);
  });

  it('a busca ignora acento e caixa', () => {
    // "Edis" tem de achar "Édis" — quem digita na fila não põe acento.
    expect(recorte({ busca: 'edis' })).toEqual(['Édis']);
    expect(recorte({ busca: 'CA' })).toEqual(['Caio']);
  });

  it('os filtros se ACUMULAM, não se somam', () => {
    // Marcar dois é procurar quem satisfaz os dois. União faria a lista
    // CRESCER ao filtrar, que é o oposto do que a pílula promete.
    expect(recorte({ filtros: new Set(['presencial', 'retirado']) })).toEqual(['Bruno']);
    expect(recorte({ filtros: new Set(['pediu', 'retirado']) })).toEqual([]);
  });

  it('"retirado" olha a hora da retirada, não o modo', () => {
    expect(recorte({ filtros: new Set(['retirado']) })).toEqual(['Bruno']);
  });

  it('ordena por hora, e quem não tem hora vai para o fim', () => {
    const semHora = [...LISTA, p({ alunoId: '5', nome: 'Zoe', pedidoEm: '' })];
    const nomes = recortarPedidos(semHora, {
      filtros: new Set(), busca: '', ordem: 'hora',
    }).map((x) => x.nome);
    expect(nomes[nomes.length - 1]).toBe('Zoe');
    // Édis carrega a hora padrão da fábrica (17:00), antes da Ana (17:10).
    expect(nomes.slice(0, 3)).toEqual(['Édis', 'Ana', 'Caio']);
  });

  it('ordena por turma e, dentro dela, por nome', () => {
    expect(recorte({ ordem: 'turma' })).toEqual(['Édis', 'Ana', 'Bruno', 'Caio']);
  });
});

describe('a hora na linha', () => {
  it('prefere a retirada ao pedido', () => {
    // Entre "quando marcou" e "quando comeu", quem confere a fila quer a segunda.
    const linha = horaDaLinha({
      pedidoEm: '2026-09-07T17:00:00Z', retiradoEm: '2026-09-08T15:07:00Z',
    });
    expect(linha).toContain('retirado');
  });

  it('sem hora nenhuma, não inventa texto', () => {
    expect(horaDaLinha({ pedidoEm: '', retiradoEm: null })).toBeNull();
  });
});
