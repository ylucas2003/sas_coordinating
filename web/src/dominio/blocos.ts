// Os blocos da coordenação: um por série (docs/44 §1).
//
// O 1º e o 2º ano fazem provas diferentes, então nunca dividem bloco, e o 3º
// reúne o cursinho porque os dois vêm do mesmo curso do Canvas.
//
// É o ENDEREÇO que diz em que bloco se está, para o link poder ser salvo e para
// não existir um modo escondido. `/alunos` continua sendo 3º e cursinho, porque
// é o que sempre foi e está em link salvo e em e-mail de lembrete; os blocos
// novos é que ganham prefixo. As fichas (`/alunos/:id`, `/ciclos/:id`,
// `/simulados/:id`) não têm prefixo: o chat e os e-mails apontam para elas, e
// quem diz a série de uma ficha é a própria coisa aberta (`useSerieDaFicha`).

export type SerieDoBloco = 1 | 2 | 3;

/** O bloco de todo endereço sem prefixo. */
export const SERIE_PADRAO: SerieDoBloco = 3;

export interface DefinicaoDoBloco {
  serie: SerieDoBloco;
  rotulo: string;
  prefixo: string;
}

export const BLOCOS: readonly DefinicaoDoBloco[] = [
  { serie: 3, rotulo: '3º e cursinho', prefixo: '' },
  { serie: 1, rotulo: '1º ano', prefixo: '/1ano' },
  { serie: 2, rotulo: '2º ano', prefixo: '/2ano' },
];

/** O que cada bloco tem, e que por isso aceita prefixo no endereço. */
export type DestinoDoBloco = 'painel' | 'alunos' | 'provas';

function definicaoDoCaminho(caminho: string): DefinicaoDoBloco {
  const comPrefixo = BLOCOS.find(
    ({ prefixo }) => prefixo && (caminho === prefixo || caminho.startsWith(`${prefixo}/`)),
  );
  return comPrefixo ?? (BLOCOS[0] as DefinicaoDoBloco);
}

function definicaoDaSerie(serie: SerieDoBloco): DefinicaoDoBloco {
  return BLOCOS.find((b) => b.serie === serie) ?? (BLOCOS[0] as DefinicaoDoBloco);
}

export function serieDoCaminho(caminho: string): SerieDoBloco {
  return definicaoDoCaminho(caminho).serie;
}

export function semPrefixoDoBloco(caminho: string): string {
  const { prefixo } = definicaoDoCaminho(caminho);
  return caminho.slice(prefixo.length) || '/';
}

/** `(1, '/provas')` → `/1ano/provas`. O caminho pode trazer query string. */
export function caminhoNoBloco(serie: SerieDoBloco, caminho: string): string {
  return `${definicaoDaSerie(serie).prefixo}${caminho}`;
}

export function rotuloDoBloco(serie: SerieDoBloco): string {
  return definicaoDaSerie(serie).rotulo;
}

/**
 * Que item do bloco este endereço acende. As fichas de ciclo e de prova acendem
 * "Provas" porque é dali que se chega nelas. `null` é tela fora dos blocos.
 */
export function destinoDoCaminho(caminho: string): DestinoDoBloco | null {
  const raiz = semPrefixoDoBloco(caminho).split('/').filter(Boolean)[0] ?? 'painel';
  if (raiz === 'painel') return 'painel';
  if (raiz === 'alunos') return 'alunos';
  if (raiz === 'provas' || raiz === 'ciclos' || raiz === 'simulados') return 'provas';
  return null;
}

const LISTAS_DO_BLOCO: ReadonlySet<string> = new Set([
  '/',
  '/painel',
  '/alunos',
  '/provas',
  '/provas/ciclos',
  '/provas/simulados',
]);

/** Tela que existe em todo bloco. Ficha não é: pertence a uma coisa só. */
export function ehListaDoBloco(caminho: string): boolean {
  return LISTAS_DO_BLOCO.has(semPrefixoDoBloco(caminho));
}

/**
 * Para onde vai quem troca de bloco no celular: a mesma tela no outro bloco. Quem
 * estava numa tela que o outro bloco não tem cai no Painel dele.
 */
export function caminhoAoTrocarDeBloco(caminho: string, serie: SerieDoBloco): string {
  const sem = semPrefixoDoBloco(caminho);
  return caminhoNoBloco(serie, ehListaDoBloco(caminho) && sem !== '/' ? sem : '/painel');
}

/**
 * O nome curto de um ciclo, tirado da ordem. No 3º é "Ciclo 11". No 1º e no 2º ano
 * cada etapa tem dois ciclos, AP e AG, nesta ordem (docs/44 §3): a ordem 6 é
 * "3ª etapa · AG". O vestibular não entra, porque quem chama já o escreve ao lado.
 */
export function nomeCurtoDoCiclo(ordem: number, serie: SerieDoBloco | undefined): string {
  if ((serie ?? SERIE_PADRAO) === SERIE_PADRAO) return `Ciclo ${ordem}`;
  return `${Math.ceil(ordem / 2)}ª etapa · ${ordem % 2 === 1 ? 'AP' : 'AG'}`;
}

/**
 * Só o que é deste bloco. Item sem série é do 3º: é o que todo dado era antes de a
 * coluna existir, e é assim que resposta antiga em cache continua correta.
 */
export function daSerie<T extends { serie?: SerieDoBloco }>(
  lista: readonly T[],
  serie: SerieDoBloco,
): T[] {
  return lista.filter((item) => (item.serie ?? SERIE_PADRAO) === serie);
}
