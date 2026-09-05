import { useCallback, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { Markdown } from '../../componentes/ui/Markdown';
import {
  RAZAO_DA_FILA,
  ordenarFilaDeTreino,
  useLista,
  useMeusErros,
  useMissaoDoDia,
  useAtualizarEstudo,
  useQuestoesDoBanco,
  useTaxonomia,
} from '../../dados/aluno';
import type {
  BlocoTaxonomia,
  FiltrosBanco,
  MateriaBanco,
  QuestaoVestibular,
  RespostaNoTreino,
  TaxonomiaMateria,
} from '../../dados/aluno';
import { ehDissertativa, letrasDaQuestao, temGabarito } from '../../dominio/banco';
import { Icone } from './pecas/Icone';
import { TarjaFonte } from './pecas/TarjaFonte';
import { MATERIAS_COM_TAXONOMIA } from './pecas/formato';

// A sessão de treino: uma fila de questões, uma por vez, em tela cheia.
//
// Rota de topo (`App.tsx`), fora do casco: sem barra inferior e sem o botão do
// Tio Léo. Uma fila com navegação por baixo convida a sair no meio, que é o
// oposto do que a sessão precisa (docs/28 §3, regra 2).
//
// ⚠️ NUNCA aparece XP aqui, em estado nenhum. Treino não é supervisionado —
// nada impede clicar em alternativa aleatória — então quem paga é o simulado
// (docs/28 §3, regra 5, e docs/26 §1). Um "+20 XP" nesta tela contradiz a regra
// central do produto inteiro.
//
// A DIVISÃO DO QUE É REAL E DO QUE NÃO É, que é o ponto do arquivo:
//   · as QUESTÕES são reais, de `GET /banco/questoes` e `GET /banco/listas/{id}`;
//   · a ORDEM é mock (`ordenarFilaDeTreino`, fonte `escolhaDaFilaDeTreino`);
//   · a RESPOSTA do aluno é mock — não existe coluna no banco para ela
//     (`questao_estudo_aluno` só tem `resolvida` e `anotacao`), então ela vive
//     em `useState` e morre com a sessão. Fonte `respostaNoTreino`.

/** A resposta de uma questão, com o assunto junto: `resumoDoTreino` agrupa por
 *  ele, e o nome do tópico não sobrevive à saída da tela. */
export interface RespostaDaSessao extends RespostaNoTreino {
  assunto: string | null;
}

/** O que a sessão manda para a tela de resumo pelo `state` do `navigate`. */
export interface EstadoDoResumo {
  respostas: RespostaDaSessao[];
  /** O caminho exato da sessão, para o "Treinar mais" voltar ao mesmo recorte. */
  voltarPara: string;
}

/**
 * Quantas questões a sessão tem quando a origem não diz.
 *
 * Não é dado do aluno: é parâmetro de interface. A origem `prioridade` usa
 * `missao.quantidade` — que desde 04/09 vem do servidor e é sempre 10, então
 * cartão e fila passaram a concordar sozinhos (docs/35 §9) —, e a `lista` usa o
 * tamanho da lista que ele montou.
 */
const QUESTOES_POR_SESSAO = 12;

/**
 * Quantas questões o servidor manda por vez.
 *
 * Bem maior que a sessão de propósito: a fila descarta dissertativas, as já
 * resolvidas e as sem gabarito, e pedir 12 devolveria menos de 12 quase sempre.
 */
const LOTE = 60;

/** O acervo só tem estas três — `MateriaBanco` é fechado, e a rota devolve 422
 *  para qualquer outra. Português, Inglês e Redação não têm banco (docs/24 §3.3). */
function materiaDoBanco(nome: string | null | undefined): MateriaBanco | null {
  return MATERIAS_COM_TAXONOMIA.find((m) => m === nome) ?? null;
}

/** Só entra na fila o que dá para RESPONDER: com alternativa e com letra a
 *  conferir. Sem isso a sessão pararia numa questão que não tem o que corrigir. */
function respondivel(questao: QuestaoVestibular): boolean {
  return !ehDissertativa(questao) && temGabarito(questao) && letrasDaQuestao(questao).length > 0;
}

export function Treino() {
  const navigate = useNavigate();
  const params = useParams();
  const [busca] = useSearchParams();

  const origem = params.origem ?? '';
  // A rota é `/treino/:origem/*`: o resto do caminho é o id da lista
  // (`/treino/lista/abc`) ou o código do assunto (`/treino/assunto/7.2`).
  const resto = (params['*'] ?? '').split('/').filter(Boolean);

  const listaId = origem === 'lista' ? (resto[0] ?? null) : null;

  // ── De onde vem o recorte ─────────────────────────────────────────────
  const missao = useMissaoDoDia();
  const erros = useMeusErros();
  const taxonomia = useTaxonomia();
  const lista = useLista(listaId);

  // `/treino/assunto/7.2` não diz a matéria, e TÓPICO EXIGE MATÉRIA: '1.1' é
  // "Fundamentos" em Física, "Conjuntos e Lógica" em Matemática e "Estrutura
  // Atômica" em Química, e a rota devolve 400 sem ela de propósito (docs/28 §6).
  // Por isso aceitamos as três formas: `/treino/assunto/Física/7.2`,
  // `?materia=Física`, e — por último — a busca no catálogo de assuntos.
  const codigoDoAssunto = origem === 'assunto' ? (resto[resto.length - 1] ?? null) : null;
  const materiaDaUrl = materiaDoBanco(resto.length > 1 ? resto[0] : busca.get('materia'));
  // A matéria de um código de tópico, procurada na taxonomia REAL do edital.
  // Antes isto vinha do catálogo mockado de cinco assuntos, que só acertava
  // para esses cinco: com os 65 tópicos de verdade, o link de assunto sem
  // matéria passa a resolver sempre.
  const materiaDoCatalogo = materiaDoBanco(
    taxonomia.data?.find((arvore: TaxonomiaMateria) =>
      arvore.blocos.some((bloco: BlocoTaxonomia) =>
        bloco.topicos.some((topico) => topico.codigo === codigoDoAssunto),
      ),
    )?.materia,
  );
  const materiaDoAssunto = materiaDaUrl ?? materiaDoCatalogo;

  // A matéria em que o aluno mais errou. Os erros são de SIMULADO e as questões
  // do treino são de PROVA PASSADA — não são as mesmas questões, e não há como
  // ligar uma na outra hoje. O que dá para honrar é o recorte por matéria, e a
  // tela diz isso em vez de fingir que revisa a questão errada.
  const materiaComMaisErros = useMemo(() => {
    const contagem = new Map<string, number>();
    for (const e of erros.data ?? []) {
      if (!e.materia) continue;
      contagem.set(e.materia, (contagem.get(e.materia) ?? 0) + 1);
    }
    const ordenadas = [...contagem.entries()].sort((a, b) => b[1] - a[1]);
    return materiaDoBanco(ordenadas[0]?.[0]);
  }, [erros.data]);

  // O escape do filtro de assunto: quando o tópico não devolve nada, o aluno
  // troca a fila para a matéria inteira em vez de encarar uma tela vazia.
  const [semAssunto, setSemAssunto] = useState(false);
  // "Não repete questão já resolvida, a menos que o aluno peça revisão"
  // (docs/28 §3, regra 4). O pedido de revisão é este.
  const [incluirResolvidas, setIncluirResolvidas] = useState(false);

  const filtros: FiltrosBanco | null = useMemo(() => {
    if (origem === 'lista') return null;
    if (origem === 'assunto') {
      if (!materiaDoAssunto) return null;
      return semAssunto || !codigoDoAssunto
        ? { materia: materiaDoAssunto, porPagina: LOTE }
        : { materia: materiaDoAssunto, topico: codigoDoAssunto, porPagina: LOTE };
    }
    if (origem === 'erros') {
      if (!materiaComMaisErros) return null;
      return { materia: materiaComMaisErros, porPagina: LOTE };
    }
    if (origem === 'prioridade') {
      const materia = materiaDoBanco(missao.data?.materia);
      if (!materia) return null;
      return semAssunto
        ? { materia, porPagina: LOTE }
        : { materia, topico: missao.data?.topicoCodigo, porPagina: LOTE };
    }
    return null;
  }, [origem, materiaDoAssunto, codigoDoAssunto, materiaComMaisErros, missao.data, semAssunto]);

  const pagina = useQuestoesDoBanco(filtros ?? {}, { habilitada: filtros !== null });

  // ── A fila ────────────────────────────────────────────────────────────
  const questoesDaLista = lista.data?.questoes;
  const questoesDaPagina = pagina.data?.questoes;

  const tamanhoDaSessao =
    origem === 'prioridade' ? (missao.data?.quantidade ?? QUESTOES_POR_SESSAO) : QUESTOES_POR_SESSAO;

  // ⚠️ Sem o `filtros &&`, a fila leria o cache da chave `{}` — a mesma que
  // outra tela do banco usa — e mostraria questões de um recorte que ninguém
  // pediu enquanto a missão ainda estava carregando.
  const bruto = origem === 'lista' ? questoesDaLista : filtros ? questoesDaPagina : undefined;

  const fila = useMemo(() => {
    const base = bruto ?? [];
    const podemSerRespondidas = base.filter(respondivel);
    const candidatas = incluirResolvidas
      ? podemSerRespondidas
      : podemSerRespondidas.filter((q) => q.resolvida !== true);

    // ⚠️ Este é o ponto único de escolha da fila, e ele é MOCK
    // (`escolhaDaFilaDeTreino`): sem `acertoPorAssunto` não dá para pesar por
    // `importância × (1 − meu acerto)`, e a régua cai para "matéria mais longe
    // do corte" (docs/28 §3, regra 1). As questões que ele ordena são reais.
    const ordenadas = ordenarFilaDeTreino(candidatas);

    // Na lista, a ordem é do ALUNO — foi ele que a montou, e é isso que
    // `RAZAO_DA_FILA.lista` promete a ele. `ordenarFilaDeTreino` continua
    // valendo como filtro (é ele que tira as dissertativas); o que se desfaz é
    // só a reordenação.
    const naOrdemCerta =
      origem === 'lista'
        ? ordenadas.slice().sort((a, b) => base.indexOf(a) - base.indexOf(b))
        : ordenadas;

    return origem === 'lista' ? naOrdemCerta : naOrdemCerta.slice(0, tamanhoDaSessao);
  }, [bruto, incluirResolvidas, origem, tamanhoDaSessao]);

  // ── O estado da sessão ────────────────────────────────────────────────
  const [indice, setIndice] = useState(0);
  const [escolha, setEscolha] = useState<string | null>(null);
  const [conferido, setConferido] = useState(false);
  const [respostas, setRespostas] = useState<RespostaDaSessao[]>([]);
  // A mesma mutação do cartão: `PUT /banco/estudo/{id}`. Um campo por vez, e
  // campo ausente não é mexido — gravar a resposta não apaga a anotação nem a
  // marca de resolvida.
  const gravarResposta = useAtualizarEstudo();

  const questao = fila[indice];
  const total = fila.length;
  const ultima = indice >= total - 1;
  const gabarito = questao?.gabarito?.trim().toUpperCase() ?? null;
  const acertou = conferido && escolha != null && escolha.toUpperCase() === gabarito;

  // Trocar o recorte troca a fila inteira: continuar no índice 5 de uma fila
  // que virou outra mostraria outra questão sem o aluno pedir.
  const recomecar = useCallback(() => {
    setIndice(0);
    setEscolha(null);
    setConferido(false);
    setRespostas([]);
  }, []);

  // PRÉ-CARREGA A IMAGEM DA PRÓXIMA enquanto o aluno resolve a atual: numa
  // sessão de 12 questões são 12 PNGs, e esperar o download a cada "Próxima"
  // é o que faz a fila parecer lenta (docs/28 §6).
  useEffect(() => {
    const proxima = fila[indice + 1];
    if (!proxima?.imagemUrl || !proxima.usaImagemNoRender) return;
    const img = new Image();
    img.src = proxima.imagemUrl;
  }, [fila, indice]);

  const responder = useCallback(() => {
    // O `conferido` guarda contra o toque duplo: sem ele, dois cliques no mesmo
    // quadro gravariam a mesma questão duas vezes em `respostas`, e a barra de
    // progresso — que conta respostas — passaria de 12/12.
    if (!questao || escolha == null || conferido) return;
    setConferido(true);
    setRespostas((anteriores) => [
      ...anteriores,
      {
        questaoId: questao.id,
        alternativaEscolhida: escolha,
        acertou: escolha.toUpperCase() === (questao.gabarito?.trim().toUpperCase() ?? null),
        assunto: questao.topicos[0]?.nome ?? null,
      },
    ]);

    // A resposta sobrevive à sessão (migration 0042). O `acertou` gravado é o
    // do SERVIDOR, conferido contra o gabarito do banco — o cálculo daqui em
    // cima serve só ao veredito imediato da tela.
    //
    // Sem `await` e sem bloquear o veredito: a conferência já está feita na
    // tela, e uma rede lenta não pode segurar a resposta na frente do aluno. Se
    // a gravação falhar, o que se perde é a estatística de estudo — não a
    // sessão, que continua no `useState`.
    //
    // ⚠️ Isto NÃO marca a questão como resolvida. `resolvida` é auto-declarado
    // e o aluno é quem dá a marca, no pé do cartão; encadear as duas apagaria a
    // diferença que "Meu progresso" é obrigado a mostrar.
    gravarResposta.mutate({
      questaoId: questao.id,
      remendo: { alternativaEscolhida: escolha },
    });
  }, [questao, escolha, conferido, gravarResposta]);

  const caminhoDaSessao = `/treino/${origem}${resto.length ? `/${resto.join('/')}` : ''}`;

  const avancar = useCallback(() => {
    if (!ultima) {
      setIndice((i) => i + 1);
      setEscolha(null);
      setConferido(false);
      return;
    }
    // O resumo é `/treino/:origem/resumo` — dois segmentos, sempre. Levar o id
    // da lista junto cairia na rota da sessão outra vez, porque
    // `/treino/lista/abc/resumo` casa com `/treino/:origem/*`, não com a rota
    // do resumo. Quem carrega o contexto é o `state`.
    const estado: EstadoDoResumo = { respostas, voltarPara: caminhoDaSessao };
    navigate(`/treino/${origem}/resumo`, { state: estado, replace: true });
  }, [ultima, respostas, caminhoDaSessao, navigate, origem]);

  const sair = useCallback(() => {
    if (window.history.length > 1) navigate(-1);
    else navigate('/estudar');
  }, [navigate]);

  // ── Estados que não são a fila ────────────────────────────────────────
  const origemConhecida = origem in RAZAO_DA_FILA;
  // ⚠️ Consulta desabilitada continua reportando `isPending` no React Query.
  // Sem o teste do `listaId`, `/treino/lista` sem id ficaria num esqueleto
  // eterno em vez de dizer que falta a lista.
  const semRecorte = origem === 'lista' ? !listaId : filtros === null;
  const carregando = semRecorte
    ? origem !== 'lista' && (missao.isPending || erros.isPending || taxonomia.isPending)
    : origem === 'lista'
      ? lista.isPending
      : pagina.isPending;
  const falhou = origem === 'lista' ? lista.isError : pagina.isError;

  if (!origemConhecida) {
    return (
      <Moldura onSair={sair}>
        <p className="alu-vazio">
          Não sei montar uma fila de treino chamada “{origem}”. As que existem são a recomendada,
          a dos seus erros, a de uma lista sua e a de um assunto.
        </p>
        <BotaoVoltar />
      </Moldura>
    );
  }

  // A resposta viva do aluno, para a barra andar mesmo no erro.
  const passos = respostas.length;

  return (
    <div className="alu-shell alu-treino">
      <header className="alu-treino__topo">
        <button type="button" className="alu-treino__icone" onClick={sair} aria-label="Sair do treino">
          <Icone nome="fechar" tamanho={22} />
        </button>

        {/* A BARRA ANDA MESMO NO ERRO (regra 4 do desenho): ela mede quantas
            foram RESPONDIDAS, não quantas foram acertadas. Quem acerta 41% e vê
            a barra travar a cada erro conclui que não está indo a lugar nenhum,
            e essa é a sensação que mata a sessão no meio. */}
        <div
          className="alu-treino__progresso"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total || 1}
          aria-valuenow={passos}
          aria-label="Progresso da sessão"
        >
          <span
            className="alu-treino__progresso-fill"
            style={{ width: `${total ? (passos / total) * 100 : 0}%` }}
          />
        </div>

        <span className="alu-treino__contagem">
          {total ? `${Math.min(indice + 1, total)}/${total}` : '—'}
        </span>
      </header>

      <div className="alu-treino__corpo">
        <PorQueEstas
          origem={origem}
          materiaDosErros={materiaComMaisErros}
          nomeDaMissao={missao.data?.nome ?? null}
          razaoDaMissao={missao.data?.razao ?? null}
          tituloDaLista={lista.data?.titulo ?? null}
          incluirResolvidas={incluirResolvidas}
          onAlternarResolvidas={() => {
            setIncluirResolvidas((v) => !v);
            recomecar();
          }}
        />

        {carregando && <Esqueleto />}

        {!carregando && falhou && (
          <div className="alu-treino__aviso">
            <p className="alu-vazio">
              Não consegui carregar as questões. Pode ser a conexão. Tente de novo em alguns
              segundos.
            </p>
            <button
              type="button"
              className="alu-tecla"
              onClick={() => (origem === 'lista' ? lista.refetch() : pagina.refetch())}
            >
              Tentar de novo
            </button>
          </div>
        )}

        {!carregando && !falhou && !questao && (
          <FilaVazia
            origem={origem}
            bruto={bruto ?? []}
            incluirResolvidas={incluirResolvidas}
            semAssunto={semAssunto}
            semRecorte={semRecorte}
            onIncluirResolvidas={() => {
              setIncluirResolvidas(true);
              recomecar();
            }}
            onSoltarAssunto={() => {
              setSemAssunto(true);
              recomecar();
            }}
          />
        )}

        {!carregando && !falhou && questao && (
          <>
            {/* A MATÉRIA vem junto do assunto, e não é enfeite: o código do
                edital significa coisa diferente nas três ('7.2' é Ondas em
                Física e não existe em Química), e é por isso que o servidor
                devolve 400 para tópico sem matéria. Uma leitura por assunto que
                não diz a matéria é ambígua na origem (docs/28 §6). */}
            <p className="alu-olho alu-treino__origem">
              {[
                questao.materia,
                questao.topicos[0]?.nome ?? 'Sem assunto classificado',
                `${questao.vestibular} ${questao.ano}`,
              ].join(' · ')}
            </p>

            <AvisoDeClassificacao questao={questao} />

            {/* `key` obrigatório: sem ele o React reusa o mesmo nó ao trocar de
                questão, e o "a imagem falhou" da anterior ficaria valendo para
                a seguinte. */}
            <Enunciado key={questao.id} questao={questao} />

            {/* Só as LETRAS. O texto que ficava ao lado era a transcrição do
                LaTeX com as barras de fração perdidas ("Δx = 3Vi 2A 11mg
                50PatmA+55mg"), repetindo pior o que a imagem acima já mostra
                impresso. Uma fileira também devolve à questão a altura que as
                cinco linhas ocupavam. */}
            <ul className="alu-treino__alternativas">
              {letrasDaQuestao(questao).map((letra) => (
                <li key={letra}>
                  <Alternativa
                    letra={letra}
                    escolhida={escolha === letra}
                    conferido={conferido}
                    correta={gabarito === letra}
                    onEscolher={() => setEscolha(letra)}
                  />
                </li>
              ))}
            </ul>
          </>
        )}
      </div>

      {questao && (
        <footer className="alu-treino__base">
          {!conferido ? (
            <button
              type="button"
              className="alu-tecla alu-tecla--larga"
              disabled={escolha == null}
              onClick={responder}
            >
              Responder
            </button>
          ) : (
            <div
              className={`alu-treino__veredito${acertou ? ' is-certa' : ' is-errada'}`}
              // O veredito é a resposta a uma ação do aluno: sem `aria-live`
              // quem usa leitor de tela aperta "Responder" e não ouve nada.
              aria-live="polite"
            >
              <p className="alu-treino__veredito-titulo">
                {acertou ? 'Você acertou' : `A resposta era ${gabarito ?? '—'}`}
              </p>
              {/* ⚠️ Gabarito 'sugerido' é letra DEDUZIDA, não publicada pela
                  banca (0031). O cartão já avisa quando o aluno pede para ver;
                  na fila é pior calar, porque aqui a tela não mostra a letra —
                  ela declara que o aluno errou. */}
              {questao.gabaritoOrigem === 'sugerido' && (
                <p className="alu-questao__aviso">
                  Sugestão de gabarito — a banca não publicou o oficial desta prova.
                </p>
              )}
              <Resolucao questao={questao} />
              <button type="button" className="alu-tecla alu-tecla--larga" onClick={avancar}>
                {ultima ? 'Ver o resumo' : 'Próxima'}
              </button>
            </div>
          )}
        </footer>
      )}
    </div>
  );
}

