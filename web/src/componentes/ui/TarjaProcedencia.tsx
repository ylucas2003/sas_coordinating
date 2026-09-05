// A TARJA DE PROCEDÊNCIA — "de onde veio este número?", numa peça só.
//
// O produto respondia essa pergunta em QUATRO dialetos: `SeloCanvas` (o estado
// da sincronização), `SeloGravacao` (o estado da gravação de aula), a marca de
// conteúdo gerado do `InsightsPainel` e a `TarjaFonte` da área do aluno.
// Quatro desenhos para a mesma pergunta significavam que o coordenador
// aprendia a marca de novo em cada tela — e que o "isto saiu de um LLM", que é
// a mais importante das quatro, era a mais fácil de confundir com decoração.
// A unificação é a fase 1 do docs/39.
//
// Duas decisões que valem mais que o desenho:
//
//   1 · QUEM DISTINGUE OS ESTADOS É A FORMA, não a cor. O glifo é o que muda
//       de um estado para o outro; a tinta é a mesma em quatro dos seis. Cor
//       aqui seria a sexta escala semântica da tela, e a R7 pede uma só.
//
//   2 · "GERADO" DEIXA DE SER OURO. O ouro tinha dois empregos — acento
//       institucional e marca de LLM — e no sistema novo ele tem um: é a
//       RÉGUA, o corte, o critério em vigor (R2). Uma marca de procedência em
//       ouro faria o olho procurar um corte onde não há nenhum.
//
// A tarja NUNCA preenche superfície, nem em `falhou`: ela fala SOBRE o dado e
// não pode disputar com ele (R4).

/**
 * Os seis estados, na ordem em que a prancheta os lista.
 *
 * `medido` é o número lançado, sem intermediário — e na maior parte das telas
 * ele não ganha tarja nenhuma, porque marcar 100% dos números é o mesmo que
 * não marcar nenhum. Ele existe no conjunto para os lugares onde a ausência de
 * marca seria ambígua: ao lado de um irmão gerado, ou confirmando que os dois
 * lados de uma integração dizem o mesmo ("no Canvas", "no YouTube").
 */
export type Procedencia =
  | 'medido'
  | 'gerado'
  | 'divergente'
  | 'pendente'
  | 'falhou'
  | 'exemplo';

/**
 * O `d` de cada glifo, em viewBox 24×24 e traço 2 — os mesmos da prancheta.
 *
 * Cada um é uma metáfora de UMA palavra, porque é ele que carrega a distinção
 * (decisão 1): o certo do que foi medido, o brilho do que foi gerado, os dois
 * caminhos que se separam, o relógio da espera, o X da falha e o tracejado do
 * exemplo.
 */
const GLIFO: Record<Procedencia, string> = {
  medido: 'M4 12.6l5 5L20 6.4',
  gerado: 'M12 3l2 6.2 6.2 2-6.2 2L12 19.4l-2-6.2-6.2-2 6.2-2z',
  divergente: 'M6 8h12M6 16h12M9 4l-3 4 3 4M15 12l3 4-3 4',
  pendente: 'M12 4.5v7.5l4.5 3M12 3.4a8.6 8.6 0 1 0 0 17.2 8.6 8.6 0 0 0 0-17.2z',
  falhou: 'M7 7l10 10M17 7L7 17',
  exemplo: 'M5 12h4M11 12h2M15 12h4',
};

interface Props {
  estado: Procedencia;
  /**
   * De onde, em 11px cinza: "Canvas", "no YouTube", "gpt-4o-mini", "dado de
   * exemplo". Some quando não há — o olho sozinho já é uma tarja válida.
   *
   * Não escreva aqui o que o olho já diz. A linha existe para nomear a FONTE,
   * que é a metade da resposta que o estado não dá.
   */
  fonte?: string | null;
  /** A frase inteira que o olho abrevia, no `title`. */
  dica?: string | null;
}

export function TarjaProcedencia({ estado, fonte = null, dica = null }: Props) {
  return (
    <span className={`procedencia procedencia--${estado}`} title={dica || undefined}>
      <svg
        className="procedencia__glifo"
        width="13"
        height="13"
        viewBox="0 0 24 24"
        fill="none"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d={GLIFO[estado]} />
      </svg>
      {/* O olho É o estado: não há mapa de rótulo porque não há tradução a
          fazer, e um mapa a mais seria um lugar a mais para divergir. */}
      <span className="procedencia__olho">{estado}</span>
      {fonte && <span className="procedencia__fonte">{fonte}</span>}
    </span>
  );
}
