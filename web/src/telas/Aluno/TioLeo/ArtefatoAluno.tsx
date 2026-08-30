import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { Artefato } from '../../../componentes/chat/Artefato';
import { useQuestaoDoBanco, useSimulado } from '../../../dados/aluno';
import type { LinhaExtrato, MateriaContraCorte } from '../../../dados/aluno';
import type { ArtefatoChat } from '../../../tipos/chat';
import { BarraCorte } from '../pecas/BarraCorte';
import { CartaoQuestaoAluno } from '../pecas/CartaoQuestaoAluno';
import { Icone } from '../pecas/Icone';
import { TarjaFonte } from '../pecas/TarjaFonte';
import {
  AVISO_DE_COBERTURA,
  MATERIAS_COM_TAXONOMIA,
  fmtDataLonga,
  fmtInteiro,
} from '../pecas/formato';

// Os artefatos do Tio Léo, no visual do aluno.
//
// ⚠️ O MODELO NÃO DESENHA NADA (docs/27 §2.1). A tool devolve `{tipo, titulo,
// payload}` com payload sendo DADO; o LLM escolhe QUAL cartão e DE QUAL FONTE,
// e quem desenha é este arquivo. É à prova de injeção por construção, e é o
// padrão que tudo aqui segue — nenhum `innerHTML`, nenhum
// `dangerouslySetInnerHTML`, nenhum SVG vindo do modelo, nunca.
//
// ⚠️ E O PAYLOAD NÃO É A FONTE DO CONTEÚDO QUE JÁ TEM ROTA. Questão e prova são
// buscadas por id em `GET /banco/questoes/{id}` e `GET /me/simulado/{id}` — as
// duas existem hoje. Redesenhá-las a partir do que a tool escreveu criaria um
// segundo contrato para um dado que já tem dono, e é assim que uma integração
// vira mock sem ninguém perceber. Do payload vem só o IDENTIFICADOR.
//
// ⚠️ E NENHUM LINK EXTERNO vindo do modelo (docs/27 §9, regra 2): link de LLM é
// vetor de phishing para um público de 16 a 18 anos. Os únicos endereços que
// aparecem aqui são rota interna montada por nós e a URL de resolução que vem
// do BANCO — dado nosso, não do modelo.
//
// ⚠️ Comparação só com AGREGADO (docs/27 §9, regra 4): o histograma mostra a
// distribuição da turma e a marca do próprio aluno, jamais a nota nominal de um
// colega. Nenhum cartão daqui aceita nome de terceiro.
//
// PAYLOAD QUE NÃO BATE NÃO FALHA EM SILÊNCIO (docs/27 §7): cai em
// `NaoDesenhavel`, que diz o que houve. Falhar visível é a regra.
//
// ⚠️ ESTE RENDERIZADOR AINDA NÃO ESTÁ COSTURADO À CONVERSA, e é um buraco
// conhecido, não um esquecimento. `componentes/chat/Conversa.tsx` e
// `Mensagem.tsx` importam `componentes/chat/Artefato` de forma fixa e não
// aceitam um renderizador por prop — e os dois servem à COORDENAÇÃO, que este
// sprint não edita. O que liga é uma prop opcional
// (`renderArtefato?: (a: ArtefatoChat) => ReactNode`, com o `Artefato` de hoje
// como padrão) nesses dois arquivos. Enquanto ela não existe, a folha do aluno
// mostra os artefatos com o desenho da coordenação — o que na prática só
// acontece com `histograma` e `linha_temporal`, porque as tools que produzem
// os tipos novos ainda não existem em `tools_aluno.py` (docs/27 §7).

