import { describe, expect, it } from 'vitest';

import { parsear } from './eventos';

// O parser de SSE, e os três casos que separam um stream longo de um curto.

describe('parser de eventos', () => {
  it('lê o nome e os dados', () => {
    const e = parsear('event: cardapio\ndata: {"cantina_id":"c1","refeicao":"almoco"}');
    expect(e).toEqual({ nome: 'cardapio', dados: { cantina_id: 'c1', refeicao: 'almoco' } });
  });

  it('IGNORA o comentário de heartbeat', () => {
    // ⚠️ O caso que mais importa. O servidor manda `: ping` a cada 25 s porque o
    // nginx corta conexão silenciosa em 300 s. Tratar isso como evento
    // dispararia um refetch por minuto, para sempre — e ninguém notaria, porque
    // a tela ficaria "só" um pouco mais lenta.
    expect(parsear(': ping')).toBeNull();
  });

  it('bloco sem data não é evento', () => {
    expect(parsear('event: cardapio')).toBeNull();
  });

  it('JSON quebrado não derruba o stream', () => {
    // O próximo evento chega igual; a tela perde um aviso, não a conexão.
    expect(parsear('event: pedido\ndata: {isso não é json')).toBeNull();
  });

  it('evento sem nome cai em message', () => {
    expect(parsear('data: {}')?.nome).toBe('message');
  });

  it('data em várias linhas é concatenado', () => {
    // O protocolo permite quebrar o `data:` em linhas; o servidor não faz isso
    // hoje, mas um proxy que reembale a resposta pode.
    expect(parsear('event: x\ndata: {"a":\ndata: 1}')?.dados).toEqual({ a: 1 });
  });
});
