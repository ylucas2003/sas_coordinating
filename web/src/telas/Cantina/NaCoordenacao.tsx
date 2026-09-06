import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { CabecaDeCampo, CartaoDeCampo } from '../../componentes/ui/Campo';
import {
  instrucaoDoBloco, prazoLegivel, ROTULO_DA_REFEICAO, ROTULO_DO_ESTADO, rotuloDoDia,
} from '../../dominio/cantina';
import { useAlunos, useDiaDaCantina } from '../../hooks/consultas';
import { useCalendarioNaCoordenacao, useCantinas, useCardapioNaCoordenacao } from '../../hooks/cantina';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import { useEventosDaCantina } from '../../hooks/eventosCantina';
import { BotoesDeExportar } from './BotoesDeExportar';
import { SeletorDeCantina, useCantinaSelecionada } from './SeletorDeCantina';
import type { Aluno } from '../../tipos/dominio';
import type {
  CantinaAdmin, DiaDoCalendario, EstadoCardapio, PedidoDeAluno, Refeicao,
} from '../../tipos/cantina';
import {
  GLIFO_DA_REFEICAO, GradeDeCardapios, janelaDoMes, LegendaDosEstados, NavegadorDeMes, nomeDoMes,
} from './GradeDeCardapios';
import * as sessao from '../../servicos/sessao';

// A CANTINA VISTA PELA COORDENAÇÃO — leitura, e só.
//
// ⚠️ **Nenhum botão de publicar, criar ou editar cardápio.** Publicar é da
// cantina, e um coordenador publicando em nome dela apagaria a autoria de
// `cardapio.criado_por`, que fica registrada. O servidor recusa de qualquer
// jeito (`get_current_cantina` não aceita sessão de coordenação); a tela não
// oferecer é a metade que evita a pessoa descobrir o limite levando um 403 na
// cara.
//
// O que a coordenação escreve é outra coisa, e mora em `Administracao/
// Cantina.tsx`: **quem tem direito** e **quem lança**. Cardápio, nunca.
//
// São quatro telas, e a árvore é a do docs/39 fase 5:
//
//   /cantina                    o hub — três cards, ou dois
//   /cantina/cardapios          o calendário do mês
//   /cantina/:data              o DIA, com as duas refeições
//   /cantina/:data/:refeicao    uma refeição, com a lista inteira de quem pediu

// ─── /cantina · o hub ─────────────────────────────────────────────────────

/**
 * O hub muda de TAMANHO conforme quem entra.
 *
 * "Administrar cantinas" é escrita exclusiva do administrador. O coordenador
 * comum vê dois cards; o administrador vê três — e o card ausente **some**, não
 * fica cinza: um botão que existe só para dar erro ensina a pessoa a
 * desconfiar da tela. Por isso a grade tem duas composições declaradas, e não
 * uma grade de três com um buraco.
 *
 * ⚠️ Este hub já ficou ÓRFÃO uma vez nesta parte do produto (docs/38, corrigido
 * em f96e961). Quem o segura é o card da Administração, que aponta para cá — e
 * o chevron daqui volta para lá, fechando o caminho nos dois sentidos.
 */