export function ArtefatoAluno({ artefato }: { artefato: ArtefatoChat }) {
  if (!artefato?.tipo) return null;

  // `histograma` e `linha_temporal` JÁ SÃO REAIS e já têm componente na
  // coordenação. Reimplementá-los daria duas versões do mesmo gráfico para
  // divergirem no primeiro conserto — delegar é o barato e o certo.
  if (artefato.tipo === 'histograma' || artefato.tipo === 'linha_temporal') {
    return <Artefato artefato={artefato} />;
  }

  if (artefato.tipo === 'barras_corte') return <BarrasCorte artefato={artefato} />;
  if (artefato.tipo === 'extrato_xp') return <ExtratoDeXp artefato={artefato} />;
  if (artefato.tipo === 'questao') return <QuestaoDoArtefato artefato={artefato} />;
  if (artefato.tipo === 'lista_questoes') return <ListaDeQuestoes artefato={artefato} />;
  if (artefato.tipo === 'prova') return <Prova artefato={artefato} />;
  if (artefato.tipo === 'formula') return <Formula artefato={artefato} />;

  return <NaoDesenhavel tipo={artefato.tipo} />;
}

// ─── O casco do cartão ───────────────────────────────────────────────────

/**
 * Cartão de artefato: 16px de raio, 1px de borda, cabeçalho em maiúscula
 * pequena e o botão de expandir no canto.
 *
 * ⚠️ Expandido, o conteúdo é montado uma SEGUNDA vez, e não movido. Mover
 * desmontaria o cartão da conversa e a folha saltaria ao fechar; a segunda
 * instância nasce com o estado interno zerado (o gabarito volta escondido), que
 * é justamente o que se quer de quem abriu a questão em tela cheia para ler.
 */
function Cartao({
  olho,
  titulo,
  children,
}: {
  olho: string;
  titulo?: string;
  children: ReactNode;
}) {
  const [expandido, setExpandido] = useState(false);
  const painel = useRef<HTMLDivElement>(null);
  const botao = useRef<HTMLButtonElement>(null);

  // Esc fecha a tela cheia, e o foco volta para o botão que a abriu. Sem a
  // volta do foco, quem usa teclado é devolvido ao topo do documento — e aqui
  // o topo do documento está atrás de duas camadas.
  useEffect(() => {
    if (!expandido) {
      return;
    }
    painel.current?.focus();

    function aoTeclar(ev: KeyboardEvent) {
      if (ev.key !== 'Escape') return;
      // ⚠️ CAPTURA, não bolha. A `Folha` escuta o mesmo Esc em `document` e
      // registrou o listener dela ANTES deste — na bolha ela rodaria primeiro e
      // um Esc fecharia a folha inteira junto com a tela cheia, porque
      // `stopPropagation` não alcança outro listener do mesmo nó. Na captura
      // este roda antes e o evento nunca chega à bolha.
      ev.stopPropagation();
      setExpandido(false);
      botao.current?.focus();
    }
    document.addEventListener('keydown', aoTeclar, true);
    return () => document.removeEventListener('keydown', aoTeclar, true);
  }, [expandido]);

  function fechar() {
    setExpandido(false);
    botao.current?.focus();
  }

  return (
    <>
      <div className="alu-tioleo__artefato">
        <TarjaFonte chave="artefatosDoTioLeo" />
        <header className="alu-tioleo__artefato-topo">
          <span className="alu-olho alu-tioleo__artefato-olho">{olho}</span>
          <button
            ref={botao}
            type="button"
            className="alu-tioleo__artefato-expandir"
            onClick={() => setExpandido(true)}
          >
            <Icone nome="expandir" tamanho={15} />
            <span className="alu-so-leitor">Abrir em tela cheia</span>
          </button>
        </header>
        {titulo && <p className="alu-tioleo__artefato-titulo">{titulo}</p>}
        <div className="alu-tioleo__artefato-corpo">{children}</div>
      </div>

      {expandido && (
        <div
          ref={painel}
          className="alu-tioleo__expandido"
          role="dialog"
          aria-modal="true"
          aria-label={titulo || olho}
          tabIndex={-1}
        >
          <header className="alu-tioleo__expandido-topo">
            <span className="alu-olho">{olho}</span>
            <button type="button" className="alu-folha__botao-icone" onClick={fechar}>
              <Icone nome="fechar" tamanho={20} />
              <span className="alu-so-leitor">Fechar</span>
            </button>
          </header>
          <div className="alu-tioleo__expandido-corpo">
            {titulo && <p className="alu-tioleo__artefato-titulo">{titulo}</p>}
            {children}
          </div>
        </div>
      )}
    </>
  );
}

