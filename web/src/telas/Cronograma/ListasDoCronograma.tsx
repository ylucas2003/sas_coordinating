import type { ReactNode } from 'react';

import {
  assuntosDaMateria, etapasDoProfessor, NAO_CONTEUDO, NOME_DO_MES, aulasNoMes, professoresDaMateria,
  type AssuntoDaMateria,
} from '../../dominio/cronograma';
import type { ItemDoPlano } from '../../tipos/cronograma';
import { CAL, fmtInteiro, fmtUmaCasa, plural, PLANO, tomDeDado } from './plano';

// As três listas da proposta de cronograma. Todas começam com o mínimo e abrem por clique:
//
//   MateriasEAssuntos   cartões das matérias → assuntos (barra + aulas) → quem dá, como chamam, peso na prova
//   QuemDaCadaAssunto   assunto com os professores que o dão → os itens de cada um (ou o inverso, por professor)
//   ProfessorNoAno      as etapas do ano de um professor → os itens de cada etapa, mês a mês

interface Abertura {
  aberto: (chave: string) => boolean;
  alternar: (chave: string) => void;
}

/** Uma linha que abre: cabeça clicável (com seta) e, aberta, o corpo. */
function LinhaQueAbre({ chave, cabeca, corpo, aberto, alternar }: Abertura & {
  chave: string; cabeca: ReactNode; corpo: () => ReactNode;
}) {
  const esta = aberto(chave);
  return (
    <div className={`crono-linha${esta ? ' is-aberta' : ''}`}>
      <button type="button" className="crono-linha__cabeca" aria-expanded={esta} onClick={() => alternar(chave)}>
        <span className="crono-seta" aria-hidden="true">›</span>
        {cabeca}
      </button>
      {esta && <div className="crono-linha__corpo">{corpo()}</div>}
    </div>
  );
}

const Chip = ({ texto, numero, onClick, titulo }: { texto: string; numero?: string; onClick?: () => void; titulo?: string }) =>
  onClick ? (
    <button type="button" className="crono-chip crono-chip--botao" onClick={onClick} title={titulo}>
      {texto}{numero != null && <b>{numero}</b>}
    </button>
  ) : (
    <span className="crono-chip">{texto}{numero != null && <b>{numero}</b>}</span>
  );

// ─── Matérias e assuntos ───────────────────────────────────────────────────

