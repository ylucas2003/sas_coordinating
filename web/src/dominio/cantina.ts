// Regras e leituras da cantina, como funções puras (docs/38).
//
// Está aqui, e não dentro das telas, pela regra da casa: regra de negócio vive
// em `src/dominio/` com teste ao lado. Três dessas funções decidem o que o
// aluno consegue enviar, e uma decide o que ele lê sobre o prazo — as duas
// coisas que, erradas, custam o almoço de alguém.
//
// ⚠️ **A validação daqui é CONVENIÊNCIA, não a regra.** Quem decide é o
// servidor (`_validar_escolhas` em `routes/cantina.py`), e ele recusa com 422 e
// 409 mesmo com a tela aberta desde antes do prazo. O que estas funções fazem é
// desabilitar o botão antes do clique — um botão que só falha depois do envio
// ensina a pessoa a desconfiar da tela.

import type {
  BlocoCardapio, Cardapio, ContagemDeOpcao, ContagemDoCardapio, ContagemPresencial, DiaDoAluno,
  EstadoCardapio, ModoDeRefeicao, PedidoDeAluno, Refeicao, RetiradaConfirmada,
} from '../tipos/cantina';

export const ROTULO_DA_REFEICAO: Record<Refeicao, string> = {
  almoco: 'Almoço',
  janta: 'Janta',
};

/** O que se diz a quem acabou de retirar. É a tela inteira depois da leitura —
    sem XP e sem cor de alerta, mesma régua do resto da área do aluno
    (docs/40 §6, docs/38 §4). */
export const BOM_PROVEITO: Record<Refeicao, string> = {
  almoco: 'Bom almoço!',
  janta: 'Boa janta!',
};

/**
 * O que cada estado significa para quem lê a tela.
 *
 * `fechado` não diz "encerrado" e sim "contagem final": é o que a cantina
 * precisa saber ao olhar o calendário de manhã — aquele número é o que vai
 * para o fogão, e não muda mais.
 */
export const ROTULO_DO_ESTADO: Record<EstadoCardapio, string> = {
  'sem-cardapio': 'Sem cardápio',
  rascunho: 'Rascunho',
  aberto: 'Aberto para pedidos',
  fechado: 'Contagem final',
  'sem-refeicao': 'Sem refeição',
};

/** Data ISO (`YYYY-MM-DD`) → `Date` no fuso LOCAL.
 *
 * `new Date('2026-09-08')` seria interpretado como UTC e voltaria como dia 7
 * à noite em qualquer fuso negativo — o Brasil inteiro. O bug clássico de
 * calendário, e ele apareceria como "o cardápio de terça aparece na segunda".
 */
export function dataLocal(iso: string): Date {
  const [ano, mes, dia] = iso.split('-').map(Number);
  return new Date(ano, mes - 1, dia);
}

const DIAS_DA_SEMANA = ['domingo', 'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado'];

/** "segunda, 8 de set" — o rótulo de um dia na lista do aluno. */
export function rotuloDoDia(iso: string): string {
  const d = dataLocal(iso);
  const mes = d.toLocaleDateString('pt-BR', { month: 'short' }).replace('.', '');
  return `${DIAS_DA_SEMANA[d.getDay()]}, ${d.getDate()} de ${mes}`;
}

