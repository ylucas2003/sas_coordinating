import { useId, useState } from 'react';

import { InsightsPainel } from './InsightsPainel';

/**
 * O mesmo gráfico, legível em três profundidades (docs/31 §P5).
 *
 *   leigo       — uma frase que diz o que o desenho mostra, e o desenho limpo
 *   insight     — a leitura do sistema sobre aquele recorte (LLM, `insight_ciclo`)
 *   estatística — o desenho com tudo ligado, mais quantis e leitura técnica
 *
 * Por que o controle é POR GRÁFICO e não um interruptor global (decisão de
 * 30/08): dois gráficos lado a lado em profundidades diferentes é o uso
 * normal — comparar a distribuição crua de um com a leitura do outro. Um
 * interruptor global tornaria isso impossível para ganhar uma preferência que
 * ninguém pediu.
 *
 * A ficha do ciclo já tinha esta ideia em escala de PÁGINA ("mostrar dados
 * estatísticos avançados"); aqui ela desce para o gráfico. O acordeão de lá
 * continua existindo porque leva também tabelas, que não são gráfico.
 */

export type Camada = 'leigo' | 'insight' | 'estatistica';

const DEGRAUS: Array<{ camada: Camada; rotulo: string; ajuda: string }> = [
  { camada: 'leigo', rotulo: 'Resumo', ajuda: 'O que o gráfico mostra, em uma frase' },
  { camada: 'insight', rotulo: 'Leitura', ajuda: 'O que o sistema concluiu deste recorte' },
  { camada: 'estatistica', rotulo: 'Estatística', ajuda: 'Quantis, dispersão e forma da distribuição' },
];

interface Props {
  titulo?: string;
  legenda?: string;
  /** A frase da camada leigo. `null` = a camada existe, sem frase a dizer. */
  frase?: string | null;
  /** Bullets do `insight_ciclo` (prático). `null` = ainda carregando. */
  insight?: string[] | null;
  /** Bullets técnicos, exibidos na camada mais funda. */
  insightTecnico?: string[] | null;
  /** O desenho. Recebe a camada para ligar KDE, eixo absoluto e afins. */
  grafico: (camada: Camada) => React.ReactNode;
  /** Números que só fazem sentido na camada mais funda (quantis, desvio). */
  estatistica?: React.ReactNode;
  /** Camada de abertura. `leigo` salvo quando quem chama sabe o contrário. */
  inicial?: Camada;
}

export function GraficoEmCamadas({
  titulo, legenda, frase, insight, insightTecnico, grafico, estatistica, inicial = 'leigo',
}: Props) {
  const idPainel = useId();
  const idAba = (c: Camada) => `${idPainel}-${c}`;

  // Degrau que não acrescenta nada não aparece. O botão "Estatística" promete
  // "quantis, dispersão e forma da distribuição" no `title`; onde quem chama
  // não passa `estatistica` nem `insightTecnico`, clicar nele só apagava a
  // frase — o degrau virava uma casca. `insight` em `null` ou `[]` CONTINUA
  // valendo: são "carregando" e "indisponível", que o InsightsPainel sabe
  // desenhar; o que some é o degrau que ninguém alimentou (`undefined`).
  const disponiveis = DEGRAUS.filter((d) => {
    if (d.camada === 'insight') return insight !== undefined;
    if (d.camada === 'estatistica') return estatistica != null || !!insightTecnico?.length;
    return true;
  });

  const [camada, setCamada] = useState<Camada>(inicial);
  const ativa = disponiveis.some((d) => d.camada === camada) ? camada : 'leigo';

  // ←/→/Home/End é o gesto que o papel `tablist` anuncia ao leitor de tela.
  // Sem ele, o componente promete uma interação que não existe.
  function aoTeclar(ev: React.KeyboardEvent) {
    const i = disponiveis.findIndex((d) => d.camada === ativa);
    const destino =
      ev.key === 'ArrowRight' ? (i + 1) % disponiveis.length
      : ev.key === 'ArrowLeft' ? (i - 1 + disponiveis.length) % disponiveis.length
      : ev.key === 'Home' ? 0
      : ev.key === 'End' ? disponiveis.length - 1
      : -1;
    if (destino < 0) return;
    ev.preventDefault();
    setCamada(disponiveis[destino].camada);
    document.getElementById(idAba(disponiveis[destino].camada))?.focus();
  }

  return (
    <div className="camadas">
      <div className="camadas__topo">
        <div className="camadas__titulo-bloco">
          {titulo && <div className="camadas__titulo">{titulo}</div>}
          {legenda && <p className="camadas__legenda">{legenda}</p>}
        </div>

        {/* `tablist` e não um grupo de botões soltos: os degraus controlam a
            MESMA região, e é isso que o leitor de tela precisa ouvir para
            entender que trocar um troca o conteúdo abaixo. Com um degrau só
            não há o que alternar, e o papel some junto. */}
        {disponiveis.length > 1 && (
          <div
            className="camadas__degraus"
            role="tablist"
            aria-label="Profundidade da leitura"
            onKeyDown={aoTeclar}
          >
            {disponiveis.map((d) => (
              <button
                key={d.camada}
                id={idAba(d.camada)}
                type="button"
                role="tab"
                className={`camadas__degrau${ativa === d.camada ? ' is-ativo' : ''}`}
                aria-selected={ativa === d.camada}
                aria-controls={idPainel}
                // Roving tabindex: o Tab entra e sai do grupo inteiro numa
                // parada, e as setas movem dentro dele.
                tabIndex={ativa === d.camada ? 0 : -1}
                title={d.ajuda}
                onClick={() => setCamada(d.camada)}
              >
                {d.rotulo}
              </button>
            ))}
          </div>
        )}
      </div>

      <div
        className="camadas__painel"
        id={idPainel}
        role="tabpanel"
        aria-labelledby={disponiveis.length > 1 ? idAba(ativa) : undefined}
      >
        {ativa === 'leigo' && frase && <p className="camadas__frase">{frase}</p>}

        <div className="camadas__grafico">{grafico(ativa)}</div>

        {ativa === 'insight' && (
          <InsightsPainel
            bullets={insight ?? []}
            titulo="Leitura do sistema"
            legenda="Gerada automaticamente a partir dos números deste recorte."
          />
        )}

        {ativa === 'estatistica' && (
          <>
            {estatistica}
            {insightTecnico && insightTecnico.length > 0 && (
              <InsightsPainel
                bullets={insightTecnico}
                titulo="Leitura técnica"
                legenda="Mesma análise, com o vocabulário estatístico."
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
