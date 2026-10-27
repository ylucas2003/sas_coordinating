import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent, ReactNode, RefObject } from 'react';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import {
  DIGITOS_DO_CODIGO, EMAIL_MAXIMO, ESPERA_PARA_OUTRO_CODIGO_MS, NOME_MAXIMO, avisoDaCaixaDoEmail,
  avisoDoCodigoDeConfirmacao, cabecalhoDeAutorizacao, codigoCompleto, comandoDoClaudeCode, dataCurta,
  emUmaLinha, emailComFormaValida, emailDaIaConfirmado, limparCodigo, mensagemDaFalhaDaConfirmacao,
  mensagemDaFalhaDoEmailDaIa, mensagemDaFalhaDoReenvio, nomeDaConexaoValido, normalizarEmail,
  ordenarConexoes, ordenarEmailsDaIa, origemLegivel, perguntaDeRemocaoDoEmail, perguntaDeRevogacao,
  permissaoDeEmitir, situacaoDaConexao, situacaoLegivel, ultimoUsoLegivel,
} from '../../dominio/conexoesDeIa';
import type { PermissaoDeEmitir } from '../../dominio/conexoesDeIa';
import { useConexoesDeIa, useDisponibilidadeDoMcp, useEmailsDaIa } from '../../hooks/consultas';
import {
  useCadastrarEmailDaIa, useConfirmarEmailDaIa, useCriarConexaoDeIa, useReenviarCodigoDoEmailDaIa,
  useRemoverEmailDaIa, useRevogarConexaoDeIa,
} from '../../hooks/mutacoes';
import { ErroApi } from '../../servicos/http';
import * as sessao from '../../servicos/sessao';
import type { ConexaoDeIa, DisponibilidadeDoMcp, EmailDaIa } from '../../tipos/dominio';
import '../../../styles/conexoes-de-ia.css';

// CONEXÕES DE IA — os tokens com que a coordenação liga a própria IA ao SAS
// (docs/43 §5.3, Fase 2), as conexões que um conector abriu pelo OAuth
// (Fase 3), e os e-mails da IA por onde essas conexões são aprovadas. O
// servidor é o MCP: processo próprio, PostgREST próprio, papel de banco que só
// lê (docs/43 §5.2).
//
// A tela tem quatro trabalhos, e cada um tem desenho próprio:
//
//   1 · Dizer o que conectar SIGNIFICA, antes do botão. Dado de aluno — o nome
//       inclusive, desde a decisão do dono de 26/10 — sai do SAS para o
//       provedor da IA, e a maioria dos alunos é menor de idade: é a mesma
//       regra da armadilha 7 do CLAUDE.md, aplicada ao servidor (docs/43
//       §5.4). A frase está em cima da tela, não num "saiba mais".
//   2 · Mostrar o token UMA vez. Ele é opaco e o servidor guarda só o sha256:
//       depois de fechado o painel, ninguém lê de volta. Por isso o painel não
//       é diálogo (o `Dialogo` fecha no clique do fundo, que é o gesto
//       distraído que perde o token — o mesmo motivo da `SenhaRevelada` da
//       cantina), e por isso o token NUNCA vai para cache nem para storage:
//       ele mora no estado desta tela enquanto o painel está aberto, e a
//       mutação que o trouxe é zerada na hora (`useCriarConexaoDeIa`).
//   3 · Os E-MAILS DA IA (decisão do dono de 26/10). O claude.ai e o ChatGPT
//       não dizem ao SAS quem está conectando: o consentimento manda um código
//       para o e-mail cadastrado aqui, e quem o digita aprova com o acesso
//       desta conta. Pode ser outro que não o do SAS, e pode haver mais de um.
//       E o e-mail só vale CONFIRMADO, com o código que chega a ele no
//       cadastro (revisão de segurança de 26/10): sem isso, o domínio digitado
//       errado entregava o acesso da conta a quem lesse aquela caixa.
//   4 · Revogar com o efeito escrito. Nada é apagado: a linha revogada é o
//       que responde, depois, quem tinha acesso e até quando.
//
// Desde 26/10 coordenador E administrador conectam (decisão do dono:
// `emissaoSoAdministrador` com padrão `false`). Se o servidor for configurado
// para só o administrador emitir, para os outros o botão SOME e a tela diz por
// quê — botão que existe para dar 403 ensina a pessoa a desconfiar da tela
// (`Contas.tsx`). A guarda de verdade é o servidor.

/** O que o painel mostra uma vez. Mora só no estado desta tela. */
interface TokenRevelado {
  nome: string;
  token: string;
}

/**
 * A frase da falha. O 403 ganha texto próprio porque o do servidor diz QUE foi
 * recusado, e a pessoa precisa saber POR QUÊ e a quem recorrer.
 */
function mensagemDaFalha(erro: unknown, { padrao, proibido }: { padrao: string; proibido: string }): string {
  if (erro instanceof ErroApi && erro.status === 403) return proibido;
  return (erro as Error)?.message || padrao;
}

function statusDe(erro: unknown): number | null {
  return erro instanceof ErroApi ? erro.status : null;
}

const SEGUNDOS_PARA_OUTRO_CODIGO = Math.round(ESPERA_PARA_OUTRO_CODIGO_MS / 1000);

