// TODO o dado falso da área do aluno. Um arquivo só, e é o ponto do arquivo.
//
// ⚠️ Nenhuma tela importa daqui. As telas importam de `index.ts`, e um teste
// (`costura.test.ts`) falha se alguma passar por cima. A razão é operacional,
// não estética: um literal falso dentro de um `.tsx` é uma integração que
// ninguém percebe que falta.
//
// ── O aluno do mock é UM aluno, e os números fecham ──────────────────────
//
// Um mock incoerente esconde bug de layout: se a soma do extrato não bate com
// o total, não dá para saber se o erro é do componente ou do dado. Então:
//
//   · Ciclo 4 (corrente) tem cinco simulados, P1 a P5, e o aluno compareceu aos
//     cinco — por isso a sequência é 12 e não quebra.
//   · O P5 é o último corrigido: 6,4, delta +0,7, 47º de 312, percentil 85.
//   · As cinco matérias do ciclo somam o extrato do P5 em 628 XP, item a item.
//   · 138 + 154 + 128 + 192 + 628 = 1.240 = o XP do ciclo, que é exatamente o
//     que a liga usa; o total do ano é 2.850.
//   · Na liga o 5º tem 1.502, e 1.502 − 1.240 = 262, que é o que falta subir.
//   · A média recente é 6,8; o corte do topo é 8,0; a distância é 1,2, e ela se
//     fecha mais barato em Química, que é a matéria mais abaixo do corte.
//   · Química (3,2) está 0,8 abaixo do corte de 4,0 e Inglês (4,6) está 0,4
//     abaixo do corte de 5,0 — o Inglês da Fase 1 do ITA é o único eliminatório.
//   · Termodinâmica lidera o plano porque 0,07 × (1 − 0,41) é o maior produto
//     da lista, que é a fórmula de docs/24 §4.5. A ordem não foi escolhida.
//
// Mexer num número aqui é mexer em todos os que dependem dele. O comentário
// acima é o mapa das dependências.

import type {
  AssuntoPrioritario,
  Conquista,
  Depoimento,
  ErroTransversal,
  ExtratoXp,
  Liga,
  MateriaContraCorte,
  MissaoDoDia,
  ProximoSimulado,
  QuestaoVestibular,
  ResumoDoTreino,
  Sequencia,
  Xp,
  ZonaEDistancia,
} from './contratos';

/** O mock devolve Promise, nunca objeto solto: é o que faz a assinatura do
 *  hook não mudar quando o `fetch` entrar no lugar. */
function entregar<T>(valor: T): Promise<T> {
  return Promise.resolve(valor);
}

/**
 * Datas relativas a hoje, e não fixas no calendário: com data fixa a contagem
 * regressiva viraria negativa depois de setembro de 2026 e o mock morreria
 * sozinho, que é como mock passa a mentir sem ninguém notar.
 */
function emDias(dias: number): string {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  d.setDate(d.getDate() + dias);
  return d.toISOString().slice(0, 10);
}

// ─── Régua de corte ──────────────────────────────────────────────────────

/** 4,0 por matéria; 5,0 no Inglês da Fase 1 do ITA, o único eliminatório. */
export const CORTE_PADRAO = 4;
export const CORTE_INGLES_ITA_F1 = 5;

export const MATERIAS_CONTRA_CORTE: MateriaContraCorte[] = [
  { materia: 'Matemática', nota: 6.8, corte: CORTE_PADRAO, eliminatoria: false },
  { materia: 'Física', nota: 7.4, corte: CORTE_PADRAO, eliminatoria: false },
  { materia: 'Química', nota: 3.2, corte: CORTE_PADRAO, eliminatoria: false },
  { materia: 'Português', nota: 5.9, corte: CORTE_PADRAO, eliminatoria: false },
  { materia: 'Inglês', nota: 4.6, corte: CORTE_INGLES_ITA_F1, eliminatoria: true },
];

export const ZONA: ZonaEDistancia = {
  zona: 'cinzenta',
  media: 6.8,
  corteProximaZona: 8,
  distancia: 1.2,
  materiaMaisCurta: 'Química',
  regua: 'Tio Leo',
};

