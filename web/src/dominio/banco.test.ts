import { describe, expect, it } from 'vitest';
import {
  FILTRO_QUESTOES_VAZIO,
  agruparPorBloco,
  algumFiltroAtivo,
  alternarAno,
  anosMarcados,
  chaveTopico,
  combinarEstatisticas,
  ehDissertativa,
  filtrarQuestoes,
  ordenarPorProva,
  reordenar,
  resumoRecorrencia,
  rotuloQuestao,
  seriesPorAno,
  temGabarito,
} from './banco';
import type { FiltroQuestoes } from './banco';
import type {
  EstatisticasBanco,
  QuestaoVestibular,
  RecorrenciaTopico,
  TopicoDaQuestao,
} from '../tipos/banco';

function topico(codigo: string, nome: string, blocoNome: string): TopicoDaQuestao {
  return { codigo, nome, blocoNome, confianca: 'alta', observacao: null };
}

function questao(p: Partial<QuestaoVestibular> & { id: string }): QuestaoVestibular {
  return {
    vestibular: 'ITA',
    ano: 2019,
    fase: 1,
    materia: 'Física',
    numero: 12,
    dissertativa: false,
    enunciadoMd: 'Um bloco desliza sobre um plano inclinado.',
    alternativas: { A: 'a', B: 'b' },
    gabarito: 'C',
    imagemUrl: null,
    usaImagemNoRender: false,
    resolucaoUrl: null,
    topicos: [topico('7.2', 'Ondas e Acústica', 'Oscilações e Ondas Mecânicas')],
    revisado: true,
    resolvida: null,
    anotacao: null,
    ...p,
  } as QuestaoVestibular;
}

function recorrencia(p: Partial<RecorrenciaTopico> & { codigo: string }): RecorrenciaTopico {
  return {
    nome: p.codigo,
    blocoNome: 'Bloco',
    total: 0,
    porAno: {},
    porFase: {},
    porVestibular: {},
    ...p,
  } as RecorrenciaTopico;
}

const filtro = (p: Partial<FiltroQuestoes>): FiltroQuestoes => ({ ...FILTRO_QUESTOES_VAZIO, ...p });
const ids = (qs: QuestaoVestibular[]) => qs.map((q) => q.id);

describe('rotuloQuestao', () => {
  it('compõe vestibular, ano, matéria, fase e número', () => {
    const q = questao({ id: 'ita_2019_fase1_q12', vestibular: 'ITA', ano: 2019, fase: 1, numero: 12 });
    expect(rotuloQuestao(q)).toBe('ITA 2019 · Física · Fase 1 · nº 12');
  });

  it('serve igual para a 2ª fase do IME', () => {
    const q = questao({ id: 'ime_2023_fase2_q03', vestibular: 'IME', ano: 2023, fase: 2, numero: 3 });
    expect(rotuloQuestao(q)).toBe('IME 2023 · Física · Fase 2 · nº 3');
  });

  // O caso que motivou pôr a matéria no rótulo: mesma prova, mesmo número,
  // questões diferentes. Sem ela os dois cartões ficam com o mesmo nome.
  it('distingue duas questões nº 1 da mesma prova, de matérias diferentes', () => {
    const mat = questao({ id: 'ime_2025_fase2_mat_q01', vestibular: 'IME', ano: 2025, fase: 2, numero: 1, materia: 'Matemática' });
    const fis = questao({ id: 'ime_2025_fase2_q01', vestibular: 'IME', ano: 2025, fase: 2, numero: 1, materia: 'Física' });
    expect(rotuloQuestao(mat)).not.toBe(rotuloQuestao(fis));
  });
});

describe('temGabarito e ehDissertativa', () => {
  it('reconhece a objetiva com letra', () => {
    const q = questao({ id: 'q1', gabarito: 'C' });
    expect(temGabarito(q)).toBe(true);
    expect(ehDissertativa(q)).toBe(false);
  });

  // 469 das 934 não têm gabarito, e a maioria por serem dissertativas
  // (docs/22 §1.4): ausência esperada, não dado faltando.
  it('dissertativa não tem gabarito, e isso não é defeito', () => {
    const q = questao({ id: 'q2', dissertativa: true, gabarito: null, alternativas: null });
    expect(ehDissertativa(q)).toBe(true);
    expect(temGabarito(q)).toBe(false);
  });

  it('trata gabarito em branco como ausente', () => {
    expect(temGabarito(questao({ id: 'q3', gabarito: '   ' }))).toBe(false);
    expect(temGabarito(questao({ id: 'q4', gabarito: null }))).toBe(false);
  });
});