export function ConexoesDeIa() {
  // Lido uma vez: o papel vem do login e não muda no meio da sessão.
  const souAdministrador = sessao.ehAdministrador();
  const disponibilidade = useDisponibilidadeDoMcp();
  const conexoes = useConexoesDeIa();
  const [criando, setCriando] = useState(false);
  const [revelado, setRevelado] = useState<TokenRevelado | null>(null);
  const botaoNovaConexao = useRef<HTMLButtonElement>(null);
  const tituloDaLista = useRef<HTMLHeadingElement>(null);
  // Fechar o painel do token e cancelar o formulário tiram da tela o elemento
  // que tinha o foco, e o navegador o devolve ao `<body>`. Quem usa teclado ou
  // leitor de tela voltaria ao topo do documento logo depois do passo mais
  // delicado da tela. O contador pede o foco para DEPOIS do desenho, quando
  // "Nova conexão" já voltou a existir.
  const [pedidosDeFoco, setPedidosDeFoco] = useState(0);

  useEffect(() => {
    if (!pedidosDeFoco) return;
    (botaoNovaConexao.current ?? tituloDaLista.current)?.focus();
  }, [pedidosDeFoco]);

  const permissao = permissaoDeEmitir(
    disponibilidade.data, disponibilidade.isLoading, souAdministrador,
  );
  // Com o painel do token aberto, "Nova conexão" some: criar a segunda antes de
  // guardar a primeira é o caminho mais curto para perder as duas.
  const ofereceCriar = permissao === 'pode' && !criando && !revelado;

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="Conexões de IA"
        para="/administracao"
        destino="Administração"
        acoes={ofereceCriar ? (
          <button
            ref={botaoNovaConexao}
            type="button"
            className="btn btn-primary"
            onClick={() => setCriando(true)}
          >
            Nova conexão
          </button>
        ) : null}
      />

      <Explicacao />

      <EstadoDoServidor
        disponibilidade={disponibilidade.data}
        falhou={disponibilidade.isError}
      />

      {/* Só aparece se o servidor foi configurado assim: o padrão desde 26/10
          é coordenador e administrador conectarem. */}
      {permissao === 'so-administrador' && (
        <p className="ia-aviso">
          Neste ambiente, só o administrador do SAS cria conexões — é uma configuração do
          servidor. Você continua vendo e revogando as conexões em seu nome.
        </p>
      )}

      {criando && (
        <NovaConexao
          onCancelar={() => {
            setCriando(false);
            setPedidosDeFoco((n) => n + 1);
          }}
          onCriada={(token) => {
            setCriando(false);
            setRevelado(token);
          }}
        />
      )}

      {revelado && (
        <PainelDoToken
          revelado={revelado}
          disponibilidade={disponibilidade.data}
          onFechar={() => {
            setRevelado(null);
            setPedidosDeFoco((n) => n + 1);
          }}
        />
      )}

      <EmailsDaIa permissao={permissao} />

      <ListaDeConexoes
        conexoes={conexoes.data}
        carregando={conexoes.isPending}
        falha={conexoes.isError ? conexoes.error : null}
        souAdministrador={souAdministrador}
        permissao={permissao}
        refDoTitulo={tituloDaLista}
      />
    </div>
  );
}

/**
 * O que conectar uma IA significa, em três frases, ANTES do botão.
 *
 * ⚠️ É texto de compromisso, não de marketing: cada frase descreve uma
 * garantia do servidor (docs/43 §5.2 e §5.3). Se uma delas deixar de ser
 * verdade lá — o MCP ganhar uma tool que escreve, por exemplo —, esta lista
 * tem de mudar no mesmo commit.
 *
 * A frase da "matrícula no lugar do nome" SAIU em 26/10: o dono decidiu que o
 * MCP devolve o nome real do aluno, e a pseudonimização virou opção de
 * configuração (`MCP_MOSTRAR_NOME_DO_ALUNO`). A tela não sabe qual das duas o
 * servidor usa (`/mcp/disponibilidade` não diz), então avisa do padrão: com a
 * pseudonimização ligada ela avisa mais do que acontece, que é o lado certo de
 * errar.
 */
function Explicacao() {
  const idTitulo = useId();
  return (
    <section className="ia-explicacao" aria-labelledby={idTitulo}>
      <h2 id={idTitulo} className="ia-explicacao__titulo">O que conectar uma IA significa</h2>
      <ul className="ia-explicacao__lista">
        <li>
          <b>O que ela consultar sai do SAS, inclusive o nome dos alunos</b> — a maioria, menor de
          idade. Vai para o provedor da IA (a empresa do Claude, do ChatGPT ou de outra) e fica sob
          as regras da conta em que você a usa.
        </li>
        <li>
          <b>Só leitura.</b> A IA consulta os dados da coordenação, com o acesso de quem a conectou,
          e não altera nada: nem nota, nem conta, nem régua.
        </li>
        {/* "Com o token revogado": é o que o servidor garante para as duas
            origens. Na conexão OAuth, revogar corta também a renovação
            (`REVOGACAO_OAUTH_CORTA_RENOVACAO`), e o `confirm` de revogar diz
            isso (`perguntaDeRevogacao`). */}
        <li>
          <b>Revogar corta na hora.</b> A primeira consulta com o token revogado já é recusada.
        </li>
      </ul>
    </section>
  );
}

/**
 * O servidor está ligado? E onde ele mora?
 *
 * O endereço fica à vista na tela, e não só no painel do token: ele não é
 * segredo, e quem configura a mesma IA num segundo aparelho precisa dele
 * outra vez — o token é que não volta.
 */
function EstadoDoServidor({
  disponibilidade, falhou,
}: {
  disponibilidade: DisponibilidadeDoMcp | undefined;
  falhou: boolean;
}) {
  if (falhou) {
    return (
      <p className="ia-aviso">
        Não consegui saber agora se o servidor MCP está ligado. A lista abaixo vale; o endereço
        para configurar a IA aparece aqui quando a consulta voltar.
      </p>
    );
  }
  if (!disponibilidade) return null;
  if (!disponibilidade.habilitado) {
    return (
      <p className="ia-aviso">
        <b>O servidor MCP está desligado neste ambiente.</b> As conexões ficam guardadas, mas
        nenhuma IA consegue ler o SAS por elas enquanto ele não for ligado.
      </p>
    );
  }
  if (!disponibilidade.urlDoServidor) {
    return (
      <p className="ia-aviso">
        O servidor MCP está ligado, mas o endereço público dele não foi configurado. Fale com
        quem administra o servidor do SAS.
      </p>
    );
  }
  return (
    <p className="ia-endereco">
      Endereço do servidor: <code>{disponibilidade.urlDoServidor}</code>
    </p>
  );
}

