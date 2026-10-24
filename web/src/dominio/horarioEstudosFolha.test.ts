import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import type { BlocoDeEstudo } from '../tipos/horarioEstudos';
import {
  PAGINA,
  PALETAS,
  faixaDeHoras,
  misturar,
  montarFolha,
  nomeDoArquivoDoHorario,
  quebrar,
} from './horarioEstudosFolha';
import type { Folha, Medir, Primitiva, Texto } from './horarioEstudosFolha';

const AQUI = dirname(fileURLToPath(import.meta.url));

/** Um medidor de mentira: cada letra tem largura fixa, e o negrito é um pouco mais largo. */
const medir: Medir = (texto, tamanho, peso) => texto.length * tamanho * (peso >= 700 ? 0.58 : 0.52);

function bloco(id: string, dia: number, inicio: string, duracao: number, rotulo = id): BlocoDeEstudo {
  return { id, diaSemana: dia, horaInicio: inicio, duracaoMinutos: duracao, rotulo };
}

// A semana de exemplo do docs/prompts-design-horario-de-estudos.md.
const SEMANA = [
  bloco('seg', 1, '19:00', 90, 'Termodinâmica'),
  bloco('ter', 2, '19:00', 90, 'Estequiometria'),
  bloco('qua', 3, '19:00', 90, 'Análise combinatória'),
  bloco('qui1', 4, '18:00', 60, 'Redação'),
  bloco('qui2', 4, '19:15', 90, 'Revisar meus erros'),
  bloco('sex', 5, '19:00', 90, 'Eletrostática'),
  bloco('sab', 6, '14:00', 120, 'Prova do ITA 2019'),
  bloco('dom', 7, '16:00', 60, 'Inglês'),
];

function folha(blocos = SEMANA, tema: 'dia' | 'noite' = 'dia', extra = {}): Folha {
  const f = montarFolha({ blocos, nome: 'BENNY', geradoEm: new Date(2026, 9, 24), tema, medir, proporcaoDaLogo: 2, ...extra });
  if (!f) throw new Error('a folha deveria existir');
  return f;
}

const textos = (f: Folha) => f.primitivas.filter((p): p is Texto => p.tipo === 'texto');
const retangulos = (f: Folha) => f.primitivas.filter((p) => p.tipo === 'retangulo');

describe('as paletas são as do site — lidas de styles/paleta.css', () => {
  const css = readFileSync(join(AQUI, '..', '..', 'styles', 'paleta.css'), 'utf8');
  const lerHex = (nome: string) => new RegExp(`--${nome}:\\s*(#[0-9a-fA-F]{6})`).exec(css)?.[1].toLowerCase();

  // O nome na folha → o token do site. `marca` não é token: é a cor que o casco dá à logo.
  const TOKENS: Record<string, string> = {
    fundo: 'fundo', superficie: 'superficie', superficie2: 'superficie-2', borda: 'borda',
    acao: 'acao', acaoTexto: 'acao-texto', dado: 'dado', dadoClaro: 'dado-claro',
    magnitude: 'magnitude', texto: 'texto', texto2: 'texto-2',
  };

  for (const tema of ['dia', 'noite'] as const) {
    it.each(Object.entries(TOKENS))(`${tema}: %s é --${tema}-%s`, (campo, token) => {
      const noCss = lerHex(`${tema}-${token}`);
      expect(noCss, `--${tema}-${token} sumiu de paleta.css`).toBeDefined();
      expect(PALETAS[tema][campo as keyof (typeof PALETAS)['dia']]).toBe(noCss);
    });

    it(`${tema}: a grade é --${tema}-grade misturada com o fundo`, () => {
      const achou = new RegExp(`--${tema}-grade:\\s*rgba\\((\\d+),\\s*(\\d+),\\s*(\\d+),\\s*([\\d.]+)\\)`).exec(css);
      expect(achou, `--${tema}-grade sumiu de paleta.css`).not.toBeNull();
      const [, r, g, b, alfa] = achou as RegExpExecArray;
      expect(PALETAS[tema].grade).toBe(misturar(PALETAS[tema].fundo, [Number(r), Number(g), Number(b)], Number(alfa)));
    });
  }

  it('a logo é azul-marinho no dia e branca na noite, como o casco a pinta', () => {
    expect(PALETAS.dia.marca).toBe('#1b3f8b');
    expect(PALETAS.noite.marca).toBe('#ffffff');
  });
});

