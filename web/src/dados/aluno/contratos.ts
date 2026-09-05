// Os tipos da área do aluno — o contrato que as telas enxergam.
//
// Duas metades, e a divisão é a mesma do `registro.ts`:
//
//   1. O que a API já devolve vem de `tipos/aluno.ts` e `tipos/banco.ts`, que
//      espelham os schemas Pydantic. Reexportado aqui, e não redeclarado: um
//      segundo tipo para a mesma resposta seria uma segunda forma de errar.
//   2. O que ainda não existe nasce aqui. São os tipos de docs/26 (jogo),
//      docs/28 (treino) e docs/29 (as rotas que faltam) — e os nomes foram
//      acordados no brief, então não os renomeie por gosto: eles são o que faz
//      trocar mock por `fetch` custar uma linha.
//
// Nenhum tipo daqui carrega valor. Dado falso mora em `mocks.ts`, e só lá.

import type { Zona } from '../../tipos/dominio';

export type {
  DetalheSimuladoAluno,
  EvolucaoAluno,
  GruposComparacao,
  InsightDoAluno,
  QuestaoDoAluno,
  QuestoesDoSimulado,
  ResultadoQuestao,
  SimuladoDoAluno,
} from '../../tipos/aluno';

export type {
  BlocoTaxonomia,
  ColecaoBanco,
  Confianca,
  EstatisticasBanco,
  EstudoQuestao,
  FiltrosBanco,
  Lista,
  ListaResumo,
  MateriaBanco,
  PaginaQuestoes,
  ParDeProgresso,
  ProgressoDoAluno,
  ProgressoPorAno,
  ProgressoPorAssunto,
  ProgressoPorMateria,
  QuestaoVestibular,
  RecorrenciaTopico,
  TaxonomiaMateria,
  TopicoDaQuestao,
  VestibularBanco,
} from '../../tipos/banco';

// `Aluno` e `Zona` vêm de `dominio.ts`, que espelha `schemas/domain.py`. Uma
// segunda declaração de `Zona` do lado do aluno seria uma segunda forma de
// errar — a régua é a mesma para os dois lados, e é esse o ponto de docs/24 §2.
export type { Aluno, Zona } from '../../tipos/dominio';

// ─── Perfil do aluno ─────────────────────────────────────────────────────

/**
 * Onde o aluno está na régua, e quanto falta para a próxima zona.
 *
 * ⚠️ `regua` não é enfeite. docs/24 §2: o rótulo nunca pode aparecer sem a
 * distância e sem o nome do critério que o produziu — "risco" sem contra qual
 * corte é só a má notícia.
 */
export interface ZonaEDistancia {
  zona: Zona;
  /** Média recente do aluno, na mesma escala do corte. */
  media: number;
  /**
   * A nota que separa a zona atual da próxima, e `null` em `top`.
   *
   * ⚠️ `top` é TERMINAL: não existe zona acima, e inventar um alvo além do topo
   * seria inventar régua. A tela mostra o corte que ele já passou (docs/36 §1.4).
   */
  corteProximaZona: number | null;
  /**
   * O corte que o aluno JÁ cruzou, e `null` em `risco` — onde não cruzou
   * nenhum. É o que a escada usa para medir FOLGA em vez de falta quando ele
   * está no topo: lá não há próxima fronteira, mas há a que ficou para trás.
   */
  corteAtual: number | null;
  /** `corteProximaZona − media`, já positivo. `null` em `top`, junto do corte. */
  distancia: number | null;
  /** Onde a distância se fecha mais barato — "Química". */
  materiaMaisCurta: string | null;
  /** O nome da régua: "Tio Leo", "ITA — Fase 1"… (`criterio_classificacao`, 0023). */
  regua: string;
  /**
   * As matérias contra o corte DESTA régua — a mesma resposta traz as duas
   * fontes (`zonaEDistancia` e `cortePorMateria`) porque separá-las convidaria
   * duas réguas diferentes na mesma tela.
   */
  materias: MateriaContraCorte[];
}

/**
 * Uma matéria contra o seu corte, para as barras de "onde você está".
 *
 * O corte é por matéria porque ele É por matéria: 4,0 no geral, e 5,0 no
 * Inglês da Fase 1 do ITA, que é o único eliminatório.
 */
export interface MateriaContraCorte {
  materia: string;
  nota: number;
  corte: number;
  /** `true` no Inglês da Fase 1 do ITA — a tela precisa dizer por quê. */
  eliminatoria: boolean;
}

// ─── Trajetória e mapa de calor ──────────────────────────────────────────
// Duas rotas prontas desde sempre e sem tela nenhuma até agora (docs/29 §A.5).
// Os tipos nascem aqui porque `api.ts` as devolvia como `unknown`.
//
// ⚠️ `ArquivoDoSimulado` morava aqui e saiu em 04/09 com o botão "Abrir a prova"
// e com a rota que o servia (docs/35 §8b).

