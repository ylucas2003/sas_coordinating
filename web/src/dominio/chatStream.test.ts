import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';
import {
  CATALOGO_DE_ARTEFATOS,
  ESTADO_INICIAL,
  LIMITE_DO_TITULO_DO_ARTEFATO,
  NOME_LEGIVEL_DA_TOOL,
  artefatosNaResposta,
  extrairArtefatos,
  mensagemDaResposta,
  nomeLegivelDaTool,
  reduzirEvento,
  resumirArgumentos,
} from './chatStream';
import type { EstadoStream } from './chatStream';
import type { MensagemChat, ToolCall } from '../tipos/chat';

const reduzir = (eventos: Array<{ nome: string; dados?: unknown }>): EstadoStream =>
  eventos.reduce((e, ev) => reduzirEvento(e, { nome: ev.nome, dados: ev.dados ?? {} }), ESTADO_INICIAL);

/** Um resultado torto como o servidor poderia mandar, sem o tipo de `ToolCall` barrar o caso. */
const torto = (resultado: Record<string, unknown>) => resultado as ToolCall['resultado'];

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

  // Texto final vazio nunca apaga o que a pessoa já leu.
  it('texto_final vazio no end também mantém o que veio nos tokens', () => {
    const e = reduzir([
      { nome: 'token', dados: { texto: 'só isso' } },
      { nome: 'end', dados: { texto_final: '' } },
    ]);
    expect(e.final!.texto).toBe('só isso');
  });

  // Regressão do streaming de verdade (docs/43 §4.2): o erro chega DEPOIS de
  // tokens já exibidos, e o `end` vem com `texto_final: ""` — a sequência de
  // test_chat_agente.py::test_falha_no_meio_do_stream. `?? estado.texto` não
  // recorria ao texto para string vazia, e a bolha trocava o que a pessoa
  // estava lendo por nada.
  it('erro no meio do stream mantém o texto exibido, e o erro vai embaixo', () => {
    const e = reduzir([
      { nome: 'token', dados: { texto: 'Sua média' } },
      { nome: 'token', dados: { texto: ' no ciclo' } },
      { nome: 'erro', dados: { mensagem: 'O serviço que gera as respostas está sobrecarregado agora.' } },
      { nome: 'end', dados: { texto_final: '', tool_calls: [] } },
    ]);
    expect(e.final).toEqual({ texto: 'Sua média no ciclo', artefatos: [] });
    expect(e.erros).toEqual(['O serviço que gera as respostas está sobrecarregado agora.']);
  });

  // O servidor, com `erro`, só grava a mensagem de erro — nenhuma `tool`, nenhum
  // `chat_artefato` (`_stream_mensagem`, rotas.py). Cartão mostrado aqui sumiria
  // ao reabrir a conversa. É o caso das voltas esgotadas: as tools rodaram, e
  // o `end` traz o resultado cheio delas.
  it('resposta que termina em erro não mostra cartão, mesmo com tools que o produziram', () => {
    const e = reduzir([
      { nome: 'tool_call_start', dados: { tool_call_id: 'a', nome: 'minha_zona', args: {} } },
      { nome: 'tool_call_end', dados: { tool_call_id: 'a', resumido: 'ok' } },
      { nome: 'erro', dados: { mensagem: 'Não consegui fechar a resposta.' } },
      {
        nome: 'end',
        dados: {
          texto_final: '',
          tool_calls: [
            {
              nome: 'minha_zona',
              resultado: { zona: 'risco', artefato: { tipo: 'barras_corte', payload: { materias: [] } } },
            },
            { nome: 'navegar_para', resultado: { tipo: 'navegacao', titulo: 'Ana', payload: { rota: '/alunos/a1' } } },
          ],
        },
      },
    ]);
    expect(e.final!.artefatos).toEqual([]);
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

  // Regressão: o servidor persiste o link desde a 0038, mas ao vivo ele não
  // aparecia — o coordenador lia o nome do aluno em texto, sem ter onde clicar.
  it('reconhece o link de navegar_para, com a rota que o servidor montou', () => {
    const payload = { rota: '/alunos/a1b2', rotulo: 'Ana Souza', entidade: 'aluno' };
    expect(extrairArtefatos([
      { nome: 'navegar_para', resultado: { tipo: 'navegacao', titulo: 'Ana Souza', payload } },
    ])).toEqual([{ tipo: 'navegacao', titulo: 'Ana Souza', payload }]);
  });

  it('não aceita navegar_para que voltou com erro', () => {
    expect(extrairArtefatos([
      { nome: 'navegar_para', resultado: { erro: 'aluno x não existe — nada para onde navegar.' } },
    ])).toEqual([]);
  });

  it('aceita o campo `artefato` no resultado de qualquer tool, ao lado do resto do dado', () => {
    const payload = { materias: [{ materia: 'Física', nota: 3.6, corte: 4, eliminatoria: false }] };
    expect(extrairArtefatos([
      {
        nome: 'minhas_notas',
        resultado: {
          total: 1,
          simulados: [],
          artefato: { tipo: 'barras_corte', titulo: 'Suas matérias contra o corte', payload },
        },
      },
    ])).toEqual([{ tipo: 'barras_corte', titulo: 'Suas matérias contra o corte', payload }]);
  });

  it.each(CATALOGO_DE_ARTEFATOS)('aceita `%s`, que está no catálogo', (tipo) => {
    expect(extrairArtefatos([
      { nome: 'qualquer_tool', resultado: { artefato: { tipo, payload: { id: 'x' } } } },
    ])).toEqual([{ tipo, titulo: undefined, payload: { id: 'x' } }]);
  });

  it('título nulo é cartão sem título, como o `prova` que a tool manda', () => {
    expect(extrairArtefatos([
      {
        nome: 'meu_desempenho_em_simulado',
        resultado: { artefato: { tipo: 'prova', titulo: null, payload: { simuladoId: 's1' } } },
      },
    ])).toEqual([{ tipo: 'prova', titulo: undefined, payload: { simuladoId: 's1' } }]);
  });

  // O servidor descarta o cartão INTEIRO quando o título não é texto, passa de
  // 200 caracteres ou o payload não é objeto (`_motivo_de_descarte`,
  // ferramentas.py). Aceitar aqui era mostrar ao vivo o que some ao reabrir.
  it('descarta o que o servidor não grava: título que não é texto, longo demais, payload que não é objeto', () => {
    const longo = 'x'.repeat(LIMITE_DO_TITULO_DO_ARTEFATO + 1);
    expect(extrairArtefatos([
      { nome: 'a', resultado: { artefato: { tipo: 'prova', titulo: 42, payload: {} } } },
      { nome: 'b', resultado: { artefato: { tipo: 'prova', titulo: longo, payload: {} } } },
      { nome: 'c', resultado: { artefato: { tipo: 'questao', payload: 'ita_2024_fase1_q07' } } },
      { nome: 'd', resultado: { artefato: { tipo: 'lista_questoes', payload: [{ assunto: 'Óptica' }] } } },
      { nome: 'e', resultado: { artefato: { tipo: 'histograma' } } },
      { nome: 'gerar_grafico', resultado: { tipo: 'histograma', titulo: 'Notas', payload: null } },
      { nome: 'gerar_grafico', resultado: torto({ tipo: 'linha_temporal', titulo: 7, payload: {} }) },
      { nome: 'navegar_para', resultado: { tipo: 'navegacao', titulo: longo, payload: { rota: '/x' } } },
    ])).toEqual([]);
  });

  it('o teto do título conta como o servidor: 200 cabem, e um emoji é um caractere', () => {
    const exato = 'x'.repeat(LIMITE_DO_TITULO_DO_ARTEFATO);
    const comEmoji = `${'x'.repeat(LIMITE_DO_TITULO_DO_ARTEFATO - 1)}📈`;
    expect(extrairArtefatos([
      { nome: 'a', resultado: { artefato: { tipo: 'prova', titulo: exato, payload: {} } } },
      { nome: 'b', resultado: { artefato: { tipo: 'prova', titulo: comEmoji, payload: {} } } },
    ]).map((a) => a.titulo)).toEqual([exato, comEmoji]);
  });

  // O servidor também não persiste o que está fora do catálogo: mostrar ao vivo
  // um cartão que some ao reabrir a conversa é pior do que não mostrar.
  it('descarta o campo `artefato` com tipo fora do catálogo, sem tipo ou malformado', () => {
    expect(extrairArtefatos([
      { nome: 'a', resultado: { artefato: { tipo: 'pizza', payload: {} } } },
      { nome: 'b', resultado: { artefato: { tipo: 'extrato_xp', payload: { linhas: [] } } } },
      { nome: 'c', resultado: { artefato: { tipo: 'formula', payload: 'x^2' } } },
      { nome: 'd', resultado: { artefato: { tipo: 'BARRAS_CORTE', payload: {} } } },
      { nome: 'e', resultado: { artefato: { payload: {} } } },
      { nome: 'f', resultado: { artefato: { tipo: 7, payload: {} } } },
      { nome: 'g', resultado: { artefato: 'barras_corte' } },
      { nome: 'h', resultado: { artefato: [{ tipo: 'barras_corte', payload: {} }] } },
      { nome: 'i', resultado: { artefato: null } },
    ])).toEqual([]);
  });

  // `csv` e `navegacao` só nascem das tools próprias. O link, em especial, tem
  // a rota montada no servidor (docs/31 §2.4): pelo campo genérico, qualquer
  // tool passaria a poder pôr um botão de navegação na conversa.
  it('não deixa o campo `artefato` produzir link de navegação nem CSV', () => {
    expect(extrairArtefatos([
      { nome: 'minhas_notas', resultado: { artefato: { tipo: 'navegacao', payload: { rota: '/x' } } } },
      { nome: 'minhas_notas', resultado: { artefato: { tipo: 'csv', payload: { conteudo: 'a' } } } },
      { nome: 'listar_alunos', resultado: { tipo: 'navegacao', payload: { rota: '/x' } } },
    ])).toEqual([]);
  });

  it('descarta o campo `artefato` de resultado com erro', () => {
    expect(extrairArtefatos([
      { nome: 'minhas_notas', resultado: { erro: 'falhou', artefato: { tipo: 'questao', payload: {} } } },
    ])).toEqual([]);
  });

  it('mantém a ordem das tools quando formatos próprios e campo genérico se misturam', () => {
    expect(extrairArtefatos([
      { nome: 'gerar_grafico', resultado: { tipo: 'histograma', titulo: 'Notas', payload: { a: 1 } } },
      { nome: 'minhas_notas', resultado: { artefato: { tipo: 'questao', payload: { id: 'ita_2024_fase1_q07' } } } },
      { nome: 'navegar_para', resultado: { tipo: 'navegacao', titulo: 'Ciclo 6', payload: { rota: '/ciclos/c6' } } },
    ]).map((a) => a.tipo)).toEqual(['histograma', 'questao', 'navegacao']);
  });
});

