import { useState } from 'react';
import type { ReactNode } from 'react';

import { alternarAno, anosMarcados } from '../../../dominio/banco';
import { useQuestoesDoBanco, useTaxonomia } from '../../../dados/aluno';
import type { ColecaoBanco, FiltrosBanco, TaxonomiaMateria } from '../../../dados/aluno';
import { Folha } from './Folha';
import { fmtInteiro } from './formato';

// Os filtros do acervo — e onde cada um mora, que é a parte que custou caro.
//
// São DUAS famílias, e a divisão não é estética (docs/35 §5):
//
//   PRIMÁRIOS   matéria e assunto. Ficam no CENTRO da tela, em `FiltrosDeMateriaEAssunto`,
//               nos dois tamanhos de tela. Matéria não é um filtro qualquer: é
//               o que DESTRAVA o assunto.
//   SECUNDÁRIOS coleção, vestibular, fase e ano. Ficam na coluna lateral no
//               desktop (`PainelDeFiltros`) e sobem do rodapé no celular
//               (`FolhaFiltros`) — `FiltrosSecundarios` é o corpo comum.
//
// ⚠️ POR QUE OS PRIMÁRIOS SAÍRAM DA COLUNA. A coluna é contêiner de rolagem
// próprio (`max-height` + `overflow-y: auto`, aluno-estudar.css). Rolada, ela
// escondia o título "Filtros" e o grupo MATÉRIA, e o que sobrava à vista era o
// ASSUNTO dizendo "escolha uma matéria primeiro" — a instrução apontando para
// um controle FORA DA TELA. No centro não há coluna que role: a instrução e o
// controle que ela cita ficam a quarenta pixels um do outro.
//
// ⚠️ A REGRA QUE ISTO EXISTE PARA CUMPRIR (docs/28 §6): filtrar por tópico
// EXIGE matéria. `1.1` é "Fundamentos" em Física, "Conjuntos e Lógica" em
// Matemática e "Estrutura Atômica" em Química — a chave do tópico é (matéria,
// código), nunca o código sozinho. A rota devolve 400 na combinação, e é
// justamente por isso que a interface tem de IMPEDIR o toque em vez de deixar
// o erro chegar: sem o 400 o aluno receberia um recorte errado sem erro nenhum
// na tela.
//
// A diferença entre as duas cascas dos secundários é de semântica, não de
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
// coordenação é uma faixa horizontal, e aqui não há 236px sobrando.

/** O que o pai não consegue rotular sozinho sem baixar a taxonomia inteira. */
export interface RotulosDeFiltro {
  /** "Termodinâmica" — o nome do tópico, que só a árvore do edital sabe. */
  topico?: string;
}

/**
 * O tópico do edital, derivado da árvore em vez de importado.
 *
 * `contratos.ts` reexporta `TaxonomiaMateria` mas não `TopicoTaxonomia`, e
 * `dados/aluno/` não é arquivo desta tela — derivar mantém o tipo amarrado à
 * mesma fonte sem tocar na camada de dado. Vale o mesmo para a matéria.
 */
type TopicoDoEdital = TaxonomiaMateria['blocos'][number]['topicos'][number];
type MateriaDoAcervo = TaxonomiaMateria['materia'];

function unicos<T>(valores: T[]): T[] {
  return [...new Set(valores)];
}

// ─── As duas coleções ────────────────────────────────────────────────────

/**
 * As duas metades do acervo, e COMO cada uma se lê — a diferença estrutural
 * das migrations 0031/0033, que não muda com importação nova.
 *
 * Mora aqui, e não na tela, porque a coleção passou a ser um grupo do painel
 * lateral (docs/35 §5) e a tela do celular usa a mesma lista: duas cópias
 * dariam dois textos diferentes para o mesmo acervo.
 */
const COLECOES: { id: ColecaoBanco; nome: string; comoE: string }[] = [
  { id: 'recentes', nome: 'Recentes', comoE: 'recorte da questão' },
  { id: 'arquivo', nome: 'Arquivo', comoE: 'página inteira do caderno' },
];

/**
 * O seletor de coleção. Controle segmentado, e não pílula removível: uma das
 * duas está SEMPRE ativa, porque as duas metades do acervo se leem de formas
 * diferentes e a tela precisa dizer qual está mostrando.
 *
 * ⚠️ O "como é" de cada uma acompanha o botão em vez de virar dica de mouse:
 * é ele que explica a diferença entre as duas leituras, e no celular não
 * existe passagem de mouse para revelar coisa nenhuma.
 */
