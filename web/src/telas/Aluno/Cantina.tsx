import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  BOM_PROVEITO, cardDaCantina, horaLegivel, instrucaoDoBloco, marcadasNoBloco, pendenciaDoPedido,
  podeMarcarMais, prazoLegivel, resumoDoPedido, ROTULO_DA_REFEICAO, rotuloDoDia, situacaoDoDia,
} from '../../dominio/cantina';
import {
  useCancelarPedido, useCantinaDoAluno, useDesistirDaRetirada, useSalvarPedido,
} from '../../hooks/cantina';
import type { DiaDoAluno } from '../../tipos/cantina';
import { Bloco } from './pecas/Bloco';

// A CANTINA do aluno — a tela cheia, em `/cantina`.
//
// Lista **todos os dias já publicados** (docs/38 §8.0.6): se a cantina lança a
// semana na sexta, o aluno resolve a semana na sexta. Cada dia tem o SEU prazo,
// e é o prazo que governa — não a posição na lista.
//
// ⚠️ **Escolher aqui tem consequência.** Quem não pedir não come, e depois do
// prazo nada entra — nem pela cantina. É por isso que o prazo aparece em
// magnitude em cada dia aberto, e não como uma linha de rodapé.
//
// ⚠️ A validação desta tela é CONVENIÊNCIA. Quem decide é o servidor: ele
// recusa com 409 depois do prazo e com 422 fora do teto, mesmo com a tela
// aberta desde antes. O que o botão desabilitado faz é evitar o clique que
// falharia — não é a regra.

export function CantinaDoAluno() {
  const { data, isPending } = useCantinaDoAluno();

  if (isPending) return <p className="alu-vazio">Carregando…</p>;

  if (!data?.direitos.length) {
    // Não é erro nem estado vazio decorado: para 800 dos 900 alunos esta tela
    // simplesmente não é deles, e o card em Hoje nem aparece.
    return (
      <div className="alu-cantina">
        <h1 className="alu-titulo-tela">Cantina</h1>
        <p className="alu-vazio">Você não tem refeição pelo colégio.</p>
      </div>
    );
  }

  return (
    <div className="alu-cantina">
      <h1 className="alu-titulo-tela">Cantina</h1>

      {!data.dias.length && (
        <p className="alu-vazio">
          A cantina ainda não publicou nenhum cardápio. Assim que publicar, ele aparece aqui.
        </p>
      )}

      {data.dias.map((dia) => (
        <DiaDaCantina key={dia.id} dia={dia} />
      ))}
    </div>
  );
}

/**
 * Um dia: o cardápio, a escolha e o prazo — e, desde docs/40, o MODO.
 *
 * A seleção é estado LOCAL semeado do servidor, e não controlada por ele: o
 * aluno marca três coisas antes de enviar, e um round-trip por clique
 * transformaria a escolha numa fila de esperas.
 *
 * ⚠️ Quem decide o que este dia oferece é `situacaoDoDia`, função pura com
 * teste ao lado — a máquina de estados do docs/40 §2 é assimétrica (pedido é
 * porta sem volta, presencial é reversível até a leitura), e regra dessa forma
 * dentro de um componente não tem como ser verificada.
 */
