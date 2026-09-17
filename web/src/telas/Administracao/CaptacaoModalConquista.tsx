import { Dialogo } from '../../componentes/dialogos/Dialogo';
import { Kpi } from '../../componentes/ui/Kpi';
import type { ConquistaExterna } from '../../tipos/captacao';

// O detalhe de UMA conquista — pedido explícito: clicar no Resultado abre a
// nota por matéria (quando a fonte publica) junto com o link pra fonte, em
// vez de espalhar isso em colunas extras na tabela (CaptacaoFicha.tsx e
// CaptacaoFusaoDetalhe.tsx, as duas telas que listam conquista cruzada).

const ROTULO_MATERIA: Record<string, string> = {
  mat: 'Matemática',
  fis: 'Física',
  qui: 'Química',
  port: 'Português',
  por: 'Português',
  ing: 'Inglês',
  ing_obj: 'Inglês (objetiva)',
  ing_disc: 'Inglês (discursiva)',
  red: 'Redação',
  media: 'Média',
  total: 'Total',
};

export function CaptacaoModalConquista({
  conquista,
  onFechar,
}: {
  conquista: ConquistaExterna;
  onFechar: () => void;
}) {
  const notas = conquista.notas_por_materia;

  return (
    <Dialogo
      titulo={`${conquista.prova_nome ?? 'Prova'} · ${conquista.ano}`}
      subtitulo={conquista.resultado}
      onFechar={onFechar}
      rodape={
        <>
          <a
            className="btn btn--ghost"
            href={conquista.fonte_url}
            target="_blank"
            rel="noreferrer"
          >
            Ver fonte ↗
          </a>
          <button type="button" className="btn btn--primary" onClick={onFechar}>
            Fechar
          </button>
        </>
      }
    >
      {notas ? (
        <div className="kpi-grid kpi-grid--cartoes">
          {Object.entries(notas).map(([materia, valor]) => (
            <Kpi key={materia} rotulo={ROTULO_MATERIA[materia] ?? materia} valor={valor} />
          ))}
        </div>
      ) : (
        <p className="tela-subtitulo">Esta fonte não publica nota por matéria.</p>
      )}
      {conquista.escola_informada && (
        <p className="tela-subtitulo" style={{ marginTop: 12 }}>
          <b>Escola informada:</b> {conquista.escola_informada}
        </p>
      )}
    </Dialogo>
  );
}
