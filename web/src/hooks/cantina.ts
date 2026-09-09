// Hooks da cantina — os três públicos (docs/38).
//
// Leitura aqui, escrita aqui: é o único arquivo de hooks do projeto que junta
// os dois, e a razão é que a superfície é pequena e inteiramente de um assunto
// só. Separar em `consultas`/`mutacoes` como o resto faria a invalidação
// atravessar arquivos para nada.

import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';

import { msAteRenovar, PRAZO_DA_RENOVACAO_MS } from '../dominio/cantina';
import {
  codigoDaJanela, janelaAtual, montarQr, msAteAProximaJanela, type SementeDoQr,
} from '../dominio/qrRotativo';
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
  // Chave própria, e não um recorte de `direitos`: são rotas diferentes com
  // custos diferentes de ordens de grandeza (docs/40 §12.1.2). Compartilhar a
  // chave faria o card do hub reaproveitar — ou disparar — a leitura pesada.
  resumo: ['administracao', 'cantina', 'resumo'] as const,
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

/**
 * As três consultas do DIA compartilham o mesmo frescor, e a razão é o stream.
 *
 * Elas eram `staleTime: 0`, escrito antes de o SSE existir: sem aviso de
 * mudança, buscar de novo a cada montagem era a única forma de não mostrar
 * contagem velha. Com o barramento no ar (docs/38 §9.3), quem avisa é o
 * servidor — `hooks/eventosCantina.ts` invalida exatamente estas chaves quando
 * alguém pede, cancela ou retira. `staleTime: 0` virou, então, refetch a cada
 * navegação para confirmar um dado que já estava confirmado.
 *
 * ⚠️ 30 s e não "infinito": o stream cai (túnel, wi-fi trocado, tela
 * bloqueada), e a reconexão tem recuo exponencial de até 30 s. Este número é a
 * rede de segurança de quando o aviso não chega — e é por isso que ele não
 * pode subir sem alguém olhar o recuo do `servicos/eventos.ts` junto.
 */
const FRESCOR_DO_DIA_MS = 30 * 1000;

export function useCardapio(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.cardapio(id ?? ''),
    queryFn: () => api.obterCardapio(id!),
    enabled: !!id,
    staleTime: FRESCOR_DO_DIA_MS,
  });
}

export function useContagem(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.contagem(id ?? ''),
    queryFn: () => api.contagemDoCardapio(id!),
    enabled: !!id,
    staleTime: FRESCOR_DO_DIA_MS,
  });
}

export function usePedidosDoCardapio(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.pedidos(id ?? ''),
    queryFn: () => api.pedidosDoCardapio(id!),
    enabled: !!id,
    staleTime: FRESCOR_DO_DIA_MS,
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
    // ⚠️ **O prazo e o sinal são o que impedem esta tela de morrer em pé.**
    //
    // Sem `tempoLimiteMs`, a renovação herdava os 300 s do gateway
    // (`servicos/http.ts`): com o wi-fi associado e sem rota — o handoff de AP no
    // corredor —, o POST PENDURA em vez de rejeitar, o `fetchStatus` fica em
    // `fetching`, e a tela do aluno passa cinco minutos em "Renovando o código…",
    // sem QR e sem erro, com ele na frente da fila. `PRAZO_DA_RENOVACAO_MS` é
    // curto o bastante para o erro ser conhecido enquanto o código velho ainda
    // vale (docs/40 §4).
    //
    // O `signal` é o que dá corpo ao cancelamento: sem repassá-lo, `query.cancel()`
    // só descarta o RESULTADO — o desmonte da tela e o "Tentar agora" deixariam a
    // tentativa pendurada de pé, disputando com a nova.
    queryFn: ({ signal }) => api.iniciarRetirada(cardapioId!, {
      tempoLimiteMs: PRAZO_DA_RENOVACAO_MS,
      sinal: signal,
    }),
    enabled: !!cardapioId && ligado,
    staleTime: 0,
    // O token não sobrevive à tela: guardá-lo no cache faria a volta a esta
    // rota mostrar um QR vencido por um instante, e um QR vencido no balcão é
    // uma leitura falhada com fila atrás.
    gcTime: 0,
    retry: false,
    refetchOnWindowFocus: true,
    refetchInterval: (consulta) => msAteRenovar(consulta.state.data?.expiraEm),
    // ⚠️ ESTE hook é a exceção do app, e a exceção é o ponto.
    //
    // Sem isto, o `refetchInterval` só dispara com a janela em foco — é o que o
    // `queryObserver` do TanStack faz quando `refetchIntervalInBackground` é
    // `false`, que é o default. A justificativa do app inteiro para não
    // revalidar em segundo plano (`main.tsx`: "os dados do SAS só mudam quando
    // entra planilha nova ou alguém edita algo") não alcança um código que
    // expira em dois minutos na mão de quem está numa fila.
    //
    // O caso é o normalíssimo, e acontece toda fila: o aluno abre o QR, guarda o
    // celular — ou o auto-lock do iOS dispara em 30 s —, e destrava no balcão.
    // Com a renovação parada, o que a cantina lê é um token vencido, e a frase
    // que ela recebe manda "peça para o aluno atualizar a tela", numa tela que
    // de propósito não tem botão de atualizar (docs/40 §4).
    refetchIntervalInBackground: true,
  });
}

