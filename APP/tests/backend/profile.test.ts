import request from 'supertest';
import type { Application } from 'express';
import { buildApp, signupUser, tinyImageBuffer, makeUuid } from './helpers';

let app: Application;

beforeAll(() =>
{
  app = buildApp();
});

// Every response is HTTP 200; success/failure is signaled by the body's
// `success` boolean.

// ── GET/PUT /users/me ─────────────────────────────────────────────────────────
// tests.md section 6

describe('GET /users/me', () =>
{
  it('TC-601 returns the caller\'s own profile', async () =>
  {
    const { user_id, access_token } = await signupUser(app, '_getme');
    const res = await request(app)
      .get('/users/me')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.user_id).toBe(user_id);
    expect(res.body).toHaveProperty('name');
    expect(res.body).toHaveProperty('bio');
  });

  it('TC-613a fails with no token', async () =>
  {
    const res = await request(app).get('/users/me');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});

describe('PUT /users/me', () =>
{
  it('TC-603 updates only the fields provided, leaving others untouched', async () =>
  {
    const { access_token } = await signupUser(app, '_putme');

    await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ name: 'ישראל ישראלי', city: 'תל אביב', gender: 'male' });

    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ bio: 'אוהב טיולים' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.bio).toBe('אוהב טיולים');
    expect(res.body.name).toBe('ישראל ישראלי');
    expect(res.body.city).toBe('תל אביב');
  });

  it('TC-604/605 fails (not a crash) on an empty body — no fields to update', async () =>
  {
    const { access_token } = await signupUser(app, '_emptyput');
    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({});

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-606 name boundary: rejects empty, accepts 80 chars, rejects 81 chars', async () =>
  {
    const { access_token } = await signupUser(app, '_namebound');
    const auth = { Authorization: `Bearer ${access_token}` };

    const empty = await request(app).put('/users/me').set(auth).send({ name: '' });
    expect(empty.body.success).toBe(false);
    expect(empty.body.message).toBe('השם חייב להכיל בין 1 ל-80 תווים');

    const at80 = await request(app).put('/users/me').set(auth).send({ name: 'א'.repeat(80) });
    expect(at80.body.success).toBe(true);

    const at81 = await request(app).put('/users/me').set(auth).send({ name: 'א'.repeat(81) });
    expect(at81.body.success).toBe(false);
  });

  it('TC-607 bio boundary: accepts empty and exactly 500 chars, rejects 501', async () =>
  {
    const { access_token } = await signupUser(app, '_biobound');
    const auth = { Authorization: `Bearer ${access_token}` };

    const empty = await request(app).put('/users/me').set(auth).send({ bio: '' });
    expect(empty.body.success).toBe(true);

    const at500 = await request(app).put('/users/me').set(auth).send({ bio: 'x'.repeat(500) });
    expect(at500.body.success).toBe(true);

    const at501 = await request(app).put('/users/me').set(auth).send({ bio: 'x'.repeat(501) });
    expect(at501.body.success).toBe(false);
  });

  it.each(['Male', 'nonbinary', ''])('TC-608 rejects an invalid gender value %j with a specific message', async (gender) =>
  {
    const { access_token } = await signupUser(app, `_badgender${Math.random().toString(36).slice(2, 8)}`);
    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ gender });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.message).toBe('יש לבחור מין תקין');
  });

  it.each(['01-01-2000', '2000/01/01', 'not-a-date'])(
    'TC-609 rejects a malformed date_of_birth %j with a specific message',
    async (date_of_birth) =>
    {
      const { access_token } = await signupUser(app, `_baddob${Math.random().toString(36).slice(2, 8)}`);
      const res = await request(app)
        .put('/users/me')
        .set('Authorization', `Bearer ${access_token}`)
        .send({ date_of_birth });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(false);
      expect(res.body.message).toBe('תאריך הלידה חייב להיות בפורמט YYYY-MM-DD');
    },
  );

  it('TC-609b accepts a well-formed date_of_birth', async () =>
  {
    const { access_token } = await signupUser(app, '_gooddob');
    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ date_of_birth: '1995-06-15' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.date_of_birth).toBe('1995-06-15');
  });

  it('TC-611 city/region boundary: rejects empty string', async () =>
  {
    const { access_token } = await signupUser(app, '_citybound');
    const auth = { Authorization: `Bearer ${access_token}` };

    const emptyCity = await request(app).put('/users/me').set(auth).send({ city: '' });
    expect(emptyCity.body.success).toBe(false);

    const emptyRegion = await request(app).put('/users/me').set(auth).send({ region: '' });
    expect(emptyRegion.body.success).toBe(false);
  });

  it('TC-612 ignores fields outside the allowlist (cannot self-set status via PUT)', async () =>
  {
    const { access_token } = await signupUser(app, '_noselfstatus');
    const res = await request(app)
      .put('/users/me')
      .set('Authorization', `Bearer ${access_token}`)
      .send({ status: 'banned', name: 'Still Works' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.name).toBe('Still Works');
    expect(res.body.status).toBeUndefined();
  });

  it('TC-613 fails with no token', async () =>
  {
    const res = await request(app).put('/users/me').send({ name: 'Nobody' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});

// ── Main photo — POST /users/me/photo ─────────────────────────────────────────
// tests.md section 7

describe('POST /users/me/photo', () =>
{
  it('TC-701 uploads a valid image and sets it as the main photo', async () =>
  {
    const { access_token } = await signupUser(app, '_mainphoto');
    const res = await request(app)
      .post('/users/me/photo')
      .set('Authorization', `Bearer ${access_token}`)
      .attach('photo', tinyImageBuffer(), { filename: 'me.png', contentType: 'image/png' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.photo_url).toMatch(/^\/uploads\//);

    const profile = await request(app).get('/users/me').set('Authorization', `Bearer ${access_token}`);
    expect(profile.body.photo_url).toBe(res.body.photo_url);
  });

  it('TC-702 replacing the main photo overwrites the stored URL', async () =>
  {
    const { access_token } = await signupUser(app, '_replacephoto');
    const auth = { Authorization: `Bearer ${access_token}` };

    const first = await request(app)
      .post('/users/me/photo')
      .set(auth)
      .attach('photo', tinyImageBuffer(), { filename: 'a.png', contentType: 'image/png' });

    const second = await request(app)
      .post('/users/me/photo')
      .set(auth)
      .attach('photo', tinyImageBuffer(), { filename: 'b.png', contentType: 'image/png' });

    expect(second.body.success).toBe(true);
    expect(second.body.photo_url).not.toBe(first.body.photo_url);
  });

  it('TC-703 rejects a request with no file attached', async () =>
  {
    const { access_token } = await signupUser(app, '_nofile');
    const res = await request(app)
      .post('/users/me/photo')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('missing_file');
  });

  it('TC-704 rejects a disallowed file type', async () =>
  {
    const { access_token } = await signupUser(app, '_badtype');
    const res = await request(app)
      .post('/users/me/photo')
      .set('Authorization', `Bearer ${access_token}`)
      .attach('photo', Buffer.from('not an image'), { filename: 'note.txt', contentType: 'text/plain' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('invalid_file_type');
  });

  it('TC-705 rejects a file over the 8MB size limit', async () =>
  {
    const { access_token } = await signupUser(app, '_toobig');
    const oversized = Buffer.alloc(8 * 1024 * 1024 + 1, 1);

    const res = await request(app)
      .post('/users/me/photo')
      .set('Authorization', `Bearer ${access_token}`)
      .attach('photo', oversized, { filename: 'huge.jpg', contentType: 'image/jpeg' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('file_too_large');
  }, 30_000);

  it('TC-707 the stored filename is server-generated, never derived from a path-traversal-shaped originalname', async () =>
  {
    const { access_token } = await signupUser(app, '_traversal');
    const res = await request(app)
      .post('/users/me/photo')
      .set('Authorization', `Bearer ${access_token}`)
      .attach('photo', tinyImageBuffer(), {
        filename: '../../../../etc/passwd.png',
        contentType: 'image/png',
      });

    expect(res.body.success).toBe(true);
    const basename = res.body.photo_url.split('/').pop();
    expect(basename).not.toContain('..');
    expect(basename).toMatch(/^[0-9a-f-]{36}\.png$/);
  });

  it('TC-708 fails with no token', async () =>
  {
    const res = await request(app)
      .post('/users/me/photo')
      .attach('photo', tinyImageBuffer(), { filename: 'x.png', contentType: 'image/png' });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});

// ── Additional photos — GET/POST/DELETE /users/me/photos ─────────────────────
// tests.md section 8

describe('Additional photos', () =>
{
  it('TC-801 GET returns an empty array for a fresh user', async () =>
  {
    const { access_token } = await signupUser(app, '_nophotos');
    const res = await request(app).get('/users/me/photos').set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.photos).toEqual([]);
  });

  it('TC-802/803 allows exactly 4 photos then rejects the 5th', async () =>
  {
    const { access_token } = await signupUser(app, '_photolimit');
    const auth = { Authorization: `Bearer ${access_token}` };

    for (let i = 0; i < 4; i++)
    {
      const res = await request(app)
        .post('/users/me/photos')
        .set(auth)
        .attach('photo', tinyImageBuffer(), { filename: `p${i}.png`, contentType: 'image/png' });

      expect(res.body.success).toBe(true);
      expect(res.body.photo_id).toBeTruthy();
    }

    const fifth = await request(app)
      .post('/users/me/photos')
      .set(auth)
      .attach('photo', tinyImageBuffer(), { filename: 'p5.png', contentType: 'image/png' });

    expect(fifth.body.success).toBe(false);
    expect(fifth.body.error).toBe('photo_limit_reached');

    const list = await request(app).get('/users/me/photos').set(auth);
    expect(list.body.photos.length).toBe(4);
  });

  it('TC-804 DELETE removes an owned photo', async () =>
  {
    const { access_token } = await signupUser(app, '_deletephoto');
    const auth = { Authorization: `Bearer ${access_token}` };

    const added = await request(app)
      .post('/users/me/photos')
      .set(auth)
      .attach('photo', tinyImageBuffer(), { filename: 'd.png', contentType: 'image/png' });

    const res = await request(app).delete(`/users/me/photos/${added.body.photo_id}`).set(auth);
    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);

    const list = await request(app).get('/users/me/photos').set(auth);
    expect(list.body.photos.find((p: { photo_id: string }) => p.photo_id === added.body.photo_id)).toBeUndefined();
  });

  it('TC-805 DELETE rejects a non-UUID photo_id', async () =>
  {
    const { access_token } = await signupUser(app, '_baduuid');
    const res = await request(app)
      .delete('/users/me/photos/not-a-uuid')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-806 DELETE fails with not_found for a UUID that does not exist', async () =>
  {
    const { access_token } = await signupUser(app, '_nosuchphoto');
    const res = await request(app)
      .delete(`/users/me/photos/${makeUuid()}`)
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });

  it('TC-807 cannot delete a photo owned by a different user (IDOR)', async () =>
  {
    const owner = await signupUser(app, '_idorowner');
    const attacker = await signupUser(app, '_idorattacker');

    const added = await request(app)
      .post('/users/me/photos')
      .set('Authorization', `Bearer ${owner.access_token}`)
      .attach('photo', tinyImageBuffer(), { filename: 'mine.png', contentType: 'image/png' });

    const res = await request(app)
      .delete(`/users/me/photos/${added.body.photo_id}`)
      .set('Authorization', `Bearer ${attacker.access_token}`);

    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');

    const ownerList = await request(app)
      .get('/users/me/photos')
      .set('Authorization', `Bearer ${owner.access_token}`);
    expect(ownerList.body.photos.some((p: { photo_id: string }) => p.photo_id === added.body.photo_id)).toBe(true);
  });

  it('TC-808 deleting a photo frees up a slot for another upload', async () =>
  {
    const { access_token } = await signupUser(app, '_freeslot');
    const auth = { Authorization: `Bearer ${access_token}` };
    const ids: string[] = [];

    for (let i = 0; i < 4; i++)
    {
      const res = await request(app)
        .post('/users/me/photos')
        .set(auth)
        .attach('photo', tinyImageBuffer(), { filename: `s${i}.png`, contentType: 'image/png' });
      ids.push(res.body.photo_id);
    }

    await request(app).delete(`/users/me/photos/${ids[0]}`).set(auth);

    const res = await request(app)
      .post('/users/me/photos')
      .set(auth)
      .attach('photo', tinyImageBuffer(), { filename: 'refill.png', contentType: 'image/png' });

    expect(res.body.success).toBe(true);
  });
});

// ── Discover — GET /users/discover ────────────────────────────────────────────
// tests.md section 9

describe('GET /users/discover', () =>
{
  it('TC-901/902 returns active candidates and excludes the caller themselves', async () =>
  {
    const { user_id, access_token } = await signupUser(app, '_disc1');
    await signupUser(app, '_disc2');
    await signupUser(app, '_disc3');

    const res = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ page: 1, limit: 10 });

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(Array.isArray(res.body.candidates)).toBe(true);
    expect(res.body.candidates.some((u: { user_id: string }) => u.user_id === user_id)).toBe(false);
  });

  it('TC-903 excludes a suspended user from every caller\'s feed', async () =>
  {
    const admin = await signupUser(app, '_discadmin');
    const target = await signupUser(app, '_discsuspend');
    const viewer = await signupUser(app, '_discviewer');

    const { makeAdmin } = await import('./helpers');
    makeAdmin(admin.user_id);
    const login = await request(app)
      .post('/auth/login')
      .send({ identifier: 'user_discadmin@test.com', password: 'Password123!' });

    await request(app)
      .put(`/admin/users/${target.user_id}/status`)
      .set('Authorization', `Bearer ${login.body.access_token}`)
      .send({ status: 'suspended' });

    const res = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${viewer.access_token}`)
      .query({ limit: 100 });

    expect(res.body.candidates.some((u: { user_id: string }) => u.user_id === target.user_id)).toBe(false);
  });

  it('TC-906 pagination returns no duplicates across two pages', async () =>
  {
    const viewer = await signupUser(app, '_page_viewer');
    for (let i = 0; i < 5; i++)
    {
      await signupUser(app, `_pagecand${i}`);
    }

    const auth = { Authorization: `Bearer ${viewer.access_token}` };
    const page1 = await request(app).get('/users/discover').set(auth).query({ page: 1, limit: 2 });
    const page2 = await request(app).get('/users/discover').set(auth).query({ page: 2, limit: 2 });

    const idsPage1 = page1.body.candidates.map((u: { user_id: string }) => u.user_id);
    const idsPage2 = page2.body.candidates.map((u: { user_id: string }) => u.user_id);
    const overlap = idsPage1.filter((id: string) => idsPage2.includes(id));

    expect(overlap).toEqual([]);
  });

  it.each([[0, false], [101, false], [100, true], [1, true]])(
    'TC-907 limit=%d succeeds=%s',
    async (limit, expectedSuccess) =>
    {
      const { access_token } = await signupUser(app, `_limitbound${limit}`);
      const res = await request(app)
        .get('/users/discover')
        .set('Authorization', `Bearer ${access_token}`)
        .query({ limit });

      expect(res.status).toBe(200);
      expect(res.body.success).toBe(expectedSuccess);
    },
  );

  it('TC-908 rejects page=0', async () =>
  {
    const { access_token } = await signupUser(app, '_page0');
    const res = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ page: 0 });

    expect(res.body.success).toBe(false);
  });

  it('TC-910 candidate objects never include email or password_hash', async () =>
  {
    const viewer = await signupUser(app, '_nosecret_viewer');
    await signupUser(app, '_nosecret_target');

    const res = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${viewer.access_token}`)
      .query({ limit: 100 });

    for (const candidate of res.body.candidates)
    {
      expect(candidate).not.toHaveProperty('email');
      expect(candidate).not.toHaveProperty('password_hash');
    }
  });

  it('TC-911 fails with no token', async () =>
  {
    const res = await request(app).get('/users/discover');

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });
});

// ── Peer profile & photos — GET /users/:id, GET /users/:id/photos ────────────
// tests.md section 10

describe('GET /users/:id', () =>
{
  it('TC-1001 returns the peer\'s public profile', async () =>
  {
    const { user_id: peerId } = await signupUser(app, '_peer_target');
    const { access_token } = await signupUser(app, '_peer_viewer');
    const res = await request(app)
      .get(`/users/${peerId}`)
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body.user_id).toBe(peerId);
    expect(res.body).not.toHaveProperty('email');
  });

  it('TC-1002 a non-UUID id fails cleanly, not swallowed by another route', async () =>
  {
    const { access_token } = await signupUser(app, '_notuuid');
    const res = await request(app)
      .get('/users/not-a-uuid')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-1002b /users/discover and /users/me are never captured by the /:id route', async () =>
  {
    const { access_token } = await signupUser(app, '_routeorder');
    const auth = { Authorization: `Bearer ${access_token}` };

    const discover = await request(app).get('/users/discover').set(auth);
    const me = await request(app).get('/users/me').set(auth);

    expect(Array.isArray(discover.body.candidates)).toBe(true);
    expect(me.body).toHaveProperty('bio');
  });

  it('TC-1003 fails with not_found for a well-formed UUID that does not exist', async () =>
  {
    const { access_token } = await signupUser(app, '_peer404');
    const res = await request(app)
      .get(`/users/${makeUuid()}`)
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('not_found');
  });

  it('TC-1005/1006 GET /:id/photos returns {name, photos} with an empty array by default', async () =>
  {
    const { user_id: peerId } = await signupUser(app, '_peerphotos_target');
    const { access_token } = await signupUser(app, '_peerphotos_viewer');

    const res = await request(app)
      .get(`/users/${peerId}/photos`)
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(true);
    expect(res.body).toHaveProperty('name');
    expect(res.body.photos).toEqual([]);
  });
});

// ── Block — POST /users/:id/block ─────────────────────────────────────────────
// tests.md section 11

describe('POST /users/:id/block', () =>
{
  it('TC-1101/904/905 blocking hides the target from both directions of discover', async () =>
  {
    const { user_id: blocked, access_token: blockedToken } = await signupUser(app, '_blk_target');
    const { access_token } = await signupUser(app, '_blk_viewer');

    const before = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ limit: 100 });
    expect(before.body.candidates.some((u: { user_id: string }) => u.user_id === blocked)).toBe(true);

    const blockRes = await request(app)
      .post(`/users/${blocked}/block`)
      .set('Authorization', `Bearer ${access_token}`);
    expect(blockRes.status).toBe(200);
    expect(blockRes.body.success).toBe(true);

    const after = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${access_token}`)
      .query({ limit: 100 });
    expect(after.body.candidates.some((u: { user_id: string }) => u.user_id === blocked)).toBe(false);

    const viewerId = (
      await request(app).get('/auth/me').set('Authorization', `Bearer ${access_token}`)
    ).body.user_id;
    const afterReverse = await request(app)
      .get('/users/discover')
      .set('Authorization', `Bearer ${blockedToken}`)
      .query({ limit: 100 });
    expect(afterReverse.body.candidates.some((u: { user_id: string }) => u.user_id === viewerId)).toBe(false);
  });

  it('TC-1102 cannot block yourself', async () =>
  {
    const { user_id, access_token } = await signupUser(app, '_selfblock');
    const res = await request(app)
      .post(`/users/${user_id}/block`)
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('cannot_block_self');
  });

  it('TC-1103 blocking the same user twice is idempotent, not an error', async () =>
  {
    const { user_id: blocked } = await signupUser(app, '_dblblock_target');
    const { access_token } = await signupUser(app, '_dblblock_viewer');
    const auth = { Authorization: `Bearer ${access_token}` };

    const first = await request(app).post(`/users/${blocked}/block`).set(auth);
    const second = await request(app).post(`/users/${blocked}/block`).set(auth);

    expect(first.body.success).toBe(true);
    expect(second.body.success).toBe(true);
  });

  it('TC-1104 rejects a non-UUID target id', async () =>
  {
    const { access_token } = await signupUser(app, '_blocknotuuid');
    const res = await request(app)
      .post('/users/not-a-uuid/block')
      .set('Authorization', `Bearer ${access_token}`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
  });

  it('TC-1108b fails with no token', async () =>
  {
    const res = await request(app).post(`/users/${makeUuid()}/block`);

    expect(res.status).toBe(200);
    expect(res.body.success).toBe(false);
    expect(res.body.error).toBe('unauthorized');
  });
});
