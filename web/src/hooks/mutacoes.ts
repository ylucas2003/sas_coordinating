// Mutações — escrita na API mais a invalidação do que ficou velho.
//
// Cada mutação invalida as chaves afetadas em vez de recarregar a tela
// inteira, que era o que o código antigo fazia disparando
// `sas:dados-atualizados` + `hashchange`.

import { useMutation, useQueryClient } from '@tanstack/react-query';
import type { QueryClient } from '@tanstack/react-query';
import * as api from '../servicos/api';
import type { CorpoAgendamento } from '../servicos/api';
import type { PapelCoordenacao } from '../tipos/dominio';
import { chaves } from './consultas';

/**
 * Mutações que mexem em nota ou em prova mudam estatística, ranking e KPI de
 * várias telas ao mesmo tempo — invalidar o cache inteiro é mais barato que
 * enumerar tudo que depende do que mudou.
 */
function invalidarTudo(queryClient: QueryClient) {
  queryClient.invalidateQueries();
}

/** Agenda um simulado (P1): nasce no SAS e o backend o cria no Canvas. */
export function useAgendarSimulado() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: CorpoAgendamento) => api.agendarSimulado(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useCancelarSimulado() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, sincronizarCanvas }: { id: string; sincronizarCanvas: boolean }) =>
      api.cancelarSimulado(id, sincronizarCanvas),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useRetrySimuladoCanvas() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.retrySimuladoCanvas(id),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useCriarCiclo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { ordem: number; vestibular: string; sincronizar_canvas: boolean }) =>
      api.criarCiclo(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useEditarSimulado() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: unknown }) => api.editarSimulado(id, corpo),
    onSuccess: (_dados, { id }) => {
      queryClient.invalidateQueries({ queryKey: chaves.simulados });
      queryClient.invalidateQueries({ queryKey: chaves.simulado(id) });
    },
  });
}

export function useEditarNota() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alunoId, simuladoId, corpo }: { alunoId: string; simuladoId: string; corpo: api.CorpoEdicaoNota }) =>
      api.editarNota(alunoId, simuladoId, corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useResolverAlerta() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.resolverAlerta(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chaves.alertas }),
  });
}

/**
 * Reabre o alerta que acabou de ser resolvido — o desfazer do `AlertCard`
 * (docs/39 §3, fase 1).
 *
 * Resolver era a única ação do Painel sem volta, e passava porque havia 900
 * linhas editáveis ao lado; no Painel novo sobram duas ações, e uma delas
 * precisava de arrependimento.
 *
 * Invalida SÓ `chaves.alertas`, e não tudo, pelo mesmo motivo do resolver: o
 * que muda é a faixa de alertas — nenhuma nota, nenhuma estatística, nenhum
 * KPI depende de um alerta estar aberto ou fechado.
 */
export function useReabrirAlerta() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.reabrirAlerta(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: chaves.alertas }),
  });
}

// ─── Administração ───────────────────────────────────────────────────────

function invalidarAdministracao(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: ['administracao'] });
  queryClient.invalidateQueries({ queryKey: ['auditoria'] });
}

export function useCriarCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: {
      email: string; nome: string; canvas_user_id?: string; senha?: string | null;
    }) => api.criarCoordenador(corpo),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useEditarCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, corpo }: { id: string; corpo: { nome?: string; ativo?: boolean; canvas_user_id?: string } }) =>
      api.editarCoordenador(id, corpo),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useLigarCoordenadorAoCanvas() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.ligarCoordenadorAoCanvas(id),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useAlterarPapelCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, papel }: { id: string; papel: PapelCoordenacao }) =>
      api.alterarPapelDoCoordenador(id, papel),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useRedefinirSenhaCoordenador() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, senha }: { id: string; senha: string | null }) =>
      api.redefinirSenhaCoordenador(id, senha),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

// ─── Conexões de IA · o MCP da coordenação (docs/43 §5.3) ────────────────
// `invalidarAdministracao` nas que mudam lista: as conexões e os e-mails da IA
// moram sob `['administracao']`, e a auditoria registra a emissão, a revogação,
// os e-mails e a resposta ao pedido.

/**
 * Emite um token pessoal. A resposta é a ÚNICA que traz o token.
 *
 * ⚠️ `gcTime: 0`, e quem chama faz `reset()` assim que copia o token para o
 * painel. A resposta de uma mutação não vai para o cache de CONSULTAS, mas
 * fica guardada no cache de MUTAÇÕES até ser coletada — cinco minutos, no
 * padrão. Com os dois juntos, o token sai da memória do react-query no tique
 * seguinte ao `reset()`, e mora só no estado da tela enquanto ela o mostra.
 */
export function useCriarConexaoDeIa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { nome: string }) => api.criarConexaoDeIa(corpo),
    gcTime: 0,
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

/** Revoga na hora: a próxima chamada da IA com este token já é recusada. */
export function useRevogarConexaoDeIa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.revogarConexaoDeIa(id),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

/**
 * Cadastra um e-mail da IA na própria conta, AGUARDANDO o código que chegou a
 * ele. 409 se ele já está no SAS.
 *
 * `onSettled`, e não `onSuccess`: o 503 (o código não saiu) é falha com o
 * e-mail JÁ na lista, aguardando — a lista tem de voltar para mostrá-lo com o
 * "enviar outro código".
 */
