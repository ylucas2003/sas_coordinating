// Calendário anual em grid de 12 mini-meses.
// Recebe um Set<string> de datas ISO (yyyy-mm-dd) que devem aparecer coloridas
// e um Set<string> de datas selecionadas. Clique numa data colorida chama
// `onToggleData(iso)`.

import { el } from '../dom.js';

const NOMES_MES = [
  'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
  'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
];

// Semana começa na segunda-feira (convenção BR).
const DIAS_SEMANA = ['S', 'T', 'Q', 'Q', 'S', 'S', 'D'];

function isoData(d) {
  const ano = d.getFullYear();
  const mes = String(d.getMonth() + 1).padStart(2, '0');
  const dia = String(d.getDate()).padStart(2, '0');
  return `${ano}-${mes}-${dia}`;
}

function deduzirAno(datasISO) {
  // Pega o ano mais frequente nas datas dadas. Empate ⇒ ano atual.
  if (!datasISO.size) return new Date().getFullYear();
  const contagem = new Map();
  for (const iso of datasISO) {
    const ano = Number(iso.slice(0, 4));
    contagem.set(ano, (contagem.get(ano) || 0) + 1);
  }
  return [...contagem.entries()].sort((a, b) => b[1] - a[1])[0][0];
}

/**
 * @param {object} opcoes
 * @param {Set<string>} opcoes.datasComSimulado - ISO yyyy-mm-dd
 * @param {Set<string>} opcoes.datasSelecionadas
 * @param {(iso: string) => void} opcoes.onToggleData
 * @param {number} [opcoes.ano] - ano alvo (default: deduzido das datas)
 */
export function calendarioAnual({
  datasComSimulado,
  datasSelecionadas,
  onToggleData,
  ano,
}) {
  const anoAlvo = ano ?? deduzirAno(datasComSimulado);
  const hojeISO = isoData(new Date());

  const meses = [];
  for (let mesIdx = 0; mesIdx < 12; mesIdx++) {
    meses.push(renderMes(mesIdx, anoAlvo, datasComSimulado, datasSelecionadas, hojeISO, onToggleData));
  }

  return el('div', { class: 'calendario' }, [
    el('div', { class: 'calendario__cabecalho' }, [
      el('div', { class: 'calendario__titulo' }, [`Calendário · ${anoAlvo}`]),
      el('div', { class: 'calendario__resumo' }, [
        `${datasComSimulado.size} dia(s) com simulado · ${datasSelecionadas.size} selecionada(s)`,
      ]),
    ]),
    el('div', { class: 'calendario__grid' }, meses),
  ]);
}

function renderMes(mesIdx, ano, comSimulado, selecionadas, hojeISO, onToggle) {
  // Posição do dia 1 (0=domingo … 6=sábado). Convertemos pra base segunda=0.
  const primeiroDia = new Date(ano, mesIdx, 1);
  const offsetSegunda = (primeiroDia.getDay() + 6) % 7;
  const diasNoMes = new Date(ano, mesIdx + 1, 0).getDate();

  const celulas = [];
  // Padding inicial (dias do mês anterior — só visualmente vazios).
  for (let i = 0; i < offsetSegunda; i++) {
    celulas.push(el('div', { class: 'calendario__dia calendario__dia--vazio' }, ['']));
  }

  for (let dia = 1; dia <= diasNoMes; dia++) {
    const iso = `${ano}-${String(mesIdx + 1).padStart(2, '0')}-${String(dia).padStart(2, '0')}`;
    const temSimulado = comSimulado.has(iso);
    const estaSelecionada = selecionadas.has(iso);
    const eHoje = iso === hojeISO;

    const classes = ['calendario__dia'];
    if (temSimulado) classes.push('calendario__dia--com-simulado');
    if (estaSelecionada) classes.push('is-selecionada');
    if (eHoje) classes.push('is-hoje');

    const attrs = {
      class: classes.join(' '),
      title: temSimulado ? `${iso} · ${selecionadas.has(iso) ? 'selecionada' : 'clique pra filtrar'}` : iso,
    };
    if (temSimulado) {
      attrs.onclick = () => onToggle(iso);
    }

    celulas.push(el('div', attrs, [String(dia)]));
  }

  return el('div', { class: 'calendario__mes' }, [
    el('div', { class: 'calendario__mes-titulo' }, [NOMES_MES[mesIdx]]),
    el('div', { class: 'calendario__semanas' },
      DIAS_SEMANA.map((d) => el('div', { class: 'calendario__dia-semana' }, [d]))
    ),
    el('div', { class: 'calendario__semanas' }, celulas),
  ]);
}
