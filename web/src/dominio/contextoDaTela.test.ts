import { describe, expect, it } from 'vitest';

import { derivarContexto } from './contextoDaTela';

describe('derivarContexto', () => {
  it('rota de listagem não abre entidade nenhuma', () => {
    expect(derivarContexto('/alunos')).toEqual({ tela: 'alunos', caminho: '/alunos' });
    expect(derivarContexto('/painel')).toEqual({ tela: 'painel', caminho: '/painel' });
  });

  it('rota de ficha abre a entidade, com o nome que a tela declarou', () => {
    expect(derivarContexto('/alunos/A023', 'Ana Souza')).toEqual({
      tela: 'alunos',
      caminho: '/alunos/A023',
      entidade: { tipo: 'aluno', id: 'A023', nome: 'Ana Souza' },
    });
  });

  it('sem título ainda carregado, a entidade vai só com o id', () => {
    const ctx = derivarContexto('/ciclos/C6');
    expect(ctx.entidade).toEqual({ tipo: 'ciclo', id: 'C6' });
  });

  it('ciclo e simulado caem na mesma tela, com entidades diferentes', () => {
    expect(derivarContexto('/ciclos/C6').tela).toBe('provas');
    expect(derivarContexto('/simulados/S9').tela).toBe('provas');
    expect(derivarContexto('/simulados/S9').entidade?.tipo).toBe('simulado');
  });

  it('rota desconhecida não inventa tela — usa a raiz como está', () => {
    expect(derivarContexto('/coisa-nova').tela).toBe('coisa-nova');
  });

  it('a raiz do ALUNO não vira "painel"', () => {
    // A home do aluno é `/`, e a folha do Tio Léo usa a mesma `Conversa` da
    // coordenação. Com o default antigo (`?? 'painel'`), o mentor de um menor
    // recebia "Tela aberta: Painel — a lista de alunos do ciclo, ordenada pela
    // régua de corte". A coordenação não perde nada: `/` redireciona para
    // `/painel` antes de qualquer render de chat.
    expect(derivarContexto('/').tela).toBe('');
    expect(derivarContexto('/').entidade).toBeUndefined();
  });

  it('recorte vazio não vira campo', () => {
    expect(derivarContexto('/painel', null, { sedeIds: [], turmaIds: [] }).recorte)
      .toBeUndefined();
  });

  it('recorte declarado pela tela entra limpo', () => {
    const ctx = derivarContexto('/painel', null, {
      cicloId: 'C6', fase: 2, criterio: 'ita-f2', sedeIds: ['S1'], turmaIds: [],
    });
    expect(ctx.recorte).toEqual({
      cicloId: 'C6', fase: 2, criterio: 'ita-f2', sedeIds: ['S1'],
    });
  });
});
