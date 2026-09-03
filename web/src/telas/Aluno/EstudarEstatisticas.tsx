import type { ReactNode } from 'react';
import { useMemo } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';

import { combinarEstatisticas } from '../../dominio/banco';
import {
  lerSerieDoAssunto,
  serieDoAssunto,
  tendenciaDaSerie,
} from '../../dominio/serieDoAssunto';
import type { SerieDoAssunto } from '../../dominio/serieDoAssunto';
import { useEstatisticasDoBanco } from '../../dados/aluno';
import type {
  EstatisticasBanco,
  MateriaBanco,
  RecorrenciaTopico,
  VestibularBanco,
} from '../../dados/aluno';
import { GraficoDoAssunto } from './pecas/GraficoDoAssunto';
import { CabecaDoCampo } from './pecas/CabecaDoCampo';
import { Icone } from './pecas/Icone';
import { AVISO_DE_COBERTURA, MATERIAS_COM_TAXONOMIA, fmtInteiro } from './pecas/formato';

// ESTATÍSTICAS — o que as provas do ITA e do IME cobram.
//
// ⚠️ ESTA TELA FALA DO MUNDO, NUNCA DO ALUNO. Nenhuma métrica de acerto entra
// aqui, e a ausência é decisão de desenho, não falta de dado: acerto por assunto
// depende de classificar as 1.031 questões de simulado (Sprint 6), e uma tela
// que misturasse "o que mais cai" com "o quanto você acerta" precisaria esperar
// por isso para existir. O eixo do aluno vive em Meu progresso, e lá ele diz "o
// que você marcou", que é outra coisa.
//
// Três vistas, e o recorte é o mesmo nas três:
//
//   RANKING  os tópicos do edital por recorrência, com decomposição opcional
//   MAPA     o edital inteiro em grade, onde o vazio é tão informativo quanto o cheio
//   FICHA    um assunto, ano a ano, uma linha por vestibular
//
// ⚠️ DUAS CHAMADAS, UMA POR VESTIBULAR — e não uma agregada. `porVestibular` é
// um total sem quebra por ano, então as duas linhas da ficha só existem assim. O
// ranking "Os dois" sai de fundir as duas respostas (`combinarEstatisticas`), o
// que garante que as duas vistas contem a MESMA coisa em vez de somarem por
// caminhos diferentes.
//
// ⚠️ E AS DUAS FALHAM DE FORMA INDEPENDENTE. Quando uma cai, a tela DECLARA a
// ausência: um ranking "Os dois" que mostra só o ITA sem avisar é um número
// errado com cara de certo, e uma série ausente desenhada em zero AFIRMA que o
// assunto não cai naquela banca.
//
// ⚠️ TODO RECORTE VIVE NA URL. Abrir uma questão é rota de topo e desmonta esta
// tela; sem a URL, voltar perderia matéria, vestibular, fase e o assunto aberto.

type Vista = 'ranking' | 'mapa';
type Decompor = 'nada' | 'banca' | 'fase';

const VESTIBULARES: VestibularBanco[] = ['ITA', 'IME'];

/** Uma matéria sempre ativa: a recorrência é de UMA matéria, e o mesmo código
 *  de tópico significa coisa diferente em cada uma (0028). */
const MATERIA_PADRAO: MateriaBanco = 'Matemática';

