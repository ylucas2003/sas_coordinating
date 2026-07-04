// Modal de edição com confirmação em 2 passos.
//
// Fluxo: formulário → diff das alterações → confirmar → resolve() com os valores.
// Cada função retorna Promise<objeto | null (cancelado)>.

import { el, fmtNota } from '../../dom.js';

let overlayAtivo = null;

function fecharOverlay() {
  if (overlayAtivo) {
    overlayAtivo.remove();
    overlayAtivo = null;
  }
}

function montarOverlay(conteudo, onFechar) {
  const overlay = el('div', { class: 'dialog-overlay' }, [conteudo]);
  overlay.addEventListener('click', (ev) => {
    if (ev.target === overlay) onFechar();
  });
  document.body.appendChild(overlay);
  overlayAtivo = overlay;
}

function criarDiff(mudancas) {
  return el('div', { class: 'dialog__body dialog__confirmacao' }, [
    el('p', { class: 'dialog__confirmacao-titulo' }, ['Confirmar as seguintes alterações?']),
    el('div', { class: 'dialog__diff' }, mudancas.map((m) =>
      el('div', { class: 'dialog__diff-linha' }, [
        el('span', { class: 'dialog__diff-campo' }, [m.campo]),
        el('span', { class: 'dialog__diff-de' }, [String(m.de)]),
        el('span', { class: 'dialog__diff-seta' }, [' → ']),
        el('span', { class: 'dialog__diff-para' }, [String(m.para)]),
      ])
    )),
  ]);
}

// ─── Edição de nota ────────────────────────────────────────────────────────

/**
 * Abre modal de edição de nota.
 *
 * @param {{ nomeAluno: string, nomeSimulado: string,
 *            pontuacaoAtual: number|null, presenteAtual: boolean,
 *            notaMaxima: number|null }} opcoes
 * @returns {Promise<{pontuacao: number|null, presente: boolean}|null>}
 */
