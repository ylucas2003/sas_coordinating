import { NavLink } from 'react-router-dom';

import type {
  EloDaCorrente,
  EvolucaoAluno,
  MateriaContraCorte,
  PontoDaTrajetoria,
  ZonaEDistancia,
} from '../../dados/aluno';
import {
  useConquistas,
  useDepoimento,
  useEvolucao,
  useLiga,
  useMateriasContraCorte,
  usePresencaPorCiclo,
  useTrajetoria,
  useZona,
} from '../../dados/aluno';
import { Bloco } from './pecas/Bloco';
import { Corrente } from './pecas/Corrente';
import { Icone } from './pecas/Icone';
import { fmt, fmtDataCurta, fmtInteiro } from './pecas/formato';

// A JORNADA — "estou evoluindo".
//
// É a aba que responde a pergunta que organiza docs/24: "como a gente cria uma
// jornada para o aluno sair de um D e ir para um A?". Todas as outras abas
// olham para um recorte; esta olha para a linha inteira.
//
// A REGRA DURA da tela (docs/24 §2): a zona NUNCA aparece sem a DISTÂNCIA e
// sem o NOME DA RÉGUA. Um aluno lendo "risco" sem saber contra qual corte, e
// sem saber quanto falta, recebe só a má notícia — e o rótulo vira sentença em
// vez de próximo passo. Por isso o hero é um bloco só: rótulo, distância e
// critério nascem juntos e não têm como se separar num refactor distraído.