export function EstudarEstatisticas() {
  const [params, setParams] = useSearchParams();
  const navegar = useNavigate();

  const materia =
    MATERIAS_COM_TAXONOMIA.find((m) => m === params.get('materia')) ?? MATERIA_PADRAO;
  const vestibular = VESTIBULARES.find((v) => v === params.get('vestibular')) ?? null;
  const faseCrua = Number(params.get('fase'));
  const fase = faseCrua === 1 || faseCrua === 2 ? faseCrua : undefined;
  const vista: Vista = params.get('vista') === 'mapa' ? 'mapa' : 'ranking';
  const assunto = params.get('assunto');
  const decompor: Decompor =
    params.get('decompor') === 'banca'
      ? 'banca'
      : params.get('decompor') === 'fase'
        ? 'fase'
        : 'nada';
  const eixo = params.get('eixo') === 'contagem' ? 'contagem' : 'percentual';
  const suavizar = params.get('suave') !== '0';

  const ita = useEstatisticasDoBanco(materia, 'ITA', fase);
  const ime = useEstatisticasDoBanco(materia, 'IME', fase);

  function mudar(mudancas: Record<string, string | null>) {
    setParams(
      (atual) => {
        const proximo = new URLSearchParams(atual);
        for (const [chave, valor] of Object.entries(mudancas)) {
          if (valor) proximo.set(chave, valor);
          else proximo.delete(chave);
        }
        return proximo;
      },
      { replace: true },
    );
  }

  // O recorte pedido, montado das duas respostas. `null` enquanto falta a que
  // ele precisa — nunca "o que deu", que seria o total errado sob o rótulo
  // certo.
  const dados = useMemo<EstatisticasBanco | null>(() => {
    if (vestibular === 'ITA') return ita.data ?? null;
    if (vestibular === 'IME') return ime.data ?? null;
    if (ita.data && ime.data) return combinarEstatisticas(ita.data, ime.data);
    return null;
  }, [vestibular, ita.data, ime.data]);

  const carregando =
    vestibular === 'ITA' ? ita.isPending : vestibular === 'IME' ? ime.isPending : ita.isPending || ime.isPending;

  // Falhou o que a vista precisa: não há o que desenhar.
  const falhouTudo =
    vestibular === 'ITA'
      ? ita.isError
      : vestibular === 'IME'
        ? ime.isError
        : ita.isError && ime.isError;

  // Falhou METADE do recorte "Os dois". Há número na tela, e ele está
  // incompleto — a tela diz qual metade falta em vez de somar o que sobrou e
  // apresentar como total.
  const bancaAusente =
    vestibular === null ? (ita.isError ? 'ITA' : ime.isError ? 'IME' : null) : null;

  const topicoAberto = useMemo(
    () => dados?.topicos.find((t) => t.codigo === assunto) ?? null,
    [dados, assunto],
  );

  return (
    <>
      <CabecaDoCampo titulo="Estatísticas" />
      <p className="alu-est-cobertura">
        <span className="alu-olho alu-olho--quieto">Cobertura</span>
        {AVISO_DE_COBERTURA}
      </p>

      <Recorte
        materia={materia}
        vestibular={vestibular}
        fase={fase}
        onMudar={mudar}
      />

      {bancaAusente && (
        <div className="alu-bloco alu-declaracao">
          <p className="alu-erro">
            A parte do {bancaAusente} não carregou. Os números abaixo são só do{' '}
            {bancaAusente === 'ITA' ? 'IME' : 'ITA'} — não são o total das duas bancas.
          </p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => (bancaAusente === 'ITA' ? ita.refetch() : ime.refetch())}
          >
            Tentar de novo
          </button>
        </div>
      )}

      {falhouTudo ? (
        <div className="alu-bloco">
          <p className="alu-erro">Não deu para carregar as estatísticas agora.</p>
          <p className="alu-vazio">
            Pode ser a sua conexão. O recorte que você escolheu continua aqui.
          </p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => {
              ita.refetch();
              ime.refetch();
            }}
          >
            Tentar de novo
          </button>
        </div>
      ) : carregando && !dados ? (
        <Esqueleto />
      ) : !dados ? (
        <Esqueleto />
      ) : topicoAberto ? (
        <Ficha
          topico={topicoAberto}
          dados={dados}
          respostas={{ ITA: ita.data ?? null, IME: ime.data ?? null }}
          erros={{ ITA: ita.isError, IME: ime.isError }}
          materia={materia}
          vestibular={vestibular}
          eixo={eixo}
          suavizar={suavizar}
          onMudar={mudar}
          onVerQuestoes={(codigo, nome, ano) => {
            const recorte = new URLSearchParams({ materia, topico: codigo, assunto: nome });
            // `anos` (lista), e não `ano`: o filtro do Banco é de múltipla
            // escolha desde 02/09. Vindo daqui é um ano só — o que o aluno
            // tocou no gráfico —, e lá ele pode acrescentar outros.
            if (ano) recorte.set('anos', String(ano));
            navegar(`/estudar/banco?${recorte}`);
          }}
        />
      ) : vista === 'mapa' ? (
        <MapaDoEdital dados={dados} onAbrir={(codigo) => mudar({ assunto: codigo })} onMudar={mudar} />
      ) : (
        <Ranking
          dados={dados}
          decompor={decompor}
          onAbrir={(codigo) => mudar({ assunto: codigo })}
          onMudar={mudar}
        />
      )}
    </>
  );
}

