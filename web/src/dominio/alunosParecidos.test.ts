import { describe, expect, it } from 'vitest';

import { descreverSemelhanca } from './alunosParecidos';
import type { TracoDoAluno } from './alunosParecidos';

const ALVO: TracoDoAluno = { perfil: 'regular', tendencia: 'caindo', zona: 'risco', media: 3.8 };

describe('descreverSemelhanca', () => {
  it('diz o que os dois têm em comum, em português', () => {
    const frase = descreverSemelhanca(ALVO, { ...ALVO, media: 4.1 });
    expect(frase).toBe('mesma zona · a nota anda no mesmo sentido · média 0,3 acima');
  });

  it('para em dois traços — a linha tem de terminar de ser lida', () => {
    const frase = descreverSemelhanca(ALVO, { ...ALVO, media: 3.8 });
    expect(frase).not.toContain('oscila do mesmo jeito');
    expect(frase).toBe('mesma zona · a nota anda no mesmo sentido · mesma média');
  });

  it('marca o lado da diferença de média', () => {
    const frase = descreverSemelhanca(
      { ...ALVO, zona: null, tendencia: null, perfil: null },
      { perfil: null, tendencia: null, zona: null, media: 3.4 },
    );
    expect(frase).toBe('média 0,4 abaixo');
  });

  it('cala a boca quando não há nada em comum a afirmar', () => {
    // Sem traço igual e sem as duas médias não há semelhança que se possa
    // dizer — e a linha some, em vez de ganhar uma frase de enchimento.
    const frase = descreverSemelhanca(
      { perfil: null, tendencia: null, zona: null, media: null },
      { perfil: 'ancora', tendencia: 'subindo', zona: 'top', media: null },
    );
    expect(frase).toBe('');
  });

  it('não conta como traço em comum o campo que os dois não têm', () => {
    const frase = descreverSemelhanca(
      { perfil: null, tendencia: null, zona: null, media: 5 },
      { perfil: null, tendencia: null, zona: null, media: 5 },
    );
    expect(frase).toBe('mesma média');
  });
});
