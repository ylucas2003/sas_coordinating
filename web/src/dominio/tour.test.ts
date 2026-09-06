import { describe, expect, it } from 'vitest';

import {
  ANCORA_VAZIA, ancoraDoTour, chaveDoTour, destinoDoPasso, montarTour, PASSOS, QUADRO,
} from './tour';
import type { AncoraDoTour } from './tour';
import type { Ciclo, Simulado } from '../tipos/dominio';

const ANCORA: AncoraDoTour = {
  cicloId: 'C4',
  nomeDoCiclo: 'Ciclo 4 · ITA · 2026',
  provaId: 'S12',
  nomeDaProva: 'Física · P8',
};

describe('os seis passos', () => {
  it('são seis, na ordem do trabalho', () => {
    expect(PASSOS.map((p) => p.chave)).toEqual([
      'bifurcacao', 'regua', 'campos', 'varredura', 'mapa', 'lugar',
    ]);
  });

  it('cita a regra de desenho em todos', () => {
    // É o que separa tour de tutorial: cada passo diz POR QUE a tela é assim,
    // e sem a regra sobra a descrição do que já está na frente da pessoa.
    for (const passo of PASSOS) {
      expect(passo.regra.length, passo.chave).toBeGreaterThan(20);
    }
  });

  it('mantém as regiões dentro do quadro da prancheta', () => {
    // O esquema do passo desenha a região sobre um retângulo de 1440×900. Uma
    // região que estourasse o quadro sairia recortada, sem erro nenhum.
    for (const { chave, regiao } of PASSOS) {
      expect(regiao.x + regiao.largura, chave).toBeLessThanOrEqual(QUADRO.largura);
      expect(regiao.y + regiao.altura, chave).toBeLessThanOrEqual(QUADRO.altura);
    }
  });

  it('numera o contador com o total da própria lista', () => {
    expect(montarTour(ANCORA).map((p) => p.contador)).toEqual([
      '1 de 6', '2 de 6', '3 de 6', '4 de 6', '5 de 6', '6 de 6',
    ]);
  });
});

describe('para onde cada passo aponta', () => {
  it('leva a régua, os campos e a varredura à MESMA ficha de ciclo', () => {
    // A absorção da fase 3: as três coisas moravam em telas diferentes e hoje
    // se respondem sem trocar de endereço. Continuam sendo três passos porque
    // são três perguntas.
    const tour = montarTour(ANCORA);
    const fichas = tour
      .filter((p) => p.chave === 'regua' || p.chave === 'campos' || p.chave === 'varredura')
      .map((p) => p.destino?.para);
    expect(fichas).toEqual(['/ciclos/C4', '/ciclos/C4', '/ciclos/C4']);
  });

  it('nomeia no botão a coisa que abre, e não a ação', () => {
    expect(destinoDoPasso('mapa', ANCORA)).toEqual({
      para: '/ciclos/C4/calibracao',
      rotulo: 'Abrir a calibração de Ciclo 4 · ITA · 2026',
    });
    expect(destinoDoPasso('lugar', ANCORA)?.rotulo).toBe('Abrir Física · P8');
  });

  // ⚠️ O teste que justifica o módulo existir. Três das seis telas do tour
  // mudaram de endereço na refatoração do docs/39, e um tour que apontasse
  // para os antigos ensinaria a procurar onde não está.
  it('nunca aponta para um endereço que a refatoração aposentou', () => {
    const mortos = [
      '/ciclos/C4/regua',   // a régua foi absorvida pela ficha (fase 3)
      '/painel',            // a tabela da varredura desceu para a ficha (fase 2)
      '/provas?aba=ciclos', // as abas viraram URL própria (fase 3)
      '/provas?aba=simulados',
      '/ciclos',            // hoje só redireciona para /provas/ciclos
      '/simulados',
    ];
    const destinos = montarTour(ANCORA).map((p) => p.destino?.para);
    for (const morto of mortos) {
      expect(destinos, morto).not.toContain(morto);
    }
  });

  it('cala o botão em vez de prometer ciclo ou prova que não existe', () => {
    // Janeiro: nenhum ciclo criado, nenhuma prova aplicada. O tour continua
    // ensinando; o que ele não faz é oferecer uma porta para o vazio.
    const tour = montarTour(ANCORA_VAZIA);
    expect(tour.map((p) => p.destino?.para ?? null)).toEqual([
      '/provas', null, null, null, null, null,
    ]);
  });

  it('mantém o hub aberto mesmo sem ciclo — ele explica a bifurcação sozinho', () => {
    expect(destinoDoPasso('bifurcacao', ANCORA_VAZIA)?.para).toBe('/provas');
  });

  it('abre a prova mesmo quando não há ciclo, e vice-versa', () => {
    // As duas âncoras são independentes: uma prova avulsa sem ciclo fechado é
    // o estado normal de quem acabou de importar a primeira planilha.
    const soProva = { ...ANCORA_VAZIA, provaId: 'S12', nomeDaProva: 'Física · P8' };
    expect(destinoDoPasso('lugar', soProva)?.para).toBe('/simulados/S12');
    expect(destinoDoPasso('varredura', soProva)).toBeNull();
  });

  it('usa um nome genérico quando o id existe e o nome não', () => {
    const semNome = { ...ANCORA, nomeDoCiclo: null, nomeDaProva: null };
    expect(destinoDoPasso('regua', semNome)?.rotulo).toBe('Abrir o ciclo');
    expect(destinoDoPasso('lugar', semNome)?.rotulo).toBe('Abrir a prova');
  });
});

