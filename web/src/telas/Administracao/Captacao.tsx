import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, Busca, Pills, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { faixasOferecidas, ROTULO_FAIXA, ROTULO_PUBLICO, rotuloEvidencia } from '../../dominio/captacao';
import { resumirSelecao, resumirTexto, resumirUnica } from '../../dominio/filtros';
import { useCandidatos, useProvas } from '../../hooks/captacao';
import type {
  CandidatoPorNome, Faixa, FiltrosCaptacao as Filtros, Publico, StatusCaptacao,
} from '../../tipos/captacao';

import '../../../styles/captacao.css';

// Captação externa (docs/41) — candidatos achados FORA do colégio, cruzando
// resultado público de olimpíada/vestibular/concurso. Não tem nada a ver com
// `aluno`: é gente que nunca colocou os pés aqui, e a lista existe pra achar
// quem convidar.
//
// **Paginação de verdade**, ao contrário de `Alunos.tsx` — e isso não é
// inconsistência, é a mesma régua do `Banco` (CLAUDE.md armadilha 2): lá o
// volume é fixo (~900 alunos, sem teto de propósito); aqui é gente de fora,
// sem teto natural — mais de 100 mil nomes e crescendo a cada fonte nova.
//
// A ordem padrão do servidor é por Nº DE CONQUISTAS, decrescente
// (`routes/captacao.py::listar_candidatos`): quem cruzou premiação em quatro
// anos seguidos é lead mais forte que quem apareceu uma vez, e é essa
// pergunta — "quem já provou que é bom?" — que a tela responde primeiro.
//
// Cada NOME é uma linha, sempre (`v_candidato_externo_por_nome`, 0063) —
// sem fila de fusão, sem "pendente": escola/cidade/UF/status são o CONJUNTO
// de tudo que qualquer conquista/perfil daquele nome já teve, e clicar no
// nome abre a mesma tela pra qualquer um (`CaptacaoPerfil.tsx`), fragmentado
// ou não (simplificação de 25/09/2026).
//
// Dois caminhos na MESMA lista (docs/41 §20): do nome pras conquistas (a busca
// por nome, como sempre), e das conquistas pros nomes — prova, resultado, ano
// e público. Os critérios de conquista valem todos para UMA MESMA conquista;
// quando algum está ativo, a coluna "Por que está aqui" mostra qual conquista
// fez o nome entrar. A unidade do resultado não muda (um nome, que abre o
// mesmo `CaptacaoPerfil`), por isso não é uma tela à parte.

const STATUS_LABEL: Record<StatusCaptacao, string> = {
  novo: 'Novo',
  contatado: 'Contatado',
  interessado: 'Interessado',
  matriculado: 'Matriculado',
  descartado: 'Descartado',
};

const OPCOES_STATUS: Array<{ valor: StatusCaptacao; label: string }> = (
  Object.keys(STATUS_LABEL) as StatusCaptacao[]
).map((valor) => ({ valor, label: STATUS_LABEL[valor] }));

const OPCOES_CONQUISTAS: Array<{ valor: number; label: string }> = [
  { valor: 2, label: '2+ conquistas' },
  { valor: 3, label: '3+ conquistas' },
  { valor: 4, label: '4+ conquistas' },
];

const PUBLICOS = Object.keys(ROTULO_PUBLICO) as Publico[];
const OPCOES_PUBLICO = PUBLICOS.map((valor) => ({ valor, label: ROTULO_PUBLICO[valor] }));

/** "desde 2026" … "desde 2022" — conquista antiga é lead frio; cinco anos
 * cobrem quem ainda está no Fundamental 2 hoje. */
const ANO_CORRENTE = new Date().getFullYear();
const OPCOES_ANO = [0, 1, 2, 3, 4].map((recuo) => ({
  valor: ANO_CORRENTE - recuo,
  label: `desde ${ANO_CORRENTE - recuo}`,
}));

const POR_PAGINA = 20;
const FILTROS_INICIAIS: Filtros = { pagina: 1, por_pagina: POR_PAGINA };

/** Campo vazio é campo ausente — senão `{ uf: '' }` e `{}` (ou `{ prova: [] }`)
 * viram cache diferente pra mesma pergunta. */
