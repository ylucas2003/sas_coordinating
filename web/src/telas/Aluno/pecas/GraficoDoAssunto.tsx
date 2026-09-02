import { useEffect, useMemo, useRef } from 'react';

import type { SerieDoAssunto } from '../../../dominio/serieDoAssunto';
import { rotuloDaSerie } from '../../../dominio/serieDoAssunto';

// A série anual de um assunto, uma linha por vestibular. SVG à mão, sem
// biblioteca — é convenção do projeto (docs/22 §P4: "SVG à mão, sem Chart.js"),
// e a razão original continua valendo: biblioteca de gráfico é terceiro na
// página, e aqui são dados de menores de idade (CLAUDE.md, regra 6).
//
// É um FORK de `componentes/ui/LinhaTemporal.tsx`, e o fork é de forma, não de
// preguiça. Aquele componente serve a coordenação e desenha UMA série mais uma
// comparação, as duas no MESMO domínio de x, com eixo 0–10 de nota. Aqui são
// duas séries com domínios DIFERENTES — o acervo do IME começa em 1996 e o do
// ITA em 2008 (migration 0031) —, e é justamente essa diferença que o gráfico
// precisa mostrar. Encaixar isso lá mudaria o comportamento de um componente
// que a coordenação usa, que é o que este projeto proíbe.
//
// ⚠️ COR NÃO É O ÚNICO DIFERENCIADOR. ITA e IME são dois valores do mesmo azul
// (`--alu-dado` e `--alu-dado-claro`), porque cor é papel e o sistema não tem
// outro papel para isto. Então a segunda pista é a FORMA: ITA é linha cheia com
// ponto preenchido, IME é tracejada com ponto vazado. Quem não distingue os dois
// azuis continua distinguindo as duas séries.
//
// ⚠️ A LINHA COMEÇA ONDE HÁ DADO. Nenhuma série é estendida com zeros até o
// começo do eixo: desenhar o ITA em zero antes de 2008 AFIRMA que o assunto não
// caía no ITA, quando a verdade é que não temos a prova. O período descoberto é
// declarado sob o eixo, em palavras.

/** Largura mínima da coluna de um ano — que é o alvo de toque (docs/20 §1.3).
 *
 *  Um ponto de 3,5px de raio não é alvo de nada. Quem recebe o toque é a coluna
 *  inteira do ano, e ela não pode ser mais estreita que o dedo. Trinta anos a
 *  44px dão um gráfico largo, e é por isso que ele rola DENTRO do próprio
 *  contêiner — o corpo da página nunca rola na horizontal. */
const PASSO_MINIMO = 44;

/** Largura da coluna do eixo Y, que fica FORA da área que rola. Dentro dela,
 *  os rótulos "0%" e "8%" saíam da tela junto com os anos antigos — e um
 *  gráfico sem escala visível não se lê. */
const EIXO_Y = 40;

const MARGEM = { esquerda: 10, direita: 16, topo: 16, base: 52 };
const ALTURA = 210;

interface Props {
  nome: string;
  /** Só as séries que CARREGARAM. Série ausente por erro é declarada pela tela,
   *  nunca passada aqui como zeros. */
  series: (SerieDoAssunto | null)[];
  /** Toque numa coluna de ano — abre o banco naquele ano. */
  onAno?: (ano: number) => void;
}