export function HubDaCantina() {
  // O stream da coordenação, nas três telas de cantina e só nelas. No `AppShell`
  // valeria para o Painel e a ficha de aluno também, e um coordenador olhando
  // nota não precisa acordar a cada pedido de almoço.
  useEventosDaCantina('/administracao/cantina/eventos');
  const souAdministrador = sessao.ehAdministrador();
  const mes = useResumoDoMes();
  const direitos = useResumoDosDireitos();
  const acesso = useResumoDoAcesso();

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Cantina" para="/administracao" destino="Administração" />
      <p className="cant-intro">
        A cantina lança o cardápio; aqui se lê o que ela lançou e se decide quem come.
      </p>

      <div className={`cant-hub${souAdministrador ? ' cant-hub--tres' : ' cant-hub--dois'}`}>
        <CartaoDeCampo
          olho="Cardápios"
          titulo="O que foi lançado?"
          para="/cantina/cardapios"
          carregando={mes.carregando}
          subtitulo={mes.texto}
          vazio="A cantina ainda não lançou nada neste mês."
          glifo={
            <>
              <path d="M12 16h46v42H12zM12 28h46" />
              <path d="M22 10v8M48 10v8" />
              <path d="M22 38h10M22 48h22" />
            </>
          }
        />

        <CartaoDeCampo
          olho="Direitos"
          titulo="Quem come aqui?"
          para="/cantina/direitos"
          carregando={direitos.carregando}
          subtitulo={direitos.texto}
          vazio="Nenhum aluno com direito a refeição ainda."
          glifo={<path d="M18 14h34M22 14v10a13 13 0 0 0 26 0V14M35 37v19M12 60h46" />}
        />

        {/* O terceiro card não é renderizado desabilitado: ele não existe para
            quem não é administrador. Ver o comentário do componente. */}
        {souAdministrador && (
          <CartaoDeCampo
            olho="Administrar cantinas"
            titulo="Quem lança o cardápio?"
            para="/cantina/acesso"
            carregando={acesso.carregando}
            subtitulo={acesso.texto}
            vazio="Nenhuma cantina cadastrada ainda."
            glifo={
              <>
                <circle cx="35" cy="34" r="6" />
                <path d="M35 14v6M35 48v6M56 34h-6M20 34h-6M50 19l-4 4M24 45l-4 4M50 49l-4-4M24 23l-4-4" />
              </>
            }
          />
        )}
      </div>

      {!souAdministrador && (
        <p className="cant-nota">
          Administrar cantinas não aparece para o seu papel — e não aparece cinza: um botão que
          existe só para dar erro ensina a desconfiar da tela.
        </p>
      )}
    </div>
  );
}

/** "setembro · 18 dias publicados · 2 em rascunho · 1.842 pedidos" */
function useResumoDoMes() {
  const hoje = useMemo(() => new Date(), []);
  const [de, ate] = useMemo(
    () => janelaDoMes(hoje.getFullYear(), hoje.getMonth()),
    [hoje],
  );
  const { data: dias, isLoading, isError } = useCalendarioNaCoordenacao(de, ate);

  const texto = useMemo(() => {
    if (!dias) return null;
    const resumo = resumirOMes(dias);
    if (!resumo) return null;
    return `${nomeDoMes(hoje.getMonth())} · ${resumo}`;
  }, [dias, hoje]);

  // Falha de consulta NÃO vira "0 dias": um número errado é pior que nenhum.
  return { texto: isError ? null : texto, carregando: isLoading };
}

/** "87 de 900 alunos · 62 almoço · 41 janta" */
function useResumoDosDireitos() {
  // ⚠️ `useAlunos()`, e **não** `useDireitos()`: o painel de direitos traz a
  // restrição alimentar de cada aluno junto, e puxá-lo só para ter uma contagem
  // carregaria dado de saúde de menor numa tela que não pede nenhum
  // (docs/38 §2.6, e o mesmo aviso está em `hooks/consultas.ts`).
  const { data: alunos, isLoading, isError } = useAlunos();
  const texto = useMemo(() => {
    const conta = contarDireitos(alunos);
    if (!conta) return null;
    return `${conta.comDireito} de ${conta.ativos} alunos`
      + ` · ${conta.almoco} almoço · ${conta.janta} janta`;
  }, [alunos]);
  return { texto: isError ? null : texto, carregando: isLoading };
}

/** "1 cantina · 2 contas · prazo: 1 dia antes, às 10h" */
function useResumoDoAcesso() {
  const { data: cantinas, isLoading, isError } = useCantinas();
  const texto = useMemo(() => {
    if (!cantinas?.length) return null;
    const contas = cantinas.reduce((soma, c) => soma + c.contas.filter((k) => k.ativo).length, 0);
    const partes = [
      `${cantinas.length} cantina${cantinas.length === 1 ? '' : 's'}`,
      `${contas} conta${contas === 1 ? '' : 's'} ativa${contas === 1 ? '' : 's'}`,
    ];
    // O prazo padrão só entra quando há UMA cantina: com duas, o número de uma
    // delas passaria por regra da casa inteira.
    if (cantinas.length === 1) partes.push(`prazo: ${regraDePrazo(cantinas[0])}`);
    return partes.join(' · ');
  }, [cantinas]);
  return { texto: isError ? null : texto, carregando: isLoading };
}

// ─── /cantina/cardapios · o calendário ────────────────────────────────────

