import { Express } from 'express';
import express from 'express';
import fs from 'fs';
import path from 'path';

// Serves a built single-page-app bundle (web or admin) as static files
// under `urlPrefix`, with an SPA fallback: a GET that doesn't match a real
// file gets `index.html` instead of a 404, so a client-side route (a deep
// link, or a refresh mid-route) still resolves correctly on the server.
//
// No-ops entirely if `staticDir` has no `index.html` yet — true during
// ordinary backend-only local dev, where web and admin run their own
// separate Vite dev servers instead of ever hitting this mount. Only a
// packaged release (see .github/workflows/release.yml) actually populates
// these folders.
//
// Must be registered after every API route it shares an origin with —
// this only serves what nothing earlier in the middleware chain claimed.
export function mountSpa(app: Express, urlPrefix: string, staticDir: string): void
{
  const resolvedDir   = path.resolve(staticDir);
  const indexHtmlPath = path.join(resolvedDir, 'index.html');

  if (!fs.existsSync(indexHtmlPath))
  {
    return;
  }

  const normalizedPrefix = urlPrefix === '/' ? '' : urlPrefix;

  app.use(urlPrefix, express.static(resolvedDir));

  app.get(`${normalizedPrefix}/*`, (_req, res) =>
  {
    res.sendFile(indexHtmlPath);
  });

  if (normalizedPrefix)
  {
    app.get(normalizedPrefix, (_req, res) =>
    {
      res.sendFile(indexHtmlPath);
    });
  }
}
