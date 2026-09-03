import { useEffect, useMemo, useRef, useState } from 'react';

import { BarraFiltros, Busca, Pills } from '../../componentes/ui/filtros/BarraFiltros';
import { alternarAno, anosMarcados } from '../../dominio/banco';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import { useTaxonomia } from '../../hooks/banco';
import type {
  BlocoTaxonomia,
  FiltrosBanco as Filtros,
  MateriaBanco,
  TaxonomiaMateria,
  VestibularBanco,
} from '../../tipos/banco';

// Os filtros do banco, agora na `BarraFiltros` da coordenação (docs/33 §7).
//
// **Por que isto mudou.** A C.1 fechou a dívida de "dois sistemas de filtro"
// para as sete telas da coordenação; o Banco nasceu depois, com `<aside>`
// próprio, e reabriu a dívida. O cabeçalho de `Banco.tsx` justificava a
// exceção — "são muitos assuntos por edital e eles não caberiam numa linha
// (docs/22 §3.5)" — e a justificativa **estava certa enquanto a faixa não
// colapsava**. Com o colapso, ela deixou de valer, e a árvore de assuntos
// passou a caber num grupo que abre em painel.
//
// ⚠️ **Esta tela serve os DOIS cascos.** `Banco.tsx` recebe `perfil`, e a
// mesma árvore roda dentro do casco do aluno, onde `.tela` é um bloco da
// coluna de `.alu-body__inner`. O tema não é o risco (banco.css sempre leu
// `--color-*`, não `--alu-*`); o layout é.
//
// ⚠️ **O que a coluna fazia e a faixa não faz:** grudar e rolar sozinha acima
// de 880px (`position: sticky`, `max-height: 100dvh`). Com uma árvore de 65
// tópicos aberta, isso valia. É o custo assumido da troca, e a mitigação é o
// painel do grupo Assunto rolar por dentro.
//
// O que NÃO podia mudar, e cada um custou um bug em algum momento:
//   · a espera de 350ms antes de consultar (a listagem é do servidor);
//   · trocar de matéria derruba o tópico junto — '1.1' existe nas três e
//     significa coisa diferente em cada uma (0028);
//   · "Sem assunto" filtra NO SERVIDOR, e não peneirando no cliente.

interface Props {
  filtros: Filtros;
  /** Campo com `undefined` = filtro removido. A casca normaliza e volta à página 1. */
  onFiltrar: (mudanca: Partial<Filtros>) => void;
}

/**
 * Espera de digitação antes de consultar. Sem isto cada tecla é uma requisição
 * e uma entrada nova no cache do React Query — e no celular, com teclado
 * lento, a lista pisca a cada letra.
 */
const ESPERA_BUSCA_MS = 350;

