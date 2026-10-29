// CONEXÕES DE IA — o que as duas telas do MCP decidem antes de desenhar
// (docs/43 §5.3): a lista de tokens e os e-mails da IA em
// `/administracao/conexoes-de-ia`, e o consentimento do OAuth em
// `/conectar-ia`, que desde 26/10 é página PÚBLICA, aprovada por código.
//
// Por que isto é domínio e não ternário no TSX: cada função abaixo responde a
// uma pergunta que, respondida errado, MENTE sobre acesso a dado de menor de
// idade — "esta conexão ainda lê o SAS?", "quem pode emitir?", "para onde o
// browser vai depois de aprovar?". Erro de layout se vê; erro aqui, não.
//
// ⚠️ Nada aqui inventa número. Lista que não chegou é `null`, não "0 ativas":
// "nenhuma IA conectada" para quem tem três ligadas é a mentira mais cara que
// esta tela poderia contar.

import type { ConexaoDeIa, DisponibilidadeDoMcp } from '../tipos/dominio';
import { destinoInterno } from './voltaDoLogin';

/** O teto do contrato (`POST /mcp/tokens`: nome de 1 a 80 caracteres). */
export const NOME_MAXIMO = 80;

export function nomeDaConexaoValido(nome: string): boolean {
  const limpo = nome.trim();
  return limpo.length >= 1 && limpo.length <= NOME_MAXIMO;
}

// ─── Texto que veio de fora ──────────────────────────────────────────────

/**
 * O teto do nome que um app declara sobre si. É de rótulo, e não o do
 * cadastro: o título do consentimento é "<nome> quer ler o SAS com o seu
 * acesso", e um nome de 300 caracteres empurraria o resto da tela para baixo
 * do botão.
 */
export const NOME_DO_APP_MAXIMO = 60;

// Controle (C0, C1, DEL) e separador de linha ou de parágrafo: viram espaço.
const CONTROLE_OU_QUEBRA = /[\p{Cc}\p{Zl}\p{Zp}]/gu;
// Formatação (U+202E, U+200B, U+2066…): é invisível, mas reordena ou esconde
// o texto em volta. Sai sem deixar espaço no lugar.
const FORMATACAO_INVISIVEL = /\p{Cf}/gu;

/**
 * O texto numa linha só, sem caractere invisível e com tamanho de rótulo.
 *
 * ⚠️ Existe por causa do nome que o app declara no cadastro dinâmico do OAuth
 * (docs/43 §2): é texto de quem pede o acesso, e ele aparece justamente onde
 * se decide sobre esse acesso. No `window.confirm` de revogar, a quebra de
 * linha é a estrutura do diálogo. Com um nome como "Claude\n\nPara revogar,
 * clique em Cancelar", o app escreveria as instruções do diálogo que serve
 * para cortá-lo. Sem os caracteres de formatação, um nome também não se
 * disfarça de outro (U+202E inverte a leitura).
 *
 * O corte é por caractere de verdade (`Array.from`), não por unidade de
 * UTF-16: cortar no meio de um par substituto deixaria um emoji quebrado no
 * fim.
 */
export function emUmaLinha(texto: string | null | undefined, maximo = Number.POSITIVE_INFINITY): string {
  const limpo = (texto ?? '')
    .replace(FORMATACAO_INVISIVEL, '')
    .replace(CONTROLE_OU_QUEBRA, ' ')
    .replace(/\s+/gu, ' ')
    .trim();
  const letras = Array.from(limpo);
  if (letras.length <= maximo) return limpo;
  return `${letras.slice(0, Math.max(maximo - 1, 0)).join('').trimEnd()}…`;
}

/** O nome que o app declarou, pronto para a tela; `null` se não sobrar nada. */
export function nomeDoApp(nome: string | null | undefined): string | null {
  return emUmaLinha(nome, NOME_DO_APP_MAXIMO) || null;
}

// ─── Situação ────────────────────────────────────────────────────────────

export type SituacaoDaConexao = 'ativa' | 'revogada' | 'expirada';

function instante(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime();
  return Number.isNaN(ms) ? null : ms;
}

/**
 * Se a conexão ainda abre o SAS.
 *
 * Revogada vence expirada: as duas fecham a porta, mas revogar foi um ATO de
 * alguém, e é o que a pessoa procura quando pergunta "o que aconteceu com
 * esta conexão?".
 *
 * ⚠️ Na conexão OAuth, `expiraEm` é o fim da CONCESSÃO, e não a validade de
 * 1 h do acesso em uso (contrato de 26/10, `GET /mcp/tokens`). A concessão
 * vale 30 dias contados da aprovação, e cada refresh herda esse fim
 * (`oauth_refresh_mcp.expira_em`, api/app/routes/oauth_mcp.py::_girar_refresh).
 * Até lá o app renova sozinho: um conector parado há duas horas tem o acesso
 * vencido e continua conectado, porque na próxima pergunta renova e lê. Depois
 * desse fim o refresh é recusado, e a conexão acabou como acaba um token
 * pessoal vencido. Por isso a regra é a mesma para as duas origens.
 *
 * Antes de 26/10 a lista trazia a validade de 1 h. Ler aquilo como "expirou"
 * escondia uma conexão viva e tirava dela o botão de revogar, e por isso a
 * regra ignorava `expiraEm` no OAuth. Agora ela confia no contrato: se o campo
 * voltar a trazer o acesso, o defeito volta junto.
 */
export function situacaoDaConexao(conexao: ConexaoDeIa, agora: Date): SituacaoDaConexao {
  if (conexao.revogadaEm) return 'revogada';
  const fim = instante(conexao.expiraEm);
  if (fim != null && fim <= agora.getTime()) return 'expirada';
  return 'ativa';
}

// ─── Datas ───────────────────────────────────────────────────────────────
//
// Os campos do contrato são INSTANTES (timestamptz), não datas: `new Date()`
// é o certo aqui, e "hoje" é o dia LOCAL de quem lê. O calendário da escola é
// local — às 22h de Fortaleza já é amanhã em UTC.

const p2 = (n: number) => String(n).padStart(2, '0');

/** O dia local como número de dias desde a época — sem o fuso nem o horário de verão. */
function diaLocal(d: Date): number {
  return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / 86_400_000;
}

