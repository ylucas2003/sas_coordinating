import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useLocation } from 'react-router-dom';

import {
  caminhoNoBloco,
  destinoDoCaminho,
  rotuloDoBloco,
  semPrefixoDoBloco,
  serieDoCaminho,
} from '../../dominio/blocos';
import type { SerieDoBloco } from '../../dominio/blocos';
import { derivarContexto } from '../../dominio/contextoDaTela';
import { useBlocos } from '../../hooks/consultas';
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
  serieDaFicha: SerieDoBloco | null;
  setSerieDaFicha: (s: SerieDoBloco | null) => void;
}>({
  titulo: null, setTitulo: () => undefined,
  recorte: null, setRecorte: () => undefined,
  serieDaFicha: null, setSerieDaFicha: () => undefined,
});

export function ProvedorMigalhas({ children }: { children: ReactNode }) {
  const [titulo, setTitulo] = useState<string | null>(null);
  const [recorte, setRecorte] = useState<RecorteDaTela | null>(null);
  const [serieDaFicha, setSerieDaFicha] = useState<SerieDoBloco | null>(null);
  const valor = useMemo(
    () => ({ titulo, setTitulo, recorte, setRecorte, serieDaFicha, setSerieDaFicha }),
    [titulo, recorte, serieDaFicha],
  );
  return <ContextoTitulo.Provider value={valor}>{children}</ContextoTitulo.Provider>;
}

/**
 * Declara de que bloco é a coisa aberta. Ficha não tem prefixo no endereço, então
 * é ela quem diz: é o que acende o bloco certo no rail e na migalha. Hook: chame
 * antes de qualquer `return` antecipado, como `useTituloDaTela`.
 */
export function useSerieDaFicha(serie: SerieDoBloco | null | undefined) {
  const { setSerieDaFicha } = useContext(ContextoTitulo);
  useEffect(() => {
    setSerieDaFicha(serie ?? null);
    return () => setSerieDaFicha(null);
  }, [serie, setSerieDaFicha]);
}

/** Em que bloco esta tela está: o que a ficha declarou, ou o que o endereço diz. */
export function useSerieDaTela(): SerieDoBloco {
  const { pathname } = useLocation();
  const { serieDaFicha } = useContext(ContextoTitulo);
  return serieDaFicha ?? serieDoCaminho(pathname);
}

/** Monta um endereço dentro do bloco desta tela: `/provas` vira `/1ano/provas`. */
export function useCaminhoDoBloco(): (caminho: string) => string {
  const serie = useSerieDaTela();
  return useCallback((caminho: string) => caminhoNoBloco(serie, caminho), [serie]);
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
    // Sem o prefixo do bloco: o chat conhece as telas, e `/1ano/alunos` é `Alunos`.
    () => derivarContexto(semPrefixoDoBloco(pathname), titulo, recorte),
    [pathname, titulo, recorte],
  );
}

const ADMIN = { texto: 'Administração', para: '/administracao' };

export function useMigalhas(): Migalha[] {
  const { pathname } = useLocation();
  const { titulo } = useContext(ContextoTitulo);
  const serie = useSerieDaTela();
  const noBloco = useCaminhoDoBloco();
  const { data: blocos = [] } = useBlocos();
  const varios = blocos.length > 1;

  return useMemo(() => {
    const partes = semPrefixoDoBloco(pathname).split('/').filter(Boolean);
    const raiz = partes[0] ?? 'painel';
    const temId = partes.length > 1;
    const folha = (padrao: string) => ({ texto: titulo ?? padrao });
    const PROVAS = { texto: 'Provas', para: noBloco('/provas') };

    const trilhaDaRota = (): Migalha[] => {
      switch (raiz) {
        case 'alunos':
          return temId ? [{ texto: 'Alunos', para: noBloco('/alunos') }, folha('Ficha do aluno')] : [{ texto: 'Alunos' }];
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
            ? [PROVAS, { texto: 'Ciclos', para: noBloco('/provas/ciclos') }, folha('Ficha do ciclo')]
            : [PROVAS, { texto: 'Ciclos' }];
        case 'simulados':
          return temId
            ? [PROVAS, { texto: 'Simulados', para: noBloco('/provas/simulados') }, folha('Ficha do simulado')]
            : [PROVAS, { texto: 'Simulados' }];
        case 'banco':
          return [{ texto: 'Banco' }];
        case 'cronograma':
          return [{ texto: 'Painel', para: noBloco('/painel') }, folha('Proposta de cronograma')];
        case 'administracao': {
          // `/administracao` é o hub; o segundo segmento é o campo, não um
          // identificador. ⚠️ A troca de telas e a captação caíam no ternário
          // antigo e a trilha dizia "Quem tem acesso" — a tela de Contas.
          const campo = partes[1];
          if (campo === 'troca-de-telas') return [ADMIN, { texto: 'Troca de Telas Automática' }];
          if (campo === 'captacao') return [ADMIN, { texto: 'Captação' }];
          if (campo === 'conexoes-de-ia') return [ADMIN, { texto: 'Conexões de IA' }];
          return temId ? [ADMIN, { texto: 'Quem tem acesso' }] : [{ texto: 'Administração' }];
        }
        // `/conectar-ia` (o consentimento do OAuth) não tem caso aqui, e não é
        // esquecimento: desde 26/10 é página pública, desenhada fora do casco
        // (`App.tsx`), sem topbar e sem trilha.
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
            // Os nomes que os cards do hub passaram a usar (docs/40 §12.2): a
            // migalha é a mesma frase que a pessoa clicou, senão ela chega numa
            // tela cujo caminho não bate com o botão.
            direitos: 'Alunos com direito',
            acesso: 'Administrar cantinas',
            custos: 'Custos',
          };
          const segundo = partes[1] ?? '';
          const nomeado = nomeados[segundo];
          if (nomeado) return [ADMIN, CANTINA, { texto: nomeado }];
          // ⚠️ Só chega aqui o que NÃO está no mapa acima. Antes de a rota de
          // custos entrar nele, `/cantina/custos` caía neste ramo e a migalha
          // dizia "Cantina › Cardápios › Custos" — um caminho que não existe.
          // Toda rota nova sob `/cantina` precisa entrar no mapa, ou passa a
          // afirmar que está dentro do calendário.
          //
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
    };

    // Com um bloco só, a trilha é a de sempre. Com vários, o primeiro degrau diz em
    // qual se está: a marca de que ninguém olha a turma errada sem perceber.
    const trilha = trilhaDaRota();
    if (!varios || destinoDoCaminho(pathname) === null) return trilha;
    return [{ texto: rotuloDoBloco(serie), para: noBloco('/painel') }, ...trilha];
  }, [pathname, titulo, serie, noBloco, varios]);
}
