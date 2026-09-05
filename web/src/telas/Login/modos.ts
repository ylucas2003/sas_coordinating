// As DUAS portas da tela de login — e só uma delas tem formulário.
//
// `Modo` diz qual porta está aberta, não quem a pessoa é: 'aluno' renderiza a
// `PortaDoAluno` inteira (que hoje é só o botão do Canvas) e 'coordenador'
// renderiza o `.lp` institucional com e-mail + senha.
//
// ⚠️ Os rótulos abaixo são só do lado da COORDENAÇÃO. Havia um par para o
// aluno até 04/09, com `fieldLabel: 'Matrícula'` e "Entrar no painel do
// aluno" — texto de um formulário que deixou de existir quando o aluno passou
// a entrar só pelo Canvas (docs/35 §11.5). Ficaria como dado morto dizendo o
// contrário do que a tela faz, então saiu junto.
//
// O terceiro papel (administrador) NÃO aparece aqui: ele entra pela mesma
// porta e pelo mesmo formulário da coordenação, e quem o distingue é o `papel`
// que volta do servidor (`servicos/sessao.ts`).

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

export const ROTULOS_COORDENACAO: RotulosModo = {
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
};
