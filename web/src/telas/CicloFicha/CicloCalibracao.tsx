import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { Conjunta, PorMateria, TabelaSimuladosDoCiclo, Avancado } from './pecas';
import {
  useCiclo, useCriteriosDisponiveis, useEstatisticasCiclo, useSimulados,
} from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';

// CALIBRAÇÃO — "A prova estava boa?"
//
// É aqui que vive TODO o avançado de hoje, e ele deixa de precisar de toggle,
// porque a tela é dele. O toggle era uma tentativa pobre de esconder metade da
// densidade — e esconder metade não é o mesmo que separar por pergunta.
//
// A pergunta importa: ninguém abre a ferramenta querendo "o último simulado";
// abre querendo saber se a prova estava boa (C1).

export function CicloCalibracao() {
  const { id = '' } = useParams();
  const { data: ciclo } = useCiclo(id);
  const { data: todos = [] } = useSimulados();
  const [criterio, setCriterio] = useState('tio-leo');
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending, isError } = useEstatisticasCiclo(id, criterio);

  useTituloDaTela('Calibração');
  useRecorteDaTela(null);

  const doCiclo = todos.filter((s) => s.cicloId === id);

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="A prova estava boa?"
        para={`/ciclos/${id}`}
        destino={ciclo?.nome ?? 'a ficha do ciclo'}
        acoes={
          <SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />
        }
      />

      {isPending ? (
        <section className="card"><div className="empty-state">Calculando estatísticas…</div></section>
      ) : isError || !stats ? (
        <section className="card">
          <div className="empty-state">Erro ao calcular estatísticas. Verifique o backend.</div>
        </section>
      ) : (
        <section className="card ciclo-ficha">
          <Conjunta stats={stats} />
          <PorMateria recortes={stats.porMateria ?? []} />
          <TabelaSimuladosDoCiclo simulados={doCiclo} />
          {/* Sem toggle: a tela é do avançado. */}
          <Avancado stats={stats} />
        </section>
      )}
    </div>
  );
}
