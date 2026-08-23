import { useMemo, useState } from 'react';

import { LinhaTemporal } from '../../componentes/ui/LinhaTemporal';
import type { PontoTemporal } from '../../componentes/ui/LinhaTemporal';
import { ordenarLinhas, proximaOrdenacao } from '../../componentes/ui/ordenacao';
import type { ColunaTabela, Ordenacao } from '../../componentes/ui/ordenacao';
import { TheadOrdenavel } from '../../componentes/ui/TabelaOrdenavel';
import { resumoRecorrencia, seriesPorAno } from '../../dominio/banco';
import { useEstatisticasBanco } from '../../hooks/banco';
import type { MateriaBanco, RecorrenciaTopico, VestibularBanco } from '../../tipos/banco';

// Recorrência por tópico — sem biblioteca de gráfico (docs/22 §P4).
//
// O site de origem usava Chart.js via jsdelivr. A biblioteca sai por ser
// terceiro na página (CLAUDE.md, regra 6: dados de menores) e não volta como
// npm: o SAS não tem biblioteca de gráfico nenhuma por decisão de projeto.
//
// Duas leituras, e a escolha de cada componente tem motivo:
//
//  · A CURVA do tópico ao longo dos anos vai em `LinhaTemporal`. É para isso
//    que `seriesPorAno` existe no domínio, e o componente já tem viewBox e
//    `max-width: 100%` — escala no celular sem trabalho novo.
//    Herda de lá os rótulos "Ciclo atual" e "Média:", que aqui querem dizer
//    "recorrência" e "questões no ano". Trocá-los mexeria nas telas de ciclo
//    da coordenação, que é o que o componente foi escrito para servir; a
//    seção diz o que o eixo é, e o rótulo do componente fica como está.
//
//  · O RANKING por tópico vai em `TabelaOrdenavel`, não em `Histograma`. O
//    contrato do histograma é faixa numérica de nota (`largura_bin`, tooltip
//    "N alunos"): tópico do edital não é faixa, e forçá-lo daria eixo x com
//    "0,0 · 1,0 · 2,0" no lugar dos nomes. Tabela certa vale mais que gráfico
//    pela metade (docs/22 §P4) — e ordenável ela responde mais perguntas.

interface Props {
  materiaInicial?: MateriaBanco;
  vestibular?: VestibularBanco;
}

/** Espelha o Literal de `schemas/banco.py` — a lista canônica das três matérias. */
const MATERIAS: MateriaBanco[] = ['Física', 'Química', 'Matemática'];

const COLUNAS: ColunaTabela<RecorrenciaTopico>[] = [
  { chave: 'topico', label: 'Tópico', valor: (t) => t.nome },
  { chave: 'bloco', label: 'Bloco', valor: (t) => t.blocoNome },
  { chave: 'total', label: 'Total', tipo: 'numero', valor: (t) => t.total },
  { chave: 'ita', label: 'ITA', tipo: 'numero', valor: (t) => t.porVestibular.ITA ?? 0 },
  { chave: 'ime', label: 'IME', tipo: 'numero', valor: (t) => t.porVestibular.IME ?? 0 },
  { chave: 'fase1', label: 'Fase 1', tipo: 'numero', valor: (t) => t.porFase[1] ?? 0 },
  { chave: 'fase2', label: 'Fase 2', tipo: 'numero', valor: (t) => t.porFase[2] ?? 0 },
];

