/**
 * A MIRA da leitura de QR, traduzida de pixels de tela para pixels do quadro
 * da câmera (docs/40 §7).
 *
 * Por que isto existe: o balcão analisa **um recorte** do quadro, não o quadro
 * inteiro. Analisar o quadro inteiro em 1280×720 custa caro justamente na cena
 * de um balcão — azulejo quadriculado e cardápio impresso são textura repetida,
 * e é procurando padrão de localização nela que o jsQR gasta o tempo dele. O
 * recorte em resolução NATIVA entrega o mesmo pixel por módulo por um terço do
 * custo (as medições estão no comentário de `LADO_MAXIMO_DO_RECORTE`, em
 * `telas/Cantina/AoVivo.tsx`).
 *
 * A mira já está desenhada na tela e o aluno aponta o código para ela: o
 * recorte segue a mira em vez de repetir a fração dela em número mágico. Assim
 * o CSS continua sendo a única fonte de "onde encostar o celular" — mexer em
 * `.cant-aovivo__mira` move os dois juntos.
 */

export interface Retangulo {
  x: number;
  y: number;
  largura: number;
  altura: number;
}

export interface MedidaDaCamera {
  /** O que a câmera entrega, em pixels de imagem (`videoWidth`/`videoHeight`). */
  quadro: { largura: number; altura: number };
  /** O `<video>` na página, em px de CSS. Nulo enquanto não houver layout. */
  video: { largura: number; altura: number } | null;
  /** A mira, em px de CSS, relativa ao canto do `<video>`. Nula = ainda não montada. */
  mira: Retangulo | null;
}

export interface Recorte {
  /** O sub-retângulo do QUADRO a ser lido — os `sx, sy, sw, sh` do `drawImage`. */
  origem: Retangulo;
  /** O tamanho do canvas de destino. Igual à origem, salvo quando o teto obriga a reduzir. */
  destino: { largura: number; altura: number };
  /** Falso quando a mira não pôde ser medida e o recorte é o de segurança. */
  daMira: boolean;
}

/**
 * O binarizador do jsQR trabalha em blocos de 8×8 pixels ancorados na origem da
 * imagem que recebe. Recortar num múltiplo de 8 preserva a FASE que o quadro
 * inteiro teria — e a fase não é detalhe.
 *
 * Medido (jsQR 1.4, cena texturada, QR a 2,75 px/módulo, 40 amostras): quadro
 * inteiro 40/40, recorte alinhado 40/40, e o MESMO recorte deslocado de 1 a 6 px
 * 16 a 18/40. Em +8 volta a 40/40 — o período é exatamente 8. Recortar sem
 * alinhar custaria mais da metade das leituras, sem mudar um pixel do conteúdo.
 */
const BLOCO_DO_BINARIZADOR = 8;

const piso8 = (v: number) => Math.max(0, Math.floor(v / BLOCO_DO_BINARIZADOR) * BLOCO_DO_BINARIZADOR);

/**
 * Onde ler, em pixels do quadro.
 *
 * `folga` é quanto o recorte se estende ALÉM da mira, em fração do lado dela e
 * de cada lado: a mira é um contorno fino, e um código encostado na borda dela
 * ficaria metade de fora. `ladoMaximo` é o teto do que se analisa por quadro —
 * uma câmera que entrega 4K faria a mira sozinha valer 2,8 megapixels.
 *
 * Devolve `null` quando não há quadro nenhum (a câmera ainda não entregou
 * dimensão), que é o mesmo caso em que não há o que ler.
 */
export function recorteDaMira(
  medida: MedidaDaCamera,
  opcoes: { folga: number; ladoMaximo: number },
): Recorte | null {
  const { quadro, video, mira } = medida;
  if (!(quadro.largura > 0) || !(quadro.altura > 0)) return null;

  let bruto: Retangulo;
  let daMira = false;

  if (mira && video && video.largura > 0 && video.altura > 0 && mira.largura > 0 && mira.altura > 0) {
    // `object-fit: cover` (ver `.cant-aovivo__video`): a imagem é ampliada até
    // COBRIR a caixa, e o excesso é cortado no eixo que sobra. O fator é o
    // MAIOR dos dois — usar o menor seria `contain`, e daria uma mira deslocada
    // sempre que a caixa e o quadro tiverem proporções diferentes (a caixa é
    // 4/3 e o quadro da câmera é 16/9: 25% da largura do quadro nem aparece).
    const escala = Math.max(video.largura / quadro.largura, video.altura / quadro.altura);
    const sobraX = (video.largura - quadro.largura * escala) / 2;
    const sobraY = (video.altura - quadro.altura * escala) / 2;
    bruto = {
      x: (mira.x - sobraX) / escala,
      y: (mira.y - sobraY) / escala,
      largura: mira.largura / escala,
      altura: mira.altura / escala,
    };
    daMira = true;
  } else {
    // Sem mira medida — os primeiros quadros, antes de o React ter pintado o
    // contorno. O recorte de segurança é o maior quadrado centrado que cabe:
    // generoso de propósito, porque errar para menos aqui é deixar de ler.
    const lado = Math.min(quadro.largura, quadro.altura);
    bruto = { x: (quadro.largura - lado) / 2, y: (quadro.altura - lado) / 2, largura: lado, altura: lado };
  }

  const folgaX = bruto.largura * opcoes.folga;
  const folgaY = bruto.altura * opcoes.folga;
  const esquerda = Math.max(0, bruto.x - folgaX);
  const topo = Math.max(0, bruto.y - folgaY);
  const direita = Math.min(quadro.largura, bruto.x + bruto.largura + folgaX);
  const baixo = Math.min(quadro.altura, bruto.y + bruto.altura + folgaY);

  // Só a ORIGEM precisa cair no múltiplo de 8: é ela que fixa a fase dos
  // blocos. Ela desce para o múltiplo anterior, o que só faz o recorte crescer.
  // O TAMANHO arredonda para cima e é aparado pelo quadro — jsQR trata o último
  // bloco parcial sem reclamar, e arredondar para baixo aqui comeria até 7 px
  // da beira da mira.
  const x = piso8(esquerda);
  const y = piso8(topo);
  const largura = Math.min(Math.ceil(direita - x), quadro.largura - x);
  const altura = Math.min(Math.ceil(baixo - y), quadro.altura - y);
  if (largura < BLOCO_DO_BINARIZADOR || altura < BLOCO_DO_BINARIZADOR) return null;

  // O teto: reduz proporcionalmente, e só quando o recorte estoura. Reduzir
  // custa pixel por módulo, então é o último recurso — mas um quadro de 4K sem
  // teto custaria mais do que o quadro inteiro custava antes.
  const maior = Math.max(largura, altura);
  const reducao = maior > opcoes.ladoMaximo ? opcoes.ladoMaximo / maior : 1;
  return {
    origem: { x, y, largura, altura },
    destino: {
      largura: Math.max(1, Math.round(largura * reducao)),
      altura: Math.max(1, Math.round(altura * reducao)),
    },
    daMira,
  };
}