// ─── Agenda e sequência ──────────────────────────────────────────────────

export function proximoSimulado(): ProximoSimulado {
  return {
    id: 'mock-c5-p1',
    rotulo: 'Ciclo 5 · P1',
    data: emDias(12),
    vestibular: 'ITA',
    fase: 1,
    dataAnterior: emDias(-11),
  };
}

export function sequencia(): Sequencia {
  return {
    simulados: 12,
    melhor: 12,
    corrente: [
      { simuladoId: 'mock-c4-p1', rotulo: 'P1', data: emDias(-70), presente: true },
      { simuladoId: 'mock-c4-p2', rotulo: 'P2', data: emDias(-56), presente: true },
      { simuladoId: 'mock-c4-p3', rotulo: 'P3', data: emDias(-42), presente: true },
      { simuladoId: 'mock-c4-p4', rotulo: 'P4', data: emDias(-25), presente: true },
      { simuladoId: 'mock-c4-p5', rotulo: 'P5', data: emDias(-11), presente: true },
      { simuladoId: null, rotulo: 'P1', data: emDias(12), presente: null },
    ],
  };
}

/**
 * A falta vive aqui, e não na corrente do ciclo corrente, porque a sequência do
 * aluno é 12 — pôr um quadrado vazado no ciclo 4 contradiria os dois números na
 * mesma tela. O ciclo 2 é onde a forma do quadrado vazado se vê.
 */
export const CICLOS_ANTERIORES: Array<{ ciclo: string; presencas: boolean[] }> = [
  { ciclo: 'Ciclo 1', presencas: [true, true, false, true, true] },
  { ciclo: 'Ciclo 2', presencas: [true, false, true, true, true] },
  { ciclo: 'Ciclo 3', presencas: [true, true, true, true, true] },
  { ciclo: 'Ciclo 4', presencas: [true, true, true, true, true] },
];

// ─── XP ──────────────────────────────────────────────────────────────────

/** Um bloco por simulado. Somam 1.240 — o XP do ciclo, que é o da liga. */
export const XP_POR_SIMULADO: Array<{ rotulo: string; xp: number }> = [
  { rotulo: 'P1', xp: 138 },
  { rotulo: 'P2', xp: 154 },
  { rotulo: 'P3', xp: 128 },
  { rotulo: 'P4', xp: 192 },
  { rotulo: 'P5', xp: 628 },
];

export const XP: Xp = {
  // 1.610 dos ciclos 1 a 3, mais os 1.240 do ciclo 4.
  total: 2850,
  ciclo: 1240,
};

/**
 * O extrato do P5, e ele é a soma exata de `XP_POR_SIMULADO[4]`.
 *
 * As linhas com `xp: 0` NUNCA somem (docs/26 §3): é onde o aluno entende o que
 * faltou, e é a única tela que explica a régua de corte sem parecer boletim.
 * O ranking paga só o nível mais alto — o "Top 10" aparece zerado para mostrar
 * qual é o degrau seguinte, não porque some com o Top 50.
 */
export const EXTRATO_XP: ExtratoXp = {
  simuladoId: 'mock-c4-p5',
  simuladoNome: 'Ciclo 4 · ITA · P5',
  total: 628,
  posicaoLiga: 6,
  linhas: [
    { rotulo: 'Compareceu', xp: 100, evidencia: 'presença confirmada' },
    { rotulo: 'Matemática acima do corte', xp: 40, evidencia: '6,8 · corte 4,0' },
    { rotulo: 'Física acima do corte', xp: 40, evidencia: '7,4 · corte 4,0' },
    { rotulo: 'Química abaixo do corte', xp: 0, evidencia: '3,2 · faltaram 0,8' },
    { rotulo: 'Português acima do corte', xp: 40, evidencia: '5,9 · corte 4,0' },
    { rotulo: 'Inglês abaixo do corte', xp: 0, evidencia: '4,6 · corte 5,0 · eliminatória' },
    { rotulo: 'Passou na régua completa', xp: 0, evidencia: 'critério Tio Leo · 2 matérias abaixo' },
    { rotulo: 'Superou seu padrão', xp: 108, evidencia: '+0,7 acima da sua média' },
    { rotulo: 'Sua melhor nota do ano', xp: 150, evidencia: '6,4 · a anterior era 5,8' },
    { rotulo: 'Top 50 da escola', xp: 150, evidencia: '47º de 312' },
    { rotulo: 'Top 10 da escola', xp: 0, evidencia: '47º de 312 · faltam 37 posições' },
  ],
};

