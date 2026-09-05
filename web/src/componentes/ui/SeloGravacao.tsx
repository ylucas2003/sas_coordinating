import type { EstadoCanvasGravacao, GravacaoAula } from '../../tipos/dominio';
import {
  ROTULO_CANVAS,
  ROTULO_SITUACAO,
  type Situacao,
  esperaCanvas,
  foraDeModulo,
  situacaoDe,
} from '../../dominio/gravacoes';
import { type Procedencia, TarjaProcedencia } from './TarjaProcedencia';

/**
 * Os dois selos de uma gravação — molde de `SeloCanvas`.
 *
 * São dois porque os eixos são independentes: o vídeo pode estar no canal e
 * ainda não ter chegado à página da aula. Um selo só obrigaria a inventar uma
 * ordem entre eles, e a pergunta "já está no YouTube?" tem resposta diferente
 * de "o aluno já vê no Canvas?".
 *
 * Desde a fase 1 do docs/39 os dois desenham `TarjaProcedencia`, com a mesma
 * assinatura de antes. O que saiu foi o `tone-*`: `tone-verde` para publicado
 * e `tone-ambar` para os limbos eram o semáforo, e ele não existe mais. A
 * tradução de `tone` continua em `dominio/gravacoes.ts` porque a tarja de data
 * do card ainda a usa — quem parou de chamá-la foi só esta peça.
 */

/**
 * As cinco situações do vídeo colapsam em três procedências, e a redução é o
 * ponto: para "de onde veio isto?" só existem três respostas — já chegou,
 * ainda está vindo, ou quebrou no caminho. O DEGRAU da espera (na fila ×
 * processando × aguardando gravação) continua dito por extenso na fonte, que é
 * onde ele importa.
 */
const PROCEDENCIA_SITUACAO: Record<Situacao, Procedencia> = {
  aguardando: 'pendente',
  na_fila: 'pendente',
  processando: 'pendente',
  publicado: 'medido',
  erro: 'falhou',
};

/**
 * Os seis estados do Canvas em quatro procedências.
 *
 * `ambiguo`, `conflito` e `ignorado` viram DIVERGENTE pelo mesmo motivo:
 * nenhum é falha do SAS e nenhum vai se resolver sozinho — em todos os três o
 * vídeo existe de um lado e não existe do outro, deliberadamente. É a mesma
 * definição de `divergente` do `SeloCanvas`: "fica diferente mesmo".
 */
const PROCEDENCIA_CANVAS: Record<EstadoCanvasGravacao, Procedencia> = {
  pendente: 'pendente',
  publicado: 'medido',
  falhou: 'falhou',
  ambiguo: 'divergente',
  conflito: 'divergente',
  ignorado: 'divergente',
};

/**
 * `ROTULO_SITUACAO.erro` é "erro ao publicar", e com o olho dizendo FALHOU a
 * primeira palavra vira eco. Partido como no `SeloCanvas`, sobra o lado do
 * pipeline — que é justamente o que aquele rótulo existe para dizer (o
 * comentário dele está em `dominio/gravacoes.ts`). Os outros quatro rótulos já
 * nomeiam o lado sozinhos e passam intactos.
 */
const FONTE_DA_FALHA = 'ao publicar o vídeo';

export function SeloSituacao({ aula }: { aula: GravacaoAula }) {
  const s = situacaoDe(aula);
  return (
    <TarjaProcedencia
      estado={PROCEDENCIA_SITUACAO[s]}
      fonte={s === 'erro' ? FONTE_DA_FALHA : ROTULO_SITUACAO[s]}
      dica={aula.erroDetalhe || undefined}
    />
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
  // ela existe e toca, mas o aluno navega por módulo e não a encontra. É
  // DIVERGENTE e não uma falha — nada quebrou, e nada vai se arrumar sozinho.
  const orfa = publicaNoCanvas && foraDeModulo(aula);
  const fonte = orfa ? 'fora de módulo' : r.texto;
  const procedencia: Procedencia = orfa ? 'divergente' : PROCEDENCIA_CANVAS[estado];
  const dica = orfa
    ? aula.canvasErro || 'A página existe, mas não está em nenhum módulo — o aluno não a encontra.'
    : aula.canvasErro || r.titulo;

  const selo = <TarjaProcedencia estado={procedencia} fonte={fonte} dica={dica} />;

  // O elo é `.procedencia-elo` e não um `<a>` cru: a pílula tem 28px de altura
  // e o alvo de toque de 44px cresce por fora dela, num pseudo-elemento.
  return aula.canvasUrl ? (
    <a
      className="procedencia-elo"
      href={aula.canvasUrl}
      target="_blank"
      rel="noreferrer"
      onClick={(e) => e.stopPropagation()}
    >
      {selo}
    </a>
  ) : (
    selo
  );
}
