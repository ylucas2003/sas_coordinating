// O TOUR — os seis passos, o que cada um explica e para onde ele aponta hoje.
//
// O conteúdo veio pronto da prancheta de Provas (Claude Design, `a8bf25f7`,
// `passos`/`passo`) e está aqui LITERAL, sem reescrita: os textos foram
// escritos com o código à vista e nomeiam a regra de desenho que justifica
// cada tela. Reescrevê-los seria perder a única explicação que o produto tem
// de por que ele é assim.
//
// ⚠️ O QUE MUDA AO SAIR DA PRANCHETA é o DESTINO, e é por isso que este
// arquivo existe em vez de um array dentro do componente. Lá o tour trocava a
// tela do mock junto com o passo — no produto ele explica seis telas que o
// coordenador vai abrir depois, e TRÊS delas mudaram de endereço na
// refatoração do docs/39:
//
//   A BIFURCAÇÃO  `/provas` era a lista de ciclos com abas (`?aba=simulados`)
//                 e virou o hub de duas portas (fase 3).
//   A RÉGUA       morava em `/ciclos/:id/regua`, tela própria. A régua e a
//                 tabela dela foram ABSORVIDAS pela ficha do ciclo, e o
//                 endereço antigo hoje só redireciona (`App.tsx`).
//   A VARREDURA   era a tabela do `/painel`. Ela sempre foi de UM ciclo, e
//                 desceu para a ficha dele na fase 2.
//
// Um tour que apontasse para os endereços velhos ensinaria a procurar onde
// não está — pior do que não ensinar. O teste ao lado ("nunca aponta para um
// endereço que a refatoração aposentou") trava os três para sempre.

import { ciclosNoRecorte, cicloPadrao, recorteCompleto } from './painelFiltros';
import type { Ciclo, Simulado } from '../tipos/dominio';

/** O quadro da prancheta, em que as regiões abaixo estão medidas. */
export const QUADRO = { largura: 1440, altura: 900 } as const;

/** A largura do rail fechado (`--rail-w`), para o esquema desenhar a coluna. */
export const RAIL = 88;

export type ChaveDoPasso = 'bifurcacao' | 'regua' | 'campos' | 'varredura' | 'mapa' | 'lugar';

/** A região destacada, em coordenadas do `QUADRO`. */
export interface Regiao {
  x: number;
  y: number;
  largura: number;
  altura: number;
}

export interface PassoDoTour {
  chave: ChaveDoPasso;
  /** O olho em caixa alta — o apelido do passo. */
  olho: string;
  titulo: string;
  texto: string;
  /** A regra de desenho que justifica a tela. É o que separa tour de tutorial. */
  regra: string;
  regiao: Regiao;
}

/**
 * Os seis, na ordem, com os textos da prancheta.
 *
 * A ordem é a do trabalho, não a do menu: escolher a leitura (a bifurcação),
 * declarar a régua, ver o que a tela pergunta por você, varrer, achar a prova
 * estranha e entender a prova achada. Um passo fora de ordem quebra a frase.
 */