/**
 * Pede só o nome — é o que a pessoa vai usar para reconhecer a conexão na
 * lista, meses depois, quando quiser revogar a do notebook que foi trocado.
 *
 * No fluxo, e não num `Dialogo`: o token aparece no MESMO lugar logo em
 * seguida, e o formulário curto não precisa de modal para ser lido.
 */
function NovaConexao({
  onCancelar, onCriada,
}: {
  onCancelar: () => void;
  onCriada: (token: TokenRevelado) => void;
}) {
  const criar = useCriarConexaoDeIa();
  const [nome, setNome] = useState('');
  const campo = useRef<HTMLInputElement>(null);
  // ⚠️ A trava contra o segundo envio é SÍNCRONA. `criar.isPending` e o
  // `disabled` do botão vêm do último desenho, e o react-query só avisa a tela
  // um macrotask depois do `mutate` (o `notifyManager` agenda com
  // `setTimeout(0)`). Dois Enter seguidos, ou um clique programático, cabem
  // nesse intervalo. Cada envio é um token: o painel mostraria o segundo, e o
  // primeiro ficaria ativo e órfão, sem ninguém que o tenha visto.
  const enviando = useRef(false);
  const idTitulo = useId();
  const idCampo = useId();
  const idAjuda = useId();

  // O formulário nasce do clique em "Nova conexão": levar o foco ao campo é
  // responder a esse clique, não sequestrar a página.
  useEffect(() => {
    campo.current?.focus();
  }, []);

  const valido = nomeDaConexaoValido(nome);

  async function enviar(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    if (!valido || criar.isPending || enviando.current) return;
    enviando.current = true;
    try {
      const resposta = await criar.mutateAsync({ nome: nome.trim() });
      const token = { nome: resposta.nome, token: resposta.token };
      // ⚠️ Antes de qualquer outra coisa: o token sai do react-query aqui
      // (`gcTime: 0` + `reset()`) e passa a morar só no painel.
      criar.reset();
      onCriada(token);
    } catch {
      // A falha fica em `criar.error` e aparece embaixo do botão.
    } finally {
      enviando.current = false;
    }
  }

  return (
    <form className="ia-nova" onSubmit={enviar} aria-labelledby={idTitulo} noValidate>
      <h2 id={idTitulo} className="ia-nova__titulo">Nova conexão</h2>
      <label className="ia-nova__rotulo" htmlFor={idCampo}>Nome da conexão</label>
      <p id={idAjuda} className="ia-nova__ajuda">
        Para você reconhecer depois, na lista: onde a IA vai morar.
      </p>
      <input
        id={idCampo}
        ref={campo}
        className="ia-nova__campo"
        value={nome}
        maxLength={NOME_MAXIMO}
        autoComplete="off"
        placeholder="Ex.: Claude Code do notebook"
        aria-describedby={idAjuda}
        onChange={(e) => setNome(e.target.value)}
      />
      <div className="ia-nova__acoes">
        <button type="submit" className="btn btn-primary" disabled={!valido || criar.isPending}>
          {criar.isPending ? 'Criando…' : 'Criar e mostrar o token'}
        </button>
        <button type="button" className="btn btn--ghost" onClick={onCancelar} disabled={criar.isPending}>
          Cancelar
        </button>
      </div>
      {criar.isError && (
        <p className="ia-erro" role="alert">
          {mensagemDaFalha(criar.error, {
            padrao: 'Não consegui criar a conexão. Tente de novo.',
            proibido: 'O servidor recusou: neste ambiente, criar conexão de IA é só do administrador do SAS.',
          })}
        </p>
      )}
    </form>
  );
}

/**
 * Copiar, com a falha À VISTA.
 *
 * Contexto sem área de transferência (http simples, permissão negada) é o pior
 * caso desta tela se falhar calado: a pessoa acha que copiou, fecha o painel e
 * o token se perde (o mesmo raciocínio da `SenhaRevelada` da cantina).
 */
function BotaoDeCopiar({
  texto, rotulo, principal = false,
}: {
  texto: string;
  rotulo: string;
  principal?: boolean;
}) {
  const [copia, setCopia] = useState<'nao' | 'feita' | 'falhou'>('nao');

  async function copiar() {
    try {
      await navigator.clipboard.writeText(texto);
      setCopia('feita');
    } catch {
      setCopia('falhou');
    }
  }

  return (
    <>
      <button
        type="button"
        className={principal ? 'btn btn-primary' : 'btn btn--ghost'}
        onClick={copiar}
      >
        {copia === 'feita' ? 'Copiado' : rotulo}
      </button>
      {/* A troca do rótulo do botão não é anunciada sozinha. */}
      <span className="ia-so-leitor" role="status">
        {copia === 'feita' ? 'Copiado para a área de transferência.' : ''}
      </span>
      {copia === 'falhou' && (
        <p className="ia-erro" role="alert">
          Não consegui copiar por aqui. Selecione o texto acima e copie à mão antes de fechar.
        </p>
      )}
    </>
  );
}

/**
 * O token, a única vez em que ele existe fora do servidor.
 *
 * A ordem do painel é a ordem do trabalho: o token, copiar, como configurar,
 * e só no FIM o "Já guardei — fechar" — que é uma afirmação de quem clica, e
 * não um "OK". Fechar antes de ler o passo a passo deixaria a pessoa com o
 * token na mão e sem saber onde pô-lo.
 */