export function MateriasEAssuntos({ materia, escolherMateria, irParaProfessor, ...abertura }: Abertura & {
  materia: string;
  escolherMateria: (materia: string) => void;
  irParaProfessor: (materia: string, professor: string) => void;
}) {
  const grupos = assuntosDaMateria(PLANO, materia);
  const conteudo = grupos.filter((g) => g.conteudo);
  const outros = grupos.filter((g) => !g.conteudo);
  const maximo = Math.max(1, ...conteudo.map((g) => g.aulas2027));
  const totalConteudo = conteudo.reduce((s, g) => s + g.aulas2027, 0) || 1;

  const corpoDoAssunto = (g: AssuntoDaMateria) => () => {
    const nomes = [...new Map([...g.itens]
      .sort((a, b) => b.item.aulas_2027 * b.peso - a.item.aulas_2027 * a.peso)
      .map(({ item }) => [item.nome, item])).keys()];
    return (
      <>
        <p className="crono-rotulo-detalhe">Quem dá</p>
        <div className="crono-chips">
          {g.porProfessor.filter(([, v]) => v >= 0.5).map(([p, v]) => (
            <Chip key={p} texto={p} numero={fmtInteiro(v)} titulo={`Ver o ano de ${p}`} onClick={() => irParaProfessor(materia, p)} />
          ))}
        </div>
        <p className="crono-rotulo-detalhe">Como os professores chamam</p>
        <div className="crono-chips">{nomes.slice(0, 14).map((n) => <Chip key={n} texto={n} />)}</div>
        {g.peso_ita != null && g.peso_ime != null && (
          <p className="crono-info crono-tecnico">
            Na prova: {fmtUmaCasa(g.peso_ita)}% no ITA e {fmtUmaCasa(g.peso_ime)}% no IME (acervo do SAS). Nas aulas
            da matéria: {fmtUmaCasa((100 * g.aulas2027) / totalConteudo)}%.
          </p>
        )}
        <p className="crono-info crono-tecnico">Em 2026: {plural(Math.round(g.aulas2026), 'aula', 'aulas')}.</p>
      </>
    );
  };

  return (
    <>
      <div className="crono-cartoes">
        {PLANO.materias.map((m) => (
          <button key={m.materia} type="button" className="crono-cartao" aria-pressed={m.materia === materia}
            onClick={() => escolherMateria(m.materia)}>
            <span className="crono-olho">{m.materia}</span>
            <span className="crono-cartao__magnitude">
              <span className="crono-cartao__numero">{fmtInteiro(m.aulas_2027)}</span> aulas
            </span>
            <span className="crono-cartao__sub">{fmtInteiro(m.horas_2027)} h · {fmtUmaCasa(m.parte_media_pct)}% do ano</span>
          </button>
        ))}
      </div>
      <div className="card crono-card">
        <div className="crono-card__cabeca">
          <div className="crono-card__texto">
            <h2 className="crono-card__titulo">{materia}: {plural(conteudo.length, 'assunto', 'assuntos')}</h2>
            <p className="crono-sub">Clique num assunto para ver quem dá, como cada professor o chama e quanto ele vale na prova.</p>
          </div>
        </div>
        <div className="crono-lista">
          {conteudo.map((g) => (
            <LinhaQueAbre key={g.codigo} chave={`m|${materia}|${g.codigo}`} {...abertura}
              cabeca={<>
                <span className="crono-linha__nome">{g.nome}</span>
                <span className="crono-linha__barra"><i style={{ width: `${(100 * g.aulas2027) / maximo}%` }} /></span>
                <span className="crono-linha__numero">{fmtInteiro(g.aulas2027)}<small> aulas</small></span>
              </>}
              corpo={corpoDoAssunto(g)} />
          ))}
          {outros.length > 0 && (
            <LinhaQueAbre chave={`m|${materia}|outros`} {...abertura}
              cabeca={<>
                <span className="crono-linha__nome crono-linha__nome--outro">Revisão, simulados e outros</span>
                <span className="crono-linha__barra crono-linha__barra--vazia" />
                <span className="crono-linha__numero">{fmtInteiro(outros.reduce((s, g) => s + g.aulas2027, 0))}<small> aulas</small></span>
              </>}
              corpo={() => (
                <div className="crono-chips">{outros.map((g) => <Chip key={g.codigo} texto={g.nome} numero={fmtInteiro(g.aulas2027)} />)}</div>
              )} />
          )}
        </div>
      </div>
    </>
  );
}

// ─── Assuntos e professores ────────────────────────────────────────────────

