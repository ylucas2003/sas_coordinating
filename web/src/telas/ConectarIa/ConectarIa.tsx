import { useEffect, useId, useRef, useState } from 'react';
import type { FormEvent, ReactNode, Ref } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import {
  DIGITOS_DO_CODIGO, EMAIL_MAXIMO, ESPERA_PARA_OUTRO_CODIGO_MS, avisoDoCodigoPedido, codigoCompleto,
  comoDesfazerAConexao, dataCurta, destinoDaVolta, diasDesde, emailComFormaValida, horaCurta,
  hostDaVolta, leituraDaFalhaDoPedido, limparCodigo, mensagemDaFalhaDoConsentimento, nomeDoApp,
  normalizarEmail,
} from '../../dominio/conexoesDeIa';
import type { AcaoDoConsentimento } from '../../dominio/conexoesDeIa';
import { usePedidoDeConexao } from '../../hooks/consultas';
import {
  useAprovarPedidoDeConexao, usePedirCodigoDoPedido, useRecusarPedidoDeConexao,
} from '../../hooks/mutacoes';
import { ErroApi } from '../../servicos/http';
import type { PedidoDeConexao } from '../../tipos/dominio';
import '../../../styles/conexoes-de-ia.css';

// CONECTAR UMA IA — o consentimento do OAuth (docs/43 §5.3, Fase 3).
//
// Um conector (o do claude.ai, o do ChatGPT) quer ler o SAS. O authorization
// server mora na API: é ele que recebe o pedido do app, guarda, e manda o
// browser para `/conectar-ia?pedido=<id>`. Esta tela só mostra o pedido e leva
// a resposta de volta — ela não monta URL nenhuma, não vê o código do OAuth
// nem token, e não sabe de PKCE.
//
// ⚠️ PÁGINA PÚBLICA desde 26/10 (decisão do dono). Fora do casco e fora da
// `RotaProtegida` (`App.tsx`), e nada aqui lê a sessão: o claude.ai e o
// ChatGPT não dizem ao SAS o e-mail da conta, e a aba que eles abrem chega sem
// login (o `sessionStorage` é por aba). Quem aprova prova a POSSE do e-mail da
// IA: digita o e-mail que cadastrou em Conexões de IA, recebe um código de seis
// dígitos, e a conexão nasce com o acesso da conta DONA daquele e-mail.
//
// ⚠️ E NENHUMA FRASE AQUI DEPENDE DE O E-MAIL EXISTIR. O pedido de código
// responde igual para e-mail cadastrado ou não, e a tela diz sempre a mesma
// coisa (`avisoDoCodigoPedido`); a aprovação recusada também é uma frase só,
// até o código certo (`mensagemDaFalhaDoConsentimento`). Uma frase a mais para
// "esse e-mail não está no SAS" faria desta página, que qualquer um abre, um
// jeito de descobrir o e-mail da coordenação. Depois do código certo, quem lê
// já provou ler a caixa, e a tela diz o que o servidor disse que houve.
//
// O que a tela tem de deixar claro antes do botão, e em que ordem:
//   1 · QUEM pede — e que o nome é o que o próprio app declarou; o que o SAS
//       confere é o endereço de volta, e é ele que ganha peso na tela;
//   2 · o que o app passa a CONSEGUIR — ler os dados da coordenação e levá-los,
//       inclusive o nome dos alunos, para fora do SAS (decisão do dono de 26/10:
//       o MCP devolve o nome real);
//   3 · que dá para desfazer, e onde.
// Pedido expirado ou inexistente não oferece "Aprovar": explica e manda de
// volta ao app, que é o único lugar onde se começa de novo.

function statusDe(erro: unknown): number | null {
  return erro instanceof ErroApi ? erro.status : null;
}

