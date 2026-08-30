// Os glifos da liga — formas geométricas, e a razão é privacidade, não estética.
//
// A liga é ANÔNIMA (docs/26 §5.1): sem nome, sem apelido, sem inicial. Cada
// participante é uma forma estável durante o ciclo.
//
// ⚠️ O glifo NUNCA é derivado do nome. Iniciais, hash do nome, cor por letra —
// tudo isso reabre a dedução que o anonimato existe para fechar, ainda mais numa
// escola onde os colegas se conhecem. A forma vem do servidor como um rótulo
// opaco, e este arquivo só a desenha.
//
// SVG inline, sem caractere Unicode: ◆ e ▲ dependem da fonte do sistema e caem
// para tofu em aparelho velho — e um quadrado vazio ao lado da posição do aluno
// pareceria erro, não anonimato.

const FORMAS: Record<string, string> = {
  losango: 'M12 3l9 9-9 9-9-9z',
  triangulo: 'M12 3.5L21.5 20H2.5z',
  circulo: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18z',
  quadrado: 'M4 4h16v16H4z',
  hexagono: 'M12 2.5l8.2 4.75v9.5L12 21.5 3.8 16.75v-9.5z',
  pentagono: 'M12 2.5l9.5 6.9-3.6 11.2H6.1L2.5 9.4z',
  estrela: 'M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z',
  anel: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm0 4.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 0 0 0-9z',
  cruz: 'M9 3h6v6h6v6h-6v6H9v-6H3V9h6z',
  meiaLua: 'M12 3a9 9 0 0 1 0 18z M12 3a9 9 0 0 0 0 18',
};

interface Props {
  forma: string;
  tamanho?: number;
  /** O glifo do próprio aluno é preenchido; os outros são vazados. */
  destacado?: boolean;
}

export function Glifo({ forma, tamanho = 24, destacado = false }: Props) {
  const d = FORMAS[forma] ?? FORMAS.circulo;
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      style={{ display: 'block', flexShrink: 0 }}
    >
      <path
        d={d}
        fill={destacado ? 'var(--alu-dado)' : 'none'}
        stroke={destacado ? 'none' : 'var(--alu-texto-2)'}
        strokeWidth="1.6"
        strokeLinejoin="round"
        fillRule="evenodd"
      />
    </svg>
  );
}
