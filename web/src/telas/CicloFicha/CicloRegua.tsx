import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { Kpi } from '../../componentes/ui/Kpi';
import { BlocoPendenciasCanvas } from './PendenciasCanvas';
import { compararPorDistancia, distanciaAoCorte, formatarDistancia } from '../../dominio/selo';
import {
  useCiclo, useClassificacaoCiclo, useCriteriosDisponiveis,
} from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';
import { fmtNota } from '../../util/formato';

// RÉGUA — "Quem passou?"
//
// A classificação do ciclo contra o critério em vigor, e os cortados.
//
// A lista abre pela DISTÂNCIA DO CORTE, ascendente (R6), como toda tabela de
// aluno do produto: sem a cor, é a ordem que entrega quem precisa de atenção.
// O ordenador aparece nomeado, porque uma ordem que o coordenador não sabe
// qual é não entrega nada.

export function CicloRegua() {
  const { id = '' } = useParams();
  const { data: ciclo } = useCiclo(id);
  const [criterio, setCriterio] = useState('tio-leo');
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: classificacao, isPending, isError } = useClassificacaoCiclo(id || null, criterio);

  useTituloDaTela('Régua');
  useRecorteDaTela(null);

  const linhas = useMemo(() => {
    if (!classificacao) return [];
    return classificacao.alunos
      .map((a) => ({ aluno: a, distancia: distanciaAoCorte(a, classificacao.criterio) }))
      .sort(
        (x, y) =>
          compararPorDistancia(x.distancia, y.distancia) ||
          x.aluno.nome.localeCompare(y.aluno.nome, 'pt-BR'),
      );
  }, [classificacao]);

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="Quem passou?"
        para={`/ciclos/${id}`}
        destino={ciclo?.nome ?? 'a ficha do ciclo'}
        acoes={<SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />}
      />

      {isPending ? (
        <section className="card"><div className="empty-state">Classificando…</div></section>
      ) : isError || !classificacao ? (
        <section className="card">
          <div className="empty-state">Não consegui classificar este ciclo com esta régua.</div>
        </section>
      ) : (
        <>
          <div className="kpi-grid kpi-grid--cartoes">
            <Kpi rotulo="Alunos classificados" valor={classificacao.total} />
            <Kpi rotulo="Cortados" valor={classificacao.cortados} sufixo={` de ${classificacao.total}`} />
            <Kpi rotulo="Régua em vigor" valor={classificacao.criterio.nome} />
          </div>

          <section className="card">
            <div className="painel-tabela-ordem">
              <span className="painel-tabela-ordem__total">
                {linhas.length} {linhas.length === 1 ? 'aluno' : 'alunos'}
              </span>
              <span className="painel-tabela-ordem__pilula">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  strokeWidth="2" strokeLinecap="round" aria-hidden="true">
                  <path d="M12 5v14M7 14l5 5 5-5" />
                </svg>
                distância do corte, pior primeiro
              </span>
            </div>

            <div className="painel-tabela-wrap">
              <table className="painel-tabela">
                <thead>
                  <tr>
                    <th className="painel-tabela__th-aluno">Aluno</th>
                    <th>Média</th>
                    <th>Situação</th>
                    <th className="painel-tabela__th-dist">Distância</th>
                  </tr>
                </thead>
                <tbody>
                  {linhas.map(({ aluno, distancia }) => (
                    <tr key={aluno.alunoId}>
                      <td className="painel-tabela__td-aluno">
                        <Link className="painel-tabela__aluno-link" to={`/alunos/${aluno.alunoId}`}>
                          {aluno.nome}
                        </Link>
                      </td>
                      <td>{fmtNota(aluno.media)}</td>
                      {/* A situação é PALAVRA, não cor: o motivo já diz qual
                          matéria e qual mínimo (R4/R7). */}
                      <td className="ciclo-regua__motivo">
                        {aluno.aprovado ? 'Passou' : (aluno.motivo ?? 'Cortado')}
                      </td>
                      <td className="painel-tabela__td-dist">
                        <span
                          className={`painel-tabela__dist${
                            distancia != null && distancia < 0 ? ' painel-tabela__dist--abaixo' : ''
                          }${distancia == null ? ' painel-tabela__dist--vazia' : ''}`}
                        >
                          {distancia == null ? '—' : formatarDistancia(distancia)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* As pendências vivem aqui: "quem passou?" não tem resposta honesta
              enquanto houver prova sem nota lançada. */}
          <BlocoPendenciasCanvas cicloId={id} canvasEstado={ciclo?.canvasEstado ?? null} />
        </>
      )}
    </div>
  );
}
