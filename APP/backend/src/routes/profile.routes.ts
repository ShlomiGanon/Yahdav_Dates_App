import { Router, Request, Response, NextFunction } from 'express';
import { body, query, param, validationResult } from 'express-validator';
import { authenticate, AuthRequest } from '../middleware/authenticate';
import { ProfileModel } from '../models/ProfileModel';
import { upload, deleteFileByUrl } from '../services/storageService';
import { ok, fail, failValidation } from '../utils/responses';

const router = Router();

// All routes in this file require auth
router.use(authenticate);

// ── My profile ────────────────────────────────────────────────────────────────

router.get('/me', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  const profile = ProfileModel.getMyProfile(sub);
  if (!profile) { fail(res, 'not_found'); return; }
  ok(res, profile);
});

const updateRules = [
  body('name').optional().trim().isLength({ min: 1, max: 80 })
    .withMessage('השם חייב להכיל בין 1 ל-80 תווים'),
  body('bio').optional().trim().isLength({ max: 500 })
    .withMessage('התיאור יכול להכיל עד 500 תווים'),
  body('city').optional().trim().isLength({ min: 1, max: 80 })
    .withMessage('שם העיר חייב להכיל בין 1 ל-80 תווים'),
  body('region').optional().trim().isLength({ min: 1, max: 80 })
    .withMessage('שם האזור חייב להכיל בין 1 ל-80 תווים'),
  body('gender').optional().isIn(['male', 'female', 'other'])
    .withMessage('יש לבחור מין תקין'),
  body('date_of_birth').optional().matches(/^\d{4}-\d{2}-\d{2}$/)
    .withMessage('תאריך הלידה חייב להיות בפורמט YYYY-MM-DD'),
];

router.put('/me', updateRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

  const { sub } = (req as AuthRequest).user;
  const allowed = ['name', 'bio', 'city', 'region', 'gender', 'date_of_birth'] as const;
  const fields = Object.fromEntries(
    allowed.filter(k => req.body[k] !== undefined).map(k => [k, req.body[k]]),
  ) as Parameters<typeof ProfileModel.updateMyProfile>[1];

  if (Object.keys(fields).length === 0) {
    fail(res, 'validation_error', { message: 'לא נשלחו שדות לעדכון' });
    return;
  }

  const updated = ProfileModel.updateMyProfile(sub, fields);
  ok(res, { ...updated }, 'הפרופיל עודכן בהצלחה');
});

// ── Main photo — POST /users/me/photo ─────────────────────────────────────────
// Field name: 'photo' (matches mobile FormData.append('photo', ...))

function handleUpload(req: Request, res: Response, next: NextFunction): void {
  upload.single('photo')(req, res, (err) => {
    if (err) {
      const code = (err as NodeJS.ErrnoException & { code?: string }).code;
      if (code === 'INVALID_FILE_TYPE') { fail(res, 'invalid_file_type'); return; }
      if (err.message === 'File too large') { fail(res, 'file_too_large'); return; }
      next(err); return;
    }
    next();
  });
}

router.post('/me/photo', handleUpload, (req: Request, res: Response): void => {
  if (!req.file) { fail(res, 'missing_file'); return; }
  const { sub } = (req as AuthRequest).user;

  const existing = ProfileModel.getMyProfile(sub);
  if (existing?.photo_url) deleteFileByUrl(existing.photo_url);

  const url = `/uploads/${req.file.filename}`;
  ProfileModel.setMainPhoto(sub, url);
  ok(res, { photo_url: url }, 'התמונה הועלתה בהצלחה');
});

// ── Additional photos ─────────────────────────────────────────────────────────

router.get('/me/photos', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  ok(res, { photos: ProfileModel.getMyPhotos(sub) });
});

router.post('/me/photos', handleUpload, (req: Request, res: Response): void => {
  if (!req.file) { fail(res, 'missing_file'); return; }
  const { sub } = (req as AuthRequest).user;

  if (ProfileModel.countPhotos(sub) >= 4) {
    deleteFileByUrl(`/uploads/${req.file.filename}`);
    fail(res, 'photo_limit_reached');
    return;
  }

  const url = `/uploads/${req.file.filename}`;
  const photo = ProfileModel.addPhoto(sub, url);
  ok(res, { ...photo }, 'התמונה נוספה בהצלחה');
});

router.delete(
  '/me/photos/:photo_id',
  [param('photo_id').isUUID().withMessage('מזהה תמונה לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    const deleted = ProfileModel.deletePhoto(sub, req.params.photo_id);
    if (!deleted) { fail(res, 'not_found'); return; }

    deleteFileByUrl(deleted.url);
    ok(res, {}, 'התמונה נמחקה בהצלחה');
  },
);

// ── Discover — returns Candidate[] ────────────────────────────────────────────

const discoverRules = [
  query('page').optional().isInt({ min: 1 }).toInt()
    .withMessage('מספר העמוד אינו תקין'),
  query('limit').optional().isInt({ min: 1, max: 100 }).toInt()
    .withMessage('מספר התוצאות חייב להיות בין 1 ל-100'),
];

router.get('/discover', discoverRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

  const { sub } = (req as AuthRequest).user;
  const page  = (req.query.page  as unknown as number) || 1;
  const limit = (req.query.limit as unknown as number) || 20;
  const result = ProfileModel.discover(sub, page, limit);
  ok(res, { candidates: result.candidates });
});

// ── Push token — /users/me/push-token ────────────────────────────────────────

router.post(
  '/me/push-token',
  [
    body('token').trim().notEmpty().withMessage('חסר טוקן התראות'),
    body('platform').optional().isIn(['ios', 'android']).withMessage('פלטפורמה לא נתמכת'),
  ],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    ProfileModel.registerPushToken(sub, req.body.token);
    ok(res, {}, 'נרשמת לקבלת התראות');
  },
);

router.delete('/me/push-token', (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  ProfileModel.unregisterPushToken(sub);
  ok(res, {}, 'התראות בוטלו');
});

// ── Peer profile — /:id routes MUST come after all /me/* and /discover ────────

router.get(
  '/:id',
  [param('id').isUUID().withMessage('מזהה משתמש לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    const peer = ProfileModel.getPeerProfile(req.params.id, sub);
    if (!peer) { fail(res, 'not_found'); return; }
    ok(res, peer);
  },
);

// Returns { name, photos } — mobile usePeerPhotos reads both fields
router.get(
  '/:id/photos',
  [param('id').isUUID().withMessage('מזהה משתמש לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    const peer = ProfileModel.getPeerProfile(req.params.id, sub);
    if (!peer) { fail(res, 'not_found'); return; }
    ok(res, { name: peer.name, photos: ProfileModel.getPeerPhotos(req.params.id) });
  },
);

router.post(
  '/:id/block',
  [param('id').isUUID().withMessage('מזהה משתמש לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    if (sub === req.params.id) { fail(res, 'cannot_block_self'); return; }

    ProfileModel.blockUser(sub, req.params.id);
    ok(res, {}, 'המשתמש נחסם בהצלחה');
  },
);

export default router;
