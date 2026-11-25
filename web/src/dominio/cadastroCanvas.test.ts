import { describe, expect, it } from 'vitest';
import {
  OUTRO_DOMINIO, contagemDoLote, frasesDaPrevia, matriculaCompleta, montarEmail, ordenarParaRevisao, podeEnviar, resumoDoCadastro,
  rotuloDoLote, soDigitos, totalDeMatriculas,
} from './cadastroCanvas';
import type {
  LinhaDaPrevia, LoteNoCanvas, PacoteDaSerie, ResultadoDoCadastro, ResultadoDoCurso,
} from '../tipos/cadastroCanvas';

function cursos(...estados: ResultadoDoCurso['estado'][]): ResultadoDoCurso[] {
  return estados.map((estado, i) => ({ id: String(i), nome: `Curso ${i}`, estado }));
}

function resultado(parcial: Partial<ResultadoDoCadastro>): ResultadoDoCadastro {
  return {
    matricula: '12345678', nome: 'Ana', canvas_user_id: '1', conta: 'criada',
    nome_no_canvas: null, email_enviado: true, ano: 2026, serie: 3, sede: 'AD Online',
    cursos: [], completo: true, ...parcial,
  };
}

function linha(parcial: Partial<LinhaDaPrevia>): LinhaDaPrevia {
  return {
    linha: 2, matricula: '12345678', nome: 'Ana', email: 'a@x.com', serie: 3, sede_id: '864',
    sede_nome: 'AD Online', situacao: 'nova', erros: [], avisos: [], nome_no_canvas: null,
    ...parcial,
  };
}

describe('matrícula', () => {
  it('fica só com os dígitos, no máximo oito', () => {
    expect(soDigitos(' 1234-5678 9')).toBe('12345678');
  });
  it('completa é exatamente oito dígitos', () => {
    expect(matriculaCompleta('12345678')).toBe(true);
    expect(matriculaCompleta('1234567')).toBe(false);
  });
});

describe('resumoDoCadastro', () => {
  it('conta nova em tudo', () => {
    const r = resultado({ cursos: cursos('matriculado', 'matriculado', 'matriculado') });
    expect(resumoDoCadastro(r)).toBe('Conta criada · matriculado nos 3 cursos');
  });
  it('a falha vem antes do resto', () => {
    const r = resultado({ cursos: cursos('falhou', 'matriculado', 'matriculado'), completo: false });
    expect(resumoDoCadastro(r)).toBe('Conta criada · 1 curso falhou · 2 matrículas novas');
  });
  it('repetição: só o que faltava', () => {
    const r = resultado({ conta: 'existente', cursos: cursos('ja_estava', 'matriculado', 'ja_estava') });
    expect(resumoDoCadastro(r)).toBe('A conta já existia · 1 matrícula nova · 2 já estavam');
  });
});

describe('lote', () => {
  const pacotes = [
    { serie: 3, cursos: Array.from({ length: 19 }, (_, i) => ({ id: String(i), nome: '' })) },
    { serie: 1, cursos: [{ id: '578', nome: '' }] },
  ] as PacoteDaSerie[];

  it('conta uma matrícula por curso do pacote, sem as linhas com erro', () => {
    const linhas = [linha({}), linha({ serie: 1 }), linha({ situacao: 'erro' })];
    expect(totalDeMatriculas(linhas, pacotes)).toBe(20);
  });

  it('só envia sem erro nenhum e com alguma linha', () => {
    const base = { ano: 2026, linhas: [] };
    expect(podeEnviar({ ...base, resumo: { total: 2, novas: 1, existentes: 1, com_erro: 0, com_aviso: 0 } })).toBe(true);
    expect(podeEnviar({ ...base, resumo: { total: 2, novas: 1, existentes: 0, com_erro: 1, com_aviso: 0 } })).toBe(false);
    expect(podeEnviar(null)).toBe(false);
  });

  it('revisão: erro, depois aviso, depois o resto, cada um na ordem do arquivo', () => {
    const ordenadas = ordenarParaRevisao([
      linha({ linha: 2 }),
      linha({ linha: 3, avisos: ['nome diferente'] }),
      linha({ linha: 4, situacao: 'erro', erros: ['x'] }),
      linha({ linha: 5, situacao: 'erro', erros: ['y'] }),
    ]);
    expect(ordenadas.map((l) => l.linha)).toEqual([4, 5, 3, 2]);
  });

  it('rótulo e contagem do import', () => {
    const lote = {
      estado: 'processando', progresso: 42.4, contas: 108, matriculas: 2052,
      total_erros: 1, total_avisos: 0,
    } as LoteNoCanvas;
    expect(rotuloDoLote(lote)).toBe('processando · 42%');
    expect(rotuloDoLote({ estado: 'concluido_com_avisos', progresso: 100 })).toBe('concluído com avisos');
    expect(contagemDoLote(lote)).toBe('108 contas · 2.052 matrículas · 1 erro');
  });
});

describe('frasesDaPrevia', () => {
  it('singular e plural em cada pedaço', () => {
    const umDeCada = { total: 1, novas: 1, existentes: 1, com_erro: 1, com_aviso: 1 };
    expect(frasesDaPrevia(umDeCada, 1)).toEqual({
      base: '1 linha · 1 conta nova · 1 já existe · 1 matrícula',
      erro: '1 com erro',
      aviso: '1 com aviso',
    });
  });
  it('milhar no formato do Brasil, e sem erro nem aviso quando não há', () => {
    const lote = { total: 108, novas: 100, existentes: 8, com_erro: 0, com_aviso: 0 };
    expect(frasesDaPrevia(lote, 2052)).toEqual({
      base: '108 linhas · 100 contas novas · 8 já existem · 2.052 matrículas',
      erro: null,
      aviso: null,
    });
  });
});

describe('montarEmail', () => {
  it('junta o começo digitado com o domínio do botão', () => {
    expect(montarEmail(' fulano.silva ', 'gmail.com')).toBe('fulano.silva@gmail.com');
  });
  it('com "@" no campo, vale o que foi digitado', () => {
    expect(montarEmail('fulano@gmail.com.br', 'gmail.com')).toBe('fulano@gmail.com.br');
  });
  it('"outro domínio" usa o campo como está', () => {
    expect(montarEmail('fulano@escola.org', OUTRO_DOMINIO)).toBe('fulano@escola.org');
  });
  it('campo vazio não vira "@gmail.com"', () => {
    expect(montarEmail('  ', 'gmail.com')).toBe('');
  });
});
