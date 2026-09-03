import { useState } from 'react';

import { Dialogo } from '../../componentes/dialogos/Dialogo';
import { SeloCanvas } from '../../componentes/ui/SeloCanvas';
import { usePendenciasCanvas } from '../../hooks/consultas';
import { useEnviarCicloAoCanvasEmLote } from '../../hooks/mutacoes';
import type { EstadoCanvas, PendenciasCanvas as Pendencias, ResultadoLoteCanvas } from '../../tipos/dominio';

// "Enviar o ciclo inteiro ao Canvas" (docs/32 §4).
//
// O buraco que isto fecha é mais fundo que o lote: `POST /ciclos/{id}/enviar-canvas`
// existia na API, estava exportado em `servicos/api.ts` e **nenhuma linha do
// front o chamava**. Um ciclo criado com `sincronizar_canvas: false` ficava em
// 'divergente' para sempre, e `GET /ciclos` nem devolvia `canvas_estado` — a
// tela não teria como mostrar que ele estava assim. O unitário faltava; o lote
// é o que se constrói em cima.
//
// A regra de 21/08 — "nada sobe ao Canvas sem alguém clicar" — aplicada ao
// lote quer dizer que o coordenador vê **a lista item a item** antes de mandar,
// e o resultado item a item depois. Um lote que diz "sucesso" tendo falhado em
// 3 de 12 é pior que não ter lote nenhum.

export function BlocoPendenciasCanvas({
  cicloId,
  canvasEstado,
}: {
  cicloId: string;
  canvasEstado: EstadoCanvas | null;
}) {
  const { data: pendencias, isPending } = usePendenciasCanvas(cicloId);
  const [confirmando, setConfirmando] = useState(false);
  const [resultado, setResultado] = useState<ResultadoLoteCanvas | null>(null);

  if (isPending || !pendencias) return null;
  if (pendencias.total === 0 && !resultado) {
    // Nada pendente: o selo do ciclo já conta a história, e um bloco vazio
    // dizendo "tudo certo" só ocuparia a dobra.
    return null;
  }

  return (
    <div className="section">
      <div className="ciclo-canvas">
        <div>
          <h2 className="section__title" style={{ margin: 0 }}>
            {pendencias.total === 1
              ? '1 pendência no Canvas'
              : `${pendencias.total} pendências no Canvas`}
            {canvasEstado && (
              <span style={{ marginLeft: 10, verticalAlign: 'middle' }}>
                <SeloCanvas estado={canvasEstado} />
              </span>
            )}
          </h2>
          <p className="section__subtitle" style={{ margin: '4px 0 0' }}>
            O que este ciclo tem no SAS e o Canvas ainda não tem.
          </p>
        </div>
        {pendencias.total > 0 && (
          <button className="btn btn--primary" onClick={() => setConfirmando(true)}>
            Enviar ao Canvas
          </button>
        )}
      </div>

      <ListaPendencias pendencias={pendencias} />

      {confirmando && (
        <DialogoConfirmar
          cicloId={cicloId}
          pendencias={pendencias}
          onFechar={(r) => {
            setConfirmando(false);
            if (r) setResultado(r);
          }}
        />
      )}

      {resultado && <DialogoResultado resultado={resultado} onFechar={() => setResultado(null)} />}
    </div>
  );
}

function ListaPendencias({ pendencias }: { pendencias: Pendencias }) {
  return (
    <ul className="ciclo-canvas__lista">
      {pendencias.grupo.pendente && (
        <li>
          <b>O grupo do ciclo</b> — o Assignment Group ainda não existe no Canvas.
          {pendencias.grupo.erro && <span className="ciclo-canvas__erro"> {pendencias.grupo.erro}</span>}
        </li>
      )}
      {pendencias.simulados.map((s) => (
        <li key={s.id}>
          <b>{s.nome}</b> — simulado criado no SAS, sem Assignment correspondente.
          {s.erro && <span className="ciclo-canvas__erro"> {s.erro}</span>}
        </li>
      ))}
      {pendencias.notas.map((n) => (
        <li key={`${n.alunoId}/${n.simuladoId}`}>
          <b>{n.aluno}</b> em {n.simulado} — {fmt(n.noSas)} no SAS, {fmt(n.noCanvas)} no Canvas.
        </li>
      ))}
      {pendencias.notasAlemDoTeto > 0 && (
        // Truncar em silêncio é exatamente o que este bloco existe para
        // evitar: o coordenador precisa saber que sobrou trabalho.
        <li className="ciclo-canvas__erro">
          {`Mais ${pendencias.notasAlemDoTeto} nota(s) divergentes ficam para um próximo envio — `}
          o lote manda por vez o que cabe numa requisição.
        </li>
      )}
    </ul>
  );
}

function DialogoConfirmar({
  cicloId,
  pendencias,
  onFechar,
}: {
  cicloId: string;
  pendencias: Pendencias;
  onFechar: (r: ResultadoLoteCanvas | null) => void;
}) {
  const enviar = useEnviarCicloAoCanvasEmLote();
  const [erro, setErro] = useState('');

  async function confirmar() {
    setErro('');
    try {
      onFechar(await enviar.mutateAsync(cicloId));
    } catch (e) {
      setErro((e as Error).message || 'Falha ao enviar.');
    }
  }

  return (
    <Dialogo
      titulo="Enviar ao Canvas"
      subtitulo={pendencias.nome ?? undefined}
      onFechar={() => onFechar(null)}
      rodape={
        <>
          <button className="btn btn--ghost" onClick={() => onFechar(null)}>Cancelar</button>
          <button className="btn btn--primary" disabled={enviar.isPending} onClick={confirmar}>
            {enviar.isPending ? 'Enviando…' : `Enviar ${pendencias.total} item(ns)`}
          </button>
        </>
      }
    >
      <p className="section__subtitle">
        Isto escreve no Canvas. Vai nesta ordem — o grupo do ciclo, depois os simulados, depois as
        notas —, porque um Assignment não entra num grupo que não existe.
      </p>
      <ListaPendencias pendencias={pendencias} />
      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}

function DialogoResultado({
  resultado,
  onFechar,
}: {
  resultado: ResultadoLoteCanvas;
  onFechar: () => void;
}) {
  return (
    <Dialogo
      titulo={
        resultado.falhas === 0
          ? `${resultado.enviados} item(ns) enviados`
          : `${resultado.enviados} enviados, ${resultado.falhas} com falha`
      }
      onFechar={onFechar}
      rodape={<button className="btn btn--primary" onClick={onFechar}>Fechar</button>}
    >
      {resultado.interrompido && (
        <p className="agendar__erro">{`O lote parou: ${resultado.interrompido}.`}</p>
      )}
      {/* Resultado por item, sempre — inclusive quando tudo deu certo. É o que
          transforma "mandei" em "sei o que foi". */}
      <ul className="ciclo-canvas__lista">
        {resultado.itens.map((i) => (
          <li key={`${i.tipo}-${i.id}`}>
            <span className={i.ok ? 'sim-selo-ok' : 'sim-selo-divergente'}>
              {i.ok ? 'enviado' : 'falhou'}
            </span>{' '}
            <b>{i.rotulo}</b>
            {i.erro && <span className="ciclo-canvas__erro"> — {i.erro}</span>}
          </li>
        ))}
      </ul>
    </Dialogo>
  );
}

function fmt(v: number | null): string {
  return v == null ? '—' : String(v);
}
