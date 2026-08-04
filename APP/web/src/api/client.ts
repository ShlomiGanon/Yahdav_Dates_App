import axios from 'axios';
import { createAuthApi }  from '@shared/api/auth';
import { createUsersApi } from '@shared/api/users';
import { createChatApi }  from '@shared/api/chat';
import { webTokenStorage } from '../auth/storage';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000';

export const axiosClient = axios.create({ baseURL: BASE_URL });

// ── Request interceptor — attach current access token ─────────────────────
axiosClient.interceptors.request.use((config) =>
{
    const token = webTokenStorage.getAccessToken();

    if (token)
    {
        config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
});

// ── Response interceptor — auto-refresh on 401 ────────────────────────────
let _isRefreshing      = false;
let _pendingQueue: Array<() => void> = [];

axiosClient.interceptors.response.use(
    (response) => response,
    async (error) =>
    {
        const originalRequest = error.config;

        if (error.response?.status !== 401 || originalRequest._retry)
        {
            return Promise.reject(error);
        }

        if (_isRefreshing)
        {
            return new Promise((resolve) =>
            {
                _pendingQueue.push(() => resolve(axiosClient(originalRequest)));
            });
        }

        originalRequest._retry = true;
        _isRefreshing = true;

        try
        {
            const stored = webTokenStorage.getRefreshToken();

            if (!stored)
            {
                throw new Error('no refresh token stored');
            }

            const { data } = await axiosClient.post('/auth/refresh', { refresh_token: stored });

            webTokenStorage.setAccessToken(data.access_token);
            webTokenStorage.setRefreshToken(data.refresh_token);

            axiosClient.defaults.headers.common.Authorization = `Bearer ${data.access_token}`;

            _pendingQueue.forEach((fn) => fn());
            _pendingQueue = [];

            return axiosClient(originalRequest);
        }
        catch (refreshError)
        {
            webTokenStorage.clear();
            window.location.href = '/login';
            return Promise.reject(refreshError);
        }
        finally
        {
            _isRefreshing = false;
        }
    },
);

// ── Typed API singletons ──────────────────────────────────────────────────
export const authApi  = createAuthApi(axiosClient);
export const usersApi = createUsersApi(axiosClient);
export const chatApi  = createChatApi(axiosClient);
