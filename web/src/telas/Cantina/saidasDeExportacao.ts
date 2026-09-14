import type { SaidaDeExportacao } from './BotaoDeExportar';
import { abrirJanelaDeImpressao, preencherGradePDF, preencherPedidosPDF } from './exportar';
import {
  csvDeAcesso, csvDeDireitos, imagemDoGraficoDeCustos, imprimirCardapioDoDia, imprimirCustos,
  imprimirDireitos,
} from './exportarTelas';
import {
  cardapioDaRefeicao, type FonteDeExportacao, gradeDoPeriodo, refeicoesDoDia,
} from './fontesDeExportacao';
import { exportarImagemDoCardapio } from './imagemDoCardapio';
import { rotuloDoPeriodo } from '../../dominio/periodo';
import * as api from '../../servicos/api';
import { baixarDaApi } from '../../servicos/baixar';
import { qs } from '../../servicos/http';
import type {
  AlunoComDireito, CantinaAdmin, CustosDaCantina, PedidoDeAluno, Refeicao,
} from '../../tipos/cantina';

/**
 * O que cada tela de cantina oferece no "Exportar" — a tabela decidida em
 * 14/09, num lugar só:
 *
 *   Cardápios          dia: imagem (PNG) · PDF      período: grade (PDF) · XLSX
 *   Pedidos            CSV · XLSX (período)         folha do balcão (PDF, um dia)
 *   Alunos c/ direito  CSV · XLSX · PDF             — sem data
 *   Adm. cantinas      CSV · XLSX                   — sem data
 *   Custos             XLSX · PDF · imagem do gráfico (período)
 *
 * As telas chamam uma função daqui e passam o resultado para `<Exportar>`.
 * Mudar um formato de uma área é mudar uma linha aqui, e não caçar botões.
 *
 * ⚠️ Toda saída que gera PDF abre a janela ANTES de buscar dado: o navegador só
 * permite `window.open` dentro do gesto, e o `await` o tiraria de lá.
 */

// ─── Cardápios ─────────────────────────────────────────────────────────

export function saidasDeCardapios(
  fonte: FonteDeExportacao, cantina: string | null,
): SaidaDeExportacao[] {
  return [
    {
      chave: 'imagem-do-dia',
      rotulo: 'Imagem para compartilhar (PNG)',
      descricao: 'O cardápio de um dia, 1080×1350 — lê inteiro no WhatsApp e no Instagram.',
      periodo: 'dia',
      executar: async (p) => {
        const refeicoes = await refeicoesDoDia(fonte, p.de);
        await exportarImagemDoCardapio({ data: p.de, cantina, refeicoes });
      },
    },
    {
      chave: 'pdf-do-dia',
      rotulo: 'PDF do dia',
      descricao: 'Almoço e janta de um dia, com os blocos e as regras de cada um.',
      periodo: 'dia',
      executar: async (p) => {
        const janela = abrirJanelaDeImpressao();
        const refeicoes = await refeicoesDoDia(fonte, p.de);
        if (!refeicoes.length) {
          janela.close();
          throw new Error('Não há cardápio publicado neste dia.');
        }
        imprimirCardapioDoDia(janela, { data: p.de, cantina, refeicoes });
      },
    },
    {
      chave: 'grade',
      rotulo: 'Grade para o mural (PDF)',
      descricao: 'Blocos nas linhas, dias nas colunas, em paisagem — a tabela que a cozinha cola na parede.',
      periodo: 'intervalo',
      executar: async (p) => {
        const janela = abrirJanelaDeImpressao();
        try {
          preencherGradePDF(janela, await gradeDoPeriodo(fonte, p), cantina);
        } catch (e) {
          janela.close();
          throw e;
        }
      },
    },
    {
      chave: 'xlsx',
      rotulo: 'Planilha (XLSX)',
      descricao: 'A mesma grade, para mexer nos números.',
      periodo: 'intervalo',
      executar: (p) => fonte.baixarCardapioXlsx(p),
    },
  ];
}

// ─── Pedidos ───────────────────────────────────────────────────────────

export function saidasDePedidos(
  fonte: FonteDeExportacao,
  { refeicao, cantina, valor, telaNoDia }: {
    refeicao: Refeicao;
    cantina: string | null;
    valor: number | null;
    /**
     * O dia que a TELA está mostrando, com a lista já filtrada. Quando o painel
     * exporta esse mesmo dia, a folha é a que está na tela — "com restrição",
     * se a pessoa filtrou (docs/40 §12.4). Outro dia, a lista inteira.
     */
    telaNoDia?: { data: string; pedidos: PedidoDeAluno[] };
  },
): SaidaDeExportacao[] {
  return [
    {
      chave: 'folha',
      rotulo: 'Folha do balcão (PDF)',
      descricao: 'Um dia: o que cozinhar e quem vai comer, para imprimir.',
      periodo: 'dia',
      executar: async (p) => {
        const janela = abrirJanelaDeImpressao();
        try {
          const dia = await cardapioDaRefeicao(fonte, p.de, refeicao);
          if (!dia) throw new Error('Não há cardápio desta refeição neste dia.');
          const { pedidos, contagem } = await fonte.pedidosDoCardapio(dia.id);
          preencherPedidosPDF(janela, {
            data: p.de,
            refeicao,
            pedidos: telaNoDia && telaNoDia.data === p.de ? telaNoDia.pedidos : pedidos,
            contagem,
            cantina,
            valor,
            incluirRestricao: fonte.comRestricao,
          });
        } catch (e) {
          janela.close();
          throw e;
        }
      },
    },
    {
      chave: 'csv',
      rotulo: 'CSV',
      descricao: 'Uma linha por aluno e dia, uma coluna por bloco — abre no Excel.',
      periodo: 'intervalo',
      executar: (p) => fonte.baixarPedidosCsv(p),
    },
    {
      chave: 'xlsx',
      rotulo: 'Planilha (XLSX)',
      descricao: 'Os mesmos pedidos, já em planilha.',
      periodo: 'intervalo',
      executar: (p) => fonte.baixarPedidosXlsx(p),
    },
  ];
}