// ─── Peças da tela ───────────────────────────────────────────────────────

/** A moldura mínima, para os estados que não têm fila nenhuma para mostrar. */
function Moldura({ children, onSair }: { children: ReactNode; onSair: () => void }) {
  return (
    <div className="alu-shell alu-treino">
      <header className="alu-treino__topo">
        <button type="button" className="alu-treino__icone" onClick={onSair} aria-label="Voltar">
          <Icone nome="voltar" tamanho={22} />
        </button>
      </header>
      <div className="alu-treino__corpo">{children}</div>
    </div>
  );
}

function BotaoVoltar() {
  return (
    <Link className="alu-tecla" to="/estudar">
      Voltar para Estudar
    </Link>
  );
}

/**
 * "Por que estas questões?" — a pergunta que mata a confiança numa recomendação
 * quando não tem resposta (o brief, e docs/24 §4.5).
 *
 * Fica aberto num `<details>` em vez de num modal: a resposta é curta, e quem
 * já entendeu não quer ler de novo a cada sessão.
 */
function PorQueEstas({
  origem,
  materiaDosErros,
  nomeDaMissao,
  razaoDaMissao,
  tituloDaLista,
  incluirResolvidas,
  onAlternarResolvidas,
}: {
  origem: string;
  materiaDosErros: MateriaBanco | null;
  nomeDaMissao: string | null;
  razaoDaMissao: string | null;
  tituloDaLista: string | null;
  incluirResolvidas: boolean;
  onAlternarResolvidas: () => void;
}) {
  return (
    <details className="alu-treino__porque">
      {/* A tarja vai DENTRO do `<summary>`. Fora dele ela cai no
          `::details-content`, que o navegador esconde com `content-visibility`
          enquanto o `<details>` está fechado — medido no Chrome 151:
          `checkVisibility()` devolve `false` mesmo com a tarja em
          `position: absolute`. A marca de MOCK da escolha da fila rege a tela
          inteira e sumia justamente no estado padrão. */}
      <summary className="alu-treino__porque-titulo">
        Por que estas questões?
        <TarjaFonte chave="escolhaDaFilaDeTreino" />
      </summary>

      <p className="alu-treino__porque-texto">
        {RAZAO_DA_FILA[origem] ?? 'Questões do acervo de provas do ITA e do IME.'}
      </p>

      {/* Sem tarja desde 04/09: a missão virou rota (`GET /missao/hoje`) e o
          nome que aparece aqui é o mesmo que o servidor usou para escolher as
          questões — antes o cartão dizia "Termodinâmica" e a fila entregava
          Ondas e Acústica (docs/35 §9). */}
      {origem === 'prioridade' && nomeDaMissao && (
        <p className="alu-treino__derivado">
          {nomeDaMissao}
          {razaoDaMissao ? ` — ${razaoDaMissao}` : ''}
        </p>
      )}

      {origem === 'erros' && (
        <p className="alu-treino__derivado">
          <TarjaFonte chave="meusErros" />
          {materiaDosErros
            ? `${materiaDosErros} é onde você mais erra nos simulados. Estas são questões de prova do mesmo assunto — não as suas questões do simulado, que não moram no acervo.`
            : 'Ainda não sei em que matéria você mais erra.'}
        </p>
      )}

      {origem === 'assunto' && (
        <p className="alu-treino__derivado">
          <TarjaFonte chave="importanciaDoAssunto" />
          A ordem dentro do assunto ainda não usa o seu acerto: ela cai para a matéria mais longe
          do corte.
        </p>
      )}

      {origem === 'lista' && tituloDaLista && (
        <p className="alu-treino__porque-texto">Lista “{tituloDaLista}”.</p>
      )}

      <button type="button" className="alu-treino__ligar" onClick={onAlternarResolvidas}>
        <Icone nome={incluirResolvidas ? 'cheque' : 'mais'} tamanho={16} />
        {incluirResolvidas
          ? 'Escondendo as que já resolvi'
          : 'Incluir as questões que eu já resolvi'}
      </button>
    </details>
  );
}

