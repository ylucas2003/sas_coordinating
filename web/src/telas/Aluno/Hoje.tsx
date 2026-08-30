import { Link } from 'react-router-dom';

import type { EvolucaoAluno, MateriaContraCorte, Zona } from '../../dados/aluno';
import {
  useEvolucao,
  useInsight,
  useMateriasContraCorte,
  useMissaoDoDia,
  useProximoSimulado,
  useSequencia,
  useSimulado,
  useSimulados,
  useZona,
} from '../../dados/aluno';
import { BarraCorte } from './pecas/BarraCorte';
import { Bloco } from './pecas/Bloco';
import { ContagemRegressiva } from './pecas/ContagemRegressiva';
import { Corrente, LeituraDaSequencia } from './pecas/Corrente';
import { Icone } from './pecas/Icone';
import { TarjaFonte } from './pecas/TarjaFonte';
import { AVISO_DE_COBERTURA, fmt, fmtDataCurta, fmtDelta } from './pecas/formato';

// HOJE — "o que eu faço agora".
//
// A ordem da tela é a resposta a essa pergunta, e não a ordem do modelo de
// dados (docs/24 §7.1):
//
//   1. a missão   o que fazer nos próximos vinte minutos
//   2. sequência  o que já foi construído e não se quer perder
//   3. contagem   quando é a próxima corrida
//   4. o corte    onde estou contra a régua
//   5. o ciclo    o que os últimos resultados dizem
//   6. a nota     a consequência, e só ela
//
// ⚠️ A NOTA NÃO É O HERÓI. A Casa era um boletim de seis indicadores olhando
// todos para trás, e é justamente por isso que não havia motivo para abrir o app
// numa terça comum — nota só muda a cada três semanas. A nota desceu para a tira
// do rodapé; o topo é a missão.
//
// ⚠️ NENHUM XP APARECE AQUI perto de treino. Treino não pontua: só o simulado
// pontua, porque só o simulado é verificável (docs/26 §1 e §2). Um "+20 XP" na
// missão contradiz a regra central do produto.

export function Hoje({ nome }: { nome: string }) {
  return (
    <div className="alu-hoje">
      {/* No celular quem cumprimenta é a barra de topo do casco, e repetir a
          saudação gastaria a primeira dobra — que é do herói. No desktop a barra
          de topo não existe, então a saudação vira o título da tela. O elemento
          fica no DOM nos dois casos: no celular o CSS o esconde só visualmente,
          para o leitor de tela continuar tendo um h1. */}
      <h1 className="alu-titulo-tela alu-hoje__saudacao">Olá, {nome}</h1>

      <MissaoDeHoje />

      {/* ⚠️ Sequência e contagem regressiva também estão na coluna direita do
          desktop (CascoAluno.tsx), e a repetição é deliberada: a lateral é o
          RESUMO — o número e a corrente miúda — e o que está aqui é a versão
          COMPLETA, com a corrente inteira rotulada simulado a simulado e a barra
          que mede o intervalo entre uma prova e a outra. No celular a lateral
          não existe, e então a Hoje é a única casa desses dois blocos. */}
      <BlocoDaSequencia />
      <BlocoDaContagem />

      <OndeVoceEsta />
      <LeituraDoCiclo />
      <TiraDaUltimaNota />
    </div>
  );
}

// ─── 1 · O herói: a missão do dia ────────────────────────────────────────

/**
 * O elemento maior da tela.
 *
 * A quantidade e o assunto vão em MAGNITUDE porque é o que se lê de longe; a
 * razão vai numa linha quieta logo abaixo, e ela não é enfeite — "por que estou
 * vendo isto" é a pergunta que mata a confiança numa recomendação quando não tem
 * resposta (docs/24 §4.5).
 */
