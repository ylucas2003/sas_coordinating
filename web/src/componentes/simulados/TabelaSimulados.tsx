import { Link, useNavigate } from 'react-router-dom';
import { SeloCanvas } from '../ui/SeloCanvas';
import { OrdenarNoCelular, TheadOrdenavel } from '../ui/TabelaOrdenavel';
import { ordenarLinhas } from '../ui/ordenacao';
import type { ColunaTabela, Ordenacao } from '../ui/ordenacao';
import { rotuloCiclo } from '../../dominio/simulados';
import type { Simulado } from '../../tipos/dominio';
import { fmtDataBR } from '../../util/data';
import { fmtNota } from '../../util/formato';

const TIPO_LABEL: Record<string, string> = { fase_1: 'Fase 1', fase_2: 'Fase 2' };

interface Props {
  simulados: readonly Simulado[];
  /** Se presente, adiciona as colunas "Sua nota" e "Δ" (vs média da turma). */
  notasAluno?: ReadonlyMap<string, number> | null;
  /** Oculta mediana, σ e n. */
  compacto?: boolean;
  /** Quando fornecido, adiciona um botão "Editar" por linha. */
  onEditarNota?: ((simulado: Simulado, notaAtual: number | null) => void) | null;
  /** Junto com `onOrdenar`, torna o cabeçalho clicável. */
  ordenacao?: Ordenacao | null;
  onOrdenar?: ((chave: string) => void) | null;
}

