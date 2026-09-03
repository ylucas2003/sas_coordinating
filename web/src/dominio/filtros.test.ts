import { describe, expect, it } from 'vitest';
import {
  resumirFiltros, resumirPeriodo, resumirSelecao, resumirTexto, resumirUnica,
} from './filtros';

const SEDES = [
  { valor: 's1', label: 'Aldeota' },
  { valor: 's2', label: 'Sobral' },
  { valor: 's3', label: 'Eusébio' },
];

describe('resumirSelecao', () => {
  it('nada selecionado não vira resumo', () => {
    expect(resumirSelecao(new Set(), SEDES, 'sede', 'sedes')).toBeNull();
  });

  it('um item mostra o rótulo, que diz mais que a contagem', () => {
    expect(resumirSelecao(new Set(['s2']), SEDES, 'sede', 'sedes')).toBe('Sobral');
  });

  it('dois ou mais viram contagem — a lista é o que não cabia na linha', () => {
    expect(resumirSelecao(new Set(['s1', 's2']), SEDES, 'sede', 'sedes')).toBe('2 sedes');
  });

  // O caso que o Painel criou: ano e vestibular nascem com tudo marcado.
  it('tudo marcado não é recorte, e não entra no resumo', () => {
    expect(resumirSelecao(new Set(['s1', 's2', 's3']), SEDES, 'sede', 'sedes')).toBeNull();
  });

  it('sem lista de opções, não há como saber se é "tudo" — conta mesmo assim', () => {
    expect(resumirSelecao(new Set(['x']), [], 'sede', 'sedes')).toBe('1 sede');
  });
});

describe('resumirUnica', () => {
  it('devolve o rótulo do selecionado', () => {
    expect(resumirUnica('s2', SEDES)).toBe('Sobral');
  });

  it('nada selecionado, nada a dizer', () => {
    expect(resumirUnica(null, SEDES)).toBeNull();
  });

  it('valor que não está nas opções não inventa rótulo', () => {
    expect(resumirUnica('zzz', SEDES)).toBeNull();
  });
});

describe('resumirTexto', () => {
  it('põe entre aspas para não virar rótulo de grupo', () => {
    expect(resumirTexto('  ana  ')).toBe('“ana”');
  });

  it('espaço em branco é vazio', () => {
    expect(resumirTexto('   ')).toBeNull();
  });
});

describe('resumirPeriodo', () => {
  it('os dois extremos', () => {
    expect(resumirPeriodo('2026-03-01', '2026-04-30')).toBe('2026-03-01 → 2026-04-30');
  });

  it('extremo aberto de cada lado', () => {
    expect(resumirPeriodo('2026-03-01', null)).toBe('desde 2026-03-01');
    expect(resumirPeriodo(null, '2026-04-30')).toBe('até 2026-04-30');
  });

  it('sem período, sem resumo', () => {
    expect(resumirPeriodo(null, null)).toBeNull();
  });

  it('aceita formatador', () => {
    expect(resumirPeriodo('2026-03-01', '2026-04-30', (i) => i.slice(8)))
      .toBe('01 → 30');
  });
});

describe('resumirFiltros', () => {
  it('junta na ordem dos grupos, pulando os inativos', () => {
    expect(resumirFiltros([
      { chave: 'ciclo', resumo: 'Ciclo 4' },
      { chave: 'sede', resumo: null },
      { chave: 'turma', resumo: '2 turmas' },
    ])).toBe('Ciclo 4 · 2 turmas');
  });

  it('nada ativo devolve vazio — quem chama decide o que dizer', () => {
    expect(resumirFiltros([{ chave: 'a' }, { chave: 'b', resumo: null }])).toBe('');
  });

  it('resumo só de espaços não conta como ativo', () => {
    expect(resumirFiltros([{ chave: 'a', resumo: '   ' }])).toBe('');
  });
});
