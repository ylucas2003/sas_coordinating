import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { gradeDoMes, isoDoDia, ROTULO_DA_REFEICAO } from '../../dominio/cantina';
import type { DiaDoCalendario, EstadoCardapio, Refeicao } from '../../tipos/cantina';

// A grade de um mês, com as duas refeições em cada dia.
//
// Está fora da tela da cantina porque a coordenação lê o MESMO calendário, e a
// pergunta que ele responde ("o que falta lançar?") é a mesma dos dois lados.
// Construir duas grades seria repetir o erro que o projeto já pagou caro no
// Banco de questões, construído duas vezes e divergido.
//
// O que muda entre os dois usos é só o DESTINO de cada célula — daí `href`
// entrar como função em vez de a grade conhecer rotas. É ele também que decide
// o que fica INERTE: na cantina o dia sem cardápio é clicável (é assim que ela
// lança); na coordenação, não, porque a coordenação lê e não lança.
//
// ⚠️ **Os cinco estados sem semáforo** (prancheta "Painel e cantina", decisão
// 2). Nenhum deles usa verde ou vermelho, e a leitura não depende da cor:
//
//   aberto ⟷ fechado   MESMO preenchimento em dado, porque são o mesmo
//                      cardápio em dois momentos do RELÓGIO. Divergem só no
//                      glifo (relógio × cadeado) e na redação do prazo. Se
//                      divergissem de cor lerian como coisas diferentes — e a
//                      passagem entre eles não é ação de ninguém: acontece
//                      sozinha quando `pedidos_ate` vence.
//   sem-cardapio       hachura. É o vazio que o sistema conhece.
//   rascunho           contorno tracejado com o lápis: existe conteúdo, e o
//                      aluno não vê. Ausência de natureza diferente da de cima.
//   sem-refeicao       não é falta, é "não se aplica" — uma diagonal única em
//                      fio de referência.

const GLIFO_RELOGIO = 'M12 7.6V12l3 2M12 3.4a8.6 8.6 0 1 0 0 17.2 8.6 8.6 0 0 0 0-17.2z';
const GLIFO_CADEADO = 'M7 11V8a5 5 0 0 1 10 0v3M5.6 11h12.8v9H5.6z';
const GLIFO_LAPIS = 'M5 19h4l9.4-9.4a2.1 2.1 0 0 0-3-3L6 16v3z';
const GLIFO_DIAGONAL = 'M5 19L19 5';

/**
 * O glifo de cada refeição — garfo e faca, cloche.
 *
 * Mora aqui, e não em `dominio/cantina.ts`, porque `dominio/` é regra pura com
 * teste ao lado e um `<path>` não é regra nenhuma. Esta folha é a dona do
 * vocabulário visual da cantina na coordenação; o dia e as pílulas de direito
 * importam daqui para o desenho ser um só.
 */
export const GLIFO_DA_REFEICAO: Record<Refeicao, string> = {
  almoco: 'M7 3v7a3 3 0 0 0 6 0V3M10 13v8M16 3c2 0 3 1.6 3 4s-1 4-3 4v10',
  janta: 'M4 10h16a8 8 0 0 1-16 0zM12 3.4v3.2M6 20h12',
};

interface Traje {
  glifo: string | null;
  /**
   * O que a célula ESCREVE.
   *
   * Em `aberto` e `fechado` é o nome da refeição, porque ali quem carrega o
   * estado é o glifo mais a contagem — e o que a pessoa procura varrendo o mês
   * é "onde está a janta". Nos outros três o estado toma a vaga: não há
   * contagem para ler, e "não lançado" é a informação inteira.
   */
  rotulo: (refeicao: Refeicao) => string;
  /** A situação por extenso, para o leitor de tela. */
  situacao: string;
  /** A contagem só aparece onde ela quer dizer alguma coisa. */
  mostraPedidos: boolean;
}

