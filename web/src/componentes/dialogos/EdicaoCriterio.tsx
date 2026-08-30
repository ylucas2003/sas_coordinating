import { useEffect, useMemo, useState } from 'react';

import { Campo, Dialogo } from './Dialogo';
import * as api from '../../servicos/api';
import type { CorpoCriterio, PredicadoEntrada, PreviaCriterio } from '../../servicos/api';
import { useCriarCriterio } from '../../hooks/mutacoes';
import { normalizar } from '../../util/formato';

/**
 * A régua do coordenador (docs/31 §P4).
 *
 * O pedido literal: *"nota 7 em Matemática, Física e Química e acima de 4 em
 * Português"* — sem pedir código a ninguém.
 *
 * Três decisões de desenho, e a terceira é a que faz a tela funcionar:
 *
 *  1. **O identificador é derivado do nome.** Ninguém deveria ter de inventar
 *     um slug; e um slug digitado à mão é uma chave que o usuário não sabe que
 *     está criando.
 *  2. **As opções de edital ficam escondidas.** `eliminatório`,
 *     `fora da média` e `peso` existem porque os editais precisam deles — a
 *     régua típica do coordenador não usa nenhum. Expostos de saída, fariam o
 *     formulário parecer o que ele não é.
 *  3. **A prévia recalcula contra o ciclo aberto.** É o único jeito de alguém
 *     perceber que digitou 7 onde queria 4 ANTES de a régua virar versão.
 */

const MATERIAS = [
  { codigo: 'matematica', nome: 'Matemática' },
  { codigo: 'fisica', nome: 'Física' },
  { codigo: 'quimica', nome: 'Química' },
  { codigo: 'portugues', nome: 'Português' },
  { codigo: 'ingles', nome: 'Inglês' },
  { codigo: 'redacao', nome: 'Redação' },
];

const OPERADORES = [
  { valor: '>=', rotulo: 'pelo menos' },
  { valor: '>', rotulo: 'acima de' },
  { valor: '<=', rotulo: 'no máximo' },
  { valor: '<', rotulo: 'abaixo de' },
];

/** '*' e '' não são matérias: são "qualquer disciplina" e "a média geral". */
const ALVOS = [
  { valor: '*', rotulo: 'Qualquer disciplina' },
  { valor: '', rotulo: 'Média geral' },
  ...MATERIAS.map((m) => ({ valor: m.codigo, rotulo: m.nome })),
];

interface Requisito extends PredicadoEntrada {
  /** Chave estável da linha — o índice mudaria ao remover uma do meio. */
  chave: string;
}

let proximaChave = 0;
const novoRequisito = (p: Partial<PredicadoEntrada> = {}): Requisito => ({
  chave: `r${proximaChave++}`,
  materia: 'matematica',
  operador: '>=',
  valor_nota: 4,
  eliminatorio: false,
  entra_na_media: true,
  peso: 1,
  ...p,
});