// ─── O recorte ───────────────────────────────────────────────────────────

function Recorte({
  materia,
  vestibular,
  fase,
  onMudar,
}: {
  materia: MateriaBanco;
  vestibular: VestibularBanco | null;
  fase: number | undefined;
  onMudar: (m: Record<string, string | null>) => void;
}) {
  return (
    <div className="alu-recorte">
      <Grupo rotulo="Matéria">
        {MATERIAS_COM_TAXONOMIA.map((m) => (
          <Opcao
            key={m}
            rotulo={m}
            ativa={m === materia}
            // Trocar a matéria fecha o assunto aberto: o código só é único
            // dentro dela, e mantê-lo apontaria para outro tópico sem avisar.
            onClick={() => onMudar({ materia: m, assunto: null })}
          />
        ))}
      </Grupo>

      <Grupo rotulo="Vestibular">
        <Opcao rotulo="ITA" ativa={vestibular === 'ITA'} onClick={() => onMudar({ vestibular: 'ITA' })} />
        <Opcao rotulo="IME" ativa={vestibular === 'IME'} onClick={() => onMudar({ vestibular: 'IME' })} />
        <Opcao rotulo="Os dois" ativa={vestibular === null} onClick={() => onMudar({ vestibular: null })} />
      </Grupo>

      <Grupo rotulo="Fase">
        <Opcao rotulo="1ª fase" ativa={fase === 1} onClick={() => onMudar({ fase: '1' })} />
        <Opcao rotulo="2ª fase" ativa={fase === 2} onClick={() => onMudar({ fase: '2' })} />
        <Opcao rotulo="As duas" ativa={fase === undefined} onClick={() => onMudar({ fase: null })} />
      </Grupo>
    </div>
  );
}

function Grupo({ rotulo, children }: { rotulo: string; children: ReactNode }) {
  return (
    <fieldset className="alu-recorte__grupo">
      <legend className="alu-olho alu-olho--quieto">{rotulo}</legend>
      <div className="alu-recorte__opcoes">{children}</div>
    </fieldset>
  );
}

function Opcao({
  rotulo,
  ativa,
  onClick,
}: {
  rotulo: string;
  ativa: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`alu-recorte__opcao${ativa ? ' is-ativa' : ''}`}
      aria-pressed={ativa}
      onClick={onClick}
    >
      {rotulo}
    </button>
  );
}

// ─── Ranking ─────────────────────────────────────────────────────────────