export function useCadastrarEmailDaIa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { email: string }) => api.cadastrarEmailDaIa(corpo),
    onSettled: () => invalidarAdministracao(queryClient),
  });
}

/**
 * Confirma o e-mail com o código que chegou a ele: daí em diante ele aprova
 * conexões. `gcTime: 0` pelo mesmo motivo de `useAprovarPedidoDeConexao` — o
 * código é segredo de uso único, e a mutação guarda as variáveis enquanto vive
 * no cache. `onSettled`: o 409 (confirmado em outra conta) e o 404 (removido em
 * outra aba) também mudam o que a lista tem de mostrar.
 */
export function useConfirmarEmailDaIa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, codigo }: { id: string; codigo: string }) => api.confirmarEmailDaIa(id, { codigo }),
    gcTime: 0,
    onSettled: () => invalidarAdministracao(queryClient),
  });
}

/** Manda outro código de confirmação; o anterior morre. O 409 (já confirmado) relê a lista. */
export function useReenviarCodigoDoEmailDaIa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.reenviarCodigoDoEmailDaIa(id),
    onError: () => invalidarAdministracao(queryClient),
  });
}

/** Tira o e-mail da lista: daí em diante, nenhum código vai para ele. */
export function useRemoverEmailDaIa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.removerEmailDaIa(id),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

// O CONSENTIMENTO, sem sessão (rota pública desde 26/10). Os três abaixo são
// chamados de uma aba que pode não ter login nenhum.

/**
 * Pede o código de aprovação para o e-mail da IA. Não invalida nada: a
 * resposta é a mesma com e-mail cadastrado ou não, e não muda lista nenhuma.
 */
export function usePedirCodigoDoPedido() {
  return useMutation({
    mutationFn: ({ pedidoId, email }: { pedidoId: string; email: string }) =>
      api.pedirCodigoDoPedido(pedidoId, { email }),
  });
}

/**
 * Aprova o pedido com o e-mail e o código. A tela segue para
 * `redirecionarPara` logo depois; a invalidação existe para quem tem sessão
 * nesta mesma aba e a volta não acontece — a conexão nova tem de aparecer na
 * lista. Sem sessão, não há consulta na memória e ela não faz nada.
 *
 * `gcTime: 0` pelo mesmo motivo do token em `useCriarConexaoDeIa`: o código é
 * segredo de uso único, e a mutação guarda as variáveis enquanto vive no
 * cache.
 */
export function useAprovarPedidoDeConexao() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pedidoId, email, codigo }: { pedidoId: string; email: string; codigo: string }) =>
      api.aprovarPedidoDeConexao(pedidoId, { email, codigo }),
    gcTime: 0,
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

export function useRecusarPedidoDeConexao() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pedidoId: string) => api.recusarPedidoDeConexao(pedidoId),
    onSuccess: () => invalidarAdministracao(queryClient),
  });
}

// ─── Foto de perfil ───────────────────────────────────────────────────────
// `invalidarTudo`, e não só `chaves.fotoPropria`: a mesma foto aparece em
// /alunos, na ficha e na auditoria (via `temFoto`/`ator_tem_foto`), e a
// mutação não sabe de antemão quais telas estão montadas.

export function useSalvarMinhaFoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: { conteudo_base64: string; content_type: string; declaracao_autorizacao: true }) =>
      api.salvarMinhaFoto(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

/**
 * O alvo declarado no onboarding — a escrita que faltava para `/me/zona` ter
 * régua (docs/36 §1.4). `invalidarTudo` porque a zona, os cortes e tudo que
 * depende da régua mudam de resposta no mesmo instante.
 */
export function useDefinirVestibulares() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (vestibulares: string[]) => api.definirVestibularesMe(vestibulares),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useRemoverMinhaFoto() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.removerMinhaFoto(),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

/** Ação da staff: tira do ar a foto de um aluno específico (P5). */
export function useRemoverFotoDeAluno() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (alunoId: string) => api.removerFotoDeAluno(alunoId),
    onSuccess: () => invalidarTudo(queryClient),
  });
}


// ─── Réguas de corte (docs/31 §P4) ───────────────────────────────────────
// Invalidam tudo: a régua muda quem está cortado, a cor de cada célula, o KPI
// e a linha de corte de todo gráfico. Enumerar o que depende dela seria
// enumerar a coordenação inteira.

export function useCriarCriterio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (corpo: api.CorpoCriterio) => api.criarCriterio(corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useEditarCriterio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ slug, corpo }: { slug: string; corpo: Omit<api.CorpoCriterio, 'slug'> }) =>
      api.editarCriterio(slug, corpo),
    onSuccess: () => invalidarTudo(queryClient),
  });
}

export function useDesativarCriterio() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) => api.desativarCriterio(slug),
    onSuccess: () => invalidarTudo(queryClient),
  });
}


/**
 * Envio em lote do ciclo ao Canvas (docs/32 §4).
 *
 * Invalida tudo porque um lote bem-sucedido mexe em estado de ciclo, de
 * simulado e de nota ao mesmo tempo — e o selo "só no SAS" some de várias
 * telas de uma vez.
 */
export function useEnviarCicloAoCanvasEmLote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (cicloId: string) => api.enviarCicloAoCanvasEmLote(cicloId),
    onSuccess: () => invalidarTudo(queryClient),
  });
}