describe('filtrarQuestoes', () => {
  const DADOS = [
    questao({ id: 'Q1', vestibular: 'ITA', ano: 2019, fase: 1, materia: 'Física' }),
    questao({ id: 'Q2', vestibular: 'ITA', ano: 2021, fase: 2, materia: 'Física', dissertativa: true }),
    questao({ id: 'Q3', vestibular: 'IME', ano: 2019, fase: 1, materia: 'Matemática' }),
  ];

  it('sem filtro devolve tudo', () => {
    expect(ids(filtrarQuestoes(DADOS, FILTRO_QUESTOES_VAZIO))).toEqual(['Q1', 'Q2', 'Q3']);
  });

  it('faz OR dentro da categoria', () => {
    expect(ids(filtrarQuestoes(DADOS, filtro({ anos: new Set([2019, 2021]) }))))
      .toEqual(['Q1', 'Q2', 'Q3']);
  });

  it('faz AND entre categorias', () => {
    expect(ids(filtrarQuestoes(DADOS, filtro({
      vestibulares: new Set(['ITA']),
      anos: new Set([2019]),
    })))).toEqual(['Q1']);
  });

  it('filtra por fase e por matéria', () => {
    expect(ids(filtrarQuestoes(DADOS, filtro({ fases: new Set([2]) })))).toEqual(['Q2']);
    expect(ids(filtrarQuestoes(DADOS, filtro({ materias: new Set(['Matemática']) })))).toEqual(['Q3']);
  });

  it('não muta a lista de origem', () => {
    const copia = [...DADOS];
    filtrarQuestoes(DADOS, filtro({ anos: new Set([2019]) }));
    expect(DADOS).toEqual(copia);
  });

  describe('busca', () => {
    const COM_TEXTO = [
      questao({ id: 'B1', enunciadoMd: 'Cálculo da variação de entropia.' }),
      questao({
        id: 'B2',
        enunciadoMd: 'Um corpo em repouso.',
        topicos: [topico('4.1', 'Termodinâmica', 'Calor')],
      }),
    ];

    it('ignora acento e caixa', () => {
      expect(ids(filtrarQuestoes(COM_TEXTO, filtro({ busca: 'ENTROPIA' })))).toEqual(['B1']);
      expect(ids(filtrarQuestoes(COM_TEXTO, filtro({ busca: 'calculo' })))).toEqual(['B1']);
    });

    it('acha pelo nome do tópico e pelo id', () => {
      expect(ids(filtrarQuestoes(COM_TEXTO, filtro({ busca: 'termodinamica' })))).toEqual(['B2']);
      expect(ids(filtrarQuestoes(COM_TEXTO, filtro({ busca: 'b1' })))).toEqual(['B1']);
    });

    it('busca só com espaço não filtra nada', () => {
      expect(ids(filtrarQuestoes(COM_TEXTO, filtro({ busca: '   ' })))).toEqual(['B1', 'B2']);
    });
  });

  describe('tópicos', () => {
    // Questão mista é a REGRA, não a exceção (docs/22 §1.2): ela casa por
    // qualquer um dos tópicos dela.
    const MISTA = questao({
      id: 'MISTA',
      materia: 'Física',
      topicos: [
        topico('7.2', 'Ondas e Acústica', 'Oscilações e Ondas Mecânicas'),
        topico('3.1', 'Energia', 'Mecânica'),
      ],
    });
    const SIMPLES = questao({
      id: 'SIMPLES',
      materia: 'Física',
      topicos: [topico('3.1', 'Energia', 'Mecânica')],
    });

    it('a mista aparece nos dois tópicos', () => {
      const porOndas = filtrarQuestoes([MISTA, SIMPLES], filtro({
        topicos: new Set([chaveTopico('Física', '7.2')]),
      }));
      const porEnergia = filtrarQuestoes([MISTA, SIMPLES], filtro({
        topicos: new Set([chaveTopico('Física', '3.1')]),
      }));
      expect(ids(porOndas)).toEqual(['MISTA']);
      expect(ids(porEnergia)).toEqual(['MISTA', 'SIMPLES']);
    });

    it('com os dois tópicos marcados, a mista entra UMA vez', () => {
      const r = filtrarQuestoes([MISTA, SIMPLES], filtro({
        topicos: new Set([chaveTopico('Física', '7.2'), chaveTopico('Física', '3.1')]),
      }));
      expect(ids(r)).toEqual(['MISTA', 'SIMPLES']);
    });

    // '1.1' existe nas três matérias e significa coisa diferente em cada uma
    // (0028). Chave só por código misturaria as três em silêncio.
    it('o mesmo código em matérias diferentes não vaza', () => {
      const fisica = questao({
        id: 'FIS',
        materia: 'Física',
        topicos: [topico('1.1', 'Fundamentos', 'Introdução')],
      });
      const matematica = questao({
        id: 'MAT',
        materia: 'Matemática',
        topicos: [topico('1.1', 'Conjuntos e Lógica', 'Fundamentos')],
      });
      const r = filtrarQuestoes([fisica, matematica], filtro({
        topicos: new Set([chaveTopico('Matemática', '1.1')]),
      }));
      expect(ids(r)).toEqual(['MAT']);
    });

    it('questão sem classificação some quando há filtro de tópico', () => {
      const semTopico = questao({ id: 'SEM', topicos: [] });
      expect(ids(filtrarQuestoes([MISTA, semTopico], filtro({
        topicos: new Set([chaveTopico('Física', '7.2')]),
      })))).toEqual(['MISTA']);
      expect(ids(filtrarQuestoes([MISTA, semTopico], FILTRO_QUESTOES_VAZIO)))
        .toEqual(['MISTA', 'SEM']);
    });
  });
});

