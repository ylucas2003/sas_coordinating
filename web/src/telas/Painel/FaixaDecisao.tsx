import { useState } from 'react';

import { AlertCard } from '../../componentes/ui/AlertCard';
import { alertasDoRecorte, contarDecisoes } from '../../dominio/painel';
import type { ClassificacaoPorAluno } from '../../dominio/painel';
import { useAlertas } from '../../hooks/consultas';
import { useResolverAlerta } from '../../hooks/mutacoes';
import type { Aluno } from '../../tipos/dominio';

// A faixa de decisão — o que merece atenção hoje, acima da tabela.
//
// É a promessa do CLAUDE.md ("sinaliza o que merece atenção em vez de esperar
// que o coordenador saiba o que procurar") chegando à tela pela primeira vez.
// O motor de 7 regras existe desde a Sprint 1, `GET /alertas` responde,
// `useAlertas` está escrito e `AlertCard.tsx` estava lá, comentado como
// "componente central do Painel" — **importado por ninguém**. O sino da topbar
// apontava para `/painel#alertas`, âncora que não existia (docs/33 §0.2).
//
// ⚠️ A tabela FICA. Cartão é para decidir, tabela é para comparar, e a maioria
// das telas de coordenação é de comparação — o Painel é a tela de varrer 900
// pessoas, e cartão não compara 900 linhas (docs/25 §2). Esta faixa não
// substitui nada; ela responde a pergunta que a tabela não responde.

/** Quantos cartões cabem antes de a faixa virar uma segunda tabela. */
const VISIVEIS_POR_PADRAO = 3;

export function FaixaDecisao({
  alunosNoRecorte,
  classificacao,
  recorteAtivo,
  nomeCriterio,
}: {
  /** Os alunos que a tabela abaixo está mostrando — sede, turma e busca já aplicados. */
  alunosNoRecorte: readonly Aluno[];
  classificacao: ClassificacaoPorAluno;
  recorteAtivo: boolean;
  nomeCriterio: string | null;
}) {
  const { data: alertas = [] } = useAlertas();
  const resolver = useResolverAlerta();
  const [verTodos, setVerTodos] = useState(false);

  const contagem = contarDecisoes(alunosNoRecorte, classificacao);
  // Os NÚMEROS desta faixa subiram para a fileira de KPIs: eles e os KPIs
  // diziam a mesma coisa em duas alturas, e o olho passava por quatro estratos
  // antes de chegar à tabela. O que sobra aqui é o que a tabela não responde —
  // os cartões de alerta. A contagem continua sendo lida para decidir se há
  // algo a mostrar.
  const { visiveis, ocultos } = alertasDoRecorte(alertas, alunosNoRecorte, recorteAtivo);
  const mostrados = verTodos ? visiveis : visiveis.slice(0, VISIVEIS_POR_PADRAO);

  const semNada = contagem.cortados === 0 && contagem.noLimite === 0 && visiveis.length === 0;

  return (
    // A âncora que o sino da topbar promete há tempo.
    <section className="faixa-decisao" id="alertas">
      <div className="faixa-decisao__topo">
        <h2 className="faixa-decisao__titulo">O que merece atenção</h2>
        {nomeCriterio && <span className="faixa-decisao__regua">{`régua: ${nomeCriterio}`}</span>}
      </div>

      {/* ⚠️ A condição é sobre haver ALERTA, não sobre haver problema.
          Enquanto os números de cortados viviam aqui, eles preenchiam o
          cartão e o caso "há cortados mas nenhum alerta" nunca aparecia
          vazio. Quando os números subiram para os KPIs, esse caso virou uma
          caixa pálida sem nada dentro — que é como a tela estava em
          05/09/2026, com 156 cortados e zero alertas.

          Um cartão vazio não é neutro: ele diz "aqui deveria ter algo" e
          quebra a leitura da tela inteira. */}
      {visiveis.length === 0 ? (
        <p className="faixa-decisao__vazio">
          {semNada
            ? 'Nada exigindo ação neste recorte. A tabela abaixo continua sendo o lugar de comparar.'
            : `Nenhum alerta aberto neste recorte. ${
                contagem.cortados === 1
                  ? 'O aluno abaixo do corte está'
                  : `Os ${contagem.cortados} alunos abaixo do corte estão`
              } na tabela, ordenados pelo pior.`}
        </p>
      ) : (
        <div className="faixa-decisao__alertas">
          {mostrados.map((a) => (
            <AlertCard
              key={a.id}
              alerta={a}
              onResolver={() => resolver.mutate(a.id)}
            />
          ))}
        </div>
      )}

      <div className="faixa-decisao__rodape">
        {visiveis.length > VISIVEIS_POR_PADRAO && (
          <button className="faixa-decisao__mais" onClick={() => setVerTodos((v) => !v)}>
            {verTodos
              ? 'Mostrar menos'
              : `Ver os outros ${visiveis.length - VISIVEIS_POR_PADRAO}`}
          </button>
        )}
        {/* ⚠️ Nunca esconder em silêncio. A faixa respeita o recorte da tela —
            senão diria "3 alunos em queda" sobre uma tabela de uma turma só —,
            mas some com alerta sem avisar seria a armadilha 2 do CLAUDE.md
            noutra roupa: número errado sem parecer errado. */}
        {ocultos > 0 && (
          <span className="faixa-decisao__ocultos">
            {`+${ocultos} fora do recorte atual`}
          </span>
        )}
      </div>
    </section>
  );
}

