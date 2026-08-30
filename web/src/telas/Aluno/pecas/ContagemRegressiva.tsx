import type { ProximoSimulado } from '../../../dados/aluno';
import { diasAte, fmtDataLonga, fracaoDoIntervalo } from './formato';

// A contagem regressiva para o próximo simulado.
//
// É o gancho diário do produto inteiro, e substitui a chama que acelera do
// Duolingo (docs/26 §2). A diferença é que esta urgência é VERDADEIRA: o
// simulado tem data, a data está no `evento_agenda`, e o e-mail da véspera já
// sai desde a Sprint 1. Nada aqui é inventado para criar ansiedade.
//
// A REGRA 3 do desenho: A CONTAGEM APERTA. Discreta quando faltam semanas,
// ganha peso conforme a data chega, e na véspera é o elemento mais forte da
// tela. Quem faz isso é `--aperto`, de 0 a 1, que o CSS usa para escalar tipo,
// peso de borda e cor — uma variável, não quatro estados codificados à mão.
//
// ⚠️ `prefers-reduced-motion` é respeitado em aluno-tokens.css, que zera as
// transições dentro de `.alu-shell`. O aperto é estático: ele não pisca.

interface Props {
  proximo: ProximoSimulado | null;
  /** No rodapé da coluna direita a peça é menor e sem a barra. */
  compacta?: boolean;
}

export function ContagemRegressiva({ proximo, compacta = false }: Props) {
  if (!proximo) {
    return (
      <p className="alu-vazio">
        Nenhum simulado agendado ainda. Quando a coordenação marcar o próximo, a data aparece aqui.
      </p>
    );
  }

  const dias = diasAte(proximo.data);
  if (dias == null) return null;

  // Aperta nos últimos 14 dias; antes disso é constante e discreta. Catorze e
  // não trinta porque o intervalo entre simulados é de ~3 semanas: apertar
  // desde o primeiro dia seria apertar sempre, que é o mesmo que nunca.
  const aperto = Math.min(1, Math.max(0, (14 - dias) / 14));
  const fracao = fracaoDoIntervalo(proximo.dataAnterior, proximo.data);

  const chamada =
    dias < 0
      ? 'A prova já foi'
      : dias === 0
        ? 'É hoje'
        : dias === 1
          ? 'É amanhã'
          : `Faltam ${dias} dias`;

  const contexto = [proximo.rotulo, proximo.vestibular, proximo.fase && `Fase ${proximo.fase}`]
    .filter(Boolean)
    .join(' · ');

  return (
    <div
      className={`alu-contagem${compacta ? ' alu-contagem--compacta' : ''}`}
      style={{ '--aperto': aperto } as React.CSSProperties}
    >
      <p className="alu-contagem__chamada">
        <strong className="alu-magnitude alu-contagem__numero">
          {dias > 1 ? dias : chamada}
        </strong>
        {dias > 1 && <span className="alu-contagem__unidade">dias</span>}
      </p>

      <p className="alu-contagem__contexto">{contexto.toUpperCase()}</p>

      {!compacta && (
        <>
          {/* A barra mede o intervalo INTEIRO entre o simulado anterior e o
              próximo — não a "quanto falta". É o que dá noção de onde o aluno
              está dentro do ciclo, em vez de só do prazo. */}
          <div
            className="alu-contagem__barra"
            role="img"
            aria-label={`${Math.round(fracao * 100)}% do intervalo entre um simulado e o outro já passou`}
          >
            <span className="alu-contagem__barra-fill" style={{ width: `${fracao * 100}%` }} />
          </div>
          <p className="alu-contagem__data">{fmtDataLonga(proximo.data)}</p>
        </>
      )}
    </div>
  );
}