function PainelDoToken({
  revelado, disponibilidade, onFechar,
}: {
  revelado: TokenRevelado;
  disponibilidade: DisponibilidadeDoMcp | undefined;
  onFechar: () => void;
}) {
  const painel = useRef<HTMLElement>(null);
  const idOlho = useId();
  const idTitulo = useId();

  // O painel nasce onde estava o formulário, mas a tela pode ter rolado; e o
  // foco vai junto, para o leitor de tela anunciar que o token chegou.
  useEffect(() => {
    const no = painel.current;
    if (!no) return;
    no.scrollIntoView({ block: 'center', behavior: 'smooth' });
    no.focus({ preventScroll: true });
  }, []);

  const url = disponibilidade?.urlDoServidor ?? null;
  const comando = url ? comandoDoClaudeCode(url, revelado.token) : null;

  return (
    <section
      className="ia-token"
      ref={painel}
      tabIndex={-1}
      aria-labelledby={`${idOlho} ${idTitulo}`}
    >
      <span id={idOlho} className="ia-token__olho">O token aparece uma vez</span>
      <h2 id={idTitulo} className="ia-token__titulo">{revelado.nome}</h2>
      <p className="ia-token__valor"><code>{revelado.token}</code></p>
      <div className="ia-token__acoes">
        <BotaoDeCopiar texto={revelado.token} rotulo="Copiar o token" principal />
      </div>

      <h3 className="ia-token__subtitulo">Como configurar a IA</h3>
      {url && comando ? (
        <>
          <dl className="ia-config">
            <dt>Endereço do servidor</dt>
            <dd><code>{url}</code></dd>
            <dt>Cabeçalho de cada chamada</dt>
            <dd><code>{cabecalhoDeAutorizacao(revelado.token)}</code></dd>
          </dl>
          <p className="ia-token__nota">
            No Claude Code, um comando só configura as duas coisas. Em outra IA, use o endereço e o
            cabeçalho acima — o token vai depois de <code>Bearer</code>.
          </p>
          <pre className="ia-comando"><code>{comando}</code></pre>
          <div className="ia-token__acoes">
            <BotaoDeCopiar texto={comando} rotulo="Copiar o comando" />
          </div>
          {/* O comando é o atalho, e o preço dele vai escrito aqui. O shell
              grava no histórico o que roda, e esse arquivo costuma ir para
              backup e sincronização: seria uma cópia a mais, e duradoura, de
              uma credencial que lê dado de menor e vale 90 dias por padrão
              (`MCP_VALIDADE_DO_TOKEN_DIAS`). */}
          <p className="ia-token__nota">
            O comando leva o token, e o terminal guarda no histórico o que você roda
            (<code>~/.zsh_history</code>, <code>~/.bash_history</code>). Depois de configurar, apague
            essa linha do histórico.
          </p>
        </>
      ) : (
        <p className="ia-aviso">
          {disponibilidade?.habilitado === false
            ? 'O servidor MCP está desligado neste ambiente, e por isso ainda não há endereço para configurar. Guarde o token mesmo assim: a conexão já existe, e o endereço aparece no topo desta tela quando o servidor for ligado.'
            : 'Não há endereço do servidor para mostrar agora. Guarde o token mesmo assim: o endereço aparece no topo desta tela assim que estiver disponível. A IA manda o token no cabeçalho Authorization, depois de "Bearer".'}
        </p>
      )}

      <p className="ia-token__nota">
        O SAS guarda só uma impressão de mão única do token: depois de fechar, ninguém lê este valor
        de volta — nem o sistema. Se perder, revogue a conexão e crie outra.
      </p>
      <div className="ia-token__acoes">
        <button type="button" className="btn btn--ghost" onClick={onFechar}>
          Já guardei — fechar
        </button>
      </div>
    </section>
  );
}

/**
 * Os e-mails da IA — por onde a conexão do claude.ai ou do ChatGPT é aprovada.
 *
 * Decisão do dono de 26/10: esses apps não dizem ao SAS qual é o e-mail da
 * conta de quem está conectando, e a aba do consentimento chega sem login. A
 * prova passou a ser a POSSE do e-mail: o consentimento (`/conectar-ia`) manda
 * um código de seis dígitos para um destes endereços, e quem o digita aprova
 * com o acesso desta conta. O token pessoal continua sendo o caminho do Claude
 * Code e do Claude Desktop, emitido aqui mesmo, por quem está logado.
 *
 * A lista é só a desta conta — também para o administrador, que vê as
 * conexões de todos, mas não os e-mails de ninguém.
 *
 * ⚠️ O e-mail nasce AGUARDANDO (revisão de segurança de 26/10): o servidor
 * manda a ele um código, e só depois que a pessoa o digita na linha dele
 * (`LinhaDoEmail`) o e-mail passa a aprovar. É a prova de que a caixa é de
 * quem a cadastrou — um "gmial.com" digitado por engano, ou a caixa que a
 * secretaria também lê, entregava o acesso desta conta a quem a lesse.
 */