/**
 * O calendário do mês — 30 dias × 2 refeições, ~60 células de estado.
 *
 * É a tela mais densa de ESTADO do produto, e ela não tem semáforo: os cinco
 * estados moram em `GradeDeCardapios`, com a legenda ao lado. Toda célula que
 * existe leva ao DIA — não à refeição —, porque a pergunta que se faz olhando o
 * mês é "o que houve no dia 9", e o dia responde as duas de uma vez.
 */
export function CalendarioNaCoordenacao() {
  useEventosDaCantina('/administracao/cantina/eventos');
  const hoje = new Date();
  const [ano, setAno] = useState(hoje.getFullYear());
  const [mes, setMes] = useState(hoje.getMonth());
  const selecionada = useCantinaSelecionada();

  const [de, ate] = useMemo(() => janelaDoMes(ano, mes), [ano, mes]);
  const { data: dias = [], isLoading, isError } = useCalendarioNaCoordenacao(de, ate, selecionada);
  const { data: cantinas = [] } = useCantinas();

  function andar(passo: number) {
    const d = new Date(ano, mes + passo, 1);
    setAno(d.getFullYear());
    setMes(d.getMonth());
  }

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="O que foi lançado?"
        para="/cantina"
        destino="a cantina"
        acoes={(
          <>
            {/* Some quando há uma cantina só, que é o estado de hoje — um
                seletor de uma opção é controle que não decide nada. */}
            <SeletorDeCantina />
            <NavegadorDeMes ano={ano} mes={mes} onAndar={andar} />
          </>
        )}
      />
      <p className="cant-intro">
        {isError
          ? 'Não consegui carregar o mês.'
          : isLoading
            ? 'Carregando…'
            : resumirOMes(dias) ?? 'A cantina ainda não lançou nada neste mês.'}
        {/* De QUAL cantina é este mês. Aparece só quando há mais de uma —
            com uma só, nomeá-la é ruído.

            ⚠️ Aqui deveria estar o SELETOR da prancheta, e ele não está por
            falta de encanamento, não por desenho: `GET /administracao/cantina/
            calendario` já aceita `?cantina=`, mas `api.calendarioNaCoordenacao`
            e `useCalendarioNaCoordenacao` ainda não repassam o parâmetro. Um
            seletor que não filtra é pior que seletor nenhum, então enquanto
            isso a tela DIZ qual cantina está lendo em vez de fingir que
            escolhe. */}
        {cantinas.length > 1 && ` · lendo ${cantinas[0].nome}`}
      </p>

      <LegendaDosEstados />

      <GradeDeCardapios
        ano={ano}
        mes={mes}
        dias={dias}
        // Dia sem cardápio fica inerte: a coordenação lê, não lança.
        href={(data, _refeicao, dia) => (dia ? `/cantina/${data}` : null)}
      />
    </div>
  );
}

// ─── /cantina/:data · o dia ───────────────────────────────────────────────

/**
 * O DIA, com as DUAS refeições lado a lado. É o destino do card do Painel —
 * daí ele pular o hub: o caminho diário fica em um clique.
 *
 * ⚠️ **Dois dos cinco estados são criados pelo RELÓGIO.** Um dia passa de
 * `aberto` para `fechado` sozinho quando `pedidos_ate` vence; ninguém aperta
 * nada. Esta tela aberta às 9h59 e às 10h01 mostra coisas diferentes, e é por
 * isso que cada cartão explica a passagem em vez de só exibir o estado.
 */
