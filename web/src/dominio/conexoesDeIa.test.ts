import { describe, expect, it } from 'vitest';

import {
  DIGITOS_DO_CODIGO,
  EMAIL_MAXIMO,
  IAS_PARA_CONECTAR,
  MENSAGEM_CONTA_DESATIVADA,
  NOME_DO_APP_MAXIMO,
  NOME_MAXIMO,
  REVOGACAO_OAUTH_CORTA_RENOVACAO,
  avisoDaCaixaDoEmail,
  avisoDoCodigoDeConfirmacao,
  avisoDoCodigoPedido,
  cabecalhoDeAutorizacao,
  codigoCompleto,
  comandoDoClaudeCode,
  comoDesfazerAConexao,
  cuidadoDePrivacidade,
  dataCurta,
  destinoDaVolta,
  diasDesde,
  emUmaLinha,
  emailComFormaValida,
  emailDaIaConfirmado,
  estadoDoEmailConfirmado,
  fraseDoProibido,
  fraseDoServidor,
  hostDaVolta,
  leituraDaFalhaDoPedido,
  limparCodigo,
  mensagemDaFalhaDaConfirmacao,
  mensagemDaFalhaDoConsentimento,
  mensagemDaFalhaDoEmailDaIa,
  mensagemDaFalhaDoReenvio,
  nomeDaConexaoValido,
  nomeDoApp,
  normalizarEmail,
  ordenarConexoes,
  ordenarEmailsDaIa,
  passosParaConectar,
  origemLegivel,
  perguntaDeRemocaoDoEmail,
  perguntaDeRevogacao,
  permissaoDeEmitir,
  resumoDasConexoes,
  situacaoDaConexao,
  situacaoLegivel,
  ultimoUsoLegivel,
  vazioDasConexoes,
} from './conexoesDeIa';
import type { ConexaoDeIa, DisponibilidadeDoMcp } from '../tipos/dominio';

// As datas são montadas no fuso LOCAL de quem roda o teste (`new Date(ano,
// mês, dia, …)`) e só então viram ISO: "hoje" e "ontem" são dias de
// calendário locais, e um ISO fixo em UTC daria outro dia num fuso negativo.
const local = (ano: number, mes: number, dia: number, hora = 12, minuto = 0) =>
  new Date(ano, mes - 1, dia, hora, minuto);
const iso = (ano: number, mes: number, dia: number, hora = 12, minuto = 0) =>
  local(ano, mes, dia, hora, minuto).toISOString();

const AGORA = local(2026, 10, 24, 15, 0);

function conexao(p: Partial<ConexaoDeIa> & { id: string }): ConexaoDeIa {
  return {
    nome: 'Claude Code do notebook',
    prefixo: 'sas_mcp_Ab3x',
    origem: 'pessoal',
    cliente: null,
    criadaEm: iso(2026, 10, 1),
    ultimoUsoEm: null,
    expiraEm: null,
    revogadaEm: null,
    dono: { id: 'u1', nome: 'Ana Coordenadora' },
    ...p,
  };
}

describe('nomeDaConexaoValido', () => {
  it('exige de 1 a 80 caracteres depois de aparar', () => {
    expect(nomeDaConexaoValido('Claude Desktop')).toBe(true);
    expect(nomeDaConexaoValido('   ')).toBe(false);
    expect(nomeDaConexaoValido('')).toBe(false);
    expect(nomeDaConexaoValido('x'.repeat(NOME_MAXIMO))).toBe(true);
    expect(nomeDaConexaoValido('x'.repeat(NOME_MAXIMO + 1))).toBe(false);
    // O espaço em volta não conta: é o nome APARADO que vai para o servidor.
    expect(nomeDaConexaoValido(`  ${'x'.repeat(NOME_MAXIMO)}  `)).toBe(true);
  });
});

describe('situacaoDaConexao', () => {
  it('sem revogação nem validade, está ativa', () => {
    expect(situacaoDaConexao(conexao({ id: 'a' }), AGORA)).toBe('ativa');
  });

  it('com validade no futuro, continua ativa', () => {
    expect(situacaoDaConexao(conexao({ id: 'a', expiraEm: iso(2026, 11, 1) }), AGORA)).toBe('ativa');
  });

  it('com validade vencida, expirou', () => {
    expect(situacaoDaConexao(conexao({ id: 'a', expiraEm: iso(2026, 10, 20) }), AGORA)).toBe('expirada');
  });

  it('revogada vence expirada: revogar foi um ato de alguém', () => {
    const c = conexao({ id: 'a', expiraEm: iso(2026, 10, 20), revogadaEm: iso(2026, 10, 22) });
    expect(situacaoDaConexao(c, AGORA)).toBe('revogada');
  });

  it('no OAuth, o conector parado continua ativo enquanto a concessão vive', () => {
    // `expiraEm` é o fim da CONCESSÃO (contrato de 26/10). O conector parado
    // há duas horas tem o acesso de 1 h vencido, e na próxima pergunta renova
    // pelo refresh. Ler isso como "expirou" tirava da tela uma conexão viva, e
    // o botão de revogá-la junto.
    const parado = conexao({
      id: 'a', origem: 'oauth', cliente: 'Claude',
      ultimoUsoEm: iso(2026, 10, 24, 13, 0), expiraEm: iso(2026, 11, 23),
    });
    expect(situacaoDaConexao(parado, AGORA)).toBe('ativa');
  });

  it('no OAuth, passado o fim da concessão, expirou: o refresh já é recusado', () => {
    const c = conexao({ id: 'a', origem: 'oauth', cliente: 'Claude', expiraEm: iso(2026, 10, 20) });
    expect(situacaoDaConexao(c, AGORA)).toBe('expirada');
  });

  it('no OAuth, revogada também vence expirada', () => {
    const c = conexao({
      id: 'a', origem: 'oauth', cliente: 'Claude', expiraEm: iso(2026, 10, 20), revogadaEm: iso(2026, 10, 18),
    });
    expect(situacaoDaConexao(c, AGORA)).toBe('revogada');
  });
});

