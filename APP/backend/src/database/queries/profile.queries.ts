import { getDb } from '../connection';

export interface ProfileRow {
  user_id: string;
  name: string;
  bio: string;
  gender: string | null;
  date_of_birth: string | null;
  city: string;
  region: string;
  photo_url: string | null;
  expo_push_token: string | null;
  status: string;
  registered_at: string;
  updated_at: string;
}

export interface PhotoRow {
  photo_id: string;
  user_id: string;
  url: string;
  created_at: string;
}

export const profileQueries = {
  create(p: {
    user_id: string;
    name: string;
    city: string;
    region: string;
    gender: string;
    date_of_birth: string;
    registered_at: string;
    updated_at: string;
  }): void {
    getDb()
      .prepare(`
        INSERT INTO user_profiles
          (user_id, name, bio, gender, date_of_birth, city, region, photo_url, status, registered_at, updated_at)
        VALUES (?, ?, '', ?, ?, ?, ?, NULL, 'active', ?, ?)
      `)
      .run(p.user_id, p.name, p.gender, p.date_of_birth, p.city, p.region, p.registered_at, p.updated_at);
  },

  findById(userId: string): ProfileRow | undefined {
    return getDb()
      .prepare('SELECT * FROM user_profiles WHERE user_id = ?')
      .get(userId) as ProfileRow | undefined;
  },

  update(userId: string, fields: Partial<Pick<ProfileRow, 'name' | 'bio' | 'city' | 'region' | 'gender' | 'date_of_birth'>>, updatedAt: string): void {
    const sets = Object.keys(fields).map(k => `${k} = ?`).join(', ');
    const values = [...Object.values(fields), updatedAt, userId];
    getDb()
      .prepare(`UPDATE user_profiles SET ${sets}, updated_at = ? WHERE user_id = ?`)
      .run(...values);
  },

  updatePhotoUrl(userId: string, url: string | null, updatedAt: string): void {
    getDb()
      .prepare('UPDATE user_profiles SET photo_url = ?, updated_at = ? WHERE user_id = ?')
      .run(url, updatedAt, userId);
  },

  updatePushToken(userId: string, token: string | null, updatedAt: string): void {
    getDb()
      .prepare('UPDATE user_profiles SET expo_push_token = ?, updated_at = ? WHERE user_id = ?')
      .run(token, updatedAt, userId);
  },

  // Discover candidates: exclude self, blocked, and users who blocked caller; active only
  findCandidates(callerId: string, limit: number, offset: number): ProfileRow[] {
    return getDb()
      .prepare(`
        SELECT p.*
        FROM user_profiles p
        WHERE p.user_id != ?
          AND p.status = 'active'
          AND p.user_id NOT IN (
            SELECT blocked_id FROM user_blocks WHERE blocker_id = ?
          )
          AND p.user_id NOT IN (
            SELECT blocker_id FROM user_blocks WHERE blocked_id = ?
          )
        ORDER BY p.registered_at DESC
        LIMIT ? OFFSET ?
      `)
      .all(callerId, callerId, callerId, limit, offset) as unknown as ProfileRow[];
  },

  countCandidates(callerId: string): number {
    const row = getDb()
      .prepare(`
        SELECT COUNT(*) as cnt
        FROM user_profiles p
        WHERE p.user_id != ?
          AND p.status = 'active'
          AND p.user_id NOT IN (
            SELECT blocked_id FROM user_blocks WHERE blocker_id = ?
          )
          AND p.user_id NOT IN (
            SELECT blocker_id FROM user_blocks WHERE blocked_id = ?
          )
      `)
      .get(callerId, callerId, callerId) as { cnt: number };
    return row.cnt;
  },

  // Additional photos
  getPhotos(userId: string): PhotoRow[] {
    return getDb()
      .prepare('SELECT * FROM user_photos WHERE user_id = ? ORDER BY created_at ASC')
      .all(userId) as unknown as PhotoRow[];
  },

  countPhotos(userId: string): number {
    const row = getDb()
      .prepare('SELECT COUNT(*) as cnt FROM user_photos WHERE user_id = ?')
      .get(userId) as { cnt: number };
    return row.cnt;
  },

  addPhoto(photo: { photo_id: string; user_id: string; url: string; created_at: string }): void {
    getDb()
      .prepare('INSERT INTO user_photos (photo_id, user_id, url, created_at) VALUES (?, ?, ?, ?)')
      .run(photo.photo_id, photo.user_id, photo.url, photo.created_at);
  },

  findPhoto(photoId: string): PhotoRow | undefined {
    return getDb()
      .prepare('SELECT * FROM user_photos WHERE photo_id = ?')
      .get(photoId) as PhotoRow | undefined;
  },

  deletePhoto(photoId: string): void {
    getDb()
      .prepare('DELETE FROM user_photos WHERE photo_id = ?')
      .run(photoId);
  },

  // Block
  addBlock(blockerId: string, blockedId: string, createdAt: string): void {
    getDb()
      .prepare('INSERT OR IGNORE INTO user_blocks (blocker_id, blocked_id, created_at) VALUES (?, ?, ?)')
      .run(blockerId, blockedId, createdAt);
  },

  // Admin
  findAll(limit: number, offset: number): ProfileRow[] {
    return getDb()
      .prepare('SELECT * FROM user_profiles ORDER BY registered_at DESC LIMIT ? OFFSET ?')
      .all(limit, offset) as unknown as ProfileRow[];
  },

  countAll(): number {
    const row = getDb()
      .prepare('SELECT COUNT(*) as cnt FROM user_profiles')
      .get() as { cnt: number };
    return row.cnt;
  },

  updateStatus(userId: string, status: string, updatedAt: string): void {
    getDb()
      .prepare("UPDATE user_profiles SET status = ?, updated_at = ? WHERE user_id = ?")
      .run(status, updatedAt, userId);
  },

  deleteUser(userId: string): void {
    getDb()
      .prepare('DELETE FROM user_profiles WHERE user_id = ?')
      .run(userId);
  },
};
