import type { MateriaContraCorte } from '../../../dados/aluno';
import { abreviarMateria, fmt } from './formato';

// "Onde você está" — as matérias contra a linha de corte.
//
// É o elemento visual central do produto, porque o corte é o conceito central:
// uma linha. SVG escrito à mão, como todos os gráficos do projeto — nenhuma
// biblioteca de gráfico entra (regra do CLAUDE.md, e docs/24 §7.4).
//
// TRÊS REGRAS, e as três são de docs/24 §7.2:
//
//   1. A barra ACIMA do corte é preenchida na cor DADO. A barra ABAIXO é
//      VAZADA — contorno sem preenchimento. Na noite lê como segmento queimado
//      de letreiro; no dia, como não-preenchido.
//   2. NUNCA vermelho na barra. Só a ETIQUETA de distância é ALERTA. Pintar a
//      barra de vermelho recria o semáforo verde-e-vermelho, que era o que mais
//      puxava a idade da tela para baixo.
//   3. A linha de corte é VALOR (ouro), não alerta. Ela não é a má notícia — é
//      a régua.
//
// ⚠️ O corte é POR MATÉRIA e não é sempre 4,0: o Inglês da Fase 1 do ITA é o
// único eliminatório, com corte 5,0. Desenhar uma linha só para todas as barras
// mentiria sobre a matéria que mais elimina.

interface Props {
  materias: MateriaContraCorte[];
  /** Compacto: some com os números no topo, para caber num artefato do chat. */
  compacto?: boolean;
}

const NOTA_MAXIMA = 10;

export function BarraCorte({ materias, compacto = false }: Props) {
  if (!materias.length) {
    return <p className="alu-vazio">Ainda não há nota para comparar com o corte.</p>;
  }

  // O corte majoritário é o que ganha a linha contínua e o rótulo "CORTE"; um
  // corte diferente vira um traço curto sobre a própria barra, para o Inglês
  // não desalinhar a leitura das outras quatro.
  const contagem = new Map<number, number>();
  for (const m of materias) contagem.set(m.corte, (contagem.get(m.corte) ?? 0) + 1);
  const corteComum = [...contagem.entries()].sort((a, b) => b[1] - a[1])[0][0];

  const largura = 320;
  const altura = compacto ? 130 : 200;
  const padTopo = compacto ? 14 : 34;
  const padBase = 30;
  const alturaPlot = altura - padTopo - padBase;
  const passo = largura / materias.length;
  const larguraBarra = Math.min(38, passo * 0.52);

  const y = (nota: number) => padTopo + alturaPlot - (nota / NOTA_MAXIMA) * alturaPlot;
  const yBase = padTopo + alturaPlot;
  const yCorte = y(corteComum);

  const colunas = materias.map((m, i) => ({
    ...m,
    x: i * passo + (passo - larguraBarra) / 2,
    topo: y(m.nota),
    acima: m.nota >= m.corte,
  }));

  return (
    <div className="alu-corte">
      <svg
        viewBox={`0 0 ${largura} ${altura}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Suas notas contra o corte: ${materias
          .map((m) => `${m.materia} ${fmt(m.nota)}, corte ${fmt(m.corte)}`)
          .join('; ')}`}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <title>Onde você está</title>

        {/* TRÊS PASSADAS, e a ordem é o que impede a colisão que aparecia
            quando tudo saía num `map` só: barra, depois linha, depois texto.
            Com o texto no mesmo grupo da barra, o valor de uma matéria logo
            abaixo do corte era desenhado ANTES da linha e ficava riscado por
            ela — que é justamente a nota que mais precisa ser lida. */}

        {/* 1 · As barras. */}
        {colunas.map((c) =>
          c.acima ? (
            <rect
              key={c.materia}
              x={c.x}
              y={c.topo}
              width={larguraBarra}
              height={Math.max(2, yBase - c.topo)}
              rx="3"
              fill="var(--alu-dado)"
            />
          ) : (
            /* VAZADA. O meio-pixel no inset impede o traço de 1,5 de ser
               cortado pela metade na borda do próprio retângulo. */
            <rect
              key={c.materia}
              x={c.x + 0.75}
              y={c.topo + 0.75}
              width={larguraBarra - 1.5}
              height={Math.max(2, yBase - c.topo - 1.5)}
              rx="3"
              fill="none"
              stroke="var(--alu-borda)"
              strokeWidth="1.5"
            />
          ),
        )}

        {/* 2 · A linha de corte, por cima das barras: ela é a referência.

            ⚠️ SEM RÓTULO dentro do gráfico. O texto "CORTE 4,0" ficava ancorado
            na borda direita e cavalgava o valor da última barra — e era legenda
            de uma linha que já se explica. Dentro do gráfico só aparecem os
            números das barras e as letras das matérias; o valor do corte volta
            na etiqueta de distância, embaixo, onde ele é acionável. */}
        <line x1="0" x2={largura} y1={yCorte} y2={yCorte} stroke="var(--alu-valor)" strokeWidth="2" />

        {/* Corte próprio — hoje só o Inglês da Fase 1 do ITA, que é o único
            eliminatório. Traço curto na altura DELE, sobre a própria barra. */}
        {colunas.map((c) =>
          c.corte === corteComum ? null : (
            <line
              key={`corte-${c.materia}`}
              x1={c.x - 5}
              x2={c.x + larguraBarra + 5}
              y1={y(c.corte)}
              y2={y(c.corte)}
              stroke="var(--alu-valor)"
              strokeWidth="2"
              strokeLinecap="round"
            />
          ),
        )}

        {/* 3 · Os textos, por último e por cima de tudo. */}
        {colunas.map((c) => (
          <g key={`texto-${c.materia}`}>
            {!compacto && (
              <text
                x={c.x + larguraBarra / 2}
                y={c.topo - 9}
                textAnchor="middle"
                className="alu-corte__valor"
              >
                {fmt(c.nota)}
              </text>
            )}
            <text
              x={c.x + larguraBarra / 2}
              y={altura - 9}
              textAnchor="middle"
              className="alu-corte__materia"
            >
              {abreviarMateria(c.materia)}
            </text>
          </g>
        ))}
      </svg>

      {/* A distância vai FORA do SVG, como etiqueta HTML: dentro dela o
          `text` não quebra linha e a pílula não acompanha o tema sem
          duplicar cor. */}
      <ul className="alu-corte__etiquetas">
        {materias.map((m) => {
          if (m.nota >= m.corte) return null;
          return (
            <li key={m.materia} className="alu-corte__etiqueta">
              <span className="alu-etiqueta-alerta">−{fmt(m.corte - m.nota)}</span>
              <span className="alu-corte__etiqueta-texto">
                {m.materia} · corte {fmt(m.corte)}
                {m.eliminatoria && <strong> · eliminatória</strong>}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
