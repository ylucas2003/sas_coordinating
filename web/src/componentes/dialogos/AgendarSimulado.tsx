import { useEffect, useMemo, useRef, useState } from 'react';
import { Campo, Dialogo, Linha2 } from './Dialogo';
import { useMaterias } from '../../hooks/consultas';
import { useAgendarSimulado } from '../../hooks/mutacoes';
import type { Ciclo, Simulado } from '../../tipos/dominio';
import { fmtDataBR } from '../../util/data';

// Diálogo do agendamento (P1). O simulado nasce no SAS e o backend cria o
// Assignment no Canvas.
//
// O preview do nome não é enfeite — é a única forma de o coordenador ver que
// SAS e Canvas vão falar a mesma língua ANTES de criar. O nome é derivado de
// (ciclo, rótulo, matéria, data); nunca digitado.

/** Espelho de `compor_nome_assignment` (api/app/canvas_sync/mapeador.py). */
function previewNome(cicloOrdem: string, rotulo: string, materiaNome: string | undefined, dataISO: string) {
  const data = dataISO ? fmtDataBR(dataISO) : '__/__/____';
  return `${cicloOrdem}_${rotulo || 'P?'} - ${materiaNome || '…'} - ${data}`;
}

interface Props {
  ciclos: readonly Ciclo[];
  onFechar: (criado: Simulado | null) => void;
}

