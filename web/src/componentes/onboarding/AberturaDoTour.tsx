import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { ancoraDoTour, montarTour } from '../../dominio/tour';
import { useCiclos, useSimulados } from '../../hooks/consultas';
import * as sessao from '../../servicos/sessao';
import { hojeISO } from '../../util/data';
import { jaViuOTour, marcarTourVisto } from './memoria';
import { Tour } from './Tour';

/**
 * O gatilho do tour — e a única coisa que as duas telas precisam montar.
 *
 * O botão fica dentro da tela, e não na topbar como a prancheta desenha, por
 * duas razões que se somam: a topbar do produto é migalha, tema e avatar (fase
 * 1 do docs/39), e um "?" permanente lá em cima seria ajuda de PRODUTO, quando
 * este tour cobre um assunto — ciclo e prova. Perto do assunto ele promete o
 * que entrega.
 *
 * ⚠️ A ABERTURA SOZINHA acontece em UM lugar só, o Painel, e é o que dá sentido
 * ao "já vi": sem ela, persistir a leitura não serviria a ninguém — quem clica
 * no botão está pedindo o tour de novo. Quem chega pela primeira vez cai na
 * home, e é lá que o tour se apresenta; no hub de Provas ele é sempre a
 * escolha de quem quer rever.
 */
export function AberturaDoTour({ abrirSozinho = false }: { abrirSozinho?: boolean }) {
  const [aberto, setAberto] = useState(false);
  const gatilho = useRef<HTMLButtonElement>(null);
  // Uma abertura automática por montagem. Sem esta trava, fechar o tour e
  // deixar a aba aberta o traria de volta no próximo render em que a consulta
  // se resolvesse de novo.
  const jaAbriuSozinho = useRef(false);

  const quem = sessao.nome();
  const hoje = hojeISO();

  const { data: ciclos = [], isPending: ciclosPendentes } = useCiclos();
  const { data: simulados = [], isPending: provasPendentes } = useSimulados();

  const passos = useMemo(
    () => montarTour(ancoraDoTour(ciclos, simulados, hoje)),
    [ciclos, simulados, hoje],
  );

  // Fechar é fechar, venha do Esc, do "Pular", do "Entendi" ou de um destino:
  // em todos os casos a pessoa viu o tour e não quer vê-lo amanhã de novo.
  const fechar = useCallback(() => {
    marcarTourVisto(quem);
    setAberto(false);
  }, [quem]);

  useEffect(() => {
    if (!abrirSozinho || jaAbriuSozinho.current) return;
    // Só depois das duas consultas: abrir antes mostraria o primeiro passo sem
    // a porta, que apareceria sozinha meio segundo depois.
    if (ciclosPendentes || provasPendentes) return;
    if (jaViuOTour(quem)) {
      // Marca a trava mesmo sem abrir: quem já viu não deve reavaliar isto a
      // cada consulta que volta.
      jaAbriuSozinho.current = true;
      return;
    }
    jaAbriuSozinho.current = true;
    setAberto(true);
  }, [abrirSozinho, ciclosPendentes, provasPendentes, quem]);

  return (
    <>
      <button
        ref={gatilho}
        type="button"
        className="tour-gatilho"
        onClick={() => setAberto(true)}
        aria-haspopup="dialog"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" aria-hidden="true">
          <circle cx="12" cy="12" r="8.6" />
          <path d="M9.6 9.4a2.5 2.5 0 1 1 3.4 2.3c-.7.3-1 .8-1 1.6M12 16.6v.4" />
        </svg>
        {/* O rótulo é o escopo. "Conheça o SAS" prometeria o produto inteiro e
            entregaria seis passos de ciclo e prova. */}
        Como se lê um ciclo e uma prova
      </button>
      {aberto && <Tour passos={passos} aoFechar={fechar} focoDeVolta={gatilho} />}
    </>
  );
}
