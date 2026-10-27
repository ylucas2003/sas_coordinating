// AS DUAS NOTAS CONTRA O CORTE — qual delas a tela mostra, e com que nome.
//
// A mesma matéria tem DUAS notas contra o corte na área do aluno, e as duas
// estão certas — cada uma responde a uma pergunta (decisão do dono de 26/10):
//
//   - a do ÚLTIMO SIMULADO: a nota do ciclo mais recente que tem prova daquela
//     matéria, de `GET /me/evolucao`. É a das barras da Hoje;
//   - a que CONTA NA RÉGUA: a que o avaliador da régua usa para dar a zona
//     (`api/app/stats/criterios.py`), de `GET /me/zona`. É a do cartão
//     `barras_corte` do Tio Léo e a da própria zona — a frase da zona na Hoje
//     e o topo da Jornada (`NOME_DA_MEDIA_DA_ZONA`).
//
// Na verificação no browser de 26/10 a aluna via Física 4,3 na Hoje e 4,6 no
// Tio Léo, sem nome nenhum, e um dos dois números parecia errado. NADA muda
// no cálculo: cada número passa a dizer o que é.

/** Que notas um gráfico de barras contra o corte está mostrando. */
export type NotasDaBarra = 'ultimo-simulado' | 'regua';

/** O nome que cada uma leva na tela — curto, em cima das barras. */
export const LEGENDA_DAS_NOTAS: Record<NotasDaBarra, string> = {
  'ultimo-simulado': 'Notas no último simulado',
  regua: 'Notas que contam na régua',
};

/**
 * O nome da MÉDIA da zona (`GET /me/zona`, campo `media`), no meio da frase:
 * "Sua média que conta na régua é 4,7".
 *
 * É a média das notas `regua` — as que o avaliador usa para dar a zona, as
 * mesmas do cartão do Tio Léo —, e não a do último simulado. A Jornada dizia só
 * "Sua média é 4,7", e quem tinha acabado de ver as barras da Hoje (do último
 * simulado) achava um número que não batia com nenhuma delas. Mora aqui, ao
 * lado de `LEGENDA_DAS_NOTAS`, para o nome da média e o das notas não se
 * separarem num ajuste de texto.
 */
export const NOME_DA_MEDIA_DA_ZONA = 'média que conta na régua';

/** O pedaço de `EvolucaoAluno` (`tipos/aluno.ts`) que esta regra lê. */
interface EvolucaoParaCorte {
  /** Por matéria, a série do aluno, paralela aos ciclos — `null` onde não houve prova. */
  materias: Record<string, { aluno: ReadonlyArray<number | null> } | undefined>;
}

/**
 * As barras da Hoje: o corte da régua (`/me/zona`) com a nota do último
 * simulado (`/me/evolucao`) — e o nome que essas notas levam.
 *
 * Uma matéria sem nota na evolução SAI da lista, em vez de cair na nota da
 * régua: mostrar ao aluno uma nota que ele não tirou é pior que mostrar uma
 * barra a menos, e misturar as duas notas no mesmo gráfico, sob um nome só, é
 * o defeito que esta regra existe para evitar.
 *
 * ⚠️ Quando a evolução inteira não veio — carregando, erro, ou aluno sem nota
 * nenhuma —, o gráfico mostra a lista de `/me/zona` como ela veio, e ESSA
 * lista traz a nota da régua. O nome acompanha a fonte: "que contam na régua".
 * Dizer "no último simulado" aí seria pôr o rótulo de uma nota na outra.
 */
export function notasContraCorte<T extends { materia: string; nota: number }>(
  cortes: readonly T[] | undefined,
  evolucao: EvolucaoParaCorte | null | undefined,
): { materias: T[]; notas: NotasDaBarra } {
  if (!cortes) return { materias: [], notas: 'regua' };
  if (!evolucao) return { materias: [...cortes], notas: 'regua' };

  const materias = cortes.flatMap((materia) => {
    // A série é paralela a `ciclos` e traz `null` no ciclo em que não houve
    // prova daquela matéria; a nota que vale é a do ciclo mais recente que tem.
    const serie = evolucao.materias[materia.materia]?.aluno ?? [];
    const ultima = serie.reduce<number | null>((achada, n) => (n == null ? achada : n), null);
    return ultima == null ? [] : [{ ...materia, nota: ultima }];
  });
  return { materias, notas: 'ultimo-simulado' };
}
