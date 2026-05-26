// Dados sintéticos para desenvolvimento. Pequenos e plausíveis, só para
// popular as telas. A calibração real virá com o upload das planilhas do
// colégio (ver decisão pendente #2 em ../../../docs/06-open-questions.md).

export const sedes = [
  { id: 'sede-centro', nome: 'Centro', modalidade: 'presencial' },
  { id: 'sede-sul', nome: 'Sul', modalidade: 'presencial' },
  { id: 'sede-online', nome: 'Online', modalidade: 'online' },
];

export const turmas = [
  { id: 'turma-3a', nome: '3ª A — ITM', sedeId: 'sede-centro', anoLetivo: 2026 },
  { id: 'turma-3b', nome: '3ª B — ITM', sedeId: 'sede-centro', anoLetivo: 2026 },
  { id: 'turma-3c', nome: '3ª C — ITM', sedeId: 'sede-sul', anoLetivo: 2026 },
  { id: 'turma-3online', nome: '3ª Online — ITM', sedeId: 'sede-online', anoLetivo: 2026 },
];

export const ciclos = [
  { id: 'C1-26', nome: 'Ciclo 1 · 2026', anoLetivo: 2026, periodoInicio: '2026-02-03', periodoFim: '2026-03-13', simuladoIds: ['S01', 'S02'] },
  { id: 'C2-26', nome: 'Ciclo 2 · 2026', anoLetivo: 2026, periodoInicio: '2026-03-16', periodoFim: '2026-04-24', simuladoIds: ['S03', 'S04'] },
  { id: 'C3-26', nome: 'Ciclo 3 · 2026', anoLetivo: 2026, periodoInicio: '2026-04-27', periodoFim: '2026-05-13', simuladoIds: ['S05', 'S06', 'S07', 'S08'] },
];

export const simulados = [
  { id: 'S01', nome: 'Simulado ITA Fase 1 — Fev/26', fase: '1a', dataAplicacao: '2026-02-15', cicloId: 'C1-26', notaMaxima: 10, anulado: false, media: 6.4, mediana: 6.3, desvioPadrao: 1.1, nPresentes: 248 },
  { id: 'S02', nome: 'Simulado IME Fase 1 — Mar/26', fase: '1a', dataAplicacao: '2026-03-10', cicloId: 'C1-26', notaMaxima: 10, anulado: false, media: 6.1, mediana: 6.0, desvioPadrao: 1.2, nPresentes: 246 },
  { id: 'S03', nome: 'Simulado ITA Fase 2 — Mar/26', fase: '2a', dataAplicacao: '2026-03-25', cicloId: 'C2-26', notaMaxima: 10, anulado: false, media: 5.8, mediana: 5.7, desvioPadrao: 1.4, nPresentes: 245 },
  { id: 'S04', nome: 'Simulado IME Fase 2 — Abr/26', fase: '2a', dataAplicacao: '2026-04-15', cicloId: 'C2-26', notaMaxima: 10, anulado: false, media: 6.2, mediana: 6.1, desvioPadrao: 1.0, nPresentes: 244 },
  { id: 'S05', nome: 'Simulado ITA Fase 1 — Abr/26', fase: '1a', dataAplicacao: '2026-04-28', cicloId: 'C3-26', notaMaxima: 10, anulado: false, media: 6.5, mediana: 6.4, desvioPadrao: 1.1, nPresentes: 247 },
  { id: 'S06', nome: 'Simulado AFA — Abr/26', fase: '1a', dataAplicacao: '2026-05-02', cicloId: 'C3-26', notaMaxima: 10, anulado: false, media: 6.8, mediana: 6.9, desvioPadrao: 0.9, nPresentes: 240 },
  { id: 'S07', nome: 'Simulado ITA Fase 2 — Mai/26', fase: '2a', dataAplicacao: '2026-05-07', cicloId: 'C3-26', notaMaxima: 10, anulado: false, media: 6.3, mediana: 6.2, desvioPadrao: 1.2, nPresentes: 246 },
  { id: 'S08', nome: 'Simulado IME Fase 2 — Mai/26', fase: '2a', dataAplicacao: '2026-05-12', cicloId: 'C3-26', notaMaxima: 10, anulado: false, media: 5.9, mediana: 5.8, desvioPadrao: 2.1, nPresentes: 244 },
];

