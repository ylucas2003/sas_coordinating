import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { useDecidirFusao, useFusao } from '../../hooks/captacao';

// A ficha de UM grupo da fila de fusão (CaptacaoFusoes.tsx) — todo
// candidato_externo com este nome, lado a lado, pra decidir se é a mesma
// pessoa. A decisão é sempre de quem está olhando: o resolver nunca funde
// por nome sozinho (docs/41 §4.1), e esta tela não muda isso — só registra
// o que um humano decidiu.

export function CaptacaoFusaoDetalhe() {
  const { nome = '' } = useParams();
  const nomeNormalizado = decodeURIComponent(nome);
  const navegar = useNavigate();
  const { data, isPending, isError } = useFusao(nomeNormalizado);
  const decidir = useDecidirFusao(nomeNormalizado);
  const [erro, setErro] = useState('');

  async function confirmar() {
    setErro('');
    try {
      await decidir.mutateAsync('confirmar');
      navegar('/administracao/captacao/fusoes');
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível fundir.');
    }
  }

  async function rejeitar() {
    setErro('');
    try {
      await decidir.mutateAsync('rejeitar');
      navegar('/administracao/captacao/fusoes');
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível registrar a rejeição.');
    }
  }

  if (isPending) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao/fusoes" destino="Fila de fusão" />
        <div className="empty-state">Carregando…</div>
      </div>
    );
  }

  if (isError || !data || data.candidatos.length < 2) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao/fusoes" destino="Fila de fusão" />
        <div className="empty-state">
          Não achei mais de um candidato com este nome.
          <div className="empty-state__hint">
            Talvez já tenha sido decidido — volte pra fila pra ver o que sobrou.
          </div>
        </div>
      </div>
    );
  }

  // Confiança da MESMA forma que a lista calcula (v_fusao_candidata): uma
  // UF só entre todo mundo do grupo é o sinal de que provavelmente é a
  // mesma pessoa; mais de uma é o caso real que já apareceu (Antonio
  // Eduardo Rossano — Fortaleza/CE numa conquista, Santa Fé do Sul/SP
  // noutra) — mesmo nome, talvez pessoas diferentes.
  const ufs = new Set(data.candidatos.map((c) => c.uf).filter(Boolean));
  const confiavel = ufs.size <= 1;

  return (
    <div className="tela">
      <CabecaDeCampo titulo={nomeNormalizado} para="/administracao/captacao/fusoes" destino="Fila de fusão" />

      <div className="tela-cabecalho">
        <p className="tela-subtitulo">
          {data.candidatos.length} candidatos com este nome.{' '}
          {confiavel
            ? 'Todos na mesma UF — sinal forte de que é a mesma pessoa.'
            : `UFs diferentes entre os candidatos (${[...ufs].join(', ') || '—'}) — pode ser gente diferente com o mesmo nome.`}
        </p>
      </div>

      <div className="campo-grade">
        {data.candidatos.map((c) => (
          <section className="card" key={c.id}>
            <h2 className="section__title">{c.escola || '— sem escola —'}</h2>
            <p className="section__subtitle">
              {[c.cidade, c.uf].filter(Boolean).join(' · ') || 'Sem cidade/UF'} · {c.conquistas_total}{' '}
              {c.conquistas_total === 1 ? 'conquista' : 'conquistas'} · status {c.status_captacao}
            </p>
            {/* Aviso automático (docs/41 §9): nível de ensino conflitante no
                mesmo ano com outro candidato deste nome — o mesmo sinal que
                desqualificou "Aline Lima de Oliveira" como fusão. Vem de
                `observacoes`, escrito por
                scripts/sinalizar_fusoes_conflito_de_nivel.py; nunca some
                sozinho, só quando alguém decidir o grupo. */}
            {c.observacoes && <p className="agendar__erro">{c.observacoes}</p>}
            <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
              {c.conquistas.map((q) => (
                <li key={q.id} className="section__subtitle">
                  {q.ano} · {q.prova_nome} · {q.resultado}
                  {' · '}
                  <a href={q.fonte_url} target="_blank" rel="noreferrer">ver fonte</a>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <section className="card">
        <h2 className="section__title">É a mesma pessoa?</h2>
        <p className="tela-subtitulo">
          Confirmando, os {data.candidatos.length} candidatos viram UM só — todas as conquistas
          somadas, o retrato (escola/cidade/UF) atualizado pela conquista mais recente. Rejeitando,
          este nome sai da fila e não volta a ser sugerido.
        </p>
        <div style={{ display: 'flex', gap: 12, marginTop: 12 }}>
          <button type="button" className="btn btn--primary" disabled={decidir.isPending} onClick={confirmar}>
            {decidir.isPending ? 'Fundindo…' : 'São a mesma pessoa'}
          </button>
          <button type="button" className="btn btn--ghost" disabled={decidir.isPending} onClick={rejeitar}>
            Não são
          </button>
          {erro && <span className="agendar__erro">{erro}</span>}
        </div>
      </section>
    </div>
  );
}
