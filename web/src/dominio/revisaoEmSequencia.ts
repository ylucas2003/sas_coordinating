// A REVISÃO EM SEQUÊNCIA — o recorte que a lista montou sobrevive à entrada
// na ficha.
//
// O custo que isto resolve é diário: o coordenador não abre a ficha de UM
// aluno, ele revisa os vinte em risco. Sem a sequência são lista → rolar →
// clicar → ler → voltar → rolar até onde estava → clicar no próximo: quarenta
// navegações para vinte alunos, e a posição se perde a cada volta
// (docs/39 §3 · fase 4, e o comentário "O recorte que a pessoa montou na
// lista" da prancheta "Alunos").
//
// ⚠️ Por que `sessionStorage` e não o `state` do `navigate`: a ficha é
// recarregada com F5, aberta em aba nova e alcançada pela busca da topbar — em
// todos esses casos o `state` chega vazio e a barra sumiria sem explicação. A
// SESSÃO é o escopo certo: o recorte é daquela aba, daquele turno de trabalho,
// e morre junto com o login.
//
// As funções de leitura e escrita ficam aqui, e não numa tela, porque quem
// GRAVA é a lista (`telas/Alunos/Alunos.tsx`) e quem LÊ é a ficha — o contrato
// entre as duas é este arquivo.

/** O recorte em vigor na lista, no momento em que ela levou alguém à ficha. */
export interface RecorteDeRevisao {
  /**
   * Os ids dos alunos na ORDEM em que a lista os mostrava — a ordenação é
   * parte do recorte (R6: é ela que faz o trabalho que a cor fazia). Guardar
   * só o filtro obrigaria a ficha a reproduzir a ordenação da lista, que é a
   * regra duplicada em dois lugares que este projeto já pagou três vezes.
   */
  ids: string[];
  /** Como o recorte se chama, em palavras: "zona de risco, pior primeiro". */
  rotulo: string;
  /**
   * A URL da lista COM o recorte em vigor — para onde a volta cai. É caminho
   * interno e é validado como tal: o valor vem de `sessionStorage`, que
   * qualquer script da própria origem pode escrever, e um `volta` externo
   * viraria redirecionamento para fora do produto no clique de "voltar".
   */
  volta: string;
  /**
   * O último aluno aberto deste recorte. Quem grava é a ficha, a cada aluno
   * lido; quem usa é a lista, para a volta cair na LINHA de onde se saiu e não
   * só na URL. Ausente na primeira entrada.
   */
  ultimoVisto?: string;
}

/** Onde a ficha está dentro do recorte, pronto para desenhar. */
export interface RevisaoEmSequencia {
  /** "aluno 4 de 23" — a frase, montada uma vez só. */
  posicao: string;
  rotulo: string;
  volta: string;
  /** O id anterior, ou `null` no começo do recorte. */
  anterior: string | null;
  /** O id seguinte, ou `null` no fim. */
  proximo: string | null;
  total: number;
  /** Base 0, para quem precisar da posição crua. */
  indice: number;
}

export const CHAVE_RECORTE = 'sas_recorte_revisao';

/**
 * Onde este aluno está no recorte — ou `null`, que é o caso normal.
 *
 * `null` quer dizer "esta ficha não faz parte de nenhuma revisão": aluno
 * alcançado pela busca da topbar, por link salvo, ou recorte de outra sessão.
 * A barra de sequência então não aparece — ela some inteira em vez de mostrar
 * "aluno 1 de 1", que prometeria uma sequência que não existe.
 */
export function montarRevisao(
  recorte: RecorteDeRevisao | null | undefined,
  id: string,
): RevisaoEmSequencia | null {
  if (!recorte || !id) return null;
  const indice = recorte.ids.indexOf(id);
  if (indice < 0) return null;

  const total = recorte.ids.length;
  return {
    posicao: `aluno ${indice + 1} de ${total}`,
    rotulo: recorte.rotulo,
    volta: recorte.volta,
    // Sem volta ao primeiro no fim da fila: dar a volta faz o coordenador
    // reler quem já leu sem perceber que terminou. O fim da revisão é uma
    // informação, e o botão desligado é onde ela aparece.
    anterior: indice > 0 ? recorte.ids[indice - 1] : null,
    proximo: indice < total - 1 ? recorte.ids[indice + 1] : null,
    total,
    indice,
  };
}

/** Caminho interno, e só ele: `/alunos?...`. Barra dupla é URL de outro host. */
function caminhoInterno(valor: unknown): valor is string {
  return typeof valor === 'string' && valor.startsWith('/') && !valor.startsWith('//');
}

/**
 * O JSON guardado vira recorte — ou `null` a qualquer sinal de que não é um.
 *
 * Falha fechada de propósito: o valor atravessa `sessionStorage`, sobrevive a
 * um deploy que mude o formato, e alimenta uma navegação. Recorte meio
 * entendido levaria a ficha a prometer uma sequência que não pode cumprir.
 */
export function desserializarRecorte(bruto: string | null | undefined): RecorteDeRevisao | null {
  if (!bruto) return null;
  let cru: unknown;
  try {
    cru = JSON.parse(bruto);
  } catch {
    return null;
  }
  if (typeof cru !== 'object' || cru === null) return null;

  const { ids, rotulo, volta, ultimoVisto } = cru as Record<string, unknown>;
  if (!Array.isArray(ids) || ids.length === 0) return null;
  if (!ids.every((i) => typeof i === 'string' && i.length > 0)) return null;
  if (typeof rotulo !== 'string' || !rotulo) return null;
  if (!caminhoInterno(volta)) return null;

  return {
    ids: ids as string[],
    rotulo,
    volta,
    ...(typeof ultimoVisto === 'string' && ultimoVisto ? { ultimoVisto } : {}),
  };
}

export function serializarRecorte(recorte: RecorteDeRevisao): string {
  return JSON.stringify(recorte);
}

/**
 * `sessionStorage` pode lançar — modo privado do Safari, cota estourada,
 * cookies de terceiro bloqueados dentro de iframe. Nenhum desses casos vale
 * derrubar a tela: sem recorte a ficha continua inteira, só sem a barra.
 */
function sessao(): Storage | null {
  try {
    return typeof sessionStorage === 'undefined' ? null : sessionStorage;
  } catch {
    return null;
  }
}

/** Chamada pela LISTA, no clique que leva à ficha. */
export function guardarRecorteDeRevisao(recorte: RecorteDeRevisao): void {
  const s = sessao();
  if (!s) return;
  try {
    s.setItem(CHAVE_RECORTE, serializarRecorte(recorte));
  } catch {
    // Guardar o recorte é conforto, não requisito: a ficha abre sem ele.
  }
}

/** Chamada pela FICHA ao abrir, e pela lista ao voltar. */
export function lerRecorteDeRevisao(): RecorteDeRevisao | null {
  const s = sessao();
  if (!s) return null;
  try {
    return desserializarRecorte(s.getItem(CHAVE_RECORTE));
  } catch {
    return null;
  }
}

/**
 * A ficha marca quem está lendo para a lista voltar na LINHA certa, não só na
 * URL certa. Escreve só quando o aluno pertence ao recorte — marcar alguém de
 * fora faria a lista rolar até uma linha que o filtro dela não mostra.
 */
export function marcarUltimoVisto(id: string): void {
  const recorte = lerRecorteDeRevisao();
  if (!recorte || recorte.ultimoVisto === id || !recorte.ids.includes(id)) return;
  guardarRecorteDeRevisao({ ...recorte, ultimoVisto: id });
}
