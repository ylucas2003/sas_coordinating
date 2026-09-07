// Hooks da cantina — os três públicos (docs/38).
//
// Leitura aqui, escrita aqui: é o único arquivo de hooks do projeto que junta
// os dois, e a razão é que a superfície é pequena e inteiramente de um assunto
// só. Separar em `consultas`/`mutacoes` como o resto faria a invalidação
// atravessar arquivos para nada.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';

import { msAteRenovar } from '../dominio/cantina';
import * as api from '../servicos/api';
import type { CorpoCardapio } from '../servicos/api';
import type { Refeicao } from '../tipos/cantina';

export const chavesCantina = {
  calendario: (de: string, ate: string) => ['cantina', 'calendario', de, ate] as const,
  cardapio: (id: string) => ['cantina', 'cardapio', id] as const,
  contagem: (id: string) => ['cantina', 'contagem', id] as const,
  pedidos: (id: string) => ['cantina', 'pedidos', id] as const,
  doAluno: ['me', 'cantina'] as const,
  /** ⚠️ FORA do galho `['me','cantina']` de propósito: o token é efêmero e a
      tela do QR o renova sozinha. Deixá-lo dentro faria cada evento do stream
      pedir um token novo, e cada pedido de token gravar no banco. */
  tokenDeRetirada: (cardapioId: string) => ['me', 'retirada', cardapioId] as const,
  calendarioCoord: (de: string, ate: string, cantina?: string) =>
    ['coord', 'cantina', de, ate, cantina ?? 'padrao'] as const,
  cardapioCoord: (id: string) => ['coord', 'cantina', 'cardapio', id] as const,
  direitos: ['administracao', 'direito-refeicao'] as const,
  cantinas: ['administracao', 'cantinas'] as const,
};

/** Publicar, salvar e copiar mudam o calendário E o dia. Invalidar o galho
    inteiro é mais barato que enumerar o que depende do quê. */
function invalidarCantina(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ['cantina'] });
  qc.invalidateQueries({ queryKey: ['coord', 'cantina'] });
}

// ─── A cantina ────────────────────────────────────────────────────────────

export function useCalendarioDaCantina(de: string, ate: string) {
  return useQuery({
    queryKey: chavesCantina.calendario(de, ate),
    queryFn: () => api.calendarioDaCantina(de, ate),
    staleTime: 30 * 1000,
  });
}

/** O público de cada refeição. Muda quando a coordenação concede direito —
    raro —, então cinco minutos de frescor bastam. */
export function usePublicoDaCantina() {
  return useQuery({
    queryKey: ['cantina', 'publico'],
    queryFn: api.publicoDaCantina,
    staleTime: 5 * 60 * 1000,
  });
}

/** O estabelecimento da sessão. Muda raramente — o preço, quando a coordenação
    mexe —, e o stream invalida esta chave quando isso acontece. */
export function useMinhaCantina() {
  return useQuery({
    queryKey: ['cantina', 'eu'],
    queryFn: api.minhaCantina,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCardapio(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.cardapio(id ?? ''),
    queryFn: () => api.obterCardapio(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function useContagem(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.contagem(id ?? ''),
    queryFn: () => api.contagemDoCardapio(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function usePedidosDoCardapio(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.pedidos(id ?? ''),
    queryFn: () => api.pedidosDoCardapio(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function useCriarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { data: string; refeicao: Refeicao }) => api.criarCardapio(corpo),
    onSuccess: () => invalidarCantina(qc),
  });
}

export function useSalvarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: CorpoCardapio }) =>
      api.salvarCardapio(id, corpo),
    onSuccess: () => invalidarCantina(qc),
  });
}

export function usePublicarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.publicarCardapio(id),
    onSuccess: () => invalidarCantina(qc),
  });
}

export function useCopiarCardapio() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, origemId }: { id: string; origemId: string }) =>
      api.copiarCardapio(id, origemId),
    onSuccess: () => invalidarCantina(qc),
  });
}

// ─── O aluno ──────────────────────────────────────────────────────────────

/**
 * O cardápio do aluno, e é aqui que mora a resposta de tempo real (docs/38 §9).
 *
 * Duas camadas, e as duas juntas custam pouco mais que uma linha:
 *
 *   0. `refetchOnWindowFocus` LIGADO, contra o default do app. A justificativa
 *      global (`main.tsx`: "os dados do SAS só mudam quando entra planilha nova
 *      ou alguém edita algo") não vale aqui — nesta tela o dado muda porque
 *      OUTRA PESSOA publicou. É o que cobre o caso real: o aluno volta ao app e
 *      o cardápio de hoje já está lá.
 *   1. polling de 60 s que se autodesliga, no padrão de `usePainelGravacoes`.
 *      Só roda para quem tem direito — 800 dos 900 alunos nunca pedem nada.
 *
 * SSE ficou de fora, e a decisão está escrita: o cardápio é publicado horas ou
 * um dia antes do prazo, então a diferença entre 60 s e 1 s é invisível. O que
 * faria valer a pena não é a publicação — é `disponivel = false` às 11h40, com
 * o prazo ainda aberto. Se esse caso aparecer na prática, é o gatilho para
 * subir a camada, e o caminho já está aberto (o chat já fala SSE, o nginx já
 * está configurado e `UVICORN_WORKERS=1` dispensa LISTEN/NOTIFY).
 */
export function useCantinaDoAluno() {
  return useQuery({
    queryKey: chavesCantina.doAluno,
    queryFn: api.cantinaDoAluno,
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchInterval: (consulta) => (consulta.state.data?.direitos.length ? 60_000 : false),
  });
}

