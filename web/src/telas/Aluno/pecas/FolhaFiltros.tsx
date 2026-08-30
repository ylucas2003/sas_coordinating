import { useState } from 'react';
import type { ReactNode } from 'react';

import { useQuestoesDoBanco, useTaxonomia } from '../../../dados/aluno';
import type { FiltrosBanco, TaxonomiaMateria } from '../../../dados/aluno';
import { Folha } from './Folha';
import { fmtInteiro } from './formato';

// A folha de filtros do acervo — matéria, vestibular, fase, ano e assunto.
//
// No celular filtro NUNCA é coluna lateral (docs/28 §4): a `FiltrosBanco` da
// coordenação é um `<aside>` de 280px, e aqui não há 280px sobrando. A mesma
// capacidade sobe do rodapé.
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

export function FolhaFiltros({ filtros, rotulos, busca, onFechar, onAplicar }: Props) {
  // Rascunho local: as pílulas mudam o recorte na hora, mas a lista só troca
  // quando o aluno confirma no rodapé. Sem isso, cada toque recarregaria a
  // lista atrás da folha — e ela nem está visível.
  const [rascunho, setRascunho] = useState<FiltrosBanco>(filtros);
  const [rotuloTopico, setRotuloTopico] = useState<string | null>(rotulos.topico ?? null);

  // Uma consulta só, sem matéria: devolve as três árvores de uma vez, e com
  // elas os anos, as fases e os vestibulares que existem no acervo. Pedir por
  // matéria daria uma requisição a cada troca de pílula sem nada em troca.
  const taxonomia = useTaxonomia();

  // A contagem do rodapé é o recorte DE VERDADE, pedido ao servidor com
  // `porPagina: 1`: só o `total` interessa, e trazer 20 questões que ninguém
  // vai ver para mostrar um número seria pagar a página duas vezes.
  const contagem = useQuestoesDoBanco({
    ...rascunho,
    busca: busca.trim() || undefined,
    pagina: 1,
    porPagina: 1,
  });

  const arvores = taxonomia.data ?? [];
  const daMateria = arvores.find((a) => a.materia === rascunho.materia) ?? null;
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
                ativa={rascunho.materia === m}
                onToque={() => alternar('materia', m)}
              />
            ))}
          </Grupo>

          <Grupo legenda="Vestibular">
            {vestibulares.map((v) => (
              <Pilula
                key={v}
                rotulo={v}
                ativa={rascunho.vestibular === v}
                onToque={() => alternar('vestibular', v)}
              />
            ))}
          </Grupo>

          <Grupo legenda="Fase">
            {fases.map((f) => (
              <Pilula
                key={f}
                rotulo={`Fase ${f}`}
                ativa={rascunho.fase === f}
                onToque={() => alternar('fase', f)}
              />
            ))}
          </Grupo>

          <Grupo legenda="Ano">
            {anos.map((a) => (
              <Pilula
                key={a}
                rotulo={String(a)}
                ativa={rascunho.ano === a}
                onToque={() => alternar('ano', a)}
              />
            ))}
          </Grupo>

          {/* `disabled` no `fieldset` e não só nos botões: é o que faz o
              teclado e o leitor de tela pularem o grupo inteiro, em vez de
              anunciarem trinta pílulas que não respondem. */}
          <fieldset className="alu-filtros__grupo" disabled={!rascunho.materia}>
            <legend className="alu-filtros__legenda">Assunto</legend>

            {!rascunho.materia ? (
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
                    ativa={rascunho.topico === t.codigo}
                    onToque={() => {
                      const jaEstava = rascunho.topico === t.codigo;
                      alternar('topico', t.codigo);
                      setRotuloTopico(jaEstava ? null : t.nome);
                    }}
                  />
                ))}
              </div>
            )}
          </fieldset>
        </>
      )}
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
