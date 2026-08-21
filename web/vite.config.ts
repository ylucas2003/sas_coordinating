import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Build do frontend do SAS. Uma entrada só: o login virou rota do SPA.
// Em dev o uvicorn roda em outra porta (ou outro container); o proxy faz o
// browser ver tudo na mesma origem, exatamente como o nginx faz em produção.
// É o que permite o cliente HTTP usar `/api` como caminho relativo sempre,
// sem detectar ambiente e sem depender de CORS.
function proxyDaApi() {
  return {
    '/api': {
      target: process.env.VITE_API_ALVO ?? 'http://localhost:8000',
      changeOrigin: true,
      rewrite: (caminho: string) => caminho.replace(/^\/api/, ''),
    },
  };
}

export default defineConfig({
  plugins: [react()],

  server: {
    // `host: true` para o dev server responder fora do container (docker-compose).
    host: true,
    port: 8080,
    proxy: proxyDaApi(),
  },

  // `npm run preview` serve o build de produção. Precisa do mesmo proxy, senão
  // o smoke test do build local não alcança a API.
  preview: {
    proxy: proxyDaApi(),
  },

  build: {
    outDir: 'dist',
    // Os assets saem com hash no nome, que é o que permite o nginx cacheá-los
    // como `immutable` (ver web/nginx.conf).
  },
});
