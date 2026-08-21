import { useEffect, useRef, useState } from 'react';
import { Campo, Dialogo, Linha2 } from './Dialogo';
import { useCriarCiclo } from '../../hooks/mutacoes';
import type { Ciclo } from '../../tipos/dominio';

interface Props {
  onFechar: (criado: Ciclo | null) => void;
}

/** Diálogo "Novo ciclo" — cria o Assignment Group no Canvas junto. */
export function CriarCiclo({ onFechar }: Props) {
  const criarCiclo = useCriarCiclo();
  const refOrdem = useRef<HTMLInputElement>(null);

  const [ordem, setOrdem] = useState('');
  const [vestibular, setVestibular] = useState('ITA');
  const [erro, setErro] = useState('');

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
      onFechar(await criarCiclo.mutateAsync({ ordem: n, vestibular }));
    } catch (e) {
      setErro((e as Error).message || 'Falha ao criar ciclo.');
    }
  }

  return (
    <Dialogo
      titulo="Novo ciclo"
      subtitulo="Cria o Assignment Group no Canvas junto"
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

      <Campo label="Vai criar no Canvas:">
        <code className="agendar__preview-nome">{`${ordem || '?'}° CICLO - ${vestibular}`}</code>
      </Campo>

      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
