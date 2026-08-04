import http from 'http';
import type { AddressInfo } from 'net';
import type { Application } from 'express';
import request from 'supertest';
import { v4 as uuidv4 } from 'uuid';
import { createApp } from '../../backend/src/app';
import { runMigrations } from '../../backend/src/database/migrate';
import { getDb } from '../../backend/src/database/connection';
import { attachWsServer } from '../../backend/src/websocket/wsServer';

export function buildApp(): Application
{
  runMigrations();
  return createApp();
}

export interface WsTestServer
{
  app: Application;
  wsBaseUrl: string;
  close: () => Promise<void>;
}

// Real WebSocket tests need an actual listening socket — supertest alone
// can't drive a `ws` connection, so this spins up the same app+http+ws
// wiring src/server.ts uses in production, bound to an ephemeral port.
export function buildWsServer(): Promise<WsTestServer>
{
  runMigrations();
  const app = createApp();
  const server = http.createServer(app);
  attachWsServer(server);

  return new Promise((resolve) =>
  {
    server.listen(0, '127.0.0.1', () =>
    {
      const { port } = server.address() as AddressInfo;
      resolve({
        app,
        wsBaseUrl: `ws://127.0.0.1:${port}/ws`,
        close: () => new Promise((closeResolve) => server.close(() => closeResolve())),
      });
    });
  });
}

export interface AuthTokens
{
  user_id: string;
  access_token: string;
  refresh_token: string;
}

// Signup no longer issues a session (the app requires a manual login right
// after registering), so this logs in immediately after signing up to hand
// back tokens for tests that need an authenticated request.
export async function signupUser(app: Application, suffix = ''): Promise<AuthTokens>
{
  const username = `testuser${suffix}`;
  const password = 'Password123!';

  const signupRes = await request(app)
    .post('/auth/signup')
    .send({
      email: `user${suffix}@test.com`,
      username,
      password,
    });

  const loginRes = await request(app)
    .post('/auth/login')
    .send({ identifier: username, password });

  return {
    user_id: signupRes.body.user_id,
    access_token: loginRes.body.access_token,
    refresh_token: loginRes.body.refresh_token,
  };
}

export function makeAdmin(userId: string): void
{
  getDb().prepare('UPDATE auth_credentials SET is_admin = 1 WHERE user_id = ?').run(userId);
}

export function makeUuid(): string
{
  return uuidv4();
}

// A syntactically-valid 1x1 transparent PNG. The backend's upload filter only
// inspects the declared multipart Content-Type (see storageService.ts), not
// the file's actual bytes, so any small buffer works for "valid image" cases —
// but using a real PNG keeps these tests honest about what a client would send.
const TINY_PNG_BASE64 =
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42' +
  'YAAAAASUVORK5CYII=';

export function tinyImageBuffer(): Buffer
{
  return Buffer.from(TINY_PNG_BASE64, 'base64');
}
