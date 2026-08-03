import { Router, Request, Response } from 'express';
import { body, validationResult } from 'express-validator';
import { authQueries } from '../database/queries/auth.queries';
import { UserModel } from '../models/UserModel';
import { SessionModel } from '../models/SessionModel';
import { authenticate, AuthRequest } from '../middleware/authenticate';

const router = Router();

// ── /auth/signup ──────────────────────────────────────────────────────────────
// Minimal registration: email + username + password only.
// Profile fields (name, city, etc.) are filled later in MyProfileScreen.

const signupRules = [
  body('username').trim().isLength({ min: 3, max: 30 }).matches(/^[a-zA-Z0-9_]+$/),
  body('email').isEmail().normalizeEmail(),
  body('password').isLength({ min: 8 }),
];

router.post('/signup', signupRules, async (req: Request, res: Response): Promise<void> => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    res.status(422).json({ errors: errors.array() });
    return;
  }

  const { username, email, password } = req.body;

  if (authQueries.findByUsername(username)) {
    res.status(409).json({ error: 'username_taken' });
    return;
  }
  if (authQueries.findByEmail(email)) {
    res.status(409).json({ error: 'email_taken' });
    return;
  }

  const userId = await UserModel.register({
    username, email, password,
    name: '', gender: '', date_of_birth: '', city: '', region: '',
  });
  const tokens = SessionModel.issue(userId, false);
  const creds  = authQueries.findById(userId)!;

  res.status(201).json({
    user_id:  userId,
    email:    creds.email,
    username: creds.username,
    is_admin: false,
    ...tokens,
  });
});

// ── /auth/login ───────────────────────────────────────────────────────────────
// Accepts { identifier, password } where identifier = username OR email.

const loginRules = [
  body('identifier').trim().notEmpty(),
  body('password').notEmpty(),
];

router.post('/login', loginRules, async (req: Request, res: Response): Promise<void> => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    res.status(422).json({ errors: errors.array() });
    return;
  }

  const { identifier, password } = req.body;
  const creds = identifier.includes('@')
    ? authQueries.findByEmail(identifier)
    : authQueries.findByUsername(identifier);

  if (!creds) {
    res.status(401).json({ error: 'invalid_credentials' });
    return;
  }

  const ok = await UserModel.verifyPassword(creds.password_hash, password);
  if (!ok) {
    res.status(401).json({ error: 'invalid_credentials' });
    return;
  }

  UserModel.touchLastLogin(creds.user_id);
  const tokens = SessionModel.issue(creds.user_id, creds.is_admin === 1);

  res.json({
    user_id:  creds.user_id,
    email:    creds.email,
    username: creds.username,
    is_admin: creds.is_admin === 1,
    ...tokens,
  });
});

// ── /auth/refresh ─────────────────────────────────────────────────────────────

router.post('/refresh', async (req: Request, res: Response): Promise<void> => {
  const { refresh_token } = req.body;
  if (!refresh_token) {
    res.status(400).json({ error: 'Missing refresh_token' });
    return;
  }

  try {
    const { userId, tokens } = await SessionModel.rotateRefresh(refresh_token);
    const creds = authQueries.findById(userId)!;
    res.json({
      user_id:  userId,
      email:    creds.email,
      username: creds.username,
      is_admin: creds.is_admin === 1,
      ...tokens,
    });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'unknown';
    if (msg === 'session_not_found' || msg === 'session_expired') {
      res.status(401).json({ error: msg });
    } else {
      res.status(401).json({ error: 'invalid_token' });
    }
  }
});

// ── /auth/logout ──────────────────────────────────────────────────────────────

router.post('/logout', (req: Request, res: Response): void => {
  const { refresh_token } = req.body;
  if (refresh_token) SessionModel.revoke(refresh_token);
  res.status(204).end();
});

// ── /auth/me ──────────────────────────────────────────────────────────────────
// Returns full user identity including email + username (used by useAutoLogin).

router.get('/me', authenticate, (req: Request, res: Response): void => {
  const { sub } = (req as AuthRequest).user;
  const creds = authQueries.findById(sub);
  if (!creds) { res.status(404).json({ error: 'not_found' }); return; }
  res.json({
    user_id:  creds.user_id,
    email:    creds.email,
    username: creds.username,
    is_admin: creds.is_admin === 1,
  });
});

export default router;
