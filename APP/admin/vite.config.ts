import { defineConfig } from 'vite';
import type { Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { APP_NAME } from '../shared/config';

// Replaces the %APP_NAME% placeholder in index.html's <title> with the
// shared constant at build/dev-serve time — matches web/vite.config.ts's
// identical plugin. See APP/shared/config.ts.
function injectAppName(): Plugin
{
  return {
    name: 'inject-app-name',
    transformIndexHtml(html)
    {
      return html.replace(/%APP_NAME%/g, APP_NAME);
    },
  };
}

export default defineConfig(({ command }) => ({
  // Only the production build needs this — the built app is served by the
  // backend from public/admin/ at the /admin route (see
  // backend/src/utils/mountSpa.ts), so its own asset URLs (JS/CSS) need
  // that prefix or they'd resolve against the site root instead. Dev
  // (`npm run dev`) keeps the existing plain http://localhost:5173/ —
  // unaffected, since Vite's dev server does apply `base` to its own
  // served paths too, and changing that would break the documented local
  // dev workflow for no reason (dev talks to the backend cross-origin via
  // CORS, never through this mount).
  base: command === 'build' ? '/admin/' : '/',
  plugins: [react(), injectAppName()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // First use of @shared from admin — matches web's vite.config.ts
      // alias exactly. Only APP_NAME is consumed today.
      '@shared': path.resolve(__dirname, '../shared'),
    },
  },
  server: {
    port: 5173,
  },
}));