export function GraficoDoAssunto({ nome, series, onAno }: Props) {
  const carregadas = useMemo(
    () => series.filter((s): s is SerieDoAssunto => s !== null),
    [series],
  );

  const desenho = useMemo(() => montar(carregadas), [carregadas]);
  const trilho = useRef<HTMLDivElement>(null);

  // Abre no ano MAIS RECENTE, e não em 1996.
  //
  // O eixo tem trinta anos a 44px, então a abertura à esquerda deixaria o aluno
  // a três telas de rolagem do ano que ele veio ver — e as primeiras colunas do
  // IME são justamente as mais esparsas do acervo. O período sem acervo não se
  // perde nisso: ele saiu de dentro do SVG e virou texto fixo abaixo do
  // gráfico, que não rola junto.
  const larguraDoDesenho = desenho?.largura;
  useEffect(() => {
    const alvo = trilho.current;
    if (!alvo || larguraDoDesenho == null) return;
    alvo.scrollLeft = alvo.scrollWidth;
  }, [larguraDoDesenho]);

  if (!desenho) return null;

  const { largura, anos, x, y, teto, grades, eixoY, formatar } = desenho;

  return (
    <div className="alu-serie">
      <div className="alu-serie__quadro">
        {/* O eixo Y, ancorado. Mesma altura e mesmas linhas do gráfico ao lado,
            para os rótulos casarem com a grade — é por isso que ele repete o
            `y()` em vez de posicionar por CSS. */}
        <svg
          className="alu-serie__eixo"
          viewBox={`0 0 ${EIXO_Y} ${ALTURA}`}
          width={EIXO_Y}
          height={ALTURA}
          aria-hidden="true"
        >
          {grades.map((valor) => (
            <text
              key={valor}
              x={EIXO_Y - 6}
              y={y(valor)}
              textAnchor="end"
              dominantBaseline="middle"
              fontSize="11"
              fill="var(--alu-texto-2)"
            >
              {formatar(valor)}
            </text>
          ))}
        </svg>

        {/* O contêiner rola; a página não. Regra de mobile do projeto. */}
        <div className="alu-serie__trilho" ref={trilho}>
        <svg
          className="alu-serie__svg"
          viewBox={`0 0 ${largura} ${ALTURA}`}
          style={{ minWidth: `${largura}px` }}
          role="img"
          aria-label={rotuloDaSerie(nome, series)}
        >
          <title>{rotuloDaSerie(nome, series)}</title>

          {grades.map((valor) => (
            <line
              key={valor}
              x1={0}
              y1={y(valor)}
              x2={largura}
              y2={y(valor)}
              stroke="var(--alu-borda)"
            />
          ))}

          {/* A hachura do período descoberto, sob o eixo. A FRASE que a explica
              fica fora do SVG (abaixo), porque aqui dentro ela rolaria para
              fora da tela justamente quando o aluno estivesse olhando os anos
              recentes — e é aí que ela precisa continuar visível. */}
          {desenho.lacunas.map((lacuna) => (
            <rect
              key={lacuna.vestibular}
              x={x(lacuna.de)}
              y={eixoY + 8}
              width={Math.max(1, x(lacuna.ate) - x(lacuna.de))}
              height="7"
              fill="none"
              stroke="var(--alu-borda)"
            />
          ))}

          {carregadas.map((serie) => {
            const ita = serie.vestibular === 'ITA';
            const cor = ita ? 'var(--alu-dado)' : 'var(--alu-dado-claro)';
            // ⚠️ A LINHA SE PARTE ONDE NÃO HOUVE PROVA. O acervo do IME pula
            // 1997, 2000, 2001 e 2003, e ligar 1996 direto a 1998 desenharia um
            // segmento passando por cima de um ano sobre o qual não sabemos
            // nada — afirmando um valor que ninguém mediu. Ano sem prova não é
            // zero e também não é interpolação: é buraco, e buraco se mostra.
            const caminho = serie.pontos
              .map((p, i) => {
                const anterior = serie.pontos[i - 1];
                const contiguo = anterior && p.ano - anterior.ano === 1;
                return `${contiguo ? 'L' : 'M'}${x(p.ano).toFixed(1)} ${y(p.valor).toFixed(1)}`;
              })
              .join(' ');
            return (
              <g key={serie.vestibular}>
                <path
                  d={caminho}
                  fill="none"
                  stroke={cor}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeDasharray={ita ? undefined : '5 4'}
                />
                {serie.pontos.map((p) => (
                  <circle
                    key={p.ano}
                    cx={x(p.ano)}
                    cy={y(p.valor)}
                    r="3.5"
                    fill={ita ? cor : 'var(--alu-fundo)'}
                    stroke={cor}
                    strokeWidth="2"
                  />
                ))}
              </g>
            );
          })}

          {/* A coluna inteira do ano é o alvo. Cada uma anuncia o valor CRU de
              cada banca — o número que existe, não a média móvel do desenho. */}
          {anos.map((ano) => (
            <rect
              key={ano}
              className="alu-serie__coluna"
              x={x(ano) - desenho.passo / 2}
              y={MARGEM.topo}
              width={desenho.passo}
              height={eixoY - MARGEM.topo}
              fill="transparent"
              role={onAno ? 'button' : undefined}
              tabIndex={onAno ? 0 : undefined}
              aria-label={descreverAno(ano, carregadas, formatar)}
              onClick={onAno ? () => onAno(ano) : undefined}
              onKeyDown={
                onAno
                  ? (ev) => {
                      if (ev.key === 'Enter' || ev.key === ' ') {
                        ev.preventDefault();
                        onAno(ano);
                      }
                    }
                  : undefined
              }
            />
          ))}

          <line x1={0} y1={eixoY} x2={largura} y2={eixoY} stroke="var(--alu-borda)" />

          {desenho.ancoras.map((ano) => (
            <text
              key={ano}
              x={x(ano)}
              y={eixoY}
              dy="18"
              textAnchor="middle"
              fontSize="11"
              fill="var(--alu-texto-2)"
            >
              {ano}
            </text>
          ))}
          </svg>
        </div>
      </div>

      {/* ⚠️ "Começa em 2008" NÃO é "só passou a cair em 2008". Sem esta frase o
          gráfico afirma, pelo silêncio, que o assunto não caía no ITA antes —
          quando a verdade é que não temos a prova (migration 0031). */}
      {desenho.lacunas.map((lacuna) => (
        <p className="alu-serie__lacuna" key={lacuna.vestibular}>
          {`Não temos prova do ${lacuna.vestibular} antes de ${lacuna.ate}. A linha dele começa ali — o período anterior está descoberto, não vazio.`}
        </p>
      ))}

      <ul className="alu-serie__legenda">
        {carregadas.map((serie) => (
          <li key={serie.vestibular}>
            <svg width="26" height="10" aria-hidden="true">
              <line
                x1="0"
                y1="5"
                x2="26"
                y2="5"
                stroke={
                  serie.vestibular === 'ITA' ? 'var(--alu-dado)' : 'var(--alu-dado-claro)'
                }
                strokeWidth="2"
                strokeDasharray={serie.vestibular === 'ITA' ? undefined : '5 4'}
              />
              <circle
                cx="13"
                cy="5"
                r="3.5"
                fill={
                  serie.vestibular === 'ITA' ? 'var(--alu-dado)' : 'var(--alu-fundo)'
                }
                stroke={
                  serie.vestibular === 'ITA' ? 'var(--alu-dado)' : 'var(--alu-dado-claro)'
                }
                strokeWidth="2"
              />
            </svg>
            {serie.vestibular === 'ITA' ? 'ITA · linha cheia' : 'IME · tracejada'}
          </li>
        ))}
      </ul>
      <p className="alu-serie__teto-oculto">{`Topo do eixo: ${formatar(teto)}`}</p>
    </div>
  );
}

