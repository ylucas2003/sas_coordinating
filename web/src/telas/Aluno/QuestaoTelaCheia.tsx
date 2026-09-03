import { useEffect, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import {
  useAdicionarQuestaoNaLista,
  useAtualizarEstudo,
  useCriarLista,
  useListas,
  useQuestaoDoBanco,
  useQuestoesDoBanco,
} from '../../dados/aluno';
import type { QuestaoVestibular } from '../../dados/aluno';
import { CartaoQuestaoAluno } from './pecas/CartaoQuestaoAluno';
import { Folha } from './pecas/Folha';
import { Icone } from './pecas/Icone';
import { fmtInteiro } from './pecas/formato';

// Uma questão em tela cheia.
//
// Rota de topo (`/questao/:id`), fora do casco: é para onde tocar num cartão
// leva, e o id é legível e estável (`ita_2019_fase1_q01`), então o link
// sobrevive a link salvo e a mensagem colada.
//
// A BARRA FIXA DA BASE é a razão da tela existir do jeito que existe: é assim
// que se anda entre questões sem voltar à lista a cada uma. Sem ela, ler cinco
// questões seguidas custa cinco idas e voltas.
//
// ⚠️ DE ONDE VEM A VIZINHANÇA, e este é o ponto honesto do arquivo. O brief
// pede "12 DE 248" — a posição dentro do RECORTE DE FILTRO da lista de onde o
// aluno veio. Esta rota não recebe esse recorte: ela recebe um id e nada mais.
// Em vez de inventar um total ou de mostrar botões que não fazem nada, a
// vizinhança é derivada da PROVA: mesma matéria, mesmo vestibular, mesmo ano e
// mesma fase. É um recorte real, explicável em uma linha ("nº 12 de 20 · ITA
// 2019 · Fase 1"), e cabe numa página só — nenhum grupo desses passa de 20
// questões no acervo. Se a questão não aparecer na página, a navegação SOME em
// vez de mentir.

/** O teto que `GET /banco/questoes` aceita (`POR_PAGINA_MAXIMO`, 422 acima
 *  disso). Pedimos o teto para a prova inteira caber numa página só e a barra
 *  da base nunca precisar paginar por dentro. */
const QUESTOES_POR_PROVA = 100;

function ehQuatrocentosEQuatro(erro: unknown): boolean {
  return (erro as { status?: number } | null)?.status === 404;
}

export function QuestaoTelaCheia() {
  const navigate = useNavigate();
  const { id } = useParams();

  const questao = useQuestaoDoBanco(id ?? null);
  const q = questao.data;

  // A prova inteira, para saber quem vem antes e quem vem depois.
  const prova = useQuestoesDoBanco(
    {
      materia: q?.materia,
      vestibular: q?.vestibular,
      // Um ano só, mas o campo é lista desde que o filtro virou múltipla
      // escolha: aqui o recorte é "a prova desta questão", não uma escolha.
      anos: q ? [q.ano] : undefined,
      fase: q?.fase,
      porPagina: QUESTOES_POR_PROVA,
    },
    { habilitada: !!q },
  );

  const irmas = prova.data?.questoes ?? [];
  const posicao = q ? irmas.findIndex((outra) => outra.id === q.id) : -1;
  const anterior = posicao > 0 ? irmas[posicao - 1] : null;
  const proxima = posicao >= 0 && posicao < irmas.length - 1 ? irmas[posicao + 1] : null;

  const estudo = useAtualizarEstudo();
  const [listaAberta, setListaAberta] = useState(false);

  // Mesmo motivo da sessão de treino: o enunciado é um PNG e esperar o download
  // a cada "Próxima" é o que faz a leitura parecer lenta (docs/28 §6).
  useEffect(() => {
    if (!proxima?.imagemUrl || !proxima.usaImagemNoRender) return;
    const img = new Image();
    img.src = proxima.imagemUrl;
  }, [proxima]);

  if (questao.isPending) {
    return (
      <Moldura titulo="" onVoltar={() => navigate(-1)}>
        <div className="alu-treino__esqueleto" aria-hidden="true">
          <span className="alu-treino__esqueleto-imagem" />
          <span className="alu-treino__esqueleto-linha" />
          <span className="alu-treino__esqueleto-linha" />
        </div>
      </Moldura>
    );
  }

  if (questao.isError || !q) {
    const naoExiste = ehQuatrocentosEQuatro(questao.error);
    return (
      <Moldura titulo="" onVoltar={() => navigate(-1)}>
        <h1 className="alu-titulo-tela">
          {naoExiste ? 'Esta questão não existe' : 'Não consegui abrir a questão'}
        </h1>
        <p className="alu-vazio">
          {naoExiste
            ? `Nenhuma questão do acervo tem o código “${id}”. O link pode ter sido digitado errado ou apontar para uma prova que ainda não foi importada.`
            : 'Pode ser a conexão. Tente de novo em alguns segundos.'}
        </p>
        <div className="alu-questao-cheia__acoes-erro">
          {!naoExiste && (
            <button type="button" className="alu-tecla" onClick={() => questao.refetch()}>
              Tentar de novo
            </button>
          )}
          <Link className="alu-tecla alu-tecla--fantasma" to="/estudar">
            Voltar para Estudar
          </Link>
        </div>
      </Moldura>
    );
  }

  const resolvida = q.resolvida === true;

  return (
    <div className="alu-shell alu-questao-cheia">
      <header className="alu-questao-cheia__topo">
        <button
          type="button"
          className="alu-treino__icone"
          onClick={() => (window.history.length > 1 ? navigate(-1) : navigate('/estudar'))}
          aria-label="Voltar"
        >
          <Icone nome="voltar" tamanho={22} />
        </button>

        <span className="alu-olho alu-questao-cheia__posicao">
          {posicao >= 0
            ? `${posicao + 1} de ${irmas.length} · ${q.vestibular} ${q.ano} · fase ${q.fase}`
            : `${q.vestibular} ${q.ano} · fase ${q.fase} · nº ${q.numero}`}
        </span>

        <button
          type="button"
          className="alu-treino__icone"
          onClick={() => setListaAberta(true)}
          aria-label="Adicionar a uma lista"
        >
          <Icone nome="mais" tamanho={22} />
        </button>
      </header>

      <div className="alu-questao-cheia__corpo">
        {/* O cartão já sabe tudo: imagem, tópicos com aviso de classificação
            incerta, gabarito escondido, anotação e a ORIGEM da resolução. Aqui
            ele só perde o link para si mesmo. */}
        {/* ⚠️ `key` obrigatório. Andar de "Próxima" não desmonta a rota, e sem
            ele o cartão manteria o gabarito revelado da questão anterior — e,
            pior, o rascunho de anotação dela, que o `blur` gravaria na
            questão errada. */}
        <CartaoQuestaoAluno key={q.id} questao={q} semLinkParaFicha />
      </div>

      {/* A barra da leitura. Fixa na base e com a safe area respeitada: no
          iPhone sem ela os botões ficam sob o indicador de gesto. */}
      <nav className="alu-questao-cheia__base" aria-label="Navegar entre as questões da prova">
        {posicao >= 0 ? (
          <>
            <Vizinha questao={anterior} sentido="anterior" />

            <button
              type="button"
              className={`alu-questao-cheia__marca${resolvida ? ' is-ativa' : ''}`}
              aria-pressed={resolvida}
              disabled={estudo.isPending}
              onClick={() =>
                estudo.mutate({ questaoId: q.id, remendo: { resolvida: !resolvida } })
              }
            >
              <Icone nome="cheque" tamanho={18} />
              {resolvida ? 'Resolvida' : 'Marcar'}
            </button>

            <Vizinha questao={proxima} sentido="proxima" />
          </>
        ) : (
          // Sem saber a vizinhança, botões de anterior e próxima seriam duas
          // afordâncias mortas. Some com elas e deixa só a marca de resolvida.
          <button
            type="button"
            className={`alu-questao-cheia__marca${resolvida ? ' is-ativa' : ''}`}
            aria-pressed={resolvida}
            disabled={estudo.isPending}
            onClick={() => estudo.mutate({ questaoId: q.id, remendo: { resolvida: !resolvida } })}
          >
            <Icone nome="cheque" tamanho={18} />
            {resolvida ? 'Resolvida' : 'Marcar como resolvida'}
          </button>
        )}
      </nav>

      {listaAberta && <FolhaDeListas questao={q} onFechar={() => setListaAberta(false)} />}
    </div>
  );
}

// ─── Peças ───────────────────────────────────────────────────────────────

function Moldura({
  titulo,
  onVoltar,
  children,
}: {
  titulo: string;
  onVoltar: () => void;
  children: ReactNode;
}) {
  return (
    <div className="alu-shell alu-questao-cheia">
      <header className="alu-questao-cheia__topo">
        <button type="button" className="alu-treino__icone" onClick={onVoltar} aria-label="Voltar">
          <Icone nome="voltar" tamanho={22} />
        </button>
        <span className="alu-olho alu-questao-cheia__posicao">{titulo}</span>
        <span className="alu-treino__icone" aria-hidden="true" />
      </header>
      <div className="alu-questao-cheia__corpo">{children}</div>
    </div>
  );
}

/** Uma ponta da barra. Sem vizinha, o lugar continua ocupado — se sumisse, a
 *  marca de resolvida saltaria de lado ao chegar na primeira questão. */
function Vizinha({
  questao,
  sentido,
}: {
  questao: QuestaoVestibular | null;
  sentido: 'anterior' | 'proxima';
}) {
  const rotulo = sentido === 'anterior' ? 'Anterior' : 'Próxima';
  const icone = sentido === 'anterior' ? 'voltar' : 'avancar';

  if (!questao) {
    return (
      <span className="alu-questao-cheia__vizinha is-fim" aria-hidden="true">
        <Icone nome={icone} tamanho={17} />
        {rotulo}
      </span>
    );
  }

  return (
    <Link className="alu-questao-cheia__vizinha" to={`/questao/${questao.id}`}>
      {sentido === 'anterior' && <Icone nome={icone} tamanho={17} />}
      {rotulo}
      {sentido === 'proxima' && <Icone nome={icone} tamanho={17} />}
      <span className="alu-so-leitor">questão {questao.numero}</span>
    </Link>
  );
}

/**
 * A folha de "adicionar à lista".
 *
 * A lista do aluno é a fila de treino que ele monta à mão (docs/28 §4), e por
 * isso ela precisa nascer aqui: obrigá-lo a ir até /estudar/listas criar a
 * lista antes de guardar a questão é perder a questão.
 */
function FolhaDeListas({
  questao,
  onFechar,
}: {
  questao: QuestaoVestibular;
  onFechar: () => void;
}) {
  const listas = useListas();
  const adicionar = useAdicionarQuestaoNaLista();
  const criar = useCriarLista();
  const [titulo, setTitulo] = useState('');
  const [erro, setErro] = useState('');

  async function guardar(listaId: string) {
    setErro('');
    try {
      await adicionar.mutateAsync({ listaId, questaoId: questao.id });
      onFechar();
    } catch (e) {
      setErro((e as Error).message || 'Não consegui guardar a questão nesta lista.');
    }
  }

  async function criarEGuardar(ev: FormEvent) {
    ev.preventDefault();
    const nome = titulo.trim();
    if (!nome) return setErro('Dê um nome à lista.');
    setErro('');
    try {
      const nova = await criar.mutateAsync(nome);
      await adicionar.mutateAsync({ listaId: nova.id, questaoId: questao.id });
      onFechar();
    } catch (e) {
      setErro((e as Error).message || 'Não consegui criar a lista.');
    }
  }

  const ocupado = adicionar.isPending || criar.isPending;

  return (
    <Folha aberta titulo="Guardar numa lista" altura="meio" onFechar={onFechar}>
      {listas.isPending && <p className="alu-carregando">Buscando suas listas…</p>}

      {listas.isError && (
        <p className="alu-erro">Não consegui ler suas listas. Tente fechar e abrir de novo.</p>
      )}

      {listas.data?.length === 0 && (
        <p className="alu-vazio">
          Você ainda não tem lista nenhuma. Crie a primeira aqui embaixo — ela vira uma fila de
          treino que você mesmo monta.
        </p>
      )}

      {listas.data?.map((lista) => (
        <button
          key={lista.id}
          type="button"
          className="alu-conta__linha"
          disabled={ocupado}
          onClick={() => guardar(lista.id)}
        >
          <Icone nome="lista" tamanho={18} />
          {lista.titulo}
          <span className="alu-questao-cheia__contagem-lista">
            {fmtInteiro(lista.totalQuestoes)}
          </span>
        </button>
      ))}

      <form className="alu-questao-cheia__nova-lista" onSubmit={criarEGuardar}>
        <label className="alu-conta__campo">
          <span className="alu-conta__rotulo">Nova lista</span>
          <input
            className="alu-campo"
            value={titulo}
            placeholder="Ex.: refazer antes do P5"
            onChange={(ev) => setTitulo(ev.target.value)}
          />
        </label>
        <button type="submit" className="alu-tecla alu-tecla--larga" disabled={ocupado}>
          Criar e guardar
        </button>
      </form>

      {erro && <p className="alu-erro">{erro}</p>}
    </Folha>
  );
}
