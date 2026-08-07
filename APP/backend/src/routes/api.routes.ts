import express from 'express';
import path from 'path';
import { config } from '../config';
import authRoutes    from './auth.routes';
import profileRoutes from './profile.routes';
import chatRoutes    from './chat.routes';
import adminRoutes   from './admin.routes';

// Composes every backend API route into one router, mounted at /api in
// app.ts. Adding a new resource is a one-line change here rather than a
// /api/* prefix string to get right at every call site.
const router = express.Router();

router.use('/uploads', express.static(path.resolve(config.uploadsDir)));

router.get('/health', (_req, res) =>
{
  res.json({ ok: true });
});

router.use('/auth',  authRoutes);
router.use('/users', profileRoutes);
router.use('/chat',  chatRoutes);
router.use('/admin', adminRoutes);

export default router;
