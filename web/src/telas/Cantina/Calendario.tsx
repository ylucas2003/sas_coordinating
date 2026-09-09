import { useMemo, useState } from 'react';

import {
  fraseDaQuebra, isoDoDia, quebraDaContagem, rotuloDaContagem, somarContagens,
} from '../../dominio/cantina';
import { useCalendarioDaCantina, useMinhaCantina } from '../../hooks/cantina';
import { BotaoDaGrade } from './BotaoDaGrade';
import { AvisoSemPublico } from './AvisoSemPublico';
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
  const { data: minha } = useMinhaCantina();
  // Só o que está PUBLICADO vai para a parede: rascunho na parede é promessa
  // que a cozinha ainda pode desfazer.
  const publicadosDoMes = useMemo(
    () => dias.filter((d) => d.estado === 'aberto' || d.estado === 'fechado'),
    [dias],
  );

  function andar(passo: number) {
    const d = new Date(ano, mes + passo, 1);
    setAno(d.getFullYear());
    setMes(d.getMonth());
  }

  const rascunhos = dias.filter((d) => d.estado === 'rascunho').length;
  const publicados = dias.filter((d) => d.estado === 'aberto' || d.estado === 'fechado').length;

  // O mês somado, só para DECODIFICAR o "44+3" das células: a linha aparece no
  // mês em que existe retirada na hora e some no mês em que não existe (docs/40
  // §10.1). Sem ela, a face compacta da célula seria charada — e é a cantina,
  // não a coordenação, quem passa o dia inteiro nesta tela.
  const contagemDoMes = somarContagens(dias);
  const quebra = quebraDaContagem(contagemDoMes);

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
                  + (rascunhos ? ` · ${rascunhos} em rascunho` : '')
                  + (quebra
                    ? ` · ${contagemDoMes.pedidos} ${rotuloDaContagem(contagemDoMes)}`
                      + ` · ${fraseDaQuebra(quebra)}`
                    : '')}
          </p>
        </div>
        <div className="cant-cabeca__acoes">
          {/* A grade para o MURAL (docs/40 §12.5.3). Não é o XLSX de outra
              forma: não se prega planilha na parede, e é a folha impressa que
              a cozinha usa hoje. */}
          <BotaoDaGrade dias={publicadosDoMes} cantina={minha?.nome ?? null} />
          <NavegadorDeMes ano={ano} mes={mes} onAndar={andar} />
        </div>
      </header>

      <AvisoSemPublico refeicoes={['almoco', 'janta']} />

      {/* A célula VAZIA de um dia futuro é clicável — é clicando nela que a
          cantina cria o cardápio. A de um dia que já passou, não: dia passado
          nunca aceita pedido, então criar ali é sempre engano de navegação, e
          foi assim que os três primeiros cardápios de produção nasceram
          invisíveis.

          Dia passado COM cardápio segue clicável: a cantina quer poder abrir o
          que serviu e quem pediu. O que some é o convite a criar. */}
      <GradeDeCardapios
        ano={ano}
        mes={mes}
        dias={dias}
        href={(data, refeicao, dia) =>
          (dia || data >= isoDoDia(new Date()) ? `/cardapios/${data}/${refeicao}` : null)}
      />
    </div>
  );
}