export function abrirEdicaoNota({ nomeAluno, nomeSimulado, pontuacaoAtual, presenteAtual, notaMaxima }) {
  return new Promise((resolve) => {
    fecharOverlay();

    let presente = presenteAtual ?? true;
    let pontuacao = pontuacaoAtual;

    const inputPontuacao = el('input', {
      type: 'number',
      class: 'dialog__input',
      min: '0',
      max: String(notaMaxima ?? ''),
      step: '0.5',
      value: pontuacao != null ? String(pontuacao) : '',
      placeholder: 'ex.: 14',
    });
    inputPontuacao.disabled = !presente;

    const checkPresente = el('input', { type: 'checkbox' });
    checkPresente.checked = presente;
    checkPresente.addEventListener('change', () => {
      presente = checkPresente.checked;
      inputPontuacao.disabled = !presente;
      if (!presente) {
        inputPontuacao.value = '';
        inputPontuacao.classList.remove('dialog__input--erro');
      }
    });

    const corpoForm = el('div', { class: 'dialog__body' }, [
      el('div', { class: 'dialog__campo' }, [
        el('label', { class: 'dialog__checkbox-row' }, [
          checkPresente,
          el('span', { class: 'dialog__checkbox-label' }, ['Presente na prova']),
        ]),
      ]),
      el('div', { class: 'dialog__campo' }, [
        el('span', { class: 'dialog__label' }, ['Pontuação']),
        inputPontuacao,
        el('span', { class: 'dialog__hint' }, [
          notaMaxima != null ? `de ${notaMaxima} questões` : 'pontuação bruta',
        ]),
      ]),
    ]);

    const btnCancelar  = el('button', { class: 'btn btn--ghost' },   ['Cancelar']);
    const btnSalvar    = el('button', { class: 'btn btn--primary' }, ['Salvar']);
    const btnVoltar    = el('button', { class: 'btn btn--ghost' },   ['← Voltar']);
    const btnConfirmar = el('button', { class: 'btn btn--primary' }, ['Confirmar']);

    btnVoltar.style.display = 'none';
    btnConfirmar.style.display = 'none';

    const footer = el('div', { class: 'dialog__footer' }, [
      btnVoltar, btnCancelar, btnSalvar, btnConfirmar,
    ]);

    const dialog = el('div', { class: 'dialog' }, [
      el('div', { class: 'dialog__header' }, [
        el('div', { class: 'dialog__titulo' }, ['Editar nota']),
        el('div', { class: 'dialog__subtitulo' }, [`${nomeAluno} · ${nomeSimulado}`]),
      ]),
      corpoForm,
      footer,
    ]);

    let diffEl = null;

    function irParaForm() {
      if (diffEl) { diffEl.remove(); diffEl = null; }
      corpoForm.style.display = '';
      btnSalvar.style.display = '';
      btnCancelar.style.display = '';
      btnVoltar.style.display = 'none';
      btnConfirmar.style.display = 'none';
    }

    function irParaDiff(mudancas) {
      diffEl = criarDiff(mudancas);
      dialog.insertBefore(diffEl, footer);
      corpoForm.style.display = 'none';
      btnSalvar.style.display = 'none';
      btnCancelar.style.display = 'none';
      btnVoltar.style.display = '';
      btnConfirmar.style.display = '';
    }

    function cancelar() { fecharOverlay(); resolve(null); }

    btnCancelar.addEventListener('click', cancelar);
    btnVoltar.addEventListener('click', irParaForm);

    btnSalvar.addEventListener('click', () => {
      inputPontuacao.classList.remove('dialog__input--erro');
      const raw = inputPontuacao.value.trim().replace(',', '.');
      presente = checkPresente.checked;
      pontuacao = presente && raw !== '' ? parseFloat(raw) : null;

      if (presente) {
        if (raw === '' || isNaN(pontuacao) || pontuacao < 0) {
          inputPontuacao.classList.add('dialog__input--erro');
          inputPontuacao.focus();
          return;
        }
        if (notaMaxima != null && pontuacao > notaMaxima) {
          inputPontuacao.classList.add('dialog__input--erro');
          inputPontuacao.focus();
          return;
        }
      }

      const mudancas = [];
      if (presente !== presenteAtual) {
        mudancas.push({ campo: 'Presente', de: presenteAtual ? 'Sim' : 'Não', para: presente ? 'Sim' : 'Não' });
      }
      if (pontuacao !== pontuacaoAtual) {
        mudancas.push({
          campo: 'Pontuação',
          de: pontuacaoAtual != null ? fmtNota(pontuacaoAtual) : '—',
          para: pontuacao != null ? fmtNota(pontuacao) : '—',
        });
      }

      if (!mudancas.length) { fecharOverlay(); resolve(null); return; }
      irParaDiff(mudancas);
    });

    btnConfirmar.addEventListener('click', () => {
      fecharOverlay();
      resolve({ pontuacao, presente });
    });

    montarOverlay(dialog, cancelar);
    setTimeout(() => (presente ? inputPontuacao.focus() : checkPresente.focus()), 50);
  });
}

// ─── Ficha de nota: comparação + edição ───────────────────────────────────

/**
 * Abre modal com stats de comparação e form de edição juntos numa única view.
 *
 * Flow: view única → Salvar → diff → Confirmar.
 *
 * @param {{ nomeAluno: string, nomeSimulado: string,
 *            pontuacaoAtual: number|null, presenteAtual: boolean,
 *            notaMaxima: number|null,
 *            stats: { posicao: number|null, totalPresentes: number,
 *                     nota: number|null, media: number, maiorNota: number,
 *                     mediaTop15: number, mediaBottom15: number,
 *                     mediana: number } }} opcoes
 * @returns {Promise<{pontuacao: number|null, presente: boolean}|null>}
 */
