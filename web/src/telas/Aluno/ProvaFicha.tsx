import { NavLink, useParams } from 'react-router-dom';

import {
  type GruposComparacao,
  type QuestaoDoAluno,
  useQuestoesDoSimulado,
  useSimulado,
} from '../../dados/aluno';
import { Bloco } from './pecas/Bloco';
import { FichaXp, Icone } from './pecas/Icone';
import { fmt, fmtDataLonga, fmtDelta, fmtDuracao, fmtInteiro } from './pecas/formato';

// A FICHA DE UM SIMULADO — a nota, contra quem, e questão por questão.
//
// Duas fontes, as duas REAIS: `/me/simulado/{id}` e `/me/simulado/{id}/questoes`.
//
// ⚠️ Havia uma terceira, e ela SAIU em 04/09 (docs/35 §8b): o botão "Abrir a
// prova" pedia uma URL assinada de vida curta em `/me/simulado/{id}/arquivo` e
// abria o PDF em aba nova. O pedido foi tirar o acesso do aluno à prova, e a
// ROTA saiu junto com o botão — porta fechada é melhor que porta sem maçaneta,
// ainda mais neste projeto, que já teve uma vulnerabilidade nascida de token de
// download (PR #7).
//
// ⚠️ A rota das questões distingue DOIS silêncios diferentes, e juntá-los num
// "sem dados" apagaria a informação mais útil: `temGabarito: false` é o simulado
// que não foi aplicado como quiz — nunca vai ter detalhe; `temMinhasRespostas:
// false` é o quiz que existe e cujas respostas ainda não sincronizaram — vai
// aparecer. São mensagens diferentes porque são esperas diferentes.

const NOTA_MAXIMA = 10;

export function ProvaFicha() {
  const { id } = useParams<{ id: string }>();
  const detalhe = useSimulado(id);

  if (detalhe.isPending) {
    return (
      <div className="alu-provas">
        <VoltarParaProvas />
        <div className="alu-bloco">
          <div className="alu-provas__esqueleto" style={{ height: 14, width: '45%' }} />
          <div className="alu-provas__esqueleto" style={{ height: 56, width: '40%' }} />
          <div className="alu-provas__esqueleto" style={{ height: 90 }} />
        </div>
      </div>
    );
  }

  if (detalhe.isError || !detalhe.data) {
    return (
      <div className="alu-provas">
        <VoltarParaProvas />
        <Bloco fonte="simulado">
          <p className="alu-vazio">
            Não achamos este simulado entre os seus. Ele pode ter sido anulado, ou o link está
            velho.
          </p>
          <NavLink className="alu-tecla alu-tecla--fantasma" to="/provas">
            Ver todos os simulados
          </NavLink>
        </Bloco>
      </div>
    );
  }

  const s = detalhe.data;
  const nome = s.rotulo || s.nome || s.id;

  return (
    <div className="alu-provas">
      <VoltarParaProvas />
      <h1 className="alu-titulo-tela">{nome}</h1>

      <Bloco fonte="simulado" olho="Sua nota" className="alu-provas__hero">
        <div className="alu-provas__hero-nota">
          <strong className="alu-magnitude alu-provas__nota">{fmt(s.nota)}</strong>
          <span className="alu-provas__escala">de {fmtInteiro(NOTA_MAXIMA)}</span>
        </div>

        {s.deltaSelf != null && (
          <p className="alu-provas__delta">
            <span className={`alu-provas__delta-valor${s.deltaSelf > 0 ? ' is-subiu' : ''}`}>
              <Icone nome={s.deltaSelf > 0 ? 'seta_cima' : 'seta_baixo'} tamanho={14} />
              {fmtDelta(s.deltaSelf)}
            </span>
            <span>contra o seu próprio padrão até aqui</span>
          </p>
        )}

        <dl className="alu-provas__leituras">
          <div className="alu-provas__leitura">
            <dt className="alu-olho alu-olho--quieto">Aplicado em</dt>
            <dd className="alu-provas__leitura-valor">{fmtDataLonga(s.dataAplicacao)}</dd>
          </div>
          <div className="alu-provas__leitura">
            <dt className="alu-olho alu-olho--quieto">Posição</dt>
            <dd className="alu-provas__leitura-valor">
              {fmtInteiro(s.posicao)}º de {fmtInteiro(s.total)}
            </dd>
          </div>
          <div className="alu-provas__leitura">
            <dt className="alu-olho alu-olho--quieto">Percentil</dt>
            <dd className="alu-provas__leitura-valor">acima de {fmtInteiro(s.percentil)}%</dd>
          </div>
        </dl>

        {/* Uma ação só desde 04/09, e a barra continua sendo barra: o extrato
            é o caminho para "de onde veio esta nota", e era ele que dividia
            espaço com o "Abrir a prova" (docs/35 §8b). */}
        <div className="alu-provas__acoes">
          <NavLink className="alu-tecla alu-tecla--valor" to={`/provas/${s.id}/extrato`}>
            <FichaXp tamanho={18} />
            Ver o extrato
          </NavLink>
        </div>
      </Bloco>

      <Comparacao grupos={s.grupos} minhaNota={s.nota} />
      <Questoes id={s.id} />
    </div>
  );
}