function Ranking({
  dados,
  decompor,
  onAbrir,
  onMudar,
}: {
  dados: EstatisticasBanco;
  decompor: Decompor;
  onAbrir: (codigo: string) => void;
  onMudar: (m: Record<string, string | null>) => void;
}) {
  // A régua das barras é o maior total do recorte, e nunca o total da matéria:
  // com o maior em 31 e a régua em 300, todas as barras virariam risquinhos
  // iguais e o ranking deixaria de se ler.
  const maior = Math.max(1, ...dados.topicos.map((t) => t.total));

  return (
    <>
      <div className="alu-decompor">
        <span className="alu-olho alu-olho--quieto">Decompor por</span>
        {(
          [
            ['nada', 'Nada'],
            ['banca', 'Banca'],
            ['fase', 'Fase'],
          ] as const
        ).map(([id, rotulo]) => (
          <button
            key={id}
            type="button"
            className={`alu-decompor__opcao${decompor === id ? ' is-ativa' : ''}`}
            aria-pressed={decompor === id}
            onClick={() => onMudar({ decompor: id === 'nada' ? null : id })}
          >
            {rotulo}
          </button>
        ))}
      </div>

      {decompor !== 'nada' && (
        <ul className="alu-legenda">
          {(decompor === 'banca' ? ['ITA', 'IME'] : ['1ª fase', '2ª fase']).map((rotulo, i) => (
            <li key={rotulo}>
              <span
                className="alu-legenda__cor"
                style={{
                  background:
                    i === 0
                      ? 'var(--alu-dado)'
                      : 'color-mix(in srgb, var(--alu-dado) 45%, var(--alu-superficie))',
                }}
              />
              {rotulo}
            </li>
          ))}
        </ul>
      )}

      <ul className="alu-ranking">
        {dados.topicos.map((topico) => (
          <li key={topico.codigo}>
            <button
              type="button"
              className="alu-ranking__linha"
              onClick={() => onAbrir(topico.codigo)}
            >
              <span className="alu-ranking__nome">
                <span className="alu-olho alu-olho--quieto">{topico.blocoNome}</span>
                {/* Tópico que nunca caiu fica em texto secundário: continua na
                    lista porque "não apareceu em dezoito anos" é informação de
                    estudo, mas não disputa a atenção com os que caem. */}
                <strong className={topico.total === 0 ? 'is-inerte' : undefined}>
                  {topico.nome}
                </strong>
              </span>

              <span className="alu-ranking__barras">
                {decompor === 'nada' ? (
                  <span className="alu-ranking__barra">
                    <span
                      className="alu-ranking__preenchimento"
                      style={{ width: `${(topico.total / maior) * 100}%` }}
                    />
                  </span>
                ) : (
                  <ParteAParte topico={topico} decompor={decompor} maior={maior} />
                )}
              </span>

              <span
                className={`alu-ranking__total${topico.total === 0 ? ' is-inerte' : ''}`}
              >
                {topico.total === 0 ? 'nunca caiu' : fmtInteiro(topico.total)}
              </span>
              <Icone nome="chevron" tamanho={16} />
            </button>
          </li>
        ))}
      </ul>

      {/* ⚠️ As sem classificação nunca somem: sem esta linha o aluno leria um
          recorte incompleto sem saber que é incompleto (docs/22 §8, risco 3). */}
      {dados.semClassificacao > 0 && (
        <div className="alu-ranking__orfas">
          <div>
            <strong>Sem classificação de assunto</strong>
            <p>Ninguém classificou estas questões ainda. Elas continuam no banco.</p>
          </div>
          <span>{fmtInteiro(dados.semClassificacao)}</span>
        </div>
      )}

      <button
        type="button"
        className="alu-tecla alu-tecla--fantasma alu-tecla--larga"
        onClick={() => onMudar({ vista: 'mapa' })}
      >
        Ver o mapa do edital
      </button>
    </>
  );
}

function ParteAParte({
  topico,
  decompor,
  maior,
}: {
  topico: RecorrenciaTopico;
  decompor: Exclude<Decompor, 'nada'>;
  maior: number;
}) {
  const partes =
    decompor === 'banca'
      ? [
          { rotulo: 'ITA', valor: topico.porVestibular.ITA ?? 0 },
          { rotulo: 'IME', valor: topico.porVestibular.IME ?? 0 },
        ]
      : [
          { rotulo: '1ª', valor: topico.porFase[1] ?? 0 },
          { rotulo: '2ª', valor: topico.porFase[2] ?? 0 },
        ];

  // ⚠️ Barras LADO A LADO, e nunca empilhadas em 100%. A soma dos tópicos passa
  // do total porque questão mista soma nos dois (docs/22 §1.5) — uma pizza ou
  // uma empilhada normalizada fechariam em mais de 100% e pareceriam defeito.
  return (
    <>
      {partes.map((parte, i) => (
        <span className="alu-ranking__parte" key={parte.rotulo}>
          <span className="alu-ranking__barra">
            <span
              className="alu-ranking__preenchimento"
              style={{
                width: `${(parte.valor / maior) * 100}%`,
                background:
                  i === 0
                    ? 'var(--alu-dado)'
                    : 'color-mix(in srgb, var(--alu-dado) 45%, var(--alu-superficie))',
              }}
            />
          </span>
          <span className="alu-ranking__parte-valor">{parte.valor}</span>
          <span className="alu-ranking__parte-rotulo">{parte.rotulo}</span>
        </span>
      ))}
    </>
  );
}