describe('datas', () => {
  it('conta dias de calendário local, não blocos de 24 horas', () => {
    // 23h50 de ontem é "ontem", embora falte só 15h10 para agora.
    expect(diasDesde(iso(2026, 10, 23, 23, 50), AGORA)).toBe(1);
    // 0h05 de hoje é "hoje".
    expect(diasDesde(iso(2026, 10, 24, 0, 5), AGORA)).toBe(0);
  });

  it('não lê instante quebrado como zero', () => {
    expect(diasDesde('não é data', AGORA)).toBeNull();
    expect(dataCurta('não é data')).toBe('—');
    expect(dataCurta(null)).toBe('—');
  });

  it('formata a data curta no fuso de quem lê', () => {
    expect(dataCurta(iso(2026, 3, 8, 23, 30))).toBe('08/03/2026');
  });
});

describe('ultimoUsoLegivel', () => {
  it.each([
    ['nunca usada', null, 'nunca'],
    ['hoje, com a hora', iso(2026, 10, 24, 14, 32), 'hoje, 14:32'],
    ['ontem, com a hora', iso(2026, 10, 23, 9, 10), 'ontem, 09:10'],
    ['nesta semana, sem a hora', iso(2026, 10, 21), 'há 3 dias'],
    ['mais longe, pela data', iso(2026, 10, 12), '12/10/2026'],
  ])('%s', (_caso, quando, esperado) => {
    expect(ultimoUsoLegivel(quando, AGORA)).toBe(esperado);
  });

  it('instante no futuro (relógio fora de acerto) lê como hoje', () => {
    expect(ultimoUsoLegivel(iso(2026, 10, 24, 15, 2), AGORA)).toBe('hoje, 15:02');
  });
});

describe('situacaoLegivel e origemLegivel', () => {
  it('diz a data que explica o estado', () => {
    expect(situacaoLegivel(conexao({ id: 'a' }), AGORA)).toBe('ativa');
    expect(situacaoLegivel(conexao({ id: 'a', expiraEm: iso(2026, 11, 1) }), AGORA))
      .toBe('ativa · expira em 01/11/2026');
    expect(situacaoLegivel(conexao({ id: 'a', revogadaEm: iso(2026, 10, 22) }), AGORA))
      .toBe('revogada em 22/10/2026');
    expect(situacaoLegivel(conexao({ id: 'a', expiraEm: iso(2026, 10, 20) }), AGORA))
      .toBe('expirou em 20/10/2026');
  });

  it('dá o nome do app só no OAuth', () => {
    expect(origemLegivel(conexao({ id: 'a' }))).toBe('token pessoal');
    expect(origemLegivel(conexao({ id: 'a', origem: 'oauth', cliente: 'Claude' }))).toBe('OAuth · Claude');
    expect(origemLegivel(conexao({ id: 'a', origem: 'oauth', cliente: null }))).toBe('OAuth');
  });

  it('no OAuth, diz que o app renova sozinho, e até quando: o fim da concessão', () => {
    const c = conexao({ id: 'a', origem: 'oauth', cliente: 'Claude', expiraEm: iso(2026, 11, 23) });
    expect(situacaoLegivel(c, AGORA)).toBe('ativa · o app renova o acesso sozinho até 23/11/2026');
    expect(situacaoLegivel({ ...c, expiraEm: null }, AGORA)).toBe('ativa · o app renova o acesso sozinho');
    expect(situacaoLegivel({ ...c, expiraEm: iso(2026, 10, 20) }, AGORA)).toBe('expirou em 20/10/2026');
    expect(situacaoLegivel({ ...c, revogadaEm: iso(2026, 10, 22) }, AGORA)).toBe('revogada em 22/10/2026');
  });

  it('o nome que o app declarou chega à coluna numa linha só', () => {
    const c = conexao({ id: 'a', origem: 'oauth', cliente: 'Claude\n\nOficial do SAS' });
    expect(origemLegivel(c)).toBe('OAuth · Claude Oficial do SAS');
    // Nome feito só de espaço e de invisível é nome nenhum.
    expect(origemLegivel({ ...c, cliente: ' ​\t ' })).toBe('OAuth');
  });
});

describe('ordenarConexoes', () => {
  it('põe as ativas primeiro, da mais nova; depois as encerradas, da que fechou por último', () => {
    const lista = [
      conexao({ id: 'revogada-antes', revogadaEm: iso(2026, 9, 1) }),
      conexao({ id: 'ativa-velha', criadaEm: iso(2026, 8, 1) }),
      conexao({ id: 'expirada-agora', expiraEm: iso(2026, 10, 23) }),
      conexao({ id: 'ativa-nova', criadaEm: iso(2026, 10, 20) }),
    ];
    expect(ordenarConexoes(lista, AGORA).map((c) => c.id)).toEqual([
      'ativa-nova', 'ativa-velha', 'expirada-agora', 'revogada-antes',
    ]);
  });

  it('não mexe na lista que recebeu', () => {
    const lista = [conexao({ id: 'b', criadaEm: iso(2026, 1, 1) }), conexao({ id: 'a' })];
    ordenarConexoes(lista, AGORA);
    expect(lista.map((c) => c.id)).toEqual(['b', 'a']);
  });

  it('a conexão OAuth dentro da concessão fica entre as ativas, onde está o botão de revogar', () => {
    const lista = [
      conexao({ id: 'oauth-encerrada', origem: 'oauth', cliente: 'Claude', expiraEm: iso(2026, 10, 20) }),
      conexao({ id: 'pessoal-expirada', expiraEm: iso(2026, 10, 23) }),
      conexao({
        id: 'oauth-parada', origem: 'oauth', cliente: 'ChatGPT',
        ultimoUsoEm: iso(2026, 10, 24, 13, 0), expiraEm: iso(2026, 11, 23),
      }),
    ];
    expect(ordenarConexoes(lista, AGORA).map((c) => c.id))
      .toEqual(['oauth-parada', 'pessoal-expirada', 'oauth-encerrada']);
  });
});

