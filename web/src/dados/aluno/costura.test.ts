// A costura tem de se defender sozinha.
//
// Os documentos dizem "nenhuma tela importa mocks.ts" e "toda fonte tem entrada
// no registro". Regra escrita em documento é regra que envelhece; estes testes
// são a mesma regra, executável — e o custo de mantê-los é zero enquanto
// ninguém tenta furá-la.

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import { FONTES, estadoDaFonte, fontesPorEstado } from './registro';

const AQUI = dirname(fileURLToPath(import.meta.url));
const SRC = join(AQUI, '..', '..');

function arquivosDe(raiz: string, extensoes: string[]): string[] {
  const achados: string[] = [];
  const visitar = (caminho: string) => {
    for (const nome of readdirSync(caminho)) {
      const cheio = join(caminho, nome);
      if (statSync(cheio).isDirectory()) visitar(cheio);
      else if (extensoes.some((ext) => nome.endsWith(ext))) achados.push(cheio);
    }
  };
  visitar(raiz);
  return achados;
}

describe('registro de fontes', () => {
  it('não tem chave repetida', () => {
    const chaves = FONTES.map((f) => f.chave);
    expect(new Set(chaves).size).toBe(chaves.length);
  });

  it("'sem-rota' diz onde o dado está, qual rota o entregaria e quanto custa", () => {
    // É o que torna a tabela 2 do docs/30 uma lista de tarefas em vez de um
    // relatório: sem `origemDoDado` ninguém sabe por onde começar, e sem
    // `esforco` a tabela não tem como ser ordenada por esforço crescente.
    for (const f of fontesPorEstado('sem-rota')) {
      expect(f.origemDoDado, `${f.chave} sem origemDoDado`).toBeTruthy();
      expect(f.rotaFutura, `${f.chave} sem rotaFutura`).toBeTruthy();
      expect(f.esforco, `${f.chave} sem esforço`).toBeTruthy();
    }
  });

  it("'mock' diz do que depende", () => {
    for (const f of fontesPorEstado('mock')) {
      expect(f.depende, `${f.chave} sem depende`).toBeTruthy();
    }
  });

  it("'real' não finge ter origem alternativa", () => {
    // `origemDoDado` só existe para explicar um dado que a API ainda não
    // devolve. Numa fonte real ele seria ruído que confunde a leitura do doc.
    for (const f of fontesPorEstado('real')) {
      expect(f.origemDoDado, `${f.chave} é real e tem origemDoDado`).toBeUndefined();
      expect(f.depende, `${f.chave} é real e tem depende`).toBeUndefined();
    }
  });

  it('toda fonte aponta um documento e pelo menos uma tela', () => {
    for (const f of FONTES) {
      expect(f.doc, `${f.chave} sem doc`).toBeTruthy();
      expect(f.telas.length, `${f.chave} sem tela`).toBeGreaterThan(0);
      expect(f.descricao, `${f.chave} sem descrição`).toBeTruthy();
    }
  });

  it('chave desconhecida cai em mock, não em real', () => {
    // Falhar para o lado de marcar demais: uma tarja a mais é visível e se
    // conserta; uma superfície mockada sem tarja vira invisível e é esquecida.
    expect(estadoDaFonte('nao-existe')).toBe('mock');
  });
});

describe('a costura', () => {
  const indice = readFileSync(join(AQUI, 'index.ts'), 'utf8');

  it('só usa chaves de mock que existem no registro', () => {
    const usadas = [...indice.matchAll(/queryKey: \['mock', '([^']+)'\]/g)].map((m) => m[1]);
    expect(usadas.length).toBeGreaterThan(0);
    for (const chave of usadas) {
      const registrada = FONTES.find((f) => f.chave === chave);
      expect(registrada, `'${chave}' é usada no index.ts e não está no registro`).toBeDefined();
      expect(registrada?.estado, `'${chave}' está no index como mock e no registro como real`)
        .not.toBe('real');
    }
  });

  it('registra toda fonte não-real que o index consome', () => {
    const usadas = new Set(
      [...indice.matchAll(/queryKey: \['mock', '([^']+)'\]/g)].map((m) => m[1]),
    );
    // Fontes que o front ainda não consome em lugar nenhum são dívida de
    // documentação, não de código — mas têm de ser deliberadas.
    const naoConsumidas = FONTES.filter(
      (f) => f.estado !== 'real' && !usadas.has(f.chave),
    ).map((f) => f.chave);

    // Estas não têm hook porque não são leitura de servidor: são regra pura
    // aplicada sobre dado real (`ordenarFilaDeTreino`, `resumoDoTreino`),
    // catálogo do chat, ou afordância sem funcionalidade.
    //
    // `respostaNoTreino` SAIU desta lista em 02/09: virou real com a migration
    // 0042 e é gravada por `useAtualizarEstudo`, a mesma mutação do cartão.
    // `importanciaDoAssunto` ENTROU: a decisão de 02/09 foi ranquear por
    // incidência bruta, sem ponderação por recência, e a tela que a consumia
    // ("O que mais cai") foi apagada. Ela sobrevive só como heurística interna
    // da fila de treino, sem hook.
    expect(naoConsumidas.sort()).toEqual(
      [
        'acertoPorAssunto',
        'artefatosDoTioLeo',
        'escolhaDaFilaDeTreino',
        'esquadrilha',
        'formulaMatematica',
        'ganchoDeRetorno',
        'importanciaDoAssunto',
      ].sort(),
    );
  });
});

describe('nenhuma tela toca no dado falso', () => {
  const telas = arquivosDe(join(SRC, 'telas'), ['.tsx', '.ts']).filter(
    (a) => !a.endsWith('.test.ts') && !a.endsWith('.test.tsx'),
  );

  it('nenhum arquivo de tela importa mocks.ts', () => {
    const infratores = telas.filter((arquivo) => {
      const fonte = readFileSync(arquivo, 'utf8');
      return /from\s+['"][^'"]*dados\/aluno\/mocks['"]/.test(fonte);
    });
    expect(infratores).toEqual([]);
  });

  it('nenhum arquivo de tela importa reais.ts, mocks.ts ou registro.ts direto', () => {
    // Passar por cima do `index.ts` é o que faz a troca de mock por fetch deixar
    // de ser uma linha: cada atalho vira um lugar a mais para procurar.
    const infratores = telas.filter((arquivo) => {
      const fonte = readFileSync(arquivo, 'utf8');
      return /from\s+['"][^'"]*dados\/aluno\/(reais|mocks|registro)['"]/.test(fonte);
    });
    expect(infratores).toEqual([]);
  });
});
