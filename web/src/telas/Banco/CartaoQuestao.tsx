import { useState } from 'react';

import { BotaoInfo } from '../../componentes/ui/BotaoInfo';
import { Markdown } from '../../componentes/ui/Markdown';
import { ehDissertativa, rotuloQuestao, temGabarito } from '../../dominio/banco';
import { useAtualizarEstudo } from '../../hooks/banco';
import type { QuestaoVestibular, TopicoDaQuestao } from '../../tipos/banco';
import type { PerfilBanco } from './Banco';

// O cartão de questão — a peça crítica no celular (docs/22 §3.5).
//
// O enunciado é um PNG de largura variável: sem `max-width: 100%`, ele estoura
// a viewport a 360px. Quem garante isso é `.banco-questao__imagem`; aqui o
// cuidado é só não trocar a classe.
//
// ⚠️ `QuestaoVestibular` é questão de PROVA PASSADA. A questão de simulado-Quiz
// do Canvas é outra coisa e mora em `tipos/dominio.ts` (docs/22 §8, risco 1).

interface Props {
  questao: QuestaoVestibular;
  perfil: PerfilBanco;
  /** A questão já está na lista de trabalho — o botão vira "tirar da lista". */
  naLista?: boolean;
  onAlternarNaLista?: (questaoId: string) => void;
  /** Rótulo da lista de trabalho, para o botão dizer onde a questão vai cair. */
  tituloListaAtiva?: string | null;
}

/** Média e baixa se declaram (4 das 934): classificação errada tem que ser diagnosticável (docs/22 §7.5). */
function incerto(topico: TopicoDaQuestao): boolean {
  return topico.confianca === 'media' || topico.confianca === 'baixa';
}

