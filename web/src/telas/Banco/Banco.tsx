import { useCallback, useMemo, useState } from 'react';
import { NavLink, Navigate, Route, Routes } from 'react-router-dom';

import {
  useAdicionarQuestaoNaLista,
  useCriarLista,
  useLista,
  useListas,
  useRemoverQuestaoDaLista,
} from '../../hooks/banco';
import type { FiltrosBanco as Filtros } from '../../tipos/banco';
import { Estatisticas } from './Estatisticas';
import { FiltrosBanco } from './FiltrosBanco';
import { ListaQuestoes } from './ListaQuestoes';
import { Mensagem } from './Mensagem';
import { MinhaLista } from './MinhaLista';

// Banco de questões ITA · IME — a casca da aba, nos dois cascos (docs/22 §P3).
//
// Uma tela só para aluno e coordenação, e não duas: o produto é o mesmo, o que
// muda é permissão. Duplicar em `telas/Aluno/Banco` e `telas/Banco` garantiria
// divergência — o primeiro conserto de CSS iria para um lado só (docs/22 §3.1).
//
// A tela devolve `.tela` (a coluna de blocos), que serve aos dois cascos: na
// coordenação vira filha do `<main>` de AppShell, no aluno é mais um bloco da
// coluna de `.alu-body__inner`.
//
// Os filtros são a coluna `.banco-filtros` de `.banco-layout`, que nasce
// empilhada no celular e vira coluna a partir de 880px. O resto da coordenação
// usa a `.barra-filtros` horizontal; aqui não, porque são muitos assuntos por
// edital e eles não caberiam numa linha (docs/22 §3.5).

/**
 * Perfil de quem está vendo a aba. Coincide com `DonoLista` (tipos/banco.ts):
 * o dono da lista é sempre o perfil da sessão. Não se chama `Perfil` porque
 * esse nome já é o perfil de desempenho do aluno em `tipos/dominio.ts`.
 */
export type PerfilBanco = 'aluno' | 'coordenacao';

/** Sub-abas são ROTAS, não estado: recarregar em /banco/lista continua ali (docs/22 §3.3). */
const SUB_ABAS = [
  { para: '/banco', rotulo: 'Questões', fim: true, soAluno: false },
  { para: '/banco/estatisticas', rotulo: 'Estatísticas', fim: false, soAluno: false },
  { para: '/banco/lista', rotulo: 'Minha lista', fim: false, soAluno: false },
  // A mensagem é do casco do aluno, decidido em 22/08 (docs/22 §P6).
  { para: '/banco/mensagem', rotulo: 'Mensagem', fim: false, soAluno: true },
];

/** Página inicial e tamanho de página — o mesmo padrão do servidor (consultas.py). */
const FILTROS_INICIAIS: Filtros = { pagina: 1, porPagina: 20 };

const TITULO_LISTA_PADRAO = 'Minha lista';

/**
 * Campo vazio é campo ausente. Sem isto `{ materia: undefined }` e `{}` viram
 * duas chaves de cache diferentes para a mesma pergunta (hooks/banco.ts usa o
 * objeto inteiro como `queryKey`).
 */
function semVazios(filtros: Filtros): Filtros {
  const limpo: Record<string, unknown> = {};
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor !== undefined && valor !== null && valor !== '') limpo[chave] = valor;
  }
  return limpo as Filtros;
}