describe('a chave do "já vi"', () => {
  it('separa dois coordenadores no mesmo computador', () => {
    // A sala da coordenação tem máquina compartilhada: com chave única, o
    // primeiro a fechar o tour o silencia para quem ainda nem entrou.
    expect(chaveDoTour('Marina Rocha')).not.toBe(chaveDoTour('Léo Sampaio'));
  });

  it('não cria duas chaves para a mesma pessoa', () => {
    expect(chaveDoTour('  Marina Rocha  ')).toBe(chaveDoTour('marina rocha'));
  });

  it('cai em anônimo quando a sessão ainda não tem nome', () => {
    // Sem nome o tour se comporta como se nunca tivesse sido visto — é o lado
    // seguro do erro: mostrar de novo incomoda, esconder para sempre ensina
    // nada.
    expect(chaveDoTour('')).toContain('anonimo');
    expect(chaveDoTour('   ')).toBe(chaveDoTour(''));
  });

  it('carrega a versão do conteúdo, para um tour reescrito voltar', () => {
    expect(chaveDoTour('Marina Rocha')).toMatch(/\.v\d+\./);
  });
});

function ciclo(p: Partial<Ciclo> & { id: string }): Ciclo {
  return {
    nome: `Ciclo ${p.ordem ?? 1} · ITA · 2026`, ordem: 1, anoLetivo: 2026, vestibularAlvo: 'ITA',
    periodoInicio: '2026-08-14', periodoFim: '2026-09-26', simuladoIds: [],
    canvasEstado: null, canvasErro: null,
    ...p,
  } as Ciclo;
}

function prova(p: Partial<Simulado> & { id: string }): Simulado {
  return {
    nome: `C4_P8 - Física - ${p.dataAplicacao ?? '2026-08-28'}`, rotuloCurto: 'P8',
    tipo: 'fase_1', materia: { id: 'M1', nome: 'Física' },
    dataAplicacao: '2026-08-28', cicloId: 'C4', cicloOrdem: 4, vestibularAlvo: 'ITA',
    notaMaxima: 20, anulado: false, notaConfiavel: true, motivoNotaNaoConfiavel: null,
    origem: 'canvas', canvasEstado: 'sincronizado', canvasErro: null,
    media: 4.2, mediana: 4.1, desvioPadrao: 2.4, nPresentes: 380,
    ...p,
  } as Simulado;
}

describe('em que ciclo e em que prova o tour ancora', () => {
  const HOJE = '2026-09-05';

  it('ancora no MESMO ciclo que a home mostra', () => {
    // `cicloPadrao`: o ciclo com a aplicação mais recente que já aconteceu.
    // Divergir da home aqui ensinaria a desconfiar das duas telas.
    const ciclos = [ciclo({ id: 'C3', ordem: 3 }), ciclo({ id: 'C4', ordem: 4 })];
    const provas = [
      prova({ id: 'S1', cicloId: 'C3', dataAplicacao: '2026-07-10' }),
      prova({ id: 'S2', cicloId: 'C4', dataAplicacao: '2026-08-28' }),
    ];
    const ancora = ancoraDoTour(ciclos, provas, HOJE);
    expect(ancora.cicloId).toBe('C4');
    expect(ancora.nomeDoCiclo).toBe('Ciclo 4 · ITA · 2026');
  });

  it('ancora na última prova APLICADA, e não na agendada', () => {
    // A agendada ainda não mediu nada, e o passo "O LUGAR" é sobre entender
    // uma medida que existe.
    const provas = [
      prova({ id: 'S2', dataAplicacao: '2026-08-28' }),
      prova({ id: 'S9', dataAplicacao: '2026-09-30' }),
    ];
    const ancora = ancoraDoTour([ciclo({ id: 'C4', ordem: 4 })], provas, HOJE);
    expect(ancora.provaId).toBe('S2');
    expect(ancora.nomeDaProva).toBe('Física · P8');
  });

  it('cai no nome do Canvas quando a prova não tem matéria nem rótulo', () => {
    const ancora = ancoraDoTour(
      [],
      [prova({ id: 'S2', materia: null, rotuloCurto: null, nome: 'Agregada 2026-08-28' })],
      HOJE,
    );
    expect(ancora.nomeDaProva).toBe('Agregada 2026-08-28');
  });

  it('devolve tudo nulo no colégio sem ciclo e sem prova', () => {
    expect(ancoraDoTour([], [], HOJE)).toEqual(ANCORA_VAZIA);
  });
});
