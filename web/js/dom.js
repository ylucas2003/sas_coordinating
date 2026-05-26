// Helpers mínimos de DOM. Sem framework — apenas funções utilitárias para
// criar elementos e tags de template.

/**
 * Cria um elemento com atributos e filhos.
 *   el('div', { class: 'card' }, [el('h1', {}, ['Olá'])])
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else {
      node.setAttribute(key, value === true ? '' : String(value));
    }
  }
  for (const child of [].concat(children)) {
    if (child == null || child === false) continue;
    if (typeof child === 'string' || typeof child === 'number') {
      node.appendChild(document.createTextNode(String(child)));
    } else {
      node.appendChild(child);
    }
  }
  return node;
}

/** Limpa um nó. */
export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

/** Formata número como "7,2" — convenção do design system (ver 03). */
export function fmtNota(n) {
  if (n == null) return '—';
  return n.toFixed(1).replace('.', ',');
}

/** Formata delta com sinal e seta. */
export function fmtDelta(d) {
  if (d == null) return '';
  const sign = d > 0 ? '↑' : d < 0 ? '↓' : '→';
  return `${sign} ${Math.abs(d).toFixed(1).replace('.', ',')}`;
}
