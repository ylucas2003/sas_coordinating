import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useTituloDaTela } from '../../componentes/layout/migalhas';
import { passosDaApresentacao, professoresDaMateria, type AbaDoCronograma } from '../../dominio/cronograma';
import { AnoDoCronograma } from './AnoDoCronograma';
import { MateriasEAssuntos, ProfessorNoAno, QuemDaCadaAssunto } from './ListasDoCronograma';
import { CAL, fmtInteiro, PLANO } from './plano';

// PROPOSTA DE CRONOGRAMA — o plano de 2027 do 3º e cursinho, para PLANEJAR e APRESENTAR (não é acompanhamento: nada
// aqui compara o plano com o que foi dado).
//
// A porta é o card do Painel do 3º e cursinho. O dado é estático, gerado fora do produto (ver `plano.ts`): aulas de
// 50 min por matéria (parte média de 2024–26), por professor (a parte média dele) e, para cada professor, o mesmo
// conjunto de 2026, com o NOME QUE ELE USA (título da aula ou capítulo da apostila). A revisão de fim de ano é à
// parte; cada item fica na semana em que foi dado em 2026, porque o calendário se repete.
//
// Quatro abas, e TODAS começam com o mínimo: cada clique abre um nível (visão geral → recorte → detalhe). A aba, a
// matéria e o professor ficam na URL (`?ver=professor&materia=Química&professor=…`), para o link poder ser mandado;
// o que está aberto em cada lista é estado da tela.
//
// "Apresentar" põe a tela em tela cheia e anda por passos com as setas: o ano; depois, para cada matéria, os
// assuntos, quem dá, e cada professor. "Ocultar detalhe técnico" tira peso na prova, números de 2026 e nomes de
// grupo do SAS — para quando o público forem os professores.

const ABAS: { id: AbaDoCronograma; rotulo: string }[] = [
  { id: 'ano', rotulo: 'O ano' },
  { id: 'materias', rotulo: 'Matérias e assuntos' },
  { id: 'quem', rotulo: 'Assuntos e professores' },
  { id: 'professor', rotulo: 'Cada professor no ano' },
];

const PASSOS = passosDaApresentacao(PLANO);

