import { getDb } from '../connection';

export interface AuthRow {
  user_id: string;
  username: string;
  email: string;
  password_hash: string;
  is_admin: number;
  created_at: string;
  last_login_at: string | null;
}

export interface SessionRow {
  token_hash: string;
  user_id: string;
  created_at: string;
  expires_at: string;
}

export const authQueries = {
  findByUsername(username: string): AuthRow | undefined {
    return getDb()
      .prepare('SELECT * FROM auth_credentials WHERE username = ? COLLATE NOCASE')
      .get(username) as AuthRow | undefined;
  },

  findByEmail(email: string): AuthRow | undefined {
    return getDb()
      .prepare('SELECT * FROM auth_credentials WHERE email = ? COLLATE NOCASE')
      .get(email) as AuthRow | undefined;
  },

  findById(userId: string): AuthRow | undefined {
    return getDb()
      .prepare('SELECT * FROM auth_credentials WHERE user_id = ?')
      .get(userId) as AuthRow | undefined;
  },

  createCredentials(c: {
    user_id: string;
    username: string;
    email: string;
    password_hash: string;
    created_at: string;
  }): void {
    getDb()
      .prepare(`
        INSERT INTO auth_credentials (user_id, username, email, password_hash, is_admin, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
      `)
      .run(c.user_id, c.username, c.email, c.password_hash, c.created_at);
  },

  updateLastLogin(userId: string, at: string): void {
    getDb()
      .prepare('UPDATE auth_credentials SET last_login_at = ? WHERE user_id = ?')
      .run(at, userId);
  },

  // Sessions
  createSession(s: { token_hash: string; user_id: string; created_at: string; expires_at: string }): void {
    getDb()
      .prepare('INSERT INTO user_sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)')
      .run(s.token_hash, s.user_id, s.created_at, s.expires_at);
  },

  findSession(tokenHash: string): SessionRow | undefined {
    return getDb()
      .prepare('SELECT * FROM user_sessions WHERE token_hash = ?')
      .get(tokenHash) as SessionRow | undefined;
  },

  deleteSession(tokenHash: string): void {
    getDb()
      .prepare('DELETE FROM user_sessions WHERE token_hash = ?')
      .run(tokenHash);
  },

  deleteExpiredSessions(): void {
    getDb()
      .prepare("DELETE FROM user_sessions WHERE expires_at < datetime('now')")
      .run();
  },
};