export function DiaNaCoordenacao() {
  useEventosDaCantina('/administracao/cantina/eventos');
  const { data = '' } = useParams<{ data: string }>();
  const selecionada = useCantinaSelecionada();
  const { data: dia, isLoading, isError } = useDiaDaCantina(data, selecionada);
  const { data: alunos } = useAlunos();
  const { data: cantinas = [] } = useCantinas();

  const titulo = useMemo(() => capitalizar(rotuloDoDia(data)), [data]);
  useTituloDaTela(titulo);

  // Dois `useCardapioNaCoordenacao` fixos, um por refeição: a lista de hooks
  // não pode variar entre renderizações, e são sempre no máximo duas.
  const almoco = useCardapioNaCoordenacao(dia?.almoco?.id);
  const janta = useCardapioNaCoordenacao(dia?.janta?.id);

  const conta = contarDireitos(alunos);
  const pedidosNoDia = (dia?.almoco?.pedidos ?? 0) + (dia?.janta?.pedidos ?? 0);
  const cantina = nomeDaCantina(cantinas, almoco.data?.cantina_id ?? janta.data?.cantina_id);

  if (isError) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={titulo} para="/cantina/cardapios" destino="o calendário" />
        <p className="cant-erro" role="alert">Não consegui carregar este dia.</p>
      </div>
    );
  }

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo={titulo}
        para="/cantina/cardapios"
        destino="o calendário"
        acoes={
          // A magnitude do dia. Um número só, e ele responde "vale abrir isto
          // hoje?" — a mesma regra do card com magnitude do Painel.
          isLoading ? null : (
            <span className="cant-magnitude">
              <span className="cant-magnitude__numero">{pedidosNoDia}</span>
              <span className="cant-magnitude__legenda">
                pedido{pedidosNoDia === 1 ? '' : 's'} no dia
              </span>
            </span>
          )
        }
      />
      {cantina && <p className="cant-intro">{cantina}</p>}

      <div className="cant-dia-duplo">
        {(['almoco', 'janta'] as Refeicao[]).map((refeicao) => (
          <CartaoDaRefeicao
            key={refeicao}
            data={data}
            refeicao={refeicao}
            doCalendario={refeicao === 'almoco' ? dia?.almoco ?? null : dia?.janta ?? null}
            cardapio={refeicao === 'almoco' ? almoco.data : janta.data}
            carregando={isLoading || (refeicao === 'almoco' ? almoco.isLoading : janta.isLoading)}
            comDireito={conta ? (refeicao === 'almoco' ? conta.almoco : conta.janta) : null}
          />
        ))}
      </div>

      <p className="cant-nota">
        Nenhum botão de publicar, criar ou editar cardápio: publicar é da cantina, e a autoria
        fica registrada. O que a coordenação escreve é <Link to="/cantina/direitos">quem tem
        direito</Link>.
      </p>
    </div>
  );
}

type CardapioLido = NonNullable<ReturnType<typeof useCardapioNaCoordenacao>['data']>;

function CartaoDaRefeicao({
  data, refeicao, doCalendario, cardapio, carregando, comDireito,
}: {
  data: string;
  refeicao: Refeicao;
  doCalendario: DiaDoCalendario | null;
  cardapio: CardapioLido | undefined;
  carregando: boolean;
  comDireito: number | null;
}) {
  const estado: EstadoCardapio = doCalendario?.estado ?? 'sem-cardapio';
  const pedidos = doCalendario?.pedidos ?? 0;
  const nome = ROTULO_DA_REFEICAO[refeicao];

  // Sem cardápio o cartão fica INERTE, não desabilitado: não é "você não
  // pode", é "não há" — e a coordenação não é quem lança.
  const inerte = estado === 'sem-cardapio' || estado === 'sem-refeicao';

  return (
    <section className={`cant-refeicao${inerte ? ' cant-refeicao--inerte' : ''}`}>
      <header className="cant-refeicao__cabeca">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
          className="cant-refeicao__glifo">
          <path d={GLIFO_DA_REFEICAO[refeicao]} />
        </svg>
        <h2 className="cant-refeicao__nome">{nome}</h2>
        <span className={`cant-selo cant-selo--${estado}`}>{ROTULO_DO_ESTADO[estado]}</span>
      </header>

      {carregando ? (
        <p className="cant-sub">Carregando…</p>
      ) : inerte ? (
        <p className="cant-sub">
          {estado === 'sem-refeicao'
            ? 'Não se serve esta refeição neste dia.'
            : 'A cantina ainda não lançou esta refeição.'}
        </p>
      ) : (
        <>
          <p className="cant-magnitude cant-magnitude--linha">
            <span className="cant-magnitude__numero">{pedidos}</span>
            <span className="cant-magnitude__legenda">
              pedido{pedidos === 1 ? '' : 's'}
              {/* "não sei" nunca vira "0": sem a lista de alunos carregada, a
                  metade do direito simplesmente não aparece. */}
              {comDireito != null && ` · ${comDireito} com direito`}
            </span>
          </p>

          <p className="cant-sub">{fraseDoPrazo(estado, cardapio?.pedidos_ate ?? null)}</p>

          {cardapio && (
            <>
              <div className="cant-refeicao__secao">
                <h3 className="cant-refeicao__olho">Cardápio</h3>
                <ul className="cant-itens">
                  {cardapio.blocos.map((bloco) => (
                    <li key={bloco.id} className="cant-itens__bloco">
                      <span className="cant-itens__titulo">
                        {bloco.nome}
                        <span className="cant-itens__instrucao">{instrucaoDoBloco(bloco)}</span>
                      </span>
                      <ul className="cant-itens__opcoes">
                        {bloco.opcoes.map((opcao) => {
                          const quantos = cardapio.contagem
                            .find((c) => c.opcao_id === opcao.id)?.quantos ?? 0;
                          return (
                            <li
                              key={opcao.id}
                              className={`cant-itens__opcao${opcao.disponivel ? '' : ' cant-itens__opcao--fora'}`}
                            >
                              <span>{opcao.nome}</span>
                              {!opcao.disponivel && <span className="cant-tarja">acabou</span>}
                              <span className="cant-itens__quantos">
                                {quantos} pedido{quantos === 1 ? '' : 's'}
                              </span>
                            </li>
                          );
                        })}
                      </ul>
                    </li>
                  ))}
                </ul>
              </div>

              <QuemPediu
                pedidos={cardapio.pedidos}
                para={`/cantina/${data}/${refeicao}`}
                nome={nome.toLowerCase()}
              />
            </>
          )}
        </>
      )}
    </section>
  );
}