describe('CATALOGO_DE_ARTEFATOS', () => {
  // Espelha a allowlist do servidor (`_talvez_salvar_artefato`, rotas.py). Este
  // teste existe para que mudar a lista seja um gesto deliberado, feito dos
  // dois lados — e não um tipo a mais que só o front conhece.
  it('é o catálogo fechado de docs/43 §4.1', () => {
    expect([...CATALOGO_DE_ARTEFATOS].sort()).toEqual(
      ['barras_corte', 'histograma', 'linha_temporal', 'lista_questoes', 'prova', 'questao'],
    );
  });
});

// O artefato que a tool anexa precisa aparecer AO VIVO, no `end`, e seguir para
// o histórico na pergunta seguinte — sem esperar a conversa ser recarregada.
describe('o artefato anexado, do end ao histórico', () => {
  it('chega ao final do stream e passa para a mensagem do assistente', () => {
    const artefato = { tipo: 'lista_questoes', titulo: 'Para treinar', payload: { itens: [] } };
    const e = reduzir([
      { nome: 'tool_call_start', dados: { tool_call_id: 'a', nome: 'minhas_questoes_erradas', args: {} } },
      { nome: 'tool_call_end', dados: { tool_call_id: 'a', resumido: 'ok' } },
      {
        nome: 'end',
        dados: {
          texto_final: 'Comece por cinemática.',
          tool_calls: [{ nome: 'minhas_questoes_erradas', resultado: { paraRevisar: [], artefato } }],
        },
      },
    ]);

    expect(e.final!.artefatos).toEqual([artefato]);
    expect(mensagemDaResposta(e)!.artefatos).toEqual([artefato]);
  });
});

