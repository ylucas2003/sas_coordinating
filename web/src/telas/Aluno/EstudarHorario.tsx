import { useState } from 'react';

import { useProximoSimulado } from '../../dados/aluno';
import {
  agruparPorDia,
  diaIso,
  duracaoPorExtenso,
  fimDe,
  proximoBloco,
  totalDeMinutos,
} from '../../dominio/horarioEstudos';
import type { ProximoBloco, SecaoDoDia } from '../../dominio/horarioEstudos';
import { useAgora, useHorarioDeEstudos } from '../../hooks/horarioEstudos';
import type { BlocoDeEstudo } from '../../tipos/horarioEstudos';
import { CabecaDoCampo } from './pecas/CabecaDoCampo';
import { FolhaDoBloco } from './pecas/FolhaDoBloco';
import { Icone } from './pecas/Icone';
import { diasAte } from './pecas/formato';

// HORÁRIO DE ESTUDOS — a semana que o aluno monta sozinho (docs/42).
//
// A estrutura é a SEMANA EMPILHADA: os sete dias numa lista só, cada um uma
// seção, e todos os blocos à vista sem escolher dia. Era a segunda de quatro
// estruturas exploradas (docs/prompts-design-horario-de-estudos.md), e a que
// ganhou, porque montar uma rotina é olhar a semana inteira — e "dia a dia" a
// escondia atrás de um seletor.
//
// ⚠️ É UM PLANO, NUNCA UM REGISTRO. Nenhum bloco é riscado, apagado ou marcado
// quando o horário passa: sem check, sem "feito", sem barra de meta, sem XP. Tempo
// de estudo é autodeclarado e o SAS só premia o que verifica (docs/26 §1) — um
// bloco "cumprido" seria o primeiro passo para uma sequência de estudo, que o 26 §2
// fechou de propósito. Quem passou fica igual a quem não passou.
//
// ⚠️ NÃO É UMA GRADE 7×HORAS. "A área do aluno não deve ter tabela nenhuma"
// (docs/24 §7), e uma grade de planilha também não cabe em 390px.
//
// ⚠️ O VAZIO É O CASO COMUM, e é desenhado primeiro: a maioria abre esta tela com
// zero blocos. Ele ensina o gesto — "segunda a sexta, 19h, 1h30" — em vez de pedir
// desculpa por estar vazio. E FALHA DE CONSULTA NUNCA VIRA VAZIO: "Monte a sua
// semana" para quem montou doze blocos é a mentira mais cara desta tela.
//
// ⚠️ PRIVADO. Ninguém da coordenação lê isto, e a tela diz que é só do aluno.

interface EstadoDaFolha {
  /** `null` = bloco novo. */
  bloco: BlocoDeEstudo | null;
  dia: number;
}

export function EstudarHorario() {
  const horario = useHorarioDeEstudos();
  const agora = useAgora();
  const [folha, setFolha] = useState<EstadoDaFolha | null>(null);

  const blocos = horario.data?.blocos ?? [];
  const abrirNovo = (dia: number) => setFolha({ bloco: null, dia });
  const abrirEdicao = (bloco: BlocoDeEstudo) => setFolha({ bloco, dia: bloco.diaSemana });

  return (
    <>
      <CabecaDoCampo titulo="Horário de estudos" />

      {horario.isError ? (
        <Falha onTentar={() => void horario.refetch()} />
      ) : horario.isPending ? (
        <Esqueleto />
      ) : blocos.length === 0 ? (
        <Vazio agora={agora} onCriar={() => abrirNovo(diaIso(agora))} />
      ) : (
        <Semana
          blocos={blocos}
          agora={agora}
          onNovo={abrirNovo}
          onEditar={abrirEdicao}
        />
      )}

      {/* Montada só enquanto aberta: o estado do rascunho nasce limpo a cada
          abertura, sem um efeito para "resetar" — e o foco volta para quem abriu
          no desmonte (Folha.tsx). */}
      {folha && (
        <FolhaDoBloco
          bloco={folha.bloco}
          diaInicial={folha.dia}
          existentes={blocos}
          onFechar={() => setFolha(null)}
        />
      )}
    </>
  );
}

// ─── A semana ────────────────────────────────────────────────────────────

