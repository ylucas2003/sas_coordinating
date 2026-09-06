import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { Histograma } from '../../componentes/ui/Histograma';
import { SeletorCriterio } from '../../componentes/ui/SeletorCriterio';
import { REGUA_DA_CASA } from '../../dominio/criterios';
import { Avancado, Conjunta } from './pecas';
import {
  comSinal, fraseDoBloco, LIMIAR_FORA_DO_PADRAO, montarMapa, nomeDaOrdem,
} from '../../dominio/mapaDoCiclo';
import type { BlocoDoMapa, Mapa, OrdemDoMapa } from '../../dominio/mapaDoCiclo';
import {
  useCiclo, useCriteriosDisponiveis, useEstatisticasCiclo, useSimulados,
} from '../../hooks/consultas';
import { useRecorteDaTela, useTituloDaTela } from '../../componentes/layout/migalhas';
import type { RecorteMateria } from '../../tipos/dominio';
import { fmtNota } from '../../util/formato';

// CALIBRAÇÃO — "A prova estava boa?" · o MAPA.
//
// É aqui que vive TODO o avançado de hoje, e ele deixa de precisar de toggle,
// porque a tela é dele. O toggle era uma tentativa pobre de esconder metade da
// densidade — e esconder metade não é o mesmo que separar por pergunta.
//
// A pergunta importa: ninguém abre a ferramenta querendo "o último simulado";
// abre querendo saber se a prova estava boa (C1).
//
// ── Duas alturas da mesma pergunta ────────────────────────────────────────
//
// Esta tela é onde se ACHA a prova estranha; a ficha da prova é onde se
// ENTENDE a que se achou. Para que não pareçam duas respostas concorrentes,
// duas coisas são deliberadas:
//
//   · o desenho é literalmente o mesmo `Histograma` da ficha, em outro tamanho
//     (a peça diz isso no próprio cabeçalho) — se não for reconhecidamente o
//     mesmo gráfico, o coordenador acha que são dois dados diferentes;
//   · cada cartão É o atalho para a prova que ele desenha. Achar e entrar são
//     um gesto só, e não duas telas que se contradizem.
//
// ── O que substituiu o `PorMateria` ───────────────────────────────────────
//
// A tela desenhava as mesmas doze distribuições em `pecas.PorMateria`, cada
// uma normalizada pelo PRÓPRIO máximo: a barra mais alta de Física ficava do
// tamanho da de Português e a comparação — que é o motivo desta tela existir —
// simplesmente não acontecia. O `picoCompartilhado` do `Histograma` é o
// conserto, e `dominio/mapaDoCiclo.ts` é quem calcula o denominador único, a
// ordem e o destaque, com teste ao lado.
//
// `PorMateria` e `TabelaSimuladosDoCiclo` continuam existindo em `pecas.tsx` —
// o dossiê do ciclo os monta —, mas saíram DESTA tela: repetir os doze
// histogramas logo abaixo do mapa seria a mesma informação duas vezes, que é o
// que a R7 proíbe. O que `PorMateria` tinha e o mapa não tem é o delta entre as
// fases; ele voltou como a tabela "Da Fase 1 para a Fase 2", abaixo.

const ROTULO_ORDEM: Record<OrdemDoMapa, string> = {
  variacao: 'Variação',
  distancia: 'Distância do corte',
};

