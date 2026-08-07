import express from 'express';
import cors from 'cors';
import { config } from './config';
import { errorHandler } from './middleware/errorHandler';
import { mountSpa } from './utils/mountSpa';
import apiRoutes from './routes/api.routes';

export function createApp(): express.Application
{
  const app = express();

  // CORS — the web and admin dashboards are served from different origins
  // than this API in dev (and typically in production too), so browsers
  // need an explicit Access-Control-Allow-Origin before they'll let
  // frontend JS read the response.
  app.use(cors({
    origin: config.corsOrigins,
    credentials: true,
  }));

  // Body parsing
  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

  // Every backend API route lives under /api/* — composed in
  // routes/api.routes.ts. The web and admin frontends are served
  // same-origin from this same server (see mountSpa below), and several
  // of their own page paths are string-identical to API paths that used
  // to live at root (/admin/users, /chat/:peer_id) — namespacing the
  // whole API under /api avoids that class of collision permanently,
  // rather than resolving it prefix-by-prefix. See APP/project.md's
  // CD-pipeline note for the history.
  app.use('/api', apiRoutes);

  // Serve the built web and admin frontends same-origin — no-ops if their
  // public/ folders aren't populated (ordinary backend-only local dev).
  // /admin must be mounted before / — a general root mount is a prefix of
  // every path, including /admin/*, so the more specific one has to run
  // first or it would never be reached.
  mountSpa(app, '/admin', config.adminPublicDir);
  mountSpa(app, '/',      config.webPublicDir);

  // Global error handler (must be last)
  app.use(errorHandler);

  return app;
}