export function DiaDaCantina({ dia }: { dia: DiaDoAluno }) {
  const [selecao, setSelecao] = useState<ReadonlySet<string>>(() => new Set(dia.meuPedido ?? []));
  // "Prefiro fazer o pedido" a partir de uma retirada: abre os blocos sem
  // desfazer nada. Quem sobrescreve a linha presencial é o `PUT` do pedido, no
  // servidor — apagar antes deixaria o aluno sem nada se ele desistir no meio.
  const [trocandoParaPedido, setTrocandoParaPedido] = useState(false);
  const salvar = useSalvarPedido();
  const cancelar = useCancelarPedido();
  const desistir = useDesistirDaRetirada();

  // Ressemeia quando o pedido muda no servidor — outra aba, ou a confirmação
  // da própria gravação. `join` e não o array: a identidade do array muda a
  // cada refetch, e o efeito rodaria por nada.
  const assinatura = (dia.meuPedido ?? []).join(',');
  useEffect(() => {
    setSelecao(new Set(assinatura ? assinatura.split(',') : []));
  }, [assinatura]);

  const situacao = situacaoDoDia(dia);
  const pendencia = useMemo(() => pendenciaDoPedido(dia, selecao), [dia, selecao]);
  const jaPedi = situacao.estado === 'pedido';
  const mudou = assinatura !== [...selecao].sort().join(',');
  // O formulário de itens aparece quando pedir é o caminho: no dia em aberto,
  // no pedido que ainda dá para trocar, e na retirada que o aluno decidiu
  // converter. Numa retirada intacta ele NÃO aparece — presencial não escolhe
  // prato (docs/40 §10.1), e mostrar os blocos ali seria oferecer o oposto.
  const escolhendo = situacao.podePedir
    && (situacao.estado !== 'presencial' || trocandoParaPedido);

  function alternar(opcaoId: string, blocoIndice: number) {
    const bloco = dia.blocos[blocoIndice];
    setSelecao((atual) => {
      const novo = new Set(atual);
      if (novo.has(opcaoId)) {
        novo.delete(opcaoId);
        return novo;
      }
      // Teto 1 é o caso comum (uma proteína): marcar a segunda TROCA em vez de
      // recusar. Recusar obrigaria a desmarcar antes, que é um clique a mais
      // para dizer a mesma coisa.
      if (bloco.escolhas_maximas === 1) {
        for (const o of bloco.opcoes) novo.delete(o.id);
      } else if (!podeMarcarMais(bloco, novo)) {
        return atual;
      }
      novo.add(opcaoId);
      return novo;
    });
  }

  return (
    <Bloco
      fonte="cantina"
      olho={`${ROTULO_DA_REFEICAO[dia.refeicao]} · ${rotuloDoDia(dia.data)}`}
      acao={
        // O prazo é do PEDIDO. Numa retirada presencial ele não governa nada
        // (docs/40 §3), e repeti-lo ali diria a coisa errada com destaque.
        situacao.estado === 'retirado' || situacao.estado === 'presencial' ? null : (
          <span
            className={`alu-cantina__prazo${situacao.podePedir ? '' : ' alu-cantina__prazo--fechado'}`}
          >
            {prazoLegivel(dia.pedidos_ate)}
          </span>
        )
      }
      className="alu-cantina__dia"
    >
      {situacao.estado === 'retirado' && (
        <>
          <p className="alu-cantina__proveito">{BOM_PROVEITO[dia.refeicao]}</p>
          <p className="alu-cantina__aviso">
            Retirado às {horaLegivel(dia.retiradoEm)}.
          </p>
        </>
      )}

      {situacao.estado === 'presencial' && !trocandoParaPedido && (
        <p className="alu-cantina__aviso">
          Você vai pegar pessoalmente — mostre o código no balcão. Não precisa escolher pratos.
        </p>
      )}

      {situacao.estado === 'pedido' && !situacao.podePedir && (
        <p className="alu-cantina__aviso">
          Seu pedido: {resumoDoPedido(dia, dia.meuPedido ?? [])}
        </p>
      )}

      {situacao.estado === 'aberto' && !situacao.podePedir && situacao.podeRetirar && (
        // A frase que a feature inteira existe para poder dizer: o prazo do
        // pedido acabou e ainda dá para comer (docs/40 §0).
        //
        // ⚠️ "pegar pessoalmente", e não "retirada na hora": ela sai no MESMO
        // cartão em que o único botão diz "Pegar pessoalmente". A área do aluno
        // tem vocabulário próprio de propósito — quem lê aqui tem 16 anos e não
        // trabalha na copa —, mas esta linha tinha pegado emprestada a palavra
        // da cantina, e as duas apareciam juntas.
        <p className="alu-cantina__aviso">
          O prazo do pedido passou, mas ainda dá para pegar pessoalmente.
        </p>
      )}

      {situacao.estado === 'aberto' && !situacao.podePedir && !situacao.podeRetirar && (
        <p className="alu-cantina__aviso">O prazo passou e você não pediu esta refeição.</p>
      )}

      {escolhendo && dia.blocos.map((bloco, i) => (
        <section key={bloco.id} className="alu-cantina__bloco">
          <header className="alu-cantina__bloco-topo">
            <h2 className="alu-cantina__bloco-nome">{bloco.nome}</h2>
            <span className="alu-cantina__instrucao">
              {instrucaoDoBloco(bloco)}
              {bloco.escolhas_maximas > 1 && (
                <> · {marcadasNoBloco(bloco, selecao)} marcada(s)</>
              )}
            </span>
          </header>

          <ul className="alu-cantina__opcoes">
            {bloco.opcoes.map((opcao) => {
              const marcada = selecao.has(opcao.id);
              return (
                <li key={opcao.id}>
                  <button
                    type="button"
                    className={`alu-cantina__opcao${marcada ? ' alu-cantina__opcao--marcada' : ''}`}
                    // Acabou o prato: o botão sai de circulação, e o motivo
                    // aparece — some sem explicação seria pior que continuar.
                    disabled={!opcao.disponivel || bloco.escolhas_maximas === 0}
                    aria-pressed={marcada}
                    onClick={() => alternar(opcao.id, i)}
                  >
                    {opcao.nome}
                    {!opcao.disponivel && <span className="alu-cantina__acabou">acabou</span>}
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      {(situacao.podePedir || situacao.podeRetirar) && (
        <footer className="alu-cantina__acoes">
          {/* A pendência aparece ANTES do botão e no lugar do erro: o aluno lê
              o que falta sem ter de clicar para descobrir. */}
          {escolhendo && pendencia && <p className="alu-cantina__pendencia">{pendencia}</p>}

          {/* ⚠️ Os DOIS caminhos lado a lado, e só quando os dois existem
              (docs/40 §6). Quando o cardápio aceita um só, aparece um só — uma
              escolha de uma opção não é escolha, é ruído na frente do almoço. */}
          <div className="alu-cantina__modos">
            {escolhendo && (
              <button
                type="button"
                className="alu-tecla alu-tecla--larga"
                disabled={!!pendencia || salvar.isPending || (!mudou && jaPedi)}
                onClick={() => salvar.mutate({ cardapioId: dia.id, opcaoIds: [...selecao] })}
              >
                {salvar.isPending
                  ? 'Salvando…'
                  : jaPedi
                    ? (mudou ? 'Salvar alteração' : 'Pedido enviado')
                    : 'Fazer pedido'}
              </button>
            )}

            {situacao.podeRetirar && (
              // Link, e não botão de mutação: quem cria a linha presencial é a
              // própria tela do QR, ao abrir. Duas portas para o mesmo POST
              // dariam duas chances de ele acontecer sem o aluno ver o código.
              //
              // VAZADA quando o pedido também está na tela, preenchida quando é
              // a única saída — a gramática da casa (preenchido é o caminho
              // principal, vazado é o outro). O pedido leva o preenchimento
              // porque é ele que EXPIRA.
              <Link
                className={`alu-tecla alu-tecla--larga${escolhendo ? ' alu-tecla--fantasma' : ''}`}
                to={`/cantina/retirada/${dia.id}`}
              >
                {situacao.estado === 'presencial' ? 'Mostrar o código' : 'Pegar pessoalmente'}
              </Link>
            )}
          </div>

          {situacao.estado === 'presencial' && situacao.podePedir && !trocandoParaPedido && (
            // O link discreto do docs/40 §6. Ele some sozinho quando o modo
            // deixa de ser presencial, porque `situacao` já não é essa.
            <button
              type="button"
              className="alu-cantina__elo-quieto"
              onClick={() => setTrocandoParaPedido(true)}
            >
              Prefiro fazer o pedido
            </button>
          )}

          {situacao.estado === 'presencial' && (
            <button
              type="button"
              // ⚠️ `alu-tecla--fina` NUNCA existiu em CSS (nasceu assim no
              // docs/38): as duas "desistir" desta tela renderizavam como
              // tecla PRINCIPAL, com o mesmo peso de "Fazer pedido". Aqui e
              // abaixo elas passam a usar as classes que existem — vazada e
              // pequena, que é o peso de uma reversão.
              className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
              disabled={desistir.isPending}
              onClick={() => desistir.mutate(dia.id)}
            >
              Desistir desta refeição
            </button>
          )}

          {jaPedi && (
            <button
              type="button"
              className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
              disabled={cancelar.isPending}
              onClick={() => cancelar.mutate(dia.id)}
            >
              Desistir desta refeição
            </button>
          )}

          {(salvar.isError || cancelar.isError || desistir.isError) && (
            <p className="alu-cantina__erro" role="alert">
              {mensagemDoErro(salvar.error ?? cancelar.error ?? desistir.error)}
            </p>
          )}
        </footer>
      )}
    </Bloco>
  );
}

/**
 * O CARD em Hoje — o resumo, com um destino.
 *
 * Fica entre a missão e a sequência porque a tela é ordenada por "o que eu faço
 * agora", e escolher o almoço é literalmente isso: é a ÚNICA coisa da tela que
 * expira. Abaixo da missão porque a missão é o herói, e isso não se mexe.
 *
 * Os estados, e a ORDEM entre eles, moram em `cardDaCantina` — o terceiro só
 * existe porque quem não pede não come, e os três últimos entraram com a
 * retirada presencial (docs/40 §6):
 *
 *   · prazo aberto sem resolver → o card cheio, com o prazo em magnitude;
 *   · retirada pendente hoje  → linha quieta com o caminho para o código;
 *   · já pedi                 → linha quieta com o resumo;
 *   · já retirei              → linha quieta com a hora. Factual, não festa;
 *   · prazo vencido, mas o dia aceita presencial → "ainda dá";
 *   · prazo vencido sem pedir → linha factual, para não caminhar até o balcão
 *                               à toa. Some depois do dia;
 *   · sem direito / sem cardápio → não existe. Some, não vira estado vazio.
 *
 * ⚠️ Nenhum XP e nenhuma cor de alerta: é o único elemento da área do aluno que
 * não fala de estudo, e puxá-lo para o vocabulário do jogo confundiria o que o
 * produto premia (docs/26 §1). Vale inclusive para o "Bom almoço!" — ele é
 * texto, não medalha.
 */
export function BlocoDaCantina() {
  const { data } = useCantinaDoAluno();
  const card = useMemo(() => cardDaCantina(data?.dias ?? []), [data]);

  if (!card) return null;
  const { tipo, dia } = card;
  const refeicao = ROTULO_DA_REFEICAO[dia.refeicao];

  // ⚠️ TODA saída quieta leva a `/cantina`. A tela não está na barra de quatro
  // destinos — de propósito —, então o card É a porta dela: uma linha sem link
  // deixa a tela inalcançável, que foi o defeito da primeira escrita.

  if (tipo === 'sem-reserva') {
    return (
      <p className="alu-cantina__linha-quieta">
        Sem {refeicao.toLowerCase()} reservado hoje.{' '}
        <Link to="/cantina">ver a cantina</Link>
      </p>
    );
  }

  if (tipo === 'presencial-aberto') {
    return (
      <p className="alu-cantina__linha-quieta">
        O prazo do pedido passou, mas dá para pegar seu {refeicao.toLowerCase()} na hora.{' '}
        <Link to={`/cantina/retirada/${dia.id}`}>mostrar o código</Link>
      </p>
    );
  }

  if (tipo === 'retirada') {
    return (
      <p className="alu-cantina__linha-quieta">
        {refeicao} de {rotuloDoDia(dia.data)}: você pega pessoalmente.{' '}
        <Link to={`/cantina/retirada/${dia.id}`}>mostrar o código</Link>
      </p>
    );
  }

  if (tipo === 'retirado') {
    return (
      <p className="alu-cantina__linha-quieta">
        {refeicao} retirado às {horaLegivel(dia.retiradoEm)}.{' '}
        <Link to="/cantina">ver a cantina</Link>
      </p>
    );
  }

  if (tipo === 'pedido-aberto' || tipo === 'pedido-fechado') {
    return (
      <p className="alu-cantina__linha-quieta">
        {refeicao} de {rotuloDoDia(dia.data)}:{' '}
        {resumoDoPedido(dia, dia.meuPedido ?? []) || 'nada marcado'}
        {' · '}
        {/* "Trocar" só enquanto dá. Depois do prazo o link continua — o pedido
            é a resposta a "o que eu vou comer amanhã" —, mas não promete uma
            edição que o servidor recusaria com 409. */}
        <Link to="/cantina">{tipo === 'pedido-aberto' ? 'trocar' : 'ver'}</Link>
      </p>
    );
  }

  const podeRetirar = situacaoDoDia(dia).podeRetirar;

  return (
    <Bloco
      fonte="cantina"
      olho="Cantina"
      className="alu-cantina__card"
      acao={<Link className="alu-bloco__link" to="/cantina">Fazer pedido</Link>}
    >
      <p className="alu-cantina__chamada">
        Escolha seu {refeicao.toLowerCase()} de {rotuloDoDia(dia.data)}
      </p>
      {/* O prazo em MAGNITUDE: perder este prazo custa a refeição, não um
          lembrete — e não há lembrete (docs/38 §7). */}
      <p className="alu-cantina__prazo-grande">{prazoLegivel(dia.pedidos_ate)}</p>
      {/* A segunda porta só existe quando o cardápio aceita as duas (docs/40
          §6). O card fica com "Fazer pedido" na ação e a retirada aqui embaixo:
          o pedido é o caminho que EXPIRA, e é ele que a magnitude está
          cobrando. */}
      {podeRetirar && (
        <p className="alu-cantina__segunda-porta">
          Ou{' '}
          <Link to={`/cantina/retirada/${dia.id}`}>pegue pessoalmente</Link>
          {' '}— sem escolher pratos, mostrando um código no balcão.
        </p>
      )}
    </Bloco>
  );
}

/** O 409 e o 422 da cantina são frases prontas para quem lê — passam inteiras
    em vez de virar "não foi possível". Mesma regra do editor da cantina. */
function mensagemDoErro(erro: unknown): string {
  if (erro instanceof Error && erro.message && !/→ \d{3}$/.test(erro.message)) return erro.message;
  return 'Não consegui salvar.';
}