// ─── Liga ────────────────────────────────────────────────────────────────

/**
 * ⚠️ O glifo é uma FORMA, nunca uma letra e nunca derivado do nome (docs/26
 * §5.1). Quem desenha é `pecas/Glifo.tsx`, com SVG nosso — o valor aqui é só o
 * nome da forma.
 */
export const LIGA: Liga = {
  nome: 'Liga Ouro',
  participantes: 34,
  sobem: 5,
  descem: 5,
  faltaParaSubir: 262,
  posicoes: [
    { posicao: 1, glifo: 'hexagono', xpCiclo: 2104, euMesmo: false },
    { posicao: 2, glifo: 'losango', xpCiclo: 1980, euMesmo: false },
    { posicao: 3, glifo: 'triangulo', xpCiclo: 1833, euMesmo: false },
    { posicao: 4, glifo: 'quadrado', xpCiclo: 1671, euMesmo: false },
    { posicao: 5, glifo: 'circulo', xpCiclo: 1502, euMesmo: false },
    { posicao: 6, glifo: 'estrela', xpCiclo: 1240, euMesmo: true },
    { posicao: 7, glifo: 'anel', xpCiclo: 1188, euMesmo: false },
    { posicao: 8, glifo: 'pentagono', xpCiclo: 1094, euMesmo: false },
    { posicao: 9, glifo: 'cruz', xpCiclo: 1020, euMesmo: false },
    { posicao: 10, glifo: 'meiaLua', xpCiclo: 964, euMesmo: false },
  ],
};

// ─── Conquistas ──────────────────────────────────────────────────────────

/**
 * Só o que se verifica (docs/26 §6). Saiu "Top 15%", que premiava posição; o
 * que entra é presença, cruzar o corte, melhor nota do ano e a régua completa.
 */
export const CONQUISTAS: Conquista[] = [
  {
    chave: 'cruzou_o_corte',
    titulo: 'Cruzou o corte',
    detalhe: 'CICLO 3',
    conquistada: true,
  },
  {
    chave: 'doze_sem_faltar',
    titulo: '12 simulados sem faltar',
    detalhe: 'SEU RECORDE',
    conquistada: true,
  },
  {
    chave: 'melhor_do_ano',
    titulo: 'Sua melhor nota do ano',
    detalhe: 'FÍSICA 7,4 · P5',
    conquistada: true,
  },
  {
    chave: 'regua_completa',
    titulo: 'Passar na régua completa',
    detalhe: 'QUÍMICA E INGLÊS ABAIXO',
    conquistada: false,
    progresso: 0.6,
    progressoRotulo: '3 de 5 matérias',
  },
];

export const DEPOIMENTO: Depoimento = {
  titulo: 'De quem já passou',
  chamada: 'Aprovados do ITM contam como organizaram o estudo entre um simulado e outro',
};

// ─── Plano de estudo ─────────────────────────────────────────────────────

/**
 * A ordem NÃO foi escolhida: é `importância × (1 − meu acerto)` (docs/24 §4.5),
 * e por isso Termodinâmica (0,07 × 0,59) vem antes de Estequiometria
 * (0,06 × 0,62) mesmo tendo acerto maior.
 *
 * A última entrada tem `nQuestoes: 2` de propósito: docs/24 §4.4 manda mostrar
 * sempre o `n` e manter fora do "priorize isto" quem tem menos de 3 — mas nunca
 * sumir com o tópico, porque "não caiu em oito anos" é informação de estudo.
 */
