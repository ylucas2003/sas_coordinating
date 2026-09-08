import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

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
  const { titulo } = useContext(ContextoTitulo);

  return useMemo(() => {
    const partes = pathname.split('/').filter(Boolean);
    const raiz = partes[0] ?? 'painel';
    const temId = partes.length > 1;
    const folha = (padrao: string) => ({ texto: titulo ?? padrao });

    switch (raiz) {
      case 'alunos':
        return temId ? [{ texto: 'Alunos', para: '/alunos' }, folha('Ficha do aluno')] : [{ texto: 'Alunos' }];
      // ⚠️ Isto lia `?aba=`, que MORREU na fase 3 do docs/39 quando as duas listas
      // ganharam rota própria (`/provas/ciclos`, `/provas/simulados`). Sem o
      // parâmetro o ternário caía sempre no `else`, e a migalha de
      // `/provas/simulados` dizia "Provas › Ciclos" — a trilha apontando para a
      // OUTRA tela. `/provas` sozinho é o hub e não tem segundo degrau.
      case 'provas': {
        const lista = partes[1];
        if (lista === 'ciclos') return [PROVAS, { texto: 'Ciclos' }];
        if (lista === 'simulados') return [PROVAS, { texto: 'Simulados' }];
        return [{ texto: 'Provas' }];
      }
      case 'ciclos':
        return temId
          ? [PROVAS, { texto: 'Ciclos', para: '/provas/ciclos' }, folha('Ficha do ciclo')]
          : [PROVAS, { texto: 'Ciclos' }];
      case 'simulados':
        return temId
          ? [PROVAS, { texto: 'Simulados', para: '/provas/simulados' }, folha('Ficha do simulado')]
          : [PROVAS, { texto: 'Simulados' }];
      case 'banco':
        return [{ texto: 'Banco' }];
      case 'administracao':
        // `/administracao` é o hub de quatro campos; `/administracao/contas` é
        // um deles. `temId` aqui é o segmento "contas", não um identificador.
        return temId ? [ADMIN, { texto: 'Quem tem acesso' }] : [{ texto: 'Administração' }];
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
      // A CANTINA não tinha caso nenhum e caía no `default`: as seis rotas dela
      // anunciavam "Painel" na topbar — a trilha dizia que a pessoa estava numa
      // tela em que ela não estava. Achado na verificação no browser da fase 6.
      //
      // Ela pendura sob Administração porque é de lá que o card leva
      // (docs/39 fase 5), e não do rail — a cantina não é um sexto destino.
      case 'cantina': {
        if (!temId) return [ADMIN, { texto: 'Cantina' }];
        const CANTINA = { texto: 'Cantina', para: '/cantina' };
        const nomeados: Record<string, string> = {
          cardapios: 'Cardápios',
          direitos: 'Quem come aqui',
          acesso: 'Administrar cantinas',
        };
        const segundo = partes[1] ?? '';
        const nomeado = nomeados[segundo];
        if (nomeado) return [ADMIN, CANTINA, { texto: nomeado }];
        // O que sobra é uma DATA (`/cantina/:data` e `/cantina/:data/:refeicao`),
        // e aí quem nomeia a folha é a tela, por `useTituloDaTela` — só ela sabe
        // dizer "9 de setembro" em vez de repetir o ISO da URL.
        return [
          ADMIN,
          CANTINA,
          { texto: 'Cardápios', para: '/cantina/cardapios' },
          folha('O dia'),
        ];
      }
      default:
        return [{ texto: 'Painel' }];
    }
  }, [pathname, titulo]);
}
