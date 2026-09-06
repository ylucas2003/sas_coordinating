import { useEffect, useId, useRef } from 'react';
import { rotuloDoCorte } from '../../dominio/criterios';
import { seloDaNota } from '../../dominio/selo';
import { fmtNota } from '../../util/formato';

// O corpo do passo 1 do diálogo de nota: o estado do registro, a pontuação e a
// escala em que a régua, a turma e esta nota são desenhadas juntas.
//
// Era só "checkbox de presença + campo de pontuação". As três mudanças vêm da
// prancheta "Diálogo de nota" (docs/39 §Fase 3):
//
//   · A PRESENÇA deixou de ser caixinha. Ausência e zero são coisas diferentes
//     no domínio e a diferença é a que mais deturpa média — a um clique
//     distraído de distância. Viraram dois estados do registro, com a
//     consequência escrita dentro do próprio botão.
//   · A CONVERSÃO ficou à vista: digita-se bruto e a nota de 0 a 10 anda ao
//     lado, enquanto se digita.
//   · A RÉGUA entrou. R2 vale aqui mais do que em qualquer tela de leitura:
//     este é o único lugar do produto onde uma nota é ESCRITA.

interface Props {
  presente: boolean;
  onPresenteChange: (v: boolean) => void;
  texto: string;
  onTextoChange: (v: string) => void;
  /** A frase sob o campo. `''` quando não há nada a dizer. */
  mensagem: string;
  /** A frase é falha, e não guia: aí o campo ganha o traço de alerta (R4). */
  emFalta: boolean;
  /** O número de questões da prova. `null` quando o servidor não o tem. */
  notaMaxima: number | null;
  /** O que a pontuação digitada vale em 0–10, agora. */
  nota: number | null;
}

/** Estado do registro + pontuação. */
export function CamposNota({
  presente,
  onPresenteChange,
  texto,
  onTextoChange,
  mensagem,
  emFalta,
  notaMaxima,
  nota,
}: Props) {
  const idPontuacao = useId();
  const idMensagem = useId();
  const refPontuacao = useRef<HTMLInputElement>(null);
  const refAusente = useRef<HTMLButtonElement>(null);

  // Foca o campo que a pessoa provavelmente quer mexer: a pontuação quando o
  // aluno está presente, o botão de ausente quando não está.
  // Só na montagem: com `presente` na lista, cada troca roubaria o foco de
  // quem está digitando.
  // biome-ignore lint/correctness/useExhaustiveDependencies: só na montagem
  useEffect(() => {
    if (presente) refPontuacao.current?.focus();
    else refAusente.current?.focus();
  }, []);

  // Campo em falta: devolve o foco para quem precisa ser corrigido. Quando a
  // falta apareceu enquanto se digitava, o foco já está lá e isto é inócuo —
  // o caso que importa é o da tentativa de salvar a partir do rodapé.
  useEffect(() => {
    if (emFalta) refPontuacao.current?.focus();
  }, [emFalta]);

  return (
    <>
      {/* `fieldset`/`legend` e não `div role="group"`: são dois controles de
          um mesmo campo, que é exatamente o que o elemento nativo significa —
          e o leitor de tela anuncia a legenda ao entrar em cada opção, sem
          depender de um `aria-labelledby` que alguém precisa manter vivo. */}
      <fieldset className="dialog__campo dialog__campo--grupo">
        <legend className="dialog__olho">Presença · estado do registro</legend>
        <div className="dialog-presenca">
          <OpcaoDePresenca
            ativa={presente}
            rotulo="Fez a prova"
            consequencia="a nota conta na média da turma e no ranking"
            onEscolher={() => onPresenteChange(true)}
          />
          <OpcaoDePresenca
            ref={refAusente}
            ativa={!presente}
            rotulo="Ausente"
            consequencia="não conta na média, e não é zero"
            onEscolher={() => onPresenteChange(false)}
          />
        </div>
      </fieldset>

      <div className="dialog__campo">
        <div className="dialog-pontuacao__topo">
          <label className="dialog__olho" htmlFor={idPontuacao}>
            Pontuação
          </label>
          {notaMaxima != null && (
            <span className="dialog-pontuacao__maximo">máximo {fmtBruto(notaMaxima)}</span>
          )}
        </div>

        <div className="dialog-pontuacao">
          <input
            ref={refPontuacao}
            id={idPontuacao}
            type="number"
            inputMode="decimal"
            className={`dialog-pontuacao__campo${emFalta ? ' dialog-pontuacao__campo--falta' : ''}`}
            min="0"
            max={notaMaxima ?? undefined}
            step="0.5"
            placeholder="—"
            /* Ausente NÃO zera o campo: ele fica visível e desabilitado, para
               quem trocou por engano ver o que tinha antes de confirmar. */
            disabled={!presente}
            value={texto}
            onChange={(e) => onTextoChange(e.target.value)}
            aria-describedby={mensagem ? idMensagem : undefined}
            aria-invalid={emFalta || undefined}
          />
          <span className="dialog-pontuacao__unidade">
            {notaMaxima != null ? `de ${fmtBruto(notaMaxima)} questões` : 'pontuação bruta'}
          </span>
          <div className="dialog-pontuacao__nota">
            <div className="dialog-pontuacao__nota-valor">{nota == null ? '—' : fmtNota(nota)}</div>
            <div className="dialog__olho">Nota de 0 a 10</div>
          </div>
        </div>

        {mensagem && (
          <p
            id={idMensagem}
            className={`dialog-pontuacao__mensagem${emFalta ? ' dialog-pontuacao__mensagem--falta' : ''}`}
          >
            {mensagem}
          </p>
        )}
      </div>
    </>
  );
}

