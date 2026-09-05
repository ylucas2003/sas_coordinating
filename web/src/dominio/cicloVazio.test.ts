import { describe, expect, it } from 'vitest';

import { saidasDoCicloVazio } from './cicloVazio';
import type { Ciclo } from '../tipos/dominio';

/** Um ciclo com o mínimo que as duas saídas leem. */
function ciclo(id: string, opcoes: Partial<Ciclo> = {}): Ciclo {
  return {
    id,
    nome: id,
    ordem: 1,
    anoLetivo: 2026,
    vestibularAlvo: 'ITA',
    periodoInicio: '',
    periodoFim: '',
    simuladoIds: [],
    canvasEstado: null,
    canvasErro: null,
    ...opcoes,
  };
}

describe('saidasDoCicloVazio · agendar', () => {
  it('oferece agendar no ciclo do ano letivo mais recente', () => {
    const alvo = ciclo('c-2026', { anoLetivo: 2026 });
    const { podeAgendar } = saidasDoCicloVazio(alvo, [alvo, ciclo('c-2022', { anoLetivo: 2022 })]);
    expect(podeAgendar).toBe(true);
  });

  it('NÃO oferece agendar num ciclo de ano antigo', () => {
    // É o caso real que motivou a tela: "Ciclo 1 · IME · 2022" não aparece na
    // lista do diálogo de agendamento, e o botão levaria a um formulário sem
    // ele.
    const alvo = ciclo('c-2022', { anoLetivo: 2022 });
    const { podeAgendar } = saidasDoCicloVazio(alvo, [alvo, ciclo('c-2026', { anoLetivo: 2026 })]);
    expect(podeAgendar).toBe(false);
  });

  it('sem a lista, assume que o próprio ciclo é o ano corrente', () => {
    // O palpite é deliberado: errar oferecendo mostra um formulário incompleto,
    // errar escondendo tira a saída de quem está no ciclo do ano em curso.
    const alvo = ciclo('c-2026', { anoLetivo: 2026 });
    expect(saidasDoCicloVazio(alvo, []).podeAgendar).toBe(true);
  });

  it('ignora ano letivo nulo dos outros ao procurar o mais recente', () => {
    const alvo = ciclo('c-2026', { anoLetivo: 2026 });
    const sujo = ciclo('c-sem-ano', { anoLetivo: null as unknown as number });
    expect(saidasDoCicloVazio(alvo, [alvo, sujo]).podeAgendar).toBe(true);
  });
});

describe('saidasDoCicloVazio · vizinho', () => {
  const comProvaIta = ciclo('ita-cheio', { vestibularAlvo: 'ITA', simuladoIds: ['s1'] });
  const comProvaIme = ciclo('ime-cheio', { vestibularAlvo: 'IME', simuladoIds: ['s2'] });

  it('prefere um ciclo do MESMO vestibular', () => {
    // ITA e IME correm em paralelo: mandar quem olhava o IME para um ciclo do
    // ITA troca o assunto sem avisar.
    const alvo = ciclo('ime-vazio', { vestibularAlvo: 'IME' });
    const { vizinho } = saidasDoCicloVazio(alvo, [alvo, comProvaIta, comProvaIme]);
    expect(vizinho?.id).toBe('ime-cheio');
  });

  it('aceita outro vestibular quando não há do mesmo', () => {
    const alvo = ciclo('ime-vazio', { vestibularAlvo: 'IME' });
    const { vizinho } = saidasDoCicloVazio(alvo, [alvo, comProvaIta]);
    expect(vizinho?.id).toBe('ita-cheio');
  });

  it('nunca aponta para outro ciclo vazio', () => {
    const alvo = ciclo('a', { vestibularAlvo: 'ITA' });
    const outroVazio = ciclo('b', { vestibularAlvo: 'ITA' });
    expect(saidasDoCicloVazio(alvo, [alvo, outroVazio]).vizinho).toBeNull();
  });

  it('nunca aponta para si mesmo, nem quando tem simulados na lista', () => {
    // A tela vazia é decidida por `doCiclo`, não por `simuladoIds`: um ciclo
    // com id de simulado que não voltou na consulta chega aqui, e um elo
    // "Ver este mesmo ciclo" seria um elo que não vai a lugar nenhum.
    const alvo = ciclo('a', { simuladoIds: ['s1'] });
    expect(saidasDoCicloVazio(alvo, [alvo]).vizinho).toBeNull();
  });

  it('devolve null com a lista vazia', () => {
    expect(saidasDoCicloVazio(ciclo('a'), []).vizinho).toBeNull();
  });
});