const TRAJE: Record<EstadoCardapio, Traje> = {
  aberto: {
    glifo: GLIFO_RELOGIO,
    rotulo: (r) => ROTULO_DA_REFEICAO[r].toLowerCase(),
    situacao: 'aberto para pedidos',
    mostraPedidos: true,
  },
  fechado: {
    glifo: GLIFO_CADEADO,
    rotulo: (r) => ROTULO_DA_REFEICAO[r].toLowerCase(),
    situacao: 'prazo encerrado, contagem final',
    mostraPedidos: true,
  },
  rascunho: {
    glifo: GLIFO_LAPIS,
    rotulo: () => 'rascunho',
    situacao: 'em rascunho, o aluno ainda não vê',
    mostraPedidos: false,
  },
  'sem-cardapio': {
    glifo: null,
    rotulo: () => 'não lançado',
    situacao: 'não lançado pela cantina',
    mostraPedidos: false,
  },
  'sem-refeicao': {
    glifo: GLIFO_DIAGONAL,
    rotulo: () => 'não se serve',
    situacao: 'não é servido neste dia',
    mostraPedidos: false,
  },
};

const MESES = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];
const CABECA_DA_SEMANA = ['dom', 'seg', 'ter', 'qua', 'qui', 'sex', 'sáb'];
const REFEICOES: Refeicao[] = ['almoco', 'janta'];

interface Props {
  ano: number;
  mes: number;
  dias: DiaDoCalendario[];
  /** Para onde vai o clique. `null` deixa a célula sem link — é o que a
      coordenação usa nos dias que ainda não existem: ela não cria cardápio. */
  href: (data: string, refeicao: Refeicao, dia?: DiaDoCalendario) => string | null;
}

export function GradeDeCardapios({ ano, mes, dias, href }: Props) {
  const casas = useMemo(() => gradeDoMes(ano, mes), [ano, mes]);
  const hoje = isoDoDia(new Date());

  // Índice por `data|refeicao`: a grade pergunta uma célula de cada vez, e
  // varrer a lista dentro do laço seria O(dias × cardápios) para nada.
  const porDia = useMemo(() => {
    const mapa = new Map<string, DiaDoCalendario>();
    for (const dia of dias) mapa.set(`${dia.data}|${dia.refeicao}`, dia);
    return mapa;
  }, [dias]);

  return (
    // Sem `role="grid"`: o ARIA grid promete navegação por setas entre células,
    // que esta grade não implementa — e papel que promete o que não cumpre é
    // pior para o leitor de tela do que papel nenhum. Como toda célula é um
    // link, uma região rotulada já entrega a leitura certa.
    <section className="cant-grade" aria-label={`Cardápios de ${MESES[mes]} de ${ano}`}>
      {CABECA_DA_SEMANA.map((d) => (
        <div key={d} className="cant-grade__cabeca">{d}</div>
      ))}

      {casas.map((iso, i) => (
        <div
          // Índice nas casas vazias porque elas não têm data — e são
          // exatamente as que nunca reordenam.
          key={iso ?? `vazio-${i}`}
          className={`cant-dia${iso ? '' : ' cant-dia--vazio'}${iso === hoje ? ' cant-dia--hoje' : ''}`}
        >
          {iso && (
            <>
              <div className="cant-dia__topo">
                <span className="cant-dia__numero">{Number(iso.slice(-2))}</span>
                {iso === hoje && <span className="cant-dia__hoje">hoje</span>}
              </div>
              {REFEICOES.map((refeicao) => (
                <Celula
                  key={refeicao}
                  dia={porDia.get(`${iso}|${refeicao}`)}
                  refeicao={refeicao}
                  para={href(iso, refeicao, porDia.get(`${iso}|${refeicao}`))}
                />
              ))}
            </>
          )}
        </div>
      ))}
    </section>
  );
}