// Regressão: o servidor pendura o artefato persistido na mensagem `tool`, e a
// conversa não desenha `tool` — reabrir a conversa apagava todo cartão.
describe('artefatosNaResposta', () => {
  const grafico = { tipo: 'histograma', titulo: 'Notas', payload: { histograma: {} } };
  const questao = { tipo: 'questao', payload: { id: 'ita_2024_fase1_q07' } };

  const turno: MensagemChat[] = [
    { papel: 'user', conteudo: 'como fui?' },
    { papel: 'assistant', conteudo: null, toolCalls: [{ name: 'a' }, { name: 'b' }], artefatos: [] },
    { papel: 'tool', conteudo: '{}', artefatos: [grafico] },
    { papel: 'tool', conteudo: '{}', artefatos: [questao] },
    { papel: 'assistant', conteudo: 'Você foi bem.', artefatos: [] },
  ];

  it('leva os artefatos das mensagens tool para a resposta do turno, na ordem', () => {
    const saida = artefatosNaResposta(turno);

    expect(saida[4]).toEqual({ papel: 'assistant', conteudo: 'Você foi bem.', artefatos: [grafico, questao] });
    expect(saida[2].artefatos).toEqual([]);
    expect(saida[3].artefatos).toEqual([]);
    // A mensagem das tool calls continua com os traces e sem artefato.
    expect(saida[1]).toEqual(turno[1]);
  });

  it('não muda a entrada e é idempotente', () => {
    const copia = structuredClone(turno);
    const uma = artefatosNaResposta(turno);

    expect(turno).toEqual(copia);
    expect(artefatosNaResposta(uma)).toEqual(uma);
  });

  it('artefato não atravessa a pergunta seguinte: sem resposta, vira mensagem própria', () => {
    const saida = artefatosNaResposta([
      { papel: 'user', conteudo: 'um' },
      { papel: 'tool', conteudo: '{}', artefatos: [grafico] },
      { papel: 'user', conteudo: 'dois' },
      { papel: 'assistant', conteudo: 'resposta do dois' },
    ]);

    expect(saida.map((m) => m.papel)).toEqual(['user', 'tool', 'assistant', 'user', 'assistant']);
    expect(saida[2]).toEqual({ papel: 'assistant', conteudo: null, artefatos: [grafico] });
    expect(saida[4]).toEqual({ papel: 'assistant', conteudo: 'resposta do dois' });
  });

  it('histórico que termina nas tools não perde o artefato', () => {
    const saida = artefatosNaResposta([
      { papel: 'user', conteudo: 'um' },
      { papel: 'tool', conteudo: '{}', artefatos: [questao] },
    ]);

    expect(saida.at(-1)).toEqual({ papel: 'assistant', conteudo: null, artefatos: [questao] });
  });

  // A coordenação tinha o mesmo buraco e ninguém o fechava: a `Conversa` de lá
  // recebia a thread crua, e o link de `navegar_para`, o gráfico e o CSV sumiam
  // a cada reabertura. A thread aqui tem a forma de `GET /chat/threads/{id}`
  // (rotas.obter_thread): o turno das tool calls, uma `tool` por chamada com o
  // artefato pendurado, e a resposta.
  it('a conversa reaberta da coordenação devolve link, gráfico e CSV à resposta do turno', () => {
    const link = { id: 'art1', tipo: 'navegacao', titulo: 'Ana Souza', payload: { rota: '/alunos/a1' }, urlExport: null };
    const grafico = { id: 'art2', tipo: 'histograma', titulo: 'Notas', payload: { histograma: {} }, urlExport: null };
    const csv = { id: 'art3', tipo: 'csv', titulo: 'Risco', payload: { conteudo: 'a,b', nLinhas: 1 }, urlExport: null };
    const reaberta = [
      { papel: 'user', conteudo: 'quem está em risco?', toolCalls: null, artefatos: [] },
      {
        papel: 'assistant',
        conteudo: null,
        toolCalls: [{ id: 'c1', name: 'navegar_para', arguments: { tipo: 'aluno', id: 'a1' } }],
        artefatos: [],
      },
      { papel: 'tool', conteudo: '{}', nomeTool: 'navegar_para', artefatos: [link] },
      { papel: 'tool', conteudo: '{}', nomeTool: 'gerar_grafico', artefatos: [grafico] },
      { papel: 'tool', conteudo: '{}', nomeTool: 'exportar_csv', artefatos: [csv] },
      { papel: 'assistant', conteudo: 'A Ana está em risco.', toolCalls: null, artefatos: [] },
      // Por `unknown` porque a API manda `toolCalls: null` nas mensagens sem
      // tool call, e `MensagemChat` não declara o null: a forma é a do fio.
    ] as unknown as MensagemChat[];

    const saida = artefatosNaResposta(reaberta);

    expect(saida.at(-1)!.artefatos).toEqual([link, grafico, csv]);
    // Mensagem `tool` não desenha nada, e o turno das tool calls segue com os
    // traces: é a resposta que leva os cartões, como ao vivo.
    expect(saida.filter((m) => m.papel === 'tool').flatMap((m) => m.artefatos ?? [])).toEqual([]);
    expect(saida[1]).toEqual(reaberta[1]);
    // A folha do aluno aplicava a passagem antes da `Conversa`; se alguém
    // voltar a aplicá-la fora, nada duplica.
    expect(artefatosNaResposta(saida)).toEqual(saida);
  });

  it('histórico sem artefato passa intacto, e ausente vira lista vazia', () => {
    const conversa: MensagemChat[] = [
      { papel: 'user', conteudo: 'oi' },
      { papel: 'tool', conteudo: '{}' },
      { papel: 'assistant', conteudo: 'olá' },
    ];
    expect(artefatosNaResposta(conversa)).toEqual(conversa);
    expect(artefatosNaResposta(undefined)).toEqual([]);
  });
});

