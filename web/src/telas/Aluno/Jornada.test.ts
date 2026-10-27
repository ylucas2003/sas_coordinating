import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import type { ZonaEDistancia } from '../../dados/aluno';
import { NOME_DA_MEDIA_DA_ZONA } from '../../dominio/notaContraCorte';
import { HeroDaZona } from './Jornada';

// O topo da Jornada diz QUAL média é (decisão do dono de 26/10): a de
// `/me/zona` é a que conta na régua, e não a do último simulado que as barras
// da Hoje mostram. A frase muda conforme o caso da escada — e o nome tem de
// estar nos quatro, no texto visível E no `aria-label`, senão quem ouve a tela
// continua recebendo um "Sua média é" sem dono.

const BASE: ZonaEDistancia = {
  zona: 'cinzenta',
  media: 4.7,
  corteProximaZona: 5.5,
  corteAtual: 4,
  distancia: 0.8,
  materiaMaisCurta: 'Química',
  regua: 'ITA — Fase 1',
  materias: [],
};

const CASOS: Array<[string, ZonaEDistancia]> = [
  ['abaixo do topo, com distância a medir', BASE],
  ['no topo, medindo a folga', { ...BASE, zona: 'top', corteProximaZona: null, distancia: null }],
  ['no risco, sem corte cruzado', { ...BASE, zona: 'risco', corteAtual: null }],
  [
    'régua sem corte de média (ime-f2)',
    { ...BASE, corteProximaZona: null, corteAtual: null, distancia: null },
  ],
];

function desenhar(zona: ZonaEDistancia): { leitura: string; rotulo: string } {
  const html = renderToStaticMarkup(createElement(HeroDaZona, { zona }));
  const leitura = /<p class="alu-jor-zona__leitura">(.*?)<\/p>/s.exec(html)?.[1] ?? '';
  const rotulo = /aria-label="([^"]*)"/.exec(html)?.[1] ?? '';
  // Sem as tags, a frase como o aluno a lê.
  return { leitura: leitura.replace(/<[^>]+>/g, ''), rotulo };
}

describe('HeroDaZona — o nome da média', () => {
  for (const [caso, zona] of CASOS) {
    it(`${caso}: diz que é a média que conta na régua`, () => {
      const { leitura, rotulo } = desenhar(zona);
      expect(leitura).toContain(`Sua ${NOME_DA_MEDIA_DA_ZONA} é 4,7`);
      expect(rotulo).toContain(`Sua ${NOME_DA_MEDIA_DA_ZONA} é 4,7`);
      expect(leitura).not.toMatch(/Sua média é/);
      expect(rotulo).not.toMatch(/Sua média é/);
    });
  }
});