export function CicloCalibracao() {
  const { id = '' } = useParams();
  const { data: ciclo } = useCiclo(id);
  const { data: todos = [] } = useSimulados();
  const [criterio, setCriterio] = useState<string>(REGUA_DA_CASA);
  const [ordemEscolhida, setOrdemEscolhida] = useState<OrdemDoMapa | null>(null);
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const { data: stats, isPending, isError } = useEstatisticasCiclo(id, criterio);

  useTituloDaTela('Calibração');
  useRecorteDaTela(null);

  const doCiclo = useMemo(() => todos.filter((s) => s.cicloId === id), [todos, id]);
  const recortes: RecorteMateria[] = useMemo(() => stats?.porMateria ?? [], [stats]);
  const nomeAnterior = stats?.cicloAnterior?.nome ?? null;

  // Duas passadas porque `temVariacao` só se sabe DEPOIS de montar os blocos —
  // o delta contra o ciclo anterior vem dentro de cada bloco do payload, não
  // num campo de topo. São doze itens; o custo é irrelevante perto de deixar a
  // tela escolher sozinha a ordem certa.
  const mapaPorDistancia = useMemo(
    () => montarMapa({ recortes, provas: doCiclo, ordem: 'distancia' }),
    [recortes, doCiclo],
  );
  const ordem: OrdemDoMapa =
    ordemEscolhida ?? (mapaPorDistancia.temVariacao ? 'variacao' : 'distancia');
  const mapa = useMemo(
    () => (ordem === 'distancia'
      ? mapaPorDistancia
      : montarMapa({ recortes, provas: doCiclo, ordem })),
    [mapaPorDistancia, recortes, doCiclo, ordem],
  );

  return (
    <div className="tela">
      <CabecaDeCampo
        titulo="A prova estava boa?"
        para={`/ciclos/${id}`}
        destino={ciclo?.nome ?? 'a ficha do ciclo'}
        acoes={
          <SeletorCriterio criterios={criterios} valor={criterio} onEscolher={setCriterio} />
        }
      />
      <p className="ciclo-mapa__intro">
        O mapa: cada aplicação do ciclo na mesma escala. Clique numa para entrar na prova.
      </p>

      {isPending ? (
        <section className="card"><div className="empty-state">Calculando estatísticas…</div></section>
      ) : isError || !stats ? (
        <section className="card">
          <div className="empty-state">Erro ao calcular estatísticas. Verifique o backend.</div>
        </section>
      ) : mapa.blocos.length === 0 ? (
        <section className="card">
          <div className="empty-state">
            <p>Nenhuma matéria deste ciclo tem nota lançada ainda.</p>
            <p className="empty-state__hint">
              O mapa aparece quando a primeira prova do ciclo tiver notas — é delas que saem as
              distribuições.
            </p>
          </div>
        </section>
      ) : (
        <>
          <FaixaDaOrdem
            mapa={mapa}
            ordem={ordem}
            nomeAnterior={nomeAnterior}
            onEscolher={setOrdemEscolhida}
          />

          <div className="ciclo-mapa">
            {mapa.blocos.map((bloco) => (
              <CartaoDoMultiplo
                key={bloco.chave}
                bloco={bloco}
                pico={mapa.pico}
                ordem={ordem}
                nomeAnterior={nomeAnterior}
              />
            ))}
          </div>

          <section className="card ciclo-ficha">
            <DeFaseAFase recortes={recortes} />
            {/* A distribuição do CICLO INTEIRO não é um décimo-terceiro
                múltiplo: é outro recorte — a média de cada aluno somando F1 e
                F2 —, e por isso fica fora da grade, com o rótulo dizendo o que
                é. Também é o único lugar da tela que carrega a leitura em
                linguagem simples; o resto é jargão. */}
            <Conjunta stats={stats} />
            <Avancado stats={stats} />
          </section>
        </>
      )}
    </div>
  );
}

// ─── R6 · o ordenador em vigor, visível e nomeado ────────────────────────
//
// Sem cor semântica, quem entrega a prova estranha é a ORDEM — e uma ordem que
// o coordenador não sabe qual é não entrega nada. As duas opções são as duas
// perguntas que "a prova estava boa?" pode significar, e elas não têm a mesma
// resposta: `variacao` pergunta pelo INSTRUMENTO (esta aplicação saiu diferente
// da mesma do ciclo passado), `distancia` pergunta pelo GRUPO (esta aplicação
// está longe do que a régua exige). Uma matéria legitimamente difícil fica
// sempre abaixo do corte sem que a prova tenha nada de errado.