function EmailsDaIa({ permissao }: { permissao: PermissaoDeEmitir }) {
  const emails = useEmailsDaIa();
  const cadastrar = useCadastrarEmailDaIa();
  const [novo, setNovo] = useState('');
  const [avisoDeForma, setAvisoDeForma] = useState(false);
  // O anúncio do cadastro feito: o campo esvazia e a lista ganha uma linha, e
  // nenhuma das duas coisas é dita sozinha ao leitor de tela.
  const [cadastrado, setCadastrado] = useState<string | null>(null);
  // As linhas cujo código saiu no cadastro, nesta tela: cada uma leva o foco ao
  // campo do código quando chega da lista, e espera antes de oferecer outro
  // código. Um conjunto, e não "a última": se só a última valesse, cadastrar
  // um segundo e-mail desligaria o relógio da linha do primeiro no meio da
  // espera, e o "enviar outro código" dela nunca mais apareceria. Cadastrar de
  // novo o mesmo endereço é outra linha, com outro id.
  const [codigosQueSairam, setCodigosQueSairam] = useState<ReadonlySet<string>>(() => new Set());
  // ⚠️ Trava SÍNCRONA, como em `NovaConexao`: dois Enter seguidos caberiam no
  // intervalo antes de `isPending` chegar à tela, e o segundo voltaria 409.
  const enviando = useRef(false);
  const campo = useRef<HTMLInputElement>(null);
  const titulo = useRef<HTMLHeadingElement>(null);
  const idTitulo = useId();
  const idExplicacao = useId();
  const idAvisoDaCaixa = useId();
  const idCampo = useId();
  const idAviso = useId();
  const idFalha = useId();
  // Recalculado a cada desenho, como na lista de conexões: "hoje" depende da hora.
  const agora = new Date();

  async function enviar(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    if (enviando.current || cadastrar.isPending) return;
    if (!emailComFormaValida(novo)) {
      setAvisoDeForma(true);
      campo.current?.focus();
      return;
    }
    enviando.current = true;
    setCadastrado(null);
    try {
      const item = await cadastrar.mutateAsync({ email: normalizarEmail(novo) });
      setNovo('');
      setCadastrado(item.email);
      // O próximo passo é o código que acabou de sair, e não outro cadastro:
      // a linha nova leva o foco ao campo dele assim que chegar da lista. Até
      // lá, ele fica no campo do e-mail, de onde o botão desabilitado o tirou.
      setCodigosQueSairam((antes) => new Set(antes).add(item.id));
      campo.current?.focus();
    } catch {
      // A falha fica em `cadastrar.error` e aparece embaixo do campo.
      campo.current?.focus();
    } finally {
      enviando.current = false;
    }
  }

  let lista: ReactNode;
  if (emails.isError) {
    lista = (
      <p className="ia-aviso">
        Não consegui carregar os seus e-mails da IA.{' '}
        {mensagemDaFalha(emails.error, {
          padrao: 'Tente de novo em instantes.',
          proibido: 'O servidor recusou a leitura desta lista para a sua conta.',
        })}
      </p>
    );
  } else if (emails.isPending) {
    lista = <p className="ia-emails__vazio">Carregando os seus e-mails…</p>;
  } else if (!emails.data.length) {
    lista = (
      <p className="ia-emails__vazio">
        Nenhum e-mail cadastrado. Sem um e-mail confirmado, a conexão do claude.ai ou do ChatGPT não
        tem como ser aprovada.
      </p>
    );
  } else {
    lista = (
      <ul className="ia-emails__lista">
        {ordenarEmailsDaIa(emails.data).map((item) => (
          <LinhaDoEmail
            key={item.id}
            item={item}
            agora={agora}
            codigoAcabouDeSair={codigosQueSairam.has(item.id)}
            onRemovido={() => titulo.current?.focus()}
          />
        ))}
      </ul>
    );
  }

  return (
    <section className="ia-emails" aria-labelledby={idTitulo}>
      {/* `tabIndex={-1}`: é para onde o foco volta depois de remover um e-mail,
          quando a linha (e o botão apertado) some da lista. */}
      <h2 id={idTitulo} ref={titulo} tabIndex={-1} className="ia-emails__titulo">
        E-mails da sua IA
      </h2>
      <p id={idExplicacao} className="ia-emails__explicacao">
        A conexão do claude.ai ou do ChatGPT é aprovada por um código enviado a um destes e-mails:
        cadastre o da conta em que você usa a IA, mesmo que não seja o do SAS.
      </p>
      {/* Antes do campo, e não num "saiba mais": é a frase que faltava na
          revisão de segurança de 26/10 — cadastrar a caixa que outra pessoa
          também lê parecia inofensivo. Neutra (`ia-aviso`), porque não é falha. */}
      <p id={idAvisoDaCaixa} className="ia-aviso">{avisoDaCaixaDoEmail()}</p>
      {lista}

      {permissao === 'pode' && (
        <form className="ia-emails__form" onSubmit={enviar} noValidate>
          <label className="ia-campo__rotulo" htmlFor={idCampo}>E-mail da conta de IA</label>
          <input
            id={idCampo}
            ref={campo}
            className="ia-campo"
            type="email"
            value={novo}
            inputMode="email"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            maxLength={EMAIL_MAXIMO}
            placeholder="nome@gmail.com"
            aria-invalid={avisoDeForma || cadastrar.isError || undefined}
            aria-describedby={[
              idExplicacao,
              idAvisoDaCaixa,
              avisoDeForma ? idAviso : null,
              cadastrar.isError ? idFalha : null,
            ].filter(Boolean).join(' ')}
            onChange={(e) => {
              setNovo(e.target.value);
              if (avisoDeForma) setAvisoDeForma(false);
            }}
          />
          <button type="submit" className="btn btn--ghost" disabled={cadastrar.isPending}>
            {cadastrar.isPending ? 'Cadastrando…' : 'Cadastrar'}
          </button>
          {avisoDeForma && (
            <p id={idAviso} className="ia-erro" role="alert">
              Escreva o e-mail inteiro, como nome@gmail.com.
            </p>
          )}
          {cadastrar.isError && (
            <p id={idFalha} className="ia-erro" role="alert">
              {mensagemDaFalhaDoEmailDaIa(statusDe(cadastrar.error), (cadastrar.error as Error)?.message)}
            </p>
          )}
          <span className="ia-so-leitor" role="status">
            {cadastrado ? avisoDoCodigoDeConfirmacao(cadastrado) : ''}
          </span>
        </form>
      )}
      {/* Só com o servidor configurado para "só o administrador": um e-mail de
          outra conta não aprovaria nada, e o formulário ensinaria o contrário. */}
      {permissao === 'so-administrador' && (
        <p className="ia-aviso">
          Neste ambiente, só o administrador do SAS conecta uma IA, e um e-mail desta conta não
          aprova conexão.
        </p>
      )}
    </section>
  );
}

