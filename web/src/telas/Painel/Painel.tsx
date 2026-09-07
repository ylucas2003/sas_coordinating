import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { AberturaDoTour } from '../../componentes/onboarding/AberturaDoTour';
import { CartaoDeCampo } from '../../componentes/ui/Campo';
import { useRecorteDaTela } from '../../componentes/layout/migalhas';
import { dataLocal, isoDoDia, quebraDaContagem, rotuloDaContagem } from '../../dominio/cantina';
import { corteDaMateria } from '../../dominio/criterios';
import { cicloPadrao, ciclosNoRecorte, recorteCompleto } from '../../dominio/painelFiltros';
import { useCalendarioNaCoordenacao } from '../../hooks/cantina';
import { useCiclos, useClassificacaoCiclo, useSimulados } from '../../hooks/consultas';
import { fmtNota } from '../../util/formato';
import { FaixaDecisao } from './FaixaDecisao';
import type { DiaDoCalendario } from '../../tipos/cantina';
import type { Ciclo, Simulado } from '../../tipos/dominio';

// O PAINEL — três portas e uma coisa que só ele faz.
//
// `/` cai aqui, rota desconhecida cai aqui, e é a primeira tela que dois ou
// três coordenadores veem toda manhã. O trabalho da fase 2 do docs/39 foi
// quase todo SUBTRAÇÃO: a tela empilhava seis estratos e cinco saíram.
//
//   a TABELA        mudou de casa para `telas/CicloFicha/TabelaDoCiclo.tsx`.
//                   Ela sempre foi de UM ciclo, e a primeira coisa que se
//                   fazia aqui era escolher esse ciclo numa faixa de filtros —
//                   a tela pedia um contexto que a URL sabe dar.
//   a FAIXA DE      ano · vestibular · ciclo · sede · turma · busca. O filtro
//   FILTROS         de ciclo existia para escolher o alvo da tabela; sem
//                   tabela não há alvo. Sede e turma iriam só recortar os
//                   alertas, e home com barra de filtro deixa de ser home e
//                   vira dashboard.
//   os 4 KPIs       todos os quatro eram sobre o ciclo, e o card do ciclo já
//                   os carrega. Sobrou UMA magnitude, dentro dele.
//   o TÍTULO        "Panorama geral" repetia a migalha da topbar, que desde a
//                   fase 1 é o título da tela (`Topbar.tsx`).
//   "QUEM MUDOU     apontava para `/painel#alertas`, que é esta tela. Era
//   DE ZONA?"       circular, e a faixa de alertas logo abaixo responde — é o
//                   alerta `ZONA_TRANSICAO`.
//
// ⚠️ A ASSIMETRIA É O DESENHO. Os três cards são ATALHOS para telas que
// existem noutro lugar; a faixa de alertas é a única coisa do produto que só
// existe aqui. Não tente equilibrar os dois lados: cards em cima porque coisa
// previsível se aprende onde fica, alertas embaixo e abertos porque coisa
// episódica precisa estar onde o olho cai.
//
// O que a subtração comprou de graça: a home deixou de baixar 900 alunos, as
// turmas, as sedes e as notas do ciclo inteiro. Sobraram quatro consultas, e
// nenhuma delas tem linha por aluno.

/**
 * A régua desta tela, fixa.
 *
 * O seletor de régua era da faixa de filtros e foi com ela — quem quer ver a
 * mesma turma sob o edital do ITA vai à ficha do ciclo, onde a régua é do
 * cabeçalho. Aqui fica a pedagógica do colégio, e a faixa de alertas a NOMEIA
 * (R2): régua não declarada é a pior fonte de engano do produto.
 */
const REGUA_DO_PAINEL = 'tio-leo';

/**
 * A partir de quantos dias sem prova nova o atalho passa a confessar a idade.
 *
 * Um ciclo aplica prova toda semana; três semanas sem nenhuma ainda é recesso
 * ou emenda de feriado. Um mês não é — é janeiro, ou a semana depois de um
 * ciclo fechar, e aí o card mostra o número de julho como se fosse o de hoje.
 * A prancheta desenha o normal com 22 dias de idade e sem ressalva nenhuma,
 * então o limite tem de ser maior que isso.
 */
const DIAS_ATE_ENVELHECER = 28;

/** O `<path>` do glifo do card de simulado — barras, 44px em traço fino. */
const GLIFO_SIMULADO = <path d="M14 52V30M26 52V18M38 52V36M50 52V24M10 58h50" />;

/** O glifo do card da cantina — talher e prato. */
const GLIFO_CANTINA = <path d="M18 14h34M22 14v10a13 13 0 0 0 26 0V14M35 37v19M12 60h46" />;

