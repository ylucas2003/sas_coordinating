import { describe, expect, it } from 'vitest';
import { ordenarLinhas, proximaOrdenacao } from './ordenacao';
import type { ColunaTabela } from './ordenacao';

interface Linha {
  nome: string;
  media: number | null;
  zona: string;
}

const COLUNAS: Array<ColunaTabela<Linha>> = [
  { chave: 'nome', label: 'Nome', valor: (l) => l.nome },
  { chave: 'media', label: 'Média', valor: (l) => l.media, tipo: 'numero' },
  {
    chave: 'zona', label: 'Zona', valor: (l) => l.zona,
    tipo: 'ordinal', ordem: ['risco', 'cinzenta', 'top'],
  },
  { chave: 'acao', label: '', ordenavel: false },
];

const nomes = (ls: Linha[]) => ls.map((l) => l.nome);

describe('ordenarLinhas', () => {
  const dados: Linha[] = [
    { nome: 'Bruno', media: 7.5, zona: 'top' },
    { nome: 'Ana', media: null, zona: 'risco' },
    { nome: 'Caio', media: 4.2, zona: 'cinzenta' },
  ];

  it('devolve a ordem original sem ordenação ativa', () => {
    expect(nomes(ordenarLinhas(dados, COLUNAS, null))).toEqual(['Bruno', 'Ana', 'Caio']);
  });

  it('não muta a lista recebida', () => {
    const copia = [...dados];
    ordenarLinhas(dados, COLUNAS, { chave: 'nome', dir: 'asc' });
    expect(dados).toEqual(copia);
  });

  it('ordena texto respeitando acento e caixa do pt-BR', () => {
    const comAcento: Linha[] = [
      { nome: 'Zulmira', media: 1, zona: 'top' },
      { nome: 'Ávila', media: 1, zona: 'top' },
      { nome: 'Bruno', media: 1, zona: 'top' },
    ];
    expect(nomes(ordenarLinhas(comAcento, COLUNAS, { chave: 'nome', dir: 'asc' })))
      .toEqual(['Ávila', 'Bruno', 'Zulmira']);
  });

  // A regra que motiva o módulo existir: aluno sem média não encabeça o "pior
  // desempenho" — ele não foi mal, ele não tem dado.
  it('afunda nulos nos DOIS sentidos', () => {
    expect(nomes(ordenarLinhas(dados, COLUNAS, { chave: 'media', dir: 'asc' })))
      .toEqual(['Caio', 'Bruno', 'Ana']);
    expect(nomes(ordenarLinhas(dados, COLUNAS, { chave: 'media', dir: 'desc' })))
      .toEqual(['Bruno', 'Caio', 'Ana']);
  });

  it('usa a ordem semântica em coluna ordinal, não a alfabética', () => {
    // Alfabético seria Cinzenta → Risco → Top; o semântico é Risco → Cinzenta → Top.
    expect(nomes(ordenarLinhas(dados, COLUNAS, { chave: 'zona', dir: 'asc' })))
      .toEqual(['Ana', 'Caio', 'Bruno']);
  });

  it('ignora ordenação pedida em coluna não ordenável', () => {
    expect(nomes(ordenarLinhas(dados, COLUNAS, { chave: 'acao', dir: 'asc' })))
      .toEqual(['Bruno', 'Ana', 'Caio']);
  });

  it('ignora chave inexistente', () => {
    expect(nomes(ordenarLinhas(dados, COLUNAS, { chave: 'inexistente', dir: 'asc' })))
      .toEqual(['Bruno', 'Ana', 'Caio']);
  });
});

describe('proximaOrdenacao', () => {
  it('começa em asc numa coluna nova', () => {
    expect(proximaOrdenacao(null, 'nome')).toEqual({ chave: 'nome', dir: 'asc' });
    expect(proximaOrdenacao({ chave: 'media', dir: 'desc' }, 'nome'))
      .toEqual({ chave: 'nome', dir: 'asc' });
  });

  it('alterna asc → desc → asc na mesma coluna', () => {
    const a = proximaOrdenacao(null, 'nome');
    const b = proximaOrdenacao(a, 'nome');
    expect(b).toEqual({ chave: 'nome', dir: 'desc' });
    expect(proximaOrdenacao(b, 'nome')).toEqual({ chave: 'nome', dir: 'asc' });
  });
});
