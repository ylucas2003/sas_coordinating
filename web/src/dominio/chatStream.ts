// Reducer do streaming do chat.
//
// A versão anterior remendava o DOM a cada evento: guardava a bolha ativa, o
// texto acumulado, o nó de texto e um Map de traces, e trocava elementos no
// lugar. Aqui os eventos viram estado e o React reconcilia — o que importa
// porque a ordem dos eventos não é garantida e a lógica de "qual trace é
// esta" fica explícita.
//
// Testado em chatStream.test.ts.

import type { ArtefatoChat, MensagemChat, ToolCall } from '../tipos/chat';

/**
 * Quem está do outro lado da conversa — os dois escopos do registro de tools
 * (docs/43 §3.1; `Escopo` em api/app/chat/ferramentas.py). A mesma `Conversa`
 * serve os dois cascos, e o que muda com o escopo mora aqui, em regra pura,
 * e não num `if` de componente.
 */
export type EscopoDaConversa = 'aluno' | 'coordenacao';

export interface TraceTool {
  id: string;
  nome: string;
  args: Record<string, unknown>;
  resumo: string | null;
  finalizada: boolean;
}

export interface EstadoStream {
  /** Texto acumulado token a token. */
  texto: string;
  traces: TraceTool[];
  erros: string[];
  /** Preenchido no evento `end`: substitui o texto cru pelo markdown final. */
  final: { texto: string; artefatos: ArtefatoChat[] } | null;
  /** Título gerado pelo backend para a thread, quando vem. */
  titulo: string | null;
}

export const ESTADO_INICIAL: EstadoStream = {
  texto: '', traces: [], erros: [], final: null, titulo: null,
};

interface EventoBruto {
  nome: string;
  dados: unknown;
}

/**
 * Os tipos que QUALQUER tool pode anexar ao resultado, no campo
 * `artefato: {tipo, titulo?, payload}` (docs/43 §4.1, defeito 6).
 *
 * ⚠️ CATÁLOGO FECHADO, e espelha a allowlist que o servidor aplica antes de
 * persistir (`TIPOS_DE_ARTEFATO` e `artefatos_do_resultado`,
 * api/app/chat/ferramentas.py): o modelo escolhe de uma lista e nunca produz
 * markup (docs/27 §3). Tipo fora daqui é descartado JÁ AO VIVO porque o
 * servidor também não o guarda — mostrar um cartão que some ao reabrir a
 * conversa é pior do que não mostrar. Mudou aqui, mude lá: o
 * test_chat_ferramentas.py lê esta constante e reprova se as duas divergirem.
 *
 * Ficam de fora de propósito: `csv` e `navegacao`, que só nascem das tools
 * próprias (o link tem a rota montada no servidor, docs/31 §2.4 — um campo
 * genérico abriria essa porta a qualquer tool); `extrato_xp`, porque o XP
 * ainda é mock (docs/26 §3); e fórmula, que é da família inline (docs/27 §3).
 */
export const CATALOGO_DE_ARTEFATOS = [
  'barras_corte',
  'questao',
  'lista_questoes',
  'prova',
  'linha_temporal',
  'histograma',
] as const;

export type TipoDoCatalogo = (typeof CATALOGO_DE_ARTEFATOS)[number];

function estaNoCatalogo(tipo: unknown): tipo is TipoDoCatalogo {
  return typeof tipo === 'string' && (CATALOGO_DE_ARTEFATOS as readonly string[]).includes(tipo);
}

/** O teto do título, o MESMO de `LIMITE_DO_TITULO` em api/app/chat/ferramentas.py. */
export const LIMITE_DO_TITULO_DO_ARTEFATO = 200;

function ehObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === 'object' && valor !== null && !Array.isArray(valor);
}

/**
 * O artefato passa no teste que o servidor aplica antes de gravá-lo
 * (`_motivo_de_descarte`, ferramentas.py)? Payload objeto; título ausente ou
 * texto de até 200 caracteres.
 *
 * ⚠️ Quem não passa NÃO aparece nem ao vivo. O servidor descarta o cartão
 * inteiro — não só o título —, e mostrar agora o que some ao reabrir a conversa
 * é pior do que não mostrar (o mesmo motivo do catálogo fechado). Os
 * caracteres contam como no Python, por ponto de código: um emoji é um.
 */
function oServidorGrava(titulo: unknown, payload: unknown): boolean {
  if (!ehObjeto(payload)) return false;
  if (titulo == null) return true;
  return typeof titulo === 'string' && [...titulo].length <= LIMITE_DO_TITULO_DO_ARTEFATO;
}

