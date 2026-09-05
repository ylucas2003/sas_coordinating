import { describe, expect, it } from 'vitest';

import {
  desserializarRecorte, montarRevisao, serializarRecorte,
} from './revisaoEmSequencia';
import type { RecorteDeRevisao } from './revisaoEmSequencia';

const RECORTE: RecorteDeRevisao = {
  ids: ['A001', 'A002', 'A003'],
  rotulo: 'zona de risco, pior primeiro',
  volta: '/alunos?filtro=risco',
};

describe('montarRevisao', () => {
  it('conta a posição em linguagem de gente, base 1', () => {
    expect(montarRevisao(RECORTE, 'A002')?.posicao).toBe('aluno 2 de 3');
  });

  it('dá os dois vizinhos no meio da fila', () => {
    const r = montarRevisao(RECORTE, 'A002');
    expect(r?.anterior).toBe('A001');
    expect(r?.proximo).toBe('A003');
  });

  it('não dá a volta no fim da fila — terminar é uma informação', () => {
    expect(montarRevisao(RECORTE, 'A001')?.anterior).toBeNull();
    expect(montarRevisao(RECORTE, 'A003')?.proximo).toBeNull();
  });

  it('some inteira para quem não está no recorte', () => {
    // O caso normal: ficha alcançada pela busca da topbar ou por link salvo.
    expect(montarRevisao(RECORTE, 'A999')).toBeNull();
    expect(montarRevisao(null, 'A001')).toBeNull();
    expect(montarRevisao(RECORTE, '')).toBeNull();
  });

  it('atravessa o recorte de um só sem inventar vizinho', () => {
    const um = montarRevisao({ ...RECORTE, ids: ['A007'] }, 'A007');
    expect(um?.posicao).toBe('aluno 1 de 1');
    expect(um?.anterior).toBeNull();
    expect(um?.proximo).toBeNull();
  });
});

describe('desserializarRecorte', () => {
  it('faz a volta completa do que a lista gravou', () => {
    const voltou = desserializarRecorte(serializarRecorte({ ...RECORTE, ultimoVisto: 'A002' }));
    expect(voltou).toEqual({ ...RECORTE, ultimoVisto: 'A002' });
  });

  it('recusa o que não é recorte, em vez de entregar meio', () => {
    expect(desserializarRecorte(null)).toBeNull();
    expect(desserializarRecorte('')).toBeNull();
    expect(desserializarRecorte('{ não é json')).toBeNull();
    expect(desserializarRecorte('"texto"')).toBeNull();
    expect(desserializarRecorte('[]')).toBeNull();
    expect(desserializarRecorte(JSON.stringify({ ...RECORTE, ids: [] }))).toBeNull();
    expect(desserializarRecorte(JSON.stringify({ ...RECORTE, ids: ['A1', 7] }))).toBeNull();
    expect(desserializarRecorte(JSON.stringify({ ...RECORTE, rotulo: '' }))).toBeNull();
  });

  it('recusa volta que sai do produto', () => {
    // O valor vem do `sessionStorage` e alimenta um `navigate`: caminho
    // externo aqui viraria redirecionamento no clique de voltar.
    expect(desserializarRecorte(JSON.stringify({ ...RECORTE, volta: 'https://exemplo.com' }))).toBeNull();
    expect(desserializarRecorte(JSON.stringify({ ...RECORTE, volta: '//exemplo.com' }))).toBeNull();
    expect(desserializarRecorte(JSON.stringify({ ...RECORTE, volta: 'alunos' }))).toBeNull();
  });

  it('deixa o último visto de fora quando ele não é id', () => {
    const voltou = desserializarRecorte(JSON.stringify({ ...RECORTE, ultimoVisto: 42 }));
    expect(voltou).toEqual(RECORTE);
    expect(voltou?.ultimoVisto).toBeUndefined();
  });
});
