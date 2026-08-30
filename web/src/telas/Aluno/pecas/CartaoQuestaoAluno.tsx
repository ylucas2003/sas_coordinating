import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ehDissertativa, temGabarito } from '../../../dominio/banco';
import { useAtualizarEstudo } from '../../../dados/aluno';
import type { QuestaoVestibular, TopicoDaQuestao } from '../../../dados/aluno';
import { Icone } from './Icone';

// O cartão de questão no casco do aluno.
//
// É um FORK DE APRESENTAÇÃO do `telas/Banco/CartaoQuestao.tsx`, não de dado:
// consome os mesmos tipos e a mesma mutação (`useAtualizarEstudo`), e não toca
// em `telas/Banco/`, que serve a coordenação e continua exatamente como está.
// O que muda é a linguagem visual — o desenho do aluno é jogo, o da coordenação
// é ferramenta de montar prova (docs/28 §4).
//
// ⚠️ A IMAGEM É O CONTEÚDO. O enunciado é um PNG de largura variável; sem
// `max-width: 100%` ele estoura a viewport a 360px (docs/28 §6). Quem garante
// isso é `.alu-questao__imagem`; aqui o cuidado é só não trocar a classe.

/** Média e baixa se declaram: classificação errada põe o aluno treinando o
 *  assunto errado, e numa sessão de treino isso importa mais (docs/28 §6). */
function incerto(topico: TopicoDaQuestao): boolean {
  return topico.confianca === 'media' || topico.confianca === 'baixa';
}

interface Props {
  questao: QuestaoVestibular;
  /** Cabeçalho compacto e sem ações — dentro da fila de treino. */
  enxuto?: boolean;
  naLista?: boolean;
  onAlternarNaLista?: (questaoId: string) => void;
  /** Some com o link "abrir em tela cheia" quando já se está nela. */
  semLinkParaFicha?: boolean;
}