export const alunos = [
  { id: 'A023', nome: 'Ana Pereira',      turmaId: 'turma-3b',      sedeId: 'sede-centro', vestibularesAlvo: ['ITA', 'IME'],    ativo: true, perfil: 'misterio', tendencia: 'caindo',  zona: 'risco',    media: 5.8, sparkline: [7.4, 7.1, 6.9, 6.2, 5.8, 5.6] },
  { id: 'A047', nome: 'Bruno Lima',       turmaId: 'turma-3a',      sedeId: 'sede-centro', vestibularesAlvo: ['ITA'],           ativo: true, perfil: 'regular',  tendencia: 'caindo',  zona: 'cinzenta', media: 5.9, sparkline: [6.9, 6.8, 6.5, 6.2, 5.9] },
  { id: 'A015', nome: 'Carolina Sá',      turmaId: 'turma-3a',      sedeId: 'sede-centro', vestibularesAlvo: ['ITA', 'IME'],    ativo: true, perfil: 'ancora',   tendencia: 'estavel', zona: 'top',      media: 8.3, sparkline: [8.1, 8.2, 8.4, 8.3, 8.3] },
  { id: 'A081', nome: 'Diego Costa',      turmaId: 'turma-3c',      sedeId: 'sede-sul',    vestibularesAlvo: ['IME', 'AFA'],    ativo: true, perfil: 'regular',  tendencia: 'subindo', zona: 'cinzenta', media: 7.2, sparkline: [5.4, 5.6, 6.1, 6.8, 7.2, 7.3] },
  { id: 'A102', nome: 'Eduarda Rocha',    turmaId: 'turma-3online', sedeId: 'sede-online', vestibularesAlvo: ['ITA'],           ativo: true, perfil: 'misterio', tendencia: 'estavel', zona: 'cinzenta', media: 6.4, sparkline: [5.8, 7.2, 5.4, 7.0, 6.4] },
  { id: 'A056', nome: 'Felipe Andrade',   turmaId: 'turma-3b',      sedeId: 'sede-centro', vestibularesAlvo: ['ITA', 'IME'],    ativo: true, perfil: 'ancora',   tendencia: 'subindo', zona: 'top',      media: 8.6, sparkline: [8.0, 8.2, 8.4, 8.5, 8.6] },
  { id: 'A089', nome: 'Gabriela Souza',   turmaId: 'turma-3c',      sedeId: 'sede-sul',    vestibularesAlvo: ['AFA', 'EsPCEx'], ativo: true, perfil: 'regular',  tendencia: 'caindo',  zona: 'risco',    media: 5.2, sparkline: [6.0, 5.8, 5.5, 5.3, 5.2] },
  { id: 'A034', nome: 'Henrique Tavares', turmaId: 'turma-3a',      sedeId: 'sede-centro', vestibularesAlvo: ['ITA'],           ativo: true, perfil: 'regular',  tendencia: 'subindo', zona: 'cinzenta', media: 6.8, sparkline: [6.0, 6.2, 6.5, 6.7, 6.8] },
];

export const alertas = [
  {
    id: 'AL-001',
    categoria: 'QUEDA_RENDIMENTO',
    severidade: 'vermelho',
    tagLabel: 'Queda de rendimento',
    titulo: 'Ana Pereira (A023) caiu 1,8 pontos em 3 simulados',
    subtitulo: 'Concentrado em Física · 3ª B · Centro',
    tempoRelativo: 'há 2 horas',
    href: '#/alunos/A023',
    sparkline: [7.4, 7.1, 6.9, 6.2, 5.8, 5.6],
  },
  {
    id: 'AL-002',
    categoria: 'ZONA_TRANSICAO',
    severidade: 'vermelho',
    tagLabel: 'Saiu da zona',
    titulo: 'Bruno Lima (A047) saiu da zona ITA',
    subtitulo: 'Média 6,8 → 5,9 em 4 simulados',
    tempoRelativo: 'há 8 horas',
    href: '#/alunos/A047',
    sparkline: [6.9, 6.8, 6.5, 6.2, 5.9],
  },
  {
    id: 'AL-003',
    categoria: 'MATERIA_EM_RISCO',
    severidade: 'ambar',
    tagLabel: 'Matéria em risco',
    titulo: 'Física: 3ª A com média 4,9 nos últimos 3 simulados',
    subtitulo: '12 alunos abaixo de 5,0 · histórico 5,8',
    tempoRelativo: 'há 5 horas',
    href: '#/simulados',
    sparkline: [5.8, 5.6, 5.2, 4.9],
  },
  {
    id: 'AL-004',
    categoria: 'PROVA_MAL_CALIBRADA',
    severidade: 'ambar',
    tagLabel: 'Possivelmente mal calibrada',
    titulo: 'Simulado IME Fase 2 — Mai/26 com variância atípica',
    subtitulo: 'Desvio padrão 2,1 vs. histórico 0,9',
    tempoRelativo: 'há 1 dia',
    href: '#/simulados/S08',
    sparkline: [0.9, 1.0, 0.8, 0.9, 2.1],
  },
  {
    id: 'AL-005',
    categoria: 'DIFERENCA_ENTRE_SEDES',
    severidade: 'ambar',
    tagLabel: 'Diferença entre sedes',
    titulo: 'Sede Sul 0,6 ponto acima do Centro em Matemática',
    subtitulo: 'Últimos 4 simulados · p = 0,02',
    tempoRelativo: 'há 1 dia',
    href: '#/ciclos/C3-26',
    sparkline: [0.2, 0.3, 0.5, 0.6],
  },
  {
    id: 'AL-006',
    categoria: 'SUBIDA_ATIPICA',
    severidade: 'verde',
    tagLabel: 'Subida atípica',
    titulo: 'Diego Costa (A081) subiu 1,9 pontos em 3 simulados',
    subtitulo: '3ª C · Sul · entrou na zona Cinzenta de IME',
    tempoRelativo: 'há 2 dias',
    href: '#/alunos/A081',
    sparkline: [5.4, 5.6, 6.1, 6.8, 7.2, 7.3],
  },
  {
    id: 'AL-007',
    categoria: 'PANORAMA_CICLO',
    severidade: 'cinza',
    tagLabel: 'Panorama do ciclo',
    titulo: 'Ciclo 3 fecha amanhã — 38% projetados em zona ITA',
    subtitulo: 'Mesma proporção da coorte 2024 nesse ponto',
    tempoRelativo: 'há 3 dias',
    href: '#/ciclos/C3-26',
    sparkline: [32, 34, 36, 37, 38],
  },
];