/** Quantos nomes cabem no cartão do dia antes de a lista virar a tela inteira. */
const NOMES_NO_CARTAO = 8;

/**
 * Quem pediu — os primeiros nomes como fichas, e o resto na tela da refeição.
 *
 * ⚠️ A restrição alimentar **não é escrita aqui**: a ficha carrega só a marca
 * de que existe uma. O texto é dado de saúde de menor, e lê-lo é ato
 * deliberado, na tela de direitos (docs/38 §2.6, docs/39 fase 5).
 */
function QuemPediu({
  pedidos, para, nome,
}: { pedidos: PedidoDeAluno[]; para: string; nome: string }) {
  if (!pedidos.length) return null;
  const primeiros = pedidos.slice(0, NOMES_NO_CARTAO);

  return (
    <div className="cant-refeicao__secao">
      <h3 className="cant-refeicao__olho">Quem pediu</h3>
      <ul className="cant-fichas">
        {primeiros.map((pedido) => (
          <li key={pedido.alunoId} className="cant-ficha">
            <span className="cant-ficha__iniciais" aria-hidden="true">
              {iniciais(pedido.nome)}
            </span>
            <span className="cant-ficha__nome">{primeiroENome(pedido.nome)}</span>
            {pedido.restricaoAlimentar && (
              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" role="img" className="cant-ficha__marca">
                <title>tem restrição alimentar</title>
                <circle cx="12" cy="12" r="8.6" />
                <path d="M12 8v5M12 16.4v.4" />
              </svg>
            )}
          </li>
        ))}
      </ul>
      {pedidos.length > primeiros.length && (
        <Link className="cant-elo" to={para}>
          ver os {pedidos.length} pedidos do {nome}
        </Link>
      )}
    </div>
  );
}

// ─── /cantina/:data/:refeicao · uma refeição ──────────────────────────────

/**
 * Uma refeição inteira: o cardápio, a contagem de produção e a lista COMPLETA
 * de quem pediu.
 *
 * Continua existindo depois de o dia ter nascido porque a lista de 62 nomes não
 * cabe no cartão do dia — é o destino de "ver os 62 pedidos", tela inteira com
 * URL própria (C3). O chevron sobe para o dia, não para o calendário.
 */