/** Esqueleto com a forma do conteúdo, nunca um spinner (o brief, §Estados). */
function Esqueleto() {
  return (
    <div className="alu-treino__esqueleto" aria-hidden="true">
      <span className="alu-treino__esqueleto-imagem" />
      {/* Cinco quadrados numa fileira, a forma que as alternativas têm agora:
          três linhas empilhadas anunciariam um layout que não vem mais. */}
      <div className="alu-treino__esqueleto-fileira">
        <span className="alu-treino__esqueleto-linha" />
        <span className="alu-treino__esqueleto-linha" />
        <span className="alu-treino__esqueleto-linha" />
        <span className="alu-treino__esqueleto-linha" />
        <span className="alu-treino__esqueleto-linha" />
      </div>
    </div>
  );
}

/**
 * A fila vazia, e ela tem TRÊS causas diferentes que pedem três frases
 * diferentes. Um "nada encontrado" genérico aqui deixa o aluno sem saber se o
 * acervo não tem o assunto, se ele já resolveu tudo, ou se só sobrou 2ª fase.
 */
function FilaVazia({
  origem,
  bruto,
  incluirResolvidas,
  semAssunto,
  semRecorte,
  onIncluirResolvidas,
  onSoltarAssunto,
}: {
  origem: string;
  bruto: QuestaoVestibular[];
  incluirResolvidas: boolean;
  semAssunto: boolean;
  semRecorte: boolean;
  onIncluirResolvidas: () => void;
  onSoltarAssunto: () => void;
}) {
  const respondiveis = bruto.filter(respondivel);
  const todasResolvidas = respondiveis.length > 0 && respondiveis.every((q) => q.resolvida === true);
  const soDissertativas = bruto.length > 0 && respondiveis.length === 0;

  if (semRecorte && origem === 'lista') {
    return (
      <div className="alu-treino__aviso">
        <p className="alu-vazio">
          Este link não diz qual lista treinar. Abra a lista que você montou e comece por ela.
        </p>
        <Link className="alu-tecla" to="/estudar/listas">
          Ver minhas listas
        </Link>
      </div>
    );
  }

  if (semRecorte) {
    return (
      <div className="alu-treino__aviso">
        <p className="alu-vazio">
          {origem === 'assunto'
            ? 'Para abrir um assunto eu preciso saber de qual matéria ele é: o mesmo código existe nas três e significa coisa diferente em cada uma. Escolha o assunto pela tela “O que mais cai”.'
            : 'Ainda não tenho o que montar aqui. Escolha um assunto e a fila aparece.'}
        </p>
        <Link className="alu-tecla" to="/estudar/assuntos">
          Ver o que mais cai
        </Link>
      </div>
    );
  }

  if (todasResolvidas && !incluirResolvidas) {
    return (
      <div className="alu-treino__aviso">
        <p className="alu-vazio">
          Você já resolveu todas as {respondiveis.length} questões deste recorte. Dá para refazer
          as mesmas, ou abrir outro assunto.
        </p>
        <button type="button" className="alu-tecla" onClick={onIncluirResolvidas}>
          Refazer as que já resolvi
        </button>
      </div>
    );
  }

  if (soDissertativas) {
    return (
      <div className="alu-treino__aviso">
        <p className="alu-vazio">
          As questões que sobraram aqui são todas de 2ª fase: elas não têm alternativa nem letra de
          gabarito, por natureza, então não dá para respondê-las numa fila. Elas continuam no acervo
          para estudar pela resolução.
        </p>
        <Link className="alu-tecla" to="/estudar">
          Escolher outro assunto
        </Link>
      </div>
    );
  }

  return (
    <div className="alu-treino__aviso">
      <p className="alu-vazio">
        O acervo não tem questão objetiva deste recorte. Ele é feito de provas passadas do ITA e
        do IME, e nem todo assunto do edital já caiu numa delas.
      </p>
      {!semAssunto && origem !== 'lista' && (
        <button type="button" className="alu-tecla" onClick={onSoltarAssunto}>
          Treinar a matéria inteira
        </button>
      )}
      <Link className="alu-tecla alu-tecla--fantasma" to="/estudar">
        Voltar para Estudar
      </Link>
    </div>
  );
}