export function CartaoQuestao({
  questao,
  perfil,
  naLista = false,
  onAlternarNaLista,
  tituloListaAtiva,
}: Props) {
  const [gabaritoVisivel, setGabaritoVisivel] = useState(false);
  const [anotando, setAnotando] = useState(false);
  // Rascunho local, gravado no blur. Não se ressincroniza com a prop: quem
  // reescreve `anotacao` é a própria gravação daqui, e um efeito de sincronia
  // apagaria o que o aluno está digitando quando outra invalidação chegasse.
  const [rascunho, setRascunho] = useState(questao.anotacao ?? '');
  const [imagemFalhou, setImagemFalhou] = useState(false);
  const [imagemOriginalAberta, setImagemOriginalAberta] = useState(false);

  const estudo = useAtualizarEstudo();

  const ehAluno = perfil === 'aluno';
  const resolvida = questao.resolvida === true;
  const rotulo = rotuloQuestao(questao);
  const dissertativa = ehDissertativa(questao);
  // Página escaneada lida por visão (docs/22, piloto ITA 1973): o OCR não dá
  // conta de datilografia antiga, e quem transcreveu foi um agente lendo a
  // imagem — a transcrição sai mais legível que o recorte. Aqui o texto é o
  // principal e a imagem vira consulta opcional, o inverso do caso comum.
  const ehVisao = questao.extraidoPor === 'visao';
  // A imagem vive num bucket S3 sem cópia local (docs/22 §0.2, risco 6) e a CSP
  // de produção só libera `img-src 'self' data: blob:` (infra/vps/nginx.conf).
  // Quando ela não vem, o texto extraído do PDF é melhor que um retângulo vazio.
  const mostrarImagem = !ehVisao && questao.usaImagemNoRender && !!questao.imagemUrl && !imagemFalhou;
  const podeAbrirImagemOriginal = ehVisao && !!questao.imagemUrl;
  // Modo página (docs/24): a imagem é a página inteira do PDF, não um recorte
  // fino da questão — pode trazer questão vizinha junto. Card só encolhe pra
  // ~330px, então uma A4 inteira em 200dpi fica pequena demais pra ler fórmula
  // sem zoom; o link abre o PNG original (pinch-zoom nativo do navegador).
  const ehPagina = questao.extraidoPor === 'pagina';

  function salvarAnotacao() {
    const texto = rascunho.trim();
    if (texto === (questao.anotacao ?? '')) return;
    estudo.mutate({ questaoId: questao.id, remendo: { anotacao: texto || null } });
  }

  return (
    <article className="banco-questao">
      <header className="banco-questao__topo">
        <span
          className={`banco-questao__selo${questao.vestibular === 'IME' ? ' banco-questao__selo--ime' : ''}`}
        >
          {questao.vestibular}
        </span>
        <span className="banco-questao__referencia">{rotulo}</span>

        <div className="banco-questao__acoes">
          {ehAluno && (
            <>
              <button
                type="button"
                className={`banco-questao__acao${resolvida ? ' is-active' : ''}`}
                aria-pressed={resolvida}
                disabled={estudo.isPending}
                onClick={() =>
                  estudo.mutate({ questaoId: questao.id, remendo: { resolvida: !resolvida } })
                }
              >
                {resolvida ? '✓ Resolvida' : 'Marcar resolvida'}
              </button>
              <button
                type="button"
                className={`banco-questao__acao${questao.anotacao ? ' is-active' : ''}`}
                aria-expanded={anotando}
                onClick={() => setAnotando((v) => !v)}
              >
                {questao.anotacao ? 'Anotação' : 'Anotar'}
              </button>
            </>
          )}

          {onAlternarNaLista && (
            <button
              type="button"
              className={`banco-questao__acao${naLista ? ' is-active' : ''}`}
              aria-pressed={naLista}
              title={tituloListaAtiva ? `Lista: ${tituloListaAtiva}` : 'Cria a lista na primeira questão'}
              onClick={() => onAlternarNaLista(questao.id)}
            >
              {naLista ? '✓ Na lista' : '+ Lista'}
            </button>
          )}
        </div>
      </header>

      <div className="banco-questao__corpo">
        {mostrarImagem ? (
          <>
            {ehPagina && (
              <p className="banco-questao__aviso-imagem">
                Localize a <strong>Questão {questao.numero}</strong>
                <BotaoInfo
                  rotulo="Sobre esta imagem"
                  texto="Página original da prova. Pode trazer outras questões junto; toque na imagem para abrir em tamanho real."
                />
              </p>
            )}
            <a href={questao.imagemUrl ?? ''} target="_blank" rel="noopener noreferrer">
              <img
                className="banco-questao__imagem"
                src={questao.imagemUrl ?? ''}
                alt={`Enunciado da questão — ${rotulo}`}
                loading="lazy"
                decoding="async"
                onError={() => setImagemFalhou(true)}
              />
            </a>
          </>
        ) : (
          // As 63 questões sem imagem de página caem aqui. O Markdown não
          // limpa a sujeira de OCR que o enunciado ainda traz (docs/22 §8,
          // risco 5) — só impede que a fórmula chegue crua junto com ela.
          <div className="banco-questao__texto">
            <Markdown texto={questao.enunciadoMd} />
          </div>
        )}

        {!mostrarImagem && questao.alternativas && (
          <ul className="banco-questao__alternativas">
            {Object.entries(questao.alternativas).map(([letra, texto]) => (
              <li key={letra} className="banco-questao__alternativa">
                <span className="banco-questao__letra">{letra}</span>
                <span>{texto}</span>
              </li>
            ))}
          </ul>
        )}

        {podeAbrirImagemOriginal && (
          <div className="banco-questao__imagem-original">
            <button
              type="button"
              className="banco-questao__acao"
              aria-expanded={imagemOriginalAberta}
              onClick={() => setImagemOriginalAberta((v) => !v)}
            >
              {imagemOriginalAberta ? 'Ocultar imagem da questão' : 'Abrir imagem da questão'}
            </button>
            {imagemOriginalAberta && !imagemFalhou && (
              <>
                <img
                  className="banco-questao__imagem"
                  src={questao.imagemUrl ?? ''}
                  alt={`Página original digitalizada — ${rotulo}`}
                  loading="lazy"
                  decoding="async"
                  onError={() => setImagemFalhou(true)}
                />
                {/* A digitalização é antiga e às vezes perde nitidez — a transcrição
                    acima já passou por conferência, mas vale contrastar quando algo
                    parecer estranho. */}
                <p className="banco-questao__aviso-imagem">
                  Página digitalizada, de resolução mais baixa — leia o enunciado
                  acima e, se algum trecho parecer estranho, confira aqui a imagem
                  original.
                </p>
              </>
            )}
          </div>
        )}

        <Gabarito
          questao={questao}
          dissertativa={dissertativa}
          visivel={gabaritoVisivel}
          onAlternar={() => setGabaritoVisivel((v) => !v)}
        />

        <div className="banco-questao__topicos">
          {questao.topicos.map((topico) => (
            <span
              key={topico.codigo}
              className={`banco-questao__topico${incerto(topico) ? ' banco-questao__topico--incerto' : ''}`}
              title={topico.observacao ?? `${topico.blocoNome} · confiança ${topico.confianca ?? '—'}`}
            >
              {`${topico.codigo} · ${topico.nome}`}
            </span>
          ))}
          {questao.topicos.length === 0 && (
            // Questão ainda sem classificação: aparece dizendo o que é, em vez
            // de parecer uma questão sem assunto por acaso (docs/22 §8, risco
            // 3). Sem número: eram 40, viraram 44 e a faixa de classificação
            // de docs/35 §3 as leva a zero — quantas são se conta no banco, e
            // nunca aqui (docs/35 §3.3).
            <span className="banco-questao__topico banco-questao__topico--incerto">
              Sem assunto classificado
            </span>
          )}
        </div>

        {ehAluno && anotando && (
          <textarea
            className="banco-questao__anotacao"
            value={rascunho}
            placeholder="Anotação pessoal sobre esta questão…"
            aria-label={`Anotação sobre ${rotulo}`}
            onChange={(ev) => setRascunho(ev.target.value)}
            onBlur={salvarAnotacao}
          />
        )}
      </div>
    </article>
  );
}

