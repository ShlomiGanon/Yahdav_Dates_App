import request from 'supertest';
import type { Application } from 'express';
import { buildApp, signupUser, makeAdmin } from './helpers';
import { getDb } from '../../backend/src/database/connection';

let app: Application;
let adminToken: string;

beforeAll(async () =>
{
  app = buildApp();

  const admin = await signupUser(app, '_dataintegrity_admin');
  makeAdmin(admin.user_id);
  const login = await request(app)
    .post('/api/auth/login')
    .send({ identifier: 'user_dataintegrity_admin@test.com', password: 'Password123!' });
  adminToken = login.body.access_token;
});

function countWhere(table: string, column: string, value: string): number
{
  const row = getDb()
    .prepare(`SELECT COUNT(*) as cnt FROM ${table} WHERE ${column} = ?`)
    .get(value) as { cnt: number };
  return row.cnt;
}

// tests.md section 18 — DB-level integrity, run through the real HTTP API
// wherever possible so these also double as end-to-end cascade coverage.

describe('ON DELETE CASCADE when a user is deleted', () =>
{
  it('TC-1802 removes auth_credentials, user_photos, user_sessions, and both directions of user_blocks', async () =>
  {
    const victim = await signupUser(app, '_cascadevictim');
    const peer = await signupUser(app, '_cascadepeer');

    // Give the victim a session, an additional photo, and both a block they
    // made and a block someone else made against them.
    await request(app)
      .post('/api/users/me/photos')
      .set('Authorization', `Bearer ${victim.access_token}`)
      .attach('photo', Buffer.from('fake'), { filename: 'p.png', contentType: 'image/png' });
    await request(app)
      .post(`/api/users/${peer.user_id}/block`)
      .set('Authorization', `Bearer ${victim.access_token}`);

    const blocker = await signupUser(app, '_cascadeblocker');
    await request(app)
      .post(`/api/users/${victim.user_id}/block`)
      .set('Authorization', `Bearer ${blocker.access_token}`);

    expect(countWhere('auth_credentials', 'user_id', victim.user_id)).toBe(1);
    expect(countWhere('user_photos', 'user_id', victim.user_id)).toBeGreaterThan(0);
    expect(countWhere('user_sessions', 'user_id', victim.user_id)).toBeGreaterThan(0);
    expect(countWhere('user_blocks', 'blocker_id', victim.user_id)).toBeGreaterThan(0);
    expect(countWhere('user_blocks', 'blocked_id', victim.user_id)).toBeGreaterThan(0);

    const del = await request(app)
      .delete(`/api/admin/users/${victim.user_id}`)
      .set('Authorization', `Bearer ${adminToken}`);
    expect(del.status).toBe(200);
    expect(del.body.success).toBe(true);

    expect(countWhere('auth_credentials', 'user_id', victim.user_id)).toBe(0);
    expect(countWhere('user_photos', 'user_id', victim.user_id)).toBe(0);
    expect(countWhere('user_sessions', 'user_id', victim.user_id)).toBe(0);
    expect(countWhere('user_blocks', 'blocker_id', victim.user_id)).toBe(0);
    expect(countWhere('user_blocks', 'blocked_id', victim.user_id)).toBe(0);
  });

  it('TC-1802b removes direct_messages where the deleted user was either sender or recipient', async () =>
  {
    const victim = await signupUser(app, '_msgvictim');
    const peerA = await signupUser(app, '_msgpeerA');
    const peerB = await signupUser(app, '_msgpeerB');

    await request(app)
      .post(`/api/chat/${peerA.user_id}`)
      .set('Authorization', `Bearer ${victim.access_token}`)
      .send({ content: 'victim as sender' });
    await request(app)
      .post(`/api/chat/${victim.user_id}`)
      .set('Authorization', `Bearer ${peerB.access_token}`)
      .send({ content: 'victim as recipient' });

    expect(countWhere('direct_messages', 'sender_id', victim.user_id)).toBeGreaterThan(0);
    expect(countWhere('direct_messages', 'recipient_id', victim.user_id)).toBeGreaterThan(0);

    await request(app)
      .delete(`/api/admin/users/${victim.user_id}`)
      .set('Authorization', `Bearer ${adminToken}`);

    expect(countWhere('direct_messages', 'sender_id', victim.user_id)).toBe(0);
    expect(countWhere('direct_messages', 'recipient_id', victim.user_id)).toBe(0);
  });
});

describe('direct_messages CHECK (sender_id <> recipient_id)', () =>
{
  it('TC-1801 rejects a raw insert where sender and recipient are the same user, at the DB layer', async () =>
  {
    const { user_id } = await signupUser(app, '_selfmsgdb');

    expect(() =>
    {
      getDb()
        .prepare(`
          INSERT INTO direct_messages (message_id, sender_id, recipient_id, content, msg_type, created_at)
          VALUES ('11111111-1111-1111-1111-111111111111', ?, ?, 'hi', 'TEXT', datetime('now'))
        `)
        .run(user_id, user_id);
    }).toThrow();
  });
});

describe('unique index behavior (defense in depth below the app-level checks)', () =>
{
  it('TC-1805 username uniqueness is enforced case-insensitively at the DB layer', async () =>
  {
    // Keep this short — it becomes part of a username capped at 30 chars.
    const suffix = Date.now().toString(36);
    const username = `testuser_uniqcheck${suffix}`;
    await signupUser(app, `_uniqcheck${suffix}`);

    expect(() =>
    {
      getDb()
        .prepare(`
          INSERT INTO auth_credentials (user_id, username, email, password_hash, is_admin, created_at)
          VALUES ('22222222-2222-2222-2222-222222222222', ?, 'someoneelse@test.com', 'hash', 0, datetime('now'))
        `)
        .run(username.toUpperCase());
    }).toThrow();
  });
});

describe('user_blocks composite primary key', () =>
{
  it('TC-1806 rejects a literal duplicate (blocker_id, blocked_id) raw insert', async () =>
  {
    const a = await signupUser(app, '_pkblockA');
    const b = await signupUser(app, '_pkblockB');

    getDb()
      .prepare('INSERT INTO user_blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, datetime(\'now\'))')
      .run(a.user_id, b.user_id);

    expect(() =>
    {
      getDb()
        .prepare('INSERT INTO user_blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, datetime(\'now\'))')
        .run(a.user_id, b.user_id);
    }).toThrow();
  });
});