/** Um ponto de `GET /me/trajetoria`, já em escala 0–10. */
export interface PontoDaTrajetoria {
  simuladoId: string | null;
  simulado: string | null;
  dataAplicacao: string | null;
  materiaId: string | null;
  tipo: string | null;
  pontuacao: number;
}

export interface SimuladoDoHeatmap {
  id: string;
  nome: string | null;
  rotulo: string | null;
  dataAplicacao: string | null;
  cicloId: string | null;
  cicloOrdem: number | null;
  cicloNome: string | null;
  vestibularAlvo: string | null;
  fase: string | null;
}

/** `GET /me/heatmap` — matéria × simulado. Célula ausente é ausência de nota. */
export interface HeatmapDoAluno {
  materias: string[];
  simulados: SimuladoDoHeatmap[];
  celulas: Array<{ materia: string; simuladoId: string; pontuacao: number }>;
}

// ─── Agenda ──────────────────────────────────────────────────────────────

/**
 * O próximo simulado. docs/29 §A.1: `evento_agenda` já manda e-mail ao aluno na
 * véspera desde a Sprint 1 — o e-mail sabe, a tela não.
 */
export interface ProximoSimulado {
  id: string;
  rotulo: string;
  /** ISO `YYYY-MM-DD`. */
  data: string;
  vestibular: string | null;
  fase: number | null;
  /** Data do simulado anterior, para a barra medir o intervalo inteiro. */
  dataAnterior: string | null;
}

// ─── Sequência e presença ────────────────────────────────────────────────

/** Um quadrado da corrente: um simulado do ciclo. */
export interface EloDaCorrente {
  simuladoId: string | null;
  rotulo: string;
  data: string | null;
  /**
   * `true` compareceu, `false` faltou (quadrado vazado), `null` ainda não
   * aconteceu (quadrado anelado).
   */
  presente: boolean | null;
}

/**
 * Um ciclo da corrente, com os elos que ele teve.
 *
 * ⚠️ Era `presencas: boolean[]` enquanto foi mock, e a Jornada tinha de
 * inventar o rótulo pela POSIÇÃO ("P1", "P2"…). Com dado real cada elo traz o
 * próprio rótulo e a própria data: o quadrado passa a saber que prova ele é.
 */
export interface CicloDePresenca {
  ciclo: string;
  elos: EloDaCorrente[];
}

/**
 * Simulados consecutivos sem faltar (docs/26 §4). Nunca dias — não existe
 * atividade diária verificável no SAS.
 */
export interface Sequencia {
  /** A sequência corrente. */
  simulados: number;
  /** O recorde, guardado separado: ele sobrevive à quebra. */
  melhor: number;
  /** Um elo por simulado do ciclo corrente, mais o próximo. */
  corrente: EloDaCorrente[];
}

// ─── XP ──────────────────────────────────────────────────────────────────

/**
 * ⚠️ XP é sempre DERIVADO de `nota`, nunca saldo gravado (docs/26 §3, 29 §B.1).
 * Nota é corrigida e simulado é anulado; recalcular faz a correção se propagar
 * sozinha, e saldo faria cada correção virar estorno manual.
 */
export interface Xp {
  /** O ano letivo inteiro. */
  total: number;
  /** Só o ciclo corrente — é o número que a liga usa. */
  ciclo: number;
}

/** Uma linha do extrato. `xp: 0` continua aparecendo, vazada. */
export interface LinhaExtrato {
  rotulo: string;
  xp: number;
  /** O que foi verificado: "6,8 · corte 4,0". */
  evidencia: string;
}

export interface ExtratoXp {
  simuladoId: string;
  simuladoNome: string;
  linhas: LinhaExtrato[];
  total: number;
  posicaoLiga: number | null;
}

// ─── Estudo ──────────────────────────────────────────────────────────────

/**
 * Um tópico do edital com importância e meu acerto (docs/24 §4 e §4.5).
 *
 * `importancia` é a fatia da prova ponderada por recência com meia-vida de 5
 * anos, não a contagem bruta — o número se lê sozinho: "vale 7% da prova".
 */
export interface AssuntoPrioritario {
  topicoCodigo: string;
  nome: string;
  materia: string;
  /** 0..1 — fatia da prova, ponderada por recência. */
  importancia: number;
  /** 0..1. */
  meuAcerto: number;
  /** Positivo sobe na banca, negativo cai. Exposto separado do índice. */
  tendencia: number;
  /** Fatia média nos 5 anos mais recentes e nos 5 anteriores — a tendência crua. */
  fatiaRecente: number;
  fatiaAntiga: number;
  /** Base amostral. Abaixo de 3 não entra no ranking, mas nunca some. */
  nQuestoes: number;
}

