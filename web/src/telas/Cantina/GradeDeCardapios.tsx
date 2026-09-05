import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { gradeDoMes, isoDoDia, ROTULO_DA_REFEICAO, ROTULO_DO_ESTADO } from '../../dominio/cantina';
import type { DiaDoCalendario, EstadoCardapio, Refeicao } from '../../tipos/cantina';

// A grade de um mês, com as duas refeições em cada dia.
//
// Está fora da tela da cantina porque a coordenação lê o MESMO calendário, e a
// pergunta que ele responde ("o que falta lançar?") é a mesma dos dois lados.
// Construir duas grades seria repetir o erro que o projeto já pagou caro no
// Banco de questões, construído duas vezes e divergido.
//
// O que muda entre os dois usos é só o DESTINO de cada célula — daí `href`
// entrar como função em vez de a grade conhecer rotas.
//
// ⚠️ A cor não carrega o estado sozinha (brief §Restrições): cada célula traz
// o rótulo por extenso e a contagem. O preenchimento acompanha, não substitui.

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
              <span className="cant-dia__numero">{Number(iso.slice(-2))}</span>
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
  const conteudo = (
    <>
      <span className="cant-celula__refeicao">{ROTULO_DA_REFEICAO[refeicao]}</span>
      <span className="cant-celula__estado">{ROTULO_DO_ESTADO[estado]}</span>
      {/* A contagem só aparece quando existe pedido: "0 pedidos" num dia
          recém-publicado é ruído, não informação. */}
      {!!dia?.pedidos && (
        <span className="cant-celula__pedidos">
          {dia.pedidos} pedido{dia.pedidos === 1 ? '' : 's'}
        </span>
      )}
    </>
  );
  const classe = `cant-celula cant-celula--${estado}`;
  return para
    ? <Link className={classe} to={para}>{conteudo}</Link>
    : <span className={`${classe} cant-celula--inerte`}>{conteudo}</span>;
}

/** O seletor de mês, que as duas telas usam igual. */
export function NavegadorDeMes({
  ano, mes, onAndar,
}: { ano: number; mes: number; onAndar: (passo: number) => void }) {
  return (
    <div className="cant-meses">
      <button type="button" className="cant-tecla" onClick={() => onAndar(-1)} aria-label="Mês anterior">←</button>
      <span className="cant-mes">{MESES[mes]} de {ano}</span>
      <button type="button" className="cant-tecla" onClick={() => onAndar(1)} aria-label="Próximo mês">→</button>
    </div>
  );
}

/** Início e fim do mês em ISO — o par que as consultas de calendário pedem. */
export function janelaDoMes(ano: number, mes: number): [string, string] {
  return [isoDoDia(new Date(ano, mes, 1)), isoDoDia(new Date(ano, mes + 1, 0))];
}
