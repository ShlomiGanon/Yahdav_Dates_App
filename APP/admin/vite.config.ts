import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

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
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 5173,
  },
}));
