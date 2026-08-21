import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import * as api from '../../servicos/api';
import {
  INTERVALO_POLLING_MS, TOTAL_ETAPAS, etapaMaisAvancada, formatarBytes, formatarDataHora,
  formatarHora, formatarSegundos, mesclarEventos, porcentagem, toneNivel, toneStatus,
} from '../../dominio/importacao';
import type {
  EstadoImportacao, EventoUpload, ResumoUpload, UploadDetalhe, UploadHistorico,
} from '../../dominio/importacao';

// Importar planilha — POST /uploads + polling do progresso real.
//
// Fluxo:
//   1. O usuário escolhe o arquivo → XHR sobe os bytes (barra 0%→30% real).
//   2. O POST devolve upload_id na hora, com status=processando.
//   3. Polling em GET /uploads/{id} a cada 600ms.
//   4. Eventos "ETAPA N/10" do pipeline avançam a barra.
//   5. Status vira sucesso/erro → o polling para e o resumo aparece.

export function Importar() {
  const queryClient = useQueryClient();

  const [arquivo, setArquivo] = useState<File | null>(null);
  const [estado, setEstado] = useState<EstadoImportacao>('aguardando');
  const [bytes, setBytes] = useState({ enviado: 0, total: 0 });
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [eventos, setEventos] = useState<EventoUpload[]>([]);
  const [resumo, setResumo] = useState<ResumoUpload | null>(null);
  const [erro, setErro] = useState('');
  const [decorrido, setDecorrido] = useState(0);
  const [sobreDropZone, setSobreDropZone] = useState(false);

  const inicioRef = useRef(0);
  const ultimaPctRef = useRef(0);
  const refInput = useRef<HTMLInputElement>(null);

  const emAndamento = estado === 'uploading' || estado === 'processando';

  // Cronômetro: 100ms é o suficiente para o décimo de segundo não pular.
  useEffect(() => {
    if (!emAndamento) return;
    const id = window.setInterval(() => setDecorrido(Date.now() - inicioRef.current), 100);
    return () => window.clearInterval(id);
  }, [emAndamento]);

  // Polling do progresso. `refetchInterval` para sozinho quando o estado sai
  // de "processando" — não há timer para limpar à mão.
  const { data: detalhe } = useQuery({
    queryKey: ['uploads', uploadId],
    queryFn: () => api.obterUpload(uploadId!) as Promise<UploadDetalhe>,
    enabled: !!uploadId && estado === 'processando',
    refetchInterval: INTERVALO_POLLING_MS,
    staleTime: 0,
    // Uma falha de polling não derruba o upload: segue tentando.
    retry: true,
  });

  const historico = useQuery({
    queryKey: ['uploads'],
    queryFn: () => api.listarUploads() as Promise<UploadHistorico[]>,
    staleTime: 0,
  });

  // Reage ao que o polling trouxe.
  useEffect(() => {
    if (!detalhe) return;

    setEventos((atuais) => mesclarEventos(atuais, detalhe.eventos ?? []));

    if (detalhe.upload.status === 'sucesso') {
      setResumo(detalhe.upload.resumo ?? {});
      setEstado('sucesso');
      ultimaPctRef.current = 100;
      historico.refetch();
      // Planilha nova: tudo que estava em cache envelheceu de uma vez.
      queryClient.invalidateQueries();
    } else if (detalhe.upload.status === 'erro') {
      setErro(detalhe.upload.erro_mensagem || 'Erro durante o processamento.');
      setEstado('erro');
      historico.refetch();
    }
    // `historico` muda de identidade a cada render; só o detalhe importa aqui.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detalhe, queryClient]);

  const enviar = useMutation({
    mutationFn: (f: File) =>
      api.enviarPlanilha(f, {
        onProgresso: (enviado, total) => setBytes({ enviado, total }),
        // Último byte entregue: agora a espera é do servidor.
        onEnviado: () => setEstado('processando'),
      }) as Promise<{ upload_id: string; status: string; resumo?: ResumoUpload }>,
  });

  async function iniciarEnvio() {
    if (!arquivo) return;

    inicioRef.current = Date.now();
    ultimaPctRef.current = 0;
    setEstado('uploading');
    setBytes({ enviado: 0, total: arquivo.size });
    setEventos([]);
    setResumo(null);
    setErro('');
    setUploadId(null);
    setDecorrido(0);

    try {
      const resp = await enviar.mutateAsync(arquivo);
      setUploadId(resp.upload_id);

      // O POST ter respondido já significa que os bytes chegaram — não dá
      // para depender só do evento de upload concluído do XHR, que pode não
      // disparar (proxy no meio, arquivo minúsculo). Sem isto o polling
      // nunca começaria e a barra ficaria parada em "Subindo arquivo".
      if (resp.status !== 'sucesso') setEstado('processando');

      if (resp.status === 'sucesso') {
        // Caminho raro: o servidor terminou de forma síncrona.
        setResumo(resp.resumo ?? {});
        setEstado('sucesso');
        ultimaPctRef.current = 100;
        historico.refetch();
        queryClient.invalidateQueries();
      }
    } catch (e) {
      setErro((e as Error).message || String(e));
      setEstado('erro');
    }
  }

  const etapa = etapaMaisAvancada(eventos);
  const pct = porcentagem(estado, bytes, etapa?.etapa ?? 0, ultimaPctRef.current);
  if (estado !== 'erro') ultimaPctRef.current = pct;

  function escolher(f: File | null) {
    setArquivo(f);
  }

  return (
    <main className="app-main">
      <section className="card">
        <div className="screen-header">
          <div className="screen-breadcrumb">Importar</div>
          <h1 className="screen-title">Importar planilha do Canvas</h1>
          <p className="screen-subtitle">
            Suba a planilha exportada do gradebook. O sistema cria alunos, turmas, ciclos,
            simulados e notas automaticamente.
          </p>
        </div>

        <div className="importar__form">
          <input
            ref={refInput}
            type="file"
            accept=".csv,.xlsx,.xlsm"
            id="campo-planilha"
            style={{ display: 'none' }}
            onChange={(ev) => escolher(ev.target.files?.[0] ?? null)}
          />

          <label
            className={`importar__drop${sobreDropZone ? ' is-over' : ''}`}
            htmlFor="campo-planilha"
            onDragOver={(ev) => {
              ev.preventDefault();
              setSobreDropZone(true);
            }}
            onDragLeave={() => setSobreDropZone(false)}
            onDrop={(ev) => {
              ev.preventDefault();
              setSobreDropZone(false);
              const f = ev.dataTransfer.files?.[0];
              if (f) escolher(f);
            }}
          >
            <div className="importar__drop-titulo">
              Arraste a planilha aqui ou clique para escolher
            </div>
            <div className="importar__drop-hint">Aceita .csv ou .xlsx exportados do Canvas.</div>
            <span className="importar__nome">
              {arquivo ? `${arquivo.name} · ${formatarBytes(arquivo.size)}` : 'Nenhum arquivo selecionado'}
            </span>
          </label>

          <div className="importar__acoes">
            <button
              className="btn btn-primary"
              disabled={!arquivo || emAndamento}
              onClick={iniciarEnvio}
            >
              Enviar para o servidor
            </button>
          </div>
        </div>

        {estado !== 'aguardando' && (
          <CartaoProgresso
            estado={estado}
            pct={pct}
            bytes={bytes}
            decorrido={decorrido}
            etapa={etapa}
            erro={erro}
          />
        )}

        {eventos.length > 0 && <LogVivo eventos={eventos} />}

        {estado === 'erro' && (
          <div className="importar__relatorio">
            <div className="card tone-vermelho-card">
              <h3>Não foi possível concluir o upload</h3>
              <p>{erro || 'Erro desconhecido.'}</p>
              {eventos.length > 0 && <ListaEventos eventos={eventos} />}
            </div>
          </div>
        )}

        {estado === 'sucesso' && resumo && (
          <div className="importar__relatorio">
            <RelatorioSucesso uploadId={uploadId} resumo={resumo} eventos={eventos} />
          </div>
        )}

        <div className="importar__historico">
          <h2 className="screen-section-title">Uploads anteriores</h2>
          <Historico consulta={historico} />
        </div>
      </section>
    </main>
  );
}

function CartaoProgresso({
  estado, pct, bytes, decorrido, etapa, erro,
}: {
  estado: EstadoImportacao;
  pct: number;
  bytes: { enviado: number; total: number };
  decorrido: number;
  etapa: { etapa: number; descricao: string } | null;
  erro: string;
}) {
  const titulo = {
    uploading: 'Subindo arquivo',
    processando: etapa
      ? `Etapa ${etapa.etapa}/${TOTAL_ETAPAS} · ${etapa.descricao}`
      : 'Aguardando servidor iniciar…',
    sucesso: 'Importação concluída',
    erro: 'Falhou',
    aguardando: '',
  }[estado];

  const subtitulo = {
    uploading: `${formatarBytes(bytes.enviado)} de ${formatarBytes(bytes.total)} · decorrido ${formatarSegundos(decorrido)}`,
    processando: `decorrido ${formatarSegundos(decorrido)}`,
    sucesso: `concluído em ${formatarSegundos(decorrido)}`,
    erro,
    aguardando: '',
  }[estado];

  const tone = estado === 'sucesso' ? 'tone-verde' : estado === 'erro' ? 'tone-vermelho' : '';

  return (
    <div className="importar__progresso">
      <div className={`card importar__status-card ${tone}`}>
        <div className="importar__status-titulo">{titulo}</div>
        <div className="importar__barra">
          <div className="importar__barra-fill" style={{ width: `${pct}%` }} />
          <div className="importar__barra-pct">{`${pct}%`}</div>
        </div>
        <div className="importar__status-subtitulo">{subtitulo}</div>
      </div>
    </div>
  );
}

/** Últimos 10 eventos — a lista completa iria ocupar a tela inteira. */
function LogVivo({ eventos }: { eventos: EventoUpload[] }) {
  return (
    <div className="importar__log-vivo">
      <div className="card importar__log-card">
        <div className="importar__log-titulo">{`Eventos do servidor (${eventos.length})`}</div>
        <ul className="importar__log-lista">
          {eventos.slice(-10).map((ev, i) => (
            <li key={`${ev.criado_em}-${i}`} className={`importar__log-item nivel-${ev.nivel}`}>
              <span className="importar__log-hora">{formatarHora(ev.criado_em)}</span>
              <span className={`importar__log-nivel nivel-${ev.nivel}`}>{ev.nivel}</span>
              <span className="importar__log-msg">{ev.mensagem}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function RelatorioSucesso({
  uploadId, resumo, eventos,
}: {
  uploadId: string | null;
  resumo: ResumoUpload;
  eventos: EventoUpload[];
}) {
  const contagens: Array<[string, number | null | undefined]> = [
    ['Alunos', resumo.alunos_processados],
    ['Sedes', resumo.sedes_processadas],
    ['Turmas', resumo.turmas_processadas],
    ['Ciclos', resumo.ciclos_processados],
    ['Simulados', resumo.simulados_processados],
    ['Notas gravadas', resumo.notas_gravadas],
    ['Colunas ignoradas', resumo.colunas_ignoradas],
  ];

  return (
    <div className="card tone-verde-card">
      <h3>Resumo da importação</h3>
      <p className="importar__upload-id">{`upload ${uploadId}`}</p>

      <div className="importar__contagens">
        {contagens.map(([rotulo, valor]) => (
          <div key={rotulo} className="importar__contagem">
            <div className="importar__contagem-valor">{valor == null ? '—' : String(valor)}</div>
            <div className="importar__contagem-rotulo">{rotulo}</div>
          </div>
        ))}
      </div>

      {!!resumo.avisos?.length && (
        <details className="importar__avisos">
          <summary>{`${resumo.avisos.length} aviso(s) do resumo`}</summary>
          <ul>
            {resumo.avisos.map((a, i) => <li key={i}>{a}</li>)}
          </ul>
        </details>
      )}

      {eventos.length > 0 && <ListaEventos eventos={eventos} />}

      <p className="importar__proximo">
        {'Já pode abrir '}
        <Link to="/alunos">Alunos</Link>
        {', '}
        <Link to="/simulados">Simulados</Link>
        {' ou '}
        <Link to="/ciclos">Ciclos</Link>
        {' pra ver os dados.'}
      </p>
    </div>
  );
}

function ListaEventos({ eventos }: { eventos: EventoUpload[] }) {
  const contagens = eventos.reduce<Record<string, number>>((acc, ev) => {
    acc[ev.nivel] = (acc[ev.nivel] ?? 0) + 1;
    return acc;
  }, {});

  const resumo = (['info', 'aviso', 'erro'] as const)
    .filter((n) => contagens[n])
    .map((n) => `${contagens[n]} ${n}`)
    .join(' · ');

  return (
    <details className="importar__eventos">
      <summary>{`Ver log completo do processamento (${eventos.length}) · ${resumo}`}</summary>
      <table className="data-table importar__eventos-tabela">
        <thead>
          <tr>
            <th>Nível</th>
            <th>Mensagem</th>
            <th>Linha</th>
            <th>Coluna</th>
            <th>Quando</th>
          </tr>
        </thead>
        <tbody>
          {eventos.map((ev, i) => (
            <tr key={`${ev.criado_em}-${i}`}>
              <td><span className={`tag ${toneNivel(ev.nivel)}`}>{ev.nivel}</span></td>
              <td>{ev.mensagem}</td>
              <td>{ev.linha_planilha == null ? '—' : String(ev.linha_planilha)}</td>
              <td>{ev.coluna_planilha || '—'}</td>
              <td>{formatarDataHora(ev.criado_em)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

function Historico({
  consulta,
}: {
  consulta: { data?: UploadHistorico[]; isError: boolean; isPending: boolean };
}) {
  if (consulta.isError) {
    return (
      <div className="empty-state">
        Não consegui carregar o histórico de uploads.
        <div className="empty-state__hint">
          Backend offline? Confira se o uvicorn está rodando.
        </div>
      </div>
    );
  }
  if (consulta.isPending) return <div className="empty-state">Carregando…</div>;
  if (!consulta.data?.length) return <div className="empty-state">Nenhum upload realizado ainda.</div>;

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Arquivo</th>
          <th>Status</th>
          <th>Linhas aceitas</th>
          <th>Data</th>
        </tr>
      </thead>
      <tbody>
        {consulta.data.map((u) => (
          <tr key={u.id}>
            <td>{u.arquivo_origem}</td>
            <td><span className={`tag ${toneStatus(u.status)}`}>{u.status}</span></td>
            <td>{u.linhas_aceitas == null ? '—' : String(u.linhas_aceitas)}</td>
            <td>{formatarDataHora(u.criado_em)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
