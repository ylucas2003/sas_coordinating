import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useEstudo, useLista, useListas, useQuestoesDoBanco } from '../../dados/aluno';
import type { ColecaoBanco, FiltrosBanco, QuestaoVestibular } from '../../dados/aluno';
import { exportarPdf, exportarWord } from '../Banco/exportar';
import { CabecaDoCampo } from './pecas/CabecaDoCampo';
import { CartaoQuestaoAluno } from './pecas/CartaoQuestaoAluno';
import {
  FolhaDaPaginaInteira,
  usePaginaInteiraExplicada,
} from './pecas/FolhaDaPaginaInteira';
import {
  FiltrosDeMateriaEAssunto,
  FolhaFiltros,
  PainelDeFiltros,
  SeletorDeColecao,
} from './pecas/FolhaFiltros';
import type { RotulosDeFiltro } from './pecas/FolhaFiltros';
import { Icone } from './pecas/Icone';
import { MATERIAS_COM_TAXONOMIA, fmtInteiro } from './pecas/formato';

// O BANCO — o acervo, com busca sempre visível.
//
// Era a segunda metade da antiga `Estudar.tsx`, e virou tela própria quando a
// aba passou a ter três campos. A lógica de recorte veio inteira de lá, com os
// comentários: ela é sutil e cada linha tem um motivo.
//
// ⚠️ O RECORTE VIVE NA URL, e não em `useState`.
//
// `/questao/:id` é rota de TOPO (App.tsx): abrir uma questão DESMONTA esta tela,
// e um filtro guardado em estado local não sobreviveria ao voltar — que é
// justamente o caminho mais usado do produto. Na URL ele volta, e de quebra o
// recorte vira link.
//
// ⚠️ AS DUAS COLEÇÕES não são um filtro a mais: são duas experiências de
// leitura diferentes do mesmo acervo (migrations 0031/0033). Em "Recentes" o
// cartão mostra o recorte da questão; em "Arquivo" mostra a PÁGINA INTEIRA do
// caderno, com as questões vizinhas junto — e é por isso que o cartão de lá tem
// tarja dizendo qual número procurar, e esta tela tem uma folha explicando por
// quê. Sem isso o aluno acha que abriu a questão errada.
//
// ⚠️ ONDE CADA FILTRO MORA mudou em 04/09 (docs/35 §5): matéria e assunto
// subiram para o CENTRO, no lugar dos cartões de coleção, e a coleção desceu
// para a coluna lateral. Matéria é o que destrava o assunto, e na coluna — que
// rola por dentro — ela saía da tela deixando à vista o aviso "escolha uma
// matéria primeiro", que apontava para um controle que já não estava lá.
// No celular não existe coluna (docs/28 §4): lá a coleção fica no fluxo, logo
// abaixo dos dois primários, e a folha do rodapé guarda só o resto.

/** A página da listagem. O mesmo padrão da rota (`POR_PAGINA_PADRAO` = 20). */
const POR_PAGINA = 20;

/** Os cinco recortes removíveis. A busca fica fora: ela mora no campo, sempre
 *  visível, e não vira pílula. A coleção também fica fora — ela é um controle
 *  segmentado próprio, sempre visível, e nunca "nenhuma". */
const CHAVES_DE_FILTRO = ['materia', 'vestibular', 'anos', 'fase', 'topico'] as const;
type ChaveDeFiltro = (typeof CHAVES_DE_FILTRO)[number];

/** Os que a FOLHA do celular guarda. Matéria e assunto não estão lá: ficam no
 *  centro, à vista (docs/35 §5). */
const CHAVES_DA_FOLHA: readonly ChaveDeFiltro[] = ['vestibular', 'anos', 'fase'];

/** Quantas colunas o desktop mostra. No celular é sempre uma. */
type Colunas = 1 | 2;

