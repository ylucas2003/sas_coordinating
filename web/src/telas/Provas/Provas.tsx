import { Link, Navigate, useSearchParams } from 'react-router-dom';

import { EloQuieto } from '../../componentes/ui/Campo';
import {
  resumirCiclos, resumirProvas, subtituloDeCiclos, subtituloDeProvas,
} from '../../dominio/provas';
import { useCiclos, useSimulados } from '../../hooks/consultas';
import { hojeISO } from '../../util/data';
// ⚠️ Esta folha é importada AQUI e não em `main.tsx`, onde moram todas as
// outras: `main.tsx` não estava no escopo desta rodada de refatoração e outros
// agentes editavam arquivos vizinhos ao mesmo tempo. Nada em `provas.css`
// redefine classe de outra folha, então a posição dela no bundle não muda
// desenho nenhum — mas o lugar certo dela é junto das irmãs, e isso ficou
// registrado como pendência.
import '../../../styles/provas.css';

/**
 * O HUB DE PROVAS — a bifurcação entre duas leituras.
 *
 * Eram duas abas (`?aba=simulados`) e viraram duas portas com URL própria
 * (C3, docs/39 fase 3). A aba era mais barata em cliques e escondia o que
 * importa: ciclo e prova não são dois tipos de objeto que por acaso convivem,
 * são duas PERGUNTAS diferentes.
 *
 *   CICLO   → leitura por PESSOA. "Como o grupo está fechando contra a régua?"
 *   PROVA   → leitura por INSTRUMENTO. "Esta medida funcionou?"
 *
 * É por isso que as pendências operacionais ("3 sem nota lançada", "1 falhou
 * no Canvas") aparecem no segundo card e não no primeiro: falha de prova é
 * problema de instrumento, não de aluno. Quem vem consertar o Canvas não está
 * perguntando como a turma está indo.
 *
 * A tela tinha um risco declarado no plano: dois cards num monitor de 1440px
 * é quase nada, e a saída fácil — dois retângulos enormes no centro — lê como
 * menu de instalador. O que a salva não é o tamanho dos cards, é o bloco de
 * texto acima deles, que entrega o critério da escolha antes de cobrar a
 * escolha; e a pergunta dentro de cada porta, que nomeia a leitura em vez de
 * nomear o objeto.
 */
export function Provas() {
  const [params] = useSearchParams();
  const hoje = hojeISO();

  const { data: ciclos, isPending: ciclosPendentes } = useCiclos();
  const { data: simulados, isPending: provasPendentes } = useSimulados();

  const resumoCiclos = resumirCiclos(ciclos ?? [], hoje);
  const resumoProvas = resumirProvas(simulados ?? [], hoje);

  // Os caminhos antigos: `/provas?aba=simulados` está em link salvo e em
  // e-mail de lembrete, e continua valendo. Ele não pode virar `<Route>`
  // porque o roteador não casa query string — quem traduz é a própria tela.
  const aba = params.get('aba');
  if (aba === 'simulados') return <Navigate to="/provas/simulados" replace />;
  if (aba === 'ciclos') return <Navigate to="/provas/ciclos" replace />;

  return (
    <div className="tela">
      <div className="provas-hub">
        <div className="provas-hub__intro">
          <span className="provas-hub__olho">Provas</span>
          <h1 className="provas-hub__titulo">Duas portas para o mesmo acervo</h1>
          <p className="provas-hub__linha">
            O ciclo é onde a turma inteira é lida contra a régua. A prova específica é onde
            se julga uma aplicação.
          </p>
        </div>

        <div className="provas-hub__portas">
          <Porta
            para="/provas/ciclos"
            olho="Leitura por pessoa"
            nome="Ciclos completos"
            pergunta="Como o grupo está fechando?"
            carregando={ciclosPendentes}
            subtitulo={subtituloDeCiclos(resumoCiclos)}
            vazio="Nenhum ciclo criado. O ano começa com o primeiro ciclo — é ele que agrupa as provas e aplica a régua."
            glifo="M12 16h46M12 30h46M12 44h30M20 10v48M40 10v48"
          />
          <Porta
            para="/provas/simulados"
            olho="Leitura por instrumento"
            nome="Provas específicas"
            pergunta="A medida funcionou?"
            carregando={provasPendentes}
            subtitulo={subtituloDeProvas(resumoProvas)}
            vazio="Nenhuma prova agendada nem aplicada. Agende a primeira e ela aparece aqui."
            glifo="M22 12h20l8 8v34a2 2 0 0 1-2 2H22a2 2 0 0 1-2-2V14a2 2 0 0 1 2-2zM42 12v8h8M28 34h16M28 42h10"
          />
        </div>

        {/* C5 · o elo quieto, que some quando está vazio E quando a consulta
            falha. `provasPendentes` cobre o segundo caso: enquanto não se sabe
            o número, "0 pendências" para quem tem 3 é pior do que nada.

            O destino carrega o recorte na URL, e não é a lista inteira: um elo
            que promete "as sem nota" e entrega 255 linhas é a promessa
            quebrada mais barata de escrever. Quem aplica o recorte é a própria
            lista — ver `Simulados.tsx::PENDENCIAS`. */}
        <div className="provas-hub__rodape">
          <EloQuieto
            para="/provas/simulados?pendencia=sem-nota"
            texto="Provas sem nota lançada"
            contagem={provasPendentes ? null : resumoProvas.semNotaLancada}
          />
          <EloQuieto
            para="/provas/simulados?pendencia=canvas-falhou"
            texto="Provas que falharam no Canvas"
            contagem={provasPendentes ? null : resumoProvas.falhouNoCanvas}
          />
        </div>
      </div>
    </div>
  );
}

interface PropsPorta {
  para: string;
  /** O olho nomeia a LEITURA, não o objeto: é o que separa as duas portas. */
  olho: string;
  /** O nome da porta — decisão do dono do produto, não negociável. */
  nome: string;
  /** A pergunta que esta leitura responde (C1). */
  pergunta: string;
  carregando: boolean;
  /** O dado vivo (C2). `null` com `carregando` falso ⇒ a frase de `vazio`. */
  subtitulo: string | null;
  /** O que dizer no começo do ano, quando não há nada para contar. */
  vazio: string;
  /** O `<path>` do glifo de 70×70. Decorativo: quem nomeia o destino é o texto. */
  glifo: string;
}

function Porta({ para, olho, nome, pergunta, carregando, subtitulo, vazio, glifo }: PropsPorta) {
  return (
    <Link className="provas-porta" to={para}>
      <span className="provas-porta__olho">{olho}</span>
      <span>
        <span className="provas-porta__nome">{nome}</span>
        <span className="provas-porta__pergunta">{pergunta}</span>
        {carregando ? (
          <span className="provas-porta__esqueleto" aria-hidden="true">
            <span />
            <span />
          </span>
        ) : (
          <span className="provas-porta__sub">{subtitulo ?? vazio}</span>
        )}
      </span>
      <svg
        className="provas-porta__glifo"
        width="70"
        height="70"
        viewBox="0 0 70 70"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.4"
        strokeLinejoin="round"
        strokeLinecap="round"
        aria-hidden="true"
      >
        <path d={glifo} />
      </svg>
    </Link>
  );
}