describe('misturar', () => {
  it('opacidade zero devolve o fundo, e um devolve a cor', () => {
    expect(misturar('#ffffff', [0, 0, 0], 0)).toBe('#ffffff');
    expect(misturar('#ffffff', [0, 0, 0], 1)).toBe('#000000');
    expect(misturar('#000000', [255, 255, 255], 0.5)).toBe('#808080');
  });
});

describe('faixaDeHoras — os MESMOS casos de test_horario_estudos_planilha.py', () => {
  it.each([
    ['19:00', 90, [17, 23]], // a folga se divide: não é 18–24
    ['00:00', 60, [0, 6]], // bate no zero: o que sobrou vai para baixo
    ['22:00', 120, [18, 24]], // bate na meia-noite: o que sobrou vai para cima
    ['23:00', 60, [18, 24]],
    ['08:00', 600, [8, 18]], // já passa do mínimo: não cresce
    ['06:00', 1020, [6, 23]],
  ])('%s por %i min → %j', (inicio, duracao, esperado) => {
    expect(faixaDeHoras([bloco('x', 1, inicio, duracao)])).toEqual(esperado);
  });

  it('cobre o bloco mais cedo e o mais tarde', () => {
    expect(faixaDeHoras([bloco('a', 1, '09:30', 60), bloco('b', 5, '21:15', 90)])).toEqual([9, 23]);
  });
});

describe('montarFolha — a página', () => {
  it('sem bloco não há o que exportar', () => {
    expect(montarFolha({ blocos: [], geradoEm: new Date(), tema: 'dia', medir, proporcaoDaLogo: 2 })).toBeNull();
  });

  it('é uma página A4 deitada', () => {
    expect(folha()).toMatchObject({ largura: 842, altura: 595 });
    expect(PAGINA).toEqual({ largura: 842, altura: 595 });
  });

  it('⚠️ UMA PÁGINA: nada fica fora dela, com a semana de exemplo', () => {
    const f = folha();
    for (const p of f.primitivas) dentroDaPagina(f, p);
  });

  it('⚠️ UMA PÁGINA, no pior caso: 60 blocos, nome e rótulos no limite', () => {
    const longo = 'Revisão geral de eletromagnetismo com resolução de provas antigas do ITA e do IME, cap. 12'.slice(0, 80);
    const blocos = Array.from({ length: 60 }, (_, i) =>
      bloco(`b${i}`, 1 + (i % 7), `${String(6 + Math.floor(i / 7) * 2).padStart(2, '0')}:00`, 45, longo),
    );
    const f = montarFolha({
      blocos, nome: 'N'.repeat(80), geradoEm: new Date(2026, 9, 24), tema: 'noite', medir, proporcaoDaLogo: 2,
    });
    expect(f).not.toBeNull();
    for (const p of (f as Folha).primitivas) dentroDaPagina(f as Folha, p);
  });

  it('o nome muito longo é aparado, e não passa por cima do total da semana', () => {
    const f = folha(SEMANA, 'dia', { nome: 'ALUNO COM UM NOME ABSURDAMENTE COMPRIDO '.repeat(6) });
    const nome = textos(f).find((t) => t.tamanho === 9 && t.cor === PALETAS.dia.texto2 && t.y === 78 && t.x < 400);
    expect(nome).toBeDefined();
    expect(nome?.texto.endsWith('…')).toBe(true);
  });

  it('sem logo a folha sai sem ela, e o título continua inteiro', () => {
    const f = folha(SEMANA, 'dia', { proporcaoDaLogo: null });
    expect(f.primitivas.some((p) => p.tipo === 'imagem')).toBe(false);
    expect(textos(f).some((t) => t.texto === 'Horário de estudos')).toBe(true);
  });

  it('a logo leva a cor da marca do tema', () => {
    for (const tema of ['dia', 'noite'] as const) {
      const logo = folha(SEMANA, tema).primitivas.find((p) => p.tipo === 'imagem');
      expect(logo).toMatchObject({ chave: 'logo', cor: PALETAS[tema].marca });
    }
  });

  it('o cabeçalho traz o total da semana e a data de geração', () => {
    const t = textos(folha()).map((x) => x.texto);
    expect(t).toContain('11h30'); // a semana de exemplo soma 690 minutos
    expect(t).toContain('Gerado em 24/10/2026');
    expect(t).toContain('Horário de estudos');
    expect(t).toContain('BENNY');
  });

  it('as legendas vão em caixa-alta e espaçadas, como o `.alu-olho` do site', () => {
    const f = folha();
    const quando = textos(f).find((t) => t.texto === 'QUANDO');
    expect(quando).toMatchObject({ peso: 700, cor: PALETAS.dia.dado });
    expect(quando?.espacamento).toBeGreaterThan(0);
  });
});

