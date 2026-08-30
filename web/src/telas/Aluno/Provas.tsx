import type { CSSProperties } from 'react';
import { NavLink } from 'react-router-dom';

import {
  type HeatmapDoAluno,
  type MateriaContraCorte,
  type SimuladoDoAluno,
  type SimuladoDoHeatmap,
  useHeatmap,
  useMateriasContraCorte,
  useSimulado,
  useSimulados,
} from '../../dados/aluno';
import { Bloco } from './pecas/Bloco';
import { FichaXp, Icone } from './pecas/Icone';
import { TarjaFonte } from './pecas/TarjaFonte';
import {
  abreviarMateria,
  fmt,
  fmtDataCurta,
  fmtDataLonga,
  fmtDelta,
  fmtInteiro,
} from './pecas/formato';

// PROVAS — "como eu fui".
//
// É a aba mais REAL da área do aluno: três rotas que estavam prontas, testadas
// e sem tela nenhuma até agora (docs/29 §A.5) entram aqui — `/me/heatmap` no
// mapa de calor, `/me/simulado/{id}` no herói e `/me/simulado/{id}/arquivo` na
// ficha. O único mock que sobra nesta tela é o CORTE por matéria, e ele leva
// tarja.
//
// A nota é o herói AQUI, e só aqui: na Hoje o herói é o que fazer agora
// (docs/24 §7). Esta é a tela do retrovisor, e por isso ela abre no último
// simulado e leva daqui para o extrato — que é onde o número vira explicação.

/** Altura de uma linha da grade e largura de uma coluna, em px.
 *  As duas viajam para o CSS por variável: a coluna de rótulos das matérias é
 *  HTML e a grade é SVG, e as duas têm de alinhar pixel a pixel. */
const ALTURA_LINHA = 30;
const LARGURA_COLUNA = 44;
/** Banda do ciclo (16) + rótulo do simulado (18). */
const ALTURA_CABECALHO = 34;
const NOTA_MAXIMA = 10;

export function Provas() {
  const simulados = useSimulados();
  const lista = simulados.data ?? [];

  // Qual é "o último" é decisão do servidor: `simulados_do_aluno` ordena por
  // data decrescente e marca `novo` no primeiro. Reordenar aqui criaria uma
  // segunda regra para a mesma pergunta, e as duas divergiriam no primeiro
  // simulado sem data.
  const ultimo = lista.find((s) => s.novo) ?? lista[0] ?? null;

  if (simulados.isPending) {
    return (
      <div className="alu-provas">
        <h1 className="alu-titulo-tela">Provas</h1>
        <EsqueletoDaTela />
      </div>
    );
  }

  if (simulados.isError) {
    return (
      <div className="alu-provas">
        <h1 className="alu-titulo-tela">Provas</h1>
        <Bloco fonte="simulados">
          <p className="alu-vazio">
            Não deu para carregar as suas notas agora. Pode ser a conexão — tente de novo.
          </p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => simulados.refetch()}
          >
            Tentar de novo
          </button>
        </Bloco>
      </div>
    );
  }

  if (!lista.length) {
    return (
      <div className="alu-provas">
        <h1 className="alu-titulo-tela">Provas</h1>
        <Bloco fonte="simulados" olho="Sua primeira nota">
          <p className="alu-vazio">
            Assim que você fizer um simulado e a correção sair, ela aparece aqui — com a sua
            posição, o mapa por matéria e o extrato de onde vieram os seus pontos.
          </p>
          <p className="alu-vazio">Até lá, o treino é livre e não espera nota nenhuma.</p>
          <NavLink className="alu-tecla" to="/estudar">
            Treinar agora
          </NavLink>
        </Bloco>
      </div>
    );
  }

  return (
    <div className="alu-provas">
      <h1 className="alu-titulo-tela">Provas</h1>
      {ultimo && <HeroUltimoSimulado simulado={ultimo} />}
      <MapaDeCalor />
      <ListaDeSimulados lista={lista} />
    </div>
  );
}

// ─── Herói: o último simulado ────────────────────────────────────────────