/** Um dos dois estados do registro. Botão, não caixinha — ver o topo do arquivo. */
function OpcaoDePresenca({
  ativa,
  rotulo,
  consequencia,
  onEscolher,
  ref,
}: {
  ativa: boolean;
  rotulo: string;
  consequencia: string;
  onEscolher: () => void;
  ref?: React.Ref<HTMLButtonElement>;
}) {
  return (
    <button
      ref={ref}
      type="button"
      className={`dialog-presenca__opcao${ativa ? ' is-ativa' : ''}`}
      aria-pressed={ativa}
      onClick={onEscolher}
    >
      <span className="dialog-presenca__rotulo">{rotulo}</span>
      <span className="dialog-presenca__consequencia">{consequencia}</span>
    </button>
  );
}

/** O que o servidor sabe da turma nesta prova. Tudo opcional: sem n, sem média. */
export interface TurmaDaProva {
  media: number | null;
  mediaTop15: number | null;
  mediaBottom15: number | null;
  /** As notas da turma, para a nuvem. Sem elas ficam só as três marcas. */
  notas?: ReadonlyArray<number | null> | null;
}

/**
 * A escala de 0 a 10 onde a régua, a turma e esta nota se leem juntas.
 *
 * Substitui os seis KPIs soltos — posição, nota, acertos, média, top 15% e
 * bottom 15% numa grade. Comparar era o assunto, e seis números lado a lado
 * não comparavam nada: o olho não converte "4,6" e "7,0" em distância. Aqui os
 * três da turma são REFERÊNCIA, cinza e atrás (R5); o desta nota é DADO, e é o
 * mesmo chip que a tabela por baixo do diálogo desenha — mesma nota, mesma
 * forma, mesmo vocabulário, que é o que o semáforo daqui quebrava.
 *
 * O desenho é `aria-hidden`: quem carrega o mesmo conteúdo para o leitor de
 * tela é a `leitura`, que fica visível logo abaixo.
 */
