import { useState } from 'react';

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

  const estudo = useAtualizarEstudo();

  const ehAluno = perfil === 'aluno';
  const resolvida = questao.resolvida === true;
  const rotulo = rotuloQuestao(questao);
  const dissertativa = ehDissertativa(questao);
  // A imagem vive num bucket S3 sem cópia local (docs/22 §0.2, risco 6) e a CSP
  // de produção só libera `img-src 'self' data: blob:` (infra/vps/nginx.conf).
  // Quando ela não vem, o texto extraído do PDF é melhor que um retângulo vazio.
  const mostrarImagem = questao.usaImagemNoRender && !!questao.imagemUrl && !imagemFalhou;

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
          <img
            className="banco-questao__imagem"
            src={questao.imagemUrl ?? ''}
            alt={`Enunciado da questão — ${rotulo}`}
            loading="lazy"
            decoding="async"
            onError={() => setImagemFalhou(true)}
          />
        ) : (
          // Texto cru, sem render de Markdown: não há biblioteca de Markdown no
          // projeto e o enunciado ainda traz sujeira de OCR (docs/22 §8, risco 5).
          <p className="banco-questao__texto">{questao.enunciadoMd}</p>
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
            // Uma das 40 sem classificação: aparece dizendo o que é, em vez de
            // parecer uma questão sem assunto por acaso (docs/22 §8, risco 3).
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
        {questao.resolucaoUrl && (
          <a
            className="banco-questao__gabarito"
            href={questao.resolucaoUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            Ver resolução ↗
          </a>
        )}
      </>
    );
  }

  return (
    <button
      type="button"
      // Mesmo elemento nos dois estados de propósito: trocar por um <div> ao
      // revelar tiraria o foco do teclado do cartão que a pessoa está lendo.
      className={`banco-questao__gabarito${visivel ? ' banco-questao__gabarito--revelado' : ''}`}
      aria-expanded={visivel}
      onClick={onAlternar}
    >
      {visivel ? (
        <span className="banco-questao__gabarito-letra">{questao.gabarito}</span>
      ) : (
        'ver gabarito'
      )}
    </button>
  );
}
