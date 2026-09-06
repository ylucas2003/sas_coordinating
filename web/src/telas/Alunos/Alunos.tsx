import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

// A folha desta tela. Importada aqui, e não em `main.tsx`, porque `main.tsx`
// não é desta rodada — ver a pendência no relatório da fase 4.
import '../../../styles/alunos.css';

import { Avatar } from '../../componentes/ui/Avatar';
import { CartaoDeEntrada } from '../../componentes/ui/Campo';
import { Sparkline } from '../../componentes/ui/Sparkline';
import { BarraFiltros, Busca, Pills, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { ordenarLinhas, proximaOrdenacao } from '../../componentes/ui/ordenacao';
import type { ColunaTabela, Ordenacao } from '../../componentes/ui/ordenacao';
import { ROTULO_DA_REFEICAO } from '../../dominio/cantina';
import { corteDaMateria, eliminaSozinho, reguaDaCasa, rotuloDoCorte } from '../../dominio/criterios';
import { resumirSelecao, resumirTexto } from '../../dominio/filtros';
import {
  aplicarRecorte,
  contarRecortes,
  contarRiscoCaindo,
  extremosPorMedia,
  lerRecorte,
  mediaDasMedias,
} from '../../dominio/recorteDeAlunos';
import type { Recorte } from '../../dominio/recorteDeAlunos';
import { guardarRecorteDeRevisao, lerRecorteDeRevisao } from '../../dominio/revisaoEmSequencia';
import { seloDaNota } from '../../dominio/selo';
import {
  useAlunos,
  useCriteriosDisponiveis,
  useRotulosDasMedias,
  useSedes,
  useTurmas,
} from '../../hooks/consultas';
import { MATERIAS_DO_DETALHAMENTO } from '../../tipos/dominio';
import type { Aluno, CriterioClassificacao, MateriaDetalhada } from '../../tipos/dominio';
import type { Refeicao } from '../../tipos/cantina';
import { fmtNota, normalizar } from '../../util/formato';

// A LISTA DE 900 — quem são eles e como estão.
//
// A tela responde a UMA pergunta, e por isso **não** vira hub de campos: o
// padrão de campo (`componentes/ui/Campo.tsx`) entra onde uma tela mistura
// perguntas diferentes, e aqui não mistura. O que ela toma emprestado dali é
// só a faixa de entrada — quatro atalhos que APLICAM RECORTE e não levam a
// lugar nenhum novo.
//
// ── R7 · UMA ESCALA SEMÂNTICA POR TELA ────────────────────────────────────
//
// Cinco escalas disputavam a mesma linha: média (número), tendência (tag
// colorida), perfil (palavra), zona (tag colorida) e trajetória (gráfico em
// escala própria). Cinco vocabulários para ler uma linha é o mesmo que
// nenhum — o olho não sabe qual deles responde "este aluno precisa de mim?".
//
// A escala que carrega a varredura é **a nota contra o corte**: preenchido
// acima, vazado abaixo, intensidade carregando a distância (R1/R3). Ela é a
// única com cor, e vale para as duas coisas que a usam — as células de média
// e a trajetória, que agora dividem a MESMA régua de 0 a 10 com o mesmo corte
// desenhado. Ler a linha é ler forma: uma fileira de células cheias, uma
// fileira de buracos.
//
// As outras quatro ficaram quietas:
//
//   zona · tendência · perfil   Saíram das tags `tone-*` e viraram PALAVRA em
//        texto secundário. Elas não sumiram — mudaram de papel: agora são
//        ORDENADORES (R6), e é ordenando por elas que o coordenador as usa.
//        Uma tag colorida ao lado de um selo de nota faz o olho decidir entre
//        duas cores que medem coisas diferentes.
//   direitos de refeição   Nunca foi escala: é cadastro. Entra como FORMA —
//        pílula com glifo, sem cor semântica — e ordena por ordem semântica
//        (nenhum → almoço → janta → os dois), não alfabética.
//
// ── A régua tem nome ──────────────────────────────────────────────────────
//
// A zona é uma leitura contra um corte, e a tela nunca dizia contra qual. O
// mesmo aluno era lido de dois jeitos em duas telas sem que nenhuma
// declarasse a régua. A tarja do cabeçalho declara — e não há seletor aqui de
// propósito: trocar a régua é decisão do ciclo, e acontece na ficha dele.
//
// ── A rolagem É a interação ───────────────────────────────────────────────
//
// 900 linhas, sem paginação, sem teto e sem "carregar mais" — decisão
// registrada do projeto (CLAUDE.md, armadilha 2: um teto truncaria a leitura
// em silêncio). O desenho assume isso: a tela ocupa a altura da janela, só a
// tabela rola, o cabeçalho fica grudado, e a contagem em vigor mora DENTRO
// dele — um "902" cravado a 40px de "3 de 902" é a contradição que este ramo
// pune, e um cabeçalho que rola para fora deixa 900 linhas sem legenda.

/** Quanto vale cada refeição na ordenação: nenhum(0) → almoço(1) → janta(2) → os dois(3). */
const PESO_DA_REFEICAO: Record<Refeicao, number> = { almoco: 1, janta: 2 };

/** O glifo de cada refeição — a coluna de direitos é FORMA, não cor. */
const GLIFO_DA_REFEICAO: Record<Refeicao, string> = {
  almoco: 'M7 3v7a3 3 0 0 0 6 0V3M10 13v8M16 3c2 0 3 1.6 3 4s-1 4-3 4v10',
  janta: 'M4 10h16a8 8 0 0 1-16 0zM12 3.4v3.2M6 20h12',
};

// As palavras que substituíram as tags. Minúsculas de propósito: elas são
// leitura de apoio, não etiqueta — e uma palavra em caixa alta volta a
// disputar a linha com o selo.
const PALAVRA_DA_ZONA = { top: 'top', cinzenta: 'cinzenta', risco: 'risco' } as const;
const PALAVRA_DA_TENDENCIA = { subindo: 'subindo', estavel: 'estável', caindo: 'caindo' } as const;
const PALAVRA_DO_PERFIL = { ancora: 'âncora', misterio: 'mistério', regular: 'regular' } as const;

// Ordem semântica das colunas categóricas — do que pede atenção ao que não
// pede. Ordenar alfabeticamente ("cinzenta, risco, top") não diria nada.
const ORDEM_ZONA = ['risco', 'cinzenta', 'top'] as const;
const ORDEM_TENDENCIA = ['caindo', 'estavel', 'subindo'] as const;
const ORDEM_PERFIL = ['regular', 'misterio', 'ancora'] as const;

type GrupoId = 'ano' | 'primeiroCiclo' | 'ultimoCiclo';

/**
 * Os três grupos de média, na ordem em que a lista os lê.
 *
 * O nome do grupo é o botão de EXPANDIR; a seta ao lado é o de ORDENAR. Um
 * grupo aberto por vez: dois abertos somam oito colunas de nota e a linha
 * deixa de ser lida — a tabela vira planilha, que é o que esta tela não é.
 */
const GRUPOS: ReadonlyArray<{ id: GrupoId; rotulo: string }> = [
  { id: 'ano', rotulo: 'Média do ano' },
  { id: 'primeiroCiclo', rotulo: 'Média do 1º ciclo' },
  { id: 'ultimoCiclo', rotulo: 'Média do último ciclo' },
];

/** Três letras no cabeçalho da subcoluna; o nome inteiro fica no `title`. */
const ABREV_MATERIA: Record<MateriaDetalhada, string> = {
  matematica: 'Mat',
  fisica: 'Fís',
  quimica: 'Quí',
};

const NOME_MATERIA: Record<MateriaDetalhada, string> = {
  matematica: 'Matemática',
  fisica: 'Física',
  quimica: 'Química',
};

/** Uma coluna de nota: o total do grupo, ou uma das três matérias dele. */
interface ColunaDeMedia {
  chave: string;
  grupo: GrupoId;
  ehGrupo: boolean;
  rotulo: string;
  /** O nome por extenso, para o rótulo da ordem: "Matemática · Média do ano". */
  rotuloLongo: string;
  /** O que o número é NESTA carga ("2026", "1º Ciclo · ITA"), vindo do servidor. */
  referencia?: string | null;
  /** A célula inteira em palavras, para o `title`: "Física · Média do ano · 2026". */
  titulo: string;
  materia?: MateriaDetalhada;
  /** O corte contra o qual esta coluna é lida. `null` = sem régua carregada. */
  corte: number | null;
  /** O grupo a que pertence está aberto — o bloco ganha fundo próprio. */
  aberto: boolean;
  /** Última coluna do bloco aberto: fecha o traço à direita. */
  fim?: boolean;
}

/** A coluna da tabela, com como se lê a ordem dela nos dois sentidos (R6). */
interface ColunaDaLista extends ColunaTabela<Aluno> {
  sentidos?: readonly [string, string];
}

/** "23 alunos" · "1 aluno" · "ninguém" — contagem com concordância, e sem "0 alunos". */
function contagemEmPalavras(n: number): string {
  if (n === 0) return 'ninguém';
  return `${n} ${n === 1 ? 'aluno' : 'alunos'}`;
}

function notaDaCelula(aluno: Aluno, coluna: ColunaDeMedia): number | null {
  const grupo = aluno.medias?.[coluna.grupo];
  if (!grupo) return null;
  return coluna.materia ? grupo[coluna.materia] : grupo.geral;
}

/**
 * O peso dos direitos, para a ordenação.
 *
 * `undefined` (o aluno não veio das rotas de coordenação) devolve `null` e
 * afunda; lista vazia devolve 0 e ordena como "nenhum". São coisas
 * diferentes: uma é não saber, a outra é saber que não tem.
 */
function pesoDosDireitos(aluno: Aluno): number | null {
  if (!aluno.direitos) return null;
  return aluno.direitos.reduce((soma, refeicao) => soma + PESO_DA_REFEICAO[refeicao], 0);
}

/**
 * O selo de uma média — preenchido acima do corte, vazado abaixo (R1), com a
 * intensidade carregando a distância (R3) e a etiqueta como único alerta (R4).
 *
 * Sem régua carregada o selo fica neutro e **não** vira "aprovado": ele mostra
 * o número sem dizer o lado, que é exatamente o que se sabe nesse momento.
 */
function CelulaDeNota({ nota, corte, titulo }: {
  nota: number | null;
  corte: number | null;
  titulo?: string;
}) {
  if (nota == null) {
    return (
      <span className="nota-badge nota-badge--vazia" title="sem nota neste recorte">
        —
      </span>
    );
  }

  const selo = seloDaNota(nota, corte);
  const semRegua = selo.estado === 'sem-dado';
  const forte = selo.estado === 'acima' && selo.intensidade > 0.5;
  const classe = semRegua ? '' : `nota-badge--${selo.estado}${forte ? ' nota-badge--acima-forte' : ''}`;

  return (
    <>
      <span
        className={`nota-badge ${classe}`.trimEnd()}
        style={{ '--nota-intensidade': selo.intensidade } as React.CSSProperties}
        title={titulo}
      >
        {fmtNota(nota)}
      </span>
      {selo.etiqueta && (
        <span className="nota-etiqueta" title={`${selo.etiqueta} em relação ao corte`}>
          {selo.etiqueta}
        </span>
      )}
    </>
  );
}

/**
 * Os direitos de refeição — dado de CADASTRO, não de desempenho.
 *
 * Entra como forma, sem cor semântica: quem almoça na escola não está melhor
 * nem pior do que quem não almoça, e pintá-lo na mesma escala das notas
 * inventaria uma leitura que não existe.
 *
 * ⚠️ A restrição alimentar **não** entra nesta coluna. É dado de saúde de
 * menor, a categoria mais sensível da LGPD, e vive na tela de direitos da
 * cantina, com o texto sob clique (docs/38 §2.6).
 */
function CelulaDeDireitos({ direitos }: { direitos?: Refeicao[] }) {
  if (!direitos) {
    return <span className="alunos-quieto" title="não veio nesta carga">—</span>;
  }
  if (!direitos.length) {
    return <span className="alunos-quieto">nenhum</span>;
  }
  return (
    <span className="alunos-direitos">
      {direitos.map((refeicao) => (
        <span className="alunos-direito" key={refeicao}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d={GLIFO_DA_REFEICAO[refeicao]} />
          </svg>
          {ROTULO_DA_REFEICAO[refeicao]}
        </span>
      ))}
    </span>
  );
}

/**
 * A RÉGUA EM VIGOR, dita com todas as letras.
 *
 * R2 · a régua está sempre desenhada e rotulada. A zona vem classificada pelo
 * servidor sob a régua da casa, e uma coluna que diz "risco" sem dizer contra
 * o quê é veredito sem juiz — a mesma pessoa lida por duas réguas em duas
 * telas, e nenhuma delas dizendo qual.
 */
function TarjaDaRegua({ regua, corte }: { regua: CriterioClassificacao | null; corte: number | null }) {
  return (
    <div className={`alunos-regua${regua ? '' : ' alunos-regua--sem'}`}>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
        strokeWidth="2" strokeLinecap="round" strokeDasharray="3 2" aria-hidden="true">
        <path d="M4 12h16" />
      </svg>
      <span>
        <span className="alunos-regua__titulo">
          {regua
            ? `Médias, zona e trajetória contra a régua ${regua.nome}`
            : 'Sem régua carregada'}
        </span>
        <span className="alunos-regua__sub">
          {regua
            ? `${corte != null ? `${rotuloDoCorte(corte, false)} onde ela não pede outro` : 'sem corte declarado'} · a régua do colégio, a mesma que o aluno vê · trocá-la é decisão do ciclo`
            : 'as notas aparecem sem o corte desenhado — o selo diz o número, não o lado'}
        </span>
      </span>
    </div>
  );
}

/** Lista de 900 — varredura por médias, trajetória e cadastro. */
export function Alunos() {
  const { data: alunos = [], isPending, isError, error } = useAlunos();
  const { data: turmas = [] } = useTurmas();
  const { data: sedes = [] } = useSedes();
  const { data: criterios = [] } = useCriteriosDisponiveis();
  // Desestruturado, e remontado num `useMemo`, porque `useRotulosDasMedias`
  // devolve objeto novo a cada render: dependendo dele direto, as colunas —
  // e a ORDENAÇÃO de 900 linhas atrás delas — se recalculariam sempre.
  const { ano: refAno, primeiroCiclo: refPrimeiro, ultimoCiclo: refUltimo } = useRotulosDasMedias();
  const rotulos = useMemo(
    () => ({ ano: refAno, primeiroCiclo: refPrimeiro, ultimoCiclo: refUltimo }),
    [refAno, refPrimeiro, refUltimo],
  );

  // A régua NÃO se escolhe aqui (ver `TarjaDaRegua`): é a mesma que produziu a
  // coluna Zona no servidor, e quem a resolve é `dominio/criterios.ts` — o
  // slug morava aqui numa constante local, e a mesma constante existia com
  // outro nome no Painel.
  const regua = reguaDaCasa(criterios);
  const corteGeral = corteDaMateria(regua, null);

  const [busca, setBusca] = useState('');
  // 🐛 O alerta de turma/sede aponta para `/alunos?turmaId=X` — `_href_para_entidade`
  // em `routes/alertas.py` monta assim desde a Sprint 1 —, e esta tela nunca
  // leu a query: os filtros moram em `useState`, e o link caía numa lista sem
  // filtro nenhum. Resíduo do hash router anterior à migração React, achado ao
  // ligar a faixa de decisão (docs/33 §3).
  //
  // Semente inicial, não sincronização: depois do primeiro render quem manda é
  // o clique do usuário. Amarrar os dois faria a pílula brigar com a URL.
  const [params, setParams] = useSearchParams();
  const [turmasSel, setTurmasSel] = useState<ReadonlySet<string>>(
    () => new Set(params.getAll('turmaId')),
  );
  const [sedesSel, setSedesSel] = useState<ReadonlySet<string>>(
    () => new Set(params.getAll('sedeId')),
  );

  // ⚠️ O RECORTE NOMEADO é o único filtro que mora na URL, e a diferença com
  // os de cima é de natureza:
  //
  //   turma, sede e busca  peneiram. São de quem está olhando, mudam a cada
  //        segundo, e a semente da URL existe só para o link do alerta cair
  //        no lugar certo.
  //   o recorte            tem NOME ("zona de risco", "bottom 30"), é o que
  //        um coordenador manda para o outro, é o que a ficha do aluno herda
  //        para revisar em sequência — e é o que a seta de VOLTAR do
  //        navegador precisa devolver. Em `useState` ele se perde ao entrar
  //        numa ficha e voltar, que é a coisa que mais se faz nesta tela.
  const recorte = lerRecorte(params.get('recorte'));

  const [expandido, setExpandido] = useState<GrupoId | null>(null);
  // R6 · a tabela ABRE PELO PIOR. Aqui o ordenador é a média do ano, que é o
  // número mais completo que a lista tem — o recorte "top" é a única exceção,
  // porque nele o interesse é o extremo de cima.
  const [ordenacao, setOrdenacao] = useState<Ordenacao | null>({ chave: 'ano', dir: 'asc' });

  useEffect(() => {
    setOrdenacao({ chave: 'ano', dir: recorte === 'top' ? 'desc' : 'asc' });
  }, [recorte]);

  // ── A volta da revisão em sequência ─────────────────────────────────────
  // Quem entra numa ficha volta pelo `volta` que a lista gravou; a ficha, por
  // sua vez, marca quem foi lido por último. Ler isso na ENTRADA e só na
  // entrada é o que faz a volta cair na linha de onde se saiu — depois disso
  // quem manda é a rolagem da pessoa, e reposicionar de novo seria arrancar a
  // tela de baixo dela. O contrato das duas telas é `dominio/revisaoEmSequencia.ts`.
  const [alunoVisto] = useState<string | null>(() => lerRecorteDeRevisao()?.ultimoVisto ?? null);
  const refCorpo = useRef<HTMLTableSectionElement>(null);
  const jaRolou = useRef(false);

  const turmaPorId = useMemo(() => new Map(turmas.map((t) => [t.id, t])), [turmas]);
  const sedePorId = useMemo(() => new Map(sedes.map((s) => [s.id, s])), [sedes]);

  // ── O peneiramento, e só ele: o recorte entra depois ────────────────────
  const base = useMemo(() => {
    const q = normalizar(busca.trim());
    return alunos.filter((a) => {
      if (turmasSel.size && !turmasSel.has(a.turmaId)) return false;
      if (sedesSel.size && !sedesSel.has(a.sedeId)) return false;
      if (q && !normalizar(a.nome).includes(q)) return false;
      return true;
    });
  }, [alunos, turmasSel, sedesSel, busca]);

  // Os extremos são calculados sobre a base PENEIRADA, não sobre o colégio
  // inteiro: com uma turma escolhida, "os 30 mais baixos" são os daquela
  // turma, e o N encolhe junto com o acervo. É o que faz o rótulo do card
  // continuar verdadeiro depois de qualquer filtro.
  const extremos = useMemo(() => extremosPorMedia(base), [base]);
  const contagens = useMemo(() => contarRecortes(base, extremos), [base, extremos]);
  const nCaindo = useMemo(() => contarRiscoCaindo(base), [base]);

  const filtrados = useMemo(
    () => aplicarRecorte(base, recorte, extremos),
    [base, recorte, extremos],
  );

  // Cross-filtering: cada dimensão conta ignorando o próprio filtro, senão as
  // contagens virariam sempre o total selecionado.
  //
  // O recorte nomeado fica de fora desta conta de propósito — ele redefine o
  // próprio N (o "bottom 30" de uma turma não é o mesmo de duas), e uma
  // contagem que muda de significado a cada pílula não é comparável.
  const contagensDeFiltro = useMemo(() => {
    const porTurma = new Map<string, number>();
    const porSede = new Map<string, number>();
    for (const a of alunos) {
      if (sedesSel.size === 0 || sedesSel.has(a.sedeId)) {
        porTurma.set(a.turmaId, (porTurma.get(a.turmaId) ?? 0) + 1);
      }
      if (turmasSel.size === 0 || turmasSel.has(a.turmaId)) {
        porSede.set(a.sedeId, (porSede.get(a.sedeId) ?? 0) + 1);
      }
    }
    return { porTurma, porSede };
  }, [alunos, turmasSel, sedesSel]);

  // ── As colunas de nota, que crescem quando um grupo abre ────────────────
  const colunasDeMedia = useMemo<ColunaDeMedia[]>(() => {
    const saida: ColunaDeMedia[] = [];
    for (const grupo of GRUPOS) {
      const aberto = expandido === grupo.id;
      const referencia = rotulos[grupo.id];
      const contexto = `${grupo.rotulo}${referencia ? ` · ${referencia}` : ''}`;
      saida.push({
        chave: grupo.id,
        grupo: grupo.id,
        ehGrupo: true,
        rotulo: grupo.rotulo,
        rotuloLongo: grupo.rotulo,
        referencia,
        titulo: contexto,
        corte: corteGeral,
        aberto,
      });
      if (!aberto) continue;
      MATERIAS_DO_DETALHAMENTO.forEach((materia, i) => {
        saida.push({
          chave: `${grupo.id}:${materia}`,
          grupo: grupo.id,
          ehGrupo: false,
          rotulo: ABREV_MATERIA[materia],
          rotuloLongo: `${NOME_MATERIA[materia]} · ${grupo.rotulo}`,
          referencia,
          titulo: `${NOME_MATERIA[materia]} · ${contexto}`,
          materia,
          corte: corteDaMateria(regua, materia),
          aberto,
          fim: i === MATERIAS_DO_DETALHAMENTO.length - 1,
        });
      });
    }
    return saida;
  }, [expandido, rotulos, regua, corteGeral]);

  // Tudo que ordena, num lugar só — é daqui que sai a ordem E o nome dela.
  const colunas = useMemo<ColunaDaLista[]>(
    () => [
      { chave: 'nome', label: 'Aluno', valor: (a) => a.nome, sentidos: ['A–Z', 'Z–A'] },
      ...colunasDeMedia.map((c): ColunaDaLista => ({
        chave: c.chave,
        label: c.rotuloLongo,
        valor: (a) => notaDaCelula(a, c),
        tipo: 'numero',
        sentidos: ['pior primeiro', 'melhor primeiro'],
      })),
      { chave: 'trajetoria', label: 'Trajetória', ordenavel: false },
      {
        chave: 'zona', label: 'Zona', valor: (a) => a.zona, tipo: 'ordinal', ordem: ORDEM_ZONA,
        sentidos: ['risco primeiro', 'top primeiro'],
      },
      {
        chave: 'tendencia', label: 'Tendência', valor: (a) => a.tendencia, tipo: 'ordinal',
        ordem: ORDEM_TENDENCIA, sentidos: ['caindo primeiro', 'subindo primeiro'],
      },
      {
        chave: 'perfil', label: 'Perfil', valor: (a) => a.perfil, tipo: 'ordinal',
        ordem: ORDEM_PERFIL, sentidos: ['regular primeiro', 'âncora primeiro'],
      },
      {
        chave: 'direitos', label: 'Direitos', valor: pesoDosDireitos, tipo: 'numero',
        sentidos: ['nenhum primeiro', 'os dois primeiro'],
      },
    ],
    [colunasDeMedia],
  );

  const linhas = useMemo(
    () => ordenarLinhas(filtrados, colunas, ordenacao),
    [filtrados, colunas, ordenacao],
  );

  useEffect(() => {
    if (jaRolou.current || !alunoVisto || !linhas.length) return;
    const corpo = refCorpo.current;
    if (!corpo) return;
    const alvo = Array.from(corpo.children).find(
      (no) => (no as HTMLElement).dataset.aluno === alunoVisto,
    ) as HTMLElement | undefined;
    if (!alvo) return;
    // Sem animação: isto é restauração de posição, não transição — quem volta
    // já sabe para onde está indo.
    jaRolou.current = true;
    alvo.scrollIntoView({ block: 'center' });
  }, [alunoVisto, linhas]);

  const nomeDoRecorte = recorte
    ? {
        risco: `zona de risco na régua ${regua?.nome ?? 'da casa'}`,
        'sem-nota': rotulos.ultimoCiclo ? `sem nota em ${rotulos.ultimoCiclo}` : 'sem nota no ciclo',
        bottom: `os ${extremos.n} de média mais baixa`,
        top: `os ${extremos.n} de média mais alta`,
      }[recorte]
    : null;

  const resumoPeneira = [
    resumirTexto(busca),
    resumirSelecao(turmasSel, turmas.map((t) => ({ valor: t.id, label: t.nome })), 'turma', 'turmas'),
    resumirSelecao(sedesSel, sedes.map((s) => ({ valor: s.id, label: s.nome })), 'sede', 'sedes'),
  ].filter(Boolean).join(' · ');

  const algumAtivo = turmasSel.size + sedesSel.size > 0 || busca.trim() !== '' || recorte != null;

  // A CONTAGEM VIVA: todo rótulo com número lê o acervo em vigor.
  const contagemViva = isPending
    ? 'Carregando…'
    : algumAtivo
      ? `${linhas.length} de ${alunos.length} · ${[nomeDoRecorte, resumoPeneira].filter(Boolean).join(' · ')} · a contagem acompanha o filtro`
      : `${alunos.length} alunos · ${turmas.length} turmas · ${sedes.length} sedes · a lista rola inteira: sem paginação e sem “carregar mais”`;

  const colunaOrdenada = colunas.find((c) => c.chave === ordenacao?.chave);
  const rotuloDaOrdem = colunaOrdenada && ordenacao
    ? `${colunaOrdenada.label.toLowerCase()}, ${(colunaOrdenada.sentidos ?? ['crescente', 'decrescente'])[ordenacao.dir === 'asc' ? 0 : 1]}`
    : 'ordem de chegada';

  function alternar<V>(conjunto: ReadonlySet<V>, valor: V): ReadonlySet<V> {
    const novo = new Set(conjunto);
    if (novo.has(valor)) novo.delete(valor);
    else novo.add(valor);
    return novo;
  }

  /** O `?recorte=` trocado, com o resto da URL preservado. */
  function urlDoRecorte(alvo: Recorte | null): string {
    const novo = new URLSearchParams(params);
    if (alvo) novo.set('recorte', alvo);
    else novo.delete('recorte');
    const texto = novo.toString();
    return texto ? `/alunos?${texto}` : '/alunos';
  }

  function irParaRecorte(alvo: Recorte | null) {
    const novo = new URLSearchParams(params);
    if (alvo) novo.set('recorte', alvo);
    else novo.delete('recorte');
    setParams(novo);
  }

  /**
   * Depois do primeiro clique nas pílulas, a SEMENTE da URL deixou de
   * descrever a tela — e uma semente que sobrevive é uma armadilha: o F5
   * ressuscitaria o filtro que a pessoa acabou de tirar. Some sem entrar no
   * histórico, porque mexer numa pílula não é navegar.
   */
  function abandonarASemente() {
    if (!params.has('turmaId') && !params.has('sedeId')) return;
    const novo = new URLSearchParams(params);
    novo.delete('turmaId');
    novo.delete('sedeId');
    setParams(novo, { replace: true });
  }

  function ordenarPor(chave: string) {
    setOrdenacao((o) => proximaOrdenacao(o, chave));
  }

  /**
   * Grava o recorte que a ficha vai herdar — a revisão em sequência.
   *
   * Vai a ORDEM, não o filtro: quem lê a ficha percorre os alunos na sequência
   * em que a lista os mostrava, e reproduzir a ordenação do outro lado seria a
   * mesma regra em dois lugares. `volta` é a URL desta lista com o recorte em
   * vigor, e é por isso que o recorte mora na query.
   */
  function guardarSequencia() {
    guardarRecorteDeRevisao({
      ids: linhas.map((a) => a.id),
      rotulo: `${nomeDoRecorte ?? 'todos os alunos'} · ${rotuloDaOrdem}`,
      volta: urlDoRecorte(recorte),
    });
  }

  /**
   * Abre ou fecha um grupo — e resgata a ordenação quando ela ia sumir junto.
   *
   * Fechar o grupo pelo qual a tabela está ordenada tiraria a coluna do ar, e
   * `ordenarLinhas` cai na ordem de chegada quando não acha a chave: 900
   * linhas se reembaralhariam **em silêncio**. A ordem cai para o total do
   * grupo, que é o parente mais próximo do que a pessoa tinha escolhido.
   */
  function alternarGrupo(id: GrupoId) {
    const proximo = expandido === id ? null : id;
    setExpandido(proximo);
    setOrdenacao((o) => {
      if (!o?.chave.includes(':')) return o;
      const grupoDaChave = o.chave.split(':')[0];
      return grupoDaChave === proximo ? o : { ...o, chave: grupoDaChave };
    });
  }

  function setaDe(chave: string): string {
    if (ordenacao?.chave !== chave) return '⇅';
    return ordenacao.dir === 'asc' ? '▲' : '▼';
  }

  function ordemAria(chave: string): 'ascending' | 'descending' | 'none' {
    if (ordenacao?.chave !== chave) return 'none';
    return ordenacao.dir === 'asc' ? 'ascending' : 'descending';
  }

  function classeDaColuna(coluna: ColunaDeMedia, prefixo: string): string {
    return [
      prefixo,
      coluna.ehGrupo ? 'alunos-col--grupo' : 'alunos-col--sub',
      coluna.aberto ? 'alunos-col--dentro' : '',
      coluna.aberto && coluna.ehGrupo ? 'alunos-col--inicio' : '',
      coluna.fim ? 'alunos-col--fim' : '',
    ].filter(Boolean).join(' ');
  }

  // Os dois extremos só existem quando há gente medida para extremar — um
  // atalho para uma lista vazia é convite para uma tela vazia (C5). Enquanto
  // carrega eles aparecem sem o N, para a faixa não pular de dois para quatro
  // cards quando o dado chega.
  const mostrarExtremos = isPending || extremos.n > 0;
  const rotuloExtremo = (lado: string) =>
    extremos.n > 0 ? `Os ${extremos.n} de média mais ${lado}` : `Os de média mais ${lado}`;

  // As pílulas dizem o mesmo que os cards, com o N do acervo em vigor. Os
  // extremos só aparecem quando existem — uma pílula "Top 0" seria um recorte
  // que não recorta.
  const opcoesDeRecorte: Array<{ valor: Recorte; label: string }> = [
    { valor: 'risco', label: 'Zona de risco' },
    {
      valor: 'sem-nota',
      label: rotulos.ultimoCiclo ? `Sem nota em ${rotulos.ultimoCiclo}` : 'Sem nota no ciclo',
    },
    ...(extremos.n > 0
      ? ([
          { valor: 'bottom', label: `Bottom ${extremos.n}` },
          { valor: 'top', label: `Top ${extremos.n}` },
        ] as Array<{ valor: Recorte; label: string }>)
      : []),
  ];

  return (
    <div className="tela alunos-tela">
      <div className="alunos-cabecalho">
        <div className="alunos-cabecalho__texto">
          <h1 className="tela-titulo">Alunos</h1>
          <p className="tela-subtitulo">{contagemViva}</p>
        </div>
        <TarjaDaRegua regua={regua} corte={corteGeral} />
      </div>

      {/* A faixa de entrada. C1 · perguntas, não objetos — e os extremos vêm
          com o de BAIXO primeiro: os melhores são justamente os que menos
          precisam do coordenador. */}
      <div className="campo-faixa-entrada">
        <CartaoDeEntrada
          olho="Movimento"
          titulo="Quem está em risco?"
          numeros={isPending
            ? null
            : `${contagemEmPalavras(contagens.risco)} · ${contagens.risco ? `${nCaindo} com a nota caindo` : `nenhum corte da régua ${regua?.nome ?? 'da casa'}`}`}
          para={urlDoRecorte('risco')}
        />
        <CartaoDeEntrada
          olho="Silêncio"
          titulo="Quem ficou sem nota?"
          numeros={isPending
            ? null
            : `${contagemEmPalavras(contagens['sem-nota'])} · ${
                rotulos.ultimoCiclo
                  ? `${contagens['sem-nota'] ? 'sem nota em' : 'todos com nota em'} ${rotulos.ultimoCiclo}`
                  : 'nenhum ciclo fechado ainda'
              }`}
          para={urlDoRecorte('sem-nota')}
        />
        {mostrarExtremos && (
          <>
            <CartaoDeEntrada
              olho="Extremo de baixo"
              titulo={rotuloExtremo('baixa')}
              numeros={extremos.n > 0
                ? `média de ${fmtNota(mediaDasMedias(aplicarRecorte(base, 'bottom', extremos)))} · o pior primeiro`
                : null}
              para={urlDoRecorte('bottom')}
            />
            <CartaoDeEntrada
              olho="Extremo de cima"
              titulo={rotuloExtremo('alta')}
              numeros={extremos.n > 0
                ? `média de ${fmtNota(mediaDasMedias(aplicarRecorte(base, 'top', extremos)))} · o melhor primeiro`
                : null}
              para={urlDoRecorte('top')}
            />
          </>
        )}
      </div>

      {/* A faixa fica ABAIXO dos cards, e não acima do título como nas outras
          superfícies: aqui ela reflete o recorte que os cards aplicam, e uma
          pílula longe do card que a acende não se lê como a mesma coisa. */}
      <BarraFiltros
        tela="alunos"
        algumAtivo={algumAtivo}
        onLimpar={() => {
          setTurmasSel(new Set());
          setSedesSel(new Set());
          setBusca('');
          // A URL vai junto: limpar a tela e deixar `?recorte=` ou a semente
          // do alerta na barra de endereço é prometer duas coisas diferentes
          // no mesmo lugar.
          setParams(new URLSearchParams());
        }}
        grupos={[
          {
            chave: 'recorte',
            rotulo: 'Recorte',
            resumo: nomeDoRecorte,
            corpo: (
              <PillsUnica
                opcoes={opcoesDeRecorte}
                selecionado={recorte}
                onSelecionar={(valor) => irParaRecorte(valor === recorte ? null : valor)}
              />
            ),
          },
          {
            chave: 'busca',
            rotulo: 'Aluno',
            resumo: resumirTexto(busca),
            corpo: (
              <Busca
                valor={busca}
                onChange={setBusca}
                // O rótulo lê a contagem em vigor: peneirar "902" quando a
                // tela mostra 3 é a contradição que este ramo pune.
                placeholder={`Peneirar ${filtrados.length === 1 ? 'este 1 aluno' : `estes ${filtrados.length} alunos`}…`}
                rotulo="Buscar aluno na lista"
              />
            ),
          },
          {
            chave: 'turma',
            rotulo: 'Turma',
            resumo: resumirSelecao(
              turmasSel, turmas.map((t) => ({ valor: t.id, label: t.nome })), 'turma', 'turmas',
            ),
            corpo: (
              <Pills
                opcoes={turmas.map((t) => ({
                  valor: t.id,
                  label: t.nome,
                  contagem: contagensDeFiltro.porTurma.get(t.id) ?? 0,
                }))}
                selecionados={turmasSel}
                onToggle={(id) => {
                  abandonarASemente();
                  setTurmasSel((s) => alternar(s, id));
                }}
              />
            ),
          },
          {
            chave: 'sede',
            rotulo: 'Sede',
            resumo: resumirSelecao(
              sedesSel, sedes.map((sd) => ({ valor: sd.id, label: sd.nome })), 'sede', 'sedes',
            ),
            corpo: (
              <Pills
                opcoes={sedes.map((sd) => ({
                  valor: sd.id,
                  label: sd.nome,
                  contagem: contagensDeFiltro.porSede.get(sd.id) ?? 0,
                }))}
                selecionados={sedesSel}
                onToggle={(id) => {
                  abandonarASemente();
                  setSedesSel((s) => alternar(s, id));
                }}
              />
            ),
          },
        ]}
      />

      <section className="alunos-caixa">
        {isError ? (
          <div className="empty-state">
            Não foi possível carregar os alunos.
            <div className="empty-state__hint">{(error as Error)?.message}</div>
          </div>
        ) : isPending ? (
          <div className="empty-state">Carregando…</div>
        ) : linhas.length === 0 ? (
          <div className="empty-state">
            Nenhum aluno atende a esses critérios.
            <div className="empty-state__hint">
              {recorte
                ? `O recorte “${nomeDoRecorte}” não tem ninguém${resumoPeneira ? ` em ${resumoPeneira}` : ''}.`
                : 'Tente remover algum filtro.'}
            </div>
          </div>
        ) : (
          <table className="alunos-tabela">
            <thead>
              <tr>
                {/* O cabeçalho da coluna do nome carrega a CONTAGEM EM VIGOR e
                    o ORDENADOR EM VIGOR (R6). Os dois moram aqui porque o
                    cabeçalho é o único pedaço que não rola: numa lista sem
                    paginação, uma legenda que sobe embora deixa 900 linhas
                    sem quem as explique. */}
                <th className="alunos-tabela__th-aluno" aria-sort={ordemAria('nome')}>
                  <button
                    className="alunos-tabela__ordenar"
                    onClick={() => ordenarPor('nome')}
                    title="Ordenar por nome"
                  >
                    <span className="alunos-tabela__contagem">
                      {contagemEmPalavras(linhas.length)}
                    </span>
                    <span className="alunos-tabela__seta">{setaDe('nome')}</span>
                  </button>
                  <span className="alunos-tabela__ordem" title={`Em ordem de ${rotuloDaOrdem}`}>
                    {rotuloDaOrdem}
                  </span>
                </th>

                {colunasDeMedia.map((c) => {
                  const divergente = c.corte != null && regua != null && c.corte !== corteGeral;
                  return (
                    <th
                      key={c.chave}
                      className={classeDaColuna(c, 'alunos-tabela__th-nota')}
                      aria-sort={ordemAria(c.chave)}
                    >
                      {c.ehGrupo ? (
                        <div className="alunos-grupo">
                          <button
                            className="alunos-grupo__abrir"
                            aria-expanded={c.aberto}
                            onClick={() => alternarGrupo(c.grupo)}
                            title={c.aberto
                              ? 'Fechar as matérias deste grupo'
                              : 'Abrir Matemática, Física e Química'}
                          >
                            <svg width="10" height="10" viewBox="0 0 24 24" fill="none"
                              stroke="currentColor" strokeWidth="3" strokeLinecap="round"
                              aria-hidden="true">
                              <path d="M5 12h14" />
                              {!c.aberto && <path d="M12 5v14" />}
                            </svg>
                            <span className="alunos-grupo__rotulo">{c.rotulo}</span>
                          </button>
                          <button
                            className="alunos-tabela__ordenar alunos-tabela__ordenar--so-seta"
                            onClick={() => ordenarPor(c.chave)}
                            aria-label={`Ordenar por ${c.rotulo}`}
                          >
                            <span className="alunos-tabela__seta">{setaDe(c.chave)}</span>
                          </button>
                          {/* O rótulo do servidor, que diz a QUE ciclo este
                              número responde. Sem ele a coluna poderia dizer
                              "1º ciclo" enquanto soma outro. */}
                          {c.referencia && (
                            <span className="alunos-grupo__ref">{c.referencia}</span>
                          )}
                        </div>
                      ) : (
                        <button
                          className="alunos-tabela__ordenar alunos-tabela__ordenar--sub"
                          onClick={() => ordenarPor(c.chave)}
                          title={`Ordenar por ${NOME_MATERIA[c.materia!]}`}
                        >
                          {c.rotulo}
                          {/* R2 · o corte que DIVERGE aparece colado no nome:
                              o Inglês da F1 do ITA exige 5,0, e uma tabela que
                              desenha tudo contra 4,0 mente na matéria que mais
                              elimina. O corte comum não se repete coluna a
                              coluna — já está dito na tarja. */}
                          {divergente && (
                            <span
                              className="alunos-tabela__corte"
                              title={rotuloDoCorte(c.corte!, eliminaSozinho(regua, c.materia))}
                            >
                              {fmtNota(c.corte)}
                            </span>
                          )}
                          <span className="alunos-tabela__seta">{setaDe(c.chave)}</span>
                        </button>
                      )}
                    </th>
                  );
                })}

                <th className="alunos-tabela__th-traj">
                  Trajetória
                  <span className="alunos-tabela__nota-de-rodape">
                    0 a 10, com o corte
                  </span>
                </th>
                {(['zona', 'tendencia', 'perfil', 'direitos'] as const).map((chave) => {
                  const coluna = colunas.find((c) => c.chave === chave)!;
                  return (
                    <th key={chave} className="alunos-tabela__th-palavra" aria-sort={ordemAria(chave)}>
                      <button className="alunos-tabela__ordenar" onClick={() => ordenarPor(chave)}
                        title={`Ordenar por ${coluna.label}`}>
                        {coluna.label}
                        <span className="alunos-tabela__seta">{setaDe(chave)}</span>
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody ref={refCorpo}>
              {linhas.map((a) => (
                <tr
                  key={a.id}
                  data-aluno={a.id}
                  className={a.id === alunoVisto ? 'alunos-linha--visto' : undefined}
                >
                  <td className="alunos-tabela__td-aluno">
                    <Link
                      className="alunos-linha__link"
                      to={`/alunos/${a.id}`}
                      onClick={guardarSequencia}
                    >
                      <Avatar tipo="aluno" id={a.id} nome={a.nome} temFoto={a.temFoto}
                        className="avatar" tamanho={30} />
                      <span className="alunos-linha__nomes">
                        <span className="alunos-linha__nome">{a.nome}</span>
                        <span className="alunos-linha__origem">
                          {[turmaPorId.get(a.turmaId)?.nome, sedePorId.get(a.sedeId)?.nome]
                            .filter(Boolean).join(' · ') || '—'}
                        </span>
                      </span>
                    </Link>
                  </td>

                  {colunasDeMedia.map((c) => (
                    <td key={c.chave} className={classeDaColuna(c, 'alunos-tabela__td-nota')}>
                      <CelulaDeNota nota={notaDaCelula(a, c)} corte={c.corte} titulo={c.titulo} />
                    </td>
                  ))}

                  <td className="alunos-tabela__td-traj">
                    {a.sparkline.length >= 2 ? (
                      // A ESCALA É COMPARTILHADA e o corte vai desenhado. Sem
                      // isso, quem oscilou entre 2,0 e 2,4 desenhava a mesma
                      // curva de quem subiu de 6,0 para 8,0 — 900 linhas de
                      // uma forma que parece comparável e não é.
                      <Sparkline
                        valores={a.sparkline}
                        largura={132}
                        altura={34}
                        cor="var(--sas-dado)"
                        corte={corteGeral ?? undefined}
                        descricao={`${a.nome}: de ${fmtNota(a.sparkline[0])} a ${fmtNota(a.sparkline[a.sparkline.length - 1])} em ${a.sparkline.length} provas${corteGeral != null ? `, ${rotuloDoCorte(corteGeral, false)}` : ''}`}
                      />
                    ) : (
                      <span className="alunos-quieto">
                        {a.sparkline.length === 1 ? 'uma prova só' : 'sem provas'}
                      </span>
                    )}
                  </td>

                  <td className="alunos-tabela__td-palavra">{PALAVRA_DA_ZONA[a.zona]}</td>
                  <td className="alunos-tabela__td-palavra">{PALAVRA_DA_TENDENCIA[a.tendencia]}</td>
                  <td className="alunos-tabela__td-palavra">{PALAVRA_DO_PERFIL[a.perfil]}</td>
                  <td className="alunos-tabela__td-palavra">
                    <CelulaDeDireitos direitos={a.direitos} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