function MissaoDeHoje() {
  const { data: missao, isPending, isError } = useMissaoDoDia();

  if (isPending) {
    return (
      <Bloco fonte="missaoDoDia" olho="Missão de hoje" className="alu-hoje__hero">
        <div className="alu-hoje__esqueleto" aria-hidden="true">
          <span className="alu-hoje__osso alu-hoje__osso--numero" />
          <span className="alu-hoje__osso alu-hoje__osso--linha" />
          <span className="alu-hoje__osso alu-hoje__osso--curta" />
          <span className="alu-hoje__osso alu-hoje__osso--tecla" />
        </div>
        <p className="alu-so-leitor">Montando sua missão de hoje…</p>
      </Bloco>
    );
  }

  // Sem missão o herói NÃO vira aviso: vira convite. É a diferença entre uma
  // tela vazia e uma tela morta (docs/24 §7, "estados que precisam existir").
  if (!missao) {
    return (
      <Bloco fonte="missaoDoDia" olho="Missão de hoje" className="alu-hoje__hero">
        {isError && (
          <p className="alu-erro">
            Não deu para montar sua missão agora. O acervo continua aberto.
          </p>
        )}
        <p className="alu-magnitude alu-hoje__convite">Escolha um assunto para treinar</p>
        <p className="alu-hoje__razao">As provas do ITA e do IME estão todas aqui.</p>
        <Link className="alu-tecla alu-tecla--larga" to="/estudar">
          Escolher assunto
        </Link>
        <p className="alu-hoje__rodape-quieto">{AVISO_DE_COBERTURA}</p>
      </Bloco>
    );
  }

  return (
    <Bloco fonte="missaoDoDia" olho="Missão de hoje" className="alu-hoje__hero">
      <p className="alu-hoje__hero-linha">
        <strong className="alu-magnitude alu-hoje__quantidade">{missao.quantidade}</strong>
        <span className="alu-hoje__hero-unidade">
          {missao.quantidade === 1 ? 'questão de' : 'questões de'}
        </span>
      </p>
      <p className="alu-magnitude alu-hoje__assunto">{missao.nome}</p>
      <p className="alu-olho alu-olho--quieto">
        {missao.materia} · {missao.topicoCodigo}
      </p>
      <p className="alu-hoje__razao">{missao.razao}</p>

      <Link className="alu-tecla alu-tecla--larga" to="/treino/prioridade">
        Começar
      </Link>

      {/* Dito uma vez, quieto, e de propósito: a economia do produto inverte a
          expectativa de quem já usou app de idioma. Treinar informa o plano;
          quem paga é a prova (docs/26 §2). Sem essa linha o aluno procura o XP
          que nunca vai aparecer aqui. */}
      <p className="alu-hoje__rodape-quieto">Treinar não vale XP — quem paga é o simulado.</p>

      {/* ⚠️ docs/24 §3.3: a missão só sabe recomendar Matemática, Física e
          Química — a taxonomia do edital não alcança as outras três. Sem esta
          linha o aluno conclui que está coberto, e logo abaixo nesta mesma tela
          ele vê o Inglês dele contra o corte 5,0, que é o ÚNICO eliminatório.
          Um plano que ignora Inglês em silêncio é pior que nenhum plano. */}
      <p className="alu-hoje__rodape-quieto">{AVISO_DE_COBERTURA}</p>
    </Bloco>
  );
}

// ─── 2 · A corrente da sequência ─────────────────────────────────────────

/**
 * Um quadrado POR SIMULADO DO CICLO, nunca por dia da semana: não existe
 * atividade diária verificável no SAS (docs/26 §1). "N simulados sem faltar" —
 * e nunca "ofensiva", que é a palavra do Duolingo.
 */
function BlocoDaSequencia() {
  const { data: sequencia, isPending } = useSequencia();

  if (isPending) {
    return (
      <Bloco fonte="sequencia" olho="Sua sequência">
        <div className="alu-hoje__esqueleto" aria-hidden="true">
          <span className="alu-hoje__osso alu-hoje__osso--elos" />
          <span className="alu-hoje__osso alu-hoje__osso--curta" />
        </div>
      </Bloco>
    );
  }

  if (!sequencia) {
    return (
      <Bloco fonte="sequencia" olho="Sua sequência">
        <p className="alu-vazio">
          Sua sequência começa no próximo simulado — basta comparecer.
        </p>
      </Bloco>
    );
  }

  return (
    <Bloco fonte="sequencia" olho="Sua sequência">
      {/* 34px e não 22px como na lateral: aqui a corrente é a peça, e cada elo
          carrega o rótulo do simulado. */}
      <Corrente elos={sequencia.corrente} tamanho={34} />
      <LeituraDaSequencia simulados={sequencia.simulados} melhor={sequencia.melhor} />
    </Bloco>
  );
}