export const ASSUNTOS: AssuntoPrioritario[] = [
  {
    topicoCodigo: '7.2',
    nome: 'Termodinâmica',
    materia: 'Física',
    importancia: 0.07,
    meuAcerto: 0.41,
    tendencia: 0.018,
    fatiaRecente: 0.07,
    fatiaAntiga: 0.052,
    nQuestoes: 17,
  },
  {
    topicoCodigo: '3.1',
    nome: 'Estequiometria',
    materia: 'Química',
    importancia: 0.06,
    meuAcerto: 0.38,
    tendencia: -0.011,
    fatiaRecente: 0.06,
    fatiaAntiga: 0.071,
    nQuestoes: 13,
  },
  {
    topicoCodigo: '5.4',
    nome: 'Análise combinatória',
    materia: 'Matemática',
    importancia: 0.05,
    meuAcerto: 0.52,
    tendencia: 0.009,
    fatiaRecente: 0.05,
    fatiaAntiga: 0.041,
    nQuestoes: 21,
  },
  {
    topicoCodigo: '4.1',
    nome: 'Eletrostática',
    materia: 'Física',
    importancia: 0.05,
    meuAcerto: 0.64,
    tendencia: -0.004,
    fatiaRecente: 0.05,
    fatiaAntiga: 0.054,
    nQuestoes: 11,
  },
  {
    topicoCodigo: '6.3',
    nome: 'Geometria analítica',
    materia: 'Matemática',
    importancia: 0.04,
    meuAcerto: 0.7,
    tendencia: 0.012,
    fatiaRecente: 0.04,
    fatiaAntiga: 0.028,
    nQuestoes: 20,
  },
  {
    topicoCodigo: '9.5',
    nome: 'Radioatividade',
    materia: 'Química',
    importancia: 0.03,
    meuAcerto: 0.5,
    tendencia: -0.021,
    fatiaRecente: 0.008,
    fatiaAntiga: 0.029,
    nQuestoes: 2,
  },
];

export const MISSAO: MissaoDoDia = {
  topicoCodigo: '7.2',
  nome: 'Termodinâmica',
  materia: 'Física',
  quantidade: 12,
  razao: 'Cai em 7% da prova do ITA. Você acerta 41%.',
};

/**
 * As questões erradas de todos os simulados. Trinta e quatro no total — é o
 * número que o cartão "Seus erros" mostra na aba Estudar.
 */
export const ERROS: ErroTransversal[] = Array.from({ length: 34 }, (_, i) => {
  const fontes = [
    { simuladoId: 'mock-c4-p5', rotulo: 'Ciclo 4 · P5', materia: 'Química', assunto: 'Estequiometria' },
    { simuladoId: 'mock-c4-p5', rotulo: 'Ciclo 4 · P5', materia: 'Física', assunto: 'Termodinâmica' },
    { simuladoId: 'mock-c4-p4', rotulo: 'Ciclo 4 · P4', materia: 'Matemática', assunto: 'Análise combinatória' },
    { simuladoId: 'mock-c4-p3', rotulo: 'Ciclo 4 · P3', materia: 'Química', assunto: 'Equilíbrio químico' },
    { simuladoId: 'mock-c4-p3', rotulo: 'Ciclo 4 · P3', materia: 'Física', assunto: 'Eletrostática' },
  ];
  const f = fontes[i % fontes.length];
  return {
    simuladoId: f.simuladoId,
    simuladoRotulo: f.rotulo,
    posicao: (i % 20) + 1,
    materia: f.materia,
    assunto: f.assunto,
    // Uma em cada sete é em branco — o suficiente para a legenda ter o que mostrar.
    emBranco: i % 7 === 3,
  };
});

// ─── Treino ──────────────────────────────────────────────────────────────

/**
 * O resumo é calculado a partir do que o aluno de fato respondeu na sessão, e
 * não fixo: um resumo que ignora as respostas seria mock dentro de tela real.
 * O que é mock aqui é só a frase de efeito no plano — ela depende do Sprint 6.
 */
