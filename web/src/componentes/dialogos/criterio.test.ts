import { describe, expect, it } from 'vitest';

import { slugDoNome } from './EdicaoCriterio';

/**
 * O slug é a chave da régua no banco, e o coordenador nunca o digita: ele sai
 * do nome. Por isso o teste — uma chave gerada errada é uma régua que não dá
 * para criar, com uma mensagem de erro que fala de algo que o usuário nem viu.
 */
describe('slugDoNome', () => {
  it('tira acento, baixa a caixa e hifeniza', () => {
    expect(slugDoNome('Meta 7 nas exatas')).toBe('meta-7-nas-exatas');
    expect(slugDoNome('Régua de Física')).toBe('regua-de-fisica');
  });

  it('não deixa hífen sobrando nas pontas nem repetido', () => {
    expect(slugDoNome('  Meta — 7  ')).toBe('meta-7');
    expect(slugDoNome('!!!')).toBe('');
  });

  it('trunca antes do limite da coluna', () => {
    expect(slugDoNome('a'.repeat(200)).length).toBe(60);
  });

  it('o que ele gera é aceito pela validação do servidor', () => {
    // Mesmo padrão de `criterios_repo._RE_SLUG`.
    const aceito = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
    for (const nome of ['Meta 7 nas exatas', 'Régua do Léo', 'ITA 2026 — turma A']) {
      expect(slugDoNome(nome)).toMatch(aceito);
    }
  });
});