export function Estatisticas({ materiaInicial, vestibular }: Props) {
  const [materia, setMateria] = useState<MateriaBanco>(materiaInicial ?? MATERIAS[0]);
  const [ordenacao, setOrdenacao] = useState<Ordenacao | null>({ chave: 'total', dir: 'desc' });
  const [codigoEscolhido, setCodigoEscolhido] = useState<string | null>(null);

  const { data, isPending, isError, error } = useEstatisticasBanco(materia, vestibular);

  const linhas = useMemo(
    () => ordenarLinhas(data?.topicos ?? [], COLUNAS, ordenacao),
    [data, ordenacao],
  );

  // Sem escolha, a curva abre no tópico mais recorrente — é a pergunta que
  // traz o coordenador aqui ("o que mais cai").
  const topico = useMemo(() => {
    if (!data) return null;
    const escolhido = data.topicos.find((t) => t.codigo === codigoEscolhido);
    return escolhido ?? resumoRecorrencia(data, 1)[0] ?? null;
  }, [data, codigoEscolhido]);

  const pontos: PontoTemporal[] = useMemo(() => {
    if (!data || !topico) return [];
    const serie = seriesPorAno(topico, data.anos);
    return serie.anos.map((ano, i) => ({
      nome: `${topico.nome} · ${ano}`,
      rotuloCurto: String(ano),
      data: null,
      media: serie.totais[i],
    }));
  }, [data, topico]);

  // O eixo do componente é 0–10 por padrão (nota). Aqui é contagem: sem subir o
  // teto, um tópico que caiu 12 vezes num ano sairia do gráfico pela borda.
  const tetoY = Math.max(10, Math.ceil(Math.max(0, ...pontos.map((p) => p.media)) / 2) * 2);

  return (
    <div className="banco-estatisticas">
      <div className="banco-cabecalho">
        <h1 className="banco-cabecalho__titulo">Recorrência por assunto</h1>
        <span className="banco-cabecalho__meta">
          {vestibular ? `${vestibular} · 2018–2025` : 'ITA e IME · 2018–2025'}
        </span>
      </div>

      <div className="banco-filtros__chips">
        {MATERIAS.map((m) => (
          <button
            key={m}
            type="button"
            className={`banco-chip${m === materia ? ' banco-chip--ativo' : ''}`}
            aria-pressed={m === materia}
            onClick={() => {
              setMateria(m);
              // O código do tópico só é único dentro da matéria (0028): mantê-lo
              // ao trocar apontaria para outro assunto sem avisar.
              setCodigoEscolhido(null);
            }}
          >
            {m}
          </button>
        ))}
      </div>

      {isError && (
        <p className="banco-vazio">
          {(error as Error)?.message || 'Não foi possível carregar as estatísticas.'}
        </p>
      )}
      {isPending && !isError && <p className="banco-vazio">Carregando estatísticas…</p>}

      {data && (
        <>
          <section className="banco-estatisticas__secao">
            <div className="banco-estatisticas__grade">
              <Indicador rotulo={`Questões de ${data.materia}`} valor={data.totalQuestoes} />
              <Indicador
                rotulo="Assuntos com pelo menos uma questão"
                valor={data.topicos.filter((t) => t.total > 0).length}
              />
              <Indicador rotulo="Sem classificação" valor={data.semClassificacao} />
              <Indicador
                rotulo="Anos cobertos"
                valor={
                  data.anos.length > 0
                    ? `${Math.min(...data.anos)}–${Math.max(...data.anos)}`
                    : '—'
                }
              />
            </div>
          </section>

          <section className="banco-estatisticas__secao">
            <h2 className="banco-cabecalho__titulo">O que mais cai</h2>
            <p className="banco-cabecalho__meta">
              Questão classificada em dois assuntos conta nos dois — questão mista é a regra
              (docs/22 §1.2). Clique no assunto para ver a curva por ano.
            </p>

            {linhas.length === 0 ? (
              <p className="banco-vazio">Nenhum assunto com questão nesta matéria.</p>
            ) : (
              <div className="banco-estatisticas__tabela">
                <table className="data-table">
                  <TheadOrdenavel
                    colunas={COLUNAS}
                    ordenacao={ordenacao}
                    onOrdenar={(chave) => setOrdenacao((o) => proximaOrdenacao(o, chave))}
                  />
                  <tbody>
                    {linhas.map((t) => (
                      <tr key={t.codigo}>
                        <td>
                          <button
                            type="button"
                            className="btn-link-resolver"
                            aria-pressed={t.codigo === topico?.codigo}
                            onClick={() => setCodigoEscolhido(t.codigo)}
                          >
                            {`${t.codigo} · ${t.nome}`}
                          </button>
                        </td>
                        <td>{t.blocoNome}</td>
                        <td>{t.total}</td>
                        <td>{t.porVestibular.ITA ?? 0}</td>
                        <td>{t.porVestibular.IME ?? 0}</td>
                        <td>{t.porFase[1] ?? 0}</td>
                        <td>{t.porFase[2] ?? 0}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="banco-estatisticas__secao">
            <h2 className="banco-cabecalho__titulo">
              {topico ? `${topico.codigo} · ${topico.nome}` : 'Curva por ano'}
            </h2>
            <p className="banco-cabecalho__meta">
              Quantas questões deste assunto caíram em cada ano. Ano sem ocorrência é zero, não
              buraco: a curva que pula de 2019 para 2021 leria "caiu todo ano".
            </p>
            <div className="banco-estatisticas__grafico">
              {topico ? (
                <LinhaTemporal
                  pontos={pontos}
                  yMax={tetoY}
                  mostrarCicloAnterior={false}
                  rotuloSerie="Questões no ano"
                  rotuloValor="Questões"
                />
              ) : (
                <p className="banco-vazio">Escolha um assunto na tabela acima.</p>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Indicador({ rotulo, valor }: { rotulo: string; valor: number | string }) {
  return (
    <div className="banco-estatisticas__cartao">
      <span className="banco-estatisticas__rotulo">{rotulo}</span>
      <span className="banco-estatisticas__valor">{valor}</span>
    </div>
  );
}