/**
 * Classificação incerta se declara — e na sessão isso importa MAIS que no
 * cartão: uma questão classificada errado põe o aluno treinando o assunto
 * errado durante doze questões seguidas (docs/28 §6).
 */
function AvisoDeClassificacao({ questao }: { questao: QuestaoVestibular }) {
  const incerto = questao.topicos.some(
    (t) => t.confianca === 'media' || t.confianca === 'baixa',
  );
  if (!incerto) return null;
  return (
    <p className="alu-treino__incerto">
      <span className="alu-questao__ponto-alerta" aria-hidden="true" />
      Classificação incerta: esta questão pode ser de outro assunto.
    </p>
  );
}

/** A imagem é o conteúdo — e sem `max-width: 100%` o PNG estoura a viewport a
 *  360px. Quem garante isso é `.alu-questao__imagem` (docs/28 §6). */
function Enunciado({ questao }: { questao: QuestaoVestibular }) {
  const [falhou, setFalhou] = useState(false);
  // 'visao' é página escaneada lida por um agente: ali o TEXTO é o principal.
  const mostrarImagem =
    questao.extraidoPor !== 'visao' && questao.usaImagemNoRender && !!questao.imagemUrl && !falhou;

  if (!mostrarImagem) {
    return <p className="alu-questao__texto">{questao.enunciadoMd}</p>;
  }

  return (
    <img
      className="alu-questao__imagem alu-treino__imagem"
      src={questao.imagemUrl ?? ''}
      alt={`Enunciado — ${questao.vestibular} ${questao.ano}, questão ${questao.numero}`}
      decoding="async"
      onError={() => setFalhou(true)}
    />
  );
}