// ─── Alunos com direito ────────────────────────────────────────────────

export function saidasDeDireitos(alunos: AlunoComDireito[] | undefined): SaidaDeExportacao[] {
  const esperando = alunos ? undefined : 'Carregando a lista…';
  return [
    {
      chave: 'csv',
      rotulo: 'CSV',
      descricao: 'Nome, matrícula, turma, almoço, janta e se tem restrição — sem o texto dela.',
      periodo: 'nenhum',
      indisponivel: esperando,
      executar: () => csvDeDireitos(alunos ?? []),
    },
    {
      chave: 'xlsx',
      rotulo: 'Planilha (XLSX)',
      descricao: 'A mesma lista, em planilha.',
      periodo: 'nenhum',
      executar: () => baixarDaApi('/administracao/cantina/direitos.xlsx', 'alunos-com-direito.xlsx'),
    },
    {
      chave: 'pdf',
      rotulo: 'PDF',
      descricao: 'A lista para imprimir.',
      periodo: 'nenhum',
      indisponivel: esperando,
      executar: () => imprimirDireitos(abrirJanelaDeImpressao(), alunos ?? []),
    },
  ];
}

// ─── Administrar cantinas ──────────────────────────────────────────────

export function saidasDeAcesso(cantinas: CantinaAdmin[] | undefined): SaidaDeExportacao[] {
  return [
    {
      chave: 'csv',
      rotulo: 'CSV',
      descricao: 'Cada cantina com as contas dela. Sem senha — ela não é guardada.',
      periodo: 'nenhum',
      indisponivel: cantinas ? undefined : 'Carregando as cantinas…',
      executar: () => csvDeAcesso(cantinas ?? []),
    },
    {
      chave: 'xlsx',
      rotulo: 'Planilha (XLSX)',
      descricao: 'O mesmo, em planilha, com prazo padrão e último acesso.',
      periodo: 'nenhum',
      executar: () => baixarDaApi('/administracao/cantina/acesso.xlsx', 'cantinas-e-contas.xlsx'),
    },
  ];
}

// ─── Custos ────────────────────────────────────────────────────────────

export type RecorteDeCusto = 'porDia' | 'porTurma' | 'porAluno' | 'porCantina';

export function saidasDeCustos(
  cantina: string | undefined,
  recorte: { chave: RecorteDeCusto; rotulo: string },
): SaidaDeExportacao[] {
  const recortePorCantina = cantina ? { cantina } : {};
  const buscar = (de: string, ate: string): Promise<CustosDaCantina> =>
    api.custosDaCantina(de, ate, cantina);
  return [
    {
      chave: 'xlsx',
      rotulo: 'Planilha com gráficos (XLSX)',
      descricao: 'Pedidos, custo por dia, turma e aluno, com gráfico em cada aba.',
      periodo: 'intervalo',
      executar: (p) => baixarDaApi(
        `/administracao/cantina/relatorio.xlsx${qs({ ...p, ...recortePorCantina })}`,
        `cantina-${p.de}-a-${p.ate}.xlsx`,
      ),
    },
    {
      chave: 'pdf',
      rotulo: 'Relatório (PDF)',
      descricao: 'Total do período e as quebras por dia, turma e aluno.',
      periodo: 'intervalo',
      executar: async (p) => {
        const janela = abrirJanelaDeImpressao();
        try {
          imprimirCustos(janela, await buscar(p.de, p.ate), rotuloDoPeriodo(p));
        } catch (e) {
          janela.close();
          throw e;
        }
      },
    },
    {
      chave: 'png',
      rotulo: `Imagem do gráfico · ${recorte.rotulo.toLowerCase()} (PNG)`,
      descricao: 'O gráfico de barras do recorte que está na tela.',
      periodo: 'intervalo',
      executar: async (p) => {
        const custos = await buscar(p.de, p.ate);
        await imagemDoGraficoDeCustos(
          custos[recorte.chave],
          `Custo ${recorte.rotulo.toLowerCase()} · ${rotuloDoPeriodo(p)}`,
          `custos-${recorte.chave}-${p.de}-a-${p.ate}.png`,
        );
      },
    },
  ];
}