export function SeletorDeColecao({
  colecao,
  onTrocar,
  variante,
}: {
  colecao: ColecaoBanco;
  onTrocar: (id: ColecaoBanco) => void;
  /**
   * 'centro' é a do celular (lado a lado, no fluxo da tela); 'painel' é a do
   * desktop (empilhada, dentro da coluna de 236px, onde não caberiam lado a
   * lado sem perder o "como é"). O CSS mostra uma e esconde a outra por
   * tamanho de tela — as duas nunca aparecem juntas.
   */
  variante: 'centro' | 'painel';
}) {
  return (
    <fieldset className={`alu-colecoes alu-colecoes--${variante}`}>
      {/* No painel o rótulo aparece, para a coleção se ler como mais um grupo
          de filtro; no centro os dois botões já se explicam sozinhos e um
          rótulo a mais só empurraria a lista para baixo. */}
      <legend className={variante === 'painel' ? 'alu-filtros__legenda' : 'alu-so-leitor'}>
        Coleção do acervo
      </legend>
      {COLECOES.map((c) => (
        <button
          key={c.id}
          type="button"
          className={`alu-colecao${c.id === colecao ? ' is-ativa' : ''}`}
          aria-pressed={c.id === colecao}
          onClick={() => onTrocar(c.id)}
        >
          <span className="alu-colecao__nome">{c.nome}</span>
          <span className="alu-colecao__como">{c.comoE}</span>
        </button>
      ))}
    </fieldset>
  );
}

// ─── Os primários: matéria e assunto, no centro ──────────────────────────

interface PropsDoFoco {
  /** O recorte em vigor. Aqui não há rascunho: a lista está logo abaixo. */
  filtros: FiltrosBanco;
  onAplicar: (filtros: FiltrosBanco, rotulos: RotulosDeFiltro) => void;
}

/**
 * Matéria e assunto, no centro da tela e nos dois tamanhos.
 *
 * A ordem é o argumento: a matéria vem primeiro porque é ela que destrava o
 * assunto, e o aviso de "escolha uma matéria" fica a uma linha das pílulas que
 * ele manda tocar — era esse o defeito de tê-los na coluna que rola.
 */
export function FiltrosDeMateriaEAssunto({ filtros, onAplicar }: PropsDoFoco) {
  const taxonomia = useTaxonomia();
  // A lista de assuntos abre por toque e rola por DENTRO: são até 26 pílulas
  // por matéria, e deixá-las sempre abertas empurraria as questões para baixo
  // da dobra no celular. Quem abriu continua vendo o botão que abriu.
  const [assuntosAbertos, setAssuntosAbertos] = useState(false);

  const arvores = taxonomia.data ?? [];
  const daMateria = arvores.find((a) => a.materia === filtros.materia) ?? null;
  const topicos: TopicoDoEdital[] = daMateria ? daMateria.blocos.flatMap((b) => b.topicos) : [];
  const escolhido = topicos.find((t) => t.codigo === filtros.topico) ?? null;

  function escolherMateria(materia: MateriaDoAcervo) {
    const mesma = filtros.materia === materia;
    const novo: FiltrosBanco = { ...filtros };
    if (mesma) delete novo.materia;
    else novo.materia = materia;
    // Trocar ou limpar a matéria limpa o tópico junto — ver o ⚠️ do topo. O
    // código sobrevivente apontaria para outro assunto em silêncio.
    delete novo.topico;
    if (mesma) setAssuntosAbertos(false);
    onAplicar(novo, {});
  }

  function escolherTopico(topico: TopicoDoEdital) {
    const jaEstava = filtros.topico === topico.codigo;
    const novo: FiltrosBanco = { ...filtros };
    if (jaEstava) delete novo.topico;
    else novo.topico = topico.codigo;
    // Escolher fecha a lista: o assunto escolhido passa a ser o rótulo do
    // botão, e manter trinta pílulas abertas por cima da resposta esconde
    // justamente o que o toque foi pedir.
    if (!jaEstava) setAssuntosAbertos(false);
    onAplicar(novo, jaEstava ? {} : { topico: topico.nome });
  }

  return (
    <section className="alu-foco">
      {taxonomia.isPending && <p className="alu-carregando">Carregando os filtros…</p>}

      {taxonomia.isError && (
        <div className="alu-filtros__erro">
          <p className="alu-erro">Não deu para carregar as matérias e os assuntos.</p>
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
            {arvores.map((a) => (
              <Pilula
                key={a.materia}
                rotulo={a.materia}
                ativa={filtros.materia === a.materia}
                onToque={() => escolherMateria(a.materia)}
              />
            ))}
          </Grupo>

          <fieldset className="alu-filtros__grupo">
            <legend className="alu-filtros__legenda">Assunto</legend>

            {!filtros.materia ? (
              <p className="alu-filtros__aviso">
                Escolha uma matéria aqui em cima — o mesmo código de assunto existe nas três e
                significa coisa diferente em cada uma.
              </p>
            ) : topicos.length === 0 ? (
              <p className="alu-filtros__aviso">
                Esta matéria ainda não tem assunto classificado no edital.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  className={`alu-foco__escolher${escolhido ? ' is-ativa' : ''}`}
                  aria-expanded={assuntosAbertos}
                  onClick={() => setAssuntosAbertos((v) => !v)}
                >
                  <span className="alu-foco__escolher-texto">
                    {escolhido ? escolhido.nome : `Escolher entre ${topicos.length} assuntos`}
                  </span>
                  <span aria-hidden="true">{assuntosAbertos ? '▴' : '▾'}</span>
                </button>

                {assuntosAbertos && (
                  <div className="alu-filtros__opcoes alu-foco__assuntos">
                    {topicos.map((t) => (
                      <Pilula
                        key={t.codigo}
                        rotulo={`${t.nome} · ${t.totalQuestoes}`}
                        ativa={filtros.topico === t.codigo}
                        onToque={() => escolherTopico(t)}
                      />
                    ))}
                  </div>
                )}
              </>
            )}
          </fieldset>
        </>
      )}
    </section>
  );
}

