import axios from 'axios';
import { tokenStore } from './tokenStore';
import type { AdminUser } from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000';

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((cfg) => {
  const token = tokenStore.get();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// The backend always answers HTTP 200; success/failure lives in the body
// (`{success, message, error?}`). Axios therefore never rejects for
// business-logic failures — the auto-refresh-on-expired-token logic has to
// live in the *success* handler, keyed off `data.error === 'unauthorized'`
// rather than a 401 status code.
//
// This also sidesteps a real deadlock the old status-code-based version was
// exposed to: if /auth/refresh itself failed with a 401, that response
// recursed back through this same interceptor with no guard against it
// being the refresh call itself. /auth/refresh's own failure codes
// (session_not_found, session_expired, invalid_token, ...) are never
// `unauthorized` — that code only ever comes from the `authenticate`
// middleware, which /auth/refresh doesn't go through — so this can't recurse.
// Shared by this interceptor's retry-on-unauthorized path and
// AuthContext's mount-time session restore. Refresh tokens are single-use,
// so two concurrent calls with the same stored token (e.g. React StrictMode
// double-invoking AuthContext's effect in dev) would otherwise race — the
// loser could clear a session the winner just established.
let refreshPromise: Promise<AdminUser | null> | null = null;

export async function performRefresh(): Promise<AdminUser | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const storedRefresh = localStorage.getItem('refresh_token');
      if (!storedRefresh) return null;

      const { data } = await api.post('/auth/refresh', { refresh_token: storedRefresh });
      if (!data.success) return null;

      tokenStore.set(data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);
      return {
        user_id:  data.user_id,
        email:    data.email,
        username: data.username,
        is_admin: data.is_admin,
      };
    } catch {
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

api.interceptors.response.use(async (response) => {
  const original = response.config as typeof response.config & { _retry?: boolean };
  const isUnauthorized = response.data?.success === false && response.data?.error === 'unauthorized';

  if (!isUnauthorized || original._retry) {
    return response;
  }

  original._retry = true;
  const refreshedUser = await performRefresh();

  if (!refreshedUser) {
    tokenStore.set(null);
    localStorage.removeItem('refresh_token');
    window.location.href = '/login';
    return response;
  }

  return api(original);
});
