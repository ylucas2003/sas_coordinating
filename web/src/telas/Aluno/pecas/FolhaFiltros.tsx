import { useState } from 'react';
import type { ReactNode } from 'react';

import { alternarAno, anosMarcados } from '../../../dominio/banco';
import { useQuestoesDoBanco, useTaxonomia } from '../../../dados/aluno';
import type { ColecaoBanco, FiltrosBanco, TaxonomiaMateria } from '../../../dados/aluno';
import { Folha } from './Folha';
import { fmtInteiro } from './formato';

// Os filtros do acervo — matéria, vestibular, fase, ano e assunto.
//
// UM corpo, DUAS cascas, e a diferença entre elas é de semântica, não de
// aparência:
//
//   FolhaFiltros    celular. Sobe do rodapé, guarda RASCUNHO e só aplica no
//                   "Ver N questões". Sem rascunho, cada toque recarregaria a
//                   lista atrás da folha — que nem está visível.
//   PainelDeFiltros desktop. Coluna fixa à esquerda, SEM rascunho: a lista está
//                   ao lado e visível, então o toque aplica na hora e o
//                   resultado é a resposta. Um botão "aplicar" aqui seria um
//                   passo a mais para ver o que já dava para ver.
//
// No celular filtro NUNCA é coluna lateral (docs/28 §4): a `FiltrosBanco` da
// coordenação é um `<aside>` de 280px, e aqui não há 280px sobrando.
//
// ⚠️ A REGRA QUE ESTA FOLHA EXISTE PARA CUMPRIR (docs/28 §6): filtrar por
// tópico EXIGE matéria. `1.1` é "Fundamentos" em Física, "Conjuntos e Lógica"
// em Matemática e "Estrutura Atômica" em Química — a chave do tópico é
// (matéria, código), nunca o código sozinho. A rota devolve 400 na combinação,
// e é justamente por isso que a interface tem de IMPEDIR o toque em vez de
// deixar o erro chegar: sem o 400 o aluno receberia um recorte errado sem erro
// nenhum na tela.

/** O que o pai não consegue rotular sozinho sem baixar a taxonomia inteira. */
export interface RotulosDeFiltro {
  /** "Termodinâmica" — o nome do tópico, que só a árvore do edital sabe. */
  topico?: string;
}

interface Props {
  /** Os filtros já aplicados. A busca não entra: ela mora no campo da tela. */
  filtros: FiltrosBanco;
  rotulos: RotulosDeFiltro;
  /** A busca corrente, para o "VER N QUESTÕES" contar o recorte de verdade. */
  busca: string;
  /**
   * A coleção em vigor. Entra na CONTAGEM do rodapé, e não nas pílulas.
   *
   * ⚠️ Sem ela o rodapé prometia "Ver 320 questões" e a tela mostrava 240:
   * a folha contava sobre o acervo inteiro enquanto a lista atrás dela já
   * estava restrita ao Arquivo. Um número que não é o que se vai ver é pior
   * que nenhum número — é o botão mentindo sobre o próprio destino.
   */
  colecao?: ColecaoBanco;
  onFechar: () => void;
  onAplicar: (filtros: FiltrosBanco, rotulos: RotulosDeFiltro) => void;
}

/**
 * O tópico do edital, derivado da árvore em vez de importado.
 *
 * `contratos.ts` reexporta `TaxonomiaMateria` mas não `TopicoTaxonomia`, e
 * `dados/aluno/` não é arquivo desta tela — derivar mantém o tipo amarrado à
 * mesma fonte sem tocar na camada de dado.
 */
type TopicoDoEdital = TaxonomiaMateria['blocos'][number]['topicos'][number];

function unicos<T>(valores: T[]): T[] {
  return [...new Set(valores)];
}

interface PropsDoCorpo {
  /** O recorte que as pílulas refletem — rascunho na folha, aplicado no painel. */
  recorte: FiltrosBanco;
  /** Troca uma chave de escolha única. `undefined` no valor limpa. */
  aoAlternar: <C extends keyof FiltrosBanco>(chave: C, valor: FiltrosBanco[C]) => void;
  /** O ano é o único grupo de MÚLTIPLA escolha, e por isso tem caminho próprio:
   *  o toggle dele não é "troca o valor", é "acrescenta ou tira da lista". */
  aoAlternarAno: (ano: number, disponiveis: readonly number[]) => void;
  /** O nome do tópico escolhido, que só a árvore do edital sabe. */
  aoEscolherTopico: (codigo: string, nome: string, jaEstava: boolean) => void;
}

/**
 * Os grupos de pílula. Sem casca e sem estado próprio: quem guarda o recorte é
 * o pai, porque é o pai que sabe se ele é rascunho ou já é o recorte da tela.
 */