/**
 * Uma alternativa: o quadrado da letra, e só.
 *
 * Leva a tecla de 4px porque É tocável — e todo o resto da tela é chapado, que
 * é o que faz a tecla continuar significando "aperte aqui" (docs/24 §7.1).
 *
 * Os quatro estados, sem cor nova: neutro na superfície; escolhida VAZADA com
 * fio DADO; depois de conferida a correta fica PREENCHIDA na cor DADO e a que
 * enganou fica VAZADA com fio ALERTA (o brief). Vazio é vazado.
 *
 * ⚠️ O `aria-label` não é enfeite: um botão cujo conteúdo é a letra "A" é
 * anunciado como "A", e quem usa leitor de tela não tem a imagem para deduzir
 * do que se trata.
 */
function Alternativa({
  letra,
  escolhida,
  conferido,
  correta,
  onEscolher,
}: {
  letra: string;
  escolhida: boolean;
  conferido: boolean;
  correta: boolean;
  onEscolher: () => void;
}) {
  const classes = ['alu-alternativa'];
  if (!conferido && escolhida) classes.push('is-escolhida');
  if (conferido && correta) classes.push('is-correta');
  if (conferido && escolhida && !correta) classes.push('is-enganou');

  return (
    <button
      type="button"
      className={classes.join(' ')}
      aria-pressed={escolhida}
      aria-label={`Alternativa ${letra}`}
      disabled={conferido}
      onClick={onEscolher}
    >
      <span className="alu-alternativa__letra">{letra}</span>
    </button>
  );
}