/** O título como a tela o recebe: texto, ou nada. */
function tituloDoArtefato(titulo: unknown): string | undefined {
  return typeof titulo === 'string' ? titulo : undefined;
}

/**
 * O campo `artefato` de um resultado, se o tipo dele estiver no catálogo e o
 * servidor for gravá-lo.
 *
 * O payload passa como veio, desde que seja objeto: quem lê os campos é o
 * renderizador, e ele já desconfia campo a campo e falha visível quando não
 * bate (`ArtefatoAluno.tsx`, docs/27 §7).
 */
function artefatoAnexado(resultado: { artefato?: unknown }): ArtefatoChat | null {
  const bruto = resultado.artefato;
  if (!ehObjeto(bruto)) return null;

  const { tipo, titulo, payload } = bruto;
  if (!estaNoCatalogo(tipo) || !oServidorGrava(titulo, payload)) return null;
  return { tipo, titulo: tituloDoArtefato(titulo), payload };
}

/**
 * Artefatos renderizáveis produzidos pelas tools da volta — o que aparece AO
 * VIVO, antes de a conversa ser recarregada.
 *
 * Reconhece o que o servidor persiste, e nada além: os formatos próprios de
 * `gerar_grafico`, `exportar_csv` e `navegar_para`, e o campo `artefato` de
 * qualquer tool — todos pelo mesmo teste de título e payload que o servidor
 * aplica (`oServidorGrava`). O resto do resultado já foi incorporado ao texto
 * da resposta pelo próprio agente.
 */
export function extrairArtefatos(toolCalls: readonly ToolCall[] = []): ArtefatoChat[] {
  const artefatos: ArtefatoChat[] = [];
  const formaPropria = (tipo: string, titulo: unknown, payload: unknown) => {
    if (oServidorGrava(titulo, payload)) artefatos.push({ tipo, titulo: tituloDoArtefato(titulo), payload });
  };

  for (const tc of toolCalls) {
    const r = tc.resultado;
    if (!r || r.erro) continue;
    const nome = tc.nome ?? tc.name;

    if (nome === 'gerar_grafico' && (r.tipo === 'histograma' || r.tipo === 'linha_temporal')) {
      formaPropria(r.tipo, r.titulo, r.payload);
    }
    // O link clicável de "os três em risco são A, B e C" (docs/31 §2.4). O
    // servidor o persiste desde a 0038, e é daqui que ele aparece ao vivo. Ao
    // reabrir a conversa ele volta pendurado na mensagem `tool`, e quem o
    // devolve à resposta é a `Conversa`, com `artefatosNaResposta` — nos dois
    // cascos desde 25/10; até ali só a folha do aluno fazia a passagem, e o
    // coordenador perdia o link toda vez que reabria a thread.
    if (nome === 'navegar_para' && r.tipo === 'navegacao') {
      formaPropria('navegacao', r.titulo, r.payload);
    }
    if (nome === 'exportar_csv' && r.tipo === 'csv') {
      formaPropria('csv', r.titulo, { conteudo: r.conteudo, nLinhas: r.nLinhas });
    }

    const anexado = artefatoAnexado(r);
    if (anexado) artefatos.push(anexado);
  }
  return artefatos;
}

/**
 * O histórico persistido com cada artefato na resposta que fecha o turno.
 *
 * ⚠️ O SERVIDOR PENDURA O ARTEFATO NA MENSAGEM `tool` que o produziu
 * (`_talvez_salvar_artefato(cliente, tool_msg_id, …)`, rotas.py), e `Mensagem`
 * não desenha mensagem `tool` — o legado em `web/js/` também não desenhava.
 * Sem esta passagem, nenhum artefato persistido aparece ao reabrir a conversa.
 * Ela leva cada um para a resposta do assistente que vem depois, que é onde ele
 * apareceu ao vivo (`BolhaStream`: o texto e, embaixo, os artefatos).
 *
 * Turno sem resposta depois das tools (o histórico acaba nelas, ou a pergunta
 * seguinte vem antes): os artefatos viram uma mensagem própria do assistente
 * naquele ponto, porque perder o cartão em silêncio é o que não pode (docs/27
 * §7). Não altera a entrada e é idempotente: na segunda passada as mensagens
 * `tool` já não têm artefato.
 */