// ─── 3 · A contagem regressiva ───────────────────────────────────────────

/**
 * O gancho diário do produto inteiro, e o substituto da chama nervosa: a
 * urgência aqui é verdadeira e verificável — a data está no `evento_agenda` e o
 * e-mail da véspera já sai desde a Sprint 1 (docs/26 §2, docs/29 §A.1).
 */
function BlocoDaContagem() {
  const { data: proximo, isPending } = useProximoSimulado();

  return (
    <Bloco fonte="proximoSimulado" olho="Próximo simulado">
      {isPending ? (
        <div className="alu-hoje__esqueleto" aria-hidden="true">
          <span className="alu-hoje__osso alu-hoje__osso--numero" />
          <span className="alu-hoje__osso alu-hoje__osso--curta" />
        </div>
      ) : (
        <ContagemRegressiva proximo={proximo ?? null} />
      )}
    </Bloco>
  );
}

// ─── 4 · Onde você está ──────────────────────────────────────────────────

/**
 * ⚠️ Metade deste bloco é DADO REAL, e a divisão importa.
 *
 * O que não tem rota é o CORTE — a régua de `criterio_classificacao`, que só a
 * coordenação lê hoje (docs/29 §A.4). A NOTA de cada matéria tem: é o que
 * `GET /me/evolucao` já devolve, aluno contra turma, ciclo a ciclo. Mockar as
 * duas juntas esconderia uma integração que existe desde sempre, e o inventário
 * já diz que `evolucao` aparece nesta tela.
 *
 * Por isso a tarja do bloco continua SEM ROTA: o corte e a lista de matérias
 * ainda vêm de lá.
 */
function OndeVoceEsta() {
  const { data: cortes, isPending: cortesPendentes } = useMateriasContraCorte();
  const { data: evolucao, isPending: evolucaoPendente } = useEvolucao();

  const materias = notasContraCorte(cortes, evolucao);

  return (
    <Bloco fonte="cortePorMateria" olho="Onde você está">
      {cortesPendentes || evolucaoPendente ? (
        <div className="alu-hoje__esqueleto" aria-hidden="true">
          <span className="alu-hoje__osso alu-hoje__osso--grafico" />
        </div>
      ) : (
        <BarraCorte materias={materias} />
      )}
      <LeituraDaZona />
    </Bloco>
  );
}

/**
 * Junta o corte (sem-rota) com a nota real da evolução.
 *
 * Uma matéria sem nota na evolução SAI da lista em vez de cair no valor
 * sem-rota: mostrar ao aluno uma nota que ele não tirou é pior que mostrar uma
 * barra a menos. Quando a evolução inteira não veio — carregando, erro, ou
 * aluno sem nota nenhuma — o bloco volta para a lista sem-rota completa, que a
 * tarja já marca como tal.
 */
function notasContraCorte(
  cortes: MateriaContraCorte[] | undefined,
  evolucao: EvolucaoAluno | null | undefined,
): MateriaContraCorte[] {
  if (!cortes) return [];
  if (!evolucao) return cortes;

  return cortes.flatMap((materia) => {
    // A série é paralela a `ciclos` e traz `null` no ciclo em que não houve
    // prova daquela matéria; a nota que vale é a do ciclo mais recente que tem.
    const serie = evolucao.materias[materia.materia]?.aluno ?? [];
    const ultima = serie.reduce<number | null>((achada, n) => (n == null ? achada : n), null);
    return ultima == null ? [] : [{ ...materia, nota: ultima }];
  });
}

// Os rótulos de zona e o alvo da distância. É vocabulário de interface, e mora
// aqui porque a régua vem do servidor como enum — traduzir no componente é o
// que impede um `zona` novo de passar despercebido pelo TypeScript.
const ZONA_ROTULO: Record<Zona, string> = {
  top: 'Zona top',
  cinzenta: 'Zona cinzenta',
  risco: 'Zona de risco',
};