export function resumoDoTreino(
  respostas: Array<{ acertou: boolean | null; assunto: string | null }>,
): ResumoDoTreino {
  const total = respostas.length;
  const acertos = respostas.filter((r) => r.acertou === true).length;

  const porAssunto = new Map<string, { nome: string; total: number; acertos: number }>();
  for (const r of respostas) {
    const nome = r.assunto || 'Sem classificação';
    const atual = porAssunto.get(nome) ?? { nome, total: 0, acertos: 0 };
    atual.total += 1;
    if (r.acertou === true) atual.acertos += 1;
    porAssunto.set(nome, atual);
  }

  const pior = [...porAssunto.values()].sort(
    (a, b) => a.acertos / a.total - b.acertos / b.total,
  )[0];

  return {
    total,
    acertos,
    assuntos: [...porAssunto.values()],
    efeitoNoPlano: pior
      ? `${pior.nome} subiu no seu plano — você acertou ${pior.acertos} de ${pior.total}.`
      : 'Seu plano segue igual.',
  };
}

/** A explicação de cada origem de fila. É o "por que estou vendo isto". */
export const RAZAO_DA_FILA: Record<string, string> = {
  prioridade:
    'Escolhidas por quanto o assunto cai na prova e quanto você erra nele. Cobre Matemática, Física e Química.',
  erros: 'As questões que você errou ou deixou em branco nos simulados.',
  lista: 'As questões que você separou na sua lista, na ordem em que você as pôs.',
  assunto: 'Todas as questões do acervo sobre este assunto, das mais recentes para as mais antigas.',
};

/**
 * Ordena as questões reais do banco para a sessão de treino.
 *
 * ⚠️ As QUESTÕES são reais (`/banco/questoes`); o que é mock é o CRITÉRIO — sem
 * `acertoPorAssunto` não há como pesar por `importância × (1 − meu acerto)`.
 * Antes do Sprint 6 a régua cai para "matéria mais distante do corte", que é o
 * que docs/28 §3 manda fazer no lugar.
 */
export function ordenarFilaDeTreino(questoes: QuestaoVestibular[]): QuestaoVestibular[] {
  const pesoDoAssunto = new Map(ASSUNTOS.map((a) => [a.topicoCodigo, a.importancia * (1 - a.meuAcerto)]));
  const distanciaDoCorte = new Map(
    MATERIAS_CONTRA_CORTE.map((m) => [m.materia, Math.max(0, m.corte - m.nota)]),
  );

  const peso = (q: QuestaoVestibular) => {
    const porTopico = q.topicos.reduce(
      (maior, t) => Math.max(maior, pesoDoAssunto.get(t.codigo) ?? 0),
      0,
    );
    return porTopico + (distanciaDoCorte.get(q.materia) ?? 0);
  };

  // Dissertativa nunca entra numa fila de objetivas: 420 das questões são de 2ª
  // fase e não têm alternativa nem gabarito por natureza (docs/28 §3, regra 3).
  return questoes
    .filter((q) => !q.dissertativa)
    .slice()
    .sort((a, b) => peso(b) - peso(a));
}

// ─── Os hooks-fonte: tudo daqui devolve Promise ──────────────────────────

export const buscarSequencia = () => entregar(sequencia());
export const buscarProximoSimulado = () => entregar(proximoSimulado());
export const buscarZona = () => entregar(ZONA);
export const buscarMateriasContraCorte = () => entregar(MATERIAS_CONTRA_CORTE);
export const buscarXp = () => entregar(XP);
export const buscarExtratoXp = () => entregar(EXTRATO_XP);
export const buscarLiga = () => entregar(LIGA);
export const buscarConquistas = () => entregar(CONQUISTAS);
export const buscarDepoimento = () => entregar(DEPOIMENTO);
export const buscarAssuntos = () => entregar(ASSUNTOS);
export const buscarMissao = () => entregar(MISSAO);
export const buscarErros = () => entregar(ERROS);
export const buscarCiclosAnteriores = () => entregar(CICLOS_ANTERIORES);
export const buscarMetaDoCiclo = () =>
  entregar({ alvo: 5, feitos: 5, rotulo: 'Comparecer aos 5 simulados do ciclo' });