export function Cronograma() {
  useTituloDaTela('Proposta de cronograma');
  const [params, setParams] = useSearchParams();
  const aba = (ABAS.find((a) => a.id === params.get('ver'))?.id ?? 'ano') as AbaDoCronograma;
  const materia = PLANO.materias.find((m) => m.materia === params.get('materia'))?.materia
    ?? (PLANO.materias[0]?.materia as string);
  const professor = params.get('professor') ?? professoresDaMateria(PLANO, materia)[0]?.professor ?? '';

  const [abertos, setAbertos] = useState<ReadonlySet<string>>(() => new Set());
  const [tecnico, setTecnico] = useState(true);
  const [agrupar, setAgrupar] = useState<'assunto' | 'professor'>('assunto');
  const [apresentando, setApresentando] = useState(false);
  const [passo, setPasso] = useState(0);
  const raiz = useRef<HTMLDivElement>(null);

  const ir = useCallback((mudanca: { ver?: AbaDoCronograma; materia?: string; professor?: string | null }) => {
    setParams((atual) => {
      const novo = new URLSearchParams(atual);
      if (mudanca.ver) novo.set('ver', mudanca.ver);
      if (mudanca.materia) {
        novo.set('materia', mudanca.materia);
        if (mudanca.professor === undefined) novo.delete('professor');
      }
      if (mudanca.professor) novo.set('professor', mudanca.professor);
      return novo;
    }, { replace: !mudanca.ver });
  }, [setParams]);

  const aberto = useCallback((chave: string) => abertos.has(chave), [abertos]);
  const alternar = useCallback((chave: string) => {
    setAbertos((atual) => {
      const novo = new Set(atual);
      if (novo.has(chave)) novo.delete(chave);
      else novo.add(chave);
      return novo;
    });
  }, []);
  const abrirMaterias = useCallback((abrir: boolean) => {
    setAbertos((atual) => {
      const novo = new Set([...atual].filter((k) => !k.startsWith('ano|')));
      if (abrir) for (const m of PLANO.materias) novo.add(`ano|${m.materia}`);
      return novo;
    });
  }, []);
  const irParaProfessor = useCallback((m: string, p: string) => ir({ ver: 'professor', materia: m, professor: p }), [ir]);

  // ─── apresentação ─────────────────────────────────────────────────────────
  const irParaPasso = useCallback((i: number) => {
    const n = Math.max(0, Math.min(PASSOS.length - 1, i));
    const p = PASSOS[n];
    if (!p) return;
    setPasso(n);
    setAbertos(new Set());
    ir({ ver: p.aba, ...(p.materia ? { materia: p.materia } : {}), ...(p.professor ? { professor: p.professor } : {}) });
    raiz.current?.scrollTo?.({ top: 0 });
  }, [ir]);

  const apresentar = useCallback((liga: boolean) => {
    setApresentando(liga);
    if (liga) {
      raiz.current?.requestFullscreen?.().catch(() => {});
      irParaPasso(0);
    } else if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }
  }, [irParaPasso]);

  useEffect(() => {
    if (!apresentando) return undefined;
    const tecla = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); irParaPasso(passo + 1); }
      if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); irParaPasso(passo - 1); }
      if (e.key === 'Escape') apresentar(false);
    };
    // Sair da tela cheia pelo navegador (Esc dele) também encerra a apresentação.
    const saiu = () => { if (!document.fullscreenElement) setApresentando(false); };
    document.addEventListener('keydown', tecla);
    document.addEventListener('fullscreenchange', saiu);
    return () => {
      document.removeEventListener('keydown', tecla);
      document.removeEventListener('fullscreenchange', saiu);
    };
  }, [apresentando, passo, irParaPasso, apresentar]);

  const total = useMemo(() => PLANO.materias.reduce((s, m) => s + m.aulas_2027, 0), []);
  const horas = Math.round((total * PLANO.minutos_por_aula) / 60);

  return (
    <div ref={raiz} className={`tela crono${tecnico ? ' crono--tecnico' : ''}${apresentando ? ' is-apresentando' : ''}`}>
      <header className="crono-cabeca">
        <div className="crono-cabeca__texto">
          <p className="crono-olho">3º ano e cursinho · ITA/IME · proposta para 2027</p>
          <h1 className="crono-titulo">Proposta de cronograma</h1>
          <p className="crono-resumo">
            <b>{fmtInteiro(total)} aulas</b> de {PLANO.minutos_por_aula} min ({fmtInteiro(horas)} h) em <b>{CAL.semanasDeAula} semanas</b>.
            {' '}A 1ª fase do IME vem depois de <b>{CAL.semanasDeAulaAntes(CAL.semanaDaProva('IME'))} semanas de aula</b>, e a do ITA,
            {' '}de <b>{CAL.semanasDeAulaAntes(CAL.semanaDaProva('ITA'))}</b> (datas de 2026, a confirmar).
          </p>
        </div>
        <div className="crono-acoes">
          <label className="crono-alternar">
            <input type="checkbox" checked={!tecnico} onChange={(e) => setTecnico(!e.target.checked)} />
            Ocultar detalhe técnico
          </label>
          <button type="button" className="btn btn-primary" onClick={() => apresentar(true)}>Apresentar</button>
        </div>
      </header>

      <div className="crono-abas" role="tablist" aria-label="Recortes da proposta">
        {ABAS.map((a) => (
          <button key={a.id} type="button" role="tab" className="crono-aba" aria-selected={a.id === aba} onClick={() => ir({ ver: a.id })}>
            {a.rotulo}
          </button>
        ))}
      </div>

      {(aba === 'quem' || aba === 'professor') && (
        <>
        {/* biome-ignore lint/a11y/useSemanticElements: `<fieldset>` tem métrica e `<legend>` próprios que não seguem a faixa flex, como em `BarraFiltros`; o grupo de botões só precisa do rótulo. */}
        <div className="crono-barra" role="group" aria-label="Matéria">
          <span className="crono-barra__rotulo">Matéria</span>
          <div className="crono-pilulas">
            {PLANO.materias.map((m) => (
              <button key={m.materia} type="button" className={`pill${m.materia === materia ? ' is-active' : ''}`}
                aria-pressed={m.materia === materia} onClick={() => ir({ materia: m.materia })}>
                {m.materia}
              </button>
            ))}
          </div>
        </div>
        </>
      )}

      {aba === 'ano' && (
        <AnoDoCronograma aberto={aberto} alternar={alternar} abrirMaterias={abrirMaterias} irParaProfessor={irParaProfessor} />
      )}
      {aba === 'materias' && (
        <MateriasEAssuntos materia={materia} escolherMateria={(m) => ir({ materia: m })} irParaProfessor={irParaProfessor}
          aberto={aberto} alternar={alternar} />
      )}
      {aba === 'quem' && (
        <QuemDaCadaAssunto materia={materia} agrupar={agrupar} setAgrupar={setAgrupar} aberto={aberto} alternar={alternar} />
      )}
      {aba === 'professor' && (
        <ProfessorNoAno materia={materia} professor={professor} escolherProfessor={(p) => ir({ professor: p })}
          aberto={aberto} alternar={alternar} />
      )}

      <details className="crono-como">
        <summary>Como foi calculado</summary>
        <ul>
          <li>Aula = bloco de {PLANO.minutos_por_aula} min; a aula dupla conta 2. O ano tem {fmtInteiro(PLANO.total_horas)} h = {fmtInteiro(PLANO.total_aulas)} aulas.</li>
          <li>Cada matéria recebe a parte média que teve em 2024, 2025 e 2026, arredondada para cima (o ano fica em {fmtInteiro(total)} aulas).</li>
          <li>Cada professor recebe a parte média dele na matéria; a soma dos professores fecha na matéria.</li>
          <li>O que cada professor dá é o mesmo de 2026, na mesma proporção e com o nome que ele usa (título da aula ou capítulo da apostila).</li>
          <li>A revisão de fim de ano é à parte, no fim; aula de outra frente dentro dela conta como revisão.</li>
          <li>Cada item fica, em 2027, na mesma semana do ano em que foi dado em 2026 (semanas 3 a 43, recesso nas 29–30).</li>
          <li>Simulados e provas de 2027 estão na semana de 2026, a confirmar pelos editais. A Sociologia (2024–2025) saiu da conta.</li>
        </ul>
        <p className="crono-sub">Dados de {PLANO.gerado_em.split('-').reverse().join('/')}: aulas ao vivo do Canvas (2024–2026), apostilas e acervo de provas ITA/IME do SAS.</p>
      </details>

      {apresentando && (
        <nav className="crono-passos" aria-label="Apresentação">
          <button type="button" className="btn btn--ghost" aria-label="Anterior" onClick={() => irParaPasso(passo - 1)}>←</button>
          <span>{passo + 1} / {PASSOS.length} · {PASSOS[passo]?.rotulo}</span>
          <button type="button" className="btn btn--ghost" aria-label="Seguinte" onClick={() => irParaPasso(passo + 1)}>→</button>
          <button type="button" className="btn btn--ghost" onClick={() => apresentar(false)}>Sair</button>
        </nav>
      )}
    </div>
  );
}