export function CartaoQuestaoAluno({
  questao,
  enxuto = false,
  naLista = false,
  onAlternarNaLista,
  semLinkParaFicha = false,
}: Props) {
  const [gabaritoVisivel, setGabaritoVisivel] = useState(false);
  const [anotando, setAnotando] = useState(false);
  // Rascunho local, gravado no blur. Não se ressincroniza com a prop: quem
  // reescreve `anotacao` é a própria gravação daqui, e um efeito de sincronia
  // apagaria o que o aluno está digitando quando outra invalidação chegasse.
  const [rascunho, setRascunho] = useState(questao.anotacao ?? '');
  const [imagemFalhou, setImagemFalhou] = useState(false);

  const estudo = useAtualizarEstudo();

  const resolvida = questao.resolvida === true;
  const dissertativa = ehDissertativa(questao);
  // 'visao' é página escaneada lida por um agente: ali o TEXTO é o principal e
  // a imagem vira consulta, o inverso do caso comum (docs/22).
  const ehVisao = questao.extraidoPor === 'visao';
  const mostrarImagem =
    !ehVisao && questao.usaImagemNoRender && !!questao.imagemUrl && !imagemFalhou;

  function salvarAnotacao() {
    const texto = rascunho.trim();
    if (texto === (questao.anotacao ?? '')) return;
    estudo.mutate({ questaoId: questao.id, remendo: { anotacao: texto || null } });
  }

  return (
    <article className="alu-questao">
      <header className="alu-questao__topo">
        <span className="alu-olho alu-questao__origem">
          {`${questao.vestibular} · ${questao.ano} · Fase ${questao.fase} · Q${questao.numero}`}
        </span>
        {dissertativa && <span className="alu-questao__selo">Dissertativa</span>}
        {!semLinkParaFicha && (
          <Link className="alu-questao__abrir" to={`/questao/${questao.id}`}>
            <Icone nome="externo" tamanho={16} />
            <span className="alu-so-leitor">Abrir em tela cheia</span>
          </Link>
        )}
      </header>

      {mostrarImagem ? (
        <img
          className="alu-questao__imagem"
          src={questao.imagemUrl ?? ''}
          alt={`Enunciado — ${questao.vestibular} ${questao.ano}, questão ${questao.numero}`}
          loading="lazy"
          decoding="async"
          onError={() => setImagemFalhou(true)}
        />
      ) : (
        // Sem render de Markdown: o projeto não tem um, e o enunciado ainda traz
        // sujeira de OCR. Fórmula em LaTeX aparece crua — dívida conhecida.
        <p className="alu-questao__texto">{questao.enunciadoMd}</p>
      )}

      <Topicos topicos={questao.topicos} />

      {!dissertativa && temGabarito(questao) ? (
        <Gabarito
          questao={questao}
          visivel={gabaritoVisivel}
          onAlternar={() => setGabaritoVisivel((v) => !v)}
        />
      ) : (
        <>
          <p className="alu-questao__sem-gabarito">
            {dissertativa
              ? 'Questão de 2ª fase: não tem alternativa nem letra de gabarito. O que existe é a resolução.'
              : 'Sem gabarito importado para esta questão.'}
          </p>
          <Resolucao questao={questao} />
        </>
      )}

      {!enxuto && (
        <footer className="alu-questao__acoes">
          <button
            type="button"
            className={`alu-questao__acao${resolvida ? ' is-ativa' : ''}`}
            aria-pressed={resolvida}
            disabled={estudo.isPending}
            onClick={() => estudo.mutate({ questaoId: questao.id, remendo: { resolvida: !resolvida } })}
          >
            <Icone nome="cheque" tamanho={17} />
            {resolvida ? 'Resolvida' : 'Marcar resolvida'}
          </button>

          <button
            type="button"
            className={`alu-questao__acao${questao.anotacao ? ' is-ativa' : ''}`}
            aria-expanded={anotando}
            onClick={() => setAnotando((v) => !v)}
          >
            <Icone nome="anotar" tamanho={17} />
            {questao.anotacao ? 'Anotação' : 'Anotar'}
          </button>

          {onAlternarNaLista && (
            <button
              type="button"
              className={`alu-questao__acao${naLista ? ' is-ativa' : ''}`}
              aria-pressed={naLista}
              onClick={() => onAlternarNaLista(questao.id)}
            >
              <Icone nome={naLista ? 'cheque' : 'mais'} tamanho={17} />
              {naLista ? 'Na lista' : 'Lista'}
            </button>
          )}
        </footer>
      )}

      {anotando && (
        <textarea
          className="alu-campo alu-questao__anotacao"
          value={rascunho}
          placeholder="Anote o que te travou nesta questão…"
          aria-label="Anotação sobre esta questão"
          onChange={(ev) => setRascunho(ev.target.value)}
          onBlur={salvarAnotacao}
        />
      )}
    </article>
  );
}

function Topicos({ topicos }: { topicos: TopicoDaQuestao[] }) {
  if (!topicos.length) {
    // Sumir com as não classificadas daria ao aluno um recorte incompleto sem
    // aviso — é a mesma regra da cobertura de matérias (docs/22 §8, docs/24 §3.3).
    return (
      <div className="alu-questao__topicos">
        <span className="alu-questao__topico alu-questao__topico--incerto">
          Sem assunto classificado
        </span>
      </div>
    );
  }

  return (
    <div className="alu-questao__topicos">
      {topicos.map((t) => (
        <span
          key={t.codigo}
          className={`alu-questao__topico${incerto(t) ? ' alu-questao__topico--incerto' : ''}`}
          title={t.observacao ?? `${t.blocoNome} · confiança ${t.confianca ?? '—'}`}
        >
          {incerto(t) && <span className="alu-questao__ponto-alerta" aria-hidden="true" />}
          {t.nome}
          {incerto(t) && <em className="alu-questao__incerto-rotulo">classificação incerta</em>}
        </span>
      ))}
    </div>
  );
}

