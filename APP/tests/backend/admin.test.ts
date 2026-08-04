import request from 'supertest';
import { buildApp, signupUser, makeAdmin } from './helpers';
import type { Application } from 'express';

let app: Application;
let adminToken: string;
let adminId: string;
let targetId: string;

beforeAll(async () => {
  app = buildApp();

  // Create admin and elevate
  const admin = await signupUser(app, '_admin');
  adminId = admin.user_id;
  makeAdmin(adminId);
  // Re-login to get token with is_admin=true in JWT
  const login = await request(app).post('/auth/login').send({
    identifier: 'user_admin@test.com',
    password:   'Password123!',
  });
  adminToken = login.body.access_token;

  // Create a regular target user
  const target = await signupUser(app, '_target');
  targetId = target.user_id;
});

describe('GET /admin/users', () => {
  it('returns user list with total', async () => {
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`);
    expect(res.status).toBe(200);
    expect(res.body).toHaveProperty('total');
    expect(Array.isArray(res.body.users)).toBe(true);
    expect(res.body.total).toBeGreaterThanOrEqual(2);
  });

  it('supports search param', async () => {
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${adminToken}`)
      .query({ search: '_target' });
    expect(res.status).toBe(200);
    expect(res.body.users.length).toBeGreaterThanOrEqual(1);
  });

  it('returns 403 for non-admin', async () => {
    const { access_token } = await signupUser(app, '_nonadmin');
    const res = await request(app)
      .get('/admin/users')
      .set('Authorization', `Bearer ${access_token}`);
    expect(res.status).toBe(403);
  });

  it('returns 401 without token', async () => {
    const res = await request(app).get('/admin/users');
    expect(res.status).toBe(401);
  });
});

describe('GET /admin/users/:id', () => {
  it('returns full user detail', async () => {
    const res = await request(app)
      .get(`/admin/users/${targetId}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(res.status).toBe(200);
    expect(res.body.user_id).toBe(targetId);
    expect(res.body).toHaveProperty('email');
    expect(res.body).toHaveProperty('username');
    expect(res.body).not.toHaveProperty('password_hash');
  });

  it('returns 404 for unknown id', async () => {
    const res = await request(app)
      .get('/admin/users/00000000-0000-0000-0000-000000000000')
      .set('Authorization', `Bearer ${adminToken}`);
    expect(res.status).toBe(404);
  });
});

describe('PUT /admin/users/:id/status', () => {
  it('changes user status', async () => {
    const res = await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'suspended' });
    expect(res.status).toBe(200);
    expect(res.body.status).toBe('suspended');

    // Restore
    await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'active' });
  });

  it('rejects invalid status', async () => {
    const res = await request(app)
      .put(`/admin/users/${targetId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'deleted' });
    expect(res.status).toBe(422);
  });

  it('prevents admin from changing own status', async () => {
    const res = await request(app)
      .put(`/admin/users/${adminId}/status`)
      .set('Authorization', `Bearer ${adminToken}`)
      .send({ status: 'suspended' });
    expect(res.status).toBe(422);
  });
});

describe('DELETE /admin/users/:id', () => {
  it('deletes a user', async () => {
    const { user_id: deleteMe } = await signupUser(app, '_deleteme');
    const res = await request(app)
      .delete(`/admin/users/${deleteMe}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(res.status).toBe(204);

    // Confirm gone
    const check = await request(app)
      .get(`/admin/users/${deleteMe}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(check.status).toBe(404);
  });

  it('prevents admin from deleting self', async () => {
    const res = await request(app)
      .delete(`/admin/users/${adminId}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(res.status).toBe(422);
  });
});