describe('montarFolha — os dois temas', () => {
  /** Toda cor que a folha usa. */
  function coresDe(f: Folha): Set<string> {
    const s = new Set<string>();
    for (const p of f.primitivas) {
      if (p.tipo === 'retangulo') {
        if (p.preenchimento) s.add(p.preenchimento);
        if (p.traco) s.add(p.traco.cor);
      } else s.add(p.cor);
    }
    return s;
  }

  it.each(['dia', 'noite'] as const)('%s: só usa cores da paleta do site', (tema) => {
    const paleta = new Set<string>(Object.values(PALETAS[tema]));
    for (const cor of coresDe(folha(SEMANA, tema))) {
      expect(paleta.has(cor), `${cor} não é do tema ${tema}`).toBe(true);
    }
  });

  it('o fundo da página é o do tema', () => {
    for (const tema of ['dia', 'noite'] as const) {
      const fundo = folha(SEMANA, tema).primitivas[0];
      expect(fundo).toMatchObject({ tipo: 'retangulo', x: 0, y: 0, largura: 842, altura: 595, preenchimento: PALETAS[tema].fundo });
    }
  });

  it('cada tema não deixa nada com a cor EXCLUSIVA do outro', () => {
    // O branco é do fundo do dia E da magnitude da noite — as cores compartilhadas
    // não entram na conta; o que não pode é a noite sair com o fundo claro, ou o
    // dia com o fundo escuro.
    const exclusivas = (de: 'dia' | 'noite', outro: 'dia' | 'noite') =>
      Object.values(PALETAS[de]).filter((c) => !Object.values(PALETAS[outro]).includes(c));
    for (const [tema, outro] of [['noite', 'dia'], ['dia', 'noite']] as const) {
      const usadas = coresDe(folha(SEMANA, tema));
      for (const cor of exclusivas(outro, tema)) expect(usadas.has(cor), `${cor} é só do tema ${outro}`).toBe(false);
    }
    expect(exclusivas('dia', 'noite')).toContain(PALETAS.dia.superficie);
  });

  it('a mesma semana tem a MESMA geometria nos dois temas — só as cores mudam', () => {
    const forma = (f: Folha) =>
      f.primitivas.map((p) => ({ ...p, cor: undefined, preenchimento: undefined, traco: undefined }));
    expect(forma(folha(SEMANA, 'noite'))).toEqual(forma(folha(SEMANA, 'dia')));
  });

  it('o bloco do dia sobe como branco, e o da noite como `superficie-2`', () => {
    const blocoDoDia = retangulos(folha(SEMANA, 'dia')).find((r) => r.traco?.cor === PALETAS.dia.dado);
    const blocoDaNoite = retangulos(folha(SEMANA, 'noite')).find((r) => r.traco?.cor === PALETAS.noite.dado);
    expect(blocoDoDia?.preenchimento).toBe(PALETAS.dia.fundo);
    expect(blocoDaNoite?.preenchimento).toBe(PALETAS.noite.superficie2);
  });
});

