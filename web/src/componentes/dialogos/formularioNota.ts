// O domínio do formulário de nota — o que se digita, o que aquilo vale, e o
// que muda se for gravado. Compartilhado pelas duas portas do diálogo: a ficha
// aberta na célula da tabela e a edição aberta na ficha do aluno ou da prova.
//
// ⚠️ DUAS UNIDADES CONVIVEM AQUI, e escondê-las era o defeito 4 da prancheta
// "Diálogo de nota" (docs/39 §Fase 3): digita-se PONTUAÇÃO BRUTA — 14, de 20
// questões — e tudo o que está atrás do diálogo mostra NOTA de 0 a 10. A conta
// não aparecia em lugar nenhum: nem ao lado do campo, nem no diff, que também
// mostrava só o bruto. `notaDaPontuacao` é essa conversão, e ela agora aparece
// nos dois lugares.
//
// As funções puras estão fora do hook de propósito — são o que
// `formularioNota.test.ts` cobre, pela regra do projeto de regra de negócio ser
// função pura com teste ao lado.

import { useState } from 'react';
import { fmtNota } from '../../util/formato';
import type { Mudanca } from './DialogoComDiff';

export interface ValoresNota {
  pontuacao: number | null;
  presente: boolean;
  /** A escolha do coordenador na confirmação (docs/18 §2.3). */
  sincronizarCanvas: boolean;
}

export type ResultadoValidacao =
  | { tipo: 'invalido' }
  | { tipo: 'sem-mudancas' }
  | { tipo: 'ok'; valores: ValoresNota; mudancas: Mudanca[] };

/**
 * Pontuação bruta → nota de 0 a 10.
 *
 * `notaMaxima` é o número de questões da prova (o Points Possible do Canvas).
 * Sem ele não há conversão possível, e o honesto é devolver `null` em vez de
 * um número: um "0,0" aqui seria lido como desempenho.
 */
export function notaDaPontuacao(
  pontuacao: number | null | undefined,
  notaMaxima: number | null | undefined,
): number | null {
  if (pontuacao == null || !Number.isFinite(pontuacao)) return null;
  if (notaMaxima == null || !Number.isFinite(notaMaxima) || notaMaxima <= 0) return null;
  return (pontuacao / notaMaxima) * 10;
}

/** "14" · vírgula decimal, como todo numeral do produto. */
function fmtBruto(pontuacao: number | null): string {
  if (pontuacao == null) return '—';
  return String(pontuacao).replace('.', ',');
}

/**
 * "14 · 7,0" — o bruto e o que ele vale, juntos.
 *
 * É a forma que o diff usa. Antes cada diálogo formatava de um jeito: a edição
 * simples passava a pontuação bruta por `fmtNota` e mostrava "14,0", que tem a
 * cara de uma nota de 0 a 10 e não é.
 */
export function rotuloDaPontuacao(
  pontuacao: number | null,
  notaMaxima: number | null | undefined,
): string {
  if (pontuacao == null) return '—';
  const nota = notaDaPontuacao(pontuacao, notaMaxima);
  return nota == null ? fmtBruto(pontuacao) : `${fmtBruto(pontuacao)} · ${fmtNota(nota)}`;
}

/** O número que o campo carrega. `null` quando está vazio, ausente ou ilegível. */
export function pontuacaoDoTexto(texto: string, presente: boolean): number | null {
  if (!presente) return null;
  const cru = texto.trim().replace(',', '.');
  if (cru === '') return null;
  const n = Number(cru);
  return Number.isFinite(n) ? n : null;
}

/**
 * A frase sob o campo. `''` quando não há nada a dizer.
 *
 * O campo vazio ganha uma frase que não é bronca, é caminho: quem não lançou
 * nota ou vai digitar uma, ou vai marcar ausente — e as duas coisas são
 * diferentes no domínio. É por isso que quem consome separa GUIA de FALHA:
 * só a falha ganha o traço de alerta (R4).
 */
export function mensagemDaPontuacao(
  texto: string,
  presente: boolean,
  notaMaxima: number | null | undefined,
): string {
  if (!presente) return '';
  const cru = texto.trim().replace(',', '.');
  if (cru === '') {
    return 'Sem pontuação não há nota. Se o aluno não fez a prova, marque ausente — ausência não é zero.';
  }
  const n = Number(cru);
  if (!Number.isFinite(n)) return 'Isto não é um número de questões.';
  if (n < 0) return 'Pontuação negativa não existe.';
  if (notaMaxima != null && n > notaMaxima) {
    return `A prova tem ${fmtBruto(notaMaxima)} questões: ${fmtBruto(n)} está acima do máximo.`;
  }
  return '';
}

/**
 * O que vai mudar se isto for gravado, nas duas unidades e com o efeito.
 *
 * O efeito é a metade que faltava: "14 → 12" não diz nada a quem não guarda o
 * corte de cabeça. Ele só é afirmado quando o servidor deu a régua — sem corte
 * resolvido, a linha fica sem efeito em vez de ganhar um palpite.
 *
 * A pontuação só entra quando o aluno está presente. Indo para ausente, o que
 * mudou é o ESTADO DO REGISTRO, e é ele que a linha de presença conta — com a
 * perda da pontuação escrita no efeito, para ninguém descobrir depois.
 */
