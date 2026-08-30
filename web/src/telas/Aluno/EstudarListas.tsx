import { useState } from 'react';
import { Link } from 'react-router-dom';

import { useApagarLista, useAtualizarLista, useCriarLista, useListas } from '../../dados/aluno';
import type { ListaResumo } from '../../dados/aluno';
import { Icone } from './pecas/Icone';
import { fmtDataCurta } from './pecas/formato';

// MINHAS LISTAS — as filas de treino que o aluno monta à mão.
//
// Tudo aqui é DADO REAL: as cinco rotas de `/banco/listas` estão em produção
// desde 23/08 (docs/28 §1). O que muda em relação à tela da coordenação é só a
// casca — a lista do aluno não é material de montar prova, é a fila que ele vai
// treinar, e por isso o caminho para `/treino/lista/:id` é o destaque.
//
// A rota tira o dono do JWT: nenhuma chamada daqui manda id de aluno, e é assim
// que uma lista de outro aluno nunca aparece (docs/22 §5.2).

export function EstudarListas() {
  const listas = useListas();
  const criar = useCriarLista();
  const [titulo, setTitulo] = useState('');

  const nomeLimpo = titulo.trim();

  function submeter(ev: React.FormEvent) {
    ev.preventDefault();
    if (!nomeLimpo || criar.isPending) return;
    criar.mutate(nomeLimpo, { onSuccess: () => setTitulo('') });
  }

  const todas = listas.data ?? [];

  return (
    <>
      <Link className="alu-est-voltar" to="/estudar">
        <Icone nome="voltar" tamanho={16} />
        Estudar
      </Link>

      <h1 className="alu-titulo-tela">Minhas listas</h1>

      <form className="alu-listas__nova" onSubmit={submeter}>
        <label className="alu-so-leitor" htmlFor="alu-nova-lista">
          Nome da nova lista
        </label>
        <input
          id="alu-nova-lista"
          className="alu-campo"
          value={titulo}
          maxLength={120}
          placeholder="Ex.: refazer antes do P5"
          onChange={(ev) => setTitulo(ev.target.value)}
        />
        <button
          type="submit"
          className="alu-tecla alu-tecla--pequena"
          disabled={!nomeLimpo || criar.isPending}
        >
          {criar.isPending ? 'Criando…' : 'Criar'}
        </button>
      </form>

      {criar.isError && (
        <p className="alu-erro">Não deu para criar a lista. Tente de novo em instantes.</p>
      )}

      {listas.isPending && <p className="alu-carregando">Abrindo suas listas…</p>}

      {listas.isError && (
        <div className="alu-bloco">
          <p className="alu-erro">Não deu para carregar suas listas.</p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => {
              listas.refetch();
            }}
          >
            Tentar de novo
          </button>
        </div>
      )}

      {listas.isSuccess && todas.length === 0 && (
        <div className="alu-bloco">
          <p className="alu-vazio">
            Você ainda não tem lista. Uma lista é a sua fila: separe as questões que te
            travaram e treine só elas, na ordem que você escolher.
          </p>
          <Link className="alu-tecla" to="/estudar">
            Escolher questões
          </Link>
        </div>
      )}

      {todas.length > 0 && (
        <ul className="alu-listas">
          {todas.map((lista) => (
            <ItemDaLista key={lista.id} lista={lista} />
          ))}
        </ul>
      )}
    </>
  );
}

function ItemDaLista({ lista }: { lista: ListaResumo }) {
  const atualizar = useAtualizarLista();
  const apagar = useApagarLista();
  const [renomeando, setRenomeando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [novoTitulo, setNovoTitulo] = useState(lista.titulo);

  function salvarNome(ev: React.FormEvent) {
    ev.preventDefault();
    const limpo = novoTitulo.trim();
    if (!limpo || limpo === lista.titulo) return setRenomeando(false);
    atualizar.mutate(
      { id: lista.id, remendo: { titulo: limpo } },
      { onSuccess: () => setRenomeando(false) },
    );
  }

  if (renomeando) {
    return (
      <li className="alu-listas__item">
        <form className="alu-listas__renomear" onSubmit={salvarNome}>
          <label className="alu-so-leitor" htmlFor={`alu-renomear-${lista.id}`}>
            Novo nome da lista
          </label>
          <input
            id={`alu-renomear-${lista.id}`}
            className="alu-campo"
            value={novoTitulo}
            maxLength={120}
            onChange={(ev) => setNovoTitulo(ev.target.value)}
          />
          <button type="submit" className="alu-tecla alu-tecla--pequena" disabled={atualizar.isPending}>
            Salvar
          </button>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
            onClick={() => {
              setNovoTitulo(lista.titulo);
              setRenomeando(false);
            }}
          >
            Cancelar
          </button>
        </form>
      </li>
    );
  }

  return (
    <li className="alu-listas__item">
      <Link className="alu-listas__elo" to={`/estudar/listas/${lista.id}`}>
        <span className="alu-listas__titulo">{lista.titulo}</span>
        <span className="alu-listas__meta">
          {/* Renomear e apagar falham em silêncio se ninguém disser: a lista
              volta ao nome antigo (ou continua na tela) e o aluno acha que o
              toque não pegou, e tenta de novo. */}
          {atualizar.isError || apagar.isError ? (
            <span className="alu-erro">Não deu para salvar. Tente de novo.</span>
          ) : (
            <>
              {lista.totalQuestoes === 1 ? '1 questão' : `${lista.totalQuestoes} questões`}
              {' · '}
              {fmtDataCurta(lista.atualizadaEm.slice(0, 10))}
            </>
          )}
        </span>
      </Link>

      <div className="alu-listas__acoes">
        <button
          type="button"
          className="alu-listas__acao"
          onClick={() => setRenomeando(true)}
          aria-label={`Renomear ${lista.titulo}`}
        >
          <Icone nome="anotar" tamanho={17} />
        </button>

        {/* Dois toques para apagar, e o segundo diz o nome. Uma lista montada à
            mão é trabalho do aluno, e um toque acidental num alvo de 44px ao
            lado do link seria fácil demais. */}
        {confirmando ? (
          <>
            <button
              type="button"
              className="alu-listas__acao alu-listas__acao--confirmar"
              disabled={apagar.isPending}
              onClick={() => apagar.mutate(lista.id)}
            >
              Apagar
            </button>
            <button
              type="button"
              className="alu-listas__acao"
              onClick={() => setConfirmando(false)}
            >
              Não
            </button>
          </>
        ) : (
          <button
            type="button"
            className="alu-listas__acao"
            onClick={() => setConfirmando(true)}
            aria-label={`Apagar ${lista.titulo}`}
          >
            <Icone nome="lixeira" tamanho={17} />
          </button>
        )}
      </div>
    </li>
  );
}
