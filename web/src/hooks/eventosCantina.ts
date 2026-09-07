import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';

import { assinarEventos } from '../servicos/eventos';
import type { EventoDoServidor } from '../servicos/eventos';

// Liga o barramento do servidor ao cache do cliente.
//
// ⚠️ **O evento não traz o dado — traz o aviso de que o dado mudou**, e este
// hook o traduz numa invalidação. Empurrar conteúdo pelo stream criaria uma
// segunda fonte da verdade, com serialização e autorização próprias, e as duas
// divergiriam no primeiro campo novo. Um `refetch` a mais custa uma requisição;
// uma cache incoerente custa uma tela que mente.
//
// Isto NÃO substitui o polling do aluno: `useCantinaDoAluno` continua com
// `refetchOnWindowFocus` e o intervalo de 60 s que se autodesliga. O stream é a
// camada rápida; o polling é a rede de segurança para quando ele cai e a
// reconexão ainda não voltou (docs/38 §9).

/** Que chaves cada tipo de evento derruba. */
const CHAVES_POR_TIPO: Record<string, string[][]> = {
  // Cardápio mexe no calendário, no dia e na leitura da coordenação.
  cardapio: [['cantina'], ['coord', 'cantina'], ['me', 'cantina']],
  // Pedido mexe na contagem e na lista do balcão — e no próprio pedido do aluno.
  pedido: [['cantina'], ['coord', 'cantina'], ['me', 'cantina']],
  // Retirada mexe exatamente no mesmo conjunto (docs/40 §5): a leitura do QR
  // muda a contagem de presencial, a lista de quem pediu e o `retiradoEm` do
  // aluno. ⚠️ O evento NÃO carrega o "Bom almoço" pronto — carrega o aviso de
  // refazer `GET /me/cantina`, e a tela decide o texto olhando `retiradoEm`.
  // O galho `['me','retirada']` fica de fora: o token é efêmero e a tela do QR
  // já o renova sozinha; derrubá-lo aqui só gravaria linha no banco à toa.
  retirada: [['cantina'], ['coord', 'cantina'], ['me', 'cantina']],
  // Direito mexe no público da cantina e no que o aluno enxerga.
  direito: [['cantina', 'publico'], ['administracao'], ['me', 'cantina']],
};

/**
 * Assina um dos três streams e invalida o que ele afeta.
 *
 * `caminho` é a rota do stream do público em questão — `/cantina/eventos`,
 * `/me/cantina/eventos` ou `/administracao/cantina/eventos`. Quem recorta o que
 * cada um recebe é o SERVIDOR: filtrar aqui não seria autorização.
 */
export function useEventosDaCantina(caminho: string, ligado = true): void {
  const qc = useQueryClient();

  useEffect(() => {
    if (!ligado) return undefined;
    const controle = new AbortController();

    const aoReceber = (evento: EventoDoServidor) => {
      // `pronto` é o handshake de abertura; não há o que invalidar. Mas vale
      // recarregar uma vez: se o stream caiu e voltou, a tela pode ter perdido
      // eventos no intervalo, e este é o único momento em que dá para saber.
      const chaves = evento.nome === 'pronto'
        ? [['cantina'], ['coord', 'cantina'], ['me', 'cantina']]
        : CHAVES_POR_TIPO[evento.nome];
      if (!chaves) return;
      for (const queryKey of chaves) qc.invalidateQueries({ queryKey });
    };

    void assinarEventos(caminho, aoReceber, controle.signal);
    return () => controle.abort();
  }, [caminho, ligado, qc]);
}
