import { createElement } from 'react';
import type { ComponentProps } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { ComoConectar } from './ConexoesDeIa';

// O passo a passo de "Como conectar a sua IA", pelo SSR: o que a tela mostra
// antes do primeiro clique, que é o caminho do claude.ai.

const URL_DO_SERVIDOR = 'https://exemplo.test/mcp';

function desenhar(p: Partial<ComponentProps<typeof ComoConectar>> = {}): string {
  return renderToStaticMarkup(
    createElement(ComoConectar, { url: URL_DO_SERVIDOR, emailsConfirmados: null, ...p }),
  ).replace(/<!-- -->/g, '');
}

describe('ComoConectar', () => {
  it('abre no claude.ai, com a escolha marcada e os passos numerados em lista ordenada', () => {
    const html = desenhar();
    expect(html).toContain('Como conectar a sua IA');
    expect(html).toMatch(/aria-pressed="true"[^>]*>claude\.ai ou Claude Desktop</);
    expect(html).toContain('<ol class="ia-guia__passos">');
    expect(html).toContain('Adicione o SAS como conector');
    expect(html).not.toContain('claude mcp list');
  });

  it('o endereço do servidor aparece para copiar', () => {
    const html = desenhar();
    expect(html).toContain(`<code>${URL_DO_SERVIDOR}</code>`);
    expect(html).toContain('Copiar o endereço');
  });

  it('o passo do e-mail diz se já está feito', () => {
    expect(desenhar({ emailsConfirmados: 1 })).toContain('Feito: esta conta tem 1 e-mail confirmado.');
    expect(desenhar({ emailsConfirmados: 0 })).toContain('Ainda falta');
    expect(desenhar()).not.toMatch(/Feito:|Ainda falta/);
  });

  it('o aviso de privacidade do claude.ai vem no fim', () => {
    expect(desenhar()).toContain('Ajudar a melhorar o Claude');
  });
});
