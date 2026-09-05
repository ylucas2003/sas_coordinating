// Regras e leituras da cantina, como funções puras (docs/38).
//
// Está aqui, e não dentro das telas, pela regra da casa: regra de negócio vive
// em `src/dominio/` com teste ao lado. Três dessas funções decidem o que o
// aluno consegue enviar, e uma decide o que ele lê sobre o prazo — as duas
// coisas que, erradas, custam o almoço de alguém.
//
// ⚠️ **A validação daqui é CONVENIÊNCIA, não a regra.** Quem decide é o
// servidor (`_validar_escolhas` em `routes/cantina.py`), e ele recusa com 422 e
// 409 mesmo com a tela aberta desde antes do prazo. O que estas funções fazem é
// desabilitar o botão antes do clique — um botão que só falha depois do envio
// ensina a pessoa a desconfiar da tela.

import type { BlocoCardapio, Cardapio, EstadoCardapio, Refeicao } from '../tipos/cantina';

export const ROTULO_DA_REFEICAO: Record<Refeicao, string> = {
  almoco: 'Almoço',
  janta: 'Janta',
};

/**
 * O que cada estado significa para quem lê a tela.
 *
 * `fechado` não diz "encerrado" e sim "contagem final": é o que a cantina
 * precisa saber ao olhar o calendário de manhã — aquele número é o que vai
 * para o fogão, e não muda mais.
 */
export const ROTULO_DO_ESTADO: Record<EstadoCardapio, string> = {
  'sem-cardapio': 'Sem cardápio',
  rascunho: 'Rascunho',
  aberto: 'Aberto para pedidos',
  fechado: 'Contagem final',
  'sem-refeicao': 'Sem refeição',
};

/** Data ISO (`YYYY-MM-DD`) → `Date` no fuso LOCAL.
 *
 * `new Date('2026-09-08')` seria interpretado como UTC e voltaria como dia 7
 * à noite em qualquer fuso negativo — o Brasil inteiro. O bug clássico de
 * calendário, e ele apareceria como "o cardápio de terça aparece na segunda".
 */
export function dataLocal(iso: string): Date {
  const [ano, mes, dia] = iso.split('-').map(Number);
  return new Date(ano, mes - 1, dia);
}

const DIAS_DA_SEMANA = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];

/** "segunda, 8 de set" — o rótulo de um dia na lista do aluno. */
export function rotuloDoDia(iso: string): string {
  const d = dataLocal(iso);
  const mes = d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '');
  return `${DIAS_DA_SEMANA[d.getDay()]}, ${d.getDate()} de ${mes}`;
}

/** ISO local de um `Date`, sem passar por UTC — mesma armadilha de `dataLocal`. */
export function isoDoDia(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, '0');
  const dia = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mes}-${dia}`;
}

/**
 * O prazo, dito de um jeito que dá para agir.
 *
 * A escala muda com a urgência de propósito: faltando menos de uma hora, o
 * número em minutos é o que faz alguém parar e escolher; faltando três dias,
 * minutos seriam ruído. É a única coisa da tela do aluno que expira, então ela
 * é a que tem direito de ser insistente (docs/38 §4).
 */
export function prazoLegivel(pedidosAte: string | null, agora: Date = new Date()): string {
  if (!pedidosAte) return 'sem prazo definido';
  const prazo = new Date(pedidosAte);
  const minutos = Math.floor((prazo.getTime() - agora.getTime()) / 60_000);
  if (minutos <= 0) return 'prazo encerrado';
  if (minutos < 60) return `faltam ${minutos} min`;

  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `faltam ${horas}h`;
  const hora = prazo.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  return `até ${rotuloDoDia(isoDoDia(prazo))}, ${hora}`;
}

export function prazoAberto(pedidosAte: string | null, agora: Date = new Date()): boolean {
  return !!pedidosAte && new Date(pedidosAte).getTime() > agora.getTime();
}

/**
 * ISO com fuso → o valor de um `<input type="datetime-local">`, que é LOCAL e
 * sem fuso ("2026-09-07T20:00").
 *
 * A conversão existe porque o input não aceita offset: passar o ISO cru faz o
 * campo aparecer vazio, sem erro nenhum — e a cantina conclui que o prazo se
 * perdeu.
 */
export function paraInputLocal(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${isoDoDia(d)}T${hh}:${mm}`;
}

