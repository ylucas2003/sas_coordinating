// Espelho de `api/app/routes/cantina.py` (docs/38).
//
// Como `tipos/dominio.ts` espelha `schemas/domain.py`: mudou lá, muda aqui —
// é o que faz um campo renomeado aparecer no build em vez de em runtime.
//
// ⚠️ A mistura de `snake_case` e `camelCase` NÃO é descuido, e a regra é a do
// resto do projeto: campo que vem cru de uma tabela mantém o nome da coluna
// (`pedidos_ate`, `escolhas_maximas`), campo que a rota CALCULA sai em
// camelCase (`pedidosAte` no calendário, `meuPedido`, `restricaoAlimentar`).
// A forma do nome diz de onde o dado veio.

/** As duas refeições. Fechado por união porque vira `CHECK` no banco (0048). */
export type Refeicao = 'almoco' | 'janta';

/**
 * Os cinco estados de um dia, e o prazo é que cria os dois do meio.
 *
 * `aberto` e `fechado` são o MESMO cardápio publicado antes e depois de
 * `pedidos_ate`. A diferença é a que a cantina mais precisa ler: em `fechado` a
 * contagem é final, e é ela que vai para o fogão (docs/38 §3.3).
 */
export type EstadoCardapio = 'sem-cardapio' | 'rascunho' | 'aberto' | 'fechado' | 'sem-refeicao';

export interface OpcaoCardapio {
  id: string;
  nome: string;
  ordem: number;
  /** false = acabou. É a única alteração permitida numa opção já pedida. */
  disponivel: boolean;
}

export interface BlocoCardapio {
  id: string;
  nome: string;
  ordem: number;
  escolhas_minimas: number;
  escolhas_maximas: number;
  opcoes: OpcaoCardapio[];
}

export interface Cardapio {
  id: string;
  cantina_id: string;
  /** ISO `YYYY-MM-DD`. */
  data: string;
  refeicao: Refeicao;
  /** Nulo enquanto rascunho; publicar sem prazo é recusado pelo servidor. */
  pedidos_ate: string | null;
  publicado_em: string | null;
  sem_refeicao: boolean;
  estado: EstadoCardapio;
  blocos: BlocoCardapio[];
}

/** Uma célula do calendário. Dia sem cardápio não vem na lista. */
export interface DiaDoCalendario {
  id: string;
  data: string;
  refeicao: Refeicao;
  estado: EstadoCardapio;
  pedidosAte: string | null;
  pedidos: number;
}

/** Uma linha da contagem de produção — o que cozinhar. */
export interface ContagemDeOpcao {
  cardapio_id: string;
  bloco_id: string;
  bloco: string;
  bloco_ordem: number;
  opcao_id: string;
  opcao: string;
  opcao_ordem: number;
  disponivel: boolean;
  quantos: number;
}

/** Uma linha da lista do balcão — o que servir, e para quem. */
export interface PedidoDeAluno {
  alunoId: string;
  nome: string | null;
  turma: string | null;
  /** A primeira informação de saúde do SAS. Só aparece aqui (docs/38 §2.6). */
  restricaoAlimentar: string | null;
  escolhas: string[];
  pedidoEm: string;
}

/** O que o aluno recebe: os direitos dele e os dias que pode resolver. */
export interface CantinaDoAluno {
  direitos: Refeicao[];
  dias: DiaDoAluno[];
}

export interface DiaDoAluno extends Cardapio {
  /** `null` = ainda não pedi. Lista vazia = pedi e não marquei nada. */
  meuPedido: string[] | null;
}

// ─── Administração ───────────────────────────────────────────────────────

export interface ContaDeCantina {
  id: string;
  cantina_id: string;
  email: string;
  nome: string;
  ativo: boolean;
  ultimo_login_em: string | null;
}

export interface CantinaAdmin {
  id: string;
  nome: string;
  ativo: boolean;
  /** A REGRA da casa, que pré-preenche cada cardápio novo — não é o prazo. */
  prazo_padrao_dias_antes: number;
  prazo_padrao_hora: string;
  contas: ContaDeCantina[];
}

export interface AlunoComDireito {
  id: string;
  nome: string;
  matricula: string | null;
  turma: string | null;
  direitos: Refeicao[];
  restricaoAlimentar: string | null;
}

export interface PainelDeDireitos {
  total: number;
  comDireito: number;
  alunos: AlunoComDireito[];
}
