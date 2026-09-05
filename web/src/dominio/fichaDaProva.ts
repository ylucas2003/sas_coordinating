// A FICHA DE UMA PROVA — o que a tela precisa decidir antes de desenhar.
//
// Por que isto é domínio e não um punhado de ternários dentro do TSX: as três
// perguntas abaixo mudam a tela INTEIRA, e cada uma delas já foi respondida
// errado em algum lugar do produto.
//
//   1 · Esta prova tem dado?      cinco travessões e um gráfico vazio não são
//                                 informação (docs/39 fase 3).
//   2 · Que ações existem HOJE?   quatro botões aparecendo e sumindo na linha
//                                 do título faziam a barra dançar de tamanho a
//                                 cada prova aberta.
//   3 · Como esta prova se chama? `simulado.nome` é o nome que estava na
//                                 planilha do Canvas, e ele não promete nada.
//
// ⚠️ Nada aqui inventa número. Onde o servidor não diz, a função devolve
// `null` ou omite a parte da frase — "0" no lugar de "não sei" é a mentira
// mais cara desta interface, e nesta tela ela tem nome: ausência contada como
// zero deturpa toda média (memória do projeto, "zeros = prováveis ausências").
//
// A régua de corte NÃO se decide aqui: quem a consulta é `dominio/criterios.ts`,
// sobre o que o servidor resolveu (docs/18 §1.2).

import type { NotaSimulado, Simulado } from '../tipos/dominio';

/** `2026-09-04` → `04/09/2026`. */
export function dataPorExtenso(iso: string): string {
  // Fatia a string em vez de passar por `Date`: `new Date('2026-09-04')` lê a
  // data como meia-noite UTC e devolve o dia ANTERIOR em todo fuso negativo —
  // o Brasil inteiro. Apareceria aqui como "a prova de hoje foi aplicada
  // ontem" (a mesma armadilha que `dominio/cantina.ts::dataLocal` documenta).
  if (!iso || iso.length < 10) return iso ?? '';
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
}

/**
 * "P8 · Física · Fase 1" — a prova pelas colunas estruturadas.
 *
 * `simulado.nome` é o último recurso, e não o primeiro, porque ele é o texto
 * que estava no Assignment do Canvas: a gramática `{ciclo}_P{n} - Matéria -
 * data` só vale para o que o SAS criou, e prova antiga veio com o nome que
 * estivesse na planilha.
 */
export function identidadeDaProva(simulado: Simulado): string {
  const fase = simulado.tipo === 'fase_1' ? 'Fase 1'
    : simulado.tipo === 'fase_2' ? 'Fase 2'
    : null;
  const partes = [simulado.rotuloCurto, simulado.materia?.nome, fase].filter(Boolean);
  return partes.length ? partes.join(' · ') : simulado.nome;
}

/**
 * A sobrancelha: onde esta prova vive e quantos ela mediu.
 *
 * Cada parte só entra se o servidor a mandou. Um "· 0 ausentes" derivado de
 * `null` diria "todo mundo veio", que é a leitura oposta de "não sei".
 */
export function contextoDaProva(
  simulado: Simulado,
  nAusentes: number | null | undefined,
  hoje: string,
): string {
  const partes: string[] = [];
  if (simulado.cicloOrdem != null) partes.push(`Ciclo ${simulado.cicloOrdem}`);
  if (simulado.vestibularAlvo) partes.push(simulado.vestibularAlvo);
  if (simulado.dataAplicacao) {
    const verbo = simulado.dataAplicacao > hoje ? 'previsto para' : 'aplicado em';
    partes.push(`${verbo} ${dataPorExtenso(simulado.dataAplicacao)}`);
  }
  if (simulado.nPresentes != null) partes.push(`${simulado.nPresentes} presentes`);
  if (nAusentes != null) partes.push(`${nAusentes} ausentes`);
  return partes.join(' · ');
}

/**
 * A pontuação bruta que o backend espera na edição.
 *
 * A linha traz a nota já em escala 0–10 (é o que `GET /simulados/{id}/notas`
 * devolve) e a escrita quer a pontuação crua — daí a volta. Sem `notaMaxima`
 * não há conversão possível, e devolver 0 seria escrever um zero onde não há
 * dado.
 */
export function pontuacaoBruta(
  nota: NotaSimulado,
  notaMaxima: number | null | undefined,
): number | null {
  if (!nota.presente || nota.pontuacao == null || !notaMaxima) return null;
  return Math.round((nota.pontuacao / 10) * notaMaxima * 100) / 100;
}

/**
 * "3 de 20" — a pontuação como ela foi lançada, ao lado da nota calculada.
 *
 * `notaMaxima` é o número de questões da prova (Points Possible do Canvas), e
 * essa é a única leitura que devolve ao coordenador o que ele de fato corrigiu.
 * A volta de 0–10 para bruto pode não fechar em inteiro quando a nota chegou
 * arredondada; nesse caso a casa decimal fica, porque escondê-la faria "9 de
 * 20" e "8,7 de 20" parecerem a mesma prova.
 */
export function acertosEmPalavras(
  nota: NotaSimulado,
  notaMaxima: number | null | undefined,
): string | null {
  const bruto = pontuacaoBruta(nota, notaMaxima);
  if (bruto == null || !notaMaxima) return null;
  const texto = Number.isInteger(bruto)
    ? String(bruto)
    : bruto.toFixed(1).replace('.', ',');
  return `${texto} de ${notaMaxima}`;
}

// ─── As ações que dependem do estado da prova ────────────────────────────

