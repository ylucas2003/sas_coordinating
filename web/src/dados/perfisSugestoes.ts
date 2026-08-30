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
];

export const CAPACIDADES_COORDENADOR: string[] = [
  'Buscar alunos, ciclos, simulados e matérias pelo nome',
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
];

export const SUGESTOES_ALUNO: GrupoSugestoes[] = [
  {
    grupo: 'Meu desempenho',
    exemplos: [
      'Como fui no último simulado?',
      'Minhas notas estão melhorando?',
    ],
  },
  {
    grupo: 'Onde melhorar',
    exemplos: [
      'Quais questões eu mais errei?',
      'No que eu devo focar agora?',
    ],
  },
  {
    grupo: 'Meu ritmo',
    exemplos: [
      'Há quanto tempo estou em sequência?',
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
 */
export function sugestoesDoCoordenador(ctx: ContextoDaTela | null): GrupoSugestoes[] {
  const nome = ctx?.entidade?.nome;

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
      ...SUGESTOES_COORDENADOR.filter((g) => g.grupo !== 'Encontrar'),
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
      ...SUGESTOES_COORDENADOR.filter((g) => g.grupo === 'Gerar'),
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
      ...SUGESTOES_COORDENADOR.filter((g) => g.grupo === 'Gerar'),
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
      ...SUGESTOES_COORDENADOR.filter((g) => g.grupo !== 'Diagnosticar'),
    ];
  }

  return SUGESTOES_COORDENADOR;
}

export const CAPACIDADES_ALUNO: string[] = [
  'Mostrar suas notas e como você foi em cada simulado',
  'Acompanhar sua evolução ao longo dos ciclos',
  'Apontar as questões e assuntos que você mais erra',
  'Resumir o que o sistema concluiu sobre o seu ciclo',
  'Ver sua sequência de participação',
];
