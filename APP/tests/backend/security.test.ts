import path from 'path';
import { spawnSync } from 'child_process';
import request from 'supertest';
import jwt from 'jsonwebtoken';
import type { Application } from 'express';
import { buildApp, signupUser } from './helpers';

let app: Application;
const JWT_SECRET = 'test-secret-key-for-jest-only'; // matches env.ts

beforeAll(() =>
{
  app = buildApp();
});

// ── Known-bug regressions ─────────────────────────────────────────────────────
// These assert the CORRECT/secure behavior for issues flagged in improve.md.
// They currently fail against the real (buggy) code, so `.failing` keeps CI
// green today; the moment the underlying bug is fixed, Jest will report
// these as "unexpectedly passing" — that's the cue to drop `.failing` and
// promote them to normal assertions. Do not delete or skip them meanwhile.

describe('known-bug regressions (improve.md)', () =>
{
  it.failing(
    'TC-307/1303 a refresh token must not authenticate as a bearer access token',
    async () =>
    {
      const { refresh_token } = await signupUser(app, '_tokentypeconfusion');

      // verifyAccess() (src/models/SessionModel.ts) only checks the JWT
      // signature/expiry, never a `type` claim — so a refresh token
      // {sub, jti} currently passes `authenticate` on any non-admin route.
      const res = await request(app)
        .get('/users/me')
        .set('Authorization', `Bearer ${refresh_token}`);

      expect(res.status).toBe(401);
    },
  );

  it.failing(
    'TC-604/605 PUT /users/me with an empty body does not 500',
    async () =>
    {
      const { access_token } = await signupUser(app, '_emptyputbody');

      // profile.queries.ts's `update()` joins `Object.keys(fields)` into the
      // SQL SET clause with no empty-check, producing `SET , updated_at = ?`
      // — a SQL syntax error — when no recognized fields are sent.
      const res = await request(app)
        .put('/users/me')
        .set('Authorization', `Bearer ${access_token}`)
        .send({});

      expect(res.status).not.toBe(500);
      expect([200, 422]).toContain(res.status);
    },
  );

  it.failing(
    'TC-1211 sending a chat message to yourself returns 422, not a raw 500',
    async () =>
    {
      const { user_id, access_token } = await signupUser(app, '_selfchat');

      // chat.routes.ts never checks `sub !== peer_id` before calling
      // MessageModel.send — it relies on the DB's
      // CHECK (sender_id <> recipient_id), which throws synchronously.
      const res = await request(app)
        .post(`/chat/${user_id}`)
        .set('Authorization', `Bearer ${access_token}`)
        .send({ content: 'talking to myself' });

      expect(res.status).toBe(422);
    },
  );

  it.failing(
    'TC-1212 sending a chat message to a well-formed but nonexistent peer id returns 404, not 500',
    async () =>
    {
      const { access_token } = await signupUser(app, '_msgghost');
      const { makeUuid } = await import('./helpers');

      const res = await request(app)
        .post(`/chat/${makeUuid()}`)
        .set('Authorization', `Bearer ${access_token}`)
        .send({ content: 'is anyone there' });

      expect(res.status).toBe(404);
    },
  );

  it.failing(
    'TC-1308 a self-message sent over the WebSocket must not crash the server process',
    () =>
    {
      // wsServer.ts's ws.on('message', ...) handler has no try/catch around
      // MessageModel.send(), so the same CHECK-constraint throw as TC-1211
      // happens outside Express's request stack — nothing catches it, and
      // it becomes an uncaughtException that kills the whole process. Run
      // in a disposable child process: a healthy handler prints "ALIVE" and
      // exits 0; the real bug kills the process before that line runs.
      const fixture = path.join(__dirname, 'fixtures', 'wsSelfMessageCrash.ts');
      const tsconfig = path.join(__dirname, 'tsconfig.json');
      const result = spawnSync('npx', ['tsx', '--tsconfig', tsconfig, fixture], {
        cwd: path.join(__dirname, '../../backend'),
        shell: true,
        encoding: 'utf8',
        timeout: 20_000,
        env: {
          ...process.env,
          DB_PATH: ':memory:',
          JWT_SECRET: 'fixture-secret-for-crash-repro-only',
          JWT_ACCESS_TTL: '15m',
          JWT_REFRESH_TTL_DAYS: '30',
          UPLOADS_DIR: '/tmp/yahdav-crash-fixture-uploads',
          PORT: '0',
        },
      });

      expect(result.status).toBe(0);
      expect(result.stdout).toContain('ALIVE');
    },
    25_000,
  );
});

