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
 * Os dois jeitos de comer (docs/40 §1).
 *
 * `pedido` compromete a cozinha com um prato; `presencial` é só declaração de
 * presença — não escolhe item nenhum (docs/40 §10.1). Vira `CHECK` na coluna
 * `pedido_refeicao.modo` (0051), daí ser união fechada como `Refeicao`.
 */
export type ModoDeRefeicao = 'pedido' | 'presencial';

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
  /**
   * A regra do bloco que o número não expressa (migration 0053).
   *
   * "Máximo 2 opções" já é `escolhas_maximas`; o que sobra é "a escolha da
   * opção 4 anula a 1 e a 2" — a coluna "Obs!" da tabela que a cozinha usa no
   * papel.
   *
   * ⚠️ **É escrita, não vigiada** (docs/40 §12.5.4): o servidor não recusa a
   * combinação que ela proíbe, e o aluno pode marcá-la. A tela mostra o texto
   * para quem escolhe; garantir é outra feature.
   */
  observacao: string | null;
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
  /**
   * Quais modos este dia aceita (docs/40 §1). Publicar com os dois em `false` é
   * recusado pelo servidor — um cardápio que não aceita nada é `sem_refeicao`
   * disfarçado.
   *
   * ⚠️ Saem em camelCase e entram em snake_case (`aceita_pedido` no corpo do
   * `PUT`), ao contrário do resto do arquivo. É o contrato da rota, não
   * descuido — e é a razão de `CorpoCardapio` ter os dois nomes.
   */
  aceitaPedido: boolean;
  aceitaPresencial: boolean;
}

/** Uma célula do calendário. Dia sem cardápio não vem na lista. */
export interface DiaDoCalendario {
  id: string;
  data: string;
  refeicao: Refeicao;
  estado: EstadoCardapio;
  pedidosAte: string | null;
  /**
   * Quantos vão comer — as DUAS portas somadas.
   *
   * ⚠️ O significado é o mesmo desde a 0049, e é por isso que o nome não mudou
   * quando a retirada presencial entrou na conta: várias telas já leem este
   * campo, e trocar o sentido dele em silêncio seria pior que a divergência que
   * a quebra abaixo resolve.
   */
  pedidos: number;
  /**
   * Quem escolheu prato — a única metade que a contagem por opção soma.
   *
   * É aqui que mora a divergência que virava chamado de bug: "47" no calendário
   * contra "44 arroz" no fogão, porque quem pega pessoalmente não escolhe prato
   * (docs/40 §10.1). Os dois números estavam certos; faltava a quebra visível.
   */
  comPedido: number;
  /** Quem declarou presença — pendentes e já retiradas juntas (view da 0052). */
  presenciais: number;
}

/**
 * O presencial na contagem, e ele fica FORA das linhas por opção de propósito:
 * quem pega pessoalmente não escolhe prato (docs/40 §10.1), então somá-lo ao
 * "47 arroz" inventaria um arroz que ninguém pediu.
 */
export interface ContagemPresencial {
  pendentes: number;
  retirados: number;
}

/** A contagem inteira de um cardápio: o que cozinhar, e quantos presenciais. */
export interface ContagemDoCardapio {
  opcoes: ContagemDeOpcao[];
  /**
   * `null` = o servidor desta instalação ainda não manda o bloco (antes da
   * 0051). A tela ESCONDE a linha nesse caso, em vez de mostrar dois zeros —
   * "não sei" virando "ninguém" é a mentira mais barata de escrever e a mais
   * cara de descobrir, e o resto da cantina já segue essa regra.
   */
  presencial: ContagemPresencial | null;
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
  /** `presencial` nunca traz `escolhas` — não há prato para servir, há alguém
      para conferir na leitura do QR (docs/40 §10.1). */
  modo: ModoDeRefeicao;
  /** Quando o QR foi lido. `null` no modo `pedido` sempre, e no `presencial`
      enquanto ninguém leu. Preenchido é final dos dois lados (docs/40 §2). */
  retiradoEm: string | null;
}

/**
 * O que `POST /me/cantina/retiradas/{cardapio_id}` devolve.
 *
 * O QR carrega este `token` — assinado, com validade curta —, e não o
 * `aluno_id` cru: um print de tela não pode virar crachá reutilizável nem
 * sobreviver ao dia (docs/40 §4). Quem renova é a própria tela, antes de
 * `expiraEm`.
 */
export interface TokenDeRetirada {
  token: string;
  expiraEm: string;
  /**
   * A SEMENTE do código rotativo, e ela **nunca entra no QR** (docs/40 §12.9.2).
   *
   * Com ela o aparelho deriva um código novo a cada 10 s, sem rede. Se ela
   * viajasse no QR, um print carregaria o material para derivar as janelas
   * seguintes — e a rotação seria decoração.
   */
  semente: string;
  pedidoId: string;
  /** A janela no relógio DO SERVIDOR quando a resposta saiu. O cliente conta o
      tempo decorrido a partir dela, e não a hora do aparelho. */
  janela: number;
  segundosDaJanela: number;
}

