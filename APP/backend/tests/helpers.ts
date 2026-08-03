import type { Application } from 'express';
import request from 'supertest';
import { createApp } from '../src/app';
import { runMigrations } from '../src/database/migrate';

export function buildApp(): Application {
  runMigrations();
  return createApp();
}

export interface AuthTokens {
  user_id:       string;
  access_token:  string;
  refresh_token: string;
}

export async function signupUser(
  app: Application,
  suffix = '',
): Promise<AuthTokens> {
  const res = await request(app)
    .post('/auth/signup')
    .send({
      email:    `user${suffix}@test.com`,
      username: `testuser${suffix}`,
      password: 'Password123!',
    });
  return {
    user_id:       res.body.user_id,
    access_token:  res.body.access_token,
    refresh_token: res.body.refresh_token,
  };
}

export function makeAdmin(userId: string): void {
  const { getDb } = require('../src/database/connection');
  getDb().prepare('UPDATE auth_credentials SET is_admin = 1 WHERE user_id = ?').run(userId);
}