function LinhaDoEmail({
  item, agora, codigoAcabouDeSair, onRemovido,
}: {
  item: EmailDaIa;
  agora: Date;
  /** O CADASTRO, nesta tela, acabou de mandar o código desta linha. */
  codigoAcabouDeSair: boolean;
  onRemovido: () => void;
}) {
  const remover = useRemoverEmailDaIa();
  const confirmar = useConfirmarEmailDaIa();
  const reenviar = useReenviarCodigoDoEmailDaIa();
  // É o que a pessoa digitou, mas passa pela mesma limpeza do resto: é ele que
  // entra no rótulo do botão e no `confirm`.
  const email = emUmaLinha(item.email, EMAIL_MAXIMO);
  // A resposta da confirmação vale antes de a lista voltar: a linha troca o
  // campo do código pela data na hora, em vez de mostrá-lo de novo até o refetch.
  const [confirmadoAgora, setConfirmadoAgora] = useState<string | null>(null);
  const confirmadoEm = item.confirmadoEm ?? confirmadoAgora;
  const confirmado = emailDaIaConfirmado({ confirmadoEm });

  const [codigo, setCodigo] = useState('');
  // A forma errada é avisada no envio, como no consentimento: botão apagado sem
  // explicação deixa a pessoa sem saber o que falta.
  const [avisoDeForma, setAvisoDeForma] = useState(false);
  // Os códigos que "enviar outro" mandou daqui. Somado ao do cadastro, é o
  // relógio da espera: cada código que sai reinicia a espera e devolve o foco
  // ao campo. Linha que chegou da lista sem código recente (a tela foi
  // reaberta) oferece outro código na hora — o servidor não diz quando saiu o
  // último, e o teto de verdade é dele.
  const [reenvios, setReenvios] = useState(0);
  const vezDoCodigo = (codigoAcabouDeSair ? 1 : 0) + reenvios;
  const [podeReenviar, setPodeReenviar] = useState(!codigoAcabouDeSair);
  // ⚠️ Trava SÍNCRONA, como em `NovaConexao`: confirmar e pedir outro código
  // ao mesmo tempo mataria o código que está sendo conferido.
  const travado = useRef(false);
  const campoCodigo = useRef<HTMLInputElement>(null);
  const situacao = useRef<HTMLSpanElement>(null);
  // Confirmar tira da tela o campo e o botão que tinham o foco: ele vai para a
  // situação da linha, que passa a dizer "confirmado em…". Ligada ANTES de
  // mandar, como em `LinhaDaConexao`: a troca pode chegar antes do `await`.
  const focarNaSituacao = useRef(false);
  const idCodigo = useId();
  const idAjuda = useId();
  const idAviso = useId();
  const idFalha = useId();

  useEffect(() => {
    if (!vezDoCodigo) return;
    campoCodigo.current?.focus();
    setPodeReenviar(false);
    const relogio = window.setTimeout(() => setPodeReenviar(true), ESPERA_PARA_OUTRO_CODIGO_MS);
    return () => window.clearTimeout(relogio);
  }, [vezDoCodigo]);

  useEffect(() => {
    if (!confirmado || !focarNaSituacao.current) return;
    focarNaSituacao.current = false;
    situacao.current?.focus();
  }, [confirmado]);

  async function confirmarRemocao() {
    if (!window.confirm(perguntaDeRemocaoDoEmail(item.email))) return;
    try {
      await remover.mutateAsync(item.id);
      // A linha some quando a lista voltar, e o foco sumiria junto com o
      // botão: ele vai para o título da seção.
      onRemovido();
    } catch {
      // A falha fica em `remover.error` e aparece na própria linha.
    }
  }

  async function aoConfirmar(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    if (travado.current || confirmar.isPending || reenviar.isPending) return;
    if (!codigoCompleto(codigo)) {
      setAvisoDeForma(true);
      campoCodigo.current?.focus();
      return;
    }
    travado.current = true;
    reenviar.reset();
    focarNaSituacao.current = true;
    try {
      const resposta = await confirmar.mutateAsync({ id: item.id, codigo });
      setConfirmadoAgora(resposta.confirmadoEm);
      setCodigo('');
      // O código sai da memória do react-query (`gcTime: 0` + `reset()`), como
      // o token em `NovaConexao`.
      confirmar.reset();
    } catch {
      focarNaSituacao.current = false;
      campoCodigo.current?.focus();
      campoCodigo.current?.select();
    } finally {
      travado.current = false;
    }
  }

  async function aoReenviar() {
    if (travado.current || confirmar.isPending || reenviar.isPending) return;
    travado.current = true;
    confirmar.reset();
    try {
      await reenviar.mutateAsync(item.id);
      setCodigo('');
      setAvisoDeForma(false);
      setReenvios((n) => n + 1);
    } catch {
      // A falha fica em `reenviar.error` e aparece embaixo do campo.
    } finally {
      travado.current = false;
    }
  }

  const frasesDoCampo = [idAjuda, avisoDeForma ? idAviso : null, confirmar.isError ? idFalha : null];

  return (
    <li className="ia-emails__item">
      <span className="ia-emails__dados">
        <span className="ia-emails__endereco">{email}</span>
        {/* `tabIndex={-1}`: é para onde o foco vai depois de confirmar. */}
        <span ref={situacao} tabIndex={-1} className="ia-emails__uso">
          {confirmado ? (
            <>
              confirmado em {dataCurta(confirmadoEm)} ·{' '}
              {item.ultimoUsoEm
                ? `última aprovação: ${ultimoUsoLegivel(item.ultimoUsoEm, agora)}`
                : 'nenhuma aprovação ainda'}
            </>
          ) : (
            <>
              <b>aguardando o código</b> · cadastrado em {dataCurta(item.criadoEm)}
            </>
          )}
        </span>
      </span>
      <button
        type="button"
        className="btn-editar"
        onClick={confirmarRemocao}
        disabled={remover.isPending}
        aria-label={remover.isPending ? `Removendo ${email}` : `Remover ${email}`}
      >
        {remover.isPending ? 'Removendo…' : 'Remover'}
      </button>
      {remover.isError && (
        <span className="ia-erro" role="alert">
          {mensagemDaFalha(remover.error, {
            padrao: 'Não consegui remover. Tente de novo.',
            proibido: 'O servidor recusou a remoção deste e-mail.',
          })}
        </span>
      )}
      {/* O e-mail que aguarda (revisão de segurança de 26/10): o campo do
          código mora na própria linha, que é onde a pessoa procura o passo
          que falta. */}
      {!confirmado && (
        <form className="ia-emails__confirmacao" onSubmit={aoConfirmar} noValidate>
          <label className="ia-campo__rotulo" htmlFor={idCodigo}>
            Código que chegou a {email}
          </label>
          <p id={idAjuda} className="ia-campo__ajuda">
            {vezDoCodigo
              ? avisoDoCodigoDeConfirmacao(item.email)
              : 'Até você digitar aqui o código que chegou a este e-mail, ele não aprova conexão nenhuma. Se o código venceu ou não chegou, peça outro.'}
          </p>
          <div className="ia-emails__codigo">
            <input
              id={idCodigo}
              ref={campoCodigo}
              className="ia-campo ia-campo--codigo"
              value={codigo}
              inputMode="numeric"
              autoComplete="one-time-code"
              spellCheck={false}
              aria-invalid={avisoDeForma || confirmar.isError || undefined}
              aria-describedby={frasesDoCampo.filter(Boolean).join(' ')}
              // Sem `maxLength`, pelo motivo do consentimento: ele cortaria o
              // que se cola antes da limpeza. Quem põe o teto é `limparCodigo`.
              onChange={(e) => {
                setCodigo(limparCodigo(e.target.value));
                if (avisoDeForma) setAvisoDeForma(false);
              }}
            />
            <button
              type="submit"
              className="btn btn--ghost"
              disabled={confirmar.isPending || reenviar.isPending}
            >
              {confirmar.isPending ? 'Confirmando…' : 'Confirmar'}
            </button>
          </div>
          {avisoDeForma && (
            <p id={idAviso} className="ia-erro" role="alert">O código tem {DIGITOS_DO_CODIGO} dígitos.</p>
          )}
          {confirmar.isError && (
            <p id={idFalha} className="ia-erro" role="alert">
              {mensagemDaFalhaDaConfirmacao(statusDe(confirmar.error))}
            </p>
          )}
          <p className="ia-emails__mais">
            {podeReenviar ? (
              <button
                type="button"
                className="link-botao"
                disabled={confirmar.isPending || reenviar.isPending}
                onClick={aoReenviar}
              >
                {reenviar.isPending ? 'Enviando outro código…' : 'Não chegou? Enviar outro código'}
              </button>
            ) : (
              // "Em até": a frase não conta os segundos, e continua verdadeira
              // do primeiro ao último deles (o mesmo do consentimento).
              <span>Não chegou? Em até {SEGUNDOS_PARA_OUTRO_CODIGO} segundos dá para pedir outro.</span>
            )}
          </p>
          {/* O código novo não precisa de anúncio próprio: o foco volta ao
              campo, e o campo se descreve com a frase do envio (`idAjuda`),
              como no consentimento. */}
          {reenviar.isError && (
            <p className="ia-erro" role="alert">
              {mensagemDaFalhaDoReenvio(statusDe(reenviar.error), (reenviar.error as Error)?.message)}
            </p>
          )}
        </form>
      )}
      {/* Confirmar troca o formulário pela data: o anúncio diz o que mudou. */}
      <span className="ia-so-leitor" role="status">
        {confirmadoAgora ? `${email} confirmado: ele já aprova conexões do claude.ai e do ChatGPT.` : ''}
      </span>
    </li>
  );
}