export function Banco({ perfil }: { perfil: PerfilBanco }) {
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_INICIAIS);
  const [listaEscolhidaId, setListaEscolhidaId] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const { data: listas = [] } = useListas();
  // Sem escolha explícita, a lista de trabalho é a mais recente — `listarListas`
  // já devolve ordenado por `atualizada_em desc` (idx_lista_questoes_dono, 0029).
  const listaAtivaId = listaEscolhidaId ?? listas[0]?.id ?? null;
  const { data: listaAtiva } = useLista(listaAtivaId);

  const criarLista = useCriarLista();
  const adicionarNaLista = useAdicionarQuestaoNaLista();
  const removerDaLista = useRemoverQuestaoDaLista();

  const idsNaLista = useMemo(
    () => new Set((listaAtiva?.questoes ?? []).map((q) => q.id)),
    [listaAtiva],
  );

  /** Qualquer mudança de filtro volta para a página 1: a página 7 do recorte antigo não existe no novo. */
  const filtrar = useCallback((mudanca: Partial<Filtros>) => {
    setFiltros((atual) => semVazios({ ...atual, pagina: 1, ...mudanca }));
  }, []);

  const irParaPagina = useCallback((pagina: number) => {
    setFiltros((atual) => ({ ...atual, pagina }));
  }, []);

  /**
   * Põe ou tira a questão da lista de trabalho.
   *
   * Sem nenhuma lista, cria uma em vez de desabilitar o botão: um botão que
   * não faz nada até o usuário descobrir outra aba é um beco sem saída — e
   * montar lista vale para os dois perfis (docs/22 §P5).
   */
  const alternarNaLista = useCallback(
    async (questaoId: string) => {
      setErro(null);
      try {
        let id = listaAtivaId;
        if (!id) {
          id = (await criarLista.mutateAsync(TITULO_LISTA_PADRAO)).id;
          setListaEscolhidaId(id);
        }
        if (idsNaLista.has(questaoId)) {
          await removerDaLista.mutateAsync({ listaId: id, questaoId });
        } else {
          await adicionarNaLista.mutateAsync({ listaId: id, questaoId });
        }
      } catch (e) {
        setErro((e as Error).message || 'Não foi possível atualizar a lista.');
      }
    },
    [adicionarNaLista, criarLista, idsNaLista, listaAtivaId, removerDaLista],
  );

  const abas = SUB_ABAS.filter((aba) => !aba.soAluno || perfil === 'aluno');

  return (
    <div className="tela">
      {/*
        banco.css não tem classe de sub-navegação, e a régua deste sprint é usar
        as classes que existem em vez de inventar (docs/22 §7.4). O arranjo é
        uma fila de chips, e chip é `.banco-chip`; só a fila em si vai por
        `style`, que o React aplica por CSSOM e a CSP de produção aceita.
      */}
      <nav aria-label="Seções do banco" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {abas.map((aba) => (
          <NavLink
            key={aba.para}
            to={aba.para}
            end={aba.fim}
            className={({ isActive }) => `banco-chip${isActive ? ' banco-chip--ativo' : ''}`}
          >
            {aba.rotulo}
          </NavLink>
        ))}
      </nav>

      {erro && <p className="banco-cabecalho__meta">{erro}</p>}

      <Routes>
        <Route
          index
          element={
            <div className="banco-layout">
              <FiltrosBanco filtros={filtros} onFiltrar={filtrar} />
              <div className="banco-conteudo">
                <ListaQuestoes
                  filtros={filtros}
                  perfil={perfil}
                  onPagina={irParaPagina}
                  idsNaLista={idsNaLista}
                  onAlternarNaLista={alternarNaLista}
                  tituloListaAtiva={listaAtiva?.titulo ?? null}
                />
              </div>
            </div>
          }
        />
        <Route
          path="estatisticas"
          element={<Estatisticas materiaInicial={filtros.materia} vestibular={filtros.vestibular} />}
        />
        <Route
          path="lista"
          element={
            <MinhaLista
              perfil={perfil}
              listaAtivaId={listaAtivaId}
              onEscolherLista={setListaEscolhidaId}
            />
          }
        />
        {perfil === 'aluno' && <Route path="mensagem" element={<Mensagem />} />}
        {/* Sub-aba desconhecida (ou /banco/mensagem na coordenação) volta ao banco. */}
        <Route path="*" element={<Navigate to="/banco" replace />} />
      </Routes>
    </div>
  );
}