/**
 * A ficha que a leitura do QR devolve no balcão.
 *
 * É a MESMA régua de dado que a cantina já tem na lista de pedidos: nome,
 * turma, refeição e a restrição alimentar. Nada de nota, de simulado nem de
 * ficha (docs/38 §8.1.2).
 */
export interface RetiradaConfirmada {
  alunoId: string;
  nome: string | null;
  turma: string | null;
  refeicao: Refeicao;
  /** ISO `YYYY-MM-DD` — o dia do CARDÁPIO, não o da leitura. Nulo só se a
      linha do cardápio vier sem data, que não deveria acontecer: a tela não
      inventa um dia por isso. */
  data: string | null;
  restricaoAlimentar: string | null;
  retiradoEm: string;
}

/** O que o aluno recebe: os direitos dele e os dias que pode resolver. */
export interface CantinaDoAluno {
  direitos: Refeicao[];
  dias: DiaDoAluno[];
}

export interface DiaDoAluno extends Cardapio {
  /** `null` = ainda não pedi. Lista vazia = pedi e não marquei nada. */
  meuPedido: string[] | null;
  /**
   * Onde eu estou na máquina de estados deste dia (docs/40 §2).
   *
   * `null` = não há linha nenhuma. ⚠️ **Este campo, e não `meuPedido`, é quem
   * responde "eu já resolvi este dia?"**: uma retirada presencial não escolhe
   * item, e o servidor devolve `meuPedido: null` para ela justamente para não
   * dizer "você pediu nada" onde a verdade é "você vai buscar no balcão". Ler o
   * pedido para decidir o modo confundiria os dois — e é o que `situacaoDoDia`
   * evita, checando `modo` ANTES de `meuPedido`.
   */
  modo: ModoDeRefeicao | null;
  /** Preenchido = já comi. Final: não há desfazer (docs/40 §2). */
  retiradoEm: string | null;
  /**
   * De QUEM é este cardápio.
   *
   * ⚠️ Passou a importar quando "Food" — que a planilha da coordenação
   * registrava como um local de consumo — revelou-se o nome de uma segunda
   * CANTINA (docs/40 §12.12). Com duas publicando o mesmo almoço, dois cartões
   * do mesmo dia chegam a esta tela, e sem o nome eles são indistinguíveis.
   *
   * `null` só em base antiga: o servidor sempre manda.
   */
  cantina: string | null;
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
  /**
   * A outra metade da regra da casa: quais modos um cardápio NOVO já nasce
   * aceitando (docs/40 §1). Irmãs de `prazo_padrao_*` — pré-preenchem
   * `cardapio.aceita_pedido`/`aceita_presencial` e **não tocam em cardápio já
   * lançado**, que a cantina troca dia a dia no editor.
   *
   * `NOT NULL` no banco (0051), com o default mantendo o comportamento de
   * antes da feature: só pedido.
   */
  aceita_pedido_almoco: boolean;
  aceita_pedido_janta: boolean;
  aceita_presencial_almoco: boolean;
  aceita_presencial_janta: boolean;
  /**
   * Preço de tabela, em reais. `null` = ainda não informado, e é DIFERENTE de
   * 0,00 — a tela não pode somar zero como se fosse dado. O SAS não cobra; o
   * valor existe para a coordenação somar o custo do que foi pedido.
   */
  valor_almoco: number | null;
  valor_janta: number | null;
  contas: ContaDeCantina[];
}

/** O estabelecimento da sessão da cantina, sem as contas. */
export type MinhaCantina = Omit<CantinaAdmin, 'contas'>;

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

/**
 * O resumo do card do hub — contagem, e nada de lista.
 *
 * A ausência de `alunos` aqui é o ponto: este é o contrato que permite ao card
 * saber "3 de 2050" sem que nome, turma ou restrição alimentar de ninguém
 * cheguem à tela (docs/40 §12.1.2).
 */
export interface ResumoDaCantina {
  ativos: number;
  /** Alunos DISTINTOS com algum direito — não a soma de almoço e janta. */
  comDireito: number;
  almoco: number;
  janta: number;
}

/** Uma linha de qualquer recorte do relatório de custos (docs/40 §12.11). */
export interface LinhaDeCusto {
  rotulo: string;
  refeicoes: number;
  total: number;
}

export interface CustosDaCantina {
  de: string;
  ate: string;
  refeicoes: number;
  total: number;
  /**
   * Quantos pedidos ficaram SEM preço carimbado.
   *
   * ⚠️ A tela precisa DIZER este número. Um relatório que soma zero em silêncio
   * faz a coordenação fechar a conta errada e nunca saber; "12 sem valor
   * registrado" transforma o buraco em pergunta (docs/40 §12.11.2).
   */
  semValor: number;
  porDia: LinhaDeCusto[];
  porTurma: LinhaDeCusto[];
  porAluno: LinhaDeCusto[];
  porCantina: LinhaDeCusto[];
}
