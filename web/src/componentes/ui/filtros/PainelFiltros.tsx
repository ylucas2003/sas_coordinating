import type { ReactNode } from 'react';
import { IconeFiltro } from './IconeFiltro';
import type { TipoIcone } from './IconeFiltro';

// Filtros laterais — componente único das quatro telas com sidebar.
//
// Junta o contêiner do Painel (seção com ícone, colapsável) com os chips
// contáveis das listagens. O corpo de uma seção é livre — hoje chips, lista de
// item único e intervalo de datas — porque nem todo filtro é uma lista de
// opções contáveis.

export interface SecaoFiltro {
  chave: string;
  rotulo: string;
  icone: TipoIcone;
  corpo: ReactNode;
}

interface PropsPainel {
  secoes: Array<SecaoFiltro | null | false>;
  /** Chaves das seções expandidas. */
  abertas: ReadonlySet<string>;
  onToggleSecao: (chave: string) => void;
  /** Omitido = sem botão de limpar. */
  onLimpar?: () => void;
  algumAtivo?: boolean;
}

export function PainelFiltros({
  secoes,
  abertas,
  onToggleSecao,
  onLimpar,
  algumAtivo = false,
}: PropsPainel) {
  return (
    <div className="filtros-root">
      {secoes.filter((s): s is SecaoFiltro => Boolean(s)).map((s) => (
        <Secao key={s.chave} secao={s} aberta={abertas.has(s.chave)} onToggle={onToggleSecao} />
      ))}

      {onLimpar && (
        <div className="filtros-rodape">
          <button className="sim-filtros__reset" disabled={!algumAtivo} onClick={onLimpar}>
            Limpar filtros
          </button>
        </div>
      )}
    </div>
  );
}

function Secao({
  secao,
  aberta,
  onToggle,
}: {
  secao: SecaoFiltro;
  aberta: boolean;
  onToggle: (chave: string) => void;
}) {
  return (
    <div className="filtros-secao">
      <button
        className="filtros-secao__header"
        aria-expanded={aberta}
        onClick={() => onToggle(secao.chave)}
      >
        <span className="filtros-secao__icon">
          <IconeFiltro tipo={secao.icone} />
        </span>
        <span className="filtros-secao__label">{secao.rotulo}</span>
        <span className={`filtros-secao__chevron${aberta ? ' is-aberto' : ''}`}>
          <IconeFiltro tipo="chevron" />
        </span>
      </button>
      <div className="filtros-secao__corpo" style={aberta ? undefined : { display: 'none' }}>
        {secao.corpo}
      </div>
    </div>
  );
}

// ─── Corpos de seção ──────────────────────────────────────────────────────

export interface OpcaoChip<V> {
  valor: V;
  label: string;
  contagem?: number;
}

/**
 * Chips com contagem. Esconde os que não trariam resultado, mas mantém os
 * ativos visíveis — senão o usuário fica preso num filtro que não enxerga
 * mais para desmarcar.
 *
 * `contagem` ausente significa "esta tela não conta", e NÃO "zero": o Painel
 * filtra alunos por sede/turma sem calcular quantos caem em cada opção, e
 * escondê-las deixava a seção inteira vazia. Quem conta deve passar `?? 0`
 * para que a opção sem resultado continue oculta.
 */
export function CorpoChips<V extends string | number>({
  opcoes,
  selecionados,
  onToggle,
}: {
  opcoes: Array<OpcaoChip<V>>;
  selecionados: ReadonlySet<V>;
  onToggle: (valor: V) => void;
}) {
  const visiveis = opcoes.filter(
    (o) => selecionados.has(o.valor) || o.contagem == null || o.contagem > 0,
  );
  if (!visiveis.length) return <div className="filtros-vazio">—</div>;

  return (
    <div className="filtros-chips">
      {visiveis.map((o) => (
        <button
          key={String(o.valor)}
          className={`sim-chip${selecionados.has(o.valor) ? ' is-active' : ''}`}
          onClick={() => onToggle(o.valor)}
        >
          {o.label}
          {o.contagem != null && <span className="sim-chip__contagem">{`· ${o.contagem}`}</span>}
        </button>
      ))}
    </div>
  );
}

/**
 * Lista de seleção única — um item ativo por vez (usada pelo Painel, onde
 * escolher um ciclo monta a tabela inteira).
 */
export function CorpoLista<V extends string | number>({
  opcoes,
  selecionado,
  onSelecionar,
}: {
  opcoes: Array<{ valor: V; label: string }>;
  selecionado: V | null;
  onSelecionar: (valor: V) => void;
}) {
  if (!opcoes.length) return <div className="filtros-vazio">—</div>;

  return (
    <div>
      {opcoes.map((o) => (
        <button
          key={String(o.valor)}
          className={`filtros-item${o.valor === selecionado ? ' is-active' : ''}`}
          onClick={() => onSelecionar(o.valor)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Intervalo de datas. Extremo vazio = aberto daquele lado. Valores em ISO
 * (YYYY-MM-DD) ou `null`.
 */
export function CorpoRangeDatas({
  inicio,
  fim,
  onChange,
}: {
  inicio: string | null;
  fim: string | null;
  onChange: (valor: { inicio: string | null; fim: string | null }) => void;
}) {
  // Empilhado: lado a lado os dois <input type="date"> não cabem na sidebar.
  return (
    <div className="filtros-range">
      <label className="filtros-range__linha">
        <span className="filtros-range__rotulo">De</span>
        <input
          type="date"
          className="filtros-data"
          value={inicio ?? ''}
          aria-label="Data inicial"
          onChange={(ev) => onChange({ inicio: ev.target.value || null, fim })}
        />
      </label>
      <label className="filtros-range__linha">
        <span className="filtros-range__rotulo">Até</span>
        <input
          type="date"
          className="filtros-data"
          value={fim ?? ''}
          aria-label="Data final"
          onChange={(ev) => onChange({ inicio, fim: ev.target.value || null })}
        />
      </label>
    </div>
  );
}
