import type { EstadoCanvasGravacao, GravacaoAula } from '../../tipos/dominio';
import {
  ROTULO_CANVAS,
  ROTULO_SITUACAO,
  esperaCanvas,
  situacaoDe,
  toneCanvas,
  toneSituacao,
} from '../../dominio/gravacoes';

/**
 * Os dois selos de uma gravação — molde de `SeloCanvas`.
 *
 * São dois porque os eixos são independentes: o vídeo pode estar no canal e
 * ainda não ter chegado à página da aula. Um selo só obrigaria a inventar uma
 * ordem entre eles, e a pergunta "já está no YouTube?" tem resposta diferente
 * de "o aluno já vê no Canvas?".
 */

export function SeloSituacao({ aula }: { aula: GravacaoAula }) {
  const s = situacaoDe(aula);
  return (
    <span className={`tag ${toneSituacao(s)}`} title={aula.erroDetalhe || undefined}>
      {ROTULO_SITUACAO[s]}
    </span>
  );
}

export function SeloCanvasGravacao({ aula }: { aula: GravacaoAula }) {
  // Sem vídeo não há o que embutir: um selo aqui sugeriria pendência do Canvas
  // quando quem está devendo é o pipeline do vídeo.
  if (!esperaCanvas(aula)) return null;

  const estado: EstadoCanvasGravacao = aula.canvasEstado;
  const r = ROTULO_CANVAS[estado];
  if (!r) return null;

  const selo = (
    <span className={`tag ${toneCanvas(estado)}`} title={aula.canvasErro || r.titulo}>
      {r.texto}
    </span>
  );

  return aula.canvasUrl ? (
    <a href={aula.canvasUrl} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
      {selo}
    </a>
  ) : (
    selo
  );
}
