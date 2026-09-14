import logoBranca from '../../../assets/ari-logo-branca.png';
import { dataLocal } from '../../dominio/cantina';
import type { BlocoCardapio, Refeicao } from '../../tipos/cantina';

/**
 * O cardápio de UM dia como imagem para compartilhar — 1080×1350 (decisão de
 * 14/09).
 *
 * Retrato 4:5 porque é o formato que o WhatsApp mostra inteiro no chat, sem
 * cortar a miniatura, e é o post do Instagram. É a peça que a coordenação manda
 * no grupo dos pais e a cantina cola no status.
 *
 * ⚠️ **Canvas 2D direto, e não SVG → canvas** como o gráfico da ficha do aluno
 * (`src/exportacao/exportar-aluno.js`). O SVG rasterizado vira uma imagem
 * isolada, que não enxerga as fontes carregadas pela página — o texto sairia na
 * fonte padrão do sistema. O `fillText` do canvas usa as fontes do documento,
 * desde que elas já tenham carregado (`document.fonts.ready`).
 *
 * ⚠️ **Paleta fixa, clara, e não os tokens da tela.** Uma imagem compartilhada
 * não tem tema: gerada por quem trabalha no escuro, ela não pode chegar preta
 * no grupo. Os hexadecimais são os de `--dia-*` em `styles/paleta.css`.
 *
 * ⚠️ Só nome de prato. Nenhum dado de aluno, nenhuma contagem de pedido — é
 * uma peça pública, que vai circular fora do sistema sem controle nenhum.
 */

export interface RefeicaoDaImagem {
  refeicao: Refeicao;
  blocos: BlocoCardapio[];
}

const LARGURA = 1080;
const ALTURA = 1350;
const MARGEM = 84;

const COR = {
  fundo: '#ffffff',
  faixa: '#12275a',
  titulo: '#0f1b33',
  texto: '#16233d',
  texto2: '#5c6883',
  linha: '#dce6f7',
  ouro: '#f2c94c',
  branco: '#ffffff',
};

const ROTULO: Record<Refeicao, string> = { almoco: 'ALMOÇO', janta: 'JANTA' };
const DIAS = ['DOMINGO', 'SEGUNDA', 'TERÇA', 'QUARTA', 'QUINTA', 'SEXTA', 'SÁBADO'];
const MESES = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];

function carregarImagem(src: string): Promise<HTMLImageElement> {
  return new Promise((ok, falha) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = () => falha(new Error('Não deu para carregar a marca do colégio.'));
    img.src = src;
  });
}

/** Quebra um texto em linhas que caibam em `largura`, pela medida real da fonte. */
function quebrar(ctx: CanvasRenderingContext2D, texto: string, largura: number): string[] {
  const palavras = texto.split(/\s+/).filter(Boolean);
  const linhas: string[] = [];
  let atual = '';
  for (const palavra of palavras) {
    const tentativa = atual ? `${atual} ${palavra}` : palavra;
    if (ctx.measureText(tentativa).width <= largura || !atual) {
      atual = tentativa;
    } else {
      linhas.push(atual);
      atual = palavra;
    }
  }
  if (atual) linhas.push(atual);
  return linhas;
}

/**
 * Desenha o miolo com uma escala de fonte e devolve até onde chegou.
 *
 * Roda duas vezes quando precisa: a primeira MEDE (com `desenhar = false`), e
 * se o dia tiver blocos demais para 1350 px, a escala desce até caber. Cortar o
 * último bloco seria mandar para o grupo um cardápio sem a salada.
 */