/** O caminho de volta. `new Date('2026-09-07T20:00')` — sem sufixo de fuso — é
    interpretado como hora LOCAL pelo JS, que é exatamente o que a cantina
    digitou. */
export function deInputLocal(valor: string): string | null {
  if (!valor) return null;
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/** Quantas opções deste bloco estão marcadas. */
export function marcadasNoBloco(bloco: BlocoCardapio, selecao: ReadonlySet<string>): number {
  return bloco.opcoes.filter((o) => selecao.has(o.id)).length;
}

/**
 * Pode marcar mais uma neste bloco?
 *
 * Teto zero significa bloco só de leitura — a cantina mostra o que tem sem
 * deixar escolher. Não é caso hipotético: é como "Sobremesa do dia" entraria
 * sem virar pedido.
 */
export function podeMarcarMais(bloco: BlocoCardapio, selecao: ReadonlySet<string>): boolean {
  return marcadasNoBloco(bloco, selecao) < bloco.escolhas_maximas;
}

/**
 * O que falta para o pedido poder ser enviado, em uma frase — ou `null` quando
 * está pronto.
 *
 * Devolve a PRIMEIRA pendência, e não a lista: quem está escolhendo almoço
 * resolve uma coisa de cada vez, e quatro avisos ao mesmo tempo não dizem por
 * onde começar.
 */
export function pendenciaDoPedido(cardapio: Cardapio, selecao: ReadonlySet<string>): string | null {
  for (const bloco of cardapio.blocos) {
    const marcadas = marcadasNoBloco(bloco, selecao);
    if (marcadas < bloco.escolhas_minimas) {
      const faltam = bloco.escolhas_minimas - marcadas;
      return `Escolha ${faltam === 1 ? 'uma opção' : `${faltam} opções`} em ${bloco.nome}.`;
    }
    if (marcadas > bloco.escolhas_maximas) {
      return `Em ${bloco.nome} dá para escolher no máximo ${bloco.escolhas_maximas}.`;
    }
  }
  return null;
}

/** "Arroz · Feijão · Frango Grelhado" — o resumo do que já foi pedido. */
export function resumoDoPedido(cardapio: Cardapio, opcaoIds: readonly string[]): string {
  const escolhidas = new Set(opcaoIds);
  const nomes = cardapio.blocos.flatMap((b) =>
    b.opcoes.filter((o) => escolhidas.has(o.id)).map((o) => o.nome),
  );
  return nomes.join(' · ');
}

/**
 * "Escolha 1" / "Escolha até 2" / "Escolha 1 ou 2" — a instrução do bloco.
 *
 * O texto muda com a forma da regra porque "escolha até 2" e "escolha 2" são
 * coisas diferentes para quem está montando o prato, e um rótulo genérico
 * ("máx. 2") obrigaria o aluno a deduzir se é obrigatório.
 */
export function instrucaoDoBloco(bloco: BlocoCardapio): string {
  const { escolhas_minimas: min, escolhas_maximas: max } = bloco;
  if (max === 0) return 'Só para conferir';
  if (min === max) return `Escolha ${min}`;
  if (min === 0) return `Escolha até ${max}`;
  return `Escolha de ${min} a ${max}`;
}

/**
 * A grade de um mês, alinhada na semana — domingo a sábado.
 *
 * Devolve `null` nas casas antes do dia 1 e depois do último, para o calendário
 * não precisar calcular deslocamento no JSX.
 */
export function gradeDoMes(ano: number, mes: number): Array<string | null> {
  const primeiro = new Date(ano, mes, 1);
  const dias = new Date(ano, mes + 1, 0).getDate();
  const casas: Array<string | null> = Array.from({ length: primeiro.getDay() }, () => null);
  for (let dia = 1; dia <= dias; dia += 1) casas.push(isoDoDia(new Date(ano, mes, dia)));
  while (casas.length % 7 !== 0) casas.push(null);
  return casas;
}
