import type { EstadoCanvas } from '../../tipos/dominio';
import { type Procedencia, TarjaProcedencia } from './TarjaProcedencia';

/**
 * O estado de um objeto em relação ao Canvas, em uma palavra.
 *
 * `divergente` é o que a coordenação pediu: "se eu disser não, fica diferente
 * mesmo" — um estado legítimo, que precisa ser visível em todo lugar em que
 * o objeto aparece, senão vira diferente E invisível (docs/18 §2.5). Por isso
 * é um componente e não um ternário em cada tela.
 *
 * Desde a fase 1 do docs/39 ele não desenha mais nada por conta própria: é uma
 * TRADUÇÃO de `EstadoCanvas` para os estados da `TarjaProcedencia`, que é a
 * peça única de "de onde veio este número?". A assinatura ficou igual de
 * propósito — as cinco telas que o chamam não mudam nesta fase.
 *
 * O que mudou no desenho: `sincronizado` era pílula preenchida em DADO e
 * `divergente` em AÇÃO, o que fazia o acordo e a discordância competirem em
 * cor com a nota da tabela ao lado. Agora as quatro são a mesma pílula vazada,
 * e quem as separa é o glifo.
 */
const TARJA: Record<EstadoCanvas, { estado: Procedencia; fonte: string; titulo: string }> = {
  // A redação de cada linha é a que já existia, PARTIDA em dois: o estado sobe
  // para o olho e o resto da frase fica na fonte, que é onde ela sempre esteve
  // dizendo o essencial — de que lado o objeto está. "falhou no Canvas" inteiro
  // na linha de baixo daria "FALHOU falhou no Canvas"; partido, dá "FALHOU no
  // Canvas", que é a mesma frase sem o eco.
  //
  // "no Canvas" continua sendo a confirmação de sucesso da seção Agendados, e
  // por isso `sincronizado` desenha em vez de sumir.
  sincronizado: { estado: 'medido', fonte: 'no Canvas', titulo: 'SAS e Canvas dizem o mesmo.' },
  pendente: {
    estado: 'pendente',
    fonte: 'enviando ao Canvas',
    titulo: 'Criado aqui; o Canvas ainda não confirmou.',
  },
  falhou: {
    estado: 'falhou',
    fonte: 'no Canvas',
    titulo: 'O Canvas recusou. Tenta de novo sozinho a cada 5 min.',
  },
  divergente: {
    estado: 'divergente',
    fonte: 'só no SAS',
    titulo: 'Você escolheu não enviar. O Canvas fica diferente até você mandar.',
  },
};

export function SeloCanvas({ estado, erro }: { estado: EstadoCanvas | null | undefined; erro?: string | null }) {
  if (!estado) return null;
  const t = TARJA[estado];
  return <TarjaProcedencia estado={t.estado} fonte={t.fonte} dica={erro || t.titulo} />;
}