describe('algumFiltroAtivo', () => {
  it('reconhece vazio, chip marcado e busca escrita', () => {
    expect(algumFiltroAtivo(FILTRO_QUESTOES_VAZIO)).toBe(false);
    expect(algumFiltroAtivo(filtro({ anos: new Set([2019]) }))).toBe(true);
    expect(algumFiltroAtivo(filtro({ busca: 'onda' }))).toBe(true);
    expect(algumFiltroAtivo(filtro({ busca: '  ' }))).toBe(false);
  });
});

describe('ordenarPorProva', () => {
  it('ano decrescente, depois vestibular, fase e número', () => {
    const embaralhado = [
      questao({ id: 'ita_2019_f1_q02', vestibular: 'ITA', ano: 2019, fase: 1, numero: 2 }),
      questao({ id: 'ita_2021_f2_q01', vestibular: 'ITA', ano: 2021, fase: 2, numero: 1 }),
      questao({ id: 'ita_2019_f1_q01', vestibular: 'ITA', ano: 2019, fase: 1, numero: 1 }),
      questao({ id: 'ime_2021_f1_q09', vestibular: 'IME', ano: 2021, fase: 1, numero: 9 }),
      questao({ id: 'ita_2021_f1_q01', vestibular: 'ITA', ano: 2021, fase: 1, numero: 1 }),
    ];
    expect(ids(ordenarPorProva(embaralhado))).toEqual([
      'ime_2021_f1_q09',
      'ita_2021_f1_q01',
      'ita_2021_f2_q01',
      'ita_2019_f1_q01',
      'ita_2019_f1_q02',
    ]);
  });

  it('devolve array novo, sem mexer na origem', () => {
    const original = [
      questao({ id: 'A', ano: 2018 }),
      questao({ id: 'B', ano: 2025 }),
    ];
    const ordenado = ordenarPorProva(original);
    expect(ids(ordenado)).toEqual(['B', 'A']);
    expect(ids(original)).toEqual(['A', 'B']);
  });

  it('aguenta lista vazia', () => {
    expect(ordenarPorProva([])).toEqual([]);
  });
});

