import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import {
  instrucaoDoBloco, marcadasNoBloco, pendenciaDoPedido, podeMarcarMais, prazoAberto,
  prazoLegivel, resumoDoPedido, ROTULO_DA_REFEICAO, rotuloDoDia,
} from '../../dominio/cantina';
import { useCancelarPedido, useCantinaDoAluno, useSalvarPedido } from '../../hooks/cantina';
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
 * Um dia: o cardápio, a escolha e o prazo.
 *
 * A seleção é estado LOCAL semeado do servidor, e não controlada por ele: o
 * aluno marca três coisas antes de enviar, e um round-trip por clique
 * transformaria a escolha numa fila de esperas.
 */
export function DiaDaCantina({ dia }: { dia: DiaDoAluno }) {
  const [selecao, setSelecao] = useState<ReadonlySet<string>>(() => new Set(dia.meuPedido ?? []));
  const salvar = useSalvarPedido();
  const cancelar = useCancelarPedido();

  // Ressemeia quando o pedido muda no servidor — outra aba, ou a confirmação
  // da própria gravação. `join` e não o array: a identidade do array muda a
  // cada refetch, e o efeito rodaria por nada.
  const assinatura = (dia.meuPedido ?? []).join(',');
  useEffect(() => {
    setSelecao(new Set(assinatura ? assinatura.split(',') : []));
  }, [assinatura]);

  const aberto = prazoAberto(dia.pedidos_ate);
  const pendencia = useMemo(() => pendenciaDoPedido(dia, selecao), [dia, selecao]);
  const jaPedi = dia.meuPedido != null;
  const mudou = assinatura !== [...selecao].sort().join(',');

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
        <span className={`alu-cantina__prazo${aberto ? '' : ' alu-cantina__prazo--fechado'}`}>
          {prazoLegivel(dia.pedidos_ate)}
        </span>
      }
      className="alu-cantina__dia"
    >
      {!aberto && (
        <p className="alu-cantina__aviso">
          {jaPedi
            ? `Seu pedido: ${resumoDoPedido(dia, dia.meuPedido ?? [])}`
            : 'O prazo passou e você não pediu esta refeição.'}
        </p>
      )}

      {aberto && dia.blocos.map((bloco, i) => (
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

      {aberto && (
        <footer className="alu-cantina__acoes">
          {/* A pendência aparece ANTES do botão e no lugar do erro: o aluno lê
              o que falta sem ter de clicar para descobrir. */}
          {pendencia && <p className="alu-cantina__pendencia">{pendencia}</p>}

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
                : 'Confirmar pedido'}
          </button>

          {jaPedi && (
            <button
              type="button"
              className="alu-tecla alu-tecla--fina"
              disabled={cancelar.isPending}
              onClick={() => cancelar.mutate(dia.id)}
            >
              Desistir desta refeição
            </button>
          )}

          {(salvar.isError || cancelar.isError) && (
            <p className="alu-cantina__erro" role="alert">
              {(salvar.error ?? cancelar.error) instanceof Error
                ? (salvar.error ?? cancelar.error)!.message
                : 'Não consegui salvar.'}
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
 * Quatro estados, e o terceiro só existe porque quem não pede não come:
 *
 *   · prazo aberto sem pedido → o card cheio, com o prazo em magnitude;
 *   · já pedi                 → linha quieta com o resumo;
 *   · prazo vencido sem pedir → linha factual, para não caminhar até o balcão
 *                               à toa. Some depois do dia;
 *   · sem direito / sem cardápio → não existe. Some, não vira estado vazio.
 *
 * ⚠️ Nenhum XP e nenhuma cor de alerta: é o único elemento da área do aluno que
 * não fala de estudo, e puxá-lo para o vocabulário do jogo confundiria o que o
 * produto premia (docs/26 §1).
 */
export function BlocoDaCantina() {
  const { data } = useCantinaDoAluno();

  const dia = useMemo(() => {
    if (!data?.dias.length) return null;
    // O PRÓXIMO prazo aberto — não o próximo dia. Um cardápio de quarta com
    // prazo até terça é mais urgente que o de amanhã já fechado.
    const abertos = data.dias.filter((d) => prazoAberto(d.pedidos_ate));
    if (abertos.length) return abertos[0];
    // Nenhum aberto: só interessa dizer que hoje ficou sem, e só hoje.
    const hoje = new Date().toISOString().slice(0, 10);
    return data.dias.find((d) => d.data === hoje && d.meuPedido == null) ?? null;
  }, [data]);

  if (!dia) return null;

  const aberto = prazoAberto(dia.pedidos_ate);
  const jaPedi = dia.meuPedido != null;

  if (!aberto) {
    return (
      <p className="alu-cantina__linha-quieta">
        Sem {ROTULO_DA_REFEICAO[dia.refeicao].toLowerCase()} reservado hoje.
      </p>
    );
  }

  if (jaPedi) {
    return (
      <p className="alu-cantina__linha-quieta">
        {ROTULO_DA_REFEICAO[dia.refeicao]} de {rotuloDoDia(dia.data)}:{' '}
        {resumoDoPedido(dia, dia.meuPedido ?? []) || 'nada marcado'}
        {' · '}
        <Link to="/cantina">trocar</Link>
      </p>
    );
  }

  return (
    <Bloco
      fonte="cantina"
      olho="Cantina"
      className="alu-cantina__card"
      acao={<Link className="alu-bloco__link" to="/cantina">Escolher</Link>}
    >
      <p className="alu-cantina__chamada">
        Escolha seu {ROTULO_DA_REFEICAO[dia.refeicao].toLowerCase()} de {rotuloDoDia(dia.data)}
      </p>
      {/* O prazo em MAGNITUDE: perder este prazo custa a refeição, não um
          lembrete — e não há lembrete (docs/38 §7). */}
      <p className="alu-cantina__prazo-grande">{prazoLegivel(dia.pedidos_ate)}</p>
    </Bloco>
  );
}
