import axios from 'axios';
import { getAccessToken, getRefreshToken, saveTokens, clearTokens } from '../auth/storage';

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://localhost:3000';

export const api = axios.create({ baseURL: BASE_URL });

// Attach Bearer token to every outgoing request
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Registered by AuthContext so the interceptor can trigger a logout
// without importing AuthContext (avoids circular dependency)
let onAuthFailure: (() => void) | null = null;
export function setOnAuthFailure(cb: () => void): void {
  onAuthFailure = cb;
}

// The backend always answers HTTP 200; success/failure lives in the
// response body (`{success, message, error?}`). Axios therefore never
// rejects for business-logic failures (wrong password, validation errors,
// blocked, ...) — only for genuine network failures. The token-refresh
// trigger has to live in the *success* handler, keyed off
// `data.error === 'unauthorized'` rather than a 401 status code.
//
// Concurrent requests that all expire at once share a single in-flight
// refresh via `refreshPromise` instead of a manual queue — every caller
// just awaits the same promise and gets the same true/false outcome. This
// is also structurally immune to a deadlock the old status-code-based
// version was exposed to: /auth/refresh's own failure codes
// (session_not_found, session_expired, invalid_token, ...) are never
// `unauthorized` — that code only ever comes from the `authenticate`
// middleware, which /auth/refresh doesn't go through — so a failing
// refresh call can't recurse back into this same trigger.
let refreshPromise: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const refreshToken = await getRefreshToken();
      if (!refreshToken) return false;

      const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });
      if (!data.success) return false;

      await saveTokens(data.access_token, data.refresh_token);
      return true;
    } catch {
      return false;
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
  const refreshed = await performRefresh();

  if (!refreshed) {
    await clearTokens();
    onAuthFailure?.();
    return response;
  }

  return api(original);
});