export function artefatosNaResposta(mensagens: readonly MensagemChat[] = []): MensagemChat[] {
  const saida: MensagemChat[] = [];
  let pendentes: ArtefatoChat[] = [];

  const soltarPendentes = () => {
    if (!pendentes.length) return;
    saida.push({ papel: 'assistant', conteudo: null, artefatos: pendentes });
    pendentes = [];
  };

  for (const m of mensagens) {
    if (m.papel === 'tool' && m.artefatos?.length) {
      pendentes = [...pendentes, ...m.artefatos];
      saida.push({ ...m, artefatos: [] });
      continue;
    }
    if (m.papel === 'assistant' && pendentes.length) {
      saida.push({ ...m, artefatos: [...(m.artefatos ?? []), ...pendentes] });
      pendentes = [];
      continue;
    }
    // Artefato não atravessa pergunta: o de um turno nunca vai parar na
    // resposta do turno seguinte.
    if (m.papel === 'user') soltarPendentes();
    saida.push(m);
  }
  soltarPendentes();
  return saida;
}

/**
 * A resposta concluída, no formato que o histórico da conversa guarda — e que
 * tem de ser o MESMO que o servidor gravou, para a tela não mudar ao reabrir.
 *
 * O stream só vive até a próxima pergunta: sem esta conversão, abrir o stream
 * seguinte descartava a resposta anterior — o backend a persistia, mas a tela
 * só a mostraria de novo depois de recarregar a conversa.
 *
 * ⚠️ RESPOSTA QUE TEVE `erro` vira só a mensagem de erro, sem texto parcial,
 * sem traces e sem cartão. É exatamente o que `_stream_mensagem`
 * (api/app/chat/rotas.py) grava nesse caso: uma linha do assistente com
 * `⚠️ Erro: <mensagem>`, a do ÚLTIMO `erro` — e nenhuma mensagem `tool`,
 * nenhum `chat_artefato`. Vale com ou sem `end`: o servidor decide pelo `erro`,
 * e o agente pode emitir o erro sem chegar ao `end` (sem credencial do
 * provedor, `agente.py`). Enquanto o stream está na tela, quem lê vê o texto
 * que já tinha chegado mais o erro (`reduzirEvento`); é na passagem ao
 * histórico que a resposta fica igual à gravada.
 *
 * Devolve `null` quando o stream não chegou ao `end` nem trouxe `erro` (ainda
 * roda, ou a conexão caiu): texto parcial não é mensagem, e o servidor também
 * não o grava como resposta.
 */
export function mensagemDaResposta(estado: EstadoStream): MensagemChat | null {
  const ultimoErro = estado.erros.at(-1);
  if (ultimoErro !== undefined) {
    return { papel: 'assistant', conteudo: `⚠️ Erro: ${ultimoErro}`, artefatos: [] };
  }
  if (!estado.final) return null;

  return {
    papel: 'assistant',
    conteudo: estado.final.texto,
    toolCalls: estado.traces.map((t) => ({ nome: t.nome, args: t.args })),
    artefatos: estado.final.artefatos,
  };
}

export function reduzirEvento(estado: EstadoStream, evento: EventoBruto): EstadoStream {
  const dados = (evento.dados ?? {}) as Record<string, any>;

  switch (evento.nome) {
    // Marcadores de ciclo de vida sem efeito na UI.
    case 'start':
    case 'user_salvo':
      return estado;

    case 'tool_call_start':
      return {
        ...estado,
        traces: [
          ...estado.traces,
          {
            id: String(dados.tool_call_id ?? estado.traces.length),
            nome: String(dados.nome ?? ''),
            args: (dados.args ?? {}) as Record<string, unknown>,
            resumo: null,
            finalizada: false,
          },
        ],
      };

    case 'tool_call_end': {
      const id = String(dados.tool_call_id ?? '');
      // Fecha a trace mantendo nome e args, que só o evento de início trouxe.
      return {
        ...estado,
        traces: estado.traces.map((t) =>
          t.id === id ? { ...t, resumo: dados.resumido ?? null, finalizada: true } : t,
        ),
      };
    }

    case 'token':
      return { ...estado, texto: estado.texto + (dados.texto ?? '') };

    case 'erro':
      return { ...estado, erros: [...estado.erros, String(dados.mensagem ?? 'erro desconhecido')] };

    case 'titulo':
      return { ...estado, titulo: dados.titulo ?? null };

    case 'end':
      // ⚠️ Resposta que terminou em ERRO: com o streaming de verdade, o erro
      // chega DEPOIS de tokens que a pessoa já está lendo, e o `end` traz
      // `texto_final: ""` (agente.py só o preenche na resposta final). Trocar o
      // texto pelo vazio apagava o que estava na tela; fica o que já chegou,
      // mais o erro embaixo. E nenhum cartão: o servidor só grava a mensagem de
      // erro (`_stream_mensagem`), e o cartão sumiria ao reabrir.
      if (estado.erros.length) {
        return { ...estado, final: { texto: estado.texto, artefatos: [] } };
      }
      return {
        ...estado,
        final: {
          // `||` e não `??`: texto final vazio nunca apaga o que já foi lido.
          texto: dados.texto_final || estado.texto,
          artefatos: extrairArtefatos(dados.tool_calls ?? []),
        },
      };

    default:
      return estado;
  }
}