describe('resumoDasConexoes', () => {
  it('não afirma nada enquanto a lista não chegou', () => {
    expect(resumoDasConexoes(undefined, true, AGORA)).toBeNull();
    // Nem quando só a disponibilidade chegou: "servidor desligado" sem saber
    // das conexões seria meia frase com cara de inteira.
    expect(resumoDasConexoes(undefined, false, AGORA)).toBeNull();
  });

  it('sem conexão nenhuma, deixa o card cair no texto de vazio', () => {
    expect(resumoDasConexoes([], true, AGORA)).toBeNull();
    expect(resumoDasConexoes([], null, AGORA)).toBeNull();
  });

  it('conta as ativas e diz o último uso', () => {
    const lista = [
      conexao({ id: 'a', ultimoUsoEm: iso(2026, 10, 20) }),
      conexao({ id: 'b', ultimoUsoEm: iso(2026, 10, 24, 9, 0) }),
    ];
    expect(resumoDasConexoes(lista, true, AGORA)).toBe('2 ativas · última usada hoje');
  });

  it('com uma só, não fala em "última"', () => {
    const lista = [conexao({ id: 'a', ultimoUsoEm: iso(2026, 10, 21) })];
    expect(resumoDasConexoes(lista, true, AGORA)).toBe('1 ativa · usada há 3 dias');
  });

  it('distingue conexão que nunca foi usada', () => {
    expect(resumoDasConexoes([conexao({ id: 'a' })], true, AGORA)).toBe('1 ativa · nunca usada');
    expect(resumoDasConexoes([conexao({ id: 'a' }), conexao({ id: 'b' })], true, AGORA))
      .toBe('2 ativas · nenhuma usada ainda');
  });

  it('o último uso é só das ativas: a revogada não lê mais', () => {
    const lista = [
      conexao({ id: 'a', ultimoUsoEm: iso(2026, 10, 12) }),
      conexao({ id: 'b', ultimoUsoEm: iso(2026, 10, 24, 9, 0), revogadaEm: iso(2026, 10, 24, 10, 0) }),
    ];
    expect(resumoDasConexoes(lista, true, AGORA)).toBe('1 ativa · usada em 12/10/2026');
  });

  it('só encerradas não é o mesmo que vazio', () => {
    const lista = [
      conexao({ id: 'a', revogadaEm: iso(2026, 10, 1) }),
      conexao({ id: 'b', expiraEm: iso(2026, 10, 2) }),
    ];
    expect(resumoDasConexoes(lista, true, AGORA)).toBe('nenhuma ativa · 2 encerradas');
  });

  it('servidor desligado vem antes de tudo, inclusive sem conexão', () => {
    const lista = [conexao({ id: 'a', ultimoUsoEm: iso(2026, 10, 23, 8, 0) })];
    expect(resumoDasConexoes(lista, false, AGORA)).toBe('servidor desligado · 1 ativa · usada ontem');
    expect(resumoDasConexoes([], false, AGORA)).toBe('servidor desligado');
  });

  it('disponibilidade desconhecida não vira "desligado"', () => {
    expect(resumoDasConexoes([conexao({ id: 'a' })], null, AGORA)).toBe('1 ativa · nunca usada');
  });

  it('o conector OAuth parado conta como ativo, e não como "nenhuma ativa"', () => {
    // Parado desde ontem: o acesso de 1 h venceu há muito, a concessão não.
    const lista = [
      conexao({
        id: 'a', origem: 'oauth', cliente: 'Claude',
        expiraEm: iso(2026, 11, 22, 9, 0), ultimoUsoEm: iso(2026, 10, 23, 8, 10),
      }),
    ];
    expect(resumoDasConexoes(lista, true, AGORA)).toBe('1 ativa · usada ontem');
  });
});

describe('vazioDasConexoes', () => {
  it('a falha não se passa por "nenhuma conectada"', () => {
    expect(vazioDasConexoes(true, true)).toBe('Não consegui ler as conexões agora.');
    expect(vazioDasConexoes(true, false)).toBe('Não consegui ler as conexões agora.');
  });

  it('o vazio do administrador fala da escola; o do coordenador, só dele', () => {
    expect(vazioDasConexoes(false, true)).toBe('Nenhuma IA conectada ao SAS ainda.');
    expect(vazioDasConexoes(false, false)).toBe('Nenhuma IA conectada em seu nome.');
  });
});

describe('perguntaDeRevogacao', () => {
  it('diz o efeito e que não há desfazer', () => {
    const texto = perguntaDeRevogacao(conexao({ id: 'a' }));
    expect(texto).toContain('Revogar “Claude Code do notebook”?');
    expect(texto).toContain('perde o acesso ao SAS na hora');
    expect(texto).toContain('Não há como desfazer');
    expect(texto).toContain('crie uma conexão nova');
    expect(texto).not.toContain('Ana Coordenadora');
  });

  it('no OAuth, promete o corte da renovação: o contrato agora o garante', () => {
    // O `/oauth/token` recusa o refresh de conexão revogada e derruba a família
    // (oauth_mcp.py::_girar_refresh, test_conexao_revogada_na_tela_nao_gira).
    expect(REVOGACAO_OAUTH_CORTA_RENOVACAO).toBe(true);
    const c = conexao({ id: 'a', origem: 'oauth', cliente: 'ChatGPT' });
    expect(perguntaDeRevogacao(c)).toBe(perguntaDeRevogacao(c, { cortaRenovacao: true }));
  });

  it('no OAuth, sem o corte garantido, não o promete e manda desconectar no app', () => {
    const texto = perguntaDeRevogacao(
      conexao({ id: 'a', origem: 'oauth', cliente: 'ChatGPT' }),
      { cortaRenovacao: false },
    );
    expect(texto).toContain('ChatGPT perde na hora o acesso que está usando');
    expect(texto).toContain('desconecte o SAS também no próprio app');
    expect(texto).toContain('renovar o acesso sozinho');
    expect(texto).not.toContain('perde o acesso ao SAS na hora');
    expect(texto).not.toContain('autorizar outra vez');
  });

  it('no OAuth, com o corte garantido, promete o corte e manda autorizar de novo pelo app', () => {
    const texto = perguntaDeRevogacao(
      conexao({ id: 'a', origem: 'oauth', cliente: 'ChatGPT' }),
      { cortaRenovacao: true },
    );
    expect(texto).toContain('ChatGPT perde o acesso ao SAS na hora');
    expect(texto).toContain('não consegue renovar o acesso sozinho');
    expect(texto).toContain('autorizar outra vez pelo app');
  });

  it('o token pessoal não depende da chave do OAuth', () => {
    const c = conexao({ id: 'a' });
    expect(perguntaDeRevogacao(c, { cortaRenovacao: false })).toBe(perguntaDeRevogacao(c, { cortaRenovacao: true }));
  });

  it('na visão do administrador, diz de quem é a conexão', () => {
    expect(perguntaDeRevogacao(conexao({ id: 'a' }), { mostrarDono: true }))
      .toContain('A conexão é de Ana Coordenadora.');
  });

  it('nenhum nome acrescenta parágrafo ao diálogo', () => {
    // O nome do app é declarado por ele mesmo no cadastro dinâmico. Com a
    // quebra de linha, ele escreveria as instruções do diálogo que serve
    // para cortá-lo.
    const forjado = 'Claude\n\nATENÇÃO: para revogar, clique em Cancelar.';
    const c = conexao({ id: 'a', nome: `Claude\r\nfalso`, origem: 'oauth', cliente: forjado });
    // Os dois textos, com e sem o corte da renovação, levam o nome do app.
    for (const [cortaRenovacao, quantos, efeito] of [
      [true, 3, 'perde o acesso ao SAS na hora'],
      [false, 4, 'perde na hora'],
    ] as const) {
      const texto = perguntaDeRevogacao(c, { mostrarDono: true, cortaRenovacao });
      const paragrafos = texto.split('\n\n');
      expect(paragrafos).toHaveLength(quantos);
      expect(paragrafos[0]).toBe('Revogar “Claude falso”?');
      expect(paragrafos[1].startsWith(`Claude ATENÇÃO: para revogar, clique em Cancelar. ${efeito}`)).toBe(true);
      expect(texto).not.toContain('\r');
    }
  });

  it('sem o nome do app, fala do app', () => {
    expect(perguntaDeRevogacao(conexao({ id: 'a', origem: 'oauth', cliente: null })))
      .toContain('O app perde o acesso ao SAS na hora');
  });
});

