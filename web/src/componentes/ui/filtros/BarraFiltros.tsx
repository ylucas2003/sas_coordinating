import type { ReactNode } from 'react';

/**
 * Filtros em faixa horizontal, acima da tabela.
 *
 * Substituiu a sidebar colapsável (`PainelFiltros`): com o rail de ícones
 * ocupando a esquerda, uma segunda coluna de filtros comia largura justamente
 * das tabelas largas — que são a razão de o SAS existir. Aqui todos os grupos
 * ficam abertos: o custo de esconder um filtro é o usuário não saber que ele
 * existe, e são poucos o bastante para caber numa linha.
 */

export interface GrupoFiltro {
  chave: string;
  rotulo: string;
  corpo: ReactNode;
}

interface Props {
  grupos: Array<GrupoFiltro | null | false>;
  /** Omitido = sem botão de limpar. */
  onLimpar?: () => void;
  algumAtivo?: boolean;
}

export function BarraFiltros({ grupos, onLimpar, algumAtivo = false }: Props) {
  const visiveis = grupos.filter((g): g is GrupoFiltro => Boolean(g));
  if (!visiveis.length) return null;

  return (
    <div className="barra-filtros">
      {visiveis.map((g, i) => (
        <div key={g.chave} className="barra-filtros__grupo">
          {i > 0 && <span className="barra-filtros__sep" aria-hidden="true" />}
          <span className="barra-filtros__rotulo" id={`filtro-${g.chave}`}>
            {g.rotulo}
          </span>
          <div className="barra-filtros__grupo" role="group" aria-labelledby={`filtro-${g.chave}`}>
            {g.corpo}
          </div>
        </div>
      ))}

      {onLimpar && (
        <button className="barra-filtros__limpar" disabled={!algumAtivo} onClick={onLimpar}>
          Limpar filtros
        </button>
      )}
    </div>
  );
}

// ─── Corpos de grupo ───────────────────────────────────────────────────────

export interface OpcaoPill<V> {
  valor: V;
  label: string;
  contagem?: number;
}

/**
 * Pílulas com contagem. Esconde as que não trariam resultado, mas mantém as
 * ativas visíveis — senão o usuário fica preso num filtro que não enxerga
 * mais para desmarcar.
 *
 * `contagem` ausente significa "esta tela não conta", e NÃO "zero": o Painel
 * filtra alunos por sede/turma sem calcular quantos caem em cada opção, e
 * escondê-las deixava o grupo inteiro vazio. Quem conta deve passar `?? 0`
 * para que a opção sem resultado continue oculta.
 */
export function Pills<V extends string | number>({
  opcoes,
  selecionados,
  onToggle,
}: {
  opcoes: Array<OpcaoPill<V>>;
  selecionados: ReadonlySet<V>;
  onToggle: (valor: V) => void;
}) {
  const visiveis = opcoes.filter(
    (o) => selecionados.has(o.valor) || o.contagem == null || o.contagem > 0,
  );
  if (!visiveis.length) return <span className="barra-filtros__vazio">—</span>;

  return (
    <>
      {visiveis.map((o) => {
        const ativo = selecionados.has(o.valor);
        return (
          <button
            key={String(o.valor)}
            className={`pill${ativo ? ' is-active' : ''}`}
            aria-pressed={ativo}
            onClick={() => onToggle(o.valor)}
          >
            {o.label}
            {o.contagem != null && <span className="pill__contagem">{o.contagem}</span>}
          </button>
        );
      })}
    </>
  );
}

/** Seleção única — um valor ativo por vez (o Painel escolhe um ciclo assim). */
export function PillsUnica<V extends string | number>({
  opcoes,
  selecionado,
  onSelecionar,
}: {
  opcoes: Array<{ valor: V; label: string }>;
  selecionado: V | null;
  onSelecionar: (valor: V) => void;
}) {
  if (!opcoes.length) return <span className="barra-filtros__vazio">—</span>;

  return (
    <>
      {opcoes.map((o) => (
        <button
          key={String(o.valor)}
          className={`pill${o.valor === selecionado ? ' is-active' : ''}`}
          aria-pressed={o.valor === selecionado}
          onClick={() => onSelecionar(o.valor)}
        >
          {o.label}
        </button>
      ))}
    </>
  );
}

/**
 * Intervalo de datas. Extremo vazio = aberto daquele lado. Valores em ISO
 * (YYYY-MM-DD) ou `null`.
 */
export function RangeDatas({
  inicio,
  fim,
  onChange,
}: {
  inicio: string | null;
  fim: string | null;
  onChange: (valor: { inicio: string | null; fim: string | null }) => void;
}) {
  return (
    <>
      <input
        type="date"
        className="pill-campo"
        value={inicio ?? ''}
        aria-label="Data inicial"
        onChange={(ev) => onChange({ inicio: ev.target.value || null, fim })}
      />
      <span className="barra-filtros__rotulo">até</span>
      <input
        type="date"
        className="pill-campo"
        value={fim ?? ''}
        aria-label="Data final"
        onChange={(ev) => onChange({ inicio, fim: ev.target.value || null })}
      />
    </>
  );
}
