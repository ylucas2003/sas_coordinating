import { useEffect, useMemo, useState } from 'react';

import { alternarAno, anosMarcados } from '../../dominio/banco';
import { useTaxonomia } from '../../hooks/banco';
import type {
  BlocoTaxonomia,
  FiltrosBanco as Filtros,
  MateriaBanco,
  TaxonomiaMateria,
  VestibularBanco,
} from '../../tipos/banco';

// Coluna de filtros do banco (docs/22 §P3): vestibular, ano, fase, matéria e a
// árvore de assuntos do edital.
//
// Empilhada no celular e coluna grudada a partir de 880px — quem decide é o
// `.banco-layout`, não este arquivo (styles/banco.css).

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

  useEffect(() => {
    const emVigor = filtros.busca ?? '';
    if (rascunhoBusca.trim() === emVigor) return;
    const relogio = window.setTimeout(
      () => onFiltrar({ busca: rascunhoBusca.trim() || undefined }),
      ESPERA_BUSCA_MS,
    );
    return () => window.clearTimeout(relogio);
  }, [rascunhoBusca, filtros.busca, onFiltrar]);

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

  return (
    <aside className="banco-filtros" aria-label="Filtros do banco de questões">
      <div className="banco-filtros__grupo">
        <label className="banco-filtros__rotulo" htmlFor="banco-busca">
          Buscar no enunciado
        </label>
        <input
          id="banco-busca"
          className="banco-filtros__busca"
          type="search"
          inputMode="search"
          placeholder="termodinâmica, log, polinômio…"
          value={rascunhoBusca}
          onChange={(ev) => setRascunhoBusca(ev.target.value)}
        />
      </div>

      <Grupo rotulo="Matéria">
        {taxonomias.map((t) => (
          <Chip
            key={t.materia}
            ativo={filtros.materia === t.materia}
            contagem={t.totalQuestoes}
            onClick={() => escolherMateria(t.materia)}
          >
            {t.materia}
          </Chip>
        ))}
        {isPending && <span className="banco-filtros__rotulo">Carregando…</span>}
      </Grupo>

      {/* Grupo vazio não vira rótulo órfão enquanto a taxonomia não chega. */}
      {vestibulares.length > 0 && (
        <Grupo rotulo="Vestibular">
          {vestibulares.map((v: VestibularBanco) => (
            <Chip
              key={v}
              ativo={filtros.vestibular === v}
              onClick={() => onFiltrar({ vestibular: filtros.vestibular === v ? undefined : v })}
            >
              {v}
            </Chip>
          ))}
        </Grupo>
      )}

      {fases.length > 0 && (
        <Grupo rotulo="Fase">
          {fases.map((f) => (
            <Chip
              key={f}
              ativo={filtros.fase === f}
              onClick={() => onFiltrar({ fase: filtros.fase === f ? undefined : f })}
            >
              {`Fase ${f}`}
            </Chip>
          ))}
        </Grupo>
      )}

      {anos.length > 0 && (
        <Grupo rotulo="Ano">
          {anos.map((ano) => (
            <Chip
              key={ano}
              // ⚠️ MÚLTIPLA ESCOLHA, e abre com TODOS marcados (decisão de
              // 02/09). "Sem filtro" e "todos os anos" são o mesmo recorte, e
              // mostrá-lo apagado diria que nada está selecionado quando tudo
              // está. Quem traduz é `anosMarcados`, compartilhado com o casco
              // do aluno: as duas telas filtram o mesmo acervo pela mesma regra.
              ativo={anosMarcados(filtros.anos, anos).has(ano)}
              onClick={() => onFiltrar({ anos: alternarAno(filtros.anos, anos, ano) })}
            >
              {ano}
            </Chip>
          ))}
        </Grupo>
      )}

      <div className="banco-filtros__grupo">
        <span className="banco-filtros__rotulo">Assunto</span>
        {daMateria ? (
          <ArvoreTopicos
            materia={daMateria}
            topicoAtivo={filtros.topico ?? null}
            blocosAbertos={blocosAbertos}
            onAlternarBloco={alternarBloco}
            onEscolherTopico={(codigo) =>
              onFiltrar({
                // Tópico sem matéria casaria o mesmo código nas três (consultas.py).
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

      {algumAtivo && (
        <div className="banco-filtros__chips">
          <Chip ativo={false} onClick={limparTudo}>
            Limpar filtros
          </Chip>
        </div>
      )}
    </aside>
  );
}

function Grupo({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="banco-filtros__grupo">
      <span className="banco-filtros__rotulo">{rotulo}</span>
      <div className="banco-filtros__chips">{children}</div>
    </div>
  );
}

function Chip({
  ativo,
  contagem,
  onClick,
  children,
}: {
  ativo: boolean;
  contagem?: number;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      className={`banco-chip${ativo ? ' banco-chip--ativo' : ''}`}
      aria-pressed={ativo}
      onClick={onClick}
    >
      {children}
      {contagem != null && <span className="banco-chip__contagem">{contagem}</span>}
    </button>
  );
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
