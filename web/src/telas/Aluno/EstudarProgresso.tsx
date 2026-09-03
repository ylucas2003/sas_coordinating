import { useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useProgressoBanco } from '../../dados/aluno';
import type { MateriaBanco, ProgressoDoAluno } from '../../dados/aluno';
import { CabecaDoCampo } from './pecas/CabecaDoCampo';
import { Icone } from './pecas/Icone';
import { AVISO_DE_COBERTURA, MATERIAS_COM_TAXONOMIA, fmtInteiro } from './pecas/formato';

// MEU PROGRESSO — o que você marcou como feito, e de quanto.
//
// ⚠️ "MARQUEI" NÃO É "ACERTEI", e a tela é obrigada a dizer isso. `resolvida`
// (migration 0029) é auto-declarado: o aluno aperta "Marcar resolvida" e ninguém
// confere nada — nem se ele respondeu, nem se acertou, nem quanto tempo levou.
// Então esta tela pode dizer "o que você marcou como feito", e NUNCA "seu
// domínio" nem "seu acerto". Quem mede acerto é o simulado, e é outra fonte.
//
// ⚠️ O VAZIO É PRIMEIRA CLASSE, e não uma sobra. A maioria dos alunos abre esta
// tela com zero marcações — é o estado mais comum, não a exceção. Por isso ele
// foi desenhado primeiro, e ensina o GESTO em vez de pedir desculpa por estar
// vazio.
//
// ⚠️ TODO NÚMERO VEM COM O PAR. "412 questões" não é progresso; "412 de 2.693"
// é. O servidor já devolve os dois juntos (`GET /banco/progresso`) justamente
// para não haver como esquecer um deles aqui.
//
// ⚠️ SEM BARRA GLOBAL, e é decisão de desenho: 2.693 é um denominador que
// ninguém zera, e uma barra parada em 15% para sempre não aconselha nada. As
// barras ficam nos recortes onde 100% é plausível — uma matéria, um assunto, um
// ano.

export function EstudarProgresso() {
  const progresso = useProgressoBanco();

  return (
    <>
      <CabecaDoCampo titulo="Meu progresso" />

      {progresso.isError ? (
        // ⚠️ FALHA DE CONSULTA NUNCA VIRA ESTADO VAZIO. "Você ainda não marcou
        // nenhuma questão" para quem marcou 412 é a mentira mais cara desta
        // tela: o aluno conclui que perdeu o que tinha feito.
        <div className="alu-bloco">
          <p className="alu-erro">Não deu para contar o seu progresso agora.</p>
          <p className="alu-vazio">
            Isto é falha de conexão, não perda de marcação — o que você marcou continua
            gravado no servidor.
          </p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => {
              progresso.refetch();
            }}
          >
            Tentar de novo
          </button>
        </div>
      ) : progresso.isPending ? (
        <Esqueleto />
      ) : progresso.data.feitas === 0 ? (
        <Vazio />
      ) : (
        <Preenchido dados={progresso.data} />
      )}
    </>
  );
}

// ─── O vazio, que é o caso comum ─────────────────────────────────────────

function Vazio() {
  return (
    <div className="alu-prog-vazio">
      <h2 className="alu-prog-vazio__titulo">Você ainda não marcou nenhuma questão</h2>
      <p className="alu-vazio">
        Este mapa mostra o que você já resolveu do banco, por matéria, por assunto e por ano
        de prova. Ele é seu: começa vazio e se preenche conforme você marca.
      </p>

      <div className="alu-bloco alu-prog-gesto">
        <span className="alu-olho">O gesto</span>
        <div className="alu-prog-gesto__linha">
          <span className="alu-prog-gesto__botao">
            <Icone nome="cheque" tamanho={16} />
            Marcar resolvida
          </span>
          <p>fica no pé de cada questão, no banco e na sessão de treino.</p>
        </div>
        <p className="alu-prog-gesto__nota">
          A marca é sua, não é correção: ela diz que você resolveu, não que acertou. Quem mede
          acerto é o simulado.
        </p>
      </div>

      <Link className="alu-tecla alu-tecla--larga" to="/estudar/banco">
        Abrir o banco
      </Link>
    </div>
  );
}

// ─── O preenchido ────────────────────────────────────────────────────────