// ─── Mapa do edital ──────────────────────────────────────────────────────

function MapaDoEdital({
  dados,
  onAbrir,
  onMudar,
}: {
  dados: EstatisticasBanco;
  onAbrir: (codigo: string) => void;
  onMudar: (m: Record<string, string | null>) => void;
}) {
  const maior = Math.max(1, ...dados.topicos.map((t) => t.total));

  // Agrupa por bloco preservando a ordem do edital — e SUPRIME o cabeçalho
  // quando ele não acrescenta nada.
  //
  // A taxonomia real não é uniforme: em Matemática e Física a maioria dos
  // blocos tem um tópico só, com o MESMO nome ("Termodinâmica" é bloco e é
  // tópico), enquanto "Álgebra e Funções" reúne três. Repetir a palavra em
  // cima da célula dobrava a altura do mapa para não dizer nada — e o mapa
  // existe justamente para caber de relance.
  //
  // Blocos redundantes CONSECUTIVOS entram na mesma grade, sem título, para as
  // células fluírem em vez de virar uma pilha de linhas de um item.
  const grupos = useMemo(() => {
    const saida: { titulo: string | null; topicos: RecorrenciaTopico[] }[] = [];
    const porBloco = new Map<string, RecorrenciaTopico[]>();
    for (const topico of dados.topicos) {
      const lista = porBloco.get(topico.blocoNome) ?? [];
      lista.push(topico);
      porBloco.set(topico.blocoNome, lista);
    }

    for (const [bloco, topicos] of porBloco) {
      const redundante = topicos.length === 1 && topicos[0].nome === bloco;
      const ultimo = saida[saida.length - 1];
      if (redundante && ultimo && ultimo.titulo === null) {
        ultimo.topicos.push(...topicos);
      } else {
        saida.push({ titulo: redundante ? null : bloco, topicos });
      }
    }
    return saida;
  }, [dados.topicos]);

  const primeiroAno = dados.anos[0];

  return (
    <>
      <div className="alu-mapa__topo">
        <p className="alu-vazio">Todo assunto que o edital cobra. Os vazios nunca caíram.</p>
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
          onClick={() => onMudar({ vista: null })}
        >
          Ver ranking
        </button>
      </div>

      {grupos.map((grupo) => (
        <section className="alu-mapa__bloco" key={grupo.titulo ?? grupo.topicos[0].codigo}>
          {grupo.titulo && <h2 className="alu-olho alu-olho--quieto">{grupo.titulo}</h2>}
          <div className="alu-mapa__grade">
            {grupo.topicos.map((topico) => {
              const fracao = topico.total / maior;
              return (
                <button
                  key={topico.codigo}
                  type="button"
                  // O vazio é CONTORNO TRACEJADO, e não um tom pálido: pálido se
                  // confunde com "pouco", e "nunca caiu" é outra categoria.
                  className={`alu-mapa__celula${topico.total === 0 ? ' is-vazia' : ''}`}
                  style={
                    topico.total === 0
                      ? undefined
                      : {
                          background: `color-mix(in srgb, var(--alu-dado) ${Math.round(18 + fracao * 72)}%, var(--alu-superficie))`,
                          color: fracao > 0.5 ? 'var(--alu-superficie)' : 'var(--alu-magnitude)',
                        }
                  }
                  onClick={() => onAbrir(topico.codigo)}
                >
                  {topico.nome}
                  <span className="alu-so-leitor">
                    {topico.total === 0
                      ? ', nunca caiu no acervo'
                      : `, ${topico.total} questões`}
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}

      <div className="alu-mapa__legenda">
        <span className="alu-mapa__legenda-vazio">
          <span className="alu-mapa__amostra is-vazia" />
          {primeiroAno ? `não caiu desde ${primeiroAno}` : 'não caiu no acervo'}
        </span>
        <span className="alu-mapa__legenda-escala">
          menos
          {[18, 40, 65, 90].map((tom) => (
            <span
              key={tom}
              className="alu-mapa__amostra"
              style={{
                background: `color-mix(in srgb, var(--alu-dado) ${tom}%, var(--alu-superficie))`,
              }}
            />
          ))}
          mais
        </span>
      </div>
    </>
  );
}

// ─── Ficha do assunto ────────────────────────────────────────────────────

function Ficha({
  topico,
  dados,
  respostas,
  erros,
  materia,
  vestibular,
  eixo,
  suavizar,
  onMudar,
  onVerQuestoes,
}: {
  topico: RecorrenciaTopico;
  dados: EstatisticasBanco;
  respostas: Record<VestibularBanco, EstatisticasBanco | null>;
  erros: Record<VestibularBanco, boolean>;
  materia: MateriaBanco;
  vestibular: VestibularBanco | null;
  eixo: 'percentual' | 'contagem';
  suavizar: boolean;
  onMudar: (m: Record<string, string | null>) => void;
  onVerQuestoes: (codigo: string, nome: string, ano?: number) => void;
}) {
  // Só as bancas que o recorte pede. Cada série sai da resposta DELA — é assim
  // que o domínio de anos de cada uma respeita o próprio acervo.
  const pedidas = vestibular ? [vestibular] : VESTIBULARES;

  const series = useMemo<(SerieDoAssunto | null)[]>(
    () =>
      pedidas.map((banca) => {
        const resposta = respostas[banca];
        if (!resposta) return null;
        const daBanca = resposta.topicos.find((t) => t.codigo === topico.codigo);
        return serieDoAssunto(daBanca, resposta, banca, { eixo, suavizar });
      }),
    [pedidas, respostas, topico.codigo, eixo, suavizar],
  );

  const ausentes = pedidas.filter((banca) => erros[banca]);
  const frase = lerSerieDoAssunto(topico.nome, series);
  const posicao = dados.topicos.findIndex((t) => t.codigo === topico.codigo);
  const tendencia = tendenciaDaSerie(series.find((s) => s) ?? null);

  function irPara(delta: number) {
    const n = dados.topicos.length;
    const proximo = dados.topicos[(posicao + delta + n) % n];
    onMudar({ assunto: proximo.codigo });
  }

  return (
    <div className="alu-ficha">
      <div className="alu-ficha__navegacao">
        <button
          type="button"
          className="alu-ficha__seta"
          aria-label="Assunto anterior"
          onClick={() => irPara(-1)}
        >
          <Icone nome="voltar" tamanho={18} />
        </button>
        <div className="alu-ficha__identidade">
          <h2 className="alu-ficha__nome">{topico.nome}</h2>
          <span className="alu-olho alu-olho--quieto">
            {topico.blocoNome} · {materia}
          </span>
        </div>
        <button
          type="button"
          className="alu-ficha__seta"
          aria-label="Próximo assunto"
          onClick={() => irPara(1)}
        >
          <Icone nome="avancar" tamanho={18} />
        </button>
      </div>

      <div className="alu-ficha__numeros">
        <div className="alu-bloco alu-ficha__numero">
          <span className="alu-magnitude">{fmtInteiro(topico.total)}</span>
          <span className="alu-olho alu-olho--quieto">Questões no acervo</span>
        </div>
        <div className="alu-bloco alu-ficha__numero">
          <span className="alu-magnitude">
            {posicao + 1}º<span className="alu-ficha__de"> de {dados.topicos.length}</span>
          </span>
          <span className="alu-olho alu-olho--quieto">Na matéria</span>
        </div>
      </div>

      <div className="alu-bloco">
        <div className="alu-ficha__cabeca">
          <span className="alu-olho">
            {eixo === 'percentual' ? '% da prova, ano a ano' : 'Questões por ano'}
          </span>
        </div>

        {/* ⚠️ A série ausente por ERRO é declarada, e nunca desenhada como zero:
            uma linha reta no chão AFIRMA que o assunto não cai naquela banca. */}
        {ausentes.map((banca) => (
          <div className="alu-declaracao" key={banca}>
            <p>
              A série do {banca} não carregou. Ela está <strong>ausente</strong> do gráfico —
              não é zero.
            </p>
          </div>
        ))}

        {/* Tocar na coluna de um ano abre o banco naquele assunto E naquele
            ano — é o gesto que transforma "cai muito em 2019" em "quero ver
            essas". */}
        <GraficoDoAssunto
          nome={topico.nome}
          series={series}
          onAno={(ano) => onVerQuestoes(topico.codigo, topico.nome, ano)}
        />

        <div className="alu-ficha__eixos">
          <button
            type="button"
            className={`alu-recorte__opcao${eixo === 'percentual' ? ' is-ativa' : ''}`}
            aria-pressed={eixo === 'percentual'}
            onClick={() => onMudar({ eixo: null })}
          >
            % da prova
          </button>
          <button
            type="button"
            className={`alu-recorte__opcao${eixo === 'contagem' ? ' is-ativa' : ''}`}
            aria-pressed={eixo === 'contagem'}
            onClick={() => onMudar({ eixo: 'contagem' })}
          >
            Contagem
          </button>
          <button
            type="button"
            className={`alu-recorte__opcao${suavizar ? ' is-ativa' : ''}`}
            aria-pressed={suavizar}
            onClick={() => onMudar({ suave: suavizar ? '0' : null })}
          >
            Suavizar
          </button>
        </div>

        {/* Por que "Suavizar" existe e por que vem ligada: uma prova por ano dá
            série ruidosa, e o pico de um ano só parece tendência. */}
        <p className="alu-ficha__nota">
          {suavizar
            ? 'A linha é a média de três anos. Toque numa coluna para ver o número do ano.'
            : 'A linha é o valor de cada ano, sem média.'}
        </p>
      </div>

      {frase && <p className="alu-ficha__frase">{frase}</p>}

      {topico.total === 0 && (
        <p className="alu-vazio">
          Está no edital e não apareceu em nenhuma prova do acervo. O gráfico fica vazio porque
          não há ocorrência, não porque a consulta falhou.
        </p>
      )}

      <dl className="alu-ficha__secos">
        <Seco rotulo="ITA" valor={topico.porVestibular.ITA ?? 0} />
        <Seco rotulo="IME" valor={topico.porVestibular.IME ?? 0} />
        <Seco rotulo="1ª fase" valor={topico.porFase[1] ?? 0} />
        <Seco rotulo="2ª fase" valor={topico.porFase[2] ?? 0} />
      </dl>

      {tendencia && (
        <p className="alu-ficha__nota">
          {tendencia.tendencia === 'estavel'
            ? 'Sem mudança clara entre os cinco anos mais recentes e os cinco anteriores.'
            : tendencia.tendencia === 'subindo'
              ? 'Vem aparecendo mais nos últimos cinco anos.'
              : 'Vem aparecendo menos nos últimos cinco anos.'}
        </p>
      )}

      <button
        type="button"
        className="alu-tecla alu-tecla--larga"
        onClick={() => onVerQuestoes(topico.codigo, topico.nome)}
      >
        Ver as questões deste assunto
      </button>
      <button
        type="button"
        className="alu-tecla alu-tecla--fantasma alu-tecla--larga"
        onClick={() => onMudar({ assunto: null })}
      >
        Voltar ao ranking
      </button>
    </div>
  );
}

function Seco({ rotulo, valor }: { rotulo: string; valor: number }) {
  return (
    <div className="alu-ficha__seco">
      <dt className="alu-olho alu-olho--quieto">{rotulo}</dt>
      <dd className="alu-magnitude">{fmtInteiro(valor)}</dd>
    </div>
  );
}

function Esqueleto() {
  return (
    <div className="alu-est-esqueleto" aria-busy="true">
      <span className="alu-so-leitor">Contando as questões das provas…</span>
      {[0, 1, 2, 3].map((i) => (
        <div key={i} className="alu-est-esqueleto__cartao">
          <span className="alu-est-esqueleto__linha alu-est-esqueleto__linha--olho" />
          <span className="alu-est-esqueleto__bloco" />
        </div>
      ))}
    </div>
  );
}