export function abrirFichaNota({ nomeAluno, nomeSimulado, pontuacaoAtual, presenteAtual, notaMaxima, stats }) {
  return new Promise((resolve) => {
    fecharOverlay();

    let presente = presenteAtual ?? true;
    let pontuacao = pontuacaoAtual;

    // ── helpers ────────────────────────────────────────────────────────
    function notaTone(v) {
      if (v == null) return '';
      return v >= 7 ? ' tone-verde' : v >= 5 ? ' tone-ambar' : ' tone-vermelho';
    }

    function kpiEl(rotulo, valor, toneClass) {
      return el('div', { class: 'dialog__kpi' }, [
        el('div', { class: 'dialog__kpi-rotulo' }, [rotulo]),
        el('div', { class: `dialog__kpi-valor${toneClass || ''}` }, [valor ?? '—']),
      ]);
    }

    // ── bloco de KPIs ────────────────────────────────────────────────
    function buildKpis() {
      if (!stats || stats.totalPresentes === 0) return null;
      const { posicao, totalPresentes, nota, media, mediaTop15, mediaBottom15, mediana } = stats;
      const posTone = posicao != null
        ? posicao <= Math.ceil(totalPresentes * 0.15) ? ' tone-verde'
        : posicao <= Math.ceil(totalPresentes * 0.5)  ? ' tone-ambar'
        : ' tone-vermelho'
        : '';
      const acertosLabel = pontuacaoAtual != null && notaMaxima != null
        ? `${pontuacaoAtual} / ${notaMaxima}`
        : pontuacaoAtual != null ? String(pontuacaoAtual) : '—';

      return el('div', { class: 'dialog__kpi-grid' }, [
        kpiEl('Posição',    posicao != null ? `#${posicao} / ${totalPresentes}` : `— / ${totalPresentes}`, posTone),
        kpiEl('Nota',       nota   != null ? fmtNota(nota)         : '—', notaTone(nota)),
        kpiEl('Acertos',    acertosLabel),
        kpiEl('Média',      media       != null ? fmtNota(media)       : '—', notaTone(media)),
        kpiEl('Top 15%',    mediaTop15  != null ? fmtNota(mediaTop15)  : '—'),
        kpiEl('Bottom 15%', mediaBottom15 != null ? fmtNota(mediaBottom15) : '—'),
      ]);
    }

    // ── form de edição ────────────────────────────────────────────────
    const inputPontuacao = el('input', {
      type: 'number',
      class: 'dialog__input',
      min: '0',
      max: String(notaMaxima ?? ''),
      step: '0.5',
      value: pontuacao != null ? String(pontuacao) : '',
      placeholder: 'ex.: 14',
    });
    inputPontuacao.disabled = !presente;

    const checkPresente = el('input', { type: 'checkbox' });
    checkPresente.checked = presente;
    checkPresente.addEventListener('change', () => {
      presente = checkPresente.checked;
      inputPontuacao.disabled = !presente;
      if (!presente) {
        inputPontuacao.value = '';
        inputPontuacao.classList.remove('dialog__input--erro');
      }
    });

    const kpisEl = buildKpis();

    const corpo = el('div', { class: 'dialog__body' }, [
      presenteAtual === false
        ? el('p', { class: 'dialog__hint dialog__hint--ambar', style: 'margin-bottom: 2px;' }, ['Aluno marcado como ausente.'])
        : null,
      kpisEl,
      kpisEl ? el('div', { class: 'dialog__sep' }) : null,
      el('div', { class: 'dialog__campo' }, [
        el('label', { class: 'dialog__checkbox-row' }, [
          checkPresente,
          el('span', { class: 'dialog__checkbox-label' }, ['Presente na prova']),
        ]),
      ]),
      el('div', { class: 'dialog__campo' }, [
        el('span', { class: 'dialog__label' }, ['Pontuação']),
        inputPontuacao,
        el('span', { class: 'dialog__hint' }, [
          notaMaxima != null ? `de ${notaMaxima} questões` : 'pontuação bruta',
        ]),
      ]),
    ]);

    // ── botões ────────────────────────────────────────────────────────
    const btnCancelar   = el('button', { class: 'btn btn--ghost' },   ['Cancelar']);
    const btnSalvar     = el('button', { class: 'btn btn--primary' }, ['Salvar']);
    const btnVoltarDiff = el('button', { class: 'btn btn--ghost' },   ['← Voltar']);
    const btnConfirmar  = el('button', { class: 'btn btn--primary' }, ['Confirmar']);

    btnVoltarDiff.style.display = 'none';
    btnConfirmar.style.display  = 'none';

    const footer = el('div', { class: 'dialog__footer' }, [
      btnVoltarDiff, btnCancelar, btnSalvar, btnConfirmar,
    ]);

    const dialog = el('div', { class: 'dialog dialog--largo' }, [
      el('div', { class: 'dialog__header' }, [
        el('div', { class: 'dialog__titulo' }, [nomeSimulado]),
        el('div', { class: 'dialog__subtitulo' }, [nomeAluno]),
      ]),
      corpo,
      footer,
    ]);

    let diffEl = null;

    function irParaForm() {
      if (diffEl) { diffEl.remove(); diffEl = null; }
      corpo.style.display = '';
      btnCancelar.style.display = '';
      btnSalvar.style.display = '';
      btnVoltarDiff.style.display = 'none';
      btnConfirmar.style.display = 'none';
    }

    function irParaDiff(mudancas) {
      diffEl = criarDiff(mudancas);
      dialog.insertBefore(diffEl, footer);
      corpo.style.display = 'none';
      btnCancelar.style.display = 'none';
      btnSalvar.style.display = 'none';
      btnVoltarDiff.style.display = '';
      btnConfirmar.style.display = '';
    }

    function cancelar() { fecharOverlay(); resolve(null); }

    btnCancelar.addEventListener('click', cancelar);
    btnVoltarDiff.addEventListener('click', irParaForm);

    btnSalvar.addEventListener('click', () => {
      inputPontuacao.classList.remove('dialog__input--erro');
      const raw = inputPontuacao.value.trim().replace(',', '.');
      presente = checkPresente.checked;
      pontuacao = presente && raw !== '' ? parseFloat(raw) : null;

      if (presente) {
        if (raw === '' || isNaN(pontuacao) || pontuacao < 0) {
          inputPontuacao.classList.add('dialog__input--erro');
          inputPontuacao.focus();
          return;
        }
        if (notaMaxima != null && pontuacao > notaMaxima) {
          inputPontuacao.classList.add('dialog__input--erro');
          inputPontuacao.focus();
          return;
        }
      }

      const mudancas = [];
      const presenteInicial = presenteAtual ?? true;
      if (presente !== presenteInicial) {
        mudancas.push({ campo: 'Presente', de: presenteInicial ? 'Sim' : 'Não', para: presente ? 'Sim' : 'Não' });
      }
      if (pontuacao !== pontuacaoAtual) {
        mudancas.push({
          campo: 'Pontuação',
          de: pontuacaoAtual != null ? String(pontuacaoAtual) : '—',
          para: pontuacao != null ? String(pontuacao) : '—',
        });
      }

      if (!mudancas.length) { fecharOverlay(); resolve(null); return; }
      irParaDiff(mudancas);
    });

    btnConfirmar.addEventListener('click', () => {
      fecharOverlay();
      resolve({ pontuacao, presente });
    });

    montarOverlay(dialog, cancelar);
    setTimeout(() => (presente ? inputPontuacao.focus() : checkPresente.focus()), 50);
  });
}