function FaixaDaOrdem({
  mapa, ordem, nomeAnterior, onEscolher,
}: {
  mapa: Mapa;
  ordem: OrdemDoMapa;
  nomeAnterior: string | null;
  onEscolher: (ordem: OrdemDoMapa) => void;
}) {
  const limiar = LIMIAR_FORA_DO_PADRAO.toFixed(1).replace('.', ',');
  const anterior = nomeAnterior ?? 'o ciclo anterior';
  const quantas = mapa.foraDoPadrao === 0 ? 'nenhuma' : String(mapa.foraDoPadrao);
  const verbo = mapa.foraDoPadrao > 1 ? 'caíram' : 'caiu';
  const foraEmPalavras = ordem === 'variacao'
    ? `${quantas} ${verbo} mais de ${limiar} contra ${anterior}`
    : `${quantas} a mais de ${limiar} abaixo do corte`;

  return (
    <div className="ciclo-mapa__faixa">
      <p className="ciclo-mapa__ordem">
        {'Ordenado por '}
        <strong>{nomeDaOrdem(ordem, nomeAnterior)}</strong>
      </p>

      {mapa.temVariacao ? (
        <div className="ciclo-mapa__ordenadores">
          {(['variacao', 'distancia'] as const).map((opcao) => {
            const nome = opcao === 'variacao'
              ? `${ROTULO_ORDEM.variacao} vs ${anterior}`
              : ROTULO_ORDEM.distancia;
            return (
              // Sem `role="group"` em volta: o nome de cada botão já diz por
              // que ele ordena, e um grupo sem `<legend>` só acrescentaria uma
              // camada que o leitor de tela anuncia sem informar nada.
              <button
                key={opcao}
                type="button"
                className="ciclo-mapa__ordenador"
                aria-pressed={ordem === opcao}
                aria-label={`Ordenar por ${nome}`}
                onClick={() => onEscolher(opcao)}
              >
                {nome}
              </button>
            );
          })}
        </div>
      ) : (
        // Um botão desligado que nunca liga é ruído. O que falta é dito.
        <span className="ciclo-mapa__sem-ordenador">
          Sem ciclo anterior para comparar — só a distância do corte ordena.
        </span>
      )}

      <p className="ciclo-mapa__escala">
        {`${mapa.blocos.length} ${mapa.blocos.length === 1 ? 'aplicação' : 'aplicações'} · ${foraEmPalavras}`}
        {mapa.pico != null && (
          <>
            {' · '}
            <span>{`todas na mesma escala: a barra mais alta vale ${mapa.pico} alunos`}</span>
          </>
        )}
        {' · preenchido é acima do corte, vazado é abaixo'}
      </p>
    </div>
  );
}

// ─── Um múltiplo ─────────────────────────────────────────────────────────

