import crypto from 'crypto';
import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import { config } from '../config';
import { authQueries } from '../database/queries/auth.queries';

export interface TokenPair {
  access_token: string;
  refresh_token: string;
}

export interface AccessPayload {
  sub: string;
  is_admin: boolean;
}

function hashToken(token: string): string {
  return crypto.createHash('sha256').update(token).digest('hex');
}

export const SessionModel = {
  issue(userId: string, isAdmin: boolean): TokenPair {
    const access_token = jwt.sign(
      { sub: userId, is_admin: isAdmin } as AccessPayload,
      config.jwtSecret,
      { expiresIn: config.jwtAccessTtl as jwt.SignOptions['expiresIn'] },
    );

    const refreshId = uuidv4();
    const refresh_token = jwt.sign(
      { sub: userId, jti: refreshId },
      config.jwtSecret,
      { expiresIn: `${config.jwtRefreshTtlDays}d` as jwt.SignOptions['expiresIn'] },
    );

    const now = new Date();
    const expires = new Date(now);
    expires.setDate(expires.getDate() + config.jwtRefreshTtlDays);

    authQueries.createSession({
      token_hash: hashToken(refresh_token),
      user_id: userId,
      created_at: now.toISOString(),
      expires_at: expires.toISOString(),
    });

    return { access_token, refresh_token };
  },

  verifyAccess(token: string): AccessPayload {
    return jwt.verify(token, config.jwtSecret) as AccessPayload;
  },

  // Returns userId if valid and not expired/revoked, throws otherwise
  async rotateRefresh(refreshToken: string): Promise<{ userId: string; isAdmin: boolean; tokens: TokenPair }> {
    const payload = jwt.verify(refreshToken, config.jwtSecret) as { sub: string };
    const tokenHash = hashToken(refreshToken);

    const session = authQueries.findSession(tokenHash);
    if (!session) throw new Error('session_not_found');

    const now = new Date();
    if (new Date(session.expires_at) < now) {
      authQueries.deleteSession(tokenHash);
      throw new Error('session_expired');
    }

    const creds = authQueries.findById(payload.sub);
    if (!creds) throw new Error('user_not_found');

    // Rotate: delete old, issue new
    authQueries.deleteSession(tokenHash);
    const tokens = SessionModel.issue(creds.user_id, creds.is_admin === 1);

    return { userId: creds.user_id, isAdmin: creds.is_admin === 1, tokens };
  },

  revoke(refreshToken: string): void {
    authQueries.deleteSession(hashToken(refreshToken));
  },
};
