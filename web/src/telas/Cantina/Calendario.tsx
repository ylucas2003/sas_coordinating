import { useMemo, useState } from 'react';

import { useCalendarioDaCantina } from '../../hooks/cantina';
import { GradeDeCardapios, janelaDoMes, NavegadorDeMes } from './GradeDeCardapios';

// O CALENDÁRIO — a tela de entrada da cantina.
//
// A pergunta que ela responde é "o que falta lançar?", e por isso o mês inteiro
// aparece de uma vez em vez de uma lista dos próximos dias: quem monta cardápio
// pensa em semana, e um buraco no meio do mês só se enxerga vendo o mês.
//
// A grade em si mora em `GradeDeCardapios` porque a coordenação lê a mesma
// coisa — o que muda entre as duas é só para onde o clique leva.

export function Calendario() {
  const hoje = new Date();
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth());

  const [de, ate] = useMemo(() => janelaDoMes(ano, mes), [ano, mes]);
  const { data: dias = [], isLoading, isError } = useCalendarioDaCantina(de, ate);

  function andar(passo: number) {
    const d = new Date(ano, mes + passo, 1);
    setAno(d.getFullYear());
    setMes(d.getMonth());
  }

  const rascunhos = dias.filter((d) => d.estado === 'rascunho').length;
  const publicados = dias.filter((d) => d.estado === 'aberto' || d.estado === 'fechado').length;

  return (
    <div className="cant-tela">
      <header className="cant-cabeca">
        <div>
          <h1 className="cant-titulo">Cardápios</h1>
          {/* Dado vivo, não descrição: ao abrir, o que interessa é quanto já
              está publicado e quanto ficou em rascunho. */}
          <p className="cant-sub">
            {isError
              ? 'Não consegui carregar o mês.'
              : isLoading
                ? 'Carregando…'
                : `${publicados} publicado${publicados === 1 ? '' : 's'}`
                  + (rascunhos ? ` · ${rascunhos} em rascunho` : '')}
          </p>
        </div>
        <NavegadorDeMes ano={ano} mes={mes} onAndar={andar} />
      </header>

      {/* Toda célula é clicável, inclusive a vazia: é clicando no vazio que a
          cantina cria o cardápio daquele dia. */}
      <GradeDeCardapios
        ano={ano}
        mes={mes}
        dias={dias}
        href={(data, refeicao) => `/cardapios/${data}/${refeicao}`}
      />
    </div>
  );
}