// ── Cross-cutting authorization sweep ─────────────────────────────────────────
// tests.md section 17

describe('every protected route rejects a missing/malformed token', () =>
{
  const routes: Array<{ method: 'get' | 'post' | 'put' | 'delete'; path: string }> = [
    { method: 'get', path: '/users/me' },
    { method: 'put', path: '/users/me' },
    { method: 'get', path: '/users/me/photos' },
    { method: 'get', path: '/users/discover' },
    { method: 'get', path: '/chat/conversations' },
    { method: 'get', path: '/admin/users' },
  ];

  it.each(routes)('TC-1701 $method $path returns 401 with no Authorization header', async ({ method, path: routePath }) =>
  {
    const res = await request(app)[method](routePath);

    expect(res.status).toBe(401);
  });

  it.each(routes)('TC-1701b $method $path returns 401 with a malformed bearer token', async ({ method, path: routePath }) =>
  {
    const res = await request(app)[method](routePath).set('Authorization', 'Bearer not.a.jwt');

    expect(res.status).toBe(401);
  });
});

describe('requireAdmin is enforced independently of authenticate', () =>
{
  it('TC-1702 a valid non-admin token passes authenticate but fails admin routes with 403', async () =>
  {
    const { access_token } = await signupUser(app, '_notadmin');

    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(403);
  });
});

describe('JWT tampering', () =>
{
  it('TC-1703 rejects a token signed with a different secret', async () =>
  {
    const forged = jwt.sign({ sub: 'fake-user-id', is_admin: true }, 'wrong-secret', { expiresIn: '15m' });

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${forged}`);

    expect(res.status).toBe(401);
  });

  it('TC-1703b rejects a token whose payload was altered after signing', async () =>
  {
    const { access_token } = await signupUser(app, '_tamperpayload');
    const [header, , signature] = access_token.split('.');
    const forgedPayload = Buffer.from(JSON.stringify({ sub: 'someone-else', is_admin: true })).toString('base64url');
    const tampered = `${header}.${forgedPayload}.${signature}`;

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${tampered}`);

    expect(res.status).toBe(401);
  });

  it('TC-1704 rejects an alg:none token even with a plausible payload', async () =>
  {
    const noneToken = jwt.sign({ sub: 'anyone', is_admin: true }, '', { algorithm: 'none' });

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${noneToken}`);

    expect(res.status).toBe(401);
  });

  it('an expired access token is rejected', async () =>
  {
    const { user_id } = await signupUser(app, '_expiredtoken');
    const expired = jwt.sign({ sub: user_id, is_admin: false }, JWT_SECRET, { expiresIn: -10 });

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${expired}`);

    expect(res.status).toBe(401);
  });
});

describe('no response ever leaks a password hash', () =>
{
  it('TC-1707 signup, login, /auth/me, and /admin/users/:id all omit password_hash', async () =>
  {
    const admin = await signupUser(app, '_nohashadmin');
    const { makeAdmin } = await import('./helpers');
    makeAdmin(admin.user_id);
    const login = await request(app)
      .post('/auth/login')
      .send({ identifier: 'user_nohashadmin@test.com', password: 'Password123!' });

    expect(login.body.password_hash).toBeUndefined();

    const me = await request(app).get('/auth/me').set('Authorization', `Bearer ${login.body.access_token}`);
    expect(me.body.password_hash).toBeUndefined();

    const target = await signupUser(app, '_nohashtarget');
    const detail = await request(app)
      .get(`/admin/users/${target.user_id}`)
      .set('Authorization', `Bearer ${login.body.access_token}`);
    expect(detail.body.password_hash).toBeUndefined();
  });
});

describe('static /uploads mount', () =>
{
  it('TC-1709 does not serve a directory listing', async () =>
  {
    const res = await request(app).get('/uploads/');

    expect(res.status).not.toBe(200);
  });
});

describe('malformed JSON body', () =>
{
  // The catch-all error handler (src/middleware/errorHandler.ts) maps every
  // error to a bare 500 regardless of type (improve.md Backend Medium #7),
  // so a body-parser SyntaxError — which Express's json() middleware itself
  // flags with `.status = 400` — currently gets flattened to 500 too.
  it.failing('TC-2639-adjacent returns a clean 4xx, not a 500, for unparseable JSON', async () =>
  {
    const res = await request(app)
      .post('/auth/login')
      .set('Content-Type', 'application/json')
      .send('{not valid json');

    expect(res.status).toBeGreaterThanOrEqual(400);
    expect(res.status).toBeLessThan(500);
  });
});