/** Quantos dias de CALENDÁRIO entre o instante e agora. 0 = hoje. */
export function diasDesde(iso: string, agora: Date): number | null {
  const ms = instante(iso);
  if (ms == null) return null;
  return diaLocal(agora) - diaLocal(new Date(ms));
}

/** `24/10/2026`, no fuso de quem lê. `—` quando o instante não é legível. */
export function dataCurta(iso: string | null | undefined): string {
  const ms = instante(iso);
  if (ms == null) return '—';
  const d = new Date(ms);
  return `${p2(d.getDate())}/${p2(d.getMonth() + 1)}/${d.getFullYear()}`;
}

/** `14:32`, no fuso de quem lê. */
export function horaCurta(iso: string | null | undefined): string {
  const ms = instante(iso);
  if (ms == null) return '—';
  const d = new Date(ms);
  return `${p2(d.getHours())}:${p2(d.getMinutes())}`;
}

/**
 * O último uso, como a coluna o mostra: "hoje, 14:32", "ontem, 09:10",
 * "há 3 dias", "12/10/2026" ou "nunca".
 *
 * A hora só aparece perto: para quem procura uma conexão que não reconhece,
 * "hoje, 03:12" é o dado que importa, e "há 40 dias, 03:12" é ruído.
 */
export function ultimoUsoLegivel(iso: string | null, agora: Date): string {
  if (!iso) return 'nunca';
  const dias = diasDesde(iso, agora);
  if (dias == null) return '—';
  // Instante no futuro é relógio fora de acerto, não viagem no tempo: lê como hoje.
  if (dias <= 0) return `hoje, ${horaCurta(iso)}`;
  if (dias === 1) return `ontem, ${horaCurta(iso)}`;
  if (dias < 7) return `há ${dias} dias`;
  return dataCurta(iso);
}

/** A coluna Situação: o estado e, quando houver, a data que o explica. */
export function situacaoLegivel(conexao: ConexaoDeIa, agora: Date): string {
  switch (situacaoDaConexao(conexao, agora)) {
    case 'revogada':
      return `revogada em ${dataCurta(conexao.revogadaEm)}`;
    case 'expirada':
      return `expirou em ${dataCurta(conexao.expiraEm)}`;
    default:
      // No OAuth a data é o fim da concessão, e o "renova sozinho" fica na
      // frase: sem ele, "expira em" faria pensar que o conector parado morre
      // antes disso, ou que é preciso fazer alguma coisa até lá.
      if (conexao.origem === 'oauth') {
        return conexao.expiraEm
          ? `ativa · o app renova o acesso sozinho até ${dataCurta(conexao.expiraEm)}`
          : 'ativa · o app renova o acesso sozinho';
      }
      return conexao.expiraEm ? `ativa · expira em ${dataCurta(conexao.expiraEm)}` : 'ativa';
  }
}

/**
 * A coluna Origem. O nome do app só existe no OAuth — no token pessoal quem
 * dá nome à conexão é a própria pessoa, e repeti-lo aqui seria eco.
 */
export function origemLegivel(conexao: ConexaoDeIa): string {
  if (conexao.origem !== 'oauth') return 'token pessoal';
  const app = nomeDoApp(conexao.cliente);
  return app ? `OAuth · ${app}` : 'OAuth';
}

// ─── A lista ─────────────────────────────────────────────────────────────

/**
 * As ativas primeiro, da mais nova para a mais velha; depois as encerradas,
 * da que fechou por último.
 *
 * ⚠️ As encerradas FICAM na lista. Revogar não apaga nada (o contrato é
 * `POST …/revogar`, não `DELETE`), e a linha revogada é o que responde, meses
 * depois, "quem tinha acesso a isto, e até quando?".
 */
export function ordenarConexoes(conexoes: readonly ConexaoDeIa[], agora: Date): ConexaoDeIa[] {
  const ms = (iso: string | null) => instante(iso) ?? 0;
  return [...conexoes].sort((a, b) => {
    const aAtiva = situacaoDaConexao(a, agora) === 'ativa';
    const bAtiva = situacaoDaConexao(b, agora) === 'ativa';
    if (aAtiva !== bAtiva) return aAtiva ? -1 : 1;
    if (aAtiva) return ms(b.criadaEm) - ms(a.criadaEm);
    return ms(b.revogadaEm ?? b.expiraEm) - ms(a.revogadaEm ?? a.expiraEm);
  });
}

function maisRecente(isos: readonly (string | null)[]): string | null {
  let melhor: string | null = null;
  let melhorMs = -Infinity;
  for (const iso of isos) {
    const ms = instante(iso);
    if (ms != null && ms > melhorMs) {
      melhor = iso;
      melhorMs = ms;
    }
  }
  return melhor;
}

/** "usada hoje", "última usada há 3 dias", "nenhuma usada ainda". */
function usoNoResumo(ativas: readonly ConexaoDeIa[], agora: Date): string | null {
  const uma = ativas.length === 1;
  const ultimo = maisRecente(ativas.map((c) => c.ultimoUsoEm));
  if (!ultimo) return uma ? 'nunca usada' : 'nenhuma usada ainda';
  const dias = diasDesde(ultimo, agora);
  if (dias == null) return null;
  const sujeito = uma ? 'usada' : 'última usada';
  if (dias <= 0) return `${sujeito} hoje`;
  if (dias === 1) return `${sujeito} ontem`;
  if (dias < 7) return `${sujeito} há ${dias} dias`;
  return `${sujeito} em ${dataCurta(ultimo)}`;
}

/**
 * O subtítulo do card no hub (C2 de `Campo.tsx`): "2 ativas · última usada
 * hoje".
 *
 * Os três estados do card, e quem decide cada um:
 *   - lista que não chegou → `null` (quem chama também zera na FALHA, e o card
 *     cai no texto de vazio em vez de um "0" falso);
 *   - nenhuma conexão, nunca → `null`, e o card diz que não há IA conectada;
 *   - o resto → a frase, com o número real.
 *
 * ⚠️ "servidor desligado" vem PRIMEIRO, pelo mesmo motivo da pendência no card
 * da cantina: é a única coisa aqui sobre a qual alguém age. Duas conexões
 * ativas num servidor desligado são duas IAs que não leem nada — e o card
 * que dissesse só "2 ativas" esconderia isso. `habilitado` nulo é "não sei"
 * (a consulta da disponibilidade falhou), e aí o card não afirma nada.
 *
 * Só as ATIVAS contam no último uso: uma revogada não lê mais, e o card
 * responde "o que está lendo o SAS agora?".
 */