function Preenchido({ dados }: { dados: ProgressoDoAluno }) {
  const [params, setParams] = useSearchParams();

  // Abre na matéria de maior buraco: `porMateria` já vem ordenada assim do
  // servidor, e a ordem é decisão de produto — reordenar aqui trocaria a régua
  // por uma ordenação local.
  const materiaPadrao = dados.porMateria[0]?.materia ?? 'Matemática';
  const materia =
    MATERIAS_COM_TAXONOMIA.find((m) => m === params.get('materia')) ?? materiaPadrao;

  const assuntos = useMemo(
    () => dados.porAssunto.filter((a) => a.materia === materia),
    [dados.porAssunto, materia],
  );

  return (
    <>
      <div className="alu-prog-topo">
        <p className="alu-prog-total">
          <span className="alu-magnitude alu-prog-total__feitas">{fmtInteiro(dados.feitas)}</span>
          <span className="alu-prog-total__de">de {fmtInteiro(dados.total)}</span>
        </p>
        <p className="alu-vazio">questões que você marcou como feitas</p>
        <p className="alu-prog-aviso">
          A marca é sua e não passa por correção: ela diz que você resolveu, não que acertou.
          Quem mede acerto é o simulado, em Provas.
        </p>
      </div>

      <section className="alu-prog-secao">
        <h2 className="alu-olho">Por matéria · maior buraco primeiro</h2>
        <ul className="alu-prog-lista">
          {dados.porMateria.map((m) => (
            <li className="alu-prog-item" key={m.materia}>
              <div className="alu-prog-item__cabeca">
                <strong className="alu-prog-item__nome">{m.materia}</strong>
                <span className="alu-prog-item__par">
                  {fmtInteiro(m.feitas)} de {fmtInteiro(m.total)}
                </span>
              </div>
              <Barra feitas={m.feitas} total={m.total} />
              {m.feitas === 0 && (
                <p className="alu-prog-item__nota">
                  Você nunca abriu nenhuma questão desta matéria.
                </p>
              )}
            </li>
          ))}
        </ul>
      </section>

      <section className="alu-prog-secao">
        <h2 className="alu-olho">Por assunto</h2>
        {/* ⚠️ A taxonomia só cobre três matérias. Um progresso por assunto que
            ignorasse Inglês em silêncio faria o aluno concluir que está coberto
            — e o Inglês da Fase 1 do ITA é a ÚNICA matéria eliminatória. */}
        <p className="alu-prog-cobertura">{AVISO_DE_COBERTURA}</p>

        <div className="alu-prog-materias">
          {MATERIAS_COM_TAXONOMIA.map((m) => (
            <button
              key={m}
              type="button"
              className={`alu-recorte__opcao${m === materia ? ' is-ativa' : ''}`}
              aria-pressed={m === materia}
              onClick={() =>
                setParams(
                  (atual) => {
                    const proximo = new URLSearchParams(atual);
                    proximo.set('materia', m);
                    return proximo;
                  },
                  { replace: true },
                )
              }
            >
              {m}
            </button>
          ))}
        </div>

        <ul className="alu-prog-lista">
          {assuntos.map((a) => (
            <li className="alu-prog-item" key={`${a.materia}-${a.codigo}`}>
              <Link
                className="alu-prog-item__elo"
                to={`/estudar/banco?materia=${encodeURIComponent(a.materia)}&topico=${encodeURIComponent(a.codigo)}&assunto=${encodeURIComponent(a.nome)}`}
              >
                <div className="alu-prog-item__cabeca">
                  <strong className="alu-prog-item__nome">{a.nome}</strong>
                  <span className="alu-prog-item__par">
                    {fmtInteiro(a.feitas)} de {fmtInteiro(a.total)}
                  </span>
                </div>
                <Barra feitas={a.feitas} total={a.total} />
                {a.total === 0 ? (
                  <p className="alu-prog-item__nota">
                    Está no edital e nunca caiu — não há questão deste assunto no acervo.
                  </p>
                ) : (
                  a.feitas === 0 && (
                    <p className="alu-prog-item__nota">Você nunca abriu este assunto.</p>
                  )
                )}
              </Link>
            </li>
          ))}
        </ul>
      </section>

      <GradePorAno dados={dados} />
    </>
  );
}

