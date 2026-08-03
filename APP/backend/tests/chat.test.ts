import request from 'supertest';
import { buildApp, signupUser } from './helpers';
import type { Application } from 'express';

let app: Application;
let userA: { user_id: string; access_token: string };
let userB: { user_id: string; access_token: string };

beforeAll(async () => {
  app = buildApp();
  userA = await signupUser(app, '_chatA');
  userB = await signupUser(app, '_chatB');
});

describe('GET /chat/conversations', () => {
  it('returns an empty list for a new user', async () => {
    const res = await request(app)
      .get('/chat/conversations')
      .set('Authorization', `Bearer ${userA.access_token}`);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBe(0);
  });

  it('returns 401 without token', async () => {
    const res = await request(app).get('/chat/conversations');
    expect(res.status).toBe(401);
  });
});

describe('POST /chat/:peer_id', () => {
  it('sends a message and returns 201 with message object', async () => {
    const res = await request(app)
      .post(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'שלום! 👋', msg_type: 'TEXT' });
    expect(res.status).toBe(201);
    expect(res.body.content).toBe('שלום! 👋');
    expect(res.body.sender_id).toBe(userA.user_id);
    expect(res.body.message_id).toBeTruthy();
    expect(res.body.created_at).toBeTruthy();
  });

  it('defaults msg_type to TEXT when omitted', async () => {
    const res = await request(app)
      .post(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'היי' });
    expect(res.status).toBe(201);
    expect(res.body.msg_type).toBe('TEXT');
  });

  it('rejects empty content', async () => {
    const res = await request(app)
      .post(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: '' });
    expect(res.status).toBe(422);
  });
});

describe('GET /chat/:peer_id', () => {
  it('returns messages between users (newest first)', async () => {
    // Send a known message
    await request(app)
      .post(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'הודעה לגלילה' });

    const res = await request(app)
      .get(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ limit: 20 });
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
    expect(res.body.length).toBeGreaterThan(0);
    expect(res.body[0]).toHaveProperty('message_id');
    expect(res.body[0]).toHaveProperty('content');
    expect(res.body[0]).toHaveProperty('sender_id');
    expect(res.body[0]).toHaveProperty('created_at');
  });

  it('supports before-cursor pagination', async () => {
    // Send several messages
    for (let i = 0; i < 5; i++) {
      await request(app)
        .post(`/chat/${userB.user_id}`)
        .set('Authorization', `Bearer ${userA.access_token}`)
        .send({ content: `הודעה ${i}` });
    }

    const first = await request(app)
      .get(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ limit: 3 });

    const oldestId = first.body.at(-1)?.message_id;
    expect(oldestId).toBeTruthy();

    const older = await request(app)
      .get(`/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ limit: 3, before: oldestId });
    expect(older.status).toBe(200);
    // All messages in `older` must be strictly before the cursor message
    expect(older.body.every((m: { message_id: string }) => m.message_id !== oldestId)).toBe(true);
  });
});

describe('GET /chat/conversations (after messages)', () => {
  it('shows conversation with unread count and last message', async () => {
    const res = await request(app)
      .get('/chat/conversations')
      .set('Authorization', `Bearer ${userB.access_token}`);
    expect(res.status).toBe(200);
    expect(res.body.length).toBeGreaterThan(0);
    const conv = res.body[0];
    expect(conv.peer_id).toBe(userA.user_id);
    expect(conv.last_content).toBeTruthy();
    expect(typeof conv.unread_count).toBe('number');
  });
});

describe('PUT /chat/:peer_id/read', () => {
  it('marks messages as read (unread_count drops to 0)', async () => {
    await request(app)
      .put(`/chat/${userA.user_id}/read`)
      .set('Authorization', `Bearer ${userB.access_token}`);

    const res = await request(app)
      .get('/chat/conversations')
      .set('Authorization', `Bearer ${userB.access_token}`);
    const conv = res.body.find((c: { peer_id: string }) => c.peer_id === userA.user_id);
    expect(conv?.unread_count).toBe(0);
  });
});

describe('blocked users', () => {
  it('cannot send a message to a user that blocked them', async () => {
    const blocker = await signupUser(app, '_blkSend1');
    const blocked = await signupUser(app, '_blkSend2');

    // blocker blocks blocked
    await request(app)
      .post(`/users/${blocked.user_id}/block`)
      .set('Authorization', `Bearer ${blocker.access_token}`);

    // blocked tries to message blocker
    const res = await request(app)
      .post(`/chat/${blocker.user_id}`)
      .set('Authorization', `Bearer ${blocked.access_token}`)
      .send({ content: 'היי' });
    expect(res.status).toBe(403);
  });
});
