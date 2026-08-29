import { describe, expect, it } from 'vitest';

import {
  FILTRO_GRAVACOES_VAZIO,
  algumEmAndamento,
  aplicarFiltros,
  contarPorChip,
  esperaCanvas,
  foraDeModulo,
  formatarDuracao,
  ordenarParaAcompanhamento,
  partesDaData,
  situacaoDe,
  tituloParaCartao,
} from './gravacoes';
import type { GravacaoAula, StatusGravacao } from '../tipos/dominio';

function aula(p: Partial<GravacaoAula> & { id: string }): GravacaoAula {
  return {
    cursoId: '692',
    conferenciaId: 1,
    titulo: 'Física - Prof. Renan - AULA 5',
    iniciadaEm: '2026-08-20T20:30:00+00:00',
    duracaoMinutos: 93,
    status: 'publicado',
    tentativas: 0,
    youtubeVideoId: 'abc123',
    youtubeTitulo: 'SAS ITA/IME 2026 - Turma 1 e 2 - Prof Renan - Aula 5 (20/08/2026)',
    youtubeUrl: 'https://youtu.be/abc123',
    erroDetalhe: null,
    canvasEstado: 'pendente',
    canvasUrl: null,
    canvasModulo: null,
    canvasErro: null,
    atualizadoEm: '2026-08-20T22:00:00+00:00',
    ...p,
  } as GravacaoAula;
}

describe('situacaoDe', () => {
  // Os dez status do backend cabem em cinco degraus — é o contrato que o
  // resto da tela consome.
  const esperado: Array<[StatusGravacao, string]> = [
    ['aguardando_gravacao', 'aguardando'],
    ['pendente', 'na_fila'],
    ['baixando', 'processando'],
    ['baixado', 'processando'],
    ['compondo', 'processando'],
    ['composto', 'processando'],
    ['publicando', 'processando'],
    ['publicado', 'publicado'],
    ['publicado_sem_confirmacao', 'publicado'],
    ['erro', 'erro'],
  ];

  it.each(esperado)('%s → %s', (status, situacao) => {
    expect(situacaoDe(aula({ id: 'a', status }))).toBe(situacao);
  });

  it('publicado_sem_confirmacao conta como sucesso, não como pendência', () => {
    // O estado é TERMINAL no backend: reprocessar geraria segunda cópia do
    // vídeo de um menor no canal. A tela não pode sugerir o contrário.
    const a = aula({ id: 'a', status: 'publicado_sem_confirmacao' });
    expect(situacaoDe(a)).toBe('publicado');
    expect(algumEmAndamento([a])).toBe(false);
  });
});

describe('algumEmAndamento', () => {
  it('liga com aula na fila ou processando', () => {
    expect(algumEmAndamento([aula({ id: 'a', status: 'pendente' })])).toBe(true);
    expect(algumEmAndamento([aula({ id: 'a', status: 'compondo' })])).toBe(true);
  });

  it('NÃO liga por aula só aguardando gravação', () => {
    // Depende do BigBlueButton terminar de processar — leva horas. Recarregar
    // de 30 em 30 s não descobriria nada e manteria a aba consumindo rede.
    expect(algumEmAndamento([aula({ id: 'a', status: 'aguardando_gravacao' })])).toBe(false);
  });

  it('não liga com tudo terminal', () => {
    expect(
      algumEmAndamento([
        aula({ id: 'a', status: 'publicado' }),
        aula({ id: 'b', status: 'erro' }),
        aula({ id: 'c', status: 'aguardando_gravacao' }),
      ]),
    ).toBe(false);
  });

  it('lista vazia não liga o polling', () => {
    expect(algumEmAndamento([])).toBe(false);
  });
});

describe('esperaCanvas', () => {
  it('só cobra o Canvas de aula que já tem vídeo', () => {
    expect(esperaCanvas(aula({ id: 'a', status: 'publicado' }))).toBe(true);
    expect(esperaCanvas(aula({ id: 'b', status: 'compondo' }))).toBe(false);
    expect(esperaCanvas(aula({ id: 'c', status: 'erro' }))).toBe(false);
  });
});

describe('aplicarFiltros', () => {
  const dados = [
    aula({ id: 'a', cursoId: '692', status: 'publicado' }),
    aula({ id: 'b', cursoId: '691', status: 'publicado' }),
    aula({ id: 'c', cursoId: '692', status: 'erro' }),
  ];

  it('conjunto vazio significa "sem filtro", não "nada"', () => {
    expect(aplicarFiltros(dados, FILTRO_GRAVACOES_VAZIO)).toHaveLength(3);
  });

  it('combina curso e situação', () => {
    const r = aplicarFiltros(dados, {
      cursos: new Set(['692']),
      situacoes: new Set(['publicado']),
    });
    expect(r.map((a) => a.id)).toEqual(['a']);
  });

  it('não muta a entrada', () => {
    const antes = [...dados];
    aplicarFiltros(dados, { cursos: new Set(['692']), situacoes: new Set() });
    expect(dados).toEqual(antes);
  });
});

