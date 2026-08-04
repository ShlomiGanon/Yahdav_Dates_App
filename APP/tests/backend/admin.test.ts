import request from 'supertest';
import type { Application } from 'express';
import { buildApp, signupUser, makeAdmin, makeUuid } from './helpers';

let app: Application;
let adminToken: string;
let adminId: string;
let targetId: string;

beforeAll(async () =>
{
  app = buildApp();

  const admin = await signupUser(app, '_admin');
  adminId = admin.user_id;
  makeAdmin(adminId);
  const login = await request(app).post('/auth/login').send({
    identifier: 'user_admin@test.com',
    password: 'Password123!',
  });
  adminToken = login.body.access_token;

  const target = await signupUser(app, '_target');
  targetId = target.user_id;
});

// Every response is HTTP 200; success/failure is signaled by the body's
// `success` boolean.

// ── GET /admin/users ───────────────────────────────────────────────────────────
// tests.md section 14

describe('GET /admin/users', () =>
{
  it('TC-1401 returns a paginated user list with a total count', async () =>
  {
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body).toHaveProperty('total');
    expect(Array.isArray(res.body.users)).toBe(true);
    expect(res.body.total).toBeGreaterThanOrEqual(2);
  });

  it('TC-1402 fails with forbidden for an authenticated non-admin', async () =>
  {
    const { access_token } = await signupUser(app, '_nonadmin');
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('forbidden');
  });

  it('TC-1403 fails with unauthorized with no token', async () =>
  {
    const res = await request(app).get('/admin/users');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });

  it('TC-1404 search matches a partial, case-insensitive substring of name/city/username/email', async () =>
  {
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`)
      .query({ search: '_TARGET' });

    expect(res.status).toBe(200);
    expect(res.body.users.some((u: { user_id: string }) => u.user_id === targetId)).toBe(true);
  });

  it('TC-1405 search with no matches returns an empty list and total 0', async () =>
  {
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`)
      .query({ search: 'no-such-user-anywhere-xyz' });

    expect(res.status).toBe(200);
    expect(res.body.total).toBe(0);
    expect(res.body.users).toEqual([]);
  });

  it('TC-1406 pagination is applied after filtering, and totals reflect the filtered count', async () =>
  {
    // Keep this short — it becomes part of a username capped at 30 chars
    // (`testuser` + `_` + suffix + index already eats 10 of those).
    const suffix = `pg${Date.now().toString(36)}`;
    for (let i = 0; i < 3; i++)
    {
      await signupUser(app, `_${suffix}${i}`);
    }

    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`)
      .query({ search: suffix, limit: 2, offset: 0 });

    expect(res.body.total).toBe(3);
    expect(res.body.users.length).toBe(2);
  });

  it.each([[0, false], [201, false], [200, true], [1, true]])(
    'TC-1408 limit=%d succeeds=%s',
    async (limit, expectedSuccess) =>
    {
      const res = await request(app)
        .get('/admin/users')
        .set('Authorization', `Bearer ${adminToken}`)
        .query({ limit });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(expectedSuccess);
    },
  );

  it('TC-1408b rejects a negative offset', async () =>
  {
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`)
      .query({ offset: -1 });

    expect(res.body.success).toBe(false);
  });
});

// ── GET /admin/users/:id ────────────────────────────────────────────────────────

describe('GET /admin/users/:id', () =>
{
  it('TC-1409 returns full user detail including email/username, never a password hash', async () =>
  {
    const res = await request(app)
      .get(`/admin/users/${targetId}`)
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.user_id).toBe(targetId);
    expect(res.body).toHaveProperty('email');
    expect(res.body).toHaveProperty('username');
    expect(res.body).not.toHaveProperty('password_hash');
  });

  it('TC-1410 fails with not_found for an unknown id', async () =>
  {
    const res = await request(app)
      .get(`/admin/users/${makeUuid()}`)
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });

  it('TC-1411 fails for a non-UUID id', async () =>
  {
    const res = await request(app)
      .get('/admin/users/not-a-uuid')
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });
});

// ── PUT /admin/users/:id/status ─────────────────────────────────────────────────
// tests.md section 15

describe('PUT /admin/users/:id/status', () =>
{
  it('TC-1501/1502 transitions through suspended, banned, and back to active', async () =>
  {
    const suspend = await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'suspended' });
    expect(suspend.body.success).toBe(true);
    expect(suspend.body.status).toBe('suspended');

    const ban = await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'banned' });
    expect(ban.body.success).toBe(true);
    expect(ban.body.status).toBe('banned');

    const restore = await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'active' });
    expect(restore.body.success).toBe(true);
    expect(restore.body.status).toBe('active');
  });

  it('TC-1503 rejects a status value outside the allowed set', async () =>
  {
    const res = await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'deleted' });

    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('סטטוס לא תקין');
  });

  it('TC-1504 an admin cannot change their own status', async () =>
  {
    const res = await request(app)
      .put(`/admin/users/${adminId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'suspended' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('cannot_change_own_status');
  });

  it('TC-1505 fails with not_found for a status change on an unknown user', async () =>
  {
    const res = await request(app)
      .put(`/admin/users/${makeUuid()}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'active' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });

  it('a suspended user disappears from every other user\'s discover feed', async () =>
  {
    const suspendMe = await signupUser(app, '_soontosuspend');
    const viewer = await signupUser(app, '_suspendviewer');

    await request(app)
      .put(`/admin/users/${suspendMe.user_id}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'suspended' });

    const discover = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${viewer.access_token}`)
      .query({ limit: 100 });

    expect(discover.body.candidates.some((u: { user_id: string }) => u.user_id === suspendMe.user_id)).toBe(false);

    // restore for hygiene, in case other tests in this file rely on total counts
    await request(app)
      .put(`/admin/users/${suspendMe.user_id}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'active' });
  });
});

// ── DELETE /admin/users/:id ──────────────────────────────────────────────────────

describe('DELETE /admin/users/:id', () =>
{
  it('TC-1506 deletes a user; a subsequent lookup fails with not_found', async () =>
  {
    const { user_id: deleteMe } = await signupUser(app, '_deleteme');
    const res = await request(app)
      .delete(`/admin/users/${deleteMe}`)
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);

    const check = await request(app)
      .get(`/admin/users/${deleteMe}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(check.body.success).toBe(false);
    expect(check.body.error).toBe('not_found');
  });

  it('TC-1507 an admin cannot delete themselves', async () =>
  {
    const res = await request(app)
      .delete(`/admin/users/${adminId}`)
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('cannot_delete_self');
  });

  it('TC-1508 fails with not_found for deleting an unknown user', async () =>
  {
    const res = await request(app)
      .delete(`/admin/users/${makeUuid()}`)
      .set('Authorization', `Bearer ${adminToken}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });

  it('TC-1623 a deleted user\'s push token no longer receives push-eligible offline delivery attempts', async () =>
  {
    // Not directly observable via push service (no real Expo call in tests), but we can
    // confirm the profile row — and therefore its push token — is actually gone.
    const { user_id, access_token } = await signupUser(app, '_deletewithpush');
    await request(app)
      .post('/users/me/push-token')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ token: 'ExponentPushToken[xxxx]' });

    await request(app)
      .delete(`/admin/users/${user_id}`)
      .set('Authorization', `Bearer ${adminToken}`);

    const check = await request(app)
      .get(`/admin/users/${user_id}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(check.body.success).toBe(false);
    expect(check.body.error).toBe('not_found');
  });
});
