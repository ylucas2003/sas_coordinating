import katex from 'katex';
import { Fragment, useMemo } from 'react';
import { type Bloco, type Trecho, analisarMarkdown } from '../../dominio/markdown';

/**
 * Markdown leve com fórmula renderizada — resolução do banco, resposta do
 * Tio Léo, qualquer texto de matemática, física ou química do produto.
 *
 * A gramática e a ordem de leitura vivem em `dominio/markdown.ts`; aqui só se
 * decide como cada pedaço vira elemento. O KaTeX foi escolhido no lugar do
 * MathJax por dois motivos concretos deste projeto: renderiza síncrono (a
 * fórmula nasce pronta, sem o pulo de layout de quem mede depois) e traz as
 * fontes dentro do pacote npm, servidas do nosso próprio domínio — asset de
 * CDN está proibido enquanto houver dado de menor de idade em tela
 * (CLAUDE.md, armadilha 6, a mesma que tirou o Google Fonts).
 */

/**
 * Notação brasileira que o KaTeX não conhece.
 *
 * `\sen` não é capricho: 14 das 58 fórmulas que falhavam na medição de 01/09
 * eram só isso. Vale para o que o professor brasileiro escreve — `tg`, `cotg`,
 * `arcsen` — e para o `\Ω` que algumas resoluções usam no lugar de `\Omega`.
 * `\operatorname` (e não `\text`) porque é ele que dá o espaçamento de função:
 * `\sen\theta` sai "sen θ", não "senθ".
 */
const MACROS_PT_BR: Record<string, string> = {
  '\\sen': '\\operatorname{sen}',
  '\\arcsen': '\\operatorname{arcsen}',
  '\\tg': '\\operatorname{tg}',
  '\\arctg': '\\operatorname{arctg}',
  '\\cotg': '\\operatorname{cotg}',
  '\\cossec': '\\operatorname{cossec}',
  '\\cosec': '\\operatorname{cossec}',
  '\\Arg': '\\operatorname{Arg}',
  '\\Ω': '\\Omega',
  '\\ohm': '\\Omega',
};

/** Vermelho do sistema, escrito por extenso: vai em `style` inline do KaTeX. */
const COR_ERRO = '#d9354a';

/**
 * O HTML de uma fórmula.
 *
 * `throwOnError: false` é a decisão importante: 26 fórmulas do acervo têm erro
 * genuíno de LaTeX, e uma exceção aqui derrubaria o cartão inteiro. Com ele
 * desligado, a fórmula quebrada aparece em vermelho, legível, com o TeX
 * original no `title` — o aluno perde a beleza daquela linha, não a resolução.
 */
function htmlDaFormula(tex: string, bloco: boolean): string {
  return katex.renderToString(tex, {
    displayMode: bloco,
    throwOnError: false,
    errorColor: COR_ERRO,
    // `strict` ligado reclama de acento e de `ª` dentro de `\text{}`, que o
    // corpus usa o tempo todo e que o KaTeX renderiza bem assim mesmo.
    strict: false,
    // Sem `\href`, `\url` nem `\includegraphics`: o TeX vem de LLM, e é este
    // sinalizador que impede que ele injete destino de link no HTML abaixo.
    trust: false,
    macros: MACROS_PT_BR,
    output: 'htmlAndMathml',
  });
}

/**
 * `dangerouslySetInnerHTML` aqui é seguro e não tem alternativa: o KaTeX
 * devolve HTML pronto (é o formato dele), escapa o que veio da entrada e, com
 * `trust: false`, não emite âncora nem `<img>`. O TeX nunca chega ao DOM como
 * marcação — chega como texto medido pelo KaTeX.
 */
function Formula({ tex, bloco }: { tex: string; bloco?: boolean }) {
  const html = useMemo(() => htmlDaFormula(tex, bloco === true), [tex, bloco]);

  if (bloco) {
    // O `div` rolável é o que segura fórmula longa no celular: sem ele, uma
    // linha de 40 caracteres estoura o cartão e leva a página junto.
    return (
      <div className="md__formula">
        {/* biome-ignore lint/security/noDangerouslySetInnerHtml: HTML do KaTeX, ver comentário acima */}
        <span dangerouslySetInnerHTML={{ __html: html }} />
      </div>
    );
  }
  return (
    // biome-ignore lint/security/noDangerouslySetInnerHtml: HTML do KaTeX, ver comentário acima
    <span className="md__formula-linha" dangerouslySetInnerHTML={{ __html: html }} />
  );
}

/**
 * O índice como `key` é o certo nestas quatro listas, não um atalho: os blocos
 * e trechos são posicionais, nascem inteiros de `analisarMarkdown(texto)` e
 * nunca são reordenados, inseridos nem removidos — trocou o texto, trocou a
 * lista toda. Não existe identidade estável a preservar, e inventar uma pelo
 * conteúdo remontaria fórmula repetida sem motivo.
 */
function Trechos({ trechos }: { trechos: Trecho[] }) {
  return (
    <>
      {/* biome-ignore-start lint/suspicious/noArrayIndexKey: lista posicional, ver comentário acima */}
      {trechos.map((t, i) => {
        if (t.tipo === 'formula') return <Formula key={i} tex={t.tex} />;
        if (t.tipo === 'negrito') return <strong key={i}>{t.valor}</strong>;
        if (t.tipo === 'italico') return <em key={i}>{t.valor}</em>;
        return <Fragment key={i}>{t.valor}</Fragment>;
      })}
      {/* biome-ignore-end lint/suspicious/noArrayIndexKey: lista posicional */}
    </>
  );
}

function Linhas({ linhas }: { linhas: Trecho[][] }) {
  return (
    <>
      {/* biome-ignore-start lint/suspicious/noArrayIndexKey: lista posicional, ver comentário acima */}
      {linhas.map((linha, i) => (
        <Fragment key={i}>
          {i > 0 && <br />}
          <Trechos trechos={linha} />
        </Fragment>
      ))}
      {/* biome-ignore-end lint/suspicious/noArrayIndexKey: lista posicional */}
    </>
  );
}

function BlocoRenderizado({ bloco }: { bloco: Bloco }) {
  if (bloco.tipo === 'formula') return <Formula tex={bloco.tex} bloco />;

  if (bloco.tipo === 'lista') {
    const Lista = bloco.ordenada ? 'ol' : 'ul';
    return (
      <Lista className="md__lista">
        {/* biome-ignore-start lint/suspicious/noArrayIndexKey: lista posicional, ver comentário acima */}
        {bloco.itens.map((item, i) => (
          <li key={i}>
            <Trechos trechos={item} />
          </li>
        ))}
        {/* biome-ignore-end lint/suspicious/noArrayIndexKey: lista posicional */}
      </Lista>
    );
  }

  return (
    <p className="md__p">
      <Linhas linhas={bloco.linhas} />
    </p>
  );
}

/**
 * @param variante Modificador de estilo (`resolucao`, hoje). O espaçamento e o
 * corpo mudam conforme o texto é uma conta para estudar ou uma fala de chat.
 */
export function Markdown({
  texto,
  variante,
}: {
  texto: string;
  variante?: 'resolucao';
}) {
  const blocos = useMemo(() => analisarMarkdown(texto), [texto]);

  return (
    <div className={variante ? `md md--${variante}` : 'md'}>
      {/* biome-ignore-start lint/suspicious/noArrayIndexKey: lista posicional, ver comentário acima */}
      {blocos.map((bloco, i) => (
        <BlocoRenderizado key={i} bloco={bloco} />
      ))}
      {/* biome-ignore-end lint/suspicious/noArrayIndexKey: lista posicional */}
    </div>
  );
}