describe('agruparPorBloco', () => {
  it('junta os tópicos de cada bloco preservando a ordem do edital', () => {
    const topicos = [
      topico('1.1', 'Fundamentos', 'Introdução'),
      topico('3.1', 'Energia', 'Mecânica'),
      topico('3.2', 'Impulso', 'Mecânica'),
      topico('7.2', 'Ondas e Acústica', 'Oscilações'),
    ];
    const blocos = agruparPorBloco(topicos);
    expect(blocos.map((b) => b.blocoNome)).toEqual(['Introdução', 'Mecânica', 'Oscilações']);
    expect(blocos[1].topicos.map((t) => t.codigo)).toEqual(['3.1', '3.2']);
  });

  // A questão mista carrega tópicos de blocos diferentes — os dois têm que
  // aparecer no cartão, e não só o primeiro.
  it('espalha a questão mista pelos dois blocos dela', () => {
    const mista = questao({
      id: 'MISTA',
      topicos: [
        topico('7.2', 'Ondas e Acústica', 'Oscilações'),
        topico('3.1', 'Energia', 'Mecânica'),
      ],
    });
    const blocos = agruparPorBloco(mista.topicos);
    expect(blocos.map((b) => b.blocoNome)).toEqual(['Oscilações', 'Mecânica']);
    expect(blocos.every((b) => b.topicos.length === 1)).toBe(true);
  });

  it('serve também à estatística, que tem outro tipo com o mesmo blocoNome', () => {
    const blocos = agruparPorBloco([
      recorrencia({ codigo: '3.1', blocoNome: 'Mecânica', total: 9 }),
      recorrencia({ codigo: '3.2', blocoNome: 'Mecânica', total: 4 }),
    ]);
    expect(blocos).toHaveLength(1);
    expect(blocos[0].topicos.map((t) => t.total)).toEqual([9, 4]);
  });

  it('lista vazia vira nenhum bloco', () => {
    expect(agruparPorBloco([])).toEqual([]);
  });
});

describe('resumoRecorrencia', () => {
  const estatisticas = {
    materia: 'Física',
    anos: [2018, 2019, 2020],
    totalQuestoes: 30,
    semClassificacao: 2,
    topicos: [
      recorrencia({ codigo: '1.1', nome: 'Fundamentos', total: 3 }),
      recorrencia({ codigo: '7.2', nome: 'Ondas e Acústica', total: 11 }),
      recorrencia({ codigo: '3.1', nome: 'Energia', total: 7 }),
      recorrencia({ codigo: '4.1', nome: 'Calorimetria', total: 7 }),
    ],
  } as EstatisticasBanco;

  it('devolve os N mais recorrentes, do maior para o menor', () => {
    expect(resumoRecorrencia(estatisticas, 2).map((t) => t.nome))
      .toEqual(['Ondas e Acústica', 'Calorimetria']);
  });

  // Empate em `total` é comum com 934 questões; sem desempate estável a ordem
  // dançaria a cada renderização.
  it('desempata pelo nome', () => {
    expect(resumoRecorrencia(estatisticas, 3).map((t) => t.nome))
      .toEqual(['Ondas e Acústica', 'Calorimetria', 'Energia']);
  });

  it('limite maior que a lista devolve a lista inteira', () => {
    expect(resumoRecorrencia(estatisticas, 99)).toHaveLength(4);
  });

  it('limite zero ou negativo devolve nada', () => {
    expect(resumoRecorrencia(estatisticas, 0)).toEqual([]);
    expect(resumoRecorrencia(estatisticas, -1)).toEqual([]);
  });

  it('não muta a ordem que veio da API', () => {
    resumoRecorrencia(estatisticas, 2);
    expect(estatisticas.topicos.map((t) => t.codigo)).toEqual(['1.1', '7.2', '3.1', '4.1']);
  });
});

describe('seriesPorAno', () => {
  const topicoOndas = recorrencia({
    codigo: '7.2',
    nome: 'Ondas e Acústica',
    total: 8,
    porAno: { 2018: 3, 2019: 5 },
  });

  // O ano sem ocorrência tem que virar zero: se sumisse, a curva pularia de
  // 2019 para 2021 e leria "caiu todo ano" onde o certo é "não caiu em 2020".
  it('ano sem ocorrência vira zero e não some', () => {
    const s = seriesPorAno(topicoOndas, [2018, 2019, 2020, 2021]);
    expect(s.anos).toEqual([2018, 2019, 2020, 2021]);
    expect(s.totais).toEqual([3, 5, 0, 0]);
  });

  it('os dois arrays têm sempre o mesmo tamanho do eixo pedido', () => {
    const s = seriesPorAno(recorrencia({ codigo: '1.1' }), [2018, 2019, 2020]);
    expect(s.anos).toHaveLength(s.totais.length);
    expect(s.totais).toEqual([0, 0, 0]);
  });

  it('ordena o eixo crescente mesmo recebendo fora de ordem', () => {
    const s = seriesPorAno(topicoOndas, [2019, 2018]);
    expect(s.anos).toEqual([2018, 2019]);
    expect(s.totais).toEqual([3, 5]);
  });

  it('ano com ocorrência fora do eixo pedido não entra', () => {
    const s = seriesPorAno(topicoOndas, [2019]);
    expect(s.anos).toEqual([2019]);
    expect(s.totais).toEqual([5]);
  });

  it('não muta o array de anos recebido', () => {
    const anos = [2020, 2018, 2019];
    seriesPorAno(topicoOndas, anos);
    expect(anos).toEqual([2020, 2018, 2019]);
  });
});