/** Falhar visível (docs/27 §7): o cartão diz o que não deu, e o que fazer. */
function NaoDesenhavel({ tipo }: { tipo: string }) {
  return (
    <div className="alu-tioleo__artefato alu-tioleo__artefato--falha">
      <TarjaFonte chave="artefatosDoTioLeo" />
      <span className="alu-olho alu-olho--quieto">Cartão não desenhado</span>
      <p className="alu-vazio">
        O Tio Léo mandou um cartão de “{tipo.slice(0, 40)}” que esta versão do app ainda não sabe
        desenhar. Peça a mesma informação em texto.
      </p>
    </div>
  );
}

/** Esqueleto com a forma do cartão enquanto a rota responde — nunca spinner. */
function CartaoCarregando({ olho }: { olho: string }) {
  return (
    <div className="alu-tioleo__artefato">
      <TarjaFonte chave="artefatosDoTioLeo" />
      <span className="alu-olho alu-olho--quieto">{olho}</span>
      <span className="alu-so-leitor">Buscando</span>
      <span className="alu-tioleo__osso alu-tioleo__osso--curto" />
      <span className="alu-tioleo__osso" />
      <span className="alu-tioleo__osso alu-tioleo__osso--medio" />
    </div>
  );
}

/** Buscar falhou — o que houve, e o botão para tentar de novo. */
function CartaoQueNaoAbriu({
  olho,
  mensagem,
  onTentarDeNovo,
}: {
  olho: string;
  mensagem: string;
  onTentarDeNovo: () => void;
}) {
  return (
    <div className="alu-tioleo__artefato alu-tioleo__artefato--falha">
      <TarjaFonte chave="artefatosDoTioLeo" />
      <span className="alu-olho alu-olho--quieto">{olho}</span>
      <p className="alu-vazio">{mensagem}</p>
      <button type="button" className="alu-tecla alu-tecla--pequena" onClick={onTentarDeNovo}>
        Tentar de novo
      </button>
    </div>
  );
}

// ─── Leitura defensiva do payload ────────────────────────────────────────
// O payload vem do servidor, mas quem escolheu o tipo foi o modelo: um cartão
// pedido com o payload de outro não pode derrubar a folha inteira.

function ehObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null;
}

function texto(valor: unknown): string | null {
  return typeof valor === 'string' && valor.trim() !== '' ? valor : null;
}

function numero(valor: unknown): number | null {
  return typeof valor === 'number' && Number.isFinite(valor) ? valor : null;
}

// ─── barras_corte ────────────────────────────────────────────────────────

function BarrasCorte({ artefato }: { artefato: ArtefatoChat }) {
  const p = artefato.payload;
  if (!ehObjeto(p) || !Array.isArray(p.materias)) return <NaoDesenhavel tipo={artefato.tipo} />;

  const materias: MateriaContraCorte[] = p.materias.filter(ehObjeto).flatMap((m) => {
    const nome = texto(m.materia);
    const nota = numero(m.nota);
    const corte = numero(m.corte);
    if (nome == null || nota == null || corte == null) return [];
    return [{ materia: nome, nota, corte, eliminatoria: m.eliminatoria === true }];
  });

  if (!materias.length) return <NaoDesenhavel tipo={artefato.tipo} />;

  return (
    // O olho NOMEIA A RÉGUA (docs/24 §2): `compacto` esconde o rótulo "CORTE
    // 4,0" de dentro do gráfico, e uma linha de ouro sem nome é veredito sem
    // régua — a etiqueta de distância sozinha vira só a má notícia.
    <Cartao olho="Suas notas contra o corte" titulo={artefato.titulo}>
      {/* `compacto` some com os números de topo: dentro de uma folha de 390px
          o rótulo por cima da barra vira ruído (docs/27 §8). */}
      <BarraCorte materias={materias} compacto />
    </Cartao>
  );
}

// ─── extrato_xp ──────────────────────────────────────────────────────────