export function FiltrosBanco({ filtros, onFiltrar }: Props) {
  const { data: taxonomias = [], isPending } = useTaxonomia();
  const [rascunhoBusca, setRascunhoBusca] = useState(filtros.busca ?? '');
  const [blocosAbertos, setBlocosAbertos] = useState<ReadonlySet<string>>(new Set());
  const [painelAssunto, setPainelAssunto] = useState(false);
  const refAssunto = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const emVigor = filtros.busca ?? '';
    if (rascunhoBusca.trim() === emVigor) return;
    const relogio = window.setTimeout(
      () => onFiltrar({ busca: rascunhoBusca.trim() || undefined }),
      ESPERA_BUSCA_MS,
    );
    return () => window.clearTimeout(relogio);
  }, [rascunhoBusca, filtros.busca, onFiltrar]);

  // Clique fora fecha o painel de assuntos — mesmo padrão do `BotaoAjuda` do
  // Painel. Sem isto ele fica aberto por cima da lista de questões.
  useEffect(() => {
    if (!painelAssunto) return;
    function aoClicarFora(ev: MouseEvent) {
      if (!refAssunto.current?.contains(ev.target as Node)) setPainelAssunto(false);
    }
    document.addEventListener('click', aoClicarFora);
    return () => document.removeEventListener('click', aoClicarFora);
  }, [painelAssunto]);

  const daMateria: TaxonomiaMateria | null = useMemo(
    () => taxonomias.find((t) => t.materia === filtros.materia) ?? null,
    [taxonomias, filtros.materia],
  );

  // Sem matéria escolhida, ano/fase/vestibular são a união das três — é o
  // recorte que a listagem devolve, e oferecer um ano que não existe em nenhuma
  // matéria daria página vazia sem explicação.
  const anos = useMemo(() => {
    const fonte = daMateria ? [daMateria] : taxonomias;
    return [...new Set(fonte.flatMap((t) => t.anos))].sort((a, b) => b - a);
  }, [daMateria, taxonomias]);

  const fases = useMemo(() => {
    const fonte = daMateria ? [daMateria] : taxonomias;
    return [...new Set(fonte.flatMap((t) => t.fases))].sort((a, b) => a - b);
  }, [daMateria, taxonomias]);

  const vestibulares = useMemo(() => {
    const fonte = daMateria ? [daMateria] : taxonomias;
    return [...new Set(fonte.flatMap((t) => t.vestibulares))].sort();
  }, [daMateria, taxonomias]);

  const algumAtivo =
    filtros.materia != null ||
    filtros.vestibular != null ||
    (filtros.anos?.length ?? 0) > 0 ||
    filtros.fase != null ||
    filtros.topico != null ||
    (filtros.busca ?? '') !== '';

  function limparTudo() {
    setRascunhoBusca('');
    onFiltrar({
      materia: undefined,
      vestibular: undefined,
      anos: undefined,
      fase: undefined,
      topico: undefined,
      busca: undefined,
    });
  }

  /**
   * Trocar de matéria derruba o tópico junto: '1.1' existe nas três e significa
   * coisa diferente em cada uma (0028), então o código herdado apontaria para
   * outro assunto sem avisar.
   */
  function escolherMateria(materia: MateriaBanco) {
    const mesma = filtros.materia === materia;
    onFiltrar({ materia: mesma ? undefined : materia, topico: undefined });
  }

  function alternarBloco(codigo: string) {
    setBlocosAbertos((abertos) => {
      const novo = new Set(abertos);
      if (novo.has(codigo)) novo.delete(codigo);
      else novo.add(codigo);
      return novo;
    });
  }

  /** Um filtro de valor único vira um `Set` de zero ou um para as `Pills`. */
  function conjunto<V>(valor: V | null | undefined): ReadonlySet<V> {
    return new Set(valor == null ? [] : [valor]);
  }

  const rotuloAssunto = nomeDoTopico(daMateria, filtros.topico ?? null);

  return (
    <BarraFiltros
      tela="banco"
      algumAtivo={algumAtivo}
      onLimpar={limparTudo}
      grupos={[
        {
          chave: 'busca',
          rotulo: 'Enunciado',
          resumo: resumirTexto(rascunhoBusca),
          corpo: (
            <Busca
              valor={rascunhoBusca}
              onChange={setRascunhoBusca}
              placeholder="termodinâmica, log, polinômio…"
              rotulo="Buscar no enunciado das questões"
            />
          ),
        },
        {
          chave: 'materia',
          rotulo: 'Matéria',
          resumo: filtros.materia ?? null,
          corpo: isPending ? (
            <span className="barra-filtros__vazio">Carregando…</span>
          ) : (
            <Pills
              opcoes={taxonomias.map((t) => ({
                valor: t.materia,
                label: t.materia,
                contagem: t.totalQuestoes,
              }))}
              selecionados={conjunto(filtros.materia)}
              onToggle={(m) => escolherMateria(m as MateriaBanco)}
            />
          ),
        },
        vestibulares.length > 0 && {
          chave: 'vestibular',
          rotulo: 'Vestibular',
          resumo: filtros.vestibular ?? null,
          corpo: (
            <Pills
              opcoes={vestibulares.map((v: VestibularBanco) => ({ valor: v, label: v }))}
              selecionados={conjunto(filtros.vestibular)}
              onToggle={(v) =>
                onFiltrar({ vestibular: filtros.vestibular === v ? undefined : v })}
            />
          ),
        },
        fases.length > 0 && {
          chave: 'fase',
          rotulo: 'Fase',
          resumo: filtros.fase == null ? null : `Fase ${filtros.fase}`,
          corpo: (
            <Pills
              opcoes={fases.map((f) => ({ valor: f, label: `Fase ${f}` }))}
              selecionados={conjunto(filtros.fase)}
              onToggle={(f) => onFiltrar({ fase: filtros.fase === f ? undefined : f })}
            />
          ),
        },
        anos.length > 0 && {
          chave: 'ano',
          rotulo: 'Ano',
          // ⚠️ MÚLTIPLA ESCOLHA, e abre com TODOS marcados (decisão de 02/09).
          // "Sem filtro" e "todos os anos" são o mesmo recorte; mostrá-lo
          // apagado diria que nada está selecionado, quando tudo está. Quem
          // traduz é `anosMarcados`, compartilhado com o casco do aluno — as
          // duas telas filtram o mesmo acervo pela mesma regra.
          resumo: resumirSelecao(
            new Set(filtros.anos ?? []),
            anos.map((a) => ({ valor: a, label: String(a) })),
            'ano', 'anos',
          ),
          corpo: (
            <Pills
              opcoes={anos.map((ano) => ({ valor: ano, label: String(ano) }))}
              selecionados={anosMarcados(filtros.anos, anos)}
              onToggle={(a) => onFiltrar({ anos: alternarAno(filtros.anos, anos, a) })}
            />
          ),
        },
        {
          chave: 'assunto',
          rotulo: 'Assunto',
          resumo: rotuloAssunto,
          // A árvore inteira num painel: 65 tópicos em 3 níveis não cabem numa
          // linha de pílulas, e transformá-los em pílulas planas perderia a
          // hierarquia do edital — que é o que o aluno reconhece.
          corpo: (
            <div className="banco-assunto" ref={refAssunto}>
              <button
                type="button"
                className={`pill${filtros.topico ? ' is-active' : ''}`}
                aria-expanded={painelAssunto}
                onClick={(ev) => {
                  ev.stopPropagation();
                  setPainelAssunto((v) => !v);
                }}
              >
                {rotuloAssunto ?? 'Escolher assunto'}
                <span aria-hidden="true"> ▾</span>
              </button>

              {painelAssunto && (
                <div className="banco-assunto__painel">
                  {daMateria ? (
                    <ArvoreTopicos
                      materia={daMateria}
                      topicoAtivo={filtros.topico ?? null}
                      blocosAbertos={blocosAbertos}
                      onAlternarBloco={alternarBloco}
                      onEscolherTopico={(codigo) =>
                        onFiltrar({
                          // Tópico sem matéria casaria o mesmo código nas três
                          // (consultas.py).
                          materia: daMateria.materia,
                          topico: filtros.topico === codigo ? undefined : codigo,
                        })
                      }
                    />
                  ) : (
                    <p className="banco-filtros__rotulo">
                      Escolha uma matéria para ver os assuntos do edital.
                    </p>
                  )}
                </div>
              )}
            </div>
          ),
        },
      ]}
    />
  );
}

