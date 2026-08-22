// Estado e validação do formulário de nota — compartilhado pelo diálogo de
// edição simples e pela ficha de nota, que têm os mesmos campos.

import { useState } from 'react';
import type { Mudanca } from './DialogoComDiff';

export interface ValoresNota {
  pontuacao: number | null;
  presente: boolean;
  /** A escolha do coordenador na confirmação (docs/18 §2.3). */
  sincronizarCanvas: boolean;
}

export type ResultadoValidacao =
  | { tipo: 'invalido' }
  | { tipo: 'sem-mudancas' }
  | { tipo: 'ok'; valores: ValoresNota; mudancas: Mudanca[] };

interface Args {
  pontuacaoAtual: number | null;
  presenteAtual: boolean;
  notaMaxima: number | null;
  /** Como formatar a pontuação no diff. A edição simples usa nota formatada; a ficha, o valor cru. */
  formatarPontuacao: (n: number | null) => string;
}

export function useFormularioNota({
  pontuacaoAtual, presenteAtual, notaMaxima, formatarPontuacao,
}: Args) {
  const [presente, setPresente] = useState(presenteAtual ?? true);
  const [texto, setTexto] = useState(pontuacaoAtual != null ? String(pontuacaoAtual) : '');
  const [erro, setErro] = useState(false);

  function alterarPresenca(novo: boolean) {
    setPresente(novo);
    if (!novo) {
      // Ausente não tem pontuação: limpa o campo e o estado de erro junto.
      setTexto('');
      setErro(false);
    }
  }

  /**
   * Valida e calcula o que mudou.
   *
   * O resultado distingue "inválido" de "sem mudanças" porque o chamador
   * reage diferente a cada um: inválido mantém o diálogo aberto com o campo
   * marcado; sem mudanças fecha sem chamar a API. Não dá para inferir isso
   * lendo `erro` logo depois — `setErro` só se reflete no próximo render.
   */
  function validar(): ResultadoValidacao {
    setErro(false);
    const cru = texto.trim().replace(',', '.');
    const pontuacao = presente && cru !== '' ? parseFloat(cru) : null;

    if (presente) {
      const invalido =
        cru === '' ||
        Number.isNaN(pontuacao) ||
        (pontuacao as number) < 0 ||
        (notaMaxima != null && (pontuacao as number) > notaMaxima);
      if (invalido) {
        setErro(true);
        return { tipo: 'invalido' };
      }
    }

    const mudancas: Mudanca[] = [];
    const presenteInicial = presenteAtual ?? true;
    if (presente !== presenteInicial) {
      mudancas.push({
        campo: 'Presente',
        de: presenteInicial ? 'Sim' : 'Não',
        para: presente ? 'Sim' : 'Não',
      });
    }
    if (pontuacao !== pontuacaoAtual) {
      mudancas.push({
        campo: 'Pontuação',
        de: formatarPontuacao(pontuacaoAtual),
        para: formatarPontuacao(pontuacao),
      });
    }

    if (!mudancas.length) return { tipo: 'sem-mudancas' };
    // `sincronizarCanvas` é decidido no passo de confirmação, não aqui.
    return { tipo: 'ok', valores: { pontuacao, presente, sincronizarCanvas: false }, mudancas };
  }

  return { presente, alterarPresenca, texto, setTexto, erro, validar };
}
