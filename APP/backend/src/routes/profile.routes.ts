import { Router, Request, Response, NextFunction } from 'express';
import { body, query, param, validationResult } from 'express-validator';
import { authenticate, AuthRequest } from '../middleware/authenticate';
import { ProfileModel } from '../models/ProfileModel';
import { upload, deleteFileByUrl } from '../services/storageService';

const router = Router();

// All routes in this file require auth
router.use(authenticate);

// ── My profile ────────────────────────────────────────────────────────────────

router.get('/me', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  const profile = ProfileModel.getMyProfile(sub);
  if (!profile) { res.status(404).json({ error: 'not_found' }); return; }
  res.json(profile);
});

const updateRules = [
  body('name').optional().trim().isLength({ min: 1, max: 80 }),
  body('bio').optional().trim().isLength({ max: 500 }),
  body('city').optional().trim().isLength({ min: 1, max: 80 }),
  body('region').optional().trim().isLength({ min: 1, max: 80 }),
  body('gender').optional().isIn(['male', 'female', 'other']),
  body('date_of_birth').optional().matches(/^\d{4}-\d{2}-\d{2}$/),
];

router.put('/me', updateRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

  const { sub } = (req as AuthRequest).user;
  const allowed = ['name', 'bio', 'city', 'region', 'gender', 'date_of_birth'] as const;
  const fields = Object.fromEntries(
    allowed.filter(k => req.body[k] !== undefined).map(k => [k, req.body[k]]),
  ) as Parameters<typeof ProfileModel.updateMyProfile>[1];

  const updated = ProfileModel.updateMyProfile(sub, fields);
  res.json(updated);
});

// ── Main photo — POST /users/me/photo ─────────────────────────────────────────
// Field name: 'photo' (matches mobile FormData.append('photo', ...))

function handleUpload(req: Request, res: Response, next: NextFunction): void {
  upload.single('photo')(req, res, (err) => {
    if (err) {
      const code = (err as NodeJS.ErrnoException & { code?: string }).code;
      if (code === 'INVALID_FILE_TYPE') { res.status(415).json({ error: 'invalid_file_type' }); return; }
      if (err.message === 'File too large') { res.status(413).json({ error: 'file_too_large' }); return; }
      next(err); return;
    }
    next();
  });
}

router.post('/me/photo', handleUpload, (req: Request, res: Response): void => {
  if (!req.file) { res.status(422).json({ error: 'missing_file' }); return; }
  const { sub } = (req as AuthRequest).user;

  const existing = ProfileModel.getMyProfile(sub);
  if (existing?.photo_url) deleteFileByUrl(existing.photo_url);

  const url = `/uploads/${req.file.filename}`;
  ProfileModel.setMainPhoto(sub, url);
  res.json({ photo_url: url });
});

// ── Additional photos ─────────────────────────────────────────────────────────

// Returns Photo[] directly (not wrapped)
router.get('/me/photos', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  res.json(ProfileModel.getMyPhotos(sub));
});

// Returns the newly added Photo (single object, not array)
router.post('/me/photos', handleUpload, (req: Request, res: Response): void => {
  if (!req.file) { res.status(422).json({ error: 'missing_file' }); return; }
  const { sub } = (req as AuthRequest).user;

  if (ProfileModel.countPhotos(sub) >= 4) {
    deleteFileByUrl(`/uploads/${req.file.filename}`);
    res.status(422).json({ error: 'photo_limit_reached' });
    return;
  }

  const url = `/uploads/${req.file.filename}`;
  const photo = ProfileModel.addPhoto(sub, url);
  res.status(201).json(photo);
});

router.delete(
  '/me/photos/:photo_id',
  [param('photo_id').isUUID()],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

    const { sub } = (req as AuthRequest).user;
    const deleted = ProfileModel.deletePhoto(sub, req.params.photo_id);
    if (!deleted) { res.status(404).json({ error: 'not_found' }); return; }

    deleteFileByUrl(deleted.url);
    res.json({ ok: true });
  },
);

// ── Discover — returns Candidate[] directly ───────────────────────────────────

const discoverRules = [
  query('page').optional().isInt({ min: 1 }).toInt(),
  query('limit').optional().isInt({ min: 1, max: 100 }).toInt(),
];

router.get('/discover', discoverRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

  const { sub } = (req as AuthRequest).user;
  const page  = (req.query.page  as unknown as number) || 1;
  const limit = (req.query.limit as unknown as number) || 20;
  const result = ProfileModel.discover(sub, page, limit);
  res.json(result.candidates);
});

// ── Push token — /users/me/push-token ────────────────────────────────────────

router.post(
  '/me/push-token',
  [body('token').trim().notEmpty(), body('platform').optional().isIn(['ios', 'android'])],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

    const { sub } = (req as AuthRequest).user;
    ProfileModel.registerPushToken(sub, req.body.token);
    res.json({ ok: true });
  },
);

router.delete('/me/push-token', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  ProfileModel.unregisterPushToken(sub);
  res.json({ ok: true });
});

// ── Peer profile — /:id routes MUST come after all /me/* and /discover ────────

router.get(
  '/:id',
  [param('id').isUUID()],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

    const { sub } = (req as AuthRequest).user;
    const peer = ProfileModel.getPeerProfile(req.params.id, sub);
    if (!peer) { res.status(404).json({ error: 'not_found' }); return; }
    res.json(peer);
  },
);

// Returns { peer_name, photos } — mobile usePeerPhotos reads both fields
router.get(
  '/:id/photos',
  [param('id').isUUID()],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

    const { sub } = (req as AuthRequest).user;
    const peer = ProfileModel.getPeerProfile(req.params.id, sub);
    if (!peer) { res.status(404).json({ error: 'not_found' }); return; }
    res.json({ name: peer.name, photos: ProfileModel.getPeerPhotos(req.params.id) });
  },
);

router.post(
  '/:id/block',
  [param('id').isUUID()],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { res.status(422).json({ errors: errors.array() }); return; }

    const { sub } = (req as AuthRequest).user;
    if (sub === req.params.id) { res.status(422).json({ error: 'cannot_block_self' }); return; }

    ProfileModel.blockUser(sub, req.params.id);
    res.json({ ok: true });
  },
);

export default router;