function HeroUltimoSimulado({ simulado }: { simulado: SimuladoDoAluno }) {
  // Posição e percentil não vêm em `/me/simulados` — só na ficha. São duas
  // rotas porque são dois custos: a lista é barata e o ranking varre o
  // simulado inteiro.
  const detalhe = useSimulado(simulado.id);
  const nome = simulado.rotulo || simulado.nome || simulado.id;

  return (
    <Bloco fonte="simulado" olho="Último simulado" className="alu-provas__hero">
      <p className="alu-provas__hero-nome">{nome}</p>

      <div className="alu-provas__hero-nota">
        <strong className="alu-magnitude alu-provas__nota">{fmt(simulado.nota)}</strong>
        <span className="alu-provas__escala">de {fmtInteiro(NOTA_MAXIMA)}</span>
      </div>

      {simulado.deltaSelf != null && (
        <p className="alu-provas__delta">
          <Delta valor={simulado.deltaSelf} />
          <span>contra o seu próprio padrão até aqui</span>
        </p>
      )}

      <dl className="alu-provas__leituras">
        <div className="alu-provas__leitura">
          <dt className="alu-olho alu-olho--quieto">Aplicado em</dt>
          <dd className="alu-provas__leitura-valor">{fmtDataLonga(simulado.dataAplicacao)}</dd>
        </div>
        <div className="alu-provas__leitura">
          <dt className="alu-olho alu-olho--quieto">Posição</dt>
          <dd className="alu-provas__leitura-valor">
            {detalhe.data
              ? `${fmtInteiro(detalhe.data.posicao)}º de ${fmtInteiro(detalhe.data.total)}`
              : detalhe.isError
                ? 'indisponível'
                : '—'}
          </dd>
        </div>
        <div className="alu-provas__leitura">
          <dt className="alu-olho alu-olho--quieto">Percentil</dt>
          <dd className="alu-provas__leitura-valor">
            {detalhe.data
              ? `acima de ${fmtInteiro(detalhe.data.percentil)}%`
              : detalhe.isError
                ? 'indisponível'
                : '—'}
          </dd>
        </div>
      </dl>

      {/* O extrato é o momento mais forte do produto (brief §Extrato) e não
          pode ficar atrás de dois toques. Tecla de VALOR porque o que se
          aperta AQUI é a recompensa, não uma navegação qualquer. */}
      <div className="alu-provas__acoes">
        <NavLink className="alu-tecla alu-tecla--valor" to={`/provas/${simulado.id}/extrato`}>
          <FichaXp tamanho={18} />
          Ver o extrato
        </NavLink>
        <NavLink className="alu-tecla alu-tecla--fantasma" to={`/provas/${simulado.id}`}>
          Abrir a ficha
        </NavLink>
      </div>
    </Bloco>
  );
}

/** O delta contra o próprio padrão. Progresso é DADO; queda é quieta, nunca
 *  ALERTA — ALERTA é reservado à distância até o corte (docs/24 §7.2). */
function Delta({ valor }: { valor: number }) {
  const subiu = valor > 0;
  return (
    <span className={`alu-provas__delta-valor${subiu ? ' is-subiu' : ''}`}>
      <Icone nome={subiu ? 'seta_cima' : 'seta_baixo'} tamanho={14} />
      {fmtDelta(valor)}
    </span>
  );
}

// ─── Mapa de calor: matéria por ciclo ────────────────────────────────────

function MapaDeCalor() {
  const mapa = useHeatmap();
  const cortes = useMateriasContraCorte();

  if (mapa.isPending) {
    return (
      <Bloco fonte="heatmap" olho="Matéria por ciclo">
        <div className="alu-provas__esqueleto" style={{ height: 180 }} />
      </Bloco>
    );
  }

  if (mapa.isError) {
    return (
      <Bloco fonte="heatmap" olho="Matéria por ciclo">
        <p className="alu-vazio">Não deu para carregar o mapa por matéria.</p>
        {/* Tecla de tamanho cheio: `--pequena` tem 36px de altura e o piso de
            toque do produto é 44 (docs/20 §1.3). Botão de recuperar erro é
            justamente o que se aperta com pressa. */}
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma"
          onClick={() => mapa.refetch()}
        >
          Tentar de novo
        </button>
      </Bloco>
    );
  }

  const dados = mapa.data;
  if (!dados?.materias.length || !dados.simulados.length) {
    return (
      <Bloco fonte="heatmap" olho="Matéria por ciclo">
        <p className="alu-vazio">
          O mapa aparece quando você tiver nota em mais de uma matéria — ele mostra onde você
          sustenta e onde escorrega, ciclo a ciclo.
        </p>
      </Bloco>
    );
  }

  return (
    <Bloco fonte="heatmap" olho="Matéria por ciclo">
      {/* A matriz é real; a RÉGUA que decide qual célula está abaixo do corte
          ainda não tem rota (docs/24 §2). Duas fontes no mesmo bloco, duas
          marcas — a do bloco é a do heatmap, e esta é a do corte. */}
      <TarjaFonte chave="cortePorMateria" />
      <Grade mapa={dados} cortes={cortes.data ?? []} />
      <LegendaDaGrade cortes={cortes.data ?? []} />
    </Bloco>
  );
}

