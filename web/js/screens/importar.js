// Importar planilha — POST /uploads + polling de progresso real.
//
// Fluxo:
//   1. Usuário escolhe o arquivo → XHR sobe os bytes (barra 0%→100% real).
//   2. POST devolve upload_id imediatamente, status=processando.
//   3. Frontend faz polling GET /uploads/{id} a cada 600ms.
//   4. Eventos ETAPA N/7 do pipeline avançam a barra (cada etapa = ~14%).
//   5. Demais eventos (info, aviso, erro) aparecem em tempo real no log.
//   6. Status muda pra sucesso/erro → polling para, resumo é exibido.

import { getApiClient } from '../services/api.js';
import { clear, el } from '../dom.js';

// 1-7: ingestão + 8-10: stats engine (métricas, classificação, alertas).
const TOTAL_ETAPAS = 10;
const INTERVALO_POLLING_MS = 600;

export async function renderImportar() {
  const api = getApiClient();

  // Estado interno.
  let arquivoSelecionado = null;
  let estado = 'aguardando'; // aguardando | uploading | processando | sucesso | erro
  let progressoBytes = { enviado: 0, total: 0 };
  let etapaAtual = 0;
  let descricaoEtapa = '';
  let tempoInicio = 0;
  let cronometroInterval = null;
  let pollingInterval = null;
  let uploadId = null;
  let resposta = null;
  let eventos = [];
  let eventosVistos = new Set(); // dedup por criado_em+mensagem
  let mensagemErro = '';

  // ─── Render de partes da tela ─────────────────────────────────────────

  const containerProgresso = el('div', { class: 'importar__progresso' }, []);
  const containerLogVivo = el('div', { class: 'importar__log-vivo' }, []);
  const containerRelatorio = el('div', { class: 'importar__relatorio' }, []);
  const containerHistorico = el('div', { class: 'importar__historico' }, []);

  function porcentagemAtual() {
    if (estado === 'uploading') {
      // Upload de bytes: 0% → 30% da barra total (a parte "rápida").
      if (progressoBytes.total === 0) return 0;
      const fracaoUpload = progressoBytes.enviado / progressoBytes.total;
      return Math.round(fracaoUpload * 30);
    }
    if (estado === 'processando') {
      // Processamento: 30% → 95% conforme avança nas etapas.
      const fracaoEtapa = etapaAtual / TOTAL_ETAPAS;
      return 30 + Math.round(fracaoEtapa * 65);
    }
    if (estado === 'sucesso') return 100;
    if (estado === 'erro') return porcentagemAtual.ultimaConhecida || 0;
    return 0;
  }

  function renderProgresso() {
    clear(containerProgresso);
    if (estado === 'aguardando') return;

    const decorrido = Date.now() - tempoInicio;
    const pct = porcentagemAtual();

    const tituloPorEstado = {
      uploading: `Subindo arquivo`,
      processando: descricaoEtapa
        ? `Etapa ${etapaAtual}/${TOTAL_ETAPAS} · ${descricaoEtapa}`
        : `Aguardando servidor iniciar…`,
      sucesso: `Importação concluída`,
      erro: `Falhou`,
    };

    const subtituloPorEstado = {
      uploading: `${formatarBytes(progressoBytes.enviado)} de ${formatarBytes(progressoBytes.total)} · decorrido ${formatarSegundos(decorrido)}`,
      processando: `decorrido ${formatarSegundos(decorrido)}`,
      sucesso: `concluído em ${formatarSegundos(decorrido)}`,
      erro: mensagemErro,
    };

    const toneClasse = {
      sucesso: 'tone-verde',
      erro: 'tone-vermelho',
    }[estado] || '';

    containerProgresso.appendChild(
      el('div', { class: `card importar__status-card ${toneClasse}` }, [
        el('div', { class: 'importar__status-titulo' }, [tituloPorEstado[estado]]),
        el('div', { class: 'importar__barra' }, [
          el('div', {
            class: 'importar__barra-fill',
            style: `width: ${pct}%`,
          }, []),
          el('div', { class: 'importar__barra-pct' }, [`${pct}%`]),
        ]),
        el('div', { class: 'importar__status-subtitulo' }, [subtituloPorEstado[estado]]),
      ])
    );
  }

  function renderLogVivo() {
    clear(containerLogVivo);
    if (eventos.length === 0) return;

    // Pega os 10 mais recentes pra evitar uma lista enorme no meio da tela.
    const recentes = eventos.slice(-10);

    containerLogVivo.appendChild(
      el('div', { class: 'card importar__log-card' }, [
        el('div', { class: 'importar__log-titulo' }, [
          `Eventos do servidor (${eventos.length})`,
        ]),
        el('ul', { class: 'importar__log-lista' },
          recentes.map((ev) =>
            el('li', { class: `importar__log-item nivel-${ev.nivel}` }, [
              el('span', { class: 'importar__log-hora' }, [formatarHora(ev.criado_em)]),
              el('span', { class: `importar__log-nivel nivel-${ev.nivel}` }, [ev.nivel]),
              el('span', { class: 'importar__log-msg' }, [ev.mensagem]),
            ])
          )
        ),
      ])
    );
  }

  function renderRelatorio() {
    clear(containerRelatorio);

    if (estado === 'erro') {
      containerRelatorio.appendChild(
        el('div', { class: 'card tone-vermelho-card' }, [
          el('h3', {}, ['Não foi possível concluir o upload']),
          el('p', {}, [mensagemErro || 'Erro desconhecido.']),
          (eventos.length > 0) ? renderListaEventos(eventos) : null,
        ])
      );
      return;
    }

    if (estado === 'sucesso' && resposta) {
      const r = resposta.resumo || {};
      containerRelatorio.appendChild(
        el('div', { class: 'card tone-verde-card' }, [
          el('h3', {}, ['Resumo da importação']),
          el('p', { class: 'importar__upload-id' }, [`upload ${resposta.upload_id}`]),
          el('div', { class: 'importar__contagens' }, [
            contagem('Alunos', r.alunos_processados),
            contagem('Sedes', r.sedes_processadas),
            contagem('Turmas', r.turmas_processadas),
            contagem('Ciclos', r.ciclos_processados),
            contagem('Simulados', r.simulados_processados),
            contagem('Notas gravadas', r.notas_gravadas),
            contagem('Colunas ignoradas', r.colunas_ignoradas),
          ]),
          (r.avisos && r.avisos.length > 0)
            ? el('details', { class: 'importar__avisos' }, [
                el('summary', {}, [`${r.avisos.length} aviso(s) do resumo`]),
                el('ul', {}, r.avisos.map((a) => el('li', {}, [a]))),
              ])
            : null,
          (eventos.length > 0) ? renderListaEventos(eventos) : null,
          el('p', { class: 'importar__proximo' }, [
            'Já pode abrir ',
            el('a', { href: '#/alunos' }, ['Alunos']),
            ', ',
            el('a', { href: '#/simulados' }, ['Simulados']),
            ' ou ',
            el('a', { href: '#/ciclos' }, ['Ciclos']),
            ' pra ver os dados.',
          ]),
        ])
      );
    }
  }

  // ─── Cronômetro + polling ─────────────────────────────────────────────

  function iniciarCronometro() {
    if (cronometroInterval) return;
    cronometroInterval = setInterval(renderProgresso, 100);
  }
  function pararCronometro() {
    if (cronometroInterval) clearInterval(cronometroInterval);
    cronometroInterval = null;
  }

  function iniciarPolling() {
    if (pollingInterval) return;
    pollingInterval = setInterval(consultarUpload, INTERVALO_POLLING_MS);
  }
  function pararPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = null;
  }

  async function consultarUpload() {
    if (!uploadId) return;
    try {
      const detalhe = await api.obterUpload(uploadId);
      mesclarEventos(detalhe.eventos || []);
      atualizarEtapa();

      const statusServer = detalhe.upload.status;
      if (statusServer === 'sucesso') {
        resposta = {
          upload_id: detalhe.upload.id,
          status: 'sucesso',
          resumo: detalhe.upload.resumo || {},
        };
        estado = 'sucesso';
        porcentagemAtual.ultimaConhecida = 100;
        pararCronometro();
        pararPolling();
        renderProgresso();
        renderLogVivo();
        renderRelatorio();
        recarregarHistorico();
      } else if (statusServer === 'erro') {
        mensagemErro = detalhe.upload.erro_mensagem || 'Erro durante o processamento.';
        estado = 'erro';
        porcentagemAtual.ultimaConhecida = porcentagemAtual();
        pararCronometro();
        pararPolling();
        renderProgresso();
        renderLogVivo();
        renderRelatorio();
        recarregarHistorico();
      } else {
        // Ainda processando — atualiza UI e continua.
        renderLogVivo();
      }
    } catch (e) {
      // Falha de polling não derruba o upload; só loga e tenta de novo.
      console.warn('Falha ao consultar upload', e);
    }
  }

  function mesclarEventos(novos) {
    for (const ev of novos) {
      const chave = `${ev.criado_em}|${ev.mensagem}`;
      if (!eventosVistos.has(chave)) {
        eventosVistos.add(chave);
        eventos.push(ev);
      }
    }
  }

  function atualizarEtapa() {
    // Acha a etapa mais alta já registrada nos eventos.
    let maiorEtapa = 0;
    let descricao = '';
    for (const ev of eventos) {
      const m = (ev.mensagem || '').match(/^ETAPA\s+(\d+)\/\d+:\s*(.+)$/);
      if (m) {
        const n = parseInt(m[1], 10);
        if (n > maiorEtapa) {
          maiorEtapa = n;
          descricao = m[2];
        }
      }
    }
    if (maiorEtapa > 0) {
      etapaAtual = maiorEtapa;
      descricaoEtapa = descricao;
    }
  }

  // ─── Ação de envio ────────────────────────────────────────────────────

  async function enviarArquivo() {
    if (!arquivoSelecionado) return;
    estado = 'uploading';
    tempoInicio = Date.now();
    progressoBytes = { enviado: 0, total: arquivoSelecionado.size };
    etapaAtual = 0;
    descricaoEtapa = '';
    eventos = [];
    eventosVistos = new Set();
    resposta = null;
    mensagemErro = '';
    uploadId = null;
    botaoEnviar.disabled = true;
    iniciarCronometro();
    renderProgresso();
    renderLogVivo();
    renderRelatorio();

    try {
      const respPost = await api.enviarPlanilha(arquivoSelecionado, {
        onProgress: (enviado, total) => {
          progressoBytes = { enviado, total };
        },
        onUploaded: () => {
          // Bytes 100% entregues — agora estamos esperando o servidor processar.
          estado = 'processando';
        },
      });
      uploadId = respPost.upload_id;
      // Se já veio status=sucesso síncrono (raro), pula polling.
      if (respPost.status === 'sucesso') {
        resposta = respPost;
        estado = 'sucesso';
        porcentagemAtual.ultimaConhecida = 100;
        pararCronometro();
        renderProgresso();
        renderRelatorio();
        recarregarHistorico();
      } else {
        // Caminho normal — começa polling pra acompanhar a ingestão.
        iniciarPolling();
      }
    } catch (e) {
      mensagemErro = e.message || String(e);
      estado = 'erro';
      porcentagemAtual.ultimaConhecida = porcentagemAtual();
      pararCronometro();
      pararPolling();
      renderProgresso();
      renderRelatorio();
    } finally {
      botaoEnviar.disabled = !arquivoSelecionado;
    }
  }

  // ─── Seleção de arquivo + drop zone ───────────────────────────────────

  function aoSelecionarArquivo(arquivo) {
    arquivoSelecionado = arquivo;
    rotuloArquivo.textContent = arquivo
      ? `${arquivo.name} · ${formatarBytes(arquivo.size)}`
      : 'Nenhum arquivo selecionado';
    botaoEnviar.disabled = !arquivo;
  }

  const inputArquivo = el('input', {
    type: 'file',
    accept: '.csv,.xlsx,.xlsm',
    id: 'campo-planilha',
    onchange: (ev) => aoSelecionarArquivo(ev.target.files[0] || null),
  });
  inputArquivo.style.display = 'none';

  const rotuloArquivo = el('span', { class: 'importar__nome' }, ['Nenhum arquivo selecionado']);

  const botaoEnviar = el(
    'button',
    { class: 'btn btn-primary', onclick: enviarArquivo },
    ['Enviar para o servidor']
  );
  botaoEnviar.disabled = true;

  const dropZone = el(
    'label',
    {
      class: 'importar__drop',
      for: 'campo-planilha',
      ondragover: (ev) => { ev.preventDefault(); dropZone.classList.add('is-over'); },
      ondragleave: () => dropZone.classList.remove('is-over'),
      ondrop: (ev) => {
        ev.preventDefault();
        dropZone.classList.remove('is-over');
        const arquivo = ev.dataTransfer.files[0];
        if (arquivo) {
          inputArquivo.files = ev.dataTransfer.files;
          aoSelecionarArquivo(arquivo);
        }
      },
    },
    [
      el('div', { class: 'importar__drop-titulo' }, ['Arraste a planilha aqui ou clique para escolher']),
      el('div', { class: 'importar__drop-hint' }, ['Aceita .csv ou .xlsx exportados do Canvas.']),
      rotuloArquivo,
    ]
  );

  // ─── Histórico ────────────────────────────────────────────────────────

  async function recarregarHistorico() {
    try {
      const uploads = await api.listarUploads();
      clear(containerHistorico);
      containerHistorico.appendChild(el('h2', { class: 'screen-section-title' }, ['Uploads anteriores']));
      if (uploads.length === 0) {
        containerHistorico.appendChild(el('div', { class: 'empty-state' }, ['Nenhum upload realizado ainda.']));
        return;
      }
      containerHistorico.appendChild(
        el('table', { class: 'data-table' }, [
          el('thead', {}, [
            el('tr', {}, [
              el('th', {}, ['Arquivo']),
              el('th', {}, ['Status']),
              el('th', {}, ['Linhas aceitas']),
              el('th', {}, ['Data']),
            ]),
          ]),
          el('tbody', {}, uploads.map((u) =>
            el('tr', {}, [
              el('td', {}, [u.arquivo_origem]),
              el('td', {}, [el('span', { class: `tag ${statusTone(u.status)}` }, [u.status])]),
              el('td', {}, [u.linhas_aceitas == null ? '—' : String(u.linhas_aceitas)]),
              el('td', {}, [formatarData(u.criado_em)]),
            ])
          )),
        ])
      );
    } catch {
      clear(containerHistorico);
      containerHistorico.appendChild(
        el('div', { class: 'empty-state' }, [
          'Não consegui carregar o histórico de uploads.',
          el('div', { class: 'empty-state__hint' }, ['Backend offline? Confira se o uvicorn está rodando em http://localhost:8000.']),
        ])
      );
    }
  }

  recarregarHistorico();

  return el('section', { class: 'card' }, [
    el('div', { class: 'screen-header' }, [
      el('div', { class: 'screen-breadcrumb' }, ['Importar']),
      el('h1', { class: 'screen-title' }, ['Importar planilha do Canvas']),
      el('p', { class: 'screen-subtitle' }, [
        'Suba a planilha exportada do gradebook. O sistema cria alunos, turmas, ciclos, simulados e notas automaticamente.',
      ]),
    ]),
    el('div', { class: 'importar__form' }, [
      inputArquivo,
      dropZone,
      el('div', { class: 'importar__acoes' }, [botaoEnviar]),
    ]),
    containerProgresso,
    containerLogVivo,
    containerRelatorio,
    containerHistorico,
  ]);
}

