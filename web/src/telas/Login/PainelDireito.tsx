import { ROTULOS_COORDENACAO } from './modos';

import ariLogo from '../../../assets/ari-logo-branca.png';
import sasLogo from '../../../assets/sas-logo.png';
import selo from '../../../assets/selo-108anos.webp';

const ESTATISTICAS = [
  { num: '108', em: 'anos', label: 'Tradição' },
  { num: '312', em: '+', label: 'Aprovações ITA' },
  { num: '287', em: '+', label: 'Aprovações IME' },
  { num: '12,4', em: 'mil', label: 'Alunos ativos' },
];

/**
 * Coluna institucional do login: marca, selo e manchete.
 *
 * ⚠️ Não recebe mais `modo`. A manchete mudava com ele, mas esta coluna só é
 * desenhada no lado da coordenação — o lado do aluno é a `PortaDoAluno`, que
 * ocupa a tela inteira. Com o formulário do aluno fora (docs/35 §11.5) o
 * `modo` aqui tinha um único valor possível.
 */
export function PainelDireito({ geracao }: { geracao: number }) {
  const m = ROTULOS_COORDENACAO;

  return (
    <div className="lp-right">
      {/* A FACHADA DE COBOGÓ — a mesma treliça do login do aluno, noutro
          ângulo, e no mesmo ritmo de 24px da grade de fundo do casco. Não são
          duas decisões: é a peça que amarra as duas portas do produto na
          primeira olhada (docs/brief-claude-design-coordenacao.md §8).

          Substituiu quatro arcos concêntricos, que eram a marca de que esta
          tela vinha de outro sistema visual. */}
      <svg className="lp-cobogo" aria-hidden="true" preserveAspectRatio="xMidYMid slice">
        <defs>
          <pattern id="login-cobogo" width="24" height="24" patternUnits="userSpaceOnUse">
            <path d="M24 0H0v24" fill="none" stroke="currentColor" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#login-cobogo)" />
      </svg>

      <div className="lp-right__header">
        <img src={ariLogo} alt="Colégio Ari de Sá Cavalcante" className="lp-logo-ari" />
        <span className="lp-right__div" />
        <img src={sasLogo} alt="SAS Educação" className="lp-logo-sas" />
        <div className="lp-right__parceria">
          <span className="lp-right__parceria-top">Parceria oficial</span>
          <span className="lp-right__parceria-sub">
            Diagnóstico pedagógico
            <br />
            integrado
          </span>
        </div>
      </div>

      <div className="lp-right__card">
        <img src={selo} alt="Selo 108 anos" className="lp-right__card-img" />
        <div className="lp-right__card-body">
          <p className="lp-right__card-year">1918 — 2026</p>
          <p className="lp-right__card-title">108 anos de Ari de Sá Cavalcante</p>
          <p className="lp-right__card-sub">Tradição centenária em formação de excelência.</p>
        </div>
      </div>

      <div className="lp-right__hero" key={geracao}>
        <h2 className="lp-right__headline">
          {m.rightHl[0]}
          <br />
          {m.rightHl[1]}
          <br />
          {m.rightHl[2]}
          <em>{m.rightHlEm}</em>
        </h2>
        <p className="lp-right__sub">{m.rightSub}</p>
      </div>

      <div className="lp-right__stats">
        {ESTATISTICAS.map((s) => (
          <div key={s.label} className="lp-stat">
            <span className="lp-stat__num">
              {`${s.num} `}
              <em>{s.em}</em>
            </span>
            <span className="lp-stat__label">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
