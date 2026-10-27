import type { ContextoDaTela } from '../dominio/contextoDaTela';
import type { GrupoSugestoes } from '../tipos/chat';

// Abertura da conversa por perfil de usuário.
//
// Coordenador e aluno conversam com agentes diferentes: tools diferentes
// (tools/ vs tools_aluno.py) e prompt diferente. A abertura precisa
// acompanhar — antes era uma constante única, e o aluno abria o Mentor lendo
// "Quais alunos estão em risco?".
//
// Duas coisas por perfil:
//
//   SUGESTOES  — exemplos clicáveis, agrupados por INTENÇÃO. Agrupar importa
//                porque 30 tools não cabem em quatro frases soltas: o que o
//                usuário precisa perceber não é a lista, é que existem
//                categorias de coisa que dá pra pedir.
//   CAPACIDADES — a resposta honesta pra "o que você sabe fazer?", em
//                linguagem de usuário. Uma linha por família de tool.
//
// Toda frase aqui tem que corresponder a algo que o perfil realmente
// consegue fazer — sugestão sem tool por trás é promessa que o agente não cumpre.

export const SUGESTOES_COORDENADOR: GrupoSugestoes[] = [
  {
    grupo: 'Encontrar',
    exemplos: [
      'Como está o aluno X?',
      'Quais simulados tiveram no ciclo mais recente?',
    ],
  },
  {
    grupo: 'Diagnosticar',
    exemplos: [
      'Quais alunos estão em risco no momento?',
      'Tem algum alerta pendente?',
      'Em quais matérias devo focar agora?',
    ],
  },
  {
    grupo: 'Comparar',
    exemplos: [
      'Compare o ciclo mais recente com o anterior',
      'Quem tem desempenho parecido com o aluno X?',
    ],
  },
  {
    grupo: 'Gerar',
    exemplos: [
      'Monte o relatório do ciclo atual',
      'Exporte os alunos em zona de risco em CSV',
    ],
  },
  // Os domínios que ganharam tool em 25/10 (docs/43 §4.3): banco de questões
  // (`recorrencia_no_banco`), régua (`cortados_pela_regua`) e as rotinas de
  // bastidor (`estado_do_sync_canvas`, `estado_das_gravacoes`,
  // `lembretes_agendados`, `historico_de_alteracoes`).
  {
    grupo: 'Banco e régua',
    exemplos: [
      'O que mais cai de Química no IME?',
      'Quem a régua da Fase 1 do ITA corta no ciclo atual?',
    ],
  },
  {
    grupo: 'Conferir as rotinas',
    exemplos: [
      'O sync do Canvas está em dia?',
      'Alguma gravação de aula travou?',
      'Quais lembretes saem nesta semana?',
      'Quem alterou notas nos últimos dias?',
    ],
  },
];

export const CAPACIDADES_COORDENADOR: string[] = [
  'Buscar alunos pelo nome ou pela matrícula, e ciclos, simulados e matérias',
  'Ler os alertas e insights que o sistema já sinalizou',
  'Listar alunos por zona, perfil, tendência, turma ou sede',
  'Estatísticas de ciclo, trajetória de aluno e histograma de simulado',
  'Apontar alunos em risco, destaques e matérias problemáticas',
  'Mostrar as questões que a turma mais errou num simulado',
  'Comparar ciclos, alunos ou simulados lado a lado',
  'Achar alunos com desempenho parecido',
  'Montar relatórios de aluno e de ciclo',
  'Gerar gráficos e exportar CSV',
  'Levar você até a ficha de um aluno, ciclo ou simulado',
  'Consultar o banco de provas do ITA e do IME: tópicos do edital, questões e o que mais cai',
  'Explicar as réguas de corte e dizer quem cada uma corta num ciclo',
  'Conferir o sync do Canvas e o que falta publicar de um ciclo',
  'Ver se as gravações de aula subiram ou travaram',
  'Mostrar o histórico de alterações de notas, simulados, ciclos e réguas',
  'Listar os lembretes agendados e a fila de envio',
];

// Cada frase do aluno, com a tool que a cumpre — a regra do topo deste arquivo,
// e a que derrubou "o que mais cai nas provas" enquanto não havia tool para
// isso (docs/43 §1, defeito 3).
export const SUGESTOES_ALUNO: GrupoSugestoes[] = [
  {
    grupo: 'Meu desempenho',
    exemplos: [
      'Como fui no último simulado?', // meu_desempenho_em_simulado
      'Quanto falta para eu chegar à próxima zona?', // minha_zona — com a régua
    ],
  },
  {
    grupo: 'Onde melhorar',
    exemplos: [
      'Quais questões eu errei no último simulado?', // minhas_questoes_erradas
      'O que mais cai de Física no ITA?', // o_que_mais_cai
    ],
  },
  {
    grupo: 'Treinar',
    exemplos: [
      'Me dá questões de cinemática do ITA', // questoes_do_banco
      // "Tem resolução", e não "me explica": a resposta honesta pode ser "não
      // há resolução no banco" (docs/27 §10), e a pergunta já a admite.
      'Tem resolução da questão 5 do ITA 2023, 1ª fase?', // resolucao_oficial
    ],
  },
  {
    grupo: 'Meu ritmo',
    exemplos: [
      'Quando é o próximo simulado?', // minha_agenda_do_ciclo
      'Há quanto tempo estou em sequência?', // meu_streak
    ],
  },
];

