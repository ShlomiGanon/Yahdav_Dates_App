import { Router, Request, Response } from 'express';
import { body, validationResult } from 'express-validator';
import { authQueries } from '../database/queries/auth.queries';
import { UserModel } from '../models/UserModel';
import { SessionModel } from '../models/SessionModel';
import { authenticate, AuthRequest } from '../middleware/authenticate';
import { ok, fail, failValidation } from '../utils/responses';

const router = Router();

// ── /auth/signup ──────────────────────────────────────────────────────────────
// Minimal registration: email + username + password only.
// Profile fields (name, city, etc.) are filled later in MyProfileScreen.

const signupRules = [
  body('username')
    .trim()
    .isLength({ min: 3, max: 30 })
    .withMessage('שם המשתמש חייב להכיל בין 3 ל-30 תווים')
    .bail()
    .matches(/^[a-zA-Z0-9_]+$/)
    .withMessage('שם המשתמש יכול להכיל רק אותיות באנגלית, ספרות וקו תחתון'),
  body('email')
    .isEmail()
    .withMessage('כתובת האימייל אינה תקינה')
    .normalizeEmail(),
  body('password')
    .isLength({ min: 8 })
    .withMessage('הסיסמה חייבת להכיל לפחות 8 תווים'),
];

router.post('/signup', signupRules, async (req: Request, res: Response): Promise<void> => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    failValidation(res, errors.array());
    return;
  }

  const { username, email, password } = req.body;

  if (authQueries.findByUsername(username)) {
    fail(res, 'username_taken');
    return;
  }
  if (authQueries.findByEmail(email)) {
    fail(res, 'email_taken');
    return;
  }

  // The findByUsername/findByEmail checks above are a pre-check, not a
  // lock — two concurrent signups for the same username can both pass them
  // before either INSERT commits. Express 4 doesn't catch rejected promises
  // from async handlers, so without this try/catch the loser's UNIQUE
  // constraint violation becomes an unhandled rejection and the request
  // just hangs forever instead of getting a clean response.
  try {
    const userId = await UserModel.register({
      username, email, password,
      name: '', gender: '', date_of_birth: '', city: '', region: '',
    });
    const tokens = SessionModel.issue(userId, false);
    const creds  = authQueries.findById(userId)!;

    ok(res, {
      user_id:  userId,
      email:    creds.email,
      username: creds.username,
      is_admin: false,
      ...tokens,
    }, 'ההרשמה בוצעה בהצלחה');
  } catch {
    // Re-check rather than parse the DB driver's error text (fragile) —
    // whichever unique constraint actually lost the race is now visible.
    if (authQueries.findByUsername(username)) { fail(res, 'username_taken'); return; }
    if (authQueries.findByEmail(email)) { fail(res, 'email_taken'); return; }
    fail(res, 'internal_error');
  }
});

// ── /auth/login ───────────────────────────────────────────────────────────────
// Accepts { identifier, password } where identifier = username OR email.

const loginRules = [
  body('identifier').trim().notEmpty().withMessage('יש להזין שם משתמש או אימייל'),
  body('password').notEmpty().withMessage('יש להזין סיסמה'),
];

router.post('/login', loginRules, async (req: Request, res: Response): Promise<void> => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    failValidation(res, errors.array());
    return;
  }

  const { identifier, password } = req.body;
  const creds = identifier.includes('@')
    ? authQueries.findByEmail(identifier)
    : authQueries.findByUsername(identifier);

  if (!creds) {
    fail(res, 'invalid_credentials');
    return;
  }

  const passwordOk = await UserModel.verifyPassword(creds.password_hash, password);
  if (!passwordOk) {
    fail(res, 'invalid_credentials');
    return;
  }

  UserModel.touchLastLogin(creds.user_id);
  const tokens = SessionModel.issue(creds.user_id, creds.is_admin === 1);

  ok(res, {
    user_id:  creds.user_id,
    email:    creds.email,
    username: creds.username,
    is_admin: creds.is_admin === 1,
    ...tokens,
  }, 'התחברת בהצלחה');
});

// ── /auth/refresh ─────────────────────────────────────────────────────────────

router.post('/refresh', async (req: Request, res: Response): Promise<void> => {
  const { refresh_token } = req.body;
  if (!refresh_token) {
    fail(res, 'missing_refresh_token');
    return;
  }

  try {
    const { userId, tokens } = await SessionModel.rotateRefresh(refresh_token);
    const creds = authQueries.findById(userId)!;
    ok(res, {
      user_id:  userId,
      email:    creds.email,
      username: creds.username,
      is_admin: creds.is_admin === 1,
      ...tokens,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'unknown';
    if (msg === 'session_not_found' || msg === 'session_expired') {
      fail(res, msg);
    } else {
      fail(res, 'invalid_token');
    }
  }
});

// ── /auth/logout ──────────────────────────────────────────────────────────────

router.post('/logout', (req: Request, res: Response): void => {
  const { refresh_token } = req.body;
  if (refresh_token) SessionModel.revoke(refresh_token);
  ok(res, {}, 'התנתקת בהצלחה');
});

// ── /auth/me ──────────────────────────────────────────────────────────────────
// Returns full user identity including email + username (used by useAutoLogin).

router.get('/me', authenticate, (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  const creds = authQueries.findById(sub);
  if (!creds) { fail(res, 'not_found'); return; }
  ok(res, {
    user_id:  creds.user_id,
    email:    creds.email,
    username: creds.username,
    is_admin: creds.is_admin === 1,
  });
});

export default router;