describe('montarFolha — os blocos', () => {
  const blocosDa = (f: Folha) => retangulos(f).filter((r) => r.traco?.largura === 1.2);

  it('um retângulo por bloco', () => {
    expect(blocosDa(folha())).toHaveLength(SEMANA.length);
  });

  it('a altura é proporcional à duração, e a posição ao horário', () => {
    // Faixa 17–23 aqui: tudo de 'sexta' em diante muda a faixa, então isola dois blocos.
    const f = folha([bloco('curto', 1, '19:00', 60), bloco('longo', 2, '19:00', 120)]);
    const [curto, longo] = blocosDa(f);
    // O desconto de 1,5pt de folga é igual nos dois: (h + 1,5) é proporcional.
    expect((longo.altura + 1.5) / (curto.altura + 1.5)).toBeCloseTo(2, 5);
    expect(curto.y).toBeCloseTo(longo.y, 5); // começam na mesma hora
  });

  it('cada dia tem a sua coluna, da esquerda para a direita', () => {
    const f = folha([bloco('seg', 1, '19:00', 60), bloco('qua', 3, '19:00', 60), bloco('dom', 7, '19:00', 60)]);
    const [seg, qua, dom] = blocosDa(f);
    expect(seg.x).toBeLessThan(qua.x);
    expect(qua.x).toBeLessThan(dom.x);
    expect(qua.x - seg.x).toBeCloseTo((dom.x - qua.x) / 2, 5); // colunas de largura igual
  });

  it('blocos encostados continuam sendo dois retângulos separados', () => {
    const f = folha([bloco('a', 4, '18:00', 60), bloco('b', 4, '19:00', 90)]);
    const [a, b] = blocosDa(f);
    expect(a.y + a.altura).toBeLessThan(b.y);
  });

  it('o horário de um bloco aparece escrito dentro dele', () => {
    const t = textos(folha()).map((x) => x.texto);
    expect(t).toContain('19:00–20:30');
    expect(t).toContain('19:15–20:45');
  });

  it('o texto de um bloco é cortado na caixa dele, nunca vaza para o vizinho', () => {
    for (const t of textos(folha()).filter((x) => x.recorte)) {
      const r = t.recorte as NonNullable<Texto['recorte']>;
      expect(t.x).toBeGreaterThanOrEqual(r.x);
      expect(t.x + medir(t.texto, t.tamanho, t.peso)).toBeLessThanOrEqual(r.x + r.largura);
    }
  });

  it('o rótulo de 80 caracteres quebra em linhas, inteiro, dentro do bloco', () => {
    const rotulo = 'Revisão geral de eletromagnetismo com resolução de provas antigas do ITA e IME';
    const f = folha([bloco('a', 1, '19:00', 120, rotulo)]);
    const linhas = textos(f).filter((t) => t.peso === 700 && t.recorte);
    expect(linhas.length).toBeGreaterThan(1);
    // Cabe INTEIRO: o bloco de 2h tem altura de sobra, e cortar o que cabe seria perder texto.
    expect(linhas.map((l) => l.texto).join(' ')).toBe(rotulo);
    for (const l of linhas) {
      const r = l.recorte as NonNullable<Texto['recorte']>;
      expect(l.y).toBeLessThanOrEqual(r.y + r.altura);
    }
  });

  it('um bloco de 15 minutos numa grade longa encolhe a fonte, e some o texto se nem assim couber', () => {
    // 06:00 às 23:00 = 17h de grade: 15 min ≈ 6pt de altura.
    const f = folha([bloco('longo', 1, '06:00', 60, 'Cedo'), bloco('tarde', 2, '22:00', 60, 'Tarde'), bloco('curto', 3, '12:00', 15, 'Curto')]);
    const rotuloCurto = textos(f).find((t) => t.texto === 'Curto');
    if (rotuloCurto) expect(rotuloCurto.tamanho).toBeLessThanOrEqual(6.5);
    const [, , c] = retangulos(f).filter((r) => r.traco?.largura === 1.2);
    expect(c.altura).toBeLessThan(10);
    for (const p of f.primitivas) dentroDaPagina(f, p);
  });

  it('o bloco alto ganha letra grande, e o curto, letra menor — o mesmo rótulo', () => {
    // Duas âncoras (06:00 e 22:00) alongam a grade para 17h: sem elas, numa semana de um
    // bloco só, a grade tem 6h e até 30 minutos ficam altos o bastante para 11pt.
    const ancoras = [bloco('cedo', 2, '06:00', 30, 'Cedo'), bloco('tarde', 3, '22:00', 60, 'Tarde')];
    const tamanhoDe = (b: BlocoDeEstudo) =>
      textos(folha([b, ...ancoras])).find((t) => t.texto === 'Eletro')?.tamanho;
    const alto = tamanhoDe(bloco('a', 1, '10:00', 240, 'Eletro'));
    const curto = tamanhoDe(bloco('b', 1, '10:00', 30, 'Eletro'));
    expect(alto).toBe(11);
    // Numa grade de 17h, 30 minutos são ~10pt de altura: o texto encolhe até caber.
    expect(curto).toBeDefined();
    expect(curto as number).toBeLessThan(alto as number);
  });

  it('nunca parte uma palavra no meio para ganhar tamanho: escolhe um corpo menor', () => {
    // "eletromagnetismo" a 11pt é mais larga que a coluna; a 9,5pt ainda é; a 8,5pt cabe.
    const f = folha([bloco('a', 1, '19:00', 180, 'eletromagnetismo')]);
    const linhas = textos(f).filter((t) => t.peso === 700 && t.recorte);
    expect(linhas.map((l) => l.texto)).toEqual(['eletromagnetismo']);
    expect(linhas[0].tamanho).toBeLessThan(11);
  });

  it('rótulo longo que não cabe inteiro vai a 7,5pt com reticências — e não a 11pt cortado na primeira palavra', () => {
    const longo = 'Revisão geral de eletromagnetismo com resolução de provas antigas do ITA e IME, cap. 12 ao 18';
    const f = folha([bloco('a', 1, '19:00', 30, longo)]);
    const linhas = textos(f).filter((t) => t.peso === 700 && t.recorte);
    expect(linhas.length).toBeGreaterThanOrEqual(1);
    expect(linhas.every((l) => l.tamanho <= 7.5)).toBe(true);
    expect(linhas.at(-1)?.texto.endsWith('…')).toBe(true);
  });

  it('a hora só aparece no bloco quando sobra altura depois do rótulo', () => {
    // 30 min a ~67pt/h = 33pt de altura: cabe rótulo + hora. 15 min ≈ 17pt: só o rótulo.
    const f = folha([bloco('a', 1, '19:00', 30, 'A'), bloco('b', 2, '19:00', 15, 'B')]);
    const t = textos(f).map((x) => x.texto);
    expect(t).toContain('19:00–19:30');
    expect(t).not.toContain('19:00–19:15');
  });
});