/** Para onde a distância aponta. `null` no top: não há próxima zona acima. */
const ALVO_DA_DISTANCIA: Record<Zona, string | null> = {
  risco: 'sair do risco',
  cinzenta: 'chegar ao top',
  top: null,
};

/**
 * A leitura da zona, logo abaixo das barras.
 *
 * ⚠️ REGRA DURA (docs/24 §2): o rótulo da zona NUNCA aparece sozinho — sempre
 * com a DISTÂNCIA e com o NOME DA RÉGUA que produziu o veredito. Um aluno lendo
 * "risco" sem saber contra qual corte e sem saber quanto falta recebe só a má
 * notícia, e não tem o que fazer com ela.
 *
 * E a zona NÃO é pintada de ALERTA. O papel ALERTA é reservado à etiqueta de
 * distância por matéria e ao valor abaixo do corte; um segundo vermelho aqui
 * recriaria o semáforo que o desenho inteiro existe para matar. Zona não
 * alcançada é VAZADA — contorno, como todo o resto que ainda não se conquistou.
 */
function LeituraDaZona() {
  const { data: zona, isPending } = useZona();

  if (isPending) {
    return (
      <div className="alu-hoje__zona">
        <span className="alu-hoje__osso alu-hoje__osso--curta" aria-hidden="true" />
      </div>
    );
  }

  if (!zona) {
    return (
      <div className="alu-hoje__zona">
        <p className="alu-vazio">
          Sua posição na régua aparece quando sair a nota do próximo simulado.
        </p>
      </div>
    );
  }

  const alvo = ALVO_DA_DISTANCIA[zona.zona];

  return (
    // `position: relative` no CSS desta div, e não só no bloco: sem isso a tarja
    // desta fonte se ancoraria no bloco inteiro e cairia por cima da tarja do
    // `cortePorMateria`. São duas fontes diferentes no mesmo bloco.
    <div className="alu-hoje__zona">
      <TarjaFonte chave="zonaEDistancia" />

      <p className="alu-hoje__zona-topo">
        <span className="alu-vazado alu-hoje__zona-chip">{ZONA_ROTULO[zona.zona]}</span>
        <span className="alu-hoje__zona-distancia">
          {alvo ? `faltam ${fmt(zona.distancia)}` : `${fmt(zona.distancia)} de folga`}
        </span>
      </p>

      <p className="alu-hoje__zona-frase">
        Sua média é <strong>{fmt(zona.media)}</strong> e o corte {alvo ? `para ${alvo}` : 'da zona'}{' '}
        é <strong>{fmt(zona.corteProximaZona)}</strong>, na régua <strong>{zona.regua}</strong>.
      </p>

      {zona.materiaMaisCurta && (
        <p className="alu-hoje__zona-frase">
          O caminho mais curto passa por <strong>{zona.materiaMaisCurta}</strong>.
        </p>
      )}
    </div>
  );
}

// ─── 5 · O que seu ciclo mostra ──────────────────────────────────────────

/**
 * Dado REAL — `GET /me/insight`.
 *
 * ⚠️ A primeira geração chama o LLM e demora segundos. A tela não espera por
 * ela: o bloco tem estado próprio de carregando, e o resto de Hoje já está
 * utilizável enquanto isso.
 */