describe('reordenar', () => {
  const LISTA = ['a', 'b', 'c', 'd'];

  it('move do meio para o meio', () => {
    expect(reordenar(LISTA, 1, 2)).toEqual(['a', 'c', 'b', 'd']);
  });

  it('move o primeiro para o último', () => {
    expect(reordenar(LISTA, 0, 3)).toEqual(['b', 'c', 'd', 'a']);
  });

  it('move o último para o primeiro', () => {
    expect(reordenar(LISTA, 3, 0)).toEqual(['d', 'a', 'b', 'c']);
  });

  // "Subir" no primeiro item pede `para = -1`; o esperado ali é nada
  // acontecer, não o item grudar no extremo oposto.
  it('índice fora da faixa é no-op', () => {
    expect(reordenar(LISTA, 0, -1)).toEqual(LISTA);
    expect(reordenar(LISTA, 3, 4)).toEqual(LISTA);
    expect(reordenar(LISTA, -1, 0)).toEqual(LISTA);
    expect(reordenar(LISTA, 9, 0)).toEqual(LISTA);
  });

  it('mesma posição é no-op', () => {
    expect(reordenar(LISTA, 2, 2)).toEqual(LISTA);
  });

  it('devolve array novo e não muta a origem', () => {
    const r = reordenar(LISTA, 0, 1);
    expect(r).not.toBe(LISTA);
    expect(LISTA).toEqual(['a', 'b', 'c', 'd']);
  });

  it('lista de um item e lista vazia não quebram', () => {
    expect(reordenar(['só'], 0, 0)).toEqual(['só']);
    expect(reordenar([], 0, 0)).toEqual([]);
  });
});

describe('combinarEstatisticas', () => {
  // A ficha do assunto precisa das duas bancas SEPARADAS (uma linha por
  // vestibular) e o ranking ao lado precisa da soma. Fundir aqui resolve os
  // dois com as mesmas duas requisições — e garante que as duas telas contem a
  // mesma coisa, em vez de somarem por caminhos diferentes.

  function resposta(
    materia: 'Matemática',
    topicos: { codigo: string; nome: string; total: number; porAno: Record<number, number> }[],
    anos: number[],
    questoesPorAno: Record<number, number>,
    semClassificacao = 0,
  ) {
    return {
      materia,
      topicos: topicos.map((t) => ({
        codigo: t.codigo,
        nome: t.nome,
        blocoNome: 'Geometria',
        total: t.total,
        porAno: t.porAno,
        porFase: {},
        porVestibular: {},
      })),
      anos,
      questoesPorAno,
      totalQuestoes: Object.values(questoesPorAno).reduce((s, v) => s + v, 0),
      semClassificacao,
    };
  }

  const ita = resposta(
    'Matemática',
    [
      { codigo: '1.1', nome: 'Trigonometria', total: 5, porAno: { 2019: 3, 2020: 2 } },
      { codigo: '1.2', nome: 'Geometria analítica', total: 1, porAno: { 2020: 1 } },
    ],
    [2019, 2020],
    { 2019: 20, 2020: 20 },
    2,
  );

  const ime = resposta(
    'Matemática',
    [
      { codigo: '1.1', nome: 'Trigonometria', total: 1, porAno: { 1998: 1 } },
      { codigo: '1.2', nome: 'Geometria analítica', total: 7, porAno: { 1998: 4, 2019: 3 } },
    ],
    [1998, 2019],
    { 1998: 10, 2019: 10 },
    1,
  );

  it('soma os totais dos tópicos sem contar ninguém duas vezes', () => {
    // Cada questão pertence a um vestibular só, então a soma é exata. (O que
    // conta duas vezes é a questão MISTA entre tópicos, e isso é de propósito.)
    const junto = combinarEstatisticas(ita, ime);
    const porCodigo = Object.fromEntries(junto.topicos.map((t) => [t.codigo, t.total]));

    expect(porCodigo).toEqual({ '1.1': 6, '1.2': 8 });
  });

  it('reordena pelo total somado, e não mantém a ordem do ITA', () => {
    // 1.1 lidera no ITA (5 contra 1) e 1.2 lidera no total (8 contra 6).
    // Manter a ordem da primeira resposta faria o ranking contradizer o número
    // que ele mostra ao lado.
    const junto = combinarEstatisticas(ita, ime);
    expect(junto.topicos.map((t) => t.codigo)).toEqual(['1.2', '1.1']);
  });

  it('une os anos dos dois acervos, que começam em anos diferentes', () => {
    const junto = combinarEstatisticas(ita, ime);
    expect(junto.anos).toEqual([1998, 2019, 2020]);
  });

  it('soma o denominador ano a ano', () => {
    // 2019 tem prova nas duas bancas: 20 do ITA mais 10 do IME.
    const junto = combinarEstatisticas(ita, ime);
    expect(junto.questoesPorAno).toEqual({ 1998: 10, 2019: 30, 2020: 20 });
  });

  it('soma porAno de cada tópico', () => {
    const junto = combinarEstatisticas(ita, ime);
    const trigonometria = junto.topicos.find((t) => t.codigo === '1.1');
    expect(trigonometria?.porAno).toEqual({ 1998: 1, 2019: 3, 2020: 2 });
  });

  it('soma as sem classificação, que não podem sumir de nenhum dos dois lados', () => {
    const junto = combinarEstatisticas(ita, ime);
    expect(junto.semClassificacao).toBe(3);
    expect(junto.totalQuestoes).toBe(60);
  });

  it('tópico presente só numa das bancas atravessa intacto', () => {
    const so = resposta('Matemática', [], [2019], { 2019: 20 });
    const junto = combinarEstatisticas(ita, so);
    expect(junto.topicos.map((t) => t.total)).toEqual([5, 1]);
  });
});

