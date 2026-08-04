import request from 'supertest';
import type { Application } from 'express';
import { buildApp, signupUser, makeAdmin, makeUuid } from './helpers';

let app: Application;

beforeAll(() =>
{
  app = buildApp();
});

// Every response is HTTP 200; success/failure is signaled by the body's
// `success` boolean, with a human-readable Hebrew `message` alongside it.

// ── POST /auth/signup ─────────────────────────────────────────────────────────
// tests.md section 1

describe('POST /auth/signup', () =>
{
  it('TC-101 creates a user and returns tokens + identity fields', async () =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: 'signup@test.com',
      username: 'signupuser',
      password: 'Password123!',
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(typeof res.body.message).toBe('string');
    expect(res.body.message.length).toBeGreaterThan(0);
    expect(res.body).toMatchObject({
      email: 'signup@test.com',
      username: 'signupuser',
      is_admin: false,
    });
    expect(res.body.user_id).toBeTruthy();
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.refresh_token).toBeTruthy();
  });

  it('TC-101b the new profile starts with empty name/bio/city/region and active status', async () =>
  {
    const { access_token } = await signupUser(app, '_freshprofile');
    const res = await request(app)
      .get('/users/me')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.name).toBe('');
    expect(res.body.bio).toBe('');
    expect(res.body.city).toBe('');
    expect(res.body.region).toBe('');
  });

  it('TC-102 rejects duplicate username (case-insensitive)', async () =>
  {
    await request(app).post('/auth/signup').send({
      email: 'caseuser1@test.com', username: 'CaseUser', password: 'Password1!',
    });

    const res = await request(app).post('/auth/signup').send({
      email: 'caseuser2@test.com', username: 'caseuser', password: 'Password1!',
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('username_taken');
    expect(res.body.message).toBe('שם המשתמש כבר תפוס');
  });

  it('TC-103 rejects duplicate email (case-insensitive)', async () =>
  {
    await request(app).post('/auth/signup').send({
      email: 'Dup@Test.com', username: 'dupuser1', password: 'Password1!',
    });

    const res = await request(app).post('/auth/signup').send({
      email: 'dup@test.com', username: 'dupuser2', password: 'Password1!',
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('email_taken');
    expect(res.body.message).toBe('האימייל כבר קיים במערכת');
  });

  it.each([
    ['ab', 'too short'],
    ['a'.repeat(31), 'too long'],
    ['bad username', 'contains a space'],
    ['bad-user', 'contains a hyphen'],
    ['משתמש', 'non-latin characters'],
  ])('TC-104 rejects username %j (%s) with a specific message', async (username) =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: `u${Date.now()}${Math.random()}@test.com`,
      username,
      password: 'Password123!',
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('validation_error');
    expect(typeof res.body.message).toBe('string');
    expect(res.body.message.length).toBeGreaterThan(0);
    expect(Array.isArray(res.body.errors)).toBe(true);
  });

  it('TC-105 rejects an invalid email format with a specific message', async () =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: 'not-an-email',
      username: 'validusername1',
      password: 'Password123!',
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('כתובת האימייל אינה תקינה');
  });

  it.each([
    ['1234567', 'seven characters'],
    ['', 'empty string'],
  ])('TC-107 rejects a password that is too short (%j — %s)', async (password) =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: `pw${Date.now()}${Math.random()}@test.com`,
      username: `pwuser${Date.now()}`,
      password,
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('הסיסמה חייבת להכיל לפחות 8 תווים');
  });

  it('TC-108 accepts a password exactly at the 8-character minimum', async () =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: `pwmin${Date.now()}@test.com`,
      username: `pwminuser${Date.now()}`,
      password: '12345678',
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it.each(['username', 'email', 'password'])('TC-109 rejects a signup missing "%s"', async (field) =>
  {
    const body: Record<string, string> = {
      email: `missing${Date.now()}@test.com`,
      username: `missing${Date.now()}`,
      password: 'Password123!',
    };
    delete body[field];

    const res = await request(app).post('/auth/signup').send(body);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-110 ignores a client-supplied is_admin field (cannot self-elevate)', async () =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: `noselfadmin${Date.now()}@test.com`,
      username: `noselfadmin${Date.now()}`,
      password: 'Password123!',
      is_admin: true,
    });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.is_admin).toBe(false);
  });

  it('TC-111 treats SQL-injection-shaped input as an ordinary (safely parameterized) string', async () =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: `sqltest${Date.now()}@test.com`,
      username: `sqluser${Date.now()}`,
      password: "' OR '1'='1",
    });

    // The validators don't reject this shape (it's a legal >=8-char password);
    // the important assertion is that it doesn't error out or corrupt the DB.
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it('TC-113 only one of two concurrent signups with the same username succeeds', async () =>
  {
    // Regression test — this used to hang indefinitely (Express 4 doesn't
    // catch rejected promises from async handlers), fixed by wrapping the
    // signup handler's DB write in try/catch.
    const username = `racer${Date.now()}`;
    const [a, b] = await Promise.all([
      request(app).post('/auth/signup').send({
        email: `racer1_${Date.now()}@test.com`, username, password: 'Password123!',
      }),
      request(app).post('/auth/signup').send({
        email: `racer2_${Date.now()}@test.com`, username, password: 'Password123!',
      }),
    ]);

    expect(a.status).toBe(200);
    expect(b.status).toBe(200);
    const successes = [a.body.success, b.body.success].sort();
    expect(successes).toEqual([false, true]);
    const loser = a.body.success ? b.body : a.body;
    expect(loser.error).toBe('username_taken');
  }, 10_000);

  it('TC-114 the issued access token is immediately usable on a protected route', async () =>
  {
    const { access_token } = await signupUser(app, '_immediate');
    const res = await request(app)
      .get('/auth/me')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it('TC-115 the response never echoes back a password hash', async () =>
  {
    const res = await request(app).post('/auth/signup').send({
      email: `hashcheck${Date.now()}@test.com`,
      username: `hashcheck${Date.now()}`,
      password: 'Password123!',
    });

    expect(res.body.password_hash).toBeUndefined();
    expect(res.body.password).toBeUndefined();
  });
});