/**
 * O campo do código e o aviso de FORMA dele ("O código tem 6 dígitos."), num
 * pedaço só: o id do aviso nasce aqui, ao lado do `aria-describedby` que o
 * cita. Separados, o aviso ficou sem id, e quem voltava ao campo com leitor de
 * tela ouvia "inválido" sem o porquê (revisão de 26/10). A etapa do e-mail faz
 * o mesmo com `idAvisoEmail`.
 *
 * Exportado para `ConectarIa.test.ts`: a etapa do código depende do estado da
 * tela e não chega por SSR (o repositório não tem jsdom), e este pedaço chega.
 */
export function CampoDoCodigo({
  id, ref, codigo, formaRecusada, codigoRecusado, idDoAvisoDeEnvio, idDaFalha, aoMudar,
}: {
  id: string;
  ref?: Ref<HTMLInputElement>;
  codigo: string;
  /** A tela recusou a forma antes de enviar: faltam dígitos. */
  formaRecusada: boolean;
  /** O servidor recusou o código (o 400 da aprovação). */
  codigoRecusado: boolean;
  /** O aviso de para onde o código foi, que descreve o campo sempre. */
  idDoAvisoDeEnvio: string;
  /** A falha do servidor, quando há uma na tela. */
  idDaFalha: string | null;
  /** Recebe o código já limpo (`limparCodigo`). */
  aoMudar: (codigo: string) => void;
}) {
  const idDaForma = useId();
  return (
    <>
      <input
        id={id}
        ref={ref}
        className="ia-campo ia-campo--codigo"
        value={codigo}
        inputMode="numeric"
        autoComplete="one-time-code"
        spellCheck={false}
        aria-invalid={codigoRecusado || formaRecusada || undefined}
        aria-describedby={[idDoAvisoDeEnvio, formaRecusada ? idDaForma : null, idDaFalha]
          .filter(Boolean)
          .join(' ')}
        // Sem `maxLength`: ele cortaria o que se cola ANTES da limpeza, e
        // "123 456" viraria "123 45". Quem põe o teto é `limparCodigo`.
        onChange={(e) => aoMudar(limparCodigo(e.target.value))}
      />
      {formaRecusada && (
        <p id={idDaForma} className="ia-erro" role="alert">O código tem {DIGITOS_DO_CODIGO} dígitos.</p>
      )}
    </>
  );
}

export function ConectarIa() {
  const [params] = useSearchParams();
  const pedidoId = params.get('pedido');
  const pedido = usePedidoDeConexao(pedidoId);

  let corpo: ReactNode;
  if (!pedidoId) {
    corpo = <SemPedido />;
  } else if (pedido.isError) {
    corpo = leituraDaFalhaDoPedido(statusDe(pedido.error)) === 'encerrado'
      ? <PedidoIndisponivel />
      : <FalhaAoLer erro={pedido.error} onTentar={() => pedido.refetch()} />;
  } else if (pedido.isPending) {
    corpo = <Carregando />;
  } else {
    corpo = <Consentimento pedido={pedido.data} />;
  }

  return (
    <div className="ia-avulsa">
      {/* A marca, sem casco em volta: quem chega aqui veio de outro site, numa
          aba nova, e a primeira coisa a conferir é se está no SAS. A máscara
          do logo é a do rail (`casco.css::.rail__logo`), e não uma cópia: o
          navy literal da marca é exceção documentada lá, e duas cópias dele
          divergiriam no primeiro ajuste. */}
      <header className="ia-avulsa__marca">
        <span className="rail__logo" role="img" aria-label="Colégio Ari de Sá Cavalcante" />
        <span className="ia-avulsa__nome">SAS · Conexões de IA</span>
      </header>
      <main className="ia-avulsa__corpo">{corpo}</main>
    </div>
  );
}

function Carregando() {
  return (
    <section className="ia-pedido" aria-busy="true">
      <span className="ia-pedido__olho">Pedido de conexão</span>
      <h1 className="ia-pedido__titulo">Conectar uma IA ao SAS</h1>
      <p className="ia-pedido__volta" role="status">Carregando o pedido de conexão…</p>
    </section>
  );
}