// Regressão: a resposta sumia da tela na pergunta seguinte, porque o stream era
// zerado sem que ela passasse para o histórico.
describe('mensagemDaResposta', () => {
  it('converte a resposta concluída em mensagem do assistente, com traces e artefatos', () => {
    const e = reduzir([
      { nome: 'tool_call_start', dados: { tool_call_id: 'a', nome: 'alunos_destaque', args: { ano: 2026 } } },
      { nome: 'tool_call_end', dados: { tool_call_id: 'a', resumido: '75 alunos' } },
      { nome: 'token', dados: { texto: 'rascunho' } },
      {
        nome: 'end',
        dados: {
          texto_final: 'Os que mais evoluíram são…',
          tool_calls: [{ nome: 'exportar_csv', resultado: { tipo: 'csv', titulo: 'Evolução', conteudo: 'a,b', nLinhas: 1 } }],
        },
      },
    ]);

    expect(mensagemDaResposta(e)).toEqual({
      papel: 'assistant',
      conteudo: 'Os que mais evoluíram são…',
      toolCalls: [{ nome: 'alunos_destaque', args: { ano: 2026 } }],
      artefatos: [{ tipo: 'csv', titulo: 'Evolução', payload: { conteudo: 'a,b', nLinhas: 1 } }],
    });
  });

  // Texto parcial sem `end` nem `erro` não é resposta: o servidor não o grava.
  it('devolve null enquanto o stream não chegou ao end nem trouxe erro', () => {
    expect(mensagemDaResposta(ESTADO_INICIAL)).toBeNull();
    expect(mensagemDaResposta(reduzir([{ nome: 'token', dados: { texto: 'parcial' } }]))).toBeNull();
  });

  // ⚠️ O que vai para o histórico tem de ser EXATAMENTE o que `_stream_mensagem`
  // grava quando houve `erro`: uma linha do assistente com "⚠️ Erro: <mensagem>",
  // sem texto parcial, sem tool calls e sem artefato. Senão a resposta muda de
  // cara na hora de reabrir a conversa.
  it('resposta que terminou em erro vai ao histórico como o servidor a grava', () => {
    const e = reduzir([
      { nome: 'tool_call_start', dados: { tool_call_id: 'a', nome: 'minhas_notas', args: {} } },
      { nome: 'tool_call_end', dados: { tool_call_id: 'a', resumido: '3 simulados' } },
      { nome: 'token', dados: { texto: 'Sua média' } },
      { nome: 'token', dados: { texto: ' no ciclo' } },
      { nome: 'erro', dados: { mensagem: 'O serviço está sobrecarregado agora.' } },
      {
        nome: 'end',
        dados: {
          texto_final: '',
          tool_calls: [
            { nome: 'minhas_notas', resultado: { artefato: { tipo: 'barras_corte', payload: { materias: [] } } } },
          ],
        },
      },
    ]);

    expect(mensagemDaResposta(e)).toEqual({
      papel: 'assistant',
      conteudo: '⚠️ Erro: O serviço está sobrecarregado agora.',
      artefatos: [],
    });
  });

  // O agente também emite o erro SEM chegar ao `end` (provedor sem credencial,
  // agente.py), e o servidor grava do mesmo jeito: quem decide é o `erro`.
  it('erro sem end também vai ao histórico, como o servidor o grava', () => {
    expect(mensagemDaResposta(reduzir([
      { nome: 'token', dados: { texto: 'parcial' } },
      { nome: 'erro', dados: { mensagem: 'O assistente está indisponível agora.' } },
    ]))).toEqual({ papel: 'assistant', conteudo: '⚠️ Erro: O assistente está indisponível agora.', artefatos: [] });
  });

  it('com mais de um erro, fica o último — é o que o servidor guarda', () => {
    expect(mensagemDaResposta(reduzir([
      { nome: 'erro', dados: { mensagem: 'primeiro' } },
      { nome: 'erro', dados: { mensagem: 'segundo' } },
      { nome: 'end', dados: { texto_final: '' } },
    ]))!.conteudo).toBe('⚠️ Erro: segundo');
  });
});