export function resumoDasConexoes(
  conexoes: readonly ConexaoDeIa[] | undefined,
  habilitado: boolean | null,
  agora: Date,
): string | null {
  if (!conexoes) return null;
  const partes: string[] = [];
  if (habilitado === false) partes.push('servidor desligado');
  const ativas = conexoes.filter((c) => situacaoDaConexao(c, agora) === 'ativa');
  if (ativas.length) {
    partes.push(`${ativas.length} ${ativas.length === 1 ? 'ativa' : 'ativas'}`);
    const uso = usoNoResumo(ativas, agora);
    if (uso) partes.push(uso);
  } else if (conexoes.length) {
    const n = conexoes.length;
    partes.push(`nenhuma ativa · ${n} ${n === 1 ? 'encerrada' : 'encerradas'}`);
  }
  return partes.length ? partes.join(' · ') : null;
}

/**
 * O texto do card quando não há resumo — o `vazio` de `CartaoDeCampo`.
 *
 * ⚠️ O card mostra `vazio` sempre que o subtítulo é nulo, e o subtítulo é nulo
 * em DOIS casos que não podem dizer a mesma coisa: a lista vazia e a lista
 * que não chegou. Nos outros cards do hub a falha cai no texto de vazio; aqui
 * não, porque "nenhuma IA conectada" dito a quem tem três ligadas é a mentira
 * do topo deste arquivo.
 *
 * O coordenador só enxerga as conexões em nome dele (`GET /mcp/tokens`), e o
 * vazio diz isso — "nenhuma IA conectada ao SAS" seria afirmar sobre a escola
 * inteira com a lista de uma pessoa.
 */
export function vazioDasConexoes(falhou: boolean, souAdministrador: boolean): string {
  if (falhou) return 'Não consegui ler as conexões agora.';
  return souAdministrador ? 'Nenhuma IA conectada ao SAS ainda.' : 'Nenhuma IA conectada em seu nome.';
}

/**
 * Revogar uma conexão OAuth corta também a RENOVAÇÃO (docs/43 §5.3, Fase 3).
 *
 * A chave nasceu `false`, como contrato pendente: `POST /mcp/tokens/{id}/revogar`
 * só preenche `revogado_em` da linha (api/app/routes/mcp_tokens.py), e o
 * refresh mora em outra tabela (`oauth_refresh_mcp`, 0073) e vale 30 dias —
 * sem um corte do lado do OAuth, o app renovaria pelo refresh logo depois da
 * revogação, e quem revogou não ficaria sabendo. Esse corte existe: o
 * `/oauth/token` só gira o refresh se a linha de `token_mcp` (a CONEXÃO) não
 * foi revogada; se foi, responde `invalid_grant` e derruba a família inteira
 * (`oauth_mcp.py::_girar_refresh`, com teste em
 * `test_oauth_mcp.py::test_conexao_revogada_na_tela_nao_gira`). Visto também
 * na stack de ponta a ponta, em 26/10: revogada na tela, o access levou 401 no
 * MCP, e o refresh, `invalid_grant`.
 *
 * Por isso as duas telas prometem o corte: o `confirm` de revogar e o
 * consentimento, que leem esta mesma chave. ⚠️ Se o `/oauth/token` deixar de
 * conferir a revogação da conexão, ela volta a `false` no mesmo commit — o
 * texto que não promete o corte continua aqui, testado, para isso.
 */
export const REVOGACAO_OAUTH_CORTA_RENOVACAO = true;

/**
 * O texto do `confirm` de revogar. Diz o EFEITO, não o nome do botão: quem
 * clica precisa saber que a IA para na hora e que não há desfazer.
 *
 * `mostrarDono` é da visão do administrador, que revoga a conexão de outra
 * pessoa — e precisa ver de quem está tirando o acesso antes de tirar.
 *
 * Todo texto que entra aqui passa por `emUmaLinha`. O `confirm` é texto puro,
 * e nele a quebra de linha é a estrutura do diálogo: nenhum nome pode
 * acrescentar um parágrafo.
 */
export function perguntaDeRevogacao(
  conexao: ConexaoDeIa,
  {
    mostrarDono = false,
    cortaRenovacao = REVOGACAO_OAUTH_CORTA_RENOVACAO,
  }: { mostrarDono?: boolean; cortaRenovacao?: boolean } = {},
): string {
  const titulo = `Revogar “${emUmaLinha(conexao.nome, NOME_MAXIMO)}”?`;
  const dono = mostrarDono ? `\n\nA conexão é de ${emUmaLinha(conexao.dono.nome)}.` : '';
  if (conexao.origem !== 'oauth') {
    return `${titulo}\n\nA IA configurada com este token perde o acesso ao SAS na hora: a próxima consulta dela já é recusada. Não há como desfazer. Para conectar de novo, crie uma conexão nova e troque o token na IA.${dono}`;
  }
  const app = nomeDoApp(conexao.cliente) ?? 'O app';
  if (cortaRenovacao) {
    return `${titulo}\n\n${app} perde o acesso ao SAS na hora: a próxima consulta já é recusada, e o app não consegue renovar o acesso sozinho. Não há como desfazer. Para conectar de novo, é preciso autorizar outra vez pelo app.${dono}`;
  }
  // O que é verdade com o contrato de hoje: o acesso EM USO morre na hora. O
  // resto do texto é o que a pessoa faz para fechar o que o SAS ainda não
  // fecha.
  return `${titulo}\n\n${app} perde na hora o acesso que está usando: a próxima consulta com ele já é recusada. Não há como desfazer.\n\nPara cortar de vez, desconecte o SAS também no próprio app. Por enquanto, o SAS não impede o app de renovar o acesso sozinho, e aí a conexão volta a aparecer nesta lista.${dono}`;
}

/**
 * Como desfazer, dito no consentimento ANTES do "Aprovar". A pessoa aprova
 * contando com isto, então só vale o que o contrato garante. A chave é a
 * mesma do `confirm` de revogar (ver `REVOGACAO_OAUTH_CORTA_RENOVACAO`).
 */