/**
 * A abertura do coordenador, ajustada à tela em que ele está.
 *
 * Regra que fecha a porta para promessa vazia, e vale tanto para as sugestões
 * fixas acima quanto para as geradas aqui: **toda frase tem que ter tool por
 * trás.** Uma sugestão que o agente não consegue cumprir é pior que sugestão
 * nenhuma — ensina a não confiar no que ele oferece.
 *
 * Fora das telas cobertas, devolve a lista fixa. Contexto ruim é o mesmo que
 * contexto nenhum, e não vale inventar grupo para preencher espaço.
 *
 * Os grupos fixos que acompanham cada contexto vão por LISTA DE NOMES, e não
 * por exclusão: assim um grupo novo da lista fixa (como os de banco, régua e
 * rotinas) entra na abertura geral sem se pendurar, calado, na ficha de um
 * aluno.
 */
export function sugestoesDoCoordenador(ctx: ContextoDaTela | null): GrupoSugestoes[] {
  const nome = ctx?.entidade?.nome;
  const grupos = (...nomes: string[]) => SUGESTOES_COORDENADOR.filter((g) => nomes.includes(g.grupo));

  if (ctx?.entidade?.tipo === 'aluno' && nome) {
    return [
      {
        grupo: `Sobre ${nome}`,
        exemplos: [
          `Como está o ${nome}?`,
          `Monte o relatório do ${nome}`,
          `Quem tem desempenho parecido com o ${nome}?`,
          `A tendência do ${nome} é de alta ou de queda?`,
        ],
      },
      ...grupos('Diagnosticar', 'Comparar', 'Gerar'),
    ];
  }

  if (ctx?.entidade?.tipo === 'ciclo' && nome) {
    return [
      {
        grupo: `Sobre ${nome}`,
        exemplos: [
          `Como foi o ${nome}?`,
          `Em quais matérias focar depois do ${nome}?`,
          `Compare o ${nome} com o ciclo anterior`,
          `Quem está em risco no ${nome}?`,
        ],
      },
      ...grupos('Gerar'),
    ];
  }

  if (ctx?.entidade?.tipo === 'simulado' && nome) {
    return [
      {
        grupo: `Sobre ${nome}`,
        exemplos: [
          `Como foi o ${nome}?`,
          `Mostre o histograma do ${nome}`,
          `Quem ficou abaixo do corte no ${nome}?`,
        ],
      },
      ...grupos('Gerar'),
    ];
  }

  if (ctx?.tela === 'painel' && ctx.recorte?.cicloId) {
    return [
      {
        grupo: 'Sobre o que está na tela',
        exemplos: [
          'Quem está em risco neste recorte?',
          'Em quais matérias devo focar agora?',
          'Tem algum alerta pendente?',
        ],
      },
      ...grupos('Encontrar', 'Comparar', 'Gerar'),
    ];
  }

  return SUGESTOES_COORDENADOR;
}

// ⚠️ "Os ASSUNTOS que você mais erra" saiu em 25/10, e não por estilo: as
// questões dos simulados não têm assunto (`questao.assunto` vazio, registro.ts
// · `meusErros`), e nenhuma tool sabe dizer isso. Volta quando o Sprint 6
// classificar as questões de simulado.
export const CAPACIDADES_ALUNO: string[] = [
  'Resumir como você está: últimas notas, zona e sequência',
  'Dizer sua zona e quanto falta para a próxima, sempre com o nome da régua',
  'Mostrar suas notas e como você foi em cada simulado',
  'Mostrar como a turma foi numa prova, sem a nota de nenhum colega',
  'Acompanhar sua evolução ao longo dos ciclos',
  'Apontar as questões que você errou num simulado',
  'Contar o que mais cai nas provas do ITA e do IME',
  'Buscar questões de provas passadas por assunto',
  'Trazer a resolução oficial de uma questão, dizendo de quem ela é',
  'Dizer quanto do banco de provas você já marcou como feito',
  'Dar a missão do dia e dizer quando é o próximo simulado',
  'Resumir o que o sistema concluiu sobre o seu ciclo',
  'Ver sua sequência de participação',
];