export function CardapioNaCoordenacao() {
  useEventosDaCantina('/administracao/cantina/eventos');
  const { data = '', refeicao = 'almoco' } = useParams<{ data: string; refeicao: Refeicao }>();
  const selecionada = useCantinaSelecionada();
  const { data: dia } = useDiaDaCantina(data, selecionada);
  const { data: cantinasParaExportar = [] } = useCantinas();
  const doDia = refeicao === 'almoco' ? dia?.almoco : dia?.janta;
  const { data: cardapio, isLoading } = useCardapioNaCoordenacao(doDia?.id);

  const titulo = `${ROTULO_DA_REFEICAO[refeicao]} · ${rotuloDoDia(data)}`;
  useTituloDaTela(titulo);

  if (isLoading) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={titulo} para={`/cantina/${data}`} destino="o dia" />
        <p className="cant-vazio">Carregando…</p>
      </div>
    );
  }

  if (!cardapio) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={titulo} para={`/cantina/${data}`} destino="o dia" />
        <p className="cant-vazio">A cantina ainda não lançou esta refeição.</p>
      </div>
    );
  }

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo={titulo}
        para={`/cantina/${data}`}
        destino="o dia"
        acoes={
          <BotoesDeExportar
            dia={{
              data,
              refeicao,
              pedidos: cardapio.pedidos,
              contagem: cardapio.contagem,
              cantina: nomeDaCantina(cantinasParaExportar, cardapio.cantina_id),
              valor: valorDaRefeicao(cantinasParaExportar, cardapio.cantina_id, refeicao),
              // ⚠️ A coordenação exporta SEM o texto da restrição alimentar.
              // A tela mostra só a marca "tem restrição alimentar", e a
              // revelação é deliberada em /cantina/direitos — um CSV que
              // vazasse o texto contornaria essa decisão pelo caminho mais
              // fácil, que é justamente o que não pode acontecer com dado de
              // saúde de menor.
              incluirRestricao: false,
            }}
          />
        }
      />
      <p className="cant-intro">
        {ROTULO_DO_ESTADO[cardapio.estado]}
        {` · ${fraseDoPrazo(cardapio.estado, cardapio.pedidos_ate)}`}
      </p>

      <section className="cant-colunas">
        <div>
          <h2 className="cant-refeicao__olho">O que cozinhar</h2>
          <ul className="cant-contagem__lista">
            {cardapio.contagem.map((linha) => (
              <li
                key={linha.opcao_id}
                className={`cant-contagem__linha${linha.disponivel ? '' : ' cant-contagem__linha--fora'}`}
              >
                <span className="cant-contagem__nome">
                  <span className="cant-contagem__bloco">{linha.bloco}</span>
                  {linha.opcao}
                </span>
                <span className="cant-contagem__numero">{linha.quantos}</span>
              </li>
            ))}
            {!cardapio.contagem.length && <li className="cant-vazio">Nenhum pedido ainda.</li>}
          </ul>
        </div>

        <div>
          <h2 className="cant-refeicao__olho">
            Quem pediu · {cardapio.pedidos.length}
          </h2>
          <ul className="cant-lista">
            {cardapio.pedidos.map((pedido) => (
              <li key={pedido.alunoId} className="cant-lista__linha">
                <span className="cant-lista__aluno">
                  {pedido.nome ?? 'sem nome'}
                  {pedido.turma && <span className="cant-lista__turma">{pedido.turma}</span>}
                </span>
                <span className="cant-lista__escolhas">{pedido.escolhas.join(' · ')}</span>
                {/* A marca, não o texto: quem precisa do texto abre em
                    /cantina/direitos, onde a revelação é deliberada. */}
                {pedido.restricaoAlimentar && (
                  <span className="cant-lista__marca">tem restrição alimentar</span>
                )}
              </li>
            ))}
            {!cardapio.pedidos.length && <li className="cant-vazio">Ninguém pediu ainda.</li>}
          </ul>
        </div>
      </section>
    </div>
  );
}

// ─── Leituras compartilhadas ──────────────────────────────────────────────

/**
 * "18 dias publicados · 2 em rascunho · 1.842 pedidos".
 *
 * Conta DIAS distintos, e não linhas: o calendário devolve uma linha por
 * refeição, e "36 lançados" num mês de 30 dias faria a pessoa reler duas vezes.
 * Um dia com almoço publicado e janta em rascunho conta nos dois — porque é
 * verdade nos dois.
 */
function resumirOMes(dias: DiaDoCalendario[]): string | null {
  if (!dias.length) return null;
  const distintos = (filtro: (d: DiaDoCalendario) => boolean) =>
    new Set(dias.filter(filtro).map((d) => d.data)).size;

  const publicados = distintos((d) => d.estado === 'aberto' || d.estado === 'fechado');
  const rascunhos = distintos((d) => d.estado === 'rascunho');
  const pedidos = dias.reduce((soma, d) => soma + d.pedidos, 0);

  const partes: string[] = [];
  if (publicados) partes.push(`${publicados} dia${publicados === 1 ? '' : 's'} publicado${publicados === 1 ? '' : 's'}`);
  if (rascunhos) partes.push(`${rascunhos} em rascunho`);
  if (pedidos) partes.push(`${pedidos.toLocaleString('pt-BR')} pedido${pedidos === 1 ? '' : 's'}`);
  return partes.length ? partes.join(' · ') : null;
}

