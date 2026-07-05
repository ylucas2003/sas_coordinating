// Trace de uma tool_call durante o streaming — bolha menor abaixo do
// "pensando..." que mostra "Buscando ciclo 2026/1..." enquanto roda.

import { el } from '../../dom.js';

const NOME_LEGIVEL = {
  buscar_aluno_por_nome:  'Buscando aluno',
  obter_aluno:            'Carregando aluno',
  listar_ciclos:          'Listando ciclos',
  listar_simulados:       'Listando simulados',
  obter_simulado:         'Carregando simulado',
  listar_materias:        'Listando matérias',
  estatisticas_ciclo:     'Calculando estatísticas do ciclo',
  trajetoria_aluno:       'Carregando trajetória do aluno',
  histograma_simulado:    'Carregando histograma',
  notas_simulado:         'Carregando notas do simulado',
  comparar_ciclos:        'Comparando ciclos',
  alunos_similares:       'Buscando alunos similares',
  alunos_em_risco:        'Identificando alunos em risco',
  alunos_destaque:        'Identificando destaques',
  tendencia_aluno:        'Analisando tendência',
  materias_problematicas: 'Identificando matérias problemáticas',
  gerar_grafico:          'Gerando gráfico',
  exportar_csv:           'Gerando CSV',

  // Tools do chat do aluno (mentor)
  minhas_notas:              'Buscando suas notas',
  meu_desempenho_em_simulado: 'Analisando seu simulado',
  minha_evolucao:            'Calculando sua evolução',
  meu_streak:                'Conferindo sua sequência',
  minhas_questoes_erradas:   'Revisando suas questões',
  meu_insight_do_ciclo:      'Gerando seu insight do ciclo',
};

/**
 * Renderiza ou atualiza uma bolha de trace. Pra atualizar com o resultado,
 * passe o mesmo elemento de volta e `resumo`.
 */
export function toolTrace({ nome, args, resumo = null, finalizada = false }) {
  return el('div', {
    class: `chat-trace ${finalizada ? 'is-finalizada' : 'is-rodando'}`,
  }, [
    el('span', { class: 'chat-trace__icone' }, [finalizada ? '✓' : '⋯']),
    el('span', { class: 'chat-trace__nome' }, [NOME_LEGIVEL[nome] || nome]),
    args && Object.keys(args).length
      ? el('span', { class: 'chat-trace__args' }, [_resumirArgs(args)])
      : null,
    resumo
      ? el('span', { class: 'chat-trace__resumo' }, [`→ ${resumo}`])
      : null,
  ].filter(Boolean));
}

function _resumirArgs(args) {
  const parts = [];
  for (const [k, v] of Object.entries(args)) {
    if (v == null) continue;
    const valor = typeof v === 'string' ? `"${v.slice(0, 30)}"` : String(v);
    parts.push(`${k}=${valor}`);
  }
  return parts.join(', ');
}