function semVazios(filtros: Filtros): Filtros {
  const limpo: Record<string, unknown> = {};
  for (const [chave, valor] of Object.entries(filtros)) {
    if (valor === undefined || valor === null || valor === '') continue;
    if (Array.isArray(valor) && valor.length === 0) continue;
    limpo[chave] = valor;
  }
  return limpo as Filtros;
}

/** Liga/desliga um valor numa seleção múltipla, devolvendo lista nova. */
function alternar<V>(lista: readonly V[] | undefined, valor: V): V[] {
  const atual = lista ?? [];
  return atual.includes(valor) ? atual.filter((v) => v !== valor) : [...atual, valor];
}

/** A célula de conquistas: participação (1ª fase do ITA feita ou faltada)
 * não conta como conquista desde a 0068, mas continua visível ao lado. */
function fmtConquistas(c: CandidatoPorNome): string {
  const base = c.conquistas_total ? String(c.conquistas_total) : '—';
  const ate = c.ano_mais_recente ? ` · até ${c.ano_mais_recente}` : '';
  const participou = c.participacoes
    ? ` · ${c.participacoes} ${c.participacoes === 1 ? 'participação' : 'participações'}`
    : '';
  return `${base}${ate}${participou}`;
}

function fmtQuando(iso: string): string {
  return new Date(iso).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

/** Lista curta em texto — "—" vazia, item único sem vírgula, resto junto por ", ".
 * `?? []` é defesa de verdade, não enfeite: a view (`v_candidato_externo_por_nome`,
 * 0065) já tinha o bug de mandar `null` em vez de `[]` quando nenhuma
 * conquista do nome preenchia o campo — derrubava a tela inteira em toda
 * busca que trouxesse um desses nomes pra página (achado em produção,
 * 28/09/2026). O SQL foi corrigido, mas esta função é a última linha de
 * defesa contra a mesma classe de bug voltar sem avisar. */
function fmtLista(itens: string[] | null | undefined): string {
  return itens?.length ? itens.join(', ') : '—';
}

export function Captacao() {
  const [filtros, setFiltros] = useState<Filtros>(FILTROS_INICIAIS);
  const [ufDigitada, setUfDigitada] = useState('');
  const { data, isPending, isError, isPlaceholderData } = useCandidatos(filtros);
  const { data: provas } = useProvas();

  const candidatos = data?.candidatos ?? [];
  const total = data?.total ?? 0;
  const anoIngresso = data?.ano_ingresso ?? ANO_CORRENTE + 1;
  const listaDeProvas = provas?.provas ?? [];
  const provasEscolhidas = filtros.prova ?? [];
  const faixasEscolhidas = filtros.faixa ?? [];
  const publicosEscolhidos = filtros.publico ?? [];
  // A ativa fica sempre visível, mesmo se a prova escolhida depois não a
  // produzir — senão vira filtro em vigor que ninguém enxerga pra desmarcar.
  const opcoesFaixa = [
    ...new Set<Faixa>([...faixasOferecidas(provasEscolhidas, listaDeProvas), ...faixasEscolhidas]),
  ].map((valor) => ({ valor, label: ROTULO_FAIXA[valor] }));
  const opcoesProva = listaDeProvas.map((p) => ({ valor: p.nome, label: p.nome }));
  const porConquista = Boolean(
    provasEscolhidas.length || faixasEscolhidas.length || filtros.ano_min || publicosEscolhidos.length,
  );
  const pagina = data?.pagina ?? filtros.pagina ?? 1;
  const porPagina = data?.por_pagina ?? filtros.por_pagina ?? POR_PAGINA;
  const totalPaginas = Math.max(1, Math.ceil(total / porPagina));

  /** Qualquer mudança de filtro volta pra página 1 — a página 40 do recorte antigo pode nem existir no novo. */
  const filtrar = useCallback((mudanca: Partial<Filtros>) => {
    setFiltros((atual) => semVazios({ ...atual, pagina: 1, ...mudanca }));
  }, []);

  const algumAtivo = Boolean(
    porConquista || filtros.uf || filtros.status_captacao || filtros.conquistas_min || filtros.busca,
  );

  return (
    <div className="tela">
      <CabecaDeCampo titulo="Captação externa" para="/administracao" destino="Administração" />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          Gente que nunca estudou aqui, achada cruzando listas públicas de premiação de olimpíada e
          vestibular. Procure pelo nome, ou pelo que a pessoa conquistou — prova, resultado, ano e
          público — e abra o nome pra ver tudo dela.
        </p>
      </div>

      <BarraFiltros
        tela="captacao"
        algumAtivo={algumAtivo}
        onLimpar={() => {
          setUfDigitada('');
          setFiltros(FILTROS_INICIAIS);
        }}
        grupos={[
          {
            chave: 'prova',
            rotulo: 'Prova',
            resumo: resumirSelecao(new Set(provasEscolhidas), opcoesProva, 'prova', 'provas'),
            corpo: (
              <Pills
                opcoes={opcoesProva}
                selecionados={new Set(provasEscolhidas)}
                onToggle={(v) => filtrar({ prova: alternar(filtros.prova, v) })}
              />
            ),
          },
          {
            chave: 'faixa',
            rotulo: 'Resultado',
            resumo: resumirSelecao(new Set(faixasEscolhidas), opcoesFaixa, 'resultado', 'resultados'),
            corpo: (
              <Pills
                opcoes={opcoesFaixa}
                selecionados={new Set(faixasEscolhidas)}
                onToggle={(v) => filtrar({ faixa: alternar(filtros.faixa, v) })}
              />
            ),
          },
          {
            chave: 'ano',
            rotulo: 'Ano',
            resumo: resumirUnica(filtros.ano_min, OPCOES_ANO),
            corpo: (
              <PillsUnica
                opcoes={OPCOES_ANO}
                selecionado={filtros.ano_min ?? null}
                onSelecionar={(v) => filtrar({ ano_min: filtros.ano_min === v ? undefined : v })}
              />
            ),
          },
          {
            chave: 'publico',
            rotulo: `Público em ${anoIngresso}`,
            resumo: resumirSelecao(new Set(publicosEscolhidos), OPCOES_PUBLICO, 'público', 'públicos'),
            corpo: (
              <Pills
                opcoes={OPCOES_PUBLICO}
                selecionados={new Set(publicosEscolhidos)}
                onToggle={(v) => filtrar({ publico: alternar(filtros.publico, v) })}
              />
            ),
          },
          {
            chave: 'conquistas',
            rotulo: 'Conquistas',
            resumo: filtros.conquistas_min ? `${filtros.conquistas_min}+` : null,
            corpo: (
              <PillsUnica
                opcoes={OPCOES_CONQUISTAS}
                selecionado={filtros.conquistas_min ?? null}
                onSelecionar={(v) =>
                  filtrar({ conquistas_min: filtros.conquistas_min === v ? undefined : v })}
              />
            ),
          },
          {
            chave: 'status',
            rotulo: 'Status',
            resumo: filtros.status_captacao ? STATUS_LABEL[filtros.status_captacao] : null,
            corpo: (
              <PillsUnica
                opcoes={OPCOES_STATUS}
                selecionado={filtros.status_captacao ?? null}
                onSelecionar={(v) =>
                  filtrar({ status_captacao: filtros.status_captacao === v ? undefined : v })}
              />
            ),
          },
          {
            chave: 'uf',
            rotulo: 'UF',
            resumo: filtros.uf ?? null,
            corpo: (
              <input
                className="pill-campo"
                style={{ width: 64, textTransform: 'uppercase' }}
                value={ufDigitada}
                maxLength={2}
                placeholder="ex.: CE"
                aria-label="Filtrar por UF"
                onChange={(e) => setUfDigitada(e.target.value.toUpperCase())}
                onBlur={() => filtrar({ uf: ufDigitada || undefined })}
                onKeyDown={(e) => e.key === 'Enter' && filtrar({ uf: ufDigitada || undefined })}
              />
            ),
          },
          {
            chave: 'busca',
            rotulo: 'Nome',
            resumo: resumirTexto(filtros.busca ?? ''),
            corpo: (
              <Busca
                valor={filtros.busca ?? ''}
                onChange={(v) => filtrar({ busca: v || undefined })}
                placeholder="Nome do candidato…"
                rotulo="Buscar candidato por nome"
              />
            ),
          },
        ]}
      />

      <section className="card">
        <div className="tela-cabecalho" style={{ padding: '10px 16px 0' }}>
          <p className="tela-subtitulo">
            {isPending
              ? 'Carregando…'
              : `${total.toLocaleString('pt-BR')} ${total === 1 ? 'nome' : 'nomes'} · página ${pagina} de ${totalPaginas}`}
            {isPlaceholderData && ' · atualizando…'}
          </p>
        </div>

        {isError ? (
          <div className="empty-state">Não foi possível carregar os candidatos.</div>
        ) : !isPending && candidatos.length === 0 ? (
          <div className="empty-state">
            Nenhum candidato com esses filtros.
            <div className="empty-state__hint">Tire um filtro ou limpe a busca.</div>
          </div>
        ) : (
          <table className="data-table data-table--cartoes">
            <thead>
              <tr>
                <th>Nome</th>
                {porConquista && <th>Por que está aqui</th>}
                <th>Escola</th>
                <th>Cidade/UF</th>
                <th>Conquistas</th>
                <th>Status</th>
                <th>Última atualização</th>
              </tr>
            </thead>
            <tbody>
              {candidatos.map((c) => (
                <tr key={c.nome_normalizado}>
                  <td data-rotulo="Nome" data-titulo>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                      <Link to={`/administracao/captacao/${encodeURIComponent(c.nome_normalizado)}`}>
                        {c.nome}
                      </Link>
                      {/* perfis_no_grupo > 1 é o único sinal de fragmentação
                          que sobra — texto solto, não outro elo: o nome
                          acima já leva pra mesma tela onde dá pra arrumar. */}
                      {c.perfis_no_grupo > 1 && (
                        <span className="section__subtitle" style={{ fontSize: 12 }}>
                          {c.perfis_no_grupo} perfis
                        </span>
                      )}
                    </span>
                  </td>
                  {porConquista && (
                    <td data-rotulo="Por que está aqui" title={c.evidencias?.[0]?.resultado}>
                      {c.evidencias?.[0] ? rotuloEvidencia(c.evidencias[0]) : '—'}
                      {(c.conquistas_casadas ?? 0) > 1 && (
                        <span className="section__subtitle" style={{ fontSize: 12 }}>
                          {` +${(c.conquistas_casadas ?? 0) - 1}`}
                        </span>
                      )}
                    </td>
                  )}
                  <td data-rotulo="Escola">{fmtLista(c.escolas)}</td>
                  <td data-rotulo="Cidade/UF">
                    {fmtLista(c.cidades)} · {fmtLista(c.ufs)}
                  </td>
                  <td data-rotulo="Conquistas">{fmtConquistas(c)}</td>
                  <td data-rotulo="Status">{fmtLista(c.status_captacao.map((s) => STATUS_LABEL[s]))}</td>
                  <td data-rotulo="Última atualização" data-secundario>{fmtQuando(c.atualizado_em)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {totalPaginas > 1 && (
          <nav
            aria-label="Paginação dos candidatos"
            style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 16px' }}
          >
            <button
              type="button"
              className="btn btn--fino"
              disabled={pagina <= 1}
              onClick={() => setFiltros((f) => ({ ...f, pagina: pagina - 1 }))}
            >
              ← Anterior
            </button>
            <span className="tela-subtitulo">{`${pagina} / ${totalPaginas}`}</span>
            <button
              type="button"
              className="btn btn--fino"
              disabled={pagina >= totalPaginas}
              onClick={() => setFiltros((f) => ({ ...f, pagina: pagina + 1 }))}
            >
              Próxima →
            </button>
          </nav>
        )}
      </section>

      {provas && provas.provas.length > 0 && (
        <section className="card">
          <div className="tela-cabecalho" style={{ padding: '10px 16px 0' }}>
            <p className="tela-subtitulo">Fontes carregadas nesta lista</p>
          </div>
          <div className="provas-pista">
            {provas.provas.map((p) => (
              <div key={p.nome} className="provas-cartao">
                <span className="provas-cartao__nome">{p.nome}</span>
                <span className="provas-cartao__anos">
                  {p.ano_min && p.ano_max
                    ? p.ano_min === p.ano_max ? p.ano_min : `${p.ano_min}–${p.ano_max}`
                    : '—'}
                </span>
                <span className="provas-cartao__categoria">{p.categoria.replace('_', ' ')}</span>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