function VoltarParaProvas() {
  return (
    <NavLink className="alu-provas__voltar" to="/provas">
      <Icone nome="voltar" tamanho={16} />
      Provas
    </NavLink>
  );
}

// ─── Comparação com a turma ──────────────────────────────────────────────

/**
 * Você, a média geral, o top 15% e o inferior 15% — na mesma régua de 0 a 10.
 *
 * SVG escrito à mão, como todo gráfico do projeto. A sua barra é preenchida na
 * cor DADO; as três referências são VAZADAS, porque não são conquista sua — são
 * a régua contra a qual você se lê.
 */
function Comparacao({ grupos, minhaNota }: { grupos: GruposComparacao | null; minhaNota: number }) {
  if (!grupos || grupos.geral == null) {
    return (
      <Bloco fonte="simulado" olho="Contra a turma">
        <p className="alu-vazio">
          Ainda não há gente suficiente com nota neste simulado para comparar sem enganar.
        </p>
      </Bloco>
    );
  }

  const linhas: Array<{ rotulo: string; valor: number | null; eu: boolean }> = [
    { rotulo: 'Top 15%', valor: grupos.top15, eu: false },
    { rotulo: 'Você', valor: grupos.voce ?? minhaNota, eu: true },
    { rotulo: 'Média geral', valor: grupos.geral, eu: false },
    { rotulo: 'Inferior 15%', valor: grupos.bottom15, eu: false },
  ].filter((l) => l.valor != null);

  const largura = 320;
  const alturaLinha = 34;
  const altura = linhas.length * alturaLinha;
  const rotuloLargura = 92;
  const larguraDaRegua = largura - rotuloLargura - 34;

  return (
    <Bloco fonte="simulado" olho="Contra a turma">
      <svg
        viewBox={`0 0 ${largura} ${altura}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Comparação neste simulado: ${linhas
          .map((l) => `${l.rotulo} ${fmt(l.valor)}`)
          .join('; ')}`}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <title>Contra a turma</title>
        {linhas.map((l, i) => {
          const y = i * alturaLinha + 8;
          const h = 16;
          const w = Math.max(2, (Math.min(NOTA_MAXIMA, l.valor ?? 0) / NOTA_MAXIMA) * larguraDaRegua);
          return (
            <g key={l.rotulo}>
              <text x={0} y={y + h - 3} className="alu-provas__grupo-rotulo">
                {l.rotulo}
              </text>
              {l.eu ? (
                <rect x={rotuloLargura} y={y} width={w} height={h} rx="4" fill="var(--alu-dado)" />
              ) : (
                <rect
                  x={rotuloLargura + 0.75}
                  y={y + 0.75}
                  width={Math.max(2, w - 1.5)}
                  height={h - 1.5}
                  rx="4"
                  fill="none"
                  stroke="var(--alu-borda)"
                  strokeWidth="1.5"
                />
              )}
              <text
                x={rotuloLargura + w + 7}
                y={y + h - 3}
                className={`alu-provas__grupo-valor${l.eu ? ' is-eu' : ''}`}
              >
                {fmt(l.valor)}
              </text>
            </g>
          );
        })}
      </svg>
    </Bloco>
  );
}

// ─── Questão por questão ─────────────────────────────────────────────────