export function Jornada() {
  const zona = useZona();
  const trajetoria = useTrajetoria();
  const evolucao = useEvolucao();
  const cortes = useMateriasContraCorte();
  const presenca = usePresencaPorCiclo();
  const liga = useLiga();
  const conquistas = useConquistas();
  const depoimento = useDepoimento();

  // A trajetória é a única fonte REAL que diz se este aluno já fez prova
  // alguma. `simulados` também diria, mas custaria uma consulta a mais para
  // responder o que esta já responde.
  const semNota = !trajetoria.isPending && !trajetoria.isError && !trajetoria.data?.length;

  return (
    <>
      <h1 className="alu-titulo-tela">Jornada</h1>

      <Bloco fonte="zonaEDistancia" olho="Onde você está">
        <Situacao consulta={zona} />
        {zona.data && <HeroDaZona zona={zona.data} />}
      </Bloco>

      {/* A linha de corte é `cortePorMateria`, que ainda não tem rota — a
          trajetória em si é real. A tarja marca o que falta, e não o bloco
          inteiro: `trajetoria` sendo 'real' no registro, a marca não apareceria
          se a chave passada fosse a dela. */}
      <Bloco fonte="cortePorMateria" olho="Sua trajetória" acao="cada ponto é uma nota">
        <Situacao consulta={trajetoria} />
        {semNota && <ConviteParaComecar />}
        {!!trajetoria.data?.length && (
          <Trajetoria
            pontos={trajetoria.data}
            corte={corteMajoritario(cortes.data)}
            turma={mediaDaTurmaPorCiclo(evolucao.data)}
          />
        )}
      </Bloco>

      <Bloco fonte="presencaNosSimulados" olho="Sua corrente" acao={resumoDePresenca(presenca.data)}>
        <Situacao consulta={presenca} />
        {presenca.data && !presenca.data.length && (
          <p className="alu-vazio">
            A corrente enche a cada simulado que você faz. O primeiro começa a sua.
          </p>
        )}
        {!!presenca.data?.length && (
          <ol className="alu-jor-ciclos">
            {presenca.data.map((ciclo) => (
              <li key={ciclo.ciclo} className="alu-jor-ciclo">
                <span className="alu-jor-ciclo__nome">{ciclo.ciclo}</span>
                <Corrente elos={elosDoCiclo(ciclo.presencas)} tamanho={22} />
              </li>
            ))}
          </ol>
        )}
      </Bloco>

      <Bloco fonte="liga" olho="Sua liga">
        <Situacao consulta={liga} />
        {liga.data && (
          <div className="alu-jor-liga">
            <Escudo tamanho={46} />
            <div className="alu-jor-liga__texto">
              <span className="alu-jor-liga__nome">{liga.data.nome}</span>
              <span className="alu-jor-liga__posicao">
                {liga.data.posicoes.find((p) => p.euMesmo)?.posicao ?? '—'}º de{' '}
                {liga.data.participantes}
              </span>
              {liga.data.faltaParaSubir != null && (
                <span className="alu-jor-liga__falta">
                  faltam {fmtInteiro(liga.data.faltaParaSubir)} XP para subir
                </span>
              )}
            </div>
            <NavLink className="alu-tecla alu-tecla--valor" to="/liga">
              Ver
            </NavLink>
          </div>
        )}
      </Bloco>

      <Bloco fonte="conquistas" olho="Conquistas">
        <Situacao consulta={conquistas} />
        {conquistas.data && !conquistas.data.length && (
          <p className="alu-vazio">
            A primeira medalha sai do primeiro simulado que você fizer.
          </p>
        )}
        {!!conquistas.data?.length && (
          <ul className="alu-jor-medalhas">
            {conquistas.data.map((c) => (
              <li
                key={c.chave}
                className={`alu-jor-medalha${c.conquistada ? '' : ' alu-jor-medalha--travada'}`}
              >
                <span className="alu-jor-medalha__selo">
                  {/* Troféu na conquistada, cadeado na travada. O ícone não é
                      escolhido pela chave de propósito: um mapa chave→ícone
                      amarraria a tela às chaves do mock. */}
                  <Icone nome={c.conquistada ? 'troféu' : 'cadeado'} tamanho={20} />
                </span>
                <span className="alu-jor-medalha__titulo">{c.titulo}</span>
                <span className="alu-olho alu-olho--quieto">{c.detalhe}</span>
                {!c.conquistada && c.progresso != null && (
                  <span
                    className="alu-jor-progresso"
                    role="img"
                    aria-label={`${Math.round(c.progresso * 100)}% do caminho`}
                  >
                    <span
                      className="alu-jor-progresso__preenchimento"
                      style={{ width: `${Math.round(c.progresso * 100)}%` }}
                    />
                  </span>
                )}
                {!c.conquistada && c.progressoRotulo && (
                  <span className="alu-olho alu-olho--quieto">{c.progressoRotulo}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Bloco>

      <Bloco fonte="depoimentos" olho="De quem já passou">
        <Situacao consulta={depoimento} />
        {depoimento.data && (
          <div className="alu-jor-depoimento">
            <p className="alu-jor-depoimento__chamada">{depoimento.data.chamada}</p>
            {/* ⚠️ Botão honestamente desligado. Citação de aprovado não se
                inventa: um depoimento fabricado numa tela que fala de
                aprovação é o tipo de mentira que o aluno leva para fora da
                plataforma. Melhor a afordância desligada até existir
                conteúdo editorial de verdade. */}
            <button
              type="button"
              className="alu-tecla alu-tecla--fantasma"
              disabled
              title="Os depoimentos ainda não foram escritos."
            >
              Ler
            </button>
            <p className="alu-vazio">Ainda sem conteúdo publicado.</p>
          </div>
        )}
      </Bloco>
    </>
  );
}

/**
 * Carregando e erro, iguais em todos os blocos das duas telas.
 *
 * Mora aqui, e não em `pecas/`, porque só a Jornada e a Liga a usam — e a Liga
 * já importa o escudo daqui. Uma peça com dois donos irmãos não precisa de
 * pasta própria.
 *
 * Devolve `null` quando a consulta deu certo, para o bloco seguir renderizando
 * o conteúdo sem um segundo `if` em cada chamada.
 */
export function Situacao({
  consulta,
}: {
  consulta: { isPending: boolean; isError: boolean; refetch: () => unknown };
}) {
  if (consulta.isPending) return <p className="alu-carregando">Carregando…</p>;
  if (!consulta.isError) return null;

  return (
    <div className="alu-jor-erro">
      {/* Diz o que houve e o que fazer. Sem pedir desculpa e sem ser vago. */}
      <p className="alu-vazio">Não deu para carregar isto agora. Pode ser a conexão.</p>
      <button
        type="button"
        className="alu-tecla alu-tecla--fantasma"
        onClick={() => consulta.refetch()}
      >
        Tentar de novo
      </button>
    </div>
  );
}

/** O escudo da liga. SVG à mão, como todo gráfico e todo ícone do projeto. */
export function Escudo({ tamanho = 46 }: { tamanho?: number }) {
  return (
    <svg
      width={tamanho}
      height={tamanho}
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
      style={{ display: 'block', flexShrink: 0 }}
    >
      <title>Escudo da liga</title>
      <path
        d="M24 3.5l16 5.2v14.4c0 9.4-6.4 17.4-16 21.4-9.6-4-16-12-16-21.4V8.7z"
        fill="none"
        stroke="var(--alu-valor)"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
      {/* A galonagem: três chevrons, a mesma forma do "sobe um degrau" da
          liga. Preenchida na cor VALOR — a liga é recompensa, não dado. */}
      <path
        d="M15.5 21.5L24 15l8.5 6.5M15.5 28.5L24 22l8.5 6.5"
        fill="none"
        stroke="var(--alu-valor)"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── O hero da zona ──────────────────────────────────────────────────────

/**
 * A escada de zonas, de cima para baixo.
 *
 * ⚠️ A escada é ESQUEMÁTICA de propósito, e é a decisão menos óbvia da tela:
 * `GET /me/zona` (docs/29 §A.4) devolve o TETO da zona corrente
 * (`corteProximaZona`) e não o piso dela. Desenhar as três faixas contra um
 * eixo 0–10 exigiria inventar a fronteira de baixo. Então as faixas têm altura
 * igual e a distância verdadeira vive no NÚMERO da cota, nunca no comprimento
 * dela.
 */
const FAIXAS = [
  { zona: 'top', rotulo: 'TOP' },
  { zona: 'cinzenta', rotulo: 'CINZENTA' },
  { zona: 'risco', rotulo: 'RISCO' },
] as const;

const NOME_DA_ZONA: Record<string, string> = {
  top: 'Zona top',
  cinzenta: 'Zona cinzenta',
  risco: 'Zona de risco',
};

function HeroDaZona({ zona }: { zona: ZonaEDistancia }) {
  const L = 320;
  const A = 200;
  const faixaX = 4;
  const faixaW = 214;
  const alturaFaixa = 52;
  const vao = 9;
  const topo = 16;
  const cotaX = 258;

  const yFaixa = (i: number) => topo + i * (alturaFaixa + vao);

  // Rótulo desconhecido cai na faixa DO MEIO, nunca na do topo. `Zona` é união
  // fechada em `tipos/dominio.ts`, mas o valor chega por JSON: se o servidor
  // ganhar uma zona nova, desenhar o aluno como TOP é a mentira mais cara que
  // esta tela pode contar.
  const achado = FAIXAS.findIndex((f) => f.zona === zona.zona);
  const indice = achado >= 0 ? achado : 1;
  // No topo não existe faixa acima: a fronteira dourada passa a ser a que ele
  // JÁ cruzou, logo abaixo, e a cota mede a folga em vez da falta.
  const noTopo = indice === 0;
  const yFronteira = noTopo ? yFaixa(1) - vao / 2 : yFaixa(indice) - vao / 2;
  const yPonto = yFaixa(indice) + alturaFaixa / 2;
  // Meio da faixa: à esquerda o ponto encostaria no rótulo da faixa, e à
  // direita o texto "VOCÊ · 6,8" sairia pela borda.
  const pontoX = faixaX + faixaW * 0.5;

  const distancia = Math.abs(zona.distancia);
  const textoCota = `${noTopo ? '+' : '−'}${fmt(distancia)}`;
  const larguraCota = 16 + textoCota.length * 7.4;
  const yCotaMeio = (yPonto + yFronteira) / 2;
  // ALERTA só quando a distância é FALTA. No topo a cota mede FOLGA, e um selo
  // vermelho ali transformaria a boa notícia em alarme — que é exatamente o
  // semáforo que docs/24 §7.2 recusa. Folga é DADO, o papel de "acima do corte".
  const corDaEtiqueta = noTopo ? 'var(--alu-dado)' : 'var(--alu-alerta)';

  const nome = NOME_DA_ZONA[zona.zona] ?? zona.zona;

  return (
    <div className="alu-jor-zona">
      <div className="alu-jor-zona__cabeca">
        <span className="alu-jor-zona__nome">{nome}</span>
        {/* A régua colada no rótulo, no mesmo bloco de texto — docs/24 §2. */}
        <span className="alu-jor-zona__regua">sob o critério {zona.regua}</span>
      </div>

      <svg
        viewBox={`0 0 ${L} ${A}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        // No topo não existe "próxima zona": a fronteira é a que ele já cruzou,
        // e chamá-la de próxima no leitor de tela contradiz o texto visível.
        aria-label={
          noTopo
            ? `${nome}, sob o critério ${zona.regua}. Sua média é ${fmt(
                zona.media,
              )} e o corte que você já cruzou é ${fmt(
                zona.corteProximaZona,
              )}: você está ${fmt(distancia)} acima dele.`
            : `${nome}, sob o critério ${zona.regua}. Sua média é ${fmt(
                zona.media,
              )} e a fronteira da próxima zona é ${fmt(
                zona.corteProximaZona,
              )}: faltam ${fmt(distancia)} para chegar lá.`
        }
        style={{ display: 'block', overflow: 'visible' }}
      >
        <title>Onde você está na régua</title>

        {FAIXAS.map((faixa, i) => {
          const aqui = i === indice;
          // VAZIO É VAZADO. A faixa RISCO nunca é preenchida, mesmo sendo a do
          // aluno: pintar o risco é recriar o semáforo que o sistema recusa
          // (docs/24 §7.2, regra 2).
          const preenchida = aqui && faixa.zona !== 'risco';
          return (
            <g key={faixa.zona}>
              <rect
                x={faixaX}
                y={yFaixa(i)}
                width={faixaW}
                height={alturaFaixa}
                rx="12"
                fill={preenchida ? 'var(--alu-superficie-2)' : 'none'}
                stroke="var(--alu-borda)"
                strokeWidth="1.5"
              />
              <text
                x={faixaX + 14}
                y={yFaixa(i) + 19}
                className={`alu-jor-zona__faixa-rotulo${
                  aqui ? ' alu-jor-zona__faixa-rotulo--aqui' : ''
                }`}
              >
                {faixa.rotulo}
              </text>
            </g>
          );
        })}

        {/* A fronteira dourada, rotulada com o corte. VALOR, sempre: ela é a
            régua, não a má notícia. */}
        <line
          x1={faixaX}
          x2={faixaX + faixaW}
          y1={yFronteira}
          y2={yFronteira}
          stroke="var(--alu-valor)"
          strokeWidth="2"
        />
        <text
          x={faixaX + faixaW}
          y={yFronteira - 6}
          textAnchor="end"
          className="alu-jor-zona__corte"
        >
          CORTE {fmt(zona.corteProximaZona)}
        </text>

        {/* O ponto do aluno. O anel na cor do fundo o separa da borda da faixa
            quando os dois se encostam. */}
        <circle
          cx={pontoX}
          cy={yPonto}
          r="7.5"
          fill="var(--alu-dado)"
          stroke="var(--alu-fundo)"
          strokeWidth="2.5"
        />
        <text x={pontoX + 14} y={yPonto + 4.5} className="alu-jor-zona__voce">
          VOCÊ · {fmt(zona.media)}
        </text>

        {/* A linha de cota: do ponto até a fronteira, com travessas nas duas
            pontas. O número dentro dela é a distância — e é ele que carrega o
            valor, porque a escada não tem escala numérica.

            O fio e as travessas são GEOMETRIA, e por isso neutros: docs/24 §7.2
            regra 2 reserva ALERTA para a ETIQUETA de distância, não para o
            desenho em volta dela. */}
        <line
          x1={cotaX}
          x2={cotaX}
          y1={yPonto}
          y2={yFronteira}
          stroke="var(--alu-texto-2)"
          strokeWidth="1.5"
        />
        <line
          x1={cotaX - 6}
          x2={cotaX + 6}
          y1={yPonto}
          y2={yPonto}
          stroke="var(--alu-texto-2)"
          strokeWidth="1.5"
        />
        <line
          x1={cotaX - 6}
          x2={cotaX + 6}
          y1={yFronteira}
          y2={yFronteira}
          stroke="var(--alu-texto-2)"
          strokeWidth="1.5"
        />
        <rect
          x={cotaX - larguraCota / 2}
          y={yCotaMeio - 10}
          width={larguraCota}
          height="20"
          rx="10"
          fill={corDaEtiqueta}
        />
        <text x={cotaX} y={yCotaMeio + 4} textAnchor="middle" className="alu-jor-zona__cota">
          {textoCota}
        </text>
      </svg>

      <p className="alu-jor-zona__leitura">
        {noTopo ? (
          <>
            Sua média é <strong>{fmt(zona.media)}</strong> e você está{' '}
            <strong>{fmt(distancia)}</strong> acima do corte de{' '}
            <strong>{fmt(zona.corteProximaZona)}</strong>.
          </>
        ) : (
          <>
            Sua média é <strong>{fmt(zona.media)}</strong>. Faltam{' '}
            <strong>{fmt(distancia)}</strong> para chegar a{' '}
            <strong>{fmt(zona.corteProximaZona)}</strong> e subir de zona
            {zona.materiaMaisCurta && (
              <> — a distância se fecha mais barato em {zona.materiaMaisCurta}</>
            )}
            .
          </>
        )}
      </p>
    </div>
  );
}

// ─── A trajetória ────────────────────────────────────────────────────────

/**
 * A linha do aluno ao longo do ano contra a linha de corte.
 *
 * `/me/trajetoria` está pronta desde sempre e nenhuma tela a desenhava
 * (docs/29 §A.5). Cada ponto é uma NOTA — a rota devolve uma linha por
 * `nota`, já em escala 0–10 e ordenada por data.
 *
 * ⚠️ O eixo da MÉDIA DA TURMA é aproximado, e é a segunda decisão não óbvia da
 * tela. A turma só existe em `/me/evolucao`, que agrega por CICLO; a
 * trajetória é por nota. As duas séries cobrem o mesmo ano letivo e saem das
 * mesmas linhas de `nota`, então os ciclos são distribuídos uniformemente na
 * mesma largura. A legenda diz "por ciclo" justamente para a diferença de
 * granularidade ficar visível em vez de escondida.
 */
function Trajetoria({
  pontos,
  corte,
  turma,
}: {
  pontos: PontoDaTrajetoria[];
  corte: number | null;
  turma: Array<number | null> | null;
}) {
  const L = 320;
  const A = 176;
  const x0 = 8;
  const x1 = L - 8;
  const y0 = 16;
  const y1 = 146;

  const n = pontos.length;
  const x = (i: number, total: number) =>
    total <= 1 ? (x0 + x1) / 2 : x0 + (i * (x1 - x0)) / (total - 1);
  const y = (nota: number) => y1 - (Math.min(10, Math.max(0, nota)) / 10) * (y1 - y0);

  const linha = pontos.map((p, i) => `${x(i, n)},${y(p.pontuacao)}`).join(' ');

  // Só o PRIMEIRO cruzamento de baixo para cima é marcado. Com uma nota por
  // matéria a linha atravessa o corte várias vezes, e marcar todas transforma
  // o marco em ruído.
  let cruzamento: { x: number; y: number } | null = null;
  if (corte != null) {
    for (let i = 1; i < n && !cruzamento; i++) {
      const antes = pontos[i - 1].pontuacao;
      const depois = pontos[i].pontuacao;
      if (antes < corte && depois >= corte) {
        const t = (corte - antes) / (depois - antes);
        cruzamento = { x: x(i - 1, n) + t * (x(i, n) - x(i - 1, n)), y: y(corte) };
      }
    }
  }

  const turmaPontos = (turma ?? [])
    .map((v, i) => ({ v, i }))
    .filter((p): p is { v: number; i: number } => p.v != null);
  const turmaLinha =
    turmaPontos.length > 1
      ? turmaPontos.map((p) => `${x(p.i, (turma ?? []).length)},${y(p.v)}`).join(' ')
      : null;

  const ultimo = pontos[n - 1];

  return (
    <div className="alu-jor-trajetoria">
      <svg
        viewBox={`0 0 ${L} ${A}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Suas ${n} notas em ordem, de ${fmt(pontos[0].pontuacao)} a ${fmt(
          ultimo.pontuacao,
        )}${corte != null ? `, contra a linha de corte em ${fmt(corte)}` : ''}.`}
        style={{ display: 'block', overflow: 'visible' }}
      >
        <title>Sua trajetória</title>

        {corte != null && (
          <>
            <line
              x1={x0}
              x2={x1}
              y1={y(corte)}
              y2={y(corte)}
              stroke="var(--alu-valor)"
              strokeWidth="2"
            />
            <text
              x={x1}
              y={Math.max(10, y(corte) - 6)}
              textAnchor="end"
              className="alu-jor-trajetoria__corte"
            >
              CORTE {fmt(corte)}
            </text>
          </>
        )}

        {turmaLinha && (
          <polyline
            points={turmaLinha}
            fill="none"
            stroke="var(--alu-texto-2)"
            strokeWidth="1.6"
            strokeDasharray="5 4"
            strokeLinejoin="round"
          />
        )}

        {n > 1 ? (
          <polyline
            points={linha}
            fill="none"
            stroke="var(--alu-dado)"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}

        {/* Com muitos pontos os círculos viram uma faixa sólida e escondem a
            linha; acima de 24 notas só a linha fica. */}
        {n <= 24 &&
          pontos.map((p, i) => (
            <circle
              // A rota devolve uma linha por nota, e duas notas do mesmo
              // simulado compartilham `simuladoId` — a posição entra na chave.
              key={`${p.simuladoId ?? 'sem-id'}-${i}`}
              cx={x(i, n)}
              cy={y(p.pontuacao)}
              r="2.8"
              fill="var(--alu-dado)"
            />
          ))}

        <circle
          cx={x(n - 1, n)}
          cy={y(ultimo.pontuacao)}
          r="5"
          fill="var(--alu-dado)"
          stroke="var(--alu-fundo)"
          strokeWidth="2"
        />

        {cruzamento && (
          <>
            <circle
              cx={cruzamento.x}
              cy={cruzamento.y}
              r="6.5"
              fill="none"
              stroke="var(--alu-valor)"
              strokeWidth="2.2"
            />
            {/* Acima do anel, salvo quando o cruzamento cai perto da direita:
                ali em cima já está o rótulo CORTE, ancorado em `x1`, e os dois
                se sobrepõem. Nesse caso a marca desce para baixo do anel. */}
            <text
              x={Math.min(x1 - 24, Math.max(x0 + 24, cruzamento.x))}
              y={
                cruzamento.x < x1 - 90
                  ? Math.max(10, cruzamento.y - 12)
                  : Math.min(A - 22, cruzamento.y + 18)
              }
              textAnchor="middle"
              className="alu-jor-trajetoria__marca"
            >
              CRUZOU
            </text>
          </>
        )}

        <text x={x0} y={A - 8} className="alu-jor-trajetoria__eixo">
          {fmtDataCurta(pontos[0].dataAplicacao)}
        </text>
        <text x={x1} y={A - 8} textAnchor="end" className="alu-jor-trajetoria__eixo">
          {fmtDataCurta(ultimo.dataAplicacao)}
        </text>
      </svg>

      <ul className="alu-jor-legenda">
        <li>
          <span className="alu-jor-legenda__fio" />
          você
        </li>
        {corte != null && (
          <li>
            <span className="alu-jor-legenda__fio alu-jor-legenda__fio--corte" />
            corte {fmt(corte)}
          </li>
        )}
        {turmaLinha && (
          <li>
            <span className="alu-jor-legenda__fio alu-jor-legenda__fio--turma" />
            média da turma · por ciclo
          </li>
        )}
      </ul>
    </div>
  );
}

// ─── Estado vazio ────────────────────────────────────────────────────────

/**
 * O aluno sem simulado nenhum. Convida a agir, e não avisa que está vazio —
 * o resto da tela continua no lugar, porque corrente, liga e conquistas já
 * dizem alguma coisa antes da primeira nota (docs/29 §E).
 */
function ConviteParaComecar() {
  return (
    <div className="alu-jor-depoimento">
      <p className="alu-jor-depoimento__chamada">
        Sua jornada começa no primeiro simulado. Até lá, o treino é o que move a linha.
      </p>
      <NavLink className="alu-tecla" to="/estudar">
        Treinar
      </NavLink>
    </div>
  );
}

// ─── Funções puras ───────────────────────────────────────────────────────

/**
 * O corte que vale para a linha da trajetória.
 *
 * O corte é POR MATÉRIA (4,0, e 5,0 no Inglês da Fase 1 do ITA), mas a
 * trajetória mistura as matérias numa linha só — então a régua desenhada é a
 * majoritária. Uma linha por matéria seria a leitura certa e é o mapa de calor
 * da aba Provas, não esta tela.
 */
function corteMajoritario(materias: MateriaContraCorte[] | undefined): number | null {
  if (!materias?.length) return null;
  const contagem = new Map<number, number>();
  for (const m of materias) contagem.set(m.corte, (contagem.get(m.corte) ?? 0) + 1);
  return [...contagem.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

/** A média da turma por ciclo, achatando as matérias. `null` quando não há. */
function mediaDaTurmaPorCiclo(
  evolucao: EvolucaoAluno | null | undefined,
): Array<number | null> | null {
  if (!evolucao?.ciclos.length) return null;
  const series = Object.values(evolucao.materias).map((m) => m.turma);
  if (!series.length) return null;

  const media = evolucao.ciclos.map((_, i) => {
    const valores = series.map((s) => s[i]).filter((v): v is number => v != null);
    if (!valores.length) return null;
    return valores.reduce((soma, v) => soma + v, 0) / valores.length;
  });

  return media.some((v) => v != null) ? media : null;
}

/**
 * Os elos de um ciclo a partir dos booleanos de presença.
 *
 * ⚠️ O rótulo é POSICIONAL ("P1", "P2"): `presencaNosSimulados` devolve só o
 * booleano, sem o nome do simulado. Quando a rota existir (docs/29 §A.2 —
 * `nota.presente`, hoje filtrado fora), ela precisa trazer o rótulo junto,
 * senão a corrente segue chamando de P3 um simulado que a coordenação chama de
 * outra coisa.
 */
function elosDoCiclo(presencas: boolean[]): EloDaCorrente[] {
  return presencas.map((presente, i) => ({
    simuladoId: null,
    rotulo: `P${i + 1}`,
    data: null,
    presente,
  }));
}

/** "18 de 20 simulados" — o resumo que vai no canto do bloco da corrente. */
function resumoDePresenca(
  ciclos: Array<{ ciclo: string; presencas: boolean[] }> | undefined,
): string | undefined {
  if (!ciclos?.length) return undefined;
  const todos = ciclos.flatMap((c) => c.presencas);
  if (!todos.length) return undefined;
  return `${todos.filter(Boolean).length} de ${todos.length} simulados`;
}