/** O endereço chegou sem `?pedido=`: alguém abriu a rota à mão. */
function SemPedido() {
  return (
    <section className="ia-pedido">
      <span className="ia-pedido__olho">Pedido de conexão</span>
      <h1 className="ia-pedido__titulo">Este endereço chegou sem o pedido</h1>
      <p className="ia-pedido__volta">
        Esta página responde a um pedido de conexão, e abre sozinha quando o claude.ai, o ChatGPT ou
        outro app de IA pede para ler o SAS. Para conectar um desses, comece pelo próprio app.
      </p>
      <p className="ia-pedido__volta">
        Para o Claude Code ou o Claude Desktop o caminho é outro: um token pessoal, criado com o seu
        login em <Link to="/administracao/conexoes-de-ia">Administração › Conexões de IA</Link>.
      </p>
    </section>
  );
}

/** 404 na leitura: o pedido expirou, já foi respondido ou nunca existiu. */
function PedidoIndisponivel() {
  return (
    <section className="ia-pedido">
      <span className="ia-pedido__olho">Pedido de conexão</span>
      <h1 className="ia-pedido__titulo">Este pedido expirou ou não existe mais</h1>
      <p className="ia-pedido__volta">
        Todo pedido de conexão tem prazo curto, e cada um só pode ser respondido uma vez. Volte ao
        app de IA e comece a conexão de novo: ele gera um pedido novo e traz você de volta para cá.
      </p>
    </section>
  );
}

/** Falha que não é "encerrado": rede, servidor. Tentar de novo pode resolver. */
function FalhaAoLer({ erro, onTentar }: { erro: unknown; onTentar: () => void }) {
  // Só a frase do transporte, que diz "sem resposta"; o texto cru do servidor
  // seria `GET /oauth/pedidos/… → 500` para quem só quer conectar a IA.
  const rede = statusDe(erro) === 0 ? (erro as Error).message : null;
  return (
    <section className="ia-pedido">
      <span className="ia-pedido__olho">Pedido de conexão</span>
      <h1 className="ia-pedido__titulo">Não consegui ler o pedido de conexão</h1>
      <p className="ia-pedido__volta">
        {rede ?? 'O SAS não respondeu como devia. Tente de novo em instantes.'}
      </p>
      <div className="ia-pedido__acoes">
        <button type="button" className="btn btn--ghost" onClick={onTentar}>
          Tentar de novo
        </button>
      </div>
    </section>
  );
}

/** "até 14:32", ou "até 25/10/2026 às 00:10" quando a validade cruza a meia-noite. */
function validade(expiraEm: string): string {
  const dias = diasDesde(expiraEm, new Date());
  return dias === 0 ? `até ${horaCurta(expiraEm)}` : `até ${dataCurta(expiraEm)} às ${horaCurta(expiraEm)}`;
}

const SEGUNDOS_PARA_OUTRO_CODIGO = Math.round(ESPERA_PARA_OUTRO_CODIGO_MS / 1000);

interface Falha {
  acao: AcaoDoConsentimento;
  erro: unknown;
}