/**
 * O link para a resolução comentada nos sites do Ari.
 *
 * Vale para questão COM e SEM gabarito: saber a letra não é saber resolver, e
 * era essa a razão de o aluno abrir o banco. Antes só aparecia onde não havia
 * gabarito, o que escondia o link em 493 das 934.
 *
 * Sem link em 210 (2ª fase do IME, que o Ari não comenta) e em toda questão
 * anterior a 2019 — o Ari só publica resolução comentada a partir daquele ano
 * (banco/resolucao.py). É para esse acervo que existe `ResolucaoSugerida`.
 */
function LinkResolucao({ url }: { url: string }) {
  return (
    <a
      className="banco-questao__gabarito banco-questao__resolucao"
      href={url}
      target="_blank"
      rel="noopener noreferrer"
    >
      Ver resolução ↗
    </a>
  );
}

/**
 * A resolução escrita no próprio cartão — o substituto do link do Ari onde ele
 * não existe (todo o acervo anterior a 2019). Fica atrás de um clique como o
 * gabarito, com o mesmo motivo: a resposta não pode aparecer antes de o aluno
 * decidir olhar.
 *
 * Desde 01/09 passa pelo `Markdown` compartilhado, com a fórmula renderizada
 * pelo KaTeX. Antes o texto ia cru para dentro de um `<p>`, e uma resolução de
 * física chegava ao coordenador como `$q=N\dfrac{\Delta\Phi}{R}$` — a dívida
 * que `docs/22 §8, risco 5` registrava.
 */
function ResolucaoSugerida({ md }: { md: string }) {
  const [aberta, setAberta] = useState(false);
  return (
    <div className="banco-questao__resolucao-sugerida">
      <button
        type="button"
        className="banco-questao__gabarito banco-questao__resolucao"
        aria-expanded={aberta}
        onClick={() => setAberta((v) => !v)}
      >
        {aberta ? 'Ocultar resolução' : 'Sugestão de resolução'}
      </button>
      {aberta && (
        <div className="banco-questao__resolucao-corpo">
          <Markdown texto={md} variante="resolucao" />
          <p className="banco-questao__resolucao-aviso">
            Sugestão de resolução — não é a resolução oficial da banca.
          </p>
        </div>
      )}
    </div>
  );
}

/** Escolhe entre o link do Ari e a resolução escrita — nunca as duas (CHECK da 0031). */
function Resolucao({ questao }: { questao: QuestaoVestibular }) {
  if (questao.resolucaoUrl) return <LinkResolucao url={questao.resolucaoUrl} />;
  if (questao.resolucaoMd) return <ResolucaoSugerida md={questao.resolucaoMd} />;
  return null;
}

/**
 * O gabarito fica atrás de um clique — é o que separa "estudar" de "conferir".
 *
 * 469 das 934 não têm letra, quase todas por serem dissertativas de 2ª fase: é
 * o esperado, não defeito. Onde não há o que revelar, o cartão não pode
 * oferecer "ver gabarito" — o lugar da resposta ali é `resolucaoUrl`
 * (docs/22 §8, risco 4).
 */
function Gabarito({
  questao,
  dissertativa,
  visivel,
  onAlternar,
}: {
  questao: QuestaoVestibular;
  dissertativa: boolean;
  visivel: boolean;
  onAlternar: () => void;
}) {
  if (!temGabarito(questao)) {
    return (
      <>
        <span className="banco-questao__gabarito banco-questao__gabarito--indisponivel">
          {dissertativa ? 'Discursiva — sem letra de gabarito' : 'Sem gabarito importado'}
        </span>
        {/* A resolução ocupa o lugar do gabarito, e por isso veste a mesma
            classe: `.banco-questao__gabarito` tem `align-self: flex-start`, o
            que a impede de esticar na coluna do corpo do cartão. */}
        <Resolucao questao={questao} />
      </>
    );
  }

  // 'sugerido' só chega aqui com confiança alta — é o próprio backend que não
  // grava a letra abaixo disso (migration 0031, calibrado em 220 questões:
  // 99,5% de acerto na faixa alta). Aqui só resta decidir a cor: âmbar, não
  // verde — verde é "confirmado" neste projeto, e uma sugestão pintada de
  // verde diria ao aluno que a banca respondeu isso.
  const sugerido = questao.gabaritoOrigem === 'sugerido';

  return (
    <>
      <button
        type="button"
        // Mesmo elemento nos dois estados de propósito: trocar por um <div> ao
        // revelar tiraria o foco do teclado do cartão que a pessoa está lendo.
        className={`banco-questao__gabarito${visivel ? ' banco-questao__gabarito--revelado' : ''}${sugerido ? ' banco-questao__gabarito--sugerido' : ''}`}
        aria-expanded={visivel}
        onClick={onAlternar}
      >
        {visivel ? (
          <span className="banco-questao__gabarito-letra">{questao.gabarito}</span>
        ) : sugerido ? (
          'sugestão de gabarito'
        ) : (
          'ver gabarito'
        )}
      </button>
      {visivel && sugerido && (
        <span className="banco-questao__gabarito-aviso">
          Sugestão de gabarito — a banca não publicou o oficial desta prova.
        </span>
      )}
      <Resolucao questao={questao} />
    </>
  );
}