export const PASSOS: readonly PassoDoTour[] = [
  {
    chave: 'bifurcacao',
    olho: 'A BIFURCAÇÃO',
    titulo: 'Duas leituras, não dois tipos de objeto',
    texto:
      'O ciclo responde “como o grupo está fechando contra a régua” — leitura por pessoa. A prova responde “a medida funcionou” — leitura por instrumento. Por isso as pendências operacionais ficam no segundo card: falha de prova é problema de instrumento.',
    regra: 'C1 · a divisão é por pergunta, nunca por tipo de objeto nem por recência.',
    regiao: { x: 112, y: 130, largura: 1080, altura: 700 },
  },
  {
    chave: 'regua',
    olho: 'A RÉGUA',
    titulo: 'Uma lente, não um filtro',
    texto:
      'O seletor no topo decide o corte da tabela e dos dois campos ao mesmo tempo. Trocar de régua muda quem está cortado, e é por isso que ele fica na linha da identidade, numa moldura de ouro, longe da faixa de pílulas da tabela.',
    regra: 'R2 · a régua é ouro e está sempre desenhada.',
    regiao: { x: 700, y: 86, largura: 712, altura: 104 },
  },
  {
    chave: 'campos',
    olho: 'OS CAMPOS',
    titulo: 'Perguntas que ninguém sabe que quer fazer',
    texto:
      '“A prova estava boa?” e “Onde estamos diferentes?” são cards, e não itens de menu, porque o coordenador não os procuraria. Mas eles viraram faixa fina ao lado dos KPIs: se ocupassem meia tela, a varredura — que é a tarefa dominante do dia — pagaria a conta todo dia.',
    regra: 'C3 · o destino é tela inteira, com URL própria.',
    regiao: { x: 842, y: 168, largura: 574, altura: 244 },
  },
  {
    chave: 'varredura',
    olho: 'A VARREDURA',
    titulo: 'A tela entrega o pior primeiro',
    texto:
      'Sem cor semântica, quem acha o aluno em risco é a ordenação: a tabela abre por distância do corte, ascendente, com o ordenador nomeado. Situação diz o motivo em palavras — “Física 3,2 < 4,0” — e Distância, o tamanho do buraco. Ao rolar, a régua e os campos encolhem para a tira do topo.',
    regra: 'R6 · a ordenação faz o trabalho que a cor fazia.',
    regiao: { x: 112, y: 68, largura: 1304, altura: 808 },
  },
  {
    chave: 'mapa',
    olho: 'O MAPA',
    titulo: 'Doze provas na mesma escala',
    texto:
      'A calibração é onde se ACHA a prova estranha: os doze histogramas dividem o mesmo pico, então a barra mais alta de Física não fica do tamanho da de Português. A matéria fora do padrão ganha destaque por tamanho e posição, nunca por cor.',
    regra: 'Média e mediana são referência cinza; só o corte é ouro.',
    regiao: { x: 112, y: 176, largura: 1304, altura: 698 },
  },
  {
    chave: 'lugar',
    olho: 'O LUGAR',
    titulo: 'E onde se entende a prova que você achou',
    texto:
      'A ficha é o mesmo histograma em outro tamanho, com as irmãs do mesmo dia, as sedes e as notas individuais. Ausência tem forma própria, nunca zero — falta contando como zero deturpa toda média. E clicar numa nota abre o diálogo de escrita, com diff antes de gravar.',
    regra: 'Ausência e zero são coisas diferentes no domínio.',
    regiao: { x: 112, y: 150, largura: 1304, altura: 724 },
  },
];

/**
 * O que o tour tem em mãos para transformar cada passo num endereço de verdade.
 *
 * Tudo pode ser `null`: em janeiro não há ciclo nem prova, e o tour continua
 * valendo como leitura — o que ele não pode é oferecer um botão que abre a
 * ficha de um ciclo que não existe.
 */
export interface AncoraDoTour {
  cicloId: string | null;
  /** "Ciclo 4 · ITA · 2026" — o que o botão promete abrir. */
  nomeDoCiclo: string | null;
  provaId: string | null;
  /** "Física · P8". */
  nomeDaProva: string | null;
}

export const ANCORA_VAZIA: AncoraDoTour = {
  cicloId: null,
  nomeDoCiclo: null,
  provaId: null,
  nomeDaProva: null,
};

export interface DestinoDoPasso {
  para: string;
  /** O rótulo do botão. Nomeia a COISA que abre, não a ação. */
  rotulo: string;
}

/**
 * Para onde o passo aponta HOJE, ou `null` quando não há o que abrir.
 *
 * Três passos — régua, campos e varredura — caem no MESMO endereço, e isso é o
 * desenho, não um descuido: a ficha do ciclo absorveu as três coisas na fase 3.
 * O tour continua contando três histórias porque são três perguntas
 * diferentes; o que mudou foi que agora elas se respondem sem trocar de tela.
 */
export function destinoDoPasso(chave: ChaveDoPasso, ancora: AncoraDoTour): DestinoDoPasso | null {
  const { cicloId, nomeDoCiclo, provaId, nomeDaProva } = ancora;
  const ciclo = nomeDoCiclo ?? 'o ciclo';

  switch (chave) {
    case 'bifurcacao':
      // O único destino sem condição: o hub existe mesmo com o banco vazio, e
      // é ele que explica a bifurcação com as próprias palavras.
      return { para: '/provas', rotulo: 'Abrir o hub de Provas' };
    case 'regua':
    case 'campos':
    case 'varredura':
      return cicloId ? { para: `/ciclos/${cicloId}`, rotulo: `Abrir ${ciclo}` } : null;
    case 'mapa':
      return cicloId
        ? { para: `/ciclos/${cicloId}/calibracao`, rotulo: `Abrir a calibração de ${ciclo}` }
        : null;
    case 'lugar':
      return provaId
        ? { para: `/simulados/${provaId}`, rotulo: `Abrir ${nomeDaProva ?? 'a prova'}` }
        : null;
  }
}

