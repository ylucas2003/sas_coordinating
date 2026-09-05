import { useState } from 'react';

import { AlertCard } from '../../componentes/ui/AlertCard';
import { useAlertas } from '../../hooks/consultas';
import { useReabrirAlerta, useResolverAlerta } from '../../hooks/mutacoes';

// A FAIXA DE DECISÃO — o que merece atenção hoje.
//
// É a promessa do CLAUDE.md ("sinaliza o que merece atenção em vez de esperar
// que o coordenador saiba o que procurar") e, desde a fase 2 do docs/39, é a
// ÚNICA coisa do Painel que não é porta: os três cards acima são atalhos para
// telas que existem noutro lugar; isto aqui não existe em lugar nenhum além
// daqui. A assimetria é o desenho.
//
// ⚠️ ELA SIMPLIFICOU, e a simplificação é consequência da tabela ter mudado de
// casa. Enquanto o Painel tinha faixa de filtros, a faixa respeitava o recorte
// da tela — senão diria "3 alunos em queda" sobre uma tabela de uma turma só —
// e era obrigada a avisar "+N fora do recorte atual", porque sumir com alerta
// em silêncio é número errado sem parecer errado. Sem filtros não há recorte:
// a faixa mostra tudo, e aquela linha de rodapé morreu junto com o motivo dela
// existir.
//
// ⚠️ E "Resolver" virou uma das DUAS coisas que se pode fazer nesta tela — a
// outra é entrar por uma porta. Antes era um botãozinho de texto no canto de
// um cartão, numa tela com 900 linhas editáveis embaixo. Resolver faz o alerta
// SUMIR, sem motivo e sem registro visível; por isso agora vem com desfazer à
// mão, enquanto a pessoa ainda está olhando.

/** Quantos cartões cabem antes de a faixa virar uma segunda tabela. */
const VISIVEIS_POR_PADRAO = 3;

export function FaixaDecisao({
  cortados,
  nomeCriterio,
  corte,
}: {
  /** Quantos alunos estão abaixo do corte no ciclo em foco. `null` = não sei. */
  cortados: number | null;
  nomeCriterio: string | null;
  /** O corte majoritário da régua em vigor, para a sparkline dos cartões (R2). */
  corte?: number;
}) {
  const { data: alertas = [] } = useAlertas();
  const resolver = useResolverAlerta();
  const reabrir = useReabrirAlerta();
  const [verTodos, setVerTodos] = useState(false);
  // O último resolvido, para o desfazer. Um só: desfazer é o gesto de quem
  // errou o clique agora, não um histórico — para histórico existe a auditoria.
  const [desfazivel, setDesfazivel] = useState<{ id: string; titulo: string } | null>(null);

  const mostrados = verTodos ? alertas : alertas.slice(0, VISIVEIS_POR_PADRAO);

  return (
    // A âncora que o sino da topbar prometia. O sino saiu na fase 1 — ele
    // apontava para cá, e "cá" virou praticamente a tela inteira.
    <section className="faixa-decisao" id="alertas">
      <div className="faixa-decisao__topo">
        <h2 className="faixa-decisao__titulo">O que merece atenção</h2>
        {nomeCriterio && <span className="faixa-decisao__regua">{`régua: ${nomeCriterio}`}</span>}
      </div>

      {/* ⚠️ A condição é sobre haver ALERTA, não sobre haver problema. Com a
          tabela embaixo, o caso "há cortados e nenhum alerta" nunca aparecia
          vazio. Sem ela, esta frase passa a ser o rodapé da tela — e caixa
          pálida vazia diz "aqui deveria ter algo" e quebra a leitura inteira.
          Aconteceu de verdade: um dia com 156 cortados e zero alertas. */}
      {alertas.length === 0 ? (
        <p className="faixa-decisao__vazio">
          {cortados == null
            ? 'Nada exigindo ação agora.'
            : cortados === 0
              ? 'Nada exigindo ação agora, e ninguém abaixo do corte no ciclo em andamento.'
              : `Nenhum alerta aberto. ${
                  cortados === 1
                    ? 'O aluno abaixo do corte está'
                    : `Os ${cortados} alunos abaixo do corte estão`
                } na tabela do ciclo, ordenados pelo pior.`}
        </p>
      ) : (
        <div className="faixa-decisao__alertas">
          {mostrados.map((a) => (
            <AlertCard
              key={a.id}
              alerta={a}
              corte={corte}
              onResolver={() => {
                resolver.mutate(a.id);
                setDesfazivel({ id: a.id, titulo: a.titulo });
              }}
            />
          ))}
        </div>
      )}

      {desfazivel && (
        <div className="faixa-decisao__desfazer" role="status">
          <span className="faixa-decisao__desfazer-texto">
            {`"${desfazivel.titulo}" saiu da lista.`}
          </span>
          <button
            type="button"
            className="faixa-decisao__desfazer-botao"
            disabled={reabrir.isPending}
            onClick={() => {
              reabrir.mutate(desfazivel.id);
              setDesfazivel(null);
            }}
          >
            Desfazer
          </button>
        </div>
      )}

      {alertas.length > VISIVEIS_POR_PADRAO && (
        <div className="faixa-decisao__rodape">
          <button
            type="button"
            className="faixa-decisao__mais"
            onClick={() => setVerTodos((v) => !v)}
          >
            {verTodos ? 'Mostrar menos' : `Ver os outros ${alertas.length - VISIVEIS_POR_PADRAO}`}
          </button>
        </div>
      )}
    </section>
  );
}
