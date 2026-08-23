import { useState } from 'react';

import { reordenar, rotuloQuestao } from '../../dominio/banco';
import {
  useApagarLista,
  useAtualizarLista,
  useCriarLista,
  useLista,
  useListas,
  useRemoverQuestaoDaLista,
} from '../../hooks/banco';
import type { Lista } from '../../tipos/banco';
import type { PerfilBanco } from './Banco';
import { exportarPdf, exportarWord } from './exportar';

// Montar, reordenar e exportar a lista (docs/22 §P5).
//
// Vale para os dois perfis: o coordenador monta lista para dar aos alunos, o
// aluno monta a própria lista de estudo. É a mesma mecânica com dono diferente,
// e o dono sai do JWT — nenhuma rota daqui manda id de dono (servicos/banco.ts).
//
// A lista mora no servidor e não no `localStorage`: o aluno entra no celular e
// no computador, e uma lista que existe só num aparelho é uma lista que ele
// perde sem saber por quê (docs/22 §5.1).

interface Props {
  perfil: PerfilBanco;
  listaAtivaId: string | null;
  onEscolherLista: (id: string) => void;
}

export function MinhaLista({ perfil, listaAtivaId, onEscolherLista }: Props) {
  const { data: listas = [], isPending } = useListas();
  const { data: lista } = useLista(listaAtivaId);
  const criar = useCriarLista();

  const [novoTitulo, setNovoTitulo] = useState('');
  const [aviso, setAviso] = useState<string | null>(null);

  async function criarLista(evento: React.FormEvent) {
    evento.preventDefault();
    const titulo = novoTitulo.trim();
    if (!titulo) return;
    setAviso(null);
    try {
      const nova = await criar.mutateAsync(titulo);
      setNovoTitulo('');
      onEscolherLista(nova.id);
    } catch (e) {
      setAviso((e as Error).message || 'Não foi possível criar a lista.');
    }
  }

  return (
    <div className="banco-conteudo">
      <div className="banco-cabecalho">
        <h1 className="banco-cabecalho__titulo">Minha lista</h1>
        <span className="banco-cabecalho__meta">
          {perfil === 'aluno'
            ? 'As questões que você separou para estudar.'
            : 'As questões separadas para montar material.'}
        </span>
      </div>

      {listas.length > 0 && (
        <div className="banco-filtros__chips">
          {listas.map((resumo) => (
            <button
              key={resumo.id}
              type="button"
              className={`banco-chip${resumo.id === listaAtivaId ? ' banco-chip--ativo' : ''}`}
              aria-pressed={resumo.id === listaAtivaId}
              onClick={() => onEscolherLista(resumo.id)}
            >
              {resumo.titulo}
              <span className="banco-chip__contagem">{resumo.totalQuestoes}</span>
            </button>
          ))}
        </div>
      )}

      {/* banco.css tem um único estilo de campo de texto (`banco-filtros__busca`);
          reusá-lo é o que evita inventar classe nova só para este formulário. */}
      <form className="banco-filtros__grupo" onSubmit={criarLista}>
        <label className="banco-filtros__rotulo" htmlFor="banco-nova-lista">
          Nova lista
        </label>
        <input
          id="banco-nova-lista"
          className="banco-filtros__busca"
          value={novoTitulo}
          placeholder="Ondas para a P2, revisão de estequiometria…"
          onChange={(ev) => setNovoTitulo(ev.target.value)}
        />
        <div className="banco-filtros__chips">
          <button type="submit" className="banco-chip" disabled={criar.isPending}>
            Criar lista
          </button>
        </div>
      </form>

      {aviso && <p className="banco-vazio">{aviso}</p>}

      {isPending && <p className="banco-vazio">Carregando suas listas…</p>}

      {!isPending && listas.length === 0 && (
        <p className="banco-vazio">
          Nenhuma lista ainda. Crie uma acima, ou use o botão “+ Lista” no cartão de uma questão.
        </p>
      )}

      {/* `key` no id: trocar de lista reinicia o rascunho do título e a
          confirmação de apagar, em vez de arrastar o estado da lista anterior. */}
      {lista && <CorpoLista key={lista.id} lista={lista} onAviso={setAviso} />}
    </div>
  );
}