function Consentimento({ pedido }: { pedido: PedidoDeConexao }) {
  const pedirCodigo = usePedirCodigoDoPedido();
  const aprovar = useAprovarPedidoDeConexao();
  const recusar = useRecusarPedidoDeConexao();

  const [email, setEmail] = useState('');
  // O e-mail para o qual o código foi pedido — é ele, e não o que estiver no
  // campo, que vai junto na aprovação: o código está preso ao pedido E ao
  // e-mail. Preenchido, a tela está na etapa do código.
  const [emailDoCodigo, setEmailDoCodigo] = useState<string | null>(null);
  const [codigo, setCodigo] = useState('');
  // A forma errada é avisada no envio, e não com o botão desabilitado: botão
  // apagado sem explicação deixa a pessoa sem saber o que falta.
  const [avisoDeForma, setAvisoDeForma] = useState<'email' | 'codigo' | null>(null);
  const [falha, setFalha] = useState<Falha | null>(null);
  // Contadores, e não booleanos: cada código pedido reinicia a espera e devolve
  // o foco ao campo, mesmo que o anterior tenha feito o mesmo.
  const [codigosPedidos, setCodigosPedidos] = useState(0);
  const [podeReenviar, setPodeReenviar] = useState(false);
  const [voltasAoEmail, setVoltasAoEmail] = useState(0);
  // O browser já está indo embora — os botões não podem voltar a aparecer.
  const [voltando, setVoltando] = useState(false);
  // O servidor respondeu, mas mandou voltar para outro lugar: o pedido já foi
  // gasto. Guarda QUAL resposta foi, porque o que fazer depois muda.
  const [voltaRecusada, setVoltaRecusada] = useState<'aprovar' | 'recusar' | null>(null);
  // ⚠️ A trava contra a segunda ação é SÍNCRONA. `ocupado` e o `disabled` dos
  // botões vêm do último desenho, e o react-query só avisa a tela um macrotask
  // depois do `mutate` (`notifyManager`, `setTimeout(0)`). Duas ativações
  // nesse intervalo (thread ocupada, clique programático, tecnologia
  // assistiva) mandariam dois e-mails, ou Aprovar e Recusar juntos — e aí quem
  // decidiria o `location.assign` seria a resposta que chegasse primeiro.
  const travado = useRef(false);
  const campoEmail = useRef<HTMLInputElement>(null);
  const campoCodigo = useRef<HTMLInputElement>(null);

  const idTitulo = useId();
  const idEtapa = useId();
  const idEmail = useId();
  const idAjudaEmail = useId();
  const idAvisoEmail = useId();
  const idCodigo = useId();
  const idAvisoCodigo = useId();
  const idFalha = useId();

  // O código chegou (ou outro foi pedido): o foco vai para o campo dele. O
  // campo descreve a si mesmo com o aviso de envio (`aria-describedby`), então
  // quem usa leitor de tela ouve a frase junto com o campo.
  useEffect(() => {
    if (!codigosPedidos) return;
    campoCodigo.current?.focus();
  }, [codigosPedidos]);

  // "Enviar outro código" só aparece depois da espera — ver
  // `ESPERA_PARA_OUTRO_CODIGO_MS`. Cada pedido reinicia o relógio.
  useEffect(() => {
    if (!codigosPedidos) return;
    setPodeReenviar(false);
    const relogio = window.setTimeout(() => setPodeReenviar(true), ESPERA_PARA_OUTRO_CODIGO_MS);
    return () => window.clearTimeout(relogio);
  }, [codigosPedidos]);

  // "Usar outro e-mail" tira da tela o botão que tinha o foco; ele volta ao
  // campo do e-mail, que é o próximo passo.
  useEffect(() => {
    if (!voltasAoEmail) return;
    campoEmail.current?.focus();
  }, [voltasAoEmail]);

  const ocupado = pedirCodigo.isPending || aprovar.isPending || recusar.isPending || voltando;
  const leitura = falha ? leituraDaFalhaDoPedido(statusDe(falha.erro)) : null;
  const encerrado = leitura === 'encerrado';
  const fraseDaFalha = falha && !encerrado
    ? mensagemDaFalhaDoConsentimento(falha.acao, statusDe(falha.erro), (falha.erro as Error)?.message)
    : null;
  const codigoRecusado = falha?.acao === 'aprovar' && leitura === 'recusado';

  const { redirectHost } = pedido.cliente;
  // O que a tela MOSTRA passa pela limpeza de texto de fora. O nome é
  // declarado pelo próprio app, e o host, mesmo conferido pelo servidor, não
  // pode trazer caractere invisível que inverta a leitura dele. E a volta
  // (`destinoDaVolta`) confere o destino contra ESTE texto, o mostrado, e não
  // contra uma releitura dele (revisão de segurança de 25/10).
  const nome = nomeDoApp(pedido.cliente.nome) ?? 'Um app sem nome';
  const hostVisivel = hostDaVolta(redirectHost);

  async function pedirOCodigo(alvo: string) {
    if (travado.current || ocupado) return;
    travado.current = true;
    setFalha(null);
    pedirCodigo.reset();
    try {
      await pedirCodigo.mutateAsync({ pedidoId: pedido.id, email: alvo });
      setEmailDoCodigo(alvo);
      setCodigo('');
      setAvisoDeForma(null);
      setCodigosPedidos((n) => n + 1);
    } catch (erro) {
      setFalha({ acao: 'codigo', erro });
      // O botão apertado foi desabilitado e perdeu o foco: ele volta ao campo
      // de onde a pessoa vai corrigir ou tentar de novo.
      (emailDoCodigo ? campoCodigo : campoEmail).current?.focus();
    } finally {
      travado.current = false;
    }
  }

  function aoEnviarEmail(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    if (!emailComFormaValida(email)) {
      setAvisoDeForma('email');
      campoEmail.current?.focus();
      return;
    }
    void pedirOCodigo(normalizarEmail(email));
  }

  function trocarEmail() {
    setEmailDoCodigo(null);
    setCodigo('');
    setFalha(null);
    setAvisoDeForma(null);
    setVoltasAoEmail((n) => n + 1);
  }

  async function responder(acao: 'aprovar' | 'recusar') {
    if (travado.current || ocupado) return;
    if (acao === 'aprovar' && (!emailDoCodigo || !codigoCompleto(codigo))) return;
    travado.current = true;
    setFalha(null);
    aprovar.reset();
    recusar.reset();
    try {
      const { redirecionarPara } = acao === 'aprovar'
        ? await aprovar.mutateAsync({ pedidoId: pedido.id, email: emailDoCodigo ?? '', codigo })
        : await recusar.mutateAsync(pedido.id);
      // Daqui em diante a trava fica fechada: o pedido foi gasto, e o
      // browser está indo embora ou a volta foi interrompida.
      const destino = destinoDaVolta(redirecionarPara, redirectHost);
      if (!destino) {
        setVoltaRecusada(acao);
        return;
      }
      setVoltando(true);
      window.location.assign(destino);
    } catch (erro) {
      // A trava abre para a pessoa tentar de novo, pedir outro código ou
      // recusar. É seguro: se o servidor chegou a registrar a primeira
      // resposta, a segunda volta 404, e a tela explica que o pedido acabou.
      setFalha({ acao, erro });
      travado.current = false;
      if (acao === 'aprovar') {
        campoCodigo.current?.focus();
        campoCodigo.current?.select();
      }
    }
  }

  function aoAprovar(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    if (!codigoCompleto(codigo)) {
      setAvisoDeForma('codigo');
      campoCodigo.current?.focus();
      return;
    }
    void responder('aprovar');
  }

  const botaoRecusar = (
    <button type="button" className="btn btn--ghost" disabled={ocupado} onClick={() => responder('recusar')}>
      {recusar.isPending ? 'Recusando…' : 'Recusar'}
    </button>
  );
  const avisoDaFalha = fraseDaFalha && (
    <p id={idFalha} className="ia-erro" role="alert">{fraseDaFalha}</p>
  );

  let etapa: ReactNode;
  if (encerrado) {
    etapa = (
      <p className="ia-erro" role="alert">
        Este pedido não pode mais ser respondido: ele expirou ou já foi respondido. Volte ao app e
        comece a conexão de novo.
      </p>
    );
  } else if (voltaRecusada) {
    etapa = (
      <p className="ia-erro" role="alert">
        O SAS registrou a resposta, mas mandou voltar para um endereço diferente de {hostVisivel}.
        Por segurança, a volta foi interrompida.{' '}
        {/* "Se aparecer", e não "a conexão que nasceu": o código da aprovação
            não chegou ao app, e se a conexão já existe ou só nasceria na troca
            do código é coisa do servidor, que esta tela não vê. */}
        {voltaRecusada === 'aprovar' ? (
          <>
            Se aparecer em <Link to="/administracao/conexoes-de-ia">Conexões de IA</Link>, no SAS,
            uma conexão que você não reconhece, revogue-a. Para conectar, comece de novo pelo app.
          </>
        ) : 'Nada foi conectado. Pode fechar esta aba.'}
      </p>
    );
  } else if (voltando) {
    etapa = (
      <p className="ia-pedido__estado" role="status">
        Voltando para {hostVisivel}… Se nada acontecer em alguns segundos, pode fechar esta aba.
      </p>
    );
  } else if (emailDoCodigo) {
    etapa = (
      // `key` nas duas etapas: sem ela o React reaproveitava o MESMO `<input>`
      // do e-mail para o código (visto no browser em 26/10), trocando tipo e
      // atributos de um campo que o navegador já tinha classificado como
      // e-mail. Cada etapa nasce com o campo dela.
      <form key="codigo" className="ia-pedido__etapa" onSubmit={aoAprovar} aria-labelledby={idEtapa} noValidate>
        <h2 id={idEtapa} className="ia-pedido__subtitulo">Digite o código</h2>
        <p id={idAvisoCodigo} className="ia-pedido__volta">{avisoDoCodigoPedido(emailDoCodigo)}</p>
        <label className="ia-campo__rotulo" htmlFor={idCodigo}>
          Código de {DIGITOS_DO_CODIGO} dígitos
        </label>
        <CampoDoCodigo
          id={idCodigo}
          ref={campoCodigo}
          codigo={codigo}
          formaRecusada={avisoDeForma === 'codigo'}
          codigoRecusado={codigoRecusado}
          idDoAvisoDeEnvio={idAvisoCodigo}
          idDaFalha={fraseDaFalha ? idFalha : null}
          aoMudar={(limpo) => {
            setCodigo(limpo);
            if (avisoDeForma === 'codigo') setAvisoDeForma(null);
          }}
        />
        {avisoDaFalha}
        <div className="ia-pedido__acoes">
          <button type="submit" className="btn btn-primary" disabled={ocupado}>
            {aprovar.isPending ? 'Aprovando…' : 'Aprovar'}
          </button>
          {botaoRecusar}
        </div>
        <p className="ia-pedido__mais">
          {podeReenviar ? (
            <button
              type="button"
              className="link-botao"
              disabled={ocupado}
              onClick={() => pedirOCodigo(emailDoCodigo)}
            >
              Não chegou? Enviar outro código
            </button>
          ) : (
            // "Em até": a frase não conta os segundos, e continua verdadeira
            // do primeiro ao último deles.
            <span>Não chegou? Em até {SEGUNDOS_PARA_OUTRO_CODIGO} segundos dá para pedir outro.</span>
          )}
          <button type="button" className="link-botao" disabled={ocupado} onClick={trocarEmail}>
            Usar outro e-mail
          </button>
        </p>
      </form>
    );
  } else {
    etapa = (
      <form key="email" className="ia-pedido__etapa" onSubmit={aoEnviarEmail} aria-labelledby={idEtapa} noValidate>
        <h2 id={idEtapa} className="ia-pedido__subtitulo">Para aprovar, confirme o e-mail da sua IA</h2>
        <label className="ia-campo__rotulo" htmlFor={idEmail}>E-mail da conta de IA</label>
        <p id={idAjudaEmail} className="ia-campo__ajuda">
          O que você cadastrou e confirmou no SAS, em Conexões de IA — o da conta em que você usa
          este app. O código para aprovar chega nele.
        </p>
        <input
          id={idEmail}
          ref={campoEmail}
          className="ia-campo"
          type="email"
          value={email}
          inputMode="email"
          autoComplete="email"
          autoCapitalize="none"
          spellCheck={false}
          maxLength={EMAIL_MAXIMO}
          placeholder="nome@gmail.com"
          aria-invalid={avisoDeForma === 'email' || undefined}
          aria-describedby={[
            idAjudaEmail,
            avisoDeForma === 'email' ? idAvisoEmail : null,
            fraseDaFalha ? idFalha : null,
          ].filter(Boolean).join(' ')}
          onChange={(e) => {
            setEmail(e.target.value);
            if (avisoDeForma === 'email') setAvisoDeForma(null);
          }}
        />
        {avisoDeForma === 'email' && (
          <p id={idAvisoEmail} className="ia-erro" role="alert">
            Escreva o e-mail inteiro, como nome@gmail.com.
          </p>
        )}
        {avisoDaFalha}
        <div className="ia-pedido__acoes">
          <button type="submit" className="btn btn-primary" disabled={ocupado}>
            {pedirCodigo.isPending ? 'Enviando…' : 'Enviar código'}
          </button>
          {botaoRecusar}
        </div>
      </form>
    );
  }

  return (
    <section className="ia-pedido" aria-labelledby={idTitulo}>
      <span className="ia-pedido__olho">Pedido de conexão</span>
      <h1 id={idTitulo} className="ia-pedido__titulo">{nome} quer ler o SAS com o seu acesso</h1>
      <p className="ia-pedido__volta">
        Depois da sua resposta, o navegador volta para{' '}
        <span className="ia-pedido__host">{hostVisivel}</span>.
      </p>

      <h2 className="ia-pedido__subtitulo">Se você aprovar, este app passa a:</h2>
      {/* ⚠️ Texto de compromisso (docs/43 §5.2 e §5.3). Desde 26/10 o MCP
          devolve o NOME do aluno, e não mais a matrícula (decisão do dono, que
          pede a base legal do art. 14 da LGPD); a frase diz isso com todas as
          letras. Se o servidor for configurado para pseudonimizar
          (`MCP_MOSTRAR_NOME_DO_ALUNO=false`), ela avisa mais do que acontece,
          e esse é o lado certo de errar. */}
      <ul className="ia-pedido__lista">
        <li>
          <b>ler os dados da coordenação</b> com o acesso da conta do SAS dona do e-mail que você
          confirmar abaixo — a conexão fica no nome dela, na lista de Conexões de IA;
        </li>
        <li>
          levar o que ler — <b>inclusive o nome dos alunos</b>, a maioria menor de idade — <b>para
          fora do SAS</b>, para o provedor do app, sob a conta em que você o usa;
        </li>
        <li>
          <b>só ler</b>: nada no SAS muda por esta conexão.
        </li>
      </ul>

      {/* O cadastro de cliente do OAuth é DINÂMICO (docs/43 §2): qualquer app
          se cadastra com o nome que quiser, inclusive "Claude". O nome não
          prova nada; o host de volta é o que o servidor confere. Esta frase é
          a defesa contra o pedido plantado — o link que alguém manda para a
          coordenadora aprovar sem ter pedido. Com a aprovação por código, ela
          vale ainda mais: o código chega no e-mail de quem foi enganado. */}
      <p className="ia-aviso">
        Aprove só se foi você quem pediu esta conexão agora, no próprio app. O nome acima é o que o
        app declarou sobre si; o que confirma para onde a resposta vai é o endereço de volta.
      </p>

      {/* Como desfazer é dito ANTES do botão, e só o que o contrato garante —
          hoje, que revogar uma conexão OAuth corta também a renovação do lado
          do servidor (`REVOGACAO_OAUTH_CORTA_RENOVACAO`, em dominio/). */}
      <p className="ia-pedido__prazo">
        {comoDesfazerAConexao()} Este pedido vale {validade(pedido.expiraEm)}.
      </p>

      {etapa}
    </section>
  );
}