export function comoDesfazerAConexao(cortaRenovacao = REVOGACAO_OAUTH_CORTA_RENOVACAO): string {
  return cortaRenovacao
    ? 'Dá para desfazer quando quiser, em Administração › Conexões de IA, e o corte é na hora.'
    : 'Para desfazer depois, revogue a conexão em Administração › Conexões de IA e desconecte o SAS também no próprio app: por enquanto, só revogar no SAS não impede o app de renovar o acesso sozinho.';
}

// ─── Configurar a IA ─────────────────────────────────────────────────────

/** A linha que toda IA de fora precisa mandar em cada chamada. */
export function cabecalhoDeAutorizacao(token: string): string {
  return `Authorization: Bearer ${token}`;
}

/**
 * O comando do Claude Code, já com o token: o caminho mais curto de "criei o
 * token" a "a IA lê o SAS", e o cliente que o docs/43 §5.3 põe primeiro.
 *
 * As aspas protegem o espaço de `Bearer …`. O token é `sas_mcp_` mais
 * base64url (letra, número, `-` e `_`), então não há o que escapar dentro
 * delas.
 */
export function comandoDoClaudeCode(url: string, token: string): string {
  return `claude mcp add --transport http sas "${url}" --header "${cabecalhoDeAutorizacao(token)}"`;
}

// ─── Quem pode emitir ────────────────────────────────────────────────────

export type PermissaoDeEmitir = 'pode' | 'so-administrador' | 'conferindo';

/**
 * Se esta sessão pode emitir token pessoal e cadastrar o e-mail da IA — as
 * duas coisas seguem a chave do servidor (`emissaoSoAdministrador`). A
 * aprovação de um pedido OAuth NÃO passa por aqui desde 26/10: ela é pelo
 * código no e-mail, numa tela sem sessão, e quem confere a chave ali é o
 * servidor, contra a conta dona do e-mail.
 *
 * Desde 26/10 a chave vem `false` por padrão: coordenador e administrador
 * conectam (decisão do dono, docs/43). `so-administrador` só aparece quando o
 * servidor foi configurado para isso (`MCP_EMISSAO_SO_ADMINISTRADOR=true`), e
 * aí o botão SOME para os outros — botão que existe para dar 403 ensina a
 * pessoa a desconfiar da tela (`Contas.tsx`).
 *
 * `conferindo` esconde a ação até a resposta chegar: um botão que aparece e
 * some meio segundo depois é pior que um que chega atrasado. Já a FALHA da
 * consulta cai em `pode` — sem a chave, quem decide é o servidor, e o 403
 * dele chega com a explicação; esconder o botão por uma falha de rede
 * trancaria o administrador fora da própria tela.
 */
export function permissaoDeEmitir(
  disponibilidade: DisponibilidadeDoMcp | undefined,
  carregando: boolean,
  ehAdministrador: boolean,
): PermissaoDeEmitir {
  if (carregando) return 'conferindo';
  if (disponibilidade?.emissaoSoAdministrador && !ehAdministrador) return 'so-administrador';
  return 'pode';
}

// ─── O consentimento do OAuth ────────────────────────────────────────────

/**
 * Os hosts de loopback do RFC 8252 §7.3, a volta de cliente nativo (Claude
 * Code, `mcp-remote`). São os únicos em que `http:` vale: a volta não sai da
 * máquina. A porta não ganha folga aqui (`destinoDaVolta`).
 */
const HOSTS_DE_LOOPBACK = new Set(['localhost', '127.0.0.1', '::1']);

function semColchetes(host: string): string {
  return host.replace(/^\[/, '').replace(/\]$/, '');
}

/**
 * O host da volta como a tela o MOSTRA — e o único texto contra o qual
 * `destinoDaVolta` confere o destino.
 *
 * O servidor manda o `redirectHost` escrito como o browser escreve o host
 * (`URL.host`: minúsculo, porta só quando não é a padrão, IPv6 comprimido
 * entre colchetes), e recusa no cadastro a volta que o browser escreveria de
 * outro jeito (api/app/routes/oauth_mcp.py::_host_de_volta). Aqui ele só passa
 * pela limpeza de texto de fora: nada invisível que inverta a leitura.
 */
export function hostDaVolta(redirectHost: string): string {
  return emUmaLinha(redirectHost);
}

/**
 * Para onde o browser segue depois da resposta — ou `null`, e a tela NÃO
 * segue.
 *
 * A tela mostrou "você volta para claude.ai", e a pessoa aprovou contando com
 * isso. Seguir para outro lugar seria aprovar uma coisa e entregar outra, e o
 * que vai junto na volta é o código que vira acesso ao SAS. Por isso:
 *   - o esquema vem de uma lista de PERMISSÃO, e não de recusa: `https:`, e
 *     `http:` só no loopback. É a mesma regra que o `/oauth/register` aplica
 *     ao cadastrar o `redirect_uri` (docs/43 §5.3), então nenhuma volta
 *     legítima fica de fora. Uma lista de recusa deixava passar o que
 *     ninguém lembrou de listar: `http://` para host de fora, que leva o
 *     código sem TLS, e `vscode:`, `intent:` e `ftp:`. E `javascript:` nunca
 *     pode passar, porque `location.assign` o EXECUTARIA aqui dentro — numa
 *     tela pública, mas que pode estar numa aba com a sessão da coordenação
 *     aberta;
 *   - o host tem de ser o TEXTO que a tela mostrou (`hostDaVolta`), letra por
 *     letra, contra o host que o browser vai usar (`URL.host`). O texto não é
 *     relido com `new URL`: relido, ele saía normalizado do mesmo jeito que o
 *     destino e "batia" mesmo quando a tela tinha mostrado outra coisa. Com
 *     https://atacante.example\.claude.ai/cb, a tela mostrava
 *     "atacante.example\.claude.ai" e o browser ia para atacante.example
 *     (revisão de segurança de 25/10). Host e porta exatos, inclusive no
 *     loopback: a porta que muda a cada vez (RFC 8252 §7.3) muda entre o
 *     cadastro e o pedido, e a tela mostra a do pedido, que é a da volta;
 *   - caminho interno do SAS passa pela mesma regra da volta do login.
 * O servidor é quem manda na volta. Esta conferência é defesa em
 * profundidade, e por isso não pode ser mais frouxa que a dele.
 */