describe('quebrar', () => {
  const m: Medir = (t) => t.length * 5;

  it('quebra nas palavras', () => {
    expect(quebrar('um dois tres quatro', 50, 10, 500, m, 5)).toEqual(['um dois', 'tres', 'quatro']);
  });

  it('parte a palavra que é maior que a linha inteira', () => {
    const l = quebrar('abcdefghijklmnopqrst', 50, 10, 500, m, 5);
    expect(l.length).toBeGreaterThan(1);
    expect(l.every((x) => m(x, 10, 500) <= 50)).toBe(true);
    expect(l.join('')).toBe('abcdefghijklmnopqrst');
  });

  it('termina em reticências quando passa do limite de linhas', () => {
    const l = quebrar('um dois tres quatro cinco seis', 50, 10, 500, m, 2);
    expect(l).toHaveLength(2);
    expect(l[1].endsWith('…')).toBe(true);
    expect(l.every((x) => m(x, 10, 500) <= 50)).toBe(true);
  });

  it('sem linha disponível não devolve nada', () => {
    expect(quebrar('qualquer', 50, 10, 500, m, 0)).toEqual([]);
  });

  it('texto vazio não vira linha', () => {
    expect(quebrar('   ', 50, 10, 500, m, 3)).toEqual([]);
  });
});

