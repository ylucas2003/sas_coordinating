import type { EstadoCanvas } from '../../tipos/dominio';

/**
 * O estado de um objeto em relação ao Canvas, em uma palavra.
 *
 * `divergente` é o que a coordenação pediu: "se eu disser não, fica diferente
 * mesmo" — um estado legítimo, que precisa ser visível em todo lugar em que
 * o objeto aparece, senão vira diferente E invisível (docs/18 §2.5). Por isso
 * é um componente e não um ternário em cada tela.
 */
const ROTULOS: Record<EstadoCanvas, { texto: string; classe: string; titulo: string }> = {
  sincronizado: { texto: 'no Canvas', classe: 'sim-selo-ok', titulo: 'SAS e Canvas dizem o mesmo.' },
  pendente: { texto: 'enviando…', classe: 'sim-selo-canvas', titulo: 'Criado aqui; o Canvas ainda não confirmou.' },
  falhou: { texto: 'falhou no Canvas', classe: 'sim-selo-canvas', titulo: 'O Canvas recusou. Tenta de novo sozinho a cada 5 min.' },
  divergente: {
    texto: 'só no SAS',
    classe: 'sim-selo-divergente',
    titulo: 'Você escolheu não enviar. O Canvas fica diferente até você mandar.',
  },
};

export function SeloCanvas({ estado, erro }: { estado: EstadoCanvas | null | undefined; erro?: string | null }) {
  if (!estado) return null;
  const r = ROTULOS[estado];
  return (
    <span className={r.classe} title={erro || r.titulo}>
      {r.texto}
    </span>
  );
}