function Questoes({ id }: { id: string }) {
  const questoes = useQuestoesDoSimulado(id);

  if (questoes.isPending) {
    return (
      <Bloco fonte="questoesDoSimulado" olho="Questão por questão">
        <div className="alu-provas__esqueleto" style={{ height: 96 }} />
      </Bloco>
    );
  }

  if (questoes.isError) {
    return (
      <Bloco fonte="questoesDoSimulado" olho="Questão por questão">
        <p className="alu-vazio">Não deu para carregar o resultado questão a questão.</p>
        {/* Tecla de tamanho cheio: `--pequena` tem 36px e o piso de toque do
            produto é 44 (docs/20 §1.3). */}
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma"
          onClick={() => questoes.refetch()}
        >
          Tentar de novo
        </button>
      </Bloco>
    );
  }

  const dados = questoes.data;

  // ⚠️ Os dois silêncios são diferentes, e a mensagem também tem de ser.
  if (!dados?.temGabarito) {
    return (
      <Bloco fonte="questoesDoSimulado" olho="Questão por questão">
        <p className="alu-vazio">
          Este simulado não foi aplicado como quiz, então não existe registro questão a questão —
          só a nota. Não é algo que vá chegar depois.
        </p>
      </Bloco>
    );
  }

  if (!dados.temMinhasRespostas) {
    return (
      <Bloco fonte="questoesDoSimulado" olho="Questão por questão">
        <p className="alu-vazio">
          O gabarito deste simulado já existe, mas as suas respostas ainda não vieram do Canvas.
          Elas aparecem aqui assim que a sincronização passar.
        </p>
      </Bloco>
    );
  }

  const duracao = fmtDuracao(dados.duracaoMediaSegundos);

  return (
    <Bloco
      fonte="questoesDoSimulado"
      olho="Questão por questão"
      acao={`${fmtInteiro(dados.questoes.length)} questões`}
    >
      <ul className="alu-provas__placar">
        <li>
          <strong className="alu-magnitude alu-provas__placar-numero">
            {fmtInteiro(dados.acertos)}
          </strong>
          <span className="alu-olho alu-olho--quieto">certas</span>
        </li>
        <li>
          <strong className="alu-magnitude alu-provas__placar-numero">
            {fmtInteiro(dados.erros)}
          </strong>
          <span className="alu-olho alu-olho--quieto">erradas</span>
        </li>
        <li>
          <strong className="alu-magnitude alu-provas__placar-numero">
            {fmtInteiro(dados.emBranco)}
          </strong>
          <span className="alu-olho alu-olho--quieto">em branco</span>
        </li>
      </ul>

      <ol className="alu-provas__questoes">
        {dados.questoes.map((q, i) => (
          <QuadradoDaQuestao key={`${q.posicao ?? 'sem'}-${i}`} questao={q} indice={i} />
        ))}
      </ol>

      <ul className="alu-provas__legenda">
        <li>
          <span className="alu-provas__amostra alu-provas__amostra--certa" />
          certa
        </li>
        <li>
          <span className="alu-provas__amostra alu-provas__amostra--errada" />
          errada
        </li>
        <li>
          <span className="alu-provas__amostra alu-provas__amostra--branco" />
          em branco
        </li>
      </ul>

      {duracao && <p className="alu-provas__aviso">Tempo médio da turma na prova: {duracao}.</p>}
    </Bloco>
  );
}

const SITUACAO = {
  correta: 'certa',
  errada: 'errada',
  em_branco: 'em branco',
} as const;

function QuadradoDaQuestao({ questao, indice }: { questao: QuestaoDoAluno; indice: number }) {
  const numero = questao.posicao ?? indice + 1;
  const detalhe = [
    questao.assunto,
    questao.alternativaCorreta && `gabarito ${questao.alternativaCorreta}`,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <li
      className={`alu-provas__questao alu-provas__questao--${questao.resultado}`}
      title={`Questão ${numero} · ${SITUACAO[questao.resultado]}${detalhe ? ` · ${detalhe}` : ''}`}
    >
      <span aria-hidden="true">{numero}</span>
      <span className="alu-so-leitor">
        Questão {numero}: {SITUACAO[questao.resultado]}
      </span>
    </li>
  );
}