describe('nomeDoArquivoDoHorario', () => {
  const dia = new Date(2026, 9, 24);

  it('leva o nome sem acento, o tema e a data', () => {
    expect(nomeDoArquivoDoHorario('João da Conceição', 'noite', dia, 'pdf')).toBe(
      'horario-de-estudos-joao-da-conceicao-noite-2026-10-24.pdf',
    );
  });

  it('sem nome, o nome some', () => {
    expect(nomeDoArquivoDoHorario('', 'dia', dia, 'png')).toBe('horario-de-estudos-dia-2026-10-24.png');
    expect(nomeDoArquivoDoHorario(null, 'dia', dia, 'png')).toBe('horario-de-estudos-dia-2026-10-24.png');
  });

  it('o claro e o escuro do mesmo dia não se sobrescrevem', () => {
    expect(nomeDoArquivoDoHorario('Ana', 'dia', dia, 'png')).not.toBe(nomeDoArquivoDoHorario('Ana', 'noite', dia, 'png'));
  });

  it('usa a data LOCAL: às 22h de 24/10 o arquivo ainda é de 24/10', () => {
    // `toISOString` daria 25/10 em UTC-3 depois das 21h.
    expect(nomeDoArquivoDoHorario('Ana', 'dia', new Date(2026, 9, 24, 22, 30), 'png')).toContain('2026-10-24');
  });

  it('não deixa caractere estranho no nome do arquivo', () => {
    const nome = nomeDoArquivoDoHorario('../../etc/passwd <script>', 'dia', dia, 'pdf');
    expect(nome).toMatch(/^[a-z0-9.-]+$/);
    expect(nome).not.toContain('..');
  });
});

// ─── Auxiliar ─────────────────────────────────────────────────────────────

/** ⚠️ A garantia de "uma página": toda primitiva cabe na A4 deitada. */
function dentroDaPagina(f: Folha, p: Primitiva): void {
  const { largura: L, altura: A } = f;
  const d = (v: number, lo: number, hi: number, o: string) => {
    expect(v, `${p.tipo} ${o}`).toBeGreaterThanOrEqual(lo - 0.01);
    expect(v, `${p.tipo} ${o}`).toBeLessThanOrEqual(hi + 0.01);
  };
  switch (p.tipo) {
    case 'retangulo':
    case 'imagem':
      d(p.x, 0, L, 'x');
      d(p.y, 0, A, 'y');
      d(p.x + p.largura, 0, L, 'x+largura');
      d(p.y + p.altura, 0, A, 'y+altura');
      break;
    case 'linha':
      d(p.x1, 0, L, 'x1'); d(p.x2, 0, L, 'x2'); d(p.y1, 0, A, 'y1'); d(p.y2, 0, A, 'y2');
      break;
    case 'texto': {
      d(p.x, 0, L, 'x');
      d(p.y, 0, A, 'baseline');
      if (!p.recorte) {
        const w = medir(p.texto, p.tamanho, p.peso) + (p.espacamento ?? 0) * Math.max(0, p.texto.length - 1);
        d(p.x + w, 0, L, `fim de "${p.texto.slice(0, 20)}"`);
      }
    }
  }
}
