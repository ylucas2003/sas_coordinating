import { Fragment } from 'react';

// Markdown leve: negrito, itálico, listas e parágrafos. Sem links, imagens
// nem HTML — o texto vem do LLM, e ampliar a gramática ampliaria a superfície
// de injeção sem ganho para o caso de uso.

const RE_MARCACAO = /(\*\*[^*]+\*\*|\*[^*]+\*)/g;

/** Quebra o texto em pedaços, transformando **negrito** e *itálico* em nós. */
function inline(texto: string) {
  return texto.split(RE_MARCACAO).map((pedaco, i) => {
    if (pedaco.startsWith('**') && pedaco.endsWith('**')) {
      return <strong key={i}>{pedaco.slice(2, -2)}</strong>;
    }
    if (pedaco.startsWith('*') && pedaco.endsWith('*') && pedaco.length > 2) {
      return <em key={i}>{pedaco.slice(1, -1)}</em>;
    }
    return <Fragment key={i}>{pedaco}</Fragment>;
  });
}

export function Markdown({ texto }: { texto: string }) {
  const blocos: React.ReactNode[] = [];
  let lista: string[] = [];

  const fecharLista = () => {
    if (!lista.length) return;
    const itens = lista;
    lista = [];
    blocos.push(
      <ul key={`ul-${blocos.length}`} className="chat-md-list">
        {itens.map((item, i) => <li key={i}>{inline(item)}</li>)}
      </ul>,
    );
  };

  for (const linha of texto.split('\n')) {
    const limpa = linha.trim();
    if (!limpa) {
      fecharLista();
      continue;
    }
    const item = limpa.match(/^[-•]\s+(.*)$/);
    if (item) {
      lista.push(item[1]);
    } else {
      fecharLista();
      blocos.push(
        <p key={`p-${blocos.length}`} className="chat-md-p">{inline(limpa)}</p>,
      );
    }
  }
  fecharLista();

  return <>{blocos}</>;
}
