import axios from 'axios';
import { tokenStore } from './tokenStore';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000';

export const api = axios.create({ baseURL: BASE_URL });

let refreshPromise: Promise<string> | null = null;

api.interceptors.request.use((cfg) => {
  const token = tokenStore.get();
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const original = err.config;
    if (err.response?.status !== 401 || original._retry) {
      return Promise.reject(err);
    }
    original._retry = true;

    try {
      if (!refreshPromise) {
        const storedRefresh = localStorage.getItem('refresh_token');
        if (!storedRefresh) return Promise.reject(err);

        refreshPromise = api
          .post<{ access_token: string; refresh_token: string }>('/auth/refresh', {
            refresh_token: storedRefresh,
          })
          .then((r) => {
            tokenStore.set(r.data.access_token);
            localStorage.setItem('refresh_token', r.data.refresh_token);
            return r.data.access_token;
          })
          .finally(() => { refreshPromise = null; });
      }

      const newToken = await refreshPromise;
      original.headers.Authorization = `Bearer ${newToken}`;
      return api(original);
    } catch {
      tokenStore.set(null);
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      return Promise.reject(err);
    }
  },
);