// ─── O trace de uma tool ─────────────────────────────────────────────────

/**
 * O que a bolha do trace escreve enquanto a tool roda: "Buscando suas notas",
 * e não `minhas_notas`.
 *
 * ⚠️ TODA tool do registro tem entrada, dos dois escopos — sem ela a pessoa lê
 * o nome cru, em snake_case, e um aluno de 17 anos lendo `o_que_mais_cai` acha
 * que o app quebrou. `chatStream.test.ts` confere esta lista contra as tools
 * declaradas no backend (`api/app/chat/tools/*.py`, `tools_aluno*.py` e
 * `roteiros.py`), como o backend confere o `CATALOGO_DE_ARTEFATOS` daqui: tool
 * nova sem nome legível reprova, e nome que sobrou de tool que saiu também.
 */
export const NOME_LEGIVEL_DA_TOOL: Readonly<Record<string, string>> = {
  // ── Coordenação · alunos, ciclos e simulados ──
  buscar_aluno_por_nome: 'Buscando aluno',
  buscar_aluno_por_matricula: 'Buscando aluno pela matrícula',
  obter_aluno: 'Carregando aluno',
  listar_alunos: 'Listando alunos',
  listar_sedes: 'Listando sedes',
  listar_turmas: 'Listando turmas',
  listar_ciclos: 'Listando ciclos',
  listar_simulados: 'Listando simulados',
  obter_simulado: 'Carregando simulado',
  listar_materias: 'Listando matérias',
  estatisticas_ciclo: 'Calculando estatísticas do ciclo',
  trajetoria_aluno: 'Carregando trajetória do aluno',
  histograma_simulado: 'Carregando histograma',
  notas_simulado: 'Carregando notas do simulado',
  questoes_do_simulado: 'Carregando as questões do simulado',
  comparar_ciclos: 'Comparando ciclos',
  comparar_alunos: 'Comparando alunos',
  comparar_simulados: 'Comparando simulados',
  alunos_similares: 'Buscando alunos similares',
  alunos_em_risco: 'Identificando alunos em risco',
  alunos_destaque: 'Identificando destaques',
  tendencia_aluno: 'Analisando tendência',
  materias_problematicas: 'Identificando matérias problemáticas',
  relatorio_aluno: 'Montando o relatório do aluno',
  historico_aluno: 'Carregando o histórico do aluno',
  relatorio_ciclo: 'Montando o relatório do ciclo',
  listar_alertas: 'Lendo os alertas',
  insights_do_ciclo: 'Lendo os insights do ciclo',
  gerar_grafico: 'Gerando gráfico',
  exportar_csv: 'Gerando CSV',
  navegar_para: 'Preparando o link',
  // ── Coordenação · banco de questões, régua e rotinas (docs/43 §4.3) ──
  topicos_do_edital: 'Consultando os tópicos do edital',
  buscar_questoes_do_banco: 'Buscando questões no banco',
  recorrencia_no_banco: 'Medindo o que mais cai no banco',
  reguas_de_corte: 'Consultando as réguas de corte',
  cortados_pela_regua: 'Aplicando a régua de corte',
  estado_do_sync_canvas: 'Conferindo o sync do Canvas',
  pendencias_canvas_do_ciclo: 'Conferindo o que falta no Canvas',
  estado_das_gravacoes: 'Conferindo as gravações',
  lembretes_agendados: 'Conferindo os lembretes agendados',
  historico_de_alteracoes: 'Lendo o histórico de alterações',
  abrir_questao_do_banco: 'Abrindo a questão do banco',
  panorama_do_banco: 'Vendo o panorama do banco',
  calibracao_da_importancia: 'Conferindo a calibração da importância',
  minhas_listas_do_banco: 'Abrindo as suas listas do banco',
  // ── Coordenação · cantina ──
  cantinas_e_regras: 'Conferindo as cantinas',
  calendario_da_cantina: 'Vendo o calendário da cantina',
  cardapio_da_cantina: 'Abrindo o cardápio',
  pedidos_da_refeicao: 'Contando os pedidos da refeição',
  custos_da_cantina: 'Somando os custos da cantina',
  direitos_a_refeicao: 'Conferindo os direitos a refeição',
  restricoes_alimentares: 'Conferindo as restrições alimentares',
  // ── Coordenação · captação externa ──
  buscar_candidatos_externos: 'Buscando candidatos externos',
  buscar_candidatos_por_conquista: 'Buscando candidatos por conquista',
  perfil_do_candidato_externo: 'Abrindo o perfil do candidato',
  provas_da_captacao: 'Listando as provas da captação',
  roteiro_da_coordenacao: 'Abrindo o roteiro',

  // ── Aluno · o Tio Léo ──
  meu_panorama: 'Montando o seu panorama',
  minha_zona: 'Conferindo sua zona',
  minha_agenda_do_ciclo: 'Conferindo sua agenda',
  minhas_notas: 'Buscando suas notas',
  meu_desempenho_em_simulado: 'Analisando seu simulado',
  distribuicao_do_simulado: 'Vendo como a turma foi',
  minhas_questoes_erradas: 'Revisando suas questões',
  minha_evolucao: 'Calculando sua evolução',
  minha_trajetoria: 'Carregando sua trajetória',
  meu_streak: 'Conferindo sua sequência',
  meu_insight_do_ciclo: 'Gerando seu insight do ciclo',
  o_que_mais_cai: 'Vendo o que mais cai nas provas',
  missao_de_hoje: 'Buscando a missão de hoje',
  questoes_do_banco: 'Buscando questões de provas',
  resolucao_oficial: 'Buscando a resolução oficial',
  meu_progresso_no_banco: 'Conferindo seu progresso no banco',
  roteiro_do_mentor: 'Organizando o passo a passo',
};

