import express from 'express';
import cors from 'cors';
import path from 'path';
import { config } from './config';
import { errorHandler } from './middleware/errorHandler';
import authRoutes    from './routes/auth.routes';
import profileRoutes from './routes/profile.routes';
import chatRoutes    from './routes/chat.routes';
import adminRoutes   from './routes/admin.routes';

export function createApp(): express.Application {
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

  // Static file serving for uploaded photos
  app.use('/uploads', express.static(path.resolve(config.uploadsDir)));

  // Health check
  app.get('/health', (_req, res) => res.json({ ok: true }));

  app.use('/auth',  authRoutes);
  app.use('/users', profileRoutes);
  app.use('/chat',  chatRoutes);
  app.use('/admin', adminRoutes);
  // app.use('/chat',   chatRoutes);   — Phase 4
  // app.use('/admin',  adminRoutes);  — Phase 5

  // Global error handler (must be last)
  app.use(errorHandler);

  return app;
}