export function QuemDaCadaAssunto({ materia, agrupar, setAgrupar, ...abertura }: Abertura & {
  materia: string;
  agrupar: 'assunto' | 'professor';
  setAgrupar: (a: 'assunto' | 'professor') => void;
}) {
  const grupos = assuntosDaMateria(PLANO, materia).filter((g) => g.conteudo);
  const profs = professoresDaMateria(PLANO, materia);
  const itensDoProfNoGrupo = (professor: string, g: AssuntoDaMateria) => PLANO.itens
    .filter((it) => it.materia === materia && it.professor === professor && (it.codigos[g.codigo] ?? 0) >= 0.2)
    .sort((a, b) => a.ordem - b.ordem);
  const lista = (itens: ItemDoPlano[], g: AssuntoDaMateria) => (
    <ul className="crono-itens">
      {itens.map((it) => (
        <li key={it.ordem}>
          <span>{it.nome}{it.ref && <small>{it.ref}</small>}</span>
          <span>{plural(Math.max(1, Math.round(it.aulas_2027 * (it.codigos[g.codigo] ?? 1))), 'aula', 'aulas')}</span>
        </li>
      ))}
    </ul>
  );

  return (
    <div className="card crono-card">
      <div className="crono-card__cabeca">
        <div className="crono-card__texto">
          <h2 className="crono-card__titulo">{materia}: {agrupar === 'assunto' ? 'quem dá cada assunto' : 'o que cada professor dá'}</h2>
          <p className="crono-sub">Clique numa linha para ver o que cada professor dá ali, com o nome que ele usa.</p>
        </div>
        {/* biome-ignore lint/a11y/useSemanticElements: `<fieldset>` tem métrica e `<legend>` próprios que não seguem a faixa flex, como em `BarraFiltros`; o grupo de botões só precisa do rótulo. */}
        <div className="crono-seg" role="group" aria-label="Agrupar por">
          <button type="button" className="crono-seg__opcao" aria-pressed={agrupar === 'assunto'} onClick={() => setAgrupar('assunto')}>Por assunto</button>
          <button type="button" className="crono-seg__opcao" aria-pressed={agrupar === 'professor'} onClick={() => setAgrupar('professor')}>Por professor</button>
        </div>
      </div>
      <div className="crono-lista crono-lista--quem">
        {agrupar === 'assunto'
          ? grupos.map((g) => {
            const quem = g.porProfessor.filter(([, v]) => v >= 0.5);
            return (
              <LinhaQueAbre key={g.codigo} chave={`q|${materia}|${g.codigo}`} {...abertura}
                cabeca={<>
                  <span className="crono-linha__nome">{g.nome}</span>
                  <span className="crono-chips crono-chips--linha">{quem.map(([p, v]) => <Chip key={p} texto={p} numero={fmtInteiro(v)} />)}</span>
                </>}
                corpo={() => quem.map(([p]) => (
                  <div key={p} className="crono-bloco-prof">
                    <p className="crono-rotulo-detalhe">{p}</p>
                    {lista(itensDoProfNoGrupo(p, g), g)}
                  </div>
                ))} />
            );
          })
          : profs.map((p) => {
            const dele = grupos
              .map((g) => [g, g.porProfessor.find(([nome]) => nome === p.professor)?.[1] ?? 0] as const)
              .filter(([, v]) => v >= 0.5)
              .sort((a, b) => b[1] - a[1]);
            return (
              <LinhaQueAbre key={p.professor} chave={`q|${materia}|p|${p.professor}`} {...abertura}
                cabeca={<>
                  <span className="crono-linha__nome">{p.professor}<small>{fmtInteiro(p.aulas_2027)} aulas</small></span>
                  <span className="crono-chips crono-chips--linha">{dele.map(([g, v]) => <Chip key={g.codigo} texto={g.nome} numero={fmtInteiro(v)} />)}</span>
                </>}
                corpo={() => dele.map(([g]) => (
                  <div key={g.codigo} className="crono-bloco-prof">
                    <p className="crono-rotulo-detalhe">{g.nome}</p>
                    {lista(itensDoProfNoGrupo(p.professor, g), g)}
                  </div>
                ))} />
            );
          })}
      </div>
    </div>
  );
}

// ─── Cada professor no ano ─────────────────────────────────────────────────

