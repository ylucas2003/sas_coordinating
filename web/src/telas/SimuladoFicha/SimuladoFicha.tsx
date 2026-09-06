import { useState } from 'react';
import type { CSSProperties } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';

import { DialogoComDiff } from '../../componentes/dialogos/DialogoComDiff';
import { EdicaoNota } from '../../componentes/dialogos/EdicaoNota';
import { EdicaoSimulado } from '../../componentes/dialogos/EdicaoSimulado';
import type { PatchSimulado } from '../../componentes/dialogos/EdicaoSimulado';
import type { ValoresNota } from '../../componentes/dialogos/formularioNota';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { GraficoEmCamadas } from '../../componentes/ui/GraficoEmCamadas';
import { Histograma } from '../../componentes/ui/Histograma';
import { Kpi } from '../../componentes/ui/Kpi';
import { SeloCanvas } from '../../componentes/ui/SeloCanvas';
import { isoDoDia } from '../../dominio/cantina';
import { corteDaMateria, eliminaSozinho, reguaDaCasa } from '../../dominio/criterios';
import {
  acertosEmPalavras, condicoesDaProva, contextoDaProva, fichaVazia, identidadeDaProva,
  pontuacaoBruta,
} from '../../dominio/fichaDaProva';
import type { AcaoDaProva, CondicaoDaProva } from '../../dominio/fichaDaProva';
import { lerDistribuicao } from '../../dominio/leituraDeGrafico';
import { seloDaNota } from '../../dominio/selo';
import {
  useCriteriosDisponiveis, useHistogramaSimulado, useNotasSimulado, useSimulado,
  useSimuladoPorMateria, useSimuladoPorSede,
} from '../../hooks/consultas';
import {
  useCancelarSimulado, useEditarNota, useEditarSimulado, useRetrySimuladoCanvas,
} from '../../hooks/mutacoes';
import type { NotaSimulado, QuebraSimulado } from '../../tipos/dominio';
import { fmtNota, iniciais } from '../../util/formato';

// A FICHA DE UMA PROVA — "esta prova estava boa?"
//
// Era UM card gigante com seis `.section` empilhadas dentro, todas com o mesmo
// peso: a distribuição, que é a resposta à pergunta da tela, tinha exatamente
// o mesmo título, a mesma moldura e o mesmo tamanho da tabela de notas
// individuais, que é um anexo de centenas de linhas.
//
// A hierarquia agora vem da SUPERFÍCIE, não do texto — cada pergunta é um card
// próprio e o tamanho dele é o peso dela (`styles/simulados.css`). Da chegada
// para baixo:
//
//   identidade      sem moldura: o título da tela não é conteúdo de uma seção
//   ressalva        moldura de RÉGUA, quando a prova está fora das contas
//   condições       uma linha por ação condicional, com o motivo escrito
//   números         cinco KPIs em cartões, e a linha que diz que falta ≠ zero
//   distribuição    o card largo, e o único olho em DADO da tela
//   quebras         as duas lado a lado: é a mesma pergunta em dois recortes
//   notas           o anexo, por último
//
// As três decisões que mudam a leitura, e que não se deduzem do desenho:
//
//   1 · "FORA DAS ESTATÍSTICAS" É ESTADO DA TELA, NÃO ETIQUETA. Ver a ressalva
//       abaixo — é a informação mais importante da tela quando existe.
//   2 · AUSÊNCIA NÃO É ÂMBAR. Quem faltou aparecia com etiqueta âmbar, que diz
//       "atenção, quase ruim". Ausência não é estado ruim: é ausência de DADO,
//       e o sistema já tem forma para isso (`nota-badge--ausente` — vazado,
//       tracejado, com travessão). Falta contando como zero é o erro mais caro
//       deste domínio (memória do projeto, "zeros = prováveis ausências").
//   3 · UM ALVO DE CLIQUE POR COLUNA. A linha tinha três, um invisível: ela
//       inteira navegava, mais um "Ver →" e um "Editar", segurados por duas
//       colunas de cabeçalho vazio. Agora são dois, os dois nomeados na dica
//       do cabeçalho, e o da linha é um `<Link>` de verdade.
//
// A régua NÃO se decide aqui: `dominio/criterios.ts` consulta o corte que o
// servidor resolveu (docs/18 §1.2).

