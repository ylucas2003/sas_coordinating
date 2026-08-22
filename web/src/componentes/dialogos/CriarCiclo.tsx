import { useEffect, useRef, useState } from 'react';
import { Campo, Dialogo, Linha2 } from './Dialogo';
import { useCriarCiclo } from '../../hooks/mutacoes';
import type { Ciclo } from '../../tipos/dominio';

interface Props {
  onFechar: (criado: Ciclo | null) => void;
}

/** Diálogo "Novo ciclo" — cria o Assignment Group no Canvas junto, se pedido. */
export function CriarCiclo({ onFechar }: Props) {
  const criarCiclo = useCriarCiclo();
  const refOrdem = useRef<HTMLInputElement>(null);

  const [ordem, setOrdem] = useState('');
  const [vestibular, setVestibular] = useState('ITA');
  const [erro, setErro] = useState('');
  // A escolha do coordenador (docs/18 §2.1).
  const [sincronizarCanvas, setSincronizarCanvas] = useState(true);

  useEffect(() => {
    refOrdem.current?.focus();
  }, []);

  async function criar() {
    setErro('');
    const n = parseInt(ordem, 10);
    if (!n || n < 1) {
      setErro('ordem inválida');
      return;
    }
    try {
      onFechar(await criarCiclo.mutateAsync({ ordem: n, vestibular, sincronizar_canvas: sincronizarCanvas }));
    } catch (e) {
      setErro((e as Error).message || 'Falha ao criar ciclo.');
    }
  }

  return (
    <Dialogo
      titulo="Novo ciclo"
      subtitulo={sincronizarCanvas ? 'Cria o Assignment Group no Canvas junto' : 'Só no SAS — o grupo no Canvas pode ser criado depois'}
      onFechar={() => onFechar(null)}
      rodape={
        <>
          <button className="btn btn--ghost" onClick={() => onFechar(null)}>
            Cancelar
          </button>
          <button className="btn btn--primary" disabled={criarCiclo.isPending} onClick={criar}>
            {criarCiclo.isPending ? 'Criando…' : 'Criar'}
          </button>
        </>
      }
    >
      <Linha2>
        <Campo label="Ordem">
          <input
            ref={refOrdem}
            type="number" className="dialog__input" min="1" max="99" placeholder="ex.: 12"
            value={ordem}
            onChange={(e) => setOrdem(e.target.value)}
          />
        </Campo>
        <Campo label="Vestibular">
          <select className="dialog__input" value={vestibular} onChange={(e) => setVestibular(e.target.value)}>
            <option value="ITA">ITA</option>
            <option value="IME">IME</option>
          </select>
        </Campo>
      </Linha2>

      <div className="dialog__campo">
        <label className="agendar__lembrete-check agendar__lembrete-check--solo">
          <input
            type="checkbox"
            checked={sincronizarCanvas}
            onChange={(e) => setSincronizarCanvas(e.target.checked)}
          />
          Criar também no Canvas
        </label>
        <span className="agendar__ajuda">
          {sincronizarCanvas
            ? 'O Assignment Group nasce agora. Simulados agendados aqui vão para ele.'
            : 'Sem grupo no Canvas, os simulados deste ciclo também ficam só no SAS até você enviar o ciclo.'}
        </span>
      </div>

      <Campo label={sincronizarCanvas ? 'Vai criar no Canvas:' : 'Nome do grupo (quando enviar):'}>
        <code className="agendar__preview-nome">{`${ordem || '?'}° CICLO - ${vestibular}`}</code>
      </Campo>

      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