export function EscalaDaNota({
  nota,
  corte,
  elimina = false,
  turma,
  leitura,
}: {
  nota: number | null;
  corte: number | null;
  elimina?: boolean;
  turma: TurmaDaProva | null;
  leitura: string;
}) {
  const selo = seloDaNota(nota, corte);
  // Sem `as const`: com ele o rótulo vira tipo literal e o predicado de
  // estreitamento deixa de ser atribuível ao elemento. A marca é opcional uma
  // a uma — uma prova recém-lançada pode ter média e não ter os percentis.
  const marcas: Array<[string, number]> = [];
  if (turma) {
    const candidatas: Array<[string, number | null]> = [
      ['bottom 15%', turma.mediaBottom15],
      ['média', turma.media],
      ['top 15%', turma.mediaTop15],
    ];
    for (const [rotulo, valor] of candidatas) {
      if (valor != null) marcas.push([rotulo, valor]);
    }
  }

  const nuvem = (turma?.notas ?? []).filter((n): n is number => n != null);

  return (
    <div className="dialog-escala">
      <div className="dialog-escala__topo">
        <span className="dialog__olho">A turma, a régua e esta nota</span>
        {corte != null && (
          <span className="dialog-escala__corte-rotulo">{rotuloDoCorte(corte, elimina)}</span>
        )}
      </div>

      {!turma && (
        <p className="dialog-escala__sem-turma">
          A prova ainda não tem estatística de turma: sem n não há média, percentil nem posição. A
          régua continua desenhada, porque ela não depende da turma.
        </p>
      )}

      <div className="dialog-escala__plano" aria-hidden="true">
        <div className="dialog-escala__pista">
          {/* A nuvem é a turma inteira, e ela é referência: cinza, miúda e
              atrás de tudo. Só aparece quando quem chama tem as notas — sem
              elas ficam as três marcas, que é a mesma comparação resumida. */}
          {nuvem.map((n, i) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: ponto sem identidade própria
              key={i}
              className="dialog-escala__ponto"
              style={{ left: pct(n), top: `${(i * 7) % 18}px` }}
            />
          ))}

          {marcas.map(([rotulo, valor]) => (
            <span key={rotulo} className="dialog-escala__marca" style={{ left: pct(valor) }}>
              <span className="dialog-escala__marca-rotulo">
                {rotulo} {fmtNota(valor)}
              </span>
            </span>
          ))}

          <span className="dialog-escala__eixo" />

          {corte != null && (
            <>
              {/* A régua é OURO e está sempre desenhada, rotulada (R2). Ela é a
                  única coisa desta escala que não depende da turma existir. */}
              <span className="dialog-escala__corte" style={{ left: pct(corte) }} />
              <span className="dialog-escala__corte-tag" style={{ left: pct(corte) }}>
                corte {fmtNota(corte)}
              </span>
            </>
          )}

          {nota != null && (
            <span className="dialog-escala__nota" style={{ left: pct(nota) }}>
              <span
                className={`nota-badge${classeDoSelo(selo.estado, selo.intensidade)}`}
                style={{ '--nota-intensidade': selo.intensidade } as React.CSSProperties}
              >
                {fmtNota(nota)}
              </span>
              {selo.etiqueta && <span className="nota-etiqueta">{selo.etiqueta}</span>}
            </span>
          )}
        </div>

        <div className="dialog-escala__extremos">
          <span>0</span>
          <span>10</span>
        </div>
      </div>

      {leitura && <p className="dialog-escala__leitura">{leitura}</p>}
    </div>
  );
}

/** 0–10 → posição na pista, em porcentagem. Fora da escala encosta na ponta. */
function pct(valor: number): string {
  return `${(Math.max(0, Math.min(10, valor)) / 10) * 100}%`;
}

/** As classes do chip, iguais às da tabela — a tradução mora em `ciclo.css`. */
function classeDoSelo(estado: string, intensidade: number): string {
  if (estado === 'sem-dado') return '';
  const forte = estado === 'acima' && intensidade > 0.5 ? ' nota-badge--acima-forte' : '';
  return ` nota-badge--${estado}${forte}`;
}

/** "20" · vírgula decimal, para o meio-ponto não virar "20.5". */
function fmtBruto(n: number): string {
  return String(n).replace('.', ',');
}
