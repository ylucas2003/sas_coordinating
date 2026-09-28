import { useState } from 'react';
import { useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { BarraFiltros, PillsUnica } from '../../componentes/ui/filtros/BarraFiltros';
import { Kpi } from '../../componentes/ui/Kpi';
import { ROTULO_MATERIA } from '../../dominio/captacao';
import { resumirUnica } from '../../dominio/filtros';
import { usePerfisDoNome } from '../../hooks/captacao';
import type { ConquistaExterna } from '../../tipos/captacao';

import '../../../styles/captacao.css';

// Ficha de UM candidato_externo, pedido do coordenador (28/09/2026): "entrar
// e visualizar de maneira mais organizada aquele perfil, podendo
// organizar/filtrar as conquistas por ano, por prova... vendo os detalhes
// escritos". `CaptacaoPerfil.tsx` (a lane) é pra ARRASTAR — bloco compacto,
// clique abre modal (`CaptacaoModalConquista`); esta tela é pra LER, cada
// conquista já aberta, sem clique, com filtro de ano/prova por cima. As duas
// telas leem o mesmo `usePerfisDoNome`, já em cache quando se entra por aqui
// vindo da lane (o elo "Ver conquistas em detalhe" de cada cartão).

export function CaptacaoConquistas() {
  const { nome = '', candidatoId = '' } = useParams();
  const nomeNormalizado = decodeURIComponent(nome);
  const paraALane = `/administracao/captacao/${encodeURIComponent(nomeNormalizado)}`;
  const { data, isPending, isError } = usePerfisDoNome(nomeNormalizado);

  const [ano, setAno] = useState<number | null>(null);
  const [prova, setProva] = useState<string | null>(null);

  if (isPending) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para={paraALane} destino={nomeNormalizado} />
        <div className="empty-state">Carregando…</div>
      </div>
    );
  }

  const candidato = data?.candidatos.find((c) => c.id === candidatoId) ?? null;
  if (isError || !candidato) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para={paraALane} destino={nomeNormalizado} />
        <div className="empty-state">Não achei este perfil.</div>
      </div>
    );
  }

  const anos = [...new Set(candidato.conquistas.map((c) => c.ano))].sort((a, b) => b - a);
  const provas = [
    ...new Set(candidato.conquistas.map((c) => c.prova_nome).filter((p): p is string => Boolean(p))),
  ].sort();

  const conquistas = candidato.conquistas
    .filter((c) => ano == null || c.ano === ano)
    .filter((c) => prova == null || c.prova_nome === prova);

  const local = [candidato.cidade, candidato.uf].filter(Boolean).join(' · ');

  return (
    <div className="tela">
      <CabecaDeCampo titulo={candidato.escola || candidato.nome} para={paraALane} destino={nomeNormalizado} />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          {local || 'Sem cidade/UF'} · {candidato.conquistas.length}{' '}
          {candidato.conquistas.length === 1 ? 'resultado' : 'resultados'}
        </p>
      </div>

      <BarraFiltros
        tela="captacao.conquistas"
        algumAtivo={ano != null || prova != null}
        onLimpar={() => {
          setAno(null);
          setProva(null);
        }}
        grupos={[
          anos.length > 1 && {
            chave: 'ano',
            rotulo: 'Ano',
            resumo: resumirUnica(ano, anos.map((a) => ({ valor: a, label: String(a) }))),
            corpo: (
              <PillsUnica
                opcoes={anos.map((a) => ({ valor: a, label: String(a) }))}
                selecionado={ano}
                onSelecionar={(v) => setAno(ano === v ? null : v)}
              />
            ),
          },
          provas.length > 1 && {
            chave: 'prova',
            rotulo: 'Prova',
            resumo: resumirUnica(prova, provas.map((p) => ({ valor: p, label: p }))),
            corpo: (
              <PillsUnica
                opcoes={provas.map((p) => ({ valor: p, label: p }))}
                selecionado={prova}
                onSelecionar={(v) => setProva(prova === v ? null : v)}
              />
            ),
          },
        ]}
      />

      <div className="captacao-conquistas">
        {conquistas.map((q) => (
          <ConquistaDetalhada key={q.id} conquista={q} />
        ))}
        {conquistas.length === 0 && (
          <div className="empty-state">
            Nenhuma conquista com esses filtros.
            <div className="empty-state__hint">Tire um filtro pra ver o resto.</div>
          </div>
        )}
      </div>
    </div>
  );
}

function ConquistaDetalhada({ conquista }: { conquista: ConquistaExterna }) {
  const notas = conquista.notas_por_materia;
  const local = [conquista.cidade_informada, conquista.uf_informada].filter(Boolean).join(' · ');

  return (
    <article className="card captacao-conquistas__item">
      <div className="captacao-conquistas__cabecalho">
        <span className="captacao-conquistas__ano">{conquista.ano}</span>
        <div>
          <h2 className="section__title">{conquista.prova_nome ?? 'Prova'}</h2>
          <p className="section__subtitle">
            {conquista.resultado}
            {conquista.nivel_texto && ` · ${conquista.nivel_texto}`}
          </p>
        </div>
      </div>

      {(conquista.escola_informada || local) && (
        <p className="section__subtitle">
          {[conquista.escola_informada, local].filter(Boolean).join(' · ')}
        </p>
      )}

      {notas && (
        <div className="kpi-grid kpi-grid--cartoes">
          {Object.entries(notas).map(([materia, valor]) => (
            <Kpi key={materia} rotulo={ROTULO_MATERIA[materia] ?? materia} valor={valor} />
          ))}
        </div>
      )}

      <a
        className="btn btn--ghost captacao-conquistas__fonte"
        href={conquista.fonte_url}
        target="_blank"
        rel="noreferrer"
      >
        Ver fonte ↗
      </a>
    </article>
  );
}
