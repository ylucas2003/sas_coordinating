import { useState } from 'react';
import { CamposNota, EscalaDaNota } from './CamposNota';
import type { TurmaDaProva } from './CamposNota';
import { DialogoComDiff } from './DialogoComDiff';
import type { Mudanca } from './DialogoComDiff';
import { leituraDaNota, useFormularioNota } from './formularioNota';
import type { ValoresNota } from './formularioNota';

// A FICHA DE NOTA — a única superfície de ESCRITA da coordenação.
//
// ⚠️ Aqui morreram os DOIS ÚLTIMOS ternários fixos do produto, e eles eram o
// caso mais puro da "régua dupla" que o sistema baniu:
//
//     toneNota     nota ≥ 7 → verde · ≥ 5 → âmbar · resto → vermelho
//     tonePosicao  top 15% → verde · metade superior → âmbar · resto → vermelho
//
// Cor decidida por número mágico, sem relação nenhuma com o corte da régua em
// vigor. Um aluno com 6,5 numa matéria de corte 4,0 está confortavelmente
// aprovado e aparecia em ÂMBAR; um com 4,5 no Inglês da Fase 1 do ITA está
// REPROVADO — lá o corte é 5,0 e elimina sozinho — e aparecia em âmbar também.
// E o diálogo abre POR CIMA de uma tabela que já segue as sete regras: o mesmo
// aluno, o mesmo número, duas linguagens visuais separadas por 200ms.
//
// ⚠️ Os SEIS KPIs soltos saíram junto. Posição, nota, acertos, média, top 15%
// e bottom 15% numa grade não comparavam nada — e comparar era o assunto. Eles
// viraram uma escala única de 0 a 10 (`EscalaDaNota`) onde a régua de ouro, a
// nuvem da turma em referência, as três marcas e a nota deste aluno são
// desenhadas juntas. Os do aluno são DADO; os da turma são REFERÊNCIA (R5).

export interface StatsNota {
  posicao: number | null;
  totalPresentes: number;
  nota: number | null;
  media: number | null;
  maiorNota?: number | null;
  mediaTop15: number | null;
  mediaBottom15: number | null;
  mediana?: number | null;
  /** As notas da turma, quando o servidor as manda: viram a nuvem da escala. */
  notas?: ReadonlyArray<number | null> | null;
}

interface Props {
  nomeAluno: string;
  nomeSimulado: string;
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  notaMaxima: number | null;
  stats: StatsNota | null;
  /** O corte desta matéria, já resolvido pelo servidor. Sem ele não há régua. */
  corte?: number | null;
  /** A matéria elimina sozinha (Inglês da F1 do ITA). Só muda o rótulo. */
  elimina?: boolean;
  onFechar: (valores: ValoresNota | null) => void;
}

/**
 * Ficha de nota: a escala com a régua, a turma e esta nota, mais a edição.
 * Fluxo: formulário → Salvar → diff → Confirmar.
 */
export function FichaNota({
  nomeAluno,
  nomeSimulado,
  pontuacaoAtual,
  presenteAtual,
  notaMaxima,
  stats,
  corte = null,
  elimina = false,
  onFechar,
}: Props) {
  const [mudancas, setMudancas] = useState<Mudanca[] | null>(null);
  const [valores, setValores] = useState<ValoresNota | null>(null);

  const form = useFormularioNota({ pontuacaoAtual, presenteAtual, notaMaxima, corte });

  // A turma só existe quando alguém já fez a prova. Sem n não há média,
  // percentil nem posição — e a escala diz isso em vez de desenhar marcas
  // inventadas. A régua continua desenhada, porque ela não depende da turma.
  const turma: TurmaDaProva | null =
    stats && stats.totalPresentes > 0
      ? {
          media: stats.media,
          mediaTop15: stats.mediaTop15,
          mediaBottom15: stats.mediaBottom15,
          notas: stats.notas ?? null,
        }
      : null;

  return (
    <DialogoComDiff
      titulo={nomeSimulado}
      subtitulo={nomeAluno}
      largo
      mudancas={mudancas}
      onCancelar={() => onFechar(null)}
      onVoltar={() => setMudancas(null)}
      canvas={{ efeito: 'atualiza a nota da submission do aluno no Canvas.' }}
      onConfirmar={(sincronizarCanvas) => onFechar(valores && { ...valores, sincronizarCanvas })}
      onSalvar={() => {
        const r = form.validar();
        if (r.tipo === 'invalido') return;
        if (r.tipo === 'sem-mudancas') return onFechar(null);
        setValores(r.valores);
        setMudancas(r.mudancas);
      }}
    >
      <CamposNota
        presente={form.presente}
        onPresenteChange={form.alterarPresenca}
        texto={form.texto}
        onTextoChange={form.setTexto}
        mensagem={form.mensagem}
        emFalta={form.emFalta}
        notaMaxima={notaMaxima}
        nota={form.nota}
      />

      <EscalaDaNota
        nota={form.nota}
        corte={corte}
        elimina={elimina}
        turma={turma}
        leitura={leituraDaNota({
          presente: form.presente,
          nota: form.nota,
          corte,
          elimina,
          media: stats?.media,
          posicao: stats?.posicao,
          totalPresentes: stats?.totalPresentes,
        })}
      />
    </DialogoComDiff>
  );
}
