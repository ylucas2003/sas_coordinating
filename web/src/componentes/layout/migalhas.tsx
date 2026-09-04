import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

import { derivarContexto } from '../../dominio/contextoDaTela';
import type { ContextoDaTela, RecorteDaTela } from '../../dominio/contextoDaTela';

/**
 * Migalhas da topbar.
 *
 * A trilha até a tela sai da rota — é informação que o roteador já tem. O que
 * ele não tem é o nome da coisa aberta ("ITA 2026 · Simulado 06"), que só
 * chega depois da consulta; por isso a ficha declara o próprio título com
 * `useTituloDaTela` e o casco o costura no fim da trilha.
 */

export interface Migalha {
  texto: string;
  /** Ausente = degrau atual, não é link. */
  para?: string;
}

const ContextoTitulo = createContext<{
  titulo: string | null;
  setTitulo: (t: string | null) => void;
  recorte: RecorteDaTela | null;
  setRecorte: (r: RecorteDaTela | null) => void;
}>({
  titulo: null, setTitulo: () => undefined,
  recorte: null, setRecorte: () => undefined,
});

export function ProvedorMigalhas({ children }: { children: ReactNode }) {
  const [titulo, setTitulo] = useState<string | null>(null);
  const [recorte, setRecorte] = useState<RecorteDaTela | null>(null);
  const valor = useMemo(
    () => ({ titulo, setTitulo, recorte, setRecorte }),
    [titulo, recorte],
  );
  return <ContextoTitulo.Provider value={valor}>{children}</ContextoTitulo.Provider>;
}

/**
 * Declara o nome da coisa aberta nesta tela. `undefined` enquanto carrega —
 * a trilha cai no rótulo genérico até o dado chegar.
 */
export function useTituloDaTela(texto: string | null | undefined) {
  const { setTitulo } = useContext(ContextoTitulo);
  useEffect(() => {
    setTitulo(texto ?? null);
    return () => setTitulo(null);
  }, [texto, setTitulo]);
}

/**
 * Declara o recorte que a tela está mostrando — ciclo, fase, régua, filtros.
 *
 * Existe pelo mesmo motivo do `useTituloDaTela`: é informação que só a tela
 * tem. A diferença é o consumidor — o título vai para a migalha, o recorte vai
 * para o assistente, que sem ele não sabe do que "e a Física?" está falando
 * (docs/31 §P2). O Painel guarda esses filtros em `useState` e eles não
 * aparecem na URL, então não há como deduzi-los da rota.
 *
 * Passe um objeto MEMOIZADO: ele entra na dependência do efeito.
 */
export function useRecorteDaTela(recorte: RecorteDaTela | null | undefined) {
  const { setRecorte } = useContext(ContextoTitulo);
  useEffect(() => {
    setRecorte(recorte ?? null);
    return () => setRecorte(null);
  }, [recorte, setRecorte]);
}

/**
 * O contexto completo da navegação, para quem precisa saber onde o usuário
 * está — hoje, só o chat.
 */
export function useContextoDaTela(): ContextoDaTela {
  const { pathname } = useLocation();
  const { titulo, recorte } = useContext(ContextoTitulo);
  return useMemo(
    () => derivarContexto(pathname, titulo, recorte),
    [pathname, titulo, recorte],
  );
}

const PROVAS = { texto: 'Provas', para: '/provas' };
const ADMIN = { texto: 'Administração', para: '/administracao' };

export function useMigalhas(): Migalha[] {
  const { pathname } = useLocation();
  const [params] = useSearchParams();
  const { titulo } = useContext(ContextoTitulo);
  const aba = params.get('aba') === 'simulados' ? 'simulados' : 'ciclos';

  return useMemo(() => {
    const partes = pathname.split('/').filter(Boolean);
    const raiz = partes[0] ?? 'painel';
    const temId = partes.length > 1;
    const folha = (padrao: string) => ({ texto: titulo ?? padrao });

    switch (raiz) {
      case 'alunos':
        return temId ? [{ texto: 'Alunos', para: '/alunos' }, folha('Ficha do aluno')] : [{ texto: 'Alunos' }];
      case 'provas':
        return [PROVAS, { texto: aba === 'simulados' ? 'Simulados' : 'Ciclos' }];
      case 'ciclos':
        return temId
          ? [PROVAS, { texto: 'Ciclos', para: '/provas' }, folha('Ficha do ciclo')]
          : [PROVAS, { texto: 'Ciclos' }];
      case 'simulados':
        return temId
          ? [PROVAS, { texto: 'Simulados', para: '/provas?aba=simulados' }, folha('Ficha do simulado')]
          : [PROVAS, { texto: 'Simulados' }];
      case 'banco':
        return [{ texto: 'Banco' }];
      case 'administracao':
        return [{ texto: 'Administração' }];
      case 'auditoria':
        return [ADMIN, { texto: 'Auditoria' }];
      case 'calibracao':
        return [ADMIN, { texto: 'Calibração' }];
      case 'importar':
        return [ADMIN, { texto: 'Importar planilha' }];
      case 'integracoes':
        return temId
          ? [ADMIN, { texto: 'Integrações', para: '/integracoes' }, folha('Sincronização')]
          : [ADMIN, { texto: 'Integrações' }];
      default:
        return [{ texto: 'Painel' }];
    }
  }, [pathname, aba, titulo]);
}