interface ContagemDeDireitos {
  ativos: number;
  comDireito: number;
  almoco: number;
  janta: number;
}

/**
 * Quantos comem aqui, a partir da lista de alunos.
 *
 * Devolve `null` — e não zeros — quando NENHUM aluno traz o campo `direitos`:
 * `Aluno.direitos` é opcional porque nem toda rota o manda, e "não veio" não é
 * "ninguém tem". Zero no lugar de "não sei" é a mentira mais barata de escrever
 * e a mais cara de descobrir.
 */
function contarDireitos(alunos: Aluno[] | undefined): ContagemDeDireitos | null {
  if (!alunos) return null;
  if (!alunos.some((a) => a.direitos != null)) return null;
  const ativos = alunos.filter((a) => a.ativo);
  const com = (refeicao: Refeicao) =>
    ativos.filter((a) => a.direitos?.includes(refeicao)).length;
  return {
    ativos: ativos.length,
    comDireito: ativos.filter((a) => a.direitos?.length).length,
    almoco: com('almoco'),
    janta: com('janta'),
  };
}

/** "1 dia antes, às 10h" — a regra da casa, não o prazo de um dia. */
function regraDePrazo(cantina: CantinaAdmin): string {
  const quando = cantina.prazo_padrao_dias_antes === 0
    ? 'no próprio dia'
    : `${cantina.prazo_padrao_dias_antes} dia${cantina.prazo_padrao_dias_antes === 1 ? '' : 's'} antes`;
  return `${quando}, às ${cantina.prazo_padrao_hora.slice(0, 5)}`;
}

function nomeDaCantina(cantinas: CantinaAdmin[], id: string | undefined): string | null {
  if (!id) return null;
  return cantinas.find((c) => c.id === id)?.nome ?? null;
}

/**
 * A frase que explica o prazo — e, nos dois estados do relógio, que a passagem
 * entre eles não é ação de ninguém.
 *
 * É a única redação da tela que muda sozinha entre 9h59 e 10h01, e ela diz
 * isso em voz alta: sem a frase, o cartão que virou "fechado" durante o café
 * parece ter sido fechado por alguém.
 */
function fraseDoPrazo(estado: EstadoCardapio, pedidosAte: string | null): string {
  switch (estado) {
    case 'aberto':
      return `Ainda dá para pedir — ${prazoLegivel(pedidosAte)}. Quando o prazo vencer, este`
        + ' cartão passa a "contagem final" sozinho: ninguém aperta nada.';
    case 'fechado':
      return 'O prazo venceu. O aluno continua vendo o cardápio e não consegue mais pedir —'
        + ' esta contagem é a que vai para o fogão.';
    case 'rascunho':
      return 'A cantina lançou e ainda não publicou. O aluno não vê.';
    case 'sem-refeicao':
      return 'Não se serve esta refeição neste dia.';
    default:
      return 'A cantina ainda não lançou esta refeição.';
  }
}

/** "quarta, 9 de set" → "Quarta, 9 de set". */
function capitalizar(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** "Ana Beatriz Correia" → "AC". */
function iniciais(nome: string | null): string {
  const partes = (nome ?? '?').trim().split(/\s+/).filter(Boolean);
  if (!partes.length) return '?';
  const letras = [partes[0], partes.length > 1 ? partes[partes.length - 1] : ''];
  return letras.map((p) => p.charAt(0).toUpperCase()).join('');
}

/** "Ana Beatriz Correia" → "Ana Beatriz" — dois nomes cabem na ficha. */
function primeiroENome(nome: string | null): string {
  if (!nome) return 'sem nome';
  return nome.trim().split(/\s+/).slice(0, 2).join(' ');
}

/** O preço de tabela daquela refeição na cantina que serviu o dia. */
function valorDaRefeicao(
  cantinas: CantinaAdmin[],
  cantinaId: string | undefined,
  refeicao: Refeicao,
): number | null {
  const cantina = cantinas.find((c) => c.id === cantinaId);
  if (!cantina) return null;
  return (refeicao === 'almoco' ? cantina.valor_almoco : cantina.valor_janta) ?? null;
}