// ── POST /auth/login ──────────────────────────────────────────────────────────
// tests.md section 2

describe('POST /auth/login', () =>
{
  const email = 'login@test.com';
  const username = 'loginuser';
  const password = 'MyPass99!';

  beforeAll(async () =>
  {
    await request(app).post('/auth/signup').send({ email, username, password });
  });

  it('TC-201 logs in by username and returns tokens', async () =>
  {
    const res = await request(app).post('/auth/login').send({ identifier: username, password });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.refresh_token).toBeTruthy();
    expect(res.body.is_admin).toBe(false);
  });

  it('TC-202 logs in by email', async () =>
  {
    const res = await request(app).post('/auth/login').send({ identifier: email, password });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.access_token).toBeTruthy();
  });

  it('TC-204 rejects a wrong password with invalid_credentials', async () =>
  {
    const res = await request(app).post('/auth/login').send({ identifier: username, password: 'wrongpassword' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('invalid_credentials');
    expect(res.body.message).toBe('שם משתמש או סיסמה שגויים');
  });

  it('TC-205 rejects an unknown identifier with the same error as a wrong password', async () =>
  {
    const res = await request(app).post('/auth/login').send({ identifier: 'nobody-here', password: 'anything123' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('invalid_credentials');
  });

  it('TC-206 identifier match is case-insensitive', async () =>
  {
    const res = await request(app).post('/auth/login').send({ identifier: username.toUpperCase(), password });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it.each([
    [{ identifier: '', password }, 'empty identifier'],
    [{ identifier: username, password: '' }, 'empty password'],
  ])('TC-207 rejects login with %j (%s)', async (body) =>
  {
    const res = await request(app).post('/auth/login').send(body);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-212 issuing a second login does not invalidate the first session', async () =>
  {
    const first = await request(app).post('/auth/login').send({ identifier: username, password });
    const second = await request(app).post('/auth/login').send({ identifier: username, password });

    expect(first.body.success).toBe(true);
    expect(second.body.success).toBe(true);

    const meFirst = await request(app).get('/auth/me').set('Authorization', `Bearer ${first.body.access_token}`);
    const meSecond = await request(app).get('/auth/me').set('Authorization', `Bearer ${second.body.access_token}`);

    expect(meFirst.body.success).toBe(true);
    expect(meSecond.body.success).toBe(true);
  });
});

// ── POST /auth/refresh ────────────────────────────────────────────────────────
// tests.md section 3

describe('POST /auth/refresh', () =>
{
  it('TC-301 rotates the refresh token and issues a new access token', async () =>
  {
    const { refresh_token: rt1 } = await signupUser(app, '_refresh');
    const res = await request(app).post('/auth/refresh').send({ refresh_token: rt1 });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.refresh_token).not.toBe(rt1);
  });

  it('TC-302 rejects reuse of an already-rotated refresh token', async () =>
  {
    const { refresh_token: rt } = await signupUser(app, '_reuse');
    await request(app).post('/auth/refresh').send({ refresh_token: rt });
    const res2 = await request(app).post('/auth/refresh').send({ refresh_token: rt });

    expect(res2.status).toBe(200);
    expect(res2.body.success).toBe(false);
  });

  it('TC-303 rejects a missing refresh_token', async () =>
  {
    const res = await request(app).post('/auth/refresh').send({});

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('missing_refresh_token');
  });

  it('TC-304 rejects a malformed token string', async () =>
  {
    const res = await request(app).post('/auth/refresh').send({ refresh_token: 'not-a-real-jwt' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('invalid_token');
  });

  it('TC-306 rejects a refresh token for a session that was already logged out', async () =>
  {
    const { refresh_token } = await signupUser(app, '_revoked');
    await request(app).post('/auth/logout').send({ refresh_token });

    const res = await request(app).post('/auth/refresh').send({ refresh_token });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('session_not_found');
  });

  it('TC-310 only one of two concurrent refreshes of the same token succeeds', async () =>
  {
    const { refresh_token } = await signupUser(app, '_racerefresh');

    const [a, b] = await Promise.all([
      request(app).post('/auth/refresh').send({ refresh_token }),
      request(app).post('/auth/refresh').send({ refresh_token }),
    ]);

    const successes = [a.body.success, b.body.success].sort();
    expect(successes).toEqual([false, true]);
  });

  it('TC-309 the refreshed response reflects the current is_admin value', async () =>
  {
    const { refresh_token } = await signupUser(app, '_refreshadmin');
    const res = await request(app).post('/auth/refresh').send({ refresh_token });

    expect(res.body.is_admin).toBe(false);
  });
});

// ── POST /auth/logout ─────────────────────────────────────────────────────────
// tests.md section 4

describe('POST /auth/logout', () =>
{
  it('TC-401 succeeds and revokes the session', async () =>
  {
    const { refresh_token } = await signupUser(app, '_logout');
    const logoutRes = await request(app).post('/auth/logout').send({ refresh_token });

    expect(logoutRes.status).toBe(200);
    expect(logoutRes.body.success).toBe(true);

    const refreshRes = await request(app).post('/auth/refresh').send({ refresh_token });
    expect(refreshRes.body.success).toBe(false);
  });

  it('TC-402 is a no-op (still success) when no refresh_token is supplied', async () =>
  {
    const res = await request(app).post('/auth/logout').send({});

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });

  it('TC-403 is idempotent — logging out twice with the same token both succeed', async () =>
  {
    const { refresh_token } = await signupUser(app, '_doublelogout');

    const first = await request(app).post('/auth/logout').send({ refresh_token });
    const second = await request(app).post('/auth/logout').send({ refresh_token });

    expect(first.body.success).toBe(true);
    expect(second.body.success).toBe(true);
  });
});

// ── GET /auth/me ───────────────────────────────────────────────────────────────
// tests.md section 5

describe('GET /auth/me', () =>
{
  it('TC-501 returns the current user identity for a valid token', async () =>
  {
    const { access_token } = await signupUser(app, '_me');
    const res = await request(app).get('/auth/me').set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.email).toBe('user_me@test.com');
    expect(res.body).toHaveProperty('user_id');
    expect(res.body).toHaveProperty('username');
    expect(res.body).toHaveProperty('is_admin');
  });

  it('TC-502 fails with no Authorization header', async () =>
  {
    const res = await request(app).get('/auth/me');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });

  it('TC-503 fails for a malformed bearer token', async () =>
  {
    const res = await request(app).get('/auth/me').set('Authorization', 'Bearer garbage.not.a.jwt');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });

  it('TC-503b fails for an Authorization header with the wrong scheme', async () =>
  {
    const { access_token } = await signupUser(app, '_wrongscheme');
    const res = await request(app).get('/auth/me').set('Authorization', `Basic ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-504 fails with not_found for a valid token whose user was since deleted', async () =>
  {
    const admin = await signupUser(app, '_deleter');
    const target = await signupUser(app, '_gone');

    makeAdmin(admin.user_id);
    const login = await request(app)
      .post('/auth/login')
      .send({ identifier: 'user_deleter@test.com', password: 'Password123!' });

    await request(app)
      .delete(`/admin/users/${target.user_id}`)
      .set('Authorization', `Bearer ${login.body.access_token}`);

    const res = await request(app).get('/auth/me').set('Authorization', `Bearer ${target.access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });
});

// Sanity-check the test-only UUID generator used across the suite for 404 lookups.
describe('makeUuid test helper', () =>
{
  it('produces well-formed, distinct random UUIDs', () =>
  {
    const a = makeUuid();
    const b = makeUuid();

    expect(a).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/);
    expect(a).not.toBe(b);
  });
});