function CartaoDoMultiplo({
  bloco, pico, ordem, nomeAnterior,
}: {
  bloco: BlocoDoMapa;
  pico: number | null;
  ordem: OrdemDoMapa;
  nomeAnterior: string | null;
}) {
  const classe = `ciclo-mapa__cartao${bloco.destaque ? ' ciclo-mapa__cartao--destaque' : ''}`;
  // O cartão que cresce tem mais largura na grade; o viewBox cresce junto para
  // que o fator de escala — e portanto o tamanho dos rótulos do eixo — fique
  // parecido nos dois tamanhos.
  const largura = bloco.destaque ? 500 : 320;
  const altura = bloco.destaque ? 176 : 112;

  const corpo = (
    <>
      <div className="ciclo-mapa__topo">
        <span className="ciclo-mapa__materia">{bloco.materia}</span>
        <span className="ciclo-mapa__fase">{`${bloco.fase} · n ${bloco.n}`}</span>
      </div>

      {/* A frase troca com o ordenador de propósito: o cartão relata a grandeza
          pela qual a grade está ordenada, nunca uma segunda que ninguém pediu. */}
      <div className="ciclo-mapa__frase">{fraseDoBloco(bloco, ordem, nomeAnterior)}</div>

      <Histograma
        payload={bloco.histograma}
        largura={largura}
        altura={altura}
        media={bloco.media}
        mediana={bloco.mediana}
        // R2 · a régua está sempre desenhada. O rótulo `CORTE 4,0` sai porque
        // o rodapé do cartão já imprime o número, e num cartão de 340px as duas
        // marcas se atropelam.
        corte={bloco.corte != null
          ? { valor: bloco.corte, eliminatoria: bloco.eliminatoria }
          : null}
        rotularCorte={false}
        picoCompartilhado={pico}
      />

      <div className="ciclo-mapa__rodape">
        <span>{`média ${fmtNota(bloco.media)}`}</span>
        <span>{`mediana ${fmtNota(bloco.mediana)}`}</span>
        <span className="ciclo-mapa__corte">
          {bloco.corte == null
            ? 'a régua não cobra aqui'
            : `corte ${fmtNota(bloco.corte)}${bloco.eliminatoria ? ' · elimina' : ''}`}
        </span>
      </div>
    </>
  );

  // Sem prova única não há ficha para abrir, e um link que não navega é a
  // promessa quebrada mais barata de escrever e a mais cara de descobrir —
  // vira superfície de leitura, dizendo por que não leva a lugar nenhum.
  if (bloco.provaId == null) {
    return (
      <div className={`${classe} ciclo-mapa__cartao--inerte`}>
        {corpo}
        <div className="ciclo-mapa__nota">
          {bloco.provasNoBloco > 1
            ? `${bloco.provasNoBloco} provas somadas — não há ficha do agregado`
            : 'sem ficha de prova para esta aplicação'}
        </div>
      </div>
    );
  }

  return (
    <Link className={classe} to={`/simulados/${bloco.provaId}`}>
      {corpo}
    </Link>
  );
}

// ─── O delta entre as fases ──────────────────────────────────────────────
//
// O que o mapa não diz: dentro de UMA matéria, o que a Fase 2 fez com a Fase 1.
// Vinha de `pecas.ResumoF1F2`, que pintava a variação de verde e vermelho — o
// último semáforo desta tela. Aqui ela é número com sinal, em referência: a
// direção está no próprio sinal, e gastar cor nela seria dizer que subir é bom
// e cair é ruim numa tela sobre a PROVA, não sobre o aluno (R4, R5).

function DeFaseAFase({ recortes }: { recortes: readonly RecorteMateria[] }) {
  const comDelta = recortes.filter((r) => r.fase1 && r.fase2);
  if (comDelta.length === 0) return null;

  return (
    <div className="section">
      <div className="section__title">Da Fase 1 para a Fase 2</div>
      <div className="section__subtitle">
        A mesma matéria nas duas aplicações. O sinal é a direção; a régua não muda entre as fases.
      </div>
      <table className="data-table ciclo-mapa__fases">
        <thead>
          <tr>
            <th>Matéria</th>
            <th>Média F1</th>
            <th>Média F2</th>
            <th>Δ média</th>
            <th>Aprovados F1</th>
            <th>Aprovados F2</th>
            <th>Δ aprovados</th>
          </tr>
        </thead>
        <tbody>
          {comDelta.map((rec) => (
            <tr key={rec.materia.codigo}>
              <td>{rec.materia.nome}</td>
              <td>{fmtNota(rec.fase1?.stats.media)}</td>
              <td>{fmtNota(rec.fase2?.stats.media)}</td>
              <td className="ciclo-mapa__delta">{sinalOuTraco(rec.deltaF1F2?.media)}</td>
              <td>{pct(rec.fase1?.stats.pctAprovados)}</td>
              <td>{pct(rec.fase2?.stats.pctAprovados)}</td>
              <td className="ciclo-mapa__delta">
                {sinalOuTraco(rec.deltaF1F2?.pctAprovados, ' p.p.')}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** `null` é travessão, nunca zero: "não sei" e "não mudou" não são a mesma coisa. */
function sinalOuTraco(valor: number | null | undefined, sufixo = ''): string {
  return valor == null ? '—' : `${comSinal(valor)}${sufixo}`;
}

function pct(valor: number | null | undefined): string {
  return valor == null ? '—' : `${valor.toFixed(1).replace('.', ',')}%`;
}