// ─── Helpers ────────────────────────────────────────────────────────────

function contagem(rotulo, valor) {
  return el('div', { class: 'importar__contagem' }, [
    el('div', { class: 'importar__contagem-valor' }, [valor == null ? '—' : String(valor)]),
    el('div', { class: 'importar__contagem-rotulo' }, [rotulo]),
  ]);
}

function renderListaEventos(eventos) {
  const contagens = eventos.reduce((acc, ev) => {
    acc[ev.nivel] = (acc[ev.nivel] || 0) + 1;
    return acc;
  }, {});
  const resumo = ['info', 'aviso', 'erro']
    .filter((n) => contagens[n])
    .map((n) => `${contagens[n]} ${n}`)
    .join(' · ');

  return el('details', { class: 'importar__eventos' }, [
    el('summary', {}, [`Ver log completo do processamento (${eventos.length}) · ${resumo}`]),
    el('table', { class: 'data-table importar__eventos-tabela' }, [
      el('thead', {}, [
        el('tr', {}, [
          el('th', {}, ['Nível']),
          el('th', {}, ['Mensagem']),
          el('th', {}, ['Linha']),
          el('th', {}, ['Coluna']),
          el('th', {}, ['Quando']),
        ]),
      ]),
      el('tbody', {}, eventos.map((ev) =>
        el('tr', {}, [
          el('td', {}, [el('span', { class: `tag ${nivelToTone(ev.nivel)}` }, [ev.nivel])]),
          el('td', {}, [ev.mensagem]),
          el('td', {}, [ev.linha_planilha == null ? '—' : String(ev.linha_planilha)]),
          el('td', {}, [ev.coluna_planilha || '—']),
          el('td', {}, [formatarData(ev.criado_em)]),
        ])
      )),
    ]),
  ]);
}

function nivelToTone(nivel) {
  if (nivel === 'erro') return 'tone-vermelho';
  if (nivel === 'aviso') return 'tone-ambar';
  return 'tone-navy';
}

function statusTone(status) {
  if (status === 'sucesso') return 'tone-verde';
  if (status === 'erro') return 'tone-vermelho';
  return 'tone-ambar';
}

function formatarSegundos(ms) {
  return `${(ms / 1000).toFixed(1).replace('.', ',')}s`;
}

function formatarBytes(b) {
  if (b == null) return '—';
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(2)} MB`;
}

function formatarHora(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return iso;
  }
}

function formatarData(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('pt-BR');
  } catch {
    return iso;
  }
}