// ─── Os secundários: vestibular, fase e ano ──────────────────────────────

interface PropsDoCorpo {
  /** O recorte que as pílulas refletem — rascunho na folha, aplicado no painel. */
  recorte: FiltrosBanco;
  /** Troca uma chave de escolha única. `undefined` no valor limpa. */
  aoAlternar: <C extends keyof FiltrosBanco>(chave: C, valor: FiltrosBanco[C]) => void;
  /** O ano é o único grupo de MÚLTIPLA escolha, e por isso tem caminho próprio:
   *  o toggle dele não é "troca o valor", é "acrescenta ou tira da lista". */
  aoAlternarAno: (ano: number, disponiveis: readonly number[]) => void;
}

/**
 * Os grupos que não são matéria nem assunto. Sem casca e sem estado próprio:
 * quem guarda o recorte é o pai, porque é o pai que sabe se ele é rascunho ou
 * já é o recorte da tela.
 *
 * Nenhum deles toca em `materia` ou `topico` — os dois vivem no centro, e é o
 * que permite às duas cascas devolverem os rótulos que receberam sem mexer.
 */
function FiltrosSecundarios({ recorte, aoAlternar, aoAlternarAno }: PropsDoCorpo) {
  // Uma consulta só, sem matéria: devolve as três árvores de uma vez, e com
  // elas os anos, as fases e os vestibulares que existem no acervo. É a mesma
  // chave que `FiltrosDeMateriaEAssunto` pede — o React Query serve as duas
  // com uma requisição.
  const taxonomia = useTaxonomia();

  const arvores = taxonomia.data ?? [];
  const daMateria = arvores.find((a) => a.materia === recorte.materia) ?? null;
  // Escolhida a matéria, os anos e as fases passam a ser os DELA: o IME
  // objetivo não tem os mesmos anos em todas as matérias, e oferecer um ano
  // que devolve lista vazia é oferecer um beco.
  const escopo = daMateria ? [daMateria] : arvores;

  const vestibulares = unicos(escopo.flatMap((a) => a.vestibulares));
  const fases = unicos(escopo.flatMap((a) => a.fases)).sort((a, b) => a - b);
  const anos = unicos(escopo.flatMap((a) => a.anos)).sort((a, b) => b - a);

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

          {/* ⚠️ O ÚNICO grupo de múltipla escolha, e ele é ADITIVO: abre TODO
              APAGADO, e tocar 2025 acende só 2025 (decisão de 04/09, docs/35
              §4). Até 02/09 abria com tudo aceso — o que desenhava a ausência
              de filtro de dois jeitos no mesmo painel, já que Vestibular e Fase
              aqui em cima abrem apagados significando "todos", e deixava o
              gesto subtrativo. Quem traduz é `anosMarcados`. */}
          <Grupo legenda="Ano">
            {anos.map((a) => (
              <Pilula
                key={a}
                rotulo={String(a)}
                ativa={anosMarcados(recorte.anos).has(a)}
                onToque={() => aoAlternarAno(a, anos)}
              />
            ))}
          </Grupo>
        </>
      )}
    </>
  );
}

/** As chaves que as duas cascas dos secundários limpam — e só elas. */
const CHAVES_SECUNDARIAS = ['vestibular', 'fase', 'anos'] as const;

function algumSecundarioAtivo(filtros: FiltrosBanco): boolean {
  return CHAVES_SECUNDARIAS.some((c) =>
    c === 'anos' ? (filtros.anos?.length ?? 0) > 0 : filtros[c] != null,
  );
}

/** Devolve o recorte sem os secundários. Matéria e assunto ficam de pé — quem
 *  os apaga é o centro, onde eles estão à vista. */
function semSecundarios(filtros: FiltrosBanco): FiltrosBanco {
  const novo: FiltrosBanco = { ...filtros };
  for (const chave of CHAVES_SECUNDARIAS) delete novo[chave];
  return novo;
}