function miolo(
  ctx: CanvasRenderingContext2D,
  familia: string,
  refeicoes: RefeicaoDaImagem[],
  topo: number,
  escala: number,
  desenhar: boolean,
): number {
  const largura = LARGURA - MARGEM * 2;
  let y = topo;
  for (const [i, r] of refeicoes.entries()) {
    if (i > 0) {
      y += 34 * escala;
      if (desenhar) {
        ctx.fillStyle = COR.linha;
        ctx.fillRect(MARGEM, y, largura, 2);
      }
      y += 40 * escala;
    }

    ctx.font = `800 ${Math.round(40 * escala)}px ${familia}`;
    if (desenhar) {
      ctx.fillStyle = COR.titulo;
      ctx.fillText(ROTULO[r.refeicao], MARGEM, y + 40 * escala);
      // A linha dourada sob o nome da refeição: é a "linha de corte" da porta
      // do produto, e liga a imagem ao resto do SAS sem precisar de legenda.
      ctx.fillStyle = COR.ouro;
      ctx.fillRect(MARGEM, y + 56 * escala, 72 * escala, 6 * escala);
    }
    y += 92 * escala;

    const blocos = [...r.blocos].sort((a, b) => a.ordem - b.ordem);
    for (const bloco of blocos) {
      const opcoes = [...bloco.opcoes]
        .filter((o) => o.disponivel)
        .sort((a, b) => a.ordem - b.ordem)
        .map((o) => o.nome);
      if (!opcoes.length) continue;

      ctx.font = `700 ${Math.round(24 * escala)}px ${familia}`;
      if (desenhar) {
        ctx.fillStyle = COR.texto2;
        ctx.fillText(bloco.nome.toUpperCase(), MARGEM, y + 24 * escala);
      }
      y += 38 * escala;

      ctx.font = `500 ${Math.round(38 * escala)}px ${familia}`;
      for (const linha of quebrar(ctx, opcoes.join(' · '), largura)) {
        if (desenhar) {
          ctx.fillStyle = COR.texto;
          ctx.fillText(linha, MARGEM, y + 38 * escala);
        }
        y += 50 * escala;
      }
      y += 22 * escala;
    }
  }
  return y;
}

export async function exportarImagemDoCardapio({
  data, cantina, refeicoes,
}: {
  data: string;
  cantina: string | null;
  refeicoes: RefeicaoDaImagem[];
}): Promise<void> {
  const comPrato = refeicoes.filter((r) => r.blocos.some((b) => b.opcoes.some((o) => o.disponivel)));
  if (!comPrato.length) throw new Error('Não há cardápio lançado neste dia.');

  await document.fonts.ready;
  const familia = getComputedStyle(document.body).fontFamily || 'sans-serif';
  const marca = await carregarImagem(logoBranca);

  const canvas = document.createElement('canvas');
  canvas.width = LARGURA;
  canvas.height = ALTURA;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Este navegador não gera imagem.');

  // ── Fundo e faixa da marca ──
  ctx.fillStyle = COR.fundo;
  ctx.fillRect(0, 0, LARGURA, ALTURA);
  const ALTURA_DA_FAIXA = 190;
  ctx.fillStyle = COR.faixa;
  ctx.fillRect(0, 0, LARGURA, ALTURA_DA_FAIXA);

  const alturaMarca = 72;
  const larguraMarca = (marca.width / marca.height) * alturaMarca;
  ctx.drawImage(marca, MARGEM, (ALTURA_DA_FAIXA - alturaMarca) / 2, larguraMarca, alturaMarca);
  if (cantina) {
    ctx.font = `600 30px ${familia}`;
    ctx.fillStyle = COR.branco;
    ctx.textAlign = 'right';
    ctx.fillText(cantina, LARGURA - MARGEM, ALTURA_DA_FAIXA / 2 + 11);
    ctx.textAlign = 'left';
  }

  // ── A data, grande ──
  const d = dataLocal(data);
  ctx.font = `800 64px ${familia}`;
  ctx.fillStyle = COR.titulo;
  ctx.fillText(`${DIAS[d.getDay()]} · ${d.getDate()} ${MESES[d.getMonth()]}`, MARGEM, 300);

  // ── O miolo, com a escala que couber ──
  const TOPO = 350;
  const LIMITE = ALTURA - 110;
  let escala = 1;
  while (escala > 0.55 && miolo(ctx, familia, comPrato, TOPO, escala, false) > LIMITE) {
    escala -= 0.05;
  }
  miolo(ctx, familia, comPrato, TOPO, escala, true);

  // ── Rodapé ──
  ctx.font = `500 24px ${familia}`;
  ctx.fillStyle = COR.texto2;
  ctx.fillText('Colégio Ari de Sá · Turma ITA/IME', MARGEM, ALTURA - 56);

  const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, 'image/png'));
  if (!blob) throw new Error('Não deu para gerar a imagem.');
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `cardapio-${data}.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
