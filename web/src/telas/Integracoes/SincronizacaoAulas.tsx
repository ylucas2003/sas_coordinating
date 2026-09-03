import { useMemo, useState } from 'react';

import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { normalizar } from '../../util/formato';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import { SeloCanvasGravacao, SeloSituacao } from '../../componentes/ui/SeloGravacao';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import { usePainelGravacoes } from '../../hooks/consultas';
import {
  FILTRO_GRAVACOES_VAZIO,
  ROTULO_SITUACAO,
  SITUACOES,
  algumFiltroAtivo,
  aplicarFiltros,
  contarPorChip,
  formatarDuracao,
  formatarHora,
  partesDaData,
  ordenarParaAcompanhamento,
  resumoAndamento,
  situacaoDe,
  tituloParaCartao,
  toneSituacao,
} from '../../dominio/gravacoes';
import type { Situacao } from '../../dominio/gravacoes';
import type { GravacaoAula } from '../../tipos/dominio';

/**
 * Acompanhamento da sincronização de aulas: o que já foi publicado, o que está
 * sendo processado agora e o que ainda vai ser.
 *
 * Antes desta tela o único jeito de saber o estado de uma aula era `psql` no
 * servidor. Ela é também o instrumento de conferência da escrita no Canvas —
 * é aqui que se olha antes de ligar `publicar_no_canvas` num curso novo.
 */

function alternar<V>(conjunto: ReadonlySet<V>, valor: V): ReadonlySet<V> {
  const novo = new Set(conjunto);
  if (novo.has(valor)) novo.delete(valor);
  else novo.add(valor);
  return novo;
}

