import { NavLink, useParams } from 'react-router-dom';

import { type LinhaExtrato, useExtratoXp } from '../../dados/aluno';
import { Bloco } from './pecas/Bloco';
import { FichaXp, Icone } from './pecas/Icone';
import { fmtInteiro } from './pecas/formato';

// O EXTRATO DE XP — de onde vieram os pontos, item por item.
//
// É a única tela do produto que explica a RÉGUA DE CORTE sem parecer boletim:
// em vez de anunciar "você ficou abaixo em Química", ela mostra a linha que não
// pagou, ao lado das que pagaram, com o número que foi conferido. O aluno lê o
// que faltou em vez de ouvir o veredito.
//
// ⚠️ XP É DERIVADO DE NOTA, NUNCA SALDO GRAVADO (docs/26 §3, docs/29 §B.1).
// Nota é corrigida e simulado é anulado — a Sprint 2 inteira tratou disso. Se o
// XP for sempre recalculado a partir de `nota`, uma correção se propaga sozinha;
// se fosse saldo acumulado, cada correção viraria estorno manual. A única
// exceção prevista é o extrato de uma liga JÁ ENCERRADA, que congela para o
// pódio não mudar depois de anunciado.
//
// ⚠️ OS NÚMEROS SÃO PRIMEIRA CALIBRAÇÃO. Rodar a tabela de XP contra os 5
// ciclos reais de 2026 é PORTÃO, não desejável (docs/29 §H): nenhum jogo
// consegue testar o próprio balanceamento contra dado real antes do primeiro
// jogador entrar, e aqui dá. Nada desta tabela se fixa antes do backtest.
//
// ⚠️ O `:id` da rota EXISTE e não é usado para escolher o extrato: o mock tem um
// só. Filtrar por id aqui seria fingir uma seleção que não acontece — quando a
// fonte virar real, é `useExtratoXp(id)` que muda, não esta tela. O id serve ao
// caminho de volta, e só.

export function ExtratoXpTela() {
  const { id } = useParams<{ id: string }>();
  const extrato = useExtratoXp();
  const voltarPara = id ? `/provas/${id}` : '/provas';

  if (extrato.isPending) {
    return (
      <div className="alu-provas">
        <Voltar para={voltarPara} />
        <div className="alu-bloco">
          <div className="alu-provas__esqueleto" style={{ height: 14, width: '45%' }} />
          <div className="alu-provas__esqueleto" style={{ height: 64, width: '50%' }} />
          <div className="alu-provas__esqueleto" style={{ height: 180 }} />
        </div>
      </div>
    );
  }

  if (extrato.isError || !extrato.data) {
    return (
      <div className="alu-provas">
        <Voltar para={voltarPara} />
        <Bloco fonte="extratoXp">
          <p className="alu-vazio">Não deu para montar o seu extrato agora.</p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma"
            onClick={() => extrato.refetch()}
          >
            Tentar de novo
          </button>
        </Bloco>
      </div>
    );
  }

  const dados = extrato.data;
  const pagaram = dados.linhas.filter((l) => l.xp > 0).length;

  return (
    <div className="alu-provas alu-extrato">
      <Voltar para={voltarPara} />

      <Bloco fonte="extratoXp" olho="Extrato de XP" className="alu-extrato__cabecalho">
        <p className="alu-extrato__simulado">{dados.simuladoNome}</p>
        <p className="alu-extrato__total">
          <FichaXp tamanho={34} />
          <strong className="alu-magnitude alu-extrato__total-numero">
            {fmtInteiro(dados.total)}
          </strong>
          <span className="alu-extrato__unidade">XP</span>
        </p>
        <p className="alu-extrato__resumo">
          {pagaram} de {dados.linhas.length} critérios pagaram. Cada linha mostra o que foi
          conferido.
        </p>
      </Bloco>

      {dados.linhas.length === 0 ? (
        <Bloco fonte="extratoXp">
          <p className="alu-vazio">
            Este simulado ainda não gerou pontos. Comparecer ao próximo já vale — é a única linha
            que não depende de nota.
          </p>
        </Bloco>
      ) : (
        <Bloco fonte="extratoXp" olho="Linha por linha">
          {/* AS LINHAS COM +0 NUNCA SOMEM. É onde o aluno entende o que faltou;
              esconder as que não pagaram transformaria o extrato num placar, e
              o placar ele já tem na ficha. */}
          <ol className="alu-extrato__linhas">
            {dados.linhas.map((linha) => (
              <Linha key={linha.rotulo} linha={linha} />
            ))}
          </ol>
        </Bloco>
      )}

      <Bloco fonte="extratoXp" olho="No total">
        <p className="alu-extrato__fecho">
          <span className="alu-extrato__fecho-rotulo">Total do simulado</span>
          <strong className="alu-magnitude alu-extrato__fecho-valor">
            +{fmtInteiro(dados.total)}
          </strong>
        </p>

        {dados.posicaoLiga != null ? (
          <>
            {/* A liga é por CICLO, nunca por semana: o XP só se move quando sai
                nota (docs/26 §5.1). Dizer "termina com o ciclo" é o que impede
                o aluno de esperar movimento numa terça-feira. */}
            <p className="alu-extrato__liga">
              Com estes pontos você está em{' '}
              <strong>{fmtInteiro(dados.posicaoLiga)}º</strong> na liga deste ciclo.
            </p>
            <NavLink className="alu-tecla alu-tecla--valor" to="/liga">
              Ver a liga
            </NavLink>
          </>
        ) : (
          <p className="alu-vazio">
            A sua posição na liga entra quando o ciclo tiver todas as notas lançadas.
          </p>
        )}
      </Bloco>
    </div>
  );
}

/**
 * Uma linha do extrato.
 *
 * A que não pontuou é VAZADA e mostra +0 em texto quieto — vazio é vazado
 * (docs/24 §7.1, regra 2). O ouro é `--alu-valor-texto`, e nunca `--alu-valor`:
 * ouro puro reprova em contraste como letra sobre fundo claro.
 */
function Linha({ linha }: { linha: LinhaExtrato }) {
  const pagou = linha.xp > 0;

  return (
    <li className={`alu-extrato__linha${pagou ? '' : ' alu-extrato__linha--vazia'}`}>
      <span className="alu-extrato__linha-texto">
        <span className="alu-extrato__rotulo">{linha.rotulo}</span>
        <span className="alu-extrato__evidencia">{linha.evidencia}</span>
      </span>
      <span className={`alu-extrato__xp${pagou ? '' : ' is-zerado'}`}>
        +{fmtInteiro(linha.xp)}
      </span>
    </li>
  );
}

function Voltar({ para }: { para: string }) {
  return (
    <NavLink className="alu-provas__voltar" to={para}>
      <Icone nome="voltar" tamanho={16} />
      Voltar para a prova
    </NavLink>
  );
}
