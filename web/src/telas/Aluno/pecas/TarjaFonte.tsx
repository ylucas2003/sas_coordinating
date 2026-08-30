import { estadoDaFonte, fonte } from '../../../dados/aluno';

// A tarja que impede a superfície mockada de virar invisível.
//
// Em desenvolvimento, todo bloco que não fala com o servidor recebe uma marca
// no canto. Em produção ela não existe — nem o elemento, nem o CSS que o
// posiciona.
//
// ⚠️ O estado vem do `registro.ts`, nunca de uma prop booleana. Se viesse de
// prop, a tarja e o inventário poderiam divergir, e a divergência apareceria
// justamente quando alguém ligasse uma fonte e esquecesse de tirar a marca —
// ou pior, ligasse e esquecesse a marca ligada em outro lugar.
//
// Duas marcas, porque são dois problemas diferentes (docs/29 §A):
//   MOCK      não existe nem dado. Desmockar é inventar produto.
//   SEM ROTA  o servidor já sabe a resposta. Desmockar é uma rota curta.

const ROTULO = {
  mock: 'MOCK',
  'sem-rota': 'SEM ROTA',
} as const;

interface Props {
  chave: string;
  /**
   * Só um ponto, em vez da palavra.
   *
   * Existe para os lugares apertados — a barra de topo do celular, onde a
   * tarja escrita cobria o próprio número que ela deveria estar qualificando.
   * A marca continua existindo e o `title` continua explicando; o que encolhe
   * é a tinta, não a honestidade.
   */
  ponto?: boolean;
}

export function TarjaFonte({ chave, ponto = false }: Props) {
  // `import.meta.env.DEV` é o equivalente do `APP_ENV=dev` no front: o Vite o
  // substitui por `false` no build, e o `if` inteiro sai no tree-shaking.
  if (!import.meta.env.DEV) return null;

  const estado = estadoDaFonte(chave);
  if (estado === 'real') return null;

  const registrada = fonte(chave);
  const rotulo = ROTULO[estado];
  const explicacao = registrada
    ? `${registrada.descricao} · ${registrada.doc}${
        registrada.origemDoDado ? ` · o dado já está em ${registrada.origemDoDado}` : ''
      }`
    : `'${chave}' não está no registro — por isso caiu em MOCK`;

  const classe = `alu-tarja alu-tarja--${estado === 'mock' ? 'mock' : 'sem-rota'}${
    ponto ? ' alu-tarja--ponto' : ''
  }`;

  return (
    <span className={classe} title={`${rotulo} · ${explicacao}`} aria-hidden="true">
      {ponto ? '' : rotulo}
    </span>
  );
}