/** Nome → identificador estável: sem acento, minúsculo, hifenizado. */
export function slugDoNome(nome: string): string {
  return normalizar(nome)
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

interface Props {
  /** Ciclo contra o qual a prévia roda. Sem ele, não há prévia. */
  cicloId: string | null;
  fase?: 1 | 2;
  onFechar: () => void;
  onSalvo: (slug: string) => void;
}

export function EdicaoCriterio({ cicloId, fase, onFechar, onSalvo }: Props) {
  const [nome, setNome] = useState('');
  const [descricao, setDescricao] = useState('');
  const [combinador, setCombinador] = useState<'todos' | 'algum'>('algum');
  const [avancado, setAvancado] = useState(false);
  const [requisitos, setRequisitos] = useState<Requisito[]>([
    novoRequisito({ materia: 'matematica', valor_nota: 7 }),
    novoRequisito({ materia: 'fisica', valor_nota: 7 }),
    novoRequisito({ materia: 'quimica', valor_nota: 7 }),
  ]);
  const [erro, setErro] = useState('');

  const criar = useCriarCriterio();
  const slug = slugDoNome(nome);

  const corpo: CorpoCriterio = useMemo(() => ({
    slug,
    nome: nome.trim(),
    descricao: descricao.trim() || null,
    combinador,
    fase: fase ?? null,
    desempate: ['media'],
    predicados: requisitos.map(({ chave: _chave, ...p }) => ({
      ...p,
      // '' no seletor quer dizer "a média geral", que no backend é `null`.
      materia: p.materia === '' ? null : p.materia,
    })),
  }), [slug, nome, descricao, combinador, fase, requisitos]);

  const previa = usePrevia(corpo, cicloId, fase, nome.trim().length > 0);

  function alterar(chave: string, campo: keyof PredicadoEntrada, valor: unknown) {
    setRequisitos((rs) => rs.map((r) => (r.chave === chave ? { ...r, [campo]: valor } : r)));
  }

  async function salvar() {
    setErro('');
    try {
      const salvo = await criar.mutateAsync(corpo);
      onSalvo(salvo.slug);
    } catch (e) {
      setErro((e as Error).message || String(e));
    }
  }

  const podeSalvar = nome.trim().length > 0 && requisitos.length > 0 && !criar.isPending;

  return (
    <Dialogo
      titulo="Nova régua de corte"
      subtitulo="Uma régua é uma lista de requisitos. O SAS aplica e diz quem passa."
      onFechar={onFechar}
      rodape={
        <>
          <button className="btn btn--ghost" onClick={onFechar}>Cancelar</button>
          <button className="btn btn--primary" disabled={!podeSalvar} onClick={salvar}>
            {criar.isPending ? 'Salvando…' : 'Criar régua'}
          </button>
        </>
      }
    >
      <Campo label="Nome">
        <input
          className="dialog__input"
          value={nome}
          placeholder="Meta 7 nas exatas"
          onChange={(e) => setNome(e.target.value)}
        />
        {slug && <span className="criterio__slug">{`identificador: ${slug}`}</span>}
      </Campo>

      <Campo label="Descrição (opcional)">
        <input
          className="dialog__input"
          value={descricao}
          placeholder="Para acompanhar quem está no ritmo do ITA."
          onChange={(e) => setDescricao(e.target.value)}
        />
      </Campo>

      <Campo label="Quando cortar">
        <div className="criterio__combinador">
          {([
            ['algum', 'Se falhar em QUALQUER requisito', 'É o que os dois editais mandam.'],
            ['todos', 'Só se falhar em TODOS', 'É a régua do colégio — mais tolerante.'],
          ] as const).map(([valor, rotulo, ajuda]) => (
            <label key={valor} className="criterio__opcao">
              <input
                type="radio"
                name="combinador"
                checked={combinador === valor}
                onChange={() => setCombinador(valor)}
              />
              <span>
                <b>{rotulo}</b>
                <em>{ajuda}</em>
              </span>
            </label>
          ))}
        </div>
      </Campo>

      <Campo label="Requisitos">
        <div className="criterio__requisitos">
          {requisitos.map((r) => (
            <div key={r.chave} className="criterio__requisito">
              <select
                className="dialog__input"
                aria-label="Disciplina"
                value={r.materia ?? ''}
                onChange={(e) => alterar(r.chave, 'materia', e.target.value)}
              >
                {ALVOS.map((a) => (
                  <option key={a.valor} value={a.valor}>{a.rotulo}</option>
                ))}
              </select>

              <select
                className="dialog__input"
                aria-label="Comparação"
                value={r.operador}
                onChange={(e) => alterar(r.chave, 'operador', e.target.value)}
              >
                {OPERADORES.map((o) => (
                  <option key={o.valor} value={o.valor}>{o.rotulo}</option>
                ))}
              </select>

              <input
                className="dialog__input criterio__nota"
                type="number"
                min={0}
                max={10}
                step={0.5}
                aria-label="Nota mínima"
                value={r.valor_nota ?? ''}
                onChange={(e) => alterar(r.chave, 'valor_nota', Number(e.target.value))}
              />

              <button
                className="criterio__remover"
                aria-label="Remover requisito"
                onClick={() => setRequisitos((rs) => rs.filter((x) => x.chave !== r.chave))}
              >
                ×
              </button>

              {avancado && (
                <div className="criterio__avancado">
                  <label>
                    <input
                      type="checkbox"
                      checked={!!r.eliminatorio}
                      onChange={(e) => alterar(r.chave, 'eliminatorio', e.target.checked)}
                    />
                    Reprova sozinho
                  </label>
                  <label>
                    <input
                      type="checkbox"
                      checked={r.entra_na_media !== false}
                      onChange={(e) => alterar(r.chave, 'entra_na_media', e.target.checked)}
                    />
                    Entra na média
                  </label>
                  <label>
                    Peso
                    <input
                      className="criterio__peso"
                      type="number"
                      min={0.5}
                      step={0.5}
                      value={r.peso ?? 1}
                      onChange={(e) => alterar(r.chave, 'peso', Number(e.target.value))}
                    />
                  </label>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="criterio__acoes">
          <button className="btn btn--ghost criterio__btn-pequeno" onClick={() => setRequisitos((rs) => [...rs, novoRequisito()])}>
            + Requisito
          </button>
          <button className="btn btn--ghost criterio__btn-pequeno" onClick={() => setAvancado((v) => !v)}>
            {avancado ? 'Esconder' : 'Mostrar'} opções de edital
          </button>
        </div>
      </Campo>

      <Previa previa={previa} temCiclo={!!cicloId} />

      {erro && <div className="criterio__previa criterio__previa--erro">{erro}</div>}
    </Dialogo>
  );
}

/**
 * A prévia, com atraso.
 *
 * O recálculo classifica ~1500 alunos sem paginação (armadilha 2 do CLAUDE.md).
 * Disparar a cada tecla seria uma varredura da base por caractere digitado —
 * por isso os 600ms e o cancelamento do pedido anterior.
 */
function usePrevia(
  corpo: CorpoCriterio,
  cicloId: string | null,
  fase: 1 | 2 | undefined,
  pronto: boolean,
) {
  const [previa, setPrevia] = useState<PreviaCriterio | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState('');

  // `corpo` já é memoizado por quem chama, então pode entrar na dependência
  // direto — o efeito só refaz quando a régua muda de verdade.
  useEffect(() => {
    if (!cicloId || !pronto) return;
    let cancelado = false;
    setCarregando(true);
    const id = window.setTimeout(async () => {
      try {
        const r = await api.previaCriterio(corpo, cicloId, fase);
        if (!cancelado) { setPrevia(r); setErro(''); }
      } catch (e) {
        if (!cancelado) { setPrevia(null); setErro((e as Error).message); }
      } finally {
        if (!cancelado) setCarregando(false);
      }
    }, 600);
    return () => { cancelado = true; window.clearTimeout(id); setCarregando(false); };
  }, [corpo, cicloId, fase, pronto]);

  return { previa, carregando, erro };
}

function Previa({
  previa: { previa, carregando, erro }, temCiclo,
}: {
  previa: ReturnType<typeof usePrevia>;
  temCiclo: boolean;
}) {
  if (!temCiclo) {
    return (
      <div className="criterio__previa criterio__previa--vazia">
        Escolha um ciclo no Painel para ver quantos alunos esta régua cortaria.
      </div>
    );
  }
  if (erro) return <div className="criterio__previa criterio__previa--erro">{erro}</div>;
  if (!previa) {
    return (
      <div className="criterio__previa criterio__previa--vazia">
        {carregando ? 'Calculando…' : 'Dê um nome à régua para ver a prévia.'}
      </div>
    );
  }

  const pct = previa.total ? Math.round((previa.cortados / previa.total) * 100) : 0;
  return (
    <div className={`criterio__previa${carregando ? ' is-recalculando' : ''}`}>
      <div className="criterio__previa-numero">
        <b>{previa.cortados}</b>
        {` de ${previa.total} alunos deste ciclo seriam cortados (${pct}%).`}
      </div>
      {previa.exemplos.length > 0 && (
        <ul className="criterio__previa-lista">
          {previa.exemplos.map((e) => (
            <li key={e.nome}>
              <b>{e.nome}</b>
              {e.motivo ? ` — ${e.motivo}` : ''}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