function ExtratoDeXp({ artefato }: { artefato: ArtefatoChat }) {
  const p = artefato.payload;
  if (!ehObjeto(p) || !Array.isArray(p.linhas)) return <NaoDesenhavel tipo={artefato.tipo} />;

  const linhas: LinhaExtrato[] = p.linhas.filter(ehObjeto).flatMap((l) => {
    const rotulo = texto(l.rotulo);
    const xp = numero(l.xp);
    if (rotulo == null || xp == null) return [];
    return [{ rotulo, xp, evidencia: texto(l.evidencia) ?? '' }];
  });

  if (!linhas.length) return <NaoDesenhavel tipo={artefato.tipo} />;

  // Sem `total` no payload o cartão SOMA O QUE MOSTRA, e não finge saber o
  // saldo do ciclo: XP é derivado (docs/26 §3) e um total que não bate com as
  // linhas visíveis é pior que total nenhum.
  const total = numero(p.total) ?? linhas.reduce((soma, l) => soma + l.xp, 0);

  return (
    <Cartao olho="Extrato de XP" titulo={artefato.titulo ?? texto(p.simuladoNome) ?? undefined}>
      <ul className="alu-tioleo__extrato">
        {linhas.map((linha) => (
          // ⚠️ As linhas que NÃO pontuaram continuam aparecendo, vazadas e com
          // +0 (docs/26 §3). Sumir com elas tiraria justamente o lugar onde o
          // aluno entende o que faltou.
          <li
            key={`${linha.rotulo}-${linha.evidencia}`}
            className={`alu-tioleo__extrato-linha${linha.xp === 0 ? ' alu-vazado' : ''}`}
          >
            <span className="alu-tioleo__extrato-rotulo">{linha.rotulo}</span>
            <span
              className={`alu-tioleo__extrato-xp${linha.xp === 0 ? ' alu-tioleo__extrato-xp--zero' : ''}`}
            >
              +{fmtInteiro(linha.xp)}
            </span>
            {linha.evidencia && (
              <span className="alu-tioleo__extrato-evidencia">{linha.evidencia}</span>
            )}
          </li>
        ))}
      </ul>
      <p className="alu-tioleo__extrato-total">
        <span className="alu-olho alu-olho--quieto">Total</span>
        <strong className="alu-magnitude">{fmtInteiro(total)}</strong>
      </p>
    </Cartao>
  );
}

// ─── questao ─────────────────────────────────────────────────────────────

/**
 * A questão do acervo, buscada por id.
 *
 * ⚠️ O ENUNCIADO NÃO VEM DO PAYLOAD. `GET /banco/questoes/{id}` já existe e
 * `useQuestaoDoBanco` já o consome; é a única fonte que traz `resolucaoUrl` e
 * `resolucaoMd`, e são elas que decidem se a resolução aparece marcada como
 * "professor do Ari" ou "gerada por IA" (docs/29 §D.1). Uma cópia do enunciado
 * dentro do payload da tool seria um segundo contrato para o mesmo dado — e o
 * primeiro a divergir seria justamente a procedência da resolução.
 *
 * Do payload sai só o id, e ele é o `{vestibular}_{ano}_fase{n}_q{NN}` do banco.
 */
function QuestaoDoArtefato({ artefato }: { artefato: ArtefatoChat }) {
  const p = artefato.payload;
  // A tool pode mandar a questão embrulhada ou solta; as duas formas custam a
  // mesma linha aqui e evitam um cartão perdido por causa de um nível de chave.
  const bruto = ehObjeto(p) && ehObjeto(p.questao) ? p.questao : p;
  const id = ehObjeto(bruto) ? (texto(bruto.id) ?? texto(bruto.questaoId)) : null;

  const consulta = useQuestaoDoBanco(id);

  if (id == null) return <NaoDesenhavel tipo={artefato.tipo} />;
  if (consulta.isPending) return <CartaoCarregando olho="Questão" />;
  if (consulta.isError || !consulta.data) {
    return (
      <CartaoQueNaoAbriu
        olho="Questão"
        mensagem="Não consegui abrir esta questão do acervo agora. Costuma ser conexão."
        onTentarDeNovo={() => void consulta.refetch()}
      />
    );
  }

  const questao = consulta.data;
  const origem = `${questao.vestibular} · ${questao.ano} · Fase ${questao.fase}`;

  return (
    <Cartao olho={origem} titulo={artefato.titulo}>
      {/* `enxuto` tira o rodapé de ações: marcar resolvida e anotar são gestos
          da tela de estudo, não da conversa. O botão "Ver a resolução" e a
          etiqueta de procedência vêm de dentro do cartão (docs/29 §D.1). */}
      <CartaoQuestaoAluno questao={questao} enxuto />
    </Cartao>
  );
}

