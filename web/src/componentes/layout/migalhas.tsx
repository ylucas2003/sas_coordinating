import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';

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
}>({ titulo: null, setTitulo: () => undefined });

export function ProvedorMigalhas({ children }: { children: ReactNode }) {
  const [titulo, setTitulo] = useState<string | null>(null);
  const valor = useMemo(() => ({ titulo, setTitulo }), [titulo]);
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
      case 'importar':
        return [ADMIN, { texto: 'Importar planilha' }];
      default:
        return [{ texto: 'Painel' }];
    }
  }, [pathname, aba, titulo]);
}
