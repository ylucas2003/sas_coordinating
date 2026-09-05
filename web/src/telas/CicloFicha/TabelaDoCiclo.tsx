import { Link } from 'react-router-dom';
import { corteDaMateria, eliminaSozinho, rotuloDoCorte } from '../../dominio/criterios';
import { LIMITES_RANKING, linhaVisivel } from '../../dominio/painel';
import type { ClassificacaoPorAluno, OrdenacaoPainel } from '../../dominio/painel';
import { distanciaAoCorte, formatarDistancia, seloDaNota } from '../../dominio/selo';
import type { TomNota } from '../../tipos/dominio';
import type { ColunaPainel, IgnoradasPorAluno, NotasPorAluno } from '../../dominio/painel';
import type { Aluno, CriterioClassificacao } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

// A VARREDURA DE UM CICLO — 900 alunos × as provas de UM ciclo.
//
// Esta tabela era `telas/Painel/TabelaPainel.tsx` e mudou de casa (docs/39
// §PRECEDÊNCIA). O argumento: ela SEMPRE foi de um ciclo só, e a primeira
// coisa que o coordenador fazia ao chegar no Painel era escolher o ciclo numa
// faixa de filtros — a tela pedia um contexto que a URL podia dar. Aqui o
// ciclo vem da rota, o ano e o vestibular vêm junto, e a régua vem herdada do
// topo da ficha.
//
// Ela também ABSORVEU `CicloRegua.tsx`, que era uma segunda tabela dos mesmos
// alunos do mesmo ciclo. Duas colunas vieram de lá e não podiam se perder na
// fusão, porque são a única explicação de corte que este produto tem:
//
//   Situação  — o motivo em PALAVRAS ("Física 3,2 < 4,0", "Passou"), que diz
//               qual matéria e qual mínimo. Uma célula vermelha não diria
//               nada disso (R4/R7).
//   Distância — o tamanho do buraco, e o número pelo qual a tabela está
//               ordenada (R6). Ele saíra do Painel porque repetia a pior
//               etiqueta das células; volta porque aqui é o ordenador, e uma
//               ordenação cujo número não aparece não se confere.
//
// Elas entram como COLUNAS, não como tooltip: num tooltip teriam se perdido na
// fusão (prancheta de Provas, "SITUAÇÃO E DISTÂNCIA SÃO COLUNAS, NÃO
// TOOLTIP").
//
// ⚠️ Uma coluna por SIMULADO, agrupadas por matéria, com o fio forte marcando
// a virada de fase. O Kit de peças da prancheta mostra uma versão por matéria;
// ali é prancheta de peça e aqui é a tela, e a tela vence (docs/39 §1).
//
// As classes continuam `.painel-tabela*`, agora em `styles/ciclo.css`: renomeá-las
// no mesmo commit em que a tabela muda de casa tiraria a chance de ver, no
// diff, o que a mudança de casa fez. O nome é herança, como `get_supabase()`.

interface Props {
  alunos: readonly Aluno[];
  colunas: readonly ColunaPainel[];
  notasAluno: NotasPorAluno;
  /** O que a média deixou de fora — a célula mostra, marcado. */
  notasIgnoradas: IgnoradasPorAluno;
  /**
   * Quem faltou, por simulado: `ausencias[alunoId][simuladoId]`.
   *
   * Opcional e hoje vazio: nenhuma consulta do front devolve ausência
   * separada de "nota não lançada" (`GET /simulados/{id}/notas` só diz se a
   * nota existe e se é computável). Enquanto não devolver, a célula cai na
   * hachura de "sem nota" — que é a leitura honesta, porque não sabemos.
   * O que NÃO pode acontecer é a falta virar zero: zero é desempenho medido,
   * e falta contando como zero deturpa toda média do ciclo.
   */
  ausencias?: AusenciasPorAluno;
  mediasVirtuais: Record<string, Record<string, number | null>>;
  mediasPorColuna: Record<string, number | null>;
  /** Veredito, motivo e cor por aluno — vem do servidor. */
  classificacao: ClassificacaoPorAluno;
  /** A régua em vigor. É dela que sai o corte de cada matéria, e sem ela o
      selo não tem como desenhar distância — só lado. */
  criterio: CriterioClassificacao | null;
  /** Qual ordenação está em vigor — R6 exige que ela seja VISÍVEL e NOMEADA. */
  ordenacao: OrdenacaoPainel;
  /**
   * A segunda linha da coluna do nome: turma, sede, o que o casco souber.
   *
   * É função e não mapa porque quem monta a tela é quem tem `useTurmas` e
   * `useSedes` — a tabela não busca nada (nenhum `fetch` em componente).
   * Devolver `null` some com a linha: melhor um nome sozinho do que um "—"
   * que se lê como turma sem nome.
   */
  nomeDaTurma?: (aluno: Aluno) => string | null;
  recolhidos: ReadonlySet<number>;
  /** `null` fora do modo ranking — os separadores só fazem sentido ordenado. */
  onToggleLimite: ((posicao: number) => void) | null;
  onEditarNota: (alunoId: string, simuladoId: string) => void;
}