// ─── lista_questoes ──────────────────────────────────────────────────────

/**
 * Só código de tópico do edital vira rota. É a "lista fechada" que docs/27 §9
 * exige: o destino é montado por nós a partir de um código validado, nunca de
 * uma string livre que o modelo escreveu.
 */
const CODIGO_DE_TOPICO = /^\d+(\.\d+)*$/;

/** O acervo só tem estas três, e `MateriaBanco` é fechado (docs/24 §3.3). */
function materiaDoAcervo(nome: string | null): string | null {
  return MATERIAS_COM_TAXONOMIA.find((m) => m === nome) ?? null;
}

function ListaDeQuestoes({ artefato }: { artefato: ArtefatoChat }) {
  const p = artefato.payload;
  const bruto = ehObjeto(p) ? (p.itens ?? p.questoes ?? p.assuntos) : null;
  if (!Array.isArray(bruto)) return <NaoDesenhavel tipo={artefato.tipo} />;

  const todos = bruto.filter(ehObjeto).flatMap((i) => {
    const assunto = texto(i.assunto) ?? texto(i.nome);
    if (assunto == null) return [];
    const codigo = texto(i.topicoCodigo) ?? texto(i.codigo);
    return [
      {
        assunto,
        materia: materiaDoAcervo(texto(i.materia)),
        quantidade: numero(i.quantidade),
        codigo: codigo && CODIGO_DE_TOPICO.test(codigo) ? codigo : null,
      },
    ];
  });

  // Três linhas: o cartão é um convite a treinar, não um índice. Quem quer a
  // lista inteira abre Estudar.
  const itens = todos.slice(0, 3);
  if (!itens.length) return <NaoDesenhavel tipo={artefato.tipo} />;

  return (
    <Cartao olho="Para treinar" titulo={artefato.titulo}>
      <ul className="alu-tioleo__lista">
        {itens.map((item) => (
          <li key={item.assunto} className="alu-tioleo__lista-linha">
            <span className="alu-tioleo__lista-assunto">
              {item.assunto}
              {(item.materia || item.quantidade != null) && (
                <em className="alu-tioleo__lista-sub">
                  {[item.materia, item.quantidade != null && `${fmtInteiro(item.quantidade)} questões`]
                    .filter(Boolean)
                    .join(' · ')}
                </em>
              )}
            </span>

            {/* ⚠️ TÓPICO EXIGE MATÉRIA, e a interface IMPEDE a combinação em vez
                de deixar o 400 chegar: '1.1' é "Fundamentos" em Física,
                "Conjuntos e Lógica" em Matemática e "Estrutura Atômica" em
                Química (docs/28 §6). Sem a matéria no payload, o "Treinar" daria
                numa fila que o `Treino` não consegue montar — então ele vira o
                caminho de escolher o assunto, que é onde a matéria existe. */}
            {item.materia && item.codigo ? (
              <Link
                className="alu-tecla alu-tecla--pequena"
                to={`/treino/assunto/${encodeURIComponent(item.materia)}/${item.codigo}`}
              >
                Treinar
              </Link>
            ) : (
              <Link className="alu-tecla alu-tecla--pequena" to="/estudar/assuntos">
                Ver em Estudar
              </Link>
            )}
          </li>
        ))}
      </ul>

      {/* Truncar em silêncio faria o aluno concluir que a lista é essa. */}
      {todos.length > itens.length && (
        <p className="alu-tioleo__lista-aviso">
          {`Mostrando 3 de ${fmtInteiro(todos.length)} — o resto está em Estudar.`}
        </p>
      )}

      {/* Leitura por assunto DIZ o que cobre (docs/24 §3.3): um plano que
          ignora Inglês em silêncio é pior que plano nenhum, e o Inglês da Fase 1
          do ITA é o único eliminatório. */}
      <p className="alu-tioleo__lista-aviso">{AVISO_DE_COBERTURA}</p>
    </Cartao>
  );
}

