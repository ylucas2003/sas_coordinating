// Roteador hash simples. Mapeia `#/alunos/A023` para um par (rota, id).
//
// Hash-based para não exigir rewrite no Vercel — qualquer URL profunda
// (`https://sas.app/#/simulados/S08`) é servida pelo index.html.

const ROUTES = [
  { pattern: /^$|^\/?$/, name: 'painel' },
  { pattern: /^\/?painel\/?$/, name: 'painel' },
  { pattern: /^\/?alunos\/?$/, name: 'alunos' },
  { pattern: /^\/?alunos\/([^/]+)\/?$/, name: 'aluno', params: ['id'] },
  { pattern: /^\/?simulados\/?$/, name: 'simulados' },
  { pattern: /^\/?simulados\/([^/]+)\/?$/, name: 'simulado', params: ['id'] },
  { pattern: /^\/?ciclos\/?$/, name: 'ciclos' },
  { pattern: /^\/?ciclos\/([^/]+)\/?$/, name: 'ciclo', params: ['id'] },
  { pattern: /^\/?importar\/?$/, name: 'importar' },
];

export function parseHash(hash) {
  const path = (hash || '').replace(/^#/, '');
  for (const route of ROUTES) {
    const m = path.match(route.pattern);
    if (m) {
      const params = {};
      (route.params || []).forEach((name, i) => { params[name] = m[i + 1]; });
      return { name: route.name, params };
    }
  }
  return { name: 'painel', params: {} };
}

/** Qual aba da topbar fica destacada para essa rota. */
export function topbarTabFor(routeName) {
  if (routeName === 'aluno') return 'alunos';
  if (routeName === 'simulado') return 'simulados';
  if (routeName === 'ciclo') return 'ciclos';
  return routeName;
}

/** Atalho para mudar a rota. */
export function navigate(path) {
  window.location.hash = path;
}