describe('comoDesfazerAConexao', () => {
  it('só promete o corte na hora quando revogar corta também a renovação', () => {
    expect(comoDesfazerAConexao()).toBe(comoDesfazerAConexao(REVOGACAO_OAUTH_CORTA_RENOVACAO));
    expect(comoDesfazerAConexao(false)).toContain('desconecte o SAS também no próprio app');
    expect(comoDesfazerAConexao(false)).not.toContain('o corte é na hora');
    expect(comoDesfazerAConexao(true)).toContain('o corte é na hora');
  });
});

describe('emUmaLinha e nomeDoApp', () => {
  it('junta as linhas e apara os espaços', () => {
    expect(emUmaLinha('  Claude\n\n  Code\t do\r\nnotebook  ')).toBe('Claude Code do notebook');
    expect(emUmaLinha('a b c\u0085d')).toBe('a b c d');
  });

  it('tira o caractere invisível que reordena ou esconde o texto', () => {
    // U+202E inverte a leitura do que vem depois; U+200B é espaço de largura zero.
    expect(emUmaLinha('Cla​ude‮')).toBe('Claude');
    expect(emUmaLinha('⁦ChatGPT⁩')).toBe('ChatGPT');
  });

  it('corta no tamanho de rótulo, por caractere e não por unidade de UTF-16', () => {
    const longo = 'x'.repeat(NOME_DO_APP_MAXIMO + 10);
    const cortado = nomeDoApp(longo) ?? '';
    expect(Array.from(cortado)).toHaveLength(NOME_DO_APP_MAXIMO);
    expect(cortado.endsWith('…')).toBe(true);
    // O emoji (dois code units) não é partido ao meio.
    const comEmoji = `${'a'.repeat(NOME_DO_APP_MAXIMO - 2)}🤖🤖🤖`;
    const emojiCortado = nomeDoApp(comEmoji) ?? '';
    expect(emojiCortado).toBe(`${'a'.repeat(NOME_DO_APP_MAXIMO - 2)}🤖…`);
    expect(nomeDoApp('x'.repeat(NOME_DO_APP_MAXIMO))).toBe('x'.repeat(NOME_DO_APP_MAXIMO));
  });

  it('nome vazio, nulo ou só de invisível é nome nenhum', () => {
    expect(nomeDoApp(null)).toBeNull();
    expect(nomeDoApp(undefined)).toBeNull();
    expect(nomeDoApp('  \n​ ')).toBeNull();
  });
});

describe('configurar a IA', () => {
  const token = 'sas_mcp_AbC-12_xyz';

  it('monta o cabeçalho de autorização', () => {
    expect(cabecalhoDeAutorizacao(token)).toBe('Authorization: Bearer sas_mcp_AbC-12_xyz');
  });

  it('monta o comando do Claude Code com o token e o endereço entre aspas', () => {
    expect(comandoDoClaudeCode('https://portalsas.online/mcp', token)).toBe(
      'claude mcp add --transport http sas "https://portalsas.online/mcp" '
        + '--header "Authorization: Bearer sas_mcp_AbC-12_xyz"',
    );
  });
});

describe('permissaoDeEmitir', () => {
  const soAdmin: DisponibilidadeDoMcp = {
    habilitado: true, emissaoSoAdministrador: true, urlDoServidor: 'https://portalsas.online/mcp',
  };
  const aberta: DisponibilidadeDoMcp = { ...soAdmin, emissaoSoAdministrador: false };

  it('esconde a ação enquanto a chave do servidor não chegou', () => {
    expect(permissaoDeEmitir(undefined, true, true)).toBe('conferindo');
  });

  it('com emissão só de administrador, só ele emite', () => {
    expect(permissaoDeEmitir(soAdmin, false, true)).toBe('pode');
    expect(permissaoDeEmitir(soAdmin, false, false)).toBe('so-administrador');
  });

  it('com emissão aberta, qualquer coordenador emite', () => {
    expect(permissaoDeEmitir(aberta, false, false)).toBe('pode');
  });

  it('o padrão de 26/10 (emissão aberta) deixa coordenador e administrador emitirem', () => {
    // A decisão do dono: os dois conectam. O "só administrador" ficou como
    // opção de configuração, testada acima.
    expect(permissaoDeEmitir(aberta, false, false)).toBe('pode');
    expect(permissaoDeEmitir(aberta, false, true)).toBe('pode');
  });

  it('falha na consulta deixa o servidor decidir, em vez de trancar a tela', () => {
    expect(permissaoDeEmitir(undefined, false, false)).toBe('pode');
  });
});

