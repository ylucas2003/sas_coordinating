import { useNavigate } from 'react-router-dom';
import { Sparkline } from './Sparkline';
import type { Alerta } from '../../tipos/dominio';

interface Props {
  alerta: Alerta;
  onResolver?: (alerta: Alerta) => void;
  /**
   * O corte da régua em vigor, para o fio de ouro do sparkline.
   *
   * Entra por prop e é OPCIONAL porque `GET /alertas` ainda não manda o corte
   * junto do alerta — quem sabe qual régua está em vigor é a tela. Sem ele a
   * curva desenha sozinha, e "caiu" e "caiu para baixo do corte" viram a mesma
   * forma (docs/39 §3 · fase 1).
   */
  corte?: number;
  /**
   * O alerta acabou de ser resolvido e ainda está na tela, esperando o desfazer.
   *
   * Não é estado do servidor: lá `resolvido` faz o alerta sumir da listagem.
   * É o intervalo de arrependimento que a tela concede antes de deixar o
   * cartão ir embora.
   */
  resolvido?: boolean;
  /** Reabre o alerta. Sem ele, o estado resolvido só confirma, sem oferecer volta. */
  onDesfazer?: (alerta: Alerta) => void;
}

/** `4` → `CORTE 4,0`. Vírgula decimal e caixa alta, como o resto da régua. */
function rotuloDoFio(corte: number): string {
  return `CORTE ${corte.toFixed(1).replace('.', ',')}`;
}

/**
 * Cartão de alerta — componente central do Painel.
 *
 * Com a tabela de 900 linhas indo para a ficha de ciclo (docs/39 §3 · fase 2),
 * ele deixa de dividir a tela e passa a ser quase todo o Painel. Por isso a
 * anatomia cresceu: título em magnitude, duas ações de 44px e o sparkline com
 * a régua desenhada, em vez da linha de 12px espremida entre uma tabela e
 * quatro KPIs (docs/04-screens.md §4.1 descreve o desenho antigo).
 */
export function AlertCard({
  alerta,
  onResolver,
  corte,
  resolvido = false,
  onDesfazer,
}: Props) {
  const navegar = useNavigate();

  // O `href` do alerta ainda vem do backend no formato antigo (`#/simulados/S3`).
  const destino = alerta.href.replace(/^#/, '');

  // Resolver era a única ação da tela que não tinha volta: o cartão sumia, sem
  // motivo, sem desfazer e sem registro visível. O cartão resolvido fica no
  // lugar dele até a próxima leitura, dizendo o que aconteceu.
  //
  // ⚠️ A prancheta escreve "guardado na auditoria, com seu nome e a hora".
  // `POST /alertas/{id}/resolver` grava `resolvido` e `resolvido_em` — a hora,
  // não o nome (`api/app/routes/alertas.py`). A frase aqui promete só o que a
  // tabela cumpre; o nome volta quando a coluna existir.
  if (resolvido) {
    return (
      <div className="alert-card alert-card--resolvido" role="status">
        <p className="alert-card__confirmacao">
          Alerta resolvido — a hora ficou registrada. Ele sai da faixa na próxima leitura.
        </p>
        {onDesfazer && (
          <button
            type="button"
            className="alert-card__desfazer"
            onClick={() => onDesfazer(alerta)}
          >
            Desfazer
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="alert-card" onClick={() => navegar(destino)}>
      {/* R4 · a barra de severidade saiu, e com ela o `tone-*` da raiz: a
          gravidade é ORDEM — o mais grave primeiro, quem monta a lista decide —
          e etiqueta, nunca uma faixa colorida na lateral. A pílula ficou de
          contorno neutro porque quem diz o estado é a PALAVRA que está dentro
          dela, e ela nomeia a CATEGORIA do alerta, não o quanto ele é grave. */}
      <div className="alert-card__main">
        <div className="alert-card__meta">
          <span className="alert-card__tag">{alerta.tagLabel}</span>
          <span className="alert-card__time">{alerta.tempoRelativo}</span>
        </div>
        <div className="alert-card__title">{alerta.titulo}</div>
        <div className="alert-card__subtitle">{alerta.subtitulo}</div>
      </div>

      {/* Sem `descricao`: o sparkline desenha o que o título ao lado já diz em
          palavras, e a Sparkline trata quem não recebe leitura como decorativo
          — dizer a mesma frase duas vezes ao leitor de tela é ruído. */}
      <div className="alert-card__viz">
        <Sparkline
          valores={alerta.sparkline ?? []}
          largura={150}
          altura={54}
          corte={corte}
          rotuloCorte={corte != null ? rotuloDoFio(corte) : undefined}
        />
      </div>

      <div className="alert-card__acoes">
        <a
          className="btn alert-card__acao alert-card__acao--ver"
          href={destino}
          onClick={(ev) => {
            ev.preventDefault();
            ev.stopPropagation();
            navegar(destino);
          }}
        >
          Ver detalhes
        </a>
        {onResolver && (
          <button
            type="button"
            className="btn btn-primary alert-card__acao"
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
