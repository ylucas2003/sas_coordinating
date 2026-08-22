// A aba de mensagem — só no casco do aluno (docs/22 §P6, decidido em 22/08).
//
// Tela estática, sem dado e sem requisição: é o único lugar do banco que não
// responde a filtro nenhum, e é de propósito.
//
// ⚠️ SEM A FOTO POR ORA. O retrato (Yan & Ryan, aprovados no ITA, T29) está no
// bucket S3 do projeto de origem e não existe cópia local (docs/22 §0.2).
// Trazê-la é o mesmo procedimento do selo do login: baixar, converter para
// WebP e servir de `web/assets/` — 1,7 MB viraram 11,4 KB lá (docs/21 §12).
// Antes disso não entra: imagem de terceiro na página é a regra 6 do CLAUDE.md
// (dados de menores), e o S3 nem passa pela CSP de produção
// (`img-src 'self' data: blob:`, infra/vps/nginx.conf).
//
// Quando o asset chegar, o lugar dele é um `<figure className="banco-mensagem__foto">`
// entre a segunda e a terceira citação — o CSS já reserva a coluna do meio
// (grid-column 2 / grid-row 1 / 3 a partir de 880px) — e o `style` de
// `grid-template-columns` abaixo sai junto.

const CITACOES = [
  {
    texto:
      'Lembre-se sempre do motivo que o trouxe até aqui — das pessoas que dependem ou ainda dependerão de você, e dos sacrifícios que só você pode enfrentar em nome de algo maior. É isso que será capaz de torná-lo forte o bastante para resistir e, enfim, vencer.',
    autor: 'Yan Lucas',
  },
  {
    texto:
      'Pode-se tirar tudo de um homem exceto uma coisa: a última das liberdades humanas — escolher a própria atitude em qualquer circunstância, escolher o próprio caminho.',
    autor: 'Viktor Frankl',
  },
  {
    texto:
      'Sua trajetória pode não ter começado de forma fácil, mas não é isso que define a sua capacidade. É o restante da sua história. Quem você escolhe ser a cada dia.',
    autor: 'Ryan Nojosa',
  },
  {
    texto:
      'Sua história pode não ter tido um começo muito feliz, mas não é isso que define quem você é. É o restante da sua história. Quem você escolhe ser.',
    autor: 'Kung Fu Panda',
  },
];

export function Mensagem() {
  return (
    <section
      className="banco-mensagem"
      aria-label="Mensagem"
      // Enquanto a foto não chega, a coluna do meio do grid de 880px receberia
      // uma citação no lugar dela. Duas colunas fluidas até lá.
      style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))' }}
    >
      {CITACOES.map((citacao) => (
        <blockquote key={citacao.autor} className="banco-mensagem__citacao">
          <p>{citacao.texto}</p>
          <cite>{citacao.autor}</cite>
        </blockquote>
      ))}
    </section>
  );
}
