import { describe, expect, it } from 'vitest';
import {
  chaveParaBytes,
  descricaoDoAparelho,
  estadoDoAparelho,
  mesmosBytes,
  plataformaDoAparelho,
} from './avisosNoAparelho';
import type { LeituraDoAparelho } from './avisosNoAparelho';

const UA = {
  iphoneSafari:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1',
  iphoneChrome:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0 Mobile/15E148 Safari/604.1',
  ipadComoMac:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15',
  androidChrome:
    'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Mobile Safari/537.36',
  samsung:
    'Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/26.0 Chrome/122.0 Mobile Safari/537.36',
  windowsEdge:
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36 Edg/131.0',
  macChrome:
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36',
  linuxFirefox: 'Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0',
};

describe('plataformaDoAparelho', () => {
  it('reconhece iPhone em qualquer navegador — todos são Safari por baixo', () => {
    expect(plataformaDoAparelho(UA.iphoneSafari)).toBe('ios');
    expect(plataformaDoAparelho(UA.iphoneChrome)).toBe('ios');
  });

  it('o iPad que se apresenta como Mac é iOS pela tela de toque', () => {
    expect(plataformaDoAparelho(UA.ipadComoMac, 5)).toBe('ios');
    expect(plataformaDoAparelho(UA.ipadComoMac, 0)).toBe('desktop');
  });

  it('Android vence o "Linux" do próprio user agent', () => {
    expect(plataformaDoAparelho(UA.androidChrome)).toBe('android');
    expect(plataformaDoAparelho(UA.linuxFirefox)).toBe('desktop');
    expect(plataformaDoAparelho('curl/8.0')).toBe('outra');
  });
});

describe('descricaoDoAparelho', () => {
  it('nomeia aparelho e navegador, na ordem certa de desempate', () => {
    expect(descricaoDoAparelho(UA.windowsEdge, 'desktop', false)).toBe('Windows · Edge');
    expect(descricaoDoAparelho(UA.samsung, 'android', false)).toBe('Android · Samsung Internet');
    expect(descricaoDoAparelho(UA.macChrome, 'desktop', false)).toBe('Mac · Chrome');
    expect(descricaoDoAparelho(UA.linuxFirefox, 'desktop', false)).toBe('Linux · Firefox');
  });

  it('instalado diz "app instalado", que é o que a pessoa reconhece', () => {
    expect(descricaoDoAparelho(UA.iphoneSafari, 'ios', true)).toBe('iPhone · app instalado');
    expect(descricaoDoAparelho(UA.ipadComoMac, 'ios', true)).toBe('iPad · app instalado');
  });
});

describe('estadoDoAparelho', () => {
  const base: LeituraDoAparelho = {
    servidorAtivo: true,
    temPush: true,
    plataforma: 'android',
    instalado: false,
    permissao: 'default',
    inscrito: false,
  };

  it('servidor sem chave some com a seção, seja qual for o aparelho', () => {
    expect(estadoDoAparelho({ ...base, servidorAtivo: false, permissao: 'granted', inscrito: true })).toBe('desligado');
  });

  it('iPhone numa aba: ensinar a instalar, não oferecer botão morto', () => {
    expect(estadoDoAparelho({ ...base, plataforma: 'ios', temPush: false, instalado: false })).toBe('precisa-instalar');
  });

  it('iPhone instalado e ainda sem PushManager é iOS antigo', () => {
    expect(estadoDoAparelho({ ...base, plataforma: 'ios', temPush: false, instalado: true })).toBe('sem-suporte');
    expect(estadoDoAparelho({ ...base, temPush: false })).toBe('sem-suporte');
  });

  it('negado é bloqueado, mesmo com inscrição velha no navegador', () => {
    expect(estadoDoAparelho({ ...base, permissao: 'denied', inscrito: true })).toBe('bloqueado');
  });

  it('ativo só com permissão E inscrição', () => {
    expect(estadoDoAparelho({ ...base, permissao: 'granted', inscrito: true })).toBe('ativo');
    expect(estadoDoAparelho({ ...base, permissao: 'granted', inscrito: false })).toBe('inativo');
    expect(estadoDoAparelho(base)).toBe('inativo');
  });
});

describe('chaveParaBytes', () => {
  it('decodifica base64url sem preenchimento', () => {
    expect(Array.from(chaveParaBytes('AQID_-8'))).toEqual([1, 2, 3, 255, 239]);
  });

  it('a chave VAPID tem 65 bytes e começa em 0x04', () => {
    const bytes = chaveParaBytes('BP4z9KsN6nGRTbVYI_c7VJSPQTBtkgcy27mlmlMoZIIgDll6e3vCYLocInmYWAmS6TlzAC8wEqKK6PBru3jl7A8');
    expect(bytes.length).toBe(65);
    expect(bytes[0]).toBe(4);
  });
});

describe('mesmosBytes', () => {
  it('compara ArrayBuffer e visão com os bytes da chave', () => {
    const chave = new Uint8Array([4, 1, 2]);
    expect(mesmosBytes(new Uint8Array([4, 1, 2]).buffer, chave)).toBe(true);
    expect(mesmosBytes(new Uint8Array([9, 4, 1, 2]).subarray(1), chave)).toBe(true);
    expect(mesmosBytes(new Uint8Array([4, 1, 3]).buffer, chave)).toBe(false);
    expect(mesmosBytes(null, chave)).toBe(false);
  });
});
