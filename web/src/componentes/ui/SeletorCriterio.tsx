import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import type { FocusEvent as FocoReact, KeyboardEvent as TecladoReact } from 'react';

import { explicarCriterio } from '../../dominio/criterios';
import type { CriterioClassificacao } from '../../tipos/dominio';
import { BotaoInfo } from './BotaoInfo';

/**
 * Qual régua de corte está em uso — a do colégio ou a de um edital.
 *
 * Saiu de dentro do Painel quando a ficha do ciclo passou a precisar dele: os
 * gráficos de lá desenhavam a linha de corte com um `4` escrito no TSX, e a
 * troca de régua tem que mover a tabela do Painel e o gráfico da ficha do
 * mesmo jeito (docs/31 §P1).
 *
 * A classe segue sendo `.painel-criterio` de propósito — é a pílula do casco,
 * já definida em `styles/painel.css`, e renomeá-la só para o componente ter
 * mudado de pasta trocaria CSS por nada.
 *
 * ⚠️ Era um `<select>` e deixou de ser: cada régua ganhou um "i" com a
 * explicação de como ela corta, e `<option>` não aceita botão dentro. A troca
 * custa o seletor nativo do celular, então a lista tem linhas de 44px no toque
 * e o "i" tem área de toque ampliada (`painel.css`). A régua é o controle que
 * muda a leitura da tela inteira — e "Tio Leo" sozinho não diz que ele corta
 * com E, enquanto os editais cortam com OU.
 */

/** Balão com lista e três blocos de texto: mais largo que o de uma frase. */
const LARGURA_EXPLICACAO = 300;

/** Folga mínima entre a lista e a borda da janela. */
const MARGEM_DA_JANELA = 8;

