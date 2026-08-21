import type { ContagensSimulados, FiltroSimulados, OpcoesSimulados } from '../../dominio/simulados';
import { algumFiltroAtivo } from '../../dominio/simulados';

// Filtros locais em linha (não na sidebar) — usados dentro do card da ficha
// do aluno, onde a sidebar já pertence a outra coisa.

interface PropsGrupo<V extends string | number> {
  rotulo: string;
  opcoes: Array<{ valor: V; label: string; contagem?: number }>;
  selecionados: ReadonlySet<V>;
  onToggle: (valor: V) => void;
}

/**
 * Esconde chips que não trariam resultado dados os outros filtros, mas mantém
 * visíveis os ativos — senão o usuário fica preso num filtro que não consegue
 * mais ver para desmarcar.
 */
function GrupoChips<V extends string | number>({
  rotulo, opcoes, selecionados, onToggle,
}: PropsGrupo<V>) {
  const visiveis = opcoes.filter(
    (o) => selecionados.has(o.valor) || (o.contagem != null && o.contagem > 0),
  );

  return (
    <div className="sim-filtros__linha">
      <div className="sim-filtros__rotulo">{rotulo}</div>
      {visiveis.length === 0 ? (
        <div className="sim-filtros__vazio">—</div>
      ) : (
        visiveis.map((o) => (
          <button
            key={String(o.valor)}
            className={`sim-chip${selecionados.has(o.valor) ? ' is-active' : ''}`}
            onClick={() => onToggle(o.valor)}
          >
            {o.label}
            {o.contagem != null && <span className="sim-chip__contagem">{`· ${o.contagem}`}</span>}
          </button>
        ))
      )}
    </div>
  );
}

interface Props {
  opcoes: OpcoesSimulados;
  filtro: FiltroSimulados;
  contagens: ContagensSimulados;
  onToggle: <K extends keyof FiltroSimulados>(
    grupo: K,
    valor: FiltroSimulados[K] extends ReadonlySet<infer V> ? V : never,
  ) => void;
  onLimpar: () => void;
}

export function SimFiltros({ opcoes, filtro, contagens, onToggle, onLimpar }: Props) {
  return (
    <div className="sim-filtros">
      <GrupoChips
        rotulo="Vestibular"
        opcoes={opcoes.vestibulares.map((v) => ({ valor: v, label: v, contagem: contagens.vestibular.get(v) ?? 0 }))}
        selecionados={filtro.vestibulares}
        onToggle={(v) => onToggle('vestibulares', v)}
      />
      <GrupoChips
        rotulo="Fase"
        opcoes={opcoes.fases.map((f) => ({ valor: f.valor, label: f.label, contagem: contagens.fase.get(f.valor) ?? 0 }))}
        selecionados={filtro.fases}
        onToggle={(v) => onToggle('fases', v)}
      />
      <GrupoChips
        rotulo="Ciclo"
        opcoes={opcoes.ciclos.map((c) => ({ valor: c.ordem, label: c.label, contagem: contagens.ciclo.get(c.ordem) ?? 0 }))}
        selecionados={filtro.ciclos}
        onToggle={(v) => onToggle('ciclos', v)}
      />
      <GrupoChips
        rotulo="Disciplina"
        opcoes={opcoes.materias.map((m) => ({ valor: m.codigo, label: m.nome, contagem: contagens.materia.get(m.codigo) ?? 0 }))}
        selecionados={filtro.materias}
        onToggle={(v) => onToggle('materias', v)}
      />
      <div className="sim-filtros__linha">
        <div className="sim-filtros__rotulo" />
        <button className="sim-filtros__reset" disabled={!algumFiltroAtivo(filtro)} onClick={onLimpar}>
          Limpar filtros
        </button>
      </div>
    </div>
  );
}