export function useSalvarPedido() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ cardapioId, opcaoIds }: { cardapioId: string; opcaoIds: string[] }) =>
      api.salvarPedido(cardapioId, opcaoIds),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.doAluno }),
  });
}

export function useCancelarPedido() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cardapioId: string) => api.cancelarPedido(cardapioId),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.doAluno }),
  });
}

/**
 * O token do QR, com a renovação silenciosa (docs/40 §6).
 *
 * É `useQuery` sobre um `POST`, e a escolha é deliberada: a rota é
 * idempotente (cria OU renova a mesma linha), e o que se quer aqui é
 * exatamente o que uma consulta faz — manter um valor fresco enquanto a tela
 * está aberta, sem ninguém apertar nada. Como mutação, a renovação viraria um
 * `setInterval` à mão dentro do componente, com o cancelamento no desmonte
 * escrito de novo.
 *
 * O intervalo sai de `expiraEm`, e não de um número fixo: quem manda na
 * validade é o servidor, e um valor cravado aqui viraria mentira no dia em que
 * os dois minutos do docs/40 §4 mudarem.
 *
 * `retry: false` porque as recusas desta rota são definitivas para a tela — 409
 * (já pedi), 422 (não aceita presencial, ou não é hoje). Tentar de novo só
 * atrasa a frase que o aluno precisa ler.
 */
export function useTokenDeRetirada(cardapioId: string | undefined, ligado = true) {
  return useQuery({
    queryKey: chavesCantina.tokenDeRetirada(cardapioId ?? ''),
    queryFn: () => api.iniciarRetirada(cardapioId!),
    enabled: !!cardapioId && ligado,
    staleTime: 0,
    // O token não sobrevive à tela: guardá-lo no cache faria a volta a esta
    // rota mostrar um QR vencido por um instante, e um QR vencido no balcão é
    // uma leitura falhada com fila atrás.
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: true,
    refetchInterval: (consulta) => msAteRenovar(consulta.state.data?.expiraEm),
  });
}

/** Desistir da retirada. Some a linha, e o dia volta a estar em aberto. */
export function useDesistirDaRetirada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (cardapioId: string) => api.desistirDaRetirada(cardapioId),
    onSuccess: (_dado, cardapioId) => {
      qc.invalidateQueries({ queryKey: chavesCantina.doAluno });
      qc.removeQueries({ queryKey: chavesCantina.tokenDeRetirada(cardapioId) });
    },
  });
}

/**
 * A leitura do QR no balcão (docs/40 §7).
 *
 * Invalida o galho inteiro da cantina porque a confirmação mexe na contagem, na
 * lista de quem pediu e no calendário — e o servidor publica o evento
 * `retirada`, que derruba as mesmas chaves em toda sessão aberta. Invalidar
 * aqui também é o que faz a PRÓPRIA tela responder sem esperar o stream.
 */
export function useConfirmarRetirada() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => api.confirmarRetirada(token),
    onSuccess: () => invalidarCantina(qc),
  });
}

// ─── A coordenação ────────────────────────────────────────────────────────

export function useCalendarioNaCoordenacao(de: string, ate: string, cantina?: string) {
  return useQuery({
    // A cantina entra na CHAVE: sem isso, trocar de cantina no seletor mostraria
    // o mês da anterior até o `staleTime` vencer.
    queryKey: chavesCantina.calendarioCoord(de, ate, cantina),
    queryFn: () => api.calendarioNaCoordenacao(de, ate, cantina),
    staleTime: 60 * 1000,
  });
}

export function useCardapioNaCoordenacao(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.cardapioCoord(id ?? ''),
    queryFn: () => api.cardapioNaCoordenacao(id!),
    enabled: !!id,
    staleTime: 0,
  });
}

export function useDireitos() {
  return useQuery({
    queryKey: chavesCantina.direitos,
    queryFn: api.listarDireitos,
    staleTime: 60 * 1000,
  });
}

export function useCantinas() {
  return useQuery({
    queryKey: chavesCantina.cantinas,
    queryFn: api.listarCantinas,
    staleTime: 60 * 1000,
  });
}

export function useConcederDireito() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { aluno_ids: string[]; refeicao: Refeicao; conceder: boolean }) =>
      api.conceberDireito(corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.direitos }),
  });
}

export function useSalvarRestricao() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ alunoId, restricao }: { alunoId: string; restricao: string | null }) =>
      api.salvarRestricaoAlimentar(alunoId, restricao),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.direitos }),
  });
}

export function useCriarCantina() {
  const qc = useQueryClient();
  return useMutation({
    // ⚠️ `Parameters<>`, como a irmã abaixo, e não `{ nome: string }`: a
    // assinatura estreita ACEITAVA os campos extras em silêncio — `corpo` é
    // variável, não literal, então não há checagem de propriedade a mais —, e
    // um nome errado (`aceita_presencial_almoço`) passaria no `tsc` e sumiria
    // no JSON.
    mutationFn: (corpo: Parameters<typeof api.criarCantina>[0]) => api.criarCantina(corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useEditarCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: Parameters<typeof api.editarCantina>[1] }) =>
      api.editarCantina(id, corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useCriarContaDeCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { cantina_id: string; email: string; nome: string }) =>
      api.criarContaDeCantina(corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useEditarContaDeCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: { nome?: string; ativo?: boolean } }) =>
      api.editarContaDeCantina(id, corpo),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

export function useRedefinirSenhaDeCantina() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.redefinirSenhaDeCantina(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}