// ─── O trace de uma tool ─────────────────────────────────────────────────

describe('NOME_LEGIVEL_DA_TOOL', () => {
  // As tools declaradas no backend, lidas da fonte — como o
  // test_chat_ferramentas.py lê o `CATALOGO_DE_ARTEFATOS` deste módulo: cada
  // lado confere o outro. Sem o backend ao lado (checkout só do front), pula.
  const CHAT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'api', 'app', 'chat');
  const temBackend = existsSync(join(CHAT, 'ferramentas.py'));

  function toolsDoBackend(): string[] {
    const tools = join(CHAT, 'tools');
    const arquivos = [
      ...readdirSync(tools).filter((n) => n.endsWith('.py') && n !== '__init__.py').map((n) => join(tools, n)),
      ...readdirSync(CHAT).filter((n) => /^tools_aluno.*\.py$/.test(n) || n === 'roteiros.py').map((n) => join(CHAT, n)),
    ];
    const nomes = new Set<string>();
    for (const arquivo of arquivos) {
      const fonte = readFileSync(arquivo, 'utf8');
      // `"name": "x"` no schema de cada tool; os roteiros montam o schema por
      // `_schema("roteiro_do_mentor", ...)`.
      for (const m of fonte.matchAll(/"name":\s*"([a-z0-9_]+)"/g)) nomes.add(m[1]);
      for (const m of fonte.matchAll(/_schema\(\s*"([a-z0-9_]+)"/g)) nomes.add(m[1]);
    }
    return [...nomes].sort();
  }

  it.skipIf(!temBackend)('a leitura do backend acha as tools (se o formato mudar, ajuste este teste)', () => {
    expect(toolsDoBackend()).toEqual(
      expect.arrayContaining(['minhas_notas', 'navegar_para', 'roteiro_do_mentor', 'roteiro_da_coordenacao']),
    );
  });

  it.skipIf(!temBackend)('dá nome legível a toda tool do registro, dos dois escopos', () => {
    const semNome = toolsDoBackend().filter((n) => !Object.hasOwn(NOME_LEGIVEL_DA_TOOL, n));
    expect(semNome, 'tool sem nome legível: o trace mostraria o nome cru').toEqual([]);
  });

  it.skipIf(!temBackend)('não guarda nome de tool que saiu do registro', () => {
    const doBackend = new Set(toolsDoBackend());
    expect(Object.keys(NOME_LEGIVEL_DA_TOOL).filter((n) => !doBackend.has(n))).toEqual([]);
  });

  it('nome desconhecido sai cru, e nunca acha o protótipo do objeto', () => {
    expect(nomeLegivelDaTool('o_que_mais_cai')).toBe('Vendo o que mais cai nas provas');
    expect(nomeLegivelDaTool('tool_inventada')).toBe('tool_inventada');
    expect(nomeLegivelDaTool('constructor')).toBe('constructor');
    expect(nomeLegivelDaTool('toString')).toBe('toString');
  });
});