/**
 * O corte mais comum entre as matérias que a régua conhece.
 *
 * É o que uma matéria de fora dela herda — Redação, por exemplo, que não está
 * em `cortePorMateria`. O número é DERIVADO do que a fonte trouxe, nunca
 * escrito aqui: a régua de verdade é `criterio_classificacao` e ainda não tem
 * rota do lado do aluno (docs/24 §2). Sem fonte, devolve `null` e nenhuma
 * célula é marcada — marcar de menos é honesto, marcar com número inventado
 * não é.
 */
function corteMajoritario(cortes: MateriaContraCorte[]): number | null {
  if (!cortes.length) return null;
  const contagem = new Map<number, number>();
  for (const c of cortes) contagem.set(c.corte, (contagem.get(c.corte) ?? 0) + 1);
  return [...contagem.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

/** O nome da banda de um simulado. `cicloNome` já traz ano e vestibular
 *  ("Ciclo 3 · ITA · 2026"), que é o que distingue dois ciclos de mesma ordem. */
function nomeDoCiclo(s: SimuladoDoHeatmap): string {
  return s.cicloNome ?? (s.cicloOrdem != null ? `Ciclo ${s.cicloOrdem}` : 'Sem ciclo');
}

function Grade({ mapa, cortes }: { mapa: HeatmapDoAluno; cortes: MateriaContraCorte[] }) {
  const { materias, celulas } = mapa;

  const porCelula = new Map(celulas.map((c) => [`${c.materia}|${c.simuladoId}`, c.pontuacao]));

  const padrao = corteMajoritario(cortes);
  const corteDe = (materia: string): number | null =>
    cortes.find((c) => c.materia === materia)?.corte ?? padrao;

  // ⚠️ A rota ordena por (cicloOrdem, fase, data) — NÃO por ciclo. E dois
  // ciclos compartilham `ordem` o tempo todo, porque cada ano letivo recomeça
  // do 1: "Ciclo 3 · ITA · 2025" e "Ciclo 3 · ITA · 2026" empatam na primeira
  // chave, e aí a fase 2 de um cai depois da fase 1 do outro. Agrupar só o que
  // vem adjacente parte o mesmo ciclo em duas bandas de nome igual com as
  // colunas de um terceiro no meio — aconteceu em 10 dos 17 ciclos do banco de
  // desenvolvimento, e é o que faz a banda mentir sobre o que agrupa.
  //
  // Reunir as colunas do mesmo ciclo é REAGRUPAMENTO, não ordenação nova: a
  // ordem em que cada ciclo aparece continua sendo a do servidor (o `Map`
  // guarda a de inserção), e a ordem dentro dele também.
  const porCiclo = new Map<string, SimuladoDoHeatmap[]>();
  for (const s of mapa.simulados) {
    const chave = s.cicloId ?? nomeDoCiclo(s);
    const grupo = porCiclo.get(chave);
    if (grupo) grupo.push(s);
    else porCiclo.set(chave, [s]);
  }
  const simulados = [...porCiclo.values()].flat();

  const bandas: Array<{ nome: string; inicio: number; fim: number }> = [];
  simulados.forEach((s, i) => {
    const nome = nomeDoCiclo(s);
    const ultima = bandas[bandas.length - 1];
    if (ultima && ultima.nome === nome) ultima.fim = i;
    else bandas.push({ nome, inicio: i, fim: i });
  });

  const largura = simulados.length * LARGURA_COLUNA;
  const altura = ALTURA_CABECALHO + materias.length * ALTURA_LINHA;

  const resumo = materias
    .map((m) => {
      const notas = simulados
        .map((s) => porCelula.get(`${m}|${s.id}`))
        .filter((n): n is number => n != null);
      return notas.length ? `${m}: ${notas.map((n) => fmt(n)).join(', ')}` : `${m}: sem nota`;
    })
    .join('; ');

  return (
    <div
      className="alu-mapa"
      style={
        {
          '--alu-mapa-linha': `${ALTURA_LINHA}px`,
          '--alu-mapa-topo': `${ALTURA_CABECALHO}px`,
        } as CSSProperties
      }
    >
      {/* A coluna de matérias fica FORA da área que rola: num aparelho de
          360px a grade sai da tela pela direita, e um rótulo de linha que
          some junto com ela deixa o mapa ilegível. */}
      <ul className="alu-mapa__materias" aria-hidden="true">
        {materias.map((m) => (
          <li key={m} className="alu-mapa__materia">
            {abreviarMateria(m)}
          </li>
        ))}
      </ul>

      <div className="alu-mapa__rolagem">
        <svg
          width={largura}
          height={altura}
          viewBox={`0 0 ${largura} ${altura}`}
          role="img"
          aria-label={`Mapa de calor por matéria e simulado. ${resumo}`}
          style={{ display: 'block' }}
        >
          <title>Matéria por ciclo</title>

          {bandas.map((b) => (
            <text
              key={`${b.nome}-${b.inicio}`}
              x={(b.inicio + (b.fim - b.inicio + 1) / 2) * LARGURA_COLUNA}
              y={11}
              textAnchor="middle"
              className="alu-mapa__ciclo"
            >
              {b.nome}
            </text>
          ))}

          {/* Fio entre ciclos: separa sem pintar nada, que é o que o mapa
              precisa para não virar tabela. */}
          {bandas.slice(1).map((b) => (
            <line
              key={`fio-${b.inicio}`}
              x1={b.inicio * LARGURA_COLUNA}
              x2={b.inicio * LARGURA_COLUNA}
              y1={2}
              y2={altura}
              stroke="var(--alu-borda)"
              strokeWidth="1"
            />
          ))}

          {simulados.map((s, j) => (
            <text
              key={`rot-${s.id}`}
              x={j * LARGURA_COLUNA + LARGURA_COLUNA / 2}
              y={28}
              textAnchor="middle"
              className="alu-mapa__coluna"
            >
              {s.rotulo || s.nome || '—'}
            </text>
          ))}

          {materias.map((m, i) =>
            simulados.map((s, j) => {
              const nota = porCelula.get(`${m}|${s.id}`);
              const x = j * LARGURA_COLUNA + 3;
              const y = ALTURA_CABECALHO + i * ALTURA_LINHA + 3;
              const w = LARGURA_COLUNA - 6;
              const h = ALTURA_LINHA - 6;
              const chave = `${m}|${s.id}`;

              // Sem nota não se desenha nada: célula ausente é ausência de
              // nota, e um quadrado cinza aí seria confundido com nota baixa.
              if (nota == null) return null;

              const corte = corteDe(m);
              const abaixo = corte != null && nota < corte;

              if (abaixo) {
                // VAZIO É VAZADO. O fio é ALERTA porque aqui ele marca o VALOR
                // abaixo do corte, que é exatamente o papel dele — a barra da
                // "onde você está" continua sem cor nenhuma (docs/24 §7.2).
                return (
                  <g key={chave}>
                    <rect
                      x={x}
                      y={y}
                      width={w}
                      height={h}
                      rx="6"
                      fill="none"
                      stroke="var(--alu-alerta)"
                      strokeWidth="1.5"
                    />
                    {/* O número fica na cor de texto normal: só o CONTORNO é
                        ALERTA. Pintar o numeral de coral recriaria o semáforo
                        que docs/24 §7.2 proíbe — e reprovaria em contraste
                        sobre a superfície clara. */}
                    <text
                      x={x + w / 2}
                      y={y + h / 2 + 4}
                      textAnchor="middle"
                      className="alu-mapa__nota"
                    >
                      {fmt(nota)}
                    </text>
                  </g>
                );
              }

              // A intensidade sai da nota, dentro de uma faixa ESTREITA de
              // propósito: 0,25 é o piso para a célula mais fraca ainda se
              // separar do fundo, e 0,75 é o teto porque acima disso o azul
              // fica escuro demais para o texto normal no tema dia — a 0,8 o
              // contraste cai para 4,49:1 e reprova AA por um fio. Faixa curta
              // e uma cor de letra só é melhor que faixa longa com duas.
              const intensidade = 0.25 + 0.5 * Math.min(1, Math.max(0, nota / NOTA_MAXIMA));

              return (
                <g key={chave}>
                  <rect
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    rx="6"
                    fill="var(--alu-dado)"
                    fillOpacity={intensidade}
                  />
                  <text
                    x={x + w / 2}
                    y={y + h / 2 + 4}
                    textAnchor="middle"
                    className="alu-mapa__nota"
                  >
                    {fmt(nota)}
                  </text>
                </g>
              );
            }),
          )}
        </svg>
      </div>
    </div>
  );
}

function LegendaDaGrade({ cortes }: { cortes: MateriaContraCorte[] }) {
  // "Abaixo do corte" sem dizer CONTRA QUAL corte é só a má notícia: o número
  // da régua é obrigatório junto do veredito (docs/24 §2). Os valores saem de
  // `cortePorMateria` e de mais lugar nenhum — a matéria cujo corte foge do
  // padrão é nomeada uma a uma, que é como o Inglês eliminatório da Fase 1 do
  // ITA aparece sem ninguém escrever "5,0" no código.
  const padrao = corteMajoritario(cortes);
  const excecoes = cortes.filter((c) => c.corte !== padrao);
  const rotuloDoCorte =
    padrao == null
      ? 'o corte não carregou — nada foi marcado'
      : `abaixo do corte · ${fmt(padrao)}${
          excecoes.length
            ? `, e ${excecoes.map((c) => `${fmt(c.corte)} em ${c.materia}`).join(', ')}`
            : ''
        }`;

  return (
    <ul className="alu-mapa__legenda">
      <li className="alu-mapa__legenda-item">
        {/* As três amostras repetem a faixa real de intensidade (0,25 a
            0,75), e não uma escala bonita: legenda que não bate com a grade
            ensina a ler errado. */}
        <span className="alu-mapa__amostra" style={{ opacity: 0.25 }} />
        <span className="alu-mapa__amostra" style={{ opacity: 0.5 }} />
        <span className="alu-mapa__amostra" style={{ opacity: 0.75 }} />
        nota mais baixa → mais alta
      </li>
      <li className="alu-mapa__legenda-item">
        <span className="alu-mapa__amostra alu-mapa__amostra--abaixo" />
        {rotuloDoCorte}
      </li>
      {/* Sem amostra, e de propósito: a grade não desenha NADA onde falta nota
          (ver `Grade`, o `return null`), então uma amostra tracejada aqui
          prometeria um marcador que não existe em lugar nenhum do mapa — e
          legenda que não bate com a grade ensina a ler errado. O que a linha
          explica é o buraco. */}
      <li className="alu-mapa__legenda-item">célula vazia · sem nota nessa matéria</li>
    </ul>
  );
}

// ─── Lista de todos os simulados ─────────────────────────────────────────

function ListaDeSimulados({ lista }: { lista: SimuladoDoAluno[] }) {
  return (
    <Bloco
      fonte="simulados"
      olho="Todos os simulados"
      acao={`${fmtInteiro(lista.length)} com nota`}
    >
      {/* ⚠️ Esta lista NÃO mostra os simulados em que o aluno faltou.
          `simulados_do_aluno` filtra `presente = true` e descarta a falta, então
          do lado do aluno a falta é invisível hoje (docs/29 §A.2). Não dá para
          contornar isso no front: a ausência não chega até aqui — some no SQL.
          O conserto é a rota (`/me/simulados?incluirFaltas=true`), e é ela que
          destrava o quadrado vazado da corrente. */}
      <ol className="alu-provas__lista">
        {lista.map((s) => (
          <li key={s.id}>
            <NavLink className="alu-provas__linha" to={`/provas/${s.id}`}>
              <span className="alu-provas__linha-texto">
                <span className="alu-provas__linha-nome">{s.rotulo || s.nome || s.id}</span>
                <span className="alu-provas__linha-meta">
                  {fmtDataCurta(s.dataAplicacao)}
                  {s.materia ? ` · ${s.materia}` : ''}
                  {s.vestibularAlvo ? ` · ${s.vestibularAlvo}` : ''}
                </span>
              </span>
              <span className="alu-provas__linha-nota">
                <strong className="alu-magnitude alu-provas__linha-valor">{fmt(s.nota)}</strong>
                {s.deltaSelf != null && <Delta valor={s.deltaSelf} />}
              </span>
              <Icone nome="chevron" tamanho={18} />
            </NavLink>
          </li>
        ))}
      </ol>
    </Bloco>
  );
}

// ─── Carregando ──────────────────────────────────────────────────────────

/** Esqueleto com a forma do conteúdo, nunca um spinner: o aluno já sabe onde
 *  a nota vai aparecer antes de ela chegar. */
function EsqueletoDaTela() {
  return (
    <>
      <div className="alu-bloco">
        <div className="alu-provas__esqueleto" style={{ height: 14, width: '40%' }} />
        <div className="alu-provas__esqueleto" style={{ height: 60, width: '55%' }} />
        <div className="alu-provas__esqueleto" style={{ height: 44 }} />
      </div>
      <div className="alu-bloco">
        <div className="alu-provas__esqueleto" style={{ height: 14, width: '35%' }} />
        <div className="alu-provas__esqueleto" style={{ height: 150 }} />
      </div>
    </>
  );
}
