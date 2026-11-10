// O dado da proposta de cronograma, importado uma vez e tipado.
//
// É JSON estático (`src/dados/cronograma2027.json`, ~300 KB), gerado fora do produto por
// `conteudo-programatico/scripts/plano_2027.py` — e por isso a rota /cronograma é carregada sob demanda
// (`cascos/AppCoordenacao.tsx`): o JSON vai num pedaço próprio do bundle e não pesa no Painel.

import dados from '../../dados/cronograma2027.json';
import { calendarioDoPlano } from '../../dominio/cronograma';
import type { PlanoDoAno } from '../../tipos/cronograma';

export const PLANO = dados as unknown as PlanoDoAno;
export const CAL = calendarioDoPlano(PLANO);

const inteiro = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const umaCasa = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const fmtInteiro = (n: number) => inteiro.format(n);
export const fmtUmaCasa = (n: number) => umaCasa.format(n);
export const plural = (n: number, um: string, varios: string) => `${inteiro.format(n)} ${Math.round(n) === 1 ? um : varios}`;

/** A intensidade de um valor em DADO, misturada ao fundo — segue o tema, porque os dois são papéis. */
export const tomDeDado = (r: number) =>
  `color-mix(in srgb, var(--sas-dado) ${Math.round(10 + 90 * Math.max(0, Math.min(1, r)))}%, var(--sas-fundo))`;
