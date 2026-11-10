import { useMemo, useState, type CSSProperties, type ReactNode } from 'react';

import {
  blocosDoProfessor, dataCurta, ehConteudo, itensDoProfessor, NAO_CONTEUDO, NOME_DO_MES, professoresDaMateria,
  type BlocoDoAno,
} from '../../dominio/cronograma';
import type { ProfessorDoPlano } from '../../tipos/cronograma';
import { CAL, fmtInteiro, plural, PLANO, tomDeDado } from './plano';

// O ANO — 2027 semana a semana, em três níveis.
//
//   fechado        uma linha por matéria, com um feixe fino (um traço por professor): a forma do ano, sem rótulo
//   matéria aberta os professores, com os assuntos em blocos nomeados
//   professor      cada item dele, semana a semana — e um clique num bloco abre o detalhe embaixo
//
// "Amplo" dá 60 px por semana e deixa o nome do bloco caber em duas linhas; a grade rola nos dois sentidos dentro
// do card, com a coluna dos nomes e o cabeçalho (mês, dia, marcos) presos. "Compacto" põe o ano inteiro na tela.

interface Props {
  aberto: (chave: string) => boolean;
  alternar: (chave: string) => void;
  abrirMaterias: (abrir: boolean) => void;
  irParaProfessor: (materia: string, professor: string) => void;
}

interface Detalhe {
  materia: string;
  professor: ProfessorDoPlano;
  bloco: BlocoDoAno;
}