describe('resumirArgumentos', () => {
  const UUID = '3f2a9c1e-5b7d-4e8f-9a0b-1c2d3e4f5a6b';

  it('na coordenação, segue como era: tudo menos nulo, texto cortado em 30', () => {
    expect(resumirArgumentos({
      ciclo_id: UUID, limite: 10, so_cortados: true, busca: null, nome: 'a'.repeat(40),
    })).toBe(`ciclo_id="${UUID.slice(0, 30)}", limite=10, so_cortados=true, nome="${'a'.repeat(30)}"`);
    expect(resumirArgumentos({ aluno_ids: [UUID, 'b'] }, 'coordenacao')).toBe(`aluno_ids=${UUID},b`);
  });

  // O aluno não lê UUID no trace (docs/43 §4.1): "simulado_id=3f2a…" não diz
  // nada a ele, e o nome legível da tool já diz o que está acontecendo.
  it('no aluno, identificador cru não aparece; o resto fica', () => {
    expect(resumirArgumentos({ simulado_id: UUID }, 'aluno')).toBe('');
    expect(resumirArgumentos({ simulado_id: ` ${UUID.toUpperCase()} ` }, 'aluno')).toBe('');
    expect(resumirArgumentos({ materia: 'Física', simulado_id: UUID, limite: 40 }, 'aluno'))
      .toBe('materia="Física", limite=40');
    // O id do banco é legível, e é ele que o aluno vê na tela da questão.
    expect(resumirArgumentos({ questao_id: 'ita_2023_fase1_q05' }, 'aluno')).toBe('questao_id="ita_2023_fase1_q05"');
  });

  it('no aluno, o UUID sai de dentro da lista, e a lista vazia some', () => {
    expect(resumirArgumentos({ ids: [UUID, 'Física'] }, 'aluno')).toBe('ids=Física');
    expect(resumirArgumentos({ ids: [UUID] }, 'aluno')).toBe('');
  });

  // O servidor descarta o `aluno_id` que o modelo manda e usa o do token
  // (docs/43 §3.2, invariante 2): mostrar seria mostrar algo que não foi usado.
  it('no aluno, aluno_id não aparece com valor nenhum', () => {
    expect(resumirArgumentos({ aluno_id: 'eu', materia: 'Química' }, 'aluno')).toBe('materia="Química"');
  });

  it('sem argumento, nada', () => {
    expect(resumirArgumentos({}, 'aluno')).toBe('');
    expect(resumirArgumentos(undefined)).toBe('');
  });
});