export function destinoDaVolta(redirecionarPara: string, redirectHost: string): string | null {
  const interno = destinoInterno(redirecionarPara);
  if (interno) return interno;
  let url: URL;
  try {
    url = new URL(redirecionarPara);
  } catch {
    return null;
  }
  const loopback = HOSTS_DE_LOOPBACK.has(semColchetes(url.hostname));
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) return null;
  // `url.host` nunca é vazio em http(s): um host mostrado vazio não confere.
  return url.host === hostDaVolta(redirectHost) ? url.href : null;
}

export type FalhaDoPedido = 'encerrado' | 'recusado' | 'espera' | 'outra';

/**
 * O que uma falha do consentimento quer dizer para quem está na tela.
 *
 * `encerrado` junta 404, 409 e 410 de propósito: para a coordenadora, "não
 * existe", "expirou" e "já foi respondido" pedem a MESMA ação — voltar ao app
 * e começar de novo — e o que a tela não pode fazer em nenhum deles é
 * continuar oferecendo "Aprovar".
 *
 * `recusado` é o 400 da aprovação — código errado, vencido ou sem tentativas,
 * numa mensagem só (contrato de 26/10) — e o 400/422 de um e-mail malformado
 * no pedido de código. `espera` é o teto do servidor (429).
 *
 * Não há leitura para 403: nenhuma rota do consentimento o devolve (a tela é
 * pública e não passa por portão de sessão), e o texto que existia para ele
 * falava de uma regra de administrador que o servidor nunca mandava aqui
 * (revisão de 26/10). Cai em `outra`.
 */
export function leituraDaFalhaDoPedido(status: number | null | undefined): FalhaDoPedido {
  if (status === 404 || status === 409 || status === 410) return 'encerrado';
  if (status === 400 || status === 422) return 'recusado';
  if (status === 429) return 'espera';
  return 'outra';
}

/**
 * A frase que o SERVIDOR escreveu para a tela, ou `null` quando o que chegou
 * não é uma.
 *
 * `servicos/http.ts` põe na mensagem do `ErroApi` o `detail` da resposta e,
 * sem ele (corpo que não é JSON, resposta de proxy), um recuo como
 * `POST /oauth/pedidos/… → 400` — que não é frase para ninguém. O 422 do
 * pydantic traz `detail` em LISTA, que chega como "[object Object]". Os dois
 * ficam de fora, e a tela usa a frase dela.
 */
export function fraseDoServidor(mensagem: string | null | undefined): string | null {
  const texto = (mensagem ?? '').trim();
  if (!texto) return null;
  if (/^[A-Z]+ \/\S* → \d{3}$/u.test(texto)) return null;
  if (texto.startsWith('[object ')) return null;
  return texto;
}

/**
 * A recusa da conta DESATIVADA que ainda tem a sessão de 8 h aberta. O servidor
 * relê a conta na tabela onde nasce credencial do MCP — emitir token,
 * cadastrar, confirmar e reenviar o código do e-mail da IA — e responde 403
 * com esta frase (`auth.MENSAGEM_CONTA_DESATIVADA`; prova de ponta a ponta de
 * 27/10, docs/43 §8.1). É o MESMO texto do servidor, letra por letra: um teste
 * do backend (`test_mcp_rotas`) reprova se os dois se separarem.
 */
export const MENSAGEM_CONTA_DESATIVADA =
  'Esta conta da coordenação está desativada e não pode conectar uma IA ao SAS.';

/**
 * A frase de um 403 na tela de Conexões de IA. Emitir token tem DUAS recusas:
 * a regra do só-administrador, em que a tela troca a frase do servidor pela
 * dela (que diz a quem recorrer), e a conta desativada, que fica com a frase do
 * servidor — o "só do administrador" seria o motivo errado.
 */
export function fraseDoProibido(mensagemDoServidor: string | null | undefined, proibido: string): string {
  return fraseDoServidor(mensagemDoServidor) === MENSAGEM_CONTA_DESATIVADA ? MENSAGEM_CONTA_DESATIVADA : proibido;
}

// ─── Os e-mails da IA e o código (decisão do dono de 26/10) ──────────────
//
// O claude.ai e o ChatGPT não dizem ao SAS qual é o e-mail da conta de quem
// está conectando, e a aba que eles abrem chega sem sessão do SAS. A prova de
// quem aprova passou a ser a POSSE do e-mail: a coordenadora cadastra em
// Conexões de IA o e-mail da conta em que usa a IA, o consentimento manda um
// código para ele, e quem digita o código aprova — com o acesso da conta dona
// daquele e-mail. Token pessoal (Claude Code, Claude Desktop) continua sendo
// emitido por quem está logado.
//
// ⚠️ E o CADASTRO também prova a posse (revisão de segurança de 26/10). O
// e-mail nasce aguardando, recebe um código, e só aprova depois que quem o
// cadastrou digita esse código no card (`POST /mcp/emails-ia/{id}/confirmar`).
// Sem isso, um domínio digitado errado ("gmial.com") ou uma caixa
// compartilhada entregava o acesso da conta — com nome de aluno menor de
// idade — a quem lesse aquela caixa.
//
// ⚠️ O consentimento é PÚBLICO, e por isso nenhuma frase daqui pode variar com
// a existência do e-mail. A resposta do pedido de código é sempre a mesma
// (`avisoDoCodigoPedido`), e a falha da aprovação também, até o código certo
// (`mensagemDaFalhaDoConsentimento`): uma frase diferente para "esse e-mail
// não está cadastrado" transformaria a tela num jeito de descobrir o e-mail da
// coordenação. Depois do código certo, quem lê a frase já provou ler a caixa.

/** O teto de um endereço de e-mail (RFC 5321 §4.5.3.1.3: 254 no caminho). */
export const EMAIL_MAXIMO = 254;

/**
 * O e-mail como vai para o servidor: aparado e em minúsculas — é como o
 * servidor o guarda (contrato de 26/10), e é o texto que a tela mostra depois
 * de enviar.
 */
export function normalizarEmail(texto: string): string {
  return texto.trim().toLowerCase();
}

// Sem espaço, sem `@` a mais, sem controle nem formatação invisível.
const FORMA_DE_EMAIL = /^[^\s@\p{Cc}\p{Cf}]+@[^\s@\p{Cc}\p{Cf}]+\.[^\s@\p{Cc}\p{Cf}]+$/u;

/**
 * Se o texto tem FORMA de e-mail — `algo@dominio.tld`.
 *
 * Não é a validação, que é do servidor. Existe para o botão não mandar
 * "ana.gmail.com" e a pessoa ficar esperando um código que não tem como
 * chegar — a resposta do servidor é a mesma de um e-mail bom, e ela não
 * saberia que errou.
 */
