import type { EstadoCanvasGravacao, GravacaoAula } from '../../tipos/dominio';
import {
  ROTULO_CANVAS,
  ROTULO_SITUACAO,
  esperaCanvas,
  foraDeModulo,
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

export function SeloCanvasGravacao({
  aula,
  publicaNoCanvas = true,
}: {
  aula: GravacaoAula;
  /** O interruptor do curso. Desligado, a aula fica `pendente` no banco para
      poder ser publicada quando alguém ligar — mas prometer "a publicar" aqui
      seria mentira, porque nada vai acontecer enquanto o curso estiver assim. */
  publicaNoCanvas?: boolean;
}) {
  // Sem vídeo não há o que embutir: um selo aqui sugeriria pendência do Canvas
  // quando quem está devendo é o pipeline do vídeo.
  if (!esperaCanvas(aula)) return null;

  const estado: EstadoCanvasGravacao = publicaNoCanvas ? aula.canvasEstado : 'ignorado';
  const r = ROTULO_CANVAS[estado];
  if (!r) return null;

  // "na página do Canvas" seria meia verdade para uma página fora de módulo:
  // ela existe e toca, mas o aluno navega por módulo e não a encontra.
  const orfa = publicaNoCanvas && foraDeModulo(aula);
  const texto = orfa ? 'fora de módulo' : r.texto;
  const tone = orfa ? 'tone-ambar' : toneCanvas(estado);
  const dica = orfa
    ? aula.canvasErro || 'A página existe, mas não está em nenhum módulo — o aluno não a encontra.'
    : aula.canvasErro || r.titulo;

  const selo = (
    <span className={`tag ${tone}`} title={dica}>
      {texto}
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
