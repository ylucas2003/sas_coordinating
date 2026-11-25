// Cadastro de aluno no Canvas (docs/46), prefixo `/administracao/cadastro-canvas`.
// Todas as rotas são de administrador — o backend recusa o resto com 403.

import { get, post, postArquivo, qs } from './http';
import type {
  CadastroDeAluno, CatalogoDePacotes, LinhaDaPrevia, LoteNoCanvas, PreviaDoLote,
  ResultadoDoCadastro,
} from '../tipos/cadastroCanvas';

const BASE = '/administracao/cadastro-canvas';

export const listarPacotes = (ano?: number | null) =>
  get<CatalogoDePacotes>(`${BASE}/pacotes${qs({ ano: ano ?? undefined })}`);

export const cadastrarAluno = (corpo: CadastroDeAluno) =>
  post<ResultadoDoCadastro>(`${BASE}/aluno`, corpo);

export const previaDoLote = (arquivo: File, ano?: number | null) =>
  postArquivo<PreviaDoLote>(`${BASE}/lote/previa`, arquivo, {
    campos: { ano: ano != null ? String(ano) : null },
  });

export const enviarLote = (ano: number, linhas: LinhaDaPrevia[]) =>
  post<LoteNoCanvas>(`${BASE}/lote`, {
    ano,
    linhas: linhas.map((l) => ({
      linha: l.linha, matricula: l.matricula, nome: l.nome, email: l.email,
      serie: l.serie, sede_id: l.sede_id,
    })),
  });

export const lotesRecentes = () => get<LoteNoCanvas[]>(`${BASE}/lote`);

export const situacaoDoLote = (id: string) =>
  get<LoteNoCanvas>(`${BASE}/lote/${encodeURIComponent(id)}`);