/**
 * De quem é a resolução, LIDA DO CAMPO `resolucaoOrigem` — que já vem no schema
 * e é fonte real (`origemDaResolucao`).
 *
 * Deduzir a origem de qual campo está preenchido só funciona enquanto
 * `resolucaoUrl` ⇔ 'ari' e `resolucaoMd` ⇔ 'sugerida' for verdade no banco: a
 * primeira questão com os dois rotularia texto de LLM como "professor do Ari",
 * que é exatamente o que docs/29 §D.1 existe para impedir. Um aluno de 17 anos
 * não tem repertório para desconfiar de uma derivação bem diagramada (docs/27
 * §10). O campo manda; o palpite é a rede de segurança da linha antiga, com
 * `resolucaoOrigem` nulo.
 */
function marcaDaOrigem(questao: QuestaoVestibular) {
  const daCasa = questao.resolucaoOrigem
    ? questao.resolucaoOrigem === 'ari'
    : !!questao.resolucaoUrl;
  return daCasa
    ? { daCasa, rotulo: 'professor do Ari', classe: 'alu-questao__origem-resolucao--ari' }
    : { daCasa, rotulo: 'gerada por IA', classe: 'alu-questao__origem-resolucao--ia' };
}

/** A resolução com a marca de quem a escreveu — nunca uma sem a outra. */
function Resolucao({ questao }: { questao: QuestaoVestibular }) {
  const [aberta, setAberta] = useState(false);
  const origem = marcaDaOrigem(questao);

  if (questao.resolucaoUrl) {
    return (
      <a
        className="alu-questao__resolucao"
        href={questao.resolucaoUrl}
        target="_blank"
        rel="noopener noreferrer"
      >
        <Icone nome="externo" tamanho={15} />
        Ver a resolução
        <span className={`alu-questao__origem-resolucao ${origem.classe}`}>{origem.rotulo}</span>
      </a>
    );
  }

  if (questao.resolucaoMd) {
    return (
      <div className="alu-questao__resolucao-escrita">
        <button
          type="button"
          className="alu-questao__resolucao"
          aria-expanded={aberta}
          onClick={() => setAberta((v) => !v)}
        >
          <Icone nome="documento" tamanho={15} />
          {aberta ? 'Esconder a resolução' : 'Ver a resolução'}
          <span className={`alu-questao__origem-resolucao ${origem.classe}`}>{origem.rotulo}</span>
        </button>
        {aberta && (
          <div className="alu-questao__resolucao-corpo">
            <Markdown texto={questao.resolucaoMd} variante="resolucao" />
            {!origem.daCasa && (
              <p className="alu-questao__aviso">
                Esta resolução foi gerada automaticamente e não passou por um professor. Confira as
                contas antes de confiar nela.
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  return <p className="alu-questao__aviso">Esta questão ainda não tem resolução escrita.</p>;
}
