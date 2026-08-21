import type { TraceTool } from '../../dominio/chatStream';

// Trace de uma tool call durante o streaming — a bolha menor que mostra
// "Buscando ciclo 2026/1…" enquanto a chamada roda.

const NOME_LEGIVEL: Record<string, string> = {
  buscar_aluno_por_nome: 'Buscando aluno',
  obter_aluno: 'Carregando aluno',
  listar_ciclos: 'Listando ciclos',
  listar_simulados: 'Listando simulados',
  obter_simulado: 'Carregando simulado',
  listar_materias: 'Listando matérias',
  estatisticas_ciclo: 'Calculando estatísticas do ciclo',
  trajetoria_aluno: 'Carregando trajetória do aluno',
  histograma_simulado: 'Carregando histograma',
  notas_simulado: 'Carregando notas do simulado',
  comparar_ciclos: 'Comparando ciclos',
  alunos_similares: 'Buscando alunos similares',
  alunos_em_risco: 'Identificando alunos em risco',
  alunos_destaque: 'Identificando destaques',
  tendencia_aluno: 'Analisando tendência',
  materias_problematicas: 'Identificando matérias problemáticas',
  gerar_grafico: 'Gerando gráfico',
  exportar_csv: 'Gerando CSV',

  // Tools do chat do aluno (mentor).
  minhas_notas: 'Buscando suas notas',
  meu_desempenho_em_simulado: 'Analisando seu simulado',
  minha_evolucao: 'Calculando sua evolução',
  meu_streak: 'Conferindo sua sequência',
  minhas_questoes_erradas: 'Revisando suas questões',
  meu_insight_do_ciclo: 'Gerando seu insight do ciclo',
};

function resumirArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .filter(([, v]) => v != null)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? `"${v.slice(0, 30)}"` : String(v)}`)
    .join(', ');
}

export function ToolTrace({ trace }: { trace: TraceTool }) {
  const args = trace.args && Object.keys(trace.args).length ? resumirArgs(trace.args) : null;

  return (
    <div className={`chat-trace ${trace.finalizada ? 'is-finalizada' : 'is-rodando'}`}>
      <span className="chat-trace__icone">{trace.finalizada ? '✓' : '⋯'}</span>
      <span className="chat-trace__nome">{NOME_LEGIVEL[trace.nome] || trace.nome}</span>
      {args && <span className="chat-trace__args">{args}</span>}
      {trace.resumo && <span className="chat-trace__resumo">{`→ ${trace.resumo}`}</span>}
    </div>
  );
}