function Gabarito({
  questao,
  visivel,
  onAlternar,
}: {
  questao: QuestaoVestibular;
  visivel: boolean;
  onAlternar: () => void;
}) {
  // 'sugerido' só chega aqui com confiança alta — o backend não grava a letra
  // abaixo disso (0031). O que resta é dizer que é sugestão, e não pintar de
  // "confirmado" o que a banca não publicou.
  const sugerido = questao.gabaritoOrigem === 'sugerido';

  return (
    <div className="alu-questao__gabarito">
      <button
        type="button"
        className={`alu-tecla alu-tecla--fantasma alu-tecla--pequena${visivel ? ' is-revelado' : ''}`}
        aria-expanded={visivel}
        onClick={onAlternar}
      >
        {visivel ? 'Esconder gabarito' : 'Ver gabarito'}
      </button>

      {visivel && (
        <div className="alu-questao__resposta">
          <span className="alu-magnitude alu-questao__letra">{questao.gabarito}</span>
          {sugerido && (
            <span className="alu-questao__aviso">
              Sugestão de gabarito — a banca não publicou o oficial desta prova.
            </span>
          )}
          <Resolucao questao={questao} />
        </div>
      )}
    </div>
  );
}

/**
 * A resolução, e A ORIGEM DELA.
 *
 * ⚠️ É o achado mais desconfortável de docs/29 §D.1: `resolucaoUrl` cobre 2019
 * em diante e aponta para os sites do próprio Ari — resolução de PROFESSOR. O
 * acervo histórico usa `resolucaoMd`, que foi GERADO PELO PIPELINE COM LLM. Sem
 * a marca, o aluno lê uma resolução de IA achando que é do professor, e um
 * aluno de 17 anos não tem repertório para desconfiar de uma derivação bem
 * diagramada (docs/27 §10).
 *
 * ⚠️ A origem vem de `resolucaoOrigem`, o CAMPO — nunca deduzida de qual dos
 * dois textos veio preenchido. A dedução acerta hoje porque o CHECK da 0031
 * garante que só um existe, mas ela é um palpite sobre a coisa mais delicada da
 * tela: bastaria uma resolução escrita passar a ter URL para o rótulo mentir.
 * Quando o campo vem `null`, a tela diz "origem não registrada" em vez de
 * escolher um dos dois — não saber é uma resposta, chutar não é.
 *
 * O link externo aqui NÃO contradiz a regra "sem link externo" de docs/27 §9: a
 * URL vem do BANCO — dado nosso, `*.aridesa.com.br` — e não do modelo. O Tio Léo
 * continua proibido de escrever link.
 */
function Resolucao({ questao }: { questao: QuestaoVestibular }) {
  const [aberta, setAberta] = useState(false);
  const origem = questao.resolucaoOrigem;

  const etiqueta =
    origem === 'ari' ? (
      <span className="alu-questao__origem-resolucao alu-questao__origem-resolucao--ari">
        professor do Ari
      </span>
    ) : origem === 'sugerida' ? (
      <span className="alu-questao__origem-resolucao alu-questao__origem-resolucao--ia">
        gerada por IA
      </span>
    ) : (
      <span className="alu-questao__origem-resolucao alu-questao__origem-resolucao--ia">
        origem não registrada
      </span>
    );

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
        {etiqueta}
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
          {etiqueta}
        </button>
        {aberta && (
          <div className="alu-questao__resolucao-corpo">
            <p>{questao.resolucaoMd}</p>
            {origem !== 'ari' && (
              <p className="alu-questao__aviso">
                Esta resolução foi gerada automaticamente e não passou por um professor.
                Confira as contas antes de confiar nela.
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  return <p className="alu-questao__sem-gabarito">Esta questão ainda não tem resolução.</p>;
}