export function SeletorCriterio({
  criterios, valor, onEscolher, onCriar, rotulo = 'Critério de classificação',
}: {
  criterios: CriterioClassificacao[];
  valor: string;
  onEscolher: (slug: string) => void;
  /** Quando presente, o seletor oferece "Criar régua…" no fim da lista. */
  onCriar?: () => void;
  rotulo?: string;
}) {
  const [aberto, setAberto] = useState(false);
  const raizRef = useRef<HTMLDivElement>(null);
  const botaoRef = useRef<HTMLButtonElement>(null);
  const listaRef = useRef<HTMLUListElement>(null);
  const idLista = useId();
  // A lista nasce ancorada à DIREITA do controle — é onde ele mora nas telas de
  // desktop. Se assim ela sair da janela (celular, controle à esquerda, nome de
  // régua comprido), passa a ancorar à esquerda.
  const [ancoraEsquerda, setAncoraEsquerda] = useState(false);
  // Só o teclado move o foco para dentro da lista ao abrir: no mouse o foco
  // fica no botão, e puxá-lo para uma linha pintaria um anel que ninguém pediu.
  const focarAoAbrir = useRef(false);

  useEffect(() => {
    if (!aberto) return;
    function aoClicarFora(ev: MouseEvent) {
      if (!raizRef.current?.contains(ev.target as Node)) setAberto(false);
    }
    document.addEventListener('mousedown', aoClicarFora);
    return () => document.removeEventListener('mousedown', aoClicarFora);
  }, [aberto]);

  // `useLayoutEffect`: a medida e a troca de âncora têm de acontecer antes da
  // pintura, senão a lista piscaria no lugar errado por um quadro.
  useLayoutEffect(() => {
    if (!aberto) {
      setAncoraEsquerda(false);
      return;
    }
    const lista = listaRef.current;
    if (lista && lista.getBoundingClientRect().left < MARGEM_DA_JANELA) setAncoraEsquerda(true);
  }, [aberto]);

  useEffect(() => {
    if (!aberto || !focarAoAbrir.current) return;
    focarAoAbrir.current = false;
    const lista = listaRef.current;
    (lista?.querySelector<HTMLElement>('[aria-current="true"]')
      ?? lista?.querySelector<HTMLElement>('.regua-seletor__opcao'))?.focus();
  }, [aberto]);

  if (!criterios.length) return null;

  // Embutidas e criadas em grupos separados: uma régua do edital e uma régua
  // que alguém digitou na terça não têm o mesmo peso, e a lista precisa dizer
  // isso sem legenda.
  const embutidas = criterios.filter((c) => c.embutido !== false);
  const minhas = criterios.filter((c) => c.embutido === false);
  const atual = criterios.find((c) => c.slug === valor);

  function fechar(devolverFoco: boolean) {
    setAberto(false);
    // Sem isso o foco cai no <body> e quem navega por teclado recomeça a
    // tabulação do topo da página.
    if (devolverFoco) botaoRef.current?.focus();
  }

  function escolher(slug: string) {
    onEscolher(slug);
    fechar(true);
  }

  function aoTeclarNoBotao(ev: TecladoReact<HTMLButtonElement>) {
    // Lista já aberta: quem leva o foco para dentro dela é `aoTeclarNaLista`,
    // que o evento alcança logo depois. Armar `focarAoAbrir` aqui o deixaria
    // ligado até a PRÓXIMA abertura — e essa, feita com o mouse, puxaria o foco.
    if (aberto || (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp')) return;
    ev.preventDefault();
    focarAoAbrir.current = true;
    setAberto(true);
  }

  function aoTeclarNaLista(ev: TecladoReact<HTMLDivElement>) {
    if (!aberto) return;
    // Sem `stopPropagation`, de propósito: o `BotaoInfo` escuta o Esc no
    // `document`, e um balão aberto tem de fechar junto com a lista — React
    // delega no contêiner, então parar o evento aqui o esconderia dele.
    if (ev.key === 'Escape') {
      fechar(true);
      return;
    }
    const opcoes = Array.from(
      listaRef.current?.querySelectorAll<HTMLElement>('.regua-seletor__opcao') ?? [],
    );
    // A posição é a da LINHA em foco: o foco também pode estar no "i" dela, e
    // `indexOf` no elemento devolveria -1 e mandaria a seta para o topo.
    const linhaEmFoco = (document.activeElement as HTMLElement | null)?.closest('.regua-seletor__item');
    const i = opcoes.findIndex((o) => o.closest('.regua-seletor__item') === linhaEmFoco);
    const destino =
      ev.key === 'ArrowDown' ? opcoes[Math.min(i + 1, opcoes.length - 1)]
      : ev.key === 'ArrowUp' ? opcoes[Math.max(i - 1, 0)]
      : ev.key === 'Home' ? opcoes[0]
      : ev.key === 'End' ? opcoes[opcoes.length - 1]
      : null;
    if (!destino) return;
    ev.preventDefault();
    destino.focus();
  }

  // Tab para fora fecha. Clique em área morta da lista NÃO: aí o
  // `relatedTarget` é `null`, e quem decide o clique fora é o `mousedown` do
  // documento, que sabe de onde veio o clique.
  function aoPerderOFoco(ev: FocoReact<HTMLDivElement>) {
    const para = ev.relatedTarget as Node | null;
    if (para && !raizRef.current?.contains(para)) setAberto(false);
  }

  function linha(c: CriterioClassificacao) {
    const escolhida = c.slug === valor;
    return (
      <li key={c.slug} className="regua-seletor__item">
        <button
          type="button"
          className={`regua-seletor__opcao${escolhida ? ' regua-seletor__opcao--atual' : ''}`}
          aria-current={escolhida ? 'true' : undefined}
          onClick={() => escolher(c.slug)}
        >
          {c.nome}
        </button>
        <BotaoInfo
          texto={<Explicacao criterio={c} />}
          rotulo={`Como funciona a régua ${c.nome}`}
          largura={LARGURA_EXPLICACAO}
        />
      </li>
    );
  }

  return (
    <div className="regua-seletor" ref={raizRef} onKeyDown={aoTeclarNaLista} onBlur={aoPerderOFoco}>
      <div className="regua-seletor__campo">
        <button
          type="button"
          ref={botaoRef}
          className="painel-criterio regua-seletor__botao"
          aria-label={atual ? `${rotulo}: ${atual.nome}` : rotulo}
          // Botão que expande uma lista de botões, não um `menu` ARIA: com
          // `aria-haspopup` o leitor de tela anunciaria "menu" e esperaria
          // `role="menuitem"` nas linhas, que aqui são botões comuns.
          aria-expanded={aberto}
          aria-controls={aberto ? idLista : undefined}
          onClick={() => setAberto((a) => !a)}
          onKeyDown={aoTeclarNoBotao}
        >
          <span>{atual?.nome ?? 'Escolher régua'}</span>
          <span className="regua-seletor__seta" aria-hidden="true">▾</span>
        </button>
        {/* O "i" da régua em vigor fica à vista: quem quer saber COMO o que está
            na tela foi cortado não deveria ter de abrir a lista para achá-lo. */}
        {atual && (
          <BotaoInfo
            texto={<Explicacao criterio={atual} />}
            rotulo={`Como funciona a régua ${atual.nome}`}
            largura={LARGURA_EXPLICACAO}
          />
        )}
      </div>

      {aberto && (
        <ul
          className={`regua-seletor__lista${ancoraEsquerda ? ' regua-seletor__lista--esquerda' : ''}`}
          id={idLista}
          ref={listaRef}
        >
          {embutidas.map(linha)}

          {minhas.length > 0 && (
            <>
              <li className="regua-seletor__grupo">Minhas réguas</li>
              {minhas.map(linha)}
            </>
          )}

          {onCriar && (
            <li className="regua-seletor__item">
              <button
                type="button"
                className="regua-seletor__opcao"
                onClick={() => {
                  onCriar();
                  fechar(true);
                }}
              >
                + Criar régua…
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

/**
 * O conteúdo do balão do "i". O texto vem de `explicarCriterio` — aqui só se
 * desenha, como no resto do front: quem sabe o que a régua exige é o servidor.
 */
function Explicacao({ criterio }: { criterio: CriterioClassificacao }) {
  const { descricao, exigencias, quandoCorta, desempate } = explicarCriterio(criterio);

  return (
    <div className="regua-info">
      <p className="regua-info__nome">{criterio.nome}</p>
      {descricao && <p className="regua-info__texto">{descricao}</p>}

      {exigencias.length > 0 && (
        <>
          <p className="regua-info__titulo">Exigências</p>
          <ul className="regua-info__lista">
            {exigencias.map((e, i) => (
              // Índice na chave: uma régua criada à mão pode repetir alvo e mínimo.
              // biome-ignore lint/suspicious/noArrayIndexKey: lista fixa, sem reordenação
              <li key={`${i}|${e.alvo}|${e.minimo}`}>
                <strong>{e.alvo}</strong> · {e.minimo}
                {e.eliminatorio && <span className="regua-info__marca">elimina</span>}
                {e.foraDaMedia && <span className="regua-info__marca">fora da média</span>}
              </li>
            ))}
          </ul>
        </>
      )}

      <p className="regua-info__titulo">Quando corta</p>
      <p className="regua-info__texto">{quandoCorta}</p>

      {desempate.length > 0 && (
        <>
          <p className="regua-info__titulo">Desempate, nesta ordem</p>
          <p className="regua-info__texto">{desempate.join(' › ')}</p>
        </>
      )}
    </div>
  );
}