function LeituraDoCiclo() {
  const { data: insight, isPending, isError, refetch } = useInsight();

  const bullets = insight?.bullets?.slice(0, 3) ?? [];

  if (isPending) {
    return (
      <Bloco fonte="insight" olho="O que seu ciclo mostra">
        <p className="alu-carregando">Analisando seu ciclo…</p>
      </Bloco>
    );
  }

  if (isError) {
    return (
      <Bloco fonte="insight" olho="O que seu ciclo mostra">
        <p className="alu-vazio">A leitura do seu ciclo não carregou.</p>
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
          onClick={() => refetch()}
        >
          Tentar de novo
        </button>
      </Bloco>
    );
  }

  if (!insight?.disponivel || bullets.length === 0) {
    return (
      <Bloco fonte="insight" olho="O que seu ciclo mostra">
        <p className="alu-vazio">
          A leitura sai quando o ciclo tiver nota suficiente para comparar. Até lá, treinar é o
          que muda o próximo resultado.
        </p>
        <Link className="alu-tecla alu-tecla--fantasma alu-tecla--pequena" to="/estudar">
          Treinar
        </Link>
      </Bloco>
    );
  }

  return (
    <Bloco fonte="insight" olho="O que seu ciclo mostra" acao={insight.cicloNome ?? undefined}>
      <ul className="alu-hoje__insights">
        {bullets.map((texto) => (
          <li key={texto} className="alu-hoje__insight">
            <span className="alu-hoje__marca" aria-hidden="true" />
            {texto}
          </li>
        ))}
      </ul>
    </Bloco>
  );
}

// ─── 6 · A tira da última nota ───────────────────────────────────────────

/**
 * Onde a nota vive agora: compacta, no rodapé, e como consequência do jogo —
 * não como o assunto da tela.
 *
 * Duas fontes REAIS: `useSimulados()` dá o mais recente e `useSimulado(id)` dá a
 * posição e o total daquele simulado. Nenhuma tarja, porque as duas já falam com
 * o servidor.
 */
function TiraDaUltimaNota() {
  const { data: simulados, isPending, isError, refetch } = useSimulados();

  // A rota já devolve do mais recente para o mais antigo e marca o primeiro com
  // `novo` (api/app/stats/aluno_dados.py). Procurar a marca em vez de confiar na
  // ordem é o que sobrevive a uma mudança de ordenação do lado do servidor.
  const ultimo = simulados?.find((s) => s.novo) ?? simulados?.[0];
  const { data: detalhe } = useSimulado(ultimo?.id);

  if (isPending) {
    return (
      <div className="alu-hoje__tira alu-hoje__tira--esqueleto" aria-hidden="true">
        <span className="alu-hoje__osso alu-hoje__osso--nota" />
        <span className="alu-hoje__osso alu-hoje__osso--linha" />
      </div>
    );
  }

  if (isError) {
    return (
      <Bloco olho="Última nota">
        <p className="alu-vazio">Sua última nota não carregou.</p>
        <button
          type="button"
          className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
          onClick={() => refetch()}
        >
          Tentar de novo
        </button>
      </Bloco>
    );
  }

  if (!ultimo) {
    return (
      <Bloco olho="Última nota">
        <p className="alu-vazio">
          Sua primeira nota aparece aqui quando o coordenador lançar os resultados.
        </p>
        <Link className="alu-tecla alu-tecla--fantasma alu-tecla--pequena" to="/estudar">
          Treinar enquanto isso
        </Link>
      </Bloco>
    );
  }

  const leitura = [
    fmtDataCurta(ultimo.dataAplicacao),
    detalhe && `${detalhe.posicao}º de ${detalhe.total}`,
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <Link to="/provas" className="alu-hoje__tira">
      <span className="alu-magnitude alu-hoje__tira-nota">{fmt(ultimo.nota)}</span>

      <span className="alu-hoje__tira-info">
        <span className="alu-olho alu-olho--quieto">Última nota</span>
        <span className="alu-hoje__tira-rotulo">{ultimo.rotulo ?? ultimo.nome ?? 'Simulado'}</span>
        <span className="alu-hoje__tira-leitura">{leitura}</span>
      </span>

      {/* Delta positivo em DADO; negativo fica QUIETO, nunca em ALERTA. Ficar
          abaixo do próprio padrão num simulado não é estar abaixo do corte, e
          ALERTA é reservado a esse. */}
      {ultimo.deltaSelf != null && (
        <span
          className={`alu-hoje__tira-delta${
            ultimo.deltaSelf >= 0 ? ' alu-hoje__tira-delta--acima' : ''
          }`}
        >
          {fmtDelta(ultimo.deltaSelf)}
          <span className="alu-so-leitor"> contra o seu próprio padrão</span>
        </span>
      )}

      <Icone nome="chevron" tamanho={18} />
      <span className="alu-so-leitor">Ver todas as provas</span>
    </Link>
  );
}