/** O nome do tópico escolhido, para o botão e para o resumo da faixa. */
function nomeDoTopico(materia: TaxonomiaMateria | null, codigo: string | null): string | null {
  if (!codigo) return null;
  if (codigo === TOPICO_SEM_CLASSIFICACAO) return 'Sem assunto';
  if (!materia) return codigo;
  for (const bloco of materia.blocos) {
    for (const topico of bloco.topicos) {
      if (topico.codigo === codigo) return `${topico.codigo} · ${topico.nome}`;
    }
  }
  return codigo;
}

/** Espelha `consultas.TOPICO_SEM_CLASSIFICACAO` do backend. */
const TOPICO_SEM_CLASSIFICACAO = 'sem-assunto';

function ArvoreTopicos({
  materia,
  topicoAtivo,
  blocosAbertos,
  onAlternarBloco,
  onEscolherTopico,
}: {
  materia: TaxonomiaMateria;
  topicoAtivo: string | null;
  blocosAbertos: ReadonlySet<string>;
  onAlternarBloco: (codigo: string) => void;
  onEscolherTopico: (codigo: string) => void;
}) {
  const temAtivo = (bloco: BlocoTaxonomia) => bloco.topicos.some((t) => t.codigo === topicoAtivo);

  return (
    <ul className="banco-arvore">
      {materia.blocos.map((bloco) => {
        // O bloco do tópico filtrado abre sozinho: fechado, o filtro em vigor
        // ficaria invisível e o aluno leria a listagem como se fosse tudo.
        const aberto = blocosAbertos.has(bloco.codigo) || temAtivo(bloco);
        return (
          <li key={bloco.codigo} className="banco-arvore__ramo">
            <button
              type="button"
              className="banco-arvore__bloco"
              aria-expanded={aberto}
              onClick={() => onAlternarBloco(bloco.codigo)}
            >
              <span aria-hidden="true">{aberto ? '▾' : '▸'}</span>
              <span className="banco-arvore__nome">{`${bloco.codigo} · ${bloco.nome}`}</span>
              <span className="banco-arvore__contagem">{bloco.totalQuestoes}</span>
            </button>

            {aberto && (
              <ul className="banco-arvore">
                {bloco.topicos.map((topico) => {
                  const ativo = topico.codigo === topicoAtivo;
                  return (
                    <li key={topico.codigo} className="banco-arvore__ramo">
                      <button
                        type="button"
                        className={`banco-arvore__topico${ativo ? ' is-active' : ''}`}
                        aria-pressed={ativo}
                        title={topico.assuntos.join(' · ')}
                        onClick={() => onEscolherTopico(topico.codigo)}
                      >
                        <span className="banco-arvore__nome">
                          {`${topico.codigo} · ${topico.nome}`}
                        </span>
                        <span className="banco-arvore__contagem">{topico.totalQuestoes}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </li>
        );
      })}

      {materia.semClassificacao > 0 && (
        <li className="banco-arvore__ramo">
          {/*
            As 40 sem classificação têm lugar visível, e não somem do filtro:
            escondê-las daria ao aluno um recorte incompleto sem aviso
            (docs/22 §8, risco 3).

            Filtra de verdade — `GET /banco/questoes?topico=sem-assunto` faz a
            diferença de conjuntos no servidor (consultas._ids_sem_classificacao),
            então total e paginação continuam certos. Peneirar no cliente é que
            daria número errado sem parecer errado, que é a armadilha 2 do
            CLAUDE.md.
          */}
          <button
            type="button"
            className={`banco-arvore__topico banco-arvore__topico--sem-classificacao${
              topicoAtivo === TOPICO_SEM_CLASSIFICACAO ? ' is-active' : ''
            }`}
            aria-pressed={topicoAtivo === TOPICO_SEM_CLASSIFICACAO}
            title="Questões que ninguém classificou ainda."
            onClick={() => onEscolherTopico(TOPICO_SEM_CLASSIFICACAO)}
          >
            <span className="banco-arvore__nome">Sem assunto</span>
            <span className="banco-arvore__contagem">{materia.semClassificacao}</span>
          </button>
        </li>
      )}
    </ul>
  );
}