/**
 * Adia um valor. A busca é textual sobre o enunciado de milhares de questões:
 * bater a cada tecla enfileiraria uma consulta por caractere, e a resposta que
 * chega primeiro nem sempre é a do texto mais recente.
 */
function useAdiado<T>(valor: T, ms = 350): T {
  const [adiado, setAdiado] = useState(valor);
  useEffect(() => {
    const t = window.setTimeout(() => setAdiado(valor), ms);
    return () => window.clearTimeout(t);
  }, [valor, ms]);
  return adiado;
}

function rotuloDoFiltro(
  chave: ChaveDeFiltro,
  filtros: FiltrosBanco,
  rotulos: RotulosDeFiltro,
): string {
  // Uma pílula por RECORTE, não por ano: com sete anos escolhidos, sete
  // pílulas empurrariam todo o resto da tela para baixo da dobra.
  if (chave === 'anos') {
    const n = filtros.anos?.length ?? 0;
    return n === 1 ? String(filtros.anos?.[0]) : `${n} anos`;
  }
  if (chave === 'fase') return `Fase ${filtros.fase}`;
  // O código do tópico não se lê sozinho ("7.2"): quem sabe o nome é a
  // taxonomia, e a folha o entrega junto ao aplicar.
  if (chave === 'topico') return rotulos.topico ?? `Assunto ${filtros.topico}`;
  return String(filtros[chave]);
}

/** O acervo só tem estes dois. `VestibularBanco` é fechado, e o `as const` é o
 *  que faz o `find` devolver o tipo em vez de `string`. */
const VESTIBULARES = ['ITA', 'IME'] as const;

/**
 * O recorte, lido da URL — e validado inteiro.
 *
 * Um link colado à mão é entrada tão válida quanto um toque na folha, e
 * `?topico=7.2` sem matéria é 400 na rota (docs/28 §6). Aqui ele simplesmente
 * não vira filtro, em vez de virar uma tela de erro.
 */
function lerFiltros(params: URLSearchParams): FiltrosBanco {
  const filtros: FiltrosBanco = {};

  // A mesma lista que o Treino e o Tio Léo usam para validar matéria — uma
  // segunda cópia aqui divergiria no dia em que uma quarta matéria ganhasse
  // taxonomia, e a divergência só apareceria em runtime.
  const materia = MATERIAS_COM_TAXONOMIA.find((m) => m === params.get('materia'));
  if (materia) filtros.materia = materia;

  const vestibular = VESTIBULARES.find((v) => v === params.get('vestibular'));
  if (vestibular) filtros.vestibular = vestibular;

  // `?anos=2024,2023`. Vírgula na URL do APP (é o aluno que lê e compartilha);
  // a repetição que o FastAPI espera é problema do `qs()`, na camada de HTTP.
  //
  // ⚠️ Ausente = TODOS, nunca "nenhum". Lista só com lixo também vira todos —
  // um recorte vazio devolveria tela em branco por causa de um link torto.
  const anos = (params.get('anos') ?? '')
    .split(',')
    .map((n) => Number(n.trim()))
    .filter((n) => Number.isInteger(n) && n > 1900);
  if (anos.length > 0) filtros.anos = [...new Set(anos)].sort((a, b) => b - a);

  const fase = Number(params.get('fase'));
  if (fase === 1 || fase === 2) filtros.fase = fase;

  const topico = params.get('topico');
  if (topico && filtros.materia) filtros.topico = topico;

  return filtros;
}

/** A coleção da URL, com 'recentes' como piso — o parâmetro é sempre um dos
 *  dois, nunca ausente, porque a tela sempre mostra uma das duas metades. */
function lerColecao(params: URLSearchParams): ColecaoBanco {
  return params.get('colecao') === 'arquivo' ? 'arquivo' : 'recentes';
}

/** Uma ou duas colunas no desktop. Duas é o padrão do desenho: serve para
 *  varrer a lista. Uma dá largura à página inteira do caderno, no Arquivo. */
