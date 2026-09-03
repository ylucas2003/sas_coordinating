import type { CSSProperties } from 'react';

// Ícones da área do aluno — SVG inline, sem biblioteca e sem CDN.
//
// Regra 6 do CLAUDE.md: nenhum asset de terceiro no front, porque os dados são
// de menores de idade. Isso exclui qualquer biblioteca de ícone remota, e é a
// mesma regra que tirou a Plus Jakarta Sans do Google.
//
// Dois tipos, e a diferença importa:
//   `Icone`  traço, `currentColor`, herda a cor de quem o contém.
//   `Selo`   preenchido, para a chama e a ficha de XP, que são cor de papel
//            (SEQUENCIA e VALOR) e não podem herdar.

export type NomeIcone = keyof typeof CAMINHOS;

/** Traço único no estilo Feather. Cada entrada é o `d` de um `<path>`. */
const CAMINHOS = {
  casa: 'M3 11.5l9-7.5 9 7.5M5 10v9a1 1 0 0 0 1 1h3v-6h6v6h3a1 1 0 0 0 1-1v-9',
  livro: 'M4 5a2 2 0 0 1 2-2h6v18H6a2 2 0 0 1-2-2z M12 3h6a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6',
  prancheta:
    'M9 4h6v3H9z M8 4H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1h-2 M9 12h6 M9 16h4',
  bandeira: 'M5 21V4 M5 4h11l-2 4 2 4H5',
  busca: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16z M21 21l-4.3-4.3',
  // Lupa com o "+" dentro: é "ver maior", e não "procurar" — o mesmo desenho
  // sem o mais já significa outra coisa dois ícones acima.
  ampliar: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M16.5 16.5L21 21 M11 8v6 M8 11h6',
  filtro: 'M3 5h18 M6 12h12 M10 19h4',
  voltar: 'M19 12H5 M12 19l-7-7 7-7',
  avancar: 'M5 12h14 M12 5l7 7-7 7',
  fechar: 'M6 6l12 12 M18 6L6 18',
  cheque: 'M4 12.5l5.5 5.5L20 7',
  mais: 'M12 5v14 M5 12h14',
  menos: 'M5 12h14',
  seta_cima: 'M12 19V5 M5 12l7-7 7 7',
  seta_baixo: 'M12 5v14 M19 12l-7 7-7-7',
  chevron: 'M9 18l6-6-6-6',
  // O irmão esquerdo do `chevron`. Não é o `voltar`: aquele é uma SETA, que
  // promete "desfazer o passo"; este é o chevron de cabeçalho do desenho, que
  // diz "subir um nível" — e a diferença aparece quando os dois convivem na
  // mesma tela, como na ficha do assunto.
  chevron_esquerda: 'M15 18l-6-6 6-6',
  chevron_baixo: 'M6 9l6 6 6-6',
  relogio: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z M12 7v5l3 2',
  calendario:
    'M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z M4 10h16 M8 3v4 M16 3v4',
  faisca: 'M12 3l1.7 4.6L18 9.3l-4.3 1.7L12 15.6l-1.7-4.6L6 9.3l4.3-1.7z M18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z',
  troféu: 'M6 9a6 6 0 0 0 12 0V3H6z M6 5H3v2a3 3 0 0 0 3 3 M18 5h3v2a3 3 0 0 1-3 3 M9 21h6 M12 15v6',
  cadeado: 'M5 11h14v10H5z M8 11V7a4 4 0 0 1 8 0v4',
  estrela: 'M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z',
  documento:
    'M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z M14 3v5h5 M9 13h6 M9 17h4',
  lista: 'M8 6h13 M8 12h13 M8 18h13 M3.5 6h.01 M3.5 12h.01 M3.5 18h.01',
  // As duas densidades do banco no desktop: uma faixa larga por questão, ou
  // duas colunas para varrer. Desenhados como o que produzem, não como o que
  // significam — o aluno reconhece a forma da lista antes de ler o rótulo.
  faixas: 'M4 5h16v6H4z M4 14h16v6H4z',
  grade: 'M4 5h7v15H4z M13 5h7v15h-7z',
  lixeira:
    'M4 7h16 M10 11v6 M14 11v6 M6 7l1 12.1a1 1 0 0 0 1 .9h8a1 1 0 0 0 1-.9L18 7 M9 7V4.5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1V7',
  anotar: 'M12 20h9 M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z',
  externo: 'M14 4h6v6 M20 4l-9 9 M18 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h6',
  /* Expandir o artefato do Tio Léo para tela cheia — num aparelho de 390px é o
     que torna gráfico e imagem de questão legíveis (docs/27 §8). */
  expandir: 'M9 3H3v6 M3 3l7 7 M15 21h6v-6 M21 21l-7-7',
  engrenagem:
    'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1v.3a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-2.8-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1A1.6 1.6 0 0 0 3.5 15a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.1-2.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1A1.6 1.6 0 0 0 11 4.3V4a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 2.7 1.2l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.2 2.7h.3a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.4 1z',
  sol: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4',
  lua: 'M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z',
  alerta: 'M12 9v4 M12 17h.01 M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  historico: 'M3 12a9 9 0 1 0 3-6.7L3 8 M3 3v5h5 M12 7v5l3.5 2',
  sair: 'M9 21H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h4 M16 17l5-5-5-5 M21 12H9',
  fogo: 'M12 2c1 4 5 5 5 9a5 5 0 0 1-10 0c0-1.5.6-2.6 1.3-3.5C9 9 9.5 8 9 6c2 1 2.5 2.8 3 4 .8-1 1-2.5 0-8z',
  olho: 'M1.5 12S5 5.5 12 5.5 22.5 12 22.5 12 19 18.5 12 18.5 1.5 12 1.5 12z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  olho_fechado:
    'M9.9 5.7A9.9 9.9 0 0 1 12 5.5c7 0 10.5 6.5 10.5 6.5a18 18 0 0 1-2.7 3.7 M6.2 7.3A18 18 0 0 0 1.5 12S5 18.5 12 18.5c1.2 0 2.3-.2 3.3-.5 M3 3l18 18 M10 10a3 3 0 0 0 4 4',
} as const;