describe('contarPorChip', () => {
  const dados = [
    aula({ id: 'a', cursoId: '692', status: 'publicado' }),
    aula({ id: 'b', cursoId: '691', status: 'publicado' }),
    aula({ id: 'c', cursoId: '692', status: 'erro' }),
  ];

  it('cada eixo conta ignorando o próprio filtro', () => {
    // Com o curso 692 marcado, a contagem POR CURSO tem que continuar
    // mostrando o 691 — senão a pílula some e o coordenador fica preso.
    const { curso, situacao } = contarPorChip(dados, {
      cursos: new Set(['692']),
      situacoes: new Set(),
    });
    expect(curso.get('691')).toBe(1);
    expect(curso.get('692')).toBe(2);
    // A situação, essa sim, respeita o filtro de curso.
    expect(situacao.get('publicado')).toBe(1);
    expect(situacao.get('erro')).toBe(1);
  });
});

describe('ordenarParaAcompanhamento', () => {
  it('aula ainda sem data vem primeiro, e o resto do mais novo ao mais velho', () => {
    // `iniciadaEm` nulo é conferência agendada que ainda não começou — é
    // justamente "a que vai ser processada", o topo da tela.
    const r = ordenarParaAcompanhamento([
      aula({ id: 'velha', iniciadaEm: '2026-08-01T20:00:00+00:00' }),
      aula({ id: 'futura', iniciadaEm: null }),
      aula({ id: 'nova', iniciadaEm: '2026-08-27T20:00:00+00:00' }),
    ]);
    expect(r.map((a) => a.id)).toEqual(['futura', 'nova', 'velha']);
  });
});

describe('formatarDuracao', () => {
  it('passa de uma hora vira 1h33', () => {
    expect(formatarDuracao(93)).toBe('1h33');
  });

  it('abaixo de uma hora fica em minutos', () => {
    expect(formatarDuracao(47)).toBe('47 min');
  });

  it('nulo não vira "0 min"', () => {
    // Duração desconhecida (aula ainda não gravada) não pode virar zero: o
    // coordenador leria como aula vazia.
    expect(formatarDuracao(null)).toBe('—');
  });
});

describe('tituloParaCartao', () => {
  // Os quatro formatos reais dos cursos monitorados, copiados da API do Canvas.
  const casos: Array<[string, string]> = [
    [
      'SAS ITA/IME 2026 - Turma 1 e 2 - Redação - Prof Camila Oliveira - 09:00 (29/08/2026)',
      'Redação · Prof Camila Oliveira',
    ],
    ['Física - Prof. Renan - AULA 7 - 17:30 (27/08/2026)', 'Física · Prof. Renan · AULA 7'],
    [
      'Química - AULA 19 - 26/08/2026 - Prof. José Marques - 17:30',
      'Química · AULA 19 · Prof. José Marques',
    ],
    [
      'Aula 08 - 25/08/2026 - Complexos: Forma Trigonométrica (pt3)',
      'Aula 08 · Complexos: Forma Trigonométrica (pt3)',
    ],
  ];

  it.each(casos)('%s', (bruto, esperado) => {
    expect(tituloParaCartao(bruto)).toBe(esperado);
  });

  it('preserva hífen sem espaços — "Tira-dúvidas" não é dois segmentos', () => {
    expect(tituloParaCartao('Tira-dúvidas - Física - Renan - 27/08/26')).toBe(
      'Tira-dúvidas · Física · Renan',
    );
  });

  it('não devolve vazio quando tudo é descartável', () => {
    // Um card sem título é pior que um card com título feio.
    expect(tituloParaCartao('SAS ITA/IME 2026 - Turma 1 e 2 - 17:30 (29/08/2026)')).toBe(
      'SAS ITA/IME 2026 - Turma 1 e 2 - 17:30 (29/08/2026)',
    );
  });

  it('não inventa nem reordena: só remove', () => {
    // Salvaguarda contra a tentação de "melhorar" o título — o que o professor
    // escreveu e não é redundante tem que aparecer inteiro e na mesma ordem.
    const r = tituloParaCartao('Aula 12 - Cinemática: lançamento oblíquo - Prof. Ryan');
    expect(r).toBe('Aula 12 · Cinemática: lançamento oblíquo · Prof. Ryan');
  });
});

describe('partesDaData', () => {
  it('quebra a data para a tarja do card', () => {
    expect(partesDaData('2026-08-27T20:23:00+00:00')).toEqual({
      dia: '27',
      mes: 'AGO',
      ano: '2026',
    });
  });

  it('nulo não vira data de hoje', () => {
    expect(partesDaData(null)).toBeNull();
  });
});

describe('foraDeModulo', () => {
  it('página publicada sem módulo é pendência visível', () => {
    // Criar a página no Canvas não a põe em módulo — são duas chamadas de API.
    // Foi assim que as quatro primeiras nasceram: publicadas e invisíveis.
    expect(
      foraDeModulo(aula({ id: 'a', canvasEstado: 'publicado', canvasModulo: null })),
    ).toBe(true);
  });

  it('com módulo, está resolvida', () => {
    expect(
      foraDeModulo(aula({ id: 'a', canvasEstado: 'publicado', canvasModulo: 'Aulas - Física 2' })),
    ).toBe(false);
  });

  it('aula que ainda nem tem página não é "fora de módulo"', () => {
    expect(foraDeModulo(aula({ id: 'a', canvasEstado: 'pendente', canvasModulo: null }))).toBe(false);
  });
});