/**
 * A legenda do histograma, que nomeia a FORMA — e só o que está desenhado.
 *
 * A redação antiga — "Linhas tracejadas: média (vermelho) e mediana (âmbar)" —
 * ficou apontando para cores que deixaram de existir: as duas viraram
 * referência cinza e o que as separa passou a ser cheia × tracejada
 * (`Histograma.tsx`). Uma legenda que nomeia cor errada é pior que nenhuma,
 * porque manda o olho procurar um vermelho e encontrar a média.
 *
 * Por isso o corte SAI da frase quando não há corte: `Histograma` só desenha o
 * traço de ouro depois que a régua resolveu um valor para a matéria, e mandar
 * procurar um traço que não está lá é o mesmo defeito com outro nome.
 *
 * Ela não repete a legenda que o próprio gráfico desenha: aquela carrega os
 * VALORES ("Média: 4,2"), esta carrega a convenção de leitura.
 */
function legendaDaDistribuicao(corte: number | null): string {
  const cinza = 'Linhas cinza: média (cheia) e mediana (tracejada).';
  return corte == null ? cinza : `${cinza} Traço de ouro: o corte.`;
}

/** A grade 6×4 do desenho de "sem nota" — posições fixas, em coordenadas do viewBox. */
const GRADE_VAZIA = Array.from({ length: 24 }, (_, i) => ({
  x: 30 + (i % 6) * 30,
  y: 30 + Math.floor(i / 6) * 24,
}));

