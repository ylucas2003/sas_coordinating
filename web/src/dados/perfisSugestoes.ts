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
//                porque 26 tools não cabem em quatro frases soltas: o que o
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
  'Comparar ciclos e achar alunos com desempenho parecido',
  'Montar relatórios de aluno e de ciclo',
  'Gerar gráficos e exportar CSV',
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

export const CAPACIDADES_ALUNO: string[] = [
  'Mostrar suas notas e como você foi em cada simulado',
  'Acompanhar sua evolução ao longo dos ciclos',
  'Apontar as questões e assuntos que você mais erra',
  'Resumir o que o sistema concluiu sobre o seu ciclo',
  'Ver sua sequência de participação',
];
