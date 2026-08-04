import request from 'supertest';
import { buildApp, signupUser } from './helpers';
import type { Application } from 'express';

let app: Application;

beforeAll(() => { app = buildApp(); });

describe('POST /auth/signup', () => {
  it('creates a user and returns tokens', async () => {
    const res = await request(app).post('/auth/signup').send({
      email:    'signup@test.com',
      username: 'signupuser',
      password: 'Password123!',
    });
    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({
      email:    'signup@test.com',
      username: 'signupuser',
      is_admin: false,
    });
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.refresh_token).toBeTruthy();
    expect(res.body.user_id).toBeTruthy();
  });

  it('rejects duplicate email', async () => {
    await request(app).post('/auth/signup').send({
      email: 'dup@test.com', username: 'dup1', password: 'Password1!',
    });
    const res = await request(app).post('/auth/signup').send({
      email: 'dup@test.com', username: 'dup2', password: 'Password1!',
    });
    expect(res.status).toBe(409);
  });

  it('rejects missing fields', async () => {
    const res = await request(app).post('/auth/signup').send({ email: 'x@x.com' });
    expect(res.status).toBe(422);
  });
});

describe('POST /auth/login', () => {
  beforeAll(async () => {
    await request(app).post('/auth/signup').send({
      email: 'login@test.com', username: 'loginuser', password: 'MyPass99!',
    });
  });

  it('logs in by username and returns tokens', async () => {
    const res = await request(app).post('/auth/login').send({
      identifier: 'loginuser', password: 'MyPass99!',
    });
    expect(res.status).toBe(200);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.is_admin).toBe(false);
  });

  it('logs in by email', async () => {
    const res = await request(app).post('/auth/login').send({
      identifier: 'login@test.com', password: 'MyPass99!',
    });
    expect(res.status).toBe(200);
    expect(res.body.access_token).toBeTruthy();
  });

  it('rejects wrong password', async () => {
    const res = await request(app).post('/auth/login').send({
      identifier: 'loginuser', password: 'wrongpassword',
    });
    expect(res.status).toBe(401);
  });

  it('rejects unknown user', async () => {
    const res = await request(app).post('/auth/login').send({
      identifier: 'nobody', password: 'anything',
    });
    expect(res.status).toBe(401);
  });
});

describe('GET /auth/me', () => {
  it('returns current user info', async () => {
    const { access_token } = await signupUser(app, '_me');
    const res = await request(app)
      .get('/auth/me')
      .set('Authorization', `Bearer ${access_token}`);
    expect(res.status).toBe(200);
    expect(res.body.email).toBe('user_me@test.com');
  });

  it('returns 401 without token', async () => {
    const res = await request(app).get('/auth/me');
    expect(res.status).toBe(401);
  });
});

describe('POST /auth/refresh', () => {
  it('rotates the refresh token', async () => {
    const { refresh_token: rt1 } = await signupUser(app, '_refresh');
    const res = await request(app).post('/auth/refresh').send({ refresh_token: rt1 });
    expect(res.status).toBe(200);
    expect(res.body.access_token).toBeTruthy();
    expect(res.body.refresh_token).not.toBe(rt1);
  });

  it('rejects an already-used token', async () => {
    const { refresh_token: rt } = await signupUser(app, '_reuse');
    await request(app).post('/auth/refresh').send({ refresh_token: rt });
    const res2 = await request(app).post('/auth/refresh').send({ refresh_token: rt });
    expect(res2.status).toBe(401);
  });
});

describe('POST /auth/logout', () => {
  it('returns 204 and revokes the session', async () => {
    const { refresh_token } = await signupUser(app, '_logout');
    const logoutRes = await request(app).post('/auth/logout').send({ refresh_token });
    expect(logoutRes.status).toBe(204);
    // refresh should now fail since session was deleted
    const refreshRes = await request(app).post('/auth/refresh').send({ refresh_token });
    expect(refreshRes.status).toBe(401);
  });
});