describe('destinoDaVolta', () => {
  it('segue para o host que a tela mostrou', () => {
    const volta = 'https://claude.ai/api/mcp/auth_callback?code=abc&state=xyz';
    expect(destinoDaVolta(volta, 'claude.ai')).toBe(volta);
  });

  it('compara host sem diferenciar maiúscula', () => {
    expect(destinoDaVolta('https://ChatGPT.com/connector_platform_oauth_redirect?code=1', 'chatgpt.com'))
      .toBe('https://chatgpt.com/connector_platform_oauth_redirect?code=1');
  });

  it('no loopback, a porta também tem de ser a mostrada, que é a do pedido', () => {
    // A porta muda entre o cadastro e o pedido (RFC 8252 §7.3), não entre o
    // pedido e a volta: o servidor mostra a porta do pedido.
    const volta = 'http://localhost:33418/callback?code=abc';
    expect(destinoDaVolta(volta, 'localhost:33418')).toBe(volta);
    expect(destinoDaVolta(volta, 'localhost')).toBeNull();
    expect(destinoDaVolta(volta, 'localhost:33419')).toBeNull();
    expect(destinoDaVolta('http://[::1]:8080/cb?code=1', '[::1]:8080')).toBe('http://[::1]:8080/cb?code=1');
    expect(destinoDaVolta('http://[::1]:8080/cb?code=1', '::1')).toBeNull();
  });

  it('confere contra o texto mostrado, sem relê-lo', () => {
    // A revisão de 25/10: relido com `new URL`, "atacante.example\.claude.ai"
    // virava atacante.example, o mesmo host do destino, e a tela seguia para
    // um host que não tinha mostrado.
    const volta = 'https://atacante.example\\.claude.ai/api/mcp/auth_callback?code=1';
    expect(new URL(volta).host).toBe('atacante.example');
    expect(destinoDaVolta(volta, 'atacante.example\\.claude.ai')).toBeNull();
    // Nem URL, nem a porta padrão por extenso, nem IPv6 por extenso: o
    // servidor manda o `URL.host`, e outra escrita do mesmo host não confere.
    expect(destinoDaVolta('https://claude.ai/cb?code=1', 'https://claude.ai')).toBeNull();
    expect(destinoDaVolta('https://claude.ai/cb?code=1', 'claude.ai:443')).toBeNull();
    expect(destinoDaVolta('https://[::1]/cb', '[0:0:0:0:0:0:0:1]')).toBeNull();
  });

  it('o host mostrado é o redirectHost limpo, e é ele que confere', () => {
    // U+202E inverteria a leitura do host na tela: sai, e o que sobra é o que
    // a pessoa leu e o que o destino tem de ser.
    expect(hostDaVolta('‮claude.ai')).toBe('claude.ai');
    expect(destinoDaVolta('https://claude.ai/cb', '‮claude.ai')).toBe('https://claude.ai/cb');
  });

  it('recusa host diferente do mostrado — inclusive o que só termina igual', () => {
    expect(destinoDaVolta('https://sas-falso.com/cb?code=abc', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('https://claude.ai.sas-falso.com/cb', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('https://falsoclaude.ai/cb', 'claude.ai')).toBeNull();
  });

  it('recusa esquema que executa em vez de navegar', () => {
    expect(destinoDaVolta('javascript:alert(document.cookie)', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('data:text/html,<script>alert(1)</script>', 'claude.ai')).toBeNull();
  });

  it('aceita só https, e http só no loopback — lista de permissão, não de recusa', () => {
    // Com a lista de recusa, todos estes passavam.
    expect(destinoDaVolta('http://claude.ai/cb?code=1', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('vscode://claude.ai/cb?code=1', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('intent://claude.ai/cb#Intent;end', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('ftp://claude.ai/cb', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('http://127.0.0.1:5000/cb?code=1', '127.0.0.1:5000')).toBe('http://127.0.0.1:5000/cb?code=1');
    expect(destinoDaVolta('https://localhost:8443/cb?code=1', 'localhost:8443')).toBe('https://localhost:8443/cb?code=1');
  });

  it('fora do loopback, a porta tem de ser a mostrada', () => {
    expect(destinoDaVolta('https://claude.ai:8443/cb', 'claude.ai')).toBeNull();
    expect(destinoDaVolta('https://claude.ai/cb', 'claude.ai:8443')).toBeNull();
    expect(destinoDaVolta('https://claude.ai:8443/cb', 'claude.ai:8443')).toBe('https://claude.ai:8443/cb');
    // A porta padrão escrita por extenso é a mesma porta.
    expect(destinoDaVolta('https://claude.ai:443/cb', 'claude.ai')).toBe('https://claude.ai/cb');
  });

  it('não toma por loopback o host que só começa como um', () => {
    expect(destinoDaVolta('http://localhost.sas-falso.com/cb', 'localhost')).toBeNull();
    expect(destinoDaVolta('https://localhost.sas-falso.com/cb', 'localhost')).toBeNull();
  });

  it('recusa volta sem host mostrado e texto que não é URL', () => {
    expect(destinoDaVolta('https://claude.ai/cb', '')).toBeNull();
    expect(destinoDaVolta('isto não é url', 'claude.ai')).toBeNull();
  });

  it('caminho interno do SAS segue a regra da volta do login', () => {
    expect(destinoDaVolta('/administracao/conexoes-de-ia', 'claude.ai')).toBe('/administracao/conexoes-de-ia');
    expect(destinoDaVolta('//sas-falso.com/cb', 'claude.ai')).toBeNull();
  });
});

describe('leituraDaFalhaDoPedido', () => {
  it.each([
    [404, 'encerrado'],
    [409, 'encerrado'],
    [410, 'encerrado'],
    [400, 'recusado'],
    [422, 'recusado'],
    [429, 'espera'],
    // Nenhuma rota do consentimento devolve 403: ele cai em "outra", e não num
    // texto sobre administrador que o servidor nunca mandou.
    [403, 'outra'],
    [500, 'outra'],
    [0, 'outra'],
    [null, 'outra'],
  ] as const)('%s → %s', (status, esperado) => {
    expect(leituraDaFalhaDoPedido(status)).toBe(esperado);
  });
});

describe('e-mail da IA', () => {
  it('normaliza como o servidor guarda: aparado e em minúsculas', () => {
    expect(normalizarEmail('  Ana.Coord@Gmail.COM ')).toBe('ana.coord@gmail.com');
  });

  it.each([
    'ana@gmail.com',
    'Ana.Coord+ia@empresa.com.br',
    '  ana@gmail.com  ',
  ])('aceita a forma de %s', (email) => {
    expect(emailComFormaValida(email)).toBe(true);
  });

  it.each([
    ['vazio', ''],
    ['sem arroba', 'ana.gmail.com'],
    ['dois arrobas', 'ana@@gmail.com'],
    ['sem domínio', 'ana@'],
    ['sem ponto no domínio', 'ana@gmail'],
    ['com espaço no meio', 'ana coord@gmail.com'],
    ['com invisível', 'ana​@gmail.com'],
    ['com quebra de linha', 'ana@gmail.com\nbcc@x.com'],
  ])('recusa e-mail %s', (_caso, email) => {
    expect(emailComFormaValida(email)).toBe(false);
  });

  it('recusa o que passa do teto de um endereço', () => {
    const local = 'a'.repeat(EMAIL_MAXIMO);
    expect(emailComFormaValida(`${local}@x.com`)).toBe(false);
  });

  it('a falha do cadastro diz que o e-mail já existe sem dizer de quem', () => {
    const texto = mensagemDaFalhaDoEmailDaIa(409);
    expect(texto).toContain('já está cadastrado no SAS, nesta conta ou em outra');
    expect(mensagemDaFalhaDoEmailDaIa(422)).toContain('Confira o e-mail');
    expect(mensagemDaFalhaDoEmailDaIa(500)).toBe('Não consegui cadastrar o e-mail. Tente de novo em instantes.');
  });

  it('o 400 do cadastro é o teto de e-mails da conta, e não um e-mail mal escrito', () => {
    // routes/mcp_emails_ia.py: a forma recusada é 422 (pydantic); o 400 é o teto.
    const doServidor = 'Uma conta tem no máximo 10 e-mails de IA. Remova um antes.';
    expect(mensagemDaFalhaDoEmailDaIa(400, doServidor)).toBe(doServidor);
    expect(mensagemDaFalhaDoEmailDaIa(400)).toContain('Remova um');
    expect(mensagemDaFalhaDoEmailDaIa(400)).not.toContain('Confira o e-mail');
    // O cadastro não passa pelo portão do administrador: o 403 é só a conta
    // desativada, que a sessão de 8 h ainda deixa abrir a tela (prova de 27/10).
    expect(mensagemDaFalhaDoEmailDaIa(403)).not.toContain('administrador');
    expect(mensagemDaFalhaDoEmailDaIa(403)).toBe(MENSAGEM_CONTA_DESATIVADA);
  });

  it('o teto de códigos diz o prazo que o servidor deu, e o código que não saiu diz onde pedir outro', () => {
    const amanha = 'Códigos de confirmação demais para este e-mail hoje. Tente de novo amanhã.';
    expect(mensagemDaFalhaDoEmailDaIa(429, amanha)).toBe(amanha);
    expect(mensagemDaFalhaDoEmailDaIa(429)).toContain('Espere');
    const naoSaiu = mensagemDaFalhaDoEmailDaIa(503);
    expect(naoSaiu).toContain('entrou na lista');
    expect(naoSaiu).toContain('Enviar outro código');
  });

  it('o e-mail só aprova depois de confirmado', () => {
    expect(emailDaIaConfirmado({ confirmadoEm: '2026-10-26T15:00:00Z' })).toBe(true);
    expect(emailDaIaConfirmado({ confirmadoEm: null })).toBe(false);
  });

  it('o card avisa que quem lê a caixa conecta com o acesso da conta', () => {
    // Revisão de segurança de 26/10: o domínio digitado errado e a caixa
    // compartilhada entregavam o acesso a quem as lê.
    const aviso = avisoDaCaixaDoEmail();
    expect(aviso).toContain('Quem lê a caixa');
    expect(aviso).toContain('com o acesso da sua conta');
    expect(aviso).toContain('só você lê');
    expect(aviso).toContain('código');
  });

  it('o aviso do código de confirmação diz para onde ele foi e que até lá o e-mail não aprova nada', () => {
    const aviso = avisoDoCodigoDeConfirmacao('  Ana@Gmail.com\n');
    expect(aviso).toContain('ana@gmail.com');
    expect(aviso).toContain('não aprova conexão nenhuma');
    expect(aviso).not.toContain('\n');
  });

  it('a falha da confirmação manda pedir outro código, ou explica o que mudou', () => {
    expect(mensagemDaFalhaDaConfirmacao(400)).toContain('peça outro');
    expect(mensagemDaFalhaDaConfirmacao(422)).toContain('peça outro');
    expect(mensagemDaFalhaDaConfirmacao(409)).toContain('outra conta');
    expect(mensagemDaFalhaDaConfirmacao(404)).toContain('não está mais');
    expect(mensagemDaFalhaDaConfirmacao(500)).toBe('Não consegui confirmar agora. Tente de novo em instantes.');
    // A conta desativada não confirma: "tente de novo" não resolveria nada.
    expect(mensagemDaFalhaDaConfirmacao(403)).toBe(MENSAGEM_CONTA_DESATIVADA);
  });

  it('a falha do reenvio usa o prazo do servidor no teto, e diz quando já está confirmado', () => {
    const naHora = 'Códigos de confirmação demais nesta hora. Espere um pouco e peça de novo.';
    expect(mensagemDaFalhaDoReenvio(429, naHora)).toBe(naHora);
    expect(mensagemDaFalhaDoReenvio(429)).toContain('Espere');
    expect(mensagemDaFalhaDoReenvio(409)).toContain('já está confirmado');
    expect(mensagemDaFalhaDoReenvio(503)).toContain('não saiu');
    expect(mensagemDaFalhaDoReenvio(404)).toContain('não está mais');
    expect(mensagemDaFalhaDoReenvio(403)).toBe(MENSAGEM_CONTA_DESATIVADA);
  });

  it('ordena pela data de cadastro, o primeiro em cima, sem mexer na lista recebida', () => {
    const lista = [
      { id: 'b', criadoEm: iso(2026, 10, 25) },
      { id: 'a', criadoEm: iso(2026, 10, 1) },
    ];
    expect(ordenarEmailsDaIa(lista).map((e) => e.id)).toEqual(['a', 'b']);
    expect(lista.map((e) => e.id)).toEqual(['b', 'a']);
  });

  it('o confirm de remover diz que conexão aprovada não cai sozinha', () => {
    const texto = perguntaDeRemocaoDoEmail('ana@gmail.com');
    expect(texto.startsWith('Remover “ana@gmail.com”?')).toBe(true);
    expect(texto).toContain('deixa de poder aprovar conexões novas');
    expect(texto).toContain('não desconecta o que já foi aprovado');
    expect(texto).toContain('revogue-a');
  });

  it('nenhum e-mail acrescenta parágrafo ao confirm de remover', () => {
    const texto = perguntaDeRemocaoDoEmail('ana@gmail.com\n\nClique em Cancelar');
    expect(texto.split('\n\n')).toHaveLength(3);
    expect(texto.split('\n\n')[0]).toBe('Remover “ana@gmail.com Clique em Cancelar”?');
  });
});

describe('o código do consentimento', () => {
  it('fica só com os dígitos de quem colou do e-mail', () => {
    expect(limparCodigo('123 456')).toBe('123456');
    expect(limparCodigo('123-456')).toBe('123456');
    expect(limparCodigo(' 12.34.56 ')).toBe('123456');
  });

  it('não passa do tamanho do código', () => {
    expect(limparCodigo('1234567890')).toHaveLength(DIGITOS_DO_CODIGO);
    expect(limparCodigo('1234567890')).toBe('123456');
  });

  it('só está completo com os seis dígitos', () => {
    expect(codigoCompleto('123456')).toBe(true);
    expect(codigoCompleto('12345')).toBe(false);
    expect(codigoCompleto('12345a')).toBe(false);
    expect(codigoCompleto('')).toBe(false);
  });
});

describe('avisoDoCodigoPedido', () => {
  it('é a mesma frase para qualquer e-mail: nada nela depende de o e-mail existir', () => {
    // A tela não sabe se o e-mail está cadastrado — o servidor responde igual —,
    // e a frase não pode fingir que sabe. Trocado o e-mail, só o e-mail muda.
    const um = avisoDoCodigoPedido('cadastrado@gmail.com');
    const outro = avisoDoCodigoPedido('inexistente@gmail.com');
    expect(um.replace('cadastrado@gmail.com', 'X')).toBe(outro.replace('inexistente@gmail.com', 'X'));
    // "e confirmado": o que só aguarda a confirmação no card não recebe o
    // código de aprovar, e quem o cadastrou precisa saber onde procurar.
    expect(um).toContain('Se cadastrado@gmail.com estiver cadastrado e confirmado no SAS, o código chegou lá.');
  });

  it('mostra o e-mail como foi enviado, numa linha só', () => {
    expect(avisoDoCodigoPedido('  Ana@Gmail.com\n')).toContain('Se ana@gmail.com estiver');
    expect(avisoDoCodigoPedido('ana@gmail.com\n\nOutra frase')).not.toContain('\n');
  });
});

describe('mensagemDaFalhaDoConsentimento', () => {
  it('o 400 da aprovação é uma frase só, que não diz qual foi o problema', () => {
    const texto = mensagemDaFalhaDoConsentimento('aprovar', 400);
    expect(texto).toContain('Não deu para aprovar com esse código');
    expect(texto).toContain('peça outro código');
    // Nada que separe "e-mail não cadastrado" de "código errado".
    for (const revelador of ['não está cadastrado', 'não existe', 'desconhecido', 'tentativas esgotadas']) {
      expect(texto).not.toContain(revelador);
    }
  });

  it('o teto do servidor manda esperar, nas três ações', () => {
    expect(mensagemDaFalhaDoConsentimento('codigo', 429)).toContain('Espere alguns minutos');
    expect(mensagemDaFalhaDoConsentimento('aprovar', 429)).toContain('Espere alguns minutos');
    expect(mensagemDaFalhaDoConsentimento('recusar', 429)).toContain('Espere alguns minutos');
  });

  it('o e-mail malformado no pedido de código diz para conferir o e-mail', () => {
    expect(mensagemDaFalhaDoConsentimento('codigo', 422)).toContain('Confira o e-mail');
  });

  it('sem resposta nenhuma, usa a frase do transporte; com resposta, nunca o texto cru do servidor', () => {
    expect(mensagemDaFalhaDoConsentimento('aprovar', 0, 'Sem resposta do servidor.')).toBe('Sem resposta do servidor.');
    expect(mensagemDaFalhaDoConsentimento('aprovar', 500, 'POST /oauth/pedidos/x/aprovar → 500'))
      .toBe('Não consegui enviar a aprovação. Tente de novo em instantes.');
    expect(mensagemDaFalhaDoConsentimento('recusar', 500)).toBe('Não consegui enviar a recusa. Tente de novo em instantes.');
  });

  it('depois do código CERTO, diz o que houve em vez de mandar pedir outro código', () => {
    // routes/oauth_mcp.py::_dono_do_codigo: só quem acertou o código chega a
    // estas frases. O código já foi gasto e um novo não chegaria — a frase
    // genérica deixava a pessoa num laço de pedir código.
    const removido = 'Este e-mail não está mais cadastrado no SAS como e-mail de conta de IA. Cadastre-o de novo em Conexões de IA e peça um código novo.';
    const semPermissao = 'A conta da coordenação dona deste e-mail não pode conectar uma IA ao SAS agora (conta desativada, ou sem o papel de administrador enquanto só ele conecta).';
    expect(mensagemDaFalhaDoConsentimento('aprovar', 400, removido)).toBe(removido);
    expect(mensagemDaFalhaDoConsentimento('aprovar', 400, semPermissao)).toBe(semPermissao);
  });

  it('os tetos do servidor dizem o prazo dele: o de um dia por e-mail não vira "alguns minutos"', () => {
    const umDia = 'Códigos demais para este e-mail hoje. Tente de novo amanhã.';
    const porPedido = 'Códigos demais para este pedido. Volte ao app de IA e comece a conexão de novo.';
    expect(mensagemDaFalhaDoConsentimento('codigo', 429, umDia)).toBe(umDia);
    expect(mensagemDaFalhaDoConsentimento('codigo', 429, porPedido)).toBe(porPedido);
    expect(mensagemDaFalhaDoConsentimento('aprovar', 429, 'Tentativas demais a partir deste endereço. Espere um minuto.'))
      .toContain('Espere um minuto');
  });

  it('sem a frase do servidor (o corpo não veio, ou não era dele), fica a da tela', () => {
    expect(mensagemDaFalhaDoConsentimento('aprovar', 400, 'POST /oauth/pedidos/x/aprovar → 400'))
      .toContain('Não deu para aprovar com esse código');
    expect(mensagemDaFalhaDoConsentimento('codigo', 429, 'POST /oauth/pedidos/x/codigo → 429'))
      .toContain('Espere alguns minutos');
    // O 422 do pydantic traz `detail` em lista, que chega como "[object Object]".
    expect(mensagemDaFalhaDoConsentimento('codigo', 422, '[object Object]')).toContain('Confira o e-mail');
  });
});

describe('fraseDoServidor', () => {
  it('devolve a frase que o servidor escreveu', () => {
    expect(fraseDoServidor('  Códigos demais para este pedido.  ')).toBe('Códigos demais para este pedido.');
  });

  it.each([
    ['vazia', ''],
    ['ausente', undefined],
    ['o recuo do transporte', 'POST /oauth/pedidos/abc/aprovar → 400'],
    ['o recuo de um GET', 'GET /mcp/emails-ia → 502'],
    ['o detail em lista do pydantic', '[object Object]'],
    ['várias listas', '[object Object],[object Object]'],
  ])('não toma por frase %s', (_caso, texto) => {
    expect(fraseDoServidor(texto)).toBeNull();
  });
});

describe('fraseDoProibido', () => {
  const proibido = 'O servidor recusou: neste ambiente, criar conexão de IA é só do administrador do SAS.';

  it('a conta desativada fica com a frase do servidor, e não com a do só-administrador', () => {
    // Emitir token tem duas recusas 403 (prova de ponta a ponta de 27/10): o
    // "só do administrador" seria o motivo errado para a conta desativada.
    expect(fraseDoProibido(MENSAGEM_CONTA_DESATIVADA, proibido)).toBe(MENSAGEM_CONTA_DESATIVADA);
    expect(fraseDoProibido(`  ${MENSAGEM_CONTA_DESATIVADA}\n`, proibido)).toBe(MENSAGEM_CONTA_DESATIVADA);
  });

  it.each([
    ['a regra do só-administrador', 'Conectar uma IA ao SAS está, neste ambiente, restrito ao administrador.'],
    ['o recuo do transporte', 'POST /mcp/tokens → 403'],
    ['vazia', ''],
    ['ausente', undefined],
  ])('com %s, a tela usa a frase dela', (_caso, doServidor) => {
    expect(fraseDoProibido(doServidor, proibido)).toBe(proibido);
  });
});

describe('passosParaConectar', () => {
  const url = 'https://exemplo.test/mcp';
  const textoDe = (passos: ReturnType<typeof passosParaConectar>) => JSON.stringify(passos);

  it('cobre as três IAs, com o caminho mais usado primeiro', () => {
    expect(IAS_PARA_CONECTAR.map((o) => o.valor)).toEqual(['claude', 'claude-code', 'chatgpt']);
    for (const { valor } of IAS_PARA_CONECTAR) {
      expect(passosParaConectar(valor, url).length).toBeGreaterThanOrEqual(4);
    }
  });

  it('no claude.ai e no ChatGPT, o primeiro passo é o e-mail confirmado, e o endereço vem para copiar', () => {
    // A aprovação é pelo código no e-mail da conta de IA (decisão de 26/10):
    // sem ele confirmado, o passo de aprovar não tem como dar certo.
    for (const ia of ['claude', 'chatgpt'] as const) {
      const passos = passosParaConectar(ia, url);
      expect(passos[0].confereEmail).toBe(true);
      expect(passos.filter((p) => p.copiar).map((p) => p.copiar?.texto)).toEqual([url]);
      expect(textoDe(passos)).toContain('Aprovar');
    }
  });

  it('no Claude Code, o caminho é o token: criar, copiar o comando e conferir', () => {
    const passos = passosParaConectar('claude-code', url);
    expect(passos[0].criaConexao).toBe(true);
    expect(passos.some((p) => p.confereEmail)).toBe(false);
    expect(passos.find((p) => p.comando)?.comando).toBe('claude mcp list');
    expect(textoDe(passos)).toContain('histórico');
  });

  it('o endereço é o que o servidor deu, nunca um escrito no texto', () => {
    // A mesma tela serve o dev, a stack de teste e a produção.
    for (const { valor } of IAS_PARA_CONECTAR) {
      expect(textoDe(passosParaConectar(valor, url))).not.toMatch(/portalsas|localhost/);
    }
  });

  it('o código do e-mail diz quantos dígitos tem, pela mesma constante da tela de aprovar', () => {
    expect(textoDe(passosParaConectar('claude', url))).toContain(`${DIGITOS_DO_CODIGO} dígitos`);
  });

  it('cada IA tem o cuidado de privacidade dela, e todos falam em treino do modelo', () => {
    expect(cuidadoDePrivacidade('claude')).toContain('Ajudar a melhorar o Claude');
    expect(cuidadoDePrivacidade('chatgpt')).toContain('Melhorar o modelo para todos');
    expect(cuidadoDePrivacidade('claude-code')).toContain('conta do Claude');
  });
});

describe('estadoDoEmailConfirmado', () => {
  it('diz se o passo do e-mail já está feito, e cala enquanto a lista não chegou', () => {
    expect(estadoDoEmailConfirmado(null)).toBeNull();
    expect(estadoDoEmailConfirmado(0)).toContain('Ainda falta');
    expect(estadoDoEmailConfirmado(1)).toBe('Feito: esta conta tem 1 e-mail confirmado.');
    expect(estadoDoEmailConfirmado(2)).toBe('Feito: esta conta tem 2 e-mails confirmados.');
  });
});