function ListaDeConexoes({
  conexoes, carregando, falha, souAdministrador, permissao, refDoTitulo,
}: {
  conexoes: ConexaoDeIa[] | undefined;
  carregando: boolean;
  falha: unknown;
  souAdministrador: boolean;
  permissao: PermissaoDeEmitir;
  /** Para onde o foco volta quando "Nova conexão" não está na tela. */
  refDoTitulo: RefObject<HTMLHeadingElement | null>;
}) {
  const idTitulo = useId();
  // Recalculado a cada desenho, de propósito: "ativa" e "hoje" dependem da
  // hora, e a lista tem dezenas de linhas — não há o que economizar.
  const agora = new Date();
  const titulo = souAdministrador ? 'Todas as conexões' : 'Suas conexões';

  let corpo: ReactNode;
  if (falha) {
    corpo = (
      <div className="card">
        <div className="empty-state">
          Não consegui carregar as conexões.
          <div className="empty-state__hint">
            {mensagemDaFalha(falha, {
              padrao: 'Tente de novo em instantes.',
              proibido: 'O servidor recusou a leitura desta lista para a sua conta.',
            })}
          </div>
        </div>
      </div>
    );
  } else if (carregando || !conexoes) {
    corpo = (
      <div className="card">
        <div className="empty-state">Carregando as conexões…</div>
      </div>
    );
  } else if (!conexoes.length) {
    corpo = (
      <div className="card">
        <div className="empty-state">
          {souAdministrador ? 'Nenhuma IA conectada ao SAS ainda.' : 'Nenhuma conexão em seu nome.'}
          <div className="empty-state__hint">
            {permissao === 'so-administrador'
              ? 'Neste ambiente, quem cria conexões é o administrador do SAS.'
              : 'Para o Claude Code ou o Claude Desktop, “Nova conexão” mostra o token uma vez, com o passo a passo. Para o claude.ai ou o ChatGPT, cadastre e confirme antes o e-mail da sua IA, acima.'}
          </div>
        </div>
      </div>
    );
  } else {
    corpo = (
      <div className="card">
        {/* `--cartoes`: no celular cada conexão vira um cartão, com o rótulo de
            cada campo escrito à mão em `data-rotulo` (web/CLAUDE.md). */}
        <table className="data-table data-table--cartoes">
          <thead>
            <tr>
              <th>Nome</th><th>Prefixo</th><th>Origem</th><th>Criada</th><th>Último uso</th>
              <th>Situação</th>
              {souAdministrador && <th>Dono</th>}
              <th><span className="ia-so-leitor">Ações</span></th>
            </tr>
          </thead>
          <tbody>
            {ordenarConexoes(conexoes, agora).map((c) => (
              <LinhaDaConexao key={c.id} conexao={c} souAdministrador={souAdministrador} agora={agora} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <section className="ia-lista" aria-labelledby={idTitulo}>
      <h2 id={idTitulo} ref={refDoTitulo} tabIndex={-1} className="section__title">{titulo}</h2>
      {corpo}
    </section>
  );
}

function LinhaDaConexao({
  conexao: c, souAdministrador, agora,
}: {
  conexao: ConexaoDeIa;
  souAdministrador: boolean;
  agora: Date;
}) {
  const revogar = useRevogarConexaoDeIa();
  const ativa = situacaoDaConexao(c, agora) === 'ativa';
  // Pelo nome, como em `Contas.tsx`: a sessão não guarda o id da conta. É só
  // para a marca "você" e para o `confirm` não dizer "a conexão é de" você.
  const souEu = c.dono.nome === sessao.nome();
  // Na conexão OAuth o nome pode vir do cadastro do app, e é texto de fora.
  // Um U+202E nele inverteria a leitura da célula e do rótulo do botão.
  const nome = emUmaLinha(c.nome, NOME_MAXIMO);
  const botaoRevogar = useRef<HTMLButtonElement>(null);
  const situacao = useRef<HTMLSpanElement>(null);
  const devolverFoco = useRef(false);

  async function confirmarRevogacao() {
    if (!window.confirm(perguntaDeRevogacao(c, { mostrarDono: souAdministrador && !souEu }))) return;
    devolverFoco.current = true;
    try {
      await revogar.mutateAsync(c.id);
    } catch {
      // A falha fica em `revogar.error` e aparece na própria linha.
    }
  }

  // O foco se perde DUAS vezes numa revogação. Primeiro quando o botão fica
  // desabilitado (o navegador tira o foco de elemento desabilitado), e de novo
  // quando ele some da linha que voltou revogada. Quando a resposta assenta,
  // o foco volta para a linha: para a Situação, que agora diz "revogada em…",
  // se deu certo; para o botão, de novo habilitado, se falhou. O sucesso
  // espera a lista voltar com a linha revogada, porque até lá ela ainda é a
  // linha ativa de antes.
  useEffect(() => {
    if (!devolverFoco.current || revogar.isPending) return;
    if (ativa && !revogar.isError) return;
    devolverFoco.current = false;
    (ativa ? botaoRevogar.current : situacao.current)?.focus();
  }, [ativa, revogar.isPending, revogar.isError]);

  return (
    <tr className={ativa ? undefined : 'ia-linha--encerrada'}>
      <td data-rotulo="Nome" data-titulo>{nome}</td>
      {/* O começo do token, e as reticências dizem que é só o começo: é por ele
          que a pessoa confere qual linha é a do token que está na IA. */}
      <td data-rotulo="Prefixo"><code className="ia-prefixo">{c.prefixo}…</code></td>
      <td data-rotulo="Origem">{origemLegivel(c)}</td>
      <td data-rotulo="Criada" data-secundario>{dataCurta(c.criadaEm)}</td>
      <td data-rotulo="Último uso">{ultimoUsoLegivel(c.ultimoUsoEm, agora)}</td>
      <td data-rotulo="Situação">
        {/* `tabIndex={-1}`: é para onde o foco volta depois de revogar. */}
        <span
          ref={situacao}
          tabIndex={-1}
          className={ativa ? 'ia-situacao ia-situacao--ativa' : 'ia-situacao'}
        >
          {situacaoLegivel(c, agora)}
        </span>
      </td>
      {souAdministrador && (
        <td data-rotulo="Dono">
          {c.dono.nome}
          {souEu && <span className="ia-voce">você</span>}
        </td>
      )}
      {/* Sem botão nas encerradas, e a célula fica VAZIA de verdade: no
          cartão do celular, `td:empty` some em vez de deixar uma linha em
          branco (`layout.css`). */}
      <td className="acoes-da-linha">
        {ativa && (
          <button
            ref={botaoRevogar}
            type="button"
            className="btn-editar"
            onClick={confirmarRevogacao}
            disabled={revogar.isPending}
            aria-label={revogar.isPending ? `Revogando ${nome}` : `Revogar ${nome}`}
          >
            {revogar.isPending ? 'Revogando…' : 'Revogar'}
          </button>
        )}
        {revogar.isError && (
          <span className="ia-erro" role="alert">
            {mensagemDaFalha(revogar.error, {
              padrao: 'Não consegui revogar. Tente de novo.',
              proibido: 'O servidor recusou: só o administrador revoga conexão de outra pessoa.',
            })}
          </span>
        )}
      </td>
    </tr>
  );
}
