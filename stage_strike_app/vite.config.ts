import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const HYPERDRIVE_BACKEND = `http://localhost:${env.HYPERDRIVE_PORT || '5500'}`;

  // Paths served by HyperDrive's web server that the Vite dev server must proxy.
  // In production the app is served by HyperDrive on the same origin, so no proxy is needed.
  const PROXIED_PATHS = [
    '/socket.io',   // WebSocket — must be first and use ws:true
    '/user_data',
    '/out',
    '/layout',
    '/assets',
    '/program-state',
    '/ruleset',
    '/stage_strike',
    // Regexes, as a '/score' or '/scoreboard' prefix would also catch the
    // /scoreboard page, which the dev server must serve itself
    '^/score$',
    '^/scoreboard\\d',
    '/characters',
    '/variants',
    '/controllers',
    '/games',
    '/current-game',
    '/match-names',
    '/playerdb',
    '/get-sets',
    '/get-match',
    '/load-',
    '/update-',
    '/set-tournament',
    '/tournament-events',
    '/states',
    '/pull-user',
    '/reset-',
    '/swap-',
    '/stats-',
    '/get-swap',
    '/clear-all',
    '/open-set',
    '/pull-stream',
    '/set-current-stage',
    '/commentary-preview',
  ];

  const silenceECONNRESET = (proxy) => {
    proxy.on('error', (err: NodeJS.ErrnoException) => {
      if (err.code !== 'ECONNRESET') console.error('[proxy]', err);
    });
  };

  const proxy = Object.fromEntries(
    PROXIED_PATHS.map(path => [
      path,
      {
        target: HYPERDRIVE_BACKEND,
        changeOrigin: true,
        ws: path === '/socket.io',
        configure: silenceECONNRESET,
      },
    ])
  );

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    // Production: served by HyperDrive under /stage_strike_app/build/. Dev: serve from root so
    // React Router and WebSocket connections work without a proxy.
    base: mode === 'production' ? '/stage_strike_app/build/' : '/',
    build: {
      outDir: 'build',
    },
    server: {
      port: 3000,
      proxy,
    },
  };
});