export function mudancasDaNota({
  pontuacaoAtual,
  presenteAtual,
  pontuacao,
  presente,
  notaMaxima,
  corte,
}: {
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  pontuacao: number | null;
  presente: boolean;
  notaMaxima: number | null;
  corte?: number | null;
}): Mudanca[] {
  const mudancas: Mudanca[] = [];

  if (presente !== presenteAtual) {
    const perdePontuacao = !presente && pontuacaoAtual != null;
    mudancas.push({
      campo: 'Presença',
      de: presenteAtual ? 'Presente' : 'Ausente',
      para: presente ? 'Presente' : 'Ausente',
      efeito: presente
        ? 'passa a contar na média'
        : perdePontuacao
          ? 'sai da média, e a pontuação deixa de valer'
          : 'sai da média, e não vira zero',
    });
  }

  if (presente && pontuacao !== pontuacaoAtual) {
    const nota = notaDaPontuacao(pontuacao, notaMaxima);
    mudancas.push({
      campo: 'Pontuação',
      de: rotuloDaPontuacao(pontuacaoAtual, notaMaxima),
      para: rotuloDaPontuacao(pontuacao, notaMaxima),
      efeito:
        corte == null || nota == null ? '' : nota >= corte ? 'passa do corte' : 'fica abaixo do corte',
    });
  }

  return mudancas;
}

/**
 * A régua em palavras — de que lado do corte este número cai, agora.
 *
 * R2 diz que não se lê uma nota sem a régua ao lado, e este é o único lugar do
 * produto onde se ESCREVE uma. O desenho da escala fica `aria-hidden`; quem
 * carrega o mesmo conteúdo para o leitor de tela é esta frase.
 *
 * Nada aqui recalcula critério: `corte` vem resolvido do servidor por
 * `dominio/criterios.ts` (docs/18 §1.2).
 */
export function leituraDaNota({
  presente,
  nota,
  corte,
  elimina = false,
  media,
  posicao,
  totalPresentes,
}: {
  presente: boolean;
  nota: number | null;
  corte?: number | null;
  elimina?: boolean;
  media?: number | null;
  posicao?: number | null;
  totalPresentes?: number;
}): string {
  if (!presente) {
    return 'Ausente: não entra na média da turma e não é zero. A nota fica sem valor, não com valor zero.';
  }
  if (nota == null) return '';

  const partes: string[] = [];

  if (corte != null) {
    const distancia = nota - corte;
    const tamanho = fmtNota(Math.abs(distancia));
    if (distancia > 0) {
      partes.push(`${fmtNota(nota)} passa o corte de ${fmtNota(corte)} por ${tamanho}.`);
    } else if (distancia === 0) {
      partes.push(`${fmtNota(nota)} bate exatamente o corte de ${fmtNota(corte)}, e bater é passar.`);
    } else {
      const fim = elimina ? ' — e nesta matéria o corte elimina sozinho.' : '.';
      partes.push(`${fmtNota(nota)} fica ${tamanho} abaixo do corte de ${fmtNota(corte)}${fim}`);
    }
  }

  if (media != null) {
    const lado = nota > media ? 'Acima' : nota < media ? 'Abaixo' : 'Em cima';
    partes.push(`${lado} da média da turma, que é ${fmtNota(media)}.`);
  }

  if (posicao != null && totalPresentes) {
    partes.push(`Posição ${posicao} de ${totalPresentes} presentes.`);
  }

  return partes.join(' ');
}

interface Args {
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  notaMaxima: number | null;
  /** O corte da régua nesta matéria, já resolvido pelo servidor. */
  corte?: number | null;
}

export function useFormularioNota({ pontuacaoAtual, presenteAtual, notaMaxima, corte }: Args) {
  const [presente, setPresente] = useState(presenteAtual ?? true);
  const [texto, setTexto] = useState(pontuacaoAtual != null ? String(pontuacaoAtual) : '');
  const [tentouSalvar, setTentouSalvar] = useState(false);

  const mensagem = mensagemDaPontuacao(texto, presente, notaMaxima);
  // GUIA × FALHA. A frase é a mesma coisa nos dois casos, o traço não é: o
  // campo só fica em alerta quando o que está escrito nele é impossível, ou
  // quando já se tentou salvar. Sem essa separação, abrir o diálogo de um
  // aluno ainda sem nota acendia um campo vermelho antes de a pessoa digitar
  // qualquer coisa — vermelho é falha operacional, e ali não houve nenhuma.
  const emFalta = mensagem !== '' && (texto.trim() !== '' || tentouSalvar);

  const pontuacao = pontuacaoDoTexto(texto, presente);
  const nota = mensagem === '' ? notaDaPontuacao(pontuacao, notaMaxima) : null;

  const mudancas =
    mensagem === ''
      ? mudancasDaNota({ pontuacaoAtual, presenteAtual, pontuacao, presente, notaMaxima, corte })
      : [];

  function alterarPresenca(novo: boolean) {
    setPresente(novo);
    // ⚠️ NÃO limpa a pontuação. Ela some da gravação — `pontuacaoDoTexto`
    // devolve `null` para quem está ausente —, mas continua VISÍVEL e
    // desabilitada, porque quem trocou por engano precisa ver o que tinha
    // antes de confirmar. Apagar em silêncio era o defeito 5 da prancheta.
  }

  /**
   * Valida e devolve o que muda.
   *
   * Os três resultados existem porque quem chama reage diferente a cada um:
   * inválido fica no formulário com o campo marcado, "sem mudanças" fecha sem
   * chamar a API — gravar igual geraria evento de auditoria falso —, e só o
   * "ok" segue para o diff.
   */
  function validar(): ResultadoValidacao {
    setTentouSalvar(true);
    if (mensagem !== '') return { tipo: 'invalido' };
    if (!mudancas.length) return { tipo: 'sem-mudancas' };
    // `sincronizarCanvas` é decidido no passo de confirmação, não aqui.
    return { tipo: 'ok', valores: { pontuacao, presente, sincronizarCanvas: false }, mudancas };
  }

  return {
    presente,
    alterarPresenca,
    texto,
    setTexto,
    mensagem,
    emFalta,
    nota,
    temMudancas: mudancas.length > 0,
    validar,
  };
}
