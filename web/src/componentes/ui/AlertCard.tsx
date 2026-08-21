import { useNavigate } from 'react-router-dom';
import { Sparkline } from './Sparkline';
import type { Alerta } from '../../tipos/dominio';

interface Props {
  alerta: Alerta;
  onResolver?: (alerta: Alerta) => void;
}

/**
 * Cartão de alerta — componente central do Painel.
 * Anatomia documentada em docs/04-screens.md (4.1).
 */
export function AlertCard({ alerta, onResolver }: Props) {
  const navegar = useNavigate();
  const tone = `tone-${alerta.severidade}`;

  // O `href` do alerta ainda vem do backend no formato antigo (`#/simulados/S3`).
  const destino = alerta.href.replace(/^#/, '');

  return (
    <div className={`alert-card ${tone}`} onClick={() => navegar(destino)}>
      <div className={`alert-card__bar ${tone}`} />
      <div className="alert-card__main">
        <div className="alert-card__meta">
          <span className={`alert-card__tag ${tone}`}>{alerta.tagLabel}</span>
          <span className="alert-card__time">{alerta.tempoRelativo}</span>
        </div>
        <div className="alert-card__title">{alerta.titulo}</div>
        <div className="alert-card__subtitle">{alerta.subtitulo}</div>
      </div>
      <div className="alert-card__viz">
        <Sparkline valores={alerta.sparkline ?? []} cor="currentColor" />
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
        <a
          className="alert-card__link"
          href={destino}
          onClick={(ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            navegar(destino);
          }}
        >
          Ver detalhes →
        </a>
        {onResolver && (
          <button
            className="btn-link-resolver"
            onClick={(ev) => {
              ev.preventDefault();
              ev.stopPropagation();
              onResolver(alerta);
            }}
          >
            Resolver
          </button>
        )}
      </div>
    </div>
  );
}