function lerColunas(params: URLSearchParams): Colunas {
  return params.get('colunas') === '1' ? 1 : 2;
}

export function EstudarBanco() {
  const [params, setParams] = useSearchParams();

  const filtros = useMemo(() => lerFiltros(params), [params]);
  const colecao = lerColecao(params);
  const colunas = lerColunas(params);
  const rotulos = useMemo<RotulosDeFiltro>(() => {
    const assunto = params.get('assunto');
    return assunto ? { topico: assunto } : {};
  }, [params]);

  // A busca é a única que não lê da URL a cada tecla: o campo tem de responder
  // na hora, e só o valor já adiado é escrito de volta.
  const [busca, setBusca] = useState(() => params.get('q') ?? '');
  const [pagina, setPagina] = useState(1);
  const [folhaAberta, setFolhaAberta] = useState(false);

  const buscaAdiada = useAdiado(busca);
  const digitando = busca.trim() !== buscaAdiada.trim();

  const explicacao = usePaginaInteiraExplicada();

  const atualizarUrl = useCallback(
    (mudancas: Record<string, string | null>) => {
      setParams(
        (atual) => {
          const proximo = new URLSearchParams(atual);
          for (const [chave, valor] of Object.entries(mudancas)) {
            if (valor) proximo.set(chave, valor);
            else proximo.delete(chave);
          }
          return proximo;
        },
        // `replace`: trocar de filtro não pode empilhar uma entrada de
        // histórico por toque — o "voltar" do aparelho tem de sair da tela, e
        // não desfazer filtro por filtro até o aluno desistir.
        { replace: true },
      );
    },
    [setParams],
  );

  // Um escritor só para `q`, e é este: dois `setParams` no mesmo tique
  // compõem sobre a MESMA URL antiga, e o segundo apagaria o primeiro.
  useEffect(() => {
    const alvo = buscaAdiada.trim();
    if ((params.get('q') ?? '') === alvo) return;
    atualizarUrl({ q: alvo || null });
  }, [buscaAdiada, params, atualizarUrl]);

  const recorte = useMemo<FiltrosBanco>(
    () => ({
      ...filtros,
      colecao,
      busca: buscaAdiada.trim() || undefined,
      pagina,
      porPagina: POR_PAGINA,
    }),
    [filtros, colecao, buscaAdiada, pagina],
  );

  const questoes = useQuestoesDoBanco(recorte);
  const estudo = useEstudo();

  // As duas contagens do acervo, sem filtro nenhum: alimentam o subtítulo de
  // cada coleção E o total do campo de busca. `porPagina: 1` porque só o
  // `total` interessa — trazer vinte questões para mostrar um número seria
  // pagar a página duas vezes. Ficam uma hora em cache (conteúdo de prova).
  const totalRecentes = useQuestoesDoBanco({ colecao: 'recentes', pagina: 1, porPagina: 1 });
  const totalArquivo = useQuestoesDoBanco({ colecao: 'arquivo', pagina: 1, porPagina: 1 });
  const porColecao: Record<ColecaoBanco, number | null> = {
    recentes: totalRecentes.data?.total ?? null,
    arquivo: totalArquivo.data?.total ?? null,
  };
  const totalDoAcervo =
    porColecao.recentes != null && porColecao.arquivo != null
      ? porColecao.recentes + porColecao.arquivo
      : null;

  // A lista de trabalho: a mais recente entre as que têm questão. Uma lista
  // vazia não se exporta, e oferecer "Exportar PDF" nela abriria um documento
  // em branco.
  const listas = useListas();
  const escolhida = useMemo(() => {
    const comQuestoes = (listas.data ?? []).filter((l) => l.totalQuestoes > 0);
    return [...comQuestoes].sort((a, b) => b.atualizadaEm.localeCompare(a.atualizadaEm))[0] ?? null;
  }, [listas.data]);
  // As questões da lista escolhida, para o exportador — ele monta o documento a
  // partir delas. São poucas (a lista é montada à mão), então vem junto em vez
  // de ser buscada no clique, que deixaria o botão pensando.
  const listaCheia = useLista(escolhida?.id ?? null);

  // ── Acúmulo das páginas ────────────────────────────────────────────────
  // "CARREGAR MAIS", e nunca rolagem infinita: o aluno abre uma questão em
  // tela cheia e volta, e a rolagem infinita perde o ponto da lista.
  const [acervo, setAcervo] = useState<QuestaoVestibular[]>([]);

  useEffect(() => {
    const resposta = questoes.data;
    if (!resposta) return;
    setAcervo((anterior) => {
      if (resposta.pagina <= 1) return resposta.questoes;
      // Dedup por id: marcar uma questão como resolvida invalida
      // `['banco','questoes']` e a página corrente volta a chegar. Sem o
      // filtro, cada refetch duplicaria as vinte da última página.
      const vistos = new Set(anterior.map((q) => q.id));
      return [...anterior, ...resposta.questoes.filter((q) => !vistos.has(q.id))];
    });
  }, [questoes.data]);

  // `resolvida` e `anotacao` viajam DENTRO de cada questão, e só a última
  // página refaz a consulta. Sem esta sobreposição, marcar uma questão de uma
  // página já acumulada não mudaria o cartão até o cache expirar.
  const porQuestao = useMemo(
    () => new Map((estudo.data ?? []).map((e) => [e.questaoId, e])),
    [estudo.data],
  );
  const lista = useMemo(
    () =>
      acervo.map((q) => {
        const meu = porQuestao.get(q.id);
        return meu ? { ...q, resolvida: meu.resolvida, anotacao: meu.anotacao } : q;
      }),
    [acervo, porQuestao],
  );

  // A explicação da página inteira abre AO ENTRAR NO BANCO, uma vez por sessão
  // (decisão de 04/09, docs/35 §6). Antes esperava a primeira lista que
  // trouxesse questão em modo página, para chegar "em contexto" — mas o
  // Arquivo é a metade maior do acervo, então o contexto é a aba inteira, e
  // esperar a lista fazia a folha aparecer por cima de questões que o aluno já
  // tinha começado a ler.
  const { explicarSePrimeiraVez } = explicacao;
  useEffect(() => {
    explicarSePrimeiraVez();
  }, [explicarSePrimeiraVez]);

  const total = questoes.data?.total ?? 0;
  const temMais = lista.length < total;
  const ativos = CHAVES_DE_FILTRO.filter((c) => filtros[c] !== undefined);
  // O contador do botão "Filtros" conta só o que a folha guarda: matéria e
  // assunto estão no centro, à vista, e somá-los aqui prometeria dentro da
  // folha um recorte que não está lá.
  const ativosNaFolha = ativos.filter((c) => CHAVES_DA_FOLHA.includes(c));
  const temRecorte = ativos.length > 0 || buscaAdiada.trim() !== '';
  const outra: ColecaoBanco = colecao === 'recentes' ? 'arquivo' : 'recentes';

  function aplicarRecorte(novos: FiltrosBanco, novosRotulos: RotulosDeFiltro) {
    atualizarUrl({
      materia: novos.materia ?? null,
      vestibular: novos.vestibular ?? null,
      anos: novos.anos?.length ? novos.anos.join(',') : null,
      fase: novos.fase != null ? String(novos.fase) : null,
      topico: novos.topico ?? null,
      assunto: novos.topico ? (novosRotulos.topico ?? null) : null,
    });
    setPagina(1);
  }

  function trocarColecao(id: ColecaoBanco) {
    atualizarUrl({ colecao: id === 'recentes' ? null : id });
    setPagina(1);
  }

  function removerFiltro(chave: ChaveDeFiltro) {
    const novos = { ...filtros };
    delete novos[chave];
    // Tirar a matéria tira o tópico junto: o código sobreviveria apontando
    // para outro assunto, e a rota devolve 400 (docs/28 §6).
    if (chave === 'materia') delete novos.topico;
    aplicarRecorte(novos, chave === 'materia' || chave === 'topico' ? {} : rotulos);
  }

  function limparTudo() {
    // `q` sai pelo efeito do debounce, não daqui: um segundo `setParams` neste
    // mesmo tique sobrescreveria o primeiro.
    setBusca('');
    aplicarRecorte({}, {});
  }

  const daLista = listaCheia.data ?? null;

  return (
    <>
      <CabecaDoCampo titulo="Banco de questões" />

      <div className="alu-banco">
        {/* A coluna fixa só existe no desktop (o CSS a esconde no celular),
            onde há largura ao lado da lista. Ela guarda os SECUNDÁRIOS —
            coleção, vestibular, fase e ano; matéria e assunto ficam no centro.
            No celular a mesma capacidade sobe do rodapé, pela folha — ver o
            comentário de `FolhaFiltros`. */}
        <PainelDeFiltros
          filtros={filtros}
          rotulos={rotulos}
          colecao={colecao}
          onTrocarColecao={trocarColecao}
          onAplicar={aplicarRecorte}
        />

        <div className="alu-banco__corpo">
          {/* Os dois grupos convivem numa barra só. No celular eles empilham —
              busca, depois filtros + lista, depois exportar. No desktop cada
              grupo vira `display: contents` e os controles se alinham numa
              linha só, como o desenho pede. É por isso que eles compartilham um
              pai: sem ele, o CSS não teria como juntá-los. */}
          <div className="alu-banco__barra">
          <div className="alu-banco__ferramentas">
            <span className="alu-est-busca__campo">
              <Icone nome="busca" tamanho={18} />
              <input
                className="alu-campo"
                type="search"
                enterKeyHint="search"
                value={busca}
                // O total no `placeholder` é o do acervo INTEIRO, e é lido do
                // servidor — nunca cravado. Um "2.693" no código envelheceria
                // calado na próxima importação, e é justamente o número que
                // promete ao aluno o tamanho do que ele tem em mãos.
                placeholder={
                  totalDoAcervo == null
                    ? 'Buscar no banco de questões'
                    : `Buscar no banco de ${fmtInteiro(totalDoAcervo)} questões`
                }
                aria-label="Buscar questões pelo enunciado"
                onChange={(ev) => {
                  setBusca(ev.target.value);
                  setPagina(1);
                }}
              />
            </span>

            {/* Some no desktop: lá o painel de filtros está sempre à vista, e
                um botão que abre o que já está aberto é ruído. */}
            <button
              type="button"
              className={`alu-est-filtrar${ativosNaFolha.length ? ' is-ativo' : ''}`}
              aria-expanded={folhaAberta}
              onClick={() => setFolhaAberta(true)}
            >
              <Icone nome="filtro" tamanho={18} />
              Filtros
              {ativosNaFolha.length > 0 && (
                <span className="alu-est-filtrar__contagem">{ativosNaFolha.length}</span>
              )}
            </button>

            <Link className="alu-banco__lista" to="/estudar/listas">
              Minha lista
              {escolhida && <span className="alu-banco__lista-n">{escolhida.totalQuestoes}</span>}
            </Link>

            {/* Uma coluna dá largura à página inteira do caderno; duas servem
                para varrer. A escolha é do aluno, e vive na URL como o resto do
                recorte. Só no desktop — a 390px não há o que escolher. */}
            <fieldset className="alu-banco__visao">
              <legend className="alu-so-leitor">Densidade da lista</legend>
              {([1, 2] as Colunas[]).map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`alu-banco__visao-opcao${colunas === n ? ' is-ativa' : ''}`}
                  aria-pressed={colunas === n}
                  aria-label={n === 1 ? 'Uma questão por linha' : 'Duas por linha'}
                  onClick={() => atualizarUrl({ colunas: n === 2 ? null : '1' })}
                >
                  <Icone nome={n === 1 ? 'faixas' : 'grade'} tamanho={17} />
                </button>
              ))}
            </fieldset>
          </div>

          {/* Exportar a lista para resolver no papel. Existe porque a prova é
              no papel: treinar na tela e fazer a prova na folha são gestos
              diferentes, e o aluno pede o PDF para simular o segundo. */}
          <div className="alu-banco__exportar">
            <p>
              {escolhida
                ? 'Exportar sua lista para resolver no papel'
                : 'Monte uma lista para exportar e resolver no papel'}
            </p>
            <button
              type="button"
              className="alu-banco__exportar-acao is-primaria"
              // Desabilitado enquanto as questões não chegaram: exportar uma
              // lista pela metade produz um PDF que parece completo.
              disabled={!daLista || daLista.questoes.length === 0}
              onClick={() => daLista && exportarPdf(daLista)}
            >
              Exportar PDF
            </button>
            <button
              type="button"
              className="alu-banco__exportar-acao"
              disabled={!daLista || daLista.questoes.length === 0}
              onClick={() => daLista && exportarWord(daLista)}
            >
              Word
            </button>
          </div>
          </div>

          {/* MATÉRIA E ASSUNTO, no slot que era dos cartões de coleção
              (docs/35 §5). São os dois primários: matéria é o que destrava o
              assunto, e o aviso que manda escolher uma agora fica a uma linha
              das pílulas que ele cita. Vale nos dois tamanhos de tela — no
              celular este É o centro. */}
          <FiltrosDeMateriaEAssunto filtros={filtros} onAplicar={aplicarRecorte} />

          {/* A coleção, no celular. No desktop ela vive no painel lateral e o
              CSS esconde esta cópia — mas no celular não há painel, e enfiá-la
              na folha do rodapé tiraria da vista o controle que diz COMO a
              lista atrás se lê. Uma das duas está sempre ativa. */}
          <SeletorDeColecao colecao={colecao} onTrocar={trocarColecao} variante="centro" />

      {ativos.length > 0 && (
        <ul className="alu-est-pilulas">
          {ativos.map((chave) => (
            <li key={chave}>
              <button type="button" className="alu-est-pilula" onClick={() => removerFiltro(chave)}>
                {rotuloDoFiltro(chave, filtros, rotulos)}
                <Icone nome="fechar" tamanho={13} />
                <span className="alu-so-leitor">Remover este filtro</span>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              className="alu-est-pilula alu-est-pilula--limpar"
              onClick={limparTudo}
            >
              Limpar tudo
            </button>
          </li>
        </ul>
      )}

          {/* ⚠️ "inclui as sem classificação de tópico" não é rodapé: sem essa
              frase o aluno soma os assuntos do filtro, não fecha com o total, e
              conclui que a tela está errada (docs/22 §8). O que a coleção É
              fica na aba acima; aqui é só quantas e o que entra na conta. */}
          <p className="alu-est-recorte" aria-live="polite">
            {questoes.isPending
              ? 'Contando…'
              : `${fmtInteiro(total)} ${total === 1 ? 'questão' : 'questões'} · inclui as sem classificação de tópico`}
          </p>

      {questoes.isError ? (
        <div className="alu-bloco">
          <p className="alu-erro">Não deu para carregar as questões agora.</p>
          <p className="alu-vazio">
            Pode ser a sua conexão. Toque para tentar de novo — o que você filtrou continua
            aqui.
          </p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => {
              questoes.refetch();
            }}
          >
            Tentar de novo
          </button>
        </div>
      ) : questoes.isPending ? (
        <Esqueleto />
      ) : total === 0 ? (
        <div className="alu-bloco">
          <p className="alu-vazio">
            {temRecorte
              ? `Nenhuma questão bate com esse recorte em ${colecao === 'recentes' ? 'Recentes' : 'Arquivo'}.`
              : 'Esta coleção está vazia por aqui. Se isso não parece certo, avise a coordenação.'}
          </p>
          {/* ⚠️ Uma das duas coleções está sempre ativa, então "não achei nada"
              nunca é a resposta sobre o acervo INTEIRO. Sem esta saída o aluno
              conclui que a questão não existe, quando ela está na outra metade. */}
          <button type="button" className="alu-tecla" onClick={() => trocarColecao(outra)}>
            Procurar em {outra === 'recentes' ? 'Recentes' : 'Arquivo'}
          </button>
          {/* A busca casa PALAVRA no enunciado; não é semântica (docs/22 §8).
              Quem procurou "questões sobre gases ideais" e não achou nada
              precisa saber disso, senão conclui que o acervo é que é pobre.
              E no Arquivo há questão sem transcrição nenhuma (0033), que a
              busca textual não alcança de jeito nenhum. */}
          {buscaAdiada.trim() !== '' && (
            <p className="alu-vazio">
              A busca procura as palavras exatas no enunciado, e não o assunto. No Arquivo
              parte das questões não tem texto transcrito — só a imagem da página —, e essas
              a busca não alcança. Para achar por assunto, use Filtrar.
            </p>
          )}
          {temRecorte && (
            <button type="button" className="alu-tecla alu-tecla--fantasma" onClick={limparTudo}>
              Limpar o recorte
            </button>
          )}
        </div>
      ) : lista.length === 0 ? (
        /* Há total, e o acumulador ainda não recebeu a página: um quadro de
           esqueleto, e nunca o estado vazio — piscar "nada encontrado" sobre
           uma lista que existe é a mentira mais fácil de cometer aqui. */
        <Esqueleto />
      ) : (
        <>
          {/* Duas classes de recorte, e as duas mexem no CHROME do cartão:
              em "Recentes" o cartão perde a caixa no celular e vira item de
              lista separado por traço (é o desenho: o enunciado já é uma caixa,
              e caixa dentro de caixa vira ruído); em "Arquivo" ele mantém a
              caixa, porque a tarja fixa precisa de um fundo para grudar. */}
          <ul
            className={`alu-est-lista alu-est-lista--${colecao} alu-est-lista--col${colunas}`}
          >
            {lista.map((q) => (
              <li key={q.id}>
                <CartaoQuestaoAluno questao={q} onExplicarPagina={explicacao.reabrir} />
              </li>
            ))}
          </ul>

          {temMais && (
            <button
              type="button"
              className="alu-tecla alu-tecla--fantasma alu-tecla--larga"
              disabled={questoes.isFetching || digitando}
              onClick={() => setPagina((p) => p + 1)}
            >
              {questoes.isFetching ? 'Carregando…' : 'Carregar mais'}
            </button>
          )}
        </>
      )}

        </div>
      </div>

      {folhaAberta && (
        <FolhaFiltros
          filtros={filtros}
          rotulos={rotulos}
          busca={buscaAdiada}
          colecao={colecao}
          onFechar={() => setFolhaAberta(false)}
          onAplicar={(novos, novosRotulos) => {
            aplicarRecorte(novos, novosRotulos);
            setFolhaAberta(false);
          }}
        />
      )}

      <FolhaDaPaginaInteira aberta={explicacao.aberta} onFechar={explicacao.fechar} />
    </>
  );
}

/** Esqueleto com a forma do conteúdo, nunca um spinner (brief §Estados). */
function Esqueleto() {
  return (
    <div className="alu-est-esqueleto" aria-busy="true">
      <span className="alu-so-leitor">Carregando as questões…</span>
      {[0, 1, 2].map((i) => (
        <div key={i} className="alu-est-esqueleto__cartao">
          <span className="alu-est-esqueleto__linha alu-est-esqueleto__linha--olho" />
          <span className="alu-est-esqueleto__bloco" />
          <span className="alu-est-esqueleto__linha" />
        </div>
      ))}
    </div>
  );
}