function Barra({ feitas, total }: { feitas: number; total: number }) {
  // Denominador zero é assunto que nunca caiu: barra vazia, e não `NaN%`.
  const fracao = total > 0 ? feitas / total : 0;
  return (
    <div className="alu-prog-barra">
      <div className="alu-prog-barra__preenchimento" style={{ width: `${fracao * 100}%` }} />
    </div>
  );
}

// ─── A grade matéria × ano ───────────────────────────────────────────────

function GradePorAno({ dados }: { dados: ProgressoDoAluno }) {
  // Índice (matéria, ano) → par. Par AUSENTE significa "não houve prova dessa
  // matéria nesse ano", e é diferente de "houve e você não fez nenhuma": a
  // primeira é buraco de acervo, a segunda é buraco de estudo, e desenhar as
  // duas igual faria o aluno confundir uma com a outra.
  const porChave = useMemo(() => {
    const mapa = new Map<string, { feitas: number; total: number }>();
    for (const p of dados.porAno) mapa.set(`${p.materia}|${p.ano}`, p);
    return mapa;
  }, [dados.porAno]);

  const materias = useMemo(
    () => [...new Set(dados.porAno.map((p) => p.materia))].sort(),
    [dados.porAno],
  );

  if (dados.anos.length === 0) return null;

  return (
    <section className="alu-prog-secao">
      <h2 className="alu-olho">Por ano de prova</h2>
      <p className="alu-prog-cobertura">
        Célula vazia é ano que você nunca tocou; onde não há célula, não houve prova daquela
        matéria naquele ano. Toque para abrir o banco no ano e na matéria.
      </p>

      {/* Rola dentro do próprio contêiner — o corpo da página nunca rola na
          horizontal. */}
      <div className="alu-prog-grade__trilho">
        <table className="alu-prog-grade">
          <caption className="alu-so-leitor">
            Questões marcadas como feitas, por matéria e por ano de prova
          </caption>
          <thead>
            <tr>
              <th scope="col">
                <span className="alu-so-leitor">Matéria</span>
              </th>
              {dados.anos.map((ano) => (
                <th scope="col" key={ano}>
                  {ano}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {materias.map((materia) => (
              <tr key={materia}>
                <th scope="row">{materia}</th>
                {dados.anos.map((ano) => (
                  <Celula
                    key={ano}
                    materia={materia}
                    ano={ano}
                    par={porChave.get(`${materia}|${ano}`)}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Celula({
  materia,
  ano,
  par,
}: {
  materia: MateriaBanco;
  ano: number;
  par: { feitas: number; total: number } | undefined;
}) {
  if (!par) {
    // Sem prova naquele ano. Fica em branco e fora da ordem de tabulação: não
    // há nada para abrir, e um alvo que não leva a lugar nenhum cansa quem
    // navega por teclado.
    return <td className="alu-prog-grade__vazia" aria-label={`${materia} em ${ano}: sem prova`} />;
  }

  const fracao = par.total > 0 ? par.feitas / par.total : 0;
  return (
    <td className="alu-prog-grade__celula">
      <Link
        className={`alu-prog-grade__alvo${par.feitas === 0 ? ' is-intocada' : ''}`}
        style={
          par.feitas === 0
            ? undefined
            : {
                background: `color-mix(in srgb, var(--alu-dado) ${Math.round(25 + fracao * 75)}%, transparent)`,
              }
        }
        to={`/estudar/banco?materia=${encodeURIComponent(materia)}&anos=${ano}`}
      >
        <span className="alu-so-leitor">
          {`${materia} em ${ano}: ${par.feitas} de ${par.total} marcadas`}
        </span>
      </Link>
    </td>
  );
}

function Esqueleto() {
  return (
    <div className="alu-est-esqueleto" aria-busy="true">
      <span className="alu-so-leitor">Contando o que você marcou…</span>
      {[0, 1, 2].map((i) => (
        <div key={i} className="alu-est-esqueleto__cartao">
          <span className="alu-est-esqueleto__linha alu-est-esqueleto__linha--olho" />
          <span className="alu-est-esqueleto__bloco" />
        </div>
      ))}
    </div>
  );
}