/**
 * Dias inteiros desde a época, a partir de um ISO `YYYY-MM-DD`.
 *
 * Passa por `Date.UTC` com os três números já separados, e não por
 * `new Date(iso)`: a segunda forma lê a string como meia-noite UTC e devolve o
 * dia anterior em todo fuso negativo — o Brasil inteiro. É a mesma armadilha
 * que `dominio/cantina.ts::dataLocal` documenta, e ela apareceria aqui como
 * "a prova de hoje foi aplicada ontem".
 */
function emDias(iso: string): number {
  const [ano, mes, dia] = iso.slice(0, 10).split('-').map(Number);
  return Math.floor(Date.UTC(ano, mes - 1, dia) / 86_400_000);
}

/** `2026-08-14` → `14/08`. Fatia a string, sem passar por `Date` nenhum. */
function dataCurta(iso: string): string {
  return `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
}

/**
 * "há 7 semanas" — a idade dita na escala em que ela importa.
 *
 * Dia enquanto o número de dias ainda diz algo; semana quando ele deixa de
 * dizer (ninguém lê "há 49 dias"); mês quando nem a semana diz.
 */
function haQuanto(iso: string, hoje: string): string {
  const dias = emDias(hoje) - emDias(iso);
  if (dias <= 0) return 'hoje';
  if (dias === 1) return 'ontem';
  if (dias < 14) return `há ${dias} dias`;
  if (dias < 60) return `há ${Math.round(dias / 7)} semanas`;
  return `há ${Math.round(dias / 30)} meses`;
}

/**
 * "Ciclo 4 · ITA · 2026".
 *
 * ⚠️ Monta-se das colunas estruturadas, e não de `ciclo.nome`, porque o
 * subtítulo tem uma obrigação: NOMEAR O VESTIBULAR. ITA e IME correm em
 * paralelo, o card mostra um só, e sem essa palavra metade do colégio olha o
 * número achando que é o dela. O `nome` hoje nasce exatamente assim
 * (`api/app/routes/ciclos.py`), mas ciclo antigo veio do Canvas com o nome que
 * estivesse na planilha — e aí a garantia se perde em silêncio.
 */
function identidadeDoCiclo(ciclo: Ciclo): string {
  const partes = [ciclo.ordem ? `Ciclo ${ciclo.ordem}` : ciclo.nome];
  if (ciclo.vestibularAlvo) partes.push(ciclo.vestibularAlvo);
  if (ciclo.anoLetivo) partes.push(String(ciclo.anoLetivo));
  return partes.join(' · ');
}

/** "Física · P8", ou o nome do Canvas quando a prova não tem matéria nem rótulo. */
function nomeDaProva(prova: Simulado): string {
  const partes = [prova.materia?.nome, prova.rotuloCurto].filter(Boolean);
  return partes.length ? partes.join(' · ') : prova.nome;
}

/**
 * Quantos pediram — e `null` quando a pergunta não se aplica.
 *
 * Rascunho e "sem cardápio" não têm contagem: o aluno nem viu o cardápio, e
 * zero ali seria "ninguém quis", que é outra coisa.
 */
function pedidosDaRefeicao(dia: DiaDoCalendario | null): number | null {
  if (!dia) return null;
  return dia.estado === 'aberto' || dia.estado === 'fechado' ? dia.pedidos : null;
}

/** O que uma refeição tem a dizer no subtítulo do card. `null` = nada. */
function fraseDaRefeicao(dia: DiaDoCalendario | null, rotulo: string): string | null {
  // Sem cardápio o card CALA. "Cardápio não lançado" é a pergunta do card da
  // Administração ("o que foi lançado?"), e os dois cards de cantina só se
  // justificam enquanto os subtítulos disserem coisas diferentes.
  if (!dia || dia.estado === 'sem-cardapio') return null;
  if (dia.estado === 'sem-refeicao') return `sem ${rotulo} hoje`;
  if (dia.estado === 'rascunho') return `${rotulo} em rascunho`;
  // A palavra troca com o que o número conta; a quebra em dois números fica
  // para `/cantina/:data`, que é o destino deste card. Um subtítulo de hub com
  // quatro números seria a tela errada para a leitura fina (docs/40 §10.1).
  return `${rotulo} ${dia.pedidos} ${rotuloDaContagem(dia)}`;
}

export function Painel() {
  // O dia, recalculado a cada render de propósito: a aba fica aberta a manhã
  // inteira, e congelar `hoje` num `useMemo(…, [])` faria a virada da
  // meia-noite passar sem a tela perceber.
  const hoje = isoDoDia(new Date());

  const { data: ciclos = [], isPending: carregandoCiclos, isError: erroCiclos } = useCiclos();
  const { data: simulados = [], isPending: carregandoSimulados } = useSimulados();

  // A fileira de ciclos sumiu, mas a ORDENAÇÃO dela não podia sumir junto: o
  // último recurso de `cicloPadrao` é `ciclos[0]`, e a API ordena só por
  // `ordem` — três ciclos empatam em `ordem = 1` e qual deles vem primeiro não
  // está definido (docs/32 §3.1). `recorteCompleto` aqui não é filtro, é
  // "todos"; o que se aproveita é a ordem que `ciclosNoRecorte` impõe.
  const ciclosOrdenados = useMemo(
    () => ciclosNoRecorte(ciclos, recorteCompleto(ciclos)),
    [ciclos],
  );
  const cicloAtivo = useMemo(
    () => cicloPadrao(ciclosOrdenados, simulados, hoje),
    [ciclosOrdenados, simulados, hoje],
  );

  // Sem `fase`: o Painel conta o ciclo INTEIRO sob a régua do colégio, e a
  // rota já cai na fase da própria régua quando o parâmetro não vai
  // (`api/app/routes/ciclos.py::classificacao_do_ciclo`). A fase era um
  // recorte da tabela, e a tabela mudou de casa.
  const classificacao = useClassificacaoCiclo(cicloAtivo?.id ?? null, REGUA_DO_PAINEL);
  const criterio = classificacao.data?.criterio ?? null;

  // O dia de hoje na cantina — as DUAS refeições numa janela de um dia só.
  const cantina = useCalendarioNaCoordenacao(hoje, hoje);

  // O que o assistente precisa para "e a Física?" ter referente. Sobrou o
  // essencial: sem filtros, o recorte desta tela é o ciclo e a régua.
  useRecorteDaTela(useMemo(
    () => ({ cicloId: cicloAtivo?.id, criterio: REGUA_DO_PAINEL }),
    [cicloAtivo?.id],
  ));

  // ─── CICLO · "Como está fechando?" ────────────────────────────────────
  const cartaoCiclo = useMemo(() => {
    if (!cicloAtivo) return null;
    const doCiclo = simulados.filter((s) => s.cicloId === cicloAtivo.id);
    const previstas = cicloAtivo.simuladoIds.length || doCiclo.length;
    const aplicadas = doCiclo.filter((s) => s.dataAplicacao && s.dataAplicacao <= hoje).length;

    // O ciclo fechou e nenhum outro começou: o número grande é história. Sem
    // esta linha, 128 cortados de julho se leem como o de hoje.
    const encerrado = !!cicloAtivo.periodoFim && cicloAtivo.periodoFim < hoje;
    const algumEmAndamento = ciclos.some(
      (c) => !!c.periodoInicio && !!c.periodoFim && c.periodoInicio <= hoje && hoje <= c.periodoFim,
    );

    return {
      subtitulo: `${identidadeDoCiclo(cicloAtivo)} · ${aplicadas} de ${previstas} provas`,
      aviso: encerrado && !algumEmAndamento
        ? `nenhum ciclo em andamento — este encerrou ${haQuanto(cicloAtivo.periodoFim, hoje)}`
        : null,
      para: `/ciclos/${cicloAtivo.id}`,
    };
  }, [cicloAtivo, ciclos, simulados, hoje]);

  // ─── SIMULADO · "A prova estava boa?" ─────────────────────────────────
  const cartaoSimulado = useMemo(() => {
    // A última APLICADA, por data de aplicação — não por nota lançada. A prova
    // que acabou de ser feita e ainda não voltou do Canvas é justamente a que
    // se quer olhar; ordenar por nome daria P9 depois de P10.
    const prova = simulados
      .filter((s) => s.dataAplicacao && s.dataAplicacao <= hoje)
      .sort((a, b) => b.dataAplicacao.localeCompare(a.dataAplicacao))[0];
    if (!prova) return null;

    const semNotas = prova.media == null;
    const envelheceu = emDias(hoje) - emDias(prova.dataAplicacao) >= DIAS_ATE_ENVELHECER;
    const quando = envelheceu
      ? `aplicada ${haQuanto(prova.dataAplicacao, hoje)}`
      : semNotas
        ? `aplicada em ${dataCurta(prova.dataAplicacao)}`
        : dataCurta(prova.dataAplicacao);

    return {
      // Aplicada e sem notas não é card quebrado: é uma PENDÊNCIA, e o card a
      // anuncia com a marca em vez de mostrar um espaço vazio onde o
      // coordenador procuraria a média.
      subtitulo: semNotas
        ? `${nomeDaProva(prova)} · ${quando} · notas ainda não lançadas`
        : `${nomeDaProva(prova)} · ${quando} · média ${fmtNota(prova.media)}`,
      marca: semNotas ? 'Pendente' : null,
      para: `/simulados/${prova.id}`,
    };
  }, [simulados, hoje]);

  // ─── CANTINA · "O que é hoje?" ────────────────────────────────────────
  const cartaoCantina = useMemo(() => {
    if (cantina.isError) {
      // A consulta falhou: nem inventa número nem some com a porta. Diz que
      // não sabe — "0 pedidos" para quem tem 62 é a mentira mais cara da tela.
      return { subtitulo: 'não deu para ler o cardápio de hoje', marca: 'Indisponível', inerte: true };
    }
    const doDia = (cantina.data ?? []).filter((d) => d.data === hoje);
    const almoco = doDia.find((d) => d.refeicao === 'almoco') ?? null;
    const janta = doDia.find((d) => d.refeicao === 'janta') ?? null;

    // Só há para onde ir se existe cardápio — rascunho inclusive, que a
    // coordenação enxerga e o aluno não.
    const abrivel = [almoco, janta].some(
      (d) => d && d.estado !== 'sem-refeicao' && d.estado !== 'sem-cardapio',
    );
    if (!abrivel) {
      const diaDaSemana = dataLocal(hoje).toLocaleDateString('pt-BR', { weekday: 'long' });
      // ⚠️ "sem refeição" só quando o SERVIDOR disse isso. Um dia que
      // simplesmente não veio no calendário pode ser sábado ou pode ser a
      // cantina que não lançou, e deduzir qual dos dois seria inventar regra
      // de negócio no front. O que a tela sabe é o dia da semana — e é ele
      // que deixa o coordenador concluir sozinho.
      const declarouSemRefeicao = [almoco, janta].some((d) => d?.estado === 'sem-refeicao');
      return {
        subtitulo: declarouSemRefeicao
          ? `sem refeição hoje · ${diaDaSemana}`
          : `nenhum cardápio para hoje · ${diaDaSemana}`,
        marca: 'Sem destino',
        inerte: true,
      };
    }

    const pedidosAlmoco = pedidosDaRefeicao(almoco);
    const pedidosJanta = pedidosDaRefeicao(janta);
    // A forma compacta só vale enquanto "pedidos" for verdade nos DOIS números.
    // Com retirada na hora no dia, o total inclui quem não pediu nada (docs/40
    // §10.1), e a frase por refeição — que nomeia cada um — volta a valer.
    const soPedido = !quebraDaContagem(almoco ?? { pedidos: 0 })
      && !quebraDaContagem(janta ?? { pedidos: 0 });
    const subtitulo = pedidosAlmoco != null && pedidosJanta != null && soPedido
      // A palavra "pedidos" uma vez só quando os dois números são pedidos: é
      // a linha da prancheta, e ela cabe onde duas frases inteiras não cabem.
      ? `almoço ${pedidosAlmoco} · janta ${pedidosJanta} pedidos`
      : [fraseDaRefeicao(almoco, 'almoço'), fraseDaRefeicao(janta, 'janta')]
        .filter((f): f is string => f != null)
        .join(' · ');

    return { subtitulo, marca: null, inerte: false };
  }, [cantina.isError, cantina.data, hoje]);

  // ─── O primeiro dia do ano letivo ─────────────────────────────────────
  // As três portas apontam para o que já aconteceu, e ainda não aconteceu
  // nada. Só vale quando as consultas VOLTARAM vazias: lista vazia por erro de
  // rede não é colégio novo, e mandar o coordenador criar um ciclo que já
  // existe seria pior que a tela em branco.
  const primeiroDia = !carregandoCiclos && !carregandoSimulados && !erroCiclos
    && ciclos.length === 0 && simulados.length === 0;

  if (primeiroDia) return <PrimeiroDia />;

  return (
    <div className="tela">
      {/* A grade é de 12 colunas, e ela tem de aceitar um quarto e um quinto
          card sem virar outra tela — o Painel vai crescer. Quem manda no
          tamanho é a MAGNITUDE, não o contrário: só um card por tela a tem, e
          é dela que a hierarquia vem (`styles/painel.css`). */}
      <section className="painel-grade" aria-label="Atalhos do dia">
        <CartaoDeCampo
          olho="Ciclo"
          titulo="Como está fechando?"
          para={cartaoCiclo?.para ?? '/provas'}
          carregando={carregandoCiclos || (!!cicloAtivo && classificacao.isPending)}
          // ⚠️ `null` e ausente não são a mesma coisa: `null` reserva o vão do
          // numeral e a grade não pula quando o número chega. Este card SEMPRE
          // declara magnitude, mesmo sem ciclo — é ela que lhe dá as 7 colunas.
          magnitude={classificacao.data ? String(classificacao.data.cortados) : null}
          magnitudeLegenda={
            classificacao.data ? `cortados de ${classificacao.data.total} alunos` : undefined
          }
          subtitulo={cartaoCiclo?.subtitulo ?? null}
          aviso={cartaoCiclo?.aviso ?? null}
          vazio="nenhum ciclo com prova aplicada"
        />

        <CartaoDeCampo
          compacto
          olho="Simulado"
          titulo="A prova estava boa?"
          para={cartaoSimulado?.para ?? '/provas?aba=simulados'}
          carregando={carregandoSimulados}
          subtitulo={cartaoSimulado?.subtitulo ?? null}
          marca={cartaoSimulado?.marca ?? null}
          vazio="nenhuma prova aplicada ainda"
          glifo={GLIFO_SIMULADO}
        />

        <CartaoDeCampo
          compacto
          olho="Cantina"
          titulo="O que é hoje?"
          // A rota `/cantina/:data` é da fase 5 e ainda não existe — hoje só
          // há `/cantina/:data/:refeicao`. O card aponta para o destino do
          // desenho de propósito (docs/39 §3, fase 5).
          para={`/cantina/${hoje}`}
          inerte={cartaoCantina.inerte}
          carregando={cantina.isPending}
          subtitulo={cartaoCantina.subtitulo}
          marca={cartaoCantina.marca}
          vazio="sem refeição hoje"
          glifo={GLIFO_CANTINA}
        />
      </section>

      <FaixaDecisao
        cortados={classificacao.data?.cortados ?? null}
        nomeCriterio={criterio?.nome ?? null}
        corte={corteDaMateria(criterio, null) ?? undefined}
      />

      {/* O TOUR (docs/39 fase 6). Ele abre SOZINHO aqui, e só aqui: esta é a
          home, é onde o coordenador novo chega, e é a única abertura que dá
          sentido ao "já vi" — quem clica no botão está pedindo de novo.

          Fica no fim da coluna de propósito. O tour não é tarefa do dia: quem
          já sabe ler um ciclo não deve tropeçar nele toda manhã acima dos
          alertas, que são a única coisa que só existe nesta tela. */}
      <AberturaDoTour abrirSozinho />
    </div>
  );
}

/**
 * O primeiro dia do ano letivo — colégio sem ciclo e sem prova.
 *
 * Não é um estado vazio de lista: é a tela inteira, porque as três portas
 * apontam para o passado e não há passado. O ano começa pelo ciclo — é ele que
 * agrupa as provas e aplica a régua —, então a tela diz isso e leva lá.
 */
function PrimeiroDia() {
  return (
    <div className="tela">
      <section className="painel-primeiro">
        <div className="painel-primeiro__texto">
          <p className="painel-primeiro__olho">Primeiro dia do ano letivo</p>
          <h2 className="painel-primeiro__titulo">Nenhum ciclo criado, nenhuma prova aplicada</h2>
          <p className="painel-primeiro__corpo">
            As três portas desta tela apontam para o que já aconteceu, e ainda não aconteceu
            nada. O ano começa pelo ciclo: é ele que agrupa as provas e aplica a régua.
          </p>
          <div className="painel-primeiro__acoes">
            <Link className="btn btn-primary" to="/provas">Criar o primeiro ciclo</Link>
            <Link className="btn" to="/alunos">Conferir os alunos importados</Link>
          </div>
        </div>
        {/* Três portas fechadas, no arranjo dos três cards que ainda não têm o
            que mostrar — 7 colunas à esquerda, duas de 5 empilhadas. */}
        <svg
          className="painel-primeiro__portas"
          width="280"
          height="200"
          viewBox="0 0 280 200"
          fill="none"
          role="img"
          aria-label="Três portas fechadas, ainda sem destino"
        >
          <rect x="14" y="26" width="120" height="150" rx="10" stroke="var(--sas-fio-forte)" strokeWidth="1.4" strokeDasharray="4 4" />
          <rect x="146" y="26" width="120" height="68" rx="10" stroke="var(--sas-fio-forte)" strokeWidth="1.4" strokeDasharray="4 4" />
          <rect x="146" y="108" width="120" height="68" rx="10" stroke="var(--sas-fio-forte)" strokeWidth="1.4" strokeDasharray="4 4" />
        </svg>
      </section>
    </div>
  );
}