export function emailComFormaValida(texto: string): boolean {
  const email = normalizarEmail(texto);
  return email.length > 0 && email.length <= EMAIL_MAXIMO && FORMA_DE_EMAIL.test(email);
}

/**
 * A frase da falha ao cadastrar um e-mail da IA, na tela de Conexões de IA —
 * que é da coordenação logada, e não pública.
 *
 * O 409 diz que o e-mail já está no SAS sem dizer em QUAL conta: o contrato o
 * recusa se ele existe em qualquer uma, e a pessoa precisa saber que não
 * adianta tentar de novo — mas o nome do dono do outro cadastro não é dela.
 *
 * Cada status é uma coisa só (routes/mcp_emails_ia.py): a forma recusada é
 * 422, do pydantic; o 400 é o TETO de e-mails da conta, e mandar "conferir o
 * e-mail" a quem escreveu certo era mandar corrigir o que não estava errado
 * (revisão de 26/10). No teto e no limite de códigos (429) vale a frase do
 * servidor, que diz o número e o prazo. 503 é o código de confirmação que não
 * saiu — o e-mail já está na lista, aguardando. O 403 é só a conta desativada
 * (`MENSAGEM_CONTA_DESATIVADA`): o cadastro não passa pelo portão do
 * administrador.
 */
export function mensagemDaFalhaDoEmailDaIa(
  status: number | null | undefined,
  mensagemDoServidor?: string,
): string {
  if (status === 403) return MENSAGEM_CONTA_DESATIVADA;
  if (status === 409) {
    return 'Esse e-mail já está cadastrado no SAS, nesta conta ou em outra. Se ele é seu e está em outra conta, fale com o administrador do SAS.';
  }
  if (status === 422) return 'Confira o e-mail: o SAS não o aceitou como endereço.';
  if (status === 400) {
    return fraseDoServidor(mensagemDoServidor) ?? 'Esta conta já tem o máximo de e-mails de IA. Remova um antes de cadastrar outro.';
  }
  if (status === 429) {
    return fraseDoServidor(mensagemDoServidor) ?? 'Códigos de confirmação demais em pouco tempo. Espere e tente de novo.';
  }
  if (status === 503) {
    return 'O e-mail entrou na lista, aguardando confirmação, mas o código não saiu agora. Use “Enviar outro código”, na linha dele, daqui a pouco.';
  }
  return 'Não consegui cadastrar o e-mail. Tente de novo em instantes.';
}

/** Se o e-mail já aprova conexão: só depois de confirmado com o código que chegou a ele. */
export function emailDaIaConfirmado(item: { confirmadoEm: string | null }): boolean {
  return Boolean(item.confirmadoEm);
}

/**
 * O aviso do card, ANTES do campo: quem lê a caixa conecta com o acesso da
 * conta. É a frase que faltava (revisão de segurança de 26/10) — sem ela,
 * cadastrar a caixa da secretaria, ou a de casa que a família também lê,
 * parecia inofensivo.
 */
export function avisoDaCaixaDoEmail(): string {
  return 'Quem lê a caixa de um destes e-mails conecta uma IA aos dados do SAS com o acesso da sua conta — o nome dos alunos inclusive. Cadastre só uma caixa que só você lê: o SAS manda um código para ela, e o e-mail só vale depois que você o digita aqui.';
}

/** O que a linha do e-mail que aguarda diz, logo depois do cadastro ou de pedir outro código. */
export function avisoDoCodigoDeConfirmacao(email: string): string {
  return `Mandamos um código de ${DIGITOS_DO_CODIGO} dígitos para ${emUmaLinha(normalizarEmail(email), EMAIL_MAXIMO)}. Até você digitá-lo aqui, este e-mail não aprova conexão nenhuma.`;
}

/**
 * A falha de confirmar o e-mail com o código. O 400 é uma frase só, como no
 * consentimento: código errado, vencido, trocado por outro e sem tentativas
 * pedem a mesma ação. O 409 é o e-mail confirmado por OUTRA conta enquanto
 * este aguardava — sem dizer qual. O 403 é a conta desativada.
 */
export function mensagemDaFalhaDaConfirmacao(status: number | null | undefined): string {
  if (status === 403) return MENSAGEM_CONTA_DESATIVADA;
  if (status === 400 || status === 422) {
    return 'Código errado, vencido ou sem tentativas. Confira o último código que chegou, ou peça outro.';
  }
  if (status === 409) {
    return 'Este e-mail acabou de ser confirmado em outra conta do SAS. Se a caixa é sua, fale com o administrador do SAS.';
  }
  if (status === 404) return 'Este e-mail não está mais na sua lista.';
  return 'Não consegui confirmar agora. Tente de novo em instantes.';
}

/**
 * A falha de pedir outro código de confirmação. No teto, a frase (e o prazo) do
 * servidor; o 403 é a conta desativada.
 */
export function mensagemDaFalhaDoReenvio(status: number | null | undefined, mensagemDoServidor?: string): string {
  if (status === 403) return MENSAGEM_CONTA_DESATIVADA;
  if (status === 429) {
    return fraseDoServidor(mensagemDoServidor) ?? 'Códigos demais em pouco tempo. Espere e peça de novo mais tarde.';
  }
  if (status === 409) return 'Este e-mail já está confirmado: não há código a pedir.';
  if (status === 404) return 'Este e-mail não está mais na sua lista.';
  if (status === 503) return 'O código não saiu agora. Tente de novo daqui a pouco.';
  return 'Não consegui pedir outro código. Tente de novo em instantes.';
}

/** Os e-mails na ordem em que foram cadastrados — a lista não pula ao cadastrar o seguinte. */
export function ordenarEmailsDaIa<T extends { criadoEm: string }>(emails: readonly T[]): T[] {
  const ms = (iso: string) => instante(iso) ?? 0;
  return [...emails].sort((a, b) => ms(a.criadoEm) - ms(b.criadoEm));
}

/**
 * O texto do `confirm` de remover um e-mail.
 *
 * Diz o efeito e o que NÃO acontece: tirar o e-mail impede aprovações novas
 * por ele, mas não desconecta o que já foi aprovado — quem quer cortar uma
 * conexão tem de revogá-la, e precisa saber disso antes de achar que já cortou.
 */