export function AgendarSimulado({ ciclos, onFechar }: Props) {
  const { data: materias = [], isError: erroMaterias } = useMaterias();
  const agendar = useAgendarSimulado();
  const refRotulo = useRef<HTMLInputElement>(null);

  // Só ciclos do ano mais recente fazem sentido para agendar.
  const opcoes = useMemo(() => {
    const anoMax = Math.max(...ciclos.map((c) => c.anoLetivo || 0));
    return ciclos.filter((c) => c.anoLetivo === anoMax).sort((a, b) => (a.nome > b.nome ? 1 : -1));
  }, [ciclos]);

  const [cicloId, setCicloId] = useState(() => opcoes[0]?.id ?? '');
  const [rotulo, setRotulo] = useState('');
  const [materiaId, setMateriaId] = useState('');
  const [data, setData] = useState('');
  const [hora, setHora] = useState('07:00');
  const [questoes, setQuestoes] = useState('');
  const [tipo, setTipo] = useState('fase_2');
  const [lembrete, setLembrete] = useState(false);
  const [lembreteDias, setLembreteDias] = useState('3');
  // Marcado por default: o lembrete de aluno é automático (P3, docs/13 §1).
  // Desmarcar é a exceção — "esta prova não avisa ninguém".
  const [avisarAlunos, setAvisarAlunos] = useState(true);
  // A escolha do coordenador (docs/18 §2.1). Default ligado: o caso comum é
  // querer a prova no Canvas; desligar é a exceção consciente.
  const [sincronizarCanvas, setSincronizarCanvas] = useState(true);
  const [erro, setErro] = useState('');

  useEffect(() => {
    refRotulo.current?.focus();
  }, []);

  const ciclo = opcoes.find((c) => c.id === cicloId) ?? opcoes[0];
  // "Ciclo 3 · ITA · 2026" → ordem 3. O payload de /ciclos não traz a ordem
  // separada; extraímos do nome padronizado.
  const ordem = ciclo ? (ciclo.nome.match(/\d+/)?.[0] ?? '?') : '?';
  const materiaNome = materias.find((m) => m.id === materiaId)?.nome;

  async function criar() {
    setErro('');
    const rotuloNorm = rotulo.trim().toUpperCase();
    const nQuestoes = parseInt(questoes, 10);
    const dias = parseInt(lembreteDias, 10);

    const problemas: string[] = [];
    if (!/^P\d+$/.test(rotuloNorm)) problemas.push('rótulo deve ser P<n> (ex.: P12)');
    if (!materiaId) problemas.push('escolha a matéria');
    if (!data) problemas.push('escolha a data');
    if (!nQuestoes || nQuestoes < 1) problemas.push('nº de questões inválido');
    if (lembrete && (Number.isNaN(dias) || dias < 0)) problemas.push('dias do lembrete inválido');
    if (problemas.length) {
      setErro(problemas.join(' · '));
      return;
    }

    try {
      const criado = await agendar.mutateAsync({
        cicloId,
        rotuloCurto: rotuloNorm,
        materiaId,
        dataAplicacao: data,
        hora: hora || '07:00',
        notaMaxima: nQuestoes,
        tipo,
        // `undefined` some do JSON — o backend só vê o campo se marcado.
        lembrarDiasAntes: lembrete ? dias : undefined,
        avisarAlunos,
        sincronizarCanvas,
      });
      onFechar(criado);
    } catch (e) {
      setErro((e as Error).message || 'Falha ao agendar.');
    }
  }

  return (
    <Dialogo
      titulo="Novo simulado"
      subtitulo={sincronizarCanvas ? 'Nasce no SAS e é criado no Canvas na hora' : 'Nasce só no SAS — o Canvas fica diferente'}
      onFechar={() => onFechar(null)}
      rodape={
        <>
          <button className="btn btn--ghost" onClick={() => onFechar(null)}>
            Cancelar
          </button>
          <button className="btn btn--primary" disabled={agendar.isPending} onClick={criar}>
            {agendar.isPending ? 'Criando…' : 'Agendar'}
          </button>
        </>
      }
    >
      <Campo label="Ciclo">
        <select className="dialog__input" value={cicloId} onChange={(e) => setCicloId(e.target.value)}>
          {opcoes.map((c) => (
            <option key={c.id} value={c.id}>{c.nome}</option>
          ))}
        </select>
      </Campo>

      <Linha2>
        <Campo label="Rótulo (Pn)">
          <input
            ref={refRotulo}
            className="dialog__input"
            placeholder="ex.: P12"
            maxLength={4}
            value={rotulo}
            onChange={(e) => setRotulo(e.target.value)}
          />
        </Campo>
        <Campo label="Matéria">
          <select className="dialog__input" value={materiaId} onChange={(e) => setMateriaId(e.target.value)}>
            <option value="">
              {erroMaterias ? 'erro ao carregar' : materias.length ? 'Escolha…' : 'Carregando…'}
            </option>
            {materias.map((m) => (
              <option key={m.id} value={m.id}>{m.nome}</option>
            ))}
          </select>
        </Campo>
      </Linha2>

      <Linha2>
        <Campo label="Data">
          <input type="date" className="dialog__input" value={data} onChange={(e) => setData(e.target.value)} />
        </Campo>
        <Campo label="Hora">
          <input type="time" className="dialog__input" value={hora} onChange={(e) => setHora(e.target.value)} />
        </Campo>
      </Linha2>

      <Linha2>
        <Campo label="Nº de questões">
          <input
            type="number" className="dialog__input" min="1" step="1" placeholder="ex.: 20"
            value={questoes} onChange={(e) => setQuestoes(e.target.value)}
          />
        </Campo>
        <Campo label="Tipo">
          <select className="dialog__input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
            <option value="fase_2">Fase 2 (matéria individual)</option>
            <option value="fase_1">Fase 1 (prova combinada)</option>
          </select>
        </Campo>
      </Linha2>

      <Linha2>
        <div className="dialog__campo">
          <label className="agendar__lembrete-check">
            <input type="checkbox" checked={lembrete} onChange={(e) => setLembrete(e.target.checked)} />
            Me lembrar por e-mail
          </label>
        </div>
        <Campo label="Dias antes (0 = no dia)">
          <input
            type="number" className="dialog__input" min="0" step="1"
            disabled={!lembrete}
            value={lembreteDias}
            onChange={(e) => setLembreteDias(e.target.value)}
          />
        </Campo>
      </Linha2>

      <div className="dialog__campo">
        <label className="agendar__lembrete-check agendar__lembrete-check--solo">
          <input type="checkbox" checked={avisarAlunos} onChange={(e) => setAvisarAlunos(e.target.checked)} />
          Avisar os alunos por e-mail na véspera
        </label>
        <span className="agendar__ajuda">
          Um e-mail por aluno às 18:00 do dia anterior, com todas as provas do dia.
        </span>
      </div>

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
            ? 'O Assignment é criado na hora. Se o Canvas falhar, fica marcado e tenta de novo sozinho.'
            : 'Fica só aqui, marcado como diferente do Canvas. Dá para enviar depois pelo botão do simulado.'}
        </span>
      </div>

      <Campo label={sincronizarCanvas ? 'Vai criar no Canvas:' : 'Nome do simulado:'}>
        <code className="agendar__preview-nome">
          {previewNome(ordem, rotulo.trim().toUpperCase(), materiaNome, data)}
        </code>
      </Campo>

      {erro && <div className="agendar__erro">{erro}</div>}
    </Dialogo>
  );
}