/** Ficha de simulado: identidade, números, distribuição, quebras e notas. */
export function SimuladoFicha() {
  const { id = '' } = useParams();

  const { data: simulado, isPending, isError } = useSimulado(id);
  const { data: hist } = useHistogramaSimulado(id);
  const { data: porMateria = [] } = useSimuladoPorMateria(id);
  const { data: porSede = [] } = useSimuladoPorSede(id);
  const { data: notas = [], isPending: carregandoNotas } = useNotasSimulado(id);

  const editarSimulado = useEditarSimulado();
  const enviarCanvas = useRetrySimuladoCanvas();
  const cancelar = useCancelarSimulado();
  const navegar = useNavigate();
  const [desmarcando, setDesmarcando] = useState(false);
  const editarNota = useEditarNota();

  // A régua da casa: esta ficha não escolhe critério, e o corte da matéria do
  // simulado é o que o gráfico e cada nota da tabela precisam desenhar.
  const { data: criterios = [] } = useCriteriosDisponiveis();
  const regua = reguaDaCasa(criterios);
  const corte = corteDaMateria(regua, simulado?.materia?.codigo);
  const elimina = eliminaSozinho(regua, simulado?.materia?.codigo);

  const [editandoSimulado, setEditandoSimulado] = useState(false);
  const [notaEmEdicao, setNotaEmEdicao] = useState<NotaSimulado | null>(null);
  const [erroSalvar, setErroSalvar] = useState('');

  // Antes de qualquer return: hook não pode ficar atrás de saída antecipada.
  useTituloDaTela(simulado ? identidadeDaProva(simulado) : undefined);

  if (isPending) {
    return (
      <div className="tela">
        <section className="card">
          <div className="empty-state">Carregando…</div>
        </section>
      </div>
    );
  }

  if (isError || !simulado) {
    return (
      <div className="tela">
        <section className="card">
          <div className="empty-state">
            {`Simulado ${id} não encontrado.`}
            <div className="empty-state__hint">
              <Link to="/provas/simulados">← Voltar para a lista</Link>
            </div>
          </div>
        </section>
      </div>
    );
  }

  // O dia, recalculado a cada render: é ele que separa "ainda não foi
  // aplicada" de "as notas não chegaram", e congelá-lo faria a virada da
  // meia-noite passar sem a tela perceber.
  const hoje = isoDoDia(new Date());
  const nAusentes = hist?.nAusentes ?? null;
  const temHistograma = (hist?.contagens?.length ?? 0) > 0;

  // ⚠️ Só depois que a lista de notas VOLTOU. Uma consulta em voo é
  // indistinguível de uma prova sem notas, e a tela piscaria o estado vazio
  // antes de mostrar os dados.
  const vazio = carregandoNotas ? null : fichaVazia(simulado, notas, hoje);
  const condicoes = condicoesDaProva(simulado);

  // A tabela de notas sobrevive ao estado vazio quando existem linhas — é o
  // caso da prova em que todo mundo faltou, onde o anexo é a única coisa que
  // ainda tem o que dizer.
  const mostrarNotas = notas.length > 0 || !vazio;

  async function salvarSimulado(patch: PatchSimulado | null) {
    setEditandoSimulado(false);
    if (!patch) return;
    try {
      await editarSimulado.mutateAsync({ id, corpo: patch });
    } catch (e) {
      setErroSalvar(`Erro ao salvar: ${(e as Error).message}`);
    }
  }

  async function salvarNota(valores: ValoresNota | null) {
    const linha = notaEmEdicao;
    setNotaEmEdicao(null);
    if (!valores || !linha?.alunoId) return;
    try {
      await editarNota.mutateAsync({ alunoId: linha.alunoId, simuladoId: id, corpo: valores });
    } catch (e) {
      setErroSalvar(`Erro ao salvar: ${(e as Error).message}`);
    }
  }

  async function executarCondicao(acao: AcaoDaProva) {
    if (acao === 'desmarcar') {
      setDesmarcando(true);
      return;
    }
    // Enviar e tentar de novo são a MESMA chamada — o que muda é o motivo pelo
    // qual ela está sendo feita, e é isso que a faixa escreve.
    setErroSalvar('');
    try {
      await enviarCanvas.mutateAsync(id);
    } catch (e) {
      setErroSalvar((e as Error).message || 'Falha ao enviar ao Canvas.');
    }
  }

  return (
    <div className="tela">
      <div className="prova-identidade">
        <CabecaDeCampo
          titulo={identidadeDaProva(simulado)}
          para="/provas/simulados"
          destino="Provas específicas"
          // A barra de ações não dança de tamanho porque aqui há UM botão, e
          // ele está sempre presente. O que é condicional desce para a faixa
          // abaixo, uma linha por condição.
          acoes={(
            <button type="button" className="prova-botao" onClick={() => setEditandoSimulado(true)}>
              Editar simulado
            </button>
          )}
        />
        <div className="prova-identidade__contexto">
          <span>{contextoDaProva(simulado, nAusentes, hoje)}</span>
          {/* A anulação é uma CATEGORIA declarada, não uma falha operacional:
              contorno, nunca preenchimento de alerta (R4). */}
          {simulado.anulado && <span className="prova-marca">Anulado</span>}
          {simulado.origem === 'sas' && (
            <SeloCanvas estado={simulado.canvasEstado} erro={simulado.canvasErro} />
          )}
        </div>
      </div>

      {/* ── A ressalva, e ela vem ANTES das ações ──────────────────────────
          A prancheta desenha a faixa condicional em cima porque lá as duas
          telas nunca coincidem. Coincidem em produção — uma prova fora das
          estatísticas pode estar divergente do Canvas —, e quando coincidem
          esta é a que muda o significado de tudo: sem ler, o coordenador
          compara esta prova com as outras e chega à conclusão errada. */}
      {!simulado.notaConfiavel && (
        <section className="prova-ressalva">
          <h2 className="prova-ressalva__olho">Fora das estatísticas</h2>
          <p className="prova-ressalva__frase">
            Esta prova não entra nas médias, nos histogramas nem nos alertas.{' '}
            {simulado.motivoNotaNaoConfiavel || 'As notas dela não representam desempenho.'}
          </p>
          {/* A segunda metade não é decoração. Sem ela a primeira lê como
              "apague esta prova da cabeça", e o aluno de 2023 perderia o
              histórico dele na leitura de quem decide (docs/32 §1.5, item 6). */}
          <p className="prova-ressalva__resto">
            As notas individuais continuam abaixo, e continuam no histórico de cada aluno.
          </p>
        </section>
      )}

      {condicoes.length > 0 && (
        <div className="prova-condicoes">
          {condicoes.map((c) => (
            <FaixaDeCondicao
              key={c.acao}
              condicao={c}
              trabalhando={enviarCanvas.isPending}
              onAgir={() => executarCondicao(c.acao)}
            />
          ))}
        </div>
      )}

      {/* `role="alert"` porque esta é uma das duas telas do produto onde uma
          nota é ESCRITA: a falha do Canvas chega depois do clique, longe do
          foco, e sem região viva ela não é anunciada para quem usa leitor de
          tela — o coordenador sairia achando que enviou. */}
      {erroSalvar && <div className="agendar__erro" role="alert">{erroSalvar}</div>}

      {vazio ? (
        <section className="card prova-vazio">
          <div className="prova-vazio__texto">
            <div className="prova-vazio__olho">{vazio.olho}</div>
            <h2 className="prova-vazio__titulo">{vazio.titulo}</h2>
            <p className="prova-vazio__frase">{vazio.frase}</p>
          </div>
          <HistogramaQueFalta corte={corte} />
        </section>
      ) : (
        <>
          <section className="prova-numeros" aria-label="Números da prova">
            <div className="kpi-grid kpi-grid--cartoes">
              <Kpi rotulo="Média" valor={fmtNota(simulado.media)} />
              <Kpi rotulo="Mediana" valor={fmtNota(simulado.mediana)} />
              <Kpi rotulo="Desvio padrão" valor={fmtNota(simulado.desvioPadrao)} />
              <Kpi rotulo="Presentes" valor={simulado.nPresentes} />
              <Kpi rotulo="Ausentes" valor={nAusentes} />
            </div>
            {/* A linha existe porque os dois KPIs vizinhos convidam à conta
                errada: somar ausentes aos presentes e dividir a soma das notas
                por esse total. `null` não vira frase — quando o histograma não
                disse quantos faltaram, a tela não sabe, e não finge saber. */}
            {nAusentes != null && nAusentes > 0 && (
              <p className="prova-aviso-ausencia">
                {nAusentes === 1
                  ? 'Ausência não é zero: a falta não entra na média, na mediana nem no histograma.'
                  : `Ausência não é zero: as ${nAusentes} faltas não entram na média, na mediana nem no histograma.`}
              </p>
            )}
          </section>

          <section className="card">
            <div className="prova-bloco__cabeca">
              {/* O único olho em DADO da tela: é a resposta à pergunta que
                  trouxe o coordenador aqui. Marcar todos de azul seria o mesmo
                  que não marcar nenhum (R7). */}
              <h2 className="prova-bloco__olho prova-bloco__olho--dado">
                {hist?.largura_bin
                  ? `A distribuição · bins de ${fmtNota(hist.largura_bin)}`
                  : 'A distribuição'}
              </h2>
              {/* Sem barra desenhada não há convenção de leitura a explicar:
                  `Histograma` troca o gráfico por "sem dados de histograma
                  ainda" (mesma guarda), e uma legenda sobrevivente descreveria
                  linhas que não estão lá. */}
              {temHistograma && (
                <p className="prova-bloco__dica">{legendaDaDistribuicao(corte)}</p>
              )}
            </div>
            <div className="prova-bloco__corpo">
              <GraficoEmCamadas
                frase={lerDistribuicao({
                  histograma: hist,
                  media: hist?.media ?? simulado.media,
                  corte,
                  rotuloGrupo: 'de quem fez',
                })?.frase ?? null}
                grafico={(camada) => (
                  <Histograma
                    payload={hist}
                    media={hist?.media ?? simulado.media}
                    mediana={hist?.mediana ?? simulado.mediana}
                    // Esta ficha desenhava a distribuição SEM linha de corte
                    // nenhuma — o número existia na régua e não chegava aqui.
                    corte={corte != null ? { valor: corte, eliminatoria: elimina } : null}
                    kde={camada === 'estatistica'}
                    eixoYAbsoluto={camada === 'estatistica' ? {} : null}
                  />
                )}
              />
            </div>
          </section>

          {/* Empilhadas em largura cheia elas custavam duas rolagens e liam
              como duas perguntas grandes. São a mesma pergunta em dois
              recortes — "onde esta prova foi diferente?". */}
          <div className="prova-quebras">
            <QuebraDaProva
              olho="Irmãs do mesmo dia"
              primeira="Matéria"
              linhas={porMateria}
              vazio="Nenhuma outra matéria foi aplicada no mesmo dia — não há irmã com que comparar."
              paraDe={(l) => (l.simuladoId ? `/simulados/${l.simuladoId}` : null)}
              rotuloDe={(l) => l.materia ?? '—'}
            />
            <QuebraDaProva
              olho="Por sede"
              primeira="Sede"
              linhas={porSede}
              vazio="As métricas por sede ainda não foram calculadas para esta prova."
              paraDe={() => null}
              rotuloDe={(l) => l.sede ?? '—'}
            />
          </div>
        </>
      )}

      {mostrarNotas && (
        <section className="card">
          <div className="prova-bloco__cabeca">
            <h2 className="prova-bloco__olho">
              {carregandoNotas ? 'Notas individuais' : `Notas individuais · ${notas.length}`}
            </h2>
            {notas.length > 0 && (
              <p className="prova-bloco__dica">a linha inteira abre o aluno; a nota abre a edição</p>
            )}
          </div>
          {notas.length === 0 ? (
            // "Nenhuma nota registrada" enquanto a consulta ainda está em voo
            // é uma afirmação falsa por um instante — e é justamente a
            // afirmação que mandaria cobrar a prova de quem já a lançou.
            <p className="prova-bloco__vazio">
              {carregandoNotas ? 'Carregando as notas…' : 'Nenhuma nota registrada nesta prova.'}
            </p>
          ) : (
            <div className="prova-bloco__corpo prova-bloco__corpo--tabela">
              <table className="data-table prova-notas">
                <thead>
                  <tr>
                    <th>Aluno</th>
                    <th>Acertos</th>
                    <th className="prova-notas__nota">Nota</th>
                  </tr>
                </thead>
                <tbody>
                  {notas.map((n, i) => (
                    <LinhaDeNota
                      key={n.alunoId ?? i}
                      nota={n}
                      notaMaxima={simulado.notaMaxima}
                      corte={corte}
                      onEditar={setNotaEmEdicao}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {desmarcando && (
        <DialogoComDiff
          titulo="Desmarcar simulado"
          subtitulo={simulado.nome}
          mudancas={[{ campo: 'Simulado', de: 'agendado', para: 'desmarcado' }]}
          canvas={
            simulado.canvasEstado === 'sincronizado'
              ? { efeito: 'apaga o Assignment no Canvas, com as submissions dos alunos.', irreversivel: true }
              : undefined
          }
          onCancelar={() => setDesmarcando(false)}
          onVoltar={() => setDesmarcando(false)}
          onSalvar={() => undefined}
          onConfirmar={async (sincronizarCanvas) => {
            setDesmarcando(false);
            setErroSalvar('');
            try {
              await cancelar.mutateAsync({ id, sincronizarCanvas });
              navegar('/provas/simulados');
            } catch (e) {
              setErroSalvar((e as Error).message || 'Falha ao desmarcar.');
            }
          }}
        >
          {null}
        </DialogoComDiff>
      )}

      {editandoSimulado && (
        <EdicaoSimulado
          nome={simulado.nome}
          rotuloAtual={simulado.rotuloCurto}
          notaMaximaAtual={simulado.notaMaxima}
          anuladoAtual={simulado.anulado}
          origemSas={simulado.origem === 'sas'}
          onFechar={salvarSimulado}
        />
      )}

      {notaEmEdicao && (
        <EdicaoNota
          nomeAluno={notaEmEdicao.nome}
          nomeSimulado={simulado.rotuloCurto || simulado.nome}
          pontuacaoAtual={pontuacaoBruta(notaEmEdicao, simulado.notaMaxima)}
          presenteAtual={notaEmEdicao.presente}
          notaMaxima={simulado.notaMaxima}
          // A régua vai junto: o diálogo desenha a escala de 0 a 10 com o
          // corte em vigor, e sem ela ele não tem o que ancorar.
          corte={corte}
          elimina={elimina}
          onFechar={salvarNota}
        />
      )}
    </div>
  );
}

/**
 * Uma ação condicional, com o MOTIVO escrito ao lado.
 *
 * Um botão que aparece sozinho, sem dizer por que hoje ele existe, é a mesma
 * pergunta que o coordenador já não sabia responder. E a moldura só fica em
 * alerta quando a condição é falha operacional — é o caso do R4.
 */
function FaixaDeCondicao({
  condicao, trabalhando, onAgir,
}: {
  condicao: CondicaoDaProva;
  trabalhando: boolean;
  onAgir: () => void;
}) {
  const canvas = condicao.acao !== 'desmarcar';
  return (
    <div className={`prova-condicao${condicao.falha ? ' prova-condicao--falha' : ''}`}>
      <p className="prova-condicao__motivo">{condicao.motivo}</p>
      <button
        type="button"
        className="prova-botao"
        disabled={canvas && trabalhando}
        onClick={onAgir}
      >
        {canvas && trabalhando ? 'Enviando…' : condicao.rotulo}
      </button>
    </div>
  );
}

/**
 * O histograma que existiria, vazado e tracejado.
 *
 * Desenho à mão, sem biblioteca (LGPD: nada de asset de terceiro). É uma GRADE
 * e não uma curva de propósito — uma silhueta de sino sugeriria uma
 * distribuição que ninguém mediu, e o assunto deste desenho é justamente não
 * haver medida. A régua entra quando existe: ela é a única coisa da tela que
 * continua verdadeira sem nota nenhuma (R2).
 */
function HistogramaQueFalta({ corte }: { corte: number | null }) {
  const base = 126;
  const esquerda = 16;
  const direita = 204;
  const corteX = corte != null ? esquerda + (corte / 10) * (direita - esquerda) : null;
  // Perto da borda direita o rótulo sairia do quadro; ali ele troca de lado.
  const rotuloADireita = corteX == null || corteX < esquerda + (direita - esquerda) * 0.66;

  return (
    <svg
      className="prova-vazio__desenho"
      width="220" height="150" viewBox="0 0 220 150" fill="none"
      role="img" aria-label="Histograma sem nenhuma barra"
    >
      <line x1={esquerda} y1={base} x2={direita} y2={base} stroke="var(--sas-borda)" />
      {GRADE_VAZIA.map((g) => (
        <rect
          key={`${g.x}-${g.y}`}
          x={g.x} y={g.y}
          width="14" height="18" rx="3"
          stroke="var(--sas-fio-forte)" strokeWidth="1" strokeDasharray="3 3"
        />
      ))}
      {corteX != null && (
        <>
          <line
            x1={corteX} y1="22" x2={corteX} y2={base}
            stroke="var(--sas-valor)" strokeWidth="1.5" strokeDasharray="4 3"
          />
          <text
            x={rotuloADireita ? corteX + 4 : corteX - 4}
            y="18"
            textAnchor={rotuloADireita ? 'start' : 'end'}
            fontSize="10" fontWeight="700" letterSpacing=".06em"
            fill="var(--sas-valor-texto)"
          >
            {`CORTE ${fmtNota(corte)}`}
          </text>
        </>
      )}
    </svg>
  );
}

/** Uma linha da tabela de notas: dois alvos, e os dois nomeados no cabeçalho. */
function LinhaDeNota({
  nota, notaMaxima, corte, onEditar,
}: {
  nota: NotaSimulado;
  notaMaxima: number | null;
  corte: number | null;
  onEditar: (n: NotaSimulado) => void;
}) {
  const acertos = acertosEmPalavras(nota, notaMaxima);
  const nome = (
    <>
      {/* Sem foto de aluno em lugar nenhum — o SAS não guarda imagem de menor
          de idade (CLAUDE.md, armadilha 6). */}
      <span className="prova-notas__iniciais" aria-hidden="true">{iniciais(nota.nome)}</span>
      <span>{nota.nome}</span>
    </>
  );

  return (
    <tr>
      <td>
        {nota.alunoId ? (
          // `<Link>` de verdade, com a camada de clique no `::after` dele — e
          // não um `onClick` no `<tr>`. Devolve teclado, foco, botão do meio e
          // "abrir em nova aba" de graça.
          <Link className="prova-elo" to={`/alunos/${nota.alunoId}`}>{nome}</Link>
        ) : (
          // Sem `alunoId` não há ficha para abrir. Mesma anatomia, sem o elo:
          // um link que não navega é a promessa quebrada mais barata de
          // escrever e a mais cara de descobrir.
          <span className="prova-notas__sem-ficha">{nome}</span>
        )}
      </td>
      <td className="prova-notas__acertos">
        {nota.presente ? (acertos ?? '—') : 'ausente'}
      </td>
      <td className="prova-notas__nota">
        <button
          type="button"
          className="prova-notas__editar"
          aria-label={`Editar a nota de ${nota.nome}`}
          onClick={() => onEditar(nota)}
        >
          <SeloDaNota nota={nota} corte={corte} />
        </button>
      </td>
    </tr>
  );
}

/**
 * A nota desenhada contra o corte — e as duas ausências de dado, distintas.
 *
 * "Esta pessoa não fez" e "ninguém lançou ainda" pedem ações diferentes: a
 * primeira manda falar com a pessoa, a segunda manda cobrar a prova. Nenhuma
 * das duas é âmbar, que era o que a tela dizia antes — âmbar significa
 * "atenção, quase ruim", e ausência não é desempenho nenhum.
 */
function SeloDaNota({ nota, corte }: { nota: NotaSimulado; corte: number | null }) {
  if (!nota.presente) {
    return (
      <span className="nota-badge nota-badge--ausente" title="ausente — não entra na média">
        —
      </span>
    );
  }
  if (nota.pontuacao == null) {
    return (
      <span className="nota-badge nota-badge--vazia" title="sem nota lançada">
        —
      </span>
    );
  }

  const selo = seloDaNota(nota.pontuacao, corte);
  const forte = selo.estado === 'acima' && selo.intensidade > 0.5;
  const classe = selo.estado === 'sem-dado'
    ? ''
    : `nota-badge--${selo.estado}${forte ? ' nota-badge--acima-forte' : ''}`;

  return (
    <>
      {/* A etiqueta vem ANTES do chip para que os chips fechem a coluna pela
          direita: uma fileira de pílulas desalinhadas deixa de ler como
          coluna. Ela é o único vermelho da tela (R4). */}
      {selo.etiqueta && (
        <span className="nota-etiqueta" title={`${selo.etiqueta} em relação ao corte da matéria`}>
          {selo.etiqueta}
        </span>
      )}
      <span
        className={`nota-badge ${classe}`.trimEnd()}
        style={{ '--nota-intensidade': selo.intensidade } as CSSProperties}
      >
        {fmtNota(nota.pontuacao)}
      </span>
    </>
  );
}

/** Uma das duas quebras. A mesma peça em dois recortes — matéria e sede. */
function QuebraDaProva({
  olho, primeira, linhas, vazio, paraDe, rotuloDe,
}: {
  olho: string;
  primeira: string;
  linhas: QuebraSimulado[];
  vazio: string;
  /** O destino da linha, ou `null` quando ela não abre nada. */
  paraDe: (linha: QuebraSimulado) => string | null;
  rotuloDe: (linha: QuebraSimulado) => string;
}) {
  return (
    <section className="card">
      <div className="prova-bloco__cabeca">
        <h2 className="prova-bloco__olho">{olho}</h2>
      </div>
      {linhas.length === 0 ? (
        <p className="prova-bloco__vazio">{vazio}</p>
      ) : (
        <div className="prova-bloco__corpo prova-bloco__corpo--tabela">
          <table className="data-table prova-quebra-tabela">
            <thead>
              <tr>
                <th>{primeira}</th>
                <th>Média</th>
                <th>Mediana</th>
                <th>Desvio</th>
                <th>Presentes</th>
              </tr>
            </thead>
            <tbody>
              {linhas.map((l, i) => {
                const para = paraDe(l);
                const rotulo = rotuloDe(l);
                return (
                  <tr key={l.simuladoId ?? l.sede ?? i} data-navegavel={para ? 'sim' : 'nao'}>
                    <td>
                      {para
                        ? <Link className="prova-elo" to={para}>{rotulo}</Link>
                        : rotulo}
                    </td>
                    <td>{fmtNota(l.media)}</td>
                    <td>{fmtNota(l.mediana)}</td>
                    <td>{fmtNota(l.desvioPadrao)}</td>
                    <td>{l.nPresentes ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