// ─── Edição de simulado ────────────────────────────────────────────────────

/**
 * Abre modal de edição de simulado.
 *
 * @param {{ nome: string, rotuloAtual: string|null,
 *            notaMaximaAtual: number|null, anuladoAtual: boolean }} opcoes
 * @returns {Promise<Partial<{nome, rotulo_curto, nota_maxima, anulado}>|null>}
 */
export function abrirEdicaoSimulado({ nome, rotuloAtual, notaMaximaAtual, anuladoAtual }) {
  return new Promise((resolve) => {
    fecharOverlay();

    let resultado = null;

    const inputNome = el('input', {
      type: 'text',
      class: 'dialog__input',
      value: nome || '',
    });

    const inputRotulo = el('input', {
      type: 'text',
      class: 'dialog__input',
      value: rotuloAtual || '',
      placeholder: 'ex.: P12',
      maxlength: '12',
    });

    const inputNotaMax = el('input', {
      type: 'number',
      class: 'dialog__input',
      min: '1',
      step: '1',
      value: notaMaximaAtual != null ? String(notaMaximaAtual) : '',
      placeholder: 'ex.: 20',
    });

    const checkAnulado = el('input', { type: 'checkbox' });
    checkAnulado.checked = anuladoAtual ?? false;

    const corpoForm = el('div', { class: 'dialog__body' }, [
      el('div', { class: 'dialog__campo' }, [
        el('span', { class: 'dialog__label' }, ['Nome']),
        inputNome,
      ]),
      el('div', { class: 'dialog__campo' }, [
        el('span', { class: 'dialog__label' }, ['Rótulo curto (Pn)']),
        inputRotulo,
        el('span', { class: 'dialog__hint' }, ['Usado no eixo do gráfico. Ex.: P12']),
      ]),
      el('div', { class: 'dialog__campo' }, [
        el('span', { class: 'dialog__label' }, ['Nota máxima (nº de questões)']),
        inputNotaMax,
      ]),
      el('div', { class: 'dialog__campo' }, [
        el('label', { class: 'dialog__checkbox-row' }, [
          checkAnulado,
          el('span', { class: 'dialog__checkbox-label' }, ['Marcar como anulado']),
        ]),
        el('span', { class: 'dialog__hint' }, [
          'Simulados anulados ficam fora das estatísticas e classificações.',
        ]),
      ]),
    ]);

    const btnCancelar  = el('button', { class: 'btn btn--ghost' },   ['Cancelar']);
    const btnSalvar    = el('button', { class: 'btn btn--primary' }, ['Salvar']);
    const btnVoltar    = el('button', { class: 'btn btn--ghost' },   ['← Voltar']);
    const btnConfirmar = el('button', { class: 'btn btn--primary' }, ['Confirmar']);

    btnVoltar.style.display = 'none';
    btnConfirmar.style.display = 'none';

    const footer = el('div', { class: 'dialog__footer' }, [
      btnVoltar, btnCancelar, btnSalvar, btnConfirmar,
    ]);

    const dialog = el('div', { class: 'dialog' }, [
      el('div', { class: 'dialog__header' }, [
        el('div', { class: 'dialog__titulo' }, ['Editar simulado']),
        el('div', { class: 'dialog__subtitulo' }, [nome || '—']),
      ]),
      corpoForm,
      footer,
    ]);

    let diffEl = null;

    function irParaForm() {
      if (diffEl) { diffEl.remove(); diffEl = null; }
      corpoForm.style.display = '';
      btnSalvar.style.display = '';
      btnCancelar.style.display = '';
      btnVoltar.style.display = 'none';
      btnConfirmar.style.display = 'none';
      resultado = null;
    }

    function irParaDiff(mudancas) {
      diffEl = criarDiff(mudancas);
      dialog.insertBefore(diffEl, footer);
      corpoForm.style.display = 'none';
      btnSalvar.style.display = 'none';
      btnCancelar.style.display = 'none';
      btnVoltar.style.display = '';
      btnConfirmar.style.display = '';
    }

    function cancelar() { fecharOverlay(); resolve(null); }

    btnCancelar.addEventListener('click', cancelar);
    btnVoltar.addEventListener('click', irParaForm);

    btnSalvar.addEventListener('click', () => {
      inputNome.classList.remove('dialog__input--erro');
      inputNotaMax.classList.remove('dialog__input--erro');

      const nomeNovo    = inputNome.value.trim();
      const rotuloNovo  = inputRotulo.value.trim() || null;
      const notaMaxRaw  = inputNotaMax.value.trim().replace(',', '.');
      const notaMaxNova = notaMaxRaw !== '' ? parseFloat(notaMaxRaw) : null;
      const anuladoNovo = checkAnulado.checked;

      if (!nomeNovo) {
        inputNome.classList.add('dialog__input--erro');
        inputNome.focus();
        return;
      }
      if (notaMaxNova !== null && (isNaN(notaMaxNova) || notaMaxNova <= 0)) {
        inputNotaMax.classList.add('dialog__input--erro');
        inputNotaMax.focus();
        return;
      }

      const mudancas = [];
      if (nomeNovo !== nome) {
        mudancas.push({ campo: 'Nome', de: nome || '—', para: nomeNovo });
      }
      if (rotuloNovo !== (rotuloAtual || null)) {
        mudancas.push({ campo: 'Rótulo', de: rotuloAtual || '—', para: rotuloNovo || '—' });
      }
      if (notaMaxNova !== null && notaMaxNova !== notaMaximaAtual) {
        mudancas.push({ campo: 'Nota máx.', de: String(notaMaximaAtual ?? '—'), para: String(notaMaxNova) });
      }
      if (anuladoNovo !== (anuladoAtual ?? false)) {
        mudancas.push({ campo: 'Anulado', de: anuladoAtual ? 'Sim' : 'Não', para: anuladoNovo ? 'Sim' : 'Não' });
      }

      if (!mudancas.length) { fecharOverlay(); resolve(null); return; }

      resultado = {};
      if (nomeNovo !== nome) resultado.nome = nomeNovo;
      if (rotuloNovo !== (rotuloAtual || null)) resultado.rotulo_curto = rotuloNovo;
      if (notaMaxNova !== null && notaMaxNova !== notaMaximaAtual) resultado.nota_maxima = notaMaxNova;
      if (anuladoNovo !== (anuladoAtual ?? false)) resultado.anulado = anuladoNovo;

      irParaDiff(mudancas);
    });

    btnConfirmar.addEventListener('click', () => {
      fecharOverlay();
      resolve(resultado);
    });

    montarOverlay(dialog, cancelar);
    setTimeout(() => inputNome.focus(), 50);
  });
}