/** O que o leitor de tela anuncia ao chegar na coluna de um ano. */
function descreverAno(
  ano: number,
  series: SerieDoAssunto[],
  formatar: (v: number) => string,
): string {
  const partes = series.map((serie) => {
    const ponto = serie.pontos.find((p) => p.ano === ano);
    // Fora do domínio da banca não é zero: é prova que não temos.
    if (!ponto) return `${serie.vestibular} sem acervo`;
    return `${serie.vestibular} ${formatar(ponto.bruto)}`;
  });
  return `${ano}: ${partes.join(', ')}`;
}

interface Desenho {
  largura: number;
  passo: number;
  anos: number[];
  ancoras: number[];
  teto: number;
  grades: number[];
  eixoY: number;
  x: (ano: number) => number;
  y: (valor: number) => number;
  formatar: (valor: number) => string;
  lacunas: { vestibular: string; de: number; ate: number }[];
}

function montar(series: SerieDoAssunto[]): Desenho | null {
  if (series.length === 0) return null;

  const todosOsAnos = series.flatMap((s) => s.pontos.map((p) => p.ano));
  if (todosOsAnos.length === 0) return null;

  const primeiro = Math.min(...todosOsAnos);
  const ultimo = Math.max(...todosOsAnos);
  const anos: number[] = [];
  for (let ano = primeiro; ano <= ultimo; ano++) anos.push(ano);

  const passo = PASSO_MINIMO;
  const largura = MARGEM.esquerda + Math.max(1, anos.length - 1) * passo + MARGEM.direita;
  const eixoY = ALTURA - MARGEM.base;

  const percentual = series[0].eixo === 'percentual';
  const maior = Math.max(0, ...series.flatMap((s) => s.pontos.map((p) => p.valor)));
  // Teto redondo, e nunca zero: um assunto que nunca caiu ainda precisa de eixo
  // desenhado — é ele que mostra que a linha está chapada no chão de propósito.
  const teto = percentual
    ? Math.max(5, Math.ceil(maior / 5) * 5)
    : Math.max(1, Math.ceil(maior));

  const x = (ano: number) => MARGEM.esquerda + (ano - primeiro) * passo;
  const y = (valor: number) => eixoY - (valor / teto) * (eixoY - MARGEM.topo);
  const formatar = percentual
    ? (v: number) => `${Math.round(v)}%`
    : (v: number) => String(Math.round(v));

  // Âncoras esparsas: um rótulo por ano ficaria ilegível a 44px de passo com
  // trinta anos. Primeiro, último, e o começo de cada acervo — que são
  // justamente os anos que a leitura precisa.
  const inicios = series.map((s) => s.pontos[0]?.ano).filter((a): a is number => a != null);
  const ancoras = [...new Set([primeiro, ...inicios, ultimo])].sort((a, b) => a - b);

  const lacunas = series
    .filter((s) => (s.pontos[0]?.ano ?? primeiro) > primeiro)
    .map((s) => ({ vestibular: s.vestibular, de: primeiro, ate: s.pontos[0].ano }));

  return { largura, passo, anos, ancoras, teto, grades: [0, teto / 2, teto], eixoY, x, y, formatar, lacunas };
}
