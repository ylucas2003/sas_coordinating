// A proposta de cronograma de 2027 do 3º e cursinho — o dado ESTÁTICO que a tela /cronograma lê.
//
// Não vem da API: é gerado fora do produto, por `conteudo-programatico/scripts/plano_2027.py` (Canvas 2024–2026 ×
// apostilas × acervo de provas do SAS), e copiado para `src/dados/cronograma2027.json`. Por isso os campos ficam em
// snake_case, como o script os escreve, e não espelham schema Pydantic nenhum.

/** Uma matéria do plano: aulas de 50 min por ano e a parte média dela no total. */
export interface MateriaDoPlano {
  materia: string;
  aulas_2024: number;
  aulas_2025: number;
  aulas_2026: number;
  parte_media_pct: number;
  aulas_2027: number;
  horas_2027: number;
}

export interface ProfessorDoPlano {
  materia: string;
  professor: string;
  frentes: string;
  aulas_2026: number;
  aulas_2027: number;
  parte_media_pct: number;
  revisao_2027: number;
  /** Sessões de 2026: simples (1 aula), duplas (2) e longas (3 ou mais). */
  formato_2026: [number, number, number];
}

/**
 * O "assunto" que deixa somar o que dois professores dão do mesmo tema: a subárea da taxonomia do SAS, ou um dos
 * códigos que não são conteúdo (REVF revisão de fim de ano, REV, SIM, PLANT, APRES, VEST, FORA, ?).
 */
export interface GrupoDoPlano {
  materia: string;
  codigo: string;
  nome: string;
  conteudo: boolean;
  peso_ita: number | null;
  peso_ime: number | null;
  peso_medio: number | null;
}

/** O que um professor dá, com o NOME QUE ELE USA (título da aula ou capítulo/tópico da apostila). */
export interface ItemDoPlano {
  materia: string;
  professor: string;
  ordem: number;
  nome: string;
  /** "cap. 7 · tópico 2", "Unit 2", ou o que uma lista cobre. Vazio quando não há. */
  ref: string;
  origem: string;
  de: string;
  ate: string;
  aulas_2026: number;
  aulas_2027: number;
  /** Código do grupo → parte do item que cai nele (somam 1). */
  codigos: Record<string, number>;
  meses_2026: number[];
  /** Semana ISO → aulas. 2027 repete a semana ISO de 2026. */
  semanas: Record<string, number>;
}

export type TipoDeMarco = 'colegio' | 'feriado' | 'simulado' | 'recesso' | 'prova';

export interface MarcoDoAno {
  semana: number;
  rotulo: string;
  tipo: TipoDeMarco;
  confirmado: boolean;
}

export interface PlanoDoAno {
  gerado_em: string;
  minutos_por_aula: number;
  total_horas: number;
  total_aulas: number;
  materias: MateriaDoPlano[];
  professores: ProfessorDoPlano[];
  grupos: GrupoDoPlano[];
  itens: ItemDoPlano[];
  calendario_2027: {
    semanas: { semana: number; inicio: string }[];
    marcos: MarcoDoAno[];
  };
}
