// Onde o usuário está — o que o assistente precisa saber para "e esse aluno?"
// ter referente (docs/31 §P2).
//
// A derivação é PURA e mora aqui, e não dentro do provedor, porque tem
// ramificação por rota e precisa de teste: um contexto errado é pior que
// contexto nenhum — o assistente responde com confiança sobre a tela errada.
//
// ⚠️ Este objeto viaja para o backend e entra no prompt. Ele é montado com
// campos fechados de propósito: nada de string livre vinda da tela, e os
// nomes que chegam aqui são reconferidos no servidor contra o banco antes de
// virar texto para o modelo.

/** O recorte que a tela está mostrando, quando ela tem um a declarar. */
export interface RecorteDaTela {
  cicloId?: string;
  fase?: 1 | 2;
  /** Slug da régua de corte em uso. */
  criterio?: string;
  sedeIds?: string[];
  turmaIds?: string[];
}

export interface EntidadeAberta {
  tipo: 'aluno' | 'ciclo' | 'simulado';
  id: string;
  /** O que a tela mostra no título. O servidor confere contra o banco. */
  nome?: string;
}

export interface ContextoDaTela {
  /** Identificador estável da tela, não o rótulo visível. */
  tela: string;
  caminho: string;
  entidade?: EntidadeAberta;
  recorte?: RecorteDaTela;
}

/** Rota → (tela, tipo de entidade quando a rota abre uma ficha). */
const ROTAS: Record<string, { tela: string; fichaDe?: EntidadeAberta['tipo'] }> = {
  painel: { tela: 'painel' },
  alunos: { tela: 'alunos', fichaDe: 'aluno' },
  provas: { tela: 'provas' },
  ciclos: { tela: 'provas', fichaDe: 'ciclo' },
  simulados: { tela: 'provas', fichaDe: 'simulado' },
  banco: { tela: 'banco' },
  auditoria: { tela: 'auditoria' },
  administracao: { tela: 'administracao' },
  importar: { tela: 'importar' },
  integracoes: { tela: 'integracoes' },
};

/**
 * Monta o contexto a partir da rota, do título que a ficha declarou e do
 * recorte que a tela declarou.
 *
 * Título e recorte são declarados pela TELA, não deduzidos da URL, porque o
 * recorte que mais importa — ciclo, fase, régua e filtros do Painel — mora em
 * `useState` e não aparece no caminho. Um contexto que acerta três telas e
 * mente na mais usada seria pior que nenhum.
 */
export function derivarContexto(
  caminho: string,
  titulo?: string | null,
  recorte?: RecorteDaTela | null,
): ContextoDaTela {
  const partes = caminho.split('/').filter(Boolean);
  // Raiz vazia é raiz vazia, não "painel". A home do ALUNO é `/`, e a folha do
  // Tio Léo usa a mesma `Conversa` da coordenação: com o default antigo, o
  // mentor de um menor recebia "Tela aberta: Painel — a lista de alunos do
  // ciclo, ordenada pela régua de corte". A coordenação não perde nada, porque
  // `App.tsx` redireciona `/` para `/painel` antes de qualquer render.
  const raiz = partes[0] ?? '';
  const rota = ROTAS[raiz];

  const ctx: ContextoDaTela = { tela: rota?.tela ?? raiz, caminho };

  const id = partes[1];
  if (rota?.fichaDe && id) {
    ctx.entidade = { tipo: rota.fichaDe, id, ...(titulo ? { nome: titulo } : {}) };
  }

  const limpo = recorte && limparRecorte(recorte);
  if (limpo) ctx.recorte = limpo;

  return ctx;
}

/** Tira chaves vazias — recorte com listas vazias só ocupa espaço no prompt. */
function limparRecorte(r: RecorteDaTela): RecorteDaTela | null {
  const saida: RecorteDaTela = {};
  if (r.cicloId) saida.cicloId = r.cicloId;
  if (r.fase) saida.fase = r.fase;
  if (r.criterio) saida.criterio = r.criterio;
  if (r.sedeIds?.length) saida.sedeIds = r.sedeIds;
  if (r.turmaIds?.length) saida.turmaIds = r.turmaIds;
  return Object.keys(saida).length ? saida : null;
}
