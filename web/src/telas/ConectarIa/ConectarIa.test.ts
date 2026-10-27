import { createElement } from 'react';
import type { ComponentProps } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { CampoDoCodigo } from './ConectarIa';

// O campo do código no leitor de tela (revisão de 26/10): quando ele está
// marcado como inválido, o PORQUÊ tem de estar no `aria-describedby`, senão
// quem volta ao campo ouve "inválido" e mais nada. E o campo nunca cita um id
// que não está na tela.

function desenhar(p: Partial<ComponentProps<typeof CampoDoCodigo>> = {}): string {
  return renderToStaticMarkup(
    createElement(CampoDoCodigo, {
      id: 'campo',
      codigo: '123',
      formaRecusada: false,
      codigoRecusado: false,
      idDoAvisoDeEnvio: 'aviso-de-envio',
      idDaFalha: null,
      aoMudar: () => {},
      ...p,
    }),
  );
}

const descricao = (html: string): string[] =>
  (/aria-describedby="([^"]*)"/.exec(html)?.[1] ?? '').split(' ').filter(Boolean);

/** O id do parágrafo cujo texto (sem os marcadores do SSR) é `texto`. */
function idDoParagrafo(html: string, texto: string): string | null {
  for (const [, id, corpo] of html.matchAll(/<p id="([^"]+)"[^>]*>(.*?)<\/p>/gs)) {
    if (corpo.replace(/<!-- -->/g, '') === texto) return id;
  }
  return null;
}

describe('CampoDoCodigo', () => {
  it('com a forma recusada, o aviso tem id e o campo o cita, depois do aviso de envio', () => {
    const html = desenhar({ formaRecusada: true });
    const idDaForma = idDoParagrafo(html, 'O código tem 6 dígitos.');
    expect(idDaForma).toBeTruthy();
    expect(descricao(html)).toEqual(['aviso-de-envio', idDaForma]);
    expect(html).toContain('aria-invalid="true"');
  });

  it('com a falha do servidor também na tela, cita as duas, na ordem da leitura', () => {
    const html = desenhar({ formaRecusada: true, idDaFalha: 'falha' });
    const idDaForma = idDoParagrafo(html, 'O código tem 6 dígitos.');
    expect(descricao(html)).toEqual(['aviso-de-envio', idDaForma, 'falha']);
  });

  it('sem aviso aceso, não há parágrafo nem id a citar, e o campo não está inválido', () => {
    const html = desenhar();
    expect(html).not.toContain('O código tem');
    expect(descricao(html)).toEqual(['aviso-de-envio']);
    expect(html).not.toContain('aria-invalid');
  });

  it('o código recusado pelo servidor marca o campo e cita a falha', () => {
    const html = desenhar({ codigoRecusado: true, idDaFalha: 'falha' });
    expect(descricao(html)).toEqual(['aviso-de-envio', 'falha']);
    expect(html).toContain('aria-invalid="true"');
  });

  it('mantém o que o campo já tinha: código de uso único, teclado numérico, sem teto que corte o colado', () => {
    // Atributo de HTML não diferencia maiúscula, e o SSR do React 19 os escreve em camelCase.
    const html = desenhar().toLowerCase();
    expect(html).toContain('autocomplete="one-time-code"');
    expect(html).toContain('inputmode="numeric"');
    expect(html).not.toContain('maxlength');
  });
});
