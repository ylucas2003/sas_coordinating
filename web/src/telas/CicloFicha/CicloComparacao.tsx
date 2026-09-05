import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { Evolucao } from './pecas';
import { useCiclo, useCriteriosDisponiveis, useEstatisticasCiclo } from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';

// COMPARAÇÃO — "Onde estamos diferentes?"
//
// ⚠️ ENTREGA PARCIAL, e está registrado assim em docs/37 em vez de escondido.
//
// O brief pede três comparações: sede × sede, turma × turma, e este ciclo
// contra o anterior. Só a TERCEIRA tem dado hoje — `evolucaoTemporal` traz
// `cicloAnteriorMedia` por prova, e é o que a `Evolucao` desenha.
//
// As duas primeiras exigem endpoint que não existe: `GET /ciclos/{id}/estatisticas`
// não recorta por sede nem por turma, e o único corte por sede do produto é
// `useSimuladoPorSede`, que é por SIMULADO. Inventar a comparação no front
// somando notas por sede seria reimplementar estatística no cliente — o mesmo
// erro que a Sprint 2 proibiu com a régua de corte.
//
// A tela diz o que falta, em vez de fingir que a pergunta foi respondida.

export function CicloComparacao() {
  const { id = '' } = useParams();
  const { data: ciclo } = useCiclo(id);
  const [criterio, setCriterio] = useState('tio-leo');
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending, isError } = useEstatisticasCiclo(id, criterio);

  useTituloDaTela('Comparação');
  useRecorteDaTela(null);

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="Onde estamos diferentes?"
        para={`/ciclos/${id}`}
        destino={ciclo?.nome ?? 'a ficha do ciclo'}
        acoes={<SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />}
      />

      {isPending ? (
        <section className="card"><div className="empty-state">Calculando…</div></section>
      ) : isError || !stats ? (
        <section className="card">
          <div className="empty-state">Erro ao calcular estatísticas. Verifique o backend.</div>
        </section>
      ) : (
        <>
          <section className="card ciclo-ficha">
            <Evolucao stats={stats} />
          </section>

          <section className="card">
            <div className="empty-state">
              <p>Comparação entre sedes e entre turmas ainda não existe.</p>
              <p className="empty-state__hint">
                O cálculo por sede e por turma precisa vir do servidor: somar as notas aqui seria
                refazer estatística no cliente, que é o que a régua de corte ensinou a não fazer.
                Por enquanto esta tela compara este ciclo com o anterior.
              </p>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