function Celula({
  dia, refeicao, para,
}: { dia?: DiaDoCalendario; refeicao: Refeicao; para: string | null }) {
  const estado: EstadoCardapio = dia?.estado ?? 'sem-cardapio';
  const traje = TRAJE[estado];
  const pedidos = traje.mostraPedidos ? dia?.pedidos ?? 0 : null;

  // A leitura completa em UM nó, com a face marcada `aria-hidden`: o rótulo
  // visível é abreviado de propósito ("rascunho" no lugar de "janta"), e quem
  // ouve a tela não pode perder de qual refeição se trata.
  const leitura = `${ROTULO_DA_REFEICAO[refeicao]}, ${traje.situacao}`
    + (pedidos != null ? `, ${pedidos} ${pedidos === 1 ? 'pedido' : 'pedidos'}` : '');

  const conteudo = (
    <>
      <span className="cant-celula__face" aria-hidden="true">
        {traje.glifo && (
          <svg
            className="cant-celula__glifo" width="11" height="11" viewBox="0 0 24 24"
            fill="none" stroke="currentColor" strokeWidth="2"
            strokeLinecap="round" strokeLinejoin="round"
          >
            <path d={traje.glifo} />
          </svg>
        )}
        <span className="cant-celula__rotulo">{traje.rotulo(refeicao)}</span>
        {pedidos != null && <span className="cant-celula__pedidos">{pedidos}</span>}
      </span>
      <span className="cant-so-leitor">{leitura}</span>
    </>
  );

  const classe = `cant-celula cant-celula--${estado}`;
  return para
    ? <Link className={classe} to={para}>{conteudo}</Link>
    : <span className={`${classe} cant-celula--inerte`}>{conteudo}</span>;
}

/**
 * A legenda dos cinco estados.
 *
 * Está desenhada em contorno tracejado, e não como um card: ela é aparato de
 * leitura, não dado. Fica ao lado da grade porque ~60 células de estado numa
 * tela sem semáforo pedem a chave à vista — decorar cinco preenchimentos antes
 * de ler o mês é o que faz alguém desistir da tela.
 */
export function LegendaDosEstados() {
  const estados: EstadoCardapio[] = ['aberto', 'fechado', 'rascunho', 'sem-cardapio', 'sem-refeicao'];
  const frase: Record<EstadoCardapio, string> = {
    aberto: 'aberto · dá para pedir',
    fechado: 'fechado · o prazo venceu',
    rascunho: 'rascunho · o aluno não vê',
    'sem-cardapio': 'não lançado',
    'sem-refeicao': 'não se serve',
  };

  return (
    <div className="cant-legenda">
      <span className="cant-legenda__olho">Os cinco estados</span>
      {estados.map((estado) => (
        <span key={estado} className="cant-legenda__item">
          <span className={`cant-legenda__amostra cant-celula--${estado}`}>
            {TRAJE[estado].glifo && (
              <svg
                width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
              >
                <path d={TRAJE[estado].glifo!} />
              </svg>
            )}
          </span>
          {frase[estado]}
        </span>
      ))}
    </div>
  );
}

/** O seletor de mês, que as duas telas usam igual. */
export function NavegadorDeMes({
  ano, mes, onAndar,
}: { ano: number; mes: number; onAndar: (passo: number) => void }) {
  return (
    <div className="cant-meses">
      <button type="button" className="cant-tecla cant-tecla--quadrada" onClick={() => onAndar(-1)} aria-label="Mês anterior">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M14 6l-6 6 6 6" />
        </svg>
      </button>
      <span className="cant-mes">{MESES[mes]} de {ano}</span>
      <button type="button" className="cant-tecla cant-tecla--quadrada" onClick={() => onAndar(1)} aria-label="Próximo mês">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M10 6l6 6-6 6" />
        </svg>
      </button>
    </div>
  );
}

/** Início e fim do mês em ISO — o par que as consultas de calendário pedem. */
export function janelaDoMes(ano: number, mes: number): [string, string] {
  return [isoDoDia(new Date(ano, mes, 1)), isoDoDia(new Date(ano, mes + 1, 0))];
}

/** O nome do mês, para quem monta subtítulo fora daqui. */
export function nomeDoMes(mes: number): string {
  return MESES[mes];
}