// ─── prova ───────────────────────────────────────────────────────────────

/**
 * A capa da prova, buscada por id.
 *
 * Mesma regra da questão: `GET /me/simulado/{id}` existe e `useSimulado` já o
 * consome, então nome e data vêm de lá. O payload entrega o identificador.
 */
function Prova({ artefato }: { artefato: ArtefatoChat }) {
  const p = artefato.payload;
  const id = ehObjeto(p) ? (texto(p.simuladoId) ?? texto(p.id)) : null;

  const ficha = useSimulado(id ?? undefined);

  if (id == null) return <NaoDesenhavel tipo={artefato.tipo} />;
  if (ficha.isPending) return <CartaoCarregando olho="Prova" />;
  if (ficha.isError || !ficha.data) {
    return (
      <CartaoQueNaoAbriu
        olho="Prova"
        mensagem="Não consegui abrir esta prova agora. Pode ser que ela não seja sua, ou seja conexão."
        onTentarDeNovo={() => void ficha.refetch()}
      />
    );
  }

  const nome = ficha.data.nome ?? ficha.data.rotulo ?? 'Simulado';

  return (
    <Cartao olho="Prova">
      <p className="alu-tioleo__prova-nome">{nome}</p>
      {ficha.data.dataAplicacao && (
        <p className="alu-tioleo__prova-data">{fmtDataLonga(ficha.data.dataAplicacao)}</p>
      )}
      {/* ⚠️ NUNCA o PDF embutido (docs/27 §6): `pdf.js` pesa ~1 MB e num celular
          entrega pior que o visualizador nativo. E o botão leva à FICHA do
          simulado, não à URL do arquivo — a URL de `/me/simulado/{id}/arquivo`
          é assinada, expira, e endereço visível é proibido (docs/27 §9). */}
      <Link className="alu-tecla alu-tecla--pequena" to={`/provas/${encodeURIComponent(id)}`}>
        Abrir a prova
      </Link>
    </Cartao>
  );
}

// ─── formula ─────────────────────────────────────────────────────────────

/**
 * Fórmula como TEXTO SIMPLES, e é decisão, não preguiça.
 *
 * A escolha entre KaTeX empacotado e MathML via Temml está EM ABERTO
 * (docs/27 §12), e nenhuma dependência entra antes dela — as quatro de produção
 * são react, react-dom, react-router-dom e @tanstack/react-query.
 *
 * ⚠️ E o risco de docs/27 §10 é o motivo de não haver pressa: FÓRMULA BONITA E
 * ERRADA AUMENTA A CONFIANÇA DO ALUNO NUMA RESPOSTA FALSA. O modelo escreve
 * LaTeX impecavelmente renderizado e matematicamente falso, e um aluno de 17
 * anos não tem repertório para desconfiar de uma derivação bem diagramada.
 * Enquanto a mitigação (mostrar a resolução oficial da questão em vez de
 * derivar do zero) não estiver no prompt, o texto cru é o estado honesto: ele
 * *parece* rascunho, e rascunho se confere.
 */
function Formula({ artefato }: { artefato: ArtefatoChat }) {
  const p = artefato.payload;
  const expressao =
    (ehObjeto(p) ? (texto(p.expressao) ?? texto(p.latex) ?? texto(p.texto)) : null) ?? texto(p);
  if (expressao == null) return <NaoDesenhavel tipo={artefato.tipo} />;

  return (
    <div className="alu-tioleo__artefato">
      <TarjaFonte chave="formulaMatematica" />
      <span className="alu-olho alu-olho--quieto">Fórmula</span>
      {/* `overflow-x: auto` no próprio bloco: uma fórmula longa rola sozinha e
          não empurra a folha (docs/27 §8). */}
      <pre className="alu-tioleo__formula">{expressao}</pre>
      <p className="alu-tioleo__formula-aviso">
        Ainda não desenhamos fórmula: isto é o texto como o Tio Léo escreveu. Confira as contas
        antes de confiar.
      </p>
    </div>
  );
}
