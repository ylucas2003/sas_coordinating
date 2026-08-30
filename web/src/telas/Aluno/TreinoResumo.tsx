import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';

import { resumoDoTreino } from '../../dados/aluno';
import { Icone } from './pecas/Icone';
import { TarjaFonte } from './pecas/TarjaFonte';
import { fmtPercentual } from './pecas/formato';
import type { EstadoDoResumo } from './Treino';

// O fim da sessão de treino.
//
// ⚠️ SEM XP E SEM CONFETE, e a ausência é a regra, não uma economia de esforço.
// Treino não paga (docs/28 §3, regra 5) e a celebração de tela cheia é reservada
// ao marco verificado — cruzar o corte, um recorde de sequência (docs/26 §6).
// Usar a celebração grande em tudo mata as duas.
//
// O que a tela entrega no lugar do XP é a única coisa que o treino de fato
// muda: o PLANO. "Estequiometria subiu no seu plano" é consequência verificável
// da sessão; "+120 XP" não seria.
//
// De onde vêm os números: das respostas da sessão, que vivem no `useState` do
// `Treino` e chegam aqui pelo `state` do `navigate`. Não há rota, não há tabela
// — `questao_estudo_aluno` não tem `alternativa_escolhida` nem `acertou`
// (fonte `respostaNoTreino`, docs/28 §3). Recarregar a página perde a sessão, e
// por isso o caso "abri /resumo direto pela URL" é um estado de primeira classe
// aqui, não um erro.

export function TreinoResumo() {
  const navigate = useNavigate();
  const { origem = 'prioridade' } = useParams();
  const { state } = useLocation();
  const estado = (state ?? null) as EstadoDoResumo | null;
  const respostas = estado?.respostas ?? [];

  if (respostas.length === 0) {
    // Estado vazio que CONVIDA A AGIR: quem chega aqui por link salvo não fez
    // nada de errado, e um "sessão não encontrada" o deixaria sem saída.
    return (
      <div className="alu-shell alu-treino-resumo">
        <div className="alu-treino-resumo__corpo">
          <span className="alu-olho">Treino</span>
          <h1 className="alu-titulo-tela">Nenhuma sessão para resumir</h1>
          <p className="alu-vazio">
            O resumo mostra o que você acertou numa sessão de treino. Comece uma e ele aparece aqui
            no fim.
          </p>
          <div className="alu-treino-resumo__acoes">
            <Link className="alu-tecla alu-tecla--larga" to="/treino/prioridade">
              Treinar agora
            </Link>
            <Link className="alu-tecla alu-tecla--fantasma alu-tecla--larga" to="/">
              Voltar para Hoje
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const resumo = resumoDoTreino(respostas);
  const voltarPara = estado?.voltarPara ?? `/treino/${origem}`;

  return (
    <div className="alu-shell alu-treino-resumo">
      <header className="alu-treino-resumo__topo">
        <button
          type="button"
          className="alu-treino__icone"
          onClick={() => navigate('/')}
          aria-label="Voltar para Hoje"
        >
          <Icone nome="fechar" tamanho={22} />
        </button>
        <span className="alu-olho">Fim da sessão</span>
      </header>

      <div className="alu-treino-resumo__corpo">
        <section className="alu-bloco alu-treino-resumo__placar">
          <TarjaFonte chave="respostaNoTreino" />
          <p className="alu-treino-resumo__conta">
            <strong className="alu-magnitude alu-treino-resumo__acertos">{resumo.acertos}</strong>
            <span className="alu-treino-resumo__de">de {resumo.total}</span>
          </p>
          <p className="alu-treino-resumo__leitura">
            {resumo.acertos === resumo.total
              ? 'Você acertou todas.'
              : `Você acertou ${fmtPercentual(resumo.acertos / resumo.total)} desta sessão.`}
          </p>
        </section>

        <section className="alu-bloco">
          {/* Os três blocos saem das MESMAS respostas em `useState` — o
              agrupamento por assunto não é mais real que o placar. */}
          <TarjaFonte chave="respostaNoTreino" />
          <span className="alu-olho">Assuntos que apareceram</span>
          <ul className="alu-treino-resumo__assuntos">
            {resumo.assuntos.map((a) => (
              <li key={a.nome} className="alu-treino-resumo__assunto">
                <span className="alu-treino-resumo__assunto-nome">{a.nome}</span>
                <span className="alu-treino-resumo__assunto-conta">
                  {a.acertos}/{a.total}
                </span>
                {/* VAZIO É VAZADO: o trilho é contorno e só a parte acertada é
                    preenchida na cor DADO. Nada aqui fica vermelho — errar
                    numa sessão de treino não é uma má notícia, é a sessão
                    funcionando (docs/24 §7.1, regra 2). */}
                <span className="alu-treino-resumo__trilho">
                  <span
                    className="alu-treino-resumo__trilho-fill"
                    style={{ width: `${(a.acertos / a.total) * 100}%` }}
                  />
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="alu-bloco alu-treino-resumo__plano">
          <TarjaFonte chave="respostaNoTreino" />
          <span className="alu-olho">O que isto mudou</span>
          <p className="alu-treino-resumo__efeito">{resumo.efeitoNoPlano}</p>
          <p className="alu-treino-resumo__nota">
            Treino não vale ponto — quem paga XP é o simulado. O que ele muda é a ordem do que você
            treina.
          </p>
        </section>

        <div className="alu-treino-resumo__acoes">
          <Link className="alu-tecla alu-tecla--larga" to="/">
            Voltar para Hoje
          </Link>
          <Link className="alu-tecla alu-tecla--fantasma alu-tecla--larga" to={voltarPara}>
            Treinar mais
          </Link>
        </div>
      </div>
    </div>
  );
}