/** Quem faltou, por simulado: `ausencias[alunoId][simuladoId]`. */
export type AusenciasPorAluno = Record<string, Record<string, boolean>>;

/** O nome do ordenador, como ele aparece no cabeçalho da tabela (R6). */
const ROTULO_ORDEM: Record<OrdenacaoPainel, string> = {
  distancia: 'distância do corte, pior primeiro',
  ranking: 'classificação do critério',
  alfabetica: 'nome, A–Z',
};

/**
 * A matéria em três letras no cabeçalho.
 *
 * Doze colunas a 52px só cabem em 1440 com o rótulo curto — é a conta da
 * prancheta, e é o que faz a virada de fase caber na tela sem rolagem
 * horizontal. Matéria fora da lista cai no rótulo inteiro: a coluna fica mais
 * larga, o que é preferível a inventar uma abreviação que ninguém reconhece.
 * O nome completo continua no `title` do cabeçalho.
 */
const ABREV_MATERIA: Record<string, string> = {
  Matemática: 'Mat',
  Física: 'Fís',
  Química: 'Quí',
  Português: 'Por',
  Inglês: 'Ing',
  Redação: 'Red',
};

/** "Ana Beatriz Correia" → "AC". Duas letras, como na prancheta. */
function iniciaisDe(nome: string): string {
  return nome
    .split(/\s+/)
    .filter(Boolean)
    .map((parte) => parte[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

function classeColuna(col: ColunaPainel, base: string): string {
  return [base, col.novaFase && 'borda-nova-fase', col.destaque && 'col-destaque']
    .filter(Boolean)
    .join(' ');
}

/**
 * O selo de uma nota — PREENCHIDO acima do corte, VAZADO abaixo (R1), com a
 * intensidade carregando a distância (R3) e a etiqueta em vermelho como único
 * alerta (R4). Ver `dominio/selo.ts`.
 *
 * A régua NÃO é decidida aqui. O corte vem resolvido do servidor e é lido por
 * `corteDaMateria` — reimplementar o encadeamento em TypeScript foi o que a
 * Sprint 2 proibiu (docs/18 §1.2).
 *
 * Quando não há corte aplicável — coluna virtual de média, ou classificação
 * ainda carregando —, cai no `tom` que o servidor mandou. Ele diz o lado mas
 * não diz a distância, então o desenho fica sem etiqueta e com intensidade
 * fixa: é menos informação, e é honesto que pareça menos.
 */
const INTENSIDADE_SEM_CORTE: Record<TomNota, { classe: string; intensidade: number }> = {
  verde: { classe: 'nota-badge--acima', intensidade: 0.7 },
  ambar: { classe: 'nota-badge--acima', intensidade: 0.15 },
  vermelho: { classe: 'nota-badge--abaixo', intensidade: 0.5 },
};

function NotaBadge({
  nota, tom, corte, daTurma = false, titulo,
}: {
  nota: number | null;
  tom?: TomNota;
  corte?: number | null;
  daTurma?: boolean;
  titulo?: string;
}) {
  if (nota == null) {
    return <span className="nota-badge nota-badge--vazia" title="sem nota lançada">—</span>;
  }

  // A média da turma é REFERÊNCIA, não desempenho de ninguém (R5): fica
  // neutra, atrás do dado, em vez de disputar a leitura com as linhas.
  if (daTurma) {
    return (
      <span className="nota-badge nota-badge--media" title={titulo}>
        {fmtNota(nota)}
      </span>
    );
  }

  const selo = seloDaNota(nota, corte);
  const semRegua = selo.estado === 'sem-dado';
  const alternativa = semRegua && tom ? INTENSIDADE_SEM_CORTE[tom] : null;

  const classe = alternativa
    ? alternativa.classe
    : semRegua
      ? ''
      : `nota-badge--${selo.estado}${selo.estado === 'acima' && selo.intensidade > 0.5 ? ' nota-badge--acima-forte' : ''}`;
  const intensidade = alternativa ? alternativa.intensidade : selo.intensidade;

  return (
    <>
      <span
        className={`nota-badge ${classe}`.trimEnd()}
        style={{ '--nota-intensidade': intensidade } as React.CSSProperties}
        title={titulo}
      >
        {fmtNota(nota)}
      </span>
      {selo.etiqueta && (
        // `title` e não `aria-label`: um `<span>` sem role não suporta
        // `aria-label`, e o texto visível já é a informação — a etiqueta É o
        // número. O `title` só acrescenta contra o quê ele é medido.
        <span className="nota-etiqueta" title={`${selo.etiqueta} em relação ao corte da matéria`}>
          {selo.etiqueta}
        </span>
      )}
    </>
  );
}

/**
 * O glifo de AUSÊNCIA — e ele não é um zero.
 *
 * Falta contando como zero deturpa toda média do ciclo, e é problema conhecido
 * do domínio (memória do projeto: "zeros = prováveis ausências"). Por isso a
 * ausência tem forma própria: vazado tracejado com um travessão, distinto da
 * hachura de "nota não lançada" — uma diz "esta pessoa não fez", a outra diz
 * "ninguém lançou ainda", e confundi-las manda o coordenador cobrar a pessoa
 * errada.
 */
function NotaAusenteBadge() {
  return (
    <span className="nota-badge nota-badge--ausente" title="ausente — não entra na média">
      —
    </span>
  );
}

/** Motivo técnico → frase. `motivo` novo cai no texto genérico, sem quebrar. */
const TEXTO_IGNORADA: Record<string, string> = {
  todas_em_branco: 'nenhuma alternativa marcada',
};

/**
 * A nota que a média não somou — visível, riscada, e dizendo por quê.
 *
 * Regra da casa: um número que o produto decidiu ignorar precisa DIZER que
 * ignorou. Some-lo da tela esconderia a decisão; deixá-lo igual aos outros
 * faria o coordenador somar de cabeça um valor que o sistema não somou
 * (docs/32 §1.5, item 7).
 */
function NotaIgnoradaBadge({ nota, motivo }: { nota: number | null; motivo: string | null }) {
  const explicacao = (motivo && TEXTO_IGNORADA[motivo]) || 'não entra na média';
  return (
    <span
      className="nota-badge nota-badge--ignorada"
      title={`${fmtNota(nota)} — ${explicacao}; não entra na média`}
    >
      {fmtNota(nota)}
    </span>
  );
}

/**
 * O cabeçalho de uma coluna de simulado: a fase em cima, a matéria embaixo.
 *
 * R2 · A RÉGUA ESTÁ SEMPRE DESENHADA E ROTULADA. Quando o corte da matéria
 * diverge do majoritário, ele aparece aqui, em ouro, colado no nome — o
 * Inglês da Fase 1 do ITA exige 5,0 e é a única eliminatória, e uma tabela
 * que desenha todas as colunas contra "4,0" mente exatamente na matéria que
 * mais elimina. Quando o corte é o de todo mundo, o número não se repete
 * doze vezes: ele já está dito na régua, no topo da ficha.
 */
function RotuloDaMateria({
  col, criterio,
}: {
  col: ColunaPainel;
  criterio: CriterioClassificacao | null;
}) {
  const materia = col.sim?.materia?.codigo ?? null;
  const corte = col.virtual ? null : corteDaMateria(criterio, materia);
  const diverge = corte != null && criterio != null && corte !== criterio.corteGenerico;
  const curto = ABREV_MATERIA[col.label] ?? col.label;

  return (
    <>
      <span className="painel-tabela__materia">{curto}</span>
      {diverge && (
        <span
          className="painel-tabela__corte"
          title={rotuloDoCorte(corte, eliminaSozinho(criterio, materia))}
        >
          {fmtNota(corte)}
        </span>
      )}
    </>
  );
}

export function TabelaDoCiclo({
  alunos, colunas, notasAluno, notasIgnoradas, ausencias, mediasVirtuais, mediasPorColuna,
  classificacao, criterio, ordenacao, nomeDaTurma,
  recolhidos, onToggleLimite, onEditarNota,
}: Props) {
  // #, Aluno, as colunas de prova, Situação e Distância. O separador de
  // ranking atravessa a linha inteira e precisa da conta certa — ela estava
  // errada em dois antes da mudança de casa, e a linha vazava para fora da
  // tabela sem que nada reclamasse.
  const totalColunas = colunas.length + 4;

  return (
    <div className="painel-tabela-wrap">
      {/* R6 · o ordenador em vigor é visível e NOMEADO. Sem a cor, é a ordem
          que entrega o aluno em risco — e uma ordem que o coordenador não sabe
          qual é não entrega nada. */}
      <div className="painel-tabela-ordem">
        <span className="painel-tabela-ordem__total">
          {alunos.length} {alunos.length === 1 ? 'aluno' : 'alunos'}
        </span>
        <span className="painel-tabela-ordem__pilula">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <path d="M12 5v14M7 14l5 5 5-5" />
          </svg>
          {ROTULO_ORDEM[ordenacao]}
        </span>
      </div>
      <table className="painel-tabela">
        <thead>
          {/* A FASE em cima, a matéria embaixo: é a ordem da prancheta, e é a
              que agrupa. Doze colunas seguidas sem a faixa de fase por cima
              leem como doze provas soltas — o que o coordenador procura é
              "como foi a Fase 1", e depois qual matéria dentro dela. */}
          <tr>
            <th className="painel-tabela__th-pos" rowSpan={2}>#</th>
            <th className="painel-tabela__th-aluno" rowSpan={2}>Aluno</th>
            {colunas.map((col) => (
              <th key={col.id} className={classeColuna(col, 'painel-tabela__th-fase')}>
                {col.fase}
              </th>
            ))}
            <th className="painel-tabela__th-situacao" rowSpan={2}>Situação</th>
            <th className="painel-tabela__th-dist" rowSpan={2}>Distância</th>
          </tr>
          <tr>
            {colunas.map((col) => (
              <th
                key={col.id}
                className={classeColuna(col, 'painel-tabela__th-col')}
                title={col.label}
              >
                <RotuloDaMateria col={col} criterio={criterio} />
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {/* A referência fica NO TOPO, e não no rodapé: o coordenador compara
              enquanto varre, e uma média da turma no fim de 900 linhas só é
              lida por quem já terminou de varrer. */}
          <tr className="painel-tabela__tr-media">
            <td className="painel-tabela__td-pos" />
            <td className="painel-tabela__td-aluno">Média da turma</td>
            {colunas.map((col) => (
              <td key={col.id} className={classeColuna(col, 'painel-tabela__td-nota')}>
                <NotaBadge nota={mediasPorColuna[col.id] ?? null} daTurma />
              </td>
            ))}
            <td className="painel-tabela__td-situacao" />
            <td className="painel-tabela__td-dist" />
          </tr>

          {alunos.flatMap((aluno, i) => {
            const pos = i + 1;
            if (!linhaVisivel(pos, recolhidos)) return [];

            const veredito = classificacao[aluno.id];
            const extra = !veredito ? '' : veredito.aprovado ? ' is-aprovado' : ' is-cortado';
            const turma = nomeDaTurma?.(aluno) ?? null;
            const distancia = distanciaAoCorte(veredito, criterio);

            const linha = (
              <tr key={aluno.id}>
                <td className="painel-tabela__td-pos">
                  <span className="pos-badge">{pos}</span>
                </td>
                <td className="painel-tabela__td-aluno">
                  <Link
                    className={`painel-tabela__aluno-link${extra}`}
                    to={`/alunos/${aluno.id}`}
                    title={veredito?.motivo ? `${aluno.nome} — cortado: ${veredito.motivo}` : aluno.nome}
                  >
                    {/* As iniciais não são enfeite: numa lista de 900 nomes
                        parecidos, o disco é a âncora que o olho reencontra ao
                        voltar de uma rolagem horizontal. */}
                    <span className="painel-tabela__iniciais" aria-hidden="true">
                      {iniciaisDe(aluno.nome)}
                    </span>
                    <span className="painel-tabela__aluno-texto">
                      <span className="painel-tabela__nome">{aluno.nome}</span>
                      {turma && <span className="painel-tabela__turma">{turma}</span>}
                    </span>
                  </Link>
                </td>
                {colunas.map((col) => {
                  const nota = col.virtual
                    ? mediasVirtuais[aluno.id]?.[col.id] ?? null
                    : col.sim
                      ? notasAluno[aluno.id]?.[col.sim.id] ?? null
                      : null;
                  const editavel = !col.virtual && !!col.sim;
                  const ignorada = col.sim ? notasIgnoradas[aluno.id]?.[col.sim.id] : undefined;
                  const ausente = col.sim ? ausencias?.[aluno.id]?.[col.sim.id] : false;

                  const conteudo = ignorada ? (
                    <NotaIgnoradaBadge nota={ignorada.nota} motivo={ignorada.motivo} />
                  ) : ausente ? (
                    <NotaAusenteBadge />
                  ) : (
                    <NotaBadge
                      nota={nota}
                      tom={col.sim?.materia?.codigo ? veredito?.notas[col.sim.materia.codigo]?.tom : undefined}
                      corte={col.virtual ? null : corteDaMateria(criterio, col.sim?.materia?.codigo)}
                    />
                  );

                  return (
                    <td key={col.id} className={classeColuna(col, 'painel-tabela__td-nota')}>
                      {editavel ? (
                        // Botão, e não `<td onClick>`: a escrita de nota é a
                        // única ação da tabela e precisa existir no teclado.
                        // Ele ocupa a célula inteira, que é o que faz o alvo
                        // chegar aos 44px da altura de linha.
                        <button
                          type="button"
                          className="painel-tabela__celula"
                          // O rótulo diz o que o clique FAZ e sobre quem — a
                          // nota visível não é rótulo suficiente para quem
                          // chega pelo leitor de tela, que não vê a coluna.
                          aria-label={`Editar ${col.label} ${col.fase} de ${aluno.nome}`}
                          onClick={(ev) => {
                            ev.stopPropagation();
                            onEditarNota(aluno.id, col.sim!.id);
                          }}
                        >
                          {conteudo}
                        </button>
                      ) : (
                        conteudo
                      )}
                    </td>
                  );
                })}

                {/* A SITUAÇÃO é palavra, não cor: o motivo já diz qual matéria
                    e qual mínimo (R4/R7). "Passou" fica em referência, porque
                    quem passou não é o assunto da varredura; o motivo do corte
                    fica em texto cheio. Sem veredito nenhum não se escreve
                    "Passou" — escreve-se que não sabemos. */}
                <td className="painel-tabela__td-situacao">
                  {!veredito ? (
                    <span className="painel-tabela__situacao--vazia" title="ainda sem classificação">—</span>
                  ) : veredito.aprovado ? (
                    <span className="painel-tabela__situacao--passou">Passou</span>
                  ) : (
                    <span title={veredito.motivo ?? undefined}>{veredito.motivo ?? 'Cortado'}</span>
                  )}
                </td>

                {/* A DISTÂNCIA é o número pelo qual a tabela está ordenada.
                    Vermelho só aqui e na etiqueta da célula (R4). Nulo é "—",
                    nunca 0,0: quem não tem nota com régua aplicável não está a
                    zero do corte, está sem medida. */}
                <td className="painel-tabela__td-dist">
                  <span
                    className={`painel-tabela__dist${
                      distancia != null && distancia < 0 ? ' painel-tabela__dist--abaixo' : ''
                    }${distancia == null ? ' painel-tabela__dist--vazia' : ''}`}
                    title={distancia == null ? 'sem nota com régua aplicável' : 'a pior distância entre as matérias com nota'}
                  >
                    {distancia == null ? '—' : formatarDistancia(distancia)}
                  </span>
                </td>
              </tr>
            );

            // Separador de ranking depois da posição N (só no modo ranking).
            if (onToggleLimite && LIMITES_RANKING.includes(pos) && i < alunos.length - 1) {
              return [
                linha,
                <SeparadorRanking
                  key={`sep-${pos}`}
                  posicao={pos}
                  colunas={totalColunas}
                  recolhido={recolhidos.has(pos)}
                  onToggle={onToggleLimite}
                />,
              ];
            }
            return [linha];
          })}
        </tbody>
      </table>
    </div>
  );
}

function SeparadorRanking({
  posicao, colunas, recolhido, onToggle,
}: {
  posicao: number;
  /** Quantas colunas a linha atravessa — a tabela inteira. */
  colunas: number;
  recolhido: boolean;
  onToggle: (p: number) => void;
}) {
  return (
    <tr className="painel-corte-row">
      <td className="painel-corte__label" colSpan={colunas}>
        <span className="painel-corte__tag">{`Top ${posicao}`}</span>
        <button className="painel-corte__btn" onClick={() => onToggle(posicao)}>
          {recolhido ? `▼ exibir abaixo do ${posicao}°` : `▲ ocultar abaixo do ${posicao}°`}
        </button>
      </td>
    </tr>
  );
}
