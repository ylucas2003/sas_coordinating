// Banco de questões ITA · IME — lógica pura, testada em banco.test.ts.
//
// É a camada que as telas de `telas/Banco/` consomem: rótulo, filtro em
// memória, ordenação, agrupamento por bloco do edital e as séries dos
// gráficos (docs/22 §7.3). Sem React e sem I/O — quem fala com a API é
// `servicos/`.
//
// ⚠️ `QuestaoVestibular` é questão de PROVA PASSADA. A questão de
// simulado-Quiz do Canvas é outra coisa e mora em `tipos/dominio.ts`.
// Confundir as duas é o risco nº 1 do sprint (docs/22 §8).

import type {
  EstatisticasBanco,
  QuestaoVestibular,
  RecorrenciaTopico,
} from '../tipos/banco';

// ─── Rótulo e leitura de uma questão ─────────────────────────────────────

/**
 * "ITA 2019 · Física · Fase 1 · nº 12" — o mesmo rótulo no cartão, na lista e
 * no PDF.
 *
 * A matéria entra porque a numeração recomeça em cada uma: sem ela, a 1ª de
 * Matemática e a 1ª de Física do IME 2025 F2 são dois cartões com o mesmo
 * nome, e a listagem "Todas as matérias" mostra os dois em sequência. Visto na
 * verificação em browser de 22/08.
 */
export function rotuloQuestao(q: QuestaoVestibular): string {
  return `${q.vestibular} ${q.ano} · ${q.materia} · Fase ${q.fase} · nº ${q.numero}`;
}

/**
 * 469 das 934 questões não têm gabarito (docs/22 §1.4) — a maioria por serem
 * dissertativas, onde não existe letra a conferir. A tela pergunta ao domínio
 * em vez de olhar o campo para que "sem gabarito" tenha um só significado:
 * não há o que conferir, seja qual for o motivo.
 */
export function temGabarito(q: QuestaoVestibular): boolean {
  return typeof q.gabarito === 'string' && q.gabarito.trim() !== '';
}

/**
 * Dissertativa é 2ª fase: `alternativas` e `gabarito` nulos são o esperado,
 * não dado faltando (0028, comentário de `dissertativa`). É o que separa
 * "não tem letra por natureza" de "não importamos a letra".
 */
export function ehDissertativa(q: QuestaoVestibular): boolean {
  return q.dissertativa === true;
}

// ─── Filtro em memória ───────────────────────────────────────────────────

/**
 * O filtro de verdade é o do servidor (`GET /banco/questoes`, docs/22 §2.1).
 * Este atende a tela de montar lista, que trabalha sobre um conjunto já
 * baixado: reconsultar a API a cada clique de chip devolveria a mesma
 * questão pela rede só para escondê-la.
 *
 * AND entre categorias, OR dentro de uma — igual a `simulados.ts`.
 */
export interface FiltroQuestoes {
  materias: ReadonlySet<string>;
  vestibulares: ReadonlySet<string>;
  anos: ReadonlySet<number>;
  fases: ReadonlySet<number>;
  /** Chaves de `chaveTopico`, não códigos crus — ver o porquê lá embaixo. */
  topicos: ReadonlySet<string>;
  busca: string;
}

export const FILTRO_QUESTOES_VAZIO: FiltroQuestoes = {
  materias: new Set(),
  vestibulares: new Set(),
  anos: new Set(),
  fases: new Set(),
  topicos: new Set(),
  busca: '',
};

export function algumFiltroAtivo(f: FiltroQuestoes): boolean {
  const marcados =
    f.materias.size + f.vestibulares.size + f.anos.size + f.fases.size + f.topicos.size;
  return marcados > 0 || f.busca.trim() !== '';
}

/**
 * Identidade de um tópico: matéria + código, nunca o código sozinho.
 *
 * '1.1' existe nas três matérias e significa coisa diferente em cada uma —
 * "Fundamentos" em Física, "Conjuntos e Lógica" em Matemática, "Estrutura
 * Atômica" em Química. Por isso a chave é composta no banco (0028), e por isso
 * é composta aqui: filtrar por código cru misturaria as três em silêncio, e o
 * sintoma apareceria como lista errada, não como erro.
 */
export function chaveTopico(materia: string, codigo: string): string {
  return `${materia}::${codigo}`;
}

/**
 * Sem acento e em caixa baixa: quem procura "termodinamica" tem que achar
 * "Termodinâmica". O teclado do celular não ajuda a acentuar, e a busca é o
 * caminho mais usado ali (docs/22 §3.5).
 */
