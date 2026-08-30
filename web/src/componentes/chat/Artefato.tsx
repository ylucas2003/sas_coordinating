import { useNavigate } from 'react-router-dom';
import { Histograma } from '../ui/Histograma';
import { LinhaTemporal } from '../ui/LinhaTemporal';
import type { ArtefatoChat } from '../../tipos/chat';

// Artefatos do chat: gráficos inline (histograma, linha temporal) e download
// de CSV.

interface PayloadHistograma {
  histograma?: unknown;
  media?: number | null;
  mediana?: number | null;
  nPresentes?: number | null;
}

interface PayloadLinha {
  pontos?: Array<{
    simuladoId?: string;
    rotulo?: string;
    data?: string;
    nota: number;
    materia?: string;
  }>;
}

interface PayloadNavegacao {
  rota?: string;
  rotulo?: string;
  entidade?: string;
}

interface PayloadCsv {
  conteudo?: string;
  nLinhas?: number;
}

export function Artefato({ artefato }: { artefato: ArtefatoChat }) {
  const navegar = useNavigate();
  if (!artefato?.tipo) return null;

  const cabecalho = artefato.titulo ? (
    <div className="chat-artefato__titulo">{artefato.titulo}</div>
  ) : null;

  if (artefato.tipo === 'histograma') {
    const p = artefato.payload as PayloadHistograma;
    if (!p?.histograma) return <ArtefatoNaoRenderizavel tipo={artefato.tipo} />;
    return (
      <div className="chat-artefato chat-artefato--grafico">
        {cabecalho}
        <Histograma
          payload={p.histograma as never}
          largura={540}
          altura={200}
          media={p.media}
          mediana={p.mediana}
        />
        <div className="chat-artefato__rodape">{`n = ${p.nPresentes ?? '?'} alunos`}</div>
      </div>
    );
  }

  if (artefato.tipo === 'linha_temporal') {
    const p = artefato.payload as PayloadLinha;
    if (!Array.isArray(p?.pontos)) return <ArtefatoNaoRenderizavel tipo={artefato.tipo} />;
    return (
      <div className="chat-artefato chat-artefato--grafico">
        {cabecalho}
        <LinhaTemporal
          pontos={p.pontos.map((ponto) => ({
            simuladoId: ponto.simuladoId,
            nome: ponto.rotulo || '',
            rotuloCurto: ponto.rotulo || '',
            data: ponto.data,
            media: ponto.nota,
            materia: ponto.materia,
          }))}
          largura={620}
          altura={220}
          onPontoClick={(ponto) => ponto.simuladoId && navegar(`/simulados/${ponto.simuladoId}`)}
        />
      </div>
    );
  }

  if (artefato.tipo === 'navegacao') {
    const p = artefato.payload as PayloadNavegacao;
    if (!p?.rota) return <ArtefatoNaoRenderizavel tipo={artefato.tipo} />;
    return (
      <div className="chat-artefato chat-artefato--link">
        {/* `button` e não `a`: navegação de SPA. Um href faria o browser
            recarregar a aplicação e derrubar a conversa aberta ao lado —
            justamente o que o painel não-modal existe para evitar. */}
        <button
          type="button"
          className="chat-artefato__link"
          onClick={() => navegar(p.rota!)}
        >
          <span className="chat-artefato__link-icone" aria-hidden="true">→</span>
          {p.rotulo || p.rota}
        </button>
      </div>
    );
  }

  if (artefato.tipo === 'csv') {
    const p = artefato.payload as PayloadCsv;
    if (!p?.conteudo) return <ArtefatoNaoRenderizavel tipo={artefato.tipo} />;
    const nome = `${(artefato.titulo || 'export').replace(/[^a-zA-Z0-9_-]/g, '_')}.csv`;
    return (
      <div className="chat-artefato chat-artefato--csv">
        {cabecalho}
        <div className="chat-artefato__csv-info">{`${p.nLinhas ?? 0} linha(s) · CSV`}</div>
        <button
          className="chat-artefato__csv-baixar"
          onClick={() => baixarCsv(p.conteudo!, nome)}
        >
          ↓ Baixar CSV
        </button>
      </div>
    );
  }

  return <ArtefatoNaoRenderizavel tipo={artefato.tipo} />;
}

function ArtefatoNaoRenderizavel({ tipo }: { tipo: string }) {
  return (
    <div className="chat-artefato chat-artefato--erro">
      {`Artefato não renderizável (tipo=${tipo}).`}
    </div>
  );
}

function baixarCsv(conteudo: string, nomeArquivo: string) {
  // O BOM na frente é o que faz o Excel ler os acentos corretamente.
  const blob = new Blob(['﻿' + conteudo], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = nomeArquivo;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 500);
}
