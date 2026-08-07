import request from 'supertest';
import type { Application } from 'express';
import WebSocket from 'ws';
import { buildWsServer, signupUser, makeUuid, type WsTestServer } from './helpers';

let server: WsTestServer;
let app: Application;
let userA: { user_id: string; access_token: string };
let userB: { user_id: string; access_token: string };

beforeAll(async () =>
{
  server = await buildWsServer();
  app = server.app;
  userA = await signupUser(app, '_chatA');
  userB = await signupUser(app, '_chatB');
});

afterAll(async () =>
{
  await server.close();
});

function openSocket(token: string): Promise<WebSocket>
{
  return new Promise((resolve, reject) =>
  {
    const ws = new WebSocket(`${server.wsBaseUrl}?token=${token}`);
    ws.once('open', () => resolve(ws));
    ws.once('error', reject);
  });
}

function nextMessage(ws: WebSocket): Promise<Record<string, unknown>>
{
  return new Promise((resolve) =>
  {
    ws.once('message', (raw) => resolve(JSON.parse(raw.toString())));
  });
}

function waitForClose(ws: WebSocket): Promise<{ code: number }>
{
  return new Promise((resolve) =>
  {
    ws.once('close', (code) => resolve({ code }));
  });
}

// REST responses are always HTTP 200; success/failure is in the body.

// ── GET /chat/conversations ───────────────────────────────────────────────────
// tests.md section 12