interface PropsDoPainel {
  filtros: FiltrosBanco;
  /** Devolvidos intactos: o painel não mexe em `topico`, então o nome dele
   *  continua valendo e não pode se perder no caminho. */
  rotulos: RotulosDeFiltro;
  colecao: ColecaoBanco;
  onTrocarColecao: (colecao: ColecaoBanco) => void;
  onAplicar: (filtros: FiltrosBanco, rotulos: RotulosDeFiltro) => void;
}

/**
 * A coluna fixa do desktop. Aplica na hora — a lista está ao lado.
 *
 * Sem rascunho e sem "aplicar": o resultado do toque é visível no mesmo
 * movimento do olho, então um botão de confirmação seria um passo a mais para
 * ver o que já estava à vista. O "Limpar" continua, porque desfazer cinco
 * pílulas uma a uma não é desfazer — e ele limpa SÓ os filtros deste painel:
 * apagar daqui a matéria, que agora está no centro, seria mexer no que o
 * botão não mostra. Quem zera tudo é o "Limpar tudo" ao lado das pílulas.
 */
export function PainelDeFiltros({
  filtros,
  rotulos,
  colecao,
  onTrocarColecao,
  onAplicar,
}: PropsDoPainel) {
  function alternar<C extends keyof FiltrosBanco>(chave: C, valor: FiltrosBanco[C]) {
    const novo: FiltrosBanco = { ...filtros };
    if (filtros[chave] === valor) delete novo[chave];
    else novo[chave] = valor;
    onAplicar(novo, rotulos);
  }

  return (
    <aside className="alu-painel-filtros">
      <div className="alu-painel-filtros__cabeca">
        <h2 className="alu-painel-filtros__titulo">Filtros</h2>
        {algumSecundarioAtivo(filtros) && (
          <button
            type="button"
            className="alu-filtros__limpar"
            onClick={() => onAplicar(semSecundarios(filtros), rotulos)}
          >
            Limpar
          </button>
        )}
      </div>

      {/* A coleção desceu para cá (docs/35 §5): ela troca de METADE do acervo,
          não recorta a que está aberta, e por isso não convive com as pílulas
          removíveis do centro. */}
      <SeletorDeColecao colecao={colecao} onTrocar={onTrocarColecao} variante="painel" />

      <FiltrosSecundarios
        recorte={filtros}
        aoAlternar={alternar}
        aoAlternarAno={(ano, disponiveis) =>
          onAplicar({ ...filtros, anos: alternarAno(filtros.anos, disponiveis, ano) }, rotulos)
        }
      />
    </aside>
  );
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

export function FolhaFiltros({ filtros, rotulos, busca, colecao, onFechar, onAplicar }: Props) {
  // Rascunho local: as pílulas mudam o recorte na hora, mas a lista só troca
  // quando o aluno confirma no rodapé. Sem isso, cada toque recarregaria a
  // lista atrás da folha — e ela nem está visível.
  const [rascunho, setRascunho] = useState<FiltrosBanco>(filtros);

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
      return novo;
    });
  }

  const total = contagem.data?.total ?? 0;

  return (
    <Folha
      aberta
      titulo="Filtrar"
      subtitulo="vestibular, fase e ano"
      altura="cheio"
      onFechar={onFechar}
      acoes={
        // Limpa só o que esta folha mostra. Matéria e assunto ficam no centro,
        // à vista, e um "Limpar" que apagasse os dois daqui derrubaria em
        // silêncio um recorte que o aluno não está olhando.
        algumSecundarioAtivo(rascunho) && (
          <button
            type="button"
            className="alu-filtros__limpar"
            onClick={() => setRascunho(semSecundarios)}
          >
            Limpar
          </button>
        )
      }
      rodape={
        <button
          type="button"
          className="alu-tecla alu-tecla--larga"
          disabled={contagem.isPending}
          // Os rótulos voltam como vieram: a folha não mexe no tópico, e
          // perder o nome dele aqui faria a pílula do centro virar "Assunto
          // 7.2" por causa de um toque em Fase.
          onClick={() => onAplicar(rascunho, rotulos)}
        >
          {contagem.isPending
            ? 'Contando…'
            : `Ver ${fmtInteiro(total)} ${total === 1 ? 'questão' : 'questões'}`}
        </button>
      }
    >
      <FiltrosSecundarios
        recorte={rascunho}
        aoAlternar={alternar}
        aoAlternarAno={(ano, disponiveis) =>
          setRascunho((atual) => ({ ...atual, anos: alternarAno(atual.anos, disponiveis, ano) }))
        }
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
 * desmarca — é o "voltar atrás" sem um botão a mais na tela. A exceção é o
 * ano, que é lista e tem caminho próprio (`alternarAno`).
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