interface PropsIcone {
  nome: NomeIcone;
  tamanho?: number;
  /** Padrão `currentColor`: o ícone herda a cor de papel de quem o contém. */
  cor?: string;
  espessura?: number;
  style?: CSSProperties;
  className?: string;
}

export function Icone({
  nome,
  tamanho = 20,
  cor = 'currentColor',
  espessura = 1.9,
  style,
  className,
}: PropsIcone) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 24 24"
      fill="none"
      stroke={cor}
      strokeWidth={espessura}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={{ display: 'block', flexShrink: 0, ...style }}
      aria-hidden="true"
      focusable="false"
    >
      <path d={CAMINHOS[nome]} />
    </svg>
  );
}

/**
 * A chama da sequência. Preenchida na cor SEQUENCIA, sempre — ela não herda
 * cor porque cor aqui é papel, e o papel dela é um só.
 *
 * ⚠️ Não acelera nem gira. A chama nervosa do Duolingo mede risco de perder
 * uma sequência DIÁRIA; aqui a sequência é de simulados a cada três semanas, e
 * não há nada em risco hoje (docs/26 §8). Quem aperta é a contagem regressiva.
 */
export function Chama({ tamanho = 22 }: { tamanho?: number }) {
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
        d="M12 2c1 4 5 5 5 9a5 5 0 0 1-10 0c0-1.5.6-2.6 1.3-3.5C9 9 9.5 8 9 6c2 1 2.5 2.8 3 4 .8-1 1-2.5 0-8z"
        fill="var(--alu-sequencia)"
      />
      <path
        d="M12 19.2a2.6 2.6 0 0 1-2.6-2.6c0-1.6 1.4-2.3 2.6-4.4 1.2 2.1 2.6 2.8 2.6 4.4a2.6 2.6 0 0 1-2.6 2.6z"
        fill="var(--alu-fundo)"
        opacity="0.28"
      />
    </svg>
  );
}

/** A ficha de XP: hexágono vazado com estrela, na cor VALOR. */
export function FichaXp({ tamanho = 26 }: { tamanho?: number }) {
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
        d="M12 1.8l8.4 4.85v9.7L12 21.2 3.6 16.35v-9.7z"
        fill="none"
        stroke="var(--alu-valor)"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
      <path
        d="M12 6.6l1.65 3.35 3.7.54-2.68 2.6.63 3.68L12 15.03 8.7 16.77l.63-3.68-2.68-2.6 3.7-.54z"
        fill="var(--alu-valor)"
      />
    </svg>
  );
}
