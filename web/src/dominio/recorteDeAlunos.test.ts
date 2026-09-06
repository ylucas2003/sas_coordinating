import { describe, expect, it } from 'vitest';

import {
  aplicarRecorte,
  contarRecortes,
  contarRiscoCaindo,
  extremosPorMedia,
  lerRecorte,
  mediaDasMedias,
  mediaDoAno,
  semNotaNoUltimoCiclo,
} from './recorteDeAlunos';
import type { Aluno, MediaDoGrupo } from '../tipos/dominio';

function grupo(geral: number | null): MediaDoGrupo {
  return { referencia: '2026', geral, matematica: geral, fisica: geral, quimica: geral };
}

/** Um aluno com o mínimo que os recortes leem. */
function aluno(id: string, opcoes: Partial<Aluno> = {}): Aluno {
  return {
    id,
    nome: id,
    turmaId: 't1',
    sedeId: 's1',
    vestibularesAlvo: ['ITA'],
    ativo: true,
    email: null,
    perfil: 'regular',
    tendencia: 'estavel',
    zona: 'cinzenta',
    media: null,
    sparkline: [],
    temFoto: false,
    ...opcoes,
  };
}

/** Com média do ano `m` e nota no último ciclo. */
function comMedia(id: string, m: number, opcoes: Partial<Aluno> = {}): Aluno {
  return aluno(id, {
    medias: { ano: grupo(m), primeiroCiclo: grupo(m), ultimoCiclo: grupo(m) },
    ...opcoes,
  });
}

describe('lerRecorte', () => {
  it('aceita os quatro recortes', () => {
    expect(lerRecorte('risco')).toBe('risco');
    expect(lerRecorte('bottom')).toBe('bottom');
  });

  it('valor desconhecido não recorta nada — URL velha não pode esvaziar a lista', () => {
    expect(lerRecorte('top10')).toBeNull();
    expect(lerRecorte(null)).toBeNull();
    expect(lerRecorte('')).toBeNull();
  });
});

describe('mediaDoAno', () => {
  it('lê a média do ano que o servidor mandou', () => {
    expect(mediaDoAno(comMedia('a', 7.2))).toBe(7.2);
  });

  it('sem `medias` é NULO, e não a média recente — são réguas diferentes', () => {
    expect(mediaDoAno(aluno('a', { media: 6.4 }))).toBeNull();
  });
});

describe('semNotaNoUltimoCiclo', () => {
  it('estrutura presente com geral nulo é silêncio', () => {
    const a = aluno('a', {
      medias: { ano: grupo(5), primeiroCiclo: grupo(5), ultimoCiclo: grupo(null) },
    });
    expect(semNotaNoUltimoCiclo(a)).toBe(true);
  });

  it('quem tem nota no último ciclo não é silêncio', () => {
    expect(semNotaNoUltimoCiclo(comMedia('a', 3.1))).toBe(false);
  });

  it('sem `medias` é desconhecimento, não ausência', () => {
    expect(semNotaNoUltimoCiclo(aluno('a'))).toBe(false);
  });
});

describe('extremosPorMedia', () => {
  const lista = [
    comMedia('a', 9.0),
    comMedia('b', 8.0),
    comMedia('c', 7.0),
    comMedia('d', 2.0),
    comMedia('e', 1.0),
  ];

  it('os dois extremos são disjuntos — metade do acervo, no máximo', () => {
    const ext = extremosPorMedia(lista);
    expect(ext.n).toBe(2);
    expect([...ext.top]).toEqual(['a', 'b']);
    expect([...ext.baixo]).toEqual(['d', 'e']);
    // O do meio não é extremo de nada.
    expect(ext.top.has('c')).toBe(false);
    expect(ext.baixo.has('c')).toBe(false);
  });

  it('o teto limita o N num acervo grande', () => {
    const muitos = Array.from({ length: 200 }, (_, i) => comMedia(`a${i}`, i / 20));
    expect(extremosPorMedia(muitos).n).toBe(30);
    expect(extremosPorMedia(muitos, 5).n).toBe(5);
  });

  it('quem não tem média fica fora dos dois extremos', () => {
    const ext = extremosPorMedia([...lista, aluno('z')]);
    expect(ext.top.has('z')).toBe(false);
    expect(ext.baixo.has('z')).toBe(false);
  });

  it('sem ninguém medido o N é zero — não existe "top 1" de lista vazia', () => {
    const ext = extremosPorMedia([aluno('z'), aluno('y')]);
    expect(ext.n).toBe(0);
    expect(ext.top.size).toBe(0);
    expect(ext.baixo.size).toBe(0);
  });

  it('com um único aluno medido ninguém é extremo — ele seria o melhor E o pior', () => {
    expect(extremosPorMedia([comMedia('a', 5)]).n).toBe(0);
  });
});

describe('aplicarRecorte', () => {
  const lista = [
    comMedia('risco1', 2.0, { zona: 'risco', tendencia: 'caindo' }),
    comMedia('risco2', 3.0, { zona: 'risco' }),
    comMedia('meio', 5.0),
    comMedia('alto', 9.0, { zona: 'top' }),
    aluno('novo', {
      medias: { ano: grupo(null), primeiroCiclo: grupo(null), ultimoCiclo: grupo(null) },
    }),
  ];

  it('sem recorte a lista passa inteira', () => {
    expect(aplicarRecorte(lista, null, extremosPorMedia(lista))).toHaveLength(5);
  });

  it('risco lê a zona que o servidor classificou', () => {
    const r = aplicarRecorte(lista, 'risco', extremosPorMedia(lista));
    expect(r.map((a) => a.id)).toEqual(['risco1', 'risco2']);
  });

  it('sem nota separa quem não foi medido de quem foi mal', () => {
    const r = aplicarRecorte(lista, 'sem-nota', extremosPorMedia(lista));
    expect(r.map((a) => a.id)).toEqual(['novo']);
  });

  it('os extremos preservam a ordem original da lista, não a do ranking', () => {
    const ext = extremosPorMedia(lista);
    expect(aplicarRecorte(lista, 'bottom', ext).map((a) => a.id)).toEqual(['risco1', 'risco2']);
    expect(aplicarRecorte(lista, 'top', ext).map((a) => a.id)).toEqual(['meio', 'alto']);
  });
});

describe('contagens dos cards', () => {
  const lista = [
    comMedia('a', 2.0, { zona: 'risco', tendencia: 'caindo' }),
    comMedia('b', 3.0, { zona: 'risco', tendencia: 'estavel' }),
    comMedia('c', 8.0),
    comMedia('d', 9.0),
    aluno('e', {
      medias: { ano: grupo(null), primeiroCiclo: grupo(null), ultimoCiclo: grupo(null) },
    }),
  ];

  it('cada card conta o que ele mesmo entregaria', () => {
    const ext = extremosPorMedia(lista);
    const contagens = contarRecortes(lista, ext);
    for (const recorte of ['risco', 'sem-nota', 'top', 'bottom'] as const) {
      expect(contagens[recorte]).toBe(aplicarRecorte(lista, recorte, ext).length);
    }
  });

  it('caindo é a interseção do risco, não uma segunda população', () => {
    expect(contarRiscoCaindo(lista)).toBe(1);
  });

  it('a média das médias ignora quem não tem média', () => {
    expect(mediaDasMedias(lista)).toBeCloseTo(5.5, 5);
    expect(mediaDasMedias([aluno('z')])).toBeNull();
  });
});
