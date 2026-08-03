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

// Auto-refresh on 401 — queue concurrent requests while refreshing
let isRefreshing = false;
let pendingQueue: Array<{ resolve: () => void; reject: (e: unknown) => void }> = [];

// Registered by AuthContext so the interceptor can trigger a logout
// without importing AuthContext (avoids circular dependency)
let onAuthFailure: (() => void) | null = null;
export function setOnAuthFailure(cb: () => void): void {
  onAuthFailure = cb;
}

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;

    if (error.response?.status !== 401 || original._retry) {
      return Promise.reject(error);
    }
    original._retry = true;

    if (isRefreshing) {
      return new Promise<void>((resolve, reject) => {
        pendingQueue.push({ resolve, reject });
      }).then(() => api(original));
    }

    isRefreshing = true;
    try {
      const refreshToken = await getRefreshToken();
      const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
        refresh_token: refreshToken,
      });
      await saveTokens(data.access_token, data.refresh_token);
      pendingQueue.forEach((p) => p.resolve());
      return api(original);
    } catch (e) {
      pendingQueue.forEach((p) => p.reject(e));
      await clearTokens();
      onAuthFailure?.();
      return Promise.reject(error);
    } finally {
      pendingQueue = [];
      isRefreshing = false;
    }
  }
);