export interface PassoMontado extends PassoDoTour {
  destino: DestinoDoPasso | null;
  /** "3 de 6" — o contador da prancheta, com o total vindo da lista. */
  contador: string;
}

/** Os seis passos já com destino e contador. É o que o componente consome. */
export function montarTour(ancora: AncoraDoTour): PassoMontado[] {
  return PASSOS.map((passo, i) => ({
    ...passo,
    destino: destinoDoPasso(passo.chave, ancora),
    contador: `${i + 1} de ${PASSOS.length}`,
  }));
}

/**
 * A versão do CONTEÚDO do tour.
 *
 * Entra na chave do "já vi" de propósito: um tour que passou a ensinar outra
 * coisa não foi visto por ninguém. Subir este número devolve o tour a todo
 * mundo — é a única forma de reabri-lo em massa sem pedir que cada
 * coordenador se lembre de procurar o botão.
 */
export const VERSAO_DO_TOUR = 1;

/**
 * A chave do "já vi", POR PESSOA.
 *
 * Por pessoa e não por aparelho porque a sala da coordenação tem computador
 * compartilhado: com uma chave só, o primeiro coordenador que fecha o tour o
 * silencia para os colegas que ainda não entraram no produto.
 *
 * O identificador é o nome da sessão (`servicos/sessao.ts`), que é o que o
 * front tem — a coordenação não recebe id de usuário. Normalizado para caixa e
 * espaço não criarem duas chaves para a mesma pessoa; sem nome (sessão em
 * montagem) cai em `anonimo`, e aí o tour se comporta como se nunca tivesse
 * sido visto, que é o lado seguro do erro.
 */
export function chaveDoTour(quem: string): string {
  const pessoa = quem.trim().toLowerCase().replace(/\s+/g, '-') || 'anonimo';
  return `sas.tour.provas.v${VERSAO_DO_TOUR}.${pessoa}`;
}

/**
 * Em que ciclo e em que prova o tour ancora os botões.
 *
 * É o MESMO ciclo em que o Painel ancora o card "Como está fechando?" — sai de
 * `cicloPadrao`, e reusá-lo é o ponto: um tour que abrisse a ficha de um ciclo
 * diferente do que a home mostra ensinaria a desconfiar dos dois.
 *
 * ⚠️ O rótulo do ciclo sai de `ciclo.nome` e não das colunas estruturadas,
 * que é como o card do Painel o monta. A diferença é deliberada: lá o
 * subtítulo TEM de nomear o vestibular, porque ITA e IME correm em paralelo e
 * quem lê "128 cortados" precisa saber de quem. Aqui o nome é só a promessa de
 * um botão — se um ciclo antigo veio do Canvas com um nome desleixado, o botão
 * continua abrindo a ficha certa e nenhuma decisão pende da palavra.
 */
export function ancoraDoTour(
  ciclos: readonly Ciclo[],
  simulados: readonly Simulado[],
  hoje: string,
): AncoraDoTour {
  const ordenados = ciclosNoRecorte(ciclos, recorteCompleto(ciclos));
  const ciclo = cicloPadrao(ordenados, simulados, hoje);

  // A última APLICADA, por data de aplicação — a mesma escolha do card de
  // simulado do Painel. A prova que acabou de ser feita é justamente a que se
  // quer abrir; ordenar por nome daria P9 depois de P10.
  const prova = simulados
    .filter((s) => s.dataAplicacao && s.dataAplicacao <= hoje)
    .sort((a, b) => b.dataAplicacao.localeCompare(a.dataAplicacao))[0];

  return {
    cicloId: ciclo?.id ?? null,
    nomeDoCiclo: ciclo?.nome ?? null,
    provaId: prova?.id ?? null,
    nomeDaProva: prova ? nomeDaProva(prova) : null,
  };
}

/** "Física · P8", ou o nome do Canvas quando a prova não tem matéria nem rótulo. */
function nomeDaProva(prova: Simulado): string {
  const partes = [prova.materia?.nome, prova.rotuloCurto].filter(Boolean);
  return partes.length ? partes.join(' · ') : prova.nome;
}
