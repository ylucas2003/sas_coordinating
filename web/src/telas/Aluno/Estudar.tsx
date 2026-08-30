import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import {
  useEstudo,
  useListas,
  useMeusErros,
  useMissaoDoDia,
  useQuestoesDoBanco,
} from '../../dados/aluno';
import type { FiltrosBanco, QuestaoVestibular } from '../../dados/aluno';
import { Bloco } from './pecas/Bloco';
import { CartaoQuestaoAluno } from './pecas/CartaoQuestaoAluno';
import { FolhaFiltros } from './pecas/FolhaFiltros';
import type { RotulosDeFiltro } from './pecas/FolhaFiltros';
import { Icone } from './pecas/Icone';
import { AVISO_DE_COBERTURA, MATERIAS_COM_TAXONOMIA, fmtInteiro } from './pecas/formato';

// ESTUDAR — duas metades, e não um controle segmentado.
//
// ⚠️ A versão anterior do desenho pedia três abas ("Prioridade", "Meus erros",
// "Banco"). Está revogada: aquilo punha em paralelo coisas de naturezas
// diferentes — duas listas curtas que terminam em "treinar" e um acervo de
// 2.693 questões que se busca — e obrigava o aluno a escolher uma aba antes de
// ver qualquer coisa, numa tela cujo trabalho é dizer o que fazer.
//
//   1ª metade  TREINAR AGORA — três ORIGENS do mesmo fluxo de treino.
//   2ª metade  TODAS AS QUESTÕES — o acervo, com busca sempre visível.
//
// E não se chama "Banco": "banco de questões" é vocabulário interno, não do
// aluno (docs/28 §4).

/** A página da listagem. O mesmo padrão da rota (`POR_PAGINA_PADRAO` = 20). */
const POR_PAGINA = 20;

/** Os cinco recortes que a folha controla. A busca fica fora: ela mora no
 *  campo, sempre visível, e não vira pílula removível. */
const CHAVES_DE_FILTRO = ['materia', 'vestibular', 'ano', 'fase', 'topico'] as const;
type ChaveDeFiltro = (typeof CHAVES_DE_FILTRO)[number];