function Semana({
  blocos,
  agora,
  onNovo,
  onEditar,
}: {
  blocos: BlocoDeEstudo[];
  agora: Date;
  onNovo: (dia: number) => void;
  onEditar: (bloco: BlocoDeEstudo) => void;
}) {
  const secoes = agruparPorDia(blocos);
  const proximo = proximoBloco(blocos, agora);
  const hoje = diaIso(agora);

  return (
    <div className="alu-hor">
      <LinhaDeContexto blocos={blocos} />

      <div className="alu-hor__semana">
        {secoes.map((secao) => (
          <SecaoDoDiaDaSemana
            key={secao.dia.numero}
            secao={secao}
            ehHoje={secao.dia.numero === hoje}
            proximo={proximo}
            onNovo={onNovo}
            onEditar={onEditar}
          />
        ))}
      </div>

      {/* Colado na base da coluna: com sete seções a página é comprida, e o gesto
          mais frequente — criar um bloco — não pode ficar a seis telas de distância. */}
      <div className="alu-hor__acao">
        <button
          type="button"
          className="alu-tecla alu-tecla--larga"
          onClick={() => onNovo(hoje)}
        >
          Adicionar bloco
        </button>
      </div>
    </div>
  );
}

/**
 * Dois fatos quietos, um em cada ponta: o próximo simulado e o total da semana.
 *
 * É FATO AO LADO DE FATO, sem "você deveria estudar mais": a tela mostra o que o
 * aluno planejou e quanto falta para a prova, e a conta é dele. Sem barra e sem
 * meta — uma meta aqui seria a primeira mecânica de cobrança sobre um dado
 * autodeclarado.
 *
 * O simulado some quando não há (e `null` é comum: docs/36 §1.2); o total aparece
 * sempre que há ao menos um bloco, que é o único caso em que esta linha existe.
 */
function LinhaDeContexto({ blocos }: { blocos: BlocoDeEstudo[] }) {
  const { data: proximo } = useProximoSimulado();
  const dias = diasAte(proximo?.data);
  const simulado = proximo && dias != null && dias >= 0 ? fraseDoSimulado(proximo.rotulo, dias) : null;

  return (
    <p className="alu-hor__contexto">
      {simulado && <span>Próximo simulado: {simulado}</span>}
      <span className="alu-hor__contexto-total">
        Semana: {duracaoPorExtenso(totalDeMinutos(blocos))} planejadas
      </span>
    </p>
  );
}

function fraseDoSimulado(rotulo: string, dias: number): string {
  if (dias === 0) return `${rotulo}, hoje`;
  if (dias === 1) return `${rotulo}, amanhã`;
  return `${rotulo}, em ${dias} dias`;
}

