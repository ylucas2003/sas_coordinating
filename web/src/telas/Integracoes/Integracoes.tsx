import { Link } from 'react-router-dom';

import { AbasAdmin } from '../../componentes/layout/AbasAdmin';
import { usePainelGravacoes } from '../../hooks/consultas';
import { resumoAndamento, situacaoDe } from '../../dominio/gravacoes';

/**
 * Vitrine das integrações com sistemas de fora.
 *
 * Nasce com um card só, mas como grade: as integrações do SAS com o mundo
 * (Canvas, YouTube, SES, Z-API) estavam espalhadas por telas que não falam
 * disso — o agendamento no Canvas dentro de Simulados, o e-mail dentro de
 * Alertas. Aqui é onde a coordenação vem perguntar "está rodando?" sem
 * precisar saber em que tela cada integração mora.
 *
 * Cada card leva a uma tela própria; a grade cresce por uma entrada no array.
 */

export function Integracoes() {
  const { data } = usePainelGravacoes();
  const aulas = data?.aulas ?? [];

  const publicadas = aulas.filter((a) => situacaoDe(a) === 'publicado').length;
  const comErro = aulas.filter((a) => situacaoDe(a) === 'erro').length;
  const andamento = resumoAndamento(aulas);

  // O erro vem antes do andamento de propósito: uma aula travada é o que a
  // coordenação precisa ver do corredor, mesmo com a fila andando.
  const resumo = !data
    ? 'Carregando…'
    : comErro
      ? `${comErro} aula${comErro > 1 ? 's' : ''} com erro`
      : (andamento ?? `${publicadas} aula${publicadas === 1 ? '' : 's'} no canal`);

  const tone = !data ? '' : comErro ? 'tone-vermelho' : andamento ? 'tone-navy' : 'tone-verde';

  return (
    <div className="tela">
      <AbasAdmin />

      <div className="tela-cabecalho">
        <div>
          <h1 className="tela-titulo">Integrações</h1>
          <p className="tela-subtitulo">
            O que o SAS troca com sistemas de fora, e se está funcionando.
          </p>
        </div>
      </div>

      <div className="integracoes-grade">
        <Link className="card integracao-card" to="/integracoes/aulas">
          <div className="integracao-card__topo">
            <h2 className="integracao-card__titulo">Canvas ↔ YouTube</h2>
            <span className={`integracao-card__estado ${tone}`}>{resumo}</span>
          </div>
          <p className="integracao-card__texto">
            Sincronização de aulas SAS. A gravação da conferência é baixada do Canvas antes de
            expirar, ganha o template da marca, sobe ao canal como não listada e volta embutida na
            página da aula.
          </p>
          <span className="integracao-card__acao">Acompanhar aulas →</span>
        </Link>
      </div>
    </div>
  );
}
