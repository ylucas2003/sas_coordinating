import { useCallback, useId, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { resumirFiltros } from '../../../dominio/filtros';
import { gravarEscolha, lerEscolha } from './memoria';

/**
 * Filtros em faixa horizontal, acima da tabela.
 *
 * Substituiu a sidebar colapsável (`PainelFiltros`): com o rail de ícones
 * ocupando a esquerda, uma segunda coluna de filtros comia largura justamente
 * das tabelas largas — que são a razão de o SAS existir.
 *
 * A aposta original era "todos os grupos abertos, sempre": o custo de esconder
 * um filtro é o usuário não saber que ele existe, e eles cabiam numa linha. A
 * regra continua; **mudou o limiar**. No Painel, Sede e Turmas são pílulas por
 * VALOR, não por categoria — com ~900 alunos são dezenas de pílulas antes de a
 * tabela começar —, e no celular praticamente toda faixa estoura.
 *
 * Então: **aberta por padrão, colapsando quando passa de uma linha**, com o
 * resumo do que está ativo no lugar.
 *
 * ⚠️ O que NÃO fazer: colapsar tudo por padrão. Isso é voltar ao
 * `PainelFiltros` lateral que o redesenho do casco tirou, e reintroduz
 * exatamente o problema que a aposta original descreve (docs/33 §2).
 *
 * ⚠️ E a regra que paga o colapso: **filtro em vigor nunca fica invisível.**
 * O resumo é obrigatório para isso — sem ele, a faixa fechada esconderia um
 * recorte que o usuário não sabe desmarcar, e a tabela abaixo mentiria em
 * silêncio.
 */

export interface GrupoFiltro {
  chave: string;
  rotulo: string;
  corpo: ReactNode;
  /**
   * O que este grupo tem de ativo, em uma expressão curta (`2 turmas`).
   * `null`/ausente = nada ativo. Quem monta o resumo é a TELA, porque só ela
   * sabe que `turmaIds.size === 2` se escreve "2 turmas" — os helpers de
   * `dominio/filtros.ts` fazem o trabalho.
   */
  resumo?: string | null;
}

interface Props {
  /**
   * Identidade da SUPERFÍCIE de filtro, para lembrar a escolha. Não é a rota:
   * `/provas` tem duas faixas (`provas.ciclos` e `provas.simulados`), e uma
   * chave só faria as duas dividirem um estado.
   */
  tela: string;
  grupos: Array<GrupoFiltro | null | false>;
  /** Omitido = sem botão de limpar. */
  onLimpar?: () => void;
  algumAtivo?: boolean;
}

export function BarraFiltros({ tela, grupos, onLimpar, algumAtivo = false }: Props) {
  const visiveis = grupos.filter((g): g is GrupoFiltro => Boolean(g));

  const refGrupos = useRef<HTMLDivElement>(null);
  const [transbordou, setTransbordou] = useState(false);
  // `null` = a pessoa nunca escolheu nesta superfície; aí quem decide é o
  // tamanho. Uma escolha explícita vence a medição, sempre.
  const [escolha, setEscolha] = useState<boolean | null>(() => lerEscolha(tela));
  const idGrupos = useId();

  const aberta = escolha ?? !transbordou;

  /**
   * ⚠️ A armadilha deste componente, e o motivo de a medição ser assim.
   *
   * Medir a ALTURA e comparar com um limite oscila: aberta transborda →
   * colapsa → colapsada cabe → expande → transborda. Laço infinito que o React
   * não acusa e que aparece como a faixa piscando.
   *
   * Duas defesas, e as duas são necessárias:
   *
   * 1. O teste é de QUEBRA DE LINHA, não de altura: com `flex-wrap`, um grupo
   *    que desceu tem `offsetTop` maior que o primeiro. Sem número mágico e
   *    sem depender de padding.
   * 2. Só se mede com a faixa ABERTA. Fechada, o valor fica congelado — o que
   *    também significa que alargar a janela com a faixa fechada não a reabre
   *    sozinha. É de propósito: o resumo continua visível, e reabrir sozinho
   *    seria a metade do laço que sobrou.
   */
  const medir = useCallback(() => {
    const alvo = refGrupos.current;
    if (!alvo) return;
    const filhos = Array.from(alvo.children) as HTMLElement[];
    if (filhos.length < 2) {
      setTransbordou(false);
      return;
    }
    const topo = filhos[0].offsetTop;
    setTransbordou(filhos.some((f) => f.offsetTop > topo));
  }, []);

  useLayoutEffect(() => {
    if (!aberta) return;
    medir();
    // O observador pega os dois casos que importam: a janela mudando de
    // largura, e as pílulas chegando depois (a lista de turmas vem de uma
    // consulta, e a faixa nasce curta).
    const alvo = refGrupos.current;
    if (!alvo || typeof ResizeObserver === 'undefined') return;
    const observador = new ResizeObserver(medir);
    observador.observe(alvo);
    return () => observador.disconnect();
  }, [aberta, medir]);

  if (!visiveis.length) return null;

  const resumo = resumirFiltros(visiveis);

  function alternar() {
    const novo = !aberta;
    setEscolha(novo);
    gravarEscolha(tela, novo);
  }

  return (
    <div className={`barra-filtros${aberta ? '' : ' is-colapsada'}`}>
      {/* O botão só aparece quando há o que colapsar: nas telas em que a faixa
          cabe numa linha, ela continua exatamente como era. */}
      {transbordou && (
        <button
          type="button"
          className="barra-filtros__alternar"
          aria-expanded={aberta}
          aria-controls={idGrupos}
          onClick={alternar}
        >
          <span aria-hidden="true">{aberta ? '▴' : '▾'}</span>
          Filtros
        </button>
      )}

      <div
        id={idGrupos}
        className="barra-filtros__grupos"
        ref={refGrupos}
        // `hidden` em vez de desmontar: `aria-controls` precisa que o alvo
        // exista, e a medição precisa do nó de volta ao expandir.
        hidden={!aberta}
      >
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
      </div>

      {!aberta && (
        <span className="barra-filtros__resumo">
          {resumo || 'Nenhum filtro ativo'}
        </span>
      )}

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
 * Busca de conteúdo da tela — filtra as linhas que estão na frente da pessoa.
 *
 * ⚠️ Não confundir com a busca da topbar, que é outra coisa e já existe: lá é
 * navegação (digita um nome de qualquer tela, atalho `/`, e vai para a ficha
 * do aluno). Aqui é recorte. As duas convivem porque respondem a perguntas
 * diferentes — "onde está o Fulano?" e "quais destes são o Fulano?".
 *
 * Antes disto a busca de tela existia em três lugares diferentes — controles
 * do cabeçalho no Painel, grupo da faixa na Administração, topo da sidebar no
 * Banco — e faltava em cinco telas. Três posições e cinco ausências para a
 * mesma ideia (docs/33 §0.3).
 */
export function Busca({
  valor,
  onChange,
  placeholder,
  rotulo,
}: {
  valor: string;
  onChange: (v: string) => void;
  /** Diga O QUE esta tela procura. "Buscar…" não ajuda ninguém. */
  placeholder: string;
  /** Rótulo acessível, quando o `placeholder` não basta como nome. */
  rotulo?: string;
}) {
  return (
    <div className="barra-filtros__busca">
      <svg
        width="15" height="15" viewBox="0 0 20 20" fill="none" stroke="currentColor"
        strokeWidth="1.8" aria-hidden="true"
      >
        <circle cx="9" cy="9" r="6" />
        <path d="M13.5 13.5L17.5 17.5" />
      </svg>
      <input
        // `type="search"` dá o botão de limpar do próprio navegador — de graça,
        // e é o que a pessoa espera de um campo de busca.
        type="search"
        className="pill-campo barra-filtros__busca-campo"
        placeholder={placeholder}
        aria-label={rotulo ?? placeholder}
        value={valor}
        onChange={(ev) => onChange(ev.target.value)}
      />
    </div>
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