/**
 * Adia um valor. A busca é textual sobre o enunciado de 2.693 questões: bater
 * a cada tecla enfileiraria uma consulta por caractere, e a resposta que chega
 * primeiro nem sempre é a do texto mais recente.
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

  const ano = Number(params.get('ano'));
  if (Number.isInteger(ano) && ano > 1900) filtros.ano = ano;

  const fase = Number(params.get('fase'));
  if (fase === 1 || fase === 2) filtros.fase = fase;

  const topico = params.get('topico');
  if (topico && filtros.materia) filtros.topico = topico;

  return filtros;
}

export function Estudar() {
  const [params, setParams] = useSearchParams();

  // ⚠️ O RECORTE VIVE NA URL, e não em `useState`.
  //
  // `/questao/:id` é rota de TOPO (App.tsx): abrir uma questão DESMONTA esta
  // tela inteira, e um filtro guardado em estado local não sobreviveria ao
  // voltar — que é justamente o caminho mais usado do produto. Na URL ele
  // volta, e de quebra o recorte vira link.
  const filtros = useMemo(() => lerFiltros(params), [params]);
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
      busca: buscaAdiada.trim() || undefined,
      pagina,
      porPagina: POR_PAGINA,
    }),
    [filtros, buscaAdiada, pagina],
  );

  const questoes = useQuestoesDoBanco(recorte);
  const estudo = useEstudo();

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
  // página já acumulada não mudaria o cartão até o cache expirar — e
  // `/banco/estudo` é justamente a rota que responde isso inteiro, de uma vez.
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

  const total = questoes.data?.total ?? 0;
  const temMais = lista.length < total;
  const ativos = CHAVES_DE_FILTRO.filter((c) => filtros[c] !== undefined);
  const temRecorte = ativos.length > 0 || buscaAdiada.trim() !== '';

  function aplicarRecorte(novos: FiltrosBanco, novosRotulos: RotulosDeFiltro) {
    atualizarUrl({
      materia: novos.materia ?? null,
      vestibular: novos.vestibular ?? null,
      ano: novos.ano != null ? String(novos.ano) : null,
      fase: novos.fase != null ? String(novos.fase) : null,
      topico: novos.topico ?? null,
      assunto: novos.topico ? (novosRotulos.topico ?? null) : null,
    });
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

  return (
    <>
      <h1 className="alu-titulo-tela">Estudar</h1>

      {/* ── PRIMEIRA METADE ─────────────────────────────────────────── */}

      <section className="alu-est-metade" aria-labelledby="alu-est-treinar">
        <h2 className="alu-olho" id="alu-est-treinar">
          Treinar agora
        </h2>

        <TiraDeCobertura />

        <CartaoRecomendado />
        <CartaoErros />
        <CartaoLista />

        <Link className="alu-est-elo-quieto" to="/estudar/assuntos">
          O que mais cai
          <Icone nome="avancar" tamanho={15} />
        </Link>
      </section>

      <hr className="alu-est-divisor" />

      {/* ── SEGUNDA METADE ──────────────────────────────────────────── */}

      <section className="alu-est-metade" aria-labelledby="alu-est-acervo">
        <h2 className="alu-olho" id="alu-est-acervo">
          Todas as questões
        </h2>

        <div className="alu-est-busca">
          <span className="alu-est-busca__campo">
            <Icone nome="busca" tamanho={18} />
            <input
              className="alu-campo"
              type="search"
              enterKeyHint="search"
              value={busca}
              placeholder="Buscar no enunciado…"
              aria-label="Buscar questões pelo enunciado"
              onChange={(ev) => {
                setBusca(ev.target.value);
                setPagina(1);
              }}
            />
          </span>

          <button
            type="button"
            className={`alu-est-filtrar${ativos.length ? ' is-ativo' : ''}`}
            aria-expanded={folhaAberta}
            onClick={() => setFolhaAberta(true)}
          >
            <Icone nome="filtro" tamanho={18} />
            Filtrar
            {ativos.length > 0 && (
              <span className="alu-est-filtrar__contagem">{ativos.length}</span>
            )}
          </button>
        </div>

        {ativos.length > 0 && (
          <ul className="alu-est-pilulas">
            {ativos.map((chave) => (
              <li key={chave}>
                <button
                  type="button"
                  className="alu-est-pilula"
                  onClick={() => removerFiltro(chave)}
                >
                  {rotuloDoFiltro(chave, filtros, rotulos)}
                  <Icone nome="fechar" tamanho={13} />
                  <span className="alu-so-leitor">Remover este filtro</span>
                </button>
              </li>
            ))}
            <li>
              <button type="button" className="alu-est-pilula alu-est-pilula--limpar" onClick={limparTudo}>
                Limpar tudo
              </button>
            </li>
          </ul>
        )}

        <p className="alu-est-recorte" aria-live="polite">
          {questoes.isPending
            ? 'Contando…'
            : `${fmtInteiro(total)} ${total === 1 ? 'questão' : 'questões'}`}
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
                ? 'Nenhuma questão bate com esse recorte. Tire um filtro ou procure por outra palavra — o acervo tem prova do ITA e do IME de quase vinte anos.'
                : 'O acervo está vazio por aqui. Se isso não parece certo, avise a coordenação.'}
            </p>
            {/* A busca casa PALAVRA no enunciado; não é semântica (docs/22 §8).
                Quem procurou "questões sobre gases ideais" e não achou nada
                precisa saber disso, senão conclui que o acervo é que é pobre. */}
            {buscaAdiada.trim() !== '' && (
              <p className="alu-vazio">
                A busca procura as palavras exatas no enunciado, e não o assunto. Para achar
                por assunto, use Filtrar.
              </p>
            )}
            {temRecorte && (
              <button type="button" className="alu-tecla" onClick={limparTudo}>
                Ver todas
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
            <ul className="alu-est-lista">
              {lista.map((q) => (
                <li key={q.id}>
                  <CartaoQuestaoAluno questao={q} />
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
      </section>

      {folhaAberta && (
        <FolhaFiltros
          filtros={filtros}
          rotulos={rotulos}
          busca={buscaAdiada}
          onFechar={() => setFolhaAberta(false)}
          onAplicar={(novos, novosRotulos) => {
            aplicarRecorte(novos, novosRotulos);
            setFolhaAberta(false);
          }}
        />
      )}
    </>
  );
}

/**
 * A tira de cobertura.
 *
 * ⚠️ Não é firula (docs/24 §3.3). A taxonomia do edital só cobre Matemática,
 * Física e Química, e um plano que silenciosamente ignora Inglês é pior que
 * nenhum plano — o aluno conclui que está coberto, e o Inglês da Fase 1 do ITA
 * é a ÚNICA matéria eliminatória. Vazada, 1px, sem preenchimento: é aviso, não
 * alarme.
 */
function TiraDeCobertura() {
  return (
    <p className="alu-est-cobertura">
      <span className="alu-olho alu-olho--quieto">Cobertura</span>
      {AVISO_DE_COBERTURA}
    </p>
  );
}

// ─── As três origens do treino ───────────────────────────────────────────

function CartaoRecomendado() {
  const missao = useMissaoDoDia();

  return (
    <Bloco fonte="missaoDoDia" olho="Recomendado" className="alu-est-origem alu-est-origem--principal">
      {missao.isPending ? (
        <p className="alu-carregando">Escolhendo o que vale mais…</p>
      ) : missao.isError || !missao.data ? (
        <p className="alu-vazio">
          Ainda não deu para escolher um assunto para você. Comece pelo acervo, aqui embaixo.
        </p>
      ) : (
        <div className="alu-est-origem__linha">
          <span className="alu-est-origem__texto">
            <strong className="alu-est-origem__titulo">{missao.data.nome}</strong>
            <span className="alu-est-origem__conta">
              {missao.data.quantidade} questões · {missao.data.materia}
            </span>
            <span className="alu-est-origem__razao">{missao.data.razao}</span>
          </span>
          <Link className="alu-tecla" to="/treino/prioridade">
            Começar
          </Link>
        </div>
      )}
    </Bloco>
  );
}

function CartaoErros() {
  const erros = useMeusErros();
  const quantos = erros.data?.length ?? 0;

  return (
    <Bloco fonte="meusErros" olho="Seus erros" className="alu-est-origem">
      {erros.isPending ? (
        <p className="alu-carregando">Somando seus erros…</p>
      ) : erros.isError ? (
        // ⚠️ Nunca cair no vazio quando a consulta falhou. "Nenhum erro
        // registrado" para quem tem 34 é a mentira mais cara desta tela: o
        // aluno conclui que está limpo e vai treinar outra coisa.
        <p className="alu-erro">
          Não deu para somar seus erros agora. Recarregue a tela — as questões continuam lá.
        </p>
      ) : quantos === 0 ? (
        <p className="alu-vazio">
          Nenhum erro registrado ainda. Depois do próximo simulado as questões que passarem
          por você aparecem aqui.
        </p>
      ) : (
        <div className="alu-est-origem__linha">
          <span className="alu-est-origem__texto">
            <strong className="alu-est-origem__titulo">
              {quantos} {quantos === 1 ? 'questão' : 'questões'}
            </strong>
            <span className="alu-est-origem__razao">
              que você errou nos simulados. É o material de estudo mais direto que você tem.
            </span>
          </span>
          <Link className="alu-tecla alu-tecla--fantasma" to="/treino/erros">
            Revisar
          </Link>
        </div>
      )}
    </Bloco>
  );
}

function CartaoLista() {
  const listas = useListas();

  // A mais recente entre as que têm questão: uma lista vazia não é fila de
  // treino, e oferecer "TREINAR" nela seria abrir uma sessão de zero questões.
  const escolhida = useMemo(() => {
    const todas = listas.data ?? [];
    const comQuestoes = todas.filter((l) => l.totalQuestoes > 0);
    return (
      [...comQuestoes].sort((a, b) => b.atualizadaEm.localeCompare(a.atualizadaEm))[0] ?? null
    );
  }, [listas.data]);

  const temAlguma = (listas.data?.length ?? 0) > 0;

  return (
    <Bloco olho="Sua lista" acao={temAlguma && <Link to="/estudar/listas">Ver todas</Link>} className="alu-est-origem">
      {listas.isPending ? (
        <p className="alu-carregando">Abrindo suas listas…</p>
      ) : listas.isError ? (
        // Mesma regra do cartão de erros: falha não pode virar "monte a sua
        // fila", que é o convite oferecido a quem ainda não tem lista nenhuma.
        <div className="alu-est-origem__linha">
          <span className="alu-est-origem__texto alu-erro">
            Não deu para abrir suas listas.
          </span>
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
      ) : !escolhida ? (
        <div className="alu-est-origem__linha">
          <span className="alu-est-origem__texto">
            <strong className="alu-est-origem__titulo">
              {temAlguma ? 'Sua lista está vazia' : 'Monte a sua fila'}
            </strong>
            <span className="alu-est-origem__razao">
              Separe as questões que você quer refazer e treine só elas, na ordem que você
              escolher.
            </span>
          </span>
          <Link className="alu-tecla alu-tecla--fantasma" to="/estudar/listas">
            Montar
          </Link>
        </div>
      ) : (
        <div className="alu-est-origem__linha">
          <span className="alu-est-origem__texto">
            <strong className="alu-est-origem__titulo">{escolhida.titulo}</strong>
            <span className="alu-est-origem__razao">
              {escolhida.totalQuestoes}{' '}
              {escolhida.totalQuestoes === 1 ? 'questão que você separou' : 'questões que você separou'}
            </span>
          </span>
          <Link className="alu-tecla alu-tecla--fantasma" to={`/treino/lista/${escolhida.id}`}>
            Treinar
          </Link>
        </div>
      )}
    </Bloco>
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