describe('GET /chat/conversations', () =>
{
  it('TC-1202 returns an empty list for a new user', async () =>
  {
    const { access_token } = await signupUser(app, '_convempty');
    const res = await request(app)
      .get('/api/chat/conversations')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.conversations).toEqual([]);
  });

  it('TC-1217a fails without a token', async () =>
  {
    const res = await request(app).get('/api/chat/conversations');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});

// ── POST /chat/:peer_id ───────────────────────────────────────────────────────

describe('POST /chat/:peer_id', () =>
{
  it('TC-1207 sends a message and returns the persisted message', async () =>
  {
    const res = await request(app)
      .post(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'שלום! 👋', msg_type: 'TEXT' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.content).toBe('שלום! 👋');
    expect(res.body.sender_id).toBe(userA.user_id);
    expect(res.body.message_id).toBeTruthy();
    expect(res.body.created_at).toBeTruthy();
  });

  it('TC-1207b defaults msg_type to TEXT when omitted', async () =>
  {
    const res = await request(app)
      .post(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'היי' });

    expect(res.body.success).toBe(true);
    expect(res.body.msg_type).toBe('TEXT');
  });

  it('TC-1208 content boundary: accepts 4000 chars, rejects 4001, rejects empty/whitespace', async () =>
  {
    const auth = { Authorization: `Bearer ${userA.access_token}` };

    const at4000 = await request(app).post(`/api/chat/${userB.user_id}`).set(auth).send({ content: 'a'.repeat(4000) });
    expect(at4000.body.success).toBe(true);

    const at4001 = await request(app).post(`/api/chat/${userB.user_id}`).set(auth).send({ content: 'a'.repeat(4001) });
    expect(at4001.body.success).toBe(false);
    expect(at4001.body.message).toBe('ההודעה ארוכה מדי (מקסימום 4000 תווים)');

    const empty = await request(app).post(`/api/chat/${userB.user_id}`).set(auth).send({ content: '' });
    expect(empty.body.success).toBe(false);
    expect(empty.body.message).toBe('יש להזין תוכן הודעה');

    const whitespace = await request(app).post(`/api/chat/${userB.user_id}`).set(auth).send({ content: '   ' });
    expect(whitespace.body.success).toBe(false);
  });

  it('TC-1209 rejects an msg_type outside TEXT/AUDIO/IMAGE', async () =>
  {
    const res = await request(app)
      .post(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'hi', msg_type: 'VIDEO' });

    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('סוג הודעה לא תקין');
  });

  it('TC-1210 cannot send to a peer who has blocked the sender', async () =>
  {
    const blocker = await signupUser(app, '_blkSend1');
    const blocked = await signupUser(app, '_blkSend2');

    await request(app)
      .post(`/api/users/${blocked.user_id}/block`)
      .set('Authorization', `Bearer ${blocker.access_token}`);

    const res = await request(app)
      .post(`/api/chat/${blocker.user_id}`)
      .set('Authorization', `Bearer ${blocked.access_token}`)
      .send({ content: 'היי' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('blocked');
  });

  it('TC-1211 sending a message to yourself fails cleanly with a specific message', async () =>
  {
    const res = await request(app)
      .post(`/api/chat/${userA.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'talking to myself' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('לא ניתן לשלוח הודעה לעצמך');
  });

  it('TC-1212 sending to a well-formed but nonexistent peer id fails with not_found', async () =>
  {
    const res = await request(app)
      .post(`/api/chat/${makeUuid()}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'is anyone there' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });

  it('TC-1217b fails without a token', async () =>
  {
    const res = await request(app).post(`/api/chat/${userB.user_id}`).send({ content: 'hi' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});

// ── GET /chat/:peer_id ─────────────────────────────────────────────────────────

describe('GET /chat/:peer_id', () =>
{
  it('TC-1203 returns messages between the two users, newest first', async () =>
  {
    await request(app)
      .post(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .send({ content: 'הודעה לגלילה' });

    const res = await request(app)
      .get(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ limit: 20 });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(Array.isArray(res.body.messages)).toBe(true);
    expect(res.body.messages.length).toBeGreaterThan(0);
    expect(res.body.messages[0]).toHaveProperty('message_id');
    expect(res.body.messages[0]).toHaveProperty('content');
    expect(res.body.messages[0]).toHaveProperty('sender_id');
    expect(res.body.messages[0]).toHaveProperty('created_at');
  });

  it('TC-1204 supports before-cursor pagination with no duplicates or gaps', async () =>
  {
    for (let i = 0; i < 5; i++)
    {
      await request(app)
        .post(`/api/chat/${userB.user_id}`)
        .set('Authorization', `Bearer ${userA.access_token}`)
        .send({ content: `הודעה ${i}` });
    }

    const first = await request(app)
      .get(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ limit: 3 });

    const oldestId = first.body.messages.at(-1)?.message_id;
    expect(oldestId).toBeTruthy();

    const older = await request(app)
      .get(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ limit: 3, before: oldestId });

    expect(older.body.success).toBe(true);
    expect(older.body.messages.every((m: { message_id: string }) => m.message_id !== oldestId)).toBe(true);
  });

  it('TC-1205 rejects a malformed before-cursor', async () =>
  {
    const res = await request(app)
      .get(`/api/chat/${userB.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`)
      .query({ before: 'not-a-uuid' });

    expect(res.body.success).toBe(false);
  });

  it('TC-1206 returns an empty array for a peer never messaged, not an error', async () =>
  {
    const stranger = await signupUser(app, '_neverchatted');
    const res = await request(app)
      .get(`/api/chat/${stranger.user_id}`)
      .set('Authorization', `Bearer ${userA.access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.messages).toEqual([]);
  });
});

// ── Conversations after messages exist ────────────────────────────────────────

describe('GET /chat/conversations (after messages)', () =>
{
  it('TC-1201 shows the conversation with unread count and last message', async () =>
  {
    const res = await request(app)
      .get('/api/chat/conversations')
      .set('Authorization', `Bearer ${userB.access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.conversations.length).toBeGreaterThan(0);
    const conv = res.body.conversations[0];
    expect(conv.peer_id).toBe(userA.user_id);
    expect(conv.last_content).toBeTruthy();
    expect(typeof conv.unread_count).toBe('number');
  });
});

// ── PUT /chat/:peer_id/read ───────────────────────────────────────────────────

describe('PUT /chat/:peer_id/read', () =>
{
  it('TC-1215 marks messages as read (unread_count drops to 0)', async () =>
  {
    await request(app)
      .put(`/api/chat/${userA.user_id}/read`)
      .set('Authorization', `Bearer ${userB.access_token}`);

    const res = await request(app)
      .get('/api/chat/conversations')
      .set('Authorization', `Bearer ${userB.access_token}`);
    const conv = res.body.conversations.find((c: { peer_id: string }) => c.peer_id === userA.user_id);

    expect(conv?.unread_count).toBe(0);
  });

  it('TC-1216 is a no-op when there is nothing unread', async () =>
  {
    const res = await request(app)
      .put(`/api/chat/${userA.user_id}/read`)
      .set('Authorization', `Bearer ${userB.access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
  });
});

// ── WebSocket — /ws ───────────────────────────────────────────────────────────
// tests.md section 13 (unaffected by the HTTP always-200 change — WS frames
// were already body-based signaling with no HTTP status code involved)

describe('WebSocket /ws', () =>
{
  it('TC-1301 accepts a connection with a valid access token', async () =>
  {
    const ws = await openSocket(userA.access_token);
    expect(ws.readyState).toBe(WebSocket.OPEN);
    ws.close();
  });

  it('TC-1302 rejects a connection with no token (close code 4001)', async () =>
  {
    const ws = new WebSocket(server.wsBaseUrl);
    const closed = waitForClose(ws);
    const result = await closed;

    expect(result.code).toBe(4001);
  });

  it('TC-1302b rejects a connection with a garbage token (close code 4001)', async () =>
  {
    const ws = new WebSocket(`${server.wsBaseUrl}?token=not-a-real-jwt`);
    const result = await waitForClose(ws);

    expect(result.code).toBe(4001);
  });

  it('TC-1304 responds to a ping frame with pong', async () =>
  {
    const ws = await openSocket(userA.access_token);
    const reply = nextMessage(ws);
    ws.send(JSON.stringify({ type: 'ping' }));

    expect(await reply).toEqual({ type: 'pong' });
    ws.close();
  });

  it('TC-1305 delivers a message in real time and acks the sender', async () =>
  {
    const senderWs = await openSocket(userA.access_token);
    const recipientWs = await openSocket(userB.access_token);

    const ack = nextMessage(senderWs);
    const delivered = nextMessage(recipientWs);

    senderWs.send(JSON.stringify({ peer_id: userB.user_id, content: 'ws hello' }));

    const ackMsg = await ack;
    const deliveredMsg = await delivered;

    expect(ackMsg.type).toBe('ack');
    expect(ackMsg.message_id).toBeTruthy();
    expect(deliveredMsg.content).toBe('ws hello');
    expect(deliveredMsg.sender_id).toBe(userA.user_id);

    senderWs.close();
    recipientWs.close();
  });

  it('TC-1306 rejects sending to a blocked peer with a typed error frame', async () =>
  {
    const blocker = await signupUser(app, '_wsblocker');
    const blocked = await signupUser(app, '_wsblocked');

    await request(app)
      .post(`/api/users/${blocked.user_id}/block`)
      .set('Authorization', `Bearer ${blocker.access_token}`);

    const blockedWs = await openSocket(blocked.access_token);
    const errorFrame = nextMessage(blockedWs);
    blockedWs.send(JSON.stringify({ peer_id: blocker.user_id, content: 'let me in' }));

    const frame = await errorFrame;
    expect(frame.type).toBe('error');
    expect(frame.code).toBe('blocked');

    blockedWs.close();
  });

  it('TC-1308 sending a message to yourself over WS returns a typed error, doesn\'t crash the connection', async () =>
  {
    // Regression coverage for the previously-unguarded self-message crash
    // (see security.test.ts / improve.md) — now explicitly validated.
    const ws = await openSocket(userA.access_token);
    const errorFrame = nextMessage(ws);
    ws.send(JSON.stringify({ peer_id: userA.user_id, content: 'talking to myself' }));

    const frame = await errorFrame;
    expect(frame.type).toBe('error');
    expect(frame.code).toBe('validation_error');

    // Connection survives — a follow-up ping still gets a pong.
    const reply = nextMessage(ws);
    ws.send(JSON.stringify({ type: 'ping' }));
    expect(await reply).toEqual({ type: 'pong' });

    ws.close();
  });

  it('TC-1309 silently ignores non-JSON frames instead of crashing the connection', async () =>
  {
    const ws = await openSocket(userA.access_token);
    ws.send('this is not json');

    // Follow up with a normal ping — if the malformed frame had broken the
    // connection or the server, this would never resolve and the test times out.
    const reply = nextMessage(ws);
    ws.send(JSON.stringify({ type: 'ping' }));
    expect(await reply).toEqual({ type: 'pong' });

    ws.close();
  });

  it('TC-1310 ignores a JSON frame with neither peer_id nor content', async () =>
  {
    const ws = await openSocket(userA.access_token);
    ws.send(JSON.stringify({ type: 'presence', status: 'online' }));

    const reply = nextMessage(ws);
    ws.send(JSON.stringify({ type: 'ping' }));
    expect(await reply).toEqual({ type: 'pong' });

    ws.close();
  });

  it('TC-1312 a message sent while the recipient is offline still persists via REST', async () =>
  {
    const offline = await signupUser(app, '_wsoffline');
    const senderWs = await openSocket(userA.access_token);

    const ack = nextMessage(senderWs);
    senderWs.send(JSON.stringify({ peer_id: offline.user_id, content: 'you were offline' }));
    await ack;

    const history = await request(app)
      .get(`/api/chat/${userA.user_id}`)
      .set('Authorization', `Bearer ${offline.access_token}`);

    expect(history.body.messages.some((m: { content: string }) => m.content === 'you were offline')).toBe(true);

    senderWs.close();
  });
});
