import { useEffect, useRef, useState } from 'react';
import { DialogoComDiff } from './DialogoComDiff';
import type { Mudanca } from './DialogoComDiff';

/** Campos alterados, no formato que a API espera (snake_case). */
export interface PatchSimulado {
  nome?: string;
  rotulo_curto?: string | null;
  nota_maxima?: number;
  anulado?: boolean;
  /** A escolha do coordenador na confirmação (docs/18 §2.3). */
  sincronizar_canvas: boolean;
}

interface Props {
  nome: string;
  rotuloAtual: string | null;
  notaMaximaAtual: number | null;
  anuladoAtual: boolean;
  /** Só simulados criados no SAS têm write-back; os do Canvas não perguntam. */
  origemSas?: boolean;
  /** `null` = cancelado ou sem alteração. */
  onFechar: (patch: PatchSimulado | null) => void;
}

/** Edição dos metadados do simulado: formulário → diff → confirmar. */
export function EdicaoSimulado({
  nome, rotuloAtual, notaMaximaAtual, anuladoAtual, origemSas = false, onFechar,
}: Props) {
  const refNome = useRef<HTMLInputElement>(null);

  const [nomeNovo, setNomeNovo] = useState(nome || '');
  const [rotulo, setRotulo] = useState(rotuloAtual || '');
  const [notaMax, setNotaMax] = useState(notaMaximaAtual != null ? String(notaMaximaAtual) : '');
  const [anulado, setAnulado] = useState(anuladoAtual ?? false);

  const [erroNome, setErroNome] = useState(false);
  const [erroNotaMax, setErroNotaMax] = useState(false);

  const [mudancas, setMudancas] = useState<Mudanca[] | null>(null);
  const [patch, setPatch] = useState<PatchSimulado | null>(null);

  useEffect(() => {
    refNome.current?.focus();
  }, []);

  function salvar() {
    setErroNome(false);
    setErroNotaMax(false);

    const nomeLimpo = nomeNovo.trim();
    const rotuloLimpo = rotulo.trim() || null;
    const notaMaxCru = notaMax.trim().replace(',', '.');
    const notaMaxNova = notaMaxCru !== '' ? parseFloat(notaMaxCru) : null;

    if (!nomeLimpo) {
      setErroNome(true);
      refNome.current?.focus();
      return;
    }
    if (notaMaxNova !== null && (Number.isNaN(notaMaxNova) || notaMaxNova <= 0)) {
      setErroNotaMax(true);
      return;
    }

    const lista: Mudanca[] = [];
    // `sincronizar_canvas` é decidido no passo de confirmação.
    const novo: PatchSimulado = { sincronizar_canvas: false };

    if (nomeLimpo !== nome) {
      lista.push({ campo: 'Nome', de: nome || '—', para: nomeLimpo });
      novo.nome = nomeLimpo;
    }
    if (rotuloLimpo !== (rotuloAtual || null)) {
      lista.push({ campo: 'Rótulo', de: rotuloAtual || '—', para: rotuloLimpo || '—' });
      novo.rotulo_curto = rotuloLimpo;
    }
    if (notaMaxNova !== null && notaMaxNova !== notaMaximaAtual) {
      lista.push({ campo: 'Nota máx.', de: String(notaMaximaAtual ?? '—'), para: String(notaMaxNova) });
      novo.nota_maxima = notaMaxNova;
    }
    if (anulado !== (anuladoAtual ?? false)) {
      lista.push({ campo: 'Anulado', de: anuladoAtual ? 'Sim' : 'Não', para: anulado ? 'Sim' : 'Não' });
      novo.anulado = anulado;
    }

    if (!lista.length) return onFechar(null);
    setPatch(novo);
    setMudancas(lista);
  }

  return (
    <DialogoComDiff
      titulo="Editar simulado"
      subtitulo={nome || '—'}
      mudancas={mudancas}
      onCancelar={() => onFechar(null)}
      onVoltar={() => {
        setMudancas(null);
        setPatch(null);
      }}
      canvas={origemSas ? { efeito: 'realinha o Assignment no Canvas (nome, data, pontos).' } : undefined}
      onConfirmar={(sincronizar_canvas) => onFechar(patch && { ...patch, sincronizar_canvas })}
      onSalvar={salvar}
    >
      <div className="dialog__campo">
        <span className="dialog__label">Nome</span>
        <input
          ref={refNome}
          type="text"
          className={`dialog__input${erroNome ? ' dialog__input--erro' : ''}`}
          value={nomeNovo}
          onChange={(e) => setNomeNovo(e.target.value)}
        />
      </div>

      <div className="dialog__campo">
        <span className="dialog__label">Rótulo curto (Pn)</span>
        <input
          type="text" className="dialog__input" placeholder="ex.: P12" maxLength={12}
          value={rotulo} onChange={(e) => setRotulo(e.target.value)}
        />
        <span className="dialog__hint">Usado no eixo do gráfico. Ex.: P12</span>
      </div>

      <div className="dialog__campo">
        <span className="dialog__label">Nota máxima (nº de questões)</span>
        <input
          type="number" min="1" step="1" placeholder="ex.: 20"
          className={`dialog__input${erroNotaMax ? ' dialog__input--erro' : ''}`}
          value={notaMax} onChange={(e) => setNotaMax(e.target.value)}
        />
      </div>

      <div className="dialog__campo">
        <label className="dialog__checkbox-row">
          <input type="checkbox" checked={anulado} onChange={(e) => setAnulado(e.target.checked)} />
          <span className="dialog__checkbox-label">Marcar como anulado</span>
        </label>
        <span className="dialog__hint">
          Simulados anulados ficam fora das estatísticas e classificações.
        </span>
      </div>
    </DialogoComDiff>
  );
}
