// Os dois modos de acesso. Mudam o texto da coluna esquerda, o rótulo do
// campo de usuário e o `tipo` enviado ao backend.

export type Modo = 'aluno' | 'coordenador';

export interface RotulosModo {
  label: string;
  hl1: string;
  hlEm: string;
  hl2: string;
  subtitle: string;
  fieldLabel: string;
  placeholder: string;
  submitText: string;
  /** Manchete da coluna direita, em três linhas. */
  rightHl: [string, string, string];
  /** A palavra em destaque, no fim da manchete. */
  rightHlEm: string;
  rightSub: string;
}

export const MODOS: Record<Modo, RotulosModo> = {
  aluno: {
    label: 'Acesso · aluno',
    hl1: 'Sua jornada,',
    hlEm: 'medida',
    hl2: ' a cada passo.',
    subtitle:
      'Veja cada simulado, cada nota e cada avanço até a sua aprovação. Sua devolutiva, sua evolução, seu painel.',
    fieldLabel: 'Matrícula',
    placeholder: 'matrícula ou e-mail institucional',
    submitText: 'Entrar no painel do aluno',
    rightHl: ['A tradição que aprova.', 'Agora, acompanhada', 'com '],
    rightHlEm: 'precisão.',
    rightSub:
      'Cada simulado ganha contexto, cada nota vira direção e cada aluno acompanha sua evolução até a aprovação.',
  },
  coordenador: {
    label: 'Acesso · coordenação',
    hl1: 'Gestão clara,',
    hlEm: 'decisões',
    hl2: ' com profundidade.',
    subtitle:
      'Acompanhe dados individuais e gerais, compare turmas, ciclos e desempenhos, identifique alertas e transforme informação em ação pedagógica.',
    fieldLabel: 'Usuário',
    placeholder: 'usuário institucional',
    submitText: 'Entrar no painel da coordenação',
    rightHl: ['Diagnóstico que organiza', 'a visão. Dados que orientam', 'a '],
    rightHlEm: 'decisão.',
    rightSub:
      'Do aluno individual ao panorama da rede, a plataforma cruza resultados, evidencia prioridades e apoia intervenções pedagógicas com clareza.',
  },
};
