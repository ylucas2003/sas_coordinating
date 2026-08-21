import { describe, expect, it } from 'vitest';
import { ESTADO_INICIAL, extrairArtefatos, reduzirEvento } from './chatStream';
import type { EstadoStream } from './chatStream';

const reduzir = (eventos: Array<{ nome: string; dados?: unknown }>): EstadoStream =>
  eventos.reduce((e, ev) => reduzirEvento(e, { nome: ev.nome, dados: ev.dados ?? {} }), ESTADO_INICIAL);

describe('reduzirEvento', () => {
  it('acumula tokens em ordem', () => {
    const e = reduzir([
      { nome: 'token', dados: { texto: 'Olá' } },
      { nome: 'token', dados: { texto: ', mundo' } },
    ]);
    expect(e.texto).toBe('Olá, mundo');
  });

  it('ignora marcadores de ciclo de vida', () => {
    expect(reduzir([{ nome: 'start' }, { nome: 'user_salvo' }])).toEqual(ESTADO_INICIAL);
  });

  it('abre e fecha a trace pelo tool_call_id, preservando nome e args', () => {
    const e = reduzir([
      { nome: 'tool_call_start', dados: { tool_call_id: 'tc1', nome: 'listar_ciclos', args: { ano: 2026 } } },
      { nome: 'tool_call_end', dados: { tool_call_id: 'tc1', resumido: '3 ciclos' } },
    ]);
    expect(e.traces).toEqual([
      { id: 'tc1', nome: 'listar_ciclos', args: { ano: 2026 }, resumo: '3 ciclos', finalizada: true },
    ]);
  });

  // Traces concorrentes podem fechar fora de ordem.
  it('fecha a trace certa quando há várias abertas', () => {
    const e = reduzir([
      { nome: 'tool_call_start', dados: { tool_call_id: 'a', nome: 'um' } },
      { nome: 'tool_call_start', dados: { tool_call_id: 'b', nome: 'dois' } },
      { nome: 'tool_call_end', dados: { tool_call_id: 'b', resumido: 'ok' } },
    ]);
    expect(e.traces.map((t) => [t.nome, t.finalizada])).toEqual([['um', false], ['dois', true]]);
  });

  it('ignora fechamento de trace desconhecida em vez de quebrar', () => {
    const e = reduzir([{ nome: 'tool_call_end', dados: { tool_call_id: 'fantasma' } }]);
    expect(e.traces).toEqual([]);
  });

  it('acumula erros sem descartar o texto já recebido', () => {
    const e = reduzir([
      { nome: 'token', dados: { texto: 'parcial' } },
      { nome: 'erro', dados: { mensagem: 'timeout' } },
    ]);
    expect(e.texto).toBe('parcial');
    expect(e.erros).toEqual(['timeout']);
  });

  it('guarda o título gerado pelo backend', () => {
    expect(reduzir([{ nome: 'titulo', dados: { titulo: 'Ciclo 3' } }]).titulo).toBe('Ciclo 3');
  });

  it('no end substitui o texto cru pelo final e extrai artefatos', () => {
    const e = reduzir([
      { nome: 'token', dados: { texto: 'rascunho' } },
      {
        nome: 'end',
        dados: {
          texto_final: '**Resposta** final',
          tool_calls: [
            { nome: 'gerar_grafico', resultado: { tipo: 'histograma', titulo: 'Notas', payload: { a: 1 } } },
          ],
        },
      },
    ]);
    expect(e.final!.texto).toBe('**Resposta** final');
    expect(e.final!.artefatos).toEqual([{ tipo: 'histograma', titulo: 'Notas', payload: { a: 1 } }]);
  });

  it('sem texto_final no end, mantém o que veio nos tokens', () => {
    const e = reduzir([{ nome: 'token', dados: { texto: 'só isso' } }, { nome: 'end', dados: {} }]);
    expect(e.final!.texto).toBe('só isso');
  });

  it('evento desconhecido não altera o estado', () => {
    const antes = reduzir([{ nome: 'token', dados: { texto: 'x' } }]);
    expect(reduzirEvento(antes, { nome: 'inventado', dados: {} })).toEqual(antes);
  });
});

describe('extrairArtefatos', () => {
  it('descarta tool call com erro e tipo não renderizável', () => {
    expect(extrairArtefatos([
      { nome: 'gerar_grafico', resultado: { erro: 'falhou' } },
      { nome: 'gerar_grafico', resultado: { tipo: 'pizza' } },
      { nome: 'listar_ciclos', resultado: { tipo: 'histograma' } },
    ])).toEqual([]);
  });

  it('monta o payload do CSV a partir do resultado', () => {
    expect(extrairArtefatos([
      { nome: 'exportar_csv', resultado: { tipo: 'csv', titulo: 'Notas', conteudo: 'a,b', nLinhas: 2 } },
    ])).toEqual([{ tipo: 'csv', titulo: 'Notas', payload: { conteudo: 'a,b', nLinhas: 2 } }]);
  });

  it('aceita a tool call vinda com `name` em vez de `nome`', () => {
    expect(extrairArtefatos([
      { name: 'gerar_grafico', resultado: { tipo: 'linha_temporal', payload: {} } },
    ])).toHaveLength(1);
  });
});