export function perguntaDeRemocaoDoEmail(email: string): string {
  return `Remover “${emUmaLinha(email, EMAIL_MAXIMO)}”?\n\nNenhum código de aprovação vai mais para este e-mail, e ele deixa de poder aprovar conexões novas do claude.ai ou do ChatGPT.\n\nRemover não desconecta o que já foi aprovado: para cortar uma conexão, revogue-a na lista de conexões.`;
}

/** O código que o consentimento manda para o e-mail: seis dígitos (contrato de 26/10). */
export const DIGITOS_DO_CODIGO = 6;

/**
 * O código como a pessoa o digitou ou colou, só com os dígitos e no tamanho
 * do código.
 *
 * Colar do e-mail traz espaço, hífen ou ponto ("123 456", "123-456"), e o
 * campo não pode recusar isso: quem cola espera que funcione. O que passa do
 * sexto dígito sai — o campo não cresce além do código.
 */
export function limparCodigo(texto: string): string {
  return texto.replace(/\D/gu, '').slice(0, DIGITOS_DO_CODIGO);
}

export function codigoCompleto(codigo: string): boolean {
  return codigo.length === DIGITOS_DO_CODIGO && /^\d+$/u.test(codigo);
}

/**
 * Quanto a tela espera antes de oferecer "Enviar outro código".
 *
 * O teto de verdade é do servidor (por endereço, por pedido e por e-mail). Este
 * é o da tela: sem ele, o segundo toque de quem acha que o primeiro não foi
 * manda dois e-mails, e o primeiro código chega já sem valer.
 */
export const ESPERA_PARA_OUTRO_CODIGO_MS = 30_000;

/**
 * O que a tela diz depois de pedir o código — A MESMA frase para e-mail
 * cadastrado ou não, porque a resposta do servidor também é a mesma.
 *
 * Repete o e-mail digitado, e isso não conta nada a ninguém: é o texto que a
 * própria pessoa escreveu, e é como ela pega um erro de digitação antes de
 * esperar à toa por um código.
 *
 * "E confirmado": o e-mail que ainda aguarda a confirmação no card não recebe
 * o código de aprovar, e quem o cadastrou e não confirmou precisa saber onde
 * está o passo que falta. A frase continua a mesma para qualquer e-mail.
 */
export function avisoDoCodigoPedido(email: string): string {
  return `Se ${emUmaLinha(normalizarEmail(email), EMAIL_MAXIMO)} estiver cadastrado e confirmado no SAS, o código chegou lá. Pode levar um minuto; confira também o spam.`;
}

export type AcaoDoConsentimento = 'codigo' | 'aprovar' | 'recusar';

/**
 * A frase da falha de cada ação do consentimento, quando o pedido NÃO foi
 * encerrado (esse caso a tela trata à parte: tira os botões e explica).
 *
 * ⚠️ O 400 da aprovação ANTES do código certo é UMA frase do servidor para
 * código errado, vencido, já sem tentativas e para e-mail que não está
 * cadastrado (`_CODIGO_RECUSADO`): ele não distingue, e a tela também não pode
 * (ver o topo desta seção). Só DEPOIS do código certo o servidor diz o que
 * houve — o e-mail foi removido, a conta não pode conectar
 * (routes/oauth_mcp.py::_dono_do_codigo) —, e aí a tela tem de dizer também:
 * o código já foi gasto, um novo não chegaria, e a frase genérica ("peça
 * outro código") deixava a pessoa num laço (revisão de 26/10). Nada nessas
 * frases depende de o e-mail existir para quem não tem o código.
 *
 * Os 429 também levam a frase do servidor, que tem o prazo certo: o teto de
 * um dia por e-mail diz "amanhã", e o do pedido manda recomeçar pelo app —
 * "espere alguns minutos" estava errado nos dois. Nenhuma das três varia com o
 * e-mail (os tetos contam qualquer um).
 *
 * `mensagem` é a do `ErroApi`: com status 0, a de `servicos/http.ts` ("sem
 * resposta do servidor", a única que ajuda ali); com 400 e 429, a frase que o
 * servidor escreveu para esta tela (`RecusaDoConsentimento`). Quando ela não
 * veio (`fraseDoServidor`), e em qualquer outra falha, a frase é a da tela —
 * o texto cru seria `POST /oauth/… → 500`.
 */
export function mensagemDaFalhaDoConsentimento(
  acao: AcaoDoConsentimento,
  status: number | null | undefined,
  mensagem?: string,
): string {
  if (status === 0 && mensagem) return mensagem;
  const leitura = leituraDaFalhaDoPedido(status);
  if (status === 400 || status === 429) {
    const doServidor = fraseDoServidor(mensagem);
    if (doServidor) return doServidor;
  }
  if (acao === 'codigo') {
    if (leitura === 'espera') return 'Pedidos de código demais em pouco tempo. Espere alguns minutos e peça de novo.';
    if (leitura === 'recusado') return 'Confira o e-mail: o SAS não o leu como um endereço completo.';
    return 'Não consegui pedir o código agora. Tente de novo em instantes.';
  }
  if (acao === 'aprovar') {
    if (leitura === 'recusado') {
      return 'Não deu para aprovar com esse código. Confira se ele é o mais recente que chegou e se o e-mail é o mesmo para o qual você o pediu — ou peça outro código.';
    }
    if (leitura === 'espera') return 'Tentativas demais em pouco tempo. Espere alguns minutos e tente de novo.';
    return 'Não consegui enviar a aprovação. Tente de novo em instantes.';
  }
  if (leitura === 'espera') return 'Respostas demais em pouco tempo. Espere alguns minutos e tente de novo.';
  return 'Não consegui enviar a recusa. Tente de novo em instantes.';
}

// ─── Como conectar: o passo a passo de cada IA ───────────────────────────
//
// A tela tinha as peças — o endereço, o card dos e-mails, "Nova conexão" —,
// mas não a ORDEM em que elas se usam, e o caminho do claude.ai e do ChatGPT
// passa por uma aba de fora (`/conectar-ia`) que a pessoa só vê depois de
// clicar em "Conectar" lá. Por isso o passo a passo é de UMA IA por vez: a
// pessoa escolhe a dela e lê só o que vai fazer, na ordem.
//
// O endereço vem do servidor (`/mcp/disponibilidade`), nunca escrito aqui: a
// mesma tela serve o dev, a stack de teste e a produção.