export function SincronizacaoAulas() {
  useTituloDaTela('Aulas · Canvas ↔ YouTube');

  const [cursos, setCursos] = useState<ReadonlySet<string>>(new Set());
  const [busca, setBusca] = useState('');
  const [situacoes, setSituacoes] = useState<ReadonlySet<Situacao>>(new Set());

  // O hook liga e desliga o próprio polling a partir da resposta.
  const { data, isPending, isError, error } = usePainelGravacoes();
  const andamento = resumoAndamento(data?.aulas ?? []);

  const aulas = useMemo(() => ordenarParaAcompanhamento(data?.aulas ?? []), [data]);
  const cursosDisponiveis = data?.cursos ?? [];
  const nomePorCurso = useMemo(
    () => new Map(cursosDisponiveis.map((c) => [c.cursoId, c.nome])),
    [cursosDisponiveis],
  );
  const publicaNoCanvasPorCurso = useMemo(
    () => new Map(cursosDisponiveis.map((c) => [c.cursoId, c.publicarNoCanvas])),
    [cursosDisponiveis],
  );

  const filtro = useMemo(() => ({ cursos, situacoes }), [cursos, situacoes]);
  const filtradas = useMemo(() => {
    const q = normalizar(busca.trim());
    const doRecorte = aplicarFiltros(aulas, filtro);
    if (!q) return doRecorte;
    return doRecorte.filter(
      (a) => normalizar(a.titulo ?? '').includes(q) || normalizar(a.youtubeTitulo ?? '').includes(q),
    );
  }, [aulas, filtro, busca]);
  const contagens = useMemo(() => contarPorChip(aulas, filtro), [aulas, filtro]);
  const ativo = algumFiltroAtivo(filtro);

  return (
    <div className="tela">
      <BarraFiltros
        tela="integracoes.aulas"
        algumAtivo={ativo || busca.trim() !== ''}
        onLimpar={() => {
          setCursos(FILTRO_GRAVACOES_VAZIO.cursos);
          setSituacoes(FILTRO_GRAVACOES_VAZIO.situacoes);
          setBusca('');
        }}
        grupos={[
          {
            chave: 'busca',
            rotulo: 'Aula',
            resumo: resumirTexto(busca),
            corpo: (
              <Busca
                valor={busca}
                onChange={setBusca}
                placeholder="Buscar aula…"
                rotulo="Buscar aula pelo título"
              />
            ),
          },
          {
            chave: 'curso',
            rotulo: 'Curso',
            resumo: resumirSelecao(
              cursos,
              cursosDisponiveis.map((c) => ({ valor: c.cursoId, label: c.nome })),
              'curso', 'cursos',
            ),
            corpo: (
              <Pills
                opcoes={cursosDisponiveis.map((c) => ({
                  valor: c.cursoId,
                  label: c.nome,
                  contagem: contagens.curso.get(c.cursoId) ?? 0,
                }))}
                selecionados={cursos}
                onToggle={(id) => setCursos((s) => alternar(s, id))}
              />
            ),
          },
          {
            chave: 'situacao',
            rotulo: 'Situação',
            resumo: resumirSelecao(
              situacoes,
              SITUACOES.map((s) => ({ valor: s, label: ROTULO_SITUACAO[s] })),
              'situação', 'situações',
            ),
            corpo: (
              <Pills
                opcoes={SITUACOES.map((s) => ({
                  valor: s,
                  label: ROTULO_SITUACAO[s],
                  contagem: contagens.situacao.get(s) ?? 0,
                }))}
                selecionados={situacoes}
                onToggle={(s) => setSituacoes((x) => alternar(x, s))}
              />
            ),
          },
        ]}
      />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Aulas · Canvas ↔ YouTube</h1>
          <p className="tela-subtitulo">
            {isPending
              ? 'Carregando…'
              : `${filtradas.length} aula${filtradas.length === 1 ? '' : 's'}${
                  ativo ? ` de ${aulas.length}` : ''
                }${andamento ? ` · ${andamento}` : ''}`}
          </p>
        </div>
      </div>

      {/* O invólucro branco fica só para os estados sem conteúdo. A grade vai
          direto no fundo da página: card branco sobre card branco apagaria a
          borda de cada aula. */}
      {isError ? (
        <section className="card">
          <div className="empty-state">
            Não foi possível carregar as aulas gravadas.
            <div className="empty-state__hint">{(error as Error)?.message}</div>
          </div>
        </section>
      ) : isPending ? (
        <section className="card">
          <div className="empty-state">Carregando…</div>
        </section>
      ) : filtradas.length === 0 ? (
        <section className="card">
          <div className="empty-state">
            {aulas.length === 0
              ? 'Nenhuma conferência registrada ainda.'
              : 'Nenhuma aula atende a esses critérios.'}
            <div className="empty-state__hint">
              {aulas.length === 0
                ? 'A rotina varre os cursos monitorados de hora em hora.'
                : 'Tente remover algum filtro.'}
            </div>
          </div>
        </section>
      ) : (
        <div className="gravacoes-grade">
          {filtradas.map((a) => (
            <Cartao
              key={a.id}
              aula={a}
              curso={nomePorCurso.get(a.cursoId) ?? a.cursoId}
              publicaNoCanvas={publicaNoCanvasPorCurso.get(a.cursoId) ?? false}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Uma aula.
 *
 * A tarja da esquerda é a data, e não um ícone: a data é a identidade da aula
 * neste sistema inteiro — é por data completa que o SAS acha a página no
 * Canvas, e é por data que a coordenação procura ("a de terça saiu?"). A cor
 * da tarja repete a situação para a grade ser legível de longe, sem ler.
 */
function Cartao({
  aula,
  curso,
  publicaNoCanvas,
}: {
  aula: GravacaoAula;
  curso: string;
  publicaNoCanvas: boolean;
}) {
  const data = partesDaData(aula.iniciadaEm);
  // O título do vídeo só existe depois da publicação; até lá o que há é o
  // texto cru que o professor escreveu no Canvas.
  const titulo = tituloParaCartao(aula.youtubeTitulo || aula.titulo);
  const hora = formatarHora(aula.iniciadaEm);
  const duracao = aula.duracaoMinutos == null ? null : formatarDuracao(aula.duracaoMinutos);

  return (
    <article className={`card gravacao gravacao--${situacaoDe(aula)}`}>
      <div className={`gravacao__data ${toneSituacao(situacaoDe(aula))}`}>
        {data ? (
          <>
            <span className="gravacao__dia">{data.dia}</span>
            <span className="gravacao__mes">{data.mes}</span>
            <span className="gravacao__ano">{data.ano}</span>
          </>
        ) : (
          <span className="gravacao__mes">agendada</span>
        )}
      </div>

      <div className="gravacao__corpo">
        <h2 className="gravacao__titulo">{titulo}</h2>
        <p className="gravacao__curso">{curso}</p>

        <div className="gravacao__selos">
          <SeloSituacao aula={aula} />
          <SeloCanvasGravacao aula={aula} publicaNoCanvas={publicaNoCanvas} />
        </div>

        {situacaoDe(aula) === 'erro' && aula.erroDetalhe && (
          <p className="gravacao__erro" title={aula.erroDetalhe}>
            {aula.erroDetalhe}
          </p>
        )}

        <div className="gravacao__rodape">
          <span className="gravacao__quando">
            {[hora, duracao].filter(Boolean).join(' · ') || 'ainda sem gravação'}
          </span>
          {aula.youtubeUrl && (
            <a
              className="gravacao__assistir"
              href={aula.youtubeUrl}
              target="_blank"
              rel="noreferrer"
            >
              Assistir →
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