describe('o filtro de anos', () => {
  // Múltipla escolha, começando com TODOS ligados (decisão de 02/09). O que
  // estes testes travam é a convenção que as duas coisas juntas exigem:
  // `undefined` significa "todos", e a lista cheia nunca chega à URL.

  const ACERVO = [2025, 2024, 2023, 2022];

  describe('anosMarcados', () => {
    it('sem filtro, TODAS as pílulas acendem', () => {
      // É o requisito de origem: uma fileira apagada diria ao aluno que nada
      // está selecionado, quando tudo está.
      expect([...anosMarcados(undefined, ACERVO)].sort()).toEqual([2022, 2023, 2024, 2025]);
    });

    it('com filtro, só os escolhidos', () => {
      expect([...anosMarcados([2024, 2022], ACERVO)].sort()).toEqual([2022, 2024]);
    });
  });

  describe('alternarAno', () => {
    it('o primeiro toque DESMARCA, porque tudo começa marcado', () => {
      expect(alternarAno(undefined, ACERVO, 2023)).toEqual([2025, 2024, 2022]);
    });

    it('desmarcar mais um vai tirando da lista', () => {
      expect(alternarAno([2025, 2024, 2022], ACERVO, 2022)).toEqual([2025, 2024]);
    });

    it('marcar de volta o que faltava colapsa para TODOS', () => {
      // Sem o colapso, a URL carregaria os quatro anos para dizer o mesmo que
      // dizer nada — e o link deixaria de valer para o ano que entrar depois.
      expect(alternarAno([2025, 2024, 2023], ACERVO, 2022)).toBeUndefined();
    });

    it('desmarcar o ÚLTIMO volta para todos, e não para nenhum', () => {
      // "Nenhum ano" só produz tela vazia, sempre. Apagar a última marca é o
      // gesto de recomeçar, então ele limpa o filtro.
      expect(alternarAno([2024], ACERVO, 2024)).toBeUndefined();
    });

    it('a ordem é decrescente: o ano recente é o que o aluno procura antes', () => {
      expect(alternarAno([2022, 2025], ACERVO, 2023)).toEqual([2025, 2023, 2022]);
    });

    it('descarta ano que já não existe no acervo', () => {
      // `?anos=1999,2025` num link velho: 1999 saiu do banco e não seleciona
      // questão nenhuma. Carregá-lo adiante só sujaria a URL.
      expect(alternarAno([1999, 2025], ACERVO, 2024)).toEqual([2025, 2024]);
    });

    it('um ano morto não impede o recorte de virar "todos"', () => {
      // Os quatro anos do acervo estão marcados; o 1999 pendurado não muda
      // isso, e o recorte É todos.
      expect(alternarAno([1999, 2025, 2024, 2023], ACERVO, 2022)).toBeUndefined();
    });

    it('acervo vazio não quebra', () => {
      expect(alternarAno(undefined, [], 2024)).toBeUndefined();
    });
  });
});
