import request from 'supertest';
import { buildApp, signupUser } from './helpers';
import type { Application } from 'express';

let app: Application;

beforeAll(() => { app = buildApp(); });

describe('GET /users/me', () => {
  it('returns my profile', async () => {
    const { user_id, access_token } = await signupUser(app, '_getme');
    const res = await request(app)
      .get('/users/me')
      .set('Authorization', `Bearer ${access_token}`);
    expect(res.status).toBe(200);
    expect(res.body.user_id).toBe(user_id);
    expect(res.body).toHaveProperty('name');
    expect(res.body).toHaveProperty('bio');
  });
});

describe('PUT /users/me', () => {
  it('updates profile fields', async () => {
    const { access_token } = await signupUser(app, '_putme');
    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ name: 'ישראל ישראלי', city: 'תל אביב', gender: 'male' });
    expect(res.status).toBe(200);
    expect(res.body.name).toBe('ישראל ישראלי');
    expect(res.body.city).toBe('תל אביב');
  });

  it('returns 422 for invalid gender', async () => {
    const { access_token } = await signupUser(app, '_badgender');
    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ gender: 'robot' });
    expect(res.status).toBe(422);
  });
});

describe('GET /users/discover', () => {
  it('returns active candidates (excludes self)', async () => {
    const { access_token } = await signupUser(app, '_disc1');
    await signupUser(app, '_disc2');
    await signupUser(app, '_disc3');

    const res = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ page: 1, limit: 10 });
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    // Should include _disc2 and _disc3 but not _disc1 (self)
    expect(res.body.every((u: { user_id: string }) => u.user_id !== res.body.user_id)).toBe(true);
  });
});

describe('GET /users/:id', () => {
  it('returns peer profile', async () => {
    const { user_id: peerId } = await signupUser(app, '_peer_target');
    const { access_token } = await signupUser(app, '_peer_viewer');
    const res = await request(app)
      .get(`/users/${peerId}`)
      .set('Authorization', `Bearer ${access_token}`);
    expect(res.status).toBe(200);
    expect(res.body.user_id).toBe(peerId);
    expect(res.body).not.toHaveProperty('email');
  });

  it('returns 404 for unknown user', async () => {
    const { access_token } = await signupUser(app, '_peer404');
    const res = await request(app)
      .get('/users/00000000-0000-0000-0000-000000000000')
      .set('Authorization', `Bearer ${access_token}`);
    expect(res.status).toBe(404);
  });
});

describe('POST /users/:id/block', () => {
  it('blocks a user and hides them from discover', async () => {
    const { user_id: blocked, access_token: blockedToken } = await signupUser(app, '_blk_target');
    const { access_token } = await signupUser(app, '_blk_viewer');

    // Confirm visible before block
    const before = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ limit: 100 });
    expect(before.body.some((u: { user_id: string }) => u.user_id === blocked)).toBe(true);

    // Block
    await request(app)
      .post(`/users/${blocked}/block`)
      .set('Authorization', `Bearer ${access_token}`);

    // Confirm hidden after block
    const after = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ limit: 100 });
    expect(after.body.some((u: { user_id: string }) => u.user_id === blocked)).toBe(false);

    // Blocker should be hidden from blocked user's discover too
    const afterReverse = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${blockedToken}`)
      .query({ limit: 100 });
    const viewerId = (
      await request(app).get('/auth/me').set('Authorization', `Bearer ${access_token}`)
    ).body.user_id;
    expect(afterReverse.body.some((u: { user_id: string }) => u.user_id === viewerId)).toBe(false);
  });
});