/** As IAs que o passo a passo cobre. */
export type IaParaConectar = 'claude' | 'claude-code' | 'chatgpt';

/** A ordem dos botões: o caminho mais usado primeiro. */
export const IAS_PARA_CONECTAR: ReadonlyArray<{ valor: IaParaConectar; rotulo: string }> = [
  { valor: 'claude', rotulo: 'claude.ai ou Claude Desktop' },
  { valor: 'claude-code', rotulo: 'Claude Code' },
  { valor: 'chatgpt', rotulo: 'ChatGPT' },
];

/**
 * Um passo: a AÇÃO, curta, que a tela põe em destaque, e o detalhe de onde
 * clicar. Os opcionais pedem à tela uma peça a mais no passo.
 */
export interface PassoDeConexao {
  acao: string;
  detalhe: string;
  /** O que a pessoa cola do outro lado — a tela põe ao lado um "Copiar". */
  copiar?: { rotulo: string; texto: string };
  /** Um comando de terminal, para ler e rodar. */
  comando?: string;
  /** O passo do e-mail confirmado: a tela diz se já está feito. */
  confereEmail?: boolean;
  /** O passo do token: a tela oferece o botão "Nova conexão" ali mesmo. */
  criaConexao?: boolean;
}

/**
 * Os passos de uma IA, na ordem em que se fazem.
 *
 * Os nomes dos menus vão em português e, onde a tradução varia, também em
 * inglês: o claude.ai e o ChatGPT mostram a língua da conta, não a do SAS.
 */
export function passosParaConectar(ia: IaParaConectar, url: string): PassoDeConexao[] {
  const copiarEndereco = { rotulo: 'Copiar o endereço', texto: url };
  const confirmarEmail: PassoDeConexao = {
    acao: 'Confirme o e-mail da sua conta de IA',
    detalhe:
      'No quadro "E-mails da sua IA", mais abaixo nesta tela. É para esse e-mail que o SAS manda o código que aprova a conexão.',
    confereEmail: true,
  };
  const aprovar: PassoDeConexao = {
    acao: 'Digite o e-mail, depois o código, e aprove',
    detalhe: `Abre uma aba do SAS. Digite o e-mail confirmado e peça o código: ele tem ${DIGITOS_DO_CODIGO} dígitos, chega em segundos e vale 10 minutos (na primeira vez, olhe também o spam). Digite o código e clique em "Aprovar".`,
  };

  if (ia === 'claude-code') {
    return [
      {
        acao: 'Crie uma conexão',
        detalhe:
          'Clique em "Nova conexão" e dê um nome que você reconheça depois — por exemplo, "Claude Code do notebook".',
        criaConexao: true,
      },
      {
        acao: 'Copie o comando pronto',
        detalhe:
          'O token aparece uma vez só, já dentro de um comando. Clique em "Copiar o comando" antes de fechar o quadro.',
      },
      {
        acao: 'Cole no terminal e rode',
        detalhe: 'Para conferir, rode o comando abaixo: o SAS tem de aparecer como conectado.',
        comando: 'claude mcp list',
      },
      {
        acao: 'Apague a linha do histórico',
        detalhe:
          'O comando leva o token, e o terminal guarda o que você roda. A conexão vale 90 dias; para cortar antes, revogue na lista desta tela.',
      },
    ];
  }

  if (ia === 'chatgpt') {
    return [
      confirmarEmail,
      {
        acao: 'Ligue o modo desenvolvedor',
        detalhe:
          'No ChatGPT, abra Configurações → Apps e conectores → Configurações avançadas e ligue o "Modo desenvolvedor" ("Developer mode").',
      },
      {
        acao: 'Crie o conector do SAS',
        detalhe:
          'Ainda em Apps e conectores, crie um conector com o nome SAS, autenticação OAuth e este endereço:',
        copiar: copiarEndereco,
      },
      aprovar,
      {
        acao: 'Use',
        detalhe: 'Numa conversa, escolha o conector SAS e faça a sua pergunta.',
      },
    ];
  }

  return [
    confirmarEmail,
    {
      acao: 'Adicione o SAS como conector',
      detalhe:
        'No claude.ai, abra Configurações → Conectores → "Adicionar conector personalizado" ("Add custom connector"). Dê o nome SAS e cole este endereço:',
      copiar: copiarEndereco,
    },
    {
      acao: 'Clique em "Conectar"',
      detalhe: 'Fica ao lado do conector que você acabou de adicionar.',
    },
    aprovar,
    {
      acao: 'Use',
      detalhe:
        'Numa conversa, ligue o SAS no menu de ferramentas e pergunte, por exemplo: "Quais alunos estão em risco no ciclo mais recente?". O Claude Desktop usa a mesma conta: o conector aparece lá também.',
    },
  ];
}

/**
 * O cuidado de antes do primeiro uso, de cada IA: desligar o uso das
 * conversas para treinar o modelo. É a decisão do dono de 27/10 (docs/43
 * §0.2): a coordenação conecta com a conta PESSOAL, e o que a IA lê do SAS —
 * nome de aluno inclusive — fica sob as regras dessa conta.
 */
export function cuidadoDePrivacidade(ia: IaParaConectar): string {
  if (ia === 'chatgpt') {
    return 'Antes de usar com dados de alunos: no ChatGPT, em Configurações → Controles de dados, desligue "Melhorar o modelo para todos" ("Improve the model for everyone").';
  }
  if (ia === 'claude-code') {
    return 'Antes de usar com dados de alunos: se o Claude Code entra com a sua conta do Claude, vale a opção de privacidade dela — no claude.ai, em Configurações → Privacidade, desligue "Ajudar a melhorar o Claude" ("Help improve Claude").';
  }
  return 'Antes de usar com dados de alunos: no claude.ai, em Configurações → Privacidade, desligue "Ajudar a melhorar o Claude" ("Help improve Claude").';
}

/** O que o passo do e-mail diz sobre ele mesmo, a partir da lista do card. */
export function estadoDoEmailConfirmado(confirmados: number | null): string | null {
  if (confirmados === null) return null;
  if (confirmados === 0) return 'Ainda falta: nenhum e-mail confirmado nesta conta.';
  return confirmados === 1
    ? 'Feito: esta conta tem 1 e-mail confirmado.'
    : `Feito: esta conta tem ${confirmados} e-mails confirmados.`;
}
