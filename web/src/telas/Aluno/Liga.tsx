import { Fragment } from 'react';
import { NavLink } from 'react-router-dom';

import { useLiga } from '../../dados/aluno';
import { Escudo, Situacao } from './Jornada';
import { Bloco } from './pecas/Bloco';
import { Glifo } from './pecas/Glifo';
import { Icone } from './pecas/Icone';
import { fmtInteiro } from './pecas/formato';

// A LIGA — alcançada pelo cartão da Jornada, e não é uma aba.
//
// ⚠️ ESTA TELA INTEIRA DEPENDE DE UMA DECISÃO DE COORDENAÇÃO AINDA ABERTA:
// "gamificação pode ser competitiva?" (docs/24 §9.1). Ela está construída
// porque o desenho precisa existir para a decisão ser tomada com algo na mão —
// não porque a decisão foi tomada. Se a resposta for não, é esta rota que sai,
// e nada mais do jogo cai junto: a liga é aditiva (docs/26 §5.3).
//
// ⚠️ E OS GRUPOS TÊM DE CRUZAR TURMA E SEDE (docs/26 §5.1). Com ~900 alunos são
// ~30 grupos de ~30; se um grupo coincidir com uma turma, o anonimato cai por
// dedução — os colegas se conhecem, sabem quem faltou e quem foi bem, e o glifo
// vira um nome em duas conversas. A regra é do agrupamento no servidor; esta
// tela não tem como consertar isso depois.
//
// A liga é POR CICLO, nunca por semana: o XP só se move quando sai nota
// (docs/26 §5.1). Nada nesta tela pode dizer "termina em 2 dias".
//
// ANÔNIMA: nenhum nome, nenhuma inicial, nenhum apelido. Cada participante é um
// glifo geométrico vindo do servidor como rótulo opaco. É restrição de
// privacidade de menor, não estética.

export function LigaTela() {
  const liga = useLiga();

  return (
    <>
      <NavLink className="alu-liga-voltar" to="/jornada">
        <Icone nome="voltar" tamanho={18} />
        Jornada
      </NavLink>

      <Bloco fonte="liga">
        <Situacao consulta={liga} />

        {liga.data && (
          <>
            <div className="alu-liga-topo">
              <Escudo tamanho={54} />
              <div className="alu-liga-topo__texto">
                <h1 className="alu-liga-topo__nome">{liga.data.nome}</h1>
                <span className="alu-olho alu-olho--quieto">
                  Termina com o ciclo · {liga.data.participantes} participantes
                </span>
              </div>
            </div>

            {liga.data.faltaParaSubir != null && (
              <p className="alu-liga-rodape">
                Faltam {fmtInteiro(liga.data.faltaParaSubir)} XP para entrar na zona de subida.
              </p>
            )}

            {!liga.data.posicoes.length ? (
              <p className="alu-vazio">
                Sua liga é montada quando o ciclo abre. O XP do próximo simulado já conta.
              </p>
            ) : (
              <TabelaDaLiga
                posicoes={liga.data.posicoes}
                sobem={liga.data.sobem}
                descem={liga.data.descem}
                participantes={liga.data.participantes}
              />
            )}

            <p className="alu-liga-rodape">
              Sobem os {liga.data.sobem} primeiros e descem os {liga.data.descem} últimos. Quando o
              ciclo fecha, o XP zera e os grupos são refeitos.
            </p>
            <p className="alu-liga-aviso">
              O XP só se move quando sai nota de simulado — treinar não muda a sua posição aqui.
            </p>
          </>
        )}
      </Bloco>
    </>
  );
}

interface PropsTabela {
  posicoes: Array<{ posicao: number; glifo: string; xpCiclo: number; euMesmo: boolean }>;
  sobem: number;
  descem: number;
  participantes: number;
}

function TabelaDaLiga({ posicoes, sobem, descem, participantes }: PropsTabela) {
  // A primeira posição que já está caindo. Ela é contada do FIM do grupo, e o
  // grupo é maior que a lista mostrada — por isso costuma cair fora dela, e por
  // isso existe a quebra no fim.
  const inicioDaDescida = participantes - descem + 1;
  const ultima = posicoes[posicoes.length - 1]?.posicao ?? 0;

  return (
    <ol className="alu-liga-tabela">
      {posicoes.map((p) => (
        <Fragment key={p.posicao}>
          {/* O `> sobem` evita o absurdo de um grupo tão pequeno que as duas
              zonas se encavalam e o fio de descida nasce antes do de subida. */}
          {p.posicao === inicioDaDescida && inicioDaDescida > sobem && (
            <li className="alu-liga-fio alu-liga-fio--desce">Descem</li>
          )}

          <li className={`alu-liga-linha${p.euMesmo ? ' alu-liga-linha--eu' : ''}`}>
            <span className="alu-liga-linha__posicao">{p.posicao}º</span>
            <span className="alu-liga-linha__marca">
              <Glifo forma={p.glifo} tamanho={22} destacado={p.euMesmo} />
            </span>
            {/* ⚠️ Esta coluna nunca recebe nome, inicial ou apelido. A única
                palavra que aparece aqui é "VOCÊ", e só na própria linha. */}
            <span className="alu-liga-linha__rotulo">{p.euMesmo ? 'Você' : ''}</span>
            <span className="alu-liga-linha__xp">{fmtInteiro(p.xpCiclo)} XP</span>
          </li>

          {p.posicao === sobem && posicoes.length > sobem && (
            <li className="alu-liga-fio alu-liga-fio--sobe">Sobem</li>
          )}
        </Fragment>
      ))}

      {/* A lista mostra o topo do grupo; a zona de descida costuma ficar fora
          dela. Sem esta quebra o rodapé falaria de uma zona que não se vê. */}
      {ultima < inicioDaDescida && (
        <li className="alu-liga-quebra">
          até o {participantes}º · descem os {descem} últimos
        </li>
      )}
    </ol>
  );
}
