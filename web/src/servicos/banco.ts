// Operações do banco de questões ITA · IME (docs/22 §2.1), prefixo `/banco`.
//
// Mesma convenção de `api.ts`: funções puras de I/O, sem estado e sem
// invalidação — quem invalida é o hook que chama (ver src/hooks/banco.ts).
//
// Arquivo próprio, e não mais um bloco em `api.ts`: o banco de questões é uma
// aba inteira com API própria, e separar mantém o diff do sprint legível.

import { ErroApi, del, get, patch, post, put, qs } from './http';
import type {
  EstatisticasBanco, EstudoQuestao, FiltrosBanco, Lista, ListaResumo, MateriaBanco,
  PaginaQuestoes, QuestaoVestibular, RemendoEstudo, RemendoLista, TaxonomiaMateria,
  VestibularBanco,
} from '../tipos/banco';

const enc = encodeURIComponent;

// ─── Leitura (vale para aluno e coordenação) ─────────────────────────────
// Conteúdo público de prova, sem dado pessoal: o backend não separa por perfil
// nestas três rotas (docs/22 §2.3).

/** Sem `materia`, devolve as três árvores de uma vez. */
export const obterTaxonomia = (materia?: MateriaBanco) =>
  get<TaxonomiaMateria[]>(`/banco/taxonomia${qs({ materia })}`);

export const listarQuestoes = (filtros: FiltrosBanco = {}) =>
  get<PaginaQuestoes>(`/banco/questoes${qs({ ...filtros })}`);

export const obterQuestao = (id: string) => get<QuestaoVestibular>(`/banco/questoes/${enc(id)}`);

/** Agrega sobre a tabela inteira; nunca pagina (docs/22 §2.2). */
export const estatisticasBanco = (materia: MateriaBanco, vestibular?: VestibularBanco) =>
  get<EstatisticasBanco>(`/banco/estatisticas${qs({ materia, vestibular })}`);

// ─── Listas (o dono é a sessão) ──────────────────────────────────────────
// Nenhuma rota daqui recebe id de dono: o backend o tira do JWT, e é assim que
// um aluno não enxerga lista de outro (docs/22 §5.2).

export const listarListas = () => get<ListaResumo[]>('/banco/listas');

export const criarLista = (titulo: string) => post<Lista>('/banco/listas', { titulo });

export const obterLista = (id: string) => get<Lista>(`/banco/listas/${enc(id)}`);

/** `questaoIds` é a ordem completa — reordenar é mandar a lista inteira. */
export const atualizarLista = (id: string, remendo: RemendoLista) =>
  patch<Lista>(`/banco/listas/${enc(id)}`, remendo);

/**
 * A rota responde 204, e o `del` do http.ts sempre tenta ler JSON — o parse do
 * corpo vazio falha **depois** de a exclusão já ter acontecido. Erro de verdade
 * chega como `ErroApi`, levantado antes da leitura do corpo, então só o parse
 * vazio passa por aqui.
 */
export const apagarLista = (id: string) =>
  del<void>(`/banco/listas/${enc(id)}`).catch((erro: unknown) => {
    if (erro instanceof ErroApi) throw erro;
  });

/** Acrescenta ao fim da lista; devolve a lista já atualizada. */
export const adicionarQuestaoNaLista = (listaId: string, questaoId: string) =>
  post<Lista>(`/banco/listas/${enc(listaId)}/questoes/${enc(questaoId)}`);

export const removerQuestaoDaLista = (listaId: string, questaoId: string) =>
  del<Lista>(`/banco/listas/${enc(listaId)}/questoes/${enc(questaoId)}`);

// ─── Estudo (só aluno) ───────────────────────────────────────────────────

/** O que o aluno já resolveu e anotou. Questão ausente = não tocada. */
export const listarEstudo = () => get<EstudoQuestao[]>('/banco/estudo');

/** `PUT` porque cria a linha na primeira marcação e atualiza nas seguintes. */
export const atualizarEstudo = (questaoId: string, remendo: RemendoEstudo) =>
  put<EstudoQuestao>(`/banco/estudo/${enc(questaoId)}`, remendo);
