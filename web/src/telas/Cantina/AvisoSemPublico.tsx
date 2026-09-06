import { ROTULO_DA_REFEICAO } from '../../dominio/cantina';
import { usePublicoDaCantina } from '../../hooks/cantina';
import type { Refeicao } from '../../tipos/cantina';

// "Publiquei e ninguém vê" — a terceira causa, e a última que ainda era muda.
//
// O incidente de 06/09 mostrou que o produto sabia por que o cardápio não
// chegava ao aluno e não dizia. Duas causas viraram impossíveis (cardápio em
// dia passado, prazo já vencido). Esta não pode virar impossível, então tem de
// virar VISÍVEL: o cardápio está perfeito e simplesmente não tem público,
// porque a coordenação ainda não concedeu o direito àquela refeição.
//
// ⚠️ **Aviso, nunca impedimento.** Publicar antes de a coordenação conceder é
// ordem de trabalho legítima — a cantina monta a semana, a coordenação libera
// os alunos, e as duas não se falam no mesmo minuto. Bloquear aqui inverteria
// essa dependência.
//
// Some quando há público, que é o caso normal: um aviso permanente vira
// paisagem e para de ser lido.

interface Props {
  /** Quais refeições checar. A tela do dia passa uma; o calendário, as duas. */
  refeicoes: readonly Refeicao[];
}

export function AvisoSemPublico({ refeicoes }: Props) {
  const { data: publico } = usePublicoDaCantina();
  if (!publico) return null;

  const vazias = refeicoes.filter((r) => (publico[r] ?? 0) === 0);
  if (!vazias.length) return null;

  const nomes = vazias.map((r) => ROTULO_DA_REFEICAO[r].toLowerCase());
  const lista = nomes.length === 1 ? nomes[0] : `${nomes[0]} nem ${nomes[1]}`;

  return (
    <p className="cant-aviso" role="status">
      <b>Nenhum aluno pode pedir {lista}.</b> O cardápio até pode ser publicado, mas ninguém vai
      ver: quem libera os alunos é a coordenação, na tela de administração do SAS.
    </p>
  );
}
