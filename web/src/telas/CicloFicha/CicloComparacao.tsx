import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { Evolucao } from './pecas';
import {
  useCiclo, useCriteriosDisponiveis, useEstatisticasCiclo, useSimuladoPorSede, useSimulados,
} from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';
import type { EstatisticasCiclo, QuebraSimulado, Simulado } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

// COMPARAÇÃO — "Onde estamos diferentes?"
//
// Três comparações, e elas têm três origens de dado diferentes. O que a tela
// mostra é exatamente o que o servidor já resolveu, uma origem por seção:
//
//   SEDE × SEDE      `GET /simulados/{id}/por-sede`, uma prova por vez. É o
//                    servidor que calcula média, mediana e desvio de cada sede;
//                    a tela só põe as provas do ciclo em sequência.
//   CICLO × ANTERIOR `evolucaoTemporal`, com `cicloAnteriorMedia` por prova.
//   TURMA × TURMA    não existe. Continua declarado como lacuna, abaixo.
//
// ⚠️ Somar as notas aqui para inventar a comparação que falta é o mesmo erro
// que a Sprint 2 proibiu com a régua de corte: estatística que vive em dois
// lugares diverge no primeiro ajuste, e o front seria o lugar errado dos dois.
//
// ── Onde a R5 trabalha mais ──────────────────────────────────────────────
//
// Comparar é a tela em que a referência mais tenta virar dado. Duas decisões
// impedem isso:
//
//   · a REFERÊNCIA é cinza e fica ATRÁS. No trilho de sedes, quem é cinza é a
//     média da prova inteira — o eixo contra o qual as sedes se leem —, e as
//     marcas das sedes passam por cima dela.
//   · não há COR CATEGÓRICA. Pintar a sede A de um matiz e a B de outro
//     reinventa o semáforo por outro caminho: em duas telas o olho já teria
//     aprendido que um dos dois matizes é "o ruim". As sedes se distinguem por
//     POSIÇÃO no trilho e por rótulo escrito, e todas usam o mesmo papel de
//     dado — o que ainda funciona se um dia forem cinco sedes em vez de duas.

export function CicloComparacao() {
  const { id = '' } = useParams();
  const { data: ciclo } = useCiclo(id);
  const { data: todos = [] } = useSimulados();
  const [criterio, setCriterio] = useState('tio-leo');
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending, isError } = useEstatisticasCiclo(id, criterio);

  useTituloDaTela('Comparação');
  useRecorteDaTela(null);

  // A ordem é a da aplicação, não a do alfabeto: comparar sedes prova a prova
  // só faz sentido se a sequência for a do calendário — é o que mostra se a
  // diferença apareceu de uma vez ou vinha crescendo.
  const doCiclo = todos
    .filter((s) => s.cicloId === id && !s.anulado && s.notaConfiavel)
    .slice()
    .sort((a, b) => (a.dataAplicacao || '').localeCompare(b.dataAplicacao || ''));

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="Onde estamos diferentes?"
        para={`/ciclos/${id}`}
        destino={ciclo?.nome ?? 'a ficha do ciclo'}
        acoes={<SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />}
      />
      <p className="ciclo-comparacao__intro">
        Entre as sedes, contra o ciclo anterior — e o que ainda não dá para comparar.
      </p>

      {isPending ? (
        <section className="card"><div className="empty-state">Calculando…</div></section>
      ) : isError || !stats ? (
        <section className="card">
          <div className="empty-state">Erro ao calcular estatísticas. Verifique o backend.</div>
        </section>
      ) : (
        <>
          <EntreAsSedes provas={doCiclo} stats={stats} />

          <section className="card ciclo-ficha">
            <div className="section__title">Contra o ciclo anterior</div>
            <div className="section__subtitle">
              {stats.cicloAnterior
                ? `A linha cheia é este ciclo; a tracejada, ${stats.cicloAnterior.nome} — referência, atrás do dado.`
                : 'Não há ciclo anterior no ano para servir de referência: só a série deste ciclo é desenhada.'}
            </div>
            <Evolucao stats={stats} />
          </section>

          <EntreAsTurmas />
        </>
      )}
    </div>
  );
}

// ─── Sede × sede ─────────────────────────────────────────────────────────

