import logoBranca from '../../../assets/ari-logo-branca.png';
import { montarFolha, nomeDoArquivoDoHorario } from '../../dominio/horarioEstudosFolha';
import type { Folha, TemaDaFolha } from '../../dominio/horarioEstudosFolha';
import {
  carregarImagem,
  criarMedidor,
  desenharFolha,
  familiaDoSite,
  prepararFontes,
} from '../../exportacao/desenharFolha';
import { escreverPdfDeImagem } from '../../exportacao/pdf';
import { baixarBlob, baixarDaApi } from '../../servicos/baixar';
import { qs } from '../../servicos/http';
import type { BlocoDeEstudo } from '../../tipos/horarioEstudos';

// Exportar o horário de estudos (docs/42): PDF, PNG e Excel, no tema DIA ou NOITE.
//
// Os três saem do MESMO horário e levam a cara do site do aluno, mas não do mesmo
// lugar, e a diferença é deliberada:
//
//   PNG    canvas 2D no navegador, a 2× (1684×1190 px) — para compartilhar.
//   PDF    o MESMO canvas, a 3× (A4 a ~250 dpi), dentro de UMA página — para imprimir.
//          Imagem, e não texto: ver `exportacao/pdf.ts` para o porquê.
//   Excel  vem da API (`GET /me/horario-estudos/planilha`), porque XLSX não se faz no
//          navegador sem uma biblioteca de ~1 MB. É o único que sai do servidor — dado
//          do próprio aluno, pelo token dele, baixado por `baixarDaApi`.
//
// PNG e PDF NÃO saem do aparelho: nenhuma requisição, nenhum serviço de terceiro. É a
// regra 7 do CLAUDE.md (dados de menores) também para o arquivo que o aluno gera.

export type SaidaDoHorario = 'pdf' | 'png' | 'xlsx';

/**
 * Um erro que já vem em português, escrito para o aluno ler.
 *
 * ⚠️ Existe para a tela saber o que PODE mostrar. Uma falha de rede chega do `fetch`
 * como `TypeError: Failed to fetch`, e um canvas que não existe como outra coisa em
 * inglês — e nada disso é para um aluno de 17 anos. A tela mostra a mensagem só dos
 * erros desta classe (e dos de `baixarDaApi`, que já são frases); o resto vira a
 * mensagem genérica de `MENSAGEM_GENERICA`.
 */
export class ErroDeExportacao extends Error {}

export const MENSAGEM_GENERICA = 'Não deu para gerar o arquivo agora. Tente de novo.';

const ESCALA_DO_PNG = 2;
const ESCALA_DO_PDF = 3;
/** JPEG a 92%: nítido o bastante para texto de 5,5pt a 250 dpi, sem o peso do PNG. */
const QUALIDADE_DO_JPEG = 0.92;

/** A folha renderizada num canvas — a base do PNG e do PDF. */
async function renderizar(
  blocos: BlocoDeEstudo[],
  nome: string,
  tema: TemaDaFolha,
  escala: number,
): Promise<{ canvas: HTMLCanvasElement; folha: Folha }> {
  const familia = familiaDoSite();
  await prepararFontes(familia);
  // Sem a logo a folha sai igual, só sem ela: a marca é enfeite, o horário não.
  const logo = await carregarImagem(logoBranca).catch(() => null);

  const folha = montarFolha({
    blocos,
    nome,
    geradoEm: new Date(),
    tema,
    medir: criarMedidor(familia),
    proporcaoDaLogo: logo ? logo.naturalWidth / logo.naturalHeight : null,
  });
  if (!folha) throw new ErroDeExportacao('O horário está vazio: crie ao menos um bloco antes de exportar.');

  const canvas = document.createElement('canvas');
  canvas.width = Math.round(folha.largura * escala);
  canvas.height = Math.round(folha.altura * escala);
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new ErroDeExportacao('Este navegador não gera imagem.');
  desenharFolha(ctx, folha, escala, familia, { logo });
  return { canvas, folha };
}

function paraBlob(canvas: HTMLCanvasElement, tipo: string, qualidade?: number): Promise<Blob> {
  return new Promise((ok, falha) =>
    canvas.toBlob((b) => (b ? ok(b) : falha(new ErroDeExportacao(MENSAGEM_GENERICA))), tipo, qualidade),
  );
}

export async function exportarHorario({
  saida,
  tema,
  blocos,
  nome,
}: {
  saida: SaidaDoHorario;
  tema: TemaDaFolha;
  blocos: BlocoDeEstudo[];
  nome: string;
}): Promise<void> {
  const agora = new Date();

  if (saida === 'xlsx') {
    try {
      // O nome do arquivo vem do servidor (`Content-Disposition`); este é só o reserva.
      await baixarDaApi(`/me/horario-estudos/planilha${qs({ tema })}`, 'horario-de-estudos.xlsx');
    } catch (erro) {
      // Os erros de `baixarDaApi` já são frases ("A sessão expirou…", o `detail` do
      // servidor). Só a falha de rede chega em inglês.
      if (erro instanceof TypeError) {
        throw new ErroDeExportacao('Sem resposta do servidor. Verifique a conexão e tente de novo.');
      }
      throw erro;
    }
    return;
  }

  try {
    if (saida === 'png') {
      const { canvas } = await renderizar(blocos, nome, tema, ESCALA_DO_PNG);
      baixarBlob(await paraBlob(canvas, 'image/png'), nomeDoArquivoDoHorario(nome, tema, agora, 'png'));
      return;
    }

    const { canvas, folha } = await renderizar(blocos, nome, tema, ESCALA_DO_PDF);
    const jpeg = new Uint8Array(await (await paraBlob(canvas, 'image/jpeg', QUALIDADE_DO_JPEG)).arrayBuffer());
    const pdf = escreverPdfDeImagem({
      jpeg,
      larguraPx: canvas.width,
      alturaPx: canvas.height,
      larguraPt: folha.largura,
      alturaPt: folha.altura,
      titulo: 'Horário de estudos',
      criadoEm: agora,
    });
    baixarBlob(new Blob([pdf], { type: 'application/pdf' }), nomeDoArquivoDoHorario(nome, tema, agora, 'pdf'));
  } catch (erro) {
    if (erro instanceof ErroDeExportacao) throw erro;
    throw new ErroDeExportacao(MENSAGEM_GENERICA);
  }
}
