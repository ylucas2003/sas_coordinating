import { describe, expect, it } from 'vitest';
import {
  etapaMaisAvancada, formatarBytes, mesclarEventos, porcentagem, toneNivel, toneStatus,
} from './importacao';
import type { EventoUpload } from './importacao';

const ev = (mensagem: string, criado_em = '2026-03-01T10:00:00'): EventoUpload =>
  ({ nivel: 'info', mensagem, criado_em });

describe('porcentagem', () => {
  it('upload de bytes ocupa a faixa 0-30%', () => {
    expect(porcentagem('uploading', { enviado: 0, total: 100 }, 0)).toBe(0);
    expect(porcentagem('uploading', { enviado: 50, total: 100 }, 0)).toBe(15);
    expect(porcentagem('uploading', { enviado: 100, total: 100 }, 0)).toBe(30);
  });

  it('arquivo de tamanho zero não divide por zero', () => {
    expect(porcentagem('uploading', { enviado: 0, total: 0 }, 0)).toBe(0);
  });

  it('processamento ocupa 30-95%, deixando os 5% finais para o "concluído"', () => {
    expect(porcentagem('processando', { enviado: 0, total: 0 }, 0)).toBe(30);
    expect(porcentagem('processando', { enviado: 0, total: 0 }, 10)).toBe(95);
  });

  it('sucesso é 100% e erro congela onde parou', () => {
    expect(porcentagem('sucesso', { enviado: 0, total: 0 }, 0)).toBe(100);
    expect(porcentagem('erro', { enviado: 0, total: 0 }, 0, 62)).toBe(62);
  });
});

describe('mesclarEventos', () => {
  it('acrescenta só o que ainda não foi visto', () => {
    const atuais = [ev('a'), ev('b')];
    const r = mesclarEventos(atuais, [ev('b'), ev('c')]);
    expect(r.map((e) => e.mensagem)).toEqual(['a', 'b', 'c']);
  });

  // Mesma mensagem em instantes diferentes são eventos diferentes.
  it('distingue mensagens iguais com horários diferentes', () => {
    const r = mesclarEventos([ev('igual', '10:00')], [ev('igual', '10:01')]);
    expect(r).toHaveLength(2);
  });

  it('não muta a lista recebida', () => {
    const atuais = [ev('a')];
    mesclarEventos(atuais, [ev('b')]);
    expect(atuais).toHaveLength(1);
  });
});

describe('etapaMaisAvancada', () => {
  it('lê a maior etapa anunciada, não a última', () => {
    const r = etapaMaisAvancada([
      ev('ETAPA 1/10: lendo planilha'),
      ev('ETAPA 4/10: gravando notas'),
      ev('ETAPA 2/10: validando'),
    ]);
    expect(r).toEqual({ etapa: 4, descricao: 'gravando notas' });
  });

  it('ignora mensagens que não seguem o formato', () => {
    expect(etapaMaisAvancada([ev('só um aviso qualquer')])).toBeNull();
    expect(etapaMaisAvancada([])).toBeNull();
  });
});

describe('formatação', () => {
  it('bytes em B, KB e MB', () => {
    expect(formatarBytes(500)).toBe('500 B');
    expect(formatarBytes(2048)).toBe('2.0 KB');
    expect(formatarBytes(5 * 1024 * 1024)).toBe('5.00 MB');
    expect(formatarBytes(null)).toBe('—');
  });

  it('tons por nível e status', () => {
    expect(toneNivel('erro')).toBe('tone-vermelho');
    expect(toneNivel('aviso')).toBe('tone-ambar');
    expect(toneNivel('info')).toBe('tone-navy');
    expect(toneStatus('sucesso')).toBe('tone-verde');
    expect(toneStatus('processando')).toBe('tone-ambar');
  });
});