/** ISO local de um `Date`, sem passar por UTC — mesma armadilha de `dataLocal`. */
export function isoDoDia(d: Date): string {
  const mes = String(d.getMonth() + 1).padStart(2, '0');
  const dia = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mes}-${dia}`;
}

/**
 * O prazo, dito de um jeito que dá para agir.
 *
 * A escala muda com a urgência de propósito: faltando menos de uma hora, o
 * número em minutos é o que faz alguém parar e escolher; faltando três dias,
 * minutos seriam ruído. É a única coisa da tela do aluno que expira, então ela
 * é a que tem direito de ser insistente (docs/38 §4).
 */
export function prazoLegivel(pedidosAte: string | null, agora: Date = new Date()): string {
  if (!pedidosAte) return 'sem prazo definido';
  const prazo = new Date(pedidosAte);
  const minutos = Math.floor((prazo.getTime() - agora.getTime()) / 60_000);
  if (minutos <= 0) return 'prazo encerrado';
  if (minutos < 60) return `faltam ${minutos} min`;

  const horas = Math.floor(minutos / 60);
  if (horas < 24) return `faltam ${horas}h`;
  const hora = prazo.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  return `até ${rotuloDoDia(isoDoDia(prazo))}, ${hora}`;
}

export function prazoAberto(pedidosAte: string | null, agora: Date = new Date()): boolean {
  return !!pedidosAte && new Date(pedidosAte).getTime() > agora.getTime();
}

/**
 * ISO com fuso → o valor de um `<input type="datetime-local">`, que é LOCAL e
 * sem fuso ("2026-09-07T20:00").
 *
 * A conversão existe porque o input não aceita offset: passar o ISO cru faz o
 * campo aparecer vazio, sem erro nenhum — e a cantina conclui que o prazo se
 * perdeu.
 */
export function paraInputLocal(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return `${isoDoDia(d)}T${hh}:${mm}`;
}

/** O caminho de volta. `new Date('2026-09-07T20:00')` — sem sufixo de fuso — é
    interpretado como hora LOCAL pelo JS, que é exatamente o que a cantina
    digitou. */
export function deInputLocal(valor: string): string | null {
  if (!valor) return null;
  const d = new Date(valor);
  return Number.isNaN(d.getTime()) ? null : d.toISOString();
}

/** Quantas opções deste bloco estão marcadas. */
export function marcadasNoBloco(bloco: BlocoCardapio, selecao: ReadonlySet<string>): number {
  return bloco.opcoes.filter((o) => selecao.has(o.id)).length;
}

/**
 * Pode marcar mais uma neste bloco?
 *
 * Teto zero significa bloco só de leitura — a cantina mostra o que tem sem
 * deixar escolher. Não é caso hipotético: é como "Sobremesa do dia" entraria
 * sem virar pedido.
 */
export function podeMarcarMais(bloco: BlocoCardapio, selecao: ReadonlySet<string>): boolean {
  return marcadasNoBloco(bloco, selecao) < bloco.escolhas_maximas;
}

/**
 * O que falta para o pedido poder ser enviado, em uma frase — ou `null` quando
 * está pronto.
 *
 * Devolve a PRIMEIRA pendência, e não a lista: quem está escolhendo almoço
 * resolve uma coisa de cada vez, e quatro avisos ao mesmo tempo não dizem por
 * onde começar.
 */
export function pendenciaDoPedido(cardapio: Cardapio, selecao: ReadonlySet<string>): string | null {
  for (const bloco of cardapio.blocos) {
    const marcadas = marcadasNoBloco(bloco, selecao);
    if (marcadas < bloco.escolhas_minimas) {
      const faltam = bloco.escolhas_minimas - marcadas;
      return `Escolha ${faltam === 1 ? 'uma opção' : `${faltam} opções`} em ${bloco.nome}.`;
    }
    if (marcadas > bloco.escolhas_maximas) {
      return `Em ${bloco.nome} dá para escolher no máximo ${bloco.escolhas_maximas}.`;
    }
  }
  return null;
}

/** "Arroz · Feijão · Frango Grelhado" — o resumo do que já foi pedido. */
export function resumoDoPedido(cardapio: Cardapio, opcaoIds: readonly string[]): string {
  const escolhidas = new Set(opcaoIds);
  const nomes = cardapio.blocos.flatMap((b) =>
    b.opcoes.filter((o) => escolhidas.has(o.id)).map((o) => o.nome),
  );
  return nomes.join(' · ');
}

/**
 * "Escolha 1" / "Escolha até 2" / "Escolha 1 ou 2" — a instrução do bloco.
 *
 * O texto muda com a forma da regra porque "escolha até 2" e "escolha 2" são
 * coisas diferentes para quem está montando o prato, e um rótulo genérico
 * ("máx. 2") obrigaria o aluno a deduzir se é obrigatório.
 */
export function instrucaoDoBloco(bloco: BlocoCardapio): string {
  const { escolhas_minimas: min, escolhas_maximas: max } = bloco;
  const contagem = (() => {
    if (max === 0) return 'Só para conferir';
    if (min === max) return `Escolha ${min}`;
    if (min === 0) return `Escolha até ${max}`;
    return `Escolha de ${min} a ${max}`;
  })();
  // A observação entra DEPOIS do número e no mesmo texto, e não numa segunda
  // linha: as duas dizem a regra do mesmo bloco, e separá-las faria o aluno ler
  // "escolha até 2" e agir antes de chegar na parte que diz que a opção 4 anula
  // as outras (docs/40 §12.5.4).
  const obs = (bloco.observacao ?? '').trim();
  return obs ? `${contagem} · ${obs}` : contagem;
}

/**
 * A grade de um mês, alinhada na semana — domingo a sábado.
 *
 * Devolve `null` nas casas antes do dia 1 e depois do último, para o calendário
 * não precisar calcular deslocamento no JSX.
 */
export function gradeDoMes(ano: number, mes: number): Array<string | null> {
  const primeiro = new Date(ano, mes, 1);
  const dias = new Date(ano, mes + 1, 0).getDate();
  const casas: Array<string | null> = Array.from({ length: primeiro.getDay() }, () => null);
  for (let dia = 1; dia <= dias; dia += 1) casas.push(isoDoDia(new Date(ano, mes, dia)));
  while (casas.length % 7 !== 0) casas.push(null);
  return casas;
}

// ─── A retirada presencial (docs/40) ──────────────────────────────────────

/**
 * Onde este (cardápio, aluno) está na máquina de estados do docs/40 §2, e o
 * que ainda dá para fazer daqui.
 *
 * A máquina é **assimétrica**, e é a regra mais importante do desenho:
 *
 *   · `pedido` é porta sem volta — compromete a cozinha com um prato
 *     específico. O aluno continua trocando os itens até o prazo, mas não vira
 *     mais presencial naquele cardápio;
 *   · `presencial` sem leitura não compromete nada, então é reversível: dá
 *     para virar pedido, ou desistir;
 *   · `retiradoEm` preenchido é final dos dois lados. O aluno já comeu.
 *
 * Está aqui, e não dentro do componente, pelo mesmo motivo de `cardDaCantina`:
 * o que decide é a ORDEM das perguntas, e ordem que mora em JSX não tem teste.
 *
 * ⚠️ `podeRetirar` só vale para HOJE, e isso é CONVENIÊNCIA espelhando a
 * recusa proposta em docs/40 §11.1 (422 se `data != hoje`). Se o servidor
 * aceitar qualquer dia publicado, o custo é o aluno gerar o QR na hora em vez
 * de na véspera — que é quando ele serve para alguma coisa. O contrário
 * (oferecer o botão e levar 422 depois do clique) ensina a desconfiar da tela.
 */
export interface SituacaoDoDia {
  estado: 'retirado' | 'presencial' | 'pedido' | 'aberto';
  /** Dá para enviar ou trocar o pedido agora? */
  podePedir: boolean;
  /** Dá para gerar (ou mostrar) o QR agora? */
  podeRetirar: boolean;
}

export function situacaoDoDia(dia: DiaDoAluno, agora: Date = new Date()): SituacaoDoDia {
  // `!== false` e `=== true` em vez de `??`: os dois campos são novos, e um
  // servidor anterior à 0051 simplesmente não os manda. A leitura tolerante
  // recai no comportamento de hoje — só pedido —, que é o default do banco.
  const aceitaPedido = dia.aceitaPedido !== false;
  const aceitaPresencial = dia.aceitaPresencial === true;
  const noPrazo = prazoAberto(dia.pedidos_ate, agora);
  const ehHoje = dia.data === isoDoDia(agora);

  if (dia.retiradoEm) return { estado: 'retirado', podePedir: false, podeRetirar: false };

  if (dia.modo === 'presencial') {
    // O QR continua acessível mesmo que a cantina tenha desligado o presencial
    // depois: quem já tem linha precisa de um caminho para a tela, e a recusa,
    // se vier, vem do servidor com a frase dele.
    return { estado: 'presencial', podePedir: aceitaPedido && noPrazo, podeRetirar: true };
  }

  // `modo === 'pedido'` é o caso normal; `meuPedido != null` cobre o servidor
  // que ainda não manda `modo` — sem isso, um pedido feito ontem apareceria
  // como dia em aberto e a tela ofereceria "Pegar pessoalmente" sobre ele.
  if (dia.modo === 'pedido' || dia.meuPedido != null) {
    return { estado: 'pedido', podePedir: noPrazo, podeRetirar: false };
  }

  return {
    estado: 'aberto',
    podePedir: aceitaPedido && noPrazo,
    podeRetirar: aceitaPresencial && ehHoje,
  };
}

/**
 * Quando renovar o token do QR, em milissegundos a partir de agora.
 *
 * O token dura dois minutos (docs/40 §4) e a tela renova sozinha ANTES de
 * vencer: um QR vencido na tela do aluno vira uma leitura falhada no balcão,
 * com a fila parada, e o aluno não tem como saber que precisa atualizar.
 *
 * A folga é o que compra a viagem de rede da renovação. O piso existe porque
 * um `expiraEm` já vencido (relógio do celular atrasado, aba dormindo) tem de
 * pedir token novo logo, e não entrar em laço de requisição.
 */
export const FOLGA_DE_RENOVACAO_MS = 25_000;
const PISO_DE_RENOVACAO_MS = 5_000;

export function msAteRenovar(
  expiraEm: string | null | undefined,
  agora: Date = new Date(),
): number {
  if (!expiraEm) return PISO_DE_RENOVACAO_MS;
  const fim = new Date(expiraEm).getTime();
  if (Number.isNaN(fim)) return PISO_DE_RENOVACAO_MS;
  return Math.max(PISO_DE_RENOVACAO_MS, fim - agora.getTime() - FOLGA_DE_RENOVACAO_MS);
}

/**
 * A margem entre o código sumir da tela e o token realmente vencer.
 *
 * É o intervalo entre o aluno virar a tela para a câmera e o servidor conferir:
 * um código que vence dentro dela chega ao balcão para ser recusado.
 */
export const MARGEM_DE_EXIBICAO_MS = 2_000;

/**
 * Quanto o celular do aluno espera pela renovação antes de desistir daquela
 * tentativa — o `tempoLimiteMs` que `hooks/cantina.ts` põe na chamada.
 *
 * ⚠️ Ele existe pelo mesmo motivo que o `RESPOSTA_NO_BALCAO_MS` do balcão: o teto
 * de `servicos/http.ts` é o do GATEWAY (5 min), calibrado para não cortar rota
 * lenta nenhuma, e cinco minutos de tela sem QR com o aluno na frente da fila é
 * o mesmo defeito que a leva anterior consertou do outro lado do balcão. A
 * diferença é que aqui não dá para pôr um `setTimeout` ao lado e seguir a vida:
 * o estado desta tela É a promessa (React Query), então o prazo tem de viajar
 * com a requisição e cancelá-la.
 *
 * O NÚMERO sai da geometria da renovação, não de gosto: ela dispara
 * `FOLGA_DE_RENOVACAO_MS` antes de vencer e o QR sai da placa
 * `MARGEM_DE_EXIBICAO_MS` antes disso, então qualquer prazo abaixo de 23 s faz o
 * erro ser conhecido ENQUANTO o código velho ainda está valendo — a tela nunca
 * chega ao vencimento sem saber o que dizer. `dominio/cantina.test.ts` tranca
 * essa desigualdade. 15 s é ~150× o que a rota leva de verdade (um INSERT
 * condicional e um JWT assinado, docs/40 §4).
 */
export const PRAZO_DA_RENOVACAO_MS = 15_000;

export interface CodigoNaTela {
  /** Mostrar o QR agora — ou, no lugar dele, o aviso de que está renovando. */
  vale: boolean;
  /** Em quantos ms ele deixa de valer, para a tela se reavaliar sozinha.
      `null` quando não há prazo que sirva de despertador. */
  msAteVencer: number | null;
}

/**
 * O código que está na mão ainda pode ir para a tela?
 *
 * Enquanto a renovação não chega, a tela não pode exibir um QR morto: o aluno
 * o apresenta, a cantina recusa, e a frase que ela lê manda "peça para o aluno
 * atualizar a tela" — numa tela que de propósito não tem botão de atualizar
 * (docs/40 §4, §6).
 *
 * A conta parte da vida APARENTE do token — `expiraEm` menos o instante em que
 * ele chegou —, e não de uma comparação nua do relógio do aparelho com
 * `expiraEm`. A diferença aparece no celular com a hora errada: se essa vida
 * sair absurda (zero ou negativa, que é o sintoma do relógio torto), a resposta
 * é MOSTRAR. Recusar aqui não salvaria ninguém — quem julga é o servidor, e
 * para ele aquele token está valendo; sem a saída, um aparelho adiantado ficaria
 * sem QR nenhum, para sempre, sem dizer por quê.
 *
 * A validade também não é cravada: sai do que o servidor mandou, porque dois
 * minutos escritos aqui viram mentira no dia em que o docs/40 §4 mudar.
 */
export function codigoNaTela(
  expiraEm: string | null | undefined,
  recebidoEm: number,
  agora: number = Date.now(),
): CodigoNaTela {
  if (!expiraEm) return { vale: false, msAteVencer: null };

  const fim = new Date(expiraEm).getTime();
  if (Number.isNaN(fim)) return { vale: true, msAteVencer: null };

  const vence = fim - MARGEM_DE_EXIBICAO_MS;
  if (vence <= recebidoEm) return { vale: true, msAteVencer: null };

  const restante = vence - agora;
  return { vale: restante > 0, msAteVencer: restante > 0 ? restante : null };
}

/**
 * O que a placa do QR mostra agora — e se sobra alguma coisa para o aluno fazer.
 *
 * Está aqui, e não no JSX, porque o que decide é a ORDEM das perguntas, e ordem
 * que mora em componente não tem teste. A ordem, e o porquê de cada degrau:
 *
 *   1. **Código válido na mão VENCE qualquer falha.** É o defeito que custou
 *      caro: `token.isError` escondia a placa inteira, e o reducer do
 *      `query-core` PRESERVA `data` no caso `"error"` — ou seja, a tela jogava
 *      fora um QR que ainda valia 23 segundos porque a renovação SEGUINTE
 *      falhou. Quem julga o código é o servidor, no balcão; enquanto ele vale,
 *      ele vale.
 *   2. **Falha sem veredito** (`status: 0` do `servicos/http.ts`, ou 5xx) é
 *      ausência de resposta, não regra de produto: a renovação volta sozinha, e
 *      a tela oferece tentar agora. É o mesmo corte que `lerRespostaDoQr` faz do
 *      outro lado do balcão.
 *   3. **Recusa do servidor** (409, 422) é definitiva e EXPLICA uma regra —
 *      "você já fez o pedido", "esta refeição já foi retirada". A frase passa
 *      inteira; trocá-la por "não foi possível" apagaria a única informação
 *      útil, e oferecer "tentar de novo" só repetiria a mesma recusa.
 *   4. Sem falha: `renovando` se há um código velho na mão, `gerando` se a
 *      primeira resposta ainda não chegou.
 */
export type PlacaDaRetirada =
  | { tipo: 'codigo' }
  | { tipo: 'gerando' }
  | { tipo: 'renovando' }
  | { tipo: 'sem-resposta'; mensagem: string }
  | { tipo: 'recusado'; mensagem: string };

/**
 * ⚠️ A frase do `sem-resposta` é PRÓPRIA do aluno, e é de propósito.
 *
 * A do transporte ("O servidor não respondeu a tempo. **Tente de novo.**") foi
 * escrita para a coordenação, que tem botão. Chegando inteira aqui, ela mandava
 * apertar o que a linha de baixo diz não existir — "Ele se renova sozinho, não
 * há nada para atualizar" (docs/40 §6). Esta diz o que é verdade nesta tela: a
 * renovação continua sozinha, e o código volta com a conexão.
 */
const SEM_RESPOSTA_NO_CELULAR =
  'Sem resposta do servidor. O código volta sozinho quando a conexão voltar.';

/** Sem "tente de novo": a recusa é definitiva, e não há segunda tentativa que
    mude a resposta. */
const RECUSA_SEM_FRASE = 'Não consegui gerar o código agora.';

export function placaDaRetirada(entrada: {
  /** Já veio algum token do servidor — inclusive um que a última renovação não
      conseguiu substituir. */
  temCodigo: boolean;
  /** `codigoNaTela(...).vale` — o código na mão ainda pode ir para a câmera. */
  codigoVale: boolean;
  /** A última renovação, quando ela falhou. */
  falha: RecusaDaLeitura | null;
}): PlacaDaRetirada {
  if (entrada.temCodigo && entrada.codigoVale) return { tipo: 'codigo' };

  if (entrada.falha) {
    // 5xx entra junto com o `status: 0`: um servidor que caiu não é veredito
    // sobre ESTE aluno, e a ação certa continua sendo tentar de novo.
    if (!entrada.falha.status || entrada.falha.status >= 500) {
      return { tipo: 'sem-resposta', mensagem: SEM_RESPOSTA_NO_CELULAR };
    }
    return {
      tipo: 'recusado',
      mensagem: fraseParaOAluno(entrada.falha.mensagem) || RECUSA_SEM_FRASE,
    };
  }

  return entrada.temCodigo ? { tipo: 'renovando' } : { tipo: 'gerando' };
}

/** A frase do servidor passa inteira; só o `POST /x → 422` cru é descartado,
    porque esse não foi escrito para ninguém ler. */
function fraseParaOAluno(mensagem: string): string {
  const limpa = mensagem.trim();
  return /→ \d{3}$/.test(limpa) ? '' : limpa;
}

/**
 * A contagem em UMA forma só, venha ela como lista (servidor anterior à 0051)
 * ou como objeto com o bloco de presencial.
 *
 * Sem isto, a janela entre o deploy do backend e o do front derruba a tela de
 * pedidos com `contagem.map is not a function` — erro que não diz nada a quem
 * está com a mão na panela.
 */
export function normalizarContagem(
  bruto: ContagemDeOpcao[] | ContagemDoCardapio | null | undefined,
): ContagemDoCardapio {
  if (!bruto) return { opcoes: [], presencial: null };
  if (Array.isArray(bruto)) return { opcoes: bruto, presencial: null };
  return { opcoes: bruto.opcoes ?? [], presencial: bruto.presencial ?? null };
}

// ─── A contagem do dia, quebrada por modo (docs/40 §10.1) ─────────────────

/**
 * Os três números de um cardápio: quantos comem, quantos pediram, quantos
 * pegam na hora.
 *
 * ⚠️ `comPedido` e `presenciais` são OPCIONAIS aqui e obrigatórios em
 * `DiaDoCalendario`, e a diferença é deliberada: o contrato diz que o servidor
 * manda os três, mas um servidor anterior à 0052 manda só `pedidos` — e nessa
 * janela "não sei" não pode virar "nenhum presencial". Quem declara o contrato
 * é rígido; quem lê, tolerante.
 */
export interface ContagemDoDia {
  /** Quantos vão comer, as duas portas somadas. */
  pedidos: number;
  /** Quantos escolheram prato. */
  comPedido?: number;
  /** Quantos declararam presença — pendentes e já retiradas juntas. */
  presenciais?: number;
}

/** Milhar com ponto: um mês inteiro passa de mil sem esforço. */
function numeroLegivel(n: number): string {
  return n.toLocaleString('pt-BR');
}

/**
 * A quebra do total, ou `null` quando não há o que quebrar.
 *
 * Ela existe porque dois números da cantina passaram a divergir POR DESENHO: o
 * calendário conta quem vai comer, e a contagem por opção conta quem escolheu
 * prato — presencial não escolhe nenhum (docs/40 §10.1). Os dois estavam
 * certos, e é justamente isso que fazia a divergência virar chamado de bug.
 *
 * `null` cobre dois casos que são o MESMO para quem lê a tela: dia sem
 * presencial nenhum, e servidor que ainda não manda a quebra. Nos dois a tela
 * fica exatamente como estava — a quebra é acréscimo, e acréscimo que aparece
 * sempre vira ruído nas ~60 células do mês em que ele não diz nada.
 */
export function quebraDaContagem(
  contagem: ContagemDoDia,
): { comPedido: number; presenciais: number } | null {
  if (contagem.comPedido == null || !contagem.presenciais) return null;
  return { comPedido: contagem.comPedido, presenciais: contagem.presenciais };
}

/**
 * "44 com pedido · 3 de retirada na hora".
 *
 * Os dois nomes saem do editor da cantina — «Pedido com antecedência» e
 * «Retirada na hora» —, que é também como a linha à parte da contagem já os
 * chama. Um segundo nome para a mesma coisa faria a cantina e a coordenação
 * lerem duas features onde há uma.
 *
 * O separador troca porque " · " não é palavra: na leitura do leitor de tela
 * ele vira " e ".
 */
export function fraseDaQuebra(
  quebra: { comPedido: number; presenciais: number },
  separador = ' · ',
): string {
  return `${numeroLegivel(quebra.comPedido)} com pedido`
    + `${separador}${numeroLegivel(quebra.presenciais)} de retirada na hora`;
}

/**
 * Como se chama o total — e a palavra muda porque o que ele conta mudou.
 *
 * "pedidos" foi verdade enquanto havia uma porta só. Com a retirada presencial
 * ligada, o total inclui quem não pediu nada, e chamar isso de pedido é
 * exatamente o que faz o número parecer errado ao lado da contagem por prato.
 * Sem presencial no dia, a palavra de sempre continua: quem nunca ligou a
 * feature não vê nada mudar.
 */
export function rotuloDaContagem(contagem: ContagemDoDia): string {
  if (contagem.presenciais) return contagem.pedidos === 1 ? 'vai comer' : 'vão comer';
  return contagem.pedidos === 1 ? 'pedido' : 'pedidos';
}

/**
 * As duas refeições de um dia — ou o mês inteiro — somadas em uma contagem só.
 *
 * A quebra só sobrevive à soma se TODAS as parcelas a trouxerem: somar um
 * cardápio que sabe a quebra com outro que não sabe daria um "com pedido" menor
 * que a verdade, e número errado é pior que número nenhum. É a mesma régua de
 * `contarDireitos` e de `useResumoDoMes`.
 */
export function somarContagens(
  partes: ReadonlyArray<ContagemDoDia | null | undefined>,
): ContagemDoDia {
  const presentes = partes.filter((p): p is ContagemDoDia => !!p);
  const pedidos = presentes.reduce((soma, p) => soma + p.pedidos, 0);
  if (!presentes.length || presentes.some((p) => p.comPedido == null || p.presenciais == null)) {
    return { pedidos };
  }
  return {
    pedidos,
    comPedido: presentes.reduce((soma, p) => soma + (p.comPedido ?? 0), 0),
    presenciais: presentes.reduce((soma, p) => soma + (p.presenciais ?? 0), 0),
  };
}

/**
 * A mesma contagem, a partir da LISTA do balcão.
 *
 * A tela de pedidos da cantina tira o total dela da lista de alunos, não do
 * calendário — e sem isto ela diria "47 pedidos" no cabeçalho tendo a linha de
 * presencial logo abaixo, contradizendo a própria frase. Duas fontes, um
 * vocabulário.
 */
export function contagemPorModo(
  pedidos: ReadonlyArray<{ modo?: ModoDeRefeicao }>,
): ContagemDoDia {
  const presenciais = pedidos.filter((p) => p.modo === 'presencial').length;
  return { pedidos: pedidos.length, comPedido: pedidos.length - presenciais, presenciais };
}

/**
 * A marca de modo nas listas da cantina e da coordenação (docs/40 §7 e §8).
 *
 * ⚠️ **"retirada na hora", nunca "presencial".** `presencial` é o valor da
 * coluna `pedido_refeicao.modo` — dado, não texto de tela. Quem lê a lista lê o
 * mesmo nome do toggle do editor da cantina e da quebra da contagem
 * (`fraseDaQuebra`), que é a regra já declarada em `ModosDaRefeicao`
 * (`telas/Administracao/Cantina.tsx`): um segundo nome faria a coordenação e a
 * cantina discutirem duas features onde há uma.
 *
 * Não é dado sensível como a restrição alimentar — é rótulo de fluxo —, então
 * o texto é o mesmo para administrador e coordenador comum.
 */
export function marcaDoModo(pedido: { modo?: ModoDeRefeicao; retiradoEm?: string | null }): string {
  if (pedido.modo !== 'presencial') return 'pedido';
  return pedido.retiradoEm ? 'retirada na hora · retirado' : 'retirada na hora';
}

/**
 * O que a coluna de escolhas diz de uma linha — inclusive quando não há prato.
 *
 * Uma retirada na hora não escolhe nada (docs/40 §10.1), e a célula vazia era
 * lida como dado FALTANDO: na folha impressa saía "João Silva · 3ºA · —", e
 * quem serve ia procurar um prato que não existe. A marca de modo diz o fluxo;
 * esta frase diz o que fazer com a linha.
 *
 * O separador é parâmetro porque a planilha do mês separa itens por " | " e a
 * folha do balcão por " · " — e quem monta a linha não deve ter de saber disso.
 */
export function escolhasDaLinha(
  pedido: { modo?: ModoDeRefeicao; retiradoEm?: string | null; escolhas?: readonly string[] },
  separador = ' · ',
): string {
  if (pedido.modo === 'presencial') {
    // ⚠️ A metade acionável ("vai mostrar o código") tem de vir junto, e o
    // motivo é a folha impressa: ela é o documento do balcão (docs/38 §8.2), e
    // dizer só "sem prato escolhido" manda quem serve procurar um prato que não
    // existe, em vez de esperar um código. A tela da cantina tinha essa frase
    // inteira e o papel não — as duas superfícies agora saem daqui.
    return pedido.retiradoEm
      ? `retirado às ${horaLegivel(pedido.retiradoEm)}`
      : 'sem prato escolhido — vai mostrar o código no balcão';
  }
  return (pedido.escolhas ?? []).join(separador);
}

/**
 * O placar da retirada na hora de um cardápio: o do servidor quando ele o
 * manda, e o da própria lista quando não.
 *
 * ⚠️ Existe pelos dois lados da mesma frase. `GET /administracao/cantina/
 * cardapios/{id}` passou a mandar `presencial` junto da contagem por opção —
 * que ignora o presencial de propósito (docs/40 §10.1) —, mas a tela é lida
 * contra servidor que ainda não o manda, e nessa janela "O que cozinhar" dizia
 * "Nenhum pedido ainda" ao lado de doze nomes na coluna vizinha. A lista de
 * pedidos já está aberta na tela e carrega `modo` e `retiradoEm`: ela responde
 * a mesma pergunta sem inventar número.
 *
 * `null` quando ninguém pega na hora — zero e zero não é placar, é ruído em
 * toda tela de cantina que nunca ligou a feature.
 */
export function presencialDoCardapio(
  doServidor: ContagemPresencial | null | undefined,
  pedidos: ReadonlyArray<{ modo?: ModoDeRefeicao; retiradoEm?: string | null }>,
): ContagemPresencial | null {
  const bloco = doServidor ?? contarPresencial(pedidos);
  return bloco.pendentes + bloco.retirados > 0 ? bloco : null;
}

function contarPresencial(
  pedidos: ReadonlyArray<{ modo?: ModoDeRefeicao; retiradoEm?: string | null }>,
): ContagemPresencial {
  const presenciais = pedidos.filter((p) => p.modo === 'presencial');
  const retirados = presenciais.filter((p) => p.retiradoEm).length;
  return { pendentes: presenciais.length - retirados, retirados };
}

/** "12:14" — a hora de uma leitura, que é o único pedaço do carimbo que
    interessa a quem está no balcão. */
export function horaLegivel(iso: string | null | undefined): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Qual refeição está sendo servida agora, para a tela "Ler código" abrir
 * já apontada para o serviço em curso.
 *
 * É um PALPITE, e a tela deixa trocar: a fase 1 não tem janela de horário
 * cadastrada (isso é a fase 3, docs/40 §13), então o corte aqui é uma
 * conveniência de abertura — nada depende dele além do destaque de "refeição
 * trocada".
 */
export function refeicaoPorHorario(agora: Date = new Date()): Refeicao {
  return agora.getHours() < 16 ? 'almoco' : 'janta';
}

/**
 * O que a tela da cantina mostra depois de uma leitura (docs/40 §7).
 *
 * Os cinco desfechos são desfechos DIFERENTES, e não "sucesso e erro": dois
 * deles são problema de verdade, e por motivos opostos.
 *
 *   · `sucesso`      → a ficha, com a restrição alimentar em destaque se
 *                      houver. É o momento em que dá para agir sobre ela;
 *   · `ja-retirado`  → segunda passagem, quase sempre por engano. A hora da
 *                      retirada original está na frase do servidor;
 *   · `atualizar`    → token vencido ou adulterado. A ação é do ALUNO: pedir
 *                      para ele atualizar a tela;
 *   · `recusado`     → cardápio de outra cantina, ou qualquer outra recusa;
 *   · `sem-resposta` → não houve veredito nenhum: a requisição não voltou. É a
 *                      única linha desta lista em que o servidor **não disse
 *                      nada**, e por isso é a única em que ler o mesmo código de
 *                      novo é a ação certa. Confundi-la com `recusado` mandaria
 *                      embora um aluno que tem direito à refeição.
 *
 * `refeicaoTrocada` não é recusa: o token é válido: é um QR de janta lido no
 * almoço. O servidor não bloqueia — quem decide é quem está no balcão.
 */
export type LeituraDoQr =
  | { tipo: 'sucesso'; ficha: RetiradaConfirmada; refeicaoTrocada: boolean }
  | { tipo: 'ja-retirado'; mensagem: string }
  | { tipo: 'atualizar'; mensagem: string }
  | { tipo: 'recusado'; mensagem: string }
  | { tipo: 'sem-resposta'; mensagem: string };

/**
 * A recusa como a tela a recebe: o status e a frase que o servidor mandou.
 *
 * `status: 0` é a convenção de `servicos/http.ts` para "não houve resposta HTTP
 * nenhuma" — rede caída, requisição abortada por tempo. Não é um veredito com
 * número baixo: é a ausência de veredito.
 */
export interface RecusaDaLeitura {
  status: number;
  mensagem: string;
}

export function lerRespostaDoQr(
  resposta: RetiradaConfirmada | RecusaDaLeitura,
  refeicaoDoServico: Refeicao,
): LeituraDoQr {
  if ('status' in resposta) {
    const mensagem = resposta.mensagem.trim();
    // Sem status HTTP não houve resposta: o servidor pode ter gravado a retirada
    // e a resposta ter se perdido na volta. A frase é sobre a AÇÃO seguinte —
    // ler de novo —, e não sobre a causa, que ninguém no balcão pode consertar.
    if (!resposta.status) {
      return {
        tipo: 'sem-resposta',
        mensagem: mensagem || 'A rede não respondeu. Peça o código de novo e leia mais uma vez.',
      };
    }
    if (resposta.status === 409) {
      return { tipo: 'ja-retirado', mensagem: mensagem || 'Esta refeição já foi retirada.' };
    }
    if (resposta.status === 422 || resposta.status === 400) {
      return {
        tipo: 'atualizar',
        mensagem: mensagem || 'Código vencido. Peça para o aluno atualizar a tela.',
      };
    }
    return { tipo: 'recusado', mensagem: mensagem || 'Não consegui confirmar esta retirada.' };
  }
  return {
    tipo: 'sucesso',
    ficha: resposta,
    refeicaoTrocada: resposta.refeicao !== refeicaoDoServico,
  };
}

/**
 * O que o card da cantina mostra em Hoje — e qual dia ele fala.
 *
 * Função pura porque a ORDEM DE PRIORIDADE é a regra, e regra que mora dentro
 * de um componente não tem teste. A ordem:
 *
 *   1. `escolher`        há prazo aberto e eu não resolvi. O único estado
 *                        urgente, e o único que merece um card grande: perder
 *                        este prazo custa a refeição.
 *   2. `retirada`        eu vou pegar pessoalmente e ninguém leu o QR ainda.
 *                        Linha quieta com o caminho para o código.
 *   3. `pedido-aberto`   há prazo aberto e eu já pedi. Linha quieta, com a
 *                        opção de trocar enquanto dá.
 *   4. `pedido-fechado`  o prazo passou e eu tenho pedido para um dia que
 *                        ainda vem. Linha quieta, sem trocar — é a resposta a
 *                        "o que eu vou comer amanhã?".
 *   5. `retirado`        eu já comi hoje. Linha quieta e factual, com a hora.
 *   6. `presencial-aberto`  o prazo de HOJE passou, eu não pedi, mas este
 *                        cardápio aceita presencial. É a diferença entre "você
 *                        perdeu" e "ainda dá" — e é a razão da feature.
 *   7. `sem-reserva`     o prazo de HOJE passou, eu não pedi e não há
 *                        presencial. Existe para o aluno não caminhar até o
 *                        balcão à toa.
 *   8. `null`            não há nada a dizer, e o card some.
 *
 * ⚠️ O estado 4 é o que faltava na primeira escrita, e a falta não era
 * cosmética: com o card sumindo, `/cantina` ficava SEM PORTA — não está na
 * barra de quatro destinos (de propósito), e o card era o único caminho. Quem
 * pedisse na véspera não tinha como conferir o próprio pedido depois que o
 * prazo fechava.
 *
 * ⚠️ `escolher` continua vencendo a retirada pendente, e é de propósito: só o
 * prazo do PEDIDO expira. O QR de hoje não vira abóbora ao meio-dia, o de
 * amanhã sim.
 */
export type CardDaCantina =
  | {
      tipo: 'escolher' | 'retirada' | 'pedido-aberto' | 'pedido-fechado' | 'retirado'
        | 'presencial-aberto' | 'sem-reserva';
      dia: DiaDoAluno;
    }
  | null;

export function cardDaCantina(dias: readonly DiaDoAluno[], agora: Date = new Date()): CardDaCantina {
  if (!dias.length) return null;
  const hoje = isoDoDia(agora);
  const situacao = (d: DiaDoAluno) => situacaoDoDia(d, agora);

  // O próximo prazo ABERTO — não o próximo dia. Um cardápio de quarta com
  // prazo até terça é mais urgente que o de amanhã já fechado.
  const abertos = dias.filter((d) => prazoAberto(d.pedidos_ate, agora));
  const porResolver = abertos.find((d) => situacao(d).estado === 'aberto');
  if (porResolver) return { tipo: 'escolher', dia: porResolver };

  // A retirada pendente de HOJE é o que o aluno faz ao chegar no balcão; a de
  // um dia futuro ainda não é ação nenhuma.
  const retirando = dias.find((d) => d.data === hoje && situacao(d).estado === 'presencial');
  if (retirando) return { tipo: 'retirada', dia: retirando };

  const pedidoAberto = abertos.find((d) => situacao(d).estado === 'pedido');
  if (pedidoAberto) return { tipo: 'pedido-aberto', dia: pedidoAberto };

  // Prazo fechado: o pedido de um dia que ainda vem continua interessando.
  const pedido = dias.find((d) => d.data >= hoje && situacao(d).estado === 'pedido');
  if (pedido) return { tipo: 'pedido-fechado', dia: pedido };

  const retirado = dias.find((d) => d.data === hoje && d.retiradoEm);
  if (retirado) return { tipo: 'retirado', dia: retirado };

  const deHoje = dias.find((d) => d.data === hoje && situacao(d).estado === 'aberto');
  if (!deHoje) return null;
  return { tipo: situacao(deHoje).podeRetirar ? 'presencial-aberto' : 'sem-reserva', dia: deHoje };
}

// ─── A planilha larga: uma coluna por bloco (docs/40 §12.5.2) ─────────────

/**
 * Os blocos de um cardápio, na ordem em que a cantina os montou.
 *
 * Sai da CONTAGEM e não do cardápio porque é a contagem que o export já tem em
 * mãos — e ela carrega `bloco_ordem`, que é a ordem verdadeira. Derivar dos
 * pedidos daria só os blocos que alguém escolheu: um dia em que ninguém pediu
 * salada perderia a coluna Salada, e a planilha da semana ficaria com colunas
 * diferentes por dia sem que nada explicasse por quê.
 */
export function blocosDaContagem(contagem: ReadonlyArray<ContagemDeOpcao>): string[] {
  const porOrdem = new Map<string, number>();
  for (const linha of contagem) {
    const atual = porOrdem.get(linha.bloco);
    if (atual === undefined || linha.bloco_ordem < atual) porOrdem.set(linha.bloco, linha.bloco_ordem);
  }
  return [...porOrdem.entries()].sort((a, b) => a[1] - b[1]).map(([nome]) => nome);
}

/**
 * A que bloco pertence cada opção, pelo NOME.
 *
 * ⚠️ Por nome, e não por id, porque é o nome que viaja em `PedidoDeAluno.escolhas`
 * — a lista do balcão manda o que servir, não identificadores. Duas opções com
 * o mesmo nome em blocos diferentes ("Ovo" em Vegetariano e em Guarnição) caem
 * na primeira: é ambiguidade do cardápio, não do código, e resolvê-la aqui
 * escondendo uma das duas seria pior que repetir o nome na coluna errada.
 */
export function blocoDeCadaOpcao(
  contagem: ReadonlyArray<ContagemDeOpcao>,
): Map<string, string> {
  const mapa = new Map<string, string>();
  for (const linha of contagem) {
    if (!mapa.has(linha.opcao)) mapa.set(linha.opcao, linha.bloco);
  }
  return mapa;
}

/**
 * As escolhas de um aluno, distribuídas nas colunas de bloco.
 *
 * Devolve um valor por bloco pedido, na mesma ordem — vazio onde ele não
 * escolheu nada, e com `; ` juntando quando o bloco permite mais de uma
 * ("Arroz; Feijão; Farofa" na Guarnição).
 *
 * ⚠️ Quem pega na hora não escolhe prato (docs/40 §10.1): todas as colunas
 * saem com o traço, e não vazias. Célula vazia numa planilha lê-se como "faltou
 * o dado"; o traço diz que não havia dado a ter.
 */
export function escolhasPorBloco(
  pedido: Pick<PedidoDeAluno, 'escolhas' | 'modo'>,
  blocos: ReadonlyArray<string>,
  deQualBloco: ReadonlyMap<string, string>,
): string[] {
  if (pedido.modo === 'presencial') return blocos.map(() => '—');
  const porBloco = new Map<string, string[]>();
  for (const escolha of pedido.escolhas ?? []) {
    const bloco = deQualBloco.get(escolha);
    if (!bloco) continue;
    porBloco.set(bloco, [...(porBloco.get(bloco) ?? []), escolha]);
  }
  return blocos.map((bloco) => (porBloco.get(bloco) ?? []).join('; '));
}

/**
 * A união dos blocos de vários dias, para a planilha da SEMANA.
 *
 * ⚠️ Cardápios de dias diferentes podem ter blocos diferentes, e é isso que
 * torna a união necessária: a planilha do Google resolvia repetindo o conjunto
 * de colunas por dia, o que fica ilegível na terceira quarta-feira. Aqui as
 * colunas são a união, e o dia que não tinha aquele bloco fica com a célula
 * vazia — que é a verdade: não havia o que escolher.
 *
 * A ordem é a do primeiro dia em que cada bloco apareceu, e não alfabética:
 * a cantina monta o cardápio numa ordem que é a da bandeja.
 */
export function blocosDoPeriodo(
  contagens: ReadonlyArray<ReadonlyArray<ContagemDeOpcao>>,
): string[] {
  const vistos: string[] = [];
  for (const contagem of contagens) {
    for (const bloco of blocosDaContagem(contagem)) {
      if (!vistos.includes(bloco)) vistos.push(bloco);
    }
  }
  return vistos;
}

// ─── A lista de trabalho (docs/40 §12.4) ─────────────────────────────────

/** Os recortes da lista de quem vai comer. */
export type FiltroDaLista = 'pediu' | 'presencial' | 'retirado' | 'restricao';

/** Por que ordenar. `hora` é a que responde "quem deixou para a última hora". */
export type OrdemDaLista = 'nome' | 'turma' | 'hora';

/**
 * A lista recortada e ordenada — a mesma função para a coordenação e o balcão.
 *
 * ⚠️ **Devolve o que a tela mostra, e é ele que o botão de exportar leva.** Um
 * export que ignorasse o filtro entregaria 47 linhas enquanto a tela mostra 44,
 * e a diferença só apareceria na cozinha (docs/40 §12.4).
 *
 * Os filtros se ACUMULAM (interseção), e é o que se espera de pílulas: marcar
 * "retirado" e "com restrição" é procurar quem já comeu e tem restrição, não a
 * união dos dois grupos.
 */
export function recortarPedidos(
  pedidos: ReadonlyArray<PedidoDeAluno>,
  { filtros, busca, ordem }: {
    filtros: ReadonlySet<FiltroDaLista>;
    busca: string;
    ordem: OrdemDaLista;
  },
): PedidoDeAluno[] {
  const q = normalizarTexto(busca.trim());

  const recortados = pedidos.filter((p) => {
    if (filtros.has('pediu') && (p.modo ?? 'pedido') !== 'pedido') return false;
    if (filtros.has('presencial') && p.modo !== 'presencial') return false;
    // "Retirado" é sobre a hora de retirada, não sobre o modo: quem pediu na
    // véspera também pode ter sido servido — o campo é o mesmo.
    if (filtros.has('retirado') && !p.retiradoEm) return false;
    if (filtros.has('restricao') && !p.restricaoAlimentar) return false;
    if (q && !normalizarTexto(p.nome ?? '').includes(q)) return false;
    return true;
  });

  return [...recortados].sort((a, b) => {
    if (ordem === 'hora') {
      // Sem hora vai para o FIM, e não para o começo: uma linha sem carimbo é
      // ausência de dado, e ausência liderando uma ordenação por tempo faz
      // parecer que ela é a mais recente.
      if (!a.pedidoEm) return 1;
      if (!b.pedidoEm) return -1;
      return a.pedidoEm.localeCompare(b.pedidoEm);
    }
    if (ordem === 'turma') {
      const porTurma = (a.turma ?? '~').localeCompare(b.turma ?? '~', 'pt-BR');
      if (porTurma !== 0) return porTurma;
    }
    return (a.nome ?? '').localeCompare(b.nome ?? '', 'pt-BR');
  });
}

/** "sem acento, minúsculo" — a mesma régua de busca do resto do produto. */
function normalizarTexto(texto: string): string {
  return texto.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();
}

/** "pediu 18:42" / "retirado 12:07" — a hora que a linha mostra.
 *
 *  Prefere a RETIRADA quando ela existe: entre "quando marcou" e "quando
 *  comeu", quem está conferindo a fila quer a segunda. */
export function horaDaLinha(pedido: Pick<PedidoDeAluno, 'pedidoEm' | 'retiradoEm'>): string | null {
  if (pedido.retiradoEm) return `retirado ${horaLegivel(pedido.retiradoEm)}`;
  if (pedido.pedidoEm) return `pediu ${horaLegivel(pedido.pedidoEm)}`;
  return null;
}
