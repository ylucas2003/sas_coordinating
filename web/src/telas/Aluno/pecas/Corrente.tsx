import type { EloDaCorrente } from '../../../dados/aluno';
import { fmtDataCurta } from './formato';

// A corrente da sequência: UM QUADRADO POR SIMULADO, nunca por dia da semana.
//
// A mudança não é cosmética. Não existe nenhuma atividade DIÁRIA verificável no
// SAS — `questao_estudo_aluno.resolvida` é autodeclarado e `aluno_modulo_progresso`
// nunca foi sincronizada do Canvas (docs/26 §1). O único evento verificado é o
// simulado, a cada ~3 semanas. Uma corrente de dias premiaria o que ninguém
// consegue conferir.
//
// Três estados, e o vazado é o que dá peso ao resto:
//   preenchido  compareceu   (`nota.presente = true`)
//   vazado      faltou       — e é justamente o quadrado que faz a sequência doer
//   anelado     ainda não aconteceu
//
// ⚠️ Hoje o vazado não tem fonte: `simulados_do_aluno` filtra `presente = true`
// e descarta a falta, então do lado do aluno a falta é invisível (docs/29 §A.2).
// O componente já sabe desenhá-la; falta a rota.

export function Corrente({ elos, tamanho = 26 }: { elos: EloDaCorrente[]; tamanho?: number }) {
  return (
    <ol className="alu-corrente" style={{ '--elo': `${tamanho}px` } as React.CSSProperties}>
      {elos.map((elo, i) => {
        const classe =
          elo.presente === true
            ? 'alu-elo alu-elo--presente'
            : elo.presente === false
              ? 'alu-elo alu-elo--falta'
              : 'alu-elo alu-elo--proximo';

        const situacao =
          elo.presente === true ? 'compareceu' : elo.presente === false ? 'faltou' : 'ainda não';

        return (
          <li
            // O rótulo se repete entre ciclos ("P1" do ciclo 4 e do 5), então a
            // chave leva o índice junto — sem ele o React reusaria o nó errado.
            key={`${elo.simuladoId ?? 'futuro'}-${i}`}
            className={classe}
            title={`${elo.rotulo} · ${fmtDataCurta(elo.data)} · ${situacao}`}
          >
            <span className="alu-elo__rotulo">{elo.rotulo}</span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * A leitura da sequência em uma linha. Existe separada da corrente porque a
 * corrente aparece sozinha no login e no rodapé, sem espaço para o texto.
 *
 * "12 SIMULADOS SEM FALTAR" — nunca "ofensiva", que é a tradução brasileira do
 * Duolingo, e nunca "dias".
 */
export function LeituraDaSequencia({
  simulados,
  melhor,
}: {
  simulados: number;
  melhor: number;
}) {
  if (simulados === 0) {
    return (
      <span className="alu-sequencia__leitura">
        Sua sequência começa no próximo simulado.
      </span>
    );
  }
  return (
    <span className="alu-sequencia__leitura">
      {simulados === 1 ? '1 simulado sem faltar' : `${simulados} simulados sem faltar`}
      {melhor > simulados && (
        <em className="alu-sequencia__recorde"> · seu recorde é {melhor}</em>
      )}
      {melhor === simulados && simulados > 1 && (
        <em className="alu-sequencia__recorde"> · é o seu recorde</em>
      )}
    </span>
  );
}