function SecaoDoDiaDaSemana({
  secao,
  ehHoje,
  proximo,
  onNovo,
  onEditar,
}: {
  secao: SecaoDoDia;
  ehHoje: boolean;
  proximo: ProximoBloco | null;
  onNovo: (dia: number) => void;
  onEditar: (bloco: BlocoDeEstudo) => void;
}) {
  const { dia, blocos, totalMinutos } = secao;

  return (
    <section
      className={`alu-hor-dia${ehHoje ? ' alu-hor-dia--hoje' : ''}`}
      aria-label={dia.nome}
    >
      <header className="alu-hor-dia__topo">
        <h2 className="alu-hor-dia__nome">
          {ehHoje && <span className="alu-hor-dia__ponto" aria-hidden="true" />}
          <span>
            {dia.secao}
            {ehHoje && ' · HOJE'}
          </span>
        </h2>
        {totalMinutos > 0 && (
          <span className="alu-hor-dia__total">{duracaoPorExtenso(totalMinutos)}</span>
        )}
        <button
          type="button"
          className="alu-hor-mais"
          onClick={() => onNovo(dia.numero)}
          aria-label={`Adicionar bloco na ${dia.nome.toLowerCase()}`}
        >
          <Icone nome="mais" tamanho={18} />
        </button>
      </header>

      {blocos.length === 0 ? (
        // Vazio é VAZADO, e a linha inteira é a ação: o aluno que toca no dia sem
        // bloco quer pôr um bloco ali.
        <button type="button" className="alu-hor-vazio" onClick={() => onNovo(dia.numero)}>
          Sem bloco
        </button>
      ) : (
        <ul className="alu-hor-dia__lista">
          {blocos.map((bloco) => (
            <li key={bloco.id}>
              <CartaoDoBloco
                bloco={bloco}
                proximo={proximo?.bloco.id === bloco.id ? proximo : null}
                onEditar={onEditar}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function CartaoDoBloco({
  bloco,
  proximo,
  onEditar,
}: {
  bloco: BlocoDeEstudo;
  proximo: ProximoBloco | null;
  onEditar: (bloco: BlocoDeEstudo) => void;
}) {
  // Só UM bloco da semana leva a marca: o que vem a seguir, esteja em que dia
  // estiver. Os que já passaram hoje NÃO ficam apagados nem riscados (ver o topo).
  return (
    <button
      type="button"
      className={`alu-hor-bloco${proximo ? ' alu-hor-bloco--proximo' : ''}`}
      onClick={() => onEditar(bloco)}
      aria-label={`${bloco.rotulo}, ${bloco.horaInicio} às ${fimDe(bloco)}. Tocar para editar.`}
    >
      <span className="alu-hor-bloco__hora alu-magnitude">{bloco.horaInicio}</span>
      <span className="alu-hor-bloco__texto">
        <span className="alu-hor-bloco__rotulo">{bloco.rotulo}</span>
        <span className="alu-hor-bloco__detalhe">
          até {fimDe(bloco)} · {duracaoPorExtenso(bloco.duracaoMinutos)}
        </span>
      </span>
      {proximo && <span className="alu-olho alu-hor-bloco__marca">{marcaDoProximo(proximo)}</span>}
    </button>
  );
}

function marcaDoProximo(proximo: ProximoBloco): string {
  if (proximo.emAndamento) return 'Agora';
  if (proximo.minutosAte != null) return `Próximo · em ${duracaoPorExtenso(proximo.minutosAte)}`;
  return 'Próximo';
}

// ─── Os três outros estados ──────────────────────────────────────────────

const COLUNAS_DO_MOSAICO = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB', 'DOM'];
// Oito quadradinhos por coluna, com chave própria: o mosaico é decorativo e
// estático, mas índice como chave é o que o linter (com razão) não deixa passar.
const LINHAS_DO_MOSAICO = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];

/**
 * O vazio, que é o caso comum — e ENSINA o gesto.
 *
 * A semana vazia é desenhada como o mosaico de quadradinhos vazados: o mesmo
 * motivo da grade do fundo, onde "vazado" é o que ainda não foi preenchido. O
 * exemplo do texto ("segunda a sexta, 19h, 1h30") é exatamente o que a folha
 * cria de uma vez, e é por isso que ele está aqui e não um "comece agora".
 */
function Vazio({ agora, onCriar }: { agora: Date; onCriar: () => void }) {
  const hoje = diaIso(agora);
  return (
    <div className="alu-hor-vazio-tela">
      <div className="alu-hor-mosaico" aria-hidden="true">
        {COLUNAS_DO_MOSAICO.map((rotulo, i) => (
          <div key={rotulo} className="alu-hor-mosaico__coluna">
            <span
              className={`alu-hor-mosaico__rotulo${i + 1 === hoje ? ' alu-hor-mosaico__rotulo--hoje' : ''}`}
            >
              {rotulo}
            </span>
            {LINHAS_DO_MOSAICO.map((linha) => (
              <span key={linha} className="alu-hor-mosaico__quadrado" />
            ))}
          </div>
        ))}
      </div>

      <div className="alu-hor-vazio-tela__texto">
        <span className="alu-olho alu-olho--quieto">Sem blocos ainda</span>
        <h2 className="alu-hor-vazio-tela__titulo">Monte a sua semana de estudo</h2>
        <p className="alu-vazio">
          Escolha os dias, a hora e o que estudar. Por exemplo: segunda a sexta, 19h, 1h30.
        </p>
      </div>

      <button type="button" className="alu-tecla alu-tecla--larga" onClick={onCriar}>
        Criar o primeiro bloco
      </button>

      <p className="alu-hor-privado">
        <Icone nome="cadeado" tamanho={14} />
        Só você vê o seu horário.
      </p>
    </div>
  );
}

function Esqueleto() {
  return (
    <div className="alu-hor" aria-hidden="true">
      <div className="alu-hor__semana">
        {[0, 1, 2].map((i) => (
          <div key={i} className="alu-hor-osso">
            <span className="alu-hor-osso__linha alu-hor-osso__linha--curta" />
            <span className="alu-hor-osso__linha" />
          </div>
        ))}
      </div>
    </div>
  );
}

function Falha({ onTentar }: { onTentar: () => void }) {
  // ⚠️ Falha de consulta nunca vira estado vazio. O texto diz que o horário
  // continua gravado, porque a leitura que o aluno faz de "não carregou" é "perdi".
  return (
    <div className="alu-bloco">
      <p className="alu-erro">Não deu para carregar o seu horário agora.</p>
      <p className="alu-vazio">
        Isto é falha de conexão, não perda de blocos — o que você montou continua gravado no
        servidor.
      </p>
      <button type="button" className="alu-tecla alu-tecla--fantasma" onClick={onTentar}>
        Tentar de novo
      </button>
    </div>
  );
}
