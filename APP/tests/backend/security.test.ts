import path from 'path';
import { spawnSync } from 'child_process';
import request from 'supertest';
import jwt from 'jsonwebtoken';
import type { Application } from 'express';
import { buildApp, signupUser, makeAdmin, makeUuid } from './helpers';

let app: Application;
const JWT_SECRET = 'test-secret-key-for-jest-only'; // matches env.ts

beforeAll(() =>
{
  app = buildApp();
});

// Every response is HTTP 200; success/failure is signaled by the body's
// `success` boolean.

// ── Known-bug regressions (improve.md) ────────────────────────────────────────
// TC-604/605 (empty PUT body), TC-1211/1212 (self-message / nonexistent-peer
// via REST), and TC-1308's WS-level error-frame behavior are now genuinely
// fixed and live as normal assertions in profile.test.ts / chat.test.ts —
// not duplicated here. What's left below are the regressions that are
// either still real bugs, or worth a standalone process-level guard.

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

      expect(res.body.success).toBe(false);
      expect(res.body.error).toBe('unauthorized');
    },
  );

  it(
    'TC-1308 a self-message sent over the WebSocket does not crash the server process',
    () =>
    {
      // Standalone regression guard, run in a disposable child process so a
      // real crash (if the bug ever comes back) can't take down this Jest
      // worker. wsServer.ts now validates self-messages before calling
      // MessageModel.send() and returns a typed error frame instead of
      // letting a CHECK-constraint violation escape as an uncaughtException
      // — the fixture should reliably survive and print "ALIVE".
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

describe('every protected route fails with unauthorized on a missing/malformed token', () =>
{
  const routes: Array<{ method: 'get' | 'post' | 'put' | 'delete'; path: string }> = [
    { method: 'get', path: '/users/me' },
    { method: 'put', path: '/users/me' },
    { method: 'get', path: '/users/me/photos' },
    { method: 'get', path: '/users/discover' },
    { method: 'get', path: '/chat/conversations' },
    { method: 'get', path: '/admin/users' },
  ];

  it.each(routes)('TC-1701 $method $path fails with no Authorization header', async ({ method, path: routePath }) =>
  {
    const res = await request(app)[method](routePath);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });

  it.each(routes)('TC-1701b $method $path fails with a malformed bearer token', async ({ method, path: routePath }) =>
  {
    const res = await request(app)[method](routePath).set('Authorization', 'Bearer not.a.jwt');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});

describe('requireAdmin is enforced independently of authenticate', () =>
{
  it('TC-1702 a valid non-admin token passes authenticate but fails admin routes with forbidden', async () =>
  {
    const { access_token } = await signupUser(app, '_notadmin');

    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('forbidden');
  });
});

describe('JWT tampering', () =>
{
  it('TC-1703 rejects a token signed with a different secret', async () =>
  {
    const forged = jwt.sign({ sub: 'fake-user-id', is_admin: true }, 'wrong-secret', { expiresIn: '15m' });

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${forged}`);

    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });

  it('TC-1703b rejects a token whose payload was altered after signing', async () =>
  {
    const { access_token } = await signupUser(app, '_tamperpayload');
    const [header, , signature] = access_token.split('.');
    const forgedPayload = Buffer.from(JSON.stringify({ sub: 'someone-else', is_admin: true })).toString('base64url');
    const tampered = `${header}.${forgedPayload}.${signature}`;

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${tampered}`);

    expect(res.body.success).toBe(false);
  });

  it('TC-1704 rejects an alg:none token even with a plausible payload', async () =>
  {
    const noneToken = jwt.sign({ sub: 'anyone', is_admin: true }, '', { algorithm: 'none' });

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${noneToken}`);

    expect(res.body.success).toBe(false);
  });

  it('an expired access token is rejected', async () =>
  {
    const { user_id } = await signupUser(app, '_expiredtoken');
    const expired = jwt.sign({ sub: user_id, is_admin: false }, JWT_SECRET, { expiresIn: -10 });

    const res = await request(app).get('/users/me').set('Authorization', `Bearer ${expired}`);

    expect(res.body.success).toBe(false);
  });
});

describe('no response ever leaks a password hash', () =>
{
  it('TC-1707 signup, login, /auth/me, and /admin/users/:id all omit password_hash', async () =>
  {
    const admin = await signupUser(app, '_nohashadmin');
    makeAdmin(admin.user_id);
    const login = await request(app)
      .post('/auth/login')
      .send({ identifier: 'user_nohashadmin@test.com', password: 'Password123!' });

    expect(login.body.success).toBe(true);
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
    // Unaffected by the always-200 API contract — this is a raw
    // express.static mount, not one of our JSON routes.
    const res = await request(app).get('/uploads/');

    expect(res.status).not.toBe(200);
  });
});

describe('malformed JSON body', () =>
{
  it('TC-2639-adjacent fails cleanly with success:false, not a crash, for unparseable JSON', async () =>
  {
    const res = await request(app)
      .post('/auth/login')
      .set('Content-Type', 'application/json')
      .send('{not valid json');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('internal_error');
  });
});

describe('IDOR / not_found consistency', () =>
{
  it('a well-formed but nonexistent user id fails with not_found on the peer-profile route', async () =>
  {
    const { access_token } = await signupUser(app, '_notfoundcheck');
    const res = await request(app)
      .get(`/users/${makeUuid()}`)
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });
});