export function CorpoDeFiltros({
  recorte,
  aoAlternar,
  aoAlternarAno,
  aoEscolherTopico,
}: PropsDoCorpo) {
  // Uma consulta só, sem matéria: devolve as três árvores de uma vez, e com
  // elas os anos, as fases e os vestibulares que existem no acervo.
  const taxonomia = useTaxonomia();

  const arvores = taxonomia.data ?? [];
  const daMateria = arvores.find((a) => a.materia === recorte.materia) ?? null;
  // Escolhida a matéria, os anos e as fases passam a ser os DELA: o IME
  // objetivo não tem os mesmos anos em todas as matérias, e oferecer um ano
  // que devolve lista vazia é oferecer um beco.
  const escopo = daMateria ? [daMateria] : arvores;

  const materias = arvores.map((a) => a.materia);
  const vestibulares = unicos(escopo.flatMap((a) => a.vestibulares));
  const fases = unicos(escopo.flatMap((a) => a.fases)).sort((a, b) => a - b);
  const anos = unicos(escopo.flatMap((a) => a.anos)).sort((a, b) => b - a);
  const topicos: TopicoDoEdital[] = daMateria
    ? daMateria.blocos.flatMap((b) => b.topicos)
    : [];

  return (
    <>
      {taxonomia.isPending && <p className="alu-carregando">Carregando os filtros…</p>}

      {taxonomia.isError && (
        <div className="alu-filtros__erro">
          <p className="alu-erro">Não deu para carregar os filtros.</p>
          <button
            type="button"
            className="alu-tecla alu-tecla--fantasma alu-tecla--pequena"
            onClick={() => {
              taxonomia.refetch();
            }}
          >
            Tentar de novo
          </button>
        </div>
      )}

      {taxonomia.isSuccess && (
        <>
          <Grupo legenda="Matéria">
            {materias.map((m) => (
              <Pilula
                key={m}
                rotulo={m}
                ativa={recorte.materia === m}
                onToque={() => aoAlternar('materia', m)}
              />
            ))}
          </Grupo>

          <Grupo legenda="Vestibular">
            {vestibulares.map((v) => (
              <Pilula
                key={v}
                rotulo={v}
                ativa={recorte.vestibular === v}
                onToque={() => aoAlternar('vestibular', v)}
              />
            ))}
          </Grupo>

          <Grupo legenda="Fase">
            {fases.map((f) => (
              <Pilula
                key={f}
                rotulo={`Fase ${f}`}
                ativa={recorte.fase === f}
                onToque={() => aoAlternar('fase', f)}
              />
            ))}
          </Grupo>

          {/* ⚠️ O ÚNICO grupo de múltipla escolha, e o único que abre com TUDO
              marcado (decisão de 02/09). "Sem filtro" e "todos os anos" são o
              mesmo recorte, e mostrá-lo apagado diria ao aluno que nada está
              selecionado — quando tudo está. Quem traduz é `anosMarcados`. */}
          <Grupo legenda="Ano">
            {anos.map((a) => (
              <Pilula
                key={a}
                rotulo={String(a)}
                ativa={anosMarcados(recorte.anos, anos).has(a)}
                onToque={() => aoAlternarAno(a, anos)}
              />
            ))}
          </Grupo>

          {/* `disabled` no `fieldset` e não só nos botões: é o que faz o
              teclado e o leitor de tela pularem o grupo inteiro, em vez de
              anunciarem trinta pílulas que não respondem. */}
          <fieldset className="alu-filtros__grupo" disabled={!recorte.materia}>
            <legend className="alu-filtros__legenda">Assunto</legend>

            {!recorte.materia ? (
              <p className="alu-filtros__aviso">
                Escolha uma matéria primeiro — o mesmo código de assunto existe nas três e
                significa coisa diferente em cada uma.
              </p>
            ) : topicos.length === 0 ? (
              <p className="alu-filtros__aviso">
                Esta matéria ainda não tem assunto classificado no edital.
              </p>
            ) : (
              <div className="alu-filtros__opcoes">
                {topicos.map((t) => (
                  <Pilula
                    key={t.codigo}
                    rotulo={`${t.nome} · ${t.totalQuestoes}`}
                    ativa={recorte.topico === t.codigo}
                    onToque={() =>
                      aoEscolherTopico(t.codigo, t.nome, recorte.topico === t.codigo)
                    }
                  />
                ))}
              </div>
            )}
          </fieldset>
        </>
      )}
    </>
  );
}

interface PropsDoPainel {
  filtros: FiltrosBanco;
  onAplicar: (filtros: FiltrosBanco, rotulos: RotulosDeFiltro) => void;
}

/**
 * A coluna fixa do desktop. Aplica na hora — a lista está ao lado.
 *
 * Sem rascunho e sem "aplicar": o resultado do toque é visível no mesmo
 * movimento do olho, então um botão de confirmação seria um passo a mais para
 * ver o que já estava à vista. O "Limpar" continua, porque desfazer cinco
 * pílulas uma a uma não é desfazer.
 */
