import { Router, Request, Response } from 'express';
import { param, query, body, validationResult } from 'express-validator';
import { authenticate, requireAdmin, AuthRequest } from '../middleware/authenticate';
import { profileQueries } from '../database/queries/profile.queries';
import { authQueries } from '../database/queries/auth.queries';
import { ok, fail, failValidation } from '../utils/responses';

const router = Router();
router.use(authenticate, requireAdmin);

// ── GET /admin/users?limit=&offset=&search= ───────────────────────────────────

const listRules = [
  query('limit').optional().isInt({ min: 1, max: 200 }).toInt()
    .withMessage('מספר התוצאות חייב להיות בין 1 ל-200'),
  query('offset').optional().isInt({ min: 0 }).toInt()
    .withMessage('פרמטר עמוד לא תקין'),
  query('search').optional().trim(),
];

router.get('/users', listRules, (req: Request, res: Response): void => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

  const limit  = (req.query.limit  as unknown as number) || 50;
  const offset = (req.query.offset as unknown as number) || 0;
  const search = (req.query.search as string | undefined)?.toLowerCase();

  let rows = profileQueries.findAll(search ? 10_000 : limit, search ? 0 : offset);

  // In-process search filter — includes name, city, username, email
  if (search) {
    const allCreds = rows.map((p) => authQueries.findById(p.user_id));
    const filtered = rows
      .map((p, i) => ({ profile: p, creds: allCreds[i] }))
      .filter(({ profile, creds: c }) =>
        profile.name.toLowerCase().includes(search) ||
        profile.city.toLowerCase().includes(search) ||
        (c?.username ?? '').toLowerCase().includes(search) ||
        (c?.email ?? '').toLowerCase().includes(search),
      );
    const total = filtered.length;
    const paged = filtered.slice(offset, offset + limit);
    const users = paged.map(({ profile, creds: c }) => buildSummary(profile, c));
    ok(res, { total, users });
    return;
  }

  const total = profileQueries.countAll();
  const creds = rows.map((p) => authQueries.findById(p.user_id));
  const users = rows.map((p, i) => buildSummary(p, creds[i]));
  ok(res, { total, users });
});

// ── GET /admin/users/:id ──────────────────────────────────────────────────────

router.get(
  '/users/:id',
  [param('id').isUUID().withMessage('מזהה משתמש לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const profile = profileQueries.findById(req.params.id);
    if (!profile) { fail(res, 'not_found'); return; }
    const creds = authQueries.findById(req.params.id);

    ok(res, {
      user_id:       profile.user_id,
      name:          profile.name,
      bio:           profile.bio,
      gender:        profile.gender,
      date_of_birth: profile.date_of_birth,
      city:          profile.city,
      region:        profile.region,
      photo_url:     profile.photo_url,
      status:        profile.status,
      registered_at: profile.registered_at,
      updated_at:    profile.updated_at,
      username:      creds?.username ?? null,
      email:         creds?.email    ?? null,
      is_admin:      creds ? creds.is_admin === 1 : false,
      last_login_at: creds?.last_login_at ?? null,
    });
  },
);

// ── PUT /admin/users/:id/status ───────────────────────────────────────────────

router.put(
  '/users/:id/status',
  [
    param('id').isUUID().withMessage('מזהה משתמש לא תקין'),
    body('status').isIn(['active', 'suspended', 'banned']).withMessage('סטטוס לא תקין'),
  ],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    if (req.params.id === sub) {
      fail(res, 'cannot_change_own_status');
      return;
    }

    const profile = profileQueries.findById(req.params.id);
    if (!profile) { fail(res, 'not_found'); return; }

    profileQueries.updateStatus(req.params.id, req.body.status, new Date().toISOString());
    ok(res, { user_id: req.params.id, status: req.body.status }, 'הסטטוס עודכן בהצלחה');
  },
);

// ── DELETE /admin/users/:id ───────────────────────────────────────────────────

router.delete(
  '/users/:id',
  [param('id').isUUID().withMessage('מזהה משתמש לא תקין')],
  (req: Request, res: Response): void => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) { failValidation(res, errors.array()); return; }

    const { sub } = (req as AuthRequest).user;
    if (req.params.id === sub) {
      fail(res, 'cannot_delete_self');
      return;
    }

    const profile = profileQueries.findById(req.params.id);
    if (!profile) { fail(res, 'not_found'); return; }

    profileQueries.deleteUser(req.params.id);
    ok(res, {}, 'המשתמש נמחק בהצלחה');
  },
);

// ── Helper ────────────────────────────────────────────────────────────────────

function buildSummary(
  profile: ReturnType<typeof profileQueries.findById>,
  creds:   ReturnType<typeof authQueries.findById>,
) {
  return {
    user_id:       profile!.user_id,
    name:          profile!.name,
    city:          profile!.city,
    gender:        profile!.gender,
    photo_url:     profile!.photo_url,
    status:        profile!.status,
    registered_at: profile!.registered_at,
    username:      creds?.username ?? null,
    email:         creds?.email    ?? null,
    is_admin:      creds ? creds.is_admin === 1 : false,
  };
}

export default router;
