import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { CabecaDeCampo } from '../../componentes/ui/Campo';
import { Kpi } from '../../componentes/ui/Kpi';
import { TarjaProcedencia } from '../../componentes/ui/TarjaProcedencia';
import { useTituloDaTela } from '../../componentes/layout/migalhas';
import { rotuloDaSerie, serieEstimadaHoje } from '../../dominio/captacao';
import { useAtualizarCandidato, useCandidato } from '../../hooks/captacao';
import { CaptacaoModalConquista } from './CaptacaoModalConquista';
import type { ConquistaExterna, StatusCaptacao } from '../../tipos/captacao';

// A ficha do candidato (docs/41 §0, §7.2): o cruzamento que a captação existe
// pra mostrar — todas as conquistas de uma pessoa, de fontes/anos diferentes,
// juntas. `status_captacao` e `observacoes` são os DOIS únicos campos que
// alguém edita aqui; o resto vem do resolver
// (`api/scripts/resolver_candidatos_externos.py`) e é só leitura.

const STATUS_LABEL: Record<StatusCaptacao, string> = {
  novo: 'Novo',
  contatado: 'Contatado',
  interessado: 'Interessado',
  matriculado: 'Matriculado',
  descartado: 'Descartado',
};

function fmtQuando(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function CaptacaoFicha() {
  const { id = '' } = useParams();
  const { data: candidato, isPending, isError } = useCandidato(id);
  const atualizar = useAtualizarCandidato(id);

  const [status, setStatus] = useState<StatusCaptacao>('novo');
  const [observacoes, setObservacoes] = useState('');
  const [erro, setErro] = useState('');
  const [conquistaAberta, setConquistaAberta] = useState<ConquistaExterna | null>(null);

  // Migalha da topbar — mesmo contrato de AlunoFicha.tsx, chamado ANTES de
  // qualquer `return` de carregamento/erro (é hook).
  useTituloDaTela(candidato?.nome);

  // Semeia o formulário quando a ficha chega — e só então, pra não sobrescrever
  // o que a coordenação está digitando se a consulta revalidar no meio.
  useEffect(() => {
    if (!candidato) return;
    setStatus(candidato.status_captacao);
    setObservacoes(candidato.observacoes ?? '');
  }, [candidato]);

  if (isPending) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo="Candidato" para="/administracao/captacao" destino="Captação externa" />
        <div className="empty-state">Carregando…</div>
      </div>
    );
  }

  if (isError || !candidato) {
    return (
      <div className="tela">
        <CabecaDeCampo titulo="Candidato" para="/administracao/captacao" destino="Captação externa" />
        <div className="empty-state">Não foi possível carregar este candidato.</div>
      </div>
    );
  }

  const faixaHoje = serieEstimadaHoje(candidato, new Date().getFullYear());
  const houveMudanca = status !== candidato.status_captacao || observacoes !== (candidato.observacoes ?? '');

  async function salvar() {
    setErro('');
    try {
      await atualizar.mutateAsync({
        ...(status !== candidato!.status_captacao ? { status_captacao: status } : {}),
        ...(observacoes !== (candidato!.observacoes ?? '') ? { observacoes } : {}),
      });
    } catch (e) {
      setErro((e as Error).message || 'Não foi possível salvar.');
    }
  }

  return (
    <div className="tela">
      <CabecaDeCampo titulo={candidato.nome} para="/administracao/captacao" destino="Captação externa" />

      {/* Alerta de duplicata pendente (docs/41, 24/09/2026): a coordenação
          descobre a partir do PERFIL da pessoa, não só varrendo a fila de
          fusão separada. `falhou` (sinal forte — nível de ensino conflitante,
          quase certeza de homônimo) e `pendente` (revisão de rotina) são os
          dois estados de TarjaProcedencia que já existiam; nenhum glifo novo. */}
      {candidato.duplicatas_pendentes > 0 && (
        <Link
          className="procedencia-elo"
          to={`/administracao/captacao/fusoes/${encodeURIComponent(candidato.nome_normalizado)}`}
        >
          <TarjaProcedencia
            estado={candidato.tem_conflito_nivel ? 'falhou' : 'pendente'}
            fonte={
              candidato.tem_conflito_nivel
                ? 'nível de ensino conflitante — provavelmente pessoas diferentes'
                : `${candidato.duplicatas_pendentes} outro${candidato.duplicatas_pendentes > 1 ? 's' : ''} perfil${candidato.duplicatas_pendentes > 1 ? 'is' : ''} com esse nome`
            }
            dica="Revisar quem é quem na fila de fusão"
          />
        </Link>
      )}

      <section className="card">
        <h2 className="section__title">Dados cruzados</h2>
        <p className="section__subtitle"><b>Escola:</b> {candidato.escola || '—'}</p>
        <p className="section__subtitle">
          <b>Cidade / UF:</b> {[candidato.cidade, candidato.uf].filter(Boolean).join(' · ') || '—'}
        </p>
        <p className="section__subtitle">
          <b>Série estimada hoje:</b> {rotuloDaSerie(faixaHoje) ?? '—'}
          {candidato.ano_referencia_serie && ` (a partir da conquista de ${candidato.ano_referencia_serie})`}
        </p>
        <p className="section__subtitle"><b>Última atualização:</b> {fmtQuando(candidato.atualizado_em)}</p>

        <div className="kpi-grid kpi-grid--cartoes" style={{ marginTop: 12 }}>
          <Kpi rotulo="Conquistas cruzadas" valor={candidato.conquistas_total} />
          <Kpi rotulo="Provas distintas" valor={candidato.provas_distintas} />
        </div>
      </section>

      <section className="card">
        <h2 className="section__title">Funil de captação</h2>
        <p className="tela-subtitulo">
          Os dois únicos campos que a coordenação controla — o resto vem do cruzamento automático.
        </p>
        <label htmlFor="capt-status" className="section__subtitle" style={{ display: 'block', marginTop: 12 }}>
          Status
        </label>
        <select
          id="capt-status"
          className="dialog__input"
          value={status}
          onChange={(e) => setStatus(e.target.value as StatusCaptacao)}
        >
          {(Object.keys(STATUS_LABEL) as StatusCaptacao[]).map((v) => (
            <option key={v} value={v}>{STATUS_LABEL[v]}</option>
          ))}
        </select>
        <label htmlFor="capt-obs" className="section__subtitle" style={{ display: 'block', marginTop: 12 }}>
          Observações
        </label>
        <textarea
          id="capt-obs"
          className="dialog__input"
          style={{ width: '100%', minHeight: 90, marginTop: 6 }}
          value={observacoes}
          onChange={(e) => setObservacoes(e.target.value)}
          placeholder="Anotações da coordenação sobre este candidato…"
        />
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
          <button
            type="button"
            className="btn btn--primary"
            disabled={!houveMudanca || atualizar.isPending}
            onClick={salvar}
          >
            {atualizar.isPending ? 'Salvando…' : 'Salvar'}
          </button>
          {erro && <span className="agendar__erro">{erro}</span>}
        </div>
      </section>

      <section className="card">
        <h2 className="section__title">
          {`Conquistas cruzadas (${candidato.conquistas.length})`}
        </h2>
        {candidato.conquistas.length === 0 ? (
          <p className="tela-subtitulo">Nenhuma conquista — não deveria acontecer, avise quem mantém o resolver.</p>
        ) : (
          <table className="data-table data-table--cartoes">
            <thead>
              <tr>
                <th>Ano</th><th>Prova</th><th>Nível</th><th>Resultado</th><th>Escola informada</th>
              </tr>
            </thead>
            <tbody>
              {candidato.conquistas.map((c) => (
                <tr key={c.id}>
                  <td data-rotulo="Ano" data-titulo>{c.ano}</td>
                  <td data-rotulo="Prova">{c.prova_nome ?? '—'}</td>
                  {/* `||`, não `??`: nível vazio ("", ITA — não tem tier por
                      série como as olimpíadas) é ausência de dado tanto
                      quanto `null`, mesma regra da Escola informada ao lado. */}
                  <td data-rotulo="Nível">{c.nivel_texto || '—'}</td>
                  <td data-rotulo="Resultado">
                    {/* Clicar expande nota por matéria (quando a fonte
                        publica) + o link pra fonte, num modal só — antes
                        eram duas colunas fixas (a nota nunca existiu; a
                        fonte sempre ficava exposta, mesmo sem ninguém
                        precisar dela na varredura). */}
                    <button type="button" className="link-botao" onClick={() => setConquistaAberta(c)}>
                      {c.resultado}
                    </button>
                  </td>
                  <td data-rotulo="Escola informada" data-secundario>{c.escola_informada || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {conquistaAberta && (
        <CaptacaoModalConquista conquista={conquistaAberta} onFechar={() => setConquistaAberta(null)} />
      )}
    </div>
  );
}