/**
 * Mantém a tela do aparelho acesa enquanto o código está sendo mostrado.
 *
 * O auto-lock do iOS cai em 30 segundos e o token dura dois minutos (docs/40
 * §4): sem isto, o percurso normal da fila — abrir o QR, guardar o celular,
 * chegar ao balcão — termina com a tela apagada na frente de quem está lendo.
 *
 * ⚠️ **Pedir uma vez não basta.** O navegador SOLTA a trava sozinho assim que o
 * documento perde visibilidade, e não a devolve na volta — é por isso que existe
 * o `visibilitychange` aqui, e é exatamente a passagem que interessa: bloquear e
 * destravar o celular no caminho até o balcão.
 *
 * Degrada em SILÊNCIO onde a API não existe (Safari anterior ao 16.4, e todo
 * navegador que nunca a teve) e onde o pedido é recusado — bateria fraca é
 * motivo legítimo de recusa. É conveniência, não requisito: uma exceção daqui
 * não pode derrubar a tela do código.
 */
export function useTelaAcesa(ligado: boolean) {
  useEffect(() => {
    if (!ligado || !('wakeLock' in navigator)) return;

    let naTela = true;
    let trava: WakeLockSentinel | null = null;

    const pedir = async () => {
      // O navegador recusa o pedido com o documento escondido, e recusa com
      // exceção: perguntar antes evita erro previsível a cada `visibilitychange`.
      if (!naTela || document.visibilityState !== 'visible') return;
      // Quem solta a trava é o navegador, e nem todo navegador a solta na mesma
      // hora: sem esta conferida, um `visibilitychange` a mais deixaria a trava
      // anterior de pé, sem ninguém com a referência para liberá-la.
      if (trava && !trava.released) return;
      try {
        const nova = await navigator.wakeLock.request('screen');
        // A tela pode ter saído durante a viagem do `await` — sem esta conferida
        // a trava ficaria de pé depois do desmonte, segurando o aparelho aceso
        // por uma tela que já não existe.
        if (naTela) trava = nova;
        else void nova.release().catch(() => {});
      } catch {
        // Recusa do navegador não é falha do produto: a tela do QR continua.
      }
    };

    const aoVoltar = () => void pedir();

    void pedir();
    document.addEventListener('visibilitychange', aoVoltar);

    return () => {
      naTela = false;
      document.removeEventListener('visibilitychange', aoVoltar);
      void trava?.release().catch(() => {});
      trava = null;
    };
  }, [ligado]);
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

export function useCalendarioNaCoordenacao(
  de: string, ate: string, cantina?: string, todas = false,
) {
  return useQuery({
    // A cantina entra na CHAVE: sem isso, trocar de cantina no seletor mostraria
    // o mês da anterior até o `staleTime` vencer.
    queryKey: chavesCantina.calendarioCoord(de, ate, todas ? 'todas' : cantina),
    queryFn: () => api.calendarioNaCoordenacao(de, ate, cantina, todas),
    staleTime: 60 * 1000,
  });
}

/** A ficha de uma refeição para a coordenação — a mesma régua de frescor das
    três consultas do dia da cantina, e pela mesma razão: quem avisa é o stream.
    Esta é a mais cara das quatro (cardápio + blocos + contagem + presencial +
    pedidos + turmas numa requisição só), então o refetch por navegação doía
    mais aqui do que em qualquer outra. */
export function useCardapioNaCoordenacao(id: string | undefined) {
  return useQuery({
    queryKey: chavesCantina.cardapioCoord(id ?? ''),
    queryFn: () => api.cardapioNaCoordenacao(id!),
    enabled: !!id,
    staleTime: FRESCOR_DO_DIA_MS,
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

/**
 * Os três números do card do hub.
 *
 * ⚠️ Não troque por `useDireitos()` nem por `useAlunos()`. O card já foi
 * escrito sobre `useAlunos()`, e aquilo custava 9,31 MB de notas para produzir
 * uma linha de texto — medido, não estimado (docs/40 §12.1.2). `useDireitos()`
 * seria mais barato e ainda assim errado: traz a restrição alimentar de cada
 * aluno, que é dado de saúde de menor e não tem por que passar por um resumo.
 */
/** Os custos de um período. Chave com o recorte inteiro: trocar o mês tem de
    buscar de novo, e não mostrar o anterior até o frescor vencer. */
export function useCustosDaCantina(de: string, ate: string, cantina?: string) {
  return useQuery({
    queryKey: ['administracao', 'cantina', 'custos', de, ate, cantina ?? 'todas'],
    queryFn: () => api.custosDaCantina(de, ate, cantina),
    staleTime: 60 * 1000,
  });
}

export function useResumoDaCantina() {
  return useQuery({
    queryKey: chavesCantina.resumo,
    queryFn: api.resumoDaCantina,
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
    mutationFn: (corpo: { cantina_id: string; email: string; nome: string; senha: string | null }) =>
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
    mutationFn: ({ id, senha }: { id: string; senha: string | null }) =>
      api.redefinirSenhaDeCantina(id, senha),
    onSuccess: () => qc.invalidateQueries({ queryKey: chavesCantina.cantinas }),
  });
}

/**
 * O código que aparece no QR, girando a cada 10 segundos (docs/40 §12.9.2).
 *
 * ⚠️ **Não vai à rede.** A semente vem uma vez, junto do token, e daqui em
 * diante o aparelho deriva sozinho. É o que permite os 10 segundos sem seis
 * requisições por minuto por aluno na fila — e sem o QR sumir quando o wi-fi do
 * corredor troca de ponto de acesso.
 *
 * O relógio usado é `performance.now`, que é MONOTÔNICO: ele não anda para trás
 * quando o sistema acerta a hora, e não depende de o celular estar com a hora
 * certa. A janela inicial é a do servidor.
 */
/**
 * O código que aparece no QR, girando a cada 10 segundos (docs/40 §12.9.2).
 *
 * ⚠️ **Não vai à rede.** A semente vem uma vez, junto do token, e daqui em
 * diante o aparelho deriva sozinho. É o que permite os 10 segundos sem seis
 * requisições por minuto por aluno na fila — e sem o QR sumir quando o wi-fi do
 * corredor troca de ponto de acesso.
 *
 * O relógio é `performance.now`, que é MONOTÔNICO: não anda para trás quando o
 * sistema acerta a hora, e não depende de o celular estar com a hora certa. A
 * janela inicial é a do servidor.
 */
export function useCodigoRotativo(seed: SementeDoQr | undefined): string | null {
  const [codigo, setCodigo] = useState<string | null>(null);
  // O instante em que a semente chegou, no relógio monotônico. `useRef` e não
  // estado: mudá-lo não redesenha nada.
  const chegou = useRef<number>(0);

  // ⚠️ **Os PRIMITIVOS na lista de dependências, e não o objeto.**
  //
  // Quem chama monta `{ pedidoId, semente, … }` inline, então `seed` é um
  // objeto NOVO a cada render. Com ele na lista, o efeito reiniciava a cada
  // render — e `chegou.current` voltava para agora toda vez, de modo que a
  // janela nunca andava: o QR ficaria parado no primeiro código, e a rotação
  // de 10 s existiria só no comentário.
  //
  // Foi o Biome que pegou (`useExhaustiveDependencies`), e não a tela: um QR
  // que não gira é indistinguível de um QR que gira, olhando.
  const { pedidoId, semente, janela, segundosDaJanela } = seed ?? {};

  useEffect(() => {
    if (!pedidoId || !semente || janela == null || !segundosDaJanela) {
      setCodigo(null);
      return;
    }
    const atual: SementeDoQr = { pedidoId, semente, janela, segundosDaJanela };
    chegou.current = performance.now();
    let vivo = true;
    let timer: number | undefined;

    async function desenhar() {
      if (!vivo) return;
      const decorrido = performance.now() - chegou.current;
      const daVez = janelaAtual(atual, decorrido);
      const novo = await codigoDaJanela(atual.semente, daVez);
      if (!vivo) return;
      setCodigo(montarQr(atual.pedidoId, daVez, novo));
      // Reagenda para a VIRADA da janela, e não a cada 10 s cravados: assim o
      // código troca junto com a fronteira que o servidor usa, e não meio
      // segundo depois — o que gastaria metade da tolerância da janela
      // anterior sem necessidade.
      timer = window.setTimeout(
        desenhar,
        msAteAProximaJanela(atual, performance.now() - chegou.current),
      );
    }
    void desenhar();

    return () => { vivo = false; if (timer) window.clearTimeout(timer); };
  }, [pedidoId, semente, janela, segundosDaJanela]);

  return codigo;
}