/**
 * O nome que a pessoa lê. `Object.hasOwn`, e não o índice direto: `constructor`
 * ou `toString` vindos do modelo achariam o protótipo do objeto e
 * desenhariam uma função no lugar do nome.
 */
export function nomeLegivelDaTool(nome: string): string {
  return Object.hasOwn(NOME_LEGIVEL_DA_TOOL, nome) ? NOME_LEGIVEL_DA_TOOL[nome] : nome;
}

/** O formato do `id` das tabelas do SAS: UUID, 8-4-4-4-12 em hexadecimal. */
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function ehUuid(valor: unknown): boolean {
  return typeof valor === 'string' && UUID.test(valor.trim());
}

function formatarArgumento(valor: unknown): string {
  return typeof valor === 'string' ? `"${valor.slice(0, 30)}"` : String(valor);
}

/**
 * Os argumentos da tool numa linha só: `materia="Física", limite=40`.
 *
 * ⚠️ NO ESCOPO DO ALUNO, IDENTIFICADOR CRU NÃO APARECE. `simulado_id="3f2a9c…"`
 * não diz nada a quem tem 17 anos e ocupa a bolha inteira — o nome legível da
 * tool já diz o que está acontecendo ("Analisando seu simulado"). Sai o
 * argumento cujo valor é UUID, e o UUID de dentro de uma lista; e sai
 * `aluno_id` com qualquer valor, porque o servidor descarta esse argumento e
 * usa o do token (docs/43 §3.2, invariante 2) — mostrar seria mostrar algo que
 * não foi usado. O resto fica.
 *
 * Na coordenação, o trace segue como era: lá o id é o mesmo da URL de cada
 * ficha (`/alunos/{id}`, `/ciclos/{id}`), e é por ele que o coordenador confere
 * de quem a resposta fala.
 */
export function resumirArgumentos(
  args: Record<string, unknown> | null | undefined,
  escopo: EscopoDaConversa = 'coordenacao',
): string {
  const doAluno = escopo === 'aluno';

  return Object.entries(args ?? {})
    .flatMap(([chave, valor]) => {
      if (valor == null) return [];
      if (!doAluno) return [`${chave}=${formatarArgumento(valor)}`];

      if (chave === 'aluno_id' || ehUuid(valor)) return [];
      if (Array.isArray(valor)) {
        const legiveis = valor.filter((item) => !ehUuid(item));
        return legiveis.length ? [`${chave}=${formatarArgumento(legiveis)}`] : [];
      }
      return [`${chave}=${formatarArgumento(valor)}`];
    })
    .join(', ');
}