export function ProfessorNoAno({ materia, professor, escolherProfessor, ...abertura }: Abertura & {
  materia: string;
  professor: string;
  escolherProfessor: (professor: string) => void;
}) {
  const profs = professoresDaMateria(PLANO, materia);
  const p = profs.find((x) => x.professor === professor) ?? profs[0];
  if (!p) return null;
  const etapas = etapasDoProfessor(PLANO, materia, p.professor, CAL.mesDaSemana, CAL.mesesDoAno);
  const maxEtapa = Math.max(1, ...etapas.flatMap((e) => e.meses));

  const celula = (v: number, maximo: number, comNumero: boolean, revisao: boolean, outro: boolean, chave: string) => {
    if (!v) return <td key={chave} className="crono-mes" />;
    const fundo = revisao ? undefined : outro ? 'var(--sas-referencia)' : tomDeDado(v / maximo);
    return (
      <td key={chave} className="crono-mes">
        <span className={revisao ? 'crono-hachura' : ''} style={fundo ? { background: fundo } : undefined}>{comNumero ? v : ''}</span>
      </td>
    );
  };

  return (
    <>
      {/* biome-ignore lint/a11y/useSemanticElements: `<fieldset>` tem métrica e `<legend>` próprios que não seguem a faixa flex, como em `BarraFiltros`; o grupo de botões só precisa do rótulo. */}
      <div className="crono-barra" role="group" aria-label="Professor">
        <span className="crono-barra__rotulo">Professor</span>
        <div className="crono-pilulas">
          {profs.map((x) => (
            <button key={x.professor} type="button" className={`pill${x.professor === p.professor ? ' is-active' : ''}`}
              aria-pressed={x.professor === p.professor} onClick={() => escolherProfessor(x.professor)}>
              {x.professor}
            </button>
          ))}
        </div>
      </div>
      <div className="card crono-card">
        <div className="crono-card__cabeca">
          <div className="crono-card__texto">
            <p className="crono-olho">{materia} · {p.frentes}</p>
            <h2 className="crono-card__titulo">{p.professor}: {fmtInteiro(p.aulas_2027)} aulas</h2>
            <p className="crono-sub">
              {plural(etapas.length, 'etapa', 'etapas')} no ano, a revisão no fim ({plural(p.revisao_2027, 'aula', 'aulas')}).
              {' '}Clique numa etapa para ver os itens com o nome que ele usa.
            </p>
          </div>
        </div>
        <div className="crono-rolagem">
          <table className="crono-tempo">
            <thead>
              <tr>
                <th>Etapa</th>
                {CAL.mesesDoAno.map((mes) => <th key={mes} className="crono-mes">{NOME_DO_MES[mes]}</th>)}
                <th className="crono-n">Aulas</th>
              </tr>
            </thead>
            <tbody>
              {etapas.flatMap((e, i) => {
                const k = `a|${materia}|${p.professor}|${e.codigo}`;
                const revisao = e.codigo === 'REVF';
                const outro = !revisao && NAO_CONTEUDO.has(e.codigo);
                const esta = abertura.aberto(k);
                const linhas = [
                  <tr key={k} className={`crono-etapa${esta ? ' is-aberta' : ''}`} tabIndex={0} aria-expanded={esta}
                    onClick={() => abertura.alternar(k)}
                    onKeyDown={(ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abertura.alternar(k); } }}>
                    <td className="crono-tempo__nome">
                      <span className="crono-seta" aria-hidden="true">›</span>{e.rotulo}
                      <small>{plural(e.itens.length, 'item', 'itens')}</small>
                    </td>
                    {e.meses.map((v, j) => celula(v, maxEtapa, false, revisao, outro, `${i}-${j}`))}
                    <td className="crono-n crono-numero-forte">{fmtInteiro(e.aulas)}</td>
                  </tr>,
                ];
                if (esta) {
                  const maxItem = Math.max(1, ...e.itens.flatMap((it) => CAL.mesesDoAno.map((mes) => aulasNoMes(it, mes, CAL.mesDaSemana))));
                  for (const it of e.itens) {
                    linhas.push(
                      <tr key={`${k}|${it.ordem}`} className="crono-subitem">
                        <td className="crono-tempo__nome">{it.nome}{it.ref && <small>{it.ref}</small>}</td>
                        {CAL.mesesDoAno.map((mes) => celula(aulasNoMes(it, mes, CAL.mesDaSemana), maxItem, true, revisao, outro, `${it.ordem}-${mes}`))}
                        <td className="crono-n">{fmtInteiro(it.aulas_2027)}</td>
                      </tr>,
                    );
                  }
                }
                return linhas;
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