/** Tabela de simulados — usada na tela Simulados e na ficha do aluno. */
export function TabelaSimulados({
  simulados,
  notasAluno = null,
  compacto = false,
  onEditarNota = null,
  ordenacao = null,
  onOrdenar = null,
}: Props) {
  const navegar = useNavigate();

  if (!simulados.length) {
    return <div className="sim-tabela__vazio">Nenhum simulado bate com os filtros.</div>;
  }

  const temAluno = !!notasAluno;
  const temEditar = !!onEditarNota;

  // Colunas na MESMA ordem das células, incluindo as condicionais — o
  // cabeçalho ordenável é montado a partir daqui.
  const colunas: Array<ColunaTabela<Simulado>> = [
    { chave: 'pn', label: 'Pn', valor: (s) => s.rotuloCurto },
    { chave: 'materia', label: 'Matéria', valor: (s) => s.materia?.nome },
    { chave: 'fase', label: 'Fase', valor: (s) => s.tipo },
    { chave: 'vest', label: 'Vest.', valor: (s) => s.vestibularAlvo },
    { chave: 'ciclo', label: 'Ciclo', valor: (s) => s.cicloOrdem, tipo: 'numero' },
    { chave: 'data', label: 'Data', valor: (s) => s.dataAplicacao },
    ...(temAluno
      ? [{ chave: 'suaNota', label: 'Sua nota', valor: (s: Simulado) => notasAluno!.get(s.id), tipo: 'numero' as const }]
      : []),
    { chave: 'media', label: 'Média', valor: (s) => s.media, tipo: 'numero' },
    ...(temAluno
      ? [{
          chave: 'delta', label: 'Δ', tipo: 'numero' as const,
          valor: (s: Simulado) => {
            const n = notasAluno!.get(s.id);
            return n == null || s.media == null ? null : n - s.media;
          },
        }]
      : []),
    ...(!compacto
      ? [
          { chave: 'mediana', label: 'Mediana', valor: (s: Simulado) => s.mediana, tipo: 'numero' as const },
          { chave: 'sigma', label: 'σ', valor: (s: Simulado) => s.desvioPadrao, tipo: 'numero' as const },
          { chave: 'n', label: 'n', valor: (s: Simulado) => s.nPresentes, tipo: 'numero' as const },
        ]
      : []),
    { chave: 'acao', label: '', ordenavel: false },
    ...(temEditar ? [{ chave: 'editar', label: '', ordenavel: false }] : []),
  ];

  const linhas = onOrdenar ? ordenarLinhas(simulados, colunas, ordenacao) : simulados;

  return (
    <>
      {/* O `<thead>` some no cartão, e com ele a ordenação — esta peça devolve
          o controle no celular. Só quando a tela de fato ordena. */}
      {onOrdenar && (
        <OrdenarNoCelular colunas={colunas} ordenacao={ordenacao} onOrdenar={onOrdenar} />
      )}

      {/* `--cartoes`: a mais larga das tabelas CURTAS — 14 colunas quando não é
          compacta, 840px medidos, +467px de transbordo a 390px. Cada linha é
          uma prova com nome próprio, então vira cartão (layout.css). */}
      <table className="data-table sim-tabela data-table--cartoes">
        {onOrdenar ? (
          <TheadOrdenavel colunas={colunas} ordenacao={ordenacao} onOrdenar={onOrdenar} />
        ) : (
          <thead>
            <tr>
              {colunas.map((c) => (
                <th key={c.chave}>{c.label}</th>
              ))}
            </tr>
          </thead>
        )}

        <tbody>
          {linhas.map((s) => {
            const notaAluno = temAluno ? (notasAluno!.get(s.id) ?? null) : null;
            return (
              <tr key={s.id} onClick={() => navegar(`/simulados/${s.id}`)}>
                <td className="sim-tabela__pn" data-rotulo="Prova" data-titulo>
                  {s.rotuloCurto || '—'}
                  {/* Simulado do SAS que não reflete o Canvas — limbo ou escolha
                      ('divergente'). Estado normal não ganha pixel; a ação de
                      enviar fica na ficha (Ver →). */}
                  {s.canvasEstado && s.canvasEstado !== 'sincronizado' && (
                    <span style={{ marginLeft: 8 }}>
                      <SeloCanvas estado={s.canvasEstado} erro={s.canvasErro} />
                    </span>
                  )}
                </td>
                <td data-rotulo="Matéria">{s.materia?.nome || '—'}</td>
                {/* `data-secundario`: some do CARTÃO, fica na tabela do desktop.
                    Sem isto o cartão desta tabela media 546px — 153 deles davam
                    99 telas de rolagem (medido a 390px em 07/09). O que sai é o
                    que a ficha da prova responde melhor. */}
                <td data-rotulo="Tipo" data-secundario>{TIPO_LABEL[s.tipo ?? ''] || '—'}</td>
                <td data-rotulo="Alvo" data-secundario>{s.vestibularAlvo || '—'}</td>
                <td data-rotulo="Ciclo" data-secundario>{rotuloCiclo(s.cicloOrdem, s.vestibularAlvo)}</td>
                <td className="sim-tabela__data" data-rotulo="Aplicada">{fmtDataBR(s.dataAplicacao)}</td>
                {temAluno && <CelulaSuaNota nota={notaAluno} />}
                <td data-rotulo="Média">{fmtNota(s.media)}</td>
                {temAluno && <CelulaDelta nota={notaAluno} media={s.media} />}
                {!compacto && <td data-rotulo="Mediana" data-secundario>{fmtNota(s.mediana)}</td>}
                {!compacto && <td data-rotulo="σ" data-secundario>{fmtNota(s.desvioPadrao)}</td>}
                {!compacto && <td data-rotulo="n" data-secundario>{s.nPresentes == null ? '—' : String(s.nPresentes)}</td>}
                <td>
                  <Link to={`/simulados/${s.id}`} onClick={(ev) => ev.stopPropagation()}>
                    Ver →
                  </Link>
                </td>
                {temEditar && (
                  <td className="acoes-da-linha" onClick={(ev) => ev.stopPropagation()}>
                    <button className="btn-editar" onClick={() => onEditarNota!(s, notaAluno)}>
                      Editar
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
          </tbody>
      </table>
    </>
  );
}

function CelulaSuaNota({ nota }: { nota: number | null }) {
  return <td className="sim-tabela__sua" data-rotulo="Sua nota">{nota == null ? '—' : fmtNota(nota)}</td>;
}

function CelulaDelta({ nota, media }: { nota: number | null; media: number | null }) {
  if (nota == null || media == null) return <td data-rotulo="Diferença">—</td>;
  const delta = nota - media;
  const tom = delta > 0.1 ? 'tone-verde' : delta < -0.1 ? 'tone-vermelho' : '';
  return (
    <td className={`sim-tabela__delta ${tom}`} data-rotulo="Diferença">
      {`${delta > 0 ? '+' : ''}${delta.toFixed(1).replace('.', ',')}`}
    </td>
  );
}