function EntreAsSedes({
  provas, stats,
}: {
  provas: readonly Simulado[];
  stats: EstatisticasCiclo;
}) {
  return (
    <section className="card ciclo-ficha">
      <div className="section__title">Entre as sedes</div>
      <div className="section__subtitle">
        Uma prova por linha, na ordem em que foram aplicadas. Cada marca é uma sede na escala de 0
        a 10; o traço cinza é a média da prova inteira, e o fio de ouro é o corte que a régua exige
        naquela matéria.
      </div>

      {provas.length === 0 ? (
        <p className="section__subtitle">Nenhuma prova deste ciclo entrou nos agregados ainda.</p>
      ) : (
        <div className="ciclo-sedes">
          {provas.map((prova) => (
            <LinhaDeSede
              key={prova.id}
              prova={prova}
              corte={corteDaProva(prova, stats)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

/**
 * O corte da matéria da prova, CONSULTADO no payload — nunca recalculado.
 *
 * `porMateria[].corte` já é o que a régua escolhida exige naquela matéria, e é
 * o mesmo número que o mapa da calibração desenha. Sem matéria (prova
 * agregada) ou sem recorte, não há régua aplicável e o fio simplesmente não é
 * desenhado: encostá-lo num valor plausível seria inventar a régua.
 */
function corteDaProva(prova: Simulado, stats: EstatisticasCiclo): number | null {
  const codigo = prova.materia?.codigo;
  if (!codigo) return null;
  const recorte = (stats.porMateria ?? []).find((r) => r.materia.codigo === codigo);
  return recorte?.corte ?? null;
}

function LinhaDeSede({ prova, corte }: { prova: Simulado; corte: number | null }) {
  const { data: sedes, isPending, isError } = useSimuladoPorSede(prova.id);

  const medidas = (sedes ?? []).filter(
    (s): s is QuebraSimulado & { media: number } => s.media != null,
  );
  const maior = extremo(medidas, 'maior');
  const menor = extremo(medidas, 'menor');
  // ⚠️ A conta é `length > 1`, não `maior !== menor`: com duas sedes de média
  // idêntica o `reduce` devolve o MESMO objeto nas duas pontas, e comparar por
  // identidade faria a linha dizer "uma sede só" justamente no caso em que as
  // duas foram medidas e empataram — que é uma informação, não uma ausência.
  const diferenca = medidas.length > 1 && maior && menor ? maior.media - menor.media : null;

  return (
    <div className="ciclo-sedes__linha">
      {/* A linha inteira do nome é o alvo, não só o rótulo: duas linhas de
          texto num link fecham os 44px sem inflar a lista com padding. */}
      <Link className="ciclo-sedes__prova" to={`/simulados/${prova.id}`}>
        <span className="ciclo-sedes__nome">{prova.rotuloCurto || prova.nome}</span>
        <span className="ciclo-sedes__contexto">
          {[prova.materia?.nome, prova.tipo === 'fase_2' ? 'F2' : 'F1', prova.dataAplicacao]
            .filter(Boolean)
            .join(' · ')}
        </span>
      </Link>

      {isPending ? (
        <div className="ciclo-sedes__vazio">Carregando as sedes…</div>
      ) : isError ? (
        // A falha é operacional, e é o único vermelho desta tela (R4). Ela não
        // pode virar "as sedes estão iguais": uma linha em branco seria lida
        // como ausência de diferença.
        <div className="ciclo-sedes__falha">Não consegui ler a quebra por sede desta prova.</div>
      ) : medidas.length === 0 ? (
        <div className="ciclo-sedes__vazio">Esta prova ainda não tem média por sede.</div>
      ) : (
        <>
          <TrilhoDeSedes medidas={medidas} media={prova.media} corte={corte} />
          <div className="ciclo-sedes__diferenca">
            {diferenca == null
              ? 'uma sede só'
              : diferenca === 0
                ? 'as sedes empataram'
                : `${fmtNota(diferenca)} entre ${maior?.sede ?? '—'} e ${menor?.sede ?? '—'}`}
          </div>
        </>
      )}
    </div>
  );
}

function extremo(
  medidas: ReadonlyArray<QuebraSimulado & { media: number }>,
  qual: 'maior' | 'menor',
): (QuebraSimulado & { media: number }) | null {
  if (medidas.length === 0) return null;
  return medidas.reduce((melhor, atual) =>
    (qual === 'maior' ? atual.media > melhor.media : atual.media < melhor.media) ? atual : melhor);
}

/**
 * O trilho: escala fixa de 0 a 10, uma marca por sede.
 *
 * A escala é FIXA e vale para todas as linhas — normalizar cada prova pelo seu
 * próprio intervalo faria 0,1 de diferença desenhar igual a 2,0, que é a mesma
 * mentira gráfica que a `Sparkline` acabou de perder.
 */
function TrilhoDeSedes({
  medidas, media, corte,
}: {
  medidas: ReadonlyArray<QuebraSimulado & { media: number }>;
  media: number | null;
  corte: number | null;
}) {
  const largura = 520;
  const altura = 42;
  const margem = 10;
  const util = largura - margem * 2;
  const eixoY = 17;
  // O nome da sede fica ABAIXO do trilho: acima ele cruzaria o fio de ouro
  // sempre que a sede caísse perto do corte — e o corte é justamente onde as
  // sedes mais interessam.
  const rotuloY = 36;
  const x = (valor: number) => margem + (Math.min(10, Math.max(0, valor)) / 10) * util;

  return (
    <svg
      className="ciclo-sedes__trilho"
      width={largura}
      height={altura}
      viewBox={`0 0 ${largura} ${altura}`}
      role="img"
      aria-label={medidas
        .map((s) => `${s.sede ?? 'sede'}: ${fmtNota(s.media)}`)
        .join('; ')}
    >
      {/* A REFERÊNCIA vai atrás: o trilho e a média da prova inteira. */}
      <line
        x1={margem} x2={margem + util} y1={eixoY} y2={eixoY}
        stroke="var(--sas-referencia-fraca)" strokeWidth="6" strokeLinecap="round"
      />
      {media != null && (
        <line
          x1={x(media).toFixed(1)} x2={x(media).toFixed(1)} y1={eixoY - 10} y2={eixoY + 10}
          stroke="var(--sas-referencia)" strokeWidth="1.5"
        >
          <title>{`Média da prova: ${fmtNota(media)}`}</title>
        </line>
      )}

      {/* R2 · a régua é ouro e está sempre desenhada — quando existe. */}
      {corte != null && (
        <line
          x1={x(corte).toFixed(1)} x2={x(corte).toFixed(1)} y1={2} y2={eixoY + 11}
          stroke="var(--sas-valor)" strokeWidth="1.5" strokeDasharray="4 3"
        >
          <title>{`Corte: ${fmtNota(corte)}`}</title>
        </line>
      )}

      {/* O DADO por cima. R1: a sede acima do corte é preenchida, a de baixo é
          vazada — a mesma forma do histograma e do selo, para que "abaixo" se
          leia igual em toda a coordenação. Sem corte não há o que ancorar, e
          todas saem preenchidas em vez de fingir um veredito. */}
      {medidas.map((sede, i) => {
        const abaixo = corte != null && sede.media < corte;
        return (
          <g key={sede.sede ?? i}>
            <circle
              cx={x(sede.media).toFixed(1)}
              cy={eixoY}
              r="6"
              fill={abaixo ? 'var(--sas-superficie)' : 'var(--sas-dado)'}
              stroke="var(--sas-dado)"
              strokeWidth={abaixo ? 2 : 0}
            >
              <title>{`${sede.sede ?? 'Sede'}: ${fmtNota(sede.media)}`}</title>
            </circle>
            <text
              x={x(sede.media).toFixed(1)}
              y={rotuloY}
              textAnchor="middle"
              fontSize="10"
              fill="var(--sas-texto-2)"
            >
              {sede.sede}
            </text>
          </g>
        );
      })}
      {/* Sem marcas de 0 e 10 em cada linha: a escala é a mesma em todas e
          está dita uma vez, no subtítulo da seção (R7). Repeti-la em doze
          trilhos seria doze vezes a mesma informação. */}
    </svg>
  );
}

// ─── Turma × turma ───────────────────────────────────────────────────────

function EntreAsTurmas() {
  return (
    <section className="card">
      <div className="empty-state">
        <p>Comparação entre turmas ainda não existe.</p>
        <p className="empty-state__hint">
          A média por turma teria de vir do servidor, como já vem a média por sede.
          Calculá-la aqui somando as notas dos alunos seria refazer estatística no cliente — que é
          exatamente o que a régua de corte ensinou a não fazer, depois de a mesma regra existir em
          três lugares e divergir.
        </p>
      </div>
    </section>
  );
}
