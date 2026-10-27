import { describe, expect, it } from 'vitest';

import { destinoInterno, enderecoDoLogin } from './voltaDoLogin';

describe('destinoInterno', () => {
  it('aceita caminho interno com a query string inteira', () => {
    // O link aberto numa aba nova chega sem sessão (`sessionStorage` é por
    // aba); sem a query, a volta levaria à tela certa com o recorte errado.
    expect(destinoInterno('/alunos/A023?aba=provas&ciclo=3')).toBe('/alunos/A023?aba=provas&ciclo=3');
  });

  it('aceita caminho interno com âncora', () => {
    expect(destinoInterno('/painel#alertas')).toBe('/painel#alertas');
  });

  it.each([
    ['URL absoluta', 'https://sas-falso.com/login'],
    ['URL absoluta sem barra no começo', 'sas-falso.com'],
    ['relativa ao protocolo', '//sas-falso.com/conectar-ia'],
    ['barra invertida logo depois da primeira', '/\\sas-falso.com'],
    ['barra invertida no meio', '/painel\\..\\..\\x'],
    ['tab entre as barras', '/\t/sas-falso.com'],
    ['quebra de linha entre as barras', '/\n/sas-falso.com'],
    ['javascript:', 'javascript:alert(1)'],
    ['vazio', ''],
  ])('recusa %s', (_caso, proximo) => {
    expect(destinoInterno(proximo)).toBeNull();
  });

  it('recusa o caminho que só vira relativo ao protocolo DEPOIS de normalizado', () => {
    // `/..//x` passa pelas recusas da entrada; quem o transforma em `//x` é o
    // parser, ao resolver o `..`. Conferir só a entrada deixaria passar.
    expect(destinoInterno('/..//sas-falso.com')).toBeNull();
    expect(destinoInterno('/.//sas-falso.com')).toBeNull();
  });

  it('recusa ausência', () => {
    expect(destinoInterno(null)).toBeNull();
    expect(destinoInterno(undefined)).toBeNull();
  });

  it('recusa voltar para o próprio login, que seria laço', () => {
    expect(destinoInterno('/login')).toBeNull();
    expect(destinoInterno('/login?proximo=%2Fpainel')).toBeNull();
    expect(destinoInterno('/login/canvas')).toBeNull();
    expect(destinoInterno('/login-cantina')).toBeNull();
  });

  it('recusa o login escrito do jeito que o roteador também casa', () => {
    // O react-router casa rota sem diferenciar maiúscula, decodifica cada
    // segmento e aceita barra no fim: os três abrem o login, e voltar para
    // eles depois de entrar seria o laço.
    expect(destinoInterno('/LOGIN')).toBeNull();
    expect(destinoInterno('/Login-Cantina')).toBeNull();
    expect(destinoInterno('/%6Cogin')).toBeNull();
    expect(destinoInterno('/login/')).toBeNull();
    expect(destinoInterno('/LOGIN/Canvas')).toBeNull();
  });

  it('não confunde rota que só COMEÇA com "login" com o login', () => {
    expect(destinoInterno('/loginho')).toBe('/loginho');
    expect(destinoInterno('/LOGINHO')).toBe('/LOGINHO');
    // `/` codificado dentro do segmento não vira separador para o roteador.
    expect(destinoInterno('/login%2Fx')).toBe('/login%2Fx');
  });

  it('codificação quebrada não derruba a regra', () => {
    expect(destinoInterno('/painel/%E0%A4%A')).toBe('/painel/%E0%A4%A');
  });

  it('devolve o caminho normalizado, não o texto cru', () => {
    expect(destinoInterno('/administracao/../alunos/A023')).toBe('/alunos/A023');
  });
});

describe('enderecoDoLogin', () => {
  it('guarda o caminho de volta codificado', () => {
    const endereco = enderecoDoLogin('/ciclos/ita-2026-3?materia=fisica&corte=abaixo');
    expect(endereco).toBe('/login?proximo=%2Fciclos%2Fita-2026-3%3Fmateria%3Dfisica%26corte%3Dabaixo');
    // E a ida e volta preserva a query inteira — é o que o `Login` lê.
    const proximo = new URLSearchParams(endereco.split('?')[1]).get('proximo');
    expect(destinoInterno(proximo)).toBe('/ciclos/ita-2026-3?materia=fisica&corte=abaixo');
  });

  it('não pendura "/" na URL: é o destino padrão de qualquer forma', () => {
    expect(enderecoDoLogin('/')).toBe('/login');
  });

  it('não guarda destino recusado', () => {
    expect(enderecoDoLogin('//sas-falso.com')).toBe('/login');
    expect(enderecoDoLogin('/login')).toBe('/login');
  });
});