export type AcaoDaProva = 'enviar-canvas' | 'tentar-canvas' | 'desmarcar';

export interface CondicaoDaProva {
  acao: AcaoDaProva;
  /** Por que este botão existe HOJE. Botão condicional mudo é a pergunta que o coordenador já não sabia responder. */
  motivo: string;
  rotulo: string;
  /** Falha operacional — a ÚNICA que ganha alerta na moldura (R4). */
  falha: boolean;
}

/**
 * As ações condicionais, em lista, com o motivo de cada uma escrito.
 *
 * "Editar simulado" NÃO está aqui de propósito: ela existe sempre, mora na
 * linha do título e é o que impede a barra de mudar de tamanho a cada prova.
 * O que varia desce para uma faixa própria, uma linha por condição.
 *
 * As três condições são disjuntas na prática — `divergente` e `falhou` são
 * estados exclusivos do mesmo campo, e uma prova sem presentes não costuma ter
 * saído do SAS —, mas a função devolve LISTA, e não uma condição só, porque
 * "desmarcar" é ortogonal às outras duas e empilhá-las é o comportamento certo
 * quando coincidem.
 */
export function condicoesDaProva(simulado: Simulado): CondicaoDaProva[] {
  // Prova que veio do Canvas não tem o que enviar de volta: o Canvas é a
  // origem, e o SAS só lê.
  if (simulado.origem !== 'sas') return [];

  const lista: CondicaoDaProva[] = [];

  // O único caminho que tira um simulado de 'divergente' — o retry automático
  // nunca faz isso, porque divergir foi uma ESCOLHA (docs/18 §2.5).
  if (simulado.canvasEstado === 'divergente') {
    lista.push({
      acao: 'enviar-canvas',
      motivo: 'O SAS e o Canvas estão diferentes nesta prova, por escolha sua.',
      rotulo: 'Enviar ao Canvas',
      falha: false,
    });
  }

  if (simulado.canvasEstado === 'falhou') {
    lista.push({
      acao: 'tentar-canvas',
      motivo: simulado.canvasErro
        || 'O Canvas recusou esta prova. A tentativa automática roda a cada 5 minutos.',
      rotulo: 'Tentar de novo no Canvas',
      falha: true,
    });
  }

  // Só prova do SAS que ninguém fez se desmarca; com nota, anula — e quem diz
  // não é esta função, é a API, que devolve 409. `nPresentes` em `null` cai
  // aqui junto com o zero, como sempre caiu: oferecer a ação e deixar o
  // servidor recusar é mais honesto do que esconder a saída de uma prova que o
  // coordenador acabou de marcar por engano.
  if (!simulado.nPresentes) {
    lista.push({
      acao: 'desmarcar',
      motivo: 'Ninguém fez esta prova ainda, então ela pode sair sem deixar rastro. Depois da primeira nota, só resta anular.',
      rotulo: 'Desmarcar',
      falha: false,
    });
  }

  return lista;
}

// ─── O estado vazio ──────────────────────────────────────────────────────

export interface FichaVazia {
  olho: string;
  titulo: string;
  frase: string;
}

/**
 * O que dizer quando não há nota — e `null` quando há.
 *
 * É o estado mais frequente logo depois de uma aplicação, e era o pior da
 * tela: cinco travessões numa fileira de KPIs, um histograma vazio e duas
 * tabelas dizendo "ainda não calculadas". Cinco buracos não são informação.
 *
 * ⚠️ Chame só com as consultas RESOLVIDAS. Uma lista de notas ainda em voo é
 * indistinguível de uma prova sem notas, e a tela piscaria o estado vazio
 * antes de mostrar os dados.
 */
export function fichaVazia(
  simulado: Simulado,
  notas: readonly NotaSimulado[],
  hoje: string,
): FichaVazia | null {
  const temNota = notas.some((n) => n.pontuacao != null);
  if (temNota || simulado.media != null) return null;

  // Ainda não aconteceu. Dizer "as notas não chegaram" de uma prova de semana
  // que vem manda cobrar uma coisa que ninguém deve.
  if (simulado.dataAplicacao && simulado.dataAplicacao > hoje) {
    return {
      olho: 'Prova agendada',
      titulo: 'Esta prova ainda não foi aplicada',
      frase: `Está marcada para ${dataPorExtenso(simulado.dataAplicacao)}. Antes da aplicação não há nota — e sem nota não há média, histograma nem distribuição.`,
    };
  }

  // Há linhas, e todas são de ausência. É o oposto de "as notas não
  // chegaram": elas chegaram, e o que elas dizem é que ninguém fez.
  if (notas.length > 0) {
    return {
      olho: 'Só ausências',
      titulo: 'Todo mundo desta prova consta como ausente',
      frase: `As ${notas.length} pessoas ligadas a esta prova estão marcadas como ausentes. Ausência não é zero: ela não entra na média nem no histograma, e por isso não há distribuição a desenhar.`,
    };
  }

  const quem = simulado.nPresentes != null ? `${simulado.nPresentes} alunos fizeram` : 'A turma fez';
  const quando = simulado.dataAplicacao ? ` em ${dataPorExtenso(simulado.dataAplicacao)}` : '';
  return {
    olho: 'Sem nota lançada',
    titulo: 'A prova foi aplicada, as notas não chegaram',
    frase: `${quem} esta prova${quando} e nenhuma nota foi lançada até agora. Sem nota não há média, histograma nem distribuição — não é uma prova ruim, é uma prova sem dado.`,
  };
}