/**
 * A missão da aba Hoje — `GET /missao/hoje`, espelha
 * `api/app/banco/missao.py::MissaoDoDia`.
 *
 * ⚠️ `topicoCodigo` é o ENDEREÇO (a fila de treino o usa para consultar o
 * acervo) e `nome` é a ETIQUETA que a tela imprime. Os dois vêm da mesma linha
 * de `topico_taxonomia`, no servidor: pareá-los à mão foi o bug de docs/35 §9.
 *
 * Não é personalizada — é o mesmo assunto para toda a turma, sorteado pela data
 * (docs/35 §9.3). Foi a personalização, `importância × (1 − meu acerto)` de
 * docs/24 §4.5, que a prendia ao Sprint 6.
 */
export interface MissaoDoDia {
  topicoCodigo: string;
  nome: string;
  materia: string;
  /** Sempre 10 hoje. A tela usa este número para dimensionar a sessão. */
  quantidade: number;
  /** Incidência no acervo — nunca acerto do aluno, que num desafio igual para
   *  todos não existe: "7% das questões objetivas de Física…". */
  razao: string;
}

/** Uma questão que o aluno errou, agregada por todos os simulados (docs/29 §A.3). */
export interface ErroTransversal {
  simuladoId: string;
  simuladoRotulo: string;
  posicao: number | null;
  materia: string | null;
  assunto: string | null;
  emBranco: boolean;
}

// ─── Treino ──────────────────────────────────────────────────────────────

/**
 * De onde a fila de treino veio. Vai na URL (`/treino/prioridade`) porque a
 * tela tem de saber dizer POR QUE são essas questões e não outras.
 */
export type OrigemTreino = 'prioridade' | 'erros' | 'lista' | 'assunto';

export interface RazaoDaFila {
  origem: OrigemTreino;
  /** "Termodinâmica", "Suas questões erradas", o título da lista. */
  titulo: string;
  /** A frase que explica a escolha, em uma linha. */
  explicacao: string;
}

/**
 * Resultado de uma questão dentro da sessão.
 *
 * ⚠️ Não existe no banco: `questao_estudo_aluno` só tem `resolvida` e
 * `anotacao`. docs/28 §3 pede `alternativa_escolhida` e `acertou`, e é a única
 * fonte de acerto por assunto que NÃO depende do Sprint 6.
 *
 * ⚠️ E não muda a diretriz do verificável: isto alimenta o plano de estudo,
 * nunca o XP nem a liga. Treino informa; prova paga.
 */
export interface RespostaNoTreino {
  questaoId: string;
  alternativaEscolhida: string | null;
  acertou: boolean | null;
}

export interface ResumoDoTreino {
  total: number;
  acertos: number;
  /** Os assuntos que apareceram, com quantas de cada. */
  assuntos: Array<{ nome: string; total: number; acertos: number }>;
  /** O que isso mudou no plano. Nunca um número de XP. */
  efeitoNoPlano: string;
}

// ─── Liga e conquistas ───────────────────────────────────────────────────

/**
 * Uma linha da liga.
 *
 * ⚠️ ANÔNIMA (docs/26 §5.1): sem nome, sem apelido, sem inicial. Cada
 * participante é um glifo geométrico estável no ciclo. É restrição de
 * privacidade de menor, não estética.
 */
export interface PosicaoLiga {
  posicao: number;
  /** O glifo — um caractere geométrico, jamais derivado do nome. */
  glifo: string;
  xpCiclo: number;
  euMesmo: boolean;
}

export interface Liga {
  nome: string;
  /** Quantos participantes no grupo (~30, cruzando turma e sede). */
  participantes: number;
  /** Quantos sobem e quantos descem quando o ciclo fecha. */
  sobem: number;
  descem: number;
  posicoes: PosicaoLiga[];
  /** XP que falta para entrar na zona de subida. */
  faltaParaSubir: number | null;
}

export interface Conquista {
  chave: string;
  titulo: string;
  /** A evidência, quando conquistada: "CICLO 3". */
  detalhe: string;
  conquistada: boolean;
  /** 0..1, só nas travadas. */
  progresso?: number;
  progressoRotulo?: string;
}

/**
 * O alvo do ciclo. Quem define é o SISTEMA e a meta é PRESENÇA (docs/36 §1.5) —
 * é o que fecha a decisão aberta de docs/24 §9.1 sem inventar produto: dá para
 * verificar com `nota.presente`, e não depende do XP, que está travado no
 * backtest de docs/29 §H.
 *
 * `alvo` sai do CALENDÁRIO do ciclo, não do que o aluno fez: contar só o que
 * ele já viu faria a meta andar junto com ele e parecer sempre cumprida.
 */
export interface MetaDoCiclo {
  alvo: number;
  feitos: number;
  rotulo: string;
}

/** O cartão "de quem já passou". Nunca citação inventada — só a afordância. */
export interface Depoimento {
  titulo: string;
  chamada: string;
}