function normalizar(texto: string): string {
  return texto
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

/** Onde a busca textual procura: enunciado, id e nome dos tópicos. */
function textoBuscavel(q: QuestaoVestibular): string {
  return normalizar([q.id, q.enunciadoMd, ...q.topicos.map((t) => t.nome)].join(' '));
}

function passa(q: QuestaoVestibular, f: FiltroQuestoes): boolean {
  if (f.materias.size && !f.materias.has(q.materia)) return false;
  if (f.vestibulares.size && !f.vestibulares.has(q.vestibular)) return false;
  if (f.anos.size && !f.anos.has(q.ano)) return false;
  if (f.fases.size && !f.fases.has(q.fase)) return false;
  // Questão mista casa por QUALQUER um dos tópicos dela, e entra uma vez só —
  // é `filter`, não `flatMap`. Mista é a regra, não a exceção (docs/22 §1.2).
  if (f.topicos.size && !q.topicos.some((t) => f.topicos.has(chaveTopico(q.materia, t.codigo)))) {
    return false;
  }
  const busca = normalizar(f.busca.trim());
  if (busca && !textoBuscavel(q).includes(busca)) return false;
  return true;
}

export function filtrarQuestoes(
  questoes: readonly QuestaoVestibular[],
  f: FiltroQuestoes,
): QuestaoVestibular[] {
  return questoes.filter((q) => passa(q, f));
}

// ─── Ordenação ───────────────────────────────────────────────────────────

/**
 * Ordem de prova: ano decrescente primeiro, porque a questão recente é a que
 * o aluno quer ver antes; dentro do ano, a ordem é a do caderno — vestibular,
 * fase e número. Devolve array novo: a lista de origem costuma vir do cache
 * do React Query, e ordenar no lugar mutaria o cache.
 */
export function ordenarPorProva(questoes: readonly QuestaoVestibular[]): QuestaoVestibular[] {
  return [...questoes].sort(
    (a, b) =>
      b.ano - a.ano ||
      a.vestibular.localeCompare(b.vestibular) ||
      a.fase - b.fase ||
      a.numero - b.numero,
  );
}

// ─── Agrupamento por bloco do edital ─────────────────────────────────────

export interface BlocoAgrupado<T> {
  blocoNome: string;
  topicos: T[];
}

/**
 * Agrupa tópicos pelo bloco do edital, preservando a ordem de chegada.
 *
 * Genérico porque serve aos dois tipos que carregam `blocoNome`:
 * `TopicoDaQuestao` (os tópicos de um cartão) e `RecorrenciaTopico` (a
 * estatística). Não ordena alfabeticamente de propósito: a API já manda na
 * ordem do edital (`topico_taxonomia.ordem`, 0028), e reordenar aqui trocaria
 * a sequência que o professor conhece por uma ordem de dicionário.
 */
export function agruparPorBloco<T extends { blocoNome: string }>(
  topicos: readonly T[],
): BlocoAgrupado<T>[] {
  const blocos = new Map<string, BlocoAgrupado<T>>();
  for (const t of topicos) {
    let bloco = blocos.get(t.blocoNome);
    if (!bloco) {
      bloco = { blocoNome: t.blocoNome, topicos: [] };
      blocos.set(t.blocoNome, bloco);
    }
    bloco.topicos.push(t);
  }
  return [...blocos.values()];
}

// ─── Recorrência ─────────────────────────────────────────────────────────

/**
 * Os `limite` tópicos mais recorrentes da matéria — o "o que mais cai" que
 * abre a aba de estatísticas.
 *
 * Empate desempata pelo nome para a ordem não dançar entre renderizações: com
 * 934 questões e três matérias, empate em `total` é comum, e `sort` estável
 * sobre uma lista que a API pode reordenar não basta.
 */
export function resumoRecorrencia(
  estatisticas: EstatisticasBanco,
  limite = 10,
): RecorrenciaTopico[] {
  if (limite <= 0) return [];
  return [...estatisticas.topicos]
    .sort((a, b) => b.total - a.total || a.nome.localeCompare(b.nome, 'pt-BR'))
    .slice(0, limite);
}

/**
 * Funde as respostas de `/banco/estatisticas` de duas bancas numa só.
 *
 * Existe porque a ficha do assunto precisa das DUAS séries separadas (uma linha
 * por vestibular, e `porVestibular` é agregado, sem quebra por ano), enquanto o
 * ranking ao lado precisa do total das duas. Buscar as duas e fundir aqui
 * resolve os dois com as MESMAS duas requisições — e, mais importante, garante
 * que o ranking e a ficha contem a mesma coisa: derivar um do outro é o que
 * impede as duas telas de mostrarem números diferentes do mesmo assunto.
 *
 * A soma é exata, e não uma aproximação: cada questão pertence a exatamente um
 * vestibular, então somar ITA e IME não conta ninguém duas vezes. (O que soma
 * duas vezes é a questão MISTA entre TÓPICOS, e isso é outra coisa e é de
 * propósito — docs/22 §1.5.)
 *
 * ⚠️ Chame só com as duas respostas presentes. Se uma falhou, o resultado desta
 * função seria "o mundo sem o IME" apresentado como "o mundo" — exatamente a
 * mentira que a tela tem de declarar em vez de desenhar.
 */
export function combinarEstatisticas(
  a: EstatisticasBanco,
  b: EstatisticasBanco,
): EstatisticasBanco {
  const somarContagens = (
    x: Record<number, number>,
    y: Record<number, number>,
  ): Record<number, number> => {
    const soma: Record<number, number> = {};
    for (const fonte of [x, y]) {
      for (const [chave, valor] of Object.entries(fonte)) {
        const k = Number(chave);
        soma[k] = (soma[k] ?? 0) + valor;
      }
    }
    return soma;
  };

  const somarTexto = (
    x: Record<string, number>,
    y: Record<string, number>,
  ): Record<string, number> => {
    const soma: Record<string, number> = { ...x };
    for (const [chave, valor] of Object.entries(y)) soma[chave] = (soma[chave] ?? 0) + valor;
    return soma;
  };

  const deB = new Map(b.topicos.map((t) => [t.codigo, t]));

  return {
    materia: a.materia,
    // A ordem canônica é recorrência decrescente, e ela muda ao somar: um
    // tópico que é 3º no ITA e 1º no IME pode virar 1º no total. Reordenar aqui
    // é o que mantém o ranking coerente com o número que ele mostra.
    topicos: a.topicos
      .map((topico) => {
        const outro = deB.get(topico.codigo);
        if (!outro) return topico;
        // ⚠️ `importancia` e `importanciaRanking` saem de propósito.
        //
        // Contagem soma; média ponderada NÃO. O índice de cada resposta é uma
        // média pesada por recência sobre o acervo DAQUELA banca — a média de
        // duas médias não é a média do conjunto, e o ITA e o IME nem têm os
        // mesmos anos (2008 contra 1996, migration 0031). Deixar o spread
        // carregar o índice do ITA para a visão "Os dois" daria um número
        // errado com cara de certo.
        //
        // Quem precisa do índice do conjunto pede ao servidor o recorte sem
        // vestibular: é lá que ele é calculado, uma vez, para todo mundo ver o
        // mesmo número (docs/34 §5 · D3).
        const { importancia: _i, importanciaRanking: _r, ...semIndice } = topico;
        return {
          ...semIndice,
          total: topico.total + outro.total,
          porAno: somarContagens(topico.porAno, outro.porAno),
          porFase: somarContagens(topico.porFase, outro.porFase),
          porVestibular: somarTexto(topico.porVestibular, outro.porVestibular),
        };
      })
      .sort((x, y) => y.total - x.total || x.nome.localeCompare(y.nome, 'pt-BR')),
    // União: o domínio do eixo passa a cobrir os dois acervos, que começam em
    // anos diferentes (migration 0031).
    anos: [...new Set([...a.anos, ...b.anos])].sort((x, y) => x - y),
    questoesPorAno: somarContagens(a.questoesPorAno, b.questoesPorAno),
    questoesClassificadasPorAno: somarContagens(
      a.questoesClassificadasPorAno,
      b.questoesClassificadasPorAno,
    ),
    totalQuestoes: a.totalQuestoes + b.totalQuestoes,
    semClassificacao: a.semClassificacao + b.semClassificacao,
  };
}

// ─── O filtro de anos ────────────────────────────────────────────────────
//
// É MÚLTIPLO, e começa com TODOS ligados (decisão de 02/09). A combinação das
// duas coisas obriga a uma convenção, porque "todos ligados" e "nenhum filtro"
// são o mesmo recorte com duas representações possíveis:
//
//   undefined   todos os anos — o filtro não está em vigor
//   [2024,2019] só estes
//   []          NUNCA. Ver `alternarAno`.
//
// `undefined` para "todos" — e não a lista cheia — mantém a URL curta no caso
// comum e, mais importante, faz um link compartilhado continuar significando
// "todos" quando o acervo ganhar um ano novo. Uma lista cheia gravada hoje
// excluiria 2026 em silêncio no dia em que ele fosse importado.

/**
 * Quais anos aparecem MARCADOS, dado o recorte e os anos que existem.
 *
 * É a tradução da convenção acima para a tela: sem filtro, todas as pílulas
 * acendem. Sem isto, "todos por padrão" viraria uma fileira apagada que diz ao
 * aluno que nada está selecionado — quando na verdade tudo está.
 */
export function anosMarcados(
  selecionados: readonly number[] | undefined,
  disponiveis: readonly number[],
): Set<number> {
  return new Set(selecionados ?? disponiveis);
}

/**
 * O novo recorte ao tocar num ano. Devolve `undefined` para "todos".
 *
 * Duas bordas, e as duas são decisão de produto:
 *
 *  · **Desmarcar o último volta para TODOS.** "Nenhum ano" é um recorte que só
 *    produz tela vazia, sempre — um beco sem informação. E o gesto de apagar a
 *    última marca é o que as pessoas fazem para recomeçar, então ele limpa o
 *    filtro em vez de zerar a tela.
 *  · **Marcar o último que faltava colapsa para TODOS.** Sem isso a URL
 *    carregaria os trinta anos do acervo para dizer o mesmo que dizer nada — e
 *    o link deixaria de valer para o ano que entrar depois.
 */
export function alternarAno(
  selecionados: readonly number[] | undefined,
  disponiveis: readonly number[],
  ano: number,
): number[] | undefined {
  const marcados = anosMarcados(selecionados, disponiveis);
  if (marcados.has(ano)) marcados.delete(ano);
  else marcados.add(ano);

  // Interseção com o acervo, e não a marcação crua: um ano que sobrou num link
  // velho e já saiu do banco não seleciona questão nenhuma, então carregá-lo
  // adiante só suja a URL. Sair pelo `disponiveis` também dá a ordem do acervo
  // de graça, sem depender de o chamador tê-lo ordenado.
  const validos = disponiveis.filter((a) => marcados.has(a));

  // Os dois extremos são o mesmo recorte — "todos" — e a mesma representação.
  if (validos.length === 0 || validos.length === disponiveis.length) return undefined;

  return [...validos].sort((a, b) => b - a);
}

export interface SerieAnual {
  anos: number[];
  totais: number[];
}

/**
 * A curva do tópico ao longo dos anos, em dois arrays paralelos —
 * `anos[i]` casa com `totais[i]`, que é o que `LinhaTemporal` desenha
 * (docs/22 §P4).
 *
 * O ano sem ocorrência vira **zero**, não some. `porAno` só traz os anos com
 * questão (schemas/banco.py), e desenhar só esses faria a curva pular de 2019
 * para 2021 como se 2020 não tivesse existido — a leitura sairia "caiu todo
 * ano" quando o certo é "não caiu em 2020".
 *
 * Ordena crescente porque o eixo X é tempo: a API manda `anos` ordenado, mas
 * uma curva com o eixo fora de ordem mente sem avisar.
 */
export function seriesPorAno(topico: RecorrenciaTopico, anos: readonly number[]): SerieAnual {
  const eixo = [...anos].sort((a, b) => a - b);
  return {
    anos: eixo,
    totais: eixo.map((ano) => topico.porAno[ano] ?? 0),
  };
}

// ─── Ordem manual da lista ───────────────────────────────────────────────

/**
 * Move um item de lugar, sem mutar a origem. É a mecânica de `posicao` da
 * `lista_questoes_item` (0029): a ordem é a escolhida por quem montou, e o
 * PATCH manda a lista inteira de uma vez (`AtualizarLista.questaoIds`).
 *
 * Índice fora da faixa é no-op, e não um `clamp`: o botão "subir" no primeiro
 * item pede `para = -1`, e o que o usuário espera ali é que nada aconteça —
 * grudar no extremo oposto seria movimento que ninguém pediu.
 */
export function reordenar<T>(ids: readonly T[], de: number, para: number): T[] {
  const copia = [...ids];
  const dentro = (i: number) => Number.isInteger(i) && i >= 0 && i < copia.length;
  if (!dentro(de) || !dentro(para) || de === para) return copia;
  const [item] = copia.splice(de, 1);
  copia.splice(para, 0, item);
  return copia;
}