export function PainelDeFiltros({ filtros, onAplicar }: PropsDoPainel) {
  const algumAtivo = Object.keys(filtros).length > 0;

  function alternar<C extends keyof FiltrosBanco>(chave: C, valor: FiltrosBanco[C]) {
    const novo: FiltrosBanco = { ...filtros };
    if (filtros[chave] === valor) delete novo[chave];
    else novo[chave] = valor;
    // Trocar ou limpar a matéria limpa o tópico junto — ver o ⚠️ do topo.
    if (chave === 'materia') delete novo.topico;
    onAplicar(novo, {});
  }

  return (
    <aside className="alu-painel-filtros">
      <div className="alu-painel-filtros__cabeca">
        <h2 className="alu-painel-filtros__titulo">Filtros</h2>
        {algumAtivo && (
          <button
            type="button"
            className="alu-filtros__limpar"
            onClick={() => onAplicar({}, {})}
          >
            Limpar
          </button>
        )}
      </div>

      <CorpoDeFiltros
        recorte={filtros}
        aoAlternar={alternar}
        aoAlternarAno={(ano, disponiveis) =>
          onAplicar({ ...filtros, anos: alternarAno(filtros.anos, disponiveis, ano) }, {})
        }
        aoEscolherTopico={(codigo, nome, jaEstava) => {
          const novo: FiltrosBanco = { ...filtros };
          if (jaEstava) delete novo.topico;
          else novo.topico = codigo;
          onAplicar(novo, jaEstava ? {} : { topico: nome });
        }}
      />
    </aside>
  );
}

export function FolhaFiltros({ filtros, rotulos, busca, colecao, onFechar, onAplicar }: Props) {
  // Rascunho local: as pílulas mudam o recorte na hora, mas a lista só troca
  // quando o aluno confirma no rodapé. Sem isso, cada toque recarregaria a
  // lista atrás da folha — e ela nem está visível.
  const [rascunho, setRascunho] = useState<FiltrosBanco>(filtros);
  const [rotuloTopico, setRotuloTopico] = useState<string | null>(rotulos.topico ?? null);

  // A contagem do rodapé é o recorte DE VERDADE, pedido ao servidor com
  // `porPagina: 1`: só o `total` interessa, e trazer 20 questões que ninguém
  // vai ver para mostrar um número seria pagar a página duas vezes.
  const contagem = useQuestoesDoBanco({
    ...rascunho,
    colecao,
    busca: busca.trim() || undefined,
    pagina: 1,
    porPagina: 1,
  });

  function alternar<C extends keyof FiltrosBanco>(chave: C, valor: FiltrosBanco[C]) {
    setRascunho((atual) => {
      const novo: FiltrosBanco = { ...atual };
      if (atual[chave] === valor) delete novo[chave];
      else novo[chave] = valor;
      // Trocar ou limpar a matéria limpa o tópico junto — ver o ⚠️ do topo.
      // O código sobrevivente apontaria para outro assunto em silêncio.
      if (chave === 'materia') delete novo.topico;
      return novo;
    });
    if (chave === 'materia') setRotuloTopico(null);
  }

  function limpar() {
    setRascunho({});
    setRotuloTopico(null);
  }

  const total = contagem.data?.total ?? 0;
  const algumAtivo = Object.keys(rascunho).length > 0;

  return (
    <Folha
      aberta
      titulo="Filtrar"
      subtitulo="o acervo do ITA e do IME"
      altura="cheio"
      onFechar={onFechar}
      acoes={
        algumAtivo && (
          <button type="button" className="alu-filtros__limpar" onClick={limpar}>
            Limpar
          </button>
        )
      }
      rodape={
        <button
          type="button"
          className="alu-tecla alu-tecla--larga"
          disabled={contagem.isPending}
          onClick={() =>
            onAplicar(rascunho, rotuloTopico ? { topico: rotuloTopico } : {})
          }
        >
          {contagem.isPending
            ? 'Contando…'
            : `Ver ${fmtInteiro(total)} ${total === 1 ? 'questão' : 'questões'}`}
        </button>
      }
    >
      <CorpoDeFiltros
        recorte={rascunho}
        aoAlternar={alternar}
        aoAlternarAno={(ano, disponiveis) =>
          setRascunho((atual) => ({ ...atual, anos: alternarAno(atual.anos, disponiveis, ano) }))
        }
        aoEscolherTopico={(codigo, nome, jaEstava) => {
          alternar('topico', codigo);
          setRotuloTopico(jaEstava ? null : nome);
        }}
      />
    </Folha>
  );
}

function Grupo({ legenda, children }: { legenda: string; children: ReactNode }) {
  return (
    <fieldset className="alu-filtros__grupo">
      <legend className="alu-filtros__legenda">{legenda}</legend>
      <div className="alu-filtros__opcoes">{children}</div>
    </fieldset>
  );
}

/**
 * Uma pílula de filtro. É seleção única por grupo porque `FiltrosBanco` é
 * assim: a rota recebe `materia=Física`, não uma lista. Tocar a ativa
 * desmarca — é o "voltar atrás" sem um botão a mais na tela.
 */
function Pilula({
  rotulo,
  ativa,
  onToque,
}: {
  rotulo: string;
  ativa: boolean;
  onToque: () => void;
}) {
  return (
    <button
      type="button"
      className={`alu-filtros__pilula${ativa ? ' is-ativa' : ''}`}
      aria-pressed={ativa}
      onClick={onToque}
    >
      {rotulo}
    </button>
  );
}