export function AnoDoCronograma({ aberto, alternar, abrirMaterias, irParaProfessor }: Props) {
  const [largura, setLargura] = useState<'amplo' | 'compacto'>('amplo');
  const [detalhe, setDetalhe] = useState<Detalhe | null>(null);
  const amplo = largura === 'amplo';
  const semanas = CAL.semanas;
  const coluna = (w: number) => semanas.indexOf(w) + 2; // a coluna 1 é a dos nomes

  // os blocos de cada professor não mudam com o clique: calculados uma vez
  const blocos = useMemo(() => {
    const mapa = new Map<string, BlocoDoAno[]>();
    for (const p of PLANO.professores) mapa.set(`${p.materia}|${p.professor}`, blocosDoProfessor(PLANO, p.materia, p.professor, semanas));
    return mapa;
    // CAL é constante do módulo (o plano é estático): calculado uma vez por montagem
  }, []);

  const celulas: ReactNode[] = [];
  let linha = 1;
  const poe = (no: ReactNode) => celulas.push(no);
  const lugar = (de: number, ate?: number): CSSProperties => ({
    gridRow: linha, gridColumn: ate ? `${de} / ${ate}` : String(de),
  });

  // ─── cabeçalho: meses, dia de início de cada semana, marcos ───────────────
  poe(<div key="canto" className="crono-ano__canto crono-ano__topo crono-ano__topo--1" style={lugar(1)} />);
  let mesAnterior = -1;
  for (const w of semanas) {
    const mes = CAL.mesDaSemana(w);
    poe(
      <div key={`m${w}`} className={`crono-ano__mes crono-ano__topo crono-ano__topo--1${mes !== mesAnterior ? ' is-inicio' : ''}`} style={lugar(coluna(w))}>
        {mes !== mesAnterior ? NOME_DO_MES[mes] : ''}
      </div>,
    );
    mesAnterior = mes;
  }
  if (amplo) {
    linha += 1;
    poe(<div key="dia" className="crono-ano__rotulo crono-ano__rotulo--cabeca crono-ano__topo crono-ano__topo--2" style={lugar(1)}>Semana de</div>);
    for (const w of semanas) {
      poe(
        <div key={`d${w}`} className={`crono-ano__dia crono-ano__topo crono-ano__topo--2${CAL.ehRecesso(w) ? ' is-recesso' : ''}`} style={lugar(coluna(w))}>
          {CAL.inicio(w).slice(8, 10)}
        </div>,
      );
    }
  }
  linha += 1;
  poe(<div key="marcos" className={`crono-ano__rotulo crono-ano__rotulo--cabeca${amplo ? ' crono-ano__topo crono-ano__topo--3' : ''}`} style={lugar(1)}>Marcos</div>);
  for (const w of semanas) {
    const ms = CAL.marcos.filter((m) => m.semana === w);
    const prova = ms.find((m) => m.tipo === 'prova');
    const tipo = prova ? 'prova' : CAL.ehRecesso(w) ? 'recesso'
      : ms.some((m) => m.tipo === 'colegio' || m.tipo === 'simulado') ? 'colegio' : ms.length ? 'feriado' : '';
    const titulo = ms.length
      ? `Semana de ${dataCurta(CAL.inicio(w))}: ${ms.map((m) => `${m.rotulo}${m.confirmado ? '' : ' (a confirmar)'}`).join('; ')}`
      : undefined;
    poe(
      // a célula (presa no topo, com fundo) leva o marcador dentro — o fundo da célula não apaga a cor dele
      <div key={`k${w}`} className={`crono-ano__celula-marco${amplo ? ' crono-ano__topo crono-ano__topo--3' : ''}`} style={lugar(coluna(w))}>
        <div className={`crono-ano__marco${tipo ? ` crono-ano__marco--${tipo}` : ''}`} title={titulo}>
          {prova ? (prova.rotulo.includes('IME') ? 'IME' : 'ITA') : ''}
        </div>
      </div>,
    );
  }

  // ─── matérias → professores → itens ───────────────────────────────────────
  for (const m of PLANO.materias) {
    const profs = professoresDaMateria(PLANO, m.materia);
    const kM = `ano|${m.materia}`;
    linha += 1;
    poe(
      <button key={kM} type="button" className="crono-ano__rotulo crono-ano__rotulo--materia" style={lugar(1)}
        aria-expanded={aberto(kM)} onClick={() => alternar(kM)}>
        <span className="crono-seta" aria-hidden="true">›</span>
        <span>{m.materia}<small>{fmtInteiro(m.aulas_2027)} aulas · {plural(profs.length, 'professor', 'professores')}</small></span>
      </button>,
    );
    if (!aberto(kM)) {
      // fechada: o feixe — um traço por professor, sem rótulo
      poe(
        <div key={`${kM}|feixe`} className="crono-ano__feixe"
          style={{ ...lugar(2, semanas.length + 2), gridTemplateColumns: `repeat(${semanas.length}, 1fr)` }}>
          {profs.flatMap((p, i) => (blocos.get(`${m.materia}|${p.professor}`) ?? []).map((b) => (
            <div key={`${p.professor}${b.de}`}
              className={`crono-ano__fio${b.codigo === 'REVF' ? ' is-revisao' : NAO_CONTEUDO.has(b.codigo) ? ' is-outro' : ''}`}
              style={{ gridRow: i + 1, gridColumn: `${semanas.indexOf(b.de) + 1} / ${semanas.indexOf(b.ate) + 2}` }} />
          )))}
        </div>,
      );
      continue;
    }
    for (const p of profs) {
      const kP = `${kM}|${p.professor}`;
      linha += 1;
      poe(
        <button key={kP} type="button" className="crono-ano__rotulo crono-ano__rotulo--prof" style={lugar(1)}
          aria-expanded={aberto(kP)} onClick={() => alternar(kP)}>
          <span className="crono-seta" aria-hidden="true">›</span>
          <span>{p.professor}<small>{p.frentes.replace(/\s*\([^)]*\)/g, '')} · {fmtInteiro(p.aulas_2027)} aulas</small></span>
        </button>,
      );
      poe(<div key={`${kP}|faixa`} className="crono-ano__faixa" style={lugar(2, semanas.length + 2)} />);
      let claro = false;
      for (const b of blocos.get(`${m.materia}|${p.professor}`) ?? []) {
        const revisao = b.codigo === 'REVF';
        const outro = !revisao && NAO_CONTEUDO.has(b.codigo);
        if (!revisao && !outro) claro = !claro;
        const largo = semanas.indexOf(b.ate) - semanas.indexOf(b.de) + 1;
        poe(
          <button key={`${kP}|${b.de}`} type="button"
            className={`crono-ano__bloco${revisao ? ' is-revisao' : outro ? ' is-outro' : claro ? ' is-claro' : ''}`}
            style={lugar(coluna(b.de), coluna(b.ate) + 1)}
            title={`${b.rotulo}${b.grupo !== b.rotulo ? ` (${b.grupo})` : ''} · ${dataCurta(CAL.inicio(b.de))} a ${dataCurta(CAL.inicio(b.ate))}`}
            onClick={() => setDetalhe({ materia: m.materia, professor: p, bloco: b })}>
            {largo >= (amplo ? 2 : 3) ? (revisao ? 'Revisão' : b.rotulo) : ''}
          </button>,
        );
      }
      if (!aberto(kP)) continue;
      const itens = itensDoProfessor(PLANO, m.materia, p.professor);
      const maximo = Math.max(1, ...itens.flatMap((it) => Object.values(it.semanas)));
      for (const it of itens) {
        linha += 1;
        const revisao = 'REVF' in it.codigos;
        poe(
          <div key={`${kP}|i${it.ordem}`} className="crono-ano__rotulo crono-ano__rotulo--item" style={lugar(1)} title={it.nome}>
            {it.nome}{it.ref ? <small>{it.ref}</small> : null}
          </div>,
        );
        for (const [w, n] of Object.entries(it.semanas)) {
          const semana = Number(w);
          if (!semanas.includes(semana)) continue;
          poe(
            <div key={`${kP}|i${it.ordem}|${w}`} className={`crono-ano__ponto${revisao ? ' is-revisao' : ''}`}
              style={{ ...lugar(coluna(semana)), ...(revisao ? {} : { background: ehConteudo(it) ? tomDeDado(n / maximo) : 'var(--sas-referencia)' }) }}
              title={`${it.nome} · semana de ${dataCurta(CAL.inicio(semana))}: ${plural(n, 'aula', 'aulas')}`} />,
          );
        }
      }
    }
  }

  return (
    <>
      <div className="card crono-card">
        <div className="crono-card__cabeca">
          <div className="crono-card__texto">
            <h2 className="crono-card__titulo">2027 semana a semana</h2>
            <p className="crono-sub">Clique numa matéria para ver os professores; num professor, para ver o que ele dá; num bloco, para o detalhe.</p>
          </div>
          <div className="crono-acoes">
            {/* biome-ignore lint/a11y/useSemanticElements: `<fieldset>` tem métrica e `<legend>` próprios que não seguem a faixa flex, como em `BarraFiltros`; o grupo de botões só precisa do rótulo. */}
            <div className="crono-seg" role="group" aria-label="Largura do calendário">
              <button type="button" className="crono-seg__opcao" aria-pressed={amplo} onClick={() => setLargura('amplo')}>Amplo</button>
              <button type="button" className="crono-seg__opcao" aria-pressed={!amplo} onClick={() => setLargura('compacto')}>Compacto</button>
            </div>
            <button type="button" className="btn btn--ghost" onClick={() => abrirMaterias(true)}>Abrir todas</button>
            <button type="button" className="btn btn--ghost" onClick={() => { abrirMaterias(false); setDetalhe(null); }}>Fechar</button>
          </div>
        </div>
        <div className="crono-rolagem-ano">
          <div className={`crono-ano${amplo ? ' crono-ano--amplo' : ''}`}
            style={{ gridTemplateColumns: amplo ? `230px repeat(${semanas.length}, 60px)` : `minmax(180px, 230px) repeat(${semanas.length}, minmax(16px, 1fr))` }}>
            {celulas}
          </div>
        </div>
      </div>

      {detalhe && (
        <div className="card crono-card">
          <div className="crono-card__cabeca">
            <div className="crono-card__texto">
              <p className="crono-olho">{detalhe.materia} · {detalhe.professor.professor}</p>
              <h2 className="crono-card__titulo">{detalhe.bloco.codigo === 'REVF' ? 'Revisão de fim de ano' : detalhe.bloco.rotulo}</h2>
              <p className="crono-sub">
                De {dataCurta(CAL.inicio(Math.min(...detalhe.bloco.semanas)))} a {dataCurta(CAL.inicio(Math.max(...detalhe.bloco.semanas)))}
                {' · '}{plural(detalhe.bloco.semanas.length, 'semana', 'semanas')} · cerca de {plural(Math.round(detalhe.bloco.aulas), 'aula', 'aulas')}
              </p>
            </div>
            <button type="button" className="btn btn--ghost" onClick={() => setDetalhe(null)}>Fechar</button>
          </div>
          <div className="crono-detalhe">
            <p className="crono-rotulo-detalhe">Como o professor chama</p>
            <div className="crono-chips">
              {detalhe.bloco.itens.slice(0, 12).map((n) => <span key={n} className="crono-chip">{n}</span>)}
            </div>
            <button type="button" className="btn btn--ghost" onClick={() => irParaProfessor(detalhe.materia, detalhe.professor.professor)}>
              Ver o ano todo de {detalhe.professor.professor}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