function CorpoLista({ lista, onAviso }: { lista: Lista; onAviso: (m: string | null) => void }) {
  const atualizar = useAtualizarLista();
  const apagar = useApagarLista();
  const remover = useRemoverQuestaoDaLista();

  const [titulo, setTitulo] = useState(lista.titulo);
  const [confirmandoApagar, setConfirmandoApagar] = useState(false);

  const ids = lista.questoes.map((q) => q.id);

  /**
   * Reordenar manda a ordem INTEIRA, e não "mova este item": o vaivém de
   * subir/descer viraria N requisições que podem chegar fora de ordem
   * (`AtualizarLista.questaoIds`, schemas/banco.py).
   */
  function mover(de: number, para: number) {
    const nova = reordenar(ids, de, para);
    if (nova.join() === ids.join()) return;
    atualizar.mutate({ id: lista.id, remendo: { questaoIds: nova } });
  }

  function renomear() {
    const limpo = titulo.trim();
    if (!limpo || limpo === lista.titulo) return;
    atualizar.mutate({ id: lista.id, remendo: { titulo: limpo } });
  }

  // "Word" e não "DOCX": o arquivo é .doc (HTML que o Word abre e edita), e o
  // rótulo não deve prometer OOXML. Ver o porquê em `exportar.ts`.
  function exportar(formato: 'pdf' | 'word') {
    onAviso(null);
    try {
      if (formato === 'pdf') exportarPdf(lista);
      else exportarWord(lista);
    } catch (e) {
      onAviso((e as Error).message);
    }
  }

  return (
    <>
      <div className="banco-filtros__grupo">
        <label className="banco-filtros__rotulo" htmlFor={`banco-titulo-${lista.id}`}>
          Título da lista
        </label>
        <input
          id={`banco-titulo-${lista.id}`}
          className="banco-filtros__busca"
          value={titulo}
          onChange={(ev) => setTitulo(ev.target.value)}
          onBlur={renomear}
        />
      </div>

      {/* Os botões com texto levam `banco-questao__acao` junto: `base.css` zera o
          padding de todo <button>, e a regra de `.banco-lista__acoes button` foi
          escrita para os de ícone (↑ ↓ ✕), que não precisam de padding. */}
      <div className="banco-lista__acoes">
        <button type="button" className="banco-questao__acao" onClick={() => exportar('pdf')}>
          Exportar PDF
        </button>
        <button type="button" className="banco-questao__acao" onClick={() => exportar('word')}>
          Exportar Word
        </button>
        <button
          type="button"
          className="banco-questao__acao"
          onClick={() => {
            if (!confirmandoApagar) {
              setConfirmandoApagar(true);
              return;
            }
            apagar.mutate(lista.id);
          }}
        >
          {confirmandoApagar ? 'Confirmar exclusão' : 'Apagar lista'}
        </button>
      </div>

      {lista.questoes.length === 0 ? (
        <p className="banco-vazio">
          Lista vazia. Abra a aba “Questões”, filtre o que quer e use “+ Lista” no cartão.
        </p>
      ) : (
        <ol className="banco-lista">
          {lista.questoes.map((questao, i) => (
            <li key={questao.id} className="banco-lista__item">
              <span className="banco-lista__ordem">{i + 1}</span>
              <span className="banco-lista__titulo">{rotuloQuestao(questao)}</span>
              <div className="banco-lista__acoes">
                <button
                  type="button"
                  aria-label={`Subir ${rotuloQuestao(questao)}`}
                  disabled={i === 0 || atualizar.isPending}
                  onClick={() => mover(i, i - 1)}
                >
                  ↑
                </button>
                <button
                  type="button"
                  aria-label={`Descer ${rotuloQuestao(questao)}`}
                  disabled={i === lista.questoes.length - 1 || atualizar.isPending}
                  onClick={() => mover(i, i + 1)}
                >
                  ↓
                </button>
                <button
                  type="button"
                  aria-label={`Tirar ${rotuloQuestao(questao)} da lista`}
                  disabled={remover.isPending}
                  onClick={() => remover.mutate({ listaId: lista.id, questaoId: questao.id })}
                >
                  ✕
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
