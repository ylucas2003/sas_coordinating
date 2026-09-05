import { estadoDaFonte, fonte } from '../../../dados/aluno';

// A tarja que impede a superfície mockada de virar invisível.
//
// Todo bloco que não fala com o servidor recebe uma marca no canto — e desde
// 04/09 ela aparece TAMBÉM em produção, para o aluno (docs/35 §10). Até então
// um `if (!import.meta.env.DEV) return null` a desligava fora de
// desenvolvimento: o inventário existia, a marca existia, e quem mais precisava
// dela — a pessoa que lê o número e acredita — era exatamente quem não a via.
//
// ⚠️ O que isso custa está registrado: `xp`, `liga`, `sequencia` e `conquistas`
// são o coração da área do aluno, e carimbar MOCK neles diz ao aluno "o seu XP
// é inventado". É verdade, e é por isso que dói. Ligar a tarja é a decisão de
// contar isso em vez de deixar o aluno descobrir sozinho.
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

// O que cada marca significa para quem está lendo o número — e não para quem
// está lendo o código. É a primeira coisa do `title` e do texto de leitor de
// tela porque, em produção, o público da tarja é o aluno.
const EM_PORTUGUES = {
  mock: 'número de exemplo: este dado ainda não existe no sistema',
  'sem-rota': 'número de exemplo: o dado existe no servidor e ainda não chega nesta tela',
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
  const estado = estadoDaFonte(chave);
  if (estado === 'real') return null;

  const registrada = fonte(chave);
  const rotulo = ROTULO[estado];
  const procedencia = registrada
    ? `${registrada.descricao} · ${registrada.doc}${
        registrada.origemDoDado ? ` · o dado já está em ${registrada.origemDoDado}` : ''
      }`
    : `'${chave}' não está no registro — por isso caiu em MOCK`;
  const explicacao = `${rotulo} — ${EM_PORTUGUES[estado]}. ${procedencia}`;

  const classe = `alu-tarja alu-tarja--${estado === 'mock' ? 'mock' : 'sem-rota'}${
    ponto ? ' alu-tarja--ponto' : ''
  }`;

  return (
    <>
      <span className={classe} title={explicacao} aria-hidden="true">
        {ponto ? '' : rotulo}
      </span>
      {/* A marca visual é decorativa (`aria-hidden`) porque a sigla sozinha não
          se lê, e `title` em `<span>` não é anunciado de forma confiável. Quem
          usa leitor de tela recebe a frase inteira aqui — em produção a tarja
          passou a ser informação para o ALUNO, e informação que só existe para
          quem enxerga não é honestidade, é decoração. */}
      <span className="alu-so-leitor">{`(${EM_PORTUGUES[estado]})`}</span>
    </>
  );
}
