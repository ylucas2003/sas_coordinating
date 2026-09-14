import * as api from '../../servicos/api';
import { baixarDaApi } from '../../servicos/baixar';
import { qs } from '../../servicos/http';
import type { Periodo } from '../../dominio/periodo';
import type {
  BlocoCardapio, Cardapio, ContagemDeOpcao, DiaDoCalendario, PedidoDeAluno, Refeicao,
} from '../../tipos/cantina';

/**
 * De onde cada exportação busca o dado — o MESMO contrato para as duas portas.
 *
 * O painel de exportar deixa escolher um dia ou um período que não é o da tela,
 * então nenhum gerador pode depender do que a tela já tem em cache: ele busca.
 * E a busca é diferente para quem está do outro lado do balcão:
 *
 *   coordenação  rotas `/administracao/cantina/*`, que servem TODAS as
 *                cantinas e nunca trazem o texto da restrição alimentar;
 *   cantina      rotas `/cantina/*`, presas ao `cantina_id` do token e COM o
 *                texto da restrição — é ela que monta o prato (docs/38 §2.6).
 *
 * Uma interface, duas implementações, e as telas não precisam saber qual.
 */

export interface PedidosDoDia {
  pedidos: PedidoDeAluno[];
  contagem: ContagemDeOpcao[];
}

export interface FonteDeExportacao {
  /** Se as exportações desta porta levam o TEXTO da restrição alimentar. */
  comRestricao: boolean;
  calendario(p: Periodo): Promise<DiaDoCalendario[]>;
  cardapio(id: string): Promise<Cardapio>;
  pedidosDoCardapio(id: string): Promise<PedidosDoDia>;
  baixarPedidosXlsx(p: Periodo): Promise<void>;
  baixarPedidosCsv(p: Periodo): Promise<void>;
  baixarCardapioXlsx(p: Periodo): Promise<void>;
}

export function fonteDaCantina(): FonteDeExportacao {
  return {
    comRestricao: true,
    calendario: (p) => api.calendarioDaCantina(p.de, p.ate),
    cardapio: (id) => api.obterCardapio(id),
    pedidosDoCardapio: async (id) => {
      const [pedidos, contagem] = await Promise.all([
        api.pedidosDoCardapio(id), api.contagemDoCardapio(id),
      ]);
      return { pedidos, contagem: contagem.opcoes };
    },
    baixarPedidosXlsx: (p) => baixarDaApi(`/cantina/pedidos.xlsx${qs({ ...p })}`, `pedidos-${p.de}.xlsx`),
    baixarPedidosCsv: (p) => baixarDaApi(`/cantina/pedidos.csv${qs({ ...p })}`, `pedidos-${p.de}.csv`),
    baixarCardapioXlsx: (p) => baixarDaApi(`/cantina/cardapio.xlsx${qs({ ...p })}`, `cardapio-${p.de}.xlsx`),
  };
}

export function fonteDaCoordenacao(cantina?: string): FonteDeExportacao {
  const recorte = cantina ? { cantina } : {};
  return {
    comRestricao: false,
    calendario: (p) => api.calendarioNaCoordenacao(p.de, p.ate, cantina),
    cardapio: (id) => api.cardapioNaCoordenacao(id),
    // A rota da coordenação já devolve pedidos e contagem junto do cardápio.
    pedidosDoCardapio: async (id) => {
      const c = await api.cardapioNaCoordenacao(id);
      return { pedidos: c.pedidos, contagem: c.contagem };
    },
    baixarPedidosXlsx: (p) => baixarDaApi(
      `/administracao/cantina/pedidos.xlsx${qs({ ...p, ...recorte })}`, `pedidos-${p.de}.xlsx`,
    ),
    baixarPedidosCsv: (p) => baixarDaApi(
      `/administracao/cantina/pedidos.csv${qs({ ...p, ...recorte })}`, `pedidos-${p.de}.csv`,
    ),
    baixarCardapioXlsx: (p) => baixarDaApi(
      `/administracao/cantina/cardapio.xlsx${qs({ ...p, ...recorte })}`, `cardapio-${p.de}.xlsx`,
    ),
  };
}

/** Só o que está PUBLICADO sai do sistema: rascunho é promessa que a cozinha
    ainda pode desfazer, e ninguém deve receber no grupo um prato que não vai
    existir. */
function publicados(dias: DiaDoCalendario[]): DiaDoCalendario[] {
  return dias.filter((d) => d.estado === 'aberto' || d.estado === 'fechado');
}

export interface RefeicaoComBlocos {
  refeicao: Refeicao;
  blocos: BlocoCardapio[];
}

/** As refeições publicadas de UM dia, com os blocos — para a imagem e o PDF do dia. */
export async function refeicoesDoDia(fonte: FonteDeExportacao, data: string): Promise<RefeicaoComBlocos[]> {
  const dias = publicados(await fonte.calendario({ de: data, ate: data }));
  const cardapios = await Promise.all(dias.map((d) => fonte.cardapio(d.id)));
  return cardapios
    .map((c) => ({ refeicao: c.refeicao, blocos: c.blocos }))
    .sort((a, b) => (a.refeicao === 'almoco' ? -1 : 1) - (b.refeicao === 'almoco' ? -1 : 1));
}

/** Os cardápios publicados de um período, para a grade do mural. */
export async function gradeDoPeriodo(
  fonte: FonteDeExportacao, p: Periodo,
): Promise<Array<{ data: string; refeicao: Refeicao; blocos: BlocoCardapio[] }>> {
  const dias = publicados(await fonte.calendario(p));
  const cardapios = await Promise.all(dias.map((d) => fonte.cardapio(d.id)));
  return cardapios.map((c) => ({ data: c.data, refeicao: c.refeicao, blocos: c.blocos }));
}

/** O cardápio de uma refeição num dia — para a folha do balcão. `null` se não houver. */
export async function cardapioDaRefeicao(
  fonte: FonteDeExportacao, data: string, refeicao: Refeicao,
): Promise<DiaDoCalendario | null> {
  const dias = await fonte.calendario({ de: data, ate: data });
  return dias.find((d) => d.refeicao === refeicao) ?? null;
}
